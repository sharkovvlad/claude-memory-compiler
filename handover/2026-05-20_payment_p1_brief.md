# Handover — Payment Phase 2 (P1 quality + P2 features)

**Дата:** 2026-05-20 evening, after PR #134 merge.
**Предыдущий handover:** `handover/2026-05-19_stage6_payment_python.md` (Stage 6 cutover).
**Audit reference:** `/tmp/payment-ux-audit-2026-05-20.md` (1900 слов, 17 пунктов P0-P3). Live-файл, не в git — если удалён, recreate from this handover.

---

## Что закрыто (P0 — pre-launch blockers, PR #134 merged)

1. **Stripe webhook idempotency** — `stripe_webhook_events(event_id TEXT PK)` table + `INSERT … ON CONFLICT DO NOTHING` guard в `checkout.session.completed` / `invoice.paid` handlers (`webhook_server.py`). Защита от Stripe at-least-once delivery → double-grant.
2. **Stars idempotency** — partial UQ `payment_events(telegram_payment_charge_id) WHERE NOT NULL` + `UniqueViolation` catch в `successful_payment` handler → fail-open (skip, return 200).
3. **Pre-checkout active-premium guard** — отбивает Telegram pre-checkout запрос если `users.subscription_status='active'` и `expires_at > now()`. Защита от double-charge параллельно работающих платежей.
4. **Stars referral reward parity** — после Stars `successful_payment` теперь вызывается `process_referral_reward(referee_tid, payment_amount)` (был только для Stripe). Bug-parity со Stripe path.

**Bonus P1 (частично):** `_format_payment_success_message` helper — читает JSONB-array `payment.success` + plan name + localised date. Покрывает Stripe checkout + invoice.paid. Stars path всё ещё с hardcoded EN — follow-up.

