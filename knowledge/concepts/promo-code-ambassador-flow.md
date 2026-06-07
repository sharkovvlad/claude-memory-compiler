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

## 100%-скидка / gift-промокод (comp-доступ для тестировщиков) — AS-BUILT 2026-06-06 (mig 476/477, PR #348)

**Задача:** друзья-тестеры вводят промокод и получают **месяц премиума бесплатно** (self-serve, через тот же promo-flow). Big-Tech аналог: Duolingo «Extended Free Trial Code» (HOTWINGS → 1 месяц Super, 1 redemption/год).

### Решение: логика «free-redeem» живёт в RPC (headless), не в Python

> **Архитектурное решение (durable, для всех агентов):** ветвление «100% скидка → выдать доступ без оплаты» **обязано** жить в SQL/RPC, а не в Python-хендлере. Это прямое следствие принципа NOMS «RPC-first + headless»: бизнес-решение (платить или подарить) — в БД; Python только оркеструет по флагу из RPC.

**Почему не в Python (push-back на наивный `if final_price==0` в хендлере):**
1. **RPC-first.** «Платить или подарить» — бизнес-логика. Место — SQL, рядом с `apply_discount_code` / `activate_subscription`.
2. **Атомарность.** Валидация кода + инкремент `current_uses` + активация подписки должны быть в одной транзакции. Разнеси по Python — гонка/частичное применение.
3. **Консистентность для будущих агентов.** Любой, кто читает promo-flow, видит знакомый headless-паттерн (как `dispatch_with_render`), а не спрятанную развилку в `payment.py`.

**Технический триггер решения:** 100%-скидка даёт `final_price = 0`, а **ни Stripe, ни Telegram Stars не выставляют счёт на 0** (минимальная сумма платежа). Значит «промокод на 100%» физически не может пройти через checkout — его надо шунтировать **до** платёжки.

### Контракт RPC ↔ Python (as-built)

**RPC = `redeem_gift_code(p_telegram_id, p_code)` (mig 476)** — отдельная тонкая обёртка (НЕ расширение `apply_discount_code`, которая остаётся чистым калькулятором). Валидирует код (active/окно/`max_uses`), проверяет что он 100% (`discount_type='percent' AND discount_value>=100`), проверяет per-user лимит (COUNT `applied_discounts`), затем `activate_subscription(p_plan_id:='monthly', p_payment_method:='comp', p_price_paid:=0, p_currency:='USD', p_discount_code_id:=…)` + чистит `pending_promo_code`. Возвращает jsonb:
- `{success:true, plan_id:'monthly', expires_at}` — уже выдано;
- `{success:false, error:'invalid_or_expired'|'not_a_gift_code'|'already_used'|'activation_failed'}`.

**Python (`handlers/payment.py:_handle_apply_promo`)**: после успешного `apply_discount_code`, если `final_price <= 0` → `_handle_gift_redeem` → вызывает `redeem_gift_code`, рендерит поздравление. Иначе (скидка <100%) — старый путь (re-render планов). Решает SQL; Python ветвится по флагу.

### Comp-подписка: жизненный цикл

- `payment_method='comp'`, `price_paid=0`, `currency='USD'`, план `'monthly'` (+30 дней) → commission **не начисляется** (price=0 → `v_commission=0`).
- Истечение: `cron_check_subscription_expiry` ловит всё `payment_method <> 'trial'` → comp откатывается в `free`, мана→2 **автоматически**. Правка крона НЕ нужна (в отличие от `gift`-награды за стрик — та пойдёт через `cron_expire_trials`, см. ниже).
- `discount_codes` row тестеров (`NOMSTEAM`, mig 476): `discount_value=100`, `discount_type='percent'`, `max_uses=25`, `max_uses_per_user=1`, `valid_until=now()+90d`, `is_ambassador_code=false`.

### Поздравительный стикер + текст — INLINE Python render (НЕ headless-экран)

> ⚠️ Поправка к первоначальному решению: premium-успех в payment-flow **не** идёт через `render_screen`/`ui_screens` (payment.py намеренно избегает re-entry в render_screen pipeline — см. `_render_my_subscription_screen` комментарий). Поэтому gift-успех рендерится **inline в Python**, как остальной payment-flow.

