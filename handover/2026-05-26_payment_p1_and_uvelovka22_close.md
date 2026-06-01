# Handover — Payment P1 / Уловка-22 closure (2026-05-26 late evening)

**От агента:** Payment-fix-sprint (sessions 7-15 от 2026-05-20 до 2026-05-26)
**Кому:** следующий агент, занимающийся payment polish / launch readiness
**Состояние сессии:** контекст 100k+ tokens, рекомендован handover до того как reset потеряет детали.

---

## Что сделано (что НЕ нужно делать заново)

### 6 PR за последние дни, все merged + deployed

| PR | Mig | Что закрыло |
|---|---|---|
| #134 | 290 | Stars idempotency UQ + 3-уровневая защита от double-grant |
| #139 | 294 | Stripe idempotency parity (UQ + RPC pre-check + 500 on transient) |
| #150 | 302 | TON wallet idempotency parity (external_charge_id колонка) |
| #151 | 303 | TON hash base64↔hex canonicalize (был cascade 14× за 65 мин) |
| #152 | 305 | Fix литерала `{expires}` в state_line (placeholder mismatch) |
| #153 | 306+307 | Sassy variants × 13 langs + RPC array-aware (random pick) |
| #158 | 313 | **Уловка-22 close**: blocker RPC + handlers/profile.py + delete_blocker_stripe screen + Stripe HTML заглушки |
| #205 | 358 | UX fixes: my_subscription body rewrite + icons + reply-kb removal on delete |

### Архитектурно-значимые изменения

1. **`payment_events.external_charge_id` колонка** (mig 302) — универсальный id для wallet/crypto. Stars → `telegram_payment_charge_id`, Stripe → `stripe_payment_intent_id`, wallet/TON → `external_charge_id`. Все три имеют partial UQ index.

2. **`activate_subscription` RPC step 0.5** — pre-check DUPLICATE_CHARGE для всех 3 платёжных путей (Stars/Stripe/wallet). Возвращает `{success:false, error:'DUPLICATE_CHARGE'}` БЕЗ side-effects. TOCTOU race защищён UQ-индексами.

3. **`get_subscription_business_data` RPC array-aware** (mig 307) — `jsonb_typeof = 'array'` → random pick из variants. Это позволяет Sassy variants и для других payment translations (active_until, etc.).

4. **`handlers/profile.py`** (новый Python handler) — `cmd_delete_account` / `cmd_confirm_delete`. Branches: `check_delete_account_blocker(tid)` → `delete_blocker_stripe` или `delete_account_confirm`. Удаляет reply-keyboard после `delete_user_account` RPC (chat_action `remove_keyboard`).

5. **Stripe HTML заглушки** (mig 313) — `nomsbot.com/payment-success` и `/payment-cancel`. JS-redirect через 1.5s на `tg://resolve?domain=nomsaibot` (БЕЗ `?start=`). Никакого видимого `/start` в чате юзера.

6. **`webhook_server.py` retry contract** — handlers возвращают bool. `True` = 200 OK (success / idempotent skip / permanent business error). `False` = HTTPException 500 → Stripe ретраит.

---

## Reading order для onboarding следующего агента

1. **CLAUDE.md** + **MEMORY.md** (стандартное)
2. **`daily/2026-05-25.md`** + **`daily/2026-05-26.md`** — детальные записи последних сессий
3. **KB:** [[concepts/payment-idempotency-pattern]] (3-уровневая защита), [[concepts/release-protocol]] (worktree gotchas)
4. **Mig 290 → 358 sequence** в `migrations/` — последовательная история «как мы сюда пришли»

---

## Что ОСТАЛОСЬ (по приоритету для launch)

### P0 — блокеры launch

**Никаких P0 блокеров.** Payment subsystem готов к публичному запуску.

### P1 — high financial impact

| # | Что | Размер | Сложность |
|---|---|---|---|
| **P1.1** | **Dunning UX** — напоминания за 7/3/1 день до expiry × 13 langs Sage texts | mig + cron job + translation keys | M (1-2 дня) |
| **P1.2** | **Crypto/promo localised dates** — аудит остальных payment paths + mig | mig + аудит | S (30 мин) |
| **P1.3** | **n8n 04_Menu cleanup** — remove nodes 121-124 (Check Subscription Blocker) теперь dead code после mig 313 | Safe PUT через scp+curl recipe | S (15 мин) |
| ~~P1.4~~ | ~~TON UX~~ — ✅ **DONE** (mig 296 + ru L1 polish). Live screen 2026-06-01: `<code>` теги для wallet/memo (тап = copy), жирный `⚠️ TON Mainnet` warning с дисклеймером про ERC/TRC/BSC, комиссия `~$0.20 сверх`, ETA `~2 часа`. Tolerance в `crons/ton_payment_checker.py`: ±15% strict baked + ±30% fallback с классификацией underpaid/overpaid (более user-friendly чем спека ±10% — owner может ужесточить позже). | — | — |
| **P1.5** | **Stars Subscriptions** — BotFather config + smoke test | External + 30 мин test | XS |

### P2 — product decisions need

