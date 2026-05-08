---
title: "n8n Stateful UI Patterns"
aliases: [stateful-ui, editMessageText, callback-message-id, typing-indicator, answer-callback-query]
tags: [n8n, ui, telegram, patterns]
sources:
  - "daily/2026-04-08.md"
  - "daily/2026-04-10.md"
  - "daily/2026-04-11.md"
  - "daily/2026-04-13.md"
  - "daily/2026-04-14.md"
created: 2026-04-08
updated: 2026-04-14
---

# n8n Stateful UI Patterns

The bot behaves like a Mini App inside Telegram chat. Messages are edited in-place rather than creating new ones, keeping the chat clean and stateful. Every tap gets immediate visual feedback.

## Key Points

- **editMessageText over sendMessage:** When a user taps an inline button, replace the message (`editMessageText`) rather than creating a new one — removes stale buttons, keeps chat clean
- **callback_message_id:** Must be threaded through all data payloads so downstream nodes can call `editMessageText` on the correct message
- **one_time_keyboard: false:** Reply keyboards must set this to `false`; otherwise the keyboard disappears after the first tap
- **Typing action (reply keyboards):** `sendChatAction('typing')` fires as a parallel dead-end branch from Menu Router before any RPC; user sees "печатает..." within ~100ms of tapping
- **answerCallbackQuery (inline buttons):** Must fire immediately on every `callback_query` as a parallel dead-end branch; without it the button spinner persists for ~3 seconds
- **Inline vs reply triggers:** Nodes reachable from both triggers need an IF node: `{{ $json.callback_message_id }}` truthy → editMessageText, else → sendMessage
- **parse_mode HTML over Markdown:** User names with underscores cause Telegram 400 errors in Markdown mode; use HTML everywhere (`<b>...</b>` not `*...*`)

## Details

### Why editMessageText is critical

When a user presses an inline button, Telegram sends a `callback_query`. If the handler calls `sendMessage`, the old message with its buttons remains in chat — the user sees stale state and accumulating clutter. Using `editMessageText` with the original `message_id` replaces the message on the spot, giving a native Mini App feel.

The `callback_message_id` field must be established at the Dispatcher level (in the "Prepare for 04" Set node) and passed down through every workflow hop. Without it, sub-workflows cannot call `editMessageText` even if they want to.

### one_time_keyboard fix (2026-04-08)

Three nodes in 04_Menu had `one_time_keyboard: true`: **Send Main Menu (Back)**, **Send Menu After Cancel**, **Send Add Food Prompt**. After setting this to `false`, the reply keyboard persists correctly after inline interactions that don't send a new message.

### Typing action pattern (2026-04-10)

Every reply-keyboard button handler (Stats, Profile, Progress, Quests, League, Shop, Friends) has a `Typing Action` node as a **parallel dead-end branch** from the Menu Router:

```
Menu Router[n] ─┬→ RPC / Build node (main flow)
                └→ Typing Action: POST sendChatAction {action: "typing"} [dead-end]
```

This fires in parallel with the RPC call. Telegram shows "печатает..." within ~100ms. If the fire-and-forget fails, the main flow is unaffected. Fire-and-forget HTTP — do not wait for response.

### answerCallbackQuery pattern (2026-04-10)

The `callback_query` spinner (loading indicator on the tapped button) only clears when `answerCallbackQuery` is called. Without it, users see the spinner for ~3 seconds — which feels like a frozen bot and encourages repeated taps.

Added as a parallel dead-end from Command Classifier[0]:

```
Command Classifier[0] ─┬→ Menu Router (main flow)
                        └→ Answer Callback Query [dead-end, fire-and-forget]
```

The `callback_query_id` needed by `answerCallbackQuery` must be passed through the Dispatcher's "Prepare for 04" Set node.

### Voice transcription fix (2026-04-10)

Voice message logs were always missing `raw_user_input` (515+ historical records). The `Parse AI` node was reading `message.text` (empty for voice) instead of `$('Transcribe').item.json.text` (the Whisper transcript). Fixed: Parse AI now conditionally reads from the Transcribe node for voice messages, and `RPC Log Meal` passes it via `p_raw_user_input`.

### "One Menu" implementation (2026-04-11)

See [[concepts/one-menu-ux]] for full details. The key principle: exactly one active navigation screen in chat at any time. When a reply-keyboard button is tapped, the previous menu message is deleted.

**Chain pattern (Stats, Profile, Progress — identical for all three):**

```
Build [Screen] Text ─┬─→ Is Callback? → Send Response → Extract Menu ID → Save Menu ID
                     └─→ Delete Old Menu   [dead-end, fire-and-forget]
```

- `Delete Old Menu`: parallel branch, fires `deleteMessage` with `last_bot_message_id` from Merge Data; `onError: continueRegularOutput` silently handles id=0 or already-deleted messages
- `Extract Menu ID`: `($json.result || $json).message_id` — universal for both HTTP Request and Telegram node response shapes
- `Save Menu ID`: calls `save_bot_message` RPC after sending, to store the new `message_id` in `users.last_bot_message_id`

**Critical distinction:** Only navigation screen messages call `save_bot_message`. Food logs, AI recognition results, cron notifications, and payment confirmations must never call it — doing so would cause the next nav tap to delete user content.

### answerCallbackQuery and callback_query_id (2026-04-11 addition)

