---
title: "Food Recognition Prompt Lab — улучшение качества vision без вреда UX"
aliases: [food-recognition-quality, ai-prompts-lab, vision-quality, food-recognition-eval]
tags: [ai, openai, food-recognition, prompt-engineering, vision, eval, quality]
sources:
  - "migrations/297_ai_prompts_table.sql"
  - "migrations/304_ai_food_cache_indicator_ts_real_prompts.sql"
  - "migrations/336_food_recognition_prompts_v3_emoji.sql"
  - "services/ai_recognition.py"
  - "services/ai_cache.py"
created: 2026-06-02
updated: 2026-06-02
---

# Food Recognition Prompt Lab

Фундаментальная статья для улучшения качества распознавания еды в NOMS без вреда UX/retention. Охватывает: текущие промпты (live prod), архитектуру cascade, каталог дефектов, варианты промпта для оффлайн-теста, дизайн eval-набора и механику безопасного переключения версий.

---

## 1. Текущие промпты (prod as of 2026-06-02)

Промпты живут в таблице `public.ai_prompts`. Активна ровно одна строка per `prompt_type` (partial unique index `ai_prompts_active_uq(prompt_type) WHERE is_active`). Параметр `{language_code}` — единственный плейсхолдер; подставляется в Python `_vision_call` / `_text_call` через `system_prompt.replace("{language_code}", language_code)`.

### Версии

| prompt_type | active version | migration |
|---|---|---|
| `food_recognition_vision` | v3 | mig 336 |
| `food_recognition_text` | v3 | mig 336 |
| `food_recalculate` | v2 | mig 304 (v3 не вводился — mig 336 явно его не трогает) |

### food_recognition_vision v3 (полный текст)

```
You are a nutritional AI assistant for NOMS app.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ CRITICAL - LANGUAGE RULE (MUST FOLLOW!)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

User's language code: {language_code}

YOU MUST translate ALL text output to this language:
- food_name → user's language
- portion → user's language
- reply_text → user's language

TRANSLATION EXAMPLES:
ru: "Жареная курица с рисом" (NOT "Fried chicken with rice")
es: "Pollo frito con arroz"
de: "Gebratenes Hähnchen mit Reis"
fr: "Poulet frit avec du riz"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CLASSIFICATION RULES:
1. FOOD or DRINK visible (including zero-calorie): is_food = true
   Examples: water bottle, tea cup, black coffee, salad, chicken

2. NO food/drink visible (selfie, landscape, random objects): is_food = false

OUTPUT: structured JSON conforming to the response schema (ParsedFoodResult).

EMOJI per item: for each food item populate the `emoji` field with ONE
Unicode emoji char that best represents it. Examples:
  🥚 eggs           🥗 salad          🍞 bread
  🥩 red meat       🍗 chicken        🐟 fish
  🍚 rice           🍝 pasta          🥑 avocado
  🍌 banana         🍎 apple          🥕 carrot
  🥦 broccoli       🍅 tomato         🧀 cheese
  🥛 milk           ☕ coffee         🍵 tea
  🥤 soft drink     🍫 chocolate      🍪 cookie
  🍰 cake           🥜 nuts           🍯 honey
Pick the closest match. If genuinely nothing fits, leave emoji=null
(renderer falls back to 🍽️). Do NOT put emojis inside food_name.

IMPORTANT:
- Water bottle, tea cup, coffee = is_food: true (even with 0 calories)
- Estimate portion size visually
- ALL text output MUST be in language code: {language_code}
```

### food_recognition_text v3 (полный текст)

