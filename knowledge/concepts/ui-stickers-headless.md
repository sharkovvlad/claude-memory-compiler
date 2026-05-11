# Sticker Architecture (4 Channels, Single Source of Truth)

> Полное архитектурное решение: ADR `docs/adr/0001-sticker-architecture.md` в репо NOMS. Этот документ — operational guide для агентов, добавляющих/правящих стикеры.

## TL;DR

Все стикеры в NOMS хранятся в **единой таблице `bot_stickers`** (single source of truth, никаких file_id в коде). Отправка идёт по **одному из 4 каналов** в зависимости от семантики стикера:

| Канал | Семантика | Триггер | Способ отправки | Удаление |
|---|---|---|---|---|
| **A** UI Content | Часть экрана (welcome, success, level_up) | SQL FSM-переход в screen_id с `meta.show_sticker=true` | Headless: `render_screen` → `telegram_ui.sticker_category` → `template_engine` → `OutboundItem(send_sticker)` → `telegram_send` через `await` | Нет (Trophy) |
| **B** Event side-channel | Реакция на action (food_recognized, water_logged) | Явный Python вызов `await stickers.send_event(...)` (TBD — Stage 2+) | Прямой POST через cache | Опционально через `meta.auto_delete_after_ms` |
| **C** Push (cron) | Push-нотификация со стикером | Cron job | Sequential `await` (sticker → text) | Нет |
| **D** Transient indicator | Thinking/analyzing ожидание | Любое входящее в `active` статусе | Fire-and-forget из `telegram_proxy.py` | Да, после AI-ответа (`users.indicator_message_id`) |

**Принцип:** SQL решает WHAT (категория, когда показать), Python — HOW (резолв file_id из кэша, HTTP-вызов).

## Семантический раздел: thinking-стикер (D) vs UI-стикер (A)

| Свойство | Channel D (thinking) | Channel A (UI content) |
|---|---|---|
| Назначение | Индикатор ожидания долгой операции | Часть приветственного / поздравительного экрана |
| Триггер | Любое входящее в `active` статусе | FSM-переход в конкретный screen_id |
| Где живёт правило показа | Python `telegram_proxy.maybe_send_indicator` | SQL `ui_screens.meta.show_sticker` |
| Способ отправки | `asyncio.create_task(_tg_send_sticker())` | `OutboundItem(send_sticker)` через envelope, **строго через `await`** |
| Порядок в чате | Не критичен (transient) | **Критичен** — должен предшествовать тексту |
| Удаление | Да, после AI-ответа | Нет, Trophy |

**Race-condition guard для Channel A:** `asyncio.create_task` ЗАПРЕЩЁН. Параллельная отправка стикера и текста инвертирует порядок на балансировщиках Telegram — текст может прийти раньше стикера. Поэтому в `services/telegram_send.py` `send_sticker` всегда через `await`. Подробности — ADR 0001.

## Контракт SQL ↔ Python (Channel A)

Это симметрично mig 157 `attach_reply_kb`: «декларативное поле в `telegram_ui` → OutboundItem в envelope».

| Источник | Поле в `telegram_ui` | Что Python добавляет | Позиция в envelope |
|---|---|---|---|
| `ui_screens.meta.reply_kb_entry=true` (mig 157) | `reply_keyboard = {...}` | `OutboundItem(attach_reply_kb)` | В КОНЕЦ |
| `ui_screens.meta.show_sticker=true` (mig 198) | `sticker_category = '<text>'` | `OutboundItem(send_sticker)` | ПОСЛЕ ACQ, ПЕРЕД основным item |

### Цепочка вызовов Channel A

```
1. ui_screens row:
   meta = {'show_sticker': true, 'sticker_category': 'onboarding_welcome'}

2. SQL render_screen (Step 8b + Step 9, mig 198):
   IF v_screen.meta->>'show_sticker' = 'true' THEN
       v_sticker_category := v_screen.meta->>'sticker_category';
   END IF;
   v_telegram_ui = jsonb_build_object(..., 'sticker_category', v_sticker_category, ...);

3. services/template_engine.py render_envelope() — Channel A block:
   sticker_category = telegram_ui.get('sticker_category')
   if isinstance(sticker_category, str) and sticker_category:
       from services import stickers_cache
       sticker_file_id = stickers_cache.lookup(sticker_category)
       if sticker_file_id:
           items.append(OutboundItem(
               strategy='send_sticker',
               chat_id=chat_id,
               sticker_id=sticker_file_id,
           ))
       # else: graceful skip (log info, main message still renders)

4. services/telegram_send.py:225-231:
   if item.strategy == 'send_sticker':
       await client.post('/sendSticker', {chat_id, sticker})
   # await — гарантия порядка
```

