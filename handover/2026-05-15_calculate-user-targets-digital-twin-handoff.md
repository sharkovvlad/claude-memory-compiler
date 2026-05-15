# Handoff — Digital Twin для `calculate_user_targets` v4 (агенту-нутрициологу)

**Адресат:** агент, создающий «цифровой двойник» формулы расчёта КБЖУ в Google Sheets («Test Oracle» / «Constants» / «Modifiers» вкладки).
**Источник:** мне (агенту-практику) был передан запрос с тремя пунктами (mig 227 SQL, app_constants snapshot, Phase 3 spec). Ниже — всё это **плюс** 5 критичных деталей, которые упущены и без которых таблица разойдётся с прод-формулой.

---

## 0. Доступ к файлам — что сделать ДО чтения остального

**Главная причина «миграций нет в `~/Documents/NOMS/migrations/`»:** основной клон отстал от GitHub. Last merge в локальном main = PR #55 (апрельский), а на GitHub уже PR #75. Нужно подтянуть:

```bash
cd /Users/vladislav/Documents/NOMS
git status                          # должен быть clean (если нет — стоп, разобраться сначала)
git pull --ff-only origin main      # подтянет всё, включая mig 227
ls migrations/227_fix_calculate_user_targets.sql  # появится
```

После этого все пути ниже работают.

---

## 1. Тело функции — НЕ один файл, а наслоение двух

⚠️ **Самое частое заблуждение:** «mig 227 содержит всю функцию». На самом деле:
- Функция в проде = **mig 055 (v3 база)** + **mig 227 (v4 patch)**.
- В mig 227 есть полный `CREATE OR REPLACE FUNCTION` (т.е. перезаписывает целиком), но смысл diff'а понятен только в сравнении с v3.

**Что читать (в этом порядке):**

