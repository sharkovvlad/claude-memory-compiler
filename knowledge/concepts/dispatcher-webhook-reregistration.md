---
title: "Dispatcher Webhook Re-registration Bug (01_Dispatcher PUT)"
aliases: [webhook-reregistration, dispatcher-put-webhook, setwebhook-displacement, webhook-lost]
tags: [n8n, telegram, webhook, architecture, incident, critical]
sources:
  - "daily/2026-04-22.md"
created: 2026-04-22
updated: 2026-04-22
---

# Dispatcher Webhook Re-registration Bug (01_Dispatcher PUT)

Критическое обнаружение: **любой PUT-запрос к 01_Dispatcher** (workflow с Telegram Trigger нодой) автоматически вызывает `setWebhook` на n8n.cloud URL, вытесняя Python proxy. Это происходит при КАЖДОМ PUT — не только при deactivate/activate. За 2026-04-22 webhook потерян 5 раз.

## Key Points

- **Триггер:** любой `PUT /api/v1/workflows/6XzdbQqpoUG0nsLe` → n8n автоматически вызывает `setWebhook` на n8n.cloud URL
- **Не только deactivate/activate:** чистый PUT без смены статуса тоже вызывает перерегистрацию
- **Инцидент 2026-04-22:** webhook потерян 5 раз (4 от deactivate/activate + 1 от чистого PUT без reactivate)
- **WebhookHealthCron:** мониторит каждую минуту, но НЕ делает auto-flip-back (предотвращает flapping)
- **Восстановление:** ручная команда `setWebhook` с self-signed cert — занимает ~1 минуту

## Детальное описание

### Механизм срабатывания

Telegram Trigger нода в 01_Dispatcher имеет `active=true` статус. n8n Cloud при **каждом PUT** к workflow с активным Telegram Trigger автоматически вызывает `setWebhook` — перерегистрирует webhook на свой собственный URL (`https://vlad1.app.n8n.cloud/...`). В результате:

1. Python proxy больше не получает апдейты от Telegram
2. n8n получает их напрямую, но без 4 удалённых нод (Phase 2 cleanup) — typing indicator не отправляется вообще
3. Пользователи видят бота без индикатора загрузки или вообще без ответов

### Хронология инцидента 2026-04-22

| Потеря | Причина |
|--------|---------|
| 1 | deactivate 01_Dispatcher перед правкой |
| 2 | activate 01_Dispatcher после правки (migration 116) |
| 3 | deactivate перед следующей правкой |
| 4 | activate после правки (migration 117) |
| 5 | чистый PUT без deactivate/activate (ни одного toggle статуса) |

### Команда восстановления

```bash
scp root@89.167.86.20:/etc/ssl/noms/noms-webhook.pem /tmp/
curl -F "url=https://89.167.86.20:8443/telegram/webhook" \
     -F "certificate=@/tmp/noms-webhook.pem" \
     -F "allowed_updates=[\"message\",\"callback_query\",\"pre_checkout_query\"]" \
     "https://api.telegram.org/bot<TOKEN>/setWebhook"

# Проверка:
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo" | jq '.result.url'
# Должно быть: "https://89.167.86.20:8443/telegram/webhook"
```

### Обязательный протокол при PUT к 01_Dispatcher

1. **До PUT:** запомнить что нужно восстановить webhook после
2. **После любого PUT (включая чистый без смены active статуса):** немедленно выполнить команду восстановления выше
3. **Проверить:** `getWebhookInfo` → url должен быть `89.167.86.20:8443/...`

### WebhookHealthCron — почему нет auto-flip-back

```python
class WebhookHealthCron(BaseCron):
    fail_count = 0

    async def run(self):
        ok = await self._check_health()
        if not ok:
            self.fail_count += 1
            if self.fail_count >= 3:
                await self._fallback_to_n8n()  # переключает на n8n, не на python!
                await self._alert_admin()
                self.fail_count = 0
```