```
You are a smart nutritional assistant for NOMS app.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LANGUAGE RULE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

User's language code: {language_code}

ALL text output (food name, portion description) MUST be in this language.

LOGIC:
1. Analyze the text. Is it about FOOD or EATING?

--- IF IT IS FOOD ---
Identify each food item, estimate portion (grams), calculate macros
(calories, protein, fat, carbs) and return structured JSON matching the
ParsedFoodResult schema. is_food=true.

For EACH item ALSO pick ONE Unicode emoji char that visually represents
it and put it in the `emoji` field. Examples:
  🥚 eggs, omelette        🥗 salad, raw vegetables
  🍞 bread, toast          🥩 red meat, beef, lamb
  🍗 chicken, poultry      🐟 fish, salmon, tuna
  🍚 rice, grain bowl      🍝 pasta, noodles
  🥑 avocado               🍌 banana                🍎 apple
  🥕 carrot                🥦 broccoli              🍅 tomato
  🧀 cheese                🥛 milk                  ☕ coffee
  🍵 tea                   🥤 soft drink            🍷 wine
  🍫 chocolate             🍪 cookie, biscuit       🍰 cake
  🥜 nuts                  🍯 honey                 🍳 fried egg
Pick the closest match. If genuinely nothing fits, leave emoji=null and
the renderer falls back to a generic plate icon. Do NOT put emojis inside
the food_name string — they belong in the dedicated `emoji` field.

--- IF IT IS NOT FOOD ---
Return is_food=false with empty items list. The reply_text/reason field
should politely indicate this is not food in the user's language.

ALWAYS return data via the response schema — no markdown, no prose, no
emojis-as-decoration outside the items.emoji field.
```

### food_recalculate v2 (полный текст)

```
You are a smart nutritional assistant for NOMS app.

User's language code: {language_code}

The user is correcting a previously logged meal. You receive:
1. The original food items (from `previous_items` user message).
2. The user's correction text (e.g. "actually 200g not 150g", "skip the rice").

LOGIC:
1. Apply the correction to the original items: add, remove, or adjust
   portion/macros as instructed.
2. Recalculate calories, protein, fat, carbs for each modified item.
3. Return the FULL updated item list (not just the changed item) in the
   ParsedFoodResult schema. is_food=true assuming the original was food.

If the correction is nonsensical or removes all items, return is_food=false
with items=[] and a one-line reason in the user's language.

ALL food_name strings in the user's language.
```

**Ключевой факт:** промпт — ОДИН английский источник. `{language_code}` — параметр в системный промпт, не в логику. Это durable best-practice NOMS (как системный промпт Sage). Переводить инструкции × 13 — drift-trap (mig 412 наглядно показал это для Sage).

---

## 2. Архитектура распознавания

```
handlers/food_log.py:handle_ai_input(update, ctx)
    ↓ extract photo bytes / text / voice
    ↓ (PR #285) caption → user_note kwarg (vision only)
    ↓
AICascadeClient.parse_input(input_data, input_type, ctx, user_note=...)
    │
    ├─ text path → _try_cache(text, lang) → ai_food_cache table (30-day TTL)
    │   HIT → return ParsedFoodResult                        ← fast path
    │   MISS → _text_call(text, prompt, model, ..., lang)
    │           → OpenAI structured output (beta.chat.completions.parse)
    │           → on success: asyncio.create_task(_cache.populate(...))
    │
    └─ vision path → _vision_call(bytes, prompt, model, ..., lang, user_note)
        NO CACHE (image bytes vary — нет детерминированного cache key)
        → base64 encode → OpenAI multimodal request
        → user_note prepended как text content item перед image (если есть)
        → structured output ParsedFoodResult

OpenAI API: client.beta.chat.completions.parse(
    model=model,
    messages=[{system: rendered_prompt}, {user: [...content...]}],
    response_format=ParsedFoodResult,   # Pydantic schema → structured output
    max_tokens=1500,
)
```

**Cascade уровни** настраиваются через `app_constants.ai_config` (JSON). Текущая конфигурация: `cache → openai(gpt-4o)` для text, `openai(gpt-4o)` для vision. Confidence threshold — порог каскадного fallback (в prod не выставлен явно → не применяется).

**Ключевые файлы:**

