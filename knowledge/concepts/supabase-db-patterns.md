---
title: "Supabase DB Patterns"
aliases: [migrations, check-constraints, schema-cleanup, rpc-patterns, sargable, indexes]
tags: [supabase, database, migrations, patterns, performance]
sources:
  - "daily/2026-04-08.md"
  - "daily/2026-04-09.md"
  - "daily/2026-04-10.md"
  - "daily/2026-04-11.md"
  - "daily/2026-04-13.md"
  - "daily/2026-04-14.md"
  - "daily/2026-04-16.md"
  - "daily/2026-04-19.md"
  - "daily/2026-04-21.md"
  - "daily/2026-04-22.md"
  - "daily/2026-04-24.md"
  - "daily/2026-04-25.md"
created: 2026-04-08
updated: 2026-04-25
---

# Supabase DB Patterns

Patterns and conventions for Supabase schema management, migrations, and data integrity in the NOMS project.

## Key Points

- **Migration method:** psycopg2 direct connection fails (DNS issue on Mac) — use Supabase REST API or n8n temp workflow with credential `Postgres_pooler_6543` (ID: `e9Rza51wAsB6UmU3`)
- **CHECK constraints as safety net:** DB-level guards (e.g., `chk_weight`, `chk_mana_nonneg`) protect against anomalous data that bypasses RPC logic
- **v_user_context is the performance hub:** All per-user context (translations, constants, user data) is bundled into one view, fetched once per request; uses `app_constants_cache` CROSS JOIN since migration 054
- **Sargable queries:** Always use range conditions (`col >= v_start AND col < v_end`) not function wrappers (`DATE(col) = X`) — the latter prevents index use even with perfect indexes in place
- **RPC-first:** All business logic belongs in PostgreSQL functions, not in Python or n8n; Python/n8n are orchestrators only

## Details

### Migrations 039–042 (2026-04-08)

**Migration 039** cleaned `v_user_context` by removing the deprecated `credits` column (which was leaking into the Dispatcher payload) and dropped `ai_response_payload` from `food_logs` (100% NULL, leftover from an unrealized feature).

**Migration 040** added a 6th parameter `p_image_url TEXT DEFAULT NULL` to `log_meal_transaction`, enabling photo URLs to be stored in `food_logs.image_url`. Previously, photos were recognized by AI but the file URL was never persisted.

**Migration 041** added CHECK constraints as a data integrity safety net:
- `chk_weight` / `chk_height`: minimum values (height ≥ 100 cm, accounting for an existing user at 100.2)
- `chk_target_cal`: positive calorie target
- `chk_mana_nonneg`: mana cannot go negative
- `chk_food_cal_nonneg`: food log calories cannot be negative

These guard against data corruption that might bypass RPC validation (e.g., direct REST calls with bad payloads).

**Migration 042** introduced the NPC bot system — see [[concepts/league-npc-system]] for details.

### Migrations 043–050 (2026-04-09)

**Migration 043** added `sync_user_profile(telegram_id, first_name, username)` RPC — updates user name fields on change and `last_active_at` with a 5-minute debounce. Previously `username` was never saved and `last_active_at` only updated on food logs.

**Migration 044** added `display_name` column to `v_user_context` (`COALESCE(first_name, username, 'User')`), added `display_name` to `cron_get_reminder_candidates` output, normalized `pt-BR`/`zh-CN` language codes to `pt`/`en`. Real lang_codes in DB: `ar, de, en, es, fa, fr, hi, id, it, pl, pt, ru, uk`.

**Migration 045** fixed `get_league_standings` v3: real users now read `u.league_xp_weekly` (not `lm.xp_earned`). One-time UPDATE synced `xp_earned = league_xp_weekly` for the current group.

**Migration 046** reset `league_xp_weekly` from all-time XP to current-week-only via a one-time UPDATE from `xp_events`. Added `MANA_ALREADY_FULL` guard to `recharge_mana_with_coins` RPC (prevents coin drain when mana is already full). Fixed `{icon_premium}` → `{{icon_premium}}` in `ui_translations` (Template Engine requires double-braces).

**Migration 047** removed dead columns: `users.credits`, `users.auth_user_id`, `users.edit_attempts`, `food_logs.tokens_used`, `food_logs.health_score` (all 100% NULL). Removed 3 broken RLS policies that depended on `auth_user_id` (always NULL — bot uses service_role, not JWT auth).

**Migrations 048–050** added `app_constants` keys for payment (TON wallet, crypto prices, Stars prices) and enhanced `get_day_summary` with `xp_today` and `streak_current` fields.

### Migrations 051–055 (2026-04-10)

**Migration 051** rewrote payment region/pricing RPCs:
- `get_pricing_region()`: JSON-based → reads `ref_countries.pricing_tier` (was returning DEFAULT for all users)
- `get_user_price()`: rewritten to query `subscription_prices` table
- `get_all_plan_prices(telegram_id)` (new): returns 3 plans with prices in user's currency + Stars + USDT in a single call

**Migration 052** added 3 composite indexes on `food_logs`:
- `idx_food_logs_user_consumed (telegram_id, consumed_at DESC)` — for get_day_summary
- `idx_food_logs_user_created (telegram_id, created_at DESC)` — for edit workflows
- `idx_food_logs_meal_id (meal_id)` — for meal detail lookups
Total: 7 indexes on the table (4 pre-existing + 3 new).