HealthCron при 3 фейлах переключает на n8n URL как fallback — это полуавтоматическая защита от падения Python proxy. Auto-flip-back на Python proxy НЕ реализован намеренно: если Python упал и HealthCron переключил на n8n, автоматический возврат создал бы петлю флаппинга. Возврат на Python — только ручной.

**Важно:** HealthCron проверяет `/telegram/health` (Python FastAPI endpoint), а не webhook registration. Если Python жив но webhook на n8n — HealthCron не среагирует. Это gap в мониторинге.

## Долгосрочные решения (Session 11+)

### Вариант A: Изолировать Telegram Trigger в отдельный workflow

Вынести Telegram Trigger в маленький stub-workflow (`00_TelegramReceiver`) который только принимает апдейты и перебрасывает в 01_Dispatcher через executeWorkflow. Тогда PUT к 01_Dispatcher не трогает workflow с Telegram Trigger → `setWebhook` не вызывается.

```
[00_TelegramReceiver: Telegram Trigger → Execute 01_Dispatcher]
[01_Dispatcher: Webhook Trigger → Route Classifier → ...]
```

**Преимущество:** полное устранение проблемы. Любые PUT к 01_Dispatcher безопасны.

### Вариант B: Улучшить Python proxy для приёма raw JSON

Доработать `webhook_server.py` для приёма сырого JSON от Telegram (без Telegram Trigger ноды). Python переупаковывает raw Telegram update так, чтобы он точно совпадал с форматом, который раньше генерировал Telegram Trigger в n8n. n8n начинает слушать через обычный Webhook Trigger вместо Telegram Trigger.

```python
# webhook_server.py: принять raw Telegram update
# → преобразовать в n8n-совместимый формат
# → форвардить на n8n Webhook Trigger URL
```

**Преимущество:** Python полностью контролирует webhook, n8n не может перехватить. Telegram Trigger в n8n больше не нужен.

### Рекомендация

Вариант B предпочтительнее — он убирает зависимость от n8n Cloud поведения при регистрации webhooks и даёт Python полный контроль над входящим потоком.

## Связь с Python Proxy

Эта проблема возникла из-за архитектурного решения перенести webhook на Python (2026-04-21). До этого webhook был на n8n и любой PUT был безвреден — n8n просто перерегистрировал на себя. После переноса на Python каждый PUT к 01_Dispatcher вытесняет Python proxy.

Подробности о Python proxy: [[concepts/telegram-proxy-indicator]].

## Related Concepts

- [[concepts/telegram-proxy-indicator]] — Python FastAPI proxy архитектура, SSL setup, WebhookHealthCron
- [[concepts/n8n-multi-agent-workflow-editing]] — protocol: GET перед PUT, проверка updatedAt после PUT
- [[concepts/dispatcher-callback-pipeline]] — 01_Dispatcher внутренняя архитектура

## Session 11 Addendum (2026-04-23)

**n8n.cloud downtime incident (19:01 MSK):** n8n.cloud briefly unavailable → Telegram Trigger auto-reregistered webhook to n8n.cloud URL during the outage. This is a new failure mode: the platform itself triggers re-registration without any PUT from agents.

**Webhook lost 3 times during Session 11** — once per Dispatcher PUT:
1. After stats_main routing patch PUT
2. After translation keys mapping PUT
3. After final wiring PUT

Each time: manual `setWebhook` restore required (~1 minute downtime per incident).

**Long-term fix status:** Python Telegram Adapter (Variant B) **approved** during Session 11, **applied Phases 1-5 in Session 12**. See [[concepts/python-telegram-adapter]].

## Session 12 — Python Telegram Middleware Applied (2026-04-23)

**Status: ROOT CAUSE ELIMINATED** for PUT-triggered displacement. Telegram Trigger node disabled; all traffic enters via `Webhook from Python` node.

### What happened

