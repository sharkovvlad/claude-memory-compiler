---
title: "Stars Subscriptions PROVIDER_ACCOUNT_INVALID — client top-up restricted (resolved)"
aliases: [stars-subscriptions-botfather-prereq, stars-recurring-provider-account-invalid, stars-subscription-setup, stars-balance-insufficient]
tags: [payment, stars, telegram-api, gotcha, resolved]
status: active
sources:
  - "daily/2026-05-28.md"
  - "daily/2026-05-31.md"
  - "concepts/architecture-registry.md"
created: 2026-05-28
updated: 2026-05-31
---

# Stars Subscriptions PROVIDER_ACCOUNT_INVALID — client top-up restricted (resolved)

> 🔥 **HUB** — read BEFORE diagnosing `PROVIDER_ACCOUNT_INVALID` on
> Stars-recurring payments. Original 2026-05-28 H1 hypothesis (undocumented
> BotFather toggle) **disproven** by Telegram Support 2026-05-31.

## TL;DR (updated 2026-05-31 after @BotSupport reply)

**One-time Stars payments work out-of-the-box.** Just call `sendInvoice` /
`createInvoiceLink` with `currency='XTR'`, no setup. ✅

**Stars Subscriptions (recurring) ALSO work** with no BotFather setup. The
`PROVIDER_ACCOUNT_INVALID` error is **a client-side Telegram bug** triggered
when the user has 0 Stars balance AND taps "Top up balance" inside the
payment modal — the internal `@PremiumBot` top-up gateway is currently
restricted (Apple/Google antitrust pressure).

