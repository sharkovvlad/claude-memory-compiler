---
title: "Smart Freeze Notification Delivery (mig 191)"
aliases: [smart-freeze, freeze-notification, freeze-pusher, pending-freeze-notification, deferred-push-delivery]
tags: [cron, streak, notifications, ux, architecture, telegram-proxy]
sources:
  - "daily/2026-05-09.md"
  - "migrations/191_smart_freeze_notifications.sql"
created: 2026-05-09
updated: 2026-05-09
---

# Smart Freeze Notification Delivery (mig 191)

Паттерн отложенной доставки push-уведомления «заморозка использована» — не в полночь (когда cron списывает freeze), а утром по локальному времени юзера ИЛИ при первом взаимодействии с ботом. Hybrid D: колонка-флаг `users.pending_freeze_notification_at` + два канала доставки (cron pusher + Scenario A перехват в telegram_proxy).

## Key Points

- **Проблема:** `cron_check_streak_breaks` работает каждый час UTC. Если у юзера полночь по его TZ — пуш о freeze приходит в 00:05 local time, будит, раздражает. Раньше текст «freeze used» шёл внутри cron — нет способа задержать.
- **Hybrid D архитектура:** cron ставит **флаг** `pending_freeze_notification_at = NOW()` (не шлёт пуш). Два независимых канала потом доставляют: (A) `telegram_proxy.maybe_send_indicator` при первом сообщении юзера ВМЕСТО thinking-стикера, (B) dedicated cron `freeze_notification_pusher` каждый час `:15` для юзеров с `local_hour >= 9`.
- **Anti-spam:** при delivery записывается `notification_log(notif_type='freeze_used')`. Cron `cron_get_reminder_candidates` (meal_morning) проверяет `NOT EXISTS notification_log type='freeze_used' today` — **не шлёт meal_morning если уже отправили freeze-пуш** (два пуша утром = спам).
- **13-language translations:** все ключи `cron_notifications.freeze_used` × 13 языков заполнены в мигр. 191 (Sassy Sage playful/empathic tone: «Ой, {name}, кажется вчера…»).
- **Стикер — placeholder:** `bot_stickers(sticker_key='freeze_used', is_active=false, file_id='TODO_...')`. Pusher и Scenario A автоматически пропускают стикер (шлют только текст). Активация одной SQL-командой после генерации file_id — без деплоя.
- **TTL: нет.** Pending живёт пока не доставим. Стрик и freeze-баланс остаются актуальны после доставки.

## Архитектура

```
[Ночь UTC] cron_check_streak_breaks v5
    ↓ streak_freezes -= 1
    ↓ pending_freeze_notification_at = NOW()
    ↓ НЕ шлёт пуш!

[Канал A — Scenario A, перехват при первом сообщении]
telegram_proxy.maybe_send_indicator(update):
    ↓ get_indicator_context(tid) → {pending_freeze_notification: true, ...}
    ↓ IF pending:
        шлём freeze-пуш ВМЕСТО thinking-стикера
        mark_freeze_notification_sent(tid)     ← атомарно: pending=NULL + notif_log INSERT
        RETURN (не шлём thinking — пуш заменяет)

[Канал B — dedicated cron, каждый час :15]
freeze_notification_pusher.run():
    ↓ get_freeze_notification_candidates() → юзеры с pending + local_hour >= 9
    ↓ фильтр zen-mode (notifications_mode='zen' → skip)
    ↓ шлём стикер (если active) + текст
    ↓ mark_freeze_notification_sent(tid)
```

## Details

### Cron `cron_check_streak_breaks` v5 (mig 191)

Добавлен блок установки pending-флага ПОСЛЕ списания freeze:

```sql
-- Внутри CTE freeze_candidates:
UPDATE users SET
    streak_freezes = streak_freezes - 1,
    last_streak_kept_date = today_in_tz - 1,
    pending_freeze_notification_at = NOW()  -- ← NEW: ставит флаг, НЕ шлёт пуш
WHERE telegram_id = candidate.telegram_id;
```

Старый inline-пуш (`send notification текстом при frozen`) **убран** из cron. Cron теперь только ставит флаг + пишет в `notification_log type='streak_frozen'` (для истории). Пуш юзеру — через каналы A/B.

### RPC `get_freeze_notification_candidates()`

Возвращает юзеров для cron-канала B:

```sql
SELECT telegram_id, language_code, display_name, timezone
FROM users
WHERE pending_freeze_notification_at IS NOT NULL
  AND is_bot = FALSE
  AND deleted_at IS NULL
  AND notifications_mode != 'zen'  -- zen-mode = только вечерний отчёт
  AND EXTRACT(HOUR FROM NOW() AT TIME ZONE COALESCE(timezone, 'UTC')) >= 9
  AND NOT EXISTS (
      SELECT 1 FROM notification_log
      WHERE user_id = users.telegram_id
        AND notification_type = 'freeze_used'
        AND sent_at > pending_freeze_notification_at
  );
```

### RPC `mark_freeze_notification_sent(p_telegram_id)`

Атомарно:
1. `UPDATE users SET pending_freeze_notification_at = NULL`
2. `INSERT INTO notification_log (user_id, notification_type, sent_at) VALUES (p_tid, 'freeze_used', NOW())`

Вызывается из обоих каналов (A и B). Idempotent — второй вызов не вставит дубль (pending уже NULL → candidates не вернёт).

### Scenario A — перехват в `telegram_proxy.py`

`get_indicator_context` v2 (mig 191) расширен: `RETURNS TABLE` shape добавлено поле `pending_freeze_notification BOOLEAN`. При DROP+CREATE сохранены все существующие поля (`status`, `last_indicator_index`, `last_text_indicator_date`, `language_code`) + добавлено новое.

В `maybe_send_indicator`:

```python
if ctx.get('pending_freeze_notification'):
    payload = await _get_freeze_payload(ctx['language_code'], ctx['display_name'])
    # Шлём стикер (если active) + текст
    if payload.get('sticker_file_id'):
        await _tg_send_sticker(chat_id, payload['sticker_file_id'])
    await _tg_send_message(chat_id, payload['text'])
    await _mark_freeze_sent(chat_id)
    return  # НЕ шлём thinking-стикер
```

Cache-helpers:
- `_get_freeze_text(lang)` — TTL 1h, из `ui_translations`
- `_get_freeze_sticker_id()` — TTL 1h, из `bot_stickers WHERE category='freeze' AND is_active=true`
- `_get_freeze_payload(lang, name)` — composites text + sticker

### `crons/freeze_notification_pusher.py`

Новый APScheduler job, pattern `BaseCron`:

```python
class FreezeNotificationPusherCron(BaseCron):
    name = "FreezeNotificationPusher"

    async def _execute(self):
        candidates = await self.rpc('get_freeze_notification_candidates')
        for user in (candidates or []):
            # Build payload
            text = await _get_freeze_text(user['language_code'])
            text = text.replace('{name}', user.get('display_name') or 'User')
            sticker_id = await _get_freeze_sticker_id()

            # Send (sticker → text, sequential)
            if sticker_id and not sticker_id.startswith('TODO_'):
                await telegram.send_sticker(user['telegram_id'], sticker_id)
            await telegram.send_message(user['telegram_id'], text)

            # Mark sent
            await self.rpc('mark_freeze_notification_sent',
                           {'p_telegram_id': user['telegram_id']})
```

Расписание: каждый час в `:15` (offset от streak cron в `:05`).

### Anti-spam с meal_morning

`cron_get_reminder_candidates` v3 (mig 191):

```sql
-- Внутри CASE WHEN p_reminder_type = 'meal_morning':
AND NOT EXISTS (
    SELECT 1 FROM notification_log
    WHERE user_id = u.telegram_id
      AND notification_type = 'freeze_used'
      AND sent_at >= date_trunc('day', NOW() AT TIME ZONE COALESCE(u.timezone, 'UTC'))
)
```

Если freeze-пуш уже отправлен сегодня — meal_morning reminder не шлётся. Юзер утром видит ОДНО сообщение, не два.

### `get_indicator_context` v2 — DROP+CREATE gotcha

Расширение RETURNS TABLE shape потребовало `DROP FUNCTION + CREATE FUNCTION` (не `CREATE OR REPLACE`). `CREATE OR REPLACE` отказывает при изменении return type. Все существующие атрибуты (`STABLE SECURITY DEFINER SET search_path = public`) **сохранены** в новом определении.

### Sticker placeholder pattern

