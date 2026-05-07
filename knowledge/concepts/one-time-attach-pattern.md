# One-Time Attach Pattern (Reply-Keyboard Lifecycle)

**Внедрено:** Migrations 182/183/184 + Python patches (handlers/onboarding_v3.py + services/template_engine.py), 07.05.2026.

## Проблема

Telegram имеет жёсткие constraints для reply-keyboard:

1. **Один message = один `reply_markup`** (либо inline-кнопки, либо ReplyKeyboardMarkup, не оба)
2. **Reply-keyboard — chat-level state**, прикрепляется к chat (не к message), Telegram кэширует на клиенте
3. **`sendMessage` требует non-empty text** (нельзя голое сообщение с одним reply_markup)
4. **`deleteMessage` carrier-сообщения УБИВАЕТ reply-kb** (smoke test 30.04)
5. **Стикеры НЕ поддерживают `reply_markup`** (актуально для будущей замены онбординг-приветствия на стикер)

До mig 182 паттерн был хрупкий:
- Mig 160: conditional re-attach при возврате с text_input — но через хардкоженный `·` carrier
- Mig 181: force-attach при каждом `/start` от registered → постоянный `·` пузырь в чате
- `onboarding_success` экрана не существовало в БД (только переводы) → юзер после онбординга попадал в неопределённое состояние

## Решение — One-Time Attach

**Reply-keyboard прикрепляется ОДИН РАЗ навсегда** в правильный момент жизненного цикла, плюс точечные re-attach в edge cases.

### Жизненный цикл reply-kb для зарегистрированного юзера

```
[Онбординг шаг N: complete_onboarding]
    ↓
[onboarding_success screen]  ← поздравительный текст, send_new
    ↓
[onboarding_success_menu screen]  ← carrier с reply-kb (meta.attach_main_kb_unconditional)
    ↓ (Telegram кэширует kb на клиенте навсегда)
[stats_main / любая навигация]  ← reply-kb уже видна, attach НЕ нужен
    ↓
[edit_age (text_input)]  ← Telegram системная клавиатура временно скрывает reply-kb
    ↓ (юзер вводит число)
[stats_main]  ← mig 160 conditional re-attach с toast «✅ Сохранено!»
    ↓
[обычная жизнь юзера — никаких ·]
    ↓
[cmd_confirm_delete]  ← ghost_remove kb (cmd_confirm_delete flow)
```

### Edge cases

- **Юзер сменил устройство / очистил чат / отсутствовал >30 дней:** mig 182 30-day heuristic в `process_user_input.action='start'` — force-attach reply-kb через `jsonb_set`. Carrier text fallback на `app_constants.icon_wave='👋'`.
- **Активные юзеры:** при /start kb уже в кэше Telegram, force-attach не срабатывает → нет `·` пузыря.

## Архитектура

### SQL слой (Headless — SQL знает контекст)

`render_screen()` имеет 3 ветки для `reply_keyboard`:

```sql
'reply_keyboard', CASE
    -- 1. Reply_kb screen: build из ui_screen_buttons (для status='new' welcome)
    WHEN v_is_reply_kb_screen
        THEN v_reply_kb_result

    -- 2. Conditional re-attach после text_input (mig 160 + mig 183)
    WHEN COALESCE(v_screen.meta->>'reply_kb_entry', '') = 'true'
         AND v_user.previous_status IN (
             SELECT ws.state_code FROM workflow_states ws
             JOIN ui_screens scr ON scr.screen_id = ws.screen_id
             WHERE scr.input_type = 'text_input'
         )
        THEN public.build_main_reply_keyboard()
             || jsonb_build_object('carrier_text_key', 'messages.saved')

    -- 3. Unconditional re-attach (mig 184) — только onboarding_success_menu
    WHEN COALESCE(v_screen.meta->>'attach_main_kb_unconditional', '') = 'true'
        THEN public.build_main_reply_keyboard()

    ELSE NULL END
```

