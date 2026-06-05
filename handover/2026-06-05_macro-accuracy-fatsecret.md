# Handover 2026-06-05 — Точность макросов / FatSecret enrichment

Брифинг для следующего агента на треке «повысить точность ккал/БЖУ». Полный дизайн
+ находки — KB [[concepts/cascade-macro-enrichment-fatsecret]]. Здесь — стартовый
5-минутный контекст.

## Что УЖЕ ЖИВОЕ (merged + deployed 2026-06-05)

| PR | Что | Эффект |
|---|---|---|
| #322 | `temperature=0.2` подключён в OpenAI-вызовы (был мёртв → дефолт 1.0) | стабильность макросов между прогонами |
| (ранее) | `image_detail:high` для vision | recall мелких позиций |
| #325 | страна+локальное время в промпт (soft tie-breaker) | определение блюда (тортилья ES/MX) |
| #324 (mig 457) | per-user `user_food_memory` — память коррекций | повтор лога = HIT, 0 токенов |
| #329 | refinement-гейт (помнить уточнения, не замены) | защита от «яблоко→груша» |
| #458 | GDPR scrub `user_food_memory` в `cron_anonymize_deleted_users` | приватность |

**Архитектура памяти (Вариант А):** ключ = точная нормализованная строка ввода;
`result_json` = полный снапшот скорректированного блюда; читается в `parse_input`
ДО глобального `ai_food_cache`+LLM; пишется в `_handle_edit_meal_input` при
`is_rememberable AND is_refinement`. Live-проверено на 417002669 (`борщ→борщ с мясом`).

## Что СЛЕДУЮЩЕЕ (не начато)

1. **Eval-стенд** (испытательный стенд, запуск с VPS — FatSecret только с whitelisted IP):
   region-tagged golden-set (6 owner-кейсов: борщ с мясом / борщ постный / тортилья MX /
   тортилья ES / гречка 100г сухой-vs-варёный / стейк 100г + LATAM). Сравнить LLM-only vs
   LLM+локация vs LLM+FatSecret. Метрики: отклонение ккал/БЖУ (±10-15% допуск), match-rate,
   ложные матчи, latency. Эталон = USDA FDC (нейтральный, не FatSecret). **Это go/no-go гейт
   перед прод-роллаутом enrichment.**
2. **FatSecret enrichment** (после эвала): стадия обогащения макросов опознанных LLM позиций.
   **enrichment ≠ cascade-level** (хук `if provider=='fatsecret'` в `ai_recognition.py` — НЕ та
   семантика, не трогать). Стадия ПОСЛЕ openai, fallthrough на LLM, пересчёт тоталов, конфиг
   `ai_config.macro_enrichment` + флаг. Owner выбрал **2 применения, прототипировать оба:**
   (a) name-lookup; (b) **barcode-2й-источник** (домен barcode-агента, `services/barcode.py`
   `lookup_product` pluggable, `barcode_cache.source` предусматривает 'fatsecret' — делать
   СОВМЕСТНО, точнее name-поиска).
3. **Прозрачный вывод допущения** (отдельный PR): «Гречка 150г (сухой 50г) — 180 ккал» —
   поле `portion_note` в схеме + промпт + рендер карточки. Owner: параллельно эвалу.

## Ключевые решения owner (durable)

- **Регион:** рамка region-aware сейчас (конфиг страна→приоритет источников), наполнение под
  эвал. FatSecret основной (локализован под ВСЕ рынки: EU/US/RU/IR/**LATAM-ES**/Brazil-PT).
  Региональные таблицы (TACO Brazil, RU-сид) — точечно где эвал покажет дыру.
- **Принцип:** для домашней/составной еды нет единой правды (±10-15%); доминирующая ошибка =
  порция/состояние (гречка сухой/варёный ×3), не база. Внешняя БД выигрывает на брендовом/
  упакованном (штрихкод) + сырых одиночных ингредиентах.
- **FatSecret НЕ снижает стоимость ИИ** (LLM всё равно зовётся для идентификации+порции).
- **Истинная метрика пользы для юзера = correction-rate** (`ai_correction_events`/edit_count) до vs после.

## Gotchas / durable

- 🔴 **Настроенный каскад dormant:** live `ai_config` = `{"vision":{"cascade":[...]}}`, а
  `_get_cascade` ждёт голый список → graceful-fallback ВСЕГДА → прод = ОДИН gpt-4o. mini-first/
  пороги/fatsecret-уровни НЕ работают. Owner: **не чинить** (починка = смена поведения прода), документ.
- 🔴 **merged-but-unwired:** фича может быть смержена, но не в живом потоке (роутинг). Память
  коррекций WRITE простаивал, пока edit-meal не мигрировал на Python (Phase 5). Проверять РОУТИНГ.
- **FatSecret creds:** в `.env` (worktree+VPS `/home/taskbot/noms/.env`), НЕ в git. Basic free
  5000/день, OAuth2 client_credentials, **IP whitelist обязателен** (VPS 89.167.86.20, активен).
  Реальные вызовы/бенч — ТОЛЬКО с VPS.
- **Координация с barcode-агентом:** разные БД (он OFF→`barcode_cache`, я FatSecret→name-cache);
  его KB §6 зафиксировал границу; совместный FatSecret-barcode-источник — в `barcode.py`.

## Файлы
`services/ai_recognition.py` (cascade, `_build_location_hint`, `_get_temperature`, `_try_user_memory`),
`services/user_food_memory.py` (lookup/populate/fetch_origin/is_rememberable/is_refinement),
`handlers/food_log.py` (`_handle_edit_meal_input` write-path), migrations 457/458.