**Migration 053** fixed `get_day_summary` for index sargability. The original query used `DATE(created_at AT TIME ZONE 'UTC') = CURRENT_DATE` — a function wrapper that prevents PostgreSQL from using any index. Rewritten to:
```sql
consumed_at >= v_day_start AND consumed_at < v_day_end
```
Day boundaries calculated once in `DECLARE`. All 4 internal queries now use indexes. Lesson: adding indexes alone is not enough — queries must be sargable (no function wrappers around indexed columns).

**Migration 054** added `app_constants_cache` table — a single-row JSONB cache with an `AFTER INSERT/UPDATE/DELETE` trigger on `app_constants` that refreshes the cache. `v_user_context` was recreated to use `CROSS JOIN app_constants_cache` instead of `SELECT jsonb_object_agg(...)` subquery. Saves ~30-50ms per request. See [[concepts/n8n-performance-optimization]] for details.

**Migration 055** added personalized macro targets — see [[concepts/personalized-macro-split]] for full details. Added 7 columns to `users`, 25 app_constants, and new RPCs `set_user_training_type` and `set_user_goal_speed`.

### Migration 056 (2026-04-11)

**Migration 056** recreated `v_user_context` via `DROP VIEW + CREATE VIEW` (not `CREATE OR REPLACE VIEW`) to add `u.last_bot_message_id` (needed for the "One Menu" UX feature) and to backfill `training_type`, `phenotype`, `goal_speed`, `target_protein_g`, `target_fat_g`, `target_carbs_g`, and `target_weight_kg` columns from migration 055 that had not been included in the live view.

**Why DROP + CREATE instead of CREATE OR REPLACE:** PostgreSQL's `CREATE OR REPLACE VIEW` cannot change the position of existing columns — it can only add new columns at the end or replace a column at the same position with the same type. Since the new columns needed to be interspersed with existing ones, a full drop and recreate was required. The view had 43 columns after migration 056.

Applied via n8n temp workflow (Postgres pooler credential).

### Migrations 057–060 (2026-04-13)

**Migration 057** applied two security fixes:
1. `ALTER TABLE app_constants_cache ENABLE ROW LEVEL SECURITY` — `app_constants_cache` was the only table in the schema without RLS. Now all tables have RLS enabled.
2. Added `log_fasting_meal(p_telegram_id BIGINT)` RPC — wraps `log_meal_transaction` with `input_source='fasting'`, enforces 1-per-day limit via sargable range query, returns `ALREADY_FASTED` on repeat. Added `icon_fasting='🤐'` to `app_constants`. Added 4 translation keys × 13 langs: `progress.skip_button`, `progress.skip_confirm`, `progress.skip_already`, `progress.skip_no_mana`.

See [[concepts/fasting-feature]] and [[concepts/supabase-security]] for details.

**Migration 058** applied three changes:
1. `REVOKE ALL ON v_user_context FROM anon, authenticated; GRANT SELECT ON v_user_context TO service_role` — restricts the PII-containing view to service_role only.
2. Added `bot_xp_base_offset INTEGER DEFAULT 0` column to `users` — gives bots a starting XP on Monday morning so the leaderboard is non-empty at week start. Updated `get_league_standings` to v4: `bot_xp_base_offset + bot_xp_per_day × days_since_monday`.
3. Added `cron_get_renewal_candidates()` RPC — properly calculates subscription expiry date math in SQL (PostgREST REST filters cannot evaluate `now() + interval '2 days'` — they silently return all rows).

See [[concepts/supabase-security]] for the REVOKE details. See [[concepts/league-npc-system]] for the XP formula changes.

**Migration 059** applied three changes:
1. **Bot humanization columns:** Added `bot_xp_rate_min`, `bot_xp_rate_max`, `bot_weekly_seed` to `users`. Updated `get_league_standings` to v5 using `hashtext()` for deterministic-but-weekly-random rates plus daily jitter. Added `rotate_bot_weekly_seeds()` RPC. Added shadow bot mechanic. Added `is_new_week` flag to standings response.
2. **Regional Stars/USDT pricing:** Added `stars_price INTEGER` and `usdt_price NUMERIC(10,2)` columns to `subscription_prices` table. Filled 30 rows (10 regions × 3 plans). Updated `get_all_plan_prices()` to read from the table instead of `app_constants`. Deprecated `app_constants.stars_price_*` and `app_constants.crypto_price_*`.
3. **plan_label fix:** Translation key `payment.plan_label` had `{name}` placeholder (conflicted with `display_name` substitution) — renamed to `{plan}` in all 13 languages.

See [[concepts/league-npc-system]] for bot humanization details. See [[concepts/payment-integration]] for pricing details.

**Migration 060** applied:
1. `cron_get_league_fomo_candidates()` RPC — returns users eligible for Sunday FOMO push (local Sunday check, hour from app_constants, dedup via notification_log).
2. 4 FOMO translation keys × 13 langs: `league_fomo_leader`, `league_fomo_promote`, `league_fomo_demote`, `league_fomo_safe` with `{name}`, `{rank}`, `{gap}`, `{xp}` placeholders.
3. Updated 3 league result keys × 13 langs: `league_promoted`, `league_demoted`, `league_result` — added `{xp}` and `{rank}` placeholders.

See [[concepts/league-fomo-push]] for details.

### Migration 062 (2026-04-14)

**Migration 062** изменила поведение `check_and_deduct_mana` RPC для Premium-пользователей:

