---
title: "Региональные food-composition databases — CIQUAL/BEDCA/IFCT/USDA-SR (deferred + 2026-06-08 eval)"
aliases: [ciqual, bedca, ifct, regional-cuisine-db, food-composition-db, regional-dishes]
tags: [accuracy, regional, latam, eu, india, russia, deferred, food-database, eval-2026-06-08]
sources:
  - "daily/2026-06-08.md"
created: 2026-06-08
updated: 2026-06-08
status: deferred-with-eval-data
---

# Региональные food-composition databases — план + readiness criteria + eval 2026-06-08

> **Status:** eval сделан 2026-06-08 (см. §4.6 ниже). **CONDITIONAL GO для ES + RU**, NO-GO для IN/BR/MX. **Shipping integration deferred** — user-base threshold (≥20 active в одной стране) не выполнен. Возвращаться когда выполнится.

---

## 1. Что это (для не-знающих)

**Food-composition databases (FCDB)** — это национальные **государственные/научные** таблицы типичных КБЖУ для **generic foods и блюд** (без бренда, без штрихкода). Не базы упакованных продуктов, не каталоги ресторанов.

Пример записи (CIQUAL):
```
ID 25024 — "Choucroute garnie, plat préparé"  (тушёная капуста с мясом, фр. блюдо)
  Energy: 138 kcal / 100g
  Protein: 8.4g
  Fat: 9.2g
  Carbs: 4.1g
  + 50+ микронутриентов (витамины, минералы) per 100g
```

**Ключевое отличие от того, что у нас уже есть:**
- OpenFoodFacts / USDA Branded = **упакованные продукты по штрихкоду** (Coca-Cola, Nutella)
- CIQUAL / BEDCA / IFCT = **generic dishes** (борщ, паэлья, дал, choucroute) — для текстового/голосового ввода

### Доступные FCDB по регионам

| База | Регион | Размер | Доступ | Особенности |
|---|---|---|---|---|
| **CIQUAL** | Франция (ANSES) | ~3000 позиций | Free CSV download | Самая полная EU; включает региональные французские блюда |
| **BEDCA** | Испания | ~1000 позиций | Free download | Испанские/средиземноморские блюда |
| **TBCA** | Бразилия (USP) | ~600 позиций | Free download | Бразильские местные блюда + ингредиенты |
| **IFCT** | Индия (NIN) | ~500 позиций | Free PDF/CSV | Индийские традиционные блюда + специи |
| **USDA-SR** | США | ~9000 позиций | Free API/CSV | Generic foods (НЕ Branded — это уже у нас) |
| **FGBNU/Тутельян** | Россия | ~3000 позиций | Free book / частично CSV | Русские и СНГ-блюда |
| **Mexico INNSZ** | Мексика | ~700 | Free PDF | Мексиканские традиционные |

Все free. Все имеют **похожую структуру** (food name + macros per 100g + micronutrients) — можно унифицировать через одну таблицу `regional_food_db` с колонкой `source`.

---

## 2. Зачем это могло бы помочь

### Где FCDB могут дать value

| Сценарий | Текущая работа | С FCDB |
|---|---|---|
| Юзер пишет «ел choucroute garnie» | GPT-4o оценивает на глаз | Точные референсные значения из CIQUAL |
| «Tortilla de patatas, 200г» | GPT-4o оценивает | BEDCA точное среднее |
| «Дал макхани, миска» | GPT-4o оценивает (вероятно знает плохо) | IFCT с расчётом по индийским специям |
| «Sirniki с творогом» | GPT-4o оценивает | FGBNU/Тутельян лабораторные данные |

### Где FCDB НЕ помогут

- Упакованные продукты (штрихкод покрывает) — уже OFF + USDA
- Уникальные домашние интерпретации («бабушкин борщ») — нет ground truth ни у кого
- Точная порция (это про identification, не про per-100g)
- Vision-распознавание (FCDB — это lookup по имени, не по фото)

### Почему **не quick win**

Из KB [[cascade-macro-enrichment-fatsecret]] §13: для **обычных одиночных позиций GPT-4o уже на уровне FatSecret** (медиана 0% отклонения от reference). Гипотеза для региональных блюд:
- 🟢 **Может быть** value для редких/традиционных блюд которых GPT-4o «не знает в подробностях»
- 🟡 **Не доказано** — без eval не знаем
- 🔴 **Риск:** GPT-4o может уже знать эти блюда лучше чем мы думаем (training data огромен)