**Reference:** PR [#134](https://github.com/sharkovvlad/noms-bot/pull/134), migration 290 (`migrations/290_payment_idempotency.sql`).

---

## Что нужно сделать дальше (priority order)

### P1 — Launch quality (1-2 sessions)

1. **Dunning UX (`invoice.payment_failed`).** Сейчас handler шлёт `"⚠️ Your payment failed."` plain EN. Нужно:
   - Retry communication (Stripe ретраит автоматически — сказать window когда retry будет).
   - «Update card» CTA — link на Stripe Customer Portal или billing-portal.
   - Grace period 3 дня после `expires_at` до demote статуса (Spotify-style).
   - i18n × 13 langs из `ui_translations`.
   - Reference: audit Q5#6 + #7.
2. **`/start payment_success` deep-link parse.** Stripe `success_url='https://t.me/nomsaibot?start=payment_success'`. Сейчас бот видит `/start` и рендерит regular menu_v3 — no celebration. Add detection в `webhook_server.py` (или `dispatcher/router.py`) `start_param='payment_success'` → route к celebration screen / `my_plan` с premium banner. Reference: audit Q5#9.
3. **Trial 7d flow.** `subscription_prices.plan_id='trial_7d'` exists (`discount_percent=100`, `duration_days=7`). No handler для `cmd_pay_trial`. No auto-convert cron. Roadmap. Reference: audit Q5#10.
4. **Localised dates everywhere.** `_format_payment_success_message` готов. Audit if другие payment-screens leak ISO timestamps (my_subscription screen showing `expires_at`, dunning, renewal). Pattern: `get_user_context(tid).lang_code` + locale-aware strftime.
5. **Stars success message i18n.** В PR #134 покрыли только Stripe path. `successful_payment` Stars path в `webhook_server.py` всё ещё hardcoded EN. Переиспользовать `_format_payment_success_message`.

### P2 — Big Tech parity (2-3 sessions)

6. **Upgrade/Downgrade** (Stripe proration). Spec в audit Q4. Migration draft signature:
   ```sql
   change_subscription_plan(p_telegram_id BIGINT, p_new_plan_id TEXT) RETURNS jsonb
   -- Upgrade (monthly→yearly): proration, immediate switch.
   -- Downgrade (yearly→monthly): schedule at expires_at.
   -- Same-plan: extend expires_at by plan.duration_days.
   ```
   Stripe SDK: `stripe.Subscription.modify(id, items=[...], proration_behavior='create_prorations')`.
7. **EU VAT.** `stripe.checkout.Session.create(..., automatic_tax={'enabled': True})`. Tax setup в Stripe Dashboard required (тимлид сам).
8. **Receipt email.** Set `customer_email` в Checkout session create + Stripe Dashboard email settings.
9. **Refund mechanism.** RPC `refund_subscription(p_telegram_id, p_reason)` + admin flow + Stripe API call.

### P3 — Tech debt

10. **One-menu pattern для всех payment screens** — Stars done (PR #124). Crypto / promo screens могут leak `last_bot_message_id`. Edit `handlers/payment.py` to use `_send_and_persist` pattern везде. KB [[concepts/save-bot-message-contract]].
11. **n8n `10_Payment` row cleanup.** Workflow `active=false` since 2026-05-19, row в БД остался. Phase 6.4 cleanup item. DELETE через `gh api -X DELETE workflows/T9753zO3ZyiYsgkp` OR sqlite UPDATE (см. KB [[concepts/n8n-sqlite-docker-cp-trap]] — обязательно `--user node` или ownership trap).
12. **Route Classifier cleanup в `01_Dispatcher`** — executeWorkflow ref на `T9753zO3ZyiYsgkp` всё ещё в графе. Safe PUT recipe ([[concepts/n8n-data-flow-patterns]]).

---

## Текущая проблема (open от тимлида, конец сессии 20.05)

**«Кнопка «Продлить подписку» не работает».** Live test от тимлида на tid=417002669 / tid=786301802. Триаж для следующего агента:

1. Это какой callback? `cmd_renew_subscription`? Где определена кнопка в `ui_screen_buttons`? Какой screen её рендерит?
2. Handler chain: скорее всего попадает в `handlers/payment.py` → if unknown callback в whitelist → `forward_to_legacy` → n8n `10_Payment` deactivated → silent. Это вероятная root cause.
3. Possible cause: parallel agent regression на router.py / payment.py (тимлид подозревает recent change).
4. **First actions:**
   - `journalctl -u noms-webhooks -f` + смотреть на момент клика тимлида (`grep -E 'tid=(417002669|786301802)'`).
   - `grep -rn 'cmd_renew\|renew_subscription' handlers/ dispatcher/` в worktree.
   - `gh pr list --state open` + `git log --oneline origin/main..HEAD -- dispatcher/router.py handlers/payment.py` — было ли что-то слито параллельно.
   - `SELECT screen_id, callback_data FROM ui_screen_buttons WHERE callback_data LIKE '%renew%' OR text_key LIKE '%renew%';` через psycopg2 — найти кнопку в headless DB.

---

## Live state production (на 2026-05-20 22:00 MSK)

- **Флаги фич:** `handler_payment_use_python='true'`, `handler_menu_v3/onboarding/location_use_python='true'`, `handler_food_log_use_python='true'` (cutover 15:34 MSK).
- **n8n:** `10_Payment.active=false` (deactivated 19.05). Активные workflows: `01_Dispatcher`, `03_AI_Engine`, `04_Menu_v3`, `04_Menu` legacy, `02.1_Location` (deactivation TODO Phase 6.4).
- **Stripe:** live keys в `/home/taskbot/noms/.env` (Stripe Review «in progress» but accepts payments). Webhook `https://nomsbot.com/webhooks/stripe`, 3 events (`checkout.session.completed`, `invoice.paid`, `customer.subscription.deleted`).
- **TLS:** Caddy + LE на nomsbot.com :443, FastAPI loopback `127.0.0.1:8443`.
- **DB migration HEAD:** 291. Последняя payment-related: mig 290.

---

## Audit report path

`/tmp/payment-ux-audit-2026-05-20.md` — полный gap analysis 17 пунктов (P0-P3). Live file (не в git). Если файл удалён к моменту следующей сессии — recreate from this handover (briefs выше содержат достаточный subset).

---

## Key files (paths in worktree / main clone)

- `webhook_server.py` — Stripe webhook handlers + `pre_checkout` + `successful_payment` + `create_checkout`. **3 P0 fixes здесь.**
- `handlers/payment.py` — paywall UX (premium plans / method picker / pay_stars / pay_crypto), ~867 LOC после PR #134.
- `dispatcher/router.py` — `PAYMENT_PREFIXES` whitelist, target='payment' classification. Watchlist для regression.
- `migrations/290_payment_idempotency.sql` — most recent payment-related migration (`stripe_webhook_events` table + partial UQ).
- `tools/_research_payment_live_schema.md` — RPC signatures dump (still valid).
- `tools/_research_10_payment_report.md` — n8n original behaviour (для reference при разборе legacy flows).

---

## KB cross-refs

- [[concepts/payment-integration]] — high-level tier-first UX, regional pricing.
- [[concepts/payment-idempotency-pattern]] — **NEW (2026-05-20)** Stripe webhook dedup + Stars UQ + pre-checkout guard.
- [[concepts/architecture-registry]] — Python authoritative targets (payment included).
- [[concepts/save-bot-message-contract]] — one-menu pattern (нужно для P3#10).
- [[concepts/telegram-invoice-constraints]] — `editMessageText` silently rejected на invoice, deleteMessage works.
- `handover/2026-05-19_stage6_payment_python.md` — Stage 6 cutover handover.