До migration 062: Premium-пользователи полностью обходили проверку маны (`bypass for premium`) — мана никогда не списывалась.

После migration 062:
- Premium mana pool: **500 единиц** (используется как safety net)
- Мана списывается при каждом логе еды (как у free-пользователей)
- Когда Premium-мана достигает 0 → функция возвращает ошибку `PREMIUM_LIMIT`
- На ошибку `PREMIUM_LIMIT` бот показывает сообщение "обратитесь к @AutoRiot" вместо стандартного "нет маны"

**Логика:** Premium-пользователь с 500 маной может сделать ~500 логов еды до hit'а лимита — это практически неограниченно для реального использования. Safety net защищает от злоупотреблений (боты, автоматические спам-логи), не ограничивая нормальных пользователей.

### Migration application method

Direct psycopg2 connection from Mac fails due to DNS resolution issues with Supabase pooler host. Two working alternatives:
1. **Supabase REST API:** For simple DDL, use `POST /rest/v1/rpc/<function_name>` with service_role key
2. **n8n temp workflow:** Create a workflow with a Webhook trigger and a Postgres node using credential `Postgres_pooler_6543` → trigger it → delete the workflow. This is the standard pattern for complex migrations.

### Sargability rule

The pattern `DATE(column AT TIME ZONE 'UTC') = CURRENT_DATE` is non-sargable: it applies a function to the column, preventing PostgreSQL from using B-tree indexes. The correct pattern is a range scan:
```sql
DECLARE v_day_start TIMESTAMPTZ := date_trunc('day', now() AT TIME ZONE user_tz);
DECLARE v_day_end   TIMESTAMPTZ := v_day_start + interval '1 day';
...
WHERE col >= v_day_start AND col < v_day_end
```
Compute boundaries once, use them everywhere in the function body.

### PostgREST date arithmetic limitation

PostgREST REST filters (e.g., `?expires_at=lt.now()+interval '2 days'`) do NOT evaluate interval arithmetic — the condition is silently ignored and all rows matching the other conditions are returned. This caused the renewal reminder cron to message all active subscribers every day.

**Rule:** Never use interval arithmetic in PostgREST REST filter query strings. Always move date range calculations into an RPC function where full SQL is available.

### Migrations 081–090 (2026-04-19) — Headless Architecture Infrastructure

Этот блок миграций реализовал Headless Architecture Variant C — конфигурационно-управляемый UI через таблицы `ui_screens` / `ui_screen_buttons` и центральные RPC `render_screen` / `process_user_input`. Полное описание архитектуры: [[concepts/headless-architecture]].

**Migration 081** создала фундамент config-driven UI:
- Таблица `ui_screens` (15 колонок): `id TEXT PK`, `name`, `text_key`, `render_strategy`, `input_type`, `save_rpc`, `back_screen_id_default`, `visible_condition_rpc`, `business_data_rpc`, `next_on_submit`, `workflow_id`, `icon_const_key`, `sort_order`, `created_at`, `updated_at`.
- Таблица `ui_screen_buttons` (9 колонок): `button_id TEXT PK`, `screen_id TEXT FK`, `button_key`, `callback_data`, `icon_const_key`, `visible_condition`, `sort_order`, `meta JSONB`, `created_at`.
- Добавлены колонки `screen_id` и `save_rpc` в таблицу `workflow_states`.

**Migration 082** — ОТМЕНЕНА. Первоначально планировалось перенести render_template в SQL, но принято решение оставить рендеринг шаблонов в n8n JS согласно TMA (Telegram Mini App) контракту.

**Migration 083** ввела `render_screen(p_telegram_id BIGINT, p_screen_id TEXT) → JSONB` — чистая функция (`SECURITY DEFINER`). Возвращает структуру `{screen_id, business_data, telegram_ui: {text_key, keyboard, render_strategy}}`. Функция вызывает `business_data_rpc` для получения данных экрана и формирует keyboard из `ui_screen_buttons`, фильтруя кнопки по `visible_condition`.

**Migration 084** ввела `process_user_input(p_tg_id BIGINT, p_action_type TEXT, p_payload JSONB, p_cb_ctx JSONB, p_skip_debounce BOOLEAN) → JSONB` — центральный обработчик всех действий пользователя. Три вспомогательные функции:
- `matches_callback_template(TEXT, TEXT) → BOOLEAN` — проверяет соответствие callback_data шаблону с wildcard `*`.
- `extract_callback_vars(TEXT, TEXT) → JSONB` — извлекает переменные из callback_data по шаблону.
- `validate_text_input(TEXT, TEXT, JSONB) → JSONB` — валидирует текстовый ввод согласно `input_type` экрана.

**Migration 085** добавила 13 wrapper-функций `get_*_business_data`: `get_profile_business_data`, `get_stats_business_data`, `get_progress_business_data`, `get_league_business_data`, `get_friends_business_data`, `get_shop_business_data`, `get_quests_business_data`, `get_my_plan_business_data`, `get_settings_business_data`, `get_payout_business_data`, `get_phenotype_business_data`, `get_help_business_data`, `get_personal_metrics_business_data`. Каждая оборачивает соответствующий существующий RPC и возвращает данные в формате, совместимом с `render_screen`.

