# Handover 2026-06-03 — Barcode logging (упакованная еда по штрихкоду)

> 5-минутный брифинг. Полная спека + находки — KB [[concepts/barcode-logging-openfoodfacts]].

## Статус: LIVE, работает, фича закрыта (ждёт только реального user-теста)

Лог упакованной еды по штрихкоду → точные КБЖУ OpenFoodFacts вместо LLM-оценки.
Reply-кнопка `[🔎 Штрихкод]`. Полностью Python, без n8n.

**Merged + deployed:**
- **#313** — восстановил фантомный контракт-тест классификации (CI `pr-content-classification.yml` ссылался на несуществующий файл → красный CI у всех; тест жил на невмерженной `14d3a17`).
- **#316** — сама фича. mig **452** (barcode_cache + users.pending_barcode + 5 RPC) + mig **453** (статус waiting_barcode_portion + кнопка + 5 UI-ключей ×13).

**Applied LIVE:** mig 452+453 применены к проду (psycopg2), verified. Auto-deploy success, `deploy.sh` сам `pip install` → zxing-cpp/Pillow на VPS. Прод-smoke: OFF reachable, e2e Nutella 539→50g=270, /health 200.

## Архитектура (одна фраза)

Barcode = **ветка обработки фото (auto-detect: decode-first в `handle_ai_input`), НЕ новый тип контента** → 3 классификатора и инвариант индикатор⟺распознавание не тронуты. Отдаёт обычный `ParsedFoodResult` → весь downstream (log_meal_transaction `input_source='barcode'`, рендер, Sage, мана) переиспользован. Декодер `zxing-cpp` (EAN checksum = роутер barcode-vs-еда: нет кода → vision). Источник OFF плагинный (под будущий FatSecret).

## Что должен знать следующий агент

1. **`services/barcode.py`** — изолирован от каскада (`ai_recognition.py` НЕ трогать, там домен FatSecret-агента). decode + OFF + cache-адаптеры + scaling + portion-parser (gpt-4o-mini, fast-path для чисел).
2. **Порция:** OFF `product_quantity` → кнопка `[✅ Вся упаковка]` (callback `cmd_barcode_whole`); иначе спросить граммы. Свободный текст/голос → дешёвый парсер. Статус `waiting_barcode_portion` хранит `users.pending_barcode`; RPC `set/get/clear_barcode_pending`.
3. **🔴 Reply-kb кнопка у существующих free юзеров НЕ появляется авто** — sleep/stress чек-ин (mig 374 reattach) ПРЕМИУМ-гейтнут (mig 330). Детали — KB [[reply-keyboard-lifecycle]] §«Новая кнопка → free». Owner-решение: не форсить, фича работает через auto-detect без кнопки.
4. **`barcode_cache`** была orphan-таблицей в проде (создана вручную, не в миграциях) — узаконена mig 452 `CREATE IF NOT EXISTS`.
5. **Двойной §12 stale-base за сессию** — main ушёл вперёд трижды (мои миграции 448/449→450/451→452/453). Урок: номер миграции брать + rebase НЕПОСРЕДСТВЕННО перед push.

## Осталось / phase 2

- **Реальный user-тест скана** (JPEG-сжатие Telegram — единственное не проверенное программно). Если капризит → готов фикс: приём фото-как-документа (без сжатия) + подсказка кадрирования.
- **Phase 2:** мульти-источник по странам (RU/IR → FatSecret/региональный) — **вместе с каскад-агентом**, через общий `barcode_cache`. Закроет слабое покрытие OFF по RU.
- Опц.: «не нашёл» → дешёвый vision-вопрос вместо тихого отката; мониторинг первых сканов (`food_logs` input_source='barcode').
- Техдолг (не barcode): `save_indicator_state HTTP 204` шум роняет smoke-тест деплоя → ложные `🚨 deploy failed`.
