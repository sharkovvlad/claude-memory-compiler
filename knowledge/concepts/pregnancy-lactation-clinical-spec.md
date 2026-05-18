---
title: "Pregnancy / Lactation — Clinical Spec для P0.6"
aliases: [pregnancy-spec, lactation-spec, p06-clinical, maternal-nutrition]
tags: [nutrition, safety, clinical, calculate-user-targets, p0, maternal]
sources:
  - "IOM (Institute of Medicine) 2002/2005 Dietary Reference Intakes"
  - "WHO 2004 Human energy requirements (FAO/WHO/UNU Expert Consultation)"
  - "ACOG (American College of Obstetricians and Gynecologists) 2013 guidelines"
  - "daily/2026-05-17.md"
  - "concepts/calc-user-targets-roadmap.md (P0.6)"
created: 2026-05-17
updated: 2026-05-17
---

# Pregnancy / Lactation — Clinical Spec для P0.6

Клиническая спецификация для имплементации защиты беременных / кормящих в `calculate_user_targets`. Готова к spawn миграции **после** UX-wireframe от owner (где собирать `is_pregnant` флаг).

**Severity:** `hard block` (per [[concepts/agent-collaboration-protocol]] Rule 1). Опасный дефицит при беременности → кетонемия → нейротоксична для плода. **Никакого opt-out** — medical lock.

---

## 1. Научное обоснование (peer-reviewed)

### Энергопотребности беременности (per IOM 2002, Table 5-15)

| Триместр | Дополнительные kcal/день | Обоснование |
|---|---|---|
| 1 (1-12 нед) | **+0 ккал** | Минимальное увеличение tissue accretion, BMR ≈ baseline |
| 2 (13-27 нед) | **+340 ккал** | Tissue accretion + lactose synthesis prep + BMR ↑ 7% |
| 3 (28+ нед) | **+452 ккал** | Maximum tissue accretion + BMR ↑ 19% + organ growth |

**Источники:**
- Institute of Medicine. "Dietary Reference Intakes for Energy, Carbohydrate, Fiber, Fat, Fatty Acids, Cholesterol, Protein, and Amino Acids." Washington, DC: National Academies Press, 2005.
- WHO/FAO/UNU Expert Consultation. "Human energy requirements." Rome, 2004.

### Энергопотребности лактации (per IOM 2002, Table 5-17)

| Тип лактации | Дополнительные kcal/день | Обоснование |
|---|---|---|
| Exclusive breastfeeding (0-6 мес) | **+500 ккал − 170 mobilization = +330 ккал** | Milk synthesis 750 mL/day × ~0.67 kcal/mL = 500 ккал; minus ~170 ккал from maternal fat stores |
| Partial breastfeeding (>6 мес или mixed) | **+300 ккал** | Reduced milk production ~500 mL/day + complementary feeding |
| Weaning / no lactation | 0 | N/A |

### Протеиновые потребности

| Состояние | Дополнительно (на baseline 0.8 г/кг) | Total target |
|---|---|---|
| Pregnancy (любой триместр) | +25 г/день | ~1.1 г/кг |
| Lactation exclusive | +25 г/день | ~1.3 г/кг (учитывая milk protein) |
| Lactation partial | +15 г/день | ~1.1 г/кг |

### Углеводы — критический минимум

- **Pregnancy minimum: 175 г/день углей** (IOM 2002) для обеспечения plasma glucose плода. Это **выше** нашего `carbs_min_g_female=100` floor.
- **Lactation minimum: 210 г/день** (IOM 2002) для milk lactose synthesis.

### Почему опасен дефицит

- **Кетонемия:** при low carb / caloric deficit беременная developing ketosis → ketones cross placenta → нейротоксичны для развивающегося мозга плода (especially Q1-Q2). Documented в multiple cohort studies (Adam 1975, Rizzo 1991, Tanaka 2017).
- **Folate / iron / Vitamin D depletion** при caloric deficit → neural tube defects, IUGR, anaemia maternal.
- **Lactation: insufficient calories** → reduced milk quantity (mother body prioritizes milk → maternal depletion → fatigue, mood disorders).

---

## 2. SQL Logic Spec

### Новые поля `users` (с DEFAULT NULL per [[concepts/agent-collaboration-protocol]] Rule 2)

