---
title: "calculate_user_targets v8 — Golden Test Cases (Digital Twin Spreadsheet)"
aliases: [twin-v8-tests, calc-test-cases, safety-guards-tests]
tags: [calc, safety-guards, testing, spreadsheet, v8]
sources:
  - "migrations/254_calculate_user_targets_v8_maternal.sql"
  - "migrations/274_safety_center_foundation.sql"
  - "migrations/276_safety_center_my_plan_integration.sql"
  - "migrations/281_my_plan_hide_pace_for_maintain.sql"
  - "concepts/personalized-macro-split.md"
  - "concepts/safety-guard-ux-pattern.md"
created: 2026-05-20
status: golden reference — update when calc v9+ ships
---

# calculate_user_targets v8 — Golden Test Cases

> **Назначение:** эталонный набор 14 тест-кейсов для проверки корректности `calculate_user_targets` после любых изменений (v8 → v9 → …). Используется как regression-suite в Google Sheets «Digital Twin» (двойник калькулятора) + как cross-check ground truth для RPC.
>
> **Google Sheet:** [NOMS LiveOps Digital Twin v8.3](https://docs.google.com/spreadsheets/d/1Yi6VyKyPjMm0Et7okGW8NZgSCepQYUZVkGU2flaRa5o/edit) (final EU-locale fix).
>
> **Каноническая папка Drive:** `1aJOXi7Y0qpR0emLSSOBrMFGyRhBJICNe`.

---

## Реальные пороги v8 (verified против pg_get_functiondef 2026-05-20)

| Параметр | Значение | Триггер |
|---|---|---|
| BMI cachexia | **<14** | `extreme_cachexia_recommend_medical` (hard_block) |
| BMI underweight | **<18,5 + goal=lose** | `underweight_lose_override` (hard_regulated, force maintain) |
| BMI obesity clamp | **>60 + goal=lose + speed in (fast,normal)** | `extreme_obesity_clamp_slow` (clamp speed→slow) |
| Age underage | **<18 + goal=lose** | `underage_forced_maintain` (hard_block, force maintain) |
| Age elderly | **>75** | `elderly_less_accurate` (informational only) |
| Pregnancy bonus | T1=+0, **T2=+340**, **T3=+452** ккал | trigger via `is_pregnant=TRUE` |
| Lactation bonus | **exclusive=+330**, **partial=+300** ккал | trigger via `is_lactating=TRUE` |
| Goal deficit | slow=10%, normal=15%, fast=20% от TDEE | `goal_type=lose` |
| Goal surplus | slow=8%, normal=10%, fast=15% от TDEE | `goal_type=gain` |
| Medical floor | female=1200, male=1500 ккал | если target < floor — force-clamp |
| Min kcal floor | **MAX(medical_floor, BMR)** | если BMR > medical → `bmr_floor_triggered` |
| Carbs floor | pregnant=175 / lactating=210 / female=100 / male=50 г | per-status |

⚠️ **Важно — расхождения с задачей:** при создании Sheet **5 порогов** оказались отличными от первоначальных предположений (BMI cachexia был 16, теперь 14; obesity 40, теперь 60; lactation +500, теперь +330/300; etc.). Канонический источник — **тело RPC** через `pg_get_functiondef('public.calculate_user_targets')`.

---

## 14 Golden Test Cases

### Входы (для каждого кейса)

| # | Сценарий | gender | weight | height | birth_date | goal | speed | activity | training | phenotype | is_preg | is_lact | trim | lact_type |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Adult maintain baseline | male | 80 | 180 | 1990-01-01 | maintain | normal | sedentary | mixed | default | FALSE | FALSE | — | — |
| 2 | Adult lose normal | male | 80 | 180 | 1990-01-01 | lose | normal | sedentary | mixed | default | FALSE | FALSE | — | — |
| 3 | Adult lose fast | male | 80 | 180 | 1990-01-01 | lose | fast | sedentary | mixed | default | FALSE | FALSE | — | — |
| 4 | Teen 16 lose fast | female | 55 | 165 | 2010-01-01 | lose | fast | sedentary | mixed | default | FALSE | FALSE | — | — |
| 5 | Pregnant T2 lose | female | 65 | 165 | 1998-01-01 | lose | normal | sedentary | mixed | default | TRUE | FALSE | 2 | — |
| 6 | Lactating exclusive maintain | female | 65 | 165 | 1998-01-01 | maintain | normal | sedentary | mixed | default | FALSE | TRUE | — | exclusive |
| 7 | Pregnant teen 17 lose | female | 55 | 165 | 2009-01-01 | lose | normal | sedentary | mixed | default | TRUE | FALSE | 2 | — |
| 8 | Underweight BMI 17 lose | female | 46 | 165 | 1995-01-01 | lose | normal | sedentary | mixed | default | FALSE | FALSE | — | — |
| 9 | Cachexia BMI 13.6 | female | 37 | 165 | 1995-01-01 | maintain | normal | sedentary | mixed | default | FALSE | FALSE | — | — |
| 10 | Extreme obesity BMI 62 lose fast | male | 200 | 180 | 1995-01-01 | lose | fast | sedentary | mixed | default | FALSE | FALSE | — | — |
| 11 | Female low-weight sub-1200 | female | 42 | 155 | 1995-01-01 | lose | fast | sedentary | cardio | default | FALSE | FALSE | — | — |
| 12 | Male adult sub-1500 | male | 55 | 165 | 1995-01-01 | lose | fast | sedentary | cardio | default | FALSE | FALSE | — | — |
| 13 | Female 17 lose fast, pregnancy NULL | female | 55 | 165 | 2009-01-01 | lose | fast | sedentary | mixed | default | NULL | NULL | — | — |
| 14 | Sub-BMR negative (BMR > target) | male | 110 | 185 | 1990-01-01 | lose | fast | sedentary | strength | default | FALSE | FALSE | — | — |

### Ожидаемые выходы

| # | effective_goal | target_kcal | warnings (csv) |
|---|---|---|---|
| 1 | maintain | 2333 | — |
| 2 | lose | 1985 | — |
| 3 | lose | 1869 | — |
| 4 | **maintain** (forced) | 1679 | `underage_forced_maintain` |
| 5 | **maintain** (forced) | 2190 | `pregnancy_force_maintain` |
| 6 | maintain | 2180 | `lactation_force_maintain` |
| 7 | **maintain** (2× forced) | 2048 | `pregnancy_force_maintain, underage_forced_maintain` |
| 8 | **maintain** (forced) | 1586 | `underweight_lose_override` |
| 9 | **maintain** (forced) | 1525 | `extreme_cachexia_recommend_medical` |
| 10 | lose (speed→slow) | 2375 | `extreme_obesity_clamp_slow` |
| 11 | **maintain** (forced) | 1451 | `underweight_lose_override` |
| 12 | lose (floored) | 1500 | `medical_floor_1500_triggered` |
| 13 | **maintain** (2× forced) | 1708 | `maternal_status_unknown_protective_maintain, underage_forced_maintain` |
| 14 | lose | 2236 | — (sub-BMR не сработал) |

**Толерантность:** ±30 ккал (учитывает DATEDIF age drift через 1 год + ROUND-порядок vs RPC).

---

## Edge cases — почему важны

- **#4 vs #11** — оба female lose+fast, разный возраст. #4 underage форсит maintain; #11 underweight override срабатывает раньше (BMI 17.5 < 18.5). Демонстрирует приоритет проверок: BMI guards → maternal → age.
- **#7** — overlap двух hard_block guards. RPC возвращает оба в warnings; effective_goal_type=maintain (любой из них достаточно).
- **#10** — единственный случай где speed clamp (не goal). Speed `fast` → `slow`, но `goal=lose` сохранён.
- **#11 vs #12** — почему `medical_floor_1200_triggered` сложно изолировать: BMI<18.5 fires FIRST → underweight_lose_override → forced maintain → kcal не падает ниже 1200. Чтобы реально протестировать `medical_floor_1200_triggered` нужен искусственный профиль (PAL=1.2, no training, very low weight но BMI≥18.5). В #12 — male sub-1500 проще получить.
- **#13** — NULL maternal status (is_pregnant=NULL, is_lactating=NULL) для F 15-50 lose → `maternal_status_unknown_protective_maintain`. **Important:** требует ISBLANK() check в формулах, не `=""`.
- **#14** — negative case: BMR=2070 < target_calories=2236, поэтому bmr_floor_triggered НЕ срабатывает.

---

## Cross-check проды

После любого изменения calc:

```sql
-- Создать sentinel юзера и вызвать RPC напрямую
SAVEPOINT s1;
UPDATE users SET
    gender='female', weight_kg=65, height_cm=165, birth_date='1998-01-01',
    goal_type='lose', goal_speed='normal', activity_level='sedentary',
    training_type='mixed', phenotype='default',
    is_pregnant=TRUE, is_lactating=FALSE, pregnancy_trimester=2
WHERE telegram_id=<test_tid>;

SELECT (calculate_user_targets(<test_tid>, FALSE))->'calculations';
-- Сравнить с expected в таблице выше (test case #5)

ROLLBACK TO SAVEPOINT s1;
```

Сравнить:
- `target_calories` → должен совпасть в пределах ±30
- `pregnancy_warning` → `pregnancy_force_maintain`
- `effective_goal_type` → `maintain`

---

## Поддержание

**Когда обновлять:**
- При apply миграции, которая модифицирует `calculate_user_targets` (v8 → v9+)
- При добавлении нового safety guard enum или family
- При изменении threshold'ов (например cachexia с 14 на 13)

**Что обновлять:**
1. Этот KB: пороги в таблице «Реальные пороги v8» + expected values в таблице 14 cases
2. Google Sheet v8.3 (или новая версия v9): константы + expected outputs
3. Sub-agent доступ к pg_get_functiondef для актуальных порогов

**Где НЕ обновлять:**
- Никогда не редактировать v6.3 Sheet (исторический baseline)

---

## Связанные KB

- [[concepts/personalized-macro-split]] — macro-split расчёты и формулы
- [[concepts/safety-guard-ux-pattern]] — severity matrix + 5 touch points (где каждый guard виден юзеру)
- [[concepts/calc-user-targets-roadmap]] — версии v4 → v8, что менялось
- [[concepts/pregnancy-lactation-clinical-spec]] — клинические обоснования maternal bonuses
- [[concepts/headless-architecture]] — где RPC интегрируется в UX

---

## Versioning

| Версия Sheet | URL | Статус |
|---|---|---|
| v6.3 (original) | [link](https://docs.google.com/spreadsheets/d/1t-5xsGaYP64Dk7NKfRnCGignlbtOKyG0a2LE6jjOGB0/edit) | historical baseline, **не редактировать** |
| v8.0 | [link](https://docs.google.com/spreadsheets/d/1HGLcFLDdtwFP7zKxLU9EKk5gk6UwQ_msZCFjmypIaAY/edit) | en-US formulas, FAIL в ru-RU locale |
| v8.1 | [link](https://docs.google.com/spreadsheets/d/10ExRBepdEyU0dsol_xns5a_wDCV4FHB4eSkhLfqlaQk/edit) | EU `;` separator, FAIL на decimals |
| v8.2 | [link](https://docs.google.com/spreadsheets/d/1D0ne8CDjM3uhCl5EU6AZntjCMkrgelS2gi4c1MtlIVY/edit) | EU full (separator + decimal), FAIL на boolean compare |
| **v8.3 (canonical)** | [link](https://docs.google.com/spreadsheets/d/1Yi6VyKyPjMm0Et7okGW8NZgSCepQYUZVkGU2flaRa5o/edit) | **WORKS** — все формулы рендерят корректно |

Промежуточные версии оставлены для post-mortem (показывают эволюцию locale-fix).

---

## v13 Digital Twin (2026-06-03) — пересборка под live v13

v8.3 отставала на **5 версий** (прод = v13, mig 429). Twin **пересобран с нуля**: 21 профиль,
все 13 шагов конвейера, провалидирован **headless (`formulas` lib) + 1:1 против живого RPC**
(дельты 0, 21/21 PASS). Файлы — `Нутрициолог (аудит расчётов v13)/` (untracked корень NOMS):
- `Digital_Twin_v13_formulas.xlsx` — 4 листа (README/Constants/Profiles/Analysis), live-движок формулами.
- `Digital_Twin_v13_values.csv` → нативный Google Sheet (Drive id `1GWSD4YiNkbkN_UQpOTlTNsEnNdKogHOS9STT9BG6zgw`).

**Lesson — version drift:** ВСЕГДА сверяй версию twin против live `pg_get_functiondef('calculate_user_targets')`
ПЕРЕД использованием. Twin — не источник истины, RPC — источник.

**Gotcha — заливка в Google Drive (MCP `create_file`):**
- **Бинарный `.xlsx` инлайном НЕНАДЁЖЕН** — 28KB файл = 37.5KB base64 (~36K токенов) не помещается в
  один Read (cap 25K) и LLM не воспроизводит base64 байт-точно (1 битый символ ломает zip).
- **Паттерн для нативного Sheet:** `create_file` с `textContent` + `contentMimeType=text/csv` →
  конвертит в `application/vnd.google-apps.spreadsheet`. Формулы (строки с `=`) **исполняются**, НО
  запятые внутри формул ломают CSV-разбор (нужны кавычки) + риск EU-locale (`,` vs `;` — баг v8.x).
- **Вывод:** values-CSV → нативный Sheet (надёжно); формульный движок → отдельный `.xlsx` для ручного
  импорта владельцем (File→Import; импорт xlsx сам разруливает locale).
