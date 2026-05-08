---
title: "Supabase Security — RLS and Access Control"
aliases: [rls, row-level-security, service-role, revoke, access-control, anon-protection]
tags: [supabase, security, rls, database, architecture]
sources:
  - "daily/2026-04-13.md"
created: 2026-04-13
updated: 2026-04-13
---

# Supabase Security — RLS and Access Control

Security hardening for Supabase tables and views in NOMS: Row-Level Security (RLS), REVOKE on sensitive views, and the service_role-only access pattern.

## Key Points

- **RLS everywhere:** Every table must have RLS enabled; `app_constants_cache` was the last table without it (fixed in migration 057)
- **REVOKE on sensitive views:** `v_user_context` contains full PII (names, targets, financial data) — access revoked from `anon` and `authenticated` roles (migration 058)
- **service_role only for the bot:** The bot connects exclusively via service_role key. `anon` and `authenticated` roles are never used. REVOKE statements restrict access accordingly
- **3 TEMP_* workflows deleted:** Forgotten n8n temp workflows (created for migration execution) were left active; manually identified and deleted as a security hygiene step

## Details

### Migration 057: RLS on app_constants_cache

`app_constants_cache` was the only table in the NOMS schema without Row-Level Security enabled. The table contains cached JSONB of all `app_constants` rows, including internal configuration values.

Fix applied in migration 057:
```sql
ALTER TABLE app_constants_cache ENABLE ROW LEVEL SECURITY;
-- Allow service_role full access (bypasses RLS by default)
-- No explicit policy needed for service_role
```

After this migration, all tables in the schema have RLS enabled.

### Migration 058: REVOKE on v_user_context

`v_user_context` is the central performance view — it bundles user data, translations, app constants, and all personalization fields in one query. As a consequence, it contains:
- `first_name`, `username` (PII)
- `target_calories`, `target_protein_g`, `target_fat_g`, `target_carbs_g` (health data)
- `subscription_status`, `nomscoins`, `level` (financial/game data)
- All 13-language translations

By default, Supabase grants `SELECT` on all views to the `anon` and `authenticated` roles. This means any anon REST request could read any user's full profile by `telegram_id`.

Migration 058 applied:
```sql
REVOKE ALL ON v_user_context FROM anon, authenticated;
GRANT SELECT ON v_user_context TO service_role;
```

After this change, `v_user_context` is only accessible via service_role — the role used exclusively by the bot's backend. Anon REST calls return a 403 Permission Denied error.

### Why service_role only

The NOMS bot never uses JWT-based authentication (no Supabase Auth users). All requests from n8n and Python go through the service_role key stored in environment variables. The `anon` and `authenticated` roles have no legitimate use case in this architecture.

This means:
- RLS policies blocking `anon` are valid security controls, not obstacles
- Removing broken RLS policies that depended on `auth.uid()` (always NULL in service_role context) was correct — see migration 047

### TEMP_* workflow cleanup

Migrations are applied via temporary n8n workflows (Webhook + Postgres nodes) created, triggered, then deleted. After the April 8–13 development sprint, 3 TEMP_* workflows had been left active in n8n.

These pose a risk:
- Active webhooks can be triggered externally
- They expose Postgres credential (`Postgres_pooler_6543`) in an easily-discoverable endpoint
- n8n cloud instances bill partly on active workflow count

All 3 were manually identified and deleted. Best practice: always delete temp migration workflows immediately after use.

### Access control summary

| Role | app_constants_cache | v_user_context | Other tables |
|------|--------------------|--------------------|-------------|
| `anon` | RLS (no policy = deny) | REVOKE (deny) | RLS (deny) |
| `authenticated` | RLS (no policy = deny) | REVOKE (deny) | RLS (deny) |
| `service_role` | Full access (bypasses RLS) | GRANT SELECT | Full access (bypasses RLS) |

## Related Concepts

- [[concepts/supabase-db-patterns]]
- [[concepts/access-credentials]]
- [[concepts/noms-architecture]]

## Sources

- [[daily/2026-04-13.md]] — Migration 057: RLS on app_constants_cache; Migration 058: REVOKE on v_user_context; 3 TEMP_* workflow cleanup
