---
title: "Telegram Proxy для мгновенного Typing Indicator"
aliases: [telegram-proxy, python-proxy-indicator, fast-indicator, webhook-proxy, indicator-latency]
tags: [python, fastapi, performance, architecture, telegram, indicator]
sources:
  - "daily/2026-04-21.md"
  - "daily/2026-04-22.md"
  - "daily/2026-04-25.md"
created: 2026-04-21
updated: 2026-04-25
---

# Telegram Proxy для мгновенного Typing Indicator

Python FastAPI proxy между Telegram и n8n для мгновенной доставки typing indicator (видеостикеров Noms). Telegram webhook переключен с n8n URL на Python (6-10ms ack). Индикатор отправляется параллельно с форвардингом в n8n — до начала обработки. Latency improvement: ~85% (1.5-2s → 400-500ms).

## Key Points

- **Архитектура:** Telegram → Python proxy (6-10ms ack) → [indicator fire-and-forget] + [forward to n8n]
- **Self-signed SSL:** `/etc/ssl/noms/` cert, Telegram `setWebhook` с `certificate` file — Telegram принимает self-signed при upload
- **Whitelist** определяет когда шлём indicator: menu-emoji / команды / флаги языков / callback_query / edit_* статусы
- **Sticker rotation:** 3 видеостикера + текстовый fallback (1 раз в день); выбор через `last_indicator_index` в БД
- **WebhookHealthCron:** каждую минуту проверяет `/telegram/health`, 3 фейла подряд → auto-fallback на n8n URL + admin alert
- **Migration 109:** `get_indicator_context()` + `save_indicator_state()` RPCs — атомарное управление состоянием индикатора
- **Phase 2:** удалены 4 ноды из 01_Dispatcher (Quick Status Check, Needs Indicator?, Send Indicator?, Send Early Indicator) — 57→53 нод

## Details

### Почему потребовался proxy

Исходная проблема: indicator в n8n стоял ПОСЛЕ `Get User Context` (Supabase, 100-300ms) в критическом пути. Попытка параллелизировать в n8n сломала удаление стикера: `06_Indicator_Clear` читает `last_bot_message_id` через RPC, но при параллельной схеме `save_indicator_state` не успевал до ответа AI (AI: 3-7s, save: 100ms — OK, но race condition при быстрых consecutive messages).

Python proxy решает это архитектурно: indicator отправляется **до** n8n, синхронно пишет `last_bot_message_id` в БД — AI всегда найдёт актуальный ID.

### Полный поток обработки

```
Telegram API
    ↓ POST /telegram/webhook
Python FastAPI (webhook_server.py)
    ↓ 200 OK (6-10ms)
    ├── background: maybe_send_indicator()
    │     ├── get_indicator_context(telegram_id) → (status, last_index, last_text_date, lang)
    │     ├── check whitelist: нужен ли indicator?
    │     ├── если да → send sticker/text
    │     └── save_indicator_state(telegram_id, message_id, new_index?, new_date?)
    └── background: forward raw body → n8n webhook URL
            ↓ n8n обрабатывает (Dispatcher, AI Engine, etc.)
            ↓ если надо удалить индикатор:
                06_Indicator_Clear → clear_bot_message() RPC
```

### Migration 109 — новые RPCs

`get_indicator_context(telegram_id BIGINT) → JSONB`:
- Читает: `status`, `last_indicator_index` (для ротации стикеров), `last_text_indicator_date` (один текстовый вариант в день), `language_code`
- Один round-trip вместо двух (было: get_user_context + отдельный save)

`save_indicator_state(telegram_id BIGINT, message_id BIGINT, new_index INT DEFAULT NULL, new_text_date DATE DEFAULT NULL) → VOID`:
- Атомарно: UPDATE `last_bot_message_id` + `last_indicator_index` + `last_text_indicator_date`
- Существующие `save_bot_message()` / `clear_bot_message()` НЕ тронуты — используются `03_AI_Engine` и `06_Indicator_Clear`

### SSL на VPS (self-signed cert)

