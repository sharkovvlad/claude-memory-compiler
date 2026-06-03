---
title: "Content-Type Classification — Canonical Pattern (три синхронных классификатора)"
aliases: [content-type-classification, content-type-sync, junk-content, food-media-routing, location-flow-gate]
tags: [router, dispatcher, python-handler, food-log, indicator, location, ux]
sources:
  - "daily/2026-06-03.md"
created: 2026-06-03
updated: 2026-06-03
status: active
---

# Content-Type Classification — Canonical Pattern

> **Это HUB-статья по классификации входящего контента.** Правило для агентов:
> **меняешь классификацию в одном файле — обнови все три** (см. раздел «Три независимых классификатора»).
> Нарушение → 3 регрессии в один день (2026-06-03).

---

## 1. Канонический паттерн: таблица классов контента

Порядок в таблице соответствует приоритету секций в `dispatcher/router.py`.

| Класс | Типы Telegram-контента | Маршрут | Индикатор | Почему |
|---|---|---|---|---|
| **location-flow** | `message.location` (geo-pin) | `target=location` (если статус ∈ `_LOCATION_HANDLER_STATUSES`) | ✅ ДА (стикер, не текст) | Reverse-geocode занимает 200–500 ms; без индикатора юзер думает, что бот завис. Стикер — geo-контекст, не "Анализирую еду". |
| **food-media / photo** | `message.photo` | `target=ai`, reason=`food_media` | ✅ ДА | Основной путь vision-распознавания (GPT-4o). |
| **food-media / image-doc** | `message.document` где `mime_type.startswith('image/')` **И** `file_size ≤ 10 MB` | `target=ai`, reason=`food_media` | ✅ ДА | Desktop Telegram: галочка «отправить без сжатия» → документ с mime `image/*`. Отличается от фото тем, что нет `message.photo`. **Size-cap (PR #300):** `file_size` берётся из апдейта → большой файл отклоняется БЕЗ скачивания (→ junk). Не-image / oversized → help. |
| **food-media / voice** | `message.voice` (с `file_id`) | `target=ai`, reason=`food_media` | ✅ ДА | OGG-запись → Whisper transcription → AI-распознавание еды. |
| **unsupported / audio-file** | `message.audio` (mp3/m4a загруженный через «музыка») | `target=error`, reason=`junk_content` | ❌ НЕТ | **НЕ транскрибируется:** файлы до 2 ГБ, Whisper лимит 25 МБ; пользователи присылают не еду-голосом, а треки. Откат (PR #300, 2026-06-03) с audio→AI: false positive + cost. |
| **unsupported / junk** | `message.video`, `video_note`, `sticker`, `animation`, не-image `document`, `contact`, `poll`, `dice` | `target=error`, reason=`junk_content` | ❌ НЕТ | Не еда, бот не умеет обрабатывать. Python отправляет `messages.spam_protect` (ключ уже ×13 в `ui_translations`). |
| **navigation** | `callback_query`, `/команды`, reply-kb иконки меню, флаги языков | menu / onboarding / etc. | ❌ НЕТ | Мгновенный ответ, нет AI-задержки. |
| **free-text food** | Любой текст вне специальных статусов/callback | `target=ai`, reason=`text_food` | ✅ ДА (если статус не в `NO_INDICATOR_STATUSES`) | Основной путь текстового лога еды. |

### Location-flow — важная деталь

Геолокация `target=location` маршрутизируется **только при статусе ∈ `_LOCATION_HANDLER_STATUSES`**:

```python
# handlers/location.py
_ONBOARDING_LOCATION_STATUSES = {"onboarding:country", "onboarding:timezone"}
_EDIT_LOCATION_STATUSES = {"edit_country", "edit_timezone", "editing:country", "editing:timezone"}
_LOCATION_HANDLER_STATUSES = _ONBOARDING_LOCATION_STATUSES | _EDIT_LOCATION_STATUSES
```

**PR #300 гейтит на уровне РОУТЕРА** (секция 1 `route()`): `if status in _LOCATION_HANDLER_STATUSES: target=location else: target=error/junk_content`. Набор статусов берётся из `handlers/location.py` ленивым импортом (единый источник, без дрифта). До #300 секция 1 была безусловной (`target=location` всегда) → для registered-юзера `handle_location` уводил в `_forward_to_legacy_envelope` → форвард в n8n `02.1_Location`, который физически DELETE'нут → **вечно висящий thinking-стикер**.

**Тонкость индикатора для геолокации (PR #303):** `_content_needs_indicator` возвращает `True` для ЛЮБОЙ геолокации (он без DB, не знает статус — а легитимному location-flow индикатор нужен: резолвер города 200-500мс). Значит для out-of-flow геопина стикер ВСЁ РАВНО улетает, а затем геолокация уходит в junk. Поэтому **junk-ветка webhook (`AUTHORITATIVE_JUNK`) обязана звать `sticker.delete_thinking(chat_id)`** — иначе стикер зомби после help-сообщения (owner-скрин 2026-06-03). Это единственный случай, где indicator=True, но route может быть junk → инвариант контракт-теста для location НЕ проверяется (location исключён из теста, см. §5).

---

## 2. Три независимых классификатора — ОБЯЗАНЫ быть синхронны

Классификация контента распределена между тремя местами. Они **не знают друг о друге** — каждый принимает решения независимо, без вызовов.

```
Входящий update
    │
    ├─ [1] dispatcher/router.py
    │      _is_junk_content(message)  — решает маршрут (target)
    │      _is_image_document(message) — хелпер: document с mime image/*
    │      Секция 1: has_location → target=location (безусловно)
    │      Секции 5/6: has_photo/has_voice → target=ai
    │
    ├─ [2] telegram_proxy.py
    │      _content_needs_indicator(update) → (bool, telegram_id)
    │      Whitelist: photo / voice / audio / image-doc → True
    │      Junk-list: sticker / video / animation / video_note / contact / poll / dice /
    │                 non-image document → False
    │      location → True (стикер, не текст)
    │      Без DB-вызова, решает чисто по payload
    │
    └─ [3] handlers/location.py
           _LOCATION_HANDLER_STATUSES — статусы = location-flow
           Строка 111: if ctx.status not in _LOCATION_HANDLER_STATUSES → forward
           Источник истины для "когда геолокация = food-media, а когда = junk"
```

### Правило синхронизации

> **Меняешь один классификатор — иди и обнови остальные два.** Проверь:
> 1. Роутер (`router.py`) → правильный target?
> 2. Индикатор (`telegram_proxy.py:_content_needs_indicator`) → нужен ли индикатор?
> 3. Статусы location-flow (`handlers/location.py:_LOCATION_HANDLER_STATUSES`) → актуальный набор?

**Шаблон для проверки при любом PR, затрагивающем контент-тип:**
```bash
grep -n "_is_junk_content\|_is_image_document\|has_audio\|has_photo\|has_voice\|has_location" dispatcher/router.py
grep -n "_content_needs_indicator\|is_image_doc\|msg.get.*audio\|msg.get.*photo" telegram_proxy.py
grep -n "_LOCATION_HANDLER_STATUSES" handlers/location.py
```

---

## 3. Хроника инцидентов 2026-06-03

Три регрессии в один день — классический drift между классификаторами.

### (а) PR #294 + отсутствующий indicator (→ PR #298)

**Что было:** PR #294 добавил `_is_image_document` в роутер → image-doc теперь шли в `target=ai`.
**Что не обновили:** `telegram_proxy.py:_content_needs_indicator` — `document` по-прежнему попадал в junk-блок → индикатор не отправлялся при отправке фото-как-файла.
**Симптом:** пользователь отправляет фото без сжатия — бот обрабатывает, но нет thinking-стикера → UX: «бот завис?»
**Fix:** PR #298 добавил `is_image_doc` ветку в `_content_needs_indicator`.

### (б) audio→AI → откат (→ PR #300)

**Что было:** PR #294 добавил `message.audio` → `target=ai` (транскрипция как voice).
**Проблема:** `message.audio` — это загруженный mp3/m4a (до 2 ГБ). Whisper лимит 25 МБ. Пользователи присылают музыкальные треки, не голос-еду. False positive + стоимость.
**Fix:** PR #300 убрал `has_audio` из роутера → audio снова junk. `telegram_proxy.py` также откатился (audio из whitelist убран).

### (в) Геолокация registered-юзера (→ PR #300)

**Что было:** router.py секция 1 — `has_location` → `target=location` безусловно (любой статус).
`handle_location()` при `status not in _LOCATION_HANDLER_STATUSES` → `_forward_to_legacy_envelope("status:registered")` → форвард в n8n `02.1_Location`.
**Проблема:** `02.1_Location` workflow DELETED (Phase 6.2). Форвард уходил в void. n8n отвечал ошибкой, Python терял ответ. Thinking-стикер отправлен, очищен никогда не был → вечно висит.
**Fix:** PR #300 изменил роутер: `has_location` при статусе вне location-flow → `target=error, reason=junk_content`. `messages.spam_protect` объясняет что геолокация сейчас не используется.

---

## 4. Текущее состояние classifiers (после PR #298 + #300, канон на 2026-06-03)

### `dispatcher/router.py`

```python
def _is_junk_content(message):
    # sticker / video / animation — без document (document проверяется отдельно)
    return any(message.get(k) is not None for k in ("sticker", "video", "animation"))

# Секция 1 (router.route):
if has_location:
    # Геолокация ТОЛЬКО при location-flow статусах
    if status in _LOCATION_HANDLER_STATUSES:
        base.target = "location"
    else:
        base.target = "error"
        base.reason = "junk_content"
    return base

# Секция 3 (junk):
if _is_junk_content(message):
    base.target = "error"; base.reason = "junk_content"

# + отдельная проверка document:
# non-image document → junk; image/* → has_image_document=True → секция 6 → ai
```

### `telegram_proxy.py:_content_needs_indicator`

```python
# Single source of truth: reuse the router's image-doc predicate (mime + size
# cap) instead of an inline check — so this fn and the router can't drift on it.
from dispatcher.router import _is_image_document   # lazy; router doesn't import this module
doc = msg.get("document")
is_image_doc = _is_image_document(msg)

# Food-media (indicator = True):
if (msg.get("photo")
    or (msg.get("voice") and msg["voice"].get("file_id"))
    or is_image_doc):
    return True, int(telegram_id)

# Junk (indicator = False): audio is here (NOT food-media):
if (msg.get("audio") or msg.get("sticker") or msg.get("video")
    or msg.get("animation") or msg.get("video_note") or msg.get("contact")
    or msg.get("poll") or msg.get("dice")
    or (doc is not None and not is_image_doc)):  # non-image / oversized document
    return False, int(telegram_id)

# Geolocation (indicator = True, sticker mode):
if msg.get("location"):
    return True, int(telegram_id)
```

**Важно:** `message.audio` **отсутствует** в whitelist. Это намеренно — см. инцидент (б) выше.

---

## 5. Защита от дрифта

**✅ Контракт-тест (PR #300, есть сейчас):** `tests/test_content_classification_contract.py` пинит инвариант **«индикатор показывается ⟺ контент идёт в распознавание (food_media)»** для всех типов контента (photo/voice/image-doc → recognition+indicator; audio/video/sticker/poll/pdf/oversized-image-doc → unsupported, без indicator). Если кто-то изменит ОДИН классификатор и забудет другой — тест падает в CI/pre-push. **Заметку можно проигнорировать, красный тест — нет.** Запускать при любой правке классификации.

**✅ Частичное объединение (PR #300):** `telegram_proxy._content_needs_indicator` теперь импортирует `_is_image_document` из роутера (mime + size-cap), а роутер лениво импортирует `_LOCATION_HANDLER_STATUSES` из `handlers/location.py`. Эти два предиката больше не дублируются.

**🟡 Полный антидрифт-рефактор (на будущее, НЕ сделано):** вынести всю классификацию в единый `dispatcher/content_classifier.py` (`classify_content(message) -> ContentClass`, `needs_indicator(content_class) -> bool`), импортировать из `router.py` и `telegram_proxy.py`. Пока остаётся правило «обнови все три» + контракт-тест как страховка.

---

## Related Concepts

- [[content-type-routing-gotchas]] — Предыстория (PR #294): image-doc detection, spam_protect reuse (×13 в БД), полный список junk-типов. Читать как «что сломалось впервые».
- [[food-log-python-cutover]] — Stage 7a: рендеринг food log confirmation в Python.
- [[telegram-sticker-pipeline]] — Как thinking-стикер отправляется и удаляется.
- [[dispatcher-callback-pipeline]] — Архитектура dispatching в целом (stale, n8n-era).
- [[canonical-hybrid-location-picker]] — Location handler: onboarding:country / edit_country flow.
- [[telegram-proxy-indicator]] — Детали maybe_send_indicator: DB-check, sticker rotation, album dedup.
