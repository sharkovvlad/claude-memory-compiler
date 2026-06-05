# Handover: Ambassador share + promo code full wiring (2026-06-06)

## Статус
- **PR #342** (mig 471) — MERGED, DEPLOYED ✅
- **PR #343** (mig 472) — ОТКРЫТ, не смержен 🟡
- **mig 471 + mig 472 + helper RPCs** — APPLIED to live DB ✅
- **Python changes (template_engine, payment.py, webhook_server.py)** — в PR #343, НЕ задеплоены 🔴

## Что было сделано

### PR #342 — mig 471 (Ambassador buttons fix)
Кнопки `share_ambassador_code` (Поделиться кодом) и `cmd_ambassador_stats` (Статистика) на экране `friends_info` не работали — пустой `meta={}` → `process_user_input` re-рендерил тот же экран.

**Фикс:** `share_ambassador_code` → `url_template: 'share_ambassador_code'` (URL-кнопка); `cmd_ambassador_stats` → `target_screen: 'ambassador_stats'` (новый экран). Resolver в `template_engine.py`.

### PR #343 — mig 472 (Promo code full wiring)
Полная механика промокода — Big Tech pattern.

**SQL (mig 472 LIVE):**
- `set_user_status(tid, status)` RPC создан
- `users.pending_promo_code TEXT` column
- `apply_discount_code` — сохраняет `pending_promo_code` при успехе
- `get_all_plan_prices` — применяет скидку из `pending_promo_code`
- `get_user_price` — то же (для Stripe checkout price)
- `get_user_pending_promo(tid)` → {discount_code_id, promo_code, discount_percent}
- `clear_user_pending_promo(tid)` → NULL
- Translations × 13: `ambassador.share_button`→«Поделиться ссылкой», `payment.promo_button`→«🎟 Ввести промокод», `ambassador.share_code_text`→clean text

**Python (PR #343, НЕ задеплоено):**
- `template_engine.py`: share URL = ref link `?start=ref_{tid}` + promo text
- `payment.py`: promo button включён; `_handle_apply_promo` → re-render plans; price label с 🎟
- `webhook_server.py`: checkout handler передаёт `discount_code_id` → `activate_subscription`; очищает `pending_promo_code`

## Следующему агенту

1. **Смержить PR #343** — `gh api -X PUT repos/sharkovvlad/noms-bot/pulls/343/merge -f merge_method=merge`
2. Следить за deploy через GitHub Actions (`.github/workflows/deploy.yml`)
3. Протестировать флоу: Банда → Поделиться ссылкой → share dialog; оплата → Ввести промокод → цены обновляются

## Known limitations / TODO

- `pending_promo_code` не expires при неоплате — юзер может ввести код и никогда не платить, скидка будет висеть. Если нужно — добавить `pending_promo_expires_at` или сбрасывать через N дней.
- `get_all_plan_prices` помечена STABLE, но теперь делает `UPDATE users` при expired promo. Технически нарушение STABLE. Безвредно сейчас, но если PostgreSQL кэширует STABLE — убрать флаг.
- Stars payment (`_handle_stars_payment`) тоже использует `get_all_plan_prices` → скидка будет применяться и к Stars оплате. Это желаемое поведение.
- TON crypto payment — нужно проверить что использует тот же `get_all_plan_prices`.
- `handle_checkout_completed` вызывает `clear_user_pending_promo` только при Stripe. Stars webhook может нуждаться в том же.

## Связанные файлы
- `migrations/471_ambassador_buttons_fix.sql`
- `migrations/472_ambassador_promo_wiring.sql`
- `services/template_engine.py`
- `handlers/payment.py`
- `webhook_server.py`