**Migration 086** наполнила таблицы данными для 9 пилотных экранов: `profile_main`, `my_plan`, `settings`, `personal_metrics`, `help`, `ask_weight`, `ask_age`, `ask_height`, `delete_account_confirm`. Вставлено 30 кнопок, 6 translation keys × 13 языков. Обновлены 3 строки `workflow_states`: `edit_weight → {screen_id: ask_weight, save_rpc: set_user_weight}` и аналогичные.

**Migration 087 (v1..v4)** — итерационная (4 версии). Добавлены текстовые шаблоны для 6 экранов × 13 языков в `ui_translations`. Пользователь итерировал контент 4 раза для финального варианта.

**Migration 088** заполнила `meta.target_screen` и `meta.set_status` для 9 кнопок. Обновлена `process_user_input` для чтения `set_status` из `meta` и соответствующего обновления статуса пользователя.

**Migration 089** — критический фикс: в теле `process_user_input` проверка `v_button IS NOT NULL` заменена на `v_button.button_id IS NOT NULL`. PostgreSQL RECORD-тип никогда не бывает NULL как целое — при отсутствии строки RECORD возвращается пустым, но `IS NOT NULL` возвращает TRUE. Необходимо проверять конкретное поле (`button_id`), чтобы обнаружить отсутствие записи. Это типичный gotcha при работе с `SELECT INTO v_record FROM table WHERE ...`.

**Migration 090** добавила 4 недостающих перевода кнопок × 13 языков: `edit_training`, `edit_phenotype`, `edit_language`, `confirm_delete`.

#### Паттерны из блока 081–090

**RECORD IS NOT NULL gotcha** (migration 089): при `SELECT INTO v_rec FROM t WHERE id = x` — если строка не найдена, переменная `v_rec` содержит RECORD с NULL-полями, но `v_rec IS NOT NULL = TRUE`. Корректная проверка: `v_rec.id IS NOT NULL` (или любое NOT NULL поле).

**Итерационные миграции** (migration 087 v1..v4): при работе с переводами лучше применять DROP + CREATE миграцию по одной, получая обратную связь от пользователя перед финальным применением. Не объединять UI-контент и схему в одну миграцию.

**Cancelled migration pattern** (migration 082): если миграция отменяется — документировать причину в комментарии, не удалять номер из последовательности. Это сохраняет непрерывность нумерации для аудита.

### Migrations 091–093 (2026-04-19) — Headless Architecture Phase 2 Stabilization

Стабилизационный блок после первого E2E прогона Profile v5 pilot. Все три применены автономно через psycopg2, без n8n PUT.

**Migration 091** (`091_profile_pilot_business_data_fixes.sql`) — два business data фикса:
1. `get_my_plan_business_data`: добавлен `goal_type` (читается из `v_user_context.goal_type`). Шаблон `profile.my_plan_text` содержал `{goal_type}` во всех 13 языках, но RPC его не возвращал → пользователь видел literal `{goal_type}`.
2. `get_personal_metrics_business_data`: заменена stub-реализация из migration 085 (возвращала `{}`) на полноценную. Возвращает `weight_kg, height_cm, gender, birth_date, age, target_weight_kg` из `v_user_context`. Stub вызывал crash 04_Menu_v3 (execution 9533).

**Migration 092** (`092_process_user_input_back_fixes.sql`) — перезаписывает `process_user_input` из migration 089 с тремя улучшениями:
1. **Status reset при Back:** при `action_type='callback'`, `callback_data='cmd_back'`, `current_screen.input_type='text_input'` → `UPDATE users SET status='registered'`. Без этого фикса пользователь оставался в `status='edit_weight'` после нажатия Cancel → следующий text input уходил в `set_user_weight` silent mutation.
2. **Валидация v_next_screen:** `v_next_screen` из `back_nav()` проверяется против таблицы `ui_screens`. Если экрана нет (legacy nav_stack entry) → fallback через `back_screen_id_default` → `profile_main`.
3. **DATA CLEANUP:** `UPDATE users SET nav_stack = filter(existing ui_screens)`. 2 затронутых пользователя: admin 417002669 (`['profile']` → `['profile_main']`), user 786301802 (`['profile','help','friends_info']` → `['help']`).

Паттерн data cleanup в миграции: встраивать одноразовые `UPDATE` прямо в migration SQL для синхронизации legacy данных при добавлении валидации.

**Migration 093** (`093_profile_markdown_to_html.sql`) — конвертация Markdown bold → HTML:
- 04_Menu_v3 Dumb Renderer hardcode'ит `parse_mode: 'HTML'`, но migration 087_v4_final заполняла шаблоны `**bold**` (Markdown синтаксис). Результат: пользователь видел literal `**Profile**`.
- Решение: конвертировать templates в HTML (не менять renderer) — одна SQL миграция без n8n PUT.
- Regexp `\*\*([^*\n]+)\*\*` → `<b>\1</b>` для 5 ключей: `profile.main_text`, `profile.my_plan_text`, `profile.settings_text`, `profile.personal_metrics_text`, `profile.help_text` × 13 языков.
- После: 0 остатков `**` в Profile v5 ключах.

**Правило:** при фиксированном `parse_mode` в рендерере — все шаблоны в `ui_translations` для соответствующих экранов должны следовать тому же формату. Смешивание Markdown и HTML в одном рендерере — баг.

### Migrations 095-098 (2026-04-20) — Headless Architecture Sessions 7-8

**Migration 095** (`095_hotfix_routing_and_records.sql`) — 5 изменений в `process_user_input` (перезапись на основе migration 089):

