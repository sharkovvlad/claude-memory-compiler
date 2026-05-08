# n8n Self-Host: Миграция с Cloud на собственный VPS

**Когда применимо:** уход с n8n Cloud на self-hosted Community Edition в Docker. Цель — убрать cold-start (n8n.cloud worker засыпает после ~30 сек простоя, тратит 1.3-1.5 сек на пробуждение), сэкономить подписку, перевести инфру под свой контроль.

**Источник:** Шаг 0 миграции NOMS, выполнен 26-27 апреля 2026 (`daily/2026-04-26.md`, `daily/2026-04-27.md`).

**Связанные:** [[concepts/noms-architecture]], [[concepts/n8n-data-flow-patterns]], [[concepts/n8n-subworkflow-contract]].

---

## Архитектура self-host (NOMS, Hetzner CX21)

```
/home/noms/                           ← user noms UID 1001, mode 750 (изоляция)
├── n8n/
│   ├── compose/
│   │   ├── docker-compose.yml        ← n8n CE official image
│   │   └── .env                      ← N8N_ENCRYPTION_KEY (стабильный!), N8N_OWNER_EMAIL, N8N_TARGET_API_KEY
│   ├── data/                         ← UID 1000 (n8n image internal node user)
│   │   └── database.sqlite           ← SQLite, не Postgres (см. рассуждения)
│   └── backups/
│       ├── backup.sh                 ← daily VACUUM INTO + gzip + 30-day retention
│       └── database_*.sqlite.gz
└── (future python/ — когда уйдём с n8n совсем)

/etc/systemd/system/noms-n8n.service  ← Type=oneshot RemainAfterExit=yes, ExecStart=docker compose up -d
```

**Почему отдельный user, не taskbot:** на VPS живёт другой проект `tasktracker-bot` под `taskbot` UID 1000. Изоляция через `usermod -l noms n8n` (UID 1001), mode 750 на parent dir. Файлы в `/home/noms/n8n/data` принадлежат UID 1000 (требование n8n image), но taskbot не имеет +x на `/home/noms` → не доступен.

**Почему SQLite, не Supabase Postgres:** n8n internal data (workflow definitions, executions, credentials) — не бизнес-данные. SQLite читает workflow в ~0.5 мс, Postgres в EU — 30-90 мс на каждое чтение. Влияние на user latency: 0 vs +50-300 мс на каждый клик. Backup: `cp database.sqlite` в S3, retention 30 дней. Disaster recovery: re-import workflows из JSON.

## docker-compose.yml ключевые параметры

```yaml
services:
  n8n:
    image: docker.n8n.io/n8nio/n8n:latest    # 2.x latest, Sept 2025+
    container_name: noms-n8n
    restart: unless-stopped
    # NO `user:` override — n8n image expects UID 1000 internal
    ports: ["127.0.0.1:5678:5678"]            # ТОЛЬКО localhost, UI через SSH-туннель
    environment:
      - N8N_HOST=localhost
      - N8N_PORT=5678
      - WEBHOOK_URL=http://localhost:5678/
      - N8N_ENCRYPTION_KEY=${N8N_ENCRYPTION_KEY}   # КРИТИЧНО: стабильный, иначе credentials становятся unreadable
      - DB_TYPE=sqlite                              # default; не указывать DB_SQLITE_DATABASE — n8n сам выберет ~/.n8n/database.sqlite
      - GENERIC_TIMEZONE=Europe/Madrid
      - TZ=Europe/Madrid
      - EXECUTIONS_DATA_PRUNE=true
      - EXECUTIONS_DATA_MAX_AGE=168                 # 7 days
      - N8N_DIAGNOSTICS_ENABLED=false
      # NO N8N_BASIC_AUTH_* (deprecated в 1.0+, заменены built-in user management)
      # NO N8N_RUNNERS_ENABLED (deprecated в 2.x — runners enabled by default)
      # NO N8N_USER_FOLDER override (двойное nesting → EACCES)
    volumes:
      - /home/noms/n8n/data:/home/node/.n8n
    deploy:
      resources:
        limits: {memory: 1500M}                     # n8n CE eats ~250-400 MB при 15 wf
```