```bash
# Создание cert
openssl req -x509 -newkey rsa:2048 -keyout /etc/ssl/noms/noms-webhook.key \
  -out /etc/ssl/noms/noms-webhook.pem -days 365 -nodes \
  -subj "/CN=89.167.86.20"

# Telegram setWebhook с upload cert
curl -F "certificate=@/etc/ssl/noms/noms-webhook.pem" \
  "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://89.167.86.20:8443/telegram/webhook"
```

Telegram принимает self-signed только через upload (не через URL). `webhook_server.py` запускается через uvicorn с `--ssl-keyfile --ssl-certfile`.

### Whitelist-логика (когда шлём indicator)

```python
INDICATOR_TRIGGERS = {
    # Главные кнопки меню
    'menu_emoji': ['☀️', '👤', '🚀', '📸', ...],
    # Команды
    'commands': ['/start', '/menu'],
    # Языковые флаги (онбординг)
    'language_flags': ['🇷🇺', '🇬🇧', '🇪🇸', ...],
    # Callback queries (все)
    'callbacks': True,
    # Edit-статусы (ожидаем текстовый ввод)
    'edit_statuses': ['edit_weight', 'edit_age', 'edit_height',
                      'registration_step_2', 'registration_step_3', 'registration_step_4', ...],
}
```

НЕ шлём indicator при: файлах без текста, стикерах, inline-answer и других нерелевантных входящих.

### Оптимизации latency

**Pre-warm cache на startup:**
```python
@app.on_event("startup")
async def startup_event():
    await _preload_stickers()      # file_ids из app_stickers
    await _preload_phrases()       # ui_translations для 13 языков
    # 955ms при старте → первый юзер не платит cold-cache цену
```

**Skip-translations для sticker-mode:**
```python
sticker_today = (last_text_date == today)
if sticker_today:
    await send_sticker(chat_id, get_sticker_id(idx))
    return  # phrases вообще не грузятся → экономия ~450ms
# Иначе → load phrases → send text
```

### Latency benchmarks

| Метрика | До proxy | После (steady state) | Улучшение |
|---|---|---|---|
| Ack Telegram | ~1s (n8n) | **6-10ms** | ~99% |
| Indicator delivered | ~1.5-2s | **~400-500ms** | ~75-80% |
| First call (cold cache) | ~2s | **~963ms** | ~50% |
| First call (prewarm) | ~2s | **~500ms** | ~75% |

**Совокупная экономия ~85%** vs baseline.

### WebhookHealthCron (auto-fallback)

```python
class WebhookHealthCron(BaseCron):
    fail_count = 0

    async def run(self):
        ok = await self._check_health()
        if not ok:
            self.fail_count += 1
            if self.fail_count >= 3:
                await self._fallback_to_n8n()
                await self._alert_admin()
                self.fail_count = 0
        else:
            self.fail_count = 0
```

Нет auto-flip-back (предотвращает flapping). Возврат на Python proxy — только ручной через rollback скрипт.

### Инцидент: параллельный агент переключил webhook (2026-04-21)

Между 15:27 и 15:40 параллельный агент вызвал `setWebhook` обратно на n8n URL (вероятно, деплой). n8n уже без indicator-нод (Phase 2 применена) → стикер не шёл вообще. Rollback обнаружен юзером, исправлен вручную.

**Рекомендация (open task):** добавить confirmation `y/n` или log каждого вызова `setWebhook` в `rollback_webhook.py`.

### 🚨 Критический инцидент: ANY PUT к 01_Dispatcher вытесняет proxy (2026-04-22)

**Обнаружено 2026-04-22:** любой `PUT /api/v1/workflows/6XzdbQqpoUG0nsLe` (01_Dispatcher — workflow с Telegram Trigger нодой) автоматически вызывает `setWebhook` на n8n.cloud URL. Это происходит при КАЖДОМ PUT — не только при deactivate/activate.

**Хронология 2026-04-22:** webhook потерян 5 раз за одну сессию:
- 4 раза от deactivate/activate при деплое
- 1 раз от чистого PUT без смены active статуса

**WebhookHealthCron** мониторит каждую минуту но НЕ делает auto-flip-back (предотвращает flapping). При 3 фейлах переключает на n8n URL как fallback.