```sql
INSERT INTO bot_stickers (sticker_key, category, file_id, file_type, description, sort_order, is_active, meta)
VALUES ('freeze_used', 'freeze', 'TODO_freeze_used', 'video_sticker',
        'Shown when streak freeze is consumed overnight', 0, false,
        '{"channel": "C"}'::jsonb);
```

`is_active=false` → pusher и Scenario A пропускают стикер, шлют только текст. Активация:

```sql
UPDATE bot_stickers SET file_id='<real_file_id>', is_active=true
WHERE sticker_key='freeze_used';
```

Эффект через ≤60с (TTL `services/stickers_cache`). Без деплоя.

### Окно доставки

**Open window:** `pending IS NOT NULL AND local_hour >= 9`. Нет верхней границы. Если cron-pusher пропустил час (например, restart сервиса) — следующий запуск всё равно доставит. Если юзер написал боту раньше 9 утра — Scenario A доставит мгновенно (не ждёт 9 часов).

Приоритет: Scenario A > Scenario B. Если юзер проснулся и написал боту в 7 утра — Scenario A отправит, mark_sent → Scenario B в 9:15 уже не найдёт pending.

## Тесты

`tests/integration/test_freeze_notifications.py` — 7 сценариев:

| Test | Что проверяет |
|---|---|
| FN1 | cron v5 ставит pending_at при freeze-save |
| FN2 | get_candidates фильтрует по local_hour >= 9 |
| FN3 | mark_sent атомарно чистит pending + пишет notification_log |
| FN4 | zen-mode юзеры не попадают в candidates |
| FN5 | повторный mark_sent idempotent (pending уже NULL) |
| FN6 | anti-spam: meal_morning skip если freeze_used сегодня (semantic test через pg_get_functiondef) |
| FN7 | Scenario A читает pending через get_indicator_context |

22/22 интеграционных тестов PASSED (включая регрессию T1-T4 streak и L1-L5 league).

## Gotchas

- **`RETURNS TABLE` shape change = DROP+CREATE.** `CREATE OR REPLACE` для функций, возвращающих TABLE, не позволяет менять набор столбцов. Необходимо явно DROP + CREATE с сохранением всех атрибутов (`STABLE`, `SECURITY DEFINER`, `SET search_path`).
- **Семантический тест vs реальные candidates.** FN6 (anti-spam) изначально пытался проверять через реальные candidate-запросы. Сломался из-за food_logs у тестового юзера (meal_morning = «нет логов сегодня» condition включало реальные данные). Переписан как семантический тест через `pg_get_functiondef()` + `find()` на SQL source.
- **`find()` с двумя CASE-блоками.** В функциях с двумя CASE-блоками (первый — для `v_target_hour`, второй — для WHERE) поиск `find('freeze_used')` может попасть на первое (неправильное) вхождение. Использовать `find()` со start-offset или специфичный anchor.
- **Scenario A message_id НЕ сохраняется** (не вызывает `save_indicator_state`). n8n `06_Indicator_Clear` не удалит freeze-пуш. Это intentional — freeze-пуш = Trophy (persistent), не indicator (transient).

## Related Concepts

- [[concepts/streak-freeze-cron-logic]] — корневой фикс `last_log_date` vs `last_active_at` (мигр. 187), которому мигр. 191 является follow-up по UX-доставке
- [[concepts/telegram-proxy-indicator]] — Scenario A живёт в `telegram_proxy.maybe_send_indicator`; расширение `get_indicator_context` v2
- [[concepts/cron-silent-failure-alerting]] — `BaseCron` pattern используется `FreezeNotificationPusherCron`
- [[concepts/ui-stickers-headless]] — Channel C sticker placeholder pattern (freeze_used row)
- [[concepts/sticker-architecture-adr]] — ADR 0001, Channel C семантика push-стикеров
- [[concepts/one-time-attach-pattern]] — аналогичный deferred-delivery паттерн для reply-keyboard (attach один раз, re-attach в edge cases)

## Sources

- [[daily/2026-05-09.md]] — Session «Smart Freeze Notifications»: мигр. 191, Hybrid D архитектура, 2 канала доставки (Scenario A перехват + cron pusher), anti-spam с meal_morning, sticker placeholder, 7 integration tests (FN1-FN7), `get_indicator_context` v2 DROP+CREATE, `cron_check_streak_breaks` v5 (pending flag, не inline push), 13-language translations