```sql
ALTER TABLE users
    ADD COLUMN is_pregnant BOOLEAN DEFAULT NULL,           -- WHY DEFAULT NULL: acute failure (silent harm) per Rule 2
    ADD COLUMN pregnancy_trimester SMALLINT DEFAULT NULL,  -- 1/2/3, NULL если не указано
    ADD COLUMN pregnancy_due_date DATE DEFAULT NULL,       -- для auto-reset
    ADD COLUMN is_lactating BOOLEAN DEFAULT NULL,
    ADD COLUMN lactation_type TEXT DEFAULT NULL CHECK (lactation_type IN ('exclusive', 'partial') OR lactation_type IS NULL),
    ADD COLUMN lactation_started DATE DEFAULT NULL;        -- для auto-reset

CREATE INDEX idx_users_maternal_protective ON users (telegram_id)
    WHERE gender = 'female' AND is_pregnant IS NULL AND birth_date IS NOT NULL;
-- Partial index для retrofit cron (filter F/15-50 с unknown pregnancy)
```

### Логика в `calculate_user_targets`

После Step 6 (goal adjustment), перед Step 7 (macros):

```sql
-- ── 6b. Maternal safety guard (P0.6) ────────────────────────────
-- Hard block: pregnancy/lactation override goal=lose к maintain + add kcal.
-- См. [[concepts/pregnancy-lactation-clinical-spec]] для научного обоснования.

v_pregnancy_warning := NULL;
v_lactation_warning := NULL;
v_maternal_kcal_bonus := 0;
v_maternal_protein_bonus := 0;
v_carbs_floor_override := NULL;  -- maternal carbs minimum (175 / 210 г) overrides standard 100/50

-- (a) Pregnancy CONFIRMED
IF v_user.is_pregnant = TRUE THEN
    -- Force maintain (override любого lose/gain)
    IF v_user.goal_type = 'lose' THEN
        v_forced_goal_type := 'maintain';
        v_pregnancy_warning := 'pregnancy_force_maintain';
    END IF;
    -- Trimester-based kcal addition
    v_maternal_kcal_bonus := CASE COALESCE(v_user.pregnancy_trimester, 2)  -- default Q2 if unknown trimester
        WHEN 1 THEN 0
        WHEN 2 THEN 340
        WHEN 3 THEN 452
        ELSE 340  -- defensive fallback
    END;
    v_maternal_protein_bonus := 25;
    v_carbs_floor_override := 175;  -- IOM minimum для plasma glucose плода

-- (b) Lactation CONFIRMED
ELSIF v_user.is_lactating = TRUE THEN
    -- Force maintain (даже если lactation+lose — milk depletion risk)
    IF v_user.goal_type = 'lose' THEN
        v_forced_goal_type := 'maintain';
        v_lactation_warning := 'lactation_force_maintain';
    END IF;
    v_maternal_kcal_bonus := CASE COALESCE(v_user.lactation_type, 'exclusive')
        WHEN 'exclusive' THEN 330
        WHEN 'partial' THEN 300
        ELSE 300  -- defensive fallback
    END;
    v_maternal_protein_bonus := CASE v_user.lactation_type
        WHEN 'exclusive' THEN 25
        ELSE 15
    END;
    v_carbs_floor_override := 210;  -- IOM lactation minimum

-- (c) PROTECTIVE MODE — pregnancy status UNKNOWN
-- Для F/15-50 с NULL is_pregnant → protective force maintain.
-- Не добавляем kcal (не знаем триместр), но защищаем от опасного дефицита.
ELSIF v_user.is_pregnant IS NULL
   AND LOWER(TRIM(v_user.gender)) IN ('female', 'f')
   AND v_age BETWEEN 15 AND 50
   AND v_user.goal_type = 'lose' THEN
    v_forced_goal_type := 'maintain';
    v_pregnancy_warning := 'maternal_status_unknown_protective_maintain';
    -- Soft warning: «уточни статус в Профиле для точного расчёта»
END IF;

-- Применить maternal_kcal_bonus к target после Goal adjustment
v_requested_kcal := v_requested_kcal + v_maternal_kcal_bonus;

-- В Step 7 protein:
v_protein := ROUND(v_protein_g_per_kg * v_target_weight) + v_maternal_protein_bonus;

-- В Step 7 carbs floor — override если maternal
v_carbs_min := COALESCE(
    v_carbs_floor_override,  -- maternal override (175 pregnancy / 210 lactation)
    (SELECT value::INT FROM app_constants WHERE key = 'carbs_min_g_' || gender_str),
    (SELECT value::INT FROM app_constants WHERE key = 'carbs_min_g'),
    50
);
```

### JSON return additions

```jsonb
"calculations": {
    ...,
    "pregnancy_warning": "pregnancy_force_maintain" | "maternal_status_unknown_protective_maintain" | NULL,
    "lactation_warning": "lactation_force_maintain" | NULL,
    "maternal_kcal_bonus": 340,       -- 0/340/452/330/300
    "maternal_protein_bonus": 25,     -- 0/25/15
    "carbs_floor_source": "maternal_pregnancy_175" | "maternal_lactation_210" | "gender_female_100" | "legacy_50"
}
```

---

## 3. Sentinel Test Cases (для КТ-2)