### Cache контракт (`services/stickers_cache.py`)

- **TTL 60 секунд** + background refresher (PgBouncer transaction mode не поддерживает LISTEN/NOTIFY, поэтому полл-модель).
- **Fail-open**: network error при refresh → `keep stale` (защита от потери welcome-стикера на pooler blip).
- **Sync lookup** (вызывается из синхронного `render_envelope`); async — только prewarm/invalidate/refresh.
- **DI-friendly**: `StickersCache(query_fn=...)` для тестов без сети.
- **Manual reload**: `POST /internal/stickers/reload` с заголовком `X-Stickers-Reload-Token` (env `STICKERS_RELOAD_TOKEN`). Возвращает 503 если token не настроен.
- **Observability**: `stats()` → `{categories, total_stickers, last_refresh_age_s, last_status: never|ok|empty|error|stale}`.

## Как добавить новый стикер на новый экран (Channel A)

1. **Получить file_id**: переслать стикер боту @RawDataBot (или любому echo-bot), скопировать `message.sticker.file_id` — длинная строка `CAACAg...`. File_id видеостикеров глобально валидны для всех ботов.
2. **Миграция (SQL only)**:
   ```sql
   -- Add sticker row
   INSERT INTO public.bot_stickers
       (sticker_key, category, file_id, file_type, description, sort_order, is_active)
   VALUES
       ('level_up_celebration_1', 'level_up_celebration',
        '<file_id>', 'video_sticker',
        'Celebration sticker shown after level-up.', 0, true)
   ON CONFLICT (sticker_key) DO UPDATE
      SET file_id = EXCLUDED.file_id, is_active = true;

   -- Declare on screen
   UPDATE public.ui_screens
      SET meta = meta
                 || jsonb_build_object('show_sticker', true)
                 || jsonb_build_object('sticker_category', 'level_up_celebration')
    WHERE screen_id = 'level_up_screen';
   ```
3. **Никаких правок в Python**. Reload `POST /internal/stickers/reload` или жди 60s TTL.

## Что НЕЛЬЗЯ делать

1. **Не клади логику Channel A в `handlers/*.py`** — нарушение headless. Только через `ui_screens.meta`.
2. **Не используй `asyncio.create_task` для Channel A** — race condition инвертирует порядок «стикер → текст».
3. **Не дублируй thinking-кэш для UI-контент** — у Channel A свой кэш (`services/stickers_cache.py`).
4. **Не хардкодь file_id в коде/конфигах/`.env`** — single source of truth = `bot_stickers`.
5. **Не используй n8n-маршрут** — миграция onboarding в Python завершена (mig 161+165+182).

## Migration roadmap

- **Stage 1 (mig 198, 2026-05-11):** Channel A работает. Channels C/D всё ещё используют свои локальные кэши в `telegram_proxy.py` / `crons/*.py`.
- **Stage 2 (planned, отдельный PR):** `telegram_proxy._get_stickers` / `_get_freeze_sticker_id` мигрируют на общий `services/stickers_cache`. Channel D `processing_*` и Channel C `freeze` живут под единой инфрой.
- **Stage 3 (по потребности):** Channel B facade `services/stickers.py:send_event(chat_id, category)` — когда AI-Engine мигрирует из n8n в Python (Roadmap).

## История

- **Mig 161** (2026-04-30): положила декларацию `meta.show_sticker` для `onboarding_welcome` + placeholder в `bot_stickers`, но цепочку не дошила (мёртвая декларация ~10 дней).
- **Mig 198** (2026-05-11): дошила Channel A — `render_screen` подмешивает `sticker_category`, `template_engine` добавляет `send_sticker` item. Заполнила реальные file_id для welcome + success. `bot_stickers` расширена (`meta jsonb`, `updated_at`, partial index, `trg_set_updated_at`).

## Связанные KB

- [headless-architecture.md](headless-architecture.md) — общий принцип SQL=WHAT, Python=HOW
- [telegram-proxy-indicator.md](telegram-proxy-indicator.md) — thinking-стикер (Channel D) pattern
- [phase4-onboarding-migration.md](phase4-onboarding-migration.md) — где жил placeholder `onboarding_welcome_1`
- [one-time-attach-pattern.md](one-time-attach-pattern.md) — родственный паттерн `attach_reply_kb` (mig 157)
