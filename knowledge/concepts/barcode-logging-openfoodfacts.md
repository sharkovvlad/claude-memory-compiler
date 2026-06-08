---
title: "Barcode Logging — packaged food via EAN → OpenFoodFacts (Python MVP)"
aliases: [barcode-logging, barcode-scan, openfoodfacts, off-lookup, ean-decode, packaged-food-log]
tags: [food-log, barcode, openfoodfacts, python-handler, ai-recognition, content-type, mvp-design]
sources:
  - "daily/2026-06-03.md"
  - "daily/2026-06-05.md"
  - "daily/2026-06-07.md"
  - "daily/2026-06-08.md"
created: 2026-06-03
updated: 2026-06-08
status: active
---

# Barcode Logging — packaged food via EAN → OpenFoodFacts

> **Design + field-findings article** для фичи «лог упакованной еды по штрихкоду».
> Owner-approved 2026-06-03. Полностью на Python (НЕ n8n). MVP-spec ниже + 3 находки
> «с полей», которые должны знать параллельные агенты (особенно FatSecret/каскад-агент).

---

## 1. Зачем (продуктовая ценность)

Сейчас все макросы считает GPT-4o «на глаз» (нестабильны между прогонами, см.
[[food-recognition-prompt-lab]] дефект C). Для **упакованной** еды есть точный
источник — КБЖУ с этикетки производителя. Barcode-лог даёт:

1. **Точность↑** — цифры производителя вместо оценки LLM.
2. **Стоимость↓** — при попадании в базу GPT-4o-vision **не вызывается** (0 токенов),
   только бесплатный HTTP в OpenFoodFacts (OFF).

---

## 2. Ключевое архитектурное решение: barcode ≠ новый тип контента

**Штрихкод — это новая ВЕТКА обработки уже существующего типа «фото», гейтированная
статусом пользователя, а НЕ новый класс контента.**

Почему это критично (см. [[content-type-classification]]): фото-штрихкода во всех трёх
классификаторах остаётся `food-media` (индикатор=True, маршрут=`ai`). Инвариант
«индикатор ⟺ распознавание» НЕ нарушается — штрихкод тоже распознавание еды.
→ **НЕ нужно добавлять новый класс во все три классификатора и рисковать их дрифтом.**
Вся новизна — одна ветка внутри `handlers/food_log.py:handle_ai_input`, выбираемая по
`users.status == 'waiting_for_barcode'` (либо по факту успешного локального декода).

И второе: barcode-путь производит обычный **`ParsedFoodResult`** (та же Pydantic-схема
из `services/ai_recognition.py`, что отдаёт LLM-каскад). Поэтому весь downstream —
`log_meal_transaction` (принимает готовые `p_food_items` с явными kcal/Б/Ж/У;
`p_input_source='barcode'`), рендер карточки, Sage, мана/XP — **остаётся без изменений**.
Barcode просто заменяет источник `ParsedFoodResult` с «LLM на глаз» на «цифры с этикетки».

---

## 3. Декодер: zxing-cpp (НЕ pyzbar)

| Вариант | Системная зависимость | Вердикт |
|---|---|---|
| `pyzbar` | требует `apt install libzbar0` на VPS | ❌ `./deploy.sh` = rsync, apt-пакеты не ставит → лишний ручной шаг + «работает локально, падает на проде» |
| **`zxing-cpp`** | **нет** (pip-wheel с нативным кодом) | ✅ ставится через `requirements.txt`, читает EAN-13/8/UPC-A + QR, checksum-валидация |

Деп: `zxing-cpp` + `Pillow` (загрузка JPEG-байт в image). Обе — pip-wheels, без apt.
⚠️ **Проверить:** деплой-пайплайн должен делать `pip install -r requirements.txt` на VPS.

**«Лёгкий ИИ для отличия штрихкода от котлеты» НЕ нужен** (owner предлагал — push back):
локальный декодер И ЕСТЬ дешёвый надёжный роутер. EAN имеет контрольную сумму →
ложные срабатывания ≈ 0. Логика:
- Прочитался валидный EAN → barcode-путь (OFF).
- EAN не прочитался (прислали котлету / размытый кадр) → **молча в обычный vision**.

Это дешевле (десятки мс, 0 токенов) и надёжнее ИИ-классификатора.

**QR-коды:** QR ≠ товарный код. Код товара = полосатый 1D EAN-13/8/UPC. QR на упаковке
обычно URL/маркетинг, не GTIN. zxing читает и QR — используем payload, ТОЛЬКО если это
цифровой GTIN (редко); иначе QR бесполезен → fall-through в еду/подсказку.

