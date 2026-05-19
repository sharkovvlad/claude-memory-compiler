---
title: "Telegram invoice — UI editing constraints (editMessageText silently rejected)"
aliases: [invoice-back-button, telegram-payments-edit, invoice-reply-markup]
tags: [telegram, payments, ux, gotcha]
sources:
  - "daily/2026-05-19.md Stage 6 (PR #118, #121)"
  - "Live test tid=786301802"
created: 2026-05-19
updated: 2026-05-19
---

# Telegram invoice — UI editing constraints

**TL;DR:** Сообщение, созданное через `sendInvoice`, имеет специальный payload-lock. **`editMessageText` silently отклоняется** (Telegram возвращает success-like response, но UI не обновляется). **`deleteMessage` работает**. `reply_markup` можно задать только при создании invoice (mix pay button + own callback buttons), нельзя изменить через `editMessageReplyMarkup`. Pattern Back-кнопки на invoice — glue Back в invoice's `reply_markup` + handler делает `delete + send_new`, не `edit`.

## Симптомы (как ловится)

1. Юзер видит invoice (например для Stars-оплаты).
2. У invoice есть Back-кнопка как inline-callback под pay button.
3. Юзер жмёт Back → handler в Python вызывается, callback fires.
4. Handler возвращает envelope `edit_existing` с новым text/reply_markup.
5. **Telegram отвечает 200 OK, ничего не меняет на экране.** UI стоит на invoice.

Молчаливый bug — нет error в журнале, нет 400 от Bot API. Только UX-симптом «кнопка не работает».

## Что делать (pattern для Back на invoice)

1. **Glue Back в invoice's `reply_markup`** прямо при `sendInvoice` (как inline-кнопка под Pay button, в том же payload).
2. **Handler Back на invoice** → envelope **`delete_only` + `send_new`**, не `edit_existing`:
   - `deleteMessage(chat_id, invoice_message_id)` — работает.
   - `sendMessage(chat_id, new_text, reply_markup=new_kb)` — новое сообщение.
3. Save `users.last_bot_message_id = new_message_id` для one-menu pattern.

## Что НЕ работает

- `editMessageText` на invoice — silently rejected (по нашим тестам 2026-05-19, tid=786301802).
- `editMessageReplyMarkup` на invoice — same.
- `editMessageCaption` — same (invoice не имеет caption в обычном смысле).

## Что работает

- `deleteMessage` на invoice — OK.
- `sendInvoice` с `reply_markup` содержащим custom inline-buttons рядом с pay button — OK.
- `answerPreCheckoutQuery` / `successful_payment` lifecycle — standard.

## Live verification

PR #121 финализировал pattern: Stars invoice Back-button через glue в reply_markup + delete+send_new.
Тестировано на tid=786301802, 2026-05-19. Все варианты edit fail'ились молча; delete+send_new прошёл с первого раза.

## Implications для архитектуры

- **One-menu pattern** на invoice screens ломается стандартным way — нельзя `editMessageText` через `services/telegram_send.py` envelope `edit_existing`.
- Handler payment (handlers/payment.py) использует `delete_and_send_new` render strategy для всех Back-flows на invoice.
- Если в будущем будут другие invoice flows (например, payout receipts) — заранее закладывать delete+send_new pattern, не пытаться edit.

## Related

- [[concepts/payment-integration]] — общий payment UX (regional pricing, Stripe/Stars/TON)
- [[concepts/one-menu-ux]] — `users.last_bot_message_id` + delete previous menu pattern
- [[concepts/save-bot-message-contract]] — обязательство всех flows сохранять mid
- Stage 6 handover `handover/2026-05-19_stage6_payment_python.md`
