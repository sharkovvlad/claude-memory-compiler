---
title: "calculate_user_targets — Roadmap P0-P3"
aliases: [roadmap-targets, safety-roadmap, calc-targets-backlog]
tags: [nutrition, safety, roadmap, calculate-user-targets, supabase]
sources:
  - "daily/2026-05-15.md"
  - "daily/2026-05-16.md"
  - "daily/2026-05-17.md"
  - "handover/2026-05-16_deep_research_handoff.md"
  - "Downloads/Глубокий анализ формулы расчета целей NOMS.md (deep research 2026-05-16)"
  - "Agent 234 critique 2026-05-17 (12/13 правок принято)"
created: 2026-05-17
updated: 2026-05-17
---

# calculate_user_targets — Roadmap P0-P3

Living document. Объединяет внутренний аудит формулы (v3→v4→v5, mig 055/227/230) + результаты deep research нутрициолога (2026-05-16) + критику агента 234 (2026-05-17) + спорные пункты и pivot'ы команды. Каждая строка — задача с обоснованием, зависимостями, рисками. Обновлять при каждом merge/decision.

## Принципы

1. **Один atomic task = одна миграция.** Разные фичи не объединяются в один PR (легче ревью, легче откат, легче sentinel scope). **Исключение:** связанные guards с общей telemetry-field имеет смысл объединять (см. P0.4 BMI-aware guards).
2. **Safety первее accuracy.** P0 закрывается до P1 — даже если accuracy fix готов раньше.
3. **Каждый task с deep research review.** Перед spawn'ом — отдельный research-агент изучает peer-reviewed evidence по конкретной задаче. Не доверяемся одному отчёту, валидируем точечно.
4. **Stack-aware planning.** Если задача требует новое поле в `users` — параллельно дизайнится pattern сбора у existing юзеров (см. [[concepts/user-data-collection-pattern]]).
5. **13-language messaging.** Любая user-facing коммуникация (особенно safety triggers «обратитесь к врачу») требует copywriter agent на 13 языках.
6. **Argued override, не молчаливая подмена.** Если бот меняет goal пользователя — обязательно user-visible banner с объяснением. Молчаливая подмена = (а) churn («бот сломан»), (б) FTC-слабая позиция, (в) противоречит Sassy Sage характеру. См. P0.8 + будущий `safety-guard-ux-pattern.md`.

## Status (на 2026-05-17)

- **Prod state:** mig 230 (v5) — PAL fusion + 'none' coefs + conditional clamp + gender carbs floor.
- **In-flight:** mig 234 — Age guards (block lose <18, warning >75). Готова к apply, агент `claude/stoic-nash-46a4f3` доделывает `underage_disclaimer` (telemetry для всех <18 даже non-lose).
- **Deep research:** done 2026-05-16, выявил 4 P0 пробела + 3 SHOULD-FIX accuracy + nice-to-have. Полный отчёт: `handover/2026-05-16_deep_research_handoff.md`.
- **Agent 234 critique:** 2026-05-17, принято 12/13 правок к roadmap+pattern (см. daily/2026-05-17).

---

## 🔴 P0 — Safety (1-2 недели)

### P0.1 ✅ Age guards (block lose <18, warning >75) — **mig 234, in-flight**

Простой goal_type override + JSON telemetry. **Baseline guard**, не финальное решение. Расширение: `underage_disclaimer` для всех <18 (UI banner «формулы адаптированы под возраст, мы не заменяем врача»).

- **Где:** `calculate_user_targets` Step 2 (after age) + Step 6 (goal adjustment)
- **Поля JSON:** `age_warning`, `original_goal_type`, `effective_goal_type`
- **Sentinel:** 6 кейсов (underage-lose/gain/maintain, elderly, boundary-18, boundary-75)
- **Status:** SQL написана, ветка `claude/stoic-nash-46a4f3`. Ждёт КТ-1 review + добавление `underage_disclaimer`.

### P0.2 🟡 Возрастные формулы (Schofield/Molnar/Lührmann) — **mig 235**

После apply mig 234 — отдельная миграция для accuracy. Pivot от агента 234:

