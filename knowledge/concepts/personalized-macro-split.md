---
title: "Personalized Macro Split"
aliases: [macro-split, training-type, phenotype, goal-speed, calculate-user-targets]
tags: [nutrition, gamification, supabase, onboarding, rpc]
sources:
  - "daily/2026-04-10.md"
  - "daily/2026-04-11.md"
  - "daily/2026-04-15.md"
  - "daily/2026-04-17.md"
  - "daily/2026-05-15.md"
  - "daily/2026-05-16.md"
created: 2026-04-10
updated: 2026-05-16
---

# Personalized Macro Split

Each user receives unique daily protein/fat/carbs targets computed from their body type, training style, and weight goal — replacing the previous one-size-fits-all macro percentages (30/25/45).

## Key Points

- **`calculate_user_targets` v3 RPC:** computes `target_protein_g`, `target_fat_g`, `target_carbs_g` from `training_type`, `phenotype`, `goal_speed`, `weight`, `height`
- **Three axes:** `training_type` (strength/cardio/mixed/sedentary) drives protein g/kg coefficients; `phenotype` (monw/athlete/obese/default) adjusts LBM proxy for the denominator; `goal_speed` (slow/normal/fast) applies calorie deficit/surplus
- **All coefficients in `app_constants`:** protein_g_per_kg_*, fat_pct_*, goal_speed_* — never hardcoded
- **7 new `users` columns:** `training_type`, `phenotype`, `goal_speed`, `target_weight_kg`, `target_protein_g`, `target_fat_g`, `target_carbs_g`, `phenotype_answers`
- **Auto-skip for sedentary:** `set_user_activity` v2 auto-sets `training_type=sedentary` and skips the training step in onboarding

## Details

### Calculation pipeline

```
Onboarding → gender, age, weight, height, activity_level, training_type, goal_type
                ↓
calculate_user_targets v3:
  1. LBM Proxy (target_weight) — from phenotype
  2. BMR (Mifflin-St Jeor) → TDEE × PAL
  3. Goal adjustment (goal_speed: slow/normal/fast)
  4. Protein = g/kg × target_weight (by training_type)
  5. Fat = % of kcal (by training_type), floor 0.8 g/kg
  6. Carbs = remainder, floor 50g
                ↓
Stored: target_calories, target_protein_g, target_fat_g, target_carbs_g → users
```

### Macro coefficients by training_type

| Training | Protein g/kg | Fat % kcal | Carbs |
|----------|-------------|------------|-------|
| strength | 2.0 | 25% | remainder |
| cardio | 1.4 | 20% | remainder |
| mixed | 1.6 | 25% | remainder |
| sedentary | 1.2 | 30% | remainder |

All four protein values are stored in `app_constants` as `protein_g_per_kg_strength`, `protein_g_per_kg_cardio`, etc.

### Goal speed modifiers

| Speed | Deficit (lose) | Surplus (gain) |
|-------|---------------|----------------|
| slow | 10% | 8% |
| normal | 15% | 10% |
| fast | 20% | 15% |

### LBM proxy by phenotype

- **monw** (metabolically obese normal weight): `weight × 0.85`
- **athlete**: `weight × 1.0`
- **obese**: `height − 100/110` (Broca formula)
- **default**: `weight × 1.0`

### Onboarding flow (7 steps after migration 055)

1. gender → step_2
2. age → step_3
3. weight → step_4
4. height → step_5
5. activity → **step_training** (sedentary → auto-skip)
6. training_type → step_goal
7. goal → registered

### v_user_context and get_day_summary

Migration 055 also added `training_type`, `phenotype`, `goal_speed`, `target_*_g`, `target_weight_kg` to `v_user_context`, and `get_day_summary` v3 now returns the personal macro targets alongside actuals. Build Stats Text v4 (n8n) displays macros as `actual/target g` using these personalized values.

### Backfill for existing users

One-time UPDATE derived `training_type` from existing `activity_level` values for all registered users who didn't go through the new onboarding flow.

### Profile UX: Build Profile Text v4.1 (2026-04-11)

The Profile screen was updated to display `training_type` and `goal_speed` in the "Твой план" section:
- `trainingMap` and `speedMap` translate enum values to user-readable labels using the user's language translations
- A 6-row keyboard was added with buttons for Training Type, Goal Speed, and 🧬 Телосложение (Phenotype)
- `cmd_edit_phenotype` → `coming_soon`: the Phenotype Quiz (Phase 2) backend spec exists but the UI is not yet implemented

