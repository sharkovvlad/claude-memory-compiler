# Deep Research Handoff — `calculate_user_targets` v5 audit

**Дата:** 2026-05-16
**Контекст:** prod-зеркало готово (Google Sheets digital twin verified 1:1 with prod via psycopg2 + Telegram bot UI on 2 live users). Перед расширением фич хочу независимый аудит научной обоснованности от ведущего клинического нутрициолога / спортивного физиолога. Ниже — промпт для deep-research агента + все исходные данные. Тебе нужно скопировать промпт + приложить этот файл целиком к новой сессии.

---

# 🎯 ПРОМПТ ДЛЯ DEEP RESEARCH АГЕНТА

> **Перед запуском:** этот документ содержит:
> 1. Полное тело SQL-функции `calculate_user_targets` v5 (prod, верифицировано 2026-05-16 через `pg_get_functiondef`)
> 2. Snapshot всех 30 `app_constants` ключей участвующих в формуле
> 3. 6 sentinel test cases с входами и выходами (4 синтетических + 2 живых юзера, верифицированы 1:1 с prod + Telegram UI)
> 4. KB-концепт с историей версий v3 → v4 → v5
> 5. Спецификации Phase 2 (Phenotype Quiz) и Phase 3 (Adaptive Modifiers)
> 6. Выдержка из Master Blueprint про nutrition safety
>
> Ничего у внешних агентов / БД запрашивать не нужно — всё в этом документе.

## Контекст продукта

NOMS — Telegram-бот трекинга питания для широкой аудитории (валидатор пускает с 13 лет). Гибрид:
- AI-распознавание еды (GPT-4o caskade: FatSecret → gpt-4o-mini → gpt-4o)
- Геймификация (XP / coins / mana / 8 лиг)
- 13 языков, character "Sassy Sage" (дерзкий мудрец без shame)
- Headless архитектура: все экраны в `ui_screens`, переводы в `ui_translations`, константы в `app_constants` (hot-reload)
- Safety: РПП Detection, Anti-Shaming, BMI Filter (блокировка weight-loss советов при underweight), Medical Disclaimer

**`calculate_user_targets`** — single SQL RPC, считающая дневные таргеты `(target_calories, target_protein_g, target_fat_g, target_carbs_g, target_weight_kg)` по профилю юзера. Это **ядро продукта** — то, ради чего юзер скачивает бота.

Эволюция:
- **v3 (mig 055, apr 2026):** базовая логика (Mifflin + PAL + phenotype LBM proxy + training_type матрица макрос)
- **v4 (mig 227, 15.05.2026):** PAL fusion (training_type как gate для bonus к PAL), conditional clamp по goal_type, `'none'` коэффициенты, telemetry-поля
- **v5 (mig 230, 16.05.2026):** gender-split carbs floor (women=100 г, men=50 г)

## Что от тебя нужно — DEEP REVIEW, 7 пунктов

Ты — ведущий клинический нутрициолог + спортивный физиолог + endocrinologist. Цель — найти всё что я мог упустить или сделать недостаточно safe/accurate. Фокус на peer-reviewed evidence (2010-2025), допускаются seminal works.

### 1. SCIENTIFIC SOUNDNESS блок-за-блоком

Пройдись по каждому из 8 шагов формулы (см. секцию A ниже) и проверь:
- Соответствует ли guidelines (NIH, ACSM, ISSN, EFSA, IOM, EAT-Lancet)?
- Где формула расходится с консенсусом? Где overly conservative / агрессивна?
- Какие коэффициенты выбраны эвристически и должны быть подкреплены / скорректированы?

**Конкретно интересует:**
- **PAL training bonus differentiation** (sedentary→+0.15, light→+0.10, moderate→+0.05, heavy→+0.00). Числа взяты «по здравому смыслу» — heavy PAL=1.725 уже включает intense training по Mifflin guidelines, sedentary 1.2 не учитывает тренировки совсем. Правильная градация? Где научный baseline?
- **fat_floor 0.8 г/кг target_weight**. У cardio-женщин 60-80 кг этот floor доминирует над `fat_pct=20%` (т.е. fact F = 0.8×70 = 56 г, а не 0.20×1726/9 = 38 г). **Намеренно?** Или это симптом неправильно подобранного `fat_pct_cardio`?
- **carbs_min 100 ж / 50 м**. Обосновано через 5'-deiodinase + reproductive axis (Loucks 2003, van der Walt 1986). Number 100 — sufficient или нужно >120 для активных юзериц на cut?
- **Phenotype LBM proxy** — `monw × 0.85`, `obese: height - 100/110 (Broca)`. Какие современные альтернативы (BIA-derived FFM, US Navy method, RFM Woolcott 2018)?

### 2. DANGEROUS EDGE CASES