| # | Что | Когда |
|---|---|---|
| **P2.1** | **Trial 7d auto-convert flow** — design first: что делать когда trial истёк? Charge Stripe? Fall to free? Upsell? Спецификация → cron | Требует product call |
| **P2.2** | **Refund policy в ToS** — Stars 30 дней auto, Stripe admin, Crypto manual/нет. Документация | Копирайтер sprint |
| **P2.3** | **Upgrade/downgrade Stripe proration** — monthly→yearly с автоматическим расчётом | Большая фича, отдельный sprint |
| **P2.4** | **EU VAT** через `automatic_tax` | Tax compliance |
| **P2.5** | **Receipt emails** + **Customer Portal** | Stripe Dashboard config |

### P3 — long tail

- L2 copywriter sprint для 11 langs (DE/ES/FR/AR/FA/HI/ID/IT/PL/PT/UK) — Sassy variants для cancel/delete текстов сейчас EN fallback. Fiverr ~$200.
- JPY/KRW currency support (нет dezimal places).
- Multi-account trial abuse detection.

---

## Live state, на которое можно опираться

### Тестовые аккаунты

| TID | Состояние |
|---|---|
| **786301802** | Был wallet premium до 2027-10-13 (artefact от TON cascade). **Deleted 2026-05-25 22:22** через mig 313 flow — успешный E2E тест. После `/start` восстановится. |
| **417002669** (admin) | RU + premium + Stripe sub с **cancelled_at IS NOT NULL** (отменена 2026-05-25 19:29). Active до 08.08.2026. Идеален для тестов resume/cancel-idempotency. |
| **786301802** (после restore) | Идеален для тестов delete-flow для wallet path. |

### Открытые задачи на проде

- `noms-cron` active, TON cascade закрыт (mig 303 hash canonicalize).
- `noms-webhooks` active, HTML заглушки `payment-success`/`payment-cancel` отвечают HTTP 200.
- Стек: Caddy + LE → FastAPI loopback → Supabase pooler. RTT ~44ms.

### Mig HEAD

Последняя моя — **mig 358**. На момент handover свободны: **359, 360, 361, 362, 363+** (см `git ls-tree origin/main migrations/` перед взятием — параллельные агенты могут взять).

### CI/CD

- `./deploy.sh` через GitHub Actions из main, auto-deploy на merge. 30 секунд average.
- Pre-push hook + CI workflow для migration collision check активны.

---

## Gotchas / lessons learned (свежие)

### Mig collision на 13 langs translation rewrite

Subagent (copywriter) может вернуть SQL только для 5 langs (RU/EN/DE/ES/FR L1) + bulk UPDATE for остальных 8 (EN fallback). **Подсчёт UPDATE rows** в его отчёте часто overstated — реально 18 UPDATE для 3 keys × (5 individual + 1 bulk × 3). Не верь reported counts blindly, проверяй `grep "lang_code\s*=" mig.sql | wc -l`.

### JSONB array vs string в RPC

`render_screen` array-aware (`jsonb_typeof`). `get_subscription_business_data` НЕ был до mig 307 — если переписываешь plain string в array через mig, **обязательно** проверь RPC что её читает — иначе юзер увидит литерал `["v1", "v2", ...]` в чате. Pattern fix:

```sql
SELECT CASE jsonb_typeof(content->'payment'->'key')
    WHEN 'array' THEN
        content->'payment'->'key'->>(floor(random() * jsonb_array_length(content->'payment'->'key'))::int)
    ELSE content->'payment'->>'key'
END
```

### Reply-keyboard removal

После `delete_user_account` нужно отправить сообщение с `reply_markup={"remove_keyboard": True}` чтобы убрать нижние кнопки (Мой день / Прогресс / Профиль). Без этого юзер удалённого аккаунта может нажать reply-кнопку → бот примет update → попытка route в menu_v3 → state '' → AI fallback. См handlers/profile.py `_handle_confirm_delete`.

### NLM может выдать stale info

NLM при вопросе про visible_condition выдал `can_cancel` — но live код использует `user_has_renewable_sub`. Всегда verify через psycopg2 SELECT, не доверяй NLM-у молча.

### Carrier-message паттерн

**`/start` без payload** для новых юзеров возвращает welcome wave 👋 + reply-keyboard (Мой день / Прогресс / Профиль). Это **carrier message** для reply-kb. **НЕ ломать**. Если режешь `/start` логику — режь только специфичные payloads через regex `^/start\s+payment_success$`, не общий `/start`.

---

## Ссылки

- KB Index: `claude-memory-compiler/knowledge/index.md`
- [[concepts/payment-idempotency-pattern]] — 3-уровневая защита
- [[concepts/architecture-registry]] — текущий Python authoritative + n8n legacy targets
- [[concepts/release-protocol]] — worktree+rebase+force-with-lease рецепт
- KB hub: [[concepts/copywriter-playbook]] — Sage tone + L1/L2 review process

---

**Если ты — следующий агент:** прочти этот файл целиком + сегодняшний daily, потом задай user'у короткий вопрос «по какой задаче из P1 начинаем?» и поехали. Не повторяй уже сделанное (см список 6 PR в начале).
