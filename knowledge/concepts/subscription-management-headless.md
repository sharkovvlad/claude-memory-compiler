---
title: "Subscription Management Headless"
aliases: [my_subscription, subscription-headless, gatekeeper-delete]
tags: [headless, payment, subscription, architecture]
sources:
  - "Tech debt #7 Phase 2 PR (mig 219-225, 2026-05-14)"
  - "Master Blueprint 3.0 §8 Payment / Premium"
  - "concepts/payment-integration.md"
created: 2026-05-14
updated: 2026-05-14
---

# Subscription Management — Headless Python

## TL;DR

После Tech debt #7 Phase 2 (mig 219-225) экран управления подпиской живёт в headless архитектуре:

- **Screen** `my_subscription` (mig 219): `business_data_rpc='get_subscription_business_data'`, `render_strategy='delete_and_send_new'`, `text_key='payment.my_subscription_body'`.
- **Routing:** `cmd_profile_subscription` в `PROFILE_V5_CALLBACKS` → `target='menu_v3'` → `handle_menu_v3` → `dispatch_with_render` → `process_user_input` fast-path (mig 225) → render `my_subscription`.
- **Cancel button:** через стандартный headless pattern `meta.save_rpc='cancel_subscription'` + `meta.target_screen='my_subscription'` (НЕ Python handler).
- **Renew button:** fallthrough на legacy n8n `10_Payment` (premium_plans upsell). Останется legacy до Phase 6.4 биллинг-модуля.

## Архитектура

```
Profile → click "Управление подпиской" (visible_condition u.subscription_status<>'free')
   ↓ cmd_profile_subscription callback
router.py PROFILE_V5_CALLBACKS → target='menu_v3'
   ↓
webhook_server._try_authoritative_path → handle_menu_v3
   ↓
dispatch_with_render → process_user_input(action='callback')
   ↓ fast-path mig 225
   v_next_screen := 'my_subscription'
   ↓
render_screen('my_subscription')
   ↓ business_data_rpc=get_subscription_business_data
get_subscription_business_data(tid):
   - SELECT FROM user_subscriptions WHERE status='active' ORDER BY created_at DESC LIMIT 1
   - resolve plan_label через ui_translations payment.plan_name_<plan_id>
   - resolve state_line через ui_translations payment.active_until (или cancelled_body)
   - can_cancel := (status='active' AND cancelled_at IS NULL)
   ↓ JSONB merged into template_vars
template_engine.render_envelope → editMessageText (через replace_existing promotion)
   + attach_reply_kb если main menu
```

### Cancel flow (headless)

```
my_subscription[1,0] click "Отменить подписку"
   ↓ cmd_cancel_subscription callback (visible_condition: can_cancel)
router → menu_v3 (cmd_cancel_subscription в PROFILE_V5_CALLBACKS)
   ↓
process_user_input → ui_screen_buttons lookup → meta.save_rpc='cancel_subscription'
   ↓ EXECUTE 'SELECT public.cancel_subscription($1)' USING p_telegram_id
cancel_subscription (mig 031):
   - UPDATE user_subscriptions SET cancelled_at=NOW() WHERE status='active' ORDER BY created_at LIMIT 1
   - INSERT INTO payment_events ('subscription_cancelled')
   - НЕ меняет status='active' (остаётся пока не expires_at)
   ↓ meta.target_screen='my_subscription' → re-render same screen
state_line теперь = "Подписка отменена. Доступ до X"
can_cancel = false → кнопка «Отменить» скрыта
```

**Важно**: status остаётся `'active'` после cancel_subscription — это by design (юзер использует оплаченный период до конца). cron `cron_check_subscription_expiry` переводит status='cancelled' после expires_at.

## Delete account flow (Gatekeeper — mig 222)

```
Profile → "Удалить аккаунт" → confirm экран
   warning_body содержит {cancel_warning_line}:
   - Trial юзер: cancel_warning_line = «⚠️ Твой триал будет тихо отменён»
   - Free/Paid: cancel_warning_line = '' (пусто)
   ↓ click "Yes, delete forever"
delete_user_account(tid) [mig 222 Gatekeeper]:
   STEP 1: silent cancel trials
     UPDATE user_subscriptions SET status='cancelled', cancelled_at=NOW()
     WHERE status='active' AND payment_method='trial'
   STEP 2: blocker check для paid subs
     IF EXISTS (status='active' AND payment_method != 'trial'):
       RETURN error='ACTIVE_SUBSCRIPTION'
       → юзер видит «Сначала отмени в Профиле → Управление подпиской»
       → идёт в my_subscription, кликает Отменить
       → возвращается, повторяет delete
       → blocker остаётся пока status='active' (Phase 6.4 закроет gap)
   STEP 3: soft-delete + subscription_status='free'
```

