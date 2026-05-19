---
title: "TLS edge: Caddy + Let's Encrypt на `nomsbot.com`"
aliases: [tls, caddy, lets-encrypt, nomsbot-domain, https-edge]
tags: [infra, tls, vps, ops]
sources:
  - "daily/2026-05-19.md TLS migration"
  - "handover/2026-05-19_tls_caddy_migration.md"
  - "PR #106, #108, #109"
created: 2026-05-19
updated: 2026-05-19
---

# TLS edge: Caddy + Let's Encrypt на `nomsbot.com`

**TL;DR:** С 2026-05-19 весь входящий HTTPS-трафик идёт через Caddy на VPS с Let's Encrypt auto-renewal. FastAPI слушает plain HTTP loopback `127.0.0.1:8443`. Self-signed сертификат больше не используется. Stripe webhook стал технически возможен (требует валидный CA-cert).

## Архитектура

```
Telegram / Stripe / любые внешние webhooks
    ↓ HTTPS :443
    Caddy (reverse-proxy + Let's Encrypt)
    ↓ plain HTTP :8443 на 127.0.0.1
    FastAPI (noms-webhooks)
```

## Состав

| Компонент | Где | В git? |
|---|---|---|
| Домен `nomsbot.com` | Namecheap, A-records на `89.167.86.20` | n/a (DNS) |
| Caddyfile | `/etc/caddy/Caddyfile` на VPS | ❌ host state |
| LE certs (auto-managed) | `/var/lib/caddy/.local/share/caddy/...` | ❌ |
| FastAPI binding | `webhook_server.py` uvicorn host=`127.0.0.1`, port=8443 | ✅ |
| Telegram webhook URL | live state (Bot API) → `https://nomsbot.com/telegram/webhook` | live |
| Stripe webhook URL | Stripe Dashboard → `https://nomsbot.com/webhooks/stripe` | dashboard |

## Why

До 2026-05-19 FastAPI слушал `:8443` с self-signed cert. Это работало для Telegram (через `has_custom_certificate=true` + cert upload), но:
- **Stripe webhook невозможен** — Stripe требует валидный CA-cert.
- **Self-signed cert pain:** каждый внешний инструмент (curl, postman, тесты) надо настраивать с `--insecure` или trust CA.
- Cert rotation руками.

Caddy + LE решает всё это за 5 минут setup + auto-renewal.

## Acme HTTP-01 challenge

Caddy получает сертификат через HTTP-01 challenge:
1. ACME-сервер обращается к `http://nomsbot.com/.well-known/acme-challenge/<token>` на `:80`.
2. Caddy должен ответить правильным token.
3. → cert выдан.

**Требования:**
- A-record `nomsbot.com → 89.167.86.20` (актуальный).
- `:80` открыт извне на Hetzner firewall.
- Caddy слушает `:80` (по дефолту делает).

**Gotcha:** до покупки домена Namecheap «parking page» на `nomsbot.com` отдавала 404 на `.well-known/acme-challenge/...` — LE issuance fail. Только после смены A-records на VPS и старта Caddy issuance прошёл.

## Operations

```bash
# Обновить Caddyfile:
ssh root@89.167.86.20
sudo vim /etc/caddy/Caddyfile
sudo systemctl reload caddy   # graceful

# Логи:
journalctl -u caddy -f

# Проверить cert:
curl -vI https://nomsbot.com 2>&1 | grep -E "subject|issuer|expire"
# Issuer: Let's Encrypt, expiry ~90 дней
```

## Smoke test в CI

`deploy.yml` smoke probe использует **loopback** `http://127.0.0.1:8443/health`, НЕ публичный URL (PR #108). Это правильно:
- Loopback exclude'ит сетевые / DNS hiccups из CI smoke.
- Внешний URL проверяется отдельно — через мониторинг (`webhook_health.py`).

## Что НЕ ломать

1. **uvicorn host = `127.0.0.1`**, не `0.0.0.0`. Иначе кто угодно из мира бьёт FastAPI plain HTTP в обход TLS.
2. **`:80` остаётся открытым** на firewall — нужен для ACME renewal. Если закрыть — cert протухнет через 60 дней.
3. **Не добавлять `tls_insecure_skip_verify` в Caddy upstream.** Upstream — loopback plain HTTP, TLS verify не нужен. Если кто-то добавит — replicate'нет реальные ошибки.
4. **Caddyfile НЕ в git** — host state. Если правишь, документируй здесь или в handover.

## Связанное

- **Запрет `docs/` в основном репо** ([CLAUDE.md правило](../../CLAUDE.md)). Этот файл живёт в `claude-memory-compiler/knowledge/concepts/`, не в `docs/adr/` основного репо.
- Handover `handover/2026-05-19_tls_caddy_migration.md` — operational бриф для будущих агентов.
- Stripe live setup использует этот edge — без TLS Stripe webhook невозможен.
- [[concepts/release-protocol]] — pipeline не изменился, deploy.sh всё так же rsync'ает только Python код.
