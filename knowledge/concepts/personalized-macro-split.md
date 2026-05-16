---
title: "Personalized Macro Split"
aliases: [macro-split, training-type, phenotype, goal-speed, calculate-user-targets]
tags: [nutrition, gamification, supabase, onboarding, rpc]
sources:
  - "daily/2026-04-10.md"
  - "daily/2026-04-11.md"
  - "daily/2026-04-15.md"
  - "daily/2026-04-17.md"
created: 2026-04-10
updated: 2026-04-17
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

**Digital twin (Google Sheets v6.3).** Pre-staging pattern — владелец заложил v5-формулы под `_proposal_vN` суффиксом ДО apply миграции, после merge mig 230 "proposals" автоматически стали ground truth без переписывания формул. Verification: твин для INPUT F/30/165/70 sed+cardio lose+slow default даёт 1728/98/56/208 — EXACT MATCH с live прод v5. **Pattern для будущих v6, v7...:** закладывать новые константы и формулы в твин под суффиксом `_proposal_vN` параллельно с написанием миграции; после merge владелец срезает суффикс. Никакого переписывания формул на стороне агента-нутрициолога не требуется.

## Related Concepts

- [[concepts/day-summary-ux]] — displays personalized targets via get_day_summary v3
- [[concepts/supabase-db-patterns]] — migration 055 applied via n8n temp workflow
- [[concepts/xp-model]] — macros are one part of the broader gamification system
- [[concepts/user-profile-personalization]] — training_type and goal_speed editable from Profile screen
- [[concepts/edit-picker-dual-render]] — ✅ checkmark pattern для edit пикеров; chk*() helpers; dual render locations

## Sources

- [[daily/2026-04-10.md]] — Migration 055: 7 new columns, 25 new app_constants, calculate_user_targets v3, set_user_training_type/set_user_goal_speed RPCs, backfill for existing users
- [[daily/2026-04-11.md]] — Build Profile Text v4.1: trainingMap/speedMap, Training/Speed/Phenotype keyboard, cmd_edit_phenotype → coming_soon, profile.body_type translation key
- [[daily/2026-04-15.md]] — Speed Edit flow: 4 новых ноды (Prepare/Save/Build/Send), cmd_speed_* routing, Build Ask Markup case, goal_speed в Dispatcher Prepare for 04
- [[daily/2026-04-17.md]] — chk*() helpers расширены на goal/training/activity/gender (оба места: Response Builder + Build Ask Markup)
- [[daily/2026-05-15.md]] — v4 mig 227: PAL fusion, 'none' coefficients, conditional clamp; digital twin верификация в Google Sheets
- [[daily/2026-05-16.md]] — v5 mig 230: gender-conditional carbs_min_g floor (women=100, men=50); PR #81; floor-bite боундари через algebra
