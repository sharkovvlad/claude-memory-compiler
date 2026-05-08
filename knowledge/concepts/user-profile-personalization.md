---
title: "User Profile Personalization"
aliases: [display-name, sync-user-profile, name-placeholder, language-normalization]
tags: [users, personalization, supabase, n8n]
sources:
  - "daily/2026-04-09.md"
created: 2026-04-09
updated: 2026-04-09
---

# User Profile Personalization

System for keeping user names current and injecting them into notifications and UI. Built across migrations 043–044.

## Key Points

- **`sync_user_profile(telegram_id, first_name, username)`** RPC: updates `first_name`/`username` on change, updates `last_active_at` if stale >5 minutes — called from Dispatcher as a parallel fire-and-forget branch on every message
- **`display_name` in `v_user_context`**: `COALESCE(first_name, username, 'User')` — fallback chain for all personalization
- **`{name}` placeholder**: added to reminder strings in `ui_translations`; Python crons do `.replace("{name}", display_name)`; n8n Template Engine Phase 2 substitutes `{name}` in all UI strings
- **Language code normalization**: regional codes `pt-BR` → `pt`, `zh-CN` → `en` — one-time UPDATE in migration 044, enforced going forward in `Auto Create User` n8n node
- **Real lang_codes in DB:** `ar, de, en, es, fa, fr, hi, id, it, pl, pt, ru, uk` (NOT `ja/zh/ko/th/tr` as old documentation claimed)

## Details

### Why this was needed

Before migration 043, `username` was never saved to the DB. `first_name` was only set at account creation and never updated. `last_active_at` was only updated when a user logged food — meaning users who only interacted with menus appeared inactive, silently breaking the inactivity reminder cron.

The `sync_user_profile` RPC debounces writes: it only updates `last_active_at` if the last recorded activity was more than 5 minutes ago, preventing a DB write on every single message. It runs in a parallel branch off the Dispatcher's "Auto Create User" node — fire-and-forget, never blocking the main response path.

### Language code normalization bug

Regional codes like `pt-BR` and `zh-CN` were stored verbatim in `users.language_code`. The `ui_translations` lookup used exact match — no translations were found for these codes, causing the bot to go silent for affected users. Fixed with a one-time normalization UPDATE in migration 044, and enforced going forward in the `Auto Create User` n8n node which normalizes the code on initial registration.

### Template Engine Phase 2

n8n Template Engine handles substitution in phases:
- Phase 1: `{{icon_xxx}}` → emoji value from `app_constants`
- Phase 2: `{name}` → `display_name` from context

Python cron scripts (`reminders.py`, `league_cycle.py`, `streak_checker.py`) handle their own `{name}` substitution with `.replace()` since they don't route through n8n. The `cron_get_reminder_candidates` RPC includes `display_name` in the JSONB per candidate so Python can access it.

## Related Concepts

- [[concepts/n8n-template-engine]]
- [[concepts/supabase-db-patterns]]
- [[concepts/noms-architecture]]

## Sources

- [[daily/2026-04-09.md]] — Migrations 043–044: sync_user_profile RPC, display_name in v_user_context, {name} placeholders in reminder strings, language code normalization
