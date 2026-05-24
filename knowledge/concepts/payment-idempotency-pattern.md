---
aliases: [stripe-webhook-idempotency, stars-idempotency, payment-dedup, pre-checkout-guard]
tags: [payments, stripe, telegram-stars, idempotency, webhooks]
---

# Payment Idempotency Pattern

**Status:** captured 2026-05-20 после PR #134 (post-first-live-payment audit). Покрывает три ортогональные idempotency-проблемы которые открылись после первого live Stripe платежа.

> **Source of truth:** `migrations/290_payment_idempotency.sql`, `webhook_server.py` (handlers `checkout.session.completed` / `invoice.paid` / `successful_payment` / `pre_checkout_query`), audit `/tmp/payment-ux-audit-2026-05-20.md`.

---

## Зачем

Любая платёжная интеграция должна выдерживать:
1. **At-least-once delivery от провайдера** (Stripe webhooks ретраит при non-2xx, Telegram повторяет `successful_payment` при transient errors).
2. **Concurrent client requests** (юзер кликнул дважды, два checkout в flight).
3. **Cross-provider race** (зашёл оплатить Stripe + параллельно Stars — нельзя списать с обеих).

Без дедупликации:
- **Double-grant premium** (юзер получает 2× duration, мы теряем revenue).
- **Double referral reward** (реферер получает 2× bonus, accounting расходится).
- **User confusion** — два «Premium Activated!» сообщения подряд.

---

## Три слоя защиты

### 1. Stripe webhook dedup (event-level)

