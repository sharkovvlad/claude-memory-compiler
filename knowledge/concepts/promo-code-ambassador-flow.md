---
title: "Promo Code & Ambassador Discount Flow"
aliases: [промокод, discount_code, pending_promo, ambassador promo, enter_promo]
tags: [payment, ambassador, promo, discount, subscription]
sources:
  - "daily/2026-06-06.md"
  - "handover/2026-06-06_ambassador-promo-full-wiring.md"
created: 2026-06-06
updated: 2026-06-06
---

# Promo Code & Ambassador Discount Flow

Амбассадор шарит промокод (`NOMS{telegram_id}`). Новый юзер вводит его в payment flow. Backend полностью построен (mig 035 + 286 + 472), frontend был закомментирован до mig 472.

## Архитектура (mig 472, 2026-06-06)

### Ключевые таблицы
- `discount_codes` — коды: `code`, `discount_type`/`discount_value`, `is_ambassador_code`, `referrer_id`, `max_uses`, `allowed_plans`
- `applied_discounts` — история применения (записывается в `activate_subscription`)
- `users.pending_promo_code TEXT` — текущий активный промокод юзера (добавлен mig 472)

### RPCs
- `apply_discount_code(tid, code, plan_id)` → TABLE(success, message, discount_type, discount_value, original_price, final_price). **mig 472:** также сохраняет в `users.pending_promo_code`.
- `get_all_plan_prices(tid)` → SETOF jsonb. **mig 472:** читает `pending_promo_code`, применяет скидку к `final_price`, добавляет `promo_discount_percent`.
- `get_user_price(tid, plan_id, method)` — то же для Stripe checkout price.
- `set_user_status(tid, status)` — создан mig 472 (был missing → entering_promo никогда не устанавливался).
- `get_user_pending_promo(tid)` → {discount_code_id, promo_code, discount_percent} — для webhook handler.
- `clear_user_pending_promo(tid)` → NULL — вызывается после успешной оплаты.
- `activate_subscription(tid, ...)` — принимает `p_discount_code_id uuid` → записывает в `applied_discounts` + начисляет ambassador commission 25%.

### Python
- `handlers/payment.py:_handle_enter_promo` — prompt + `set_user_status('entering_promo')`
- `handlers/payment.py:_handle_apply_promo` — вызывает `apply_discount_code` → при success re-renders plans с обновлёнными ценами
- `webhook_server.py:handle_checkout_completed` — читает `get_user_pending_promo` → передаёт `discount_code_id` в `activate_subscription`

## User Flow (Big Tech pattern)

```
Амбассадор → Поделиться ссылкой → share:
  "Попробуй NOMS! Промокод NOMS417002669 для 10% скидки"
  https://t.me/nomsaibot?start=ref_417002669

Новый юзер → бот → оплата → [🎟 Ввести промокод]
  → вводит NOMS417002669
  → apply_discount_code (pending_promo_code сохраняется)
  → get_all_plan_prices возвращает discounted prices
  → Monthly $3.59 (🎟 -10%) / Quarterly $6.74 / Yearly $35.99
  → выбирает → Stripe checkout на $3.59 (get_user_price применяет pending_promo)
  → payment success → activate_subscription(discount_code_id=...) → 25% комиссия
  → clear_user_pending_promo
```

## Key Points

- Ambassador promo code formula: `NOMS{telegram_id}` (определено в `create_ambassador_code`, проверено против live `get_ambassador_stats`)
- `pending_promo_code` не expires автоматически — очищается только после оплаты. Юзер, введший код и не заплативший, будет видеть скидку постоянно. TODO: добавить TTL или сброс при /start.
- `get_all_plan_prices` помечена STABLE но делает `UPDATE users` при expired promo (auto-clear). Технически нарушение, безвредно на практике.
- Stars payment (`_handle_stars_payment`) также использует `get_all_plan_prices` → скидка применяется к Stars тоже. Желаемое поведение.
- Promo button UI: ключ `payment.promo_button` × 13 langs (добавлен mig 472). Label рендерится Python-side в `_handle_premium_plans`.
- Routing для `entering_promo` status уже был в `router.py` (line 991-992) — никаких изменений не потребовалось.
- `allowed_plans` в `discount_codes` — поле существует, но `apply_discount_code` его не проверяет. Ambassador код применим ко всем тарифам.

## Gotchas (урок от 2026-06-06)

**«Backend всё сделал, но frontend закомментирован»** — `_handle_enter_promo`, `_handle_apply_promo` существовали с mig 286 (2026-05-19) но кнопка была скрыта из-за отсутствия `set_user_status` RPC. Комментарий в коде объяснял причину. 5 строк SQL (CREATE FUNCTION set_user_status) + 1 строка Python (раскомментировать кнопку) — и фича включается.

**Всегда проверяй**: если в `payment.py` есть `# disabled until backend is finished` — ищи что именно не готово, часто это 1-2 простых RPC.

## Related Concepts
- [[concepts/subscription-management-headless]] — entitlement logic
- [[concepts/ambassador-payout-system]] — payout flow for ambassadors
- [[concepts/headless-architecture]] §Gotcha4 — target_screen meta pattern
