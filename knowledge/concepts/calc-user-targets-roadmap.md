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
created: 2026-05-17
updated: 2026-05-17
---

# calculate_user_targets — Roadmap P0-P3

Living document. Объединяет внутренний аудит формулы (v3→v4→v5, mig 055/227/230) + результаты deep research нутрициолога (2026-05-16) + спорные пункты и pivot'ы команды. Каждая строка — задача с обоснованием, зависимостями, рисками. Обновлять при каждом merge/decision.

## Принципы

1. **Один atomic task = одна миграция.** Разные фичи не объединяются в один PR (легче ревью, легче откат, легче sentinel scope).
2. **Safety первее accuracy.** P0 закрывается до P1 — даже если accuracy fix готов раньше.
3. **Каждый task с deep research review.** Перед spawn'ом — отдельный research-агент изучает peer-reviewed evidence по конкретной задаче. Не доверяемся одному отчёту, валидируем точечно. Вдруг исследователь упустил.
4. **Stack-aware planning.** Если задача требует новое поле в `users` — параллельно дизайнится pattern сбора у existing юзеров (см. [[concepts/user-data-collection-pattern]]).
5. **13-language messaging.** Любая user-facing коммуникация (особенно safety triggers «обратитесь к врачу») требует copywriter agent на 13 языках.

## Status (на 2026-05-17)

- **Prod state:** mig 230 (v5) — PAL fusion + 'none' coefs + conditional clamp + gender carbs floor.
- **In-flight:** mig 234 — Age guards (block lose <18, warning >75). Готова к apply, агент `claude/stoic-nash-46a4f3` подтвердил Variant 1 staged подход.
- **Deep research:** done 2026-05-16, выявил 4 P0 пробела + 3 SHOULD-FIX accuracy + nice-to-have. Полный отчёт: [handover/2026-05-16_deep_research_handoff.md].

---

## 🔴 P0 — Safety (1-2 недели)

### P0.1 ✅ Age guards (block lose <18, warning >75) — **mig 234 готова, ждёт apply**

Простой goal_type override + JSON telemetry. **Baseline guard**, не финальное решение.

- **Где:** `calculate_user_targets` Step 2 (after age) + Step 6 (goal adjustment)
- **Поля JSON:** `age_warning`, `original_goal_type`, `effective_goal_type`
- **Sentinel:** 6 кейсов (underage-lose/gain/maintain, elderly, boundary-18, boundary-75)
- **Status:** SQL написана, ветка `claude/stoic-nash-46a4f3`. Ждёт КТ-1 review.

### P0.2 🟡 Возрастные формулы (Schofield/Molnar/Lührmann) — **mig 235**

После apply mig 234 — отдельная миграция для accuracy. Pivot от агента 234 (на основе свежих research):

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

### P0.3 🔴 Min kcal floor 1200ж / 1500м — **отдельная mig**

Critical safety. DR (deep research) выявил **критическую дыру** — миниатюрная женщина с агрессивным дефицитом может получить расчёт <1000 ккал. Это medical supervision-only режим (PSMF), не для autonomous app.

- **Где:** `calculate_user_targets` Step 8 (target rebalance), после clamp
- **Реализация:** `v_target := GREATEST(v_target, CASE gender WHEN 'female' THEN 1200 ELSE 1500 END)`
- **JSON:** `min_kcal_floor_triggered` boolean
- **Deps:** none
- **Research:** WHO guidelines (1200/1500 — баланс между BMR и survival), ACSM, EFSA

### P0.4 🔴 BMI sanity check + age range — **отдельная mig**

DR: «текущая валидация проверяет лишь техническое присутствие данных (NOT NULL), но игнорирует физиологическую адекватность».

- **Где:** `calculate_user_targets` Step 1 (load user), после INCOMPLETE_DATA guard
- **Реализация:** RETURN error если BMI < 14 / > 60 или age < 13 / > 90
- **Аналогия с UI validation:** UI пускает с age 13, но если кто-то ввёл вес 35 + рост 180 — формула посчитает кошмарный дефицит. SQL должна быть **самодостаточной**.
- **Deps:** none
- **Considered:** добавить как extra constraint без INCOMPLETE_DATA fallback

### P0.5 🔴 BMI <18.5 + goal=lose → SQL override

DR: «SQL-логика должна быть самодостаточной и аппаратно переопределять goal_type на gain или maintain при BMI < 18.5, игнорируя входящие параметры». Сейчас защита от похудения для underweight живёт только на уровне UI — если функция вызовется напрямую (cron, internal RPC), защита не сработает.

