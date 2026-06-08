---
title: "FX policy для RevShare/комиссий — snapshot на дату операции"
aliases: [fx_usd_eur, fx_rates_daily, snapshot курса, ECB reference rate, валюта учёта, ambassador commission currency]
tags: [payment, ambassador, fx, currency, monetization, accounting]
sources:
  - "daily/2026-06-08.md"
  - "handover/2026-06-07_ambassador-commission-currency.md"
  - "migrations/492_ambassador_eur_net_commission.sql"
created: 2026-06-08
updated: 2026-06-08
---

# FX policy для RevShare/комиссий — snapshot на дату операции

Как считать комиссию амбассадору в multi-currency среде (Stars/USD/EUR/USDT) и хранить курсы так, чтобы было прозрачно для партнёра и испанской налоговой.

## Принцип (durable, Big-Tech consensus)

**Курс FX фиксируется в момент транзакции (дата операции), не на дату выплаты.** Snapshot хранится на самой строке начисления (`referral_rewards.fx_used`, `fx_date`). Историческое начисление НИКОГДА не пересчитывается при изменении курса.

Это создаёт fairness для партнёра: «ты заработал на этой подписке в день её покупки, по курсу того дня». А когда происходит cash-out — если валюта учёта = валюта выплаты (EUR/EUR), дополнительной конверсии нет.

## Аналоги Big Tech (исследовано 2026-06-08)

| Компания | Что фиксируют | Когда |
|---|---|---|
| **Stripe Connect** (multi-currency) | Курс на момент charge (timestamp транзакции) | дата операции |
| **Apple App Store** (dev payouts) | Курс ЦБ страны разработчика на закрытие месяца | дата выплаты (month-end) |
| **Google Play Developer** | Курс на день закрытия отчётного периода | дата выплаты |
| **YouTube AdSense** | Курс на дату конверсии (monthly) | дата выплаты |
| **Amazon Associates** | Курс на дату payout | дата зачисления |
| **PayPal Mass Payout** | Spot rate в момент перевода | дата выплаты |
| **Booking.com Partner** | Курс ЕЦБ на дату резервации | **дата операции** |

**Общее:** транзакционный учёт → дата операции, выплата → или та же валюта (без конверсии), или snapshot на дату payout. Прозрачность: партнёр видит «дата X, курс Y, сумма Z».

## Для NOMS (as-built, mig 492)

- **Валюта учёта = EUR** (юрлицо в Испании, проще отчётность испанской налоговой).
- **Валюта выплат = EUR** — без дополнительной конверсии (баланс накапливается в EUR).
- **Snapshot курса на дату операции** — в момент INSERT в `referral_rewards`. Источник — `fx_rates_daily` (ECB reference rate). Курс никогда не пересчитывается ретроспективно.
- **Источник курса:** ЕЦБ daily reference rate (https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml). Публичный, бесплатный, авторитетный для испанской налоговой.

## Архитектура (mig 492)

### Таблица `fx_rates_daily` (audit-only, INSERT-only)

```
date        DATE PRIMARY KEY
fx_usd_eur  NUMERIC(10,6) NOT NULL   -- 1 USD = N EUR
source      TEXT NOT NULL DEFAULT 'ECB'
created_at  TIMESTAMPTZ
```

Snapshots никогда не UPDATE'ятся. Для weekend/holiday (ECB не публикует) `fx_usd_eur_on(date)` берёт ближайшую более раннюю дату.

### Helper RPC `fx_usd_eur_on(date)`

3-уровневый fallback:
1. Exact match по дате.
2. Ближайший earlier snapshot (weekend/holiday → previous TARGET2 day).
3. Текущее значение `app_constants.fx_usd_eur` (fallback).
4. Last-resort hardcode 0.86 (никогда не должен сработать).

### Write API: `update_fx_rate_snapshot(date, fx, source)`

Атомарный owner записи: INSERT-on-conflict в `fx_rates_daily` + UPDATE `app_constants.fx_usd_eur`. RPC-first — никаких прямых INSERT/UPDATE из Python.

### Cron `FxRateUpdateCron` (daily 16:00 UTC)

`crons/fx_rate_update.py` — fetch ECB XML → parse `<Cube currency='USD' rate='X'/>` → `fx_usd_eur = 1/X` → `update_fx_rate_snapshot(date, fx, 'ECB')`. Weekend/holiday no-op. ECB публикует в ~14:15 UTC, забор в 16:00 UTC для безопасности.

### Snapshot колонки на `referral_rewards` (mig 492)

| Колонка | Что хранит |
|---|---|
| `base_amount` | Сумма до 25% и до FX, в исходной валюте |
| `base_currency` | XTR / USD / EUR / USDT |
| `fx_used` | Курс USD→EUR в момент INSERT (NULL если base_currency='EUR') |
| `fx_date` | Дата snapshot курса |
| `commission_rate` | 25 (L1) или 5 (L2) |
| `stars_payout_rate_used` | Stars-курс в момент INSERT (NULL для не-Stars) |