| Кейс | Формула | Почему |
|---|---|---|
| <18, BMI<30 | **Schofield-HW** | best для здоровых 3-18 лет, mean diff vs калориметрии = 3.7 ккал/день (PMC 8685418) |
| <18, BMI≥30 | **Molnar** | best для obese подростков, точность 87% |
| <18 + goal=gain, age 13-14 | force maintain | активный пубертат, набор без врача рискован |
| <18 + goal=gain, age 15-17 | разрешить + disclaimer | старшие подростки сознательно набирают (спорт/growth) |
| >75 | **Lührmann** | учёт саркопении, лучше Mifflin (PubMed 17583391) |
| >75 + goal=lose | clamp speed на `slow` max (-10%, не -20%) | агрессивный дефицит ускоряет саркопению |

- **JSON telemetry:** `bmr_formula` поле (`mifflin`/`schofield_hw`/`molnar`/`luhrmann`)
- **UI:** banner «формулы адаптированы под твой возраст. Мы не заменяем врача.» — legal cover (см. ниже про FTC/California)
- **Deps:** mig 234 merged
- **Research note:** Mifflin под-predict в 79% случаев у obese youth (Nature Sci Rep 2023) — формула не просто «неточная», она систематически занижает → ребёнок на goal=lose получает экстремальный дефицит. Это **именно почему** mig 234 baseline force maintain правильный.

### P0.3 🔴 Min kcal floor (compromise: GREATEST 1200/1500 + BMR) — **отдельная mig**

Critical safety. DR выявил критическую дыру (миниатюрная женщина 45 кг с агрессивным дефицитом → расчёт <1000 ккал = PSMF режим, medical supervision only).

**Compromise от агента 234** (избегает странного edge case где fixed 1200 > maintenance):

```sql
v_target := GREATEST(
    v_target,                                           -- result после Step 8
    CASE WHEN gender='female' THEN 1200 ELSE 1500 END,  -- medical industry floor
    ROUND(v_bmr)::INTEGER                                -- physiological BMR floor
);
```

- **Логика:** двойная защита: medical guideline (WHO/ACSM/EFSA) + BMR-based physiological floor.
- **Edge case:** если BMR < 1200 для миниатюрной женщины → дефицит вообще не показан → triggers warning «BMR ниже medical floor, дефицит не рекомендован → переключаем на maintain». Спасает её от попытки худеть на enzymatically невозможном уровне.
- **JSON:** `min_kcal_floor_triggered` (boolean), `min_kcal_floor_source` (`medical_1200`/`medical_1500`/`bmr_floor`)
- **Deps:** none

### P0.4 🔴 BMI-aware guards (объединённые tiered policy) — **отдельная mig**

**Объединили P0.4 + P0.5** в один atomic task (общая telemetry-field `bmi_warning`, единый disclaimer-pattern, одна миграция).

Tiered BMI policy, **не RETURN ERROR** (он сломал бы Profile у edge cases типа 60-летняя с раком BMI 13.5 в реабилитации):

| BMI range | Action |
|---|---|
| **BMI < 14** (extreme cachexia) | force `goal_type='maintain'` + warning `bmi_warning='extreme_cachexia_recommend_medical'`. Не error — продолжаем считать target, но без дефицита. |
| **BMI 14-18.5** (underweight) | если `goal_type='lose'` → force `goal_type='maintain'` + warning `bmi_warning='underweight_lose_override'`. P0.5 был именно про это. Защита SQL-самодостаточная (не зависит от UI filter). |
| **BMI > 60** (extreme morbid obesity) | warning `bmi_warning='extreme_obesity_clamp_slow'` + clamp goal_speed на `slow` max (нельзя fast/normal deficit без medical supervision). |
| **age < 13 / age > 90** | error (validator должен был отсечь — defensive) |

- **JSON:** `bmi_warning` (text enum / NULL), `original_goal_type`, `effective_goal_type` (re-use из P0.1)
- **Deps:** P0.1 (использует те же telemetry-поля)

### P0.6 🔴 Pregnancy / Lactation поле + защита

Самая сложная P0 — требует новые поля + UX wireframe + retrofit cron для existing женщин. Опасный дефицит при беременности → кетонемия → нейротоксична для плода.

