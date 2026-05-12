---
title: "Noop Pattern — подавить main item, использовать carrier как единственное текстовое сообщение"
aliases: [noop-pattern, suppress-main-item, carrier-only-render]
tags: [headless, template-engine, ui, render-strategy, channel-a]
sources:
  - "mig 208 (2026-05-12) — Phase 6.1 follow-up: устранение лишнего «👋» carrier на финале онбординга"
  - "Tech-lead 2026-05-12 — не трогать icon_wave fallback, решать на уровне SQL"
related:
  - sticker-architecture-adr
  - ui-stickers-headless
  - one-time-attach-pattern
  - one-menu-ux
  - headless-architecture
  - reply-keyboard-routing-pattern
created: 2026-05-12
updated: 2026-05-12
---

# Noop Pattern

> **Зачем:** сделать ровно ОДНО текстовое сообщение со стикером и нижней клавиатурой, без лишнего «carrier с 👋». Используется когда экран должен показать только sticker (Channel A) + текст с reply-keyboard, без отдельного inline-keyboard сообщения.

## Когда применять

Trophy-mode screens, у которых:
- НЕТ inline-кнопок (только текст).
- ЕСТЬ Channel A sticker (`meta.show_sticker=true`).
- ЕСТЬ reply-keyboard (`meta.attach_main_kb_unconditional=true`).
- Текст и reply-keyboard должны быть в ОДНОМ сообщении (а не двух).

Пример: `onboarding_success` (mig 208).

## Проблема которую решаем

Стандартный flow для screen с `attach_main_kb_unconditional=true`:

```
SQL render_screen('onboarding_success_menu') → telegram_ui = {
  text_key: 'onboarding_success.menu_hint',
  reply_keyboard: {rows: [...]}    # без carrier_text_key
}
↓
template_engine.render_envelope:
  [ACQ, send_new(text=menu_hint), attach_reply_kb(text=icon_wave, reply_markup=kb)]
↓
В чате юзер видит:
  - Текст "Используй меню..."           ← main item
  - "👋" с присоединённой нижней kb     ← carrier fallback
```

**Два сообщения**, второе — паразитный «👋»-пузырь (фолбэк `_resolve_carrier_text` на `icon_wave` константу когда нет `carrier_text_key`).

## Решение — Noop Pattern (mig 208)

### SQL изменения

1. **`ui_screens.<screen>.render_strategy = 'noop'`** — template_engine skip-нет main item (`elif strategy == "noop": pass`).
2. **`ui_screens.<screen>.meta.attach_main_kb_unconditional = true`** — SQL `render_screen` эмитит `reply_keyboard` field.
3. **`render_screen` (mig 208 патч)** — для `attach_main_kb_unconditional` screens с `text_key` инжектит `carrier_text_key = v_screen.text_key`:

```sql
WHEN COALESCE(v_screen.meta->>'attach_main_kb_unconditional', '') = 'true'
    THEN public.build_main_reply_keyboard()
         || CASE
              WHEN v_screen.text_key IS NOT NULL AND v_screen.text_key <> ''
                THEN jsonb_build_object('carrier_text_key', v_screen.text_key)
              ELSE '{}'::jsonb
            END
```

### Result envelope

```
[ACQ?, send_sticker, attach_reply_kb(text=resolve(text_key), reply_markup=mainkb)]
                     ↑
                     carrier-сообщение несёт и текст, и нижнюю клавиатуру
```

**ОДНО** текстовое сообщение (carrier с резолвом из `text_key`), плюс стикер. icon_wave fallback больше не активируется.

## Что НЕ ломаем

- `template_engine.py` НЕ тронут — нулевые правки в ядре.
- `app_constants.icon_wave` остаётся — `_resolve_carrier_text` fallback chain работает для других screens.
- `cmd_restore_account` flow — `editMessageText` + carrier с 👋 + reply-kb по-прежнему работает (`restore_choice` screen меняет inline-кнопку «Восстановить» на текст «✅ Аккаунт восстановлен!», затем отдельный carrier с keyboard).
- Profile v5 deep-nav — то же.

Noop Pattern касается ТОЛЬКО screens с конкретной конфигурацией (`render_strategy='noop'` + `attach_main_kb_unconditional` + `text_key`).

## Edge case — One Menu UX cleanup

⚠️ **noop НЕ удаляет предыдущее сообщение.** Если экран был достигнут через `edit_existing` (in-place transition на inline-button picker), prev message остаётся в чате. На финальном экране (trophy) это нарушает «one active menu».

**Решение** — handler делает fire-and-forget `deleteMessage(decision.callback_message_id)` до build envelope. Пример из `handlers/location.py:_render_onboarding_success`:

```python
if decision.callback_message_id is not None and decision.callback_message_id > 0:
    import asyncio
    from services.telegram_send import _post as _telegram_post
    asyncio.create_task(
        _telegram_post(
            "deleteMessage",
            {"chat_id": ctx.telegram_id, "message_id": decision.callback_message_id},
        )
    )
```

Silent на failure (message уже удалён, network), не блокирует main flow. Тот же паттерн что `_clear_inline_keyboard_safe` в `webhook_server.py` (mig 207 phase4 gotcha #34).

## Прецеденты

| Screen | Migration | Сценарий |
|---|---|---|
| `onboarding_success` | mig 208 (2026-05-12) | Финал онбординга: sticker + Sassy text с main reply-kb. |

## Когда НЕ использовать

- Screen с inline-кнопками **И** reply-keyboard — Telegram constraint: один `sendMessage` = один `reply_markup`, не оба сразу. Нужны два сообщения: main inline + carrier с reply-kb. icon_wave fallback или явный `carrier_text_key` — обычный паттерн.
- Screen без text_key — Noop без text_key → carrier пустой → fallback на `icon_wave`. Бессмысленно.
- Screen с input_type='text_input' (юзер должен напечатать число/строку) — main item нужен чтобы донести вопрос текстом + `remove_keyboard:true`.

## Связанные находки сессии mig 208

1. `template_engine._resolve_carrier_text` уже имеет chain: `raw_reply_kb.carrier_text_key` → `icon_wave` → `·`. Достаточно SQL заполнить `carrier_text_key` — Python сам резолвит без правок.
2. CHECK constraint `ui_screens_render_strategy_check` исторически не включал `'noop'`. `template_engine` его поддерживал (line 629), но БД-уровневая валидация блокировала. mig 208 расширил constraint.
3. `reset_to_onboarding(p_telegram_id bigint)` RPC (mig 203) уже покрывает **64 поля** — savepoint-verified 12.05.2026. Замените 50-строчные UPDATE на one-liner. См. [[test-user-reset-recipe]].

## Файлы

- `migrations/208_onboarding_success_unified_carrier.sql` — applied 2026-05-12.
- `scripts/_build_mig_208.py` — stale-base builder.
- `handlers/location.py` `_render_onboarding_success` — One Menu UX delete pattern.
- `services/template_engine.py:629` — `elif strategy == "noop": pass` (existing, не тронут).
- `services/template_engine.py:431-474` `_resolve_carrier_text` — carrier_text_key chain (existing).