- **Текст** — `ui_translations` ключ `gift.premium_activated` × 13 langs (скаляр, не variant-array). RU/EN — Sage ToV; 11 остальных — copywriter-playbook + L1-ревью (AR: `السحر`→нейтральное `كله اشتغل وبيلمع` из-за оккультного оттенка sihr; FA: `بلیت`→`بلیط`). Рендер: `_lookup_translation(ctx, "gift.premium_activated")` + `OutboundItem(send_new)`.
- **Стикер** — опционален: `stickers_cache.lookup("gift_premium_activated")` → если есть `OutboundItem(send_sticker)` перед текстом, иначе graceful-skip. `bot_stickers` row `gift_premium_activated_1` заведён placeholder'ом (`file_id='TODO_…'`, `is_active=false`, channel B). Владелец активирует позже **одной SQL-строкой** (`UPDATE … SET file_id=…, is_active=true`) + reload — **без правок Python** (стикер появится сам). Это и есть «sticker = one SQL line later».

### Gotcha: двойной инкремент `current_uses` (fix mig 477)

`activate_subscription` §8 **явно** делал `UPDATE discount_codes SET current_uses=current_uses+1`, а триггер `trigger_increment_discount_uses` (AFTER INSERT на `applied_discounts`) делает то же. → каждое погашение = **+2**. Безвредно для амбассадорских кодов (`max_uses=NULL`, uncapped), но **ополовинивало лимит** у первого capped-кода (NOMSTEAM 25→~12). **Fix (mig 477):** убран явный инкремент, триггер — единственный источник; `updated_at` поддерживает `set_updated_at_discount_codes`. **Durable: любой новый capped discount-код — проверь фактический инкремент `current_uses` (был баг до mig 477).**

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
- [[concepts/ui-stickers-headless]] — sticker registration + placeholder pattern (gift celebration sticker, Channel B graceful-skip)

## ⚠️ Stars commission base + currency normalization — OPEN ISSUE (2026-06-07)

**Design B (mig 479) считает Stars-комиссию неверно — переплата.** Owner поймал на live.

**Что сейчас (mig 479/483):** для Stars-оплаты база комиссии = **USD-цена плана DEFAULT-региона** (`subscription_prices.amount`, напр. quarterly $12.99). Комиссия = 25% × $12.99 = $3.25.

**Почему это переплата:**
- Прайс-лист ≠ выручка. Telegram платит разработчику **developer payout ~$0.013/⭐** (берёт ~30%, на мобиле + Apple/Google 30%).
- 580 ⭐ (реальная quarterly-оплата) → NOMS получает ≈ 580×$0.013 ≈ **$7.5**, а не $12.99.
- Комиссия $3.25 / реальные $7.5 = **~43%** вместо 25%.
- **Правильная база Stars = net developer payout, не прайс-лист.** 25%×$7.5 ≈ $1.9.

**Источники курса (durable):**
- ✅ Telegram developer payout rate (~$0.013/⭐, уточнять — плавает) — авторитетно.
- ✅ Реальные выписки вывода (Fragment/TON) — ground truth.
- ❌ Курс ПОКУПКИ звёзд юзером (~1.66–1.82 ₽/⭐ из Telegram buy-dialog) — gross с маржой Telegram, НЕ наша выручка.
- ❌ Среднее по пакетам покупки — не нужно; нужен один payout-курс.

**Валюта (Испания/EUR):** юрлицо в Испании → учёт EUR. Сейчас комиссия в смешанных валютах (Stars→USD, Stripe→валюта оплаты), `get_ambassador_balance` складывает наивно. Нужна нормализация к ОДНОЙ валюте. Решение owner: EUR (юрлицо) vs USD (выплаты в USDT).

**TODO (до реальных амбассадоров, не хотфикс):**
1. `stars_payout_rate_usd` константа в `app_constants` (~0.013), крутить без миграций.
2. `process_referral_payment_reward`: Stars-база = `stars_paid × stars_payout_rate_usd`, не цена плана DEFAULT.
3. Решение по валюте комиссии (EUR vs USD) + FX-нормализация в `get_ambassador_balance`.
4. Коррекция backfill: строка $3.25 за sub `cc711c9a` (Евгения) завышена ~вдвое → ~$1.9.

### Решения owner (2026-06-07) — реализовать
- Stars: комиссия с **NET** (после удержания Telegram); card/USDT — с **полной** оплаты.
- Валюта комиссии и **выплат = EUR** (юрлицо Испания; USDT был случайным дефолтом `payout_requests.currency`, не решением, 0 выплат).
- Полный план реализации — handover `2026-06-07_ambassador-commission-currency.md`.
