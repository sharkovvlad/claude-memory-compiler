---
title: "Test User Reset Recipe — обнуление для повторного онбординга"
aliases: [test-user-reset, reset-onboarding, fresh-user-reset]
tags: [testing, e2e, supabase, onboarding, dev-utility]
sources:
  - "Live UAT с user 786301802 (11.05.2026) — обнаружили stale phenotype_answers + ✅ misleading"
  - "Verified против live information_schema на 11.05.2026 (после mig 198 stickers + mig 201 one-time)"
  - "Verified savepoint test 12.05.2026 — функция reset_to_onboarding (mig 203) покрывает все 64 поля"
created: 2026-05-11
updated: 2026-05-12
---

# Test User Reset Recipe

Полное обнуление тестового пользователя для повторного прогона онбординга E2E. **С 2026-05-12 — one-liner:**

```sql
SELECT public.reset_to_onboarding(<TARGET_TELEGRAM_ID>);
```

Через psycopg2:
```python
cur.execute("SELECT public.reset_to_onboarding(%s)", (786301802,))
print(cur.fetchone()[0])   # {"success": true, "reset_by": "mig_203", "status": "new"}
```

Функция (mig 203) обнуляет **64 поля** атомарно в одной транзакции, в т.ч.:
- `status='new'`, `nav_stack='[]'`, `stickers_shown='{}'`, `previous_status=NULL`
- Биометрию (`gender/birth_date/weight/height/activity/training/goal/speed`)
- Phenotype quiz (`phenotype='default'`, `phenotype_answers=NULL`, generated cols q1..q4 auto-reset)
- Gamification (`xp=0`, `level=1`, `nomscoins=0`, `current_streak=0`, league/tamagotchi reset)
- Mana (`mana_current=2`, `mana_max=2`)
- Location funnel (`country_code=NULL`, `timezone=NULL`, declared/billing/override все NULL)
- UI state (`last_bot_message_id=NULL`, `indicator_message_id=NULL`)
- Cycle tracking (для женских юзеров)
- Notifications mode='balanced' (NOT NULL default)
- `updated_at` + `last_active_at = NOW()`

Что **сохраняется**: identity (telegram_id, first_name, username, language_code, email), subscription/billing, referrer info, phone, roles (ambassador/trainer), NPC bot fields. См. список `NOT TOUCHED` в теле функции `pg_get_functiondef('public.reset_to_onboarding(bigint)'::regprocedure)`.

## Сверка покрытия

Если хочешь убедиться что новое поле в `users` тоже обнуляется при reset (например, после миграции добавившей колонку):
```python
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='users'")
all_cols = {r[0] for r in cur.fetchall()}
body = open_pg_functiondef('public.reset_to_onboarding(bigint)')
covered = {c for c in all_cols if re.search(rf'^\s*{c}\s*=', body, re.M)}
uncovered_writable = all_cols - covered - PRESERVED_BY_DESIGN  # check this set
```

Если что-то «потерялось» — обновить mig (новой миграцией NNN, stale-base safe).

## Manual UPDATE fallback (для случаев когда RPC недоступен)

Используй только если функция `reset_to_onboarding` не существует или нужны нестандартные правки сверх дефолта.

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

## Script (verified против live schema на 2026-05-11, после mig 201 и 207)

UPDATE users
SET
  -- ──── BASE ────
  status = 'new',
  deleted_at = NULL,
  gender = NULL, birth_date = NULL, weight_kg = NULL, height_cm = NULL,
  activity_level = NULL, training_type = NULL,
  goal_type = NULL, goal_speed = NULL,
  phenotype = 'default',
  nav_stack = '[]'::jsonb,
  last_bot_message_id = NULL, indicator_message_id = NULL,
  previous_status = NULL,
  country_code = NULL, timezone = NULL,
  xp = 0, level = 1, nomscoins = 0, mana_current = 2,

  -- ──── Stickers / indicators ────
  stickers_shown = '{}'::jsonb, -- Это уже стирает onboarding_success
  last_indicator_index = 0,
  last_text_indicator_date = NULL,
  last_bot_message_type = NULL,
  last_action_ms = NULL,
  last_action_signature = '{}'::jsonb,

  -- ──── Phenotype quiz state ────
  phenotype_answers = NULL,
  target_weight_kg = NULL,
  body_type = NULL, 

  -- ──── Computed targets ────
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
  league_id = 1,
  league_xp_weekly = 0,
  tamagotchi_stage = 'egg',

  -- ──── Mana ────
  mana_max = 2,
  mana_last_recharge_at = NULL,
  mana_recharges_today = 0,

  -- ──── Cycle tracking ────
  cycle_avg_length = NULL,
  cycle_start_date = NULL,
  cycle_phase = NULL,

  -- ──── Notifications ────
  notifications_mode = 'balanced',

  -- ──── Ghost states ────
  editing_meal_id = NULL,
  pending_freeze_notification_at = NULL,

  -- ──── Activity touch ────
  last_active_at = NOW()