| # | Профиль | Expected | Что проверяет |
|---|---|---|---|
| 1 | F/28/165/68 + is_pregnant=TRUE + trimester=2 + lose+normal | force maintain + +340 kcal + +25g protein + carbs floor 175 | Q2 pregnancy override |
| 2 | F/30/170/72 + is_pregnant=TRUE + trimester=3 + lose+fast | force maintain + +452 kcal + +25g protein + carbs floor 175 | Q3 максимум |
| 3 | F/29/162/60 + is_pregnant=TRUE + trimester=NULL + maintain | maintain + +340 kcal (Q2 default) + +25g protein | Unknown trimester safe default |
| 4 | F/32/168/65 + is_lactating=TRUE + lactation_type=exclusive + lose | force maintain + +330 kcal + +25g protein + carbs floor 210 | Exclusive lactation |
| 5 | F/28/160/58 + is_lactating=TRUE + lactation_type=partial + maintain | maintain + +300 kcal + +15g protein + carbs floor 210 | Partial lactation |
| 6 | **F/25/162/55 + is_pregnant=NULL + lose+normal** | force maintain + 0 bonus + protective warning | **Protective mode — самая важная защита** |
| 7 | F/30/165/65 + is_pregnant=FALSE + lose+normal | No override (standard formula) | False-positive prevention |
| 8 | M/30/175/75 + lose+normal | No maternal logic triggered | Gender filter works |
| 9 | F/55/160/60 + is_pregnant=NULL + lose+normal | No protective mode (out of 15-50 age range) | Age range respect |

---

## 4. UX-Wireframe Options (для owner decision)

Это блокер для spawn'а миграции. Три варианта сбора `is_pregnant`:

### Option A — Onboarding step (новый шаг для F/15-50)

После goal selection, **до** registration confirmation:

> **🤰 Маленький вопрос для безопасности**
>
> Чтобы не навредить — нужно знать. Не для статистики, не для рекламы.
>
> [🤰 Беременна] [🤱 Кормлю] [❌ Ни то ни другое] [🤐 Не отвечу]

Если «Не отвечу» → `is_pregnant=NULL` → protective mode активируется.
Если «Беременна» → follow-up: «Какой триместр?» [Q1] [Q2] [Q3] [Не знаю]
Если «Кормлю» → follow-up: «Только грудью или с прикормом?» [Только грудью] [С прикормом]

**Pros:** 100% покрытие новых юзеров. **Cons:** добавляет 1-2 экрана в онбординг = drop-off risk.

### Option B — One-time retrofit popup для existing F (HIGH priority cron)

Те же 4 кнопки, но шлётся as one-time message в чат через 7 days window после deploy (per Rule 10 priority).

**Pros:** не задевает onboarding flow. **Cons:** некоторые игнорируют popup → остаются NULL → protective mode для них (acceptable fallback).

### Option C — Profile toggle (passive, юзер сам найдёт)

В Profile → Settings → Health: toggle «Беременность / лактация».

**Pros:** GDPR-friendly (passive). **Cons:** низкое adoption — юзер не знает что нужно сказать.

### Option D (recommended) — Combination A + B + C

- **A (onboarding):** для всех новых F/15-50 — 100% покрытие
- **B (retrofit):** one-time popup для existing F (HIGH priority — first 7 days)
- **C (Profile):** persistent edit point — для изменения статуса (новая беременность, окончание лактации)

Auto-reset (Rule 10 transitions):
- После `pregnancy_due_date + 30 days` → prompt «Как ты, всё ещё беременна или уже родила?» → switch на lactation flow или NULL.
- После `lactation_started + 24 months` → prompt «Всё ещё кормишь?» → reset.

**Privacy/GDPR:**
- Все 4 кнопки equal — «Не отвечу» не штрафуется, остаются NULL → protective mode.
- Можно отозвать в Profile → Settings → «Удалить данные о беременности» → reset to NULL.
- Никаких ретаргет-сообщений если ответил «Ни то ни другое» (1 раз спросили — больше не спрашиваем).

---

## 5. Translation Keys (10 keys × 13 langs = 130 строк)

Per [[concepts/safety-guard-ux-pattern]] Translation Pipeline. Severity = hard block → **L1+L2 cultural review mandatory** для AR/FA/HI/ID (Ramadan fasting context, halal medical advice, caste-aware healthcare).

