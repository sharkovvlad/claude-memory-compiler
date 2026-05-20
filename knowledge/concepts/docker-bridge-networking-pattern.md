# Docker bridge networking: container→host loopback gotcha

> **Lesson date:** 2026-05-20 (food log Python cutover, PR C iterations v2-v3).
> **Symptom:** ECONNREFUSED при n8n container → host webhook_server.

## TL;DR

**`127.0.0.1` внутри Docker container** = container's own loopback (тот же container), **НЕ хост**. Если host service биндится на `127.0.0.1:PORT`, контейнер до него **не достучится**.

## Symptom

n8n container (network `compose_default`, IP `172.18.0.2`) делал HTTP POST на `http://127.0.0.1:8443/internal/food_log/render`. Webhook server (uvicorn) на хосте binding `127.0.0.1:8443`. Result: **ECONNREFUSED** в n8n execution log, despite service active и host curl возвращает 403/400 correctly.

## Root cause

Container shares network stack with itself, **не с хостом**. `127.0.0.1` resolves в container's own loopback interface. Host's `127.0.0.1` accessible через:

1. **Bridge gateway IP** (e.g. `172.18.0.1` для `compose_default`, `172.17.0.1` для default bridge).
2. **`host.docker.internal`** — requires explicit `extra_hosts: - "host.docker.internal:host-gateway"` в docker-compose, иначе not resolved.
3. **`network_mode: host`** — container shares host namespace, but loses isolation. Heavy hammer.

## Fix pattern

### 1. Find bridge gateway IP

From inside container:
```bash
docker exec <container> sh -c "ip route | grep default"
# default via 172.18.0.1 dev eth0
```

Or from host:
```bash
ip -br addr show | grep -E "br-|docker"
# docker0          DOWN  172.17.0.1/16
# br-XXXXXXXXXX    UP    172.18.0.1/16
```

### 2. Make host service listen on accessible IP

**Option A: `0.0.0.0` (всё)** — simplest, but exposes to **public** если firewall не блокирует port. Check via external scan:
```bash
# From outside machine
timeout 5 bash -c '</dev/tcp/<public-ip>/<port>' && echo OPEN || echo BLOCKED
```
If blocked by cloud firewall (Hetzner, AWS SG, etc.) → safe to bind 0.0.0.0.

**Option B: bridge gateway IP only** — `172.18.0.1:PORT`. Cleaner, но requires uvicorn/service to bind на specific IP that's only docker-reachable. Beware: Caddy на host через `127.0.0.1` upstream **потеряет access**. Need bind на оба addresses OR change Caddy upstream.

### 3. Use bridge gateway in container code

```python
PYTHON_ENDPOINT_URL = "http://172.18.0.1:8443/internal/food_log/render"
```

NOT `127.0.0.1:8443`.

### 4. Verify reachability

```bash
docker exec <container> node -e "
const http = require('http');
const req = http.request({host:'172.18.0.1', port:8443, path:'/health', method:'GET', timeout:3000}, r => console.log(r.statusCode));
req.on('error', e => console.log('ERROR', e.code));
req.end();
"
# Expected: 200 OK или 403 (with token requirement), not ECONNREFUSED.
```

## In NOMS context

Used by n8n `03_AI_Engine` → `POST /internal/food_log/render` (handlers/food_log.py callback, mig 287/PR #131).

- n8n container в bridge network `compose_default`, gateway `172.18.0.1`.
- webhook_server systemd unit получил drop-in override (`/etc/systemd/system/noms-webhooks.service.d/override.conf`) binding `0.0.0.0:8443`.
- External 8443 blocked by Hetzner Cloud Firewall (verified).
- See `tools/_n8n_03_ai_engine_modify.py` constant `PYTHON_ENDPOINT_URL`.

## Alternative: outbound через Caddy public URL

Если bridge access сложно (e.g. n8n в другой network namespace) — container может POST на public URL: `https://nomsbot.com/internal/food_log/render`. Tradeoffs: +TLS handshake overhead (~50-100ms), +Caddy routing config, surface через public. Хорош только если container не в той же docker network as host.

## Связано

- [[concepts/tls-caddy-nomsbot]] — Caddy edge + loopback `127.0.0.1:8443` (host-only).
- [[concepts/systemd-dropin-override-pattern]] — persistent bind change.
- [[daily/2026-05-20]] — PR C iterations v2-v3 (полная chronology).