WHERE telegram_id = 786301802;

-- Включаем Python location handler и мгновенно сбрасываем кэш констант
UPDATE app_constants SET value='true' WHERE key='handler_location_use_python';


## Поля которые НЕ трогать

- `telegram_id`, `created_at`, `username`, `first_name`, `is_bot` — identity.
- `email` — auth handle.
- `phenotype_q1..q4` — generated columns (mig 199), auto-sync с `phenotype_answers`. Read-only.
- `sage_quote_index`, `tamagotchi_xp_total` — non-blocking decoration.
- `subscription_status`, `limit_variant`, `sage_tier` — Premium статус. Не сбрасывать, если хочешь тест Premium flow. Сбросить отдельно для тестирования free-tier UX.
- `referrer_id`, `referral_count`, `paid_referral_count` — контрибуция к чужим аккаунтам (не теряем при start fresh).
- **`phone`, `phone_confirmed_at`, `phone_source`** — связано с реферальным/payout flow. Решение 2026-05-11: сохранять. Пересмотр — TODO Опция 2 в [[concepts/start-fresh-gaps-2026-05-11]].
- `ambassador_tier`, `ambassador_commission_rate`, `is_trainer`, `trainer_commission_rate` — роли. По умолчанию НЕ сбрасывать (нужен product decision).
- `food_logs`, `xp_events`, `payment_transactions`, `meal_corrections`, `streak_events`, `referral_escrow` — отдельные таблицы, история. Анонимизация food_logs — TODO Опция 2.

## Common pitfalls (Lessons from 11.05.2026)

1. **`stickers_shown` существует и `NOT NULL`** — это mig 198 sticker_foundation. NLM думал что колонки нет — wrong. Reset через `'{}'::jsonb`.
2. **`notifications_mode NOT NULL`** — нельзя ставить NULL. Default 'balanced'.
3. **`phenotype = 'default'` (не NULL)** — match'ит initial create state. Live default = 'default'::text.
4. **`level = 1` (не 0)** — геймификация считает с 1. Может сломать прогресс-бар.
5. **`league_id = 1`** — стартовая лига «Onion/Лук». NULL сделает юзера «бездомным» в лиговой логике.
6. **`tamagotchi_stage = 'egg'`** — иначе у новичка показывается взрослый Номс.
7. **Daily counters reset (0, не NULL)** — `xp_logs_today`, `xp_corrections_today`, `mana_recharges_today`, `streak_freezes`, `league_xp_weekly`, `current_streak`, `max_streak`.
8. **`language_code` НЕ сбрасывается** (ни в test SQL, ни в prod RPC `reset_to_onboarding` mig 203). Это **последний осознанный выбор юзера** — терять его при start_fresh не нужно. Юзер мог уехать из Испании, переключить язык в боте на русский, потом удалить аккаунт и через год вернуться. Telegram-locale у него ≠ его NOMS-locale. Для полностью новых юзеров язык предзаполняется из Telegram через `ensure_user_exists()` при первой регистрации (mig 161). Стикеры NOMS универсальны (без надписей), поэтому язык вообще не влияет на их показ.
8b. **Если в тесте нужен ДРУГОЙ язык** — сделай отдельным `UPDATE users SET language_code='X' WHERE telegram_id=...` после reset. Не зашивай в этот recipe — он переиспользуемый, любой агент будет ожидать что existing язык сохраняется.
9. **`status = 'new'`, не `'registration_step_1'`** — `'new'` ведёт на `onboarding_welcome` (welcome-стикер + приветствие через Channel A). `'registration_step_1'` сразу на `edit_gender` — **пропускает welcome experience**. Текущая prod RPC `reset_to_onboarding` (mig 079) делает это неправильно — отдельный TODO ([[concepts/start-fresh-gaps-2026-05-11]] Gap 1).
10. **`level = 1` после reset триггерит `finalize_onboarding_location.already_completed`** (mig 179 guard `IF level >= 1`). Это значит после прохождения онбординга → location pin → success-стикер НЕ покажется + поздравительное сообщение НЕ придёт. **Fix эволюционировал:** mig 203 (Опция A — `status='registered' AND level>=1`) → отвергнут live-тестом 12.05, потому что `set_user_location` переключает status='registered' ДО finalize → mig 204 (Опция C — `xp>0 OR nomscoins>0`). Детали — [[concepts/start-fresh-gaps-2026-05-11]] Gap 2 секция "Эволюция guard'а".
11. **`set_user_location` переключает status напрямую** через `COALESCE(p_new_status, status)` — это значит во время онбординг flow status='registered' установлен раньше чем `finalize_onboarding_location` вызовется. Любой guard discriminator основанный на status (не на xp/nomscoins) для отличения "completed" от "in_progress" — **broken by design**. Используй `xp>0 OR nomscoins>0` как инвариант "юзер уже получил welcome rewards".