1. **Hybrid cascade state resolution:** определение current_screen теперь идёт по трём уровням: (a) `workflow_states` по `users.status`; (b) если не найдено — `nav_stack->>-1` (PG 15 JSONB negative indexing); (c) дефолт `profile_main`.

2. **RECORD gotcha fix:** `FOR loop + v_button := NULL` → `SELECT INTO v_button ... LIMIT 1; IF FOUND THEN ... END IF`. Устраняет SQLSTATE 55000 "record v_button is not assigned yet" при матчинге кнопки.

3. **push_nav семантика:** `push_nav(v_current_screen)` → `push_nav(v_next_screen)` + `IS DISTINCT FROM` guard (не пушить если top стека = v_next_screen). Устраняет дублирование в стеке.

4. **Status reset расширен:** при `cmd_back` сбрасывает `status='registered'` при `input_type='text_input' OR v_save_rpc IS NOT NULL` (было: только `input_type='text_input'`). Future-proof для inline_kb process states.

5. **DDL:** `CHECK (length(callback_data) <= 64)` на `ui_screen_buttons`. Применён через `DO $$ BEGIN ALTER TABLE... EXCEPTION WHEN duplicate_object THEN NULL; END $$` паттерн.

**Migration 096** (`096_rpc_validate_screen_exists.sql`) — defensive patch поверх 095:
- Existence guard между hybrid cascade step 2 (nav_stack->>-1) и fallback: если screen_id не существует в `ui_screens` → NULL → следующий шаг (fallback profile_main).
- Повторный data cleanup `users.nav_stack` (legacy 'profile' → 'profile_main' фильтрация).
- Валидация `back_nav` result: если `parent` не в `ui_screens` → fallback через `back_screen_id_default`.

**Migration 097** (`097_rpc_override_strategy_for_text.sql`) — BUG 1 root cause fix:
- При `p_action_type='text'` или пустом `cb_ctx.callback_message_id` → override `render_strategy='delete_and_send_new'`.
- Без этого: RPC возвращал `render_strategy='replace_existing'` с пустым callback_message_id → n8n вызывал `editMessageText(message_id=0)` → Telegram 400.

**Migration 098** (`098_rpc_success_reaction.sql`) — UX паттерн text save:
- При `p_action_type='text' AND v_save_ok` → добавляет `telegram_ui.success_reaction='👌'`.
- n8n workflow читает поле и ставит реакцию через `setMessageReaction` на user's message.
- Без reaction при validation_error или save_rpc_failed (юзер понимает что-то пошло не так).

#### Паттерны из migrations 095-098

**Hybrid cascade state resolution** (migration 095): при headless архитектуре статус пользователя может находиться в двух местах: `users.status` (процессные FSM-статусы) и `users.nav_stack` (экраны навигации). Корректный порядок разрешения: workflow_states → nav_stack top → default screen.

**RECORD IS NOT NULL gotcha (расширение от migration 089):** PostgreSQL `SELECT INTO v_rec` при отсутствии строки возвращает RECORD с NULL-полями. Проверка `v_rec IS NOT NULL` вернёт TRUE даже для "пустого" RECORD. Правильные паттерны:
- Использовать `IF FOUND THEN` после `SELECT INTO`
- Либо проверять конкретное NOT NULL поле: `IF v_rec.id IS NOT NULL THEN`

**Success reaction pattern** (migration 098): вместо отдельного toast-сообщения "✅ Сохранено" — Telegram реакция 👌 на user-сообщение. Преимущества: мгновенный ack, чистый чат (нет accumulation), universally consistent. Реализация через `telegram_ui.success_reaction` поле — n8n fire-and-forget ветка без изменений прикладных RPC.

### Migrations 100+101 (2026-04-20) — Profile Agent Dossier Pure Headless

**Migration 100** (`100_profile_business_data_extended.sql`) — расширение `get_profile_business_data`:
- Поля 1-26 без изменений (существующие метрики профиля)
- 7 новых полей: `sage_tier` (MONW/obese/athlete/default → group key), `limit_variant` (subscription_status → trial/active/free), `sage_quote_index` (случайная цитата), `sage_quote_text` (локализованный текст), `member_since_month`, `member_since_year`, `subscription_status_display` (локализованная метка статуса)
- Calendar translations × 13 langs добавлены в `ui_translations` (месяцы, единицы измерения, форматы дат)

Ключевой паттерн: **helper-поля как group mapping.** Вместо передачи в шаблон сырых значений (`phenotype_type='MONW'`) RPC вычисляет `sage_tier='monw'` — Dumb Renderer просто подставляет в `{{sage_{sage_tier}}}`. Это исключает missing-key ошибки для промежуточных статусов (например, `trial` subscription при `limit_variant`).

**Migration 101** (`101_profile_main_text_template.sql`) — универсальный шаблон Profile Main Screen:
- Ключ `profile.main_text` × 13 langs в `ui_translations`
- Agent Dossier layout: секции (Agent ID, Sassy Sage quote, цели, физические параметры, геолокация, дата, статус подписки, лимиты)
- Nested placeholder синтаксис: `{{goal_{goal_type}}}`, `{{sage_{sage_tier}}}`, `{{limit_badge_{limit_variant}}}` — разворачивается через multi-pass Dumb Renderer
- **Pure Headless:** вся верстка Profile Main Screen живёт в БД, не в n8n JS

#### Паттерны из migrations 100-101

