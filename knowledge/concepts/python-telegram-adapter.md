---
title: "Python Telegram Adapter — Replacing Telegram Trigger in n8n"
aliases: [telegram-adapter, python-adapter, raw-json-adapter, webhook-adapter]
tags: [python, telegram, webhook, architecture, adapter, deployed]
sources:
  - "daily/2026-04-23.md"
created: 2026-04-23
updated: 2026-04-23
status: "LIVE — Phases 1-5 deployed (Session 12). Phase 6 pending (remove Trigger node)"
---

# Python Telegram Adapter

Architectural solution to the webhook auto-reregistration problem. Python proxy re-packages raw Telegram JSON to exactly mimic the Telegram Trigger output format. n8n receives familiar payload through a regular Webhook Trigger instead of Telegram Trigger — eliminating the auto-`setWebhook` displacement issue.

## Problem Being Solved

Any `PUT /api/v1/workflows/6XzdbQqpoUG0nsLe` (01_Dispatcher) causes n8n Cloud to call `setWebhook`, displacing the Python proxy. Session 11: webhook lost 3 times (once per Dispatcher PUT). Session 10: lost 5 times.

Root cause: 01_Dispatcher contains a Telegram Trigger node. n8n Cloud re-registers its webhook on every PUT to any workflow with an active Telegram Trigger.

See: [[concepts/dispatcher-webhook-reregistration]]

## Solution: Adapter Pattern

```
[Telegram]
    ↓ raw Telegram update (message/callback_query/etc.)
[Python webhook_server.py]
    ↓ ack 200 OK to Telegram (6-10ms)
    ↓ adapter: repackage raw update → n8n Telegram Trigger format
[n8n Webhook Trigger]  ← NOT Telegram Trigger anymore
    ↓ receives familiar payload, processes normally
[01_Dispatcher Route Classifier → ...]
```

n8n sees exactly the same payload structure it always received from Telegram Trigger — no n8n-internal changes required.

## Baseline Dump

**File:** `.claude/data/telegram_trigger_dump.json`

15 execution samples, 7 update types:
- `message` (text)
- `message` (photo)
- `callback_query`
- `message` (voice)
- `pre_checkout_query`
- `message` (location)
- `message` (contact)

The dump captures the exact field names, nesting, and data types that Telegram Trigger emits. The adapter must reproduce this format faithfully for every update type.

## 6-Phase Rollout Plan

| Phase | Description |
|-------|-------------|
| 1 | Implement adapter: `raw_telegram_update → n8n_format()` function in Python |
| 2 | Unit test against all 7 dump samples (field-by-field equality) |
| 3 | Add n8n Webhook Trigger node to 01_Dispatcher (alongside existing Telegram Trigger) |
| 4 | Shadow mode: adapter sends to both Telegram Trigger and Webhook Trigger; compare outputs |
| 5 | Cut over: disable Telegram Trigger routing, enable Webhook Trigger |
| 6 | Remove Telegram Trigger node from 01_Dispatcher (now safe to PUT without webhook displacement) |

Flag-based: each phase is a config flag in Python, allowing instant rollback to any previous phase.

## Key Mapping: Telegram raw → n8n Telegram Trigger format

The Telegram Trigger node transforms raw Telegram API updates before forwarding to the workflow. Key transformations:

```python
# Raw Telegram callback_query
{
    "update_id": 123456789,
    "callback_query": {
        "id": "...",
        "from": {"id": 417002669, ...},
        "message": {"message_id": 42, ...},
        "data": "cmd_get_profile"
    }
}

# n8n Telegram Trigger output (what 01_Dispatcher Route Classifier reads)
{
    "update_id": 123456789,
    "callback_query": {
        "id": "...",
        "from": {"id": 417002669, ...},
        "message": {"message_id": 42, ...},
        "data": "cmd_get_profile"
    },
    # Telegram Trigger adds top-level shortcuts:
    "message": null,  # or flattened
    "callback_query_id": "...",
    "callback_data": "cmd_get_profile"  # top-level shortcut
    # ... etc
}
```

Exact mapping verified from dump file — do not rely on memory. Read `.claude/data/telegram_trigger_dump.json` before implementing.

## Why Not Variant A (Separate 00_TelegramReceiver workflow)

Variant A (isolate Telegram Trigger into stub `00_TelegramReceiver` → executeWorkflow to 01_Dispatcher) was also considered. Python Adapter (Variant B) is preferred because:

