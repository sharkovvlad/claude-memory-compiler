---
title: "Canonical Hybrid Location Picker — reply-kb prompt + inline list"
aliases: [canonical-hybrid, location-picker-ux, reply-kb-location, phase-6-3]
tags: [ux, telegram, location, reply-keyboard, headless, phase-6-3]
sources:
  - "Master Blueprint profile-v5-screens-specs.md Часть 2 Шаг 10"
  - "Tech-lead 2026-05-14 — utvержденный UX: «Спецификационный Hybrid»"
  - "Phase 6.3 implementation (mig 210, PR #66)"
related:
  - phase6-location-migration-plan
  - phase4-onboarding-migration
  - headless-fsm-vs-dynamic-handler-separation
  - one-menu-ux
  - noop-render-strategy-pattern
created: 2026-05-14
updated: 2026-05-14
---

# Canonical Hybrid — два состояния location picker

> **Зачем:** запросить геолокацию у пользователя через нативный Telegram-UI (reply-button с `request_location:true`) и одновременно дать fallback на manual выбор из списка стран. Решает Telegram constraint «один reply_markup per message» через **handler-side intercept** + **two-state** screen.

## Контекст

Phase 6.3 переносит обработку геопозиции (`message.location`) из legacy n8n 02.1_Location в Python. Параллельно — UX-revamp онбординг страны: вместо сухого `edit_country` («Откуда ты?» + inline [Авто]/[Список]/[Назад]) показываем Sassy `onboarding_country_picker` с motivational text + GPS-CTA.

**Telegram constraint:** одно `sendMessage` принимает **одно** значение `reply_markup` (либо `InlineKeyboardMarkup`, либо `ReplyKeyboardMarkup`, либо `ReplyKeyboardRemove`, либо `ForceReply`). Невозможно прислать одно сообщение с inline-кнопками **и** persistent reply-kb с location-кнопкой.

## Решение — два состояния

### Default state (entry to onboarding:country)

- **Trigger**: после phenotype quiz `process_onboarding_input` для `status='onboarding:country'` возвращает `render_screen('onboarding_country_picker')` (mig 210 Block D L468).
- **Render**: `handlers.onboarding_v3._envelope_from_rpc_result` детектит `result.screen_id == 'onboarding_country_picker'` → делегирует в `handlers.location._render_geo_request_prompt`.
- **Output**: **одно** `sendMessage` с:
  - `text` = резолв `onboarding.ask_country` (JSONB array Sassy variants, Python random-pick через `_resolve_icons_in_text`). Merged motivation + GPS-hint (mig 210 Block A).
  - `reply_markup = ReplyKeyboardMarkup`:
    - `[{text: "📍 Отправить местоположение", request_location: true}, {text: "📋 Выбрать из списка"}]`.
    - `resize_keyboard: true, one_time_keyboard: false` — persistent до явного `ReplyKeyboardRemove`.

### List state (user clicks `📋 Выбрать из списка`)

- **Trigger**: Telegram присылает `message.text = "📋 Выбрать из списка"` (text button → пользовательский text-message).
- **Router intercept** (`dispatcher/router.py` section 10.4):
  ```python
  if (status == "onboarding:country" and text and not has_callback
      and _matches_manual_list_button(text, translations)):
      base.target = "location"
      base.synth_callback = "cmd_list_countries"
  ```
- **Render** (`handlers.location.handle_location`):
  - Callback `cmd_list_countries` → `_render_country_picker_with_kbd_remove`.
  - **Два сообщения** (Telegram constraint workaround):
    1. Carrier "·" с `reply_markup = {"remove_keyboard": True}` — убирает persistent reply-kb.
    2. Inline-picker через `_render_country_picker` (existing Phase 6.1) — список стран с пагинацией.

### Geo-pin path (user clicks `📍 Отправить местоположение`)

- **Trigger**: Telegram присылает `message.location = {latitude, longitude}` (т.к. `request_location:true`).
- **Handler** (`handlers.location._handle_geo_pin`):
  1. Validate `lat ∈ [-90, 90]`, `lon ∈ [-180, 180]`. Invalid → re-prompt (rare edge).
  2. `services.geolocation.reverse_geocode(lat, lon)` → Geoapify HTTP → `{country_code: "ES", timezone: "Europe/Madrid"}`.
  3. None → ReplyKeyboardRemove + manual picker (graceful fallback).
  4. Success → `_finalize_with_timezone(ctx, decision, cc, tz, rpc_caller)` (Phase 6.2 — branches `is_edit`).
- **Envelope prepend**: carrier "·" с `remove_keyboard:true` (Reply-kb с location-кнопкой больше не нужна после finalize).

