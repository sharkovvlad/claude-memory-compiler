---
title: "n8n Self-Hosting on VPS"
aliases: [n8n-docker, self-hosted-n8n, vps-n8n]
tags: [n8n, infrastructure, docker, performance]
sources:
  - "daily/2026-04-26.md"
created: 2026-04-26
updated: 2026-04-27
---

# n8n Self-Hosting on VPS

Migration from n8n Cloud to self-hosted n8n CE in Docker on the NOMS VPS (Hetzner CX21, `89.167.86.20`). Primary motivation: eliminate cold-start latency ~1.3-1.5s on first user click after cloud scheduler idle.

## Status

**Steps 0.1–0.8 DONE (2026-04-26 → 2026-04-27).** Self-hosted n8n CE 2.17.7 живой, 15 workflows импортированы и активированы, traffic переключён на `localhost:5678`, бот работает на self-host. Подробности процесса миграции (REST API quirks, draft/published validation хак, big-bang switch) — в [[concepts/n8n-selfhost-migration]].

**Steps 0.9–0.10 IN PROGRESS:** 24-72h наблюдение latency, затем отмена n8n Cloud subscription.

**Latency benchmark (live, 2026-04-27 18:55+ UTC):**
- `forward_to_n8n elapsed_ms`: 58-157 ms (cloud: ~370-700 ms p95)
- Cold-start первого клика: 0 (cloud: +1.3-1.5 s)
- Reduction 4-6x на forward, ~10x на cold-start.

## VPS Resource Baseline

| Resource | Before (2026-04-26) | After n8n container |
|---|---|---|
| RAM | 717 MB used / 3.7 GB | 1.0 GB used / 3.7 GB |
| Disk | 5.8 GB / 38 GB | unchanged |
| Ports (new) | — | `127.0.0.1:5678` (n8n, localhost only) |
| n8n container RAM | — | 236 MB (limit 1.5 GB) |

Existing services (`noms-webhooks`, `noms-cron`, `tasktracker-bot`) not touched.

## File Layout on VPS

```
/home/noms/n8n/                  mode 750, owner n8n:n8n  ← isolation boundary
  compose/
    .env                    mode 600, owner n8n       ← credentials
    docker-compose.yml
  data/                     owner 1000:1000 (node user inside image)
  backups/                  for future SQLite copies
/etc/systemd/system/noms-n8n.service
```

## docker-compose.yml Key Decisions

```yaml
image: docker.n8n.io/n8nio/n8n:latest   # CE, v2.17.7
ports:
  - "127.0.0.1:5678:5678"               # localhost only — SSH tunnel for UI
volumes:
  - /home/noms/n8n/data:/home/node/.n8n      # persistent SQLite + credentials
mem_limit: 1.5g
environment:
  N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS: "true"
  EXECUTIONS_DATA_PRUNE: "true"
  EXECUTIONS_DATA_MAX_AGE: 7            # retain 7 days
  N8N_DIAGNOSTICS_ENABLED: "false"
  N8N_VERSION_NOTIFICATIONS_ENABLED: "false"
restart: unless-stopped
```

No `user:` override — image runs as UID 1000 (`node`). No `N8N_USER_FOLDER` or `DB_SQLITE_DATABASE` overrides.

## .env Credentials (VPS, mode 600)

| Variable | How generated |
|---|---|
| `N8N_ENCRYPTION_KEY` | `openssl rand -hex 32` (64 hex chars) — stable, never rotate |
| `N8N_BASIC_AUTH_USER` | N/A (removed — deprecated since n8n 1.0+, owner created at `/setup`) |
| `N8N_BASIC_AUTH_PASSWORD` | N/A (removed) |

Owner account created at first browser visit to `http://localhost:5678/setup` (via SSH tunnel).

## systemd Unit

```
/etc/systemd/system/noms-n8n.service

Type=oneshot
RemainAfterExit=yes
ExecStart=docker compose -f /home/noms/n8n/compose/docker-compose.yml up -d
ExecStop=docker compose -f /home/noms/n8n/compose/docker-compose.yml down
```

`Type=oneshot RemainAfterExit` is the correct pattern for systemd wrapping `docker compose up -d` — the process exits immediately after starting detached containers, but the unit stays `active`.

## Isolation Pattern

**Permissions-based isolation, not UID namespace remapping:**

- `/home/n8n` mode 750, owner `n8n:n8n` → `taskbot` (UID 1000) has no execute bit, cannot enter directory
- Files inside `/home/noms/n8n/data/` owned by UID 1000 (resolves to `taskbot` on host, but is the `node` user inside container) — this is expected
- `userns-remap` not needed; cost is low, complexity is zero

## SQLite Choice (not Supabase)

n8n's internal database (workflow definitions, executions, credentials, settings) is **not business data**. SQLite reads workflows in ~0.5ms local vs ~30ms via Supabase network (EU region). Business data stays in Supabase PostgreSQL via RPC as always.

