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

## Связанные
- [[concepts/food-recognition-prompt-lab]] — промпты, дефекты, eval golden-set
- [[concepts/barcode-logging-openfoodfacts]] — barcode-трек, `barcode_cache`, `lookup_product` pluggable
- [[concepts/food-log-python-cutover]] — `handle_ai_input` pipeline