**Helper-поля для group mapping:** при наличии категориальных переменных с несколькими enum-значениями, которые должны маппиться на подмножество translation-ключей (например, 4 phenotype → 2 visual группы, 3 subscription statuses → 2 display варианта) — вычислять helper-поле в SQL RPC, не в JS Renderer. Это делает шаблон стабильным и предотвращает missing-key ошибки при добавлении новых enum-значений.

**Nested placeholder синтаксис:** `{{group_{variable}}}` — вложенный placeholder разворачивается за 2 прохода: первый проход заменяет `{variable}` → значение, второй — `{{group_value}}` → emoji/текст из app_constants. Требует multi-pass Renderer с stability loop (`iter < 5`, exit при отсутствии изменений).

### Migration 109 (2026-04-21) — Python Proxy Indicator RPCs

**Migration 109** (`109_indicator_context_rpcs.sql`) — два новых RPC для Python proxy typing indicator:

`get_indicator_context(telegram_id BIGINT) → JSONB`:
- Атомарно читает: `status`, `last_indicator_index` (для ротации 3 стикеров), `last_text_indicator_date` (1 текстовый вариант в день), `language_code`
- Один round-trip вместо двух (заменяет: get_user_context + save separately)
- Вызывается Python proxy ПЕРЕД форвардингом в n8n

`save_indicator_state(telegram_id BIGINT, message_id BIGINT, new_index INT DEFAULT NULL, new_text_date DATE DEFAULT NULL) → VOID`:
- Атомарно: UPDATE `last_bot_message_id` + `last_indicator_index` + `last_text_indicator_date`
- `new_index` и `new_text_date` — NULL если не нужно обновлять
- Существующие `save_bot_message()` / `clear_bot_message()` НЕ тронуты — продолжают использоваться `03_AI_Engine` и `06_Indicator_Clear`

Контекст: Python proxy (git commit `02931fe`) — full details в [[concepts/telegram-proxy-indicator]].

### Migrations 104–108 (2026-04-21) — Sassy Sage Dialog Variants

Серия миграций создала JSONB-массивы из 3 вариантов в `ui_translations` для вариативных ответов Sassy Sage.

**Deep-merge правило (критично):** Использовать `jsonb_set(content, '{section,key}', '[...]'::jsonb)`, НЕ `content || '{section:{key:[...]}}'::jsonb`. Shallow merge (`||`) стирает все соседние ключи в секции.

**Self-referential UPDATE (migration 107):** Для синхронизации legacy scalar ключей с вариантами — копировать `content -> 'section' -> 'array_key' -> 0` в scalar key. Гарантирует стилевую консистентность.

**Scale verification паттерн:** после apply — независимый SELECT `jsonb_array_length(content->section->key) = 3` для всех ключей × 13 langs. При 19 ключах = 247 проверок.

Full details: [[concepts/sassy-sage-dialog-variants]].

### Migrations 116–121 (2026-04-22) — Profile v5 Polish + back_nav Anchor Fallback

**Migrations 116–120** — Session 10 финальный блок (Profile v5 inline picker polish):

- **116:** Dispatcher Route Classifier — picker callbacks всегда роутятся в `menu_v3` без guard по `user.status`. Фикс timezone формата `UTCSG0002:00` → `UTC+02:00`. Revert `success_reaction` 👌 для `delete_and_send_new` стратегии.
- **117:** `cmd_back` priority = `back_screen_id_default` FIRST (иерархический), затем `nav_stack` fallback. Unique icons для notification options (🧘/⚖️/🔥).
- **118:** Убрана `success_reaction` эмиссия для callback saves (callback saves не создают user message → нет объекта для реакции). Stripped literal `{pct}%` из `profile.speed_deficit/surplus`.
- **119:** `cmd_select_none` ("Нет тренировок") → отдельное значение `none`; `set_user_training_type` расширен CASE. Country/timezone triggers unhidden в UI. `cmd_back` hidden в онбординге на `edit_*` экранах.
- **120:** `edit_country`/`edit_timezone` → 2-button inline_kb entry screen (📍 Auto / 📋 Выбрать список). Translations × 13. Dispatcher Route Classifier: `cmd_auto_location`/`cmd_list_countries`/`cmd_list_timezones` → legacy 05_Location.

**Migration 121** (`121_back_nav_anchor_fallback.sql`) — фикс `back_nav` при пустом стеке после `clear_status=true`:

**Проблема:** `cmd_lang_ru` на `edit_lang` → `clear_status=true` → `status='registered'`, `nav_stack=[]` → следующий `cmd_back` → `back_nav` возвращает `{parent: NULL}` → UI зависает.

**Новая сигнатура:**

```sql
back_nav(p_telegram_id bigint, p_current_screen text DEFAULT NULL) RETURNS jsonb
```

**3-приоритетная цепочка anchor fallback:**

```
1. stack non-empty → нормальный pop
   Edge: pop → empty → parent=NULL → ui_screens[popped].back_screen_id_default
2. stack empty + p_current_screen → ui_screens[p_current_screen].back_screen_id_default
3. stack empty + no hint → workflow_states[users.status].screen_id → его back_screen_id_default
Fallback: {parent: NULL, source: 'empty_no_anchor'} (caller: hard fallback profile_main)
```

**`source` поле для debug:** `stack` | `anchor_after_pop` | `anchor_from_param` | `anchor_from_status` | `empty_no_anchor` | `user_not_found`

