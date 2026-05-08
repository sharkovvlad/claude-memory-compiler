# UX-паттерн: реакция бота на изменение параметров пользователя

> **Статус:** активный паттерн (2026-04-20, Session 8). Применяется во всех text_input flows Headless Architecture.
>
> **Где задекларирован:** RPC `process_user_input` (migration 098) эмитит `telegram_ui.success_reaction='👌'`. n8n workflow (04_Menu_v3 после Session 8 PUT) читает и ставит реакцию через Telegram Bot API `setMessageReaction`.

---

## Что это

Когда пользователь меняет параметр профиля (вес, рост, возраст, пол, цель, активность и т.д.) и бот успешно сохранил значение, пользователь получает **мгновенный визуальный ack** через Telegram-реакцию на своё сообщение + обновлённый экран.

**3 сигнала подтверждения происходят параллельно:**
1. 👌 реакция на сообщение пользователя (мгновенный ack «сохранено»)
2. Удаление prompt-сообщения (“Твой вес (кг):”)
3. Появление обновлённого экрана с новым значением (например, `personal_metrics` с weight_kg=99)

**Без чего:** без отдельного текстового сообщения “✅ Вес обновлён!” Это не нужно — 👌 на user-сообщении + новый экран достаточно self-explanatory. Чат остаётся чистым (принцип One Menu).

---

## Пример: обновление веса

**Поток:**
```
(юзер на personal_metrics)
  ↓ нажимает [⚖️ Изменить вес]
(бот рендерит ask_weight)
  Твой вес (кг):
  [❌ Отмена]
  ↓ юзер пишет "99"
(бот делает 3 вещи параллельно)
  • ставит 👌 на сообщение "99"
  • удаляет prompt "Твой вес (кг):"
  • отправляет новое сообщение personal_metrics
(юзер видит)
  ─────── его сообщение ───────
  99 👌
  ─────── бот ───────
  📏 Мои Данные
  Вес: 99 кг
  Рост: 193 см
  [⚖️ Изменить вес] [📏 Изменить рост]
  [🎂 Изменить возраст] [🚻 Изменить пол]
  [🔙 Назад]
```

---

## Где применять паттерн

**Применяем всегда, когда:**
- `p_action_type='text'` ИЛИ inline callback save (в будущем migrations)
- save_rpc вернул без exception (v_save_ok=TRUE)
- текст пользователя прошёл валидацию

**Экраны с text_input (текущие):**
- `ask_weight` → `set_user_weight` → personal_metrics
- `ask_age` → `set_user_age` → personal_metrics
- `ask_height` → `set_user_height` → personal_metrics

**Экраны с inline-kb save (будущие, пример):**
- gender picker: `cmd_select_male/female` → `set_user_gender` → personal_metrics
- goal picker: `cmd_select_lose/maintain/gain` → `set_user_goal_type` → my_plan
- activity picker: `cmd_select_sedentary/light/moderate/active/very_active` → `set_user_activity_level` → my_plan
- speed picker: `cmd_select_speed_slow/normal/fast` → `set_user_goal_speed` → my_plan
- training picker: `cmd_select_training_strength/cardio/mixed/none` → `set_user_training_type` → my_plan
- phenotype: после quiz → `set_user_phenotype` → profile_main

> **Замечание про callback-saves:** сейчас migration 098 эмитит `success_reaction` только для `p_action_type='text'`, т.к. для callback'а стандартный UX — update inline-кнопки (editMessageText). Если нужна реакция и на callback-save — расширить условие в migration 098:
> ```sql
> IF (p_action_type = 'text' AND v_save_ok) OR (v_button.meta ? 'success_reaction') THEN
> ```

---

## Контракт (как эмитит RPC)

`process_user_input` возвращает в `telegram_ui`:

```json
{
  "render_strategy": "delete_and_send_new",
  "success_reaction": "👌",
  "chat_id": "417002669",
  "text_key": "profile.personal_metrics_text",
  "template_vars": { "weight_kg": 99, "height_cm": 193, ... },
  ...
}
```