## After reset — что проверить вручную

- `/start` от reset'нутого юзера → `onboarding_welcome` screen с приветственным стикером (mig 198/201 Channel A).
- Прогон полного онбординга: language → name → biometry → goal → speed → phenotype quiz → location → timezone → completion.
- Phenotype quiz Q1 при первом проходе → **нет ✅** ни на одной кнопке (потому что phenotype_answers = NULL → phenotype_q1 = NULL).
- После Q4 → render phenotype_result (mig 202) → click «Готово» → forward to location.
- Location picker → выбор страны/таймзоны → завершение → success sticker (Channel A, mig 198/201).

## ⚠️ Update 2026-05-14 (mig 224): расширенная signature

```sql
public.reset_to_onboarding(p_telegram_id BIGINT, p_reset_referrer BOOLEAN DEFAULT TRUE)
```

Mig 224 закрыл gap из mig 203:

- **Безусловно** теперь обнуляется `subscription_status='free'` + `UPDATE user_subscriptions SET status='cancelled' WHERE active`.
- **Условно** (`p_reset_referrer=TRUE` default): `referrer_id=NULL`, `referral_count=0`, `paid_referral_count=0`.

**Product semantic change**: prod `cmd_start_fresh` теперь полностью обнуляет referrer link. Пригласитель теряет attribution если invitee делает start_fresh.

**Test-loop bug fix**: admin больше не может re-получить trial через `reset_to_onboarding(<self>)` — referrer_id обнуляется, auto-trial mig 034 не сработает.

Связан с [[concepts/subscription-management-headless]].

## Связанные KB

- [[concepts/start-fresh-gaps-2026-05-11]] — **identified production gaps** в `reset_to_onboarding` RPC (статус 'new' vs 'registration_step_1', `level=1` конфликт с finalize, неполный сброс полей). Mig 224 закрыл subscription/referrer gaps. Остальные production RPC gaps — отдельные миграции.
- [[concepts/start-fresh-flow]] — current `cmd_start_fresh` n8n + Python flow.
- [[concepts/phase4-onboarding-migration]] — gotchas #1-#33, история phenotype quiz Sub-FSM.
- [[concepts/sticker-architecture-adr]] — mig 198 unified sticker foundation + Stage 1.1 one-time semantics (mig 201).
- [[concepts/soft-delete-account]] — full deletion lifecycle (Phase 1-4) + 30-day grace window.
- [[concepts/release-protocol]] — параллельные агенты, mig-number reservation.

## Reusability

Если хочешь автоматизировать, сохрани script под `scripts/reset_test_user.sql` в основном репо (с placeholder для telegram_id) и используй как:

```bash
psql "$DATABASE_URL" -v telegram_id=786301802 -f scripts/reset_test_user.sql
```

Replace `WHERE telegram_id = <TARGET_TELEGRAM_ID>` на `WHERE telegram_id = :telegram_id`.
