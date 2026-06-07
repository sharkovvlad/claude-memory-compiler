---
title: "Energy Availability (EA / RED-S) — Design Decision: defer to P2"
aliases: [ea-decision, red-s-decision, energy-availability-design]
tags: [nutrition, safety, calculate-user-targets, p2, red-s, energy-availability]
sources:
  - "Loucks AB. Energy balance and body composition in sports and exercise. J Sports Sci 2004"
  - "Mountjoy M et al. IOC consensus statement: RED-S Update. Br J Sports Med 2018"
  - "Areta JL et al. Low energy availability. Eur J Sport Sci 2021"
  - "concepts/calc-user-targets-roadmap.md (P2.5b)"
  - "Session 2026-05-18 nutritionist owner triage"
created: 2026-05-18
updated: 2026-06-07
---

# Energy Availability — Design Decision

**TL;DR:** EA защита **отложена до P2** (после P2.1 waist quiz + P2.5a workout tracking). EA-lite (без exercise tracking) даёт **false negatives на активных юзерах** — ключевой demographic, который мы должны защитить. Делать «pretending to protect» хуже, чем явно не закрывать guard.

---

## 1. Что такое Energy Availability

**EA = (target_kcal − exercise_kcal) / LBM_kg**

Единица: ккал на кг fat-free mass в день. Это «оставшиеся калории после тренировки» — то, что тело реально получает на основные функции (BMR, репродукция, иммунитет, костный обмен).

Пороги (Loucks 2004, IOC RED-S 2018):

| EA (kcal/kg LBM/day) | Состояние |
|---|---|
| ≥ 45 | Optimal — для adaptation/recovery |
| 30 – 45 | Reduced — функция сохранена, но adaptation impaired |
| < 30 | **LEA (Low EA)** — гипоталамо-гипофизарное подавление, аменорея, костная потеря, иммунодепрессия. **RED-S триггер.** |

## 2. Почему это критичная safety-фича

LEA — это **не вес и не дефицит**, это **относительный дефицит энергии для активного организма**. Юзер может:

- Иметь BMI 22 (норма)
- Видеть в боте `target_kcal = 1800` (выше medical floor 1200)
- Не triggered ни одним из текущих guards (age, BMI, min_kcal)
- **И при этом** жечь 700 ккал/день в тренировках, иметь EA = (1800 − 700) / 50 = 22 → **серьёзная LEA с долгосрочными последствиями: аменорея, остеопороз, RED-S**

В нашем демографическом сегменте «motivated weight-loss user» риск **выше базы**, потому что:
1. Установка «больше тренировки = быстрее результат»
2. Установка «strict deficit + cardio» (подкреплено fitness-инфлюенсерами)
3. Невидимость для bot'а: тренировки происходят вне его контекста

## 3. Почему EA-lite (без exercise tracking) — плохая идея

**EA-lite:** аппроксимировать exercise_kcal через `PAL_coefficient × BMR − BMR` (т.е. «фактический PAL минус sedentary baseline»). LBM_proxy брать из phenotype quiz (Phase 2).

### Проблема 1 — false negatives на active demographic

Юзер с PAL='active' (1.725) и тренировками 5×/нед → PAL уже учитывает amortized exercise. `target_kcal` уже включает TDEE, который **уже** учитывает тренировки в среднем. Считать «exercise_kcal = PAL_excess» = вычитать то, что уже было прибавлено. Получим EA = target/LBM, что для нормального cut = 30-35 — **на границе, но не triggers**. А реальный паттерн «strict deficit + intense cardio days» — exactly те юзеры, которым нужна защита — пройдут под радаром.

Численный пример:
- F/25/55kg/PAL=active/lose+fast → target_kcal = 1450, LBM_proxy ≈ 42 кг
- EA-lite = 1450 / 42 = **34.5** → выше threshold 30, no warning
- Реальный паттерн: 3 strength + 2 cardio (60 мин) → exercise_burn ≈ 600 ккал/день. Реальная EA = (1450 − 600) / 42 = **20.2** → critical LEA.
- **Наш guard молчит, юзер думает что мы заботимся, аменорея через 3-6 месяцев.**

### Проблема 2 — false positives на sedentary с низким PAL

