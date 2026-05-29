---
title: "Cron-Pushed Callback Fallback Pattern"
aliases: [global-floating-actions, cron-callback-button-gap, off-screen-callback]
tags: [cron, sql, callbacks, headless, p0-lessons]
sources:
  - "migrations/211_global_floating_actions_and_delete_last_meal.sql"
  - "migrations/343_phase3_toast_and_strip.sql"
  - "migrations/366_cron_reminders_zen_filter_and_activity_mutex.sql"
  - "migrations/372_global_floating_actions_sleep_stress_callbacks.sql"
  - "daily/2026-05-29.md"
created: 2026-05-29
---

# Cron-Pushed Callback Fallback Pattern

**Принцип:** любая inline-кнопка которая может прийти юзеру в cron-pushed message (reminder, alert, push) — должна иметь row в `_global_floating_actions` virtual screen, иначе click не сработает.

## Background — почему gap возникает

`process_user_input` (mig 343) ищет button по:

```sql
WHERE screen_id = v_current_screen  -- top of users.nav_stack
   AND callback_data = p_callback
```

С fallback'ом на:

```sql
WHERE screen_id = '_global_floating_actions'  -- mig 211 virtual screen
   AND callback_data = p_callback
```

Когда юзер тапает callback в **screen-bound** message (открыл stats_main → нажал кнопку на stats_main) — `v_current_screen = 'stats_main'`, lookup на stats_main находит button.

Когда callback приходит из **cron-pushed message** (sleep_checkin reminder в 9 утра, food card AI alert и т.п.) — юзер на любом screen'е (где он недавно был), а button defined на screen_id который соответствует **типу сообщения**, не текущему UI юзера. Lookup на current_screen → **NOT FOUND**.

Без fallback: `v_save_ok=FALSE` → весь flow skip:
- `save_rpc` не fires (никакого DB write)
- `callback_alert_text` не resolved (нет toast)
- `target_screen` ignored (нет navigation)

## Lesson — P0 incident mig 366 → fix mig 372

**Mig 366 (28.05)** добавил inline-keyboard для sleep_checkin/stress_checkin cron push'ей (F1 фикс «нет кнопок»). Но buttons defined только на `sleep_checkin`/`stress_checkin` screens. **Юзер на любом другом current_screen** → lookup fails → click ничего не делает.

**Симптомы (29.05):**
- Нет toast «✅ Учтено»
- `daily_modifiers` не пишется
- Нет навигации
- **Cron F3 mutex (тот же mig 366) НИКОГДА не срабатывает** — потому что mutex проверяет `EXISTS daily_modifiers WHERE ...`, а записей нет
- Reminder завтра прилетает снова — bug self-reinforcing

**Evidence:** `notification_log` show stress_checkin pushed daily 27-29.05; `daily_modifiers` последняя stress запись — **25.05** (за 3+ дня до F1 deploy).

**Fix (mig 372):** INSERT 6 button rows в `_global_floating_actions`:
- screen_id='_global_floating_actions', row_index continuing после existing 0..2
- callback_data + text_key + meta скопированы as-is с source button rows
- Meta содержит save_rpc, save_value, target_screen, callback_alert_i18n_key — те же что на real screen

После fix:
1. Lookup на current_screen → not found → fallback → **FOUND**
2. Полный flow работает (save + toast + navigate)
3. F3 mutex наконец срабатывает (daily_modifiers пишется)

## Rule for future agents — checklist

**Если добавляешь cron-pushed inline button**, после mig:

1. ✅ Button row на «real» screen (для in-app flow когда юзер открывает screen вручную)
2. ✅ **DUPLICATE row в `_global_floating_actions`** с тем же meta — для cron-push case
3. ✅ Если callback has `save_rpc` — meta должна быть identical (saving работает уже из обеих entry-points)
4. ✅ Verify через query:
   ```sql
   SELECT screen_id FROM ui_screen_buttons WHERE callback_data='cmd_X';
   -- Должно вернуть ≥2 строки: real screen + _global_floating_actions
   ```

**Если есть Python intercept** для callback (например `_handle_stress_high` для РПП safety modal):
- Python intercept fires первым (router level)
- SQL fallback row нужна для **navigation only** (after Python save)
- Meta может быть БЕЗ `save_via_callback` (Python handles save directly)
- См. `cmd_stress_high` в mig 372 как пример

## Existing rows в `_global_floating_actions` (as of 2026-05-29)

```
row 0: cmd_edit_last         → set_editing_last_meal      → edit_food_prompt
row 1: cmd_delete_last       → delete_last_meal_with_revert → delete_confirmed
row 2: cmd_show_meals        → (nav only)                 → stats_main
row 3: cmd_sleep_short       → set_user_sleep_quality(short) → stats_main   (mig 372)
row 4: cmd_sleep_okay        → set_user_sleep_quality(okay)  → stats_main   (mig 372)
row 5: cmd_sleep_great       → set_user_sleep_quality(great) → stats_main   (mig 372)
row 6: cmd_stress_none       → set_user_stress_label(none)   → stats_main   (mig 372)
row 7: cmd_stress_moderate   → set_user_stress_label(moderate) → stats_main (mig 372)
row 8: cmd_stress_high       → set_user_stress_label(high)  → stats_main   (mig 372)
```

## Audit candidates — potential same-pattern gaps

Кнопки которые могут пушиться из cron / async backend и могут иметь ту же gap:
- `cmd_quests` — already covered (top-level fast-path в mig 343 L169)
- `cmd_cycle_*` (mig 334 luteal phase) — same risk если пушится из cron вне cycle screens. **TODO check** при следующем cycle UAT
- `cmd_freeze_*` (если есть) — proactive freeze offer via cron
- Любые safety_guard checkin callbacks (`cmd_safety_*`) — if pushed via SafetyGuardResolverCron

**Future CI guard idea:** проверять при PR что новый cron-related callback в reminders или alerts имеет row в `_global_floating_actions`. Маловероятно false-positive (можно opt-out tag для exceptions).

## Links

- [[one-menu-ux]] — replace_existing pattern для callback с callback_message_id (это как cron-pushed reminder становится «target message» для edit)
- [[save-bot-message-contract]] — last_bot_message_id mechanic; пока cron не сохраняет, navigation на cron message работает по callback_message_id отдельно
- [[reply-keyboard-routing-pattern]] — two-path architecture (reply text vs inline callback)
- [[cron-reminder-suppression-tunables]] — mute window для checkin reminders, mutex depends on daily_modifiers WHICH depends on this fix
