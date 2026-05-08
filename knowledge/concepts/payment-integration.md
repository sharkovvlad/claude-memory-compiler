---
title: "Payment Integration"
aliases: [stars, stripe, ton, usdt, payment-flow, subscriptions, premium]
tags: [payments, telegram, stars, stripe, ton, subscriptions]
sources:
  - "daily/2026-04-09.md"
  - "daily/2026-04-10.md"
  - "daily/2026-04-11.md"
  - "daily/2026-04-13.md"
  - "daily/2026-04-16.md"
  - "daily/2026-04-17.md"
  - "daily/2026-04-27.md"
created: 2026-04-09
updated: 2026-04-27
---

# Payment Integration

Three payment methods (Telegram Stars, Stripe card, TON/USDT) integrated without a dedicated "Payments" menu. Entry points are the Profile screen and Shop screen.

## Key Points

- **Entry points:** Profile screen (subscription status + [👑 Go PRO]) and Shop screen ([👑 PRO] teaser for free users) — no separate "Payments" menu item
- **Tier-first UX:** User selects a plan (Monthly/Quarterly/Yearly) first, then chooses payment method (Card / Stars / USDT)
- **Regional pricing:** `get_all_plan_prices(telegram_id)` returns prices in user's currency (EUR for ES, RUB for RU) from `subscription_prices` table; one RPC replaces 3 parallel HTTP calls
- **Telegram Stars:** `sendInvoice` via Telegram API; `successful_payment` must be in Dispatcher's `update_types`; prices from `subscription_prices.stars_price`
- **Stripe:** `webhook_server.py` FastAPI; `create-checkout` returns `RedirectResponse(302)` — NOT JSON; HTTP not HTTPS (server has no SSL cert — HTTPS causes TLS error)
- **`workflowInputs` must be explicit:** `Go to 10_Payment` node must pass all 8 fields; empty `{}` breaks the entire payment flow silently

## Details

### Workflow architecture (10_Payment, ID: `xYKmBTWI4c0VoSqs`)

Payment Router (Switch node) branches on `command` value — must read from `$('Merge Data').item.json.command`, NOT `$json.command` (which is clobbered by any HTTP Request node before it):

| Output | Condition | Destination |
|--------|-----------|-------------|
| 0 | `cmd_premium_plans` or `cmd_select_plan_*` | Plans / Method Selection |
| 1 | `cmd_pay_stars_*` | Stars invoice |
| 2 | `cmd_pay_crypto_*` | Crypto instructions |
| 3 | `cmd_enter_promo` | Promo code entry |
| 4 | `cmd_premium_plans_list` | Full plan list for premium users |

### Payment UX v2: tier-first flow (2026-04-10)

The original Plans screen had 7 buttons (3 plans × 3 methods) on one screen. Replaced with a two-screen flow:

**Screen 1 — Plan selection:** 3 buttons with price in user's local currency (`cmd_select_plan_monthly/quarterly/yearly`), sourced from `get_all_plan_prices(telegram_id)` RPC. Promo code + Back buttons.

**Screen 2 — Method selection:** 💳 Card (Stripe redirect), ⭐ Stars (Telegram native), 💎 USDT (TON wallet). Plan is carried in the command (`cmd_pay_crypto_quarterly` → $8 USDT). Back to plans button.

### Regional pricing (migration 051)

`get_pricing_region()` was rewritten from JSON-based lookup to reading `ref_countries.pricing_tier`. Previously returned DEFAULT for all users. `get_user_price()` was rewritten to query `subscription_prices` table. New `get_all_plan_prices(telegram_id)` returns all 3 plans with prices in user's currency + Stars count + USDT amount in a single RPC call.

**Important:** `app_constants.stars_price_*` and `app_constants.crypto_price_*` are deprecated. Source of truth is `subscription_prices.stars_price` and `subscription_prices.usdt_price`.

### Race condition pitfall — parallel price nodes

Original Plans flow used 3 parallel HTTP Request nodes (`Get Price Monthly`, `Get Price Quarterly`, `Get Price Yearly`) running simultaneously. n8n does not guarantee execution order — `Build Plans Text` was reached before all 3 completed, causing `Node 'Get Price Quarterly' hasn't been executed` errors.

**Fix:** Replace 3 parallel HTTP calls with a single `get_all_plan_prices(telegram_id)` RPC that returns all prices in one response. This is both correct and faster.

### Multiple-item fix (Limit 1 nodes)