A new translation key `profile.body_type` was added for all 13 languages to label the Phenotype button.

**Deployment note:** The update was done as a full keyboard rewrite rather than surgical patching. Replace-patch approach failed because the target strings in the live workflow didn't match the local file — a known risk when local files drift from live n8n state. When patches fail to match, rewrite the entire section from a fresh GET of the live workflow.

### Speed Edit flow в 04_Menu (2026-04-15)

Добавлена полная UI-цепочка редактирования `goal_speed` прямо из Profile экрана.

**4 новых ноды в 04_Menu (95 → 99 нод):**
1. **Prepare Speed Save** (Code) — маппинг `cmd_speed_slow/normal/fast` → key/name/icon
2. **Save Speed RPC** (HTTP Request) — `POST set_user_goal_speed` через Supabase credential
3. **Build Speed Confirmation** (Code) — payload для editMessageText с ✅ + Back кнопкой
4. **Send Speed Confirmation** (HTTP Request) — Telegram `editMessageText`

**Изменения в существующих нодах:**
- **Command Classifier v3.1:** добавлен маршрут `cmd_speed_*` → route `save_speed`
- **Menu Router:** добавлен 23-й output `save_speed` → Prepare Speed Save
- **Build Ask Markup:** новый `case 'edit_speed'`: 3 кнопки (🐢 Slow, ⚖️ Normal, 🚀 Fast) с ✅ на текущей скорости пользователя
- **Edit Type Router:** добавлен 6-й output `edit_speed` → Build Ask Markup
- **Build Profile Text v4.1:** кнопка Speed добавлена рядом с Goal в inline keyboard

**Данные для Speed Edit:** `goal_speed` теперь передаётся в Dispatcher "Prepare for 04" (поле добавлено как часть Phase 4 callback pipeline fix) и в Merge Data v3.3 в 04_Menu.

**Проверка статуса:** user 417002669 был в state `edit_speed` от предыдущей сессии → сброшен в `registered` вручную.

### Phase 2 and Phase 3 (future)

- **Phase 2 (Phenotype Quiz):** 4 heuristic questions to classify phenotype automatically. Spec: `.claude/specs/phenotype_quiz_spec.md`
- **Phase 3 (Adaptive Modifiers):** Sleep deprivation → +15% protein; stress → +10% carbs; PMS → +150-200 kcal. Spec: `.claude/specs/adaptive_modifiers_spec.md`

### Dual Render для edit pickers goal/training/activity (2026-04-17)

`chk*()` helpers (✅ на текущем значении) расширены на `goal`, `training`, `activity`, `gender` pickers в двух местах:
1. `02_Onboarding → Response Builder` — для inline пикеров (goalInlineKB, trainingInlineKB)
2. `04_Menu → Build Ask Markup` — для reply keyboard edit cases (edit_activity, edit_gender)

Полный паттерн и список 9 edit cases: [[concepts/edit-picker-dual-render]].

### v4 — mig 227 (2026-05-15): PAL fusion + 'none' coefficients + target rebalance

Аудит v3 выявил три системные проблемы; исправлены без изменения UI и схемы.

**Что починили:**

1. **PAL fusion.** `activity_level` (PAL) и `training_type` были decoupled — sedentary-юзер с тренировками 3×/нед получал TDEE как чистый офисный работник (занижение 15-25%). Добавлены `app_constants.pal_training_bonus_{sedentary|light|moderate|heavy} = 0.15/0.10/0.05/0.00`. Дифференциация по base activity_level — защита от двойного учёта (heavy=1.725 уже включает intense training в Mifflin таблицах). `v_pal_adjusted = LEAST(pal_base + bonus, 1.8)`. Bonus применяется ТОЛЬКО если `training_type IN ('strength','cardio','mixed')` (для `'none'`, `'sedentary'`, NULL — bonus=0).

2. **`'none'` coefficients.** `training_type='none'` (mig 119, для «реально не тренируюсь») попадал в `COALESCE(_, 'mixed')` fallback и получал mixed-tier макро. Добавлены `protein_g_per_kg_none=1.2 / fat_pct_none=30` (= sedentary tier). НЕ путать с `'skip'` mapping — `cmd_select_training_skip → 'mixed'` это сознательная политика тимлида (mig 119/190), означает «не хочу отвечать сейчас, дай дефолт».