Партнёр на экране Статистика увидит формулу:
```
22.05.2026 — Евгения, quarterly CIS
580⭐ → $7.54 net → ×25% = $1.88 → ×0.86244 (EUR на 22.05) = €1.63
```

(TODO mig N+1: добавить кнопку «Подробнее» с этой формулой на экране Статистика.)

## Per-method commission base (mig 492 owner decision)

Решение owner (2026-06-07):

| Метод | База комиссии | Почему |
|---|---|---|
| **Telegram Stars (XTR)** | NET payout = `price_paid (XTR) × stars_payout_rate_usd` | Telegram удерживает ~30% margin + Apple/Google ещё ~30% на mobile. С прайс-листа считать = переплата |
| **Stripe USD** | FULL `price_paid` USD | Stripe ~3% пренебрегаем |
| **Stripe EUR** | FULL `price_paid` EUR (без FX) | Native EUR, нет конверсии |
| **Crypto USDT** | FULL `price_paid` USD | Нет платформенных удержаний |

**Durable урок:** «комиссию/RevShare считать ВСЕГДА с net-выручки (после платформенных удержаний), не с прайс-листа/gross». Telegram Stars ≠ полученные деньги (~30%+ удержание). Card/crypto — удержание мало, можно с полной.

## `stars_payout_rate_usd` — ⚠️ placeholder до Fragment-выписки

**0.013 USD/star — это публичная эвристика**, не подтверждённая Telegram. Telegram **не публикует API курса** ⭐→USD. Реальный payout — в TON через Fragment, и TON-курс плавает. Источники:
- Bot API docs: ~$0.013/⭐ при выводе через Fragment (desktop, после удержания ~30% Telegram).
- На iOS/Android Telegram прокидывает ещё ~30% Apple/Google → реальный net ~$0.010/⭐ для in-app покупок на мобиле.

**Ground truth — только реальная выписка Fragment.** До первого вывода — `requires_calibration_after_first_fragment_withdraw` (комментарий на app_constants row).

**Мониторинг:** при каждой реальной выплате TON → Fragment пересчитать `(полученные USDT после конвертации) / (количество выведенных звёзд)` → это реальный rate за период. Минимум **раз в квартал**, и при движении TON > 20%.

Если реальный rate окажется $0.010 (mobile-heavy юзеры) — Stars net упадёт на 23% от прайса. Тогда нужно **поднимать Stars-номиналы в `subscription_prices`**, чтобы net остался ровным с card/USDT.

## Перекосы между методами — проверено 2026-06-08

Owner уже интуитивно затюнил Stars-номиналы с учётом ~30% удержания. По всем активным регионам/периодам net расхождение между методами ≤ 5% (см. `daily/2026-06-08.md` таблица). Решение «Stars=net, card/USDT=full» даёт амбассадору ≈одинаковую комиссию за подписку независимо от метода (отклонение <1%).

Quarterly CIS (Евгения): card $7.49 → 25% = $1.87, Stars 580⭐×$0.013 = $7.54 → 25% = $1.88. Совпадает.

## Backfill Евгении (mig 492 §J)

| Поле | До mig 492 | После mig 492 |
|---|---|---|
| reward_value | 3.25 | **1.63** |
| currency | USD | **EUR** |
| base_amount | (no col) | 580 |
| base_currency | (no col) | XTR |
| fx_used | (no col) | 0.86244 |
| fx_date | (no col) | 2026-05-22 |
| commission_rate | (no col) | 25 |
| stars_payout_rate_used | (no col) | 0.013 |

Расчёт: 580⭐ × 0.013 = $7.54 → × 25% = $1.885 → × 0.86244 (ECB EUR/USD 1.1595 на 22.05.2026) = **€1.6256 → €1.63**.

UPDATE идемпотентна — `WHERE id=... AND currency='USD' AND reward_value=3.25` — повторный apply делает no-op.

## Related

- [[promo-code-ambassador-flow]] — амбассадорский UX и `process_referral_payment_reward` overview
- [[ambassador-payout-system]] — общий payout flow
- [[release-protocol]] — `./deploy.sh` дисциплина, на которой едет cron

## ⛔ Что НЕ делать

- **НЕ пересчитывать исторические `referral_rewards.reward_value`** при изменении курса. Snapshot — закон. Если нашли ошибку в curse конкретной даты — UPDATE одной строки fx_rates_daily + ручной перерасчёт затронутых rows, не глобальный rerun.
- **НЕ применять `fx_usd_eur` к строкам с `base_currency='EUR'`** — там FX не было, `fx_used IS NULL`.
- **НЕ хардкодить FX в RPC.** Всегда через `fx_usd_eur_on(date)` чтобы корректно обрабатывать историю и weekend/holiday fallback.
- **НЕ заводить новый payout-метод без расчёта эффективной net-выручки.** TON, Telegram Stars, любые новые рельсы — измерить реальный payout vs gross перед запуском RevShare.