### Payment method matrix

| payment_method | Behaviour |
|---|---|
| `trial` | Silent cancel при delete. Никаких Stripe API. **Single текущий path (14.05)** — Stripe ещё не подключён. |
| `stripe` | Blocker. cancel_subscription меняет cancelled_at локально. **Когда Stripe подключат (Phase 6.4)** — обеспечить `stripe.Subscription.modify(cancel_at_period_end=True)` в cancel handler. |
| `stars` | Blocker. Cancel — Telegram API (TODO Phase 6.4). |
| `ton` | Blocker. Cancel — TON blockchain monitor (TODO Phase 6.4). |

## Zombie Subscriptions — design consideration для Phase 6.4

**Сейчас (14.05) Stripe не подключён к боту** — все active subs это `payment_method='trial'` (auto-trial через mig 034 для рефералов). Никаких реальных payment.* событий, никаких реальных списаний.

**После Phase 6.4 (Stripe integration)** возникнет gap если cancel flow остаётся pure-SQL:

1. Real-paid юзер клик «Отменить» в my_subscription → `cancelled_at=NOW()` в local БД.
2. Stripe auto-renew не остановлен на Stripe-стороне → через месяц charge.
3. Юзер видит chargebacks → жалобы.

**Phase 6.4 биллинг-модуль ОБЯЗАН закрыть** через `stripe.Subscription.modify(cancel_at_period_end=True)` Python handler перед локальным `cancel_subscription`. Это design constraint, не текущий active risk.

Separation of Concerns: `delete_user_account` НЕ должна делать Stripe API call. Логика отмены биллинга живёт в дедикейтид handler, который зовётся при click «Отменить» в my_subscription.

## get_subscription_business_data fields

Returns JSONB:

| Field | Description |
|---|---|
| `plan_label` | Локализованный label плана через `payment.plan_name_<plan_id>` |
| `state_line` | Localized state: «Active until X» или «Cancelled. Access until X» |
| `expires_at_formatted` | DD.MM.YYYY |
| `can_cancel` | Boolean: status='active' AND cancelled_at IS NULL |
| `has_subscription` | Boolean: есть ли active sub вообще |
| `plan_id` | Raw plan_id для debugging |
| `payment_method` | Raw payment_method для debugging |

## Grammar (single-brace)

После mig 221 все `payment.*` + `delete_account.*` keys используют single-brace `{x}` placeholders (Python `.format()` style). Это значит:

- ✅ Headless экраны (my_subscription, delete_account_confirm) рендерятся корректно через Python template_engine.
- ⚠️ Legacy n8n `10_Payment` (premium_plans upsell) теперь покажет сырое `{icon_premium}` в title — **acceptable временный gap**. Phase 6.4 миграция перенесёт premium_plans на Python.

## reset_to_onboarding (mig 224)

Расширена signature: `(p_telegram_id BIGINT, p_reset_referrer BOOLEAN DEFAULT TRUE)`.

- Безусловно: `subscription_status='free'` + `UPDATE user_subscriptions SET status='cancelled' WHERE active`.
- Условно (`p_reset_referrer=TRUE` default): `referrer_id=NULL`, `referral_count=0`, `paid_referral_count=0`.

**Product semantic change**: prod `cmd_start_fresh` теперь полностью обнуляет referrer link юзера. Пригласитель теряет attribution если invitee делает start_fresh.

## Связанные KB

- [[concepts/payment-integration.md]] — общая Stripe/Stars/TON интеграция
- [[concepts/save-bot-message-contract.md]] — compliance Python paths
- [[concepts/one-menu-ux.md]] — render_strategy паттерны
- [[concepts/test-user-reset-recipe.md]] — test reset через `reset_to_onboarding`
- [[concepts/architecture-registry.md]] — Python authoritative targets registry

## Open TODOs (Phase 6.4 биллинг-модуль)

1. `stripe.Subscription.modify(cancel_at_period_end=True)` Python handler перед `cancel_subscription` RPC для real Stripe subs.
2. Telegram Stars cancel API integration.
3. `premium_plans` headless миграция (сейчас n8n 10_Payment).
4. `cron_check_subscription_expiry` enhancement — переводить `status='active' + cancelled_at != NULL` в `status='cancelled'` после expires_at.
5. Renew/Change Plan flow — отдельный screen для смены тарифа без legacy upsell.