3. **Target rebalance — conditional clamp.** Сумма (P×4+F×9+C×4) могла превышать `target_calories` при срабатывании `fat_min_g_per_kg` или `carbs_min_g` floor'ов. Step 8 теперь:
   ```sql
   v_actual_kcal := v_protein * 4 + v_fat * 9 + v_carbs * 4;
   IF v_user.goal_type = 'lose' THEN
       v_target := LEAST(v_actual_kcal, ROUND(v_tdee)::INTEGER);
   ELSE
       v_target := v_actual_kcal;
   END IF;
   ```

**Lesson — conditional clamp по goal_type важен.** Изначально написал безусловный `LEAST(actual, ROUND(tdee))`. Это сломало бы gain-юзеров: floor мог поднять `actual_kcal` чуть выше `tdee` (естественно для gain, target должен быть > TDEE), а LEAST срезал бы до TDEE → вместо +10% профицита получаем maintain. Поймал на бумаге при подсчёте sentinel'ов ДО apply. **Правило:** при clamp'ах в RPC, которые применяются к разным целевым модам — всегда conditional по `goal_type`, никогда unconditional.

**JSON.calculations расширен** (без удаления v3 ключей, для будущего UI-warning о смягчённом дефиците):
- `pal_base`, `pal_adjusted` — telemetry PAL fusion
- `requested_kcal` — из TDEE×goal_speed_factor (до floor'ов)
- `actual_kcal` — фактическая сумма БЖУ (после floor'ов)
- `floor_triggered_fat`, `floor_triggered_carbs` — bool, сработал ли минимум
- `effective_deficit_pct` — реальный дефицит после rebalance

Все callers (mig 063/085/091/094) парсят только `->>'success'` — добавление новых полей безопасно. Verified grep'ом.

**Snapshot + backfill.** `users_targets_backup_20260515` — rollback rope (drop after 7d). Backfill DO-блок recalc для всех `registered` с полным профилем. Time: миллисекунды (4 юзера в проде).

**Cosmetic gap.** COMMENT в `pg_proc` остался `'v4 (mig 217)'` — миграция применена ещё под именем 217 до rebase-renumbering (collision с параллельным агентом). Не functional.

**Что НЕ покрыто v4** (отложено по решению владельца):
- Age guard `<18` (Mifflin не валиден для подростков), `>75` (формула занижает RMR)
- Беременность/лактация — нет поля в users → опасный дефицит
- `phenotype='athlete'` остаётся no-op (попадает в default ветку)
- Mifflin у obese переоценивает RMR на 5-10% — Katch-McArdle от LBM был бы точнее (Phase 2 quiz даёт LBM proxy → можно использовать)
- Adaptive modifiers Phase 3 (сон/стресс/ПМС)

**Verification (sentinel cases, прогнаны через psycopg2 на проде 2026-05-15):**

| Профиль | target_cal | P/F/C | Что доказывает |
|---|---|---|---|
| F/30/165/70 sed+cardio lose+slow default | 1728 | 98/56/208 | fat_floor доминирует над cardio 20% |
| M/25/180/75 mod+strength gain+normal monw | **3090** | 128/86/451 | **gain target>TDEE 2808 — conditional clamp** |
| F/40/165/100 light+mixed lose+fast obese | 1971 | 88/55/281 | obese phenotype target_weight=55 |
| M/30/175/70 sed+strength lose+normal default | 1892 | 140/56/207 | PAL fusion +247 ккал/день |
| M/30/175/70 sed+`none` lose+normal default | 1684 | 84/56/211 | new constants protein_g_per_kg_none |

p95 latency = 45 ms с VPS persistent psycopg2 (25 runs). Baseline RTT = 44 мс → RPC ≈1 мс.

PR: [noms-bot#75](https://github.com/sharkovvlad/noms-bot/pull/75). Daily: [[daily/2026-05-15]].

### Mig 228 (2026-05-15): скрыть «⏭ Пропустить» на edit_training (follow-up v4)

На экране `edit_training` в онбординге было 5 опций: strength / cardio / mixed / none / training_skip. Кнопка `cmd_select_training_skip` маппилась через RPC `set_user_training_type` в `training_type='mixed'` (mig 119 policy). С v4-формулой это означает: юзер думает «отказываюсь отвечать», получает Mixed-tier макро (PAL bonus, 1.6 г/кг белка) — **UX-обман**. Реально сидячему юзеру подходит честная опция «Не тренируюсь» (training_type=`'none'`, v4: PAL +0, 1.2 г/кг, 30% fat).

**Fix:** `UPDATE ui_screen_buttons SET visible_condition='false' WHERE screen_id='edit_training' AND callback_data='cmd_select_training_skip'`. Кнопка перестала рендериться в онбординге и профиле. Backend-ветка `cmd_select_training_skip → 'mixed'` оставлена (для in-flight inline-клавиатур у юзеров с недоставленными обновлениями).

**Итог UX:** 4 опции везде (strength / cardio / mixed / none), без Skip.

### v5 — mig 230 (2026-05-16): gender-conditional carbs_min_g floor

**Что починили.** До v5 углеводный floor (`carbs_min_g=50`) был universal — одинаковый для женщин и мужчин. Для женщин это слишком низко: на длительном <50 г/день при энерго-дефиците ломается T4→T3 конверсия (5'-deiodinase, van der Walt & Wiersinga 1986; Spaulding et al. 1976) и через thyroid axis затрагивается reproductive axis → функциональная гипоталамическая аменорея (Loucks 2003). v5 поднимает floor для женщин до 100 г; для мужчин остаётся 50 г (эффект слабее без cycle-axis).

**Изменения:**

- **app_constants:** INSERT `carbs_min_g_female=100`, `carbs_min_g_male=50`. Legacy `carbs_min_g=50` оставлен — 2-й уровень COALESCE fallback. **Не удалять** — safety net для NULL gender / неожиданных значений (defensive design).
- **`calculate_user_targets` Step 7** — единственное изменение vs v4:
  ```sql
  v_carbs_min := COALESCE(
      (SELECT value::INT FROM public.app_constants
       WHERE key = 'carbs_min_g_' || LOWER(TRIM(COALESCE(v_user.gender, 'male')))),
      (SELECT value::INT FROM public.app_constants WHERE key = 'carbs_min_g'),
      50
  );
  ```
  Трёхуровневый fallback. `LOWER(TRIM(COALESCE(..., 'male')))` — defensive против NULL/whitespace/регистра.
- **COMMENT** обновлён на `v5 (mig 230)` (заодно лечит cosmetic gap v4: COMMENT там остался `'v4 (mig 217)'` из-за rebase-renumbering).

**Lesson — floor cрабатывает реже, чем кажется.** Первый sentinel был F/45/170/55 strength sedentary lose+fast — ожидал floor-bite. Не сработал: формула v4 дала C=122 (выше floor 100). Алгебраическая граница: floor триггерится только при очень малом весе + старом возрасте + sedentary PAL. Realistic floor-bite кейс: **F/65/155/40 strength sedentary lose+fast** — там carbs остаток = 86 г, floor поднимает до 100. Это и есть смысл safety floor'а — он защищает edge cases, не «среднюю юзерицу».

**Sentinel verification (psycopg2 на проде, BEGIN/INSERT/CALL/ROLLBACK):**

| Профиль | v4 (carbs_min=50) | v5 (carbs_min=100) | Что доказывает |
|---|---|---|---|
| F/65/155/40 strength sed lose+fast | 952/80/32/**86** eff=20.1% | 1008/80/32/**100** eff=15.4% | floor BITES; +56 ккал/+14g C; eff_deficit -4.7pp |
| M/30/175/70 strength sed lose+normal | 1892/140/56/207 | 1892/140/56/207 | male не задет (EXACT MATCH baseline) |
| F/30/165/55 strength mod gain+normal | TDEE=2032 target=2238 | TDEE=2032 target=2238 | conditional clamp v4 для gain работает |

**Эффект на existing prod users** (5 registered): **никаких изменений** — все 3 male C=304-440 >> 50; обе female C=149,296 >> 100. Floor — защита для будущих юзериц малого веса на агрессивном дефиците, не для текущих.

**Pattern — sentinel via transactional ROLLBACK.** Чтобы пройти sentinel'ы без сайд-эффектов в проде: `BEGIN; INSERT users (telegram_id=-N, …); SELECT calculate_user_targets(-N, FALSE); ROLLBACK;`. Уникальный негативный `telegram_id` гарантирует отсутствие коллизий с реальными юзерами. Idempotent — можно гонять сколько угодно. Для прямого сравнения v4 vs v5 в той же сессии — параметризовать `UPDATE app_constants SET value=…` внутри tx, потом ROLLBACK обнуляет.

**Snapshot + backfill.** `users_targets_backup_20260516` (35 строк). Drop ≥ 2026-05-23. Backfill DO-блок — те же 5 registered, цифры не меняются (verified diff vs snapshot = 0).

**Latency:** p95 = **42.96 ms** (25 runs persistent psycopg2 с VPS). Чуть лучше mig 227 baseline 45 ms — extra COALESCE level не добавил издержек, оба lookup hit same PK index `app_constants(key)`.

**Что НЕ покрыто v5** (отложено): age guard / беременность / `'athlete'` / Katch-McArdle / adaptive modifiers Phase 3 — те же ограничения, что в v4.

PR: [noms-bot#81](https://github.com/sharkovvlad/noms-bot/pull/81) — **merged 2026-05-16**. Daily: [[daily/2026-05-16]].

### v6 — mig 234 (2026-05-17): age safety guards

Уже подробно описано в KB и daily/2026-05-17. Краткая ссылка для контекста v7: v6 ввёл два новых блока в формулу — Step 2 «Age + safety guards» (forced maintain при `<18+lose`, informational warning при `>75`) и трёхпольную telemetry в JSON (`age_warning`, `original_goal_type`, `effective_goal_type`). Steps 6 и 8 переключены с `v_user.goal_type` на `v_effective_goal_type = COALESCE(v_forced_goal_type, v_user.goal_type)`. PR [#86](https://github.com/sharkovvlad/noms-bot/pull/86), merged.

### v7 — mig 246 (2026-05-18): safety baseline guards (min kcal floor + BMI-aware tiered)

**Что починили.** До v7 формула давала любой результат, даже клинически опасный: BMI 11 с целью maintain мог получить 800 ккал, BMI 65 с lose+fast — −20% дефицит от 3267 ккал → нагрузка на сердце. v7 — atomic safety baseline через 4 новых guard под feature flags для granular rollback.

**Изменения (на одной CREATE OR REPLACE):**

1. **Step 1b — BMI sanity + BMI-aware guards (P0.4):**

   ```sql
   v_bmi := v_user.weight_kg / POWER(v_user.height_cm / 100.0, 2);

   IF v_bmi < 14 THEN
       v_forced_goal_type := 'maintain';
       v_bmi_warning      := 'extreme_cachexia_recommend_medical';   -- hard block
   ELSIF v_bmi < 18.5 AND v_user.goal_type = 'lose' THEN
       v_forced_goal_type := 'maintain';
       v_bmi_warning      := 'underweight_lose_override';            -- hard regulated
   ELSIF v_bmi > 60 AND v_user.goal_type = 'lose'
                    AND v_user.goal_speed IN ('fast','normal') THEN
       v_user.goal_speed := 'slow';                                  -- clamp speed
       v_bmi_warning     := 'extreme_obesity_clamp_slow';            -- hard regulated
   ELSIF v_bmi > 60 THEN
       v_bmi_warning := 'extreme_obesity_informational';             -- informational
   END IF;
   ```

   Tiered policy, **не RETURN ERROR**. BMI 13.5 не ломает Profile screen, только enforces force maintain + recommends medical. BMI и age guards могут срабатывать вместе — оба пишут в `v_forced_goal_type='maintain'`, результат идентичен; telemetry полей два (`bmi_warning` + `age_warning`).

2. **Step 8b — Min kcal floor (P0.3):**

   ```sql
   v_medical_floor := CASE LOWER(TRIM(v_user.gender))
       WHEN 'female' THEN 1200
       WHEN 'f'      THEN 1200
       ELSE               1500
   END;
   v_min_kcal_floor := GREATEST(v_medical_floor, ROUND(v_bmr)::INTEGER);

   IF v_target < v_min_kcal_floor THEN
       IF ROUND(v_bmr)::INTEGER > v_medical_floor THEN
           v_min_kcal_warning := 'bmr_floor_triggered';
       ELSIF LOWER(TRIM(v_user.gender)) IN ('female','f') THEN
           v_min_kcal_warning := 'medical_floor_1200_triggered';
       ELSE
           v_min_kcal_warning := 'medical_floor_1500_triggered';
       END IF;
       v_target := v_min_kcal_floor;
   END IF;
   ```

   Compromise per agent 234 dialog: `GREATEST(actual_target, medical_floor, BMR)`. Источники: medical floor 1200ж/1500м — WHO/ACSM/EFSA industry standard; BMR — physiological floor (под BMR = подавление щитовидки + потеря мышц).

3. **Step 8c — guard_audit_log INSERTs** (для FTC/legal traceability). Защищены `to_regclass`-guard'ом на случай rollback storage (defensive net). trigger_name формат `bmi_aware_<warning>` / `<min_kcal_warning>`; metadata содержит bmi/goal/target_before/after/bmr.

4. **JSON return +4 полей** в `calculations`: `bmi_value`, `bmi_warning`, `min_kcal_warning`, `min_kcal_floor_applied`.

5. **app_constants feature flags** (INSERT): `safety_guard_min_kcal_enabled`, `safety_guard_bmi_14_enabled`, `safety_guard_bmi_185_enabled`, `safety_guard_bmi_60_enabled` — все `true`. Каждый guard в SQL читает свой флаг через `COALESCE((SELECT ... ), TRUE)` — granular rollback без миграции.

6. **COMMENT** → `'v7 (mig 246): safety baseline (min_kcal_floor + BMI-aware guards). v6 (mig 234) age guards preserved 1:1.'`

**Sentinel verification** (8 кейсов через transactional ROLLBACK на проде):

| # | Профиль | Expected | Actual |
|---|---|---|---|
| 1 | F/30/165/30 (BMI 11) maintain | extreme_cachexia, force maintain | ✅ target=1378, bmi_w=extreme_cachexia_recommend_medical |
| 2 | F/25/165/45 (BMI 16.5) lose+normal | underweight_lose_override, force maintain | ✅ target=1613, effective_goal=maintain |
| 3 | F/40/165/175 (BMI 64) lose+fast | clamp_slow (10% deficit) | ✅ target=2940 (TDEE=3267, eff_def=10.0%) |
| 4 | F/40/165/175 (BMI 64) maintain | informational | ✅ target=3268, bmi_w=extreme_obesity_informational |
| 5 | F/45/160/40 (BMI 15.6) lose+fast | underweight_lose_override | ✅ target=1370 (BMI guard takes precedence over min_kcal) |
| 6 | M/40/170/55 (BMI 19) lose+fast | (no trigger if target ≥1500) | ✅ target=1532 — выше 1500 floor, нет trigger |
| 7 | F/30/165/70 sed+cardio lose+slow | NULL warnings, target=1728 (v6 baseline) | ✅ v6=1728, v7=1728 — exact match |
| 8 | M/25/180/75 mod+strength gain+normal | NULL warnings, baseline match | ✅ v6=2415, v7=2415 — exact match |

**Эффект на existing prod users** (5 registered, все BMI 22-26.6, none triggers any guard): **delta=0** для всех kcal/P/F/C. Verified против snapshot `users_targets_backup_20260518_pre_v7`.

**Audit log live verification**: BMI=11 maintain sentinel → 1 row в `guard_audit_log`: `trigger_name='bmi_aware_extreme_cachexia_recommend_medical'`, `event='triggered'`, `metadata={'bmi': 11.02, 'goal_type': 'maintain', 'goal_speed': 'normal'}`. ✅ INSERT работает на live storage (mig 239).

**Latency:** p95 = **44.11 ms** (25 runs persistent psycopg2 с VPS). Дельта v6→v7 ≈ +0 ms — новые IF блоки + COALESCE flag lookups hit same `app_constants(key)` PK index, цена незаметна. Target <50 ms — OK.

**Pattern для будущих guard'ов:** каждый новый safety guard в v7+ должен (1) иметь `<trigger>_warning` JSON поле (snake_case, NOT boolean, enum string), (2) использовать feature flag `safety_guard_<family>_enabled` (default `TRUE`), (3) писать в `guard_audit_log` через `to_regclass`-guarded INSERT, (4) preserve существующую логику 1:1 (`v_forced_goal_type` накапливается без stomp; multiple guards могут сработать одновременно). См. [[concepts/safety-guard-ux-pattern]] §3 для severity classification.

**Что НЕ покрыто v7** (отложено):
- **P0.6 pregnancy/lactation** (`is_pregnant=TRUE+lose → force maintain + +340/+452 kcal по триместру`). Заблокировано на UX-wireframe.
- **P1.5 age-aware formulas** (Schofield-HW для healthy <18, Molnar для obese <18, Lührmann для >75). Reclassified в P1 как silent accuracy — Mifflin replaced без banner.
- BMI cutoffs остаются strict `<14 / <18.5 / >60` (не >18.5 для underweight). Soft transitions (BMI 18.5-20 + lose с disclaimer) — backlog при появлении real users в borderline zone.

PR (pending review). Daily: [[daily/2026-05-18]].

**Digital twin (Google Sheets v6.3).** Pre-staging pattern — владелец заложил v5-формулы под `_proposal_vN` суффиксом ДО apply миграции, после merge mig 230 "proposals" автоматически стали ground truth без переписывания формул. Verification: твин для INPUT F/30/165/70 sed+cardio lose+slow default даёт 1728/98/56/208 — EXACT MATCH с live прод v5. **Pattern для будущих v6, v7...:** закладывать новые константы и формулы в твин под суффиксом `_proposal_vN` параллельно с написанием миграции; после merge владелец срезает суффикс. Никакого переписывания формул на стороне агента-нутрициолога не требуется.

## Related Concepts

- [[concepts/day-summary-ux]] — displays personalized targets via get_day_summary v3
- [[concepts/supabase-db-patterns]] — migration 055 applied via n8n temp workflow
- [[concepts/xp-model]] — macros are one part of the broader gamification system
- [[concepts/user-profile-personalization]] — training_type and goal_speed editable from Profile screen
- [[concepts/edit-picker-dual-render]] — ✅ checkmark pattern для edit пикеров; chk*() helpers; dual render locations

### v9 — mig 291 (2026-05-20): vegan/vegetarian DIAAS protein multiplier

Applied to prod 2026-05-20 evening. `calculate_user_targets v8 → v9`. CASE multiplier поверх baseline + maternal_protein_bonus по diet_type.

| diet_type | multiplier | DIAAS justification |
|---|---|---|
| `omnivore` (default) | 1.00 | Reference animal protein |
| `vegetarian` | 1.10 | ~85% DIAAS (молочка + яйца — полноценные АК) |
| `vegan` | 1.25 | ~70-80% DIAAS, неполный аминокислотный профиль |

- **Schema:** `users.diet_type TEXT DEFAULT 'omnivore'` CHECK IN (3 enum values).
- **Multiplier order:** applied **после** maternal_protein_bonus → vegan-pregnant = `(baseline + 25) × 1.25`.
- **Owner decision:** 3-state enum вместо `is_vegan` BOOLEAN из ТЗ нутрициолога — DIAAS science даёт промежуточный профиль для vegetarian.
- **Telemetry:** `calculations.diet_type` + `calculations.protein_diet_multiplier`.
- **UX:** `edit_diet` ui_screen + setter RPC `set_user_diet_type` + 13 langs translations.
- **Severity:** silent accuracy. Banner НЕТ.

PR [#135](https://github.com/sharkovvlad/noms-bot/pull/135).

### v10 — mig 292 (2026-05-20): age-aware BMR formulas (Schofield/Molnar/Lührmann)

Applied to prod 2026-05-20 evening. Step 4 BMR — CASE switch по age + BMI.

| Case | Formula | Source |
|---|---|---|
| `<18 + BMI<30` | **Henry 2005** Schofield-HW | PMID 16277825, SACN 2011 |
| `<18 + BMI≥30` | **Molnar 1995** | PMID 7562290 |
| `>75` | **Lührmann 2002** (no-height) | PMID 12111047 |
| `18..75` | Mifflin-St Jeor (unchanged) | — |

- **Units warning (critical):** Henry в **метрах**, Molnar в **сантиметрах**. Поймано dimensional analysis subagent'ом.
- **Boundary:** `<18` exclusive, `>75` exclusive. Age=18/75 → Mifflin.
- **Telemetry:** `calculations.bmr_formula` enum (`mifflin`/`schofield_hw`/`molnar`/`luhrmann`).
- **Severity:** silent accuracy.

PR [#137](https://github.com/sharkovvlad/noms-bot/pull/137). Подробности — [[concepts/calc-user-targets-roadmap]] §P1.5.

### v11 — mig 295 (2026-05-20): RFM + Katch-McArdle + waist + Брока ликвидирована

Applied to prod 2026-05-20 night. **Формула Брока полностью ликвидирована** (DR §LBM Proxy: «глубоко антинаучный подход»).

- **Schema:** `users.waist_circumference NUMERIC` (см, NULL OK). Validation 40-200 cm.
- **Step 3 obese branch:** Брока removed. `obese + waist NOT NULL` → RFM math → `target_weight = LBM_kg`. `obese + waist NULL` → `target_weight = actual_weight` (Mifflin path).
- **Step 4 BMR:** ELSIF `v_lbm_kg IS NOT NULL` → Katch-McArdle (`370 + 21.6 × LBM`).
- **RFM (Woolcott & Bergman 2018):** Male `BF% = 64 − 20×(H/W)`, Female `BF% = 76 − 20×(H/W)`. Defensive clamp BF% ∈ [5, 60]%.
- **Priority order BMR:** pediatric → geriatric → **Katch-McArdle** → Mifflin.
- **UX:** `edit_waist` screen + entry button на `phenotype_result` (visible_condition='obese AND waist IS NULL'). Quiz stays 4-step.
- **Retrofit cron:** `waist_retrofit` (hour=14 local, phenotype='obese' AND waist IS NULL).
- **Impact on existing users:** 0 obese users на moment apply → нулевая регрессия.

Sprint P1 Accuracy finale. Подробности — [[concepts/calc-user-targets-roadmap]] §P2.1/P2.2/P2.3.

## 🟡 PROPOSAL — Fix C: goal-aware protein (2026-06-02, НЕ реализовано)

**Статус:** design-only, ждёт owner sign-off. Открыто после owner-теста 417002669 (М, 99 кг, 193 см, цель «похудеть», тренировки «кардио»).

**Проблема.** Белок задаётся ТОЛЬКО по `training_type`: `protein_g_per_kg_cardio=1.4`. Для худеющего (caloric deficit) это **занижено** — доказательная норма при дефиците + тренировках = **1.6–2.2 г/кг** (ISSN position stand; Helms et al. 2014 — верхняя граница при дефиците для сохранения LBM). У owner'а: 1.4×99 = 139 г (21% kcal).

**Каскад на углеводы.** Углеводы = **остаток** после белка и жира (`v_carbs = (kcal − protein_kcal − fat_kcal)/4`). Белок занижен (21%), жир на floor (0.8 г/кг = 27%) → остаток валится в углеводы → **344 г (52%)**. Owner справедливо заметил «углеводы завышены» — это симптом низкого белка, не отдельный баг. Белок 1.8–2.0 г/кг (≈178–198 г) → углеводы сами падают до ~40–45%.

**Жир (79 г) — НЕ трогать.** Floor `fat_min_g_per_kg=0.8` (сработал `floor_triggered_fat`). Научно обоснован (гормоны, жирорастворимые витамины).

**Решение (goal-aware множитель).** Вместо плоского `protein_g_per_kg_<training>` — `max(training-baseline, goal-floor)`:
- `goal_type='lose'` → protein floor **1.8 г/кг** независимо от типа тренировки.
- `gain`/`maintain` → текущая training-based логика.
- Impl: новый `app_constants` `protein_g_per_kg_goal_lose_floor` (hot-reload), `v_protein := GREATEST(ROUND(v_protein_g_per_kg*v_tw), ROUND(goal_floor*v_tw))` в `calculate_user_targets` (после строки ~364, до diet_multiplier ~377).

**Pre-impl обязательно:** (1) NLM-first схема v11 mig 295; (2) digital-twin regression на существующих юзерах — не пробьёт ли `min_kcal_floor` / `carbs_min_g`; (3) РПП-safety gate (рост белка vs underweight/cachexia guards); (4) p95; (5) **отдельный PR/миграция, не смешивать с mig 424**.

**Источники для верификации:** ISSN Protein & Exercise (Jäger 2017); Helms ER et al. (2014); `Разработка алгоритмов питания…md` §макро.

## Sources

- [[daily/2026-04-10.md]] — Migration 055: 7 new columns, 25 new app_constants, calculate_user_targets v3, set_user_training_type/set_user_goal_speed RPCs, backfill for existing users
- [[daily/2026-04-11.md]] — Build Profile Text v4.1: trainingMap/speedMap, Training/Speed/Phenotype keyboard, cmd_edit_phenotype → coming_soon, profile.body_type translation key
- [[daily/2026-04-15.md]] — Speed Edit flow: 4 новых ноды (Prepare/Save/Build/Send), cmd_speed_* routing, Build Ask Markup case, goal_speed в Dispatcher Prepare for 04
- [[daily/2026-04-17.md]] — chk*() helpers расширены на goal/training/activity/gender (оба места: Response Builder + Build Ask Markup)
- [[daily/2026-05-15.md]] — v4 mig 227: PAL fusion, 'none' coefficients, conditional clamp; digital twin верификация в Google Sheets
- [[daily/2026-05-16.md]] — v5 mig 230: gender-conditional carbs_min_g floor (women=100, men=50); PR #81; floor-bite боундари через algebra
- [[daily/2026-05-20.md]] — v9 mig 291: vegan/vegetarian DIAAS multiplier. v10 mig 292: Schofield/Molnar/Lührmann BMR switch. v11 mig 295: RFM + Katch-McArdle + waist + Брока ликвидирована. P1 Accuracy sprint закрыт.
