# Handover — Python AI Engine idempotency hotfix (PR #177)

**Date:** 2026-05-25
**From:** Agent wonderful-keller-8af0e2 (Adaptive Modifiers / Phase 3 sprint)
**To:** Python AI Engine agent (Stage 7a/b/c owner)

---

## TL;DR

**P0 LIVE bug:** канарейка Python AI Engine (tid=417002669) **не логирует еду** уже 6+ часов. Root cause — defensive idempotency check, который **сам себя** блокирует. **PR #177 merged** (по решению тимлида) — твоя зона затронута, проверь.

## Что было сломано

Файл: `handlers/food_log.py`, функция `handle_ai_input`, строки **461-486** до фикса.

Commit `ff3446f` (22.05, **Stage 7a PR C: AI Engine cutover infra**) добавил:

```python
# ── 1. Defensive idempotency (PR C) ─────────────
# webhook_server already locks (tid, message_id) before calling us,
# so in production this is a no-op...
if isinstance(message_id_raw, int):
    try:
        already = await rpc_fn("is_idempotent_message", {
            "p_telegram_id": telegram_id,
            "p_message_id":  message_id_raw,
        })
        if already is True:
            logger.info("handle_ai_input: defensive idempotent skip ...")
            return ResponseEnvelope.empty()
```

## Почему сломано

`is_idempotent_message` — это не read-only check, это **claim**:

```sql
INSERT INTO processed_messages (tid, mid) VALUES (...)
ON CONFLICT (tid, mid) DO NOTHING;
GET DIAGNOSTICS v_rows = ROW_COUNT;
RETURN (v_rows = 0);  -- TRUE если уже было (дубль)
```

Архитектура:
1. **webhook_server** (line 1554) → вызов claim → ROW_COUNT=1 (новый) → returns FALSE → продолжает
2. **webhook_server** → вызывает `handle_ai_input(update, ctx)` (line 1572)
3. **handle_ai_input** (line 470) → ВТОРОЙ вызов того же RPC → ROW_COUNT=0 (только что webhook_server INSERT'нул) → returns TRUE → **defensive skip** → empty envelope

Юзер видит только thinking sticker. AI Engine **никогда** не вызывается.

**Комментарий автора** «in production this is a no-op (the row exists → webhook returns early without invoking us)» — **неверный**. Webhook возвращает early только когда `already=TRUE`, но webhook сам создаёт row, поэтому он сам ВСЕГДА получает `already=FALSE` (новый INSERT). Defensive double-check в handler — после того как webhook claim'ил — всегда видит row → всегда TRUE → всегда skip.

## Доказательства

Live confirmed 2026-05-25 09:20-10:30 MSK:

```
$ ssh root@89.167.86.20 'journalctl -u noms-webhooks --since "10:15" --until "10:25" | grep 417002669'
... AUTHORITATIVE_AI update_id=455700978 tid=417002669 reason=text_food elapsed_ms=675
... handle_ai_input: defensive idempotent skip tid=417002669 mid=6248
```

```sql
SELECT COUNT(*) FROM food_logs WHERE telegram_id=417002669 AND created_at > now() - INTERVAL '6 hours';
-- 0 rows
```

```sql
SELECT * FROM processed_messages WHERE telegram_id=417002669 ORDER BY processed_at DESC LIMIT 5;
-- 6248 at 07:19:48 UTC, 6243 at 07:01:30 UTC (both claimed by webhook_server, both got skipped by handler)
```

## Fix (в PR #177)

Удалить block lines 461-486 (defensive check). Оставить `rpc_fn` resolve (lines 455-459) — он нужен дальше для `log_meal_transaction`.

```python
# ── 1. Defensive idempotency — REMOVED 2026-05-25 ───
# webhook_server is the single source of idempotency claim.
# Defensive double-check just blocks the real flow.
```

36 lines удалено, 10 lines comment-replacement.

## Что я НЕ сделал (твоя зона)

1. **Не добавил тесты для handle_ai_input idempotency** — если хочешь pattern «handler safe to call directly» (out-of-band entry points), нужно либо:
   - (a) подать `already_claimed: bool` параметр через caller chain
   - (b) делать claim **внутри** handler и убрать его из webhook_server (одно место истины)
   Я не выбирал — это твой architectural call. Сейчас claim в webhook_server (status-quo до PR C).

2. **Не обновил KB**. Lesson: `is_idempotent_message` — это **claim** (INSERT…ON CONFLICT), а не **check**. Только **один** caller может его вызывать per (tid, mid). Defensive double-check после claim — anti-pattern. Если есть смысл — добавь в `claude-memory-compiler/knowledge/concepts/` (возможно вариант `idempotency-claim-vs-check` или append в существующий).

3. **Не trogал webhook_server.py** — fix только в food_log.py. webhook_server остался единственным claim point.

## Verification после merge

- `food_logs` table получает INSERT при отправке любого food message от 417002669
- В journal `noms-webhooks` исчезают строки `defensive idempotent skip`
- В journal появляются `AUTHORITATIVE_AI ... reason=text_food elapsed_ms=...` БЕЗ последующего skip

## Что было НЕ затронуто этим fix'ом

- Mig 334 Phase 3d Luteal (моя зона) — не related, корректно applied
- cron mutex sleep/stress/meal_morning (mig 330) — корректно работает (verified live)
- ConnectTimeout алерты в 10:00 MSK / 10:50 MSK — transient Supabase pooler glitches (~30 сек каждый), recovered. Не связано с deploy.
- Деплой PR #176 (mig 334) — **прошёл успешно**, smoke test был false-positive (поймал тот же class transient errors)

— wonderful-keller-8af0e2 (Adaptive Modifiers sprint)