**Подвох с правами:** при `chown -R UID_OTHER:UID_OTHER /home/noms/n8n/data` контейнер падает с `EACCES: mkdir '/home/node/.n8n/.n8n'`. Потому что n8n image внутри запускается под UID 1000 (node user), и `/home/node` mode 700. Override `user: "X:Y"` не помогает (UID 1000 структуры в image нет для других UIDs). **Правильно:** `chown -R 1000:1000 /home/noms/n8n/data`. Изоляция от других пользователей хоста — через mode 750 на parent `/home/noms`.

## Owner setup без UI

n8n CE 1.x+ убрал `N8N_BASIC_AUTH_*` в пользу built-in user management. При первом visit показывает `/setup`. Но это можно автоматизировать через REST:

```bash
# 1. POST /rest/owner/setup → создаёт owner, возвращает session cookie
curl -i -X POST http://127.0.0.1:5678/rest/owner/setup \
  -H 'Content-Type: application/json' \
  -d '{"email":"...","firstName":"...","lastName":"...","password":"..."}'
# Set-Cookie: n8n-auth=eyJ...; Path=/; HttpOnly

# 2. POST /rest/api-keys (с cookie) → возвращает rawApiKey (показывается только при создании!)
curl -X POST http://127.0.0.1:5678/rest/api-keys \
  -H "Cookie: n8n-auth=$COOKIE" \
  -H 'Content-Type: application/json' \
  -d '{"label":"name","scopes":["workflow:create",...]}'
```

**⚠️ Scope для API key — критично:**
- `workflow:create/read/update/delete/list/move` — для импорта
- `credential:create/delete/list` — для credentials
- **НЕ хватает `workflow:execute`** для активации через `POST /api/v1/workflows/{id}/activate` → 403. Решение: использовать internal `/rest/workflows/{id}/activate` через session cookie (full owner permissions).

**rawApiKey засветится в вашем transcript при создании.** Если работа идёт через AI-агента — DELETE через `/rest/api-keys/{id}` сразу после, создать новый ключ и tee'нуть напрямую в `.env` (минуя AI канал).

## Public REST API vs Internal REST API

| Endpoint | Auth | Use case | Pitfall |
|---|---|---|---|
| `/api/v1/workflows` (POST/GET/DELETE) | `X-N8N-API-KEY` header | Программный импорт | PUT отвергает `active` ("read-only") |
| `/api/v1/workflows/{id}/activate` (POST) | `X-N8N-API-KEY` | Activation | 403 если scope не покрывает (требует `workflow:execute`) |
| `/api/v1/credentials` (POST) | `X-N8N-API-KEY` | Создать credential | Schema validation — см. подвохи ниже |
| `/api/v1/credentials/schema/{type}` (GET) | `X-N8N-API-KEY` | Узнать что в `data` | Полезно для отладки 400 на создании |
| `/rest/login` (POST) | — | Получить session cookie | Body: `emailOrLdapLoginId` (не `email`!) |
| `/rest/workflows/{id}/activate` (POST) | `Cookie: n8n-auth=...` | Activation с full permissions | Body: `{versionId: "<current>"}` обязателен (optimistic concurrency) |
| `/rest/owner/setup` (POST) | — | Первичный owner | Возвращает auth cookie |

**Public API не возвращает `rawApiKey` после создания** (только masked `***f5AE`). Backup — сохранить значение из POST response. Если потерял — DELETE и создай заново.

## Schema validation подвохи credentials

При POST `/api/v1/credentials` с типом `postgres` и `openAiApi` schema requires разных полей условно:

**postgres:** schema content `if allowUnauthorizedCerts==false then required: ssl`. Без явного `sshTunnel: false` schema трактует sshAuthenticateWith как обязательный → 400.

**openAiApi:** schema `if header==true then required: headerName, headerValue. else not headerName, not headerValue`. Без явного `header: false` schema fails требованием headerName.

**Правило:** перед массовым POST credentials — `GET /api/v1/credentials/schema/{type}` и проверить `allOf.if/then/else` блоки. Дать explicit `false` для всех опциональных бинарных полей.

