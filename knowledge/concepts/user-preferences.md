---
title: "User Preferences (Vlad)"
aliases: [preferences, working-style]
tags: [user, workflow]
sources:
  - "daily/2026-04-08.md"
created: 2026-04-08
updated: 2026-05-30
---

# User Preferences

Working style and conventions for the NOMS project owner.

## Communication style (2026-05-30)

- **Простой, доступный язык.** Owner — продуктовый/бизнес-владелец, не инженер. Объясняй *последствиями* для пользователя/продукта, а не внутренней механикой. Избегай жаргона (TTL, race condition, idempotency, fire-and-forget, regen) там, где без него можно обойтись; если термин нужен — дай короткий человеческий перевод рядом.
  - ❌ «кеш `my_day_insight` просрочен по TTL 4ч → fallback на статичный `insight_eating_little`»
  - ✅ «фраза Номса хранится 4 часа, потом устаревает — и бот показывает заранее заготовленную фразу вместо живой AI»
  - Технические имена (таблицы, RPC, callback, file:line, номера миграций) — в конец, как ссылка «где лежит», а не в тело объяснения.
  - Стиль для общения с owner-ом. В коде / коммитах / KB технические термины уместны.
- **Всё по-русски** (кроме имён БД / callback / RPC / state_code / путей).

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