**Патч `process_user_input`:** `back_nav(p_telegram_id)` → `back_nav(p_telegram_id, v_current_screen)`. 2 строки, idempotent DO block.

**E2E verification:** 7 сценариев на ephemeral user `telegram_id=99999999991`. Anchor покрывает 17 из 18 экранов (исключение: `profile_main` — это root, `back_screen_id_default=NULL` ожидаемо).

#### Паттерн: передавать hint-экран в RPC до изменения статуса

При любом RPC, который изменяет `users.status` или `nav_stack`, вызывающая сторона должна вычислить `v_current_screen` ДО изменения и передать его как параметр. Это предотвращает "context loss" когда cleanup операции уничтожают информацию о текущем экране.

```sql
-- Правильно: v_current_screen вычислен ДО блока обработки callback
v_current_screen := resolve_current_screen(p_telegram_id);
-- ... обработка callback, возможно clear_status, push/pop nav ...
v_back_result := back_nav(p_telegram_id, v_current_screen);  -- hint передан
```

### Migrations 122–123 (2026-04-23) — Stats Main Headless Phase 3A

**Migration 122** (`122_stats_main_headless.sql`, 344 lines) — первый экран Phase 3A:

1. **`get_stats_business_data(p_telegram_id BIGINT) → JSONB`** — wrapper поверх существующего `get_day_summary`. Вызывает `get_day_summary` + обогащает данными из `v_user_context` (calorie_goal, targets, language_code, display_name).

2. **`ui_screens` запись:** `stats_main` с `input_type='inline_kb'`, `render_strategy='replace_existing'`, `business_data_rpc='get_stats_business_data'`, `validation_rules='{}'::jsonb` (обязательно — NOT NULL колонка).

3. **3 кнопки** в `ui_screen_buttons`: `add_food`, `history`, `edit_last`.

4. **`stats.*` ключи × 13 языков** — новые ключи для экрана статистики.

**Adversarial review поймал 3 критических проблемы перед apply:**
- Literal `💬` → должно быть `{{icon_speech}}`
- Literal `⭐` → должно быть `{{icon_stars}}`
- `validation_rules` без значения → нарушение NOT NULL constraint. Фикс: явный `'{}'::jsonb`.

Dry-run паттерн (`BEGIN; ... ROLLBACK;`) подтвердил fix перед apply.

**Migration 123** (`123_stats_report_translations.sql`) — восполнение gap переводов + process_user_input fast-path:

**Gap fix:** Legacy n8n stats screen хранил строки `report.*` прямо в JS code нодах, не в `ui_translations`. При переходе на `{tr:report.*}` placeholder-ы ключи отсутствовали. Пользователь увидел литеральный текст `{tr:report.unit_kcal}` и др.

**Добавленные ключи (195+ строк):**
- `report.unit_kcal`, `report.unit_g`, `report.unit_per_100g`
- `report.streak_label`, `report.no_streak`
- `report.status_deficit`, `report.status_surplus`, `report.status_maintain`
- `report.meals_header`, `report.no_meals_today`
- 5 insight keys: `report.insight_*`

**Fast-path:** Добавлен top-level fast-path в `process_user_input` для `cmd_get_stats → stats_main`.

Использован `jsonb_set` deep-merge паттерн (стандарт NOMS — не shallow merge через `||`).

**Migration 124** (`124_stats_rewrite_spec_aligned.sql`, 408 строк) — полная перезапись stats headless RPC, aligned со spec §25:

1. **`get_daily_stats_rpc(p_telegram_id BIGINT) → JSONB`** — заменяет `get_stats_business_data`. Возвращает **FLAT top-level** поля (19 placeholder-ов). Нет вложенного `template_vars` wrapper — `render_screen` делает merge сам.

2. **Дизайн:**
   - Светофоры `p/f/c_status`: CASE по `app_constants.macro_threshold_*` (30/85/110%) — без хардкодов
   - `meals_list_formatted`: `string_agg + row_number()` с eager resolve `unit_kcal` из `ui_translations` per user language (fallback → `en` + `RAISE EXCEPTION`)
   - `no_meals_yet`: тоже eager resolve (не `{tr:}` placeholder внутри `{var}`)
   - `current_date`/`current_time`: `to_char(timezone(u.timezone, now()), ...)`
   - Zero hardcoded strings/icons/thresholds

3. **UI:** 1 кнопка `[✏️ Исправить]` с `visible_condition` на `meals > 0` (было: 3 кнопки)

4. **DDL:** `DROP FUNCTION get_stats_business_data` + обновление `ui_screens.stats_main.business_data_rpc`

5. **Bugs поймано при review + dry-run (3)** и **после apply (2):**
   - Double-nested `template_vars`: RPC оборачивал в key `template_vars` → `render_screen` оборачивал повторно → flat переменные недоступны. Fix: RPC возвращает FLAT.
   - `{tr:}` inside `{var}` не резолвится: Dumb Renderer делает sequential pass (tr → const → var), var pass однократный вне цикла. Fix: eager-resolve в RPC.
   - `validation_rules NOT NULL`, лишний `updated_at` в UPDATE, `RAISE NOTICE %%%` format — исправлено на dry-run.

**Translation Gap Pattern правило (из migration 123/124):** При миграции ЛЮБОГО legacy n8n экрана на headless — аудировать ВСЕ строки в JS code нодах и добавить их в `ui_translations` ДО перехода на `{tr:...}` placeholder-ы. Полное описание: [[concepts/stats-main-headless]].