**postgres + Supabase pooler (HOT bug, 2026-04-28):** `allowUnauthorizedCerts` ОБЯЗАН быть `True`. Иначе credential POST успешен, но runtime каждый postgres-узел падает с `NodeOperationError: self-signed certificate in certificate chain` — Supabase pooler chain не в default CA bundle Node.js контейнера. Каскад: `06_Indicator_Clear` (Postgres node вызывает `clear_bot_message` RPC) → fail → indicator-стикер не удаляется → cascade error в parent workflows (Dispatcher, Menu_v3, AI_Engine), потому что executeWorkflow ждёт ответа. Пользователь видит «бот работает но медленно, стикер не пропадает». Симптомы маскируют первопричину — на 39 execs было 3 разных error fingerprints (postgres cert, NodeApiError, PostgREST filter), но root cause один. **Fix:** PATCH credential через `/rest/credentials/{id}` (full body с `data.allowUnauthorizedCerts: true`). Хот-релоад без рестарта контейнера, ~30 сек до полного применения. Скрипт `scripts/n8n_migrate.py` обновлён (default `True`).

## Migration script (паттерн)

`scripts/n8n_migrate.py` — двухфазный CLI:

1. **import phase:**
   - Создать 4 credentials (POST `/api/v1/credentials`, fields из `.env`)
   - Импорт workflow JSON: для каждого — replace `nodes[*].credentials[*].id` (cloud → new), POST `/api/v1/workflows`
   - Сохранить mapping `{cloud_id → new_id}` в state file
2. **relink phase:**
   - Walk все импортированные wf на target
   - В `executeWorkflow` нодах replace `parameters.workflowId` (string ИЛИ resourceLocator object с `value`)
   - PUT обратно
   - Также обновить `cachedResultUrl` для UI consistency

**Settings whitelist при PUT** (правило 13 из `CLAUDE.md`): `{executionOrder, saveManualExecutions, callerPolicy, executionTimeout, timezone, saveExecutionProgress, saveDataSuccessExecution, saveDataErrorExecution, errorWorkflow}`. Прочие top-level — отбрасывать.

## Активация и draft/published quirk (n8n 2.x)

**n8n 2.x ввёл concept draft/published.** `active=true` в DB не достаточно — webhooks регистрируются только для **published** воркфлоу. Зависимости в `workflow_entity`:
- `activeVersionId` (NULL у draft, = `versionId` у published)
- Запись в `workflow_published_version (workflowId, publishedVersionId)`
- Snapshot в `workflow_history (versionId, workflowId, nodes, connections, ...)` для current versionId

**Publish-time validation в 2.x:** при `POST /rest/workflows/{id}/activate` проверяется что **все referenced sub-workflows в `executeWorkflow` нодах уже published**. Если есть **circular reference** (NOMS архитектура: 02_Onboarding ↔ 02.1_Location, 04_Menu → 02_Onboarding и т.д.) → ни один из узлов цикла не может стать первым published через REST. На cloud (старая версия) этой проверки нет.

**Что НЕ работает:**
- `PUT /api/v1/workflows/{id}` с body `{active: true}` → 400 "active is read-only"
- env vars типа `N8N_*VALIDATION*` — нет
- 2 passes activation (sub-first, parent-second) — циклы не разрываются
- UPDATE `workflow_entity SET active=1` без published mapping → boot log `0 published workflows`, webhooks не registered

**Симметричное правило для DEACTIVATION** (подтверждено 29.04 при отключении legacy 08.1-08.4):
для гарантированной остановки workflow одного `active=0` НЕ достаточно — n8n при boot регистрирует workflows где `activeVersionId IS NOT NULL`. Нужно одновременно:

```sql
UPDATE workflow_entity 
SET active = 0,
    activeVersionId = NULL    -- критично, иначе webhook продолжает регистрироваться
WHERE id IN ('<wf1>', '<wf2>', ...);
```
+ `systemctl restart noms-n8n`. После рестарта в boot log виден `Activated X workflows` где X не включает деактивированные. **Откат:** restore `activeVersionId` из `workflow_history` (latest по `createdAt`).

**Что сработало (SQL workaround):**