`get_all_plan_prices` is a `RETURNS TABLE` function — Supabase returns 3 rows (one per plan). n8n creates 3 items, causing every downstream node to execute 3 times (3× editMessageText, 3× sendInvoice). Fix: `Limit 1` Code nodes (`return [$input.first()]`) placed after each price HTTP Request node to collapse 3 items into 1.

### Shop: workflowInputs not saved by n8n PUT API

n8n PUT API does not persist `workflowInputs.value` for Execute Workflow nodes. The `Go to 08.4_Shop` node always received default values (`subscription_status='free'`, `nomscoins=0`) after any deployment. Fix: added a `Get User Status` HTTP Request node at the start of 08.4_Shop that fetches fresh data from Supabase directly — making the workflow self-contained and immune to the PUT API bug.

### Double-emoji bug (PRO buttons)

Both Profile's [👑 Go PRO] and Shop's [👑 PRO] button texts had emoji prepended in code, while the `payment.go_premium_button` translation already contained `{{icon_premium}}`. Result: `👑 👑 Premium`. See [[concepts/n8n-template-engine]] for the pattern.

### Stripe HTTP bug

Stripe URL was set to `https://89.167.86.20:8443` — the FastAPI server runs without SSL (plain HTTP), so HTTPS caused an immediate TLS handshake failure. The URL must be `http://89.167.86.20:8443`. Additionally, `create-checkout` must return `RedirectResponse(302)`, not a JSON body — browsers/WebView need an HTTP redirect to follow the Stripe checkout URL automatically.