См. план eval ниже (§4).

---

## 3. Readiness-критерии для shipping (deferred-gate)

**Eval можно делать в любой момент** (cheap — CIQUAL/BEDCA CSV скачиваются за 1 минуту, харнес копируется с FatSecret-eval). Но **ship integration в прод** имеет смысл только при выполнении ВСЕХ:

### 3.1 User-base критерии

| Условие | Зачем |
|---|---|
| **≥20 active users** в целевом регионе (Spain / Mexico / Brazil / India / Russia) | Меньше — не оправдывает поддержку отдельного слоя. Один тестер не делает фичу |
| **≥30 дней** их активного использования (≥10 food-logs each) | Хотим увидеть реальный паттерн потребления, не первый день |
| **≥50 region-specific dish logs/месяц** в целевой стране | Тот же smoke — стоит ли оптимизировать |

Сейчас (2026-06-08): real users `is_bot=false` = **~12 человек**. Из них в EU: 5 UA + 3 ES. В LATAM: 0. **Все критерии ниже floor.**

### 3.2 Eval-результат критерии

| Условие | Зачем |
|---|---|
| **≥15% улучшение медианной точности** на региональном golden-set vs GPT-4o-only | Меньше — sample noise, не стоит implementation complexity |
| **Coverage хотя бы 50%** региональных блюд из реальных логов | Если CIQUAL знает только 20% того что юзеры пишут — не оправдывает |
| **Latency p95 <100ms** на lookup | Local DB query быстрый, но если требует fuzzy-match по имени — может тормозить |

### 3.3 Operational критерии

| Условие | Зачем |
|---|---|
| **Обновляемость**: источник публикует updates с понятной каденцией (раз в год/два) | Иначе ship'ить stale CSV — антипаттерн |
| **Лицензия** позволяет коммерческое использование | CIQUAL/USDA — public domain ✅; BEDCA — нужно проверить |
| **Storage cost разумен** — CSV 1-5 MB на регион, в Supabase легко | Не критерий, но проверить |

---

## 4. План eval (next-session, owner-approved 2026-06-08)

**Цель:** определить, действительно ли CIQUAL/BEDCA точнее GPT-4o на региональных блюдах. Декомпозиция:

### 4.1 Golden-set (один регион за раз — начинаем с Испании, потому что Spain #3 в нашей base)

50 испанских блюд минимум:
- 20 классические (paella, tortilla de patatas, gazpacho, jamón, churros, …)
- 15 LATAM-Spain crossover (Coca-Cola Mexicana, queso fresco, …)
- 10 региональных вариаций (paella valenciana vs paella mixta)
- 5 десертов/завтраков (turrón, chocolate con churros, …)

Reference values — из BEDCA (она сама ground truth).

### 4.2 Прогон

```
для каждого блюда из golden:
    truth_macros = BEDCA[блюдо]
    gpt_macros = GPT-4o.text_query("оцени КБЖУ на 100г: <блюдо>", lang='es')
    delta = abs(gpt - truth) / truth * 100
    log(name, truth, gpt, delta_per_nutrient)
```

### 4.3 Метрики

- Median % error per nutrient (kcal/protein/fat/carbs)
- Coverage rate (сколько из 50 GPT смог идентифицировать)
- Outliers (>30% off) — для каждого нутриента
- Cost per query (text input ~50 токенов, output ~80 токенов = ~$0.0002 → 50 запросов = $0.01)

### 4.4 Решение

| Результат | Действие |
|---|---|
| GPT median ≤5% — лучше или равно BEDCA | NO-GO как FatSecret. Зафиксировать в KB, не строить интеграцию. |
| GPT median 5-15% — заметно хуже на части блюд | Маркировать **conditional GO** — построить fallback только для блюд где разница >20% |
| GPT median >15% — систематически хуже | GO — построить полноценную интеграцию с BEDCA как первичным источником для Spanish-locale text-queries |

### 4.5 ⚠️ Statistical caveat

**N=50 на одну страну — всё ещё малая выборка.** Wide CI. Вывод направления, не вердикт. См. [[food-data-evals]] §1. После активной базы в Испании ≥20 — пересмотреть с N=200+.