Кто получит **опасный** результат? Опиши конкретный сценарий-профиль и что произойдёт:
- **Подростки 13-17 лет** (валидатор пускает) — Mifflin не валиден.
- **Беременные / лактирующие** — нет поля, BMR занижен на 300-500 ккал.
- **Пожилые >75** — Mifflin занижает RMR.
- **Истинно obese (BMI>35)** — Mifflin переоценивает RMR на 5-10% (Frankenfield 2013).
- **Endurance athletes** (марафонцы, велосипедисты) на cut — формула может недооценивать energy expenditure от длительных тренировок.
- **Vegan / vegetarian** — растительные белки biological value 70-80% (DIAAS), нужно ~25% больше. Сейчас не учитывается.
- **Underweight** (BMI<18.5) на самом деле — есть BMI filter (блокировка lose-целей), но формула этого не отражает.

### 3. ACCURACY IMPROVEMENTS

Что добавить чтобы повысить точность без over-engineering:
- **Katch-McArdle** вместо Mifflin когда есть LBM (а после Phase 2 quiz он будет)? Когда переходить?
- **TEF (Thermic Effect of Food)** compensation — стоит ли явно? Какой % калорий типично теряется на TEF при разных пропорциях макрос?
- **Adaptive thermogenesis** — при долгом дефиците RMR снижается на 5-15% (metabolic adaptation, Müller 2015). Стоит ли учесть и как?
- **Refeed cycles / diet breaks** — после 8-12 недель дефицита нужны 5-14 дней maintenance (Trexler 2014). Алгоритм пересмотра целей?
- **Body composition tracking** — корректировка целей по trend (-0.5 кг/неделю vs +0.2 кг/неделю)?

### 4. COMPARISON С INDUSTRY LEADERS

Как наша формула отличается от:
- **MyFitnessPal** (default macros 50C/30F/20P для всех — устарело)
- **Cronometer** (Mifflin + user-set activity, без training fusion)
- **MacroFactor** (adaptive based on weight trend, без явных coefficients)
- **Renaissance Periodization Diet Coach** (high protein 1g/lb, фазы дефицита)
- **Apple Health / Google Fit** calorie recommendations

Где мы лучше? Где хуже? Где у нас уникальное?

### 5. SAFETY HOLES

Какие safety guardrails ОБЯЗАТЕЛЬНЫ перед public scale? Приоритет P0 → P3:
- Age guards (`<18`, `>75`)
- Pregnancy / lactation flag
- BMI floor для weight-loss целей (есть, но не интегрирован в RPC)
- Activity sanity checks (heavy + cardio + lose+fast — extreme dangerous combo)
- Maximum deficit % (10kg/неделя — невозможно, как ловить?)
- Minimum kcal floor (≤1000-1200 ккал — under medical supervision only)

### 6. PHASE 3 ADAPTIVE MODIFIERS — еvaluate plan

Подробный план в секции F. Кратко:
- **Sleep < 6h** → +15% protein (Protein Leverage Hypothesis, Simpson & Raubenheimer), углеводы пропорционально снижаются, total kcal без изменений.
- **High stress** → +10-15% carbs (за счёт fat), Protein без изменений.
- **Luteal phase** → +150-200 kcal, fat +5-10% (прогестерон → enhanced lipid oxidation).

**Evidence-based или дилетантизм?** Конкретные исследования за/против. Какие корректировки нужны до apply?

### 7. IF YOU WERE BUILDING NOMS FROM SCRATCH

С теми же ограничениями (один Telegram-бот, один RPC, headless UI, 13 языков, audience 13+, no clinical supervision) — что бы ты сделал принципиально иначе?

---

## ФОРМАТ ВЫВОДА

Markdown отчёт, ≤4000 слов. Каждый critique с:
1. Описание проблемы (1-2 предложения)
2. Научная аргументация с конкретным цитированием (автор + год + где найти)
3. Предлагаемый fix (точная SQL-правка или ENV-константа или новый guard)

В конце — ranked list рекомендаций:
- **MUST-FIX before scaling** (safety-критично)
- **SHOULD-FIX in next 2-3 sprints** (accuracy)
- **NICE-TO-HAVE** (premium features / edge cases)

## ТОН

Критический, без вежливости. Если что-то идиотично — скажи прямо.
Если что-то OK — скажи коротко, не растягивай похвалы.
Длинная критика > длинные похвалы.

## ЧТО НЕ ДЕЛАТЬ

- Не пересказывай мне формулу обратно — я её знаю.
- Не предлагай radical replatform (вынести в Python, заменить SQL на ML-модель) — это вне scope.
- Не предлагай Phase 3 как «давайте добавим» — он уже в roadmap (см. секцию F), фокус на verify прав ли план.

---

# 📎 ИСТОЧНИКИ

## A. Полное тело SQL-функции v5 (verified 2026-05-16 через pg_get_functiondef)