**Команда восстановления:**

```bash
scp root@89.167.86.20:/etc/ssl/noms/noms-webhook.pem /tmp/
curl -F "url=https://89.167.86.20:8443/telegram/webhook" \
     -F "certificate=@/tmp/noms-webhook.pem" \
     -F "allowed_updates=[\"message\",\"callback_query\",\"pre_checkout_query\"]" \
     "https://api.telegram.org/bot<TOKEN>/setWebhook"
# Verify: curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo" | jq '.result.url'
```

**Обязательный протокол:** после КАЖДОГО PUT к 01_Dispatcher — восстанавливать webhook командой выше.

**Долгосрочные решения:**
- **Вариант A:** вынести Telegram Trigger в отдельный stub-workflow `00_TelegramReceiver` → тогда PUT к 01_Dispatcher не трогает Telegram Trigger
- **Вариант B (приоритет):** доработать Python proxy для приёма raw Telegram JSON, убрать Telegram Trigger из n8n полностью → Python полностью контролирует webhook

Полное описание: [[concepts/dispatcher-webhook-reregistration]].

### Phase 3: `maybe_sync_user_profile()` — Dispatcher migration Step 1 (2026-04-25)

**Контекст:** `Sync Profile` была n8n-нодой-тупиком в 01_Dispatcher, обновлявшей `last_active_at` при каждом запросе. Она создавала race condition с `debounce_user_action` (см. [[concepts/anti-spam-debounce]] Migration 141). Первый шаг миграции Dispatcher из n8n в Python — перенести `Sync Profile` в Python proxy.

**Реализация в `telegram_proxy.py`:**

```python
async def maybe_sync_user_profile(update: dict) -> None:
    """Fire-and-forget: sync user profile (replaces n8n Sync Profile node)."""
    msg = update.get('message') or update.get('callback_query', {}).get('message', {})
    from_user = (update.get('message') or update.get('callback_query', {})).get('from', {})
    if not from_user:
        return
    telegram_id = from_user.get('id')
    if not telegram_id:
        return
    payload = {
        'p_telegram_id': telegram_id,
        'p_username': from_user.get('username'),
        'p_first_name': from_user.get('first_name'),
        'p_last_name': from_user.get('last_name'),
        'p_language_code': from_user.get('language_code'),
    }
    await call_rpc('sync_user_profile', payload)
```

Вызывается как третья задача fire-and-forget в `/telegram/webhook`:

```python
asyncio.create_task(maybe_send_indicator(update))
asyncio.create_task(forward_to_n8n(raw_body))
asyncio.create_task(maybe_sync_user_profile(update))
```

**01_Dispatcher PUT (55→54 нод):** `Sync Profile` нода удалена вместе с её подключением от `User Exists?[true]`. Все остальные 54 ноды сохранены.

**Зачем Python, а не n8n:**
- Устраняет race condition с `debounce_user_action` (оба писали в `last_active_at` параллельно)
- Уменьшает количество нод в Dispatcher (roadmap: полный перенос Route Classifier в Python)
- Python `asyncio.create_task` гарантирует fire-and-forget без влияния на latency основного пути

### Phase 2: 01_Dispatcher cleanup

После стабилизации Python proxy удалены 4 ноды из 01_Dispatcher:
- `Quick Status Check` — HTTP GET /users?status check
- `Needs Indicator?` — IF node
- `Send Indicator?` — IF node
- `Send Early Indicator` — executeWorkflow 06_Indicator_Send

Новая топология: `Is Callback? [FALSE]` → `Get User Context` напрямую. 57 → 53 нод.

### Rollback артефакты

Сохранены в `.claude/rollback/dispatcher_python_proxy_2026-04-21/`:
- `rollback_webhook.py` — одна команда возвращает webhook на n8n URL
- `rollback_cleanup.py` — восстанавливает 4 удалённые ноды в Dispatcher
- `telegram_webhook_BEFORE.json`, `01_Dispatcher_BEFORE_cleanup.json`
- `noms-webhook.pem` — копия cert для повторного upload

Git commit `02931fe` — 9 files changed, 1041 insertions.