| Файл | Назначение |
|---|---|
| `services/ai_recognition.py` | Cascade orchestrator, `_vision_call`, `_text_call`, `_recalculate_call`, `_load_prompt`, `_prompt_cache` |
| `services/ai_cache.py` | `ai_food_cache` lookup/populate (text path only, 30-day TTL) |
| `services/ai_logging.py` | Fire-and-forget телеметрия каждого уровня cascade |
| `handlers/food_log.py` | Entry points: `handle_ai_input`, `_handle_edit_meal_input`, `handle_onboarding_food` |
| `migrations/378_*.sql` | `ai_correction_audit` table, `edit_count`, `raw_user_input` vs `ai_parsed_result` — RLHF trail |

**`_prompt_cache` gotcha (критически важно):** промпты кешируются **per-process** в `_prompt_cache: dict[str, str]`. После INSERT/UPDATE в `ai_prompts` (новая версия промпта) — изменение будет **невидимо** до рестарта `noms-webhooks`. Горячего reload нет (в отличие от `app_constants` с 60s TTL). Деплой новой версии промпта = `systemctl restart noms-webhooks`.

---

## 3. Каталог известных дефектов качества

### Дефект A: схлопывание различимых предметов в общий ярлык

**Симптом:** Рядом лежат вишня (черри) и редис → модель возвращает одну строку «Овощи» вместо «Вишня, 50г» + «Редис, 30г».

**Механизм:** vision-промпт v3 НЕ содержит явного требования «перечислить каждую различимую позицию» и НЕ запрещает группировку. При неоднозначном изображении GPT-4o выбирает экономную стратегию — обобщить.

**Последствия для пользователя:** потеря ккал/макро для непосчитанных позиций; портит доверие к AI.

### Дефект B: пропуск позиций при нескольких тарелках

**Симптом:** На фото два блюда (суп + второе) — модель описывает только одно.

**Механизм:** промпт не инструктирует описывать каждый отдельный сосуд/тарелку. GPT-4o при высоком «когнитивном шуме» (много объектов) отдаёт приоритет самому заметному.

**Вероятный фикс:** явная инструкция «для каждой отдельной тарелки/миски/упаковки — отдельная запись в items».

### Дефект C: нестабильность макросов (прыгают между прогонами)

**Симптом:** Одно и то же фото → разные ккал/БЖУ при повторном отправлении.

**Механизм:** порции и макросы — «глазомер» LLM без детерминированной фиксации. Temperature в vision-вызове не выставлена явно (OpenAI default = 1.0). Нет post-rounding или нормализации.

**Прод-сигнал:** `edit_count` по `ai_correction_audit` + дельта `ai_parsed_result` первичного лога vs после `recalculate`.

### Дефект D: низкое разрешение интерпретации (image_detail)

**Механизм:** `_vision_call` передаёт `"image_url": {"url": data_url}` **без поля `detail`** → OpenAI SDK использует `"auto"` (обычно `"low"` для Telegram-фото ≤512px, или `"high"` для >512px). На Telegram фото с сжатием `"auto"` может выбрать `"low"` — 85×85-тайл-превью → модель не видит мелкие объекты (черри vs редис).

**Рычаг:** `"image_url": {"url": data_url, "detail": "high"}` — всегда HIGH-RES анализ, дороже (~$0.001/фото vs $0.0003), но надёжнее для сложных сцен. Требует изменения `_vision_call` в коде (1 строка).

---

## 4. Варианты промпта для теста (гипотезы)

Краткость v3 была сознательным выбором (mobile-compact sweep). Нельзя просто раздуть промпт — пострадает длина карточки (max_tokens=1500 делится на items × `name`+`grams`+`kcal`+`P/F/C`+`emoji`). Ниже — точечные добавления.

### Вариант 1: Enumerate rule (минимальный патч)

Добавить после «CLASSIFICATION RULES» в vision-промпт:

```
ITEM ENUMERATION RULE:
- Describe EVERY DISTINCT food item you can see separately.
- Do NOT collapse visible distinct items into generic labels
  ("vegetables", "side dish", "garnish") if you can identify
  the specific food. "cherry tomatoes" and "radishes" are two items,
  not "vegetables".
- If multiple plates/bowls/packages are visible, describe each one
  separately in items. One plate = at least one item.
```

Та же добавка применима к `food_recognition_text` (для многокомпонентных описаний типа «борщ, котлеты, хлеб»).