---

## 4. Поток (MVP, owner-approved)

```
Reply-кнопка [🔎 Штрихкод]  (рядом с [➕ Добавить еду])
  → status='waiting_for_barcode' + промпт «Наведи камеру на штрихкод и пришли фото»
  → юзер шлёт фото (индикатор-стикер показывается — фото = food-media везде)
  → handle_ai_input, ветка barcode:
       decode (zxing): EAN-13/8/UPC | QR-с-GTIN
         ├─ нет кода → обычный vision (вдруг котлета) → существующий путь
         └─ EAN есть → barcode_cache → miss → OpenFoodFacts (по users.country_code)
               ├─ не найдено → ОТКАТ на обычный vision (owner-выбор; юзер всё равно получит лог)
               └─ найдено → вес упаковки из OFF (product_quantity)
                     ├─ вес известен → карточка «[product] — [X ккал]. Упаковка [N г]. Съел всю?»
                     │      [✅ Да, всю упаковку (N г)]  + «или пришли вес/скажи голосом»
                     └─ вес неизвестен → «Сколько грамм?»
                     → дешёвая LLM парсит текст/голос порции (см. §5) → grams
                     → существующий log_meal_transaction (input_source='barcode') → карточка/Sage/мана
  → status='registered'
```

Экономика: 1 barcode-лог = 1 мана (переиспользуется существующий путь лога).

---

## 5. Порция: дешёвая LLM парсит ответ (owner-decision)

Owner: после нахождения товара дать кнопку `[✅ Да, всю упаковку]` (детерминированный
fast-path по `product_quantity`) И принимать свободный ответ текстом/голосом. Свободный
ответ прогоняется через **дешёвую модель** (mini-tier) с узкой задачей:
`{mode: whole|grams|fraction, value}` — «да всё съел»→whole, «половину»→fraction 0.5,
«грамм 30»→grams 30. Голос → транскрипция (как обычный voice) → тот же парсер.

Нюанс жидкостей: OFF nutriments per 100 g, но напитки в упаковке в `ml`. Если
`product_quantity` в граммах есть — берём его; иначе ml≈g (плотность ≈1) с пометкой в коде.

---

## 6. Координация с FatSecret/каскад-агентом ⚠️

**FatSecret — домен другого агента** (провайдер каскада, хук
`services/ai_recognition.py:205` `if provider == "fatsecret": continue`, сейчас
`enabled=false`). Чтобы НЕ пересечься:

- Barcode-MVP — на **OpenFoodFacts** (открытый, без ключа, не зависит от его кода).
- Источник данных делаю **плагинным** (`services/barcode.py`, интерфейс «EAN → продукт»),
  чтобы позже FatSecret-lookup-по-штрихкоду добавился как 2-й источник — вместе с тем агентом.
- **Общий `barcode_cache`** (см. §7) — единый кэш для любого источника.
- **НЕ трогаю `ai_recognition.py`** и систему каскад-провайдеров.

OFF vs FatSecret: OFF = open/free/no-key/краудсорс/слабее RU; FatSecret = коммерческий
OAuth API, шире бренды + barcode-lookup, free-tier с rate-limit. Phase 2: мульти-источник
по `country_code` (RU/IR → региональный / FatSecret).

---

## 7. 🔴 Находки «с полей» (live ≠ NLM/MEMORY) — для всех агентов

### (а) Таблица `barcode_cache` УЖЕ существует в проде — orphan

Live-БД содержит готовую таблицу под ровно эту фичу:
`id, barcode, barcode_type, product_name, brand, calories, protein, fat, carbs,
serving_size_g, source, country_code, image_url, created_at, updated_at` (0 строк).
**Но:** её не создаёт ни одна миграция в репозитории, на неё не ссылается ни код, ни RPC.
Создана вручную в Supabase прошлым агентом и брошена. → Узакониваю миграцией
`CREATE TABLE IF NOT EXISTS` + RPC get/upsert, переиспользую как кэш OFF.

### (б) Контракт-тест классификации — ФАНТОМ (CI сломан на main)