Sedentary юзер (PAL=1.2) с тяжелым cut → EA-lite вычитает «exercise = 0», EA ≈ target/LBM. У миниатюрной женщины (LBM=35) и target=1200 (medical floor) EA = **34.3**. Borderline. Если floor 1100 (что бывает у F/45/150/45) → EA = 31.4. Trigger? Не должен — она не активна. Но guard сработает.

### Проблема 3 — LBM proxy ненадёжен без waist

Текущий phenotype quiz даёт LBM proxy для `monw`/`obese` от `weight × 0.85` или `target_weight × 0.85`. Это груба для среднего, **но ужасно** для:
- Spo­rty mesomorph женщины (реальный LBM = 0.78-0.82 × weight) — мы дадим завышенный LBM proxy → EA выглядит выше реальной → false negative
- Sarcopenic 70-летней (LBM = 0.55-0.60 × weight) — мы дадим заниженный proxy

Корректный LBM нужен через RFM (Woolcott 2018) с waist circumference — это P2.1.

### Вывод

EA-lite **систематически underprotects exactly the demographic, который нужен — активные молодые женщины на cut**. Это хуже чем отсутствие guard'а — даёт ложное чувство безопасности и владельцу проекта (думает «у нас есть RED-S защита»), и юзеру (получает blank screen там, где должен быть warning).

## 4. Что нужно для полноценного EA guard (P2 dependencies)

### P2.1 — Waist circumference quiz extension

- Добавить Q5 в Phenotype Phase 2 quiz: «Окружность талии (см)»
- Skippable (legacy users → fallback на текущий proxy)
- → Расчёт LBM через RFM: `RFM = 64 − (20 × height/waist) + (12 × sex)`
- Pattern: [[concepts/user-data-collection-pattern]] retrofit HIGH priority

### P2.5a — Workout tracking infrastructure

Один из трёх путей (выбор владельца):

| Path | Pros | Cons |
|---|---|---|
| **Apple HealthKit / Google Fit deep link** | Реальные данные, exact kcal, automation | iOS only initial (HK), Android fragmentation (GF or Samsung Health or Garmin), Telegram-bot deep link → mobile app → permissions flow требует UX |
| **Strava OAuth** | API стандарт, kcal estimates, активная audience overlap | Требует Strava Premium для some metrics? Cardio-skewed (less strength) |
| **Manual log в боте** | Zero external deps, дешевле, control | UX friction (юзер должен помнить логать), точность сомнительна (юзер указывает «бегал 30 мин» — мы считаем MET × time = imperfect) |

Рекомендация (для будущего решения): начать с **manual log** как fastest-to-ship, добавить HealthKit deep link во вторую очередь, Strava как nice-to-have. Manual log хотя бы создаёт telemetry для калибровки.

### P2.5b — EA calculation + guard

После P2.1 + P2.5a:

```sql
-- В calculate_user_targets, после Step 8 (target rebalance):
-- ── 8d. Energy Availability check (P2.5b) ──────────────────────────
v_lbm_kg := compute_lbm_from_rfm(v_user.height_cm, v_phenotype_q5_waist_cm, v_user.gender);
v_exercise_kcal := COALESCE(
    (SELECT AVG(daily_burn_kcal) FROM workout_summary_view
     WHERE telegram_id = p_telegram_id AND date >= CURRENT_DATE - INTERVAL '7 days'),
    0
);
v_ea := (v_target - v_exercise_kcal) / NULLIF(v_lbm_kg, 0);

IF v_ea < 30 AND v_lbm_kg > 0 AND v_exercise_kcal > 0 THEN
    -- Soft override: raise target до v_lbm_kg × 30 + v_exercise_kcal
    v_required_kcal_for_safe_ea := (v_lbm_kg * 30) + v_exercise_kcal;
    v_target := GREATEST(v_target, ROUND(v_required_kcal_for_safe_ea)::INTEGER);
    v_ea_warning := 'low_energy_availability_red_s_risk';
END IF;
```

Severity = **soft override** (per [[concepts/safety-guard-ux-pattern]] §3): пользователь может opt-out при наличии medical confirmation (спортсмен на cut под надзором тренера/RD).

## 5. Что закрывает текущий v7 baseline без EA

Mig 246 v7 закрывает три из четырёх path'ов к опасному дефициту:

| Path | Closed by |
|---|---|
| Hard medical floor (юзер хочет 800 ккал) | min_kcal_warning (medical_floor_1200/1500) |
| BMI < 14 catastrophic | extreme_cachexia force maintain |
| BMI < 18.5 + lose | underweight_lose_override force maintain |
| Pregnancy/lactation deficit | P0.6 (in flight) |
| **LEA на normal BMI + active phenotype** | **НЕ закрыто** ⚠️ |

Это известная open gap. Mitigation в текущем стеке:
- Profile banner / educational content про RED-S
- В `app_constants` пометить informational disclaimer для F с goal=lose
- НЕ давать ложного гарда

## 6. Когда пересмотреть

Триггеры разморозки:

- (a) Audit показывает рост cohort F/15-35 с goal=lose+fast (signal of risk demographic)
- (b) User report «у меня пропали месячные» (тяжёлый сигнал, escalate immediately)
- (c) P2.1 + P2.5a выполнены (зависимости готовы)
- (d) FTC/California laws эволюционируют в сторону mandated RED-S screening

Owner на 2026-05-18 принял решение **отложить до P2** на основании анализа выше. Decision rationale зафиксирован для следующих сессий — не пересматривать без новых evidence.

## 6a. Re-triage 2026-06-07 + interim educational disclaimer (mig 484, PR #359)

Owner **подтвердил defer-to-P2** на свежих live-данных. Снимок аудитории (`is_bot=false`):
14 живых юзеров; 6 женщин; goal `lose`=3, `maintain`=10; **нет ни одного `goal_speed='fast'`**;
**нет heavy/extreme activity**; **группа риска Ж/15-35/lose = 0 человек**; `waist_circumference`
заполнен 2/14. Таблиц трекинга тренировок — **нет ни одной** (P2.5a отсутствует). Вывод: носителей
риска в текущей когорте физически ноль → строить guard не от кого, фейковый EA-lite по-прежнему
вреден.

**Вместо guard — честный информационный дисклеймер** (не претендует на расчёт EA):
- Дом — **экран Women's Health** (`personal_metrics_women_health`), НЕ Safety Center. Причина: Safety
  Center (`get_safety_center_data`) — динамическое табло сработавших calc-гардов, и mig 263 ЯВНО прячет
  severity `informational`/`silent_accuracy`; справочная заметка туда либо не попадёт, либо потребует
  фейкового non-info severity. Women's Health — женский, информационный, тематически про гормоны.
- Ключ `ui_translations.profile.women_health_red_s_note` (13 языков, мастер RU+EN; 11 — без native L1).
- Placeholder `{red_s_note}` в `profile.women_health_text`; `get_women_health_business_data` возвращает
  `red_s_note` под условием **`goal_type='lose' AND NOT is_pregnant AND NOT is_lactating`**.
- Текст: «💛 Энергия и цикл» — без чисел, без жаргона RED-S, anti-shame, самонацеливающийся, врач при
  пропавшем цикле. Эмодзи 💛 встроен в текст (как 🌸 в существующих ключах).

**🔴 Durable gotcha (поймано здесь):** беременность/кормление/underage в `calculate_user_targets`
форсят `effective_goal_type='maintain'`, но **НЕ меняют сохранённый `users.goal_type`** (остаётся
`lose`). Любой UI/гейтинг по `goal_type='lose'` ОБЯЗАН доп. исключать `is_pregnant`/`is_lactating`,
иначе беременная увидит контент для худеющих. Это причина двойного условия в RPC.

**Сторож разморозки — measurable (admin-алерт owner отклонил, только документация):** поднять приоритет
настоящего EA-гарда (ручной лог тренировок → P2.5a → guard P2.5b), когда в БД появится **профиль
Ж / 15-35 / `goal_type='lose'` / (`goal_speed='fast'` ИЛИ activity heavy/extreme)**, ЛИБО юзер сообщит
про пропавший/сбившийся цикл (escalate immediately). Сейчас таких 0.

## 7. Связанные

- [[concepts/calc-user-targets-roadmap]] P2.5a / P2.5b
- [[concepts/safety-guard-ux-pattern]] §3 soft override severity
- [[concepts/phenotype-quiz]] — Phase 2 q5 placeholder для waist
- [[concepts/user-data-collection-pattern]] — retrofit pattern для workout tracking onboarding