### 4.6 ✅ Eval сделан 2026-06-08 — направление найдено

Прогон: 39 dishes / 5 regions (~8 per region). GPT-4o vs reference values из BEDCA / TBCA / IFCT / FGBNU / USDA-SR.

**Полный отчёт:** `tools/macro_eval/results_regional_2026-06-08.md`.

**Headline (median kcal deviation, lower = GPT знает лучше):**

| Регион | kcal dev | Решение по §3 threshold (≥15%) |
|---|---|---|
| IN (Indian) | 5.8% ✅ | NO-GO — IFCT не оправдан |
| BR (Brazilian) | 7.7% ✅ | NO-GO — TBCA не оправдан |
| MX (Mexican) | 11.1% 🟡 | NO-GO (под порогом) |
| **RU (Russian)** | **15.9%** | **CONDITIONAL GO** (gate user-base) |
| **ES (Spanish)** | **16.9%** | **CONDITIONAL GO** (gate user-base) |

**Outliers:** винегрет 67%, horchata 32%, croquetas 31% — GPT-4o уверенно ошибается, видимо путая с близкими блюдами.

**Surprise:** macros (protein/fat/carbs) отклоняются СИЛЬНЕЕ kcal во всех регионах (RU protein 25%, fat 29%; ES protein 21.6%, fat 22.5%). Гипотеза — GPT знает энергетическую плотность ОК, но split хуже. Аргумент для **macro-split-only eval** в будущем (особенно для премиум-юзеров с macro-tracking).

**Decision (owner-pending, default action):**
- Зафиксировать ES + RU в watchlist
- Ship НЕ сейчас (user-base gate не выполнен: 3 ES active, 0 RU active)
- Re-eval с N=50+ когда регион достигнет 20+ active users
- Документация в KB обновлена; интеграция отложена

**Caveat:** N=8/region даёт CI ~±10pp. Real-world median может быть {ES: 7-27%, RU: 6-26%}. Direction reliable, magnitude — нет.

---

## 5. Implementation skeleton (когда readiness-критерии выполнены)

Не делать сейчас. Здесь — для будущего агента, чтобы быстрее построить.

```python
# services/regional_fcdb.py
async def fetch_regional(query: str, lang_code: str, country_code: str) -> ParsedFoodResult | None:
    """Lookup in regional FCDB by fuzzy name match. None on miss/below-threshold."""
    db = _select_db_for_country(country_code)  # 'BEDCA' for ES, 'CIQUAL' for FR, ...
    candidates = await _fuzzy_search(db, query, lang_code)
    best = candidates[0] if candidates and candidates[0].score > 0.8 else None
    if not best:
        return None
    return _to_parsed_food(best)

# Cascade в handle_ai_input (text path), после vision cascade и до FatSecret-fallback:
# 1. cache по точному имени
# 2. regional FCDB lookup (если активна для региона юзера)
# 3. GPT-4o (как сейчас)
```

Storage:
- Таблица `regional_food_db(source, country, food_id, name_canonical, name_localized, kcal_100g, protein, fat, carbs, ...)`
- Индексы: GIN trigram на name_canonical + name_localized для fuzzy
- Заливка: миграция с CSV-импортом + cron на ежегодное обновление

---

## 6. Связь с другими evals и идеями

- **Vision-биас по региону** уже частично сделан в PR #325 (location-в-промпте). FCDB поможет на text-path, vision уже улучшен.
- **Restaurant chains** — параллельная идея, но другой класс источника (Nutritionix, не FCDB). Не путать.
- **Multi-ingredient composite breakdown** — возможно FCDB поможет с борщ-как-сумма-ингредиентов точнее чем GPT целиком. Кандидат на отдельный eval.

---

## Related Concepts

- [[food-data-evals]] — единый hub всех evals (FatSecret сделан, CIQUAL/BEDCA queued)
- [[cascade-macro-enrichment-fatsecret]] §13 — методология предыдущего eval (FatSecret NO-GO)
- [[cascade-macro-enrichment-fatsecret]] §13.1 — statistical caveat: N=20 → нужно ≥100 для CI
- [[food-recognition-prompt-lab]] — vision prompts (другая ось точности)
- [[barcode-logging-openfoodfacts]] — barcode cascade (другой класс источника)
