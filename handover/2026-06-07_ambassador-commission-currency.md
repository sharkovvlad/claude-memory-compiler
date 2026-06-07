# Handover: Ambassador commission — Stars net-base + EUR normalization (2026-06-07)

**Для агента, который подхватит.** Design B (комиссия по реферальному дереву) уже LIVE и работает, НО экономика курса/валюты неверна. Owner принял решения — нужно реализовать. **Это касается реальных денег → не хотфикс, делать аккуратно с rollback-тестами + явным go owner на apply.**

## Контекст (что уже LIVE на 2026-06-07)

- **mig 479** (PR #350): Design B — `process_referral_payment_reward` начисляет 25% L1 + 5% L2 кэш по `referrer_id` (дереву), промоушен на 5-м оплатившем, `activate_subscription` ветка комиссии удалена (анти-double-dip).
- **mig 480/483** (PR #351/#356): экраны Панель (командный центр) / Статистика (`get_ambassador_detail`), backfill Евгении.
- Все три применены к live БД.

## ⛔ Проблема, которую решаем

**1. База Stars-комиссии = ПРАЙС-ЛИСТ, а должна быть NET payout.**
Сейчас в `process_referral_payment_reward` для `currency='XTR'` берётся `subscription_prices.amount` DEFAULT-региона (напр. quarterly $12.99). Но:
- Telegram удерживает ~30% (на мобиле + Apple/Google ещё 30%). Реально нам падает **developer payout ~$0.013/⭐**.
- 580⭐ → нам ≈ $7.5 net (НЕ $12.99). Комиссия $3.25 от $12.99 = 43% от реальной выручки вместо 25% → **переплата, риск минуса**.

**2. Валюта комиссии не нормализована.** Сейчас: Stars→USD (по прайсу), Stripe→валюта оплаты (EUR/USD), crypto→USDT. `get_ambassador_balance` складывает `reward_value` наивно across currencies. Выплаты — дефолт `payout_requests.currency='USDT'` (не решение, 0 выплат).

## ✅ РЕШЕНИЯ OWNER (зафиксированы, реализовать)

1. **Stars: комиссия с NET** (что осталось у нас после удержания Telegram). «Честно объяснить партнёру: процент с денег, которые остаются в нашем распоряжении».
2. **Card (Stripe) / USDT-crypto: комиссия с ПОЛНОЙ суммы оплаты** (там нет 30%-удержания; ~3% Stripe пренебрегаем — owner решил полную).
3. **Валюта комиссии и ВЫПЛАТ = EUR.** Юрлицо в Испании → проще отчитываться испанской налоговой. (USDT был случайным дефолтом, не решением.)

## TODO (реализация)

### A. Stars net-base
- Добавить `app_constants.stars_payout_rate_usd` (≈ `0.013`, **уточнить по реальной выписке Telegram/Fragment** — это ground truth, не гадать). Крутить без миграций.
- В `process_referral_payment_reward`: для `v_sub_currency='XTR'` база = `price_paid (XTR) × stars_payout_rate_usd`, НЕ `subscription_prices.amount`. (price_paid в XTR = число звёзд, оно есть в `user_subscriptions.price_paid`.)
- Card/USDT: оставить `price_paid` как есть (полная сумма).

### B. EUR-нормализация
- Решить **источник FX** (USD→EUR, и Stars-net-USD→EUR): фиксированная константа `fx_usd_eur` в app_constants (просто, owner крутит) ИЛИ live (ECB API — сложнее, не для бота). **Рекомендую константу** (мало платежей, owner контролирует, налоговая любит фиксированные).
- Все ветки комиссии конвертируют в EUR перед записью в `referral_rewards.reward_value` (currency='EUR'):
  - Stripe EUR → как есть.
  - Stripe USD / Stars-net-USD / crypto-USDT → × fx → EUR.
- `get_ambassador_balance`: currency='EUR', суммировать только EUR-строки (или конвертировать на лету — лучше хранить уже в EUR).
- `payout_requests.currency` default → 'EUR'. Методы выплат (TON/USDT/bank/invoice) остаются, но учёт/сумма в EUR.

### C. UI
- `get_ambassador_detail` + `get_friends_info_rpc` dashboard: символ валюты `$` → `€` (сейчас хардкод `v_sym:='$'` в get_ambassador_detail; в переводах `${amount}`/`${total}` — заменить на `€`). ×13 langs ключи (`earn_*`, `dash_available`, `dash_min`, `stats_balance`, `stats_total_paid`).

### D. Коррекция backfill
- Строка `ambassador_commission` $3.25 USD за sub `cc711c9a` (Евгения, telegram_id referred 1670095403) — пересчитать: 580⭐ × stars_payout_rate × 0.25 → в EUR. UPDATE или DELETE+INSERT. (~$1.9 до EUR-конверсии.)

## Открытые вопросы (решить с owner / проверить)
- **Реальный Telegram payout rate** — взять из фактической выписки вывода (Fragment/TON), не из общих $0.013. До первого реального вывода — поставить $0.013 как placeholder + флаг «уточнить».
- **fx_usd_eur** — какое значение/источник. Owner задаёт.
- **Историческая конверсия** — backfill Евгении по какому курсу (на дату оплаты май vs текущий). Для налоговой — обычно на дату операции.

## Файлы / RPC
- `process_referral_payment_reward` (SQL) — база комиссии per-method + EUR.
- `get_ambassador_balance` (SQL) — EUR.
- `get_ambassador_detail`, `get_friends_info_rpc` (SQL) — символ €.
- `app_constants`: `stars_payout_rate_usd`, `fx_usd_eur`.
- `payout_requests.currency` default.
- `ui_translations` ambassador.* — символ валюты ×13.
- Backfill row в `referral_rewards`.

## Метод проверки (как в этой сессии)
Rollback-транзакция: применить миграцию + синтетические оплаты (Stars 580⭐, Stripe EUR, Stripe USD) → проверить что комиссия = 25% от net (Stars) / full (card) в EUR; backfill пересчитан; баланс в EUR; экраны показывают €. prod не трогать до явного go owner.

## Durable урок
**Комиссию/RevShare считать ВСЕГДА с net-выручки (после платформенных удержаний), не с прайс-листа/gross.** Telegram Stars ≠ полученные деньги (~30%+ удержание). Card/crypto — удержание мало, можно с полной. Для multi-currency бизнеса нормализовать к валюте юрлица (EUR для Испании) фиксированным FX. KB [[promo-code-ambassador-flow]] §Stars-rate.