- **Новые поля users:** `is_pregnant BOOLEAN DEFAULT NULL` (**не FALSE** — critical, см. [[concepts/user-data-collection-pattern]] § smart defaults), `is_lactating BOOLEAN DEFAULT NULL`, опц. `pregnancy_trimester INT`, `lactation_started DATE`
- **Где в формуле:** Step 6 — force maintain (или add maintenance kcal +300-500 в зависимости от триместра/лактации). Для `gender=female AND age 15-50 AND is_pregnant IS NULL` → защитный default force maintain + soft warning «уточни в Профиле».
- **UX questions** (требуют решение тимлида перед spawn'ом):
  - Где собираем? Новый шаг в онбординге (только для gender=female age 15-50)? Toggle в Profile? One-time popup для existing?
  - Privacy: GDPR sensitive data — opt-in с явным объяснением.
- **Retrofit:** см. [[concepts/user-data-collection-pattern]] — cron для опроса existing женщин (gender=female AND age 15-50 AND is_pregnant IS NULL)
- **Messaging:** требует copywriter agent на 13 языках (≥10 строк: prompt с объяснением, согласие, отказ, подтверждение, smart-defaults для возраста / триместра)
- **Deps:** UX-decision от тимлида → новые поля → retrofit cron pattern зафиксирован → migration + messaging

### P0.8 🔴 UI surfaces + opt-out matrix — **мета-задача, новый KB**

JSON telemetry полей недостаточно. Каждый guard должен иметь **decision tree для UI**: где показывается banner, можно ли opt-out, expiry.

**Дифференциация hard vs soft guards** (критично — opt-out не для всех):

| Guard category | Examples | Opt-out? | Почему |
|---|---|---|---|
| **HARD safety** | age<18 force maintain, pregnancy force maintain, BMI<14 cachexia, BMI<18.5 underweight | ❌ **НЕТ opt-out** | Legal floor (FTC/California — ребёнок не может consent), medical floor (РПП-риск, плод). |
| **SOFT advisory** | athlete using default formula, age>75 less-accurate warning, low-EA warning (после P2.5b) | ✅ **Opt-out OK** | Информационный, не life-threatening. Юзер с тренером может сознательно accept risk: «я понимаю, ответственность на мне». |

- **Где зафиксировать:** новый KB concept `safety-guard-ux-pattern.md` (после apply mig 234). Принцип «argued override», decision tree, opt-out matrix, expiry rules (age_warning снимается auto при апдейте dob), 13-language messaging map.
- **Deps:** mig 234 apply + копирайтер agent на 3 messaging templates (`underage_forced_maintain`, `underage_disclaimer`, `elderly_less_accurate`)

---

## 🟠 P1 — Accuracy (2-4 недели после P0)

### P1.1 fat_floor — phenotype branch (resolved через compromise агента 234)

Раньше был открытый спор (DR: floor от actual_weight, prod: от target_weight). Compromise:

```sql
v_fat_floor := CASE COALESCE(v_user.phenotype, 'default')
    WHEN 'obese' THEN ROUND(v_fat_min_g_per_kg * v_target_weight)  -- target_weight (LBM proxy)
    WHEN 'monw'  THEN ROUND(v_fat_min_g_per_kg * v_target_weight)  -- target_weight
    ELSE ROUND(v_fat_min_g_per_kg * v_user.weight_kg)              -- actual (default + athlete)
END;
```

**Логика:** для obese/monw — target_weight даёт реалистичный floor (avoids overload жирами на cut). Для default/athlete — actual_weight (стандартная рекомендация 0.8 г/кг body weight, athlete: actual ≈ LBM).

### P1.2 Vegan / vegetarian protein adjustment

- DIAAS показывает: растительные белки имеют biological value 70-80%
- Веган на дефиците с нормой 1.6 г/кг фактически усвоит ~1.1-1.2 г/кг → катаболизм мышц
- **Решение:** flag `diet_type` (`omnivore`/`vegan`/`vegetarian`) → `protein × 1.25` для vegan
- **UX:** где собираем? см. [[concepts/user-data-collection-pattern]]
- **Deps:** UX-decision

### P1.3 Adjusted Body Weight для obese (промежуток до Phase 2 RFM)

DR: «До развертывания Phase 2 следует применять формулу Adjusted Body Weight = IBW + 0.25 × (Actual − IBW), которая является стандартом в клинической диетологии для пациентов с ожирением». Лучше Брока, не требует waist circumference.

- **Где:** `calculate_user_targets` Step 3 (phenotype='obese' ветка)
- **Замена:** `v_target_weight := IBW + 0.25 * (v_user.weight_kg - IBW)` (где IBW = Брока)
- **Эффект:** меньшее занижение target_weight для obese, более realistic protein/fat targets
- **Deps:** none

### P1.4 Phenotype 'athlete' telemetry + UI disclaimer

Сейчас athlete = default (target_weight = actual_weight). Для серьёзного атлета (LBM 80 кг, weight 90 кг) считаем как для 90-кг dude → слегка занижаем потребности.

- **До перехода на Katch-McArdle (P2.3)** — minimal fix:
  - JSON: `bmr_formula='mifflin'` + `athlete_using_default_formula=TRUE`
  - UI: banner «athlete-specific formula coming soon» (soft guard, opt-out OK)
- **Категория:** P1 accuracy, не P0 safety (silent gap, не life-threatening)

---

## 🟡 P2 — Adaptive (после Phase 2 quiz расширения)

### P2.1 Phase 2 quiz расширение — waist circumference

Чтобы перейти на RFM (Woolcott 2018) для obese — единственный sciencefull замены Брока.

- **Новый Q5:** «Окружность талии» (см / inches) — optional, skippable
- **JSON:** `phenotype_answers.q5_waist_cm`
- **Pattern:** см. [[concepts/user-data-collection-pattern]] — retrofit для existing юзеров с obese phenotype

### P2.2 RFM вместо Adjusted Body Weight для obese

После P2.1 — RFM формула: `RFM = 64 - (20 × height/waist) + (12 × sex)` → даёт более точный LBM proxy.

- **Источник:** Woolcott & Bergman 2018 (PMC 6054651)
- **Deps:** P2.1 (нужна waist data)

### P2.3 Katch-McArdle на базе LBM (вместо Mifflin когда есть LBM)

DR: «При наличии надежных данных о LBM алгоритм должен переключаться на Katch-McArdle». BMR = 370 + 21.6 × LBM. Изолирует метаболически активную ткань.

- **Switch criteria:** если phenotype_answers.q5_waist_cm IS NOT NULL → Katch-McArdle, иначе Mifflin
- **Deps:** P2.2 (RFM даёт LBM)

### P2.4 Phase 3 Adaptive Modifiers (сон / стресс / цикл)

**Полностью одобрен deep research** с одним nuance:

| Trigger | Действие | Pivot от DR |
|---|---|---|
| Sleep < 6h | +15% protein, углеводы -эквивалент | OK, evidence-based (Protein Leverage, Simpson & Raubenheimer) |
| High stress | +10-15% carbs за счёт fat | **Важно: low GI углеводы** (иначе скачок инсулина + кортизол → visceral fat) |
| Luteal phase | +150-200 kcal, fat +5-10% | OK, фундаментально обосновано (прогестерон термогенез) |

- **Spec:** `.claude/specs/adaptive_modifiers_spec.md` (обновить с low-GI pivot)
- **Deps:** UX для daily check-in (cron messaging pattern) + новые поля + messaging
- **Pattern:** см. [[concepts/user-data-collection-pattern]] § daily/event-driven/weekly разделение

### P2.5a Workout tracking infrastructure — **отдельный prerequisite**

DR: для EA-check нужны exercise calories (duration × intensity → MET). Сейчас у нас только `training_type` категория — этого недостаточно.

- **Source options:** Apple Health / Strava / manual workout log в боте
- **Schema:** новая таблица `workouts(telegram_id, started_at, duration_min, met, calories)`
- **Deps:** UX wireframe + integration choice от тимлида

### P2.5b Energy Availability check — **после P2.5a**

DR: «Заменить статический углеводный пол на динамический барьер EA = (Target Calories − Exercise Energy Expenditure) / LBM. Если EA < 30 → принудительно повышать калории».

- **Без P2.5a EA = target_calories / LBM** — бесполезно (вырождается в почти-BMR check). Agent 234 правильно подсветил: без infrastructure это «фантом».
- **RED-S protection:** при heavy + cardio + lose → EA check блокирует катастрофу
- **Deps:** P2.5a (workout tracking) + P2.1 (LBM из RFM)

### P2.6 Diet break automation

DR: «После 8-12 недель агрессивного goal=lose система должна инициировать Diet Break, принудительно пересчитывая target_calories на уровень maintain продолжительностью 7-14 дней».

- **Trigger:** cron каждый день проверяет users где goal=lose AND days_in_deficit > 56
- **Действие:** force `goal_type='maintain'` на 7-14 дней, потом возврат
- **Messaging:** объяснение «Это перерыв для метаболизма, не сдача. Через 10 дней вернёмся к похудению.»
- **Deps:** weight tracking history + days_in_deficit field + messaging

---

## 🟢 P3 — Architecture roadmap (6-9 месяцев, возможно до 12)

### P3.1 Adaptive TDEE в стиле MacroFactor

**DR positions this as the gold standard.** Концептуально: не предсказывать TDEE формулой (MSJ), а **измерять** по реальной динамике веса × калорий за 14+ дней. EWMA (Exponentially Weighted Moving Average).

```
Истинный TDEE = (Avg calories consumed) + (Weight delta in kg × 7700 / days)
```

- **Архитектура:** Cold start = MSJ (первые 14 дней), потом detected adaptive TDEE.
- **Deps:** stable weight tracking history (14+ дней) для каждого юзера + cron для weekly TDEE refresh
- **Impact:** автоматически учитывает NEAT, TEF, adaptive thermogenesis, individual metabolic variation
- **Timeline (agent 234 pivot):** 6-9 мес минимум, реально до 12 — это **fundamental architectural shift** + UX retraining (юзер откроет Profile, увидит другие числа — нужен onboarding на новую модель) + canary 10% перед mass rollout. Иначе массовый «бот сломался, цифры скачут» churn.
- **Эта фича превращает NOMS из «калькулятора» в «adaptive engine»** — стратегический shift, сильно повышает retention.

---

## Юридический контекст (FTC / California)

**Это не paranoia, реальный risk на 1-3 года вперёд:**

- **FTC 2025:** оштрафовали NextMed на $150k за вводящие weight-loss claims
- **FTC:** TruHeight оштрафован за рекламу supplements для роста подростков (FTC активно смотрит «детский сегмент»)
- **California:** готовится закон со штрафом $250k для платформ с алгоритмами, ведущими детей к diet products / РПП

**Митигации:**
- P0.1 age guards (block lose <18) — first line
- P0.2 disclaimer banner «формулы адаптированы под твой возраст. Мы не заменяем врача.» — legal cover
- P0.6 pregnancy — отдельная защита (legal liability огромная)
- P0.8 UI surfaces + hard-guard NO opt-out для подростков и беременных — юридически правильная позиция
- Все safety triggers должны иметь user-visible disclaimer на 13 языках

---

## Что делать ДО spawn каждой задачи

1. **Создать отдельный research handoff** — точечный исследовательский запрос по конкретной задаче (вдруг исследователь упустил).
2. **Решить UX-вопросы** если требуются новые поля (где собирать, как у existing юзеров).
3. **Согласовать messaging** если есть user-facing коммуникация (copywriter agent с 13 языками).
4. **Зафиксировать backfill стратегию** для existing users (cron / one-time popup / Profile prompt).

См. [[concepts/user-data-collection-pattern]] для reusable framework по 2-4.

---

## Связанные концепты

- [[concepts/personalized-macro-split]] — текущая v5 формула (база)
- [[concepts/user-data-collection-pattern]] — reusable framework для добавления полей у existing users
- [[concepts/migration-collision-guard]] — защита от collision NNN
- `handover/2026-05-16_deep_research_handoff.md` — полный пакет deep research
- `Downloads/Глубокий анализ формулы расчета целей NOMS.md` — отчёт DR (внешний агент)
- (Будущий) `safety-guard-ux-pattern.md` — decision tree UI banners + opt-out matrix (создаётся после mig 234 apply)
