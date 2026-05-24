---
title: "Language Switch UX in Headless Architecture"
aliases: [language-switch, lang-refresh, translations-override, reply-keyboard-refresh]
tags: [headless, n8n, ux, language, dumb-renderer, process-user-input]
sources:
  - "daily/2026-04-25.md"
  - "daily/2026-05-15.md"
created: 2026-04-25
updated: 2026-05-15
---

# Language Switch UX in Headless Architecture

Language change is a special case in the headless architecture: the Dispatcher snapshot of `translations` was taken before the language changed, so every screen rendered immediately after a language switch would still display the old language. Four distinct bugs compound this problem. The fixes are: a fresh `translations_override` from the RPC, a `reply_keyboard_refresh` flag, an explicit `cmd_back` → menu_v3 route for `registered` status, and `continueOnFail` on deleteMessage.

## Key Points

- **`translations_override` field** — `process_user_input` emits fresh translations for the new language when `save_rpc='set_user_language'`; Dumb Renderer prioritises `data.translations_override || trigger.translations`
- **`reply_keyboard_refresh: true` flag** — when language changes, the reply keyboard must be re-sent via `sendMessage` (not `editMessageText`) with a fresh main menu keyboard built from the new translations
- **`cmd_back` → menu_v3 for `registered` status** — `registered` was not in `PROFILE_V5_STATUSES` set; explicit route branch added to Dispatcher Route Classifier
- **`continueOnFail: true` on HTTP deleteMessage** — without it, a 400 from Telegram (message already deleted) silently stops the workflow; `onError: 'continueRegularOutput'` needed alongside
- **`buttons.edit_lang` text_key** — `buttons.edit_language` existed only in `ru`; all 13 langs have `buttons.edit_lang`. Fix: `ui_screen_buttons.text_key` changed + orphan key removed
- **Migration 124** — adds `v_lang_just_changed`, `translations_override`, `reply_keyboard_refresh`, `language_code_new` to `process_user_input` response when `save_rpc='set_user_language'`

## Details

### Bug 1 — Missing translations for Settings "Язык" button

**Symptom:** Settings screen rendered the raw translation key (`buttons.edit_language`) as button text for all non-ru users.

**Root cause:** `ui_screen_buttons.text_key` was `buttons.edit_language`. That key was inserted into `ui_translations` only for `ru`. All 13 other langs fell back to showing the raw key string.

**Fix:**
- `UPDATE ui_screen_buttons SET text_key='buttons.edit_lang' WHERE ...`
- `DELETE FROM ui_translations WHERE text_key='buttons.edit_language'` (orphan cleanup)
- `buttons.edit_lang` already existed with all 13 translations; `ru` value cleaned: `"Язык / Language"` → `"Язык"`

### Bug 2 — Old language shown in Settings buttons after language change

**Symptom:** User changes language to English → taps Settings → button labels still in old language.

**Root cause:** `trigger.translations` in Dumb Renderer is a Dispatcher snapshot. The snapshot was taken when `v_user_context` was fetched — before the language save. `render_screen` queries `v_user_context` which reads current `language_code`, but by the time Dispatcher built its `translations` payload, the value was the old language.

**Fix (Migration 124 + Dumb Renderer):**
- `process_user_input` detects `save_rpc = 'set_user_language'`: after the SET, does a fresh `SELECT * FROM v_user_context WHERE telegram_id = p_telegram_id` and includes full `translations` in the response as `translations_override`
- Dumb Renderer JS priority: `const translations = data.translations_override || trigger.translations || {}`

### Bug 3 — `cmd_back` from Language picker → Welcome screen (👋)

**Symptom:** After editing language, tapping the Back button showed the "welcome" / onboarding screen instead of Settings.

**Root cause:** `registered` status was not included in `PROFILE_V5_STATUSES` set in the Route Classifier. `cmd_back` with `status='registered'` fell through to legacy `04_Menu` routing → `Back Target Router` fallback → `Send Main Menu (Back)` node (sends 👋 welcome message).