The Dispatcher "Prepare for 04" Set node was updated to include `callback_query_id` (in addition to the existing 30 fields). An `Answer Callback Query` node was added to 04_Menu as a parallel dead-end from Command Classifier[0] — fires immediately on every inline callback tap to clear the button spinner.

### Affected workflows (2026-04-08 migration)

- **04_Menu** (`sxzbSc61YuHFbV4i`): Edit Options and Delete Confirmation converted from Telegram nodes to HTTP Request `editMessageText`; removed 4 intermediate Remove Buttons + Passthrough nodes; added Build Delete Result Code node
- **04.2_Edit_StatsDaily** (`YebaQhipJrKZcGRO`): Send List, Send List1, Send Edit Prompt converted to `editMessageText`; `message_id` field added throughout; `callback_message_id` threaded into Merge Data

### One Menu rule extends to invoice sends (2026-04-13)

The One Menu UX principle was extended to the payment flow. A `Delete Old Menu` node (fire-and-forget parallel branch) was added before `Send Invoice` in 10_Payment. This deletes the navigation menu that was open when the user triggered payment.

Without this, the old Profile/Plans menu remains visible below the invoice — the user has two "active" screens simultaneously, violating the One Menu contract.

**Pattern (same as reply-keyboard screens):**
```
Build Invoice Data ─┬→ Send Invoice (main flow)
                    └→ Delete Old Menu: deleteMessage(last_bot_message_id) [dead-end]
```

### Back button Progress: Markdown → HTML fix (2026-04-13)

`Edit Progress (inline)` node used `parse_mode: Markdown`. This caused Telegram 400 errors for users whose `username` or `first_name` contains underscore characters (`_`), because `_` is the Markdown italic delimiter.

Fix applied:
1. All `*bold*` formatting → `<b>bold</b>`
2. `parse_mode: Markdown` → `parse_mode: HTML`
3. `onError: continueRegularOutput` added — Telegram formatting errors no longer silently kill the Progress handler

**General rule:** Use `parse_mode: HTML` everywhere. HTML is more predictable with user-generated content (names, food names) because `<` and `>` are the only characters that need escaping, and those are rare in names. Markdown `_`, `*`, `[`, `]` are common in usernames and food descriptions.

### Delete Old Menu race condition fix (2026-04-14)

**Проблема:** `Delete Old Menu` ранее всегда срабатывал как параллельная ветка из ноды `Build Text`. Это вызывало race condition для inline-callbacks: `editMessageText` редактировал то же сообщение, которое пыталась удалить нода `Delete Old Menu`. В результате `deleteMessage` падал с ошибкой 400 "message can't be deleted", либо удалял сообщение раньше, чем `editMessageText` успевал его обновить.

**Старый паттерн (неверный):**
```
Build [Screen] Text ─┬─→ Is Callback? → [true] editMessageText
                     │                 → [false] Send Response → Extract/Save Menu ID
                     └─→ Delete Old Menu   [dead-end, ВСЕГДА]
```

**Новый паттерн (правильный):**
```
Build [Screen] Text → Is Callback? → [true]  editMessageText                  (нет Delete)
                                   → [false] Send Response ─┬─→ Extract/Save Menu ID
                                                             └─→ Delete Old Menu [dead-end]
```

**Правило:** `Delete Old Menu` должен срабатывать ТОЛЬКО из ветки `Is Callback?[false]` — то есть только когда отправляется новое сообщение (reply-keyboard), а не когда редактируется inline. При inline-callbacks сообщение уже обновляется через `editMessageText` — удалять его не нужно и вредно.

Применено к экранам Stats, Profile, Progress в `04_Menu`.

### Send Progress parse_mode fix (2026-04-14)

`Send Progress (inline)` нода имела `parse_mode: Markdown`, тогда как `Build Progress Text (inline)` генерирует HTML-разметку (`<b>...</b>`, `<code>...</code>`). Несовместимость вызывала ошибки рендеринга или Telegram 400.

Исправлено: `parse_mode: Markdown` → `parse_mode: HTML` в `Send Progress (inline)`.

**Общее правило:** При инлайнировании sub-workflow (вставке логики из 08_Progress в 04_Menu) — проверять совместимость `parse_mode` между нодой, генерирующей текст, и нодой, его отправляющей. Они должны совпадать.

## Related Concepts

- [[concepts/one-menu-ux]]
- [[concepts/n8n-data-flow-patterns]]
- [[concepts/n8n-performance-optimization]]
- [[concepts/noms-architecture]]
- [[concepts/access-credentials]]

## Sources

- [[daily/2026-04-08.md]] — Initial implementation: sendMessage → editMessageText migration for 04_Menu and 04.2; one_time_keyboard fix
- [[daily/2026-04-10.md]] — Typing action × 7 buttons; answerCallbackQuery parallel branch; voice transcription raw_user_input fix
- [[daily/2026-04-11.md]] — "One Menu" implementation (9 new nodes: Delete/Extract/Save chains × 3 screens); callback_query_id added to Dispatcher Prepare for 04; Answer Callback Query node added to 04_Menu
- [[daily/2026-04-13.md]] — One Menu extended to invoice sends (Delete Old Menu before Send Invoice in 10_Payment); Back button Progress: parse_mode Markdown → HTML fix for underscore names; onError continueRegularOutput
- [[daily/2026-04-14.md]] — Delete Old Menu race condition fix: теперь срабатывает ТОЛЬКО из Is Callback?[false] ветки (Stats, Profile, Progress); Send Progress parse_mode Markdown → HTML (несовместимость с HTML-генерацией Build Progress Text)
