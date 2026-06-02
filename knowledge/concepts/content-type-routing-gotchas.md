---
title: "Content-type routing gotchas — image-doc, audio, junk в dispatcher/router.py"
aliases: [content-type-routing, image-document-routing, audio-routing, junk-content, spam-protect-key]
tags: [router, dispatcher, food-log, python-cutover, ux]
sources:
  - "daily/2026-06-02.md"
created: 2026-06-02
updated: 2026-06-02
---

# Content-type routing gotchas

Типичные случаи «бот промолчал», хотя должен ответить, из-за неполного детектирования
типов входящего контента в `dispatcher/router.py`. Все три закрыты в PR #294 (2026-06-02).

## Key Points

### (а) Фото отправленное «как файл» = `message.document`, mime `image/*`

Desktop Telegram даёт галочку «отправить без сжатия» / «как файл». В этом случае
Telegram присылает `message.document` с `mime_type='image/jpeg'` (или png, webp…),
а НЕ `message.photo`. До PR #294 `_is_junk_content()` включал все `document` → junk → тишина.

**Fix:** `_is_image_document(message)` → True если `document.mime_type.startswith('image/')`.
Документ с image/* **исключён из junk** → `has_image_document=True` → `target=ai/food_media`.
В хендлерах (`handle_ai_input`, `_handle_edit_meal_input`, `handle_onboarding_food`) добавлена
ветка: берём `file_id` из `document` → vision cascade (тот же путь, что обычное фото).

### (б) `message.audio` ≠ `message.voice`

`message.voice` — запись голосового сообщения (OGG). `message.audio` — загруженный mp3/m4a
через «прикрепить файл → музыка». Пользователь думает что наговорил еду — bot молчит.

**Fix:** добавлен `has_audio=True` в `RouteDecision` при наличии `message.audio.file_id`.
Тот же `target=ai/food_media`. В хендлерах — ветка `message.audio` → `transcribe_voice` (как voice).

### (в) `messages.spam_protect` — уже в БД ×13, reuse без миграции

При добавлении «дружелюбный ответ вместо тишины» для junk — ключ `messages.spam_protect`
**уже существовал** в `ui_translations` ×13 языков (n8n era: нода «Send Junk Error» в
`01_Dispatcher` использовала этот же ключ). Миграция не потребовалась.

**Lesson: перед созданием нового translation key** — искать в БД по семантике:
`SELECT lang_code, content->'messages'->'spam_protect' FROM ui_translations` и по смысловым
соседям (`errors.*`, `messages.*`). Экономит migration номер и L1 review.

**Доступ в Python:** `ctx.translations.get('messages', {}).get('spam_protect')`.
`ctx.translations` приходит из `v_user_context` и содержит весь JSONB блок `ui_translations.content`.

### (г) Неполный `_is_junk_content` tuple

Оригинальный список junk-типов: `("sticker", "video", "document", "animation")`.
**Отсутствовали:** `video_note`, `contact`, `poll`, `dice` — они молча проваливались в legacy n8n
без ответа пользователю. PR #294 добавил все четыре.

**Актуальный список junk** (после PR #294):
```python
("sticker", "video", "animation", "video_note", "contact", "poll", "dice")
# + document только если NOT image/*  (проверяется отдельной веткой)
```

## Архитектурная точка подключения

Junk-контент перехватывается в `_try_authoritative_path` (`webhook_server.py`) ветке
`target == "error" and decision.reason == "junk_content"`. Отправка через `send_telegram`
(уже есть в `webhook_server.py`). Python полностью владеет этим ответом — n8n 01_Dispatcher
больше не нужен для этого случая.

## Related Concepts

- [[concepts/food-log-python-cutover]] — Stage 7a: рендеринг food-log в Python
- [[concepts/dispatcher-callback-pipeline]] — архитектура dispatching
- [[concepts/action-router-pattern]] — pattern роутинга по content/status