```sql
-- Для каждого draft с circular ref:
INSERT OR IGNORE INTO workflow_history (versionId, workflowId, authors, nodes, connections, name, autosaved, description)
  SELECT versionId, id, '', nodes, connections, name, 0, COALESCE(description, '')
  FROM workflow_entity WHERE id=:wf_id;
INSERT OR REPLACE INTO workflow_published_version (workflowId, publishedVersionId)
  SELECT id, versionId FROM workflow_entity WHERE id=:wf_id;
UPDATE workflow_entity SET activeVersionId=versionId WHERE id=:wf_id;
```

После SQL + `systemctl restart noms-n8n` → boot log `X published workflows` → webhooks registered → POST `/webhook/<path>` возвращает 200.

⚠️ Это разовый хак для миграции. Bypass'ит publish-time validation полностью, поэтому **выполнять только если confident что workflow JSON валидный** (мы уверены — это импорт из работающего cloud). После полной миграции в Python (Phase 1-7 plan) n8n уйдёт.

**Backup перед хаком обязателен:** `cp /home/noms/n8n/data/database.sqlite{,.pre-publish.$(date -u +%Y%m%d_%H%M%S)}`.

## Big-bang switch checklist

1. **Pre-flight:**
   - Self-hosted: 15 wf импортированы, релинкованы, healthz=200
   - В импортированном Dispatcher: webhook node `path` совпадает с тем, что Python forward'ит
   - `Validate Secret` нода в Dispatcher — hardcoded EXPECTED совпадает (импорт 1-к-1 из cloud)
   - Telegram `getWebhookInfo`: pending_update_count=0 (nothing in flight)
2. **Backup:** `cp /home/taskbot/noms/.env{,.bak.bigbang.$(date -u +%Y%m%d_%H%M%S)}`
3. **Activate:** все wf на self-hosted → published (через REST + SQL хак для circular)
4. **Switch:** `sed -i 's|^N8N_WEBHOOK_URL=.*|N8N_WEBHOOK_URL=http://localhost:5678/webhook/<path>|' /home/taskbot/noms/.env`
5. **Restart:** `systemctl restart noms-webhooks` (~30 сек атомарно)
6. **Smoke test:** `curl /telegram/health` + `journalctl -u noms-webhooks --since "1 min ago" | grep forward_to_n8n` → должны быть POSTs на localhost:5678 с HTTP 200
7. **Live test:** пользователь делает 3-5 кликов — отвечает ли бот
8. **Откат-план:** `sed -i` URL обратно на cloud + restart. ~30 сек. Cloud остаётся active, готов принять.

## Latency benchmark (NOMS)

| Метрика | n8n Cloud | Self-hosted (localhost) | Reduction |
|---|---|---|---|
| `forward_to_n8n elapsed_ms` p50 | ~370 ms | ~60 ms | 6x |
| `forward_to_n8n elapsed_ms` p95 | ~700 ms | ~150 ms | 4-5x |
| Cold-start первого клика после простоя | +1.3-1.5 сек | 0 (worker не засыпает) | ~10x |

**Источник:** `journalctl -u noms-webhooks --since "..." | grep "TIMING forward_to_n8n"`.

## Известные техдолги после self-host

1. ~~**noms-webhooks пингует `https://vlad1.app.n8n.cloud/` каждую минуту** — health probe в Python proxy. Не блокирует, убрать в Phase 1 миграции.~~
   **✅ Closed 2026-04-29:** убран хардкод полностью. `telegram_proxy.check_n8n_reachable()` теперь читает env `N8N_HEALTH_URL` (default `http://127.0.0.1:5678/healthz`) — без хардкоженных URL. Покрыто 6 unit-тестами в `tests/test_telegram_proxy_health.py` (200/503/4xx/ConnectError/env-override/default). Контекст: 2026-04-27 hot-fix временно подставил localhost; формализовали через env-переменную перед окончательной отменой n8n cloud (~30.04.2026). **Урок предыдущего инцидента (2026-04-27) сохраняется:** через 18 минут после big-bang switch'а cloud worker уснул, GET на cloud начал давать 5xx → `/telegram/health` каскадно вернул 503 → cron `webhook_health.py` после 3 fail'ов автоматически переключил Telegram webhook обратно на N8N_WEBHOOK_URL (cron не подхватил новый env после `sed -i`). При любом `sed` на VPS `.env` — `systemctl restart noms-webhooks noms-cron` (оба, не один).