| # | Файл | Зачем |
|---|---|---|
| 1 | [`migrations/055_personalized_macros.sql`](https://github.com/sharkovvlad/noms-bot/blob/main/migrations/055_personalized_macros.sql) строки 163-345 | v3 база — чтобы понять контекст: 9 шагов расчёта, LBM proxy, BMR Mifflin, goal_speed coefficients |
| 2 | [`migrations/227_fix_calculate_user_targets.sql`](https://github.com/sharkovvlad/noms-bot/blob/main/migrations/227_fix_calculate_user_targets.sql) | **Финальная v4** — целиком новое тело. Диффы от v3 помечены `-- v4 additions` / `-- v4 fix` |
| 3 | [`migrations/119_training_none_revert_country_hide_back_onboarding.sql`](https://github.com/sharkovvlad/noms-bot/blob/main/migrations/119_training_none_revert_country_hide_back_onboarding.sql) Block A.3 (~строка 130-160) | Где `training_type='none'` появился. **Понимание `cmd_select_training_skip → 'mixed'` — это политика, не баг** |
| 4 | [`migrations/190_fix_set_user_training_type_status_advance.sql`](https://github.com/sharkovvlad/noms-bot/blob/main/migrations/190_fix_set_user_training_type_status_advance.sql) | Финальный mapping callback_data → training_type. Все возможные значения `training_type` в проде: `strength`, `cardio`, `mixed`, `sedentary`, `none`. NULL допустим. |

**Альтернатива (быстрее и точнее):** попроси меня экспортировать `pg_get_functiondef('public.calculate_user_targets(bigint,boolean)'::regprocedure)` живого прода — получишь **финальное тело** v4 одним куском, без необходимости читать diff. Скажи «дай pg_get_functiondef» — я сделаю через psycopg2 (разрешение есть).

---

## 2. Полный snapshot `app_constants` — все 22 ключа, участвующих в расчёте

Снято из NotebookLM `NOMS Supabase Data` 2026-05-15, **после** apply mig 227. Если что-то изменится — повторно сними через `notebooklm ask` (notebook ID `fa75f4de-96c2-4dc0-bc9d-0bf07bd992f5`) или через прямой SELECT.

**Белок (g/kg на target_weight):**
```
protein_g_per_kg_strength  = 2.0
protein_g_per_kg_cardio    = 1.4
protein_g_per_kg_mixed     = 1.6
protein_g_per_kg_sedentary = 1.2
protein_g_per_kg_none      = 1.2    -- mig 227, для «реально не тренируюсь»
```

**Жиры (% от target_kcal):**
```
fat_pct_strength  = 25
fat_pct_cardio    = 20
fat_pct_mixed     = 25
fat_pct_sedentary = 30
fat_pct_none      = 30              -- mig 227
```

**Защитные минимумы:**
```
fat_min_g_per_kg = 0.8              -- floor для жира (от target_weight)
carbs_min_g      = 50               -- абсолютный минимум углеводов
```

**Базовый PAL (от activity_level):**
```
pal_sedentary = 1.2
pal_light     = 1.375
pal_moderate  = 1.55
pal_heavy     = 1.725
```

**PAL bonus за тренировки (mig 227, добавляется к базовому PAL):**
```
pal_training_bonus_sedentary = 0.15
pal_training_bonus_light     = 0.10
pal_training_bonus_moderate  = 0.05
pal_training_bonus_heavy     = 0.00
```

**Phenotype модификаторы (LBM proxy):**
```
phenotype_monw_modifier      = 0.85   -- target_weight = weight × 0.85
phenotype_obese_offset_male  = 100    -- target_weight = max(height - 100, 40)
phenotype_obese_offset_female = 110   -- target_weight = max(height - 110, 40)
```

**Goal speed (% дефицита/профицита от TDEE):**
```
goal_speed_slow_deficit   = 10
goal_speed_normal_deficit = 15
goal_speed_fast_deficit   = 20
goal_speed_slow_surplus   = 8
goal_speed_normal_surplus = 10
goal_speed_fast_surplus   = 15
```

---

## 3. Schema `users` — какие колонки читает функция

Все nullable, кроме указанного guard'а. Типы из live базы (NLM подтвердил 2026-05-15).

| Колонка | Тип | Default | Допустимые значения | Role |
|---|---|---|---|---|
| `weight_kg` | NUMERIC | NULL | 30-300 (validation_limits) | **Guard: NOT NULL** |
| `height_cm` | NUMERIC | NULL | 100-250 | **Guard: NOT NULL** |
| `birth_date` | DATE | NULL | -- | **Guard: NOT NULL**, age = `DATE_PART('year', AGE(birth_date))` |
| `gender` | TEXT | NULL | `'male'`, `'m'`, остальное → female | **Guard: NOT NULL**. Lower+trim перед сравнением |
| `activity_level` | TEXT | NULL | `'sedentary'/'light'/'moderate'/'heavy'` | Используется ТОЛЬКО для PAL bonus lookup (`pal_training_bonus_||activity_level`) |
| `pal_coefficient` | NUMERIC | NULL → 1.2 | 1.2 / 1.375 / 1.55 / 1.725 | Базовый PAL (записывается из activity_level в `set_user_activity`) |
| `training_type` | TEXT | `'mixed'` | `'strength'/'cardio'/'mixed'/'sedentary'/'none'` или NULL → 'mixed' | Драйвер protein/fat коэффициентов **И** условие применения PAL bonus |
| `phenotype` | TEXT | `'default'` | `'monw'/'athlete'/'obese'/'default'` или NULL → 'default' | Драйвер LBM proxy. **`'athlete'` сейчас = no-op** (попадает в default ветку) |
| `goal_type` | TEXT | NULL | `'lose'/'gain'/'maintain'` или NULL/прочее → maintain | Драйвер deficit/surplus, ТАКЖЕ **conditional clamp в Step 8** |
| `goal_speed` | TEXT | `'normal'` | `'slow'/'normal'/'fast'` | Размер deficit/surplus |
| `status` | TEXT | -- | `'registered'` для backfill | НЕ читается функцией, нужен только для DO-backfill |

**Output (записывается обратно если `p_save_to_db=true`):**
- `target_calories` INT
- `target_protein_g` INT
- `target_fat_g` INT
- `target_carbs_g` INT
- `target_weight_kg` NUMERIC

---

## 4. Sentinel cases — ground truth для validation вкладки

Эти 5 кейсов **прогнаны на проде 2026-05-15** через `SELECT calculate_user_targets(<test_tg>, false)` и совпали с pre-расчётом на бумаге **до грамма**. Используй для проверки своих формул.

| # | Профиль | bmr | tdee | pal_base→adj | requested | actual | **target** | P/F/C | floor F/C | eff_def% |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | F/30/165/70 sed+cardio lose+slow default | 1420.25 | 1917.34 | 1.20→1.35 | 1726 | 1728 | **1728** | 98/56/208 | T/F | 9.9 |
| 2 | M/25/180/75 mod+strength gain+normal monw | 1755 | 2808 | 1.55→1.60 | 3089 | 3090 | **3090** | 128/86/451 | F/F | **−10.0** |
| 3 | F/40/165/100 light+mixed lose+fast obese | 1670.25 | 2463.62 | 1.375→1.475 | 1971 | 1971 | **1971** | 88/55/281 | F/F | 20.0 |
| 4 | M/30/175/70 sed+strength lose+normal default | 1648.75 | 2225.81 | 1.20→1.35 | 1892 | 1892 | **1892** | 140/56/207 | T/F | 15.0 |
| 5 | M/30/175/70 sed+`none` lose+normal default | 1648.75 | 1978.5 | 1.20→1.20 | 1682 | 1684 | **1684** | 84/56/211 | F/F | 14.9 |

**Что специально проверяет каждый:**
- **#1** — `fat_floor` доминирует над `fat_pct` (0.8×70=56 ккал-эквивалент 504 > 20% от 1726 = 38). Cardio-женщины 60-80 кг — самый частый случай.
- **#2** — gain target > TDEE (3090 > 2808). **Доказывает**, что conditional clamp работает (безусловный `LEAST(actual, tdee)` дал бы 2808 = maintain).
- **#3** — phenotype obese: `target_weight = max(165−110, 40) = 55` (не 100). BMR при этом считается **по реальному весу** 100, не по 55.
- **#4** — sentinel **PAL fusion**: pal_base=1.2, pal_adjusted=1.35 (+0.15 за strength training на sedentary base). Без mig 227 был бы 1.2 → TDEE 1979, target ≈1683. Прирост обещанной нормы +209 ккал/день.
- **#5** — sentinel `'none'`: те же входы что #4, но `training_type='none'` → bonus НЕ применяется (training_type не входит в active set), protein 1.2 г/кг (новая константа), fat 30%.

---

## 5. ⚠️ Пять критичных деталей, которые надо учесть в Sheets-формулах

### 5.1. PostgreSQL `ROUND` ≠ Google Sheets `ROUND` на границах X.5

- **Postgres** для NUMERIC использует **half-to-even** (banker's rounding): `ROUND(0.5)=0, ROUND(1.5)=2, ROUND(2.5)=2, ROUND(3.5)=4`.
- **Google Sheets** использует **half-away-from-zero**: `ROUND(0.5)=1, ROUND(1.5)=2, ROUND(2.5)=3, ROUND(3.5)=4`.

В функции **8+ ROUND'ов** (BMR не округляется, но requested_kcal, protein, fat, fat_floor, carbs, target, effective_deficit_pct — да). На границах X.5 разница ±1.

**Решение:** для banker's rounding в Sheets:
```
=IF(MOD(ABS(x*2), 2)=1, 2*ROUND(x/2, 0), ROUND(x, 0))
```
Или проще — задокументируй в Constants вкладке «допустимое расхождение ±1 на values оканчивающихся на .5» и используй обычный ROUND. Тестовые сценарии в исходной документации тоже допускают «1-2 грамма расхождение».

### 5.2. `DATE_PART('year', AGE(birth_date))` совместим с `DATEDIF(birth_date, TODAY(), "Y")`

Postgres `AGE()` возвращает интервал лет/месяцев/дней; `DATE_PART('year', ...)` берёт целое число лет. Для «25 лет, день рождения сегодня» вернёт 25.

Google Sheets `DATEDIF(birth_date, TODAY(), "Y")` — то же поведение (целые годы по факту). **Совпадает**, можно использовать напрямую.

### 5.3. `LEAST` в Postgres NULL-strict; `MIN` в Sheets — нет

- Postgres `LEAST(NULL, 5) = NULL` (если хоть один аргумент NULL).
- Sheets `MIN(blank, 5) = 5`.

В нашей функции `LEAST` получает только не-NULL (всё через COALESCE с дефолтами). Безопасно мапить на `MIN` в Sheets — поведение совпадёт.

### 5.4. Phenotype `obese` имеет MIN floor 40 кг для target_weight

```sql
v_target_weight := GREATEST(v_user.height_cm - v_obese_offset, 40);
```

Female 145см obese: `target_weight = MAX(145−110, 40) = 40` (не 35). Edge case для миниатюрных — не забыть `MAX(_, 40)` в формуле.

### 5.5. PAL bonus читается по `activity_level`, training_type — только gate

Самая нелогичная часть формулы:

```sql
IF training_type IN ('strength','cardio','mixed') THEN
    bonus := SELECT value FROM app_constants WHERE key = 'pal_training_bonus_' || activity_level;
ELSE
    bonus := 0;
```

**Размер bonus** определяется базовой активностью (`activity_level`), а **сам факт применения** — типом тренировки. Не путать с `protein_g_per_kg_*` и `fat_pct_*` — те читаются по `training_type`. Это **два независимых лукапа в одной функции**.

Pseudo-код для ясности:
```
bonus = IF(training_type in ['strength','cardio','mixed'],
           VLOOKUP('pal_training_bonus_' & activity_level, constants, 2, false),
           0)
pal_adjusted = MIN(pal_base + bonus, 1.8)
```

---

## 6. Phase 3 (Adaptive Modifiers) — где это будет хитекаться

Файл: [`.claude/specs/adaptive_modifiers_spec.md`](https://github.com/sharkovvlad/noms-bot/blob/main/.claude/specs/adaptive_modifiers_spec.md) (4.4 KB, апрель). 3 модификатора:

| Триггер | Что меняется | Источник данных | Изменение в формуле |
|---|---|---|---|
| **Sleep < 6h** | Protein +15% (или min 1.8-2.0 г/кг), Carbs −пропорционально | Утренний чек-ин `users.sleep_quality TEXT` (новая колонка, daily reset) | После Step 7, перед Step 8 |
| **High stress** | Carbs +10-15% (за счёт fat), Protein без изменений | Sentiment-анализ или чек-ин `users.stress_level TEXT` | После Step 7, перед Step 8 |
| **Luteal phase (PMS)** | TDEE +5-10% (+100-300 ккал/день) | Cycle tracking `users.cycle_phase` (есть в БД, но мёртвый груз) | В Step 5, после PAL fusion |

**Дизайн «Modifiers» вкладки в Sheets:**
- Входы: sleep_quality (short/okay/great), stress_level (none/moderate/high), cycle_phase (luteal/follicular/none).
- Логика: applies multiplicative/additive modifiers поверх base v4 results.
- Output: модифицированные target_kcal/P/F/C.

Это будет следующий слой поверх v4 в БД (новые поля в JSON.calculations: `modifier_sleep_applied`, `modifier_stress_applied`, `modifier_cycle_applied`). Сейчас **в коде их нет**, формула v4 их игнорирует.

---

## 7. Phase 2 (Phenotype Quiz) — для понимания phenotype assignment

Файл: [`.claude/specs/phenotype_quiz_spec.md`](https://github.com/sharkovvlad/noms-bot/blob/main/.claude/specs/phenotype_quiz_spec.md). 4 вопроса → определение фенотипа (`monw`/`athlete`/`obese`/`default`).

KB concept: [[concepts/phenotype-quiz]] (свежий обзор).

Релевантно для двойника тем, что **`phenotype` — input в формулу**, и понимание как он assigned'ится поможет составить «Test Oracle» вкладку с реалистичными комбинациями.

---

## 8. Что НЕ покрывает v4 — важно для дизайна вкладок

Эти gap'ы зафиксированы в KB [[concepts/personalized-macro-split]] секция «v4». Если делаешь Modifiers/Roadmap вкладку — учитывай:

1. **Age guard `<18` и `>75`** — нет защиты. Mifflin не валиден для подростков, занижает у пожилых. **Подростки 13-17 лет могут регистрироваться** (validation_limits.age_years.min=13).
2. **Беременность/лактация** — нет поля в `users`, нет коррекции BMR. Опасный дефицит.
3. **`phenotype='athlete'`** — попадает в default ветку, ничего не меняет. UX-обман.
4. **Mifflin у obese переоценивает RMR на 5-10%** — Katch-McArdle от LBM (есть из Phase 2 quiz) был бы точнее.
5. **Adaptive modifiers Phase 3** — отсутствуют (см. секцию 6).

В таблице это можно отдельной вкладкой «Known Gaps» — чтобы наглядно видеть, **где формула априори даёт неточность**, и не пугаться расхождений с реальной физиологией на этих кейсах.

---

## 9. Итеративный цикл «Sheets ↔ Prod» для будущей балансировки

Когда таблица будет готова — типовой workflow для тюнинга:

1. Меняем константу в **«Constants»** вкладке (например, `pal_training_bonus_sedentary: 0.15 → 0.18`).
2. Все 5 sentinel-кейсов в **«Test Oracle»** автоматически пересчитываются → видим эффект.
3. Если ОК — синхронизируем в Postgres: `UPDATE app_constants SET value='0.18' WHERE key='pal_training_bonus_sedentary'`. Триггер `trg_refresh_constants_cache` автомат обновит кеш.
4. Через 30 сек (TTL) — функция начнёт использовать новое значение. Никаких миграций, никакого деплоя кода.
5. Если откат — Constants вкладка имеет «Эталонную/Baseline» колонку → копируем обратно через тот же UPDATE.

**Важно:** изменения константы в БД повлияют на **новые** вызовы `calculate_user_targets`. Существующие `users.target_*` колонки **не пересчитаются автоматически** — нужен ручной backfill (`PERFORM calculate_user_targets(tg, true)` по нужным юзерам). Snapshot для отката — `users_targets_backup_20260515` (drop по графику 2026-05-22).

---

## 10. Когда таблица будет готова — что я могу делать с ней

У меня будет доступ к Sheets через Google Drive. Могу:
- **Прогон validation** — сверять live SELECT calculate_user_targets vs values в Test Oracle вкладке после каждого константного UPDATE. Автоматически, без ручной работы.
- **Backfill после изменения констант** — если ПМ через таблицу решил что новые значения OK, я могу пересчитать всех registered юзеров по команде.
- **Snapshot на каждое изменение** — перед каждым UPDATE делать `users_targets_backup_<date>` для rollback.
- **Sentinel set расширение** — добавлять новые edge cases по мере находок.

---

## Контрольный список перед началом работы

- [ ] `git pull` сделан, `migrations/227_*.sql` появился в `/Users/vladislav/Documents/NOMS/migrations/`.
- [ ] Прочитан mig 227 целиком (300 строк, 60% — комментарии-документация, читается быстро).
- [ ] Прочитан раздел 5 этого хендоффа (Postgres-Sheets gotchas) — без него таблица разойдётся с прод.
- [ ] Прочитан `adaptive_modifiers_spec.md` для Phase 3 интеграции.
- [ ] Запрошен у меня `pg_get_functiondef` (опц., если хочешь финальное тело без diff-чтения).

Если что-то непонятно — спрашивай через ПМ-агента. Я буду верифицировать формулы Sheets против live-SELECT'ов после первой версии таблицы.
