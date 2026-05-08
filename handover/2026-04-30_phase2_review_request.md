# Phase 2 (n8n→Python migration, menu_v3 handler) — Review Request

**Дата:** 2026-04-30
**Автор:** Claude Opus 4.7 (PM-агент Phase 2)
**Адресат:** другой ИИ-ревьюер (для второго мнения)
**Статус:** работа завершена, ветка `claude/phase2-menu-v3` запушена, **не замерджена**, **не задеплоена**.
**Цель документа:** передать всё, что я думал, делал, выбирал, и где сомневаюсь — чтобы другой ИИ мог прийти со свежим взглядом и либо подтвердить, либо оспорить решения.

---

## 0. TL;DR (одна страница)

NOMS — Telegram-бот для трекинга питания. Стек: n8n (workflow-оркестратор) + Supabase PostgreSQL (вся бизнес-логика в RPC) + Python (FastAPI webhook proxy + APScheduler cron).

**Проблема:** end-to-end latency клика в боте ~1.8 секунды. Профилирование показало, что чистый SQL занимает ~46ms (RTT 44ms + RPC ~2ms), а ~1700ms теряется в **n8n internal overhead** — каждая node добавляет 30-80ms, а 04_Menu_v3 + 01_Dispatcher вместе содержат десятки HTTP/Code/IF nodes.

**Решение Phase 2:** реализовать на Python нативный обработчик `handle_menu_v3()`, который заменит n8n workflow `04_Menu_v3` для всех маршрутов с `target=menu_v3` (Profile, Settings, Progress, Shop, Friends, Quests, League, Ambassador Payout user side, Edit pickers — большинство меню-кликов).

**Результат:**
- 322 строки кода + 611 строк тестов + 137 строк бенчмарка + 67 строк добавлено в webhook_server.py.
- 35 новых pytest кейсов, 170/170 всего зелёные, mypy --strict clean.
- Бенчмарк (Hetzner→Supabase, persistent psycopg2): p50=45-48ms, p95=48-266ms (один cold-cache outlier).
- Ожидаемая E2E после флипа флага: **60-90ms vs текущие 1800ms** (≈20-30× ускорение).
- Под feature flag `HANDLER_MENU_V3_USE_PYTHON` (по умолчанию OFF). При любой ошибке Python-пути — fallthrough на старый n8n forward.

**Что я хочу проверить ревью:**
1. Корректно ли я использую SQL bundle `dispatch_with_render` как единственную точку входа?
2. Правильно ли построен payload / cb_context / action_type?
3. Не упустил ли я критичный edge case?
4. Безопасна ли стратегия rollout (флаг + fallthrough)?
5. Стоит ли что-то делать иначе?

---

## 1. Контекст: где это в общем плане

### 1.1 Что такое NOMS-бот (минимум)

- ~5000 пользователей, 13 языков, Telegram-бот
- Каждый клик: пользователь нажимает кнопку → Telegram → webhook на VPS Hetzner (FastAPI :8443) → forward в n8n (self-hosted на том же VPS) → n8n зовёт Supabase RPC → ответ обратно в Telegram
- Архитектурный принцип "RPC-First" (зафиксирован в CLAUDE.md): **вся** бизнес-логика в SQL функциях. Python и n8n — оркестраторы.
- "Headless Architecture" (миграции 130+): SQL RPC `process_user_input` принимает action_type и payload, обновляет state, и через `render_screen` возвращает готовый `telegram_ui` (текст + reply_markup + render_strategy). n8n должен был быть тонким транспортом, но там разрослись HTTP Request nodes для одного только дебаунса/логгирования/синхронизации.

### 1.2 Migration roadmap (Variant C из `groovy-marinating-eclipse.md`)

| Phase | Что | Status |
|---|---|---|
| 0.5 | Контракты `services/envelope.py`, `services/telegram_send.py`, `services/render.py`, `services/nav_stack.py` | shipped |
| 1 | `dispatcher/router.py` (Python-порт n8n Route Classifier v1.8), `dispatcher/context.py`, `dispatcher/shadow.py` (observation-only) | shipped |
| **2** | **`handlers/menu_v3.py`** — заменяет n8n `04_Menu_v3` | **этот PR** |
| 3 | `handlers/edit_stats_daily.py` — заменяет n8n `04.2_Edit_StatsDaily` | pending |
| 4 | `handlers/onboarding.py`, `handlers/location.py`, `handlers/payment.py`, `handlers/ai_engine.py` | pending |
| 5 | Finalize: убрать n8n forward, депрекировать workflows | pending |

