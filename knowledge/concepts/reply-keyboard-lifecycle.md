---
title: "Reply-Keyboard Lifecycle — все события attach / detach / revive"
aliases: [reply-kb-lifecycle, reply-keyboard-revive, reply-kb-restore, reattach-reply-keyboard, lost-reply-keyboard]
tags: [ux, telegram, reply-keyboard, headless, lifecycle, wontfix]
sources:
  - "daily/2026-06-03.md"
created: 2026-06-03
updated: 2026-06-03
---

# Reply-Keyboard Lifecycle — все точки attach / detach / revive

Главная reply-клавиатура (`🍽 Добавить еду` / `☀️ Мой день` / `🚀 Прогресс` /
`👤 Профиль`) — **chat-level state** Telegram: привязана к чату, кэшируется
клиентом, НЕ к конкретному сообщению. Её можно потерять (системная клавиатура
телефона перекрывает при text-input; явный `remove_keyboard`; смена устройства /
очистка чата). Эта статья — **единый список ВСЕХ мест**, где kb прикрепляется,
снимается и восстанавливается, чтобы агент не искал по 5 файлам.

Механику «как именно attach работает» (carrier text, why deleteMessage убивает kb)
см. [[concepts/one-time-attach-pattern]]. Routing reply-tap vs inline —
[[concepts/reply-keyboard-routing-pattern]].

## Жёсткие ограничения Telegram (почему всё именно так)

1. **Один message = один `reply_markup`** — либо inline-кнопки, либо
   ReplyKeyboardMarkup, НЕ оба. → нельзя повесить reply-kb на сообщение с inline.
2. **`deleteMessage` reply-kb-носителя УБИВАЕТ клавиатуру** (smoke 30.04). →
   reply-kb должна ехать на сообщении, которое НЕ удаляется. Поэтому carrier'ы
   шлются стратегией `attach_reply_kb` и НЕ трекаются как `last_bot_message_id`
   (иначе One-Menu navigate их удалит → kb умрёт).
3. **Стикеры не несут `reply_markup`** (`sendSticker` без этого параметра).
4. **`sendMessage` требует непустой text** — нужен carrier-текст (см.
   `_resolve_carrier_text`).

## ATTACH / REVIVE — где клавиатура возвращается

### SQL `render_screen` — 4 ветки `reply_keyboard` CASE
1. **reply_kb screen** — `input_type='reply_kb'` (welcome `status='new'`), kb из
   `ui_screen_buttons`.
2. **conditional re-attach после text_input** — `meta.reply_kb_entry='true'` И
   `previous_status` был text_input screen → `build_main_reply_keyboard()` +
   carrier `messages.saved` (mig 160/183). Экраны: `stats_main`, `profile_main`,
   `progress_main`, `personal_metrics` (mig 392).
3. **pending_kb_reattach** — `meta.reply_kb_entry='true'` И
   `users.pending_kb_reattach=TRUE` → attach + carrier `messages.saved`
   (mig 374). См. «Ежедневная страховка» ниже.
4. **unconditional** — `meta.attach_main_kb_unconditional='true'` → attach всегда.
   Сейчас только `onboarding_success_menu` (mig 184).

### SQL `process_user_input` action='start'
5. **30-day fallback** — при `/start` если `last_active_at` NULL или > 30 дней →
   force-attach reply-kb (mig 182). Для активных юзеров не срабатывает (kb уже в
   кэше Telegram) → нет лишнего `·` пузыря.

### Python handlers (`handlers/menu_v3.py`)
6. **save-toast** — `_maybe_build_save_toast`: после **text-input save** в
   Profile v5 статусах (`edit_age`/`weight`/`height`/`waist`) → отдельный
   `OutboundItem` strategy `attach_reply_kb`, text `messages.saved`. НЕ обновляет
   `last_bot_message_id`.
7. **lang-refresh** — `_maybe_build_reply_kb_refresh`: после смены языка
   (`result.reply_keyboard_refresh=true`) → re-attach на свежем языке (kb —
   chat state, Telegram сам не пересоздаёт).

### ★ Ежедневная страховочная сетка (mig 374) — ГЛАВНЫЙ recovery
8. **Чек-ины сон/стресс** — кнопки утреннего/вечернего чек-ина имеют
   `meta.reattach_main_kb_after_save=true` (12 button rows). При save через
   `process_user_input` (save_via_callback) ставится `users.pending_kb_reattach=TRUE`,
   следующий `render_screen` ветка 3 возвращает kb, флаг flush'ится (single-shot).
   **Эффект:** каждый день, отвечая на «Как спалось?» / «Как стресс?», юзер
   гарантированно получает клавиатуру обратно. Это закрывает edge-case потери
   reply-kb без вмешательства в Golden Path логирования еды.

## DETACH — где клавиатура снимается
- **`cmd_confirm_delete` / account flows** — `ghost_remove_reply_keyboard`
  (`services/telegram_send.py`): шлёт `⏳` с `remove_keyboard=True` и сразу
  удаляет (это команда «убрать kb», не носитель новой kb — удалять можно).
- **text-input экраны** — системная клавиатура телефона ВРЕМЕННО перекрывает
  reply-kb (не снимает её на сервере); после закрытия — возвращается. Именно
  отсюда ощущение «пропала» → ветки 2/6 делают явный re-attach с тостом.