`process_user_input.action='start'` (mig 182):
```sql
IF p_action_type = 'start' THEN
    DECLARE v_start_render JSONB;
    BEGIN
        v_start_render := public.render_screen(p_telegram_id, 'stats_main');
        -- 30-day fallback re-attach
        IF v_user.last_active_at IS NULL OR
           v_user.last_active_at < NOW() - INTERVAL '30 days' THEN
            v_start_render := jsonb_set(v_start_render, '{telegram_ui,reply_keyboard}',
                                        public.build_main_reply_keyboard(), true);
        END IF;
        RETURN v_start_render;
    END;
END IF;
```

### Python слой (Dumb Renderer — резолвит текст)

`services/template_engine.py:_resolve_carrier_text()` — chain fallback для carrier text:

```python
def _resolve_carrier_text(raw_reply_kb, translations, constants):
    # 1. carrier_text_key (от SQL render_screen)
    if isinstance(raw_reply_kb, dict):
        key = raw_reply_kb.get("carrier_text_key")
        if key:
            text = _walk_translation_path(translations, key)
            if text:
                return _resolve_icons(text, constants)
    # 2. fallback на icon_wave constant
    wave = constants.get("icon_wave")
    if wave:
        return wave
    # 3. final fallback
    return "·"
```

`handlers/onboarding_v3.py:_envelope_from_rpc_result` — multi-item envelope после complete_onboarding:

```python
if result.get("onboarding_complete") is True or screen_id == "onboarding_success":
    # Второй RPC: render_screen('onboarding_success_menu')
    menu_result = await rpc_caller("render_screen",
                                   {"p_telegram_id": tid,
                                    "p_screen_id": "onboarding_success_menu"})
    menu_envelope = render_envelope(menu_ui, ctx, ...)
    envelope.items.extend(menu_envelope.items)
```

## Использование

### Создание нового root reply-kb screen

1. INSERT в `ui_screens` с `meta.attach_main_kb_unconditional=true` (или `meta.reply_kb_entry=true` для conditional)
2. `input_type='inline_kb'` (НЕ `'reply_kb'` — иначе попадёт в первую ветку CASE с пустым reply_kb_rows)
3. Не нужны кнопки в `ui_screen_buttons` — kb строится через `build_main_reply_keyboard()`

### Toast после text_input action

Автоматически — `render_screen` для root reply_kb_entry screen инжектирует `carrier_text_key='messages.saved'` если `previous_status` это text_input screen.

Перевод `messages.saved` существует на 13 языков ("✅ Сохранено!" / "✅ Saved!" / "✅ Збережено!" / etc.).

### Edge case fallback (>30 дней неактивности)

Автоматически — mig 182 conditional в `process_user_input.action='start'`. Carrier — `icon_wave` constant ('👋').

## Что НЕ нужно делать

- ❌ Не использовать `text_input` тип для root reply_kb screens — это устаревшее
- ❌ Не add force-attach reply-kb в каждом /start (mig 181 был отозван — создавал постоянный `·`)
- ❌ Не делать `deleteMessage` carrier — убьёт reply-kb (smoke 30.04)
- ❌ Не зашивать carrier text как hardcode в Python — всегда через resolver chain

## Связанные миграции

- **Mig 160** — изначальный conditional re-attach после text_input (с хардкоженным `·`)
- **Mig 181** (REVERTED in mig 182) — force-attach при /start (давал `·` всегда)
- **Mig 182** — One-Time Attach + revert mig 181 + 30-day heuristic
- **Mig 183** — carrier_text_key для toast «✅ Сохранено!»
- **Mig 184** — unconditional re-attach branch для onboarding_success_menu

## Tech debt — открытые вопросы

- **#7:** ghost_remove reply-kb для status='new' после soft-delete restore (NLM-pointed случай — юзер видит "противоречивый" интерфейс)
- **#8:** Активация bot_stickers (`onboarding_welcome` + `onboarding_success`) — ждёт file_id от owner. После этого первое сообщение онбординга/завершения станет стикером. Архитектура уже готова: 2 messages (стикер + текст-подсказка с kb).
- **#11:** Расширение conditional re-attach для других root paths (cmd_get_stats, cmd_get_profile, cmd_progress) — сейчас только при возврате с text_input