```
prompt.maternal.onboarding              -- объяснение зачем спрашиваем
option.maternal.pregnant                -- кнопка «🤰 Беременна»
option.maternal.lactating               -- кнопка «🤱 Кормлю»
option.maternal.neither                 -- кнопка «❌ Ни то ни другое»
option.maternal.prefer_not              -- кнопка «🤐 Не отвечу»
prompt.maternal.trimester               -- follow-up «Какой триместр?»
prompt.maternal.lactation_type          -- follow-up «Только грудью или с прикормом?»

warning.maternal.pregnancy_force_maintain.banner_title
warning.maternal.pregnancy_force_maintain.banner_body
warning.maternal.pregnancy_force_maintain.modal_full      -- детальное объяснение + medical disclaimer

warning.maternal.lactation_force_maintain.banner_title
warning.maternal.lactation_force_maintain.banner_body
warning.maternal.lactation_force_maintain.modal_full

warning.maternal.status_unknown_protective.banner_title   -- «Защита для женщин 15-50 без указанного статуса»
warning.maternal.status_unknown_protective.banner_body
warning.maternal.status_unknown_protective.modal_full

warning.maternal.auto_resolved                            -- «У тебя сменился статус — защита снята»
```

**Total:** 17 keys × 13 langs = **221 строка**. Из них:
- 7 keys onboarding/options = informational (glossary self-screen)
- 10 keys warnings = hard block (mandatory L1+L2)

---

## 6. Что должен сделать mig-engineer после UX-wireframe

1. **Apply миграции** (поля + RPC update + sentinel)
2. **Retrofit cron** (HIGH priority, см. [[concepts/user-data-collection-pattern]] §4) для existing F/15-50 без is_pregnant
3. **Auto-reset cron** (daily) — проверяет `pregnancy_due_date + 30 days` или `lactation_started + 24 months` → prompt
4. **Storage:** `users.shown_guards JSONB` для one-time modal logic + `user_overrides` (но `is_pregnant` = hard block, opt-out=НЕТ, в overrides не пишется) + `guard_audit_log` event'ы
5. **Live-test sentinel** (Telethon) — F/25/162/55 с NULL → protective banner показывается; F+pregnant → banner + force maintain в Profile

---

## 6b. Goal interaction matrix — APPROVED 2026-05-18

Owner подтвердил clinical decision: **`is_pregnant=TRUE + goal=gain` НЕ блокировать.**

Базис: во время беременности норма прибавки 11.5-16 кг (плод+плацента+амнио+кровь). Q2/Q3 потребность +340-450 ккал/день. Если беременная осознанно выбрала `gain` — она клинически правильно следует норме. Force-maintain здесь бы означал **скрытое голодание плода**.

| goal_type | Maternal (pregnancy/lactation TRUE) | Maternal protective (NULL F/15-50) |
|---|---|---|
| **lose** | **Hard override → force maintain** + kcal bonus | **Hard override → force maintain** (no bonus, protective) |
| **maintain** | Allow + kcal bonus (целостный maternal расчёт) | Allow (no bonus, no override) |
| **gain** | **ALLOW** + kcal bonus (норма прибавки веса) | Allow (no bonus, no override) |

v8 (mig 254) уже реализует это правильно — gain branch не triggers `v_forced_goal_type`.

**Banner enforcement principle (canonical):** При любом forced override юзер **обязан** видеть banner с объяснением. Argued Override > silent substitution. Иначе UX = «бот сломан» + legal exposure (FTC silent override). Это distributed enforcement — banner injection должен быть на **всех** screens где user видит/меняет goal/данные влияющие на формулу (profile_main, my_plan, personal_metrics, day_summary). См. [[concepts/safety-guard-ux-pattern]] §2 touch-points #1-#5.

## 7. Что НЕ покрывает эта спека (явные ограничения)

- **Высокорисковая беременность** (gestational diabetes, preeclampsia, hyperemesis) — алгоритм даёт baseline IOM рекомендации. Юзер с диагнозом должна работать с врачом, banner упоминает это.
- **Многоплодная беременность** (twins/triplets) — kcal bonus +340/+452 рассчитан на singleton. Twins требует +600 в Q2-Q3 (NIH 2010), но это edge case (~1% беременностей). На этапе P0.6 не покрываем, banner предупреждает «расчёт для одной беременности».
- **Bariatric surgery patients** + pregnancy — требует RD supervision, baseline формула неприменима.
- **Adolescent pregnancy** (<18 + pregnant) — двойной P0 risk. Логика: age guard (force maintain) + pregnancy guard (force maintain + kcal bonus) — оба triggered, банер показывает оба + strong recommend medical.

---

## 8. Связанные концепты

- [[concepts/calc-user-targets-roadmap]] P0.6
- [[concepts/safety-guard-ux-pattern]] — UX pattern для banner / modal / auto-reset
- [[concepts/user-data-collection-pattern]] — retrofit cron HIGH priority pattern
- [[concepts/agent-collaboration-protocol]] Rules 1, 2, 7, 9, 10
- [[concepts/sassy-sage-multilingual-glossary]] — tone для maternal messaging (особенно `medical-careful` register vs full Sassy Sage)
