---
title: "calculate_user_targets — Roadmap (P0 active sprint + P1+ backlog)"
aliases: [roadmap-targets, safety-roadmap, calc-targets-backlog]
tags: [nutrition, safety, roadmap, calculate-user-targets, supabase]
sources:
  - "daily/2026-05-15.md"
  - "daily/2026-05-16.md"
  - "daily/2026-05-17.md"
  - "handover/2026-05-16_deep_research_handoff.md"
  - "Downloads/Глубокий анализ формулы расчета целей NOMS.md (deep research 2026-05-16)"
  - "Agent 234 critique 2026-05-17 (14/15 правок принято, мono-mig consolidation)"
created: 2026-05-17
updated: 2026-05-17
---

# calculate_user_targets — Roadmap

Living document. **P0 = active sprint** (focus). **P1+ = backlog** (defer until P0 closed).

Все задачи маркируются по [[concepts/agent-collaboration-protocol]] Rule 1 severity. Migrations apply через mig-engineer ownership (Rule 4). Клинические решения per task — clinical owner (Rule 4).

## Status (на 2026-05-18 — P0 sprint SQL-side CLOSED, готов к UX/translations finish)

- **Prod state:** mig 254 (v8) — **Maternal safety guard** (pregnancy/lactation/protective). v7 BMI+min_kcal preserved. v6 age preserved. mig 252 banner injection family-agnostic для my_plan screen.
- **Closed P0 deliverables (2026-05-17/18):**
  - mig 234 (v6) age guards baseline — **merged** PR [#86](https://github.com/sharkovvlad/noms-bot/pull/86)
  - mig 239 storage infrastructure (`shown_guards JSONB` + `user_overrides` + `guard_audit_log`) — **merged** PR [#89](https://github.com/sharkovvlad/noms-bot/pull/89)
  - mig 240/241/242 age-warning translations (13 langs × 12 keys + L2 cultural review pass 1+2) — **merged** PR #90/#91/#92
  - mig 246 (v7) safety baseline (P0.3+P0.4) — **merged** PR [#94](https://github.com/sharkovvlad/noms-bot/pull/94)
  - **mig 252 banner injection (P0.8 passive-banner #2)** — applied на prod, [PR #96](https://github.com/sharkovvlad/noms-bot/pull/96) open
  - **mig 253+254 (P0.6 pregnancy/lactation v8)** — applied на prod, [PR #96](https://github.com/sharkovvlad/noms-bot/pull/96) open
- **Open closing artifacts (next sessions):**
  - **Live-test в боте** — see [handover/2026-05-18_nutritionist_session_close.md](../../handover/2026-05-18_nutritionist_session_close.md) §A для recipe
  - **Translations bmi/min_kcal banner texts** (~351 entries × 13 langs) — brief: [handover/2026-05-18_bmi_min_kcal_copywriter_brief.md](../../handover/2026-05-18_bmi_min_kcal_copywriter_brief.md)
  - **Translations maternal banner texts** (~221 entries × 13 langs) — 17 keys в [pregnancy-lactation-clinical-spec.md §5](pregnancy-lactation-clinical-spec.md)
  - **Onboarding step + Profile toggle + retrofit cron** для maternal status (Option D approved)
  - **Auto-reset cron** для pregnancy `due_date+30d` и lactation `started+24mo`
  - **First-trigger modal (#3 touch-point)** — Python hook reading `shown_guards`
- **Deferred to P2 (по design decision 2026-05-18):**
  - **EA > 30 ккал/кг LBM (RED-S protection)** — rationale в [[concepts/energy-availability-design-decision]]. Зависит от P2.1 waist + P2.5a workout tracking.
- **Coordination protocol:** [[concepts/agent-collaboration-protocol]] (10 правил)
- **UX-pattern:** [[concepts/safety-guard-ux-pattern]] v2 (5-tier severity + L1/L2 cultural review + auto-reset variants)
- **Banner injection pattern:** [[mig 252]] family-agnostic — auto-renders new families когда переводы appear под `warning.<family>.<enum>.banner_*`. No code change needed для bmi/min_kcal/maternal once copy ready.

---

# 🔴 P0 ACTIVE SPRINT — 4 задачи

Focus discipline: только safety baseline. Accuracy fixes (formulas, vegan, ABW) — в P1 backlog.

## P0.1 ✅ DONE — Age guards baseline (mig 234)

| Field | Value |
|---|---|
| Severity | **hard block** (`<18+lose`) + **informational** (`<18` disclaimer, `>75` elderly) |
| Migration | 234 (merged) |
| JSON telemetry | `age_warning`, `original_goal_type`, `effective_goal_type` |
| Auto-reset | full release при стуkнет 18 (см. [[concepts/safety-guard-ux-pattern]] §5b) |
| Closing artifacts | Copywriter spawn pending, storage mig pending, Python handlers pending |

## P0.3 + P0.4 ✅ DONE — Mono-mig: Safety baseline guards (mig 246)

**Объединены в одну atomic migration** `migrations/246_safety_baseline_guards.sql` per agent 234 proposal (accepted). Семантически связаны — оба про «защита от опасных таргетов». Applied на prod 2026-05-18; v6 age guards preserved 1:1; prod 5 users delta = 0; p95 = 44.1 ms (target <50).

### P0.3 sub: Min kcal floor

| Field | Value |
|---|---|
| Severity | **hard regulated** (без opt-out, medical floor) |
| Где в формуле | Step 8 (target rebalance), 1 IF block |
| Логика | `v_target := GREATEST(v_target, CASE gender WHEN 'female' THEN 1200 ELSE 1500 END, ROUND(v_bmr)::INTEGER)` |
| JSON | `min_kcal_warning` enum (`bmr_floor_triggered` / `medical_floor_1200_triggered` / `medical_floor_1500_triggered` / NULL) |
| Feature flag | `app_constants.safety_guard_min_kcal_enabled` (для granular rollback) |
| Sentinel | 3 кейса: миниатюрная женщина BMR<1200 (BMR floor); средняя женщина target<1200 (medical floor); средний мужчина target<1500 (medical floor); + 1 контрольный без trigger |

### P0.4 sub: BMI-aware guards (tiered policy, не RETURN ERROR)

| Field | Value |
|---|---|
| Severity | **hard block** (BMI<14) + **hard regulated** (BMI<18.5+lose, BMI>60+fast) + **informational** (BMI>60 общий) |
| Где в формуле | Step 1 (validation BMI) + Step 6 (goal override) |
| Логика | 3 IF блока: BMI<14 → force maintain + warning; BMI 14-18.5+lose → force maintain + warning; BMI>60 → clamp speed на slow max |
| JSON | `bmi_warning` enum (`extreme_cachexia_recommend_medical` / `underweight_lose_override` / `extreme_obesity_clamp_slow` / NULL) |
| Feature flags | `safety_guard_bmi_14_enabled`, `safety_guard_bmi_185_enabled`, `safety_guard_bmi_60_enabled` (granular) |
| Sentinel | 4 кейса: BMI 13 maintain (force maintain), BMI 16+lose (override), BMI 65+fast (clamp slow), BMI 25 control (no trigger) |

### Mono-mig артефакты

| Field          | Value                                                                                                  |
| -------------- | ------------------------------------------------------------------------------------------------------ |
| Файл           | `<NNN>_safety_baseline_guards.sql` (NNN = следующий свободный, проверить через protocol Rule 7)        |
| Sentinel total | 8 кейсов в одном run                                                                                   |
| COMMENT        | `v7 (mig NNN): safety baseline (min_kcal_floor + BMI-aware guards). v6 (mig 234) age logic preserved.` |
| Snapshot       | `users_targets_backup_<DATE>`                                                                          |
| Backfill       | Стандартный DO-блок recalc всех registered                                                             |
| p95 target     | <50 ms (current baseline 43ms + ~5ms на новые проверки)                                                |
| Deps           | Storage migration N+1 (`shown_guards`, `user_overrides`, `guard_audit_log`) merged ПЕРЕД apply         |

## P0.6 — Pregnancy / Lactation flag + защита

| Field | Value |
|---|---|
| Severity | **hard block** (`is_pregnant=TRUE + lose` → force maintain + add maintenance kcal) |
| Migration | TBD (после P0.4 mono-mig) |
| Новые поля `users` | `is_pregnant BOOLEAN DEFAULT NULL`, `is_lactating BOOLEAN DEFAULT NULL`, `pregnancy_trimester INT` (1/2/3/NULL), `lactation_type TEXT` ('exclusive'/'partial'/NULL), `lactation_started DATE` |
| DEFAULT NULL обязателен | Rule 2 — acute failure mode, silent harm. Для `F + age 15-50 + is_pregnant IS NULL` → protective force maintain + soft warning «уточни в Профиле» |
| Где в формуле | Step 6 — pregnancy adds `+340 kcal` (Q2) / `+452 kcal` (Q3); lactation adds `+330` (exclusive) / `+300` (partial) per IOM 2002 |
| JSON | `pregnancy_warning`, `lactation_warning` |
| Clinical spec | [[concepts/pregnancy-lactation-clinical-spec]] (готов to spawn) |
| UX dependency | **Wireframe от owner блокирует spawn** — где собирать (onboarding step / Profile toggle / retrofit popup)? |
| Retrofit cron | HIGH priority (Rule 10) — first 7 days после registration для existing F/15-50 |
| Messaging | ~10 keys × 13 langs = 130 строк; cultural review L1+L2 mandatory (Rule 9, hard block) |
| Sentinel | F/28/165/68 + Q2 + lose (force maintain + +340 kcal); F/30/170/65 + lactation_exclusive + lose (force maintain + +330); F/25/160/55 + NULL pregnancy + lose (protective maintain) + 2 control |

## P0.8 — UI surfaces + opt-out matrix (мета-задача, частично закрыто)

| Field | Value |
|---|---|
| Severity | meta (не migration) |
| Status | Частично закрыто [[concepts/safety-guard-ux-pattern]] v2 — описаны 5 touch points + opt-out matrix по severity tier |
| Что осталось | Per-guard decision tree (где banner / когда modal / opt-out flow code / auto-reset cron). Описано в [[concepts/safety-guard-ux-pattern]] §9 «Architecture Beyond SQL» — 9 пунктов post-mig работы |
| Deps | Каждая P0 mig (`P0.1`, `P0.3+P0.4`, `P0.6`) триггерит post-apply work по этим 9 пунктам |

---

# 🟠 P1 BACKLOG — Accuracy (после закрытия P0)

Переезжают сюда после reclassification 2026-05-17. P0 narrowed для focus discipline.

### P1.1 fat_floor — phenotype branch (resolved через compromise агента 234)

Раньше был открытый спор (DR: floor от actual_weight, prod: от target_weight). Compromise:

```sql
v_fat_floor := CASE COALESCE(v_user.phenotype, 'default')
    WHEN 'obese' THEN ROUND(v_fat_min_g_per_kg * v_target_weight)
    WHEN 'monw'  THEN ROUND(v_fat_min_g_per_kg * v_target_weight)
    ELSE ROUND(v_fat_min_g_per_kg * v_user.weight_kg)
END;
```

**Severity:** silent accuracy (Rule 8).

### P1.2 ✅ DONE — Vegan / vegetarian protein adjustment (mig 291, 2026-05-20)

Applied to prod 2026-05-20 evening. `calculate_user_targets v8 → v9` накладывает CASE multiplier поверх baseline + maternal_protein_bonus:

| diet_type | multiplier | DIAAS justification |
|---|---|---|
| `omnivore` (default) | 1.00 | Reference animal protein |
| `vegetarian` | 1.10 | ~85% DIAAS (молочка + яйца — полноценные АК) |
| `vegan` | 1.25 | ~70-80% DIAAS, неполный аминокислотный профиль |

- **Schema:** `users.diet_type` TEXT DEFAULT 'omnivore' CHECK IN (3 enum values).
- **RPC v9 changes:** `v_diet_multiplier` declare, multiplier applied **после** maternal_protein_bonus (vegan-pregnant = (baseline + 25) × 1.25), telemetry `calculations.diet_type` + `calculations.protein_diet_multiplier`.
- **Setter RPC:** `set_user_diet_type(BIGINT, TEXT) → JSONB` для save_via_callback паттерна; triggers recalc.
- **UX:** `edit_diet` ui_screen (pattern из `edit_speed`) + 4 buttons + 13 langs ui_translations (Sassy Sage tone).
- **Tests:** 5 integration зелёных через TX/ROLLBACK (omnivore baseline, vegan +25%, vegetarian +10%, vegan+pregnant order, set_user_diet_type invalid value rejected).
- **Severity:** silent accuracy. Юзер видит только final protein number; banner не нужен.
- **Owner decision (2026-05-20):** 3-state enum `diet_type` вместо `is_vegan` BOOLEAN из ТЗ нутрициолога — DIAAS science даёт промежуточный профиль для vegetarian.

**Open follow-ups** (отдельные PR'ы, не блокируют mig 291):
- Onboarding step `registration_step_diet` — требует правки `process_onboarding_input` (576 LOC FSM); natural way вместе с mig 293 quiz extension.
- `profile_main` entry point + current value display — требует правки `get_profile_business_data`.
- Retrofit cron — translation key `cron_notifications.diet_retrofit_prompt` уже на проде × 13 langs; wiring через `cron_get_reminder_candidates` отдельным PR.

### P1.3 Adjusted Body Weight для obese (промежуток до Phase 2 RFM)

DR: «До развертывания Phase 2 следует применять формулу Adjusted Body Weight = IBW + 0.25 × (Actual − IBW)».

- **Severity:** silent accuracy
- **Замена:** `v_target_weight := IBW + 0.25 * (v_user.weight_kg - IBW)` для obese phenotype
- **Deps:** none

### P1.4 Phenotype 'athlete' telemetry + UI disclaimer

- **Severity:** informational (banner OK, нет override) + silent accuracy (когда переключимся на Katch-McArdle)
- **До перехода на Katch-McArdle:** JSON `bmr_formula='mifflin'` + `athlete_using_default_formula=TRUE`
- UI: banner «athlete-specific formula coming soon» (soft, opt-out OK)

### P1.5 ✅ DONE — Возрастные формулы Schofield/Molnar/Lührmann (mig 292, 2026-05-20)

Applied to prod 2026-05-20 evening (session 9). `calculate_user_targets v9 → v10`: Step 4 BMR — CASE switch по age + BMI.

| Case | Formula | Source | Coefficients (kcal/day) |
|---|---|---|---|
| `<18 + BMI<30` | **Henry 2005** Schofield-HW | PMID 16277825, SACN 2011 endorsed | Male: `15.6·W + 266·H + 299` (H=м!); Female: `9.40·W + 249·H + 462` |
| `<18 + BMI≥30` | **Molnar 1995** | PMID 7562290; accuracy 87% per Acosta 2010 AJCN | Male: `(50.0·W + 25.3·H_cm − 50.3·A + 26.9) / 4.184`; Female: `(51.2·W + 24.5·H_cm − 207.5·A + 1629.8) / 4.184` |
| `>75` | **Lührmann 2002** | PMID 12111047; no-height by design (elderly compression) | Male: `935.4 + 11.95·W − 3.657·A`; Female: `757.1 + 11.95·W − 3.657·A` |
| `18..75` | Mifflin-St Jeor (unchanged) | — | preserved verbatim from v9 |
| `age IS NULL` | Defensive fallback → Mifflin | — | pre-mig292 behaviour preserved |

- **Severity:** silent accuracy. Banner НЕТ, цель не меняется, формула меняется.
- **JSON telemetry:** `calculations.bmr_formula` enum (`mifflin` / `schofield_hw` / `molnar` / `luhrmann`). Audit-ready для Digital Twin sync.
- **Boundary discipline:** `<18` exclusive, `>75` exclusive. Age=18 → mifflin. Age=75 → mifflin. Age=76 → luhrmann.
- **Tests:** 10 sentinel checks прошли (math drift <2 kcal); 8 pytest integration зелёных.

**Surprise discovery от research subagent'а:** Henry 2005 публикует **ОДНУ** формулу для 10-18 на пол — НЕ sub-split 10-12/13-15/16-18 как roadmap изначально предполагал. Sub-split не существует ни в Henry 2005, ни в Schofield 1985 HW form (sub-split есть только в weight-only Schofield). Использован canonical single 10-18 block per gender (SACN 2011 endorsed).

**Critical units lesson:** Henry в **метрах**, Molnar в **сантиметрах**. PMC review (PMC8685418) мис-labeled units; subagent dimensional analysis на boy 13yo поймал bug (Henry: 1427 kcal с метрами ✓, с см → 43,561 ✗ невозможно).

**Out of scope mig 292 (явно отложено):** safety guards `<18+gain age 13-14 force maintain` (пубертат) и `>75+lose clamp slow` — оба не formula switch, отдельный workstream.

---

# 🟡 P2 BACKLOG — Adaptive (после Phase 2 quiz расширения)

### P2.1 + P2.2 + P2.3 ✅ DONE — RFM + Katch-McArdle + waist collection (mig 295, 2026-05-20)

Applied to prod 2026-05-20 night (session 10). Закрыты склейкой как 3-PR P1 Accuracy sprint finale. **Брока полностью ликвидирована** (DR §LBM Proxy: «глубоко антинаучный подход»).

**Schema:**
- `users.waist_circumference NUMERIC` (см, NULL OK). Validation 40-200 cm на app level через `set_user_waist_circumference(BIGINT, NUMERIC)` setter RPC.

**RPC v10 → v11:**
- Step 3 obese branch — Брока removed. Новая логика:
  - `obese + waist NOT NULL` → RFM math → `target_weight = LBM_kg`
  - `obese + waist NULL` → `target_weight = actual_weight_kg` (Mifflin path, НЕ Брока)
- Step 4 BMR — new ELSIF branch `v_lbm_kg IS NOT NULL` → Katch-McArdle (`370 + 21.6 × LBM`).

**Math (Woolcott & Bergman 2018, JCEM PMC 6054651):**

| | Formula | Validation |
|---|---|---|
| RFM Male | `BF% = 64 − 20 × (height_cm / waist_cm)` | Male H=180 W=95 → 26.1% ✓ |
| RFM Female | `BF% = 76 − 20 × (height_cm / waist_cm)` | Female H=170 W=100 → 42% ✓ |
| LBM | `weight × (1 − BF%/100)` | — |
| Katch BMR | `370 + 21.6 × LBM` | — |

Defensive clamp: `BF% ∈ [5, 60]%` против extreme inputs.

**Priority order BMR (с mig 292 интеграцией):**
1. age < 18 → pediatric (Schofield-HW / Molnar)
2. age > 75 → geriatric (Lührmann)
3. **phenotype='obese' AND waist NOT NULL → Katch-McArdle** ← mig 295
4. else → Mifflin-St Jeor

Pediatric/geriatric sacrosanct над Katch — safety > accuracy boost.

**UX (lighter approach, owner-approved):**
- `edit_waist` ui_screen (pattern из `ask_weight`, input_type='text_input').
- Entry button «📏 Уточнить талией» на `phenotype_result` screen с `visible_condition='u.phenotype=obese AND u.waist_circumference IS NULL'`. **Не правили `process_user_input` FSM** — quiz остаётся 4-step.

**Retrofit cron:** `cron_get_reminder_candidates` extend с type `'waist_retrofit'` (hour=14 local, WHERE phenotype='obese' AND waist_circumference IS NULL). Anti-spam через existing `notification_log` NOT EXISTS pattern.

**Telemetry:** `calculations.lbm_kg` (NULL если не Katch), `calculations.rfm_body_fat_pct`, `calculations.bmr_formula='katch_mcardle'`.

**Tests:** 8 sentinel checks прошли (math drift < 1 kcal); 8 pytest integration зелёных — включая T7 multi-mig compatibility (vegan obese adult: Katch BMR + protein × 1.25).

**Real-world impact:** 0 obese users в проде на момент apply (37 default, 1 monw) → нулевая регрессия. Retrofit cron активируется когда первый obese зарегистрируется через quiz.

**Key lesson — single-source Брока removal каскадирует.** Все downstream Macros (Step 7) и carbs floor (Step 8) уже параметризованы через `v_target_weight` — surgical edit в Step 3 obese branch автоматически обновляет protein/fat/carbs targets для всего obese path. Headless architecture сила.

**Out of scope:** Q5 в quiz pipeline FSM правка (Variant B lighter chosen); onboarding step для waist (только через retrofit + Profile entry).

### P2.4 Phase 3 Adaptive Modifiers (сон / стресс / цикл)

| Trigger | Действие | Pivot от DR |
|---|---|---|
| Sleep < 6h | +15% protein, углеводы −эквивалент | OK, Protein Leverage Hypothesis |
| High stress | +10-15% carbs за счёт fat | **low-GI углеводы обязательно** (иначе скачок инсулина + кортизол → visceral fat) |
| Luteal phase | +150-200 kcal, fat +5-10% | OK, прогестерон термогенез |

- **Severity:** informational (banner «адаптировано под состояние») + silent accuracy (для расчёта)
- **Deps:** Daily/event-driven check-in patterns ([[concepts/user-data-collection-pattern]]) + новые поля + messaging
- **Spec:** `.claude/specs/adaptive_modifiers_spec.md` (обновить с low-GI pivot)

### P2.5a Workout tracking infrastructure (prerequisite для P2.5b)

- Source: Apple Health / Strava / manual log в боте
- Schema: новая таблица `workouts(telegram_id, started_at, duration_min, met, calories)`
- **Severity:** new feature (не guard)
- **Deps:** UX wireframe + integration choice от owner

### P2.5b Energy Availability check (после P2.5a)

- EA = (target_kcal − exercise_kcal) / LBM. Если <30 → принудительное повышение калорий.
- **RED-S protection** для heavy + cardio + lose.
- **Severity:** soft override (юзер может opt-out с medical confirm — спортсмен на cut под надзором тренера)
- **Deps:** P2.5a + P2.1 (LBM)

### P2.6 Diet break automation

- Trigger: cron каждый день проверяет `goal=lose AND days_in_deficit > 56` → force `maintain` на 7-14 дней.
- Messaging: «Это перерыв для метаболизма, не сдача. Через 10 дней — обратно к похудению.»
- **Severity:** soft override (можно opt-out если осознанно нарушает)
- **Deps:** weight tracking history + days_in_deficit field + messaging

---

# 🟢 P3 BACKLOG — Architecture (6-9 мес, до 12)

### P3.1 Adaptive TDEE в стиле MacroFactor

DR's gold standard. Не предсказывать TDEE формулой (MSJ), а **измерять** по реальной динамике (EWMA веса × калорий за 14+ дней).

```
Истинный TDEE = (Avg calories consumed) + (Weight delta in kg × 7700 / days)
```

- **Архитектура:** Cold start = MSJ (первые 14 дней), потом detected adaptive TDEE.
- **Deps:** stable weight tracking history + weekly TDEE refresh cron + UX retraining + canary 10%
- **Impact:** автоматически учитывает NEAT, TEF, adaptive thermogenesis, individual metabolic variation
- **Эта фича превращает NOMS из «калькулятора» в «adaptive engine»** — стратегический shift, сильно повышает retention.

---

## Юридический контекст (FTC / California)

Базис для severity `hard block` на детях:

- **FTC 2025:** оштрафовали NextMed на $150k за вводящие weight-loss claims
- **FTC:** TruHeight оштрафован за рекламу supplements для роста подростков
- **California:** готовится закон со штрафом $250k для платформ с алгоритмами, ведущими детей к diet products / РПП

Митигации зафиксированы:
- P0.1 hard block `<18+lose` без opt-out (ребёнок не consent'ит)
- P0.1 informational disclaimer для всех `<18` (legal cover)
- P0.6 hard block pregnancy
- [[concepts/safety-guard-ux-pattern]] L1+L2 cultural review + audit log для FTC traceability

---

## Связанные концепты

- [[concepts/agent-collaboration-protocol]] — 10 правил координации (Rule 1 severity, Rule 4 ownership)
- [[concepts/safety-guard-ux-pattern]] — UX pattern v2 (5-tier severity, auto-reset variants, L1/L2)
- [[concepts/user-data-collection-pattern]] — retrofit для new fields (P0.6, P1.2, P2.1)
- [[concepts/pregnancy-lactation-clinical-spec]] — clinical spec для P0.6 (готов, ждёт UX-wireframe)
- [[concepts/personalized-macro-split]] — текущая v6 формула (mig 234 applied)
- `handover/2026-05-16_deep_research_handoff.md` — пакет deep research
- `handover/2026-05-17_mig234_copywriter_brief.md` — brief копирайтеру (in-flight artifact)