**Fix (01_Dispatcher Route Classifier PUT):**
```javascript
// Explicit branch added before PROFILE_V5_STATUSES check:
if (callback === 'cmd_back' && user.status === 'registered') {
    return { route_target: 'menu_v3', action_type: 'callback',
             payload: { callback_data: 'cmd_back' }, skip_debounce: false };
}
```

### Bug 4 — Reply keyboard still in old language after language change

**Symptom:** Screen text updates to new language, but the persistent reply keyboard at the bottom (☀️ / 👤 / 🚀) retains old language labels.

**Root cause:** `editMessageText` cannot update the reply keyboard. The reply keyboard is a separate object attached to the original `sendMessage` call. `editMessageText` only updates inline keyboards.

**Fix (Migration 124 + Dumb Renderer):**
- `process_user_input` sets `reply_keyboard_refresh: true` and `language_code_new: <new_lang>` in the response
- Dumb Renderer: when `data.reply_keyboard_refresh === true`, prepend a `sendMessage` item with `mainMenuKB()` built from `translations` (override already applied), then send the settings screen via `send_new` render strategy — both items flow through the same `send_new` Switch output for sequential ordering

```javascript
// Dumb Renderer prepend logic:
if (data.reply_keyboard_refresh === true) {
    items.unshift({
        json: {
            action: 'sendMessage',
            chat_id: trigger.chat_id,
            text: '✅',
            reply_markup: { keyboard: mainMenuKB(translations), ... }
        }
    });
}
```

### Bug 5 — Debounce race condition (separate article: [[concepts/anti-spam-debounce]])

**Root cause:** `Sync Profile` n8n node was updating `last_active_at` **in parallel** with the main flow. `debounce_user_action` reads and writes the same `last_active_at` non-atomically. If `Sync Profile` ran and updated `last_active_at` during the debounce window, the debounce saw a fresh timestamp and returned FALSE → duplicate execution was silently dropped.

**Fix:** Dedicated `users.last_action_ms BIGINT` column + atomic `UPDATE ... WHERE last_action_ms IS NULL OR last_action_ms < (now_ms - cooldown)` + `GET DIAGNOSTICS v_found = ROW_COUNT`. See [[concepts/anti-spam-debounce]] for full migration 141 details.

### Bug 6 — deleteMessage blocking workflow

**Symptom:** When "One Menu" pattern tries to delete an already-deleted message, the HTTP `deleteMessage` returns Telegram 400 → n8n raises an error → `sendMessage` with new screen never executes → user sees nothing.

**Root cause:** HTTP Request node without `continueOnFail` will throw on non-2xx responses, stopping the workflow branch.

**Fix:** Set `continueOnFail: true` + `onError: 'continueRegularOutput'` on any HTTP deleteMessage node. This makes Telegram 400 flow to the regular output instead of stopping execution.

```
⚠️ Rule: ANY HTTP deleteMessage node in n8n MUST have continueOnFail + onError:continueRegularOutput.
   Stale message IDs are routine; 400 is expected, not exceptional.
```

## Migration 124 — process_user_input lang refresh

`migrations/124_process_user_input_lang_refresh.sql`:

```sql
-- In process_user_input, after the save_rpc block for 'set_user_language':
IF v_save_rpc = 'set_user_language' THEN
    -- Do fresh SELECT of user context to get new-language translations
    SELECT translations, language_code
    INTO v_fresh_translations, v_new_lang
    FROM v_user_context
    WHERE telegram_id = p_telegram_id;

    v_response := v_response
        || jsonb_build_object(
            'translations_override', v_fresh_translations,
            'reply_keyboard_refresh', true,
            'language_code_new', v_new_lang
        );
END IF;
```

## Dumb Renderer update summary

Changes to `04_Menu_v3` JS (Session 15 PUT):

1. **Priority chain:** `const translations = data.translations_override || trigger.translations || {}`
2. **Reply keyboard refresh:** when `data.reply_keyboard_refresh === true`, prepend `sendMessage` item with `mainMenuKB(translations)` built from fresh translations
3. **Both items via `send_new`:** all items when `reply_keyboard_refresh` go through a single `send_new` branch for sequential ordering (avoids Switch output-index ordering issue where output_index=1 executes before output_index=2)

