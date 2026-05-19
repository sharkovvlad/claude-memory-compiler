# Handover — TLS migration к `nomsbot.com` (Caddy + Let's Encrypt)

**Дата:** 2026-05-19. **Статус:** live, стабильно. **Для:** следующего агента, который захочет понять как устроен TLS-edge на VPS, что и где править.

---

## Архитектура (одна строкой)

```
Telegram / Stripe / любые внешние webhooks
    ↓ HTTPS :443
    Caddy (reverse-proxy + Let's Encrypt auto-renewal)
    ↓ plain HTTP :8443 на 127.0.0.1
    FastAPI (noms-webhooks, user: taskbot, WD: /home/taskbot/noms)
```

- Домен `nomsbot.com` куплен через Namecheap. A-records → `89.167.86.20`.
- Caddy слушает `:80` (HTTP-01 ACME challenge + redirect на HTTPS) и `:443` (TLS termination).
- FastAPI теперь plain HTTP loopback `127.0.0.1:8443`. Self-signed cert убран из FastAPI (не нужен).
- Let's Encrypt cert auto-renewal делает Caddy. Cert и keys лежат в `/var/lib/caddy/...` (стандартный Caddy data dir).

---

## Где что лежит

| Что | Где | В git? |
|---|---|---|
| **Caddyfile** | `/etc/caddy/Caddyfile` на VPS | ❌ host state, не в репо |
| **LE certs** | `/var/lib/caddy/.local/share/caddy/...` | ❌ |
| **FastAPI config** | `webhook_server.py` (uvicorn host=`127.0.0.1`, port=8443, без ssl_keyfile/certfile) | ✅ |
| **Telegram webhook URL** | задаётся через Bot API `setWebhook` → `https://nomsbot.com/telegram/webhook` | live state |
| **Stripe webhook URL** | задаётся в Stripe Dashboard → `https://nomsbot.com/webhooks/stripe` | dashboard state |

**Caddyfile (примерная форма, проверять live):**
```
nomsbot.com {
    reverse_proxy 127.0.0.1:8443
    encode gzip
}
```

---

## Операции

### Обновить Caddy config

```bash
ssh root@89.167.86.20
sudo vim /etc/caddy/Caddyfile
sudo systemctl reload caddy   # graceful, без drop соединений
sudo systemctl status caddy
journalctl -u caddy -f         # follow логи
```

### Проверить cert

```bash
ssh root@89.167.86.20 'curl -vI https://nomsbot.com 2>&1 | grep -E "subject|issuer|expire"'
# Issuer: Let's Encrypt, expiry ~90 дней, Caddy renew'ит за 30 дней до.
```

### Логи

- Caddy: `journalctl -u caddy -f`
- FastAPI: `journalctl -u noms-webhooks -f`

### Smoke test (что работает)

```bash
# Извне (любая машина):
curl -sS https://nomsbot.com/health
# {"status":"ok",...}

# С VPS (loopback, минуя Caddy):
ssh root@89.167.86.20 'curl -sS http://127.0.0.1:8443/health'
```

Smoke в `deploy.yml` уже использует loopback `http://127.0.0.1:8443/health` (PR #108) — НЕ ходит через домен, чтобы CI не валился из-за DNS / external network hiccup.

---

## Что НЕ ломать

1. **Не возвращать `tls_insecure_skip_verify` в Caddy config.** Не нужен — апстрим plain HTTP loopback. Если кто-то добавит — Caddy будет молча отбрасывать TLS errors апстрима, маскируя реальные проблемы.
2. **Не давать FastAPI наружу.** uvicorn host должен быть `127.0.0.1`, не `0.0.0.0`. Иначе кто угодно из мира может бить FastAPI plain HTTP в обход Caddy и TLS.
3. **Не менять `nomsbot.com` A-records без координации.** Если IP VPS меняется (переезд) — Telegram webhook надо переустановить через `setWebhook`, Stripe webhook через Dashboard.
4. **LE renewal требует доступности `:80` извне.** ACME HTTP-01 challenge. Если firewall закроет `:80` — renewal упадёт через ~60 дней, cert протухнет. Hetzner firewall сейчас открыт на 80/443.
5. **Caddyfile НЕ в git.** Если правишь — задокументируй в handover'е или в KB, иначе следующий агент не узнает.

---

## История

- **До 2026-05-19:** FastAPI слушал `:8443` с self-signed cert. Telegram принимал self-signed (через `has_custom_certificate=true` + cert загружен). Stripe webhook был **технически невозможен** (Stripe требует валидный CA-cert).
- **2026-05-19 (этот handover):** домен куплен, Caddy + LE поставлены, FastAPI на loopback, Telegram webhook переустановлен через Bot API, Stripe webhook создан в Dashboard, `sk_live/whsec` в `.env`.
- **PR'ы:** #106 (config), #108 (smoke loopback), #109 (`webhook_health.py` default URL).

---

## Связанное

- `services/webhook_health.py` — теперь дефолтит на `https://nomsbot.com/...`.
- `.github/workflows/deploy.yml` — smoke probe использует `http://127.0.0.1:8443/health` (loopback), не публичный URL.
- KB `release-protocol.md` — pipeline не изменился, deploy.sh всё так же rsync'ает Python код на VPS.

**Если что-то сломается в TLS:**
1. `curl -vI https://nomsbot.com` — что-то с cert / DNS / Caddy.
2. `systemctl status caddy && journalctl -u caddy -n 100` — Caddy state.
3. `dig nomsbot.com` — A-records актуальны.
4. Emergency fallback: вернуть Telegram webhook на self-signed `https://89.167.86.20:8443/telegram/webhook` через `setWebhook` (cert ещё лежит на VPS как backup, проверить путь).
