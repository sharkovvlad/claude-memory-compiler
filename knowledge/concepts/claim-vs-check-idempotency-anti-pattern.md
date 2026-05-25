---
title: "Idempotency claim vs check — anti-pattern double-call"
tags: [idempotency, anti-pattern, lessons-learned, food-logging, hotfix]
sources:
  - "PR #177 (2026-05-25, P0 hotfix)"
  - "Stage 7a PR C: AI Engine cutover (commit ff3446f, 2026-05-22)"
  - "handler chain: webhook_server._try_authoritative_path → handlers/food_log.handle_ai_input"
created: 2026-05-25
updated: 2026-05-25
---

# Idempotency claim ≠ check (anti-pattern double-call)

> **Lesson learned (P0 hotfix 2026-05-25):** `is_idempotent_message(tid, mid)` RPC — это **claim** (атомарный INSERT с детектом дубля), а не **check** (read-only). Один caller per (tid, mid). Defensive double-check в downstream handlers — anti-pattern, **гарантированно** блокирует real flow.

## Что такое claim vs check

### Check (read-only)
```sql
SELECT EXISTS(SELECT 1 FROM processed_messages WHERE tid=$1 AND mid=$2);
-- Returns TRUE/FALSE без изменений
-- Можно вызывать N раз — состояние не меняется
```

### Claim (атомарный INSERT...ON CONFLICT)
```sql
-- public.is_idempotent_message(tid, mid) implementation:
INSERT INTO processed_messages (telegram_id, message_id) VALUES ($1, $2)
ON CONFLICT (telegram_id, message_id) DO NOTHING;
GET DIAGNOSTICS v_rows = ROW_COUNT;
RETURN (v_rows = 0);  -- TRUE = row уже была (дубль) / FALSE = только что claim'нули
```

**Critical:** `is_idempotent_message` **меняет** состояние (вставляет row). Это **POST**, не GET — даже если возвращает boolean.

## Anti-pattern (что было сломано в PR C, 22.05)

`handlers/food_log.py:handle_ai_input` (lines 461-486 до фикса):

```python
# ── 1. Defensive idempotency (PR C) — ANTI-PATTERN ──────────────────
# webhook_server._try_authoritative_path already locks (tid, message_id)
# before calling us, so in production this is a no-op (the row exists →
# webhook returns early without invoking us). The guard here protects
# alternate entry points (tests with explicit message_id, future endpoints).
if isinstance(message_id_raw, int):
    already = await rpc_fn("is_idempotent_message", {
        "p_telegram_id": telegram_id,
        "p_message_id":  message_id_raw,
    })
    if already is True:
        return ResponseEnvelope.empty()  # skip
```

### Reasoning автора (ошибочное)
> «webhook_server проверяет первым → если juzhe — возвращает early. Если дошли сюда — то webhook не нашёл duplicate. Defensive повторный check ничего не сломает (no-op).»

### Реальность
`webhook_server._try_authoritative_path` (line 1554):
```python
already = await supabase_rpc("is_idempotent_message", {...})  # ← claim!
if already is True:
    return True  # skip
# Else continue to handle_ai_input
from handlers.food_log import handle_ai_input
envelope = await handle_ai_input(update, ctx)  # ← вызов handler
```

Sequence:
1. `webhook_server` вызывает `is_idempotent_message(tid, mid)` → **INSERT успешен** → ROW_COUNT=1 → returns FALSE (claim won)
2. `webhook_server` НЕ skip → calls `handle_ai_input`
3. `handle_ai_input` вызывает **тот же** `is_idempotent_message(tid, mid)` → строка **уже есть** (webhook_server только что INSERT'нул) → ROW_COUNT=0 → returns **TRUE** (видит «duplicate»)
4. Handler **skip** → empty envelope → юзер видит только thinking sticker

**Defensive check всегда срабатывает после первого claim.** Handler **никогда** не работает.

## Симптомы в проде

- `food_logs` table empty за 6 часов для канарейки 417002669 (Python AI Engine)
- VPS journal: `handle_ai_input: defensive idempotent skip tid=417002669 mid=<N>` для каждой попытки
- `processed_messages` содержит rows для каждого attempt (claim'нуты webhook_server'ом, но не processed handler'ом)

```sql
-- Live debugging query:
SELECT telegram_id, message_id, processed_at
  FROM processed_messages
 WHERE telegram_id = 417002669
 ORDER BY processed_at DESC LIMIT 5;
-- Все rows есть, но food_logs пуст → claim успешен, processing — нет.
```

## Fix (PR #177)

Удалить весь defensive check block. webhook_server — **единственный** source of idempotency claim. Handler доверяет вызывающему.

```python
# ── 1. Defensive idempotency — REMOVED 2026-05-25 ───────────────────
# webhook_server.claim — single source of truth.
# Defensive double-check is anti-pattern: is_idempotent_message ATOMIC
# INSERT, не read-only check. Double-call always returns TRUE second time.
```

После fix: канарейка работает (owner confirmed). Food parsing logs INSERT нормально.

## Когда defensive check **легитимен**

Если бы `is_idempotent_message` был **action-less query**:
```sql
-- Hypothetical read-only check:
SELECT EXISTS(SELECT 1 FROM processed_messages WHERE tid=$1 AND mid=$2);
```
Тогда double-call безопасен — нет side effects, оба caller'а видят consistent state.

**Но НЕ путать с claim.** Claim API возвращающее boolean — это **mutation API**, не **query API**.

## Правила

1. **Один claim per (tid, mid).** Если RPC возвращает «claim успешен» / «уже existed» — только **один** caller должен его вызывать.
2. **Передача состояния через ctx**, не через повторный claim. Если handler нужно знать «было ли это уже claim'нуто» — pass parameter из caller'а:
   ```python
   envelope = await handle_ai_input(update, ctx, already_claimed=False)
   # Inside handler: if already_claimed: assume webhook decided OK
   ```
3. **API naming.** Если функция называется `is_X` или `has_X` (boolean returning) и **меняет state** — переименуй в `claim_X` / `try_X` / `acquire_X`. «Is» подразумевает query, «claim/try/acquire» подразумевает action.
4. **Defensive «safety net»** для idempotency — обычно **не нужен**. Если архитектура корректна — claim в одном месте достаточен. «Defensive» double-check добавляет complexity и риск false positive.

## Связанные паттерны

- **`processed_messages` table** — single source of truth для message deduplication. UNIQUE (telegram_id, message_id). См. `webhook_server.py:1537+`.
- **`notification_log` dedup** для cron pushes — pattern «notif_type + tid + sent_at» per-day. См. mig 330 `cron_get_reminder_candidates`.
- **Stripe `stripe_webhook_events(event_id PK)`** — webhook dedup для payment retries (mig 290). Same idea: claim once, return early on duplicate.

Anti-patterns aside, эти все идемпотентность patterns — same family: **claim-once, downstream trust**.

## TL;DR for next engineer

> Если видишь `is_idempotent_message` / `claim_*` / `try_lock_*` вызов **больше чем раз** в одной call chain — это bug. Удалить все кроме первого. Передавать `already_claimed: bool` через ctx если нужно.