**Проблема:** Stripe доставляет webhook минимум один раз. Если наш endpoint вернул timeout / 5xx / даже 2xx с retry-after — Stripe ретраит **с тем же `event.id`**. Idempotent handlers — обязательное требование Stripe ([docs](https://stripe.com/docs/webhooks#handle-duplicate-events)).

**Решение:** PK-based dedup на `stripe.event.id`:

```sql
CREATE TABLE stripe_webhook_events (
    event_id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

Handler pattern:
```python
async def handle_stripe_webhook(event: dict):
    event_id = event["id"]
    try:
        await db.execute(
            "INSERT INTO stripe_webhook_events(event_id, type) VALUES ($1, $2)",
            event_id, event["type"],
        )
    except UniqueViolation:
        # Уже обрабатывали — Stripe просто получил наш не-2xx и ретрит
        logger.info("stripe.webhook.duplicate", event_id=event_id)
        return Response(status_code=200)  # ack чтоб Stripe больше не ретраил
    # ... фактический grant premium / referral / etc.
```

**Важно:** INSERT идёт **первым** до side-effects. Если grant premium падает — row уже committed, Stripe больше не ретрайнет, **но и grant не произойдёт**. Это компромисс — лучше lost grant (есть alert + manual reconciliation) чем double-grant. Альтернатива (transactional grant + insert) рассмотрена и отвергнута: side-effects часто внешние (Telegram message, Stars charge) — нельзя rollback'нуть.

**Cleanup:** rows не удаляются (полная история событий = audit trail для диспутов). При желании — TTL cron на 90 дней (Stripe не ретраит дольше).

### 2. Telegram Stars dedup (charge-id-level)

**Проблема:** Telegram отдаёт `successful_payment` callback с `telegram_payment_charge_id`. При transient error на нашем endpoint Telegram ретрит — тот же charge_id, та же сумма. Без UQ Index в `payment_events` table получаем double-grant.

**Решение:** partial UQ index:

```sql
CREATE UNIQUE INDEX uq_payment_events_charge_id
    ON payment_events(telegram_payment_charge_id)
    WHERE telegram_payment_charge_id IS NOT NULL;
```

(Stripe payments не имеют этого поля → `WHERE NOT NULL` — partial UQ exclude'ит их.)

Handler pattern:
```python
try:
    await db.execute(
        "INSERT INTO payment_events(...) VALUES (...)",
        ..., telegram_payment_charge_id,
    )
except UniqueViolation:
    logger.warning("telegram.stars.duplicate", charge_id=charge_id)
    return  # fail-open: уже обработали успешно, второй grant не нужен
# ... grant premium + referral + send success message
```

**Fail-open rationale:** дубль Stars-charge — Telegram-side retry, не fraud. Premium уже выдан в первом проходе. Молча skip, return 200.

### 3. Pre-checkout active-premium guard (state-level)

**Проблема:** юзер с активной подпиской `expires_at > now()` инициирует второй checkout (Stars или Stripe). Без guard'а — двойная оплата, двойная подписка, юзер злится.

**Решение:** перехват в `pre_checkout_query` handler **до** того как Telegram спишет деньги:

```python
async def handle_pre_checkout(query: PreCheckoutQuery):
    user = await get_user(query.from_.id)
    if user.subscription_status == "active" and user.expires_at > now():
        await bot.answer_pre_checkout_query(
            query.id,
            ok=False,
            error_message=t("payment.already_active", user.lang_code),
        )
        return
    await bot.answer_pre_checkout_query(query.id, ok=True)
```

**Critical timing:** Telegram даёт нам 10 секунд на ответ `answerPreCheckoutQuery`. Если не ответили — он сам answer'ит `ok=True`, деньги списываются, refund manually. Гvalid `pre_checkout` поэтому Python-only (без флага) — нельзя пропускать.

Stripe не имеет аналога `pre_checkout` — там сessионный URL уже подписан, отбить можно только на webhook стороне (но deny уже после списания → нужен refund). Поэтому Stripe pre-checkout guard делается на UI level: `cmd_pay_stripe` handler перед `create_checkout_session` проверяет active subscription и шлёт error screen.

---

## Тестирование

PR #134 добавил 7 интеграционных тестов:
- 4× idempotency (Stripe webhook dedup × 2 types + Stars duplicate + pre-checkout active-guard).
- 1× Stars referral parity (cross-provider behaviour).
- 2× localised success message (RU + EN — verify JSONB array variants + plan name + locale date).

Pattern для idempotency-test:
```python
async def test_stripe_duplicate_webhook_no_double_grant():
    # Arrange: clean state
    await db.execute("DELETE FROM stripe_webhook_events WHERE event_id = $1", TEST_EVENT_ID)

    # Act: deliver same event twice
    res1 = await client.post("/webhooks/stripe", json=event_payload)
    res2 = await client.post("/webhooks/stripe", json=event_payload)

    # Assert: both 200, but only one grant
    assert res1.status_code == 200
    assert res2.status_code == 200
    grants = await db.fetch("SELECT * FROM subscription_history WHERE event_id = $1", TEST_EVENT_ID)
    assert len(grants) == 1
```

---

## Anti-patterns (наблюдалось / могло быть в проекте)

1. **«Stripe не ретраит, пропустим dedup»** — он ретраит, всегда. Любой не-2xx + timeout = retry с тем же `event.id`. Промазали бы при первом outage.
2. **`get_or_create` без транзакции** — race window между SELECT и INSERT. Использовать `INSERT … ON CONFLICT` или try/catch UniqueViolation, не двушаговый паттерн.
3. **Idempotency key в headers** (Stripe `Idempotency-Key`) — клиент-side header для **наших** requests к Stripe API (создание Customer/PaymentIntent). Это **другой** слой; не заменяет webhook dedup на event-id.
4. **DELETE FROM stripe_webhook_events at end of handler** — наоборот, ОСТАВЛЯТЬ rows как audit trail. Цена 1 row = ~50 bytes; даже 100k webhook'ов в год = 5 MB.
5. **Pre-checkout `ok=True` always** — Telegram автоматически отвечает `True` если мы не ответили в 10s, но если мы вернули `ok=False` неправильно — деньги списались. Логика: проверка state ДО `answer_pre_checkout_query(ok=True)`, на ошибку — `ok=False, error_message=<i18n>`.

---

## Cross-refs

- [[concepts/payment-integration]] — high-level payment UX (tier picker, regional pricing).
- [[concepts/architecture-registry]] — payment в Python authoritative с 2026-05-19.
- [[concepts/telegram-invoice-constraints]] — `editMessageText` silently rejected на invoice (другой gotcha).
- [[concepts/save-bot-message-contract]] — one-menu pattern, separate.
- `migrations/290_payment_idempotency.sql` — SQL spec.
- `handover/2026-05-20_payment_p1_brief.md` — что дальше делать с payment quality (P1 + P2).
