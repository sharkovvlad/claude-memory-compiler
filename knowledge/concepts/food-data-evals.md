---
title: "Food-data evals — единый hub: что измеряли, что планируем, когда пересматривать"
aliases: [eval-hub, food-evals, macro-evals, nutrition-data-evals]
tags: [eval, accuracy, fatsecret, ciqual, golden-set, statistical-significance]
sources:
  - "daily/2026-06-05.md"
  - "daily/2026-06-08.md"
created: 2026-06-08
updated: 2026-06-08
status: active
---

# Food-data evals — единый каталог

Сводный hub для **всех** evals «насколько точно мы считаем КБЖУ». Чтобы агенты ИИ и owner находили оба (текущие+планируемые) в одном месте и не строили дублирующих стендов.

> **Принцип:** перед интеграцией нового источника данных — eval ПЕРВЫМ. Дёшево, спасает от FatSecret-сценария (потратили сессию на клиент → eval показал no-go → клиент закрыт). См. [[release-protocol]] и lesson PR #337.

---

## Каталог evals

### ✅ Completed

| Дата | Eval | Результат | Detail |
|---|---|---|---|
| **2026-06-05** | FatSecret name-enrichment vs GPT-4o per-100g (PR #337) | 🔴 **NO-GO** (FS не превзошёл GPT-4o + покрытие хуже) | [[cascade-macro-enrichment-fatsecret]] §13 |

### 🟡 Planned / queued

| Когда | Eval | Цель | Брифинг |
|---|---|---|---|
| **Next session** | CIQUAL/BEDCA/IFCT vs GPT-4o на региональных блюдах | Определить, есть ли value в локальных food-composition-БД для региональных кухонь | [[regional-food-composition-databases]] §4 (план + golden-set) |

### 🔮 Future (по triggers)

| Триггер | Eval | Зачем |
|---|---|---|
| Активная база ≥100 DAU | Расширенный golden-set FatSecret re-eval | Текущий N=20 → CI слишком широкий, нужен N=100+ для статистики |
| Новый major LLM (GPT-5, Claude, итд) | Перепрогон существующих evals | Training-data drift, новые capabilities |
| ≥20 active users в одной стране | Региональный eval для этой страны | Когда есть кого обслуживать — мерить точность на их фактических блюдах |
| >180 дней с последнего eval | Просто перепрогон | Provider data drift, prompt aging |
| Жалоба на устойчивую ошибку класса блюд | Добавить класс в golden-set + прогон | Дешёвый ground-truth расширение |

---

## Принципы дизайна evals (durable)

### 1. Sample-size floors

| N | Что это даёт | Когда годится |
|---|---|---|
| 5-20 | Smoke / direction check | Sanity check «может ли вообще работать», как PR #337 |
| 50-100 | Качественный вывод по класcу | «По одиночным англ. ингредиентам — равно/лучше» |
| 100-300 | CI ±5% per dimension | Стат-значимый вывод per region / per category |
| 500+ | Production-grade quality bar | Для ship/no-ship решений на крупной базе |

**Сегодня (2026-06-08):** все наши evals на уровне N=20. Это **направление**, не вердикт.

### 2. Ground truth — где брать

| Тип ground truth | Источник | Применимость |
|---|---|---|
| Лабораторные референсные таблицы | CIQUAL (FR), BEDCA (ES), USDA (US), IFCT (IN), FGBNU (RU) | Generic dishes, ингредиенты |
| Этикетки производителя | OpenFoodFacts, USDA Branded | Брендовые упакованные продукты |
| Опубликованные рецепты с КБЖУ | Cookbooks, Spoonacular composite | Сложные многокомпонентные блюда |
| Owner manual annotation | Сами с весами/анализом | Кейсы где других источников нет |

**Грязный sample (correction-rate из прод-логов) ≠ ground truth** (silent-user bias — KB cascade-macro-enrichment-fatsecret §13).

### 3. Multi-dimension сэмплирование

Eval НЕ должен мерить только одну размерность. Минимум 3 оси:

| Ось | Примеры значений |
|---|---|
| **Категория блюда** | Одиночный ингредиент / Составное домашнее / Бренд / Регион |
| **Локаль** | EN / ES / PT / RU / FA / AR / HI |
| **Тип входа** | text / voice / vision |

Иначе вывод хрупкий: N=20 одиночных англ. text-input говорит ТОЛЬКО о том режиме, ни о чём больше.

### 4. Что мерить (не только per-100g!)

Полный pipeline = **идентификация + порция + макросы**. Каждый уровень даёт свою ошибку:

| Уровень | Ошибка | Метрика |
|---|---|---|
| **Идентификация** | «Это куриный сэндвич, не индейка» | Top-1 / Top-3 accuracy на labeled golden-set |
| **Порция** | «Тарелка ~250г а не 350г» | Mean abs % error на grams |
| **Макросы per 100g** | «Курица 120 ккал, не 165» | Median % error per-100g per nutrient |

FatSecret eval (PR #337) мерил только последний. **Real-world ошибка преимущественно в порции** (owner durable insight, KB §13).

### 5. Eval-harness паттерны

Существующий стенд `tools/macro_eval/`:
- `golden_set.json` — список позиций с reference values
- `run_eval.py` — прогон одного источника против golden-set + печать прод-снимка
- `results_YYYY-MM-DD.md` — датированный snapshot результата

**Расширение для новых evals:** копировать паттерн (`golden_set_regional.json`, `run_regional_eval.py`, `results_regional_YYYY-MM-DD.md`) вместо переписывания общего. Каждый eval — отдельный артефакт, легко сравнивать историю.

### 6. ⚠️ Анти-паттерны

- **«У нас уже есть eval» как заклинание** — указывать N и dimensions. N=20 ≠ доказательство.
- **`correction-rate` как точность** — это «готовность юзера править», silent-user bias заваливает метрику в 0. См. KB §13.
- **Один прогон = вечная истина** — training data провайдеров дрейфует, переmery с каденцией.
- **Eval после интеграции** — наоборот, eval ПЕРЕД построением. Иначе sunk cost мешает no-go решению.

---

## Что ещё стоит замерять (idea backlog)

Размышление 2026-06-08, не приоритизировано:

1. **Cooking-method axis** — Vary/Fried/Boiled/Raw для одного и того же продукта. GPT-4o понимает? CIQUAL имеет отдельные записи. Sample 30 ингредиентов × 3 метода = 90.
2. **Multi-ingredient composite accuracy** — оливье, борщ, рагу. GPT-4o оценивает целиком, CIQUAL/Spoonacular разбивают на ингредиенты. Какой подход точнее?
3. **Restaurant chains** — McDonald's, Starbucks. Nutritionix/MyFitnessPal имеют. Eval бы показал нужно ли отдельный provider.
4. **Vision-only vs text-prompted vision** — гипотеза: добавление текста («куриный салат») к vision-фото даёт точность лучше vision-only. Owner reported это работает (PR #325), но без чисел.
5. **Random-sample manual verification** как замена correction-rate — тэгировать 5 logs/неделя, спрашивать юзера «правильно?», считать ответы. Реальный proxy точности вместо silent-bias correction-rate.

---

## Related concepts

- [[cascade-macro-enrichment-fatsecret]] §13 — FatSecret eval результат (NO-GO)
- [[regional-food-composition-databases]] — план CIQUAL/BEDCA/IFCT eval (queued)
- [[food-recognition-prompt-lab]] — prompts + общий golden-set для распознавания
- [[barcode-logging-openfoodfacts]] — barcode-cascade (другой класс eval — по штрихкодам)