```sql
CREATE OR REPLACE FUNCTION public.calculate_user_targets(p_telegram_id bigint, p_save_to_db boolean DEFAULT false)
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_user RECORD;
    v_age INTEGER;
    v_bmr NUMERIC;
    v_tdee NUMERIC;
    v_target INTEGER;
    v_gender_offset INTEGER;
    v_target_weight NUMERIC;
    v_protein INTEGER;
    v_fat INTEGER;
    v_carbs INTEGER;
    v_status TEXT;
    -- Constants from app_constants
    v_protein_g_per_kg NUMERIC;
    v_fat_pct NUMERIC;
    v_fat_min_g_per_kg NUMERIC;
    v_carbs_min INTEGER;
    v_deficit_pct NUMERIC;
    v_surplus_pct NUMERIC;
    v_monw_modifier NUMERIC;
    v_obese_offset INTEGER;
    v_protein_kcal INTEGER;
    v_fat_kcal INTEGER;
    v_fat_floor INTEGER;
    -- v4 additions: PAL fusion
    v_pal_base NUMERIC;
    v_pal_bonus NUMERIC;
    v_pal_adjusted NUMERIC;
    -- v4 additions: target rebalance
    v_requested_kcal INTEGER;
    v_actual_kcal INTEGER;
    v_floor_triggered_fat   BOOLEAN := FALSE;
    v_floor_triggered_carbs BOOLEAN := FALSE;
    v_effective_deficit_pct NUMERIC;
BEGIN
    -- ── 1. Load user ────────────────────────────────────────
    SELECT * INTO v_user FROM public.users WHERE telegram_id = p_telegram_id;
    IF v_user IS NULL THEN
        RETURN jsonb_build_object('success', false, 'error', 'USER_NOT_FOUND');
    END IF;

    IF v_user.weight_kg IS NULL OR v_user.height_cm IS NULL
       OR v_user.birth_date IS NULL OR v_user.gender IS NULL THEN
        RETURN jsonb_build_object('success', false, 'error', 'INCOMPLETE_DATA');
    END IF;

    -- ── 2. Age ──────────────────────────────────────────────
    v_age := DATE_PART('year', AGE(v_user.birth_date));

    -- ── 3. LBM Proxy (target_weight) ────────────────────────
    v_monw_modifier := COALESCE(
        (SELECT value::NUMERIC FROM public.app_constants WHERE key = 'phenotype_monw_modifier'),
        0.85
    );

    CASE COALESCE(v_user.phenotype, 'default')
        WHEN 'monw' THEN
            v_target_weight := v_user.weight_kg * v_monw_modifier;
        WHEN 'obese' THEN
            IF LOWER(TRIM(v_user.gender)) IN ('male', 'm') THEN
                v_obese_offset := COALESCE(
                    (SELECT value::INT FROM public.app_constants WHERE key = 'phenotype_obese_offset_male'), 100);
            ELSE
                v_obese_offset := COALESCE(
                    (SELECT value::INT FROM public.app_constants WHERE key = 'phenotype_obese_offset_female'), 110);
            END IF;
            v_target_weight := GREATEST(v_user.height_cm - v_obese_offset, 40);
        ELSE -- 'default', 'athlete'
            v_target_weight := v_user.weight_kg;
    END CASE;

    -- ── 4. BMR (Mifflin-St Jeor) ────────────────────────────
    CASE LOWER(TRIM(v_user.gender))
        WHEN 'male' THEN v_gender_offset := 5;
        WHEN 'm'    THEN v_gender_offset := 5;
        ELSE             v_gender_offset := -161;
    END CASE;

    v_bmr := (10 * v_user.weight_kg) + (6.25 * v_user.height_cm) - (5 * v_age) + v_gender_offset;

    -- ── 5. PAL fusion: NEAT (activity_level) + training bonus ───
    -- v4 fix: ранее decoupled training_type теперь поднимает TDEE.
    -- Bonus дифференцирован по activity_level → защита от double-count
    -- (heavy уже включает intense training в стандарте Mifflin).
    -- Только active training types получают bonus; 'none', 'sedentary', NULL → 0.
    v_pal_base := COALESCE(v_user.pal_coefficient, 1.2);

    IF COALESCE(v_user.training_type, 'mixed') IN ('strength', 'cardio', 'mixed') THEN
        v_pal_bonus := COALESCE(
            (SELECT value::NUMERIC FROM public.app_constants
             WHERE key = 'pal_training_bonus_' || COALESCE(v_user.activity_level, 'sedentary')),
            0
        );
    ELSE
        v_pal_bonus := 0;
    END IF;

    -- Clamp 1.8 — защита от patological значений
    -- (например edge case heavy + кастомные bonus константы).
    v_pal_adjusted := LEAST(v_pal_base + v_pal_bonus, 1.8::NUMERIC);

    v_tdee := v_bmr * v_pal_adjusted;

    -- ── 6. Goal adjustment (goal_type + goal_speed) ─────────
    -- v4: пишем в v_requested_kcal вместо v_target.
    -- Финальный v_target будет посчитан в Step 8 после floor'ов.
    CASE v_user.goal_type
        WHEN 'lose' THEN
            v_deficit_pct := COALESCE(
                (SELECT value::NUMERIC FROM public.app_constants
                 WHERE key = 'goal_speed_' || COALESCE(v_user.goal_speed, 'normal') || '_deficit'),
                15
            );
            v_requested_kcal := ROUND(v_tdee * (1 - v_deficit_pct / 100));
            v_status := 'deficit';
        WHEN 'gain' THEN
            v_surplus_pct := COALESCE(
                (SELECT value::NUMERIC FROM public.app_constants
                 WHERE key = 'goal_speed_' || COALESCE(v_user.goal_speed, 'normal') || '_surplus'),
                10
            );
            v_requested_kcal := ROUND(v_tdee * (1 + v_surplus_pct / 100));
            v_status := 'surplus';
        ELSE
            v_requested_kcal := ROUND(v_tdee);
            v_status := 'maintain';
    END CASE;

    -- ── 7. Macros (by training_type, on target_weight) ──────

    -- Protein: g/kg × target_weight
    -- Для training_type='none' читается protein_g_per_kg_none=1.2 (mig 217 вставил).
    v_protein_g_per_kg := COALESCE(
        (SELECT value::NUMERIC FROM public.app_constants
         WHERE key = 'protein_g_per_kg_' || COALESCE(v_user.training_type, 'mixed')),
        1.6
    );
    v_protein := ROUND(v_protein_g_per_kg * v_target_weight);

    -- Fat: % of requested kcal → grams, with floor
    -- Для training_type='none' читается fat_pct_none=30 (mig 217 вставил).
    v_fat_pct := COALESCE(
        (SELECT value::NUMERIC FROM public.app_constants
         WHERE key = 'fat_pct_' || COALESCE(v_user.training_type, 'mixed')),
        25
    );
    v_fat_min_g_per_kg := COALESCE(
        (SELECT value::NUMERIC FROM public.app_constants WHERE key = 'fat_min_g_per_kg'),
        0.8
    );
    v_fat := ROUND((v_requested_kcal * v_fat_pct / 100) / 9);
    v_fat_floor := ROUND(v_fat_min_g_per_kg * v_target_weight);
    IF v_fat < v_fat_floor THEN
        v_fat := v_fat_floor;
        v_floor_triggered_fat := TRUE;
    END IF;

    -- Carbs: остаток, с floor
    -- v5 (mig 230): gender-split — carbs_min_g_<gender> с двухуровневым
    -- fallback (carbs_min_g → 50). Female=100 защищает thyroid/reproductive
    -- axis у активных юзериц на cut. Male=50 unchanged.
    v_carbs_min := COALESCE(
        (SELECT value::INT FROM public.app_constants
         WHERE key = 'carbs_min_g_' || LOWER(TRIM(COALESCE(v_user.gender, 'male')))),
        (SELECT value::INT FROM public.app_constants WHERE key = 'carbs_min_g'),
        50
    );
    v_protein_kcal := v_protein * 4;
    v_fat_kcal     := v_fat * 9;
    v_carbs := ROUND(GREATEST(v_requested_kcal - v_protein_kcal - v_fat_kcal, 0)::NUMERIC / 4);
    IF v_carbs < v_carbs_min THEN
        v_carbs := v_carbs_min;
        v_floor_triggered_carbs := TRUE;
    END IF;

    -- ── 8. Target rebalance (v4) ────────────────────────────
    -- Сумма БЖУ может ≠ v_requested_kcal из-за floor'ов или округления.
    -- Логика по goal_type:
    --   • lose: LEAST(actual, ROUND(tdee)) — защита от «дефицит превратился
    --     в профицит» при экстремальных floor-комбинациях. Если floor не
    --     сработал → actual ≈ requested (расхождение 1-3 ккал от ROUND).
    --   • gain: target := actual безусловно — gain намеренно хочет target > TDEE,
    --     clamp сломал бы набор массы.
    --   • maintain: target := actual — floor-погрешность ±50 ккал допустима
    --     в обе стороны от TDEE.
    v_actual_kcal := v_protein * 4 + v_fat * 9 + v_carbs * 4;

    IF v_user.goal_type = 'lose' THEN
        v_target := LEAST(v_actual_kcal, ROUND(v_tdee)::INTEGER);
    ELSE
        v_target := v_actual_kcal;
    END IF;

    -- Effective deficit/surplus AFTER floor adjustments (telemetry для UI).
    -- Положительное значение = реальный дефицит, отрицательное = профицит.
    v_effective_deficit_pct := CASE
        WHEN v_tdee > 0 THEN ROUND(((v_tdee - v_target) / v_tdee * 100)::NUMERIC, 1)
        ELSE 0
    END;

    -- ── 9. Save to DB ───────────────────────────────────────
    IF p_save_to_db THEN
        UPDATE public.users SET
            target_calories  = v_target,
            target_protein_g = v_protein,
            target_fat_g     = v_fat,
            target_carbs_g   = v_carbs,
            target_weight_kg = v_target_weight,
            updated_at       = NOW()
        WHERE telegram_id = p_telegram_id;
    END IF;

    -- ── 10. Return ──────────────────────────────────────────
    -- v4 поля сидят в существующем calculations-объекте → callers,
    -- читающие только success, не задеты. Старые v3 ключи preserved.
    RETURN jsonb_build_object(
        'success', true,
        'telegram_id', p_telegram_id,
        'user_data', jsonb_build_object(
            'gender', v_user.gender,
            'age', v_age,
            'weight', v_user.weight_kg,
            'height', v_user.height_cm,
            'pal', v_user.pal_coefficient,
            'training_type', COALESCE(v_user.training_type, 'mixed'),
            'phenotype', COALESCE(v_user.phenotype, 'default'),
            'goal_speed', COALESCE(v_user.goal_speed, 'normal')
        ),
        'calculations', jsonb_build_object(
            -- v3 (preserved 1:1)
            'bmr', v_bmr,
            'tdee', v_tdee,
            'gender_offset', v_gender_offset,
            'target_calories', v_target,
            'target_weight', v_target_weight,
            'deficit_or_surplus_pct', COALESCE(v_deficit_pct, v_surplus_pct, 0),
            -- v4 additions
            'pal_base', v_pal_base,
            'pal_adjusted', v_pal_adjusted,
            'requested_kcal', v_requested_kcal,
            'actual_kcal', v_actual_kcal,
            'floor_triggered_fat', v_floor_triggered_fat,
            'floor_triggered_carbs', v_floor_triggered_carbs,
            'effective_deficit_pct', v_effective_deficit_pct
        ),
        'macros', jsonb_build_object(
            'protein_g', v_protein,
            'fat_g', v_fat,
            'carbs_g', v_carbs,
            'protein_g_per_kg', v_protein_g_per_kg,
            'fat_pct', v_fat_pct
        )
    );
END;
$function$
```

