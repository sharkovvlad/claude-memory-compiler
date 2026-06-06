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

## 100%-скидка / gift-промокод (comp-доступ для тестировщиков) — DECISION 2026-06-06

**Задача:** друзья-тестеры вводят промокод и получают **месяц премиума бесплатно** (self-serve, через тот же promo-flow). Big-Tech аналог: Duolingo «Extended Free Trial Code» (HOTWINGS → 1 месяц Super, 1 redemption/год).

### Решение: логика «free-redeem» живёт в RPC (headless), не в Python

> **Архитектурное решение (durable, для всех агентов):** ветвление «100% скидка → выдать доступ без оплаты» **обязано** жить в SQL/RPC, а не в Python-хендлере. Это прямое следствие принципа NOMS «RPC-first + headless»: бизнес-решение (платить или подарить) — в БД; Python только оркеструет по флагу из RPC.

**Почему не в Python (push-back на наивный `if final_price==0` в хендлере):**
1. **RPC-first.** «Платить или подарить» — бизнес-логика. Место — SQL, рядом с `apply_discount_code` / `activate_subscription`.
2. **Атомарность.** Валидация кода + инкремент `current_uses` + активация подписки должны быть в одной транзакции. Разнеси по Python — гонка/частичное применение.
3. **Консистентность для будущих агентов.** Любой, кто читает promo-flow, видит знакомый headless-паттерн (как `dispatch_with_render`), а не спрятанную развилку в `payment.py`.

**Технический триггер решения:** 100%-скидка даёт `final_price = 0`, а **ни Stripe, ни Telegram Stars не выставляют счёт на 0** (минимальная сумма платежа). Значит «промокод на 100%» физически не может пройти через checkout — его надо шунтировать **до** платёжки.

### Контракт RPC ↔ Python

Authoritative redeem-RPC сам решает и возвращает Python флаг:
- `{activated: true, plan_id, expires_at, target_screen}` → уже выдано (`activate_subscription(p_payment_method='comp', p_price_paid=0, p_currency='NONE', p_discount_code_id=...)`); Python рендерит success-экран + стикер, **минуя checkout**.
- `{requires_payment: true, final_price, ...}` → обычная скидка (<100%); Python ведёт на Stripe/Stars как сейчас.

Python **не знает «почему»** — знает «что рендерить». Точное имя RPC (новый `redeem_promo_code` vs расширение `apply_discount_code`) финализируется на impl-шаге после live-верификации promo-flow (mig 472 / PR #343 может быть ещё не смержен).

### Comp-подписка: жизненный цикл

- `payment_method='comp'`, `price_paid=0`, `currency='NONE'`, `is_ambassador_code=FALSE` → **commission НЕ начисляется** (price=0).
- Истечение: `cron_check_subscription_expiry` ловит всё `payment_method <> 'trial'` → comp откатывается в `free`, мана→2 **автоматически**. Правка крона НЕ нужна (в отличие от `gift`-награды за стрик — та пойдёт через `cron_expire_trials`, см. ниже).
- `discount_codes` row для тестеров: `discount_value=100`, `discount_type='percent'`, привязка к 30-дневному плану, `max_uses=N` (число тестеров), `max_uses_per_user=1`, `valid_until` (срок акции).

### Поздравительный стикер + текст (Channel A)

После comp-активации юзер получает **поздравляющий стикер + текстовое сообщение** через headless success-экран:
- Стикер — **Channel A** (UI content, Trophy): `bot_stickers` row `gift_premium_celebration_1` / category `gift_premium_celebration`, success-экран с `meta.show_sticker=true` (см. [[concepts/ui-stickers-headless]] «Как добавить новый стикер»). file_id поставляется владельцем → placeholder-паттерн (`file_id LIKE 'TODO_%'`, `is_active=false`) до получения.
- Текст — `ui_translations` ключ `gift.premium_activated` × 13 langs (copywriter playbook: Telegram SRE ≤35char/line, gender-neutral, anti-shame, culture-adapt). Тон проходит ревью через `/sage-tov` агента перед локализацией.
- **Не Python.** Стикер и текст — через `ui_screens.meta` + `ui_translations`, никаких `sendSticker`/хардкод-строк в хендлере (headless invariant).

### Отличие от «gift-награды за стрик» (Фаза 2, отложено)

| | Comp-тестеры (эта секция) | Gift за стрик (Фаза 2) |
|---|---|---|
| Канал выдачи | 100%-промокод (self-serve) | авто, cron по `current_streak` |
| `payment_method` | `'comp'` | `'gift'` |
| Срок | 30 дней | 3–7 дней (TBD) |
| Истечение | `cron_check_subscription_expiry` (as-is) | `cron_expire_trials` + фильтр `IN ('trial','gift')` |
| Best-practice | Duolingo extended-trial code | Duolingo streak reward + loss-aversion на истечении |

## Related Concepts
- [[concepts/subscription-management-headless]] — entitlement logic
- [[concepts/ambassador-payout-system]] — payout flow for ambassadors
- [[concepts/headless-architecture]] §Gotcha4 — target_screen meta pattern
- [[concepts/ui-stickers-headless]] — Channel A sticker registration (gift celebration)