## Why handler-side, не SQL render_screen

`render_screen` SQL поддерживает только `attach_main_kb_unconditional` reply-kb (через `build_main_reply_keyboard()`). Custom reply-kb с `request_location:true` и переменными translations — **не умеет**. Расширять `render_screen` — большое изменение core RPC. Проще: handler перехватывает по `screen_id` и строит свой envelope (text — всё ещё резолвится через DB translation, layout — Python).

Это вариация паттерна [[headless-fsm-vs-dynamic-handler-separation]]: статические кнопки (`cmd_back`) обрабатывает SQL FSM; динамические (`loc_country_<CC>`, `loc_tz_<TZ>`) — Python; **специальные UX layouts** (Canonical Hybrid two-state) — Python intercept по screen_id.

## Mig 210 Block A — merged Sassy variants

3 sassy variants × 13 langs объединяют:
- Motivation (предыдущий `ask_country`): «Я умею отличать хамон от докторской колбасы».
- GPS-hint (предыдущий `ask_share_location`): «Жми кнопку 📍 внизу».

Каждая variant — разная **рамка** (food/cheese hook, barcode hook, biorhythm hook). Variation между 3 вариантами **сохранена** (lesson [[python-vs-n8n-template-grammar]] секция «Variant-массивы»: APPEND ≠ REPLACE для variation preservation).

Mig 210 Block B удаляет `onboarding.ask_share_location` как dead code (`content #- '{onboarding,ask_share_location}'`).

## ReplyKeyboardRemove edge cases

- `editMessageText` НЕ убирает reply-kb (она chat-level, не message-level).
- ОБЯЗАТЕЛЬНО `sendMessage` с `reply_markup={"remove_keyboard": true}`.
- Carrier "·" (1 символ, ~невидим) — минимум noise в чате. Альтернатива — `sendChatAction("typing")` (не убирает kbd) — не подходит.
- При finalize → `_handle_geo_pin` prepend carrier ДО `_finalize_with_timezone` envelope. User видит: убирается reply-kb → стикер success → Sassy completion message.

## Tests (`tests/handlers/test_location.py`)

| Test | Что покрывает |
|---|---|
| `test_location_pin_geocodes_and_finalizes_via_python` | Geoapify mock → ES/Europe/Madrid → set_user_location + finalize + ReplyKeyboardRemove carrier. |
| `test_location_pin_geocoding_fails_falls_back_to_picker` | reverse_geocode None → ReplyKeyboardRemove + inline picker. |
| `test_cmd_auto_location_renders_geo_request_prompt` | callback cmd_auto_location (legacy compat) → reply-kb с request_location:true. |
| `test_cmd_list_countries_renders_picker_page0` | reply-text matching → ReplyKeyboardRemove + inline picker. |

## Prerequisites — что должно быть в БД

1. `ui_screens.onboarding_country_picker` (mig 207 Phase 6.1) с `text_key=onboarding.ask_country`, `render_strategy=replace_existing`.
2. `ui_screens.onboarding_timezone_picker` (mig 207) с `text_key=onboarding.ask_timezone`.
3. `ui_translations.content.onboarding.ask_country` JSONB array из 3 merged Sassy variants × 13 langs (mig 210 Block A).
4. `ui_translations.content.buttons.share_location` × 13 langs (mig 210 Block C) — label для reply-button с request_location.
5. `ui_translations.content.buttons.manual_list` × 13 langs (existing) — для reply-text matching в router.
6. `process_onboarding_input` для `status='onboarding:country'/'onboarding:timezone'` рендерит **новые** screens (mig 210 Block D, 4 точечных substitutions).

## Phase 6.4 cleanup (pending)

- Удалить `GEOAPIFY_API_KEY` из VPS `.env` (после стабильности Python path).
- Удалить `Search Geo` node из n8n 02.1_Location (через safe PUT).
- Деактивировать `02.1_Location` workflow целиком (через SQLite UPDATE, lesson Phase 4 gotcha #4).
- Удалить `dispatcher_python_authoritative_admin_only` ключ из БД + RPC `get_dispatcher_flags` ремонт.

## Cross-references

- [[phase6-location-migration-plan]] — финальный план Phase 6 (6.1-6.4).
- [[phase4-onboarding-migration]] — base architectural pattern для onboarding.
- [[headless-fsm-vs-dynamic-handler-separation]] — общий принцип Headless DB ↔ Python handler.
- [[one-menu-ux]] — editMessageText контракт.
- [[noop-render-strategy-pattern]] — параллельный case для onboarding_success (carrier + reply-kb).
- [[safe-create-or-replace-recipe]] — stale-base для process_onboarding_input в Block D.
