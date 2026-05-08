---
title: "NOMS Architecture"
aliases: [architecture, tech-stack]
tags: [architecture, core]
sources:
  - "daily/2026-04-08.md"
created: 2026-04-08
updated: 2026-04-14
---

# NOMS Architecture

Telegram nutrition tracking bot with AI food recognition, gamification (XP, leagues, quests, NomsCoins), 13-language support, and subscriptions. Character: "Sassy Sage" — helpful without shaming.

## Key Points

- Hybrid: n8n (interactive UI) + Python (cron/webhooks/proxy) + Supabase (all business logic in RPC)
- RPC-first: all business logic in PostgreSQL functions, not Python/n8n
- Every feature = separate n8n workflow (easier to manage)
- Python cron: mana reset, streak checker, league cycle, notifications, subscription lifecycle
- **Python Telegram proxy (since 2026-04-21):** `webhook_server.py` sits between Telegram and n8n for latency-critical paths (typing indicator). Telegram → Python (ack in 6-10ms) → fire-and-forget indicator + forward raw update to n8n. Self-signed TLS cert on `:8443`. See [[concepts/telegram-proxy-indicator]].
- Speed priority: SQL/RPC > Python > n8n for logic
- Bot username: @nomsaibot. Deep link: `https://t.me/nomsaibot?start=ref_XXX`

## Layer Responsibilities

| Layer | Role | When to use |
|---|---|---|
| **Supabase RPC / SQL** | Business logic, transactions, gamification math | Always first — RPC-first principle |
| **n8n CE (self-hosted, Docker on VPS)** | UI routing, menus, onboarding, AI orchestration, admin flows | Complex visual routing, frequent non-engineer edits. **Migration from Cloud in progress (steps 0.1-0.4 done 2026-04-26, traffic switch pending).** See [[concepts/n8n-self-hosting]]. |
| **Python FastAPI (`webhook_server.py`)** | Latency-critical proxy, payment webhooks, external integrations | Ack < 10ms, fire-and-forget side-effects, race-sensitive DB writes. See [[concepts/telegram-proxy-indicator]] §"When to migrate n8n workflow to Python" for decision framework. |
| **Python APScheduler (`main.py`)** | Cron jobs — mana regen, streaks, leagues, reminders, health checks | Scheduled work, no user-facing latency |

## Related Concepts

- [[concepts/access-credentials]]
- [[concepts/user-preferences]]
- [[concepts/xp-model]]
- [[concepts/n8n-stateful-ui]]
- [[concepts/n8n-data-flow-patterns]]
- [[concepts/n8n-performance-optimization]]
- [[concepts/n8n-self-hosting]]
- [[concepts/telegram-proxy-indicator]]
- [[concepts/supabase-db-patterns]]
- [[concepts/league-npc-system]]
