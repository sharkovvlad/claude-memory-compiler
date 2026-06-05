---
title: "Macro Enrichment via FatSecret/OFF — дизайн, находки, eval-гейт"
aliases: [fatsecret-enrichment, macro-enrichment, cascade-macros, external-nutrition-db]
tags: [ai, food-recognition, fatsecret, openfoodfacts, macros, accuracy, cascade, eval]
sources:
  - "services/ai_recognition.py"
  - "services/barcode.py"
  - "migrations/296_ai_config_extend.sql"
  - "migrations/452_barcode_cache_and_pending.sql"
created: 2026-06-04
updated: 2026-06-04
---

# Macro Enrichment via FatSecret / OpenFoodFacts

Дизайн-док и журнал находок задачи «повысить точность макросов (ккал/Б/Ж/У)» через внешнюю пищевую БД. Дополняет [[concepts/food-recognition-prompt-lab]] (промпты/eval) и [[concepts/barcode-logging-openfoodfacts]] (barcode-трек).

> **Статус 2026-06-04:** Фаза 0 (PR #322) — `temperature` подключён. Фаза 1 (eval) — в работе, блокер: FatSecret API creds. Фаза 2 — gated на результат эвала.

---

## 1. Находки «с полей» (live verify, durable)

### 1.1 `temperature: 0.2` был мёртв (ИСПРАВЛЕНО, PR #322)
`ai_config.temperature=0.2` (mig 296) **не передавался** в `beta.chat.completions.parse` → OpenAI SDK использовал дефолт **1.0**. Это корень «прыгающих» макросов между прогонами (KB prompt-lab §Дефект C). Фикс: `AICascadeClient._get_temperature(ctx)` резолвит из `ctx.constants.ai_config`, clamp `[0,2]`, дефолт 0.2; проброшен keyword-only в три call-метода.

### 1.2 `image_detail: "high"` (УЖЕ сделан, commit d050ce6)
До меня. Полноразмерный vision-анализ. Цена: ~×3 image-токены + latency. Это рычаг **recall позиций**, не стабильности макросов.

### 1.3 🔴 Настроенный каскад СЕЙЧАС не исполняется (НЕ фиксим, owner-решение — задокументировать)
Live `ai_config` хранит уровни как `{"vision": {"cascade": [...]}}` (объект-обёртка), а `AICascadeClient._get_cascade` читает `cfg.get(input_type)` и **ждёт голый список**:
```python
cascade = cfg.get(input_type, [])
if not isinstance(cascade, list) or not cascade:
    return [{"provider": "openai", "model": "gpt-4o", "timeout_ms": 30000}]  # ← срабатывает ВСЕГДА
```
`{cascade:[...]}` — dict → `isinstance(list)` False → **graceful-fallback одним gpt-4o**. Значит настроенные уровни (`fatsecret` 500ms, `gpt-4o-mini` confidence_threshold 0.8 → `gpt-4o`) **не работают**; в проде vision/text идут одним gpt-4o, 30s timeout. Тесты `test_ai_recognition.py` зелёные потому что фикстуры используют **голый список** (старая форма), а не live-обёртку — drift между тестами и продом. Owner (2026-06-04): оставить как есть (один gpt-4o норм), починка `_get_cascade` = смена поведения прода (mini-first), не в скоупе.

---

## 2. Ключевая семантика: enrichment ≠ cascade-level

Зарезервированный хук `if provider == "fatsecret": continue` (`ai_recognition.py`) трактует FatSecret как **уровень каскада** — провайдера-ровню openai, отдающего полный `ParsedFoodResult`. **Это неверная модель.** У FatSecret/OFF:
- нет зрения (не распознают фото);
- не парсят свободный текст в позиции с граммами.

Они умеют только **дотянуть макросы к уже распознанным позициям**. Поэтому правильная точка встройки — **стадия обогащения** поверх `result.items` ПОСЛЕ успешного openai-вызова, НЕ уровень каскада:

```
openai (identify items + estimate grams) → result.items
  → для каждого item: lookup по имени во внешней БД
      match-score ≥ порог → заменить per-100g макросы, scale на item.grams
      иначе/неоднозначно/таймаут → оставить оценку LLM (fallthrough)
  → пересчитать total_kcal/protein_g/fat_g/carbs_g из items
```

Мёртвый хук `fatsecret` в каскаде **не трогаем** (не та семантика) — обогащение конфигурируется отдельным блоком `ai_config.macro_enrichment` (provider, enabled, timeout_ms, min_match_score), hot-reload + флаг отката.

**Где встраивать:** централизованно в `parse_input` (после успешного level-вызова, до return) — тогда оба хендлера (`handle_ai_input` + edit) и все консьюмеры получают обогащённые данные, а тоталы остаются консистентны (`log_meal_transaction` тоталы НЕ пересчитывает — берёт per-item как есть, тоталы считает Python для рендера).

---

## 3. Что даёт FatSecret (честный анализ для owner)

- **Стоимость ИИ НЕ снижает.** LLM всё равно вызывается (идентификация + порция). FatSecret работает ПОСЛЕ → это +вызов/+latency, не замена. Basic free (5000/день) денег не стоит, но gpt-4o-вызов остаётся.
- **Точность — только для уверенно матчащихся позиций:** брендовое/упакованное/стандартные одиночные продукты + мультиязычность (релевантно 13 langs). Домашние блюда → fuzzy-матч шумит. **Порцию (граммы) всё равно оценивает LLM — доминирующий источник ошибки, внешняя БД его не закрывает.**
- **OFF vs FatSecret:** оба восходят к этикетке производителя. OFF = краудсорс (огромное покрытие EU/упаковка, неполные поля, слабо RU/IR, бесплатно). FatSecret = модерируемый гибрид (консистентнее, есть generic/ресторан, мультиязык, OAuth+лимиты). На пересечении значения совпадают → выигрыш двух источников = **покрытие**, не точность.

### FatSecret API (verified 2026-06-04)
Basic free: 5000 вызовов/день, OAuth 2.0 client_credentials (server-to-server), **IP whitelist обязателен** (до 15 IP; VPS `89.167.86.20`). Premier (платно/по заявке): без лимитов, CIDR, NLP-endpoint (текст→еда, пересекается с LLM — не нужен). Ключи — `.env` на VPS, НЕ в git.

---

## 4. Два применения FatSecret (owner выбрал: оба прототипировать в эвале)

1. **name-lookup (мой трек):** обогащение макросов опознанных LLM позиций по названию. Шире охват, но шумный fuzzy-матч + порция от LLM.
2. **barcode 2-й источник (домен barcode-агента, совместно):** barcode-агент уже построил под это — `ProductInfo.source` предусматривает `'fatsecret'`, `lookup_product` = «pluggable source», `barcode_cache.source` колонка. Добавляется FatSecret-fetch-по-баркоду после OFF-miss в `services/barcode.py`, tag `source='fatsecret'`. Дедуп через `UNIQUE(barcode)`. **Точнее name-поиска** (нет fuzzy, нет неоднозначности порции сверх размера упаковки) → возможно лучший первый ROI FatSecret. Порядок источников по `country_code` (RU/IR → региональный/FatSecret).

---

## 5. Edge: кнопка [Исправить] (closed-loop)
`[Исправить]` = recalc (`ai_correction_audit` mig 378). Следствия:
- **Истинная метрика пользы для юзера = correction-rate** (доля правок макросов/блюд) до vs после. Оффлайн-эвал гейтит ship; прод correction-rate подтверждает реальную пользу.
- **Исправления = бесплатный golden-set** реальных ошибок LLM → майнить для эвала.
- **Не переопределять явно введённое юзером** (CLAUDE §3 closed-loop): обогащение масштабирует под скорректированные граммы/переименование, но не спорит с ручной правкой макроса.

---

## 6. Latency (durable нюанс)
Порог **p95 < 700ms — про UI/меню, НЕ про AI-распознавание** (оно многосекундное, за индикатором «печатает», под гейт не попадает). Обогащение: per-item 1–2 FatSecret-вызова (~200–500ms каждый), параллелить по позициям + жёсткий таймаут (~600–800ms) + fallthrough → cache-miss добавляет ≤~0.8с, никогда не блокирует; cache-hit ≈0. `image_detail:high` тоже +0.5–1.5с/+×3 cost.

---

## 7. Eval-гейт (go/no-go перед прод-роллаутом)
- Текстовый golden-set ~30 именованных позиций (одиночные ингредиенты / брендовые / домашние блюда) + эталонные макросы на 100г.
- Метрики: медианное отклонение ккал/Б/Ж/У от эталона, match-rate, доля ложных матчей, run-to-run стабильность; + майнинг `ai_correction_audit`.
- Прогон: LLM-only vs LLM+FatSecret(name) vs barcode+FatSecret — сравнение цифрами. Шум/нет выигрыша → честно «не даёт на наших данных», не катим.

---

## 8. Координация с barcode-агентом (zero-collision)
- **Разные БД:** barcode → OFF → `barcode_cache`; я → FatSecret → name-cache (+ совместный FatSecret-barcode-источник в `barcode.py`).
- Barcode-агент сам зафиксировал границу (его KB §6): «FatSecret = домен другого агента», «не трогать `services/ai_recognition.py`». Я не трогаю `services/barcode.py` кроме совместного 2-источника.
- **Миграции:** следующий свободный номер через `git fetch origin main` + проверка открытых PR прямо перед push (HEAD на 2026-06-04 = mig 456).

---

## 9. Региональная стратегия (owner-driven 2026-06-04)

### 9.1 Принцип, на котором держится всё
Для **домашней/составной еды единого «правильного» макро НЕ существует** — натуральная вариативность + неизвестная порция > разницы между базами. Внешняя БД даёт защищаемый выигрыш ТОЛЬКО где правда объективна:
1. **Брендовое/упакованное** → этикетка (трек штрихкода, точно).
2. **Стандартный сырой ингредиент** (стейк, гречка, яйцо) → базы сходятся в пределах %.
Для составных блюд (борщ, паэлья) БД бесполезна — работает только LLM, и главный рычаг = **правильное определение блюда + порции**, не «дотягивание макросов».

### 9.2 Конфликт «яйцо 70 vs 80 ккал — кто прав?»
Никто и оба: для сырого продукта правда — **диапазон**, не точка (яйцо С2 ~65 / С0 ~105 ккал; юзер категорию не указывает). Правило: **не усреднять — выбрать ОДИН авторитетный источник на регион + допуск ±10–15%**. Где правда точна (бренд/штрихкод) — конфликта нет.

### 9.3 Доминирующая ошибка — порция/состояние, не база
«гречка 100 г» — сухой vs варёный = **×3 по ккал**. Решается уточнением/умным дефолтом, НЕ внешней БД. Держать в голове при оценке выигрыша.

### 9.4 Региональная карта источников (рынки: EU, US, RU, IR, **LATAM-приоритет** ES+PT/Brazil)
| Регион | Сильный источник | Заметка |
|---|---|---|
| EU/US | OFF (упаковка) + USDA FDC (сырое, free, EN/западное) + FatSecret | покрыто |
| LATAM ES (приоритет) | **FatSecret** (локализован: ES/MX/AR) + локация-в-промпт | |
| Brazil PT | FatSecret BR + **TACO** (офиц. таблица, датасет не API → засеять при нужде) | |
| Russia | FatSecret RU + курируемый сид (тип «Скурихин») для дыр | бесплатного API нет |
| Iran FA | почти пусто везде | LLM + маленький курируемый сид |
**Вывод:** FatSecret — единственный источник, локализованный под ВСЕ рынки сразу → основной. Региональные таблицы (TACO и т.п.) добавлять точечно, только где эвал покажет слабость FatSecret. USDA FDC = нейтральный free эталон для теста (не сервис бота).

### 9.5 Архитектурное решение (owner 2026-06-04): рамка сейчас, наполнение под эвал
- Заложить region-aware интерфейс: конфиг «страна → приоритет источников» + код, спрашивающий источник по `ctx.country_code`.
- Наполнять по одному источнику/региону, gated эвалом. Начать с FatSecret + локация-в-промпт.

### 9.6 Локация в промпт LLM (PR #323, stacked на #322 — решено отдельным PR)
`_build_location_hint(ctx)` → `ctx.country_code` + локальное время (zoneinfo) в user-сообщение (vision: content-item; text: префикс). Не в статичный `ai_prompts` (per-request + без рестарт-кэша). **Вероятно главный рычаг точности определения** (тортилья ES/MX, региональные рецепты/порции). Замер в эвале: с локацией vs без.

### 9.7 Канонические тест-кейсы для golden-set (от owner)
борщ с мясом (RU/UA/BY) · борщ постный · тортилья MX (лепёшка) · тортилья ES (картофельный омлет!) · гречка 100г (сухой/варёный — ×3) · стейк 100г. Region-tagged. Эталон: USDA для сырого западного, рецепт/региональная таблица для блюд, **допуск ±10–15%**, не точное совпадение.

---

## 10. Память коррекций (PR #324, mig 457 LIVE — приоритет owner)

«Один раз поправил — бот запомнил для этого юзера». Edge-case: мексиканец ест испанскую тортилью; локация-подсказка склоняет к лепёшке → промах; жать [Исправить] каждый раз = плохой UX.

- **mig 457:** таблица `user_food_memory(telegram_id, normalized_term, language_code, result_json)` + UNIQUE. **Per-user** (правка не течёт другим). Применена+verified на проде.
- **🔑 Реализация = Вариант А (NLM-review 2026-06-04), НЕ «на 100г»:** ключ = ТОЧНАЯ нормализованная строка ввода; `result_json` = ПОЛНЫЙ снапшот скорректированного блюда (абсолютные граммы/ккал), отдаётся как есть. Нет «макросов на 100г», нет регулярок для веса, LLM не зовётся. «тортилья»→HIT; «тортилья 200г»→другая строка→MISS→LLM. Зеркало `ai_food_cache`, но per-user + абсолютный приоритет. (Вариант Б — база на 100г + bias в промпт без пропуска LLM — возможное будущее для «тортилья 150г vs 200г», НЕ в MVP.)
- `services/user_food_memory.py`: `lookup`/`populate` (PostgREST, тот же `ai_cache._normalize` → консистентный ключ), `fetch_origin` (читает исходный термин ДО `replace_meal_transaction`, который затирает `food_logs.raw_user_input` текстом коррекции — **критичный порядок!**), `is_rememberable` (MVP-гейт). Fail-open.
- `parse_input` (text): память консультируется **до** глобального `ai_food_cache` и LLM. HIT = мгновенно + 0 токенов.
- `_handle_edit_meal_input`: захват origin до replace + fire-and-forget populate после успешной подходящей коррекции.
- **Охват MVP:** text/voice, одноайтемные. Vision/мульти-айтем — позже. **Не трогал** `get_meal_by_id`/`replace_meal_transaction` (origin = изолированный select) → миграция = только таблица.
- **3 слоя защиты от mis-ID** (тортилья): (1) локация=soft tie-breaker PR #325; (2) прозрачный вывод допущения (отдельный PR, план); (3) **память коррекций (этот) = ответ на «не жать каждый день»**.
- Follow-up: GDPR scrub в `cron_anonymize_deleted_users`.
- **🔴 Урок (real-test 2026-06-05): WRITE зависел от edit-флоу в Python.** Изначально правки шли в ЛЕГАСИ n8n (`reason='editing_meal'` не проходил Python-гейт `startswith(food_media|text_food)` → fall-through). Мой populate в `_handle_edit_meal_input` не вызывался → память не наполнялась. Починилось когда ДРУГОЙ агент сделал edit-meal Python cutover (Phase 5, handover `2026-06-05_edit_meal_python_cutover.md`, KB `stage7-global-cutover §поправка-06-05` «merged-but-unwired»). **Урок: проверять РОУТИНГ (не только что хендлер существует) — фича может быть merged, но un-wired.**
- **🔴 Refinement-vs-replacement (PR #329, real-test): помнить только УТОЧНЕНИЯ, не замены.** Наивный «помнить любую правку» дал `яблоко→pera` → «яблоко» стало выдавать грушу (trust-killer). `is_refinement(origin_term, corrected_name)` = каждое слово ввода юзера есть в исправленном названии (token-subset): `борщ⊆борщ с мясом`✅, `tortilla⊆tortilla española`✅, `стейк=стейк`(порция)✅, `яблоко⊄pera`❌. Гейт = `is_rememberable AND is_refinement`. Best-practice: precision>recall (false-negative безвреден, запомнить замену — вред). Cross-script = safe-negative. **Будущее (Big Tech, не MVP): bias-LLM вместо hard-override (адаптивно к порции + сам разрулит refinement/replacement) + transparency-лейбл «(recordado)» на карточке.**

## 11. Статус PR (2026-06-04)
- **#322 temperature → MERGED в main.** ✅ (база теперь содержит `_get_temperature`).
- **#323 location** — ⚠️ авто-mis-merge: GitHub смержил его в уже-удалённую base-ветку #322, НЕ в main → location в main НЕ попал. Урок в [[concepts/stacked-pr-base-change-gotcha]]. Заменён **#325** (те же коммиты, rebase на main, base=main).
- **#324 correction memory** — open, base=main, mig 457 LIVE.
- **#325 location (soft tie-breaker)** — open, base=main.

## 12. FatSecret client + live match-quality preview (PR #335, 2026-06-05)

`services/fatsecret_client.py` — read-only lookup (OAuth2 token-кэш, foods.search → Jaccard-ранг с singular/plural-норм + prefer Generic → парс «Per Ng» → per-100g, fail-open). 7 unit + live-smoke с VPS.

**🔬 Реальные данные (превью эвала, дёшево):**
- ✅ англ. одиночные: chicken/steak/buckwheat/oatmeal/tortilla/apple → Generic, score 1.0.
- 🔴 **кириллица (гречка/борщ) → НЕТ матча** — FatSecret search англоцентричен.
- порция/состояние всё ещё двусмысленны (buckwheat=сухой 343, oatmeal=варёный 62).
- live-промах сингуляр/плюрал («apple»→«Apples») починен нормализацией.

**🔑 Durable дизайн-инсайт для enrichment:** lookup делать по **АНГЛ. каноническому имени**, не по локализованному (LLM может вернуть `name` для показа + `name_en` для lookup). По кириллице/локали FatSecret не находит → для RU/IR name-enrichment либо через англ-канон, либо регион-источник, либо skip (fallthrough на LLM). Это уточняет региональную карту §9.4.

## Связанные
- [[concepts/food-recognition-prompt-lab]] — промпты, дефекты, eval golden-set
- [[concepts/barcode-logging-openfoodfacts]] — barcode-трек, `barcode_cache`, `lookup_product` pluggable
- [[concepts/food-log-python-cutover]] — `handle_ai_input` pipeline
