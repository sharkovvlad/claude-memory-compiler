# Handover 2026-06-03 — Классификация типов контента: инцидент + защита

**Для следующего агента. 5-минутный брифинг.**

## Что произошло
Тип входящего контента (фото/голос/текст/файл/аудио/геолокация/junk) классифицируется в **ТРЁХ независимых местах**, которые ОБЯЗАНЫ быть синхронны:
1. `dispatcher/router.py` — `_is_junk_content()`, `_is_image_document()` → маршрут (`ai`/`error`/`location`).
2. `telegram_proxy.py:_content_needs_indicator()` — показывать ли «думающий» индикатор (whitelist, без DB).
3. `handlers/location.py:_LOCATION_HANDLER_STATUSES` — какие статусы = location-flow.

За одну сессию они разъехались трижды (PR #294 расширил роутер, забыл индикатор; audio→AI оказался ошибкой; геолокация registered-юзера форвардилась в мёртвый n8n). Итог — 8 PR, все merged + LIVE.

## Текущее состояние (канон после фиксов)
- **photo / voice / image-doc (image/* ≤10MB) / text-food** → распознавание + индикатор.
- **audio / video / video_note / sticker / animation / PDF / oversized-image-doc / contact / poll / dice** → `error/junk_content` → help `messages.spam_protect` ×13, **без** индикатора. junk-ветка webhook чистит стикер (`delete_thinking`).
- **геолокация** → location-хендлер ТОЛЬКО при статусе ∈ `_LOCATION_HANDLER_STATUSES` (онбординг country/timezone + edit_country/timezone); иначе → junk/help (раньше → зависание стикера на мёртвом n8n 02.1_Location).
- **audio НЕ транскрибируется** (Whisper лимит 25МБ, файлы до 2ГБ).

## Защита от рецидива (3 слоя)
1. **Контракт-тест** `tests/test_content_classification_contract.py` — инвариант «индикатор ⟺ распознавание (food_media)» для всех типов. Падает при дрифте. **Гоняй при любой правке классификации.**
2. **Объединённые предикаты** — `telegram_proxy` импортирует `_is_image_document` из router; router лениво импортирует `_LOCATION_HANDLER_STATUSES` из location. Эти два больше не дублируются.
3. **CI** `pr-content-classification.yml` гоняет контракт-тест на релевантных PR (advisory).

## ПРАВИЛО для будущих агентов
Меняешь классификацию контента в ОДНОМ месте — **обнови все три** + прогони контракт-тест. KB: [[concepts/content-type-classification.md]].

## Migration HEAD: 440 (applied LIVE)
mig 440 = подсказка точности в `edit_food.prompt_variants` ×13 (истинный APPEND). L1 native review нужен для 11 не-EN/RU langs (только суффикс).

## Отложено (отдельные сессии)
- **Штрихкод**: локальный декодер EAN (pyzbar/zxing) → OpenFoodFacts, без LLM. Reply-кнопка.
- **Каскад FatSecret/OpenFoodFacts**: точные макросы вместо LLM-оценки. Уровень cascade с fallthrough. Хук `fatsecret` в `services/ai_recognition.py:~205` пустой.
- **Качество распознавания**: golden-set оффлайн-эвал → промпт «перечисляй все позиции» + temperature-tuning. Дизайн в [[concepts/food-recognition-prompt-lab.md]].
- **Full pytest-CI gate**: блокирован 4 пред-существующими падениями (payment-моки + router callback/text-тесты) — сначала их фикс.

## PR этой сессии
#294 (silent-drop), #298 (indicator hotfix), #300 (audio→junk + geo-gate + size-cap + unified + contract), #301 (image_detail=high), #303 (junk-стикер cleanup), #304 (mig 440 tip), #305 (CI). Все LIVE.
