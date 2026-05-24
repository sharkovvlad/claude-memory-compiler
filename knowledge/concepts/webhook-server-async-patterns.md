---
title: "Webhook Server Async Patterns — concurrency + performance"
aliases: [per-tid-lock, asyncio-gather-parallel, pre-delete-legacy-forward, webhook-concurrency]
tags: [python, performance, concurrency, webhook, architecture, asyncio]
sources:
  - "daily/2026-05-08.md"
created: 2026-05-08
updated: 2026-05-08
---

# Webhook Server Async Patterns

Три паттерна конкурентности и производительности в `webhook_server.py`, обнаруженных и починенных 2026-05-08 после серии UAT-тестов с деплоями. Все три — pre-existing проблемы, ставшие видимыми при ускорении turnaround (TD-#16 → TD-#17 → TD-#18 каскад).

## Key Points

- **TD-#16 `asyncio.gather` parallel delete+send:** `delete_and_send_new` стратегия делала sequential `await delete` + `await send` (~120-200ms overhead). Замена на `asyncio.gather(return_exceptions=True)` — p50 reply-button 323ms → 180ms (−143ms, экономия ~44%).
- **TD-#17 Per-tid `asyncio.Lock`:** два concurrent `_route_or_forward` task'а для одного `chat_id` оба читали stale `last_bot_message_id` → оба пытались удалить тот же mid → second WARNING + orphaned bubble. Fix: `_user_locks: dict[int, asyncio.Lock]` → `_route_or_forward_locked` под per-user lock.
- **TD-#18 Pre-delete for legacy forward:** кнопка «Добавить еду» fallthrough'ила в legacy n8n без удаления текущего menu → чат накапливал stale dashboards. Fix: `_maybe_pre_delete_for_add_food` fire-and-forget перед `forward_to_n8n`.
- **Каскад открытий:** TD-#16 (faster turnaround) расширил окно гонки → TD-#17 стал видимым. TD-#17 fix (serialization) открыл visual cleanup → TD-#18 стал очевидным.

## Details

### TD-#16 — `asyncio.gather` для параллельного delete + send

**Проблема:** `services/telegram_send.py` для стратегии `delete_and_send_new` делал sequential await:

```python
# До (sequential, ~120-200ms overhead):
await _post('deleteMessage', {'chat_id': cid, 'message_id': old_mid})
result = await _post('sendMessage', {'chat_id': cid, 'text': text, ...})
```

Каждый HTTP round-trip к Telegram API ~60-100ms. Два последовательных = 120-200ms. Для reply-button clicks (которые всегда `delete_and_send_new`) это ощутимая задержка.

**Fix (PR #22):**

```python
async def _delete_and_send_parallel(chat_id, old_mid, send_params):
    delete_coro = _post('deleteMessage', {'chat_id': chat_id, 'message_id': old_mid})
    send_coro = _post('sendMessage', send_params)
    results = await asyncio.gather(delete_coro, send_coro, return_exceptions=True)
    # delete failure (stale mid) — silently ignored
    # send failure — propagated
    if isinstance(results[1], Exception):
        raise results[1]
    return results[1]  # SendResult from sendMessage
```

Применён к двум paths:
- `delete_and_send_new` стратегия (основной)
- `edit_existing` HTTP-400 fallback path (когда editMessageText fails с «inline keyboard expected»)

**Измерения (prod, n=65 reply-text logs after deploy 15:36 MSK):** p50 **323ms → 180ms** (−143ms).

**Тесты:** 3 новых (parallelism regression-guard <80ms, gather + delete-fail, gather + send-fail). Full suite 31/31 passed.

### TD-#17 — Per-tid `asyncio.Lock`

**Проблема:** после TD-#16 (faster turnaround = шире окно гонки) стал виден race condition. Два concurrent Telegram webhook'а от одного юзера (double-tap reply-button, Telegram retry) оба входили в `_route_or_forward` параллельно:

```
T+0ms  task_1: SELECT last_bot_message_id → mid=4913
T+1ms  task_2: SELECT last_bot_message_id → mid=4913  (same stale value!)
T+60ms task_1: deleteMessage(4913) → ok
T+61ms task_2: deleteMessage(4913) → WARNING "message not found"
T+120ms task_1: sendMessage → mid=4920, save_bot_message(4920)
T+121ms task_2: sendMessage → mid=4921, save_bot_message(4921) ← overwrites!
```

Результат: юзер видит два сообщения (4920 orphaned + 4921 актуальное). One Menu UX нарушен.

**Fix (PR #24):**

```python
_user_locks: dict[int, asyncio.Lock] = {}

def _get_user_lock(chat_id: int) -> asyncio.Lock:
    if chat_id not in _user_locks:
        _user_locks[chat_id] = asyncio.Lock()
    return _user_locks[chat_id]

async def _route_or_forward(update, body, fwd_hdr, t0):
    chat_id = _extract_chat_id(update)
    if chat_id is None:
        await _route_or_forward_locked(update, body, fwd_hdr, t0)
        return
    async with _get_user_lock(chat_id):
        await _route_or_forward_locked(update, body, fwd_hdr, t0)
```

Разные `telegram_id` продолжают обрабатываться параллельно. Только один и тот же юзер сериализуется.

**Тесты:** 4/4 (same-tid serialization, different-tid parallelism, chat_id=None bypass, lock-release on exception). Full suite 426 passed.

**Edge case — memory leak:** `_user_locks` растёт по мере новых юзеров. Для NOMS (десятки юзеров) — negligible. При 100k+ юзеров потребуется LRU eviction или WeakValueDictionary. Текущая оценка: 1 Lock = ~200 bytes → 1000 unique users = 200 KB.

### TD-#18 — Pre-delete menu для legacy forward

**Проблема:** кнопка «🍽 Добавить еду» reply-keyboard fallthrough'ит в legacy n8n (`03_AI_Engine`), который шлёт «📸 Send a photo» без предварительного удаления текущего меню (Profile/Stats/Progress). Чат накапливает stale dashboards.

**Root cause:** legacy n8n не вызывает `save_bot_message` и не делает `deleteMessage` предыдущего menu (это задокументировано в [[concepts/save-bot-message-contract]]). Починить legacy — отдельная Phase 6.4 задача.

**Fix (PR #25) — bridge-паттерн:**

```python
async def _maybe_pre_delete_for_add_food(update, ctx):
    """Fire-and-forget: delete prior menu before forwarding to legacy n8n."""
    text = (update.get('message') or {}).get('text', '')
    icon = ctx.constants.get('icon_add_food', '🍽')
    if not text.startswith(icon):
        return
    mid = ctx.last_bot_message_id
    if not mid or not isinstance(mid, int) or mid <= 0:
        return
    try:
        await _post('deleteMessage', {'chat_id': ctx.telegram_id, 'message_id': mid})
    except Exception:
        pass  # silent — n8n forward continues regardless
```

Вызывается **под TD-#17 lock** (race-free) перед `forward_to_n8n`. Fire-and-forget по семантике (n8n forward всегда продолжается), но по execution — sequential благодаря lock.

**Тесты:** 7/7 (canonical path + 6 silent-bail edges). Full suite 433 passed.

**Obsolescence:** helper станет ненужным после Phase 6.4+ (миграция `03_AI_Engine` в Python).

## Архитектурные принципы

### 1. gather > sequential для independent I/O

Когда два HTTP-вызова независимы (delete предыдущего + send нового), `asyncio.gather` сокращает wall-time на ~50%. Исключения обрабатываются через `return_exceptions=True` + post-check.

### 2. Per-user lock для state-dependent operations

Если операция читает user-state → mutates → writes, и могут быть concurrent requests от одного юзера (Telegram double-tap, retry) — per-user asyncio.Lock. НЕ global lock (блокирует всех). НЕ без lock (race condition).

### 3. Bridge-pattern для legacy gaps

Когда legacy flow не соблюдает контракт (например, One Menu UX) и полная миграция — отдельный спринт, bridge-helper на Python-стороне закрывает gap. Всегда fire-and-forget + swallow-every-error чтобы не сломать основной legacy path.

## Performance timeline (2026-05-08 evening)

| Момент | Reply-button p50 | Что изменилось |
|---|---|---|
| До TD-#16 | 323 ms | Sequential delete+send |
| После TD-#16 (PR #22) | **180 ms** | `asyncio.gather` parallel |
| После TD-#17 (PR #24) | 180 ms | Lock не добавляет latency (< 1ms acquire) |
| После TD-#18 (PR #25) | 180 ms | Pre-delete ≤ 60ms, happens before forward |

Net improvement: **−143ms p50** для reply-buttons (−44%), при этом race condition устранён и One Menu UX соблюдается для legacy paths.

## Related Concepts

- [[concepts/one-menu-ux]] — `last_bot_message_id` + `save_bot_message` контракт, который эти паттерны защищают
- [[concepts/save-bot-message-contract]] — legacy n8n не вызывает save_bot_message (корень TD-#18)
- [[concepts/phase2-python-menu-v3]] — `_send_and_persist` helper использует эти паттерны
- [[concepts/telegram-proxy-indicator]] — fire-and-forget паттерн (прецедент для TD-#18 bridge)
- [[concepts/n8n-data-flow-patterns]] — `continueOnFail` pattern на стороне n8n (аналог swallow-error)

## Sources

- [[daily/2026-05-08.md]] — TD-#16 (PR #22): `asyncio.gather` для parallel delete+send, p50 323→180ms. TD-#17 (PR #24): per-tid asyncio.Lock, 4 теста, 426 passed. TD-#18 (PR #25): `_maybe_pre_delete_for_add_food` bridge-helper, 7 тестов, 433 passed. Каскадное обнаружение трёх связанных проблем в одной evening session.