## GAP (durable) — крон-пуши reply-kb НЕ привязывают
`crons/reminders.py`, `streak_checker.py`, `trial_expiry.py`,
`subscription_lifecycle.py` — все используют `inline_keyboard`, не reply-kb.
Утренние/вечерние напоминания клавиатуру НЕ реанимируют сами по себе. Восстановление
держится на чек-инах (mig 374, п.8) + `/start` (mig 182, п.5).

## WONTFIX — re-attach reply-kb на food-log (2026-06-03)

Предлагалось: «любой юзер вернёт клавиатуру просто залогировав еду» → прикрепить
reply-kb к ответу food-log. **Отклонено владельцем (Архитектор/UX). НЕ переоткрывать.**

Почему нельзя «просто прицепить»:
- Карточка еды — ОДНО компактное сообщение с inline `[Исправить][Удалить]`.
  Ограничение #1 → reply-kb на неё повесить нельзя.
- Комментарий Сейджа (Номса) **встроен в карточку** (`{noms_comment_block}` внутри
  `food_log.confirmation_text_*`), отдельного сообщения нет. Вынос в отдельный пузырь =
  разбиение карточки на 2 сообщения.
- Индикатор «анализирую…» как носитель не годится: он удаляется через
  `delete_thinking()`, а ограничение #2 → удаление убьёт kb. Оставлять его «висеть»
  = визуальный мусор.

Продуктовая аргументация WONTFIX:
1. **Golden Path неприкосновенен.** Логирование еды — самый частый сценарий; чистый
   1-пузырь с БЖУ + эмоцией нельзя ломать на 2 сообщения ради edge-case (~1% юзеров).
2. **Шум / скролл.** Второй пузырь толкает карточку вверх → юзер скроллит за
   калориями. Хуже читаемость на главном пути.
3. **Риск уже закрыт.** Ежедневные чек-ины (mig 374, п.8) гарантированно возвращают
   kb. Дублировать механизм в еде не нужно.

**Вывод для будущих агентов:** НЕ вешать reply-kb на food-карточку / индикатор. Для
восстановления потерянной reply-kb полагаться на чек-ины (mig 374) + `/start` 30-day
fallback (mig 182). Если возникнет НОВАЯ массовая (не edge-case) потребность —
сначала продуктовое решение владельца, не инженерный self-serve.

## Технические факты (durable, пригодятся при любой работе с reply-kb)
- `build_main_reply_keyboard()` RPC → RETURNS jsonb с **ключами** (`text_key` /
  `icon_const_key`), НЕ готовые метки. Резолв меток — только Python:
  `services/template_engine.py:_build_main_reply_keyboard_markup` +
  `_build_button_text` (формат `'{icon} {text}'`). Публичный алиас —
  `build_main_reply_keyboard_markup` (используется в `handlers/menu_v3.py`).
- **Proxy-слой `telegram_proxy.py` НЕ имеет** `translations`/`constants` → не может
  сам собрать метки kb (нужен либо ctx как в хендлерах, либо server-resolved RPC).
- Текстовый индикатор «анализирую» throttled **раз/UTC-день** через
  `users.last_text_indicator_date` (set прокси ДО food-хендлера — поэтому в хендлере
  его НЕЛЬЗЯ использовать как «первый-лог-за-день» сигнал, он уже = today).
- `ui_translations` = `(lang_code, content jsonb, created_at)`; путь `buttons.add_food`
  = `content->'buttons'->>'add_food'`. `app_constants.value` тип `text`.

## Related Concepts
- [[concepts/one-time-attach-pattern]] — механика attach (carrier, deleteMessage kills kb)
- [[concepts/reply-keyboard-routing-pattern]] — reply-tap vs inline routing
- [[concepts/save-bot-message-contract]] — почему carrier НЕ трекается как last_bot_message_id
- [[concepts/one-menu-ux]] — One Menu (single active навигационный экран)

## Профиль-edit text-input: inline-back вместо remove_keyboard (mig 446)

**Гоча:** для text-input edit-экранов (вес/рост/возраст) `remove_keyboard` снимал постоянную
reply-kb И был несовместим с `editMessageText` (400 «inline keyboard expected») → fallback
`delete_and_send_new` (лишний пузырь). Кнопка [Назад] из `ui_screen_buttons` при `remove_keyboard`
вообще не рендерилась.

**Правило (durable):** чтобы у профиль-edit числового поля был [Назад] И сохранялась reply-kb —
включи `text_input_inline_back` для его статуса (`render_screen` gate). Тогда `_build_reply_markup`
отдаёт `inline_keyboard` (НЕ `remove_keyboard`): (1) `editMessageText` правит на месте (чистота
чата, без delete+send), (2) постоянная reply-kb остаётся (Telegram не трогает chat-level reply-kb
при editMessageText — она переживает сообщения пока не remove/replace). **«Сохранить reply-kb» =
просто перестать слать `remove_keyboard`.** mig 392 re-attach при этом становится избыточным/безвредным.

mig 446 включил это для `edit_age/edit_weight/edit_height` (статусы ∈ PROFILE_V5_STATUSES, cmd_back
уже корректен через menu_v3→process_user_input mig110+back_screen_id_default). Онбординг не задет
(cmd_back через process_onboarding_input mig390). edit_waist — НЕ включён (свой экран mig442,
show_back_inline=NULL, не в router PROFILE_V5).