## Bug 7 — Python handler не обрабатывал `reply_keyboard_refresh` (2026-05-15)

**Symptom:** после смены языка через Settings → Lang picker нижняя reply-keyboard оставалась на старом языке. SQL-сторона корректно возвращала `reply_keyboard_refresh: true` + `translations_override` (mig 124), но Python никогда не читал эти поля.

**Root cause:** при миграции рендеринга с n8n Dumb Renderer на Python `handlers/menu_v3.py` (Phase 2, 28.04) сигналы `reply_keyboard_refresh` и `translations_override` **не были портированы**. `grep reply_keyboard_refresh --include='*.py'` — ноль ссылок. SQL-работа шла «в пустоту».

**Диагностика (последовательность проверок):**
1. SQL `build_main_reply_keyboard()` — headless OK, отдаёт `text_key + icon_const_key`.
2. `ui_translations` buttons.* — 13 языков заполнены ✓.
3. `v_user_context` для admin (lang=en) — правильные переводы ✓.
4. Python `_build_main_reply_keyboard_markup` — live test: вернул правильный EN keyboard ✓.
5. `process_user_input` (pg_get_functiondef) — возвращает `reply_keyboard_refresh=true` ✓.
6. **`grep reply_keyboard_refresh *.py` — 0 результатов** ← gap найден.

**Fix (PR #79):**

Новая функция `_maybe_build_reply_kb_refresh(ctx, result, rpc_caller)` в `handlers/menu_v3.py`:
- Проверяет `result.reply_keyboard_refresh == true`.
- Вызывает `build_main_reply_keyboard()` RPC.
- Резолвит кнопки через `translations_override` (свежий dict, потому что `ctx.translations` устарел — UserCtx собирается одноразово в начале запроса).
- Carrier text — `messages.saved` на новом языке (тот же UX-pattern что `_maybe_build_save_toast`).
- Создаёт SimpleNamespace mock ctx для `resolve_translation_text`.
- Append `OutboundItem(strategy='attach_reply_kb')` в конец envelope.

**Lesson (KB-кандидат):** SQL `process_user_input` отдаёт ряд post-action сигналов (`reply_keyboard_refresh`, `translations_override`, `language_code_new`, `success_reaction`, etc.) на верхнем уровне результата. **Эти сигналы НЕ доходят до `render_envelope` автоматически** — она получает только `telegram_ui` блок. Для signal-обработки нужен пост-процессор в handler'е (как `_maybe_build_save_toast` или `_maybe_build_reply_kb_refresh`). Иначе SQL-работа идёт «в пустоту».

**Тесты:** 3 unit-теста (full flow ru→es, no-flag path, defensive fallback при missing override).

## Related Concepts

- [[concepts/headless-architecture]] — `process_user_input` RPC response contract
- [[concepts/anti-spam-debounce]] — Bug 5: atomic debounce via `last_action_ms`
- [[concepts/n8n-data-flow-patterns]] — `continueOnFail` pattern on deleteMessage nodes
- [[concepts/headless-picker-pattern]] — other pickers that follow the same save_rpc pattern
- [[concepts/dispatcher-callback-pipeline]] — Route Classifier modification for `cmd_back` + `registered` status
- [[concepts/phase2-python-menu-v3]] — Python handler architecture where signal gap lived

## Sources

- [[daily/2026-04-25.md]] — Session 15: 6 language switch UX bugs diagnosed and fixed; Bug 1 (missing text_key translations), Bug 2 (stale translations after language change), Bug 3 (cmd_back → welcome screen), Bug 4 (reply keyboard stale), Bug 5 (debounce race), Bug 6 (deleteMessage blocking)
- [[daily/2026-05-15.md]] — Bug 7: Python handler не обрабатывал `reply_keyboard_refresh` сигнал из SQL; fix в `_maybe_build_reply_kb_refresh`; lesson про SQL→Python signal gap