2. **MCP webhooks** активированы во всех 14 воркфлоу (UUID-paths) — не вызываются извне (порт 5678 на localhost), безопасно.
3. **Activation API в n8n 2.x требует `workflow:execute` scope** — issue для будущих агентов: создавать ключи с этим scope изначально.
4. **Hardcoded TELEGRAM_BOT_TOKEN в 11+ HTTP nodes** — техдолг из `CLAUDE.md`, не лечит миграция, лечит Phase 7 (AI Engine → Python).
5. ~~**Memory leak в Node.js heap n8n 2.17.7**~~ **DEFENDED 2026-04-28 22:00 MSK:** за 22ч контейнер вырос с 250 MB → 2.7 GB anon-rss → OOM kill. БД при этом 17 MB / 86 executions — leak НЕ в SQLite. Применена защита: host swap 2 GB + `vm.swappiness=10` + n8n env `EXECUTIONS_DATA_MAX_AGE=48`, `PRUNE_MAX_COUNT=5000`, `PRUNE_HARD_DELETE_BUFFER=24` + `NODE_OPTIONS=--max-old-space-size=1024` (heap cap). **`memswap_limit` оставлен равным `mem_limit=1500m`** — fail-fast, не разрешаем контейнеру уходить в host swap (избегаем зомби-бота с latency 15с). Root cause leak не найден — следующий шаг расследовать **81% error rate в 01_Dispatcher / 04_Menu_v3** (70/86 за сутки), вероятно retry feedback-loop держит state в heap. См. `daily/2026-04-28.md` сессия 7.

## Уроки (2026-04-27 → 2026-04-28)

- **`deploy.resources.limits.memory: 1500M` в Compose v3 spec НЕ enforce'ится в standalone Docker** — только в Swarm mode. Молча игнорируется, контейнер растёт без ограничения. **Используй `mem_limit: 1500m` и `memswap_limit: 1500m`** на верхнем уровне сервиса (Compose v2/v3 совместимый синтаксис). Проверять enforcement: `docker stats <container>` показывает `MemUsage / LIMIT` — limit должен быть = `mem_limit`, а не host RAM.
- **Прескриптивные prune-настройки помогают будущему, не текущему утечке.** Если БД tiny (десятки записей) — `MAX_AGE` / `PRUNE_MAX_COUNT` бесполезны для текущего incident'а; их роль — защита от будущего lateral роста execution_data, когда нагрузка вырастет. Реальная защита от heap-leak'а — `NODE_OPTIONS=--max-old-space-size=N` (явный потолок).
- **Host swap ≠ container swap.** Swap'ить контейнер — anti-pattern для realtime сервиса (Telegram bot): swap I/O даст 200-1500 ms latency на каждый callback. Host swap полезен для kernel'а и других процессов (sshd, systemd) во время memory pressure, но контейнер должен fail быстро (`memswap_limit=mem_limit`).

## Daily backup стратегия

```bash
# /home/noms/n8n/backups/backup.sh — под user noms, cron 15 3 * * *
TS=$(date -u +%Y%m%d_%H%M)
sqlite3 /home/noms/n8n/data/database.sqlite "VACUUM INTO '/home/noms/n8n/backups/database_${TS}.sqlite'"
gzip -9 "/home/noms/n8n/backups/database_${TS}.sqlite"
find /home/noms/n8n/backups -name "database_*.sqlite.gz" -mtime +30 -delete
```

`VACUUM INTO` даёт consistent online snapshot (не corrupt даже если n8n пишет в момент бэкапа). gzip ~440KB / 1MB raw для 15 wf без executions history.

## Ссылки

- План миграции (исходный): `/Users/vladislav/.claude/plans/groovy-marinating-eclipse.md`
- Скрипт миграции: `scripts/n8n_migrate.py`
- Backup script: `scripts/n8n_backup.py` (daily cron из cloud — продолжает работать до отмены подписки)
- Daily logs: `claude-memory-compiler/daily/2026-04-26.md` (setup), `2026-04-27.md` (миграция + big-bang)
