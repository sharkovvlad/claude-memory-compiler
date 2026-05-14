---
title: "One Menu UX"
aliases: [one-menu, last-bot-message-id, save-bot-message, delete-old-menu]
tags: [n8n, ui, telegram, patterns, ux]
sources:
  - "daily/2026-04-11.md"
  - "daily/2026-04-17.md"
created: 2026-04-11
updated: 2026-04-17
---

# One Menu UX

The bot keeps exactly one active navigation screen in chat at any time. When a reply-keyboard button is tapped, the previous menu message is deleted before (or in parallel with) the new one being sent.

## Key Points

- **`last_bot_message_id`** stored in `users` table and exposed via `v_user_context` (migration 056) — tracks the most recently sent navigation screen
- **`save_bot_message` RPC** called after every navigation screen send to persist the new `message_id` into `users.last_bot_message_id`
- **Delete Old Menu** fires as a parallel dead-end branch from the Build Text node — fire-and-forget, `onError: continueRegularOutput`
- **ONLY top-level navigation screens are tracked** (Stats / Profile / Progress). Food logs, AI recognition results, level-up notifications, cron reminders, payment confirmations — none of these call `save_bot_message`
- **⚠️ Sub-screens и pickers NOT tracked** (Settings, My Plan, edit_speed / edit_goal / edit_weight pickers, Language picker, Country picker и т.д.). При переключении reply-кнопкой на другой top-level **старые pickers физически остаются на экране**. Это tech-debt, не bug. См. "Known gap" ниже.
- **`last_bot_message_id=0`** produces a Telegram 400 error on `deleteMessage` — silently ignored via `onError: continueRegularOutput`
- **`/start` как нативная кнопка Telegram** показывается ОДИН раз при первом добавлении бота. Для зарегистрированных юзеров в обычном flow не появляется. Юзер может вручную набрать `/start`, но это редкое событие. Значит One-Menu не обрабатывает `/start`-переключения специально.

## Known gap: sub-screens не участвуют в One-Menu (2026-04-17)

**Сценарий:**
1. Юзер в Profile → Мой план → Цель → Speed picker (edit_speed)
2. Вместо Back нажимает reply-кнопку "📈 Прогресс"
3. Progress rendered, старое меню Profile удалено ✅
4. **НО** picker "Velocidad de pérdida de peso" (edit_speed) всё ещё висит на экране выше
5. Если юзер клик по его inline-кнопкам (Slow/Normal/Fast/Atrás) — непредсказуемое поведение (может apply speed change или Back из неактуального стека)

**Почему:** Каждый sub-screen рендерится через `sendMessage` (или `editMessageText` для inline Back). `save_bot_message` вызывается ТОЛЬКО для top-level. `last_bot_message_id` хранит последнее top-level menu_id, не picker_id. При next top-level switch `deleteMessage(last_bot_message_id)` удалит top-level меню, но picker — нет.

**Tech-debt решение (для будущих сессий):**
- Вариант A: добавить `last_sub_screen_message_id` колонку + track pickers через отдельный `save_sub_screen_message` RPC. При top-level switch — delete обоих (top-level + sub-screen).
- Вариант B: расширить `save_bot_message` принимать `message_type` (top_level / sub_screen) + хранить JSONB `{top_level_id, sub_screen_id}`. Delete обоих при top-level switch.
- Вариант C: при top-level reply-button render — delete ALL user's recent bot messages (более агрессивный cleanup). Рисковано — может удалить food logs.

Вариант B рекомендован — расширяет существующую инфру минимально.

**Связь с nav_stack (migration 076-078):** nav_stack чистится корректно через `reset_nav_to` на top-level render (Bug 6 Phase 1.5). Эта проблема — отдельный layer (физическое сообщение vs logical navigation state).

## Details

### Why "One Menu"

Navigation screens (Stats, Profile, Progress) go stale the moment they're sent. If a user taps "☀️ Мой день" twice, two different calorie counts appear in chat — confusing. Each press should replace the previous screen, not append.

Content messages are permanent by design: food logs are a nutrition diary. Deleting them would destroy the user's data.

### Database layer (migration 056)

Migration 056 recreated `v_user_context` as a full `DROP VIEW + CREATE VIEW` (not `CREATE OR REPLACE`) to insert `u.last_bot_message_id` and also backfill the `training_type`, `phenotype`, `goal_speed`, and `target_*` columns from migration 055 that had not been added to the live view.

`CREATE OR REPLACE VIEW` cannot insert columns in the middle of an existing select list — it can only append or replace identical-position columns. When column order matters (or new columns need to be inserted between existing ones), drop and recreate.

### n8n implementation in 04_Menu

Nine nodes were added (80 → 89 nodes total). Three identical chains for Stats, Profile, and Progress:

```
Build [Screen] Text ─┬─→ Is Callback? → Send Response → Extract Menu ID → Save Menu ID
                     └─→ Delete Old Menu   [dead-end, fire-and-forget]
```

**Delete Old Menu** (HTTP Request POST `deleteMessage`):
- Reads `last_bot_message_id` from Merge Data
- `onError: continueRegularOutput` — silently continues if message already deleted or id=0
- Dead-end: no outgoing connections

**Extract Menu ID** (Code node):
```js
return [{ json: { message_id: ($json.result || $json).message_id } }];
```
The `($json.result || $json)` pattern handles two different response shapes:
- HTTP Request `sendMessage` returns `{ result: { message_id: ... } }`
- Telegram node returns `{ message_id: ... }` directly

**Save Menu ID** (HTTP Request POST Supabase RPC `save_bot_message`):
- Runs after Send Response (sequential, not parallel)
- Updates `users.last_bot_message_id` for the next navigation tap

### Dispatcher: threading last_bot_message_id

The "Prepare for 04" Set node in 01_Dispatcher includes:
```
last_bot_message_id: $json.last_bot_message_id || 0
```
This is field 31 of the Set node. Without it, 04_Menu cannot read the value from Merge Data.

### Merge Data update

04_Menu's Merge Data node was updated to include:
```js
last_bot_message_id: input.last_bot_message_id || 0
```
So the value flows to all downstream nodes including Delete Old Menu.

### What NOT to track

The following message types must never call `save_bot_message`:
- Food log confirmations (AI recognition results)
- Level-up, achievement, or XP notifications
- Cron-sent reminders (meal reminders, streak warnings, league results)
- Payment confirmations or invoices

Tracking these would cause the next navigation tap to delete a food log entry — permanently losing user data.

## Related Concepts

- [[concepts/save-bot-message-contract]] — **обязательство** для всех воркфлоу вызывать `save_bot_message` после финального user-visible сообщения. Без этого One Menu UX ломается на следующей навигации. Lesson 14.05 (Tech debt #7 smoke): legacy n8n `02.1_AI_Engine` нарушает контракт → orphaned bubbles в чате.
- [[concepts/n8n-stateful-ui]] — editMessageText, callback_message_id, inline nav patterns
- [[concepts/n8n-data-flow-patterns]] — fire-and-forget parallel branch rule
- [[concepts/supabase-db-patterns]] — migration 056, DROP+CREATE VIEW pattern

## Sources

- [[daily/2026-04-11.md]] — Full implementation: migration 056 (v_user_context + last_bot_message_id), Dispatcher "Prepare for 04" field 31, 04_Menu 9 new nodes (80→89), Delete/Extract/Save chains for Stats/Profile/Progress