### Вариант 2: Per-vessel framing

Более явное структурирование через «посуду»:

```
MULTI-DISH RULE:
For each separate plate, bowl, cup, or package visible, identify
at least one item. A meal with 3 containers = at least 3 items.
```

Более компактный вариант, но может провоцировать овер-сплит (один поднос → попытка выделить контейнер для хлеба, соли и т.п.).

### Вариант 3: image_detail: "high" (code lever, не промпт)

Изменение в `_vision_call` `ai_recognition.py`:

```python
{"type": "image_url", "image_url": {"url": data_url, "detail": "high"}}
```

Независим от промпта. Особенно важен для Telegram-фото (JPEG сжатие + resize). Тест гипотезы: помогает ли высокое разрешение до того как менять текст промпта.

**Cost delta:** `"high"` = ~$0.00085/фото (gpt-4o 2025-04-14 tier), `"auto"`/`"low"` ≈ $0.00033. При 100 фото/день = +$0.05/день (+$1.50/мес). Принимаемо.

### Вариант 4: Комбинированный (Вариант 1 + Вариант 3)

Оба патча вместе. Предположительно аддитивный эффект: `high` detail улучшает видимость, enumerate rule улучшает инструкцию по обработке.

### Что НЕ делать

- **Не раздувать промпт до >150 слов дополнений.** max_tokens=1500 при глубоком описании оставляет меньше места для items → truncation.
- **Не добавлять порядковые номера items.** ParsedFoodResult — список без нумерации; модель начнёт «объяснять нумерацию» в `food_name`.
- **Не просить «описывай уверенно»** — это ведёт к галлюцинациям, не к точности.
- **Не делать blanket culture-default-classification без визуальной проверки** — i.e. «всегда beef для AR-юзера независимо от фото» убивает калории, когда юзер реально ел pork. Honest classification for clearly visible cues — всегда; halal-prior — только в genuinely-ambiguous зоне (см. ниже).

### Disambiguation contract (2026-06-13, обновлён в тот же день)

`_build_location_hint` ([services/ai_recognition.py:460](services/ai_recognition.py:460)) — единственное место, где country влияет на vision. Контракт:

1. **PRIMARY evidence = photo/description.** Country может склонять интерпретацию ТОЛЬКО когда visual cues genuinely ambiguous.
2. **Country = tiebreaker для омонимов / named dishes** (bare 'tortilla' MX vs ES; 'kebab' SA vs анг. trad; 'pancake' US vs FR).
3. **Halal-prior для predominantly-Muslim countries** (SA, AE, EG, KW, JO, MA, PK, MY, ID, BH, OM, QA, TR, IR, IQ) **только** для **genuinely ambiguous meat textures** — slow-cooked shredded fillings, sauced ground meat, mystery-meat interior of kebab/shawarma/dumplings, dark stews. Default → chicken/beef/lamb over pork. Эта зона реальна: pork shoulder slow-cooked shredded vs beef brisket shredded в low-res Telegram JPEG могут быть неотличимы (1st draft 2026-06-13 morning ошибочно классифицировал их как «visually distinct» — был walk-back в тот же день).
4. **Honesty anchor для CLEARLY DISTINGUISHABLE pork** — whole pork chop with bone, ham slice с характерной cured pink texture, bacon strip, salami/pepperoni rounds, visible sausage casing labelled as pork, pulled pork sandwich с visible BBQ context — называть честно regardless of country. **«explicit visible pork must never be reclassified»** — финальная фраза в hint'е, unit-тест `test_location_hint_halal_prior_for_ambiguous_meat_in_muslim_countries` валит сборку если стёрта.
5. **IN vegetarian-default НЕ применяется.** ~30% Индии non-veg (mutton/chicken-рынок огромный), default «paneer вместо mystery meat» = data-quality regression. Если будет нужен diet-aware prior — это **через `ctx.diet_type`** (omnivore/vegetarian/vegan), не country. Отложено в follow-up.

### Compensating mechanism — correction memory