Python Adapter (Variant B) implemented in Session 12:
- New node `Webhook from Python` (`n8n-nodes-base.webhook`, path=`telegram-updates`) added to 01_Dispatcher
- New node `Validate Secret` (Code node) checks `X-Noms-Secret` header, normalizes payload shape
- **80 downstream `$('Telegram Trigger')` references** migrated to `$('Validate Secret')` across 14 nodes
- `telegram_proxy.py` now sends `X-Noms-Secret` header on every forward
- `N8N_WEBHOOK_URL` updated to webhook path, `N8N_WEBHOOK_SECRET` (64 hex) added to `.env`
- Telegram Trigger node **disabled** (`disabled=true`) as rollback safety net

### Async T+8s drift — new failure mode discovered

During Session 12 Phase 2 PUT, a new failure mode was observed:

```
T+0s  PUT Dispatcher (add Webhook node + refs)
T+0s  Agent restores setWebhook manually
T+8s  n8n.cloud async post-save webhook sync → OVERWRITES with n8n.cloud URL
T+8s  WebhookHealthCron detects drift → alert
```

n8n.cloud performs an **asynchronous webhook re-sync ~8 seconds after any PUT** to a workflow that still has an active Telegram Trigger. This is separate from the immediate PUT response.

**Rule:** After any PUT to 01_Dispatcher while Telegram Trigger is present/active, verify webhook at **T+5s AND T+15s**, not just immediately after PUT.

### Webhook drift log for Session 12

| # | Cause | Expected? |
|---|-------|-----------|
| 1 | First PUT (add nodes + partial refs) | Yes — Telegram Trigger still active |
| 2 | deactivate/activate (register Webhook endpoint in n8n Cloud) | Yes |
| 3 | Second PUT (deep-replace refs) + **async T+8s sync** | Yes (new mode: async) |
| 4 | `disabled=true` PUT → n8n calls `deleteWebhook` | Yes — graceful, webhook URL cleared not overwritten |

After Phase 5.5 (Trigger disabled) → no-op PUT at T+60s → **webhook remained on `89.167.86.20:8443` at T+10s and T+25s**. Root cause confirmed resolved.

### Current state (post Session 12)

- `01_Dispatcher`: 55 nodes (Telegram Trigger node present but `disabled=true`)
- All traffic: `Telegram → Python proxy → Webhook from Python → Validate Secret → Route Classifier`
- No more auto-`setWebhook` on PUT (Telegram Trigger disabled)
- Phase 6 pending: remove Telegram Trigger node entirely (safe after 48h stability period)

## Sessions 13-14 — First Production PUT Without Webhook Drift (2026-04-24)

**Validation confirmed:** Dispatcher Route Classifier v1.12 PUT during Progress Hub headless migration (Sessions 13-14) completed without any webhook drift. Telegram Trigger `disabled=true` (Session 12) fully prevents `setWebhook` on PUT.

This is the first Dispatcher PUT since the Python Middleware fix that touched the live workflow without incident. Session 12 root cause elimination is confirmed in production.

**PUT scope:** Added `cmd_quests`, `cmd_league`, `cmd_friends_info`, `cmd_shop` to `PROFILE_V5_CALLBACKS` + reply-text detection for `icon_progress`. No webhook restoration needed post-PUT.

## Sources

- [[daily/2026-04-22.md]] — Discovery и incident log: webhook потерян 5 раз за одну сессию (4 deactivate/activate + 1 чистый PUT); команда восстановления; долгосрочные решения A и B
- [[daily/2026-04-23.md]] — Session 11: n8n.cloud downtime incident + webhook lost 3× (once per Dispatcher PUT during stats headless migration); Python Adapter approved. Session 12: Phase 1-5 applied, async T+8s drift discovered, root cause eliminated
- [[daily/2026-04-24.md]] — Sessions 13-14: first prod PUT without drift confirms Session 12 fix