### Roadmap оптимизаций (отложено)

- Объединить `get_indicator_context` + `save_indicator_state` в один атомарный RPC (экономия ~100ms, снимает race при двух быстрых сообщениях)
- Запуск `sendSticker` параллельно с `get_indicator_context` (рискованно: может отправить стикер в edit_weight контексте)
- p50/p95 benchmark по накопленным production execution'ам после нескольких дней

## When to migrate n8n workflow to Python — Decision Framework

Typing-indicator кейс показал когда Python-прокси оправдан. Не каждый workflow стоит переносить — n8n идеален для визуальной оркестрации UI-роутинга. Критерии миграции:

### Миграция ОПРАВДАНА если:

1. **Latency-критичность** — юзер напрямую ощущает задержку (indicator, ack, first-byte). n8n scheduler добавляет 200-1500ms overhead даже на тривиальных workflow'ах (cold start JS engine, cross-node references `$('NodeName')`, queue delays). Indicator-кейс: 1.5-2s → 400-500ms.
2. **Fire-and-forget side-effects** — операция не должна блокировать main flow (typing, stickers, analytics events). В n8n это решается dead-end branches, но n8n scheduler всё равно их часто shedule'ит последними.
3. **Race conditions с БД** — workflow читает/пишет одно и то же поле через несколько параллельных веток. Python + async + атомарные RPC дают более предсказуемое ordering.
4. **Простая логика без UI** — если flow — это "проверить → действие → сохранить", без меню/сообщений/callbacks, Python дешевле в поддержке.
5. **Объём HTTP I/O** — n8n делает отдельный Execute Workflow hop для каждого sub-workflow (~30-50ms). Python httpx.AsyncClient с connection pool экономит многократно.

### Миграция НЕ ОПРАВДАНА если:

1. **Сложный UI-роутинг** — n8n Visual Switch router + Menu Router нагляднее 500 строк Python `if/elif`. Например, 04_Menu, 02_Onboarding_v3 — логика понятнее в n8n canvas.
2. **Частые правки от non-engineer'ов** — n8n позволяет "покрутить" nodes без git push. Если копирайтер / PM часто меняет тексты/callbacks — лучше n8n.
3. **Низкая latency-критичность** — cron jobs уже в Python, админ-флоу (payout approval) тоже. Что исполняется редко и юзер не ждёт результата — оставить в n8n/cron.
4. **Нужна визуальная отладка** — n8n executions показывают каждый шаг с данными. Для дебага сложных paywall / league / quest flows это бесценно.

### Критерии ROI до начала миграции

Перед переносом любого n8n workflow в Python оценить:

| Метрика | Порог для миграции |
|---|---|
| Реальная latency (не atribution) | p95 ≥ 1s и юзер-видимая |
| Частота запросов | ≥ 100/день (иначе ROI от оптимизации мизерный) |
| Сложность бизнес-логики | Умещается в один `.py` файл ≤500 строк; если нет — тревога, может в RPC надо |
| Наличие HTTPS на VPS | Обязательно (self-signed ok для Telegram, валидный — для Stripe/etc.) |
| Есть ли rollback-сценарий за 5 минут | Обязательно (в indicator-кейсе — `setWebhook` обратно на n8n) |

### Шаблонный Python proxy для следующего переноса

Для любого будущего workflow, который хотим перенести из n8n в Python, используется тот же каркас (`telegram_proxy.py`):

1. **FastAPI endpoint** с `asyncio.create_task()` для fire-and-forget.
2. **Pre-warm cache на startup** — загрузить всё что часто читается (переводы, константы, static data).
3. **Один RPC на context** — минимум DB round-trips. Один `get_X_context(...)` возвращает всё нужное.
4. **Health endpoint `/X/health`** + **auto-fallback cron** на оригинальный workflow (WebhookHealthCron pattern).
5. **Rollback-скрипт в `.claude/rollback/<task_2026-XX-YY>/`** — `setWebhook` обратно + BEFORE snapshot + `rollback_cleanup.py` для восстановления n8n нод.
6. **Whitelist логики** в Python + сохранение контракта старых RPC (`save_bot_message` / `clear_bot_message` не трогаем — используются AI Engine).

