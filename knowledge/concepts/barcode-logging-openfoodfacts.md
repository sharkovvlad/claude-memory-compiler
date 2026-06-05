---
title: "Barcode Logging — packaged food via EAN → OpenFoodFacts (Python MVP)"
aliases: [barcode-logging, barcode-scan, openfoodfacts, off-lookup, ean-decode, packaged-food-log]
tags: [food-log, barcode, openfoodfacts, python-handler, ai-recognition, content-type, mvp-design]
sources:
  - "daily/2026-06-03.md"
  - "daily/2026-06-05.md"
created: 2026-06-03
updated: 2026-06-05
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