Phase 2 — самая большая по объёму обрабатываемых маршрутов (Profile + Settings + Shop + Friends + Quests + League + Edit pickers + Ambassador Payout user side ≈ 60% callback'ов).

### 1.3 SQL bundle, на который я опираюсь

Migration 149 (`dispatch_with_render_bundle.sql`) ввёл RPC:

```sql
dispatch_with_render(
    p_telegram_id BIGINT,
    p_action_type TEXT,         -- 'callback' | 'text' | 'photo' | 'voice' | 'location'
    p_payload JSONB,             -- {"callback_data": "..."} or {"text": "..."} etc.
    p_cb_context JSONB DEFAULT '{}',  -- {"is_inline": bool, "callback_query_id": "..."}
    p_skip_debounce BOOLEAN DEFAULT FALSE
) RETURNS JSONB
```

Возвращает один из:
- `{status: 'render', screen_id, telegram_ui: {render_strategy, chat_id, message_id?, text, parse_mode, reply_markup, extra_items}, business_data, bundle, meta}`
- `{status: 'debounced', cooldown_remaining_ms, bundle}`
- `{status: 'forward', forward_to, payload, bundle}` — для /start → onboarding, **не должно случаться** для menu_v3
- `{status: 'validation_error', error_key, retry_screen_id, bundle}`
- `{status: 'error', error_code, details, bundle}`

Это тонкая обёртка над `process_user_input` (которая внутри уже зовёт `render_screen`), плюс defensive fallback на прямой `render_screen` если `telegram_ui` пустое.

**Ключевое:** один RPC roundtrip даёт всё, что нужно для отправки в Telegram. Это и есть архитектурный фундамент Phase 2.

---

## 2. Что построено

### 2.1 `handlers/menu_v3.py` (322 строки)

Один публичный async-функция:
```python
async def handle_menu_v3(
    update: dict[str, Any],
    ctx: UserCtx,
    decision: RouteDecision,
    *,
    rpc_caller: Any = None,
) -> ResponseEnvelope
```

#### Алгоритм

1. **Build payload** (`_build_payload`):
   - Если `decision.is_callback` → `{"callback_data": decision.callback_data}`
   - Иначе если `decision.synth_callback` (reply-keyboard кнопка → синтетический callback) → `{"callback_data": decision.synth_callback}`
   - Иначе если `decision.is_text` → `{"text": decision.text}`
   - Если есть `has_photo` → добавить `"photo": [...]` из update.message
   - Аналогично voice / location

2. **Build cb_context** (`_build_cb_context`):
   - Базируется на `decision.cb_context` (если router его установил, например `{"is_inline": False}` для синтетика)
   - Если `is_inline` не установлен — выводим: `decision.is_callback AND NOT decision.synth_callback`. То есть inline-button = True, reply-kb синтетик = False. Это критично для миграции 153 (wipe nav_stack для всех reply-kb root callbacks).
   - Добавляем `callback_query_id` и `callback_message_id` если есть (для ACQ и edit_existing на SQL стороне).

3. **Resolve action_type** (`_resolve_action_type`):
   - is_callback OR synth_callback → "callback"
   - has_photo → "photo", has_voice → "voice", has_location → "location"
   - Иначе → "text"

4. **RPC call**:
   ```python
   rpc_result = await rpc_caller("dispatch_with_render", {
       "p_telegram_id": ctx.telegram_id,
       "p_action_type": action_type,
       "p_payload": payload,
       "p_cb_context": cb_context,
       "p_skip_debounce": False,
   })
   ```

5. **Defensive parsing**:
   - None → `_error_envelope(code="rpc_returned_null")`
   - List-wrapped (Supabase REST иногда оборачивает single-JSONB в массив) → unwrap
   - Не dict → `_error_envelope(code="rpc_unexpected_shape")`

6. **Status dispatch** (`_envelope_from_rpc_result`):
   - `debounced` + есть callback_query_id → одиночный `answer_callback_only` item (убрать спиннер) + `flags["debounced"]=True`
   - `debounced` без callback_query_id → пустой envelope
   - `validation_error` → `_validation_error_envelope`: ACQ + send_new с локализованным текстом из `error_key` (поиск через dotted-path в `ctx.translations`), fallback на русский литерал "⚠️ Что-то пошло не так..."
   - `forward` → log warning + пустой envelope (для menu_v3 не должно быть)
   - `error` (или unknown status) → `_error_envelope`: ACQ + send_new с `errors.generic`
   - `render` без `telegram_ui` → `_error_envelope("render_no_telegram_ui")`
   - `render` нормально → переиспользую **существующий** `services.render.parse_render_response(telegram_ui)` (он уже умеет render_strategy, extra_items, next_state) → если decision.callback_query_id есть И в envelope нет answer_callback_only → **prepend** ACQ как первый item. Если уже есть (RPC сам положил в extra_items) — не дублируем.

#### Локализация ошибок (`_lookup_translation`)

Вспомогательная функция с dotted-path: `errors.generic`, `errors.validation_age_range` → ходит по `ctx.translations` dict. Возвращает None если ключа нет → fallback на русский литерал.

### 2.2 Тесты (`tests/handlers/test_menu_v3.py`, 611 строк, 35 кейсов)

Использую существующие фикстуры из `tests/conftest.py`: `make_user_ctx`, `sample_callback_update`, `sample_text_update`, `sample_photo_update`, `sample_voice_update`, `sample_location_update`. Везде `AsyncMock` для `rpc_caller`.

Покрытие:
1. **Render path inline callback** (`cmd_get_profile`) → ACQ FIRST, потом edit_existing
2. **Reply-kb synth (delete_and_send_new)** — One Menu pattern (миграция 153) — нет ACQ, потому что нет callback_query_id
3. **Debounced + callback_query_id** → только ACQ, `flags["debounced"]=True`
4. **Debounced без callback_query_id** → empty envelope
5. **Validation error** + локализованный error_key → ACQ + send_new с текстом из ctx.translations
6. **Generic error** → ACQ + send_new с errors.generic
7. **RPC None** → error envelope code "rpc_returned_null"
8. **RPC list-wrapped** → unwrap корректно
9. **RPC non-dict** → "rpc_unexpected_shape"
10. **Forward для menu_v3** → empty (с warning log)
11. **Render без telegram_ui** → "render_no_telegram_ui"
12. **action_type resolution** (parameterized): callback / synth_callback / photo / voice / location / text
13. **Payload для callback** — только callback_data
14. **Payload для text input** (например edit_weight numeric) — только text, action_type=="text"
15. **cb_context defaults** (parameterized): inline → is_inline=True; synth с router-cb_context → False сохранено
16. **callback_query_id passthrough в cb_context**
17. **callback_message_id passthrough**
18. **ACQ не дублируется** если RPC сам положил в extra_items
19. **RPC params shape sanity** (assert_awaited_once_with)
20. **Default rpc_caller** через monkeypatched supabase_client (sys.modules injection — caveat ниже)
21. **Translations missing → fallback** на русский литерал
22. **extra_items propagation** через parse_render_response
23. **next_state propagation** в envelope.next_state
24. (+ ещё около 12 параметризованных под-кейсов)

### 2.3 Бенчмарк (`tests/handlers/bench_menu_v3.py`, 137 строк)

Standalone runnable script, **не pytest** (префикс `bench_`).
- Persistent `psycopg2.connect()` ОДИН раз перед циклом, реюз cursor
- 15 итераций для каждого из 4 callback'ов: cmd_get_stats, cmd_settings, cmd_buy_freeze, cmd_back
- `p_skip_debounce=TRUE` (иначе повторные дебаунсятся)
- Admin tid=417002669 (тот же, что в migration 149 verify-block)
- p50/p95 через sorted-list nearest-rank (без numpy)
- SELECT 1 baseline для RTT-сравнения
- Header docstring с командой запуска через ssh на VPS

### 2.4 Webhook integration (`webhook_server.py`, +67 строк)

```python
HANDLER_MENU_V3_USE_PYTHON = os.getenv("HANDLER_MENU_V3_USE_PYTHON", "").lower() in (
    "1", "true", "yes", "on",
)
```

В `telegram_webhook` ПЕРЕД `forward_to_n8n`:
```python
if HANDLER_MENU_V3_USE_PYTHON:
    chat_id = _extract_chat_id_from_update(update)
    if chat_id is not None:
        try:
            ctx = await get_user_context(chat_id)
            decision = route_update(update, ctx)
            if decision.target == "menu_v3" and ctx is not None:
                asyncio.create_task(maybe_send_indicator(update))
                asyncio.create_task(maybe_sync_user_profile(update))
                envelope = await handle_menu_v3(update, ctx, decision)
                asyncio.create_task(telegram_send(envelope))
                return Response(status_code=200)
        except Exception:
            logger.exception("menu_v3 handler error tid=%s — falling through to n8n", chat_id)
# fall-through: original n8n forward path unchanged (n8n продолжает работать как сейчас)
```

Принципы:
- Флаг по умолчанию OFF — нулевой риск при merge
- Любой exception → fallthrough на n8n (n8n путь НЕ удалён)
- `telegram_send(envelope)` запускается через `create_task` чтобы webhook отвечал Telegram'у в <10ms (не блокировать ack)
- Indicator + profile sync продолжают работать
- Только когда target ИМЕННО menu_v3 — Python берёт верх. Все остальные пути (onboarding, ai, location, menu legacy, payment) идут через n8n как раньше

---

## 3. Архитектурные решения и trade-offs

### 3.1 Почему bundle `dispatch_with_render`, а не отдельные `process_user_input` + `render_screen`?

**Спецификация явно указала использовать bundle.** Альтернатива (старый путь) — два RPC roundtrip'а: pui для state + render для UI. Bundle экономит один RTT (~44ms) без потери семантики, потому что pui уже зовёт render внутри в render-status.

Bundle также tag'ает результат `bundle: "dispatch_with_render"` — полезно для observability в логах Supabase.

**Trade-off:** если когда-то понадобится изменить state без рендера (silent SQL ops), bundle не подходит. Но для menu_v3 это не нужно — каждый клик по умолчанию рендерит.

### 3.2 Почему я переиспользую `services.render.parse_render_response`, а не пишу свой парсер telegram_ui?

`telegram_ui` внутри dispatch_with_render возвращает **точно такую же** форму, что и `render_screen` (миграция 149 это явно гарантирует). Существующий `parse_render_response` уже:
- разбирает render_strategy, chat_id, message_id, text, parse_mode, reply_markup, sticker_id, callback_query_id, callback_alert_text, callback_show_alert
- обрабатывает extra_items (fan-out)
- propagate-ит next_state
- даунгрейдит unknown strategy в noop

Дублировать это было бы анти-DRY и опасно (два места для багов). Экономия ~30 строк.

**Trade-off:** связал menu_v3 с эволюцией render.py. Но render.py — frozen контракт Phase 0.5, его не должны менять часто.

### 3.3 Почему ACQ prepend (FIRST), а не append?

Если сначала отправить editMessageText, а потом answerCallbackQuery — пользователь видит **сначала** обновление текста, **потом** убирается спиннер на кнопке. На UX это выглядит как заметная задержка.

Если сначала ACQ, потом edit — спиннер исчезает мгновенно, потом плавно обновляется содержимое. Гладкий UX.

ВАЖНО: `services.telegram_send.send()` обрабатывает items **строго последовательно** (см. строки 143-153 telegram_send.py: `for item in envelope.items`). Так что порядок в `envelope.items` определяет порядок Bot API calls.

### 3.4 Почему `asyncio.create_task(telegram_send(envelope))` а не await?

Webhook должен ack-нуть Telegram за <10ms. Если await отправку — webhook ждёт всех Bot API calls (~100-300ms суммарно). Telegram повторит запрос если не получил 200 за ~30 секунд, но если ack'аем медленно — webhook очередь забивается.

Существующий код для `forward_to_n8n` использует тот же паттерн (`asyncio.create_task` без await). Я следую ему.

**Trade-off:** если `telegram_send` упадёт — webhook уже вернул 200, ошибка только в логах. Но это приемлемо — она автоматически попадёт в `telegram_send.SendResult.errors`, я могу добавить мониторинг позже.

### 3.5 Почему feature flag, а не straight cutover?

CLAUDE.md и общий принцип "deploy-test-fix loop" требуют осторожности с production. Phase 2 — крупное изменение (60% callback трафика). Слепой merge → возможные регрессии для всех users.

Флаг даёт:
1. Merge без риска (OFF по умолчанию)
2. Юзер сам решает когда включить (после своего ревью)
3. Откат = `unset` env + restart, без revert commit
4. Можно включить только на VPS (admin tid 417002669) для smoke test, потом всем

**Trade-off:** дополнительная сложность в webhook_server.py. Но 67 строк — приемлемо.

### 3.6 Почему fallthrough, а не fail-fast?

При exception в Python пути → пользователь получает ошибку, потом ещё n8n обработает тот же update (если бы не было fallthrough — пользователь видит молчание). С fallthrough — пользователь получает n8n ответ как раньше + я вижу ошибку в логах. Это safety net.

**Trade-off:** возможны двойные ответы если Python успел отправить часть items. На практике если exception — ничего не успело отправиться, потому что envelope создаётся ПЕРЕД `create_task(telegram_send)`. Но если exception в самом `_envelope_from_rpc_result` после успешного RPC — может быть double work на SQL стороне (process_user_input уже пробежал, n8n снова его вызовет). Дебаунс защитит от двойного render благодаря 500ms окну (миграция 140).

### 3.7 Почему `_extract_chat_id_from_update` дублирован, а не импортирован из `dispatcher.shadow`?

В shadow.py он назван `_extract_chat_id` (private, prefixed underscore). Импортировать private symbols — анти-паттерн. Альтернатива — extract в общий `dispatcher/utils.py`. Решил дублировать (~15 строк) ради чистого import surface.

**Trade-off:** если будем добавлять обработчики в Phase 3+, надо вынести в utils. Можно сделать в Phase 3.

### 3.8 Почему синтетический callback (`synth_callback`) обрабатывается отдельно от `is_callback`?

Router (`dispatcher/router.py`) при reply-keyboard клике на кнопку "Профиль" / "Мой день" / "Прогресс" не имеет настоящего callback_query — Telegram прислал просто текст. Router определяет, что текст содержит icon_profile, и устанавливает `decision.synth_callback = "cmd_get_profile"` + `decision.is_callback = False` + `decision.cb_context = {"is_inline": False}`.

На SQL стороне миграция 153 wipe-ит nav_stack для всех таких "go home" кликов (is_inline=False). Если бы я при синтетике поставил `is_inline=True` — стек бы не очистился, "Назад" бы вёл не туда.

Также для синтетики **нет callback_query_id** → не нужно ACQ. Это естественно работает: в моём коде `if decision.callback_query_id: prepend ACQ`.

### 3.9 Почему я положил `ctx is not None` проверку в webhook?

Если юзер впервые пишет боту — `get_user_context` вернёт None (нет строки в users). В legacy n8n flow это обрабатывается через "Auto Create User" branch. Phase 2 не реализует создание юзера — это onboarding flow (Phase 4). Поэтому если ctx None → fallthrough на n8n, n8n создаст юзера и обработает.

---

## 4. Validation results

### 4.1 pytest

```
collected 170 items
...
============================== 170 passed in 0.20s ==============================
```

Все 35 новых кейсов в `tests/handlers/test_menu_v3.py` зелёные. Существующие 135 не сломаны. Никаких regression'ов.

### 4.2 mypy --strict

`mypy --strict handlers/menu_v3.py`:
- 0 ошибок в самом `handlers/menu_v3.py`
- 5 ошибок в `supabase_client.py` (foreign module, Phase 0.5 foundation, не входит в scope Phase 2). Это untyped functions / missing type args — known issue, не блокер.

### 4.3 Бенчмарк (на VPS Hetzner → Supabase EU pooler)

```
SELECT 1 baseline:    p50=42.4ms  p95=42.7ms

dispatch_with_render (skip_debounce=TRUE, 15 iterations each):
  cmd_get_stats:      p50=48.3ms  p95=265.8ms  ⚠️ один cold-cache outlier
  cmd_settings:       p50=45.0ms  p95=64.0ms
  cmd_buy_freeze:     p50=46.0ms  p95=51.9ms
  cmd_back:           p50=47.3ms  p95=48.1ms
```

CLAUDE.md baseline: `v_user_context` Hetzner→Supabase EU pooler RTT = 44 ms. Мой SELECT 1 показал 42.4 — в норме.

Все p95 < gate 700ms. Чистый SQL ~46ms = 44 RTT + 2ms сам RPC. После Python wrap (httpx + parse + envelope build): прогноз 60-90ms E2E vs текущие 1800ms.

**Аномалия cmd_get_stats p95=266ms** — единственный outlier, остальные 14 итераций были ~47ms. Гипотеза: cold cache в pg shared buffers (первый вызов после периода неактивности). Не блокер, но в watchlist.

### 4.4 Import sanity

`python3 -c "import webhook_server"` — clean import без ошибок. Подтверждает что добавленные импорты `dispatcher.context`, `dispatcher.router`, `handlers.menu_v3`, `services.telegram_send.send` все resolved.

---

## 5. Что я мог упустить (мои собственные сомнения)

### 5.1 Edge cases которые НЕ покрыл тестами

1. **edit_weight numeric input** с `decision.is_text=True`, `status=edit_weight` (router этот случай тоже ловит как target=menu_v3). Покрыто только генерально (test 14 — text decision → action_type=text). Не проверял что SQL сторона действительно принимает текст в action_type=text для edit_weight (полагаюсь на pre-existing работу router-теста).
2. **Multi-render через extra_items** для shop confirmations (например, "Купил Streak Freeze" → ACQ + edit_existing с обновлёнными NomsCoins + send_sticker с поздравлением). Я тестирую что extra_items propagate-ятся, но не end-to-end shop сценарий.
3. **Concurrent clicks на одного юзера** (debounce race). Полагаюсь на migration 148 (per-callback debounce) + 150 (idempotent). Не симулирую parallel.
4. **Network failure в `rpc_caller`** — что если httpx падает? `supabase_client.rpc` уже имеет retry с exponential backoff (config.MAX_RETRIES). Тест на это не написал. Если все retries падают → возвращает None → мой `_error_envelope("rpc_returned_null")` обрабатывает.

### 5.2 Архитектурные сомнения

**(a) Я не реализую `next_state` PATCH.**
Контракт ResponseEnvelope имеет поле `next_state` — handler может попросить router обновить `users.status`. Я **не** делаю PATCH в Phase 2 потому что `process_user_input` сам внутри SQL обновляет users.status (это часть transaction). Поэтому next_state в моём envelope нужно для observability, но не для эффекта.

В тестах я проверяю что next_state propagate-ится (test 23). Если потом окажется, что webhook должен PATCH-ить — это быстрая правка.

**(b) Я не вызываю `last_bot_message_id` save.**
Старый n8n путь после отправки сообщения сохранял Telegram message_id в users.last_bot_message_id (для One Menu — следующее меню удалит это сообщение). Я НЕ делаю это в Python — потому что `services.telegram_send.send()` сейчас не возвращает Telegram message_id наружу из responses.

Это работает потому что для большинства render strategy (`edit_existing`) ID не меняется (используется существующий). Но для `delete_and_send_new` (One Menu для reply-kb root jumps) и `send_new` — новый message_id ДОЛЖЕН сохраниться, иначе следующий menu jump удалит не то сообщение.

**Это потенциальный баг в моей реализации.** Но он inherited из текущего telegram_send.py — он не возвращает SendResult с message_ids. Чинить это надо в Phase 0.5/1 контракте.

**Workaround на сейчас:** SQL `process_user_input` уже сам обновляет `users.last_bot_message_id` для edit_existing path. Для send_new и delete_and_send_new — вероятно есть RPC `save_bot_message`. Старый n8n flow зовёт его в конце. Я **не зову** его. Это значит после Python flip, последовательность delete_and_send_new → клик на следующее меню → пытаемся удалить сохранённое в БД старое (несуществующее) → 400 error → fallthrough.

**ЭТО ПОТЕНЦИАЛЬНО БЛОКЕР ROLLOUT.** Нужно проверить с пользователем / реальным flow.

**(c) `SendResult` errors не сообщаются обратно.**
`telegram_send` возвращает `SendResult{sent, failed, errors}`, но я делаю `asyncio.create_task` без await — результат теряется. Если Bot API упадёт (rate limit / message not found) — не вижу. Можно добавить простой `_done_callback` для логирования.

### 5.3 Открытые вопросы к рассмотрению

1. **Как правильно обновлять `users.last_bot_message_id` после `send_new` / `delete_and_send_new`?** В n8n путь зовёт RPC `save_bot_message(p_telegram_id, p_message_id)`. Куда это положить в Python flow — внутри `telegram_send` (changes Phase 0.5 contract) или в отдельный handler step?

2. **Стоит ли await-ить `telegram_send` ради корректности?** Сейчас webhook ack-ает Telegram моментально, но если `telegram_send` падает — пользователь молчит (без n8n fallthrough, потому что мы уже return Response). Альтернатива: await `telegram_send`, но тогда webhook отвечает за 100-300ms вместо <10ms. Это в пределах 30-секундного timeout Telegram, но против существующего pattern.

3. **Что делать если `parse_render_response` вернёт пустой envelope (telegram_ui с unknown render_strategy)?** Сейчас items=[] и я не отправляю ничего, не показываю ошибку юзеру. Потенциально лучше бы показать generic error.

4. **Тест #20 (default rpc_caller через sys.modules injection) — flaky?** Если supabase_client уже импортирован в process до этого теста — мой monkeypatch не сработает. Subagent написал, я не валидировал глубоко. В CI может flake.

---

## 6. Inherited caveats (из live calibration, F2/F3/F4)

Эти проблемы существуют на SQL уровне. Мой Python handler наследует их 1:1 — он только проксирует payload в SQL. Чинить надо в SQL миграциях, не в Phase 2.

- **F2:** `cmd_league_info` / `cmd_buy_freeze` REPLACE стек вместо push parent. Когда юзер делает "Назад" — попадает не туда, куда ожидает.
- **F3:** mid-flow reply-kb push vs cold-flow wipe inconsistency. Одинаковый клик в разных контекстах ведёт к разному поведению стека.
- **F4:** spec drift — в CLAUDE.md написано `cmd_edit_lang`, `edit_timezone`, а в реальном коде/SQL `editing:lang`, `editing:timezone`. Не блокер, но требует sync.

См. `tests/live/CALIBRATION_REPORT.md` для деталей.

---

## 7. Рекомендуемые next steps (для юзера)

### Immediate (перед merge)
1. **Code review** Python кода — особенно `handle_menu_v3`, `_envelope_from_rpc_result`, `_build_cb_context`.
2. **Ответить на вопрос section 5.2.b** — нужно ли мне сохранять `last_bot_message_id` в Python? Если да — это блокер для merge, надо доработать.

### При rollout (после merge)
1. На VPS: добавить `HANDLER_MENU_V3_USE_PYTHON=1` в `.env` **только** для admin tid сначала (через какой-то отладочный whitelist? или просто включить и кликать самому).
2. `systemctl restart noms-webhooks noms-cron` (CLAUDE.md правило про оба сервиса!).
3. Smoke test: cmd_get_stats, cmd_settings, cmd_back, cmd_buy_freeze, cmd_get_profile, edit_weight.
4. Watch logs: `journalctl -u noms-webhooks -f | grep HANDLER_MENU_V3`.
5. Мониторить ack_ms — должны быть <10ms всегда. handler error логи должны быть пусты.

### После 24h наблюдения
- Если всё ок → выкатить на всех (флаг уже глобально).
- Если проблемы → unset флаг, restart, разбираться.

### После 7+ дней shadow-clean
- Удалить `forward_to_n8n` для menu_v3 routes (но оставить для других).
- Депрекировать workflow `04_Menu_v3` (id `0xJXA5M4wQUSiGXT`) на n8n — пометить inactive.

---

## 8. Альтернативные подходы (для второго мнения)

Это варианты, которые я **рассматривал** но **не выбрал**. Перечисляю чтобы ревьюер мог оспорить.

### 8.1 Не использовать bundle, а пойти через render.py
`services.render.render(telegram_id, screen_id, ctx)` уже существует. Я мог бы:
1. Вызвать `process_user_input` напрямую
2. Прочитать новый screen_id из результата
3. Вызвать `render(screen_id)` для получения envelope

**Почему отверг:** два RPC roundtrip'а вместо одного, никакой выгоды. Bundle спроектирован именно для этого случая.

### 8.2 Сделать handle_menu_v3 синхронным await
Вместо `asyncio.create_task(telegram_send(envelope))` — `await telegram_send(envelope)`.

**Trade-off:**
- Pro: SendResult видим, можем в случае failed → exception → fallthrough на n8n
- Con: webhook отвечает Telegram за 100-300ms, не <10ms

Решил оставить fire-and-forget потому что (а) consistent с существующим forward_to_n8n паттерном, (б) Telegram timeout 30s даёт большой запас, (в) при failed envelope items дебаунс уже упал в SQL, ретрай не поможет.

### 8.3 Один gigantic test файл vs split
Subagent сделал один файл 611 строк с 35 кейсами. Альтернатива — split на test_payload.py / test_envelope.py / test_status_handling.py.

**Почему оставил:** consistent с tests/dispatcher/test_router.py (один файл с 70+ кейсов). Удобно grep-ать.

### 8.4 Не переиспользовать parse_render_response
Написать свой парсер telegram_ui inside menu_v3.py, без зависимости на render.py.

**Почему отверг:** DRY-нарушение. render.py — Phase 0.5 frozen контракт, его и так не должны трогать.

### 8.5 Cutover без feature flag
Удалить forward_to_n8n для menu_v3 directly.

**Почему отверг:** слишком рискованно для 60% трафика. CLAUDE.md тоже требует осторожности.

---

## 9. Что я бы спросил у ИИ-ревьюера

Конкретные вопросы, на которые хочу второе мнение:

1. **Section 5.2.b** — `last_bot_message_id` save после send_new / delete_and_send_new. Это блокер? Где это лучше всего разместить — в `services.telegram_send.send`, в `handle_menu_v3`, или в отдельной post-send hook?

2. **Section 5.2.c** — `SendResult` с `failed > 0` сейчас не наблюдается. Стоит ли добавить простой `_done_callback` к `asyncio.create_task` для логирования или это premature optimization?

3. **Section 8.2** — стоит ли всё-таки await-ить `telegram_send` для лучшего контроля ошибок? Какие risks vs benefits?

4. **Тест #20** (default rpc_caller injection) — flaky-ли это в реальности? Стоит ли rewrite через `pytest.MonkeyPatch.setattr`?

5. **Cold-cache outlier cmd_get_stats p95=266ms** — это нормально (single sample, Russian roulette) или signal для materialized view? CLAUDE.md упоминает `my_plan` тоже имел 570ms outlier. Может быть pattern.

6. **Architecturally** — мой подход использовать ОДИН handler для всех menu_v3 callback'ов через bundle RPC. Альтернатива (более классическая) — диспатч таблица `cmd_get_profile → handler_profile`, `cmd_settings → handler_settings` etc. SQL делает это внутри `process_user_input`. Стоит ли мне в Python тоже расщепить, или RPC-first подход лучше?

7. **Безопасность fallthrough** — exception → n8n. Что если exception частичный (часть items успели отправиться)? Может ли быть double-send? Я считаю что нет, потому что envelope строится синхронно, отправка через `create_task` после return Response. Прав ли я?

8. **mypy errors в supabase_client.py** — я их игнорирую как foreign. Стоит ли всё-таки потратить 15 минут и починить? Это не входит в Phase 2 scope, но pollute-ит mypy output.

9. **Должен ли я сразу включить флаг для одного юзера** (admin tid 417002669), или это выходит за scope подготовки PR?

---

## 10. Locator файлов

Все артефакты в worktree `/Users/vladislav/Documents/NOMS/.claude/worktrees/vibrant-jackson-b27c62/`, ветка `claude/phase2-menu-v3`, коммит `e8c0c31`:

- `handlers/__init__.py` (0 строк, package marker)
- `handlers/menu_v3.py` (322 строки, основная логика)
- `tests/handlers/__init__.py` (0 строк)
- `tests/handlers/test_menu_v3.py` (611 строк, 35 кейсов)
- `tests/handlers/bench_menu_v3.py` (137 строк, latency bench)
- `webhook_server.py` (+67 строк, feature flag + early routing)

Foundation, на который опирается (НЕ менялось):
- `services/envelope.py` (контракт ResponseEnvelope)
- `services/telegram_send.py` (outbound dispatcher)
- `services/render.py` (parse_render_response переиспользуется)
- `dispatcher/context.py` (UserCtx + get_user_context)
- `dispatcher/router.py` (RouteDecision + route)
- `migrations/149_dispatch_with_render_bundle.sql` (SQL bundle)

KB-документ:
- `claude-memory-compiler/daily/2026-04-30.md` (дневной changelog)
- `claude-memory-compiler/handover/2026-04-30_phase2_review_request.md` (этот файл)

Deployment-related:
- VPS: 89.167.86.20 (Hetzner CX21, 2 vCPU, 3.7GB RAM, +2GB swap)
- Прод сервисы: `noms-webhooks` (FastAPI :8443), `noms-cron` (APScheduler)
- User: `taskbot`, WorkingDirectory: `/home/taskbot/noms`

PR ссылка: https://github.com/sharkovvlad/noms-bot/pull/new/claude/phase2-menu-v3

---

## 11. Ничего не упустил? Чек-лист

- [x] Контекст проекта (NOMS, n8n, RPC-first)
- [x] Migration roadmap и где Phase 2
- [x] Что построено — детально (handler + tests + bench + flag)
- [x] Все judgment calls с обоснованием
- [x] Все validation results (pytest, mypy, bench)
- [x] Inherited caveats F2/F3/F4
- [x] Открытые вопросы / сомнения (section 5)
- [x] Альтернативы (section 8)
- [x] Конкретные вопросы к ревьюеру (section 9)
- [x] Locator файлов
- [x] Deployment plan
- [x] Risk: last_bot_message_id потенциальный блокер (5.2.b)
- [x] Risk: SendResult ошибки не наблюдаются (5.2.c)
- [x] Cold-cache outlier на cmd_get_stats
- [x] Test #20 flake risk
- [x] Не задеплоено + почему
- [x] Не замерджено + почему

Если ИИ-ревьюер найдёт что-то ещё, что я не учёл — это ценно. Я закрываю эту сессию с пониманием что Phase 2 готова к ревью, но не претендую на 100% полноту анализа.
