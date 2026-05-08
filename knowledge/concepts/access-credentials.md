---
title: "NOMS Access Credentials"
aliases: [credentials, api-keys]
tags: [reference, infrastructure]
sources:
  - "daily/2026-04-08.md"
  - "daily/2026-05-05.md"
created: 2026-04-08
updated: 2026-05-05
---

# NOMS Access Credentials

API keys and access for project automation.

## Key Points

- **Supabase REST API:** `https://pymmeubsoeuglivywhhv.supabase.co/rest/v1/` with `apikey` + `Authorization: Bearer <service_role>`
- **Supabase DB (psycopg2):** `DATABASE_URL` в `.env` через Supabase pooler (`aws-1-eu-west-1.pooler.supabase.com:5432`). Default метод для миграций.
- **n8n self-hosted API:** `http://127.0.0.1:5678/api/v1/` на VPS, доступ через SSH: `ssh root@89.167.86.20 'curl -H "X-N8N-API-KEY: $KEY" http://127.0.0.1:5678/...'`. Ключ `N8N_TARGET_API_KEY` в `/home/noms/n8n/compose/.env` (mode 600). UI — SSH-туннель `ssh -L 5678:127.0.0.1:5678 root@89.167.86.20`.
- **n8n Cloud (DEPRECATED 2026-04-30):** `https://vlad1.app.n8n.cloud` отменён. Если потребуется восстановить — поднять `N8N_BASE_URL` в `.env` нужного host.
- DB host DNS doesn't resolve from Mac → REST API или SSH tunnel.
- All credentials stored in `/Users/vladislav/Documents/NOMS/.env`.
- **Миграции:** psycopg2 через `DATABASE_URL` (default). Альтернатива: n8n temp workflow с credential `Postgres_pooler_6543` (ID `JW48yu2pfTUSntRn` self-hosted).

## Related Concepts

- [[concepts/noms-architecture]]
- [[concepts/n8n-self-hosting]]
- [[concepts/release-protocol]]