`.github/workflows/pr-content-classification.yml` (PR #305, merged) запускает
`pytest tests/test_content_classification_contract.py …`, **но самого файла на `main` НЕТ.**
Тест остался на невмерженной ветке `claude/content-classification-fix` (коммит `14d3a17`,
26 кейсов). PR #305 вмержил ТОЛЬКО workflow-yml. Следствие:
- Анти-дрифт-защита, на которую MEMORY/KB ссылаются как на «есть и пинит инвариант»,
  **не работает** на main.
- **Любой PR**, трогающий `dispatcher/router.py`/`telegram_proxy.py`/`handlers/food_log.py`/
  `handlers/location.py`, запускает этот CI-job → он **падает на сборе** (file not found).
→ Восстанавливаю тест из `14d3a17` в barcode-PR (+ barcode-кейс). Быстрый фикс для ВСЕХ —
cherry-pick `14d3a17` в main отдельным PR. См. [[content-type-classification]] §5.

### (в) NLM соврал про `workflow_states` — live прав

NLM заявил: таблицы `workflow_states` нет, FK `users.status` нет. **Live:** таблица есть,
FK `users_status_fkey` (users.status → workflow_states.state_code) есть. Значит новый статус
`waiting_for_barcode` **обязан** быть строкой в `workflow_states` (иначе 23503) — ровно как
предупреждает MEMORY/CLAUDE.md. `screen_id` nullable (30 статусов с NULL, вкл. `editing_meal`)
→ экран-приглашение в `ui_screens` НЕ обязателен; повторяю runtime-статус-паттерн `editing_meal`.
Подтверждение durable-правила [[memory-claim-vs-live-verification]]: trust live, не NLM.

---

## 8. Реализация (ГОТОВО — PR #316, mini-PR #313)

**Статус 2026-06-03:** код написан, оба PR открыты, **не смержены** (ждут апрува owner).
- **mini-PR #313** — восстановление фантомного контракт-теста (§7б), ALL GREEN. Мержить ПЕРВЫМ.
- **PR #316** — сама фича. Green кроме contract-CI (файл живёт на #313 → green после merge #313 + rebase #316).

**Миграции (ИТОГ — 452/453 после двойной collision-renumber, см. ниже):**
- **mig 452** `barcode_cache_and_pending` — `CREATE TABLE IF NOT EXISTS barcode_cache`
  (узаконен orphan) + `users.pending_barcode` + 5 RPC: `get_barcode_cache`,
  `upsert_barcode_cache`, `set_barcode_pending`, `get_barcode_pending`, `clear_barcode_pending`.
- **mig 453** `barcode_reply_button_and_copy` — статус `waiting_barcode_portion`
  (screen_id NULL, FK workflow_states); `icon_barcode='🔎'` в `app_constants`;
  `build_main_reply_keyboard` += scan_barcode в row 1; 5 UI-ключей ×13:
  `buttons.scan_barcode` (БЕЗ эмодзи — icon_const_key даёт 🔎),
  `buttons.barcode_whole_package`, `messages.barcode_prompt`,
  `questions.barcode_portion_pack`/`questions.barcode_portion_grams`.
  ⚠️ **Применять к LIVE только вместе с Python-деплоем** (кнопка становится видимой сразу).

**Финальный поток (prod-spec):** auto-detect — ЛЮБОЕ фото в `handle_ai_input` сначала
`decode_barcode`; EAN+OFF found → `set_barcode_pending` + портион-промпт (whole-pack кнопка
если `product_quantity` известен, иначе спросить граммы) → ответ (callback `cmd_barcode_whole`
/ текст / голос; голос транскрибируется; свободный текст → `gpt-4o-mini` portion-parser) →
`product_to_parsed_result` → `log_meal_transaction` `input_source='barcode'` → clear pending.
Кнопка [🔎 Штрихкод] = просто промпт (без статуса; фото auto-detect'ятся в любом статусе).

**Python:** `services/barcode.py` (новый, изолирован от каскада); ветки в
`handlers/food_log.py:handle_ai_input` + `_handle_barcode_portion` + `_log_parsed_result`
(additive, существующий new-log блок не тронут); 1 правило в `dispatcher/router.py` (4k.5,
whole-pack callback перед generic menu); `requirements.txt` (+`zxing-cpp`, `Pillow`).
**Кнопка не потребовала router-правки** — reply-text падает в default text→ai, где
`handle_ai_input` ловит её по `_is_barcode_button_text`. Три классификатора НЕ тронуты.
30 тестов (23 unit + 7 flow) зелёные; миграции validated через `BEGIN…ROLLBACK`.

**Не трогать:** `services/ai_recognition.py` (домен FatSecret/каскад-агента).

### 🔴 Lesson: двойной §12 stale-base collision за одну сессию

Main ушёл вперёд ДВАЖДЫ во время сессии (агенты мержили 447→449). Симптомы на ОБОИХ PR:
(1) migration-collision CI (мои 448/449 ↔ чужие 448/449 уже на main); (2) diff-sanity CI
«deleted N migration files» (ветка от старого base → чужие свежие миграции выглядят как
удаление). Fix по протоколу: `git fetch origin main && git rebase origin/main`, renumber
моих 448→452/449→453 (`git mv` + sed внутр. рефов «Migration NNN»/«mig NNN»),
`--force-with-lease`. **Durable: брать номер миграции + rebase НЕПОСРЕДСТВЕННО перед push,
не в начале сессии** (KB [[migration-collision-guard]]). Контракт-тест из #313 тоже потребовал
rebase (база устарела на 447).

---

## Related Concepts

- [[content-type-classification]] — 3 классификатора; barcode НЕ добавляет класс (ветка по статусу)
- [[food-recognition-prompt-lab]] — текущее vision-распознавание, дефект C (нестабильные макросы)
- [[food-log-python-cutover]] — handle_ai_input, log_meal_transaction, dumb-renderer
- [[memory-claim-vs-live-verification]] — trust live, не NLM (находка в)
- [[migration-collision-guard]] — номер миграции, fetch+rebase перед push
- [[copywriter-playbook]] — ×13 тексты, ≤18 ch/кнопка, anti-shame
- [[food-data-evals]] — eval-hub: FatSecret done, CIQUAL/BEDCA queued, статистические floors
- [[regional-food-composition-databases]] — план для CIQUAL/BEDCA на text-path региональных блюд (deferred + readiness criteria)
- [[cascade-macro-enrichment-fatsecret]] §13.1 — caveat: N=20 → не финальный вердикт

---

## 9. 🔴 Critical gotcha: Python AI gate не включал barcode flows (2026-06-05)

**Симптомы:** после успешного сканирования — [Вся упаковка] молчит, текст порции даёт "Мой процессор перегрелся", повторный [🔎 Штрихкод] тоже ошибка.

**Причина:** Python AI gate в `webhook_server.py` проверял:
```python
and (ctx.status or "") in ("registered", "editing_meal")
```
Статус `waiting_barcode_portion` — не в списке → все barcode-действия падали в n8n.
Кроме того, reason=`barcode_portion` не входил в `startswith(("food_media","text_food"))` → тоже мимо.

**Fix (PR #341):** добавить `_is_barcode_portion` и `"waiting_barcode_portion"`:
```python
_is_barcode_portion = _ai_reason == "barcode_portion"
if (
    target == "ai"
    and (
        _ai_reason.startswith(("food_media", "text_food"))
        or _is_edit_recognition
        or _is_barcode_portion          # ← новое
    )
    and (ctx.status or "") in ("registered", "editing_meal", "waiting_barcode_portion")  # ← новое
):
```

**Правило для будущих статус-based handlers:** при создании нового `waiting_*` статуса — **обязательно** проверить, что Python gate в `webhook_server._try_authoritative_path` пропускает все reason'ы, которые могут прийти в этом статусе. Паттерн роутера: text/voice в `waiting_X` → reason=`X_portion`; photo → reason=`food_media` но status=`waiting_X`; callback → reason=`X_portion`. Всё это должно матчить gate.

**Дополнительно исправлено:**
- Стикер "думающий Номс" при нажатии [🔎 Штрихкод] — был зомби (ранний return ПЕРЕД `finally`-блоком). Fix: явный `await sticker_module.delete_thinking(telegram_id)` перед возвратом `_barcode_prompt_envelope`.
- Нечитаемое фото в `waiting_barcode_portion` → retry message вместо vision fallback → fog "не еда".
- Тексты `messages.barcode_prompt` (mig 470): "Наведи камеру" → "Сделай фото штрихкода и пришли его." × 13.
- Новый ключ `messages.barcode_scan_retry` × 13 для retry UX.

---

## 10. Регионализация / crowd correction (2026-06-07, PR #341)

Три улучшения для LATAM (Spain уже #3 среди real users) и для weak-coverage regions (RU/IR/IN/AR). Без миграций БД.

### 10.1 Локализованные имена продуктов

OFF отдаёт `product_name_<lc>` для каждого языка, где community локализовала продукт. Раньше мы брали `product_name` (default) + `product_name_en` — для LATAM/RU юзеров часто приходило французское/английское имя.

**Реализация:**
- `_OFF_FIELDS` запрашивает все 13 lang-полей (`product_name_es`, `product_name_pt`, ...)
- `_pick_localized_name(product, lang_code)`: приоритет `product_name_<user-lang>` → default → English
- `_parse_off_product` принимает `lang_code=` параметр и вызывает `_pick_localized_name`

### 10.2 Региональный фильтр (lc + cc)

OFF API поддерживает `lc` (язык) и `cc` (страна) query params. Для barcode v2 endpoint основные эффекты:
1. Server-side приоритизация локализованных полей в ответе
2. Если у продукта есть региональные варианты рецептуры (Coca-Cola Mexico vs EU) — OFF выбирает регионально-релевантный

**Реализация:** `fetch_openfoodfacts(barcode, *, lang_code, country_code)` → `params["lc"]=lang_code; params["cc"]=country_code.lower()`. Подцеплено к `users.language_code` + `users.country_code` через `_try_barcode_lookup`.

**Замечание про источник региональности:** Telegram стрипает EXIF из фото (privacy), поэтому GPS-координаты съёмки до нас не доходят. Источник правды — `users.country_code` из онбординга. Эту параллель часто хотят установить — нет, не работает.

### 10.3 Self-learning кэш — crowd correction (как Yuka/MyFitnessPal)

Когда юзер делает «Исправить» на блюде с `input_source='barcode'` И **не меняет порцию** (только КБЖУ) — исправленные значения пересчитываются в per-100g и upsert'ятся в `barcode_cache` с `source='user_corrected'`. Следующий юзер в любой стране, отсканировавший тот же штрихкод, получает выверенные данные.

**🔑 Критичная защита — `is_macro_correction(original_portion, corrected_grams)`:**
- Same-portion edit (±10%) → пишем в кэш (юзер исправил данные продукта)
- Different-portion edit → НЕ пишем (юзер исправил порцию, его per-portion math нерелевантен для per-100g shared base)
- Unparseable original portion → НЕ пишем (defensive)

**Дополнительные guard'ы:**
- Только single-item meals (`len(result.items) == 1 and len(old_items) == 1`) — multi-item обычно name-only correction
- Только GTIN-checksum-valid `origin_raw_text` (defensive — не любой текст в raw_user_input принимаем как штрихкод)
- `p_serving_size_g=None` в upsert — НИКОГДА не перетирать manufacturer pack weight юзерским вводом
- `p_brand=None` — user edit не сообщает бренд
- Fire-and-forget везде (`asyncio.create_task`) — не блокирует confirmation envelope
- Если хоть что-то пошло не так — silently skip, никаких user-facing errors

**Где в коде:** `services/barcode.py::upsert_user_correction()` + хук в `handlers/food_log.py::_handle_edit_meal_input` секция 5c, параллельно с уже существующим 5b `_ufm.populate` (per-user memory). Это два независимых пути: per-user (личная коррекция) и shared crowd-base (коррекция продукта).

### 10.4 Что НЕ сделано (roadmap)

- USDA FoodData Central как второй источник для US/глобальных брендов в LATAM (free, no auth) — следующий PR
- GPT-fallback по EAN для weak-coverage regions (RU/IR/IN/AR) — следующий PR
- Nutritionix (~$5/мес при росте) для US/UK brand coverage — отложено
- OCR этикетки как ultimate fallback — отложено (нужен дополнительный UI flow)
- OFF write-back (contribute corrected data into OFF community) — отложено (требует OFF API key и consent flow)

---

## 11. Каскад источников: USDA + GPT-fallback (2026-06-08, PR #364, mig 488 LIVE)

Расширили одноисточниковый lookup (только OFF) до 4-tier cascade под weak-coverage regions и брендов которых нет в OFF.

```
cache → OpenFoodFacts → USDA FoodData Central → GPT-fallback по EAN
```

### 11.1 USDA FoodData Central (`services/usda_client.py`)

- Free API от US Department of Agriculture
- Силён для **американских и глобальных брендов** (Coca-Cola, Pepsi, Kraft) которые широко распространены в LATAM, но в OFF покрыты неровно
- Поиск по UPC в Branded foods: `GET /fdc/v1/foods/search?query=<UPC>&dataType=Branded&api_key=...`
- Активация: owner делает signup на https://fdc.nal.usda.gov/api-signup.html (30 сек, без карты), `USDA_API_KEY=...` в `/home/taskbot/noms/.env` + рестарт `noms-webhooks`. **Без env → слой no-ops silently** (caller → next tier)
- Free tier rate limit: 1000 req/hour
- Nutrient IDs (per USDA dictionary): 1008=kcal, 1003=protein, 1004=fat, 1005=carbs
- `_extract_per_100g` обрабатывает обе формы ответа: search endpoint `{nutrientId, value}` vs food endpoint `{nutrient:{id}, amount}`
- **Защитная эвристика:** `servingSize` в граммах → используем как `package_grams`; в `ml`/прочих → `package_grams=None` (плотность неизвестна, мл≠г)

### 11.2 GPT-fallback по EAN (последний резерв)

Когда штрихкод прочитан, но **нигде не найден** — спрашиваем `gpt-4o-mini` через structured output. Для weak-coverage regions (RU/IR/IN/AR) — главный спасатель.

**Защита от мусора в кэше:**
- Confidence floor 0.7 (`_GPT_FALLBACK_CONF_FLOOR`) — ниже → discard
- `is_known=false` → discard
- `kcal_100g=0` → discard (defensive — модель сказала `is_known=true` но не дала макросов)
- Промпт-инструкции: «угадывать категорию (`молоко`/`сок`) хуже чем сказать "не знаю"»

**EAN-prefix → country mapping (`_EAN_PREFIX_COUNTRY`):** ~85 GS1 ranges. Префикс → ISO alpha-2 (например 460-469→RU, 626→IR, 890→IN, 482→UA, 750→MX, 789-790→BR, 84→ES, 380-440→DE, ...). Это hint для модели — _не_ user country (брендовый продукт может быть импортным).

```python
# Пример промпта:
# Barcode: 4607097960058
# EAN prefix country (manufacturer GS1 origin): RU
# User country hint: RU
# What product is this? Reply via the structured schema.
```

**Гейт:** `gpt_barcode_fallback_enabled` (default `'false'`) — копейки за запрос (~250 токенов), но не нули. Toggle в `app_constants` → hot-reload через `v_user_context` без рестарта.

### 11.3 Каскад в `lookup_product`

- **Cache hit short-circuit** — не идёт в OFF/USDA/GPT
- **Cache warming на каждом не-cache hit** — `source` метка ('openfoodfacts' / 'usda' / 'gpt_inferred'). Следующий скан = cache hit мгновенно
- **Layer exceptions изолированы** — USDA упал → caught и каскад продолжается на GPT. Pattern: `try: product = await fetch_X(...) except Exception: product = None; continue`
- **Flags гейтят слои:** `usda_enabled` (default True; `fetch_usda` no-ops без env), `gpt_fallback_enabled` (default False; cents per call)

### 11.4 🔑 Durable принципы каскадных интеграций

1. **Каждый tier независимо отключаем флагом** + miss/exception одного НЕ ломает остальных. Mocking в тестах элементарный (patch один tier, проверить fallthrough на следующий).

2. **External-API tier ships disabled-by-default через env-gate:** `if not api_key: return None`. Owner активирует «строчкой в .env + рестартом» без code change. **НЕ raise, НЕ warning spam** на каждом запросе.

3. **GPT-угадывание = confidence-gated structured output**, никогда free-form. Free-form → модель «уверенно врёт» («просто молоко» вместо конкретного бренда → poison cache).

4. **Cache-warming на каждом hit** — превращает любой источник в O(1) для повторных сканов. Свежий контракт `barcode_cache.source` поле = audit trail (можно делать аналитику «сколько hits через USDA vs GPT»).

### 11.5 EAN-prefix таблица — потенциальное переиспользование

`_EAN_PREFIX_COUNTRY` сейчас только в `services/barcode.py` для GPT-fallback hint. Если понадобится в других местах (биас vision-распознавания, регионализация уведомлений) — выделить в `services/ean_prefix.py` с публичной функцией `country_from_ean(barcode) -> str | None`. Пока КИСС.

### 11.6 Активация (для следующего агента / для прода)

- **PR #364 готов**, mig 488 LIVE
- **USDA включается** установкой `USDA_API_KEY` в `.env` на VPS + рестарт noms-webhooks (флаг уже ON)
- **GPT-fallback включается** `UPDATE app_constants SET value='true' WHERE key='gpt_barcode_fallback_enabled'` — hot-reload, без рестарта
- Метрика мониторинга: `SELECT source, COUNT(*) FROM barcode_cache GROUP BY source` — увидеть в каких регионах USDA/GPT реально помогают