## B. Snapshot `app_constants` (все 30 ключей участвующих в формуле)

| key | value | description |
|---|---|---|
| pal_sedentary | 1.2 | PAL: Сидячий образ жизни |
| pal_light | 1.375 | PAL: Лёгкая активность |
| pal_moderate | 1.55 | PAL: Умеренная активность |
| pal_heavy | 1.725 | PAL: Тяжёлая активность |
| pal_training_bonus_sedentary | 0.15 | Bonus к PAL если training_type ∈ {strength,cardio,mixed} |
| pal_training_bonus_light | 0.10 | (same) |
| pal_training_bonus_moderate | 0.05 | (same; smaller — moderate уже включает тренировки) |
| pal_training_bonus_heavy | 0.00 | (heavy уже включает intense training в Mifflin standard) |
| protein_g_per_kg_strength | 2.0 | на target_weight |
| protein_g_per_kg_cardio | 1.4 | на target_weight |
| protein_g_per_kg_mixed | 1.6 | на target_weight |
| protein_g_per_kg_sedentary | 1.2 | на target_weight |
| protein_g_per_kg_none | 1.2 | для тех кто выбрал "не тренируюсь" |
| fat_pct_strength | 25 | % от target_kcal |
| fat_pct_cardio | 20 | % от target_kcal |
| fat_pct_mixed | 25 | % от target_kcal |
| fat_pct_sedentary | 30 | % от target_kcal |
| fat_pct_none | 30 | % от target_kcal |
| fat_min_g_per_kg | 0.8 | floor на target_weight (применяется MAX) |
| carbs_min_g | 50 | legacy fallback (используется только если gender NULL) |
| carbs_min_g_female | 100 | mig 230 — thyroid/reproductive axis safety |
| carbs_min_g_male | 50 | mig 230 — unchanged |
| phenotype_monw_modifier | 0.85 | target_weight = actual_weight × this |
| phenotype_obese_offset_male | 100 | target_weight = MAX(height - this, 40) |
| phenotype_obese_offset_female | 110 | target_weight = MAX(height - this, 40) |
| goal_speed_slow_deficit | 10 | % от TDEE для lose+slow |
| goal_speed_normal_deficit | 15 | % от TDEE для lose+normal |
| goal_speed_fast_deficit | 20 | % от TDEE для lose+fast |
| goal_speed_slow_surplus | 8 | % от TDEE для gain+slow |
| goal_speed_normal_surplus | 10 | % от TDEE для gain+normal |
| goal_speed_fast_surplus | 15 | % от TDEE для gain+fast |