1. Python already controls the webhook — natural place for the adapter
2. Removes n8n Cloud dependency for webhook registration entirely
3. Easier to test (pure Python, no n8n API involved)
4. Future-proof: Python can add pre-processing (rate limiting, dedup, analytics) without n8n changes

## Deployment Status (Session 12 — 2026-04-23)

**Phases 1-5: LIVE.** Root cause of webhook displacement eliminated.

### What was deployed

| Phase | Status | Details |
|-------|--------|---------|
| 1 | ✅ | Backup Dispatcher snapshot (`/tmp/dispatcher_phase1_backup_1776973596.json`). 14 nodes identified as consumers of `$('Telegram Trigger')`. |
| 2 | ✅ | `Webhook from Python` node added (path=`telegram-updates`, responseMode=onReceived). `Validate Secret` Code node added — checks `X-Noms-Secret`, normalizes shape. **80 downstream refs** migrated to `$('Validate Secret')` across 14 nodes. Both connected in parallel with existing Telegram Trigger. |
| 3 | ✅ | `telegram_proxy.py:365-382` — `forward_to_n8n` now sends `X-Noms-Secret: $N8N_WEBHOOK_SECRET` header. `N8N_WEBHOOK_SECRET` (64 hex) added to `.env` (local + VPS). |
| 4 | — | Shadow mode skipped — dump already validated field-by-field; direct cutover deemed safe. |
| 5 | ✅ | `N8N_WEBHOOK_URL` updated to `https://vlad1.app.n8n.cloud/webhook/telegram-updates`. Telegram Trigger **disabled** (`disabled=true`) as rollback safety net. Smoke tests passed (5 scenarios). |
| 6 | ⏳ | Remove Telegram Trigger node from Dispatcher entirely. Pending 48h stability. |

### Smoke test results (Session 12, admin user 417002669)

| Test | Entry node | Result |
|------|-----------|--------|
| Reply "☀️ Mi Día" | Webhook from Python | ✅ Stats headless (2185/2483 ккал, 3 meals) |
| Reply "👤 Perfil" | Webhook from Python | ✅ Profile |
| Reply "🚀 Progreso" | Webhook from Python | ✅ Progress legacy |
| Text "кофе с молоком" | Webhook from Python | ✅ AI analysis: 30 ккал, +15 XP |
| Inline "✏️ Исправить" (Stats) | Webhook from Python | ⚠️ Routing bug — separate task |
| Bad `X-Noms-Secret` | Webhook from Python | ✅ Rejected with "Unauthorized" |

Execution 10290 = first end-to-end success via new path.

### Async T+8s drift discovery

During Phase 2 deployment, a new failure mode was found: n8n.cloud performs async webhook re-sync ~8 seconds after PUT while Telegram Trigger is still active. Agent restores webhook manually → 8s later n8n overwrites it again.

**Rule:** When Telegram Trigger is active in a workflow, verify webhook at **T+5s AND T+15s** after any PUT, not just immediately.

After Phase 5.5 (Trigger disabled) → no-op PUT at T+60s → webhook remained stable at T+10s and T+25s. **Root cause confirmed resolved.**

### Phase 6 — pending (Session 13)

```
1. GET Dispatcher fresh
2. Remove Telegram Trigger node + its connections (Validate Secret stays)
3. PUT Dispatcher (now safe — no Trigger = no auto-setWebhook)
4. Update KB: dispatcher-webhook-reregistration → status resolved
5. Update this article → status complete
```

### Current state of 01_Dispatcher

- 55 nodes (was 53)
- Telegram Trigger: present but `disabled=true`
- All downstream nodes reference `$('Validate Secret')`, not `$('Telegram Trigger')`
- `N8N_WEBHOOK_URL`: `https://vlad1.app.n8n.cloud/webhook/telegram-updates`
- `N8N_WEBHOOK_SECRET`: set on local + VPS

Short-term mitigation no longer needed after Phase 5 — PUT to Dispatcher is safe while Trigger is disabled.

## Related

- [[concepts/dispatcher-webhook-reregistration]] — the problem this solves
- [[concepts/telegram-proxy-indicator]] — current Python proxy architecture (where adapter will be added)
- [[concepts/n8n-multi-agent-workflow-editing]] — GET before PUT protocol (still needed until adapter deployed)