- **Где:** `calculate_user_targets` Step 6 (goal adjustment)
- **Реализация:** `IF v_bmi < 18.5 AND v_user.goal_type = 'lose' THEN v_forced_goal_type := 'maintain'; v_underweight_warning := TRUE`
- **JSON:** `underweight_override_triggered`
- **Deps:** none (можно сразу)

### P0.6 🔴 Pregnancy / Lactation поле + защита

Самая сложная P0 — требует новые поля + UX wireframe + retrofit cron для existing женщин. Опасный дефицит при беременности → кетонемия → нейротоксична для плода.

- **Новые поля users:** `is_pregnant BOOLEAN DEFAULT FALSE`, `is_lactating BOOLEAN DEFAULT FALSE`, опц. `pregnancy_trimester INT`, `lactation_started DATE`
- **Где в формуле:** Step 6 — force maintain (или add maintenance kcal +300-500 в зависимости от триместра/лактации)
- **UX questions** (требуют решение тимлида перед spawn'ом):
  - Где собираем? Новый шаг в онбординге (только для gender=female age 15-50)? Toggle в Profile? One-time popup для existing?
  - Privacy: GDPR sensitive data — opt-in с явным объяснением.
- **Retrofit:** см. [[concepts/user-data-collection-pattern]] — cron для опроса existing женщин (gender=female AND age 15-50 AND is_pregnant IS NULL)
- **Messaging:** требует copywriter agent на 13 языках (≥10 строк: prompt с объяснением, согласие, отказ, подтверждение, smart-defaults для возраста / триместра)
- **Deps:** UX-decision от тимлида → новые поля → retrofit cron pattern зафиксирован → migration + messaging

---

## 🟠 P1 — Accuracy (2-4 недели после P0)

### P1.1 fat_floor — ОТКРЫТЫЙ вопрос (actual vs target weight)

DR утверждает: «fat_floor должен рассчитываться от текущей массы тела, а не от target_weight». Текущий prod использует target_weight.

**Спор:**
- **DR position:** floor от actual = эндокринная буферизация зависит от общей массы тела (стандартная рекомендация 0.8 г/кг body weight).
- **Текущая prod:** floor от target_weight = гормоны производятся в lean mass, не в жире. Для obese 100 кг + actual = 80 г жира = 36% от target_calories на cut — слишком много.

**Что делать:** перед изменением — отдельный research session (нужно второе мнение клинического нутрициолога). НЕ менять самостоятельно. Возможно компромисс: floor от actual только для **default phenotype**, от target_weight для obese/monw.

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
- **Pattern:** см. [[concepts/user-data-collection-pattern]] — daily check-in vs one-time

### P2.5 Workout tracking + Energy Availability check

DR: «Заменить статический углеводный пол на динамический барьер EA = (Target Calories − Exercise Energy Expenditure) / LBM. Если EA < 30 → принудительно повышать калории».

- **Нужно:** workout duration + MET multiplier tracking (новая таблица или интеграция с Apple Health / Strava)
- **RED-S protection:** при heavy + cardio + lose → EA check блокирует катастрофу
- **Deps:** P2.1 (LBM) + workout tracking infrastructure

### P2.6 Diet break automation

DR: «После 8-12 недель агрессивного goal=lose система должна инициировать Diet Break, принудительно пересчитывая target_calories на уровень maintain продолжительностью 7-14 дней».

- **Trigger:** cron каждый день проверяет users где goal=lose AND days_in_deficit > 56
- **Действие:** force `goal_type='maintain'` на 7-14 дней, потом возврат
- **Messaging:** объяснение «Это перерыв для метаболизма, не сдача. Через 10 дней вернёмся к похудению.»
- **Deps:** weight tracking history + days_in_deficit field + messaging

---

## 🟢 P3 — Architecture roadmap (3-6 месяцев)

### P3.1 Adaptive TDEE в стиле MacroFactor

**DR positions this as the gold standard.** Концептуально: не предсказывать TDEE формулой (MSJ), а **измерять** по реальной динамике веса × калорий за 14+ дней. EWMA (Exponentially Weighted Moving Average).

```
Истинный TDEE = (Avg calories consumed) + (Weight delta in kg × 7700 / days)
```

- **Архитектура:** Cold start = MSJ (первые 14 дней), потом detected adaptive TDEE.
- **Deps:** stable weight tracking history (14+ дней) для каждого юзера + cron для weekly TDEE refresh
- **Impact:** автоматически учитывает NEAT, TEF, adaptive thermogenesis, individual metabolic variation
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