## C. Sentinel test cases (verified 1:1 с prod + Telegram UI)

**Все цифры получены через `SELECT calculate_user_targets(tg, false)` на проде после mig 230, 2026-05-16. 2 живых юзера дополнительно подтверждены через `@nomsaibot` Profile screen.**

### Синтетические (4)

| # | Профиль (gender/age/h/w/activity/training/goal/speed/phenotype) | target_cal | P_g | F_g | C_g | floor_F | floor_C | BMR | TDEE | PAL_adj |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | F/30/165/70/sedentary/cardio/lose/slow/default | 1728 | 98 | 56 | 208 | TRUE | FALSE | 1420.25 | 1917.34 | 1.35 |
| 2 | M/25/180/75/moderate/strength/gain/normal/monw | 3090 | 128 | 86 | 451 | FALSE | FALSE | 1755.00 | 2808.00 | 1.60 |
| 3 | F/40/165/100/light/mixed/lose/fast/obese | 1971 | 88 | 55 | 281 | FALSE | FALSE | 1670.25 | 2463.62 | 1.475 |
| 4 | M/30/175/70/sedentary/strength/lose/normal/default | 1892 | 140 | 56 | 207 | TRUE | FALSE | 1648.75 | 2225.81 | 1.35 |

### Живые юзеры (2, prod-confirmed)

