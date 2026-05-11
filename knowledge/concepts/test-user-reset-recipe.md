---
title: "Test User Reset Recipe — обнуление для повторного онбординга"
aliases: [test-user-reset, reset-onboarding, fresh-user-reset]
tags: [testing, e2e, supabase, onboarding, dev-utility]
sources:
  - "Live UAT с user 786301802 (11.05.2026) — обнаружили stale phenotype_answers + ✅ misleading"
  - "Verified против live information_schema на 11.05.2026 (после mig 198 stickers + mig 201 one-time)"
created: 2026-05-11
updated: 2026-05-11
---

# Test User Reset Recipe

Атомарный SQL UPDATE для **полного обнуления** тестового пользователя — позволяет повторно прогнать онбординг E2E как если бы юзер только что зарегистрировался. Применять вручную в Supabase SQL editor.

## Когда использовать

- Регрессионное E2E тестирование онбординга (после каждого PR с изменениями в onboarding flow).
- Тестирование phenotype quiz «с нуля» (без stale `phenotype_answers`).
- Воспроизведение багов new-user сценариев (например stickers welcome не показывается).
- После применения миграций со схемой users — убедиться что reset script не упадёт на новых constraints.

## ⚠️ Live schema is source of truth, не NLM

NLM возвращает **stale knowledge** — у него snapshot схемы от какой-то даты. Если параллельные агенты применили миграции (mig 198 sticker_foundation, mig 201 one-time, и т.п.), NLM их не видит и может выдать неверный SQL.

**Перед использованием reset script** проверь актуальную схему через psycopg2:

```python
cur.execute(
    "SELECT column_name, data_type, is_nullable, column_default "
    "FROM information_schema.columns "
    "WHERE table_name='users' ORDER BY column_name"
)
```

Особенно для `NOT NULL` constraints — NULL вместо нужного default сломает транзакцию.

## Script (verified против live schema на 2026-05-11, после mig 201)

```sql
UPDATE users
SET
  -- ──── BASE ────
  status = 'new',
  deleted_at = NULL,
  gender = NULL, birth_date = NULL, weight_kg = NULL, height_cm = NULL,
  activity_level = NULL, training_type = NULL,
  goal_type = NULL, goal_speed = NULL,
  phenotype = 'default',                                -- default 'default'::text
  nav_stack = '[]'::jsonb,
  last_bot_message_id = NULL, indicator_message_id = NULL,
  language_code = 'ru', previous_status = NULL,
  country_code = NULL, timezone = NULL,
  xp = 0, level = 1, nomscoins = 0, mana_current = 2,

  -- ──── Stickers / indicators ────
  stickers_shown = '{}'::jsonb,                         -- NOT NULL (mig 198 sticker_foundation)
  last_indicator_index = 0,
  last_text_indicator_date = NULL,
  last_bot_message_type = NULL,
  last_action_ms = NULL,
  last_action_signature = '{}'::jsonb,

  -- ──── Phenotype quiz state ────
  phenotype_answers = NULL,                             -- nullable, NULL match'ит initial create
  target_weight_kg = NULL,

  -- ──── Computed targets (заполнятся calculate_user_targets на goal save) ────
  target_calories = NULL, target_protein_g = NULL,
  target_carbs_g = NULL, target_fat_g = NULL,
  target_speed_percent = NULL, pal_coefficient = NULL,
  neat_tier = NULL,

  -- ──── Location funnel ────
  country_code_declared = NULL,
  country_code_billing = NULL,
  country_code_override = NULL,
  timezone_declared = NULL,
  location_set_at = NULL,

  -- ──── Streak / XP daily counters ────
  last_log_date = NULL, last_streak_kept_date = NULL,
  xp_today_date = NULL,
  current_streak = 0, max_streak = 0,
  streak_freezes = 0,
  xp_logs_today = 0, xp_corrections_today = 0,

  -- ──── League & Gamification ────
  league_group_id = NULL,
  league_id = 1,                                        -- стартовая «Лук» (default 1)
  league_xp_weekly = 0,
  tamagotchi_stage = 'egg',                             -- сброс пета (default 'egg')

  -- ──── Mana ────
  mana_max = 2,
  mana_last_recharge_at = NULL,
  mana_recharges_today = 0,

  -- ──── Cycle tracking (female feature) ────
  cycle_avg_length = NULL,
  cycle_start_date = NULL,
  cycle_phase = NULL,

  -- ──── Notifications ────
  notifications_mode = 'balanced',                      -- ⚠️ NOT NULL, default 'balanced'

  -- ──── Ghost states ────
  editing_meal_id = NULL,
  pending_freeze_notification_at = NULL,

  -- ──── Activity touch ────
  last_active_at = NOW()

WHERE telegram_id = <TARGET_TELEGRAM_ID>;
```

## Поля которые НЕ трогать

- `telegram_id`, `created_at`, `username`, `first_name` — identity.
- `phenotype_q1..q4` — generated columns (mig 199), auto-sync с `phenotype_answers`. Read-only.
- `sage_quote_index`, `tamagotchi_xp_total` — non-blocking decoration.
- `subscription_status`, `limit_variant`, `sage_tier` — Premium статус. Не сбрасывать, если хочешь тест Premium flow. Сбросить отдельно для тестирования free-tier UX.

## Common pitfalls (Lessons from 11.05.2026)

1. **`stickers_shown` существует и `NOT NULL`** — это mig 198 sticker_foundation. NLM думал что колонки нет — wrong. Reset через `'{}'::jsonb`.
2. **`notifications_mode NOT NULL`** — нельзя ставить NULL. Default 'balanced'.
3. **`phenotype = 'default'` (не NULL)** — match'ит initial create state. Live default = 'default'::text.
4. **`level = 1` (не 0)** — геймификация считает с 1. Может сломать прогресс-бар.
5. **`league_id = 1`** — стартовая лига «Onion/Лук». NULL сделает юзера «бездомным» в лиговой логике.
6. **`tamagotchi_stage = 'egg'`** — иначе у новичка показывается взрослый Номс.
7. **Daily counters reset (0, не NULL)** — `xp_logs_today`, `xp_corrections_today`, `mana_recharges_today`, `streak_freezes`, `league_xp_weekly`, `current_streak`, `max_streak`.

## After reset — что проверить вручную

- `/start` от reset'нутого юзера → `onboarding_welcome` screen с приветственным стикером (mig 198/201 Channel A).
- Прогон полного онбординга: language → name → biometry → goal → speed → phenotype quiz → location → timezone → completion.
- Phenotype quiz Q1 при первом проходе → **нет ✅** ни на одной кнопке (потому что phenotype_answers = NULL → phenotype_q1 = NULL).
- После Q4 → render phenotype_result (mig 202) → click «Готово» → forward to location.
- Location picker → выбор страны/таймзоны → завершение → success sticker (Channel A, mig 198/201).

## Связанные KB

- [[concepts/phase4-onboarding-migration]] — gotchas #1-#33, история phenotype quiz Sub-FSM.
- [[concepts/sticker-architecture-adr]] (если есть) — mig 198 unified sticker foundation.
- [[concepts/release-protocol]] — параллельные агенты, mig-number reservation.

## Reusability

Если хочешь автоматизировать, сохрани script под `scripts/reset_test_user.sql` в основном репо (с placeholder для telegram_id) и используй как:

```bash
psql "$DATABASE_URL" -v telegram_id=786301802 -f scripts/reset_test_user.sql
```

Replace `WHERE telegram_id = <TARGET_TELEGRAM_ID>` на `WHERE telegram_id = :telegram_id`.