**Fix is UX-only:** show a warning before the payment modal opens, asking
the user to top up Stars manually first via Telegram Settings → My Stars
→ Top Up Balance. NOMS implementation: `payment.stars_balance_warning` ×
13 langs + send_message прямо перед sendInvoice/createInvoiceLink (mig 414
+ handlers/payment.py:_handle_pay_stars, 2026-05-31, PR #пнр).

## Resolution timeline

| Дата | Что |
|---|---|
| 2026-05-28 | Stage 2 раскатился (PR #214 → #216, mig 365). Live-test показал PROVIDER_ACCOUNT_INVALID. Гипотеза H1 — BotFather toggle. Hotfix PR #217 отключил monthly recurring (`_STARS_SUBSCRIPTION_PLANS = frozenset()`). |
| 2026-05-28 | Issue #218 открыт владельцу: написать саппорту Telegram, ждать ответ. |
| 2026-05-31 20:16 UTC | @BotSupport ответил: «It is not an issue with your bot specifically. Payments towards most bots through @PremiumBot are restricted due to external circumstances. ... It should work fine if user has enough stars.» → **H2 подтверждена**, H1 disproven. |
| 2026-05-31 (этот PR) | Revert PR #217: `_STARS_SUBSCRIPTION_PLANS = frozenset({"monthly"})`. Un-skip 2 integration tests. + mig 414: `payment.stars_balance_warning` × 13 langs. + `_handle_pay_stars`: send_message warning перед sendInvoice/createInvoiceLink. Issue #218 закрыт. |

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

## Root cause analysis — 4 hypotheses considered

### H1: undocumented BotFather setup ❌ DISPROVEN (2026-05-28)

Owner-verified via screenshots from `@BotFather → /mybots → @nomsaibot`:
* **Bot Settings → Payments** — lists only fiat providers (Redsys,
  ЮKassa, PayMaster, ECOMMPAY, Bank 131, Robokassa, PayBox.money).
  No mention of Stars subscriptions.
* **Bot Settings → Telegram Stars** — placeholder text + «Learn More»
  button only. No subscription configuration UI.
* **Monetization section** — two entries: Payments + Telegram Stars.
  No separate «Subscriptions» item.

Conclusion: **BotFather UI does not expose any subscription setup
toggle** for @nomsaibot. H1 ruled out.

### H2: regional limitation (user-side) — POSSIBLE

Per [Bot API docs](https://core.telegram.org/bots/api), Telegram has a
`stars_purchase_blocked` field — Stars features can be **regionally
restricted on the USER side**. Owner tested from EU (Spain). Stars
Subscriptions may not be fully rolled out to EU yet (first-rollout
regions are typically US / GCC / SE Asia / LATAM).

**Discriminator:** have one tester from US/SA/UAE/India click the same
invoice URL. If it works → confirmed regional; NOMS adds per-user region
detection and falls back to one-time Stars for restricted users.

### H3: Telegram-internal whitelist (most likely — owner-side action required)

Telegram operates many features behind internal gating. Stars
Subscriptions was launched in Bot API 8.0 (Nov 2024) but may still
be on a gated/whitelist rollout for bots, not exposed via BotFather.
Activation only via `@BotSupport` request.

**Escalation:** owner contacts `@BotSupport` (template in tracking
issue #218). Wait 1-7 days for Telegram response.

### H4: bot account has stale fiat provider that conflicts

@nomsaibot has 7 fiat payment providers listed in BotFather (Redsys/
ЮKassa/etc) — these were likely added during n8n-era experiments and
NOT cleaned up. For Stars ONE-TIME, Telegram bypasses provider entirely
(direct XTR). For Stars SUBSCRIPTIONS with `subscription_period`,
Telegram may attempt to route recurring billing through the bot's
configured payment provider — finds an invalid/test-only one — fails
with `PROVIDER_ACCOUNT_INVALID`.

**Discriminator:** owner removes ALL fiat providers from BotFather
(`Payments → Redsys → Delete`, repeat). Test Stars subscription again.
If now works → H4 confirmed. **Caveat:** this removes Stripe etc.
NOMS uses Stripe (PR #134 era), so this would break fiat too. Don't do
H4-test without first verifying Stripe is wired through a DIFFERENT
mechanism (Stripe webhook, not BotFather provider).

### Best path: H2 cheap-test first, then H3 escalation

Cost ladder:
1. **H2** — 5 min — ask non-EU tester to click URL (no permanent change)
2. **H3** — 30 sec write to @BotSupport, then 1-7 day wait
3. **H4** — destructive (removes fiat providers); LAST resort after
   verifying Stripe doesn't depend on BotFather payment list

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

## Admin observability — Stars balance & transactions (2026-06-01)

Сразу после re-enable Stars Subscriptions (mig 414) owner спросил «куда приходят и как посмотреть». Telegram Bot API даёт `getMyStarBalance` + `getStarTransactions`. Реализованы **3 уровня доступа** для admin:

### 1. CLI на VPS — `scripts/stars_balance.py` (PR #272, merged)

```bash
sudo -u taskbot bash -c "cd /home/taskbot/noms && set -a && source .env && set +a && \
    /home/taskbot/noms/venv/bin/python scripts/stars_balance.py [--limit N] [--json]"
```

Output: balance + last N tx (default 20, max 100) с USDT estimate. `--json` для машинного чтения.

### 2. Daily digest cron — `StarsDigestCron` (PR #275)

`crons/stars_digest.py`, schedule `06:30 UTC` (между `subscription_lifecycle :00` и `reminders :20`). Filter транзакций за последние 24h. **Молчит когда 0 tx** — не спамит admin chat. При активности → HTML message в `ADMIN_CHAT_ID`: balance + USDT estimate + IN/OUT counts + last 10 tx с partner info.

### 3. On-demand bot commands — `/admin_stars` & `/admin_stars_export` (PR #275)

`handlers/admin_stars.py`. Fast-path в `webhook_server._route_or_forward_locked` — если `text.startswith('/admin_stars')` AND `chat_id == ADMIN_CHAT_ID` → handle directly, BYPASSING dispatch_with_render/menu_v3 (паттерн как `admin_payout_*` callbacks).

- **`/admin_stars [N]`** — баланс + last N в HTML message (default 20, max 50)
- **`/admin_stars_export [N]`** — CSV файл через sendDocument (default 100, max 500). Пагинация когда N>100 (Telegram API cap).

Non-admin chat_id шлёт `/admin_stars` → fast-path не срабатывает, текст идёт в обычный AI handler (silent ignore без security exposure).

### Куда уходят Stars

`@nomsaibot` аккаунт. Просмотр через `@BotFather → Bot Settings → Payments` (или `Stars`). Вывод: `convertStarToTon` Bot API → TON wallet → Fragment. Telegram retains ~30%, min payout 1000 ⭐. Estimate в Python: `usdt_net = stars * 0.006 * 0.7`.

### Live state (01.06.2026)

Баланс @nomsaibot = **580 ⭐** (~$2.44 net). 1 IN транзакция от tid 1670095403 (Евгения) — первая реальная Stars-покупка.