| tg | name | gender | age | h | w | activity | training | goal | speed | pheno | target_cal | P_g | F_g | C_g | tgt_w |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 417002669 | Vladislav (admin) | male | 42 | 194 | 98 | light | cardio | lose | slow | default | 2638 | 137 | 78 | 347 | 98 |
| 786301802 | Владислав | male | 30 | 190 | 90 | moderate | mixed | maintain | null | default | 3110 | 144 | 86 | 440 | 90 |

417002669: bmr=1987.5, tdee=2931.56, pal_adj=1.475 (light 1.375 + cardio bonus 0.10), floor_F=TRUE.
786301802: bmr=1942.5, tdee=3108.0, pal_adj=1.60 (moderate 1.55 + mixed bonus 0.05), goal=maintain → target=ROUND(tdee), floors=FALSE.

`users.target_*` колонки совпадают 1:1 с live `calculate_user_targets(_, false)` для обоих → backfill чисто отработал, persistence синхронна.

**Telegram UI confirmation:** оба видят те же цифры в Profile → Мой план (P137/F78/C347 для Vladislav, P144/F86/C440 для Владислав).

## D. KB концепт — `personalized-macro-split` (история v3 → v4 → v5)

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

---

## E. Phase 2 Spec — Phenotype Quiz (backend готов, UI заглушка)

# Spec: Phenotype Quiz (Phase 2)

## Overview
4 text-based heuristic questions to classify user body composition phenotype without hardware diagnostics. Results in LBM Proxy (adjusted target weight) for more accurate macro calculation.

## Source Document
`Разработка алгоритмов питания для Telegram-бота.md` — Section 1.2-1.3

## Phenotype Types
| Phenotype | Description | LBM Proxy |
|-----------|-------------|-----------|
| **MONW** (Skinny Fat) | Normal BMI but high body fat, low muscle | weight x 0.85 |
| **Athlete** | High muscle mass, low fat | weight x 1.0 |
| **Obese** | True abdominal obesity, BMI > 27 | height - 100/110 (Broca) |
| **Default** (Normosthenic) | Everything else | weight x 1.0 |

## 4 Questions (onboarding — optional, skippable)

### Q1: Fat Distribution Pattern (Visceral Marker)
**Key:** `phenotype_q1`
**Prompt:** "If you put on a tight t-shirt your size, where does it fit tightest?"
- A) Shoulders and chest → `q1=a` (developed upper body, low abdominal fat)
- B) Evenly everywhere → `q1=b` (proportional distribution)
- C) Around belly/waist → `q1=c` (central/visceral fat deposit)

### Q2: Strength Training Experience
**Key:** `phenotype_q2`
**Prompt:** "How would you describe your strength training experience in the last year?"
- A) No training or only light cardio/yoga → `q2=a` (no hypertrophy stimulus)
- B) Irregular training (1-2x/week, frequent breaks) → `q2=b`
- C) Consistent 3+ times/week with progressive overload → `q2=c` (developed muscle mass)

### Q3: Tissue Density (MONW Validator)
**Key:** `phenotype_q3`
**Prompt:** "If you feel your arms and legs in a fully relaxed state, how do they feel?"
- A) Soft, muscles barely detectable under skin → `q3=a` (sarcopenia marker)
- B) Normal, both fat and muscle tone present → `q3=b`
- C) Dense, firm, muscle bellies clearly defined → `q3=c` (high LBM density)

### Q4: Weight History (Metabolic Flexibility)
**Key:** `phenotype_q4`
**Prompt:** "How has your weight changed over the past 3-5 years?"
- A) Yo-yo: lose and regain 5-10 kg cycles → `q4=a` (damaged basal metabolism)
- B) Relatively stable, within 1-2 kg → `q4=b`
- C) Gradually and intentionally increasing → `q4=c` (muscle building period if q2=c)

## Classification Matrix (SQL)
```sql
CASE
  WHEN q1='c' AND q2 IN ('a','b') AND q3='a' THEN 'monw'
  WHEN q1='a' AND q2='c' AND q3='c' THEN 'athlete'
  WHEN q1='c' AND q2='a' AND q3='a'
       AND (weight_kg / (height_cm/100.0)^2) > 27 THEN 'obese'
  ELSE 'default'
END
```

