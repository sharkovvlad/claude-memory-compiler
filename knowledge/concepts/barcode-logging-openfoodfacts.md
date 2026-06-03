---
title: "Barcode Logging — packaged food via EAN → OpenFoodFacts (Python MVP)"
aliases: [barcode-logging, barcode-scan, openfoodfacts, off-lookup, ean-decode, packaged-food-log]
tags: [food-log, barcode, openfoodfacts, python-handler, ai-recognition, content-type, mvp-design]
sources:
  - "daily/2026-06-03.md"
created: 2026-06-03
updated: 2026-06-03
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

## 8. Scope изменений (для коллизий с другими агентами)

**Миграции** (номер — `git fetch origin main` + collision-guard ПЕРЕД push):
- **mig A** — headless-проводка: `waiting_for_barcode` (+ возможно `waiting_for_barcode_grams`)
  в `workflow_states`; `buttons.scan_barcode` ×13 + иконка в `app_constants`; правка RPC
  `build_main_reply_keyboard`; тексты `messages.barcode_*` ×13 + `questions.barcode_grams` ×13.
- **mig B** — узаконить `barcode_cache`: `CREATE TABLE IF NOT EXISTS` + RPC get/upsert.

**Python:** `services/barcode.py` (новый, изолирован от каскада); ветка в
`handlers/food_log.py:handle_ai_input`; `cmd_scan_barcode` в `handlers/menu_v3.py`;
reply-кнопка → `cmd_scan_barcode` в `dispatcher/router.py` (минимально); `requirements.txt`
(+`zxing-cpp`, `Pillow`). Три классификатора по сути НЕ трогаются.

**Не трогать:** `services/ai_recognition.py` (домен FatSecret/каскад-агента).

---

## Related Concepts

- [[content-type-classification]] — 3 классификатора; barcode НЕ добавляет класс (ветка по статусу)
- [[food-recognition-prompt-lab]] — текущее vision-распознавание, дефект C (нестабильные макросы)
- [[food-log-python-cutover]] — handle_ai_input, log_meal_transaction, dumb-renderer
- [[memory-claim-vs-live-verification]] — trust live, не NLM (находка в)
- [[migration-collision-guard]] — номер миграции, fetch+rebase перед push
- [[copywriter-playbook]] — ×13 тексты, ≤18 ch/кнопка, anti-shame
