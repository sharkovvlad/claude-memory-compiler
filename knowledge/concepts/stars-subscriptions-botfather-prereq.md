---
title: "Telegram Stars Subscriptions — undocumented BotFather prerequisite"
aliases: [stars-subscriptions-botfather-prereq, stars-recurring-provider-account-invalid, stars-subscription-setup]
tags: [payment, stars, telegram-api, gotcha, p0]
status: active
sources:
  - "daily/2026-05-28.md"
  - "concepts/architecture-registry.md"
created: 2026-05-28
updated: 2026-05-28
---

# Telegram Stars Subscriptions — undocumented BotFather prerequisite

> 🔥 **HUB** — read BEFORE enabling Stars Subscriptions in any new bot or
> re-enabling NOMS' disabled flow.

## TL;DR

**One-time Stars payments work out-of-the-box.** Just call `sendInvoice` /
`createInvoiceLink` with `currency='XTR'`, no setup. ✅

**Stars Subscriptions (recurring) require BotFather setup** that Telegram
does NOT document anywhere. Skip it → users see
`Error: PROVIDER_ACCOUNT_INVALID` in the payment modal when they click
the invoice link.

## The incident (2026-05-28)

Stage 2 of Stars Recurring (mig 365, PR #214 → #216) shipped:
* `_handle_pay_stars` routes `plan_id='monthly'` to
  `createInvoiceLink` with `subscription_period=2592000`.
* Other plans (quarterly / yearly) still use `sendInvoice` (one-time).

Live-test on accounts 786301802 + 417002669 from EU iOS/desktop:

```
Bot → createInvoiceLink: HTTP 200 OK ✅
Bot → sendMessage(URL button "Pay ⭐ 310"): HTTP 200 OK ✅
User → tap button → Telegram payment modal opens
Telegram payment modal → "Error: PROVIDER_ACCOUNT_INVALID" ❌
```

The Telegram **Bot API** accepted the call and returned a valid
`https://t.me/$...` URL. The failure is in Telegram's **MTProto payment
backend** when the client opens the URL — it tries to validate the
bot's payment provider account for the **subscription** capability and
fails.

For comparison: identical `sendInvoice` payload (same `currency='XTR'`,
same `prices`, same `payload`) for quarterly/yearly one-time Stars
**works** on the same bot, same accounts. The ONLY new parameter
between working and broken: `subscription_period=2592000`.

## Root cause hypothesis

Telegram treats `subscription_period` as a separate capability that
requires the bot to be **explicitly enabled for Star Subscriptions** by
its owner via BotFather. The path is **not in Telegram's public docs**
as of Bot API 8.0 (Nov 2024) — neither the changelog
([core.telegram.org/bots/api-changelog](https://core.telegram.org/bots/api-changelog))
nor `/bots/payments-stars` mentions a setup step.

Likely location in BotFather (unverified — owner has to dig):
```
@BotFather → /mybots → @nomsaibot → Bot Settings → Configure Stars Subscriptions
```
OR:
```
@BotFather → /mybots → @nomsaibot → Payments → Star Subscriptions → ...
```

A separate possibility: bot needs to be **whitelisted by Telegram**
(send request to `@BotSupport`) before subscriptions are allowed.

## NOMS current state (post 2026-05-28 hotfix)

`handlers/payment.py:_STARS_SUBSCRIPTION_PLANS = frozenset()` —
**no plans use subscription_period right now.** All Stars plans
(monthly/quarterly/yearly) route through one-time `sendInvoice`. This
restores the pre-Stage-2 working behavior.

`migrations/365_stars_recurring_rpcs.sql` infrastructure is **live in DB
and harmless**: `activate_subscription` accepts `p_is_recurring`,
`renew_recurring_subscription` exists, RPC v3 renders Stars-recurring
correctly. Nothing fires because Python never sets the flag.

`handlers/payment.py` cancel/resume Stars-recurring branches stay in
place — they're inert (no recurring subs exist → branches never reached).

Tests covering the Stars-subscription path: `pytest.mark.skip` with the
re-enable reason (search for `stars-subscriptions-botfather-prereq`).

## Re-enabling checklist

When BotFather setup is confirmed:

1. **Verify in BotFather** that Stars Subscriptions is now enabled for
   @nomsaibot (screenshot for KB).
2. **Test in dev first:** create test invoice with `subscription_period`
   via Postman / curl using `@nomsaibot`. Open URL on iOS + desktop +
   Android — confirm no `PROVIDER_ACCOUNT_INVALID`.
3. **Revert hotfix:**
   ```python
   # handlers/payment.py
   _STARS_SUBSCRIPTION_PLANS: frozenset[str] = frozenset({"monthly"})
   ```
4. **Un-skip tests:** remove `@pytest.mark.skip` decorators on
   `test_pay_stars_monthly_uses_create_invoice_link_with_subscription`
   and `test_pay_stars_monthly_create_invoice_link_failure_returns_error`.
5. **Run live-test** with the protocol below.

## Live-test protocol (for re-enable session)

Setup: account 786301802 (Premium subscription already exists OR fresh
Free account; need 310⭐ balance — buy from
[Fragment.com](https://fragment.com/stars) — cheapest in 2026, ~$4 via
TON).

| Step | Expected |
|---|---|
| 1. Profile → 👑 Премиум → Месяц → ⭐ Stars | Bot sends sendMessage with URL-button `Pay ⭐ 310` (NOT invoice bubble — that would mean still using `sendInvoice`) |
| 2. Tap URL-button | Telegram payment modal opens, header shows the bot title, body mentions **«subscription»** keyword, button «Подтвердить и заплатить ⭐ 310» |
| 3. Confirm | Bot sends single «Премиум активирован» message |
| 4. Profile → Управление подпиской | Renders `«🔄 Авто-продление: вкл»` |
| 5. Telegram Settings → Stars → My Subscriptions | @nomsaibot appears in list with next-charge date |
| 6. Profile → Управление подпиской → Отменить подписку | Bot calls `editUserStarSubscription(is_canceled=true)` → re-render shows `«Авто-продление: выкл»` |
| 7. Telegram Settings → Stars → My Subscriptions → @nomsaibot | Subscription marked as «cancelled» (access keeps to expiration date) |
| 8. Profile → Управление подпиской → Возобновить | Bot calls `editUserStarSubscription(is_canceled=false)` → back to «вкл» |

If step 2 returns `PROVIDER_ACCOUNT_INVALID` → re-do BotFather setup.

If step 6 fails with `INVALID_CHARGE_ID` or similar → check
`user_subscriptions.telegram_payment_charge_id` was populated from
successful_payment (mig 365 INSERT). Look at
`webhook_server.py:_handle_successful_payment` — the
`telegram_payment_charge_id` field.

## Side-lesson — `provider_token` for Stars

Per [aiogram Stars docs](https://docs.aiogram.dev/en/v3.22.0/api/methods/edit_user_star_subscription.html):
> «The parameter `provider_token` of the methods `sendInvoice` and
> `createInvoiceLink` must be omitted for payments in Telegram Stars.»

**Don't** pass `provider_token=""` (empty string). **Omit the field entirely.**
NOMS code today already omits it (`handlers/payment.py:423` builds the
payload dict without that key). Re-check on every refactor — adding
`provider_token` will silently break Stars (current Telegram behavior:
accept empty in some clients, reject as `PROVIDER_ACCOUNT_INVALID` in
others).

## Cross-references

* `MEMORY.md` — «Phase 6.4» note about Stars subscriptions.
* `claude-memory-compiler/daily/2026-05-28.md` — full incident timeline.
* `concepts/architecture-registry.md` — payment target = Python authoritative.
* `concepts/subscription-management-headless.md` — mig 362 RPC v3 logic.
* `migrations/365_stars_recurring_rpcs.sql` — DB-side infrastructure (live, dormant).