## UX Flow

### During Onboarding (after goal step)
1. Offer: "Want to fine-tune your nutrition? 4 quick questions — I'll understand your metabolism better."
2. Buttons: [Start Quiz] [Skip]
3. If skip → phenotype = 'default', proceed to registered
4. If start → 4 questions sequentially, then classification + explanation

### In Profile (after registration)
Button "Body Type" → retake quiz or view current phenotype
When answers change → recalculate phenotype → recalculate all macro targets

## Storage
- `users.phenotype_answers JSONB` — `{"q1":"a","q2":"b","q3":"c","q4":"b"}`
- `users.phenotype TEXT` — computed from answers
- `users.target_weight_kg NUMERIC` — computed from phenotype + weight

## Translation Requirements
- 4 questions x 13 languages = 52 strings
- 3 answers per question x 13 = 156 strings
- Intro + skip + back + result explanations = ~40 strings
- **Total: ~248 translation strings**
- Tone: Sassy Sage — casual, non-judgmental, curious

## Translation Keys (ui_translations)
```
phenotype.quiz_intro
phenotype.quiz_skip
phenotype.q1_prompt / phenotype.q1_a / phenotype.q1_b / phenotype.q1_c
phenotype.q2_prompt / phenotype.q2_a / phenotype.q2_b / phenotype.q2_c
phenotype.q3_prompt / phenotype.q3_a / phenotype.q3_b / phenotype.q3_c
phenotype.q4_prompt / phenotype.q4_a / phenotype.q4_b / phenotype.q4_c
phenotype.result_monw / phenotype.result_athlete / phenotype.result_obese / phenotype.result_default
phenotype.result_explanation (general)
```

## Dependencies
- Migration 055 (columns already added: phenotype, phenotype_answers, target_weight_kg)
- `calculate_user_targets` v3 already handles phenotype-based LBM Proxy
- Only need: classification RPC, n8n quiz flow, translations

---

## F. Phase 3 Spec — Adaptive Modifiers (план, не реализовано)

# Spec: Adaptive Macro Modifiers (Phase 3 — Future)

## Overview
Dynamic macro adjustment based on physiological triggers: sleep deprivation, psychological stress, menstrual cycle (luteal phase). These modify the daily macro targets temporarily.

## Source Document
`Разработка алгоритмов питания для Telegram-бота.md` — Section 4

---

## Modifier 1: Sleep Deprivation (< 6 hours)

### Clinical Basis
- Sleep loss → ghrelin surge (hunger hormone) + leptin drop (satiety)
- Prefrontal cortex inhibition → craving for high-calorie comfort food
- **Protein Leverage Hypothesis** (Simpson & Raubenheimer): body keeps seeking food until protein quota is met → overeating if protein is low

### Algorithmic Adjustment
- **Trigger:** User reports < 6h sleep (morning check-in or text analysis)
- **Protein:** +15% above normal target (or minimum 1.8-2.0 g/kg)
- **Carbs:** Proportionally reduced to maintain same total calories
- **Total calories:** Unchanged (no increase)
- **Advice:** High-protein breakfast, foods rich in tryptophan (turkey, dairy, eggs), magnesium (nuts, greens)

### Data Collection Required
- Morning check-in: "How did you sleep?" → short/okay/great
- Or text analysis: detect sleep-related complaints
- New column: `users.sleep_quality TEXT` (daily, auto-reset)

---

## Modifier 2: High Psychological Stress

### Clinical Basis
- Chronic stress → HPA axis → cortisol hypersecretion
- Cortisol → gluconeogenesis + insulin resistance → visceral fat deposit
- Restricting carbs during stress WORSENS cortisol → clinical error
- Moderate carbs → serotonin synthesis → cortisol suppression

### Algorithmic Adjustment
- **Trigger:** User reports stress (text analysis: "stressed", "exhausted", "want to eat everything")
- **Carbs:** +10-15% (taken from fat allocation)
- **Protein:** Unchanged (maintain muscle protection)
- **Focus:** Complex carbs (whole grains), Omega-3 (fatty fish, walnuts)
- **Advice:** Anti-inflammatory diet, NO caloric restriction

### Data Collection Required
- Sentiment analysis of food log messages
- Optional stress check-in
- New column: `users.stress_level TEXT` (none/moderate/high)

---

## Modifier 3: Luteal Phase (Menstrual Cycle)

### Clinical Basis
- Luteal phase (ovulation → period start): progesterone dominance
- Basal metabolic rate increases 5-10% (+100-300 kcal/day)
- Transient insulin resistance
- Enhanced lipid oxidation (fat-burning mode)
- Strong cravings for energy-dense food (sugar + fat combo)

### Algorithmic Adjustment
- **Trigger:** Calendar-based (7-10 days before cycle start)
- **Total calories:** +150-200 kcal
- **Fat:** Slight increase (+5-10% of kcal) — body uses fat efficiently
- **Carbs:** Remainder of extra calories → complex carbs for serotonin
- **Advice:** Destigmatize appetite increase, magnesium + iron-rich foods