**Поля которые читает n8n workflow:**
- `success_reaction` — строка-emoji. Если присутствует — fire-and-forget `setMessageReaction` на `$('Execute Workflow Trigger').item.json.message.message_id` (user's input message ID).
- `render_strategy` — как обычно (delete_and_send_new для text save).

**Эмит происходит в migration 098** (файл `migrations/098_rpc_success_reaction.sql`), в блоке:
```sql
IF p_action_type = 'text' AND v_save_ok THEN
    v_telegram_ui := v_telegram_ui || jsonb_build_object('success_reaction', '👌');
END IF;
```

---

## n8n реализация (04_Menu_v3 / v4)

Параллельная ветка от Dumb Renderer:

```
[Dumb Renderer]
    │
    ├────→ [IF success_reaction present] → [HTTP setMessageReaction] (fire-and-forget)
    │
    └────→ [Switch Render Strategy] → editMessageText / deleteMessage+sendMessage / sendMessage
```

**HTTP Set Message Reaction node (пример):**
```json
{
  "method": "POST",
  "url": "https://api.telegram.org/bot<token>/setMessageReaction",
  "sendBody": true,
  "specifyBody": "json",
  "jsonBody": "={{ { chat_id: $json.chat_id, message_id: $('Execute Workflow Trigger').item.json.message.message_id, reaction: [{type:'emoji', emoji: $json.success_reaction}] } }}",
  "options": { "ignoreResponseCode": true }
}
```

`ignoreResponseCode: true` — реакция может не сработать (rate limit / deleted message), не ронять основной flow.

**Реальная реализация (04_Menu_v3, Session 8 2026-04-20, 19 нод):**

Round 1 PUT (15→18 нод):
- Switch Render Strategy: `mode="rules"` → `mode="expression"` с явным int-mapping `{replace_existing:0, delete_and_send_new:1, send_new:2}[render_strategy] ?? 2`. Причина: n8n Switch rules-mode имел cache routing bug — `delete_and_send_new` ошибочно шёл в output 0.
- Early Answer Callback Query: перенесён из `RPC → ACQ` в `Extract Payload → ACQ` параллельно (убирает "query too old" errors, ACQ теперь < 100ms после click).
- Set Message Reaction: parallel fire-and-forget ветка от Dumb Renderer.
- Save Bot Message: fire-and-forget `save_bot_message` RPC после sendMessage (поддерживает `last_bot_message_id` для One Menu UX).

Round 2 PUT (18→19 нод, bugfixes после first live test):
- **sendMessage clobber fix:** нода `HTTP sendMessage` читала `$json.text` → после `HTTP deleteMessage` `$json` = `{result: true}` (ответ Telegram API). Fix: `$('Dumb Renderer').item.json.text` (CLAUDE.md Data Flow Rule #1).
- **success_reaction forwarding:** Dumb Renderer JS не включал `success_reaction` в return object. Fix: `success_reaction: ui.success_reaction || ''` добавлен в output.
- **Typing indicator:** нода `HTTP sendChatAction(action='typing')` добавлена параллельно от Extract Payload (fire-and-forget) — юзер видит typing до RPC response.

---

## Почему этот паттерн

1. **Фокус на пользователе:** главный сигнал — его собственное сообщение получило 👌. Это inherently личнее и быстрее чем бот-сообщение "Вес обновлён".
2. **Чистота чата:** нет accumulation confirm-сообщений в истории диалога. Чат остаётся профильно-ориентированным.
3. **Мгновенность:** реакция через `setMessageReaction` не требует round-trip через render_screen → один HTTP call вместо полного rendering pipeline.
4. **Универсальность:** работает для всех текстовых save — один паттерн, 0 code в прикладных RPC (`set_user_weight`, `set_user_age`, etc.). Логика в одном месте (`process_user_input`).
5. **Graceful degradation:** если reaction API упал/rate-limited — `ignoreResponseCode:true` не ломает render.

---

## Что НЕ делаем

- Не шлём "✅ Вес обновлён!" отдельным сообщением.
- Не ставим реакцию на callback-save (там spinner уже ack, дополнительная реакция дублирует signal).
- Не эмитим `success_reaction` если save упал (validation_error ИЛИ save_rpc_failed) — без реакции юзер понимает что что-то пошло не так (покажется error_key в retry screen).
- Не хардкодим эмодзи в workflow — всегда читать из `telegram_ui.success_reaction`. Миграция может поменять emoji без touching n8n.

---

## Расширения на будущее

### E1. Контекстные реакции
Разные эмодзи для разных типов save:
- 👌 — обычный numeric save (weight, height)
- 🎉 — milestone save (first meal, streak start)
- 💪 — goal/training change (motivational)
- 🎯 — goal achieved (BMI target hit)

Implementation: в `process_user_input` читать `ui_screens.success_reaction_override` (новая колонка) или `save_rpc` возвращать `{reaction: '...'}` в JSONB.

### E2. Adaptive reactions
Читать emoji из `app_constants.reaction_text_save_default` — позволит менять глобально без миграций.

### E3. Отключение по user preference
Если юзер включил "минимальный UI" в settings — не эмитить `success_reaction`. Через `u.ui_preferences` JSONB.

---

## История

- **2026-04-20 (Session 8):** паттерн введён по запросу user'а после обнаружения UX gap — text save не показывал confirmation в Headless. Альтернатива (legacy-style "✅ Сохранено" toast) была отклонена в пользу Headless-пуристского подхода с reaction + screen update. Migration 098 + задеплоен в 04_Menu_v3 (Session 8, 2 PUT rounds, 15→19 нод). Bug 1 closed.

---

## Связанные концепты

- [[headless-architecture]] — Headless pattern, где `process_user_input` эмитит `telegram_ui` контракт.
- [[one-menu-ux]] — "Ровно одно активное меню" + `last_bot_message_id` + `save_bot_message` RPC.
- [[n8n-data-flow-patterns]] — fire-and-forget параллельные ветки, side-effect HTTP requests.
- [[profile-v5-screens-specs]] — Profile v5 text_input screens (ask_weight/age/height).