### Кандидаты на будущий перенос (по убыванию ROI)

Оцениваются по latency-impact. Не руководство к действию — только наблюдение:

| Workflow | Текущая latency | Кандидат? | Обоснование |
|---|---|---|---|
| **Early Typing Action** (`sendChatAction`) | ~50ms в n8n | Нет — уже быстро | Exec Workflow hop копеечный, работает |
| **`06_Indicator_Clear` → `deleteMessage`** | ~200-400ms в n8n | Возможно | Тоже fire-and-forget; может влиться в Python proxy после AI ответа. Сейчас остаётся в n8n потому что `03_AI_Engine` вызывает его по event-hook'у. |
| **Dispatcher routing** (Route Classifier) | ~50ms | Нет — UI-роутер, очень сложный switch | n8n Visual Switch эффективнее Python if/elif |
| **`02_Onboarding_v3`** (12-step flow) | ~300-800ms | Нет | UI-flow с пикчерами, частые правки копирайтера |
| **`03_AI_Engine`** | 3-7s (AI bound) | Только в AI-части | Latency диктует OpenAI, не n8n. Move GPT call в Python даст контроль над timeouts + retries, но не ускорит user-perceived latency |
| **`09_League_Display`** (standings) | ~500ms-1s | Возможно | Supabase-heavy, мало UI. RPC + Python render может быть быстрее. Но редкая операция (юзер открывает раз в день). |

### Lessons Learned (для следующего переноса)

1. **n8n `Code node` attribution врёт** — нода с простым кодом может отчитываться как 1.4s при реальном execution 20ms. Это scheduler queue time + cross-node ref overhead, не сама логика. **Не оптимизируй код ноды — оптимизируй топологию workflow**.
2. **Параллелизация n8n veterok не работает надёжно** — оба выхода IF-ноды сходящиеся в одну ноду всё равно блокируются. Race conditions неявные. Для реальной параллели — выносить в dead-end branch или переносить в Python.
3. **Self-signed cert достаточно для Telegram** — не надо домен + Let's Encrypt + Caddy. `openssl` + `setWebhook --form certificate=@cert.pem` работает с 2018 года.
4. **Ack < 10ms — must-have** — Telegram retry'ит webhook если долго не отвечаем. Python FastAPI с `asyncio.create_task()` даёт это бесплатно.
5. **Canary + auto-fallback OBLIGATORY** — любой webhook-proxy должен иметь health-check cron, который за минуту переключит Telegram webhook обратно на fallback URL при падении Python.
6. **Атомарный RPC лучше двух** — если получили context и потом сохраняем result, объединить в один RPC. Меньше roundtrip + нет race при concurrent sessions.

## Related Concepts

- [[concepts/n8n-performance-optimization]] — оригинальные попытки оптимизации indicator в n8n; Early Typing Action pattern; QSC параллельно
- [[concepts/n8n-stateful-ui]] — `last_bot_message_id`, `save_bot_message`, indicator clear pattern
- [[concepts/supabase-db-patterns]] — migration 109: get_indicator_context + save_indicator_state RPCs
- [[concepts/noms-architecture]] — Python APScheduler + FastAPI как отдельный слой; VPS deployment
- [[concepts/dispatcher-webhook-reregistration]] — критический баг: ANY PUT к 01_Dispatcher вытесняет Python proxy; recovery protocol; долгосрочные фиксы

## Sources

- [[daily/2026-04-21.md]] — Full Python proxy implementation: SSL setup, whitelist logic, rotation, health cron, migration 109, Phase 2 Dispatcher cleanup, latency benchmarks, rollback plan
- [[daily/2026-04-22.md]] — Критический инцидент: webhook потерян 5 раз от PUT к 01_Dispatcher; команда восстановления; долгосрочные решения A (изолировать Telegram Trigger) и B (Python raw JSON proxy)
- [[daily/2026-04-25.md]] — Phase 3: `maybe_sync_user_profile()` добавлена как третья fire-and-forget задача; `Sync Profile` нода удалена из 01_Dispatcher (55→54 нод); первый шаг Dispatcher migration roadmap