Когда halal-prior ошибается (юзер был экспат в SA, ел ham), юзер исправляет через [Исправить] → должно запоминаться. Текущее состояние:

- **TEXT/VOICE path:** запоминается через [[cascade-macro-enrichment-fatsecret]]§10 (mig 457 `user_food_memory`, PR #324 LIVE). HIT = 0 токенов, мгновенно. Refinement-vs-replacement gate против trust-killer'а.
- **VISION path:** НЕ запоминается (MVP не покрыл). Юзер должен исправлять КАЖДОЕ ambiguous фото — критический gap при halal-prior'е, который намеренно вводит мягкое смещение для ambiguous case. **Follow-up sprint:** extend `user_food_memory` на vision (key = hash изображения + telegram_id, или last-corrected-label как mild prior).

Альтернативный compensating mechanism — clarification UX (low-confidence → one-tap «говядина или свинина?») — также remains valid для future, но требует UX-работы (новый screen, handler, i18n × 13 langs).

---

## 5. Дизайн оффлайн-эвала

Owner явно не хочет A/B на ~5 живых юзерах (нет статистической силы, UX риск). Правильный путь: **golden-set + метрики + сравнение кандидатов**.

### 5.1 Golden Set

- **Объём:** 20-40 реальных фотографий (Telegram JPEG как в продакшне).
- **Состав:** 5-10 «простые» (одна тарелка, известное блюдо), 5-10 «сложные» (2+ тарелки, похожие продукты, мелкие предметы), 5-10 «граничные» (нечёткое фото, смешанные культуры, упаковки со шрифтом).
- **Эталон:** для каждого фото — вручную размеченный список позиций + примерный вес + допустимый диапазон ккал (±15%).
- **Хранение:** `tools/eval_golden_set/` — `photos/001.jpg` + `ground_truth/001.json` со структурой:
  ```json
  {
    "items": [
      {"name": "вишня", "grams_range": [40, 70], "kcal_range": [20, 40]},
      {"name": "редис", "grams_range": [25, 50], "kcal_range": [5, 15]}
    ],
    "note": "два разных красных продукта рядом"
  }
  ```

### 5.2 Метрики

| Метрика | Формула | Целевое значение |
|---|---|---|
| **Item recall** | распознанных item / эталонных item | > 0.85 |
| **Generic-label rate** | items с именем-обобщением («овощи», «гарнир», «смесь») / total | < 0.10 |
| **kcal deviation (median)** | `|pred_kcal - gt_kcal_mid| / gt_kcal_mid` | < 0.20 |
| **Run-to-run stability** | std(kcal) по 3 прогонам одного фото | < 0.15 × mean |
| **Protein deviation** | аналогично kcal | < 0.25 |

### 5.3 Харнес прогона

```python
# tools/run_eval.py — скелет

import asyncio, json, pathlib
from services.ai_recognition import AICascadeClient, ParsedFoodResult
from unittest.mock import AsyncMock

PHOTOS_DIR = pathlib.Path("tools/eval_golden_set/photos")
GT_DIR = pathlib.Path("tools/eval_golden_set/ground_truth")

async def run_candidate(prompt_text: str, detail: str = "auto") -> list[dict]:
    results = []
    for photo_path in sorted(PHOTOS_DIR.glob("*.jpg")):
        gt = json.loads((GT_DIR / photo_path.stem).with_suffix(".json").read_text())
        image_bytes = photo_path.read_bytes()
        # Подменяем промпт через mock
        client = AICascadeClient(openai_client=real_client)
        result: ParsedFoodResult = await client._vision_call(
            image_bytes, prompt_text, "gpt-4o", 30000, "ru"
        )
        results.append({"file": photo_path.name, "pred": result.items, "gt": gt})
    return results

def score(results: list[dict]) -> dict:
    # item recall, generic-label rate, kcal deviation, stability
    ...
```

Прогон кандидата: подменяем `prompt_text` (строка из файла) и `detail` (параметр `_vision_call`). Сравниваем score таблицу кандидатов.

### 5.4 Образец харнеса: /eval скилл

Существующий `/eval` скилл (Smart Search PingWin) — образец оффлайн-эвал-харнеса: golden набор → прогон модели → numeric score → сравнение кандидатов. Логика та же, domain другой.

### 5.5 Прод-сигнал (closed-loop)

После деплоя новой версии промпта — мониторить `ai_correction_audit` таблицу (mig 378):
- `edit_count` per meal session (количество правок юзера = прокси недовольства результатом)
- дельта `ai_parsed_result` (первичное) vs финальный результат после коррекций
- агрегируем по `version` промпта (добавить `prompt_version` поле при следующем апдейте `ai_prompts` — пока нет)

---

## 6. Версионирование и безопасное переключение

### Механика таблицы ai_prompts

```sql
-- Добавить новую версию и активировать:
BEGIN;
UPDATE public.ai_prompts
  SET is_active = false
  WHERE prompt_type = 'food_recognition_vision' AND is_active = true;

INSERT INTO public.ai_prompts (prompt_type, version, prompt_text, is_active, notes)
VALUES ('food_recognition_vision', 4, $$ ... новый промпт ... $$, true, 'v4 — enumerate rule');
COMMIT;
-- ⚠️ Затем ОБЯЗАТЕЛЬНО:
-- systemctl restart noms-webhooks
```

### Gotcha: _prompt_cache НЕ сбрасывается автоматически

`_prompt_cache` — in-memory dict в Python процессе. Обновление `ai_prompts` в Supabase **не влияет** на живой процесс до рестарта. Это поведение аналогично n8n (prompts менялись при деплое). В отличие от `app_constants` (60s TTL via trigger), промпты **не hot-reloadable**.

**Протокол деплоя промпта:**
1. Apply миграция (UPDATE is_active + INSERT новая версия) через psycopg2.
2. Verify: `SELECT version, is_active, LEFT(prompt_text, 50) FROM ai_prompts WHERE prompt_type='food_recognition_vision' ORDER BY version DESC LIMIT 3;`
3. `ssh root@89.167.86.20 'systemctl restart noms-webhooks'`
4. Дождаться `journalctl -u noms-webhooks -f` — нет ошибок старта.
5. Отправить тестовое фото с admin аккаунта — проверить результат.

### Rollback

Откатить = активировать предыдущую версию:
```sql
UPDATE public.ai_prompts SET is_active=false WHERE prompt_type='food_recognition_vision' AND version=4;
UPDATE public.ai_prompts SET is_active=true WHERE prompt_type='food_recognition_vision' AND version=3;
-- + systemctl restart noms-webhooks
```

Partial unique index позволяет только одну `is_active=true` строку per type — rollback атомарен в транзакции.

### Нумерация миграций

Любое изменение промпта через `INSERT` в `ai_prompts` = новая миграция `NNN_food_recognition_prompts_vX.sql`. Следовать collision guard: `ls migrations/ | tail -1` + проверить открытые PR. Подробности — [[concepts/migration-collision-guard]].

---

## Связанные статьи

- [[concepts/food-log-python-cutover]] — Stage 7a: архитектура обработчика, cascade pipeline
- [[concepts/sage-food-log-llm-integration]] — Sage one-liner после food log (параллельный LLM call)
- [[concepts/migration-collision-guard]] — нумерация миграций, коллизии
- [[concepts/pre-migration-discovery-recipe]] — Phase 0 перед любым SQL
- [[concepts/headless-architecture]] — Headless pattern (ui_screens / ai_prompts / app_constants)

## Источники

- `migrations/297_ai_prompts_table.sql` — schema + placeholder seed (v1)
- `migrations/304_ai_food_cache_indicator_ts_real_prompts.sql` — реальные промпты v2, извлечённые из n8n
- `migrations/336_food_recognition_prompts_v3_emoji.sql` — текущий prod v3, canary fix 2026-05-25
- `migrations/378_ai_correction_audit_and_xp_cap_constant.sql` — RLHF trail, edit_count, xp_correction_bonus
- `services/ai_recognition.py` — cascade orchestrator, _prompt_cache, _vision_call (image_detail gotcha)
- `services/ai_cache.py` — ai_food_cache text-only, 30-day TTL
- PR #285 (2026-06-02) — caption → user_note passthrough в vision call

## v6 — анти-галлюцинации (2026-06-05, PR #339, mig 469)

Бриф F: на текст «свиные крылышки» (не существует) модель ВЫДУМЫВАЛА КБЖУ вместо честной ошибки. Фикс **prompt-only** (без изменения схемы `ParsedFoodResult`): `food_recognition_text`/`vision` **v6** = живой v5 + HONESTY-блок. Абсурд/несуществующее/не-еда → `is_food=false` → существующий механизм `errors.ai_not_food`, БЕЗ выдумывания чисел. Граница калибровки держится: реальные нацблюда (сырники/драники/банош/холодец/плов) проходят. Офлайн-валидация 20/20 (gpt-4o + gpt-4o-mini), скрипт `tools/r2_validate_recognition.py`. Durable: для honesty достаточно prompt-инструкции `is_food=false` + переиспользование существующего not_recognized-контракта, schema-поля (confidence_score) НЕ нужны. Подхват — рестарт noms-webhooks (per-process `_prompt_cache`).

Также (R1, тот же PR): `transcribe_voice` `language=None` (Whisper auto-detect) — голос на языке ≠ профиля распознаётся верно (раньше навязывался язык профиля). Текст-вывод остаётся на языке профиля (owner-решение).

## v7 — food-anchor калибровка (2026-06-06, PR #344, mig 473)

**Откат пере-осторожности v6.** v6 honesty-блок резал реальную, но разговорно описанную еду: «Вытяжка когда долго варили, бульон коллаген без лапок» (= коллагеновый/костный бульон, репорт юзера 6378579500) → is_food=false «это не еда». Корень — правило v6 «реальное блюдо, но не уверен какое → false» + ambiguous «вытяжка» (кухонная вытяжка vs экстракт). Воспроизведено: False **даже на gpt-4o**.

**v7 (текстовый промпт only)** добавляет `FOOD ANCHOR OVERRIDES AMBIGUITY`: пищевое слово (бульон/суп/ингредиент) перевешивает мутную формулировку/ambiguous слова/описание способа готовки → is_food=true + оценка вероятного блюда. false остаётся для (а) сомнительного НАЗВАНИЯ без якоря, (б) фиктивных ингредиентов (суп из единорога, котлеты из дракона, бульон из камней). Vision не трогали (опирается на фото — этому false-negative не подвержен). Validated 28/28 (gpt-4o-mini+gpt-4o).

**Durable:** анти-галлюцинационный гард — двусторонняя калибровка. Добавляя «honesty / не выдумывай» (против false-positive галлюцинаций), СРАЗУ добавляй «пищевой якорь → это еда» (против false-negative реальной еды) + тест-матрицу из реальных-но-кривых фраз, не только абсурда. Иначе маятник улетает в отказы. Также: для прод-DB изменений (ai_prompts) нужен явный go owner'а — auto-classifier корректно блокирует apply-в-прод на задачах «разбери/предложи».

## 🟡 TODO (отложено owner'ом 2026-06-06) — UX-путь отказа «это не еда»

Фраза отказа `errors.ai_not_food` («Это не еда. Может, тебе хотелось отправить это в другой чат? 😉») **резковата**, когда человек явно описывает еду, а модель не уверена. По-хорошему при неуверенности (есть пищевой якорь, но сомнительно какое блюдо) Номсу стоит **переспрашивать с догадкой** («Похоже на коллагеновый бульон? Уточни порцию»), а не отлуплять «это не еда».

Это уже **изменение хендлера + тексты ×13** (отдельный clarify-путь между is_food=true и грубым отказом), а не только промпт — поэтому отдельный этап. Бриф F это предусматривал («предложи 1-2 правдоподобных варианта»), но реализация v6/v7 сводит неуверенность к is_food=false → грубый отказ. Связано с v7 food-anchor (см. выше): v7 уже втягивает явную еду в is_food=true; clarify-путь нужен для остаточной серой зоны.