### Migrations 140–141 (2026-04-25) — Debounce architectural fix

**Migration 140** (`140_debounce_window_500ms.sql`) — быстрый workaround: cooldown 1500ms → 500ms. Реализован через `pg_get_functiondef` REPLACE pattern (нет DDL изменений схемы, только логика).

**Migration 141** (`141_debounce_dedicated_column.sql`) — архитектурный фикс race condition:

**Проблема:** `debounce_user_action` и `Sync Profile` n8n нода читали/писали в одно поле `last_active_at`. SELECT-then-UPDATE в `debounce_user_action` не атомарен. `Sync Profile` мог записать новый `last_active_at` между SELECT и UPDATE в debounce → функция видела свежий timestamp → возвращала FALSE → запрос дропался без обработки.

**Решение:**

```sql
-- Новая колонка только для debounce (не трогает last_active_at):
ALTER TABLE users ADD COLUMN last_action_ms BIGINT;

-- Атомарный UPDATE WHERE — нет отдельного SELECT:
UPDATE users
SET    last_action_ms = v_now_ms
WHERE  telegram_id = p_telegram_id
  AND  (last_action_ms IS NULL OR last_action_ms < v_now_ms - p_cooldown_ms);
GET DIAGNOSTICS v_found = ROW_COUNT;
RETURN v_found > 0;
```

`last_active_at` остаётся нетронутым — cron/streak логика продолжает его использовать без изменений. `Sync Profile` нода перемещена из n8n в Python proxy (`maybe_sync_user_profile`) — источник гонки устранён.

Full details: [[concepts/anti-spam-debounce]].

## Related Concepts

- [[concepts/access-credentials]]
- [[concepts/noms-architecture]]
- [[concepts/league-npc-system]]
- [[concepts/personalized-macro-split]]
- [[concepts/n8n-performance-optimization]]
- [[concepts/supabase-security]]
- [[concepts/fasting-feature]]
- [[concepts/league-fomo-push]]

## Sources

- [[daily/2026-04-08.md]] — Migrations 039–042: schema cleanup, image_url storage, CHECK constraints, NPC bot system
- [[daily/2026-04-09.md]] — Migrations 043–050: sync_user_profile, display_name, language normalization, dead column cleanup, broken RLS removal, payment constants
- [[daily/2026-04-10.md]] — Migrations 051–055: regional pricing RPCs, food_logs indexes, sargability fix, app_constants_cache, personalized macro split
- [[daily/2026-04-11.md]] — Migration 056: v_user_context DROP+CREATE to add last_bot_message_id and backfill training_type/phenotype columns; DROP vs CREATE OR REPLACE limitation
- [[daily/2026-04-13.md]] — Migrations 057–060: RLS on app_constants_cache, log_fasting_meal RPC, REVOKE on v_user_context, bot_xp_base_offset, cron_get_renewal_candidates, bot humanization columns, regional Stars/USDT in subscription_prices, cron_get_league_fomo_candidates, FOMO translations
- [[daily/2026-04-14.md]] — Migration 062: check_and_deduct_mana теперь списывает ману у Premium (pool 500, safety net), возвращает PREMIUM_LIMIT при исчерпании
- [[daily/2026-04-16.md]] — Migration 067: get_league_standings v6 (bot spikes daily multiplier, last_seen_hours_ago field), cron_get_league_midweek_candidates RPC; migrations 068–074 спроектированы (Squad v2, ambassador program, payout_requests table)
- [[daily/2026-04-19.md]] — Migrations 081–090: Headless Architecture Infrastructure — ui_screens/ui_screen_buttons tables, render_screen RPC, process_user_input RPC + 3 helpers, 13 get_*_business_data wrappers, 9 pilot screens seeded, RECORD IS NOT NULL gotcha fix; Migrations 091–093: Phase 2 stabilization — business data fixes (goal_type, personal_metrics real impl), cmd_back status reset + nav_stack validation, Markdown→HTML template conversion
- [[daily/2026-04-21.md]] — Migration 109: get_indicator_context + save_indicator_state RPCs for Python proxy; Migrations 104–108: Sassy Sage dialog variants (JSONB array[3]), deep-merge jsonb_set rule, self-referential UPDATE sync, 741+ строк контента × 13 langs
- [[daily/2026-04-22.md]] — Migrations 116–120: Session 10 final polish (picker routing guard fix, cmd_back hierarchy, success_reaction callback fix, training none value, edit_country/timezone 2-button entry); Migration 121: back_nav anchor fallback (new signature + p_current_screen hint, 3-priority chain, source debug field, 7-scenario E2E)
- [[daily/2026-04-23.md]] — Migrations 122–124: Phase 3A stats_main headless. 122: get_stats_business_data wrapper + ui_screens seed + 3 buttons + stats.* keys; adversarial review caught 3 criticals. 123: report.* keys × 13 langs + process_user_input fast-path. 124: full rewrite → get_daily_stats_rpc FLAT + светофоры + meals_list_formatted + 1 button; caught double-nest + {tr:} inside {var} bugs post-apply.
- [[daily/2026-04-25.md]] — Migration 140: debounce cooldown 1500ms→500ms workaround. Migration 141: `users.last_action_ms BIGINT` + атомарный `UPDATE WHERE` в `debounce_user_action` — устранение race condition с n8n `Sync Profile` нодой; `last_active_at` остаётся для cron/streak.