### Data Collection Required
- Menstrual cycle tracker (optional, female users only)
- New columns: `users.cycle_length INT`, `users.last_period_start DATE`
- Privacy-sensitive — must be opt-in with clear explanation

---

## Implementation Architecture (Future)

### New Table: `daily_modifiers`
```sql
CREATE TABLE daily_modifiers (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT REFERENCES users(telegram_id),
    date DATE NOT NULL,
    modifier_type TEXT NOT NULL, -- 'sleep', 'stress', 'luteal'
    calories_delta INT DEFAULT 0,
    protein_delta_pct INT DEFAULT 0,
    fat_delta_pct INT DEFAULT 0,
    carbs_delta_pct INT DEFAULT 0,
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Modified get_day_summary
Return `adjusted_targets` alongside base targets:
```json
{
  "target_protein_g": 160,
  "target_fat_g": 69,
  "target_carbs_g": 310,
  "adjusted_protein_g": 184,   // +15% (sleep modifier)
  "adjusted_carbs_g": 286,     // reduced to compensate
  "active_modifiers": ["sleep_deprivation"]
}
```

### AI Tips (Sassy Sage ToV)
Each modifier triggers contextual micro-tips following the "Sandwich Rule" (10-12 lines):
1. Empathy + sass (hook)
2. Clinical core (why this is happening)
3. Algorithmic micro-action (what to do)

Example templates are in the source document, Section 5.

---

## Priority
- P3 (future sprint, after Phase 1 + Phase 2)
- Requires: data collection UX, sentiment analysis, cycle tracker
- Estimated scope: 2-3 migration files, n8n check-in workflow, translations

---

## G. Выдержка из Master Blueprint про nutrition safety

> «Концептуальная идентичность бота (архетип *The Sassy Sage* или «Дерзкий Мудрец») поддерживается динамической локализацией на 13 языков через таблицу `ui_translations`. Ироничный тон бота дополняется строгими фильтрами безопасности (Health Safety). **Мониторинг расстройств пищевого поведения (РПП)** и **фильтрация по индексу массы тела (BMI)** интегрированы в ИИ-слой: при обнаружении экстремального дефицита калорий алгоритмы активируют **«парадоксальную интервенцию»**, рекомендуя отдых, а при критически низком весе система блокирует любые советы, направленные на похудение, перенаправляя пользователя к медицинским специалистам.»

> «Логика установки целей (`set_user_goal`, `set_user_goal_speed`, `calculate_user_targets`) учитывает множество фенотипических параметров (модификатор "monw" 0.85, смещения для случаев ожирения и различные уровни PAL — от 1.2 до 1.725) для точного расчета базального метаболизма. Процедуры `sync_user_weight` и `sync_weight_from_metrics` гарантируют, что изменение веса в одной части системы автоматически каскадируется во все аналитические сводки.»

> «Инновация самообучающегося нутрициолога заключается в способности ИИ анализировать не только калорийность, но и фактический биологический отклик конкретного пользователя. Таблица `daily_metrics` служит хранилищем "биологической истины" (ground truth), фиксируя массив `symptoms` (например, "headache", "fatigue"), `energy_level` (шкала 1-10) и `sleep_hours`. Алгоритм Reward Model (модели вознаграждения) будет анализировать корреляцию между `health_score` потребляемой пищи и последующими значениями в `daily_metrics`. Если после регулярного потребления продуктов, которые ИИ считает «полезными» (например, высокий health_score), пользователь систематически логирует падение `energy_level` или появление симптомов усталости, модель пенализирует рекомендации этих продуктов для данного конкретного фенотипа.»

**Что важно для аудита:**
- BMI filter существует на UI-слое (блокировка weight-loss целей при underweight), но **не интегрирован** в `calculate_user_targets` напрямую.
- `daily_metrics` (symptoms, energy_level, sleep_hours) уже существует в схеме, но **формула расчёта таргетов её не использует** — это материал для Phase 3 adaptive modifiers.
- Парадоксальная интервенция при extreme deficit (<600 ккал/день) — на уровне AI-промптов, не в SQL формуле.

---

## Технический контекст

- БД: Supabase PostgreSQL EU pooler, RTT 44ms baseline
- p95 latency `calculate_user_targets`: 43 ms (verified 2026-05-16, 25 runs persistent psycopg2 с VPS)
- Все константы — hot-reload через `app_constants_cache` trigger (AFTER INSERT/UPDATE/DELETE)
- Функция вызывается из `set_user_*` RPC цепочки при онбординге и Profile-edit
- p_save_to_db=TRUE → пишет в `users.target_*` колонки
- Callers (mig 063/085/091/094) парсят только `success` field из JSON return → структурные доб change безопасны

---

**Конец handoff'а.** Жду критический разбор согласно 7 пунктам выше.
