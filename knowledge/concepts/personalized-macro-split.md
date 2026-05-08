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
