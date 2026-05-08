---
title: "User Preferences (Vlad)"
aliases: [preferences, working-style]
tags: [user, workflow]
sources:
  - "daily/2026-04-08.md"
created: 2026-04-08
updated: 2026-04-14
---

# User Preferences

Working style and conventions for the NOMS project owner.

## Key Points

- Maximum delegation: provide SQL + JSON + JS + Python code ready to run
- Always: plan first, approve, then implement
- Minimal user involvement (just run SQL, import JSON, deploy Python)
- AI-generated docs — treat with skepticism, trust real code/DB
- Priority: Gamification > Menu > Payments > Referral > Notifications
- Bot must be fast — optimize where possible
- NO hardcoded emojis — all from `app_constants` table via `$json.icon_xxx || 'fallback'`
- n8n HTTP Request: `{{ $json.icon_xxx || 'emoji' }}` pattern, NEVER raw `\u{XXXX}`
- Local JSON files may be OUTDATED — always use MCP `get_workflow_details`
- One bug per session (from global CLAUDE.md rules)

## Related Concepts

- [[concepts/noms-architecture]]