## Deprecated Config Removed

| What was tried | Why removed |
|---|---|
| `N8N_BASIC_AUTH_*` | Deprecated since n8n 1.0+; owner created at `/setup` instead |
| `N8N_USER_FOLDER` + `DB_SQLITE_DATABASE` overrides | Caused double-nested path `/home/node/.n8n/.n8n` + EACCES |
| `N8N_RUNNERS_ENABLED=true` | Deprecated in 2.x — runners enabled by default |
| `user: "1001:1001"` in compose | Image has `/home/node` owned by UID 1000 mode 700; UID override broke access |

`chown -R 1000:1000 /home/noms/n8n/data` is required because Docker image runs as UID 1000 (`node`), not UID 1001 (`n8n` host user).

## Migration Plan (Pending Steps)

| Step | What | Notes |
|---|---|---|
| 0.5 | **Owner setup** — SSH tunnel `ssh -L 5678:127.0.0.1:5678 root@89.167.86.20` → `http://localhost:5678/setup` with `sharkov.vlad@gmail.com` | Password in `/home/noms/n8n/compose/.env` |
| 0.5 | **N8N_API_KEY** — Settings → API → Create API Key | Needed for `n8n_migrate.py` |
| 0.6 | **`scripts/n8n_migrate.py`** — import 14 workflows from `json архив/n8n_2026.04.26/` via POST `/workflows`, re-link 3 credential types (Telegram bot token, Supabase service_role, Postgres pooler) | Credentials must be re-created manually in UI first |
| 0.7 | **Test executions** on self-hosted without switching production traffic | 24-72h observation |
| 0.8 | **Big-bang traffic switch** — update `N8N_WEBHOOK_URL` on VPS, re-register Telegram webhook | Nighttime EU window |
| 0.9 | **Latency monitoring** | 24-72h post-switch |
| 0.10 | **Cancel n8n Cloud** | Only after 3+ days stable |

## Backup Strategy

Daily SQLite copy via cron under user `noms` (DONE 2026-04-27): `/home/noms/n8n/backups/database_*.sqlite.gz` at **03:15 UTC**, retained 30 days.

## Tuning Parameters (28.04 update)

После пары инцидентов OOM на CX21 (2 vCPU + 3.7 GB RAM) — добавлены защитные параметры:

| Parameter | Value | Why |
|---|---|---|
| Host swap | `/swapfile` 2 GB, `vm.swappiness=10`, persistent в `/etc/fstab` | Защита **OS**, НЕ контейнера. `memswap_limit=mem_limit=1500m` оставлен (fail-fast: Docker убивает n8n при OOM, не уходит в swap) |
| Pruning | `EXECUTIONS_DATA_MAX_AGE=48` (часов), `PRUNE_MAX_COUNT=5000`, `PRUNE_HARD_DELETE_BUFFER=24` | Не разрастается БД executions |
| V8 heap cap | `NODE_OPTIONS=--max-old-space-size=1024` | Видимая ошибка OOM вместо kernel OOM kill |
| Visibility | `SAVE_ON_SUCCESS=all`, `SAVE_ON_ERROR=all` | Все executions в БД для дебага |

## ⚠️ Multi-agent safety

**НЕ работать на prod VPS** через долгие интерактивные SSH-сессии. Если несколько агентов одновременно делают `ripgrep` через всю кодовую базу или массовый `grep -r` — VPS уходит в OOM, бот молчит, SSH не отвечает (инцидент 28.04 17:30 MSK).

**Правило:** worktree живут на маке. Agents используют SSH к VPS только для коротких read-only проверок (`curl healthz`, `cat .env`, `journalctl --since`). Любая долгая операция (grep по большой кодбазе, `du -h`, `find /`) — на маке после `scp -r`.

## Cancellation of n8n Cloud (2026-04-30)

n8n Cloud (`vlad1.app.n8n.cloud`) **отменён**. Self-hosted на VPS — единственный источник истины. Cleanup [release 2026-05-05]: убран cloud-fallback из `scripts/n8n_backup.py`, KB-упоминания почищены.

## Related Concepts

- [[concepts/n8n-selfhost-migration]] — **полный playbook миграции (0.5-0.8)**: REST API patterns, schema validation подвохи, draft/published хак, big-bang switch checklist, latency benchmark
- [[concepts/noms-architecture]] — n8n is the UI orchestration layer; self-hosting eliminates Cloud cold-start
- [[concepts/n8n-performance-optimization]] — cold-start was the remaining bottleneck after Python proxy (~85% improvement for indicator, but first-click menu still had 1.3-1.5s from Cloud idle)
- [[concepts/telegram-proxy-indicator]] — Python proxy eliminated indicator latency; this migration addresses menu response latency