Status: Card redirects work but Stripe keys (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`) must be added to `/home/taskbot/noms/.env` before Card payments process successfully.

### Routing requirements

`cmd_select_plan_*` and `cmd_pay_crypto_*` commands must be registered in:
1. **01_Dispatcher Route Classifier:** route to `menu`
2. **04_Menu Command Classifier:** route to `payment`
3. **10_Payment Payment Router:** handle the specific command

Missing any one of these three causes a silent "Скоро!" (coming soon) response.

### Premium subscription screen (2026-04-11)

Build Plans Text now has two branches based on `isPremiumUser`:

**Branch A — `isPremiumUser = true`:** Subscription details screen showing plan name, expiry date (formatted `DD.MM.YYYY`), and payment method. Buttons: ✨/🔥/⭐ for renewing or switching to a different tier. Uses 4 new translation keys: `payment.my_subscription`, `payment.active_until` (with `{date}` placeholder), `payment.plan_label` (with `{plan}` placeholder — note: early versions used `{name}` which conflicted with `display_name`), `payment.renew_plan`.

**Branch B — `isPremiumUser = false`:** Standard plan selection screen with prices in user's currency from `get_all_plan_prices` RPC.

The `reply_markup` keyboard is now built dynamically inside Build Plans Text and passed forward, rather than being hardcoded in the Send node.

### Get Subscription node and the free-user empty-array problem

A `Get Subscription` HTTP Request node (`GET user_subscriptions?status=eq.active&order=created_at.desc&limit=1`) was added to 10_Payment. For free users, Supabase returns an empty array `[]`, which produces **0 n8n items** — causing the entire downstream chain (including Payment Router) to not execute at all.

Fix pattern:
1. `Get Subscription` uses `fullResponse: true` — always returns exactly 1 item regardless of body content
2. An `Extract Sub` Code node follows: `const body = $input.item.json.body || []; return [{ json: body[0] || {} }]` — extracts the subscription record or falls back to `{}`
3. `Build Plans Text` reads from `$('Extract Sub')` instead of `$('Get Subscription')`

This pattern is reusable whenever a Supabase REST call may legitimately return 0 rows and downstream nodes must still execute.

**Important:** `Get Subscription` must NOT be placed between `Merge Data` and `Payment Router` in the main chain — it clobbers `$json.command` (see [[concepts/n8n-data-flow-patterns]] — Get Subscription incident). It should only be on the Plans sub-path after the router has already branched. `Get Subscription` was moved to the Plans-path only (after Payment Router branches, not before it) to fix this.

### Shop Pattern A: mana block and double-emoji fix (2026-04-11)

Build Shop Text was rewritten following "Pattern A":
1. `isPremiumUser` declared first, before any text assembly
2. Mana block (text + `cmd_buy_mana` button) hidden with `if (!isPremiumUser)` — premium users have `mana_max=500` and don't need manual recharges
3. Double-emoji fix: removed `iconFreeze + ' '` and `iconMana + ' '` prefixes from button text; the `buy_freeze` and `buy_mana` translation keys already contain `{{icon_freeze}}` / `{{icon_mana}}` — prepending the icon in code caused `❄️ ❄️ Freeze`
4. Premium user button changed to "👑 Ваша подписка" → `cmd_premium_plans`
5. Edit Shop Message: `parse_mode Markdown → HTML`

Merge Data in 04_Menu also had `mana_recharges_today` missing (was `undefined`); added as `mana_recharges_today: input.mana_recharges_today || 0`.

### cmd_premium_plans routing (restored 2026-04-11)

Build Profile Text had a conditional: `isPro ? 'cmd_noop' : 'cmd_premium_plans'` — premium users tapping their subscription button got "Скоро!" (`coming_soon`). Fixed to always use `'cmd_premium_plans'` so both free and premium users reach the Plans/Subscription screen.

This fix was first applied on 2026-04-10 and then overwritten by a stale-base PUT on 2026-04-11. Had to be reapplied. See [[concepts/n8n-data-flow-patterns]] for the stale PUT base rule.

Command Classifier in 04_Menu was also updated to add `command.startsWith('cmd_select_plan_')` and `command.startsWith('cmd_pay_crypto_')` to the payment route, preventing these commands from falling through to `coming_soon`.

### parse_mode for payment screens

All payment UI nodes must use `parse_mode: HTML`, not Markdown. Markdown V1 silently fails when combined with emoji in text. Formatting: `<b>title</b>` not `*title*`.

### Subscription renewal reminders fix (2026-04-13)

**Root cause:** PostgREST does NOT support `now()+interval '2 days'` in REST filter expressions — it silently ignores the condition and returns ALL active users. As a result, `subscription_lifecycle.py` was sending "expires in 3 days" messages to every active subscriber every day.

**Fix:** New `cron_get_renewal_candidates()` RPC that performs the date math in SQL:
```sql
-- Returns users whose subscription expires in 1-3 days
SELECT telegram_id, language_code, display_name, subscription_plan, expires_at
FROM user_subscriptions us
JOIN users u USING (telegram_id)
WHERE us.status = 'active'
  AND us.expires_at >= now()
  AND us.expires_at < now() + interval '3 days'
  AND is_bot = false;
```

**4 additional fixes in `subscription_lifecycle.py`:**
1. Uses new RPC instead of REST query
2. Real `{days}` calculation: `ceil((expires_at - now) / 86400)` — was always "3 days" before
3. `payment.expired_cta` translation key instead of hardcoded "👑 Renew" string
4. `{name}` personalization in renewal messages

**Cron schedule fix:** `main.py` changed `hour=6` → `hour=12` (12:00 UTC) to avoid sending renewal reminders at 06:00 when users in many timezones are asleep.

### Subscription UX improvements (2026-04-13)

**Bug fixed: `{name}` in plan_label:** Translation key `payment.plan_label` used `{name}` as a placeholder (e.g., "Тариф: Vladislav"), but `{name}` was being substituted with `display_name` (user's first name) instead of the plan name. Fixed: placeholder renamed to `{plan}` in all 13 languages. Updated in n8n Build Plans Text to pass `plan: planName`.

**3 new translation keys × 13 languages:**
| Key | Placeholders | Description |
|-----|-------------|-------------|
| `payment.days_remaining` | `{days}` | "⏳ Осталось: {days} дней" — shown on premium subscription screen |
| `payment.renew_current` | — | "Продлить текущий" button label |
| `payment.all_plans` | — | "Все тарифы" button label |

**New premium subscription screen buttons:**
- [Продлить текущий] → `cmd_premium_plans_list` (renew at current tier)
- [Все тарифы] → `cmd_select_plan_*` flow (switch tier)

Replaced the old 3 separate tier buttons ([✨ Monthly] [🔥 Quarterly] [⭐ Yearly]) with these 2 cleaner buttons.

**New callback:** `cmd_premium_plans_list` added to Payment Router (Output 4) and registered in Dispatcher + 04_Menu Command Classifier.

### Regional Stars and USDT prices in subscription_prices (2026-04-13, migration 059)

**Migration 059** added `stars_price INTEGER` and `usdt_price NUMERIC(10,2)` columns to the `subscription_prices` table. 30 rows filled: 10 regions × 3 plans.

`get_all_plan_prices()` was updated to read Stars and USDT prices from the table instead of `app_constants`. This makes regional Stars pricing possible (previously all regions paid the same Stars count).

**Deprecated:** `app_constants.stars_price_monthly/quarterly/yearly` and `app_constants.crypto_price_*` — source of truth is now exclusively `subscription_prices`.

**n8n extraction (2 new nodes):**
- `Get Stars Price` — HTTP Request: `get_all_plan_prices` RPC, reads `stars_price` for selected plan
- `Get Crypto Price` — HTTP Request: `get_all_plan_prices` RPC, reads `usdt_price` for selected plan

Both nodes followed by `Limit 1` Code nodes (see RETURNS TABLE flickering fix below).

**ton_payment_checker.py updated:**
- `PLAN_AMOUNTS` dict replaced with `_load_price_ranges()` function
- Reads `usdt_price` per plan from `subscription_prices` table at startup
- Notification on successful payment uses `payment.activated_body` translation key instead of hardcoded text

### RETURNS TABLE flickering fix — Limit 1 pattern (2026-04-13)

**Problem:** `get_all_plan_prices` is a `RETURNS TABLE` PostgreSQL function. Supabase PostgREST returns 3 rows (one per plan). When n8n calls this via HTTP Request, it creates **3 n8n items**. Every downstream node executes **3 times** — resulting in triple `editMessageText` (screen flickers), triple `sendInvoice` (3 invoices sent).

**Fix:** `Limit 1` Code node placed after each HTTP Request that calls a `RETURNS TABLE` RPC:
```javascript
return [$input.first()];
```

This collapses 3 items back into 1 before any downstream node sees the data.

**Scope:** 4 `Limit 1` nodes added — one after each price-fetching HTTP Request:
- After `Get All Prices` (for Plans screen)
- After `Get Stars Price` (for Stars invoice)
- After `Get Crypto Price` (for USDT instructions)
- After `Get Sub Details` (for premium screen)

Note: Downstream Code nodes that need all 3 plan prices (e.g., for building the plans keyboard) still use `$('Get All Prices').all()` — the Limit 1 only applies to the item chain, not to cross-node references.

### Free user flow fix — Get Subscription positioning (2026-04-13)

Expanded the fix documented in the "Get Subscription node and the free-user empty-array problem" section:

`Get Subscription` was previously placed in the main chain before `Payment Router`, causing: (1) `$json.command` clobbering, (2) 0 items for free users stopping all downstream execution.

Final architecture:
```
Merge Data → Payment Router → [branch 0: Plans path]
                                  → Get Subscription (fullResponse: true)
                                  → Extract Sub
                                  → Build Plans Text
```

`Get Subscription` is now exclusively on the Plans branch (Output 0), invoked only when the user explicitly navigates to plans/subscription. It is not in the main chain.

### Back button Progress: Markdown → HTML fix (2026-04-13)

`Edit Progress (inline)` node had `parse_mode: Markdown`. User names containing underscores (e.g., a `username` with `_`) caused Telegram to return a 400 error because `_` is the Markdown italic delimiter.

Fix:
- All `*...*` bold markers → `<b>...</b>`
- `parse_mode: Markdown` → `parse_mode: HTML`
- `onError: continueRegularOutput` added — Telegram formatting errors no longer silently kill the handler

### One Menu in payment: Delete Old Menu before invoice (2026-04-13)

The One Menu UX rule (see [[concepts/one-menu-ux]]) was extended to invoice sends. A `Delete Old Menu` node was added before `Send Invoice` in 10_Payment, firing `deleteMessage` with `last_bot_message_id` as a parallel dead-end branch. This ensures stale navigation menus are cleaned up when the invoice replaces the screen.

### Переход Stripe sandbox → live (2026-04-16)

**Текущее состояние:** Stripe работает в sandbox-режиме — в `.env` на VPS вероятно лежат тестовые ключи (`sk_test_...`, `whsec_test_...`).

**Причины почему может быть sandbox:**
1. В `.env` на VPS тестовый ключ вместо боевого (`sk_live_...`)
2. Webhook endpoint зарегистрирован в Stripe Dashboard в тестовом режиме
3. Stripe аккаунт не прошёл KYC/активацию

**Чеклист для перехода на live:**

В Stripe Dashboard:
- Заполнить бизнес-профиль (страна, тип бизнеса, банковский счёт)
- Пройти верификацию (документы, налоговые данные) — занимает 1-3 дня
- Получить боевые ключи: `sk_live_...` и `pk_live_...`
- Создать webhook endpoint → получить `whsec_live_...`

На VPS в `.env`:
```bash
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_live_...
```

В коде ничего менять не нужно — ключи берутся из `.env`.

**Условия для перехода:**
- Только когда есть реальные пользователи готовые платить
- Stripe аккаунт верифицирован
- Весь payment flow протестирован в sandbox без багов
- Текущий статус: payment не в фокусе (приоритет — Squad/Ambassador)

### Nav Stack миграция — Phase 5 (2026-04-17)

**Костыль `subscription_source` убран.** До Phase 5 Merge Data хранил `subscription_source` (profile/progress) — текстовую "записку" для Back button. Build Plans Text Back: `subscription_source === 'profile' ? 'cmd_get_profile' : 'cmd_back_to_progress'`.

**После Phase 5:** nav_stack корректно отражает entry path: `[profile, premium_plans]` или `[progress, premium_plans]`. Back callback универсально `cmd_back` → nav_stack решает куда.

**10_Payment (34→35 нод):**
- Build Plans Text: 2× Back callback → `cmd_back`
- **Push Nav (Plans)** — `p_screen='premium_plans'`, fire-and-forget параллельно Build Plans Text
- Forward-nav (Plans ↔ Methods) оставлен как есть — direct callbacks, не nav_stack

### Pre-existing JSON.stringify bug в Get *Price нодах (2026-04-17)

4 Supabase RPC ноды (Get All Prices, Get Card Price, Get Stars Price, Get Crypto Price) использовали `JSON.stringify({...})` в `jsonBody`. При `specifyBody=json` n8n парсит expression дважды → отправлял пустое body → Supabase 404 "Could not find function without parameters".

**Fix:** `JSON.stringify({...})` → `{...}` (plain object). n8n сам сериализует.

**Дополнительно:** Get All Prices читал `$json.telegram_id` от пустого Extract Sub output (free users: `[]` → Extract Sub = `{}`). Fix: `$('Merge Data').item.json.telegram_id`.

Подробности nav_stack: [[concepts/nav-stack-architecture]].

## Related Concepts

- [[concepts/n8n-template-engine]]
- [[concepts/n8n-data-flow-patterns]]
- [[concepts/supabase-db-patterns]]
- [[concepts/user-preferences]]
- [[concepts/one-menu-ux]]
- [[concepts/nav-stack-architecture]] — Phase 5 убрала subscription_source hack; Plans Back через nav_stack

## Sources

- [[daily/2026-04-09.md]] — Payment UX Phase 4: Stars + Stripe + TON/USDT integration; race condition fix in Plans flow; double-emoji bug fix; routing requirements
- [[daily/2026-04-10.md]] — Payment UX v2: tier-first flow, regional pricing via migration 051, Stripe HTTP fix, multiple-item Limit 1 fix, parse_mode HTML, Shop workflowInputs bug
- [[daily/2026-04-11.md]] — Premium subscription screen (two-branch Build Plans Text), Get Subscription + Extract Sub free-user fix, Shop Pattern A (mana hidden for premium, double-emoji fix), cmd_premium_plans routing restored, 4 new translation keys
- [[daily/2026-04-13.md]] — Renewal reminders fix (PostgREST filter bug, cron_get_renewal_candidates RPC), subscription UX (days_remaining, renew_current, all_plans, plan_label {name}→{plan}), regional Stars/USDT in subscription_prices (migration 059), Get Stars/Crypto Price nodes, RETURNS TABLE flickering fix (Limit 1 × 4), free user flow fix, ton_payment_checker regional prices, Back button HTML fix, One Menu before invoice
- [[daily/2026-04-16.md]] — Stripe sandbox → live: чеклист перехода, `.env` ключи, условия готовности
- [[daily/2026-04-17.md]] — Phase 5 nav_stack: subscription_source hack убран, Build Plans Text Back → cmd_back, Push Nav (Plans) добавлен; pre-existing JSON.stringify double-serialization в 4 Get *Price нодах → Supabase 404 для free юзеров (fix: plain object вместо JSON.stringify); Get All Prices $json source fix ($json.telegram_id → $('Merge Data').item.json.telegram_id)
- [[daily/2026-04-27.md]] — Deployment confirmation: Phase 5 Payment задеплоена. JSON.stringify баг подтверждён как pre-existing (не regression Phase 5) — free user 786301802 не мог активировать подписку из-за пустого body в Get *Price нодах. Урок: всегда проверять $json source в цепочке нод после HTTP Request
