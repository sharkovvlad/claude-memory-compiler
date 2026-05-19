# Handover — Stage 6 (n8n `10_Payment` → Python `handlers/payment.py`)

**Дата:** 2026-05-19. **Статус:** live, флаг flipped 17:00 UTC. **Master roadmap:** `/Users/vladislav/.claude/plans/groovy-marinating-eclipse.md` Stage 6.

---

## Что мигрировано

n8n workflow `10_Payment` (id `T9753zO3ZyiYsgkp`, ~35 нод) переписан в Python `handlers/payment.py` (~728 LOC, 7 branches).

**Покрытие 7 branches handler:**
- `cmd_pay_*` (выбор плана)
- `cmd_premium_plans` (показ tier-list)
- `cmd_pay_stars` / `cmd_pay_card` / `cmd_pay_crypto` (методы)
- `pre_checkout` (Telegram Payments hook, **безусловно** в Python, без флага)
- `successful_payment` (Telegram Payments hook, **безусловно** в Python)
- Stripe webhook events: `checkout.session.completed` / `invoice.paid` / `customer.subscription.deleted` (Stripe live setup, см. handover `2026-05-19_tls_caddy_migration.md`)

---

## Флаг и graceful degradation

```sql
SELECT key, value FROM app_constants WHERE key = 'handler_payment_use_python';
-- value = 'true' (set 2026-05-19 ~17:00)
```

- Hot-reload через `app_constants_cache` (TTL 60s). Откатить можно за минуту без рестарта `noms-webhooks`.
- При `false` Python router увидит `flags.forward_target='payment'` → `forward_to_n8n()` → n8n `10_Payment`.
- **НО:** n8n `10_Payment` **деактивирован** 2026-05-19 (`UPDATE workflow_entity SET active=0 WHERE id='T9753zO3ZyiYsgkp'`). Поэтому `false` → fallback effectively no-op (n8n trigger не реагирует). Если нужен реальный rollback на n8n — сначала `active=1` через SQLite, потом флаг.
- `pre_checkout` / `successful_payment` всегда в Python — флага у них нет (Telegram Payments lifecycle нельзя терять).

---

## PR'ы

| PR | Что |
|---|---|
| #115 | Implementation: handler + tests + mig 275 (флаг создан, default `false`) |
| #116 | Fix: icon substitution + hide promo button |
| #118 | UX round 2: emoji prefix, unified back, Stars i18n, отдельный back для Stars invoice |
| #121 | Unify Stars Back UX (glue back в invoice's reply_markup + delete+send_new strategy) |
| #122 | i18n migrations 279/280 + smoke fix |

Все merged.

---

## Миграции

| Mig | Что |
|---|---|
| 275 | `app_constants` row `handler_payment_use_python` (default `false`, flipped к `true` после deploy) |
| 279 | i18n: `payment.pay_with_stars`, `payment.pay_button`, `payment.invoice_back_hint` × 13 langs |
| 280 | Dead-keys cleanup: `back_to_plans`, `plan_monthly`, `plan_quarterly`, `plan_yearly` (legacy n8n keys) |

---

## Live тест

- **Card flow:** Stripe Checkout open для tid=786301802, регион Испания, $3.99 USD, Pay button рендерится. Реальный платёж пока не делали (только UI rendering).
- **Stars flow:** UX round 2 + Back-button finalised в PR #121 (delete+send_new pattern из-за Telegram invoice editMessageText limitation, см. KB [[concepts/telegram-invoice-constraints]]).

---

## Open tech debt

1. **One-menu pattern для payment screens.** Stars и crypto flows не сохраняют `users.last_bot_message_id` после render → когда юзер кликает reply-keyboard, `menu_v3` не находит что удалять → старое payment-меню остаётся в чате параллельно с новым. Fix: вызов `save_bot_message` в handler после финального sendMessage / sendInvoice. См. KB [[concepts/save-bot-message-contract]] и lesson 14.05 (Tech debt #7 AI Engine).
2. **`set_user_status` RPC** для promo flow — нужна, если будем расширять промо-механики (промо-коды, реферальные скидки).
3. **n8n cleanup:** удалить `10_Payment` workflow (id `T9753zO3ZyiYsgkp`) из n8n БД (сейчас `active=0`, но row есть). Также убрать `executeWorkflow → 10_Payment` refs в `01_Dispatcher` и `04_Menu`/`04_Menu_v3`. Делать через Safe PUT recipe (см. KB [[concepts/n8n-data-flow-patterns]]).

---

## KB-уроки рождённые в этой миграции

- [[concepts/telegram-invoice-constraints]] — `editMessageText` silently rejected на invoice, deleteMessage работает. Pattern Back-кнопки.
- [[concepts/n8n-sqlite-docker-cp-trap]] — ownership trap при `docker cp` writable файла (поймали при `active=0` UPDATE через копию БД, 1+ час crash loop).

---

## Архитектурный registry update

KB `architecture-registry.md`:
- **Python authoritative targets:** menu_v3, onboarding, location, **payment** (новый).
- **n8n active=0 (deactivated):** 10_Payment (2026-05-19, Stage 6).
- Остаются в n8n: 03_AI_Engine (Add food / Vision), 02.1_Location (тоже под деактивацию после Phase 6.4 cleanup), 04_Menu (legacy Edit Meal flow), 04.2_Edit_StatsDaily.

---

## Stage 7+ (что дальше по roadmap)

Master roadmap `groovy-marinating-eclipse.md`:
- Stage 7: `03_AI_Engine` (Vision/Transcribe) → Python — самый большой и рискованный, OpenAI SDK напрямую вместо n8n langchain нод.
- После 7 → cleanup всех legacy 04_Menu / 04.2_Edit_StatsDaily / 06_Indicator_Send (deferred Phase 6.4).

Полный план stages 0-7 — `/Users/vladislav/.claude/plans/groovy-marinating-eclipse.md`.
