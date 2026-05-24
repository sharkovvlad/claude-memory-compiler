---
title: "NOMS Access Credentials + Agent Tools Recipe"
aliases: [credentials, api-keys, agent-tools, psycopg2-recipe, nlm-recipe, tool-decision-matrix]
tags: [reference, infrastructure, agent-onboarding, tools]
sources:
  - "daily/2026-04-08.md"
  - "daily/2026-05-05.md"
  - "agent confusion 2026-05-12 (psycopg2 blocked / NLM cookie expired)"
created: 2026-04-08
updated: 2026-05-12
---

# NOMS Access Credentials + Agent Tools Recipe

API keys, access points, и **canonical recipes** для агентов: psycopg2 для live БД, NLM для RAG, SSH для n8n.

## Key Points

- **Supabase REST API:** `https://pymmeubsoeuglivywhhv.supabase.co/rest/v1/` with `apikey` + `Authorization: Bearer <service_role>`
- **Supabase DB (psycopg2):** `DATABASE_URL` в `.env` через Supabase pooler (`aws-1-eu-west-1.pooler.supabase.com:5432`). Default метод для миграций.
- **n8n self-hosted API:** `http://127.0.0.1:5678/api/v1/` на VPS, доступ через SSH: `ssh root@89.167.86.20 'curl -H "X-N8N-API-KEY: $KEY" http://127.0.0.1:5678/...'`. Ключ `N8N_TARGET_API_KEY` в `/home/noms/n8n/compose/.env` (mode 600). UI — SSH-туннель `ssh -L 5678:127.0.0.1:5678 root@89.167.86.20`.
- **n8n Cloud (DEPRECATED 2026-04-30):** `https://vlad1.app.n8n.cloud` отменён. Если потребуется восстановить — поднять `N8N_BASE_URL` в `.env` нужного host.
- DB host DNS doesn't resolve from Mac → REST API или SSH tunnel.
- All credentials stored in `/Users/vladislav/Documents/NOMS/.env`.
- **Миграции:** psycopg2 через `DATABASE_URL` (default). Альтернатива: n8n temp workflow с credential `Postgres_pooler_6543` (ID `JW48yu2pfTUSntRn` self-hosted).
- **NLM re-login** (когда cookie истёк — обычно раз в 1-2 недели; см. Recipe 2 ниже для двухступенчатой проверки):
  ```bash
  source /Users/vladislav/Documents/NotebookLM+Claude/plugins/notebooklm-rag/.venv/bin/activate && notebooklm login
  ```
  Юзер выполняет руками (Google OAuth требует human), агент сам залогиниться не может.

## Agent Tools Decision Matrix

| Need | Tool | Latency | Trust level |
|---|---|---|---|
| Точная SQL схема / live state / `pg_get_functiondef` / `pg_proc` body / column defaults | **psycopg2** (live) | ~50ms | **canonical (live)** |
| n8n workflow JSON, executions status, выполняющиеся ноды | **`ssh + curl n8n API`** | ~200ms | **canonical (live)** |
| VPS logs (Python webhook, cron) | **`ssh ... journalctl`** | ~100ms | **canonical (live)** |
| Архитектурные паттерны, история, gotcha'ы (cross-cutting) | **NLM ask** (RAG snapshot) | ~3-5s | snapshot ≤24h old |
| Прямой grep по KB | `grep -r claude-memory-compiler/knowledge/` | мгновенно | canonical |
| Python код NOMS (handlers, dispatcher, services) | **Read/Grep** (Claude tools) | мгновенно | canonical (current branch) |
| Чужой код агентов (параллельные ветки) | `git ls-remote origin 'refs/heads/*'` + `git show` | ~100ms | canonical |

**Правило приоритета:** при противоречии **live wins**. NLM snapshot может быть до суток stale. Для функций которые редактировали сегодня — обязательно `pg_get_functiondef` LIVE, не NLM.

## Recipe 1 — psycopg2 read-only (live SQL inspection)

**Canonical паттерн:**

```bash
cd /Users/vladislav/Documents/NOMS && python3 << 'EOF'
import psycopg2, os
from dotenv import load_dotenv
load_dotenv('.env')
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

# Examples:
cur.execute("SELECT pg_get_functiondef(oid) FROM pg_proc WHERE proname = 'process_onboarding_input'")
print(cur.fetchone()[0][:500])

cur.execute("""SELECT column_name, data_type, is_nullable, column_default
                 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='users'
                ORDER BY ordinal_position""")
for row in cur.fetchall(): print(row)
EOF
```

**Permissions:** `~/.claude/settings.json` имеет `permissions.defaultMode: "bypassPermissions"` — read-only psycopg2 не требует prompt'а. Если всё равно блокирует — проверь не в plan mode ли ты (там только Read/Grep/WebFetch разрешены).

**Safety:**
- `SELECT` / `pg_get_functiondef` / `information_schema.*` — **safe**, никаких approvals не нужно.
- `UPDATE` / `INSERT` / `DELETE` / `CREATE OR REPLACE FUNCTION` — **миграция**, требует stale-base правил (см. [[concepts/safe-create-or-replace-recipe]]) + явного approval тимлида.
- Test reset live юзеров — см. [[concepts/test-user-reset-recipe]]; для прода — **только через RPC** `reset_to_onboarding`.

**p95 benchmark recipe:** минимум 10 прогонов, persistent psycopg2 connection (один `.connect()` ПЕРЕД циклом), с VPS не с Mac (иначе RTT 400ms искажает цифру).

## Recipe 2 — NLM RAG (архитектурные вопросы)

**Notebook:** `NOMS Supabase Data` (id `fa75f4de-96c2-4dc0-bc9d-0bf07bd992f5`) — 3 слоя: таблицы Supabase + n8n workflows MD + Python код.

### Активация venv (обязательно!)

CLI установлен в venv плагина:
```bash
source /Users/vladislav/Documents/NotebookLM+Claude/plugins/notebooklm-rag/.venv/bin/activate
```
Без активации команда `notebooklm` → `command not found`.

### Сессия живая? (двухступенчатая проверка)

`notebooklm auth check` проверяет только **наличие** cookie-файла, не его validity. Делай **обе** проверки:

```bash
# 1. cookie file exists?
notebooklm auth check --json

# 2. LIVE validation — реальный API-запрос
notebooklm source list -n fa75f4de-96c2-4dc0-bc9d-0bf07bd992f5 --json
```

Если LIVE-ответ содержит `"Authentication expired or invalid. Redirected to: accounts.google.com/..."` — Google cookie истёк (обычно 1-2 недели TTL), нужен re-login.

### Re-login (юзер делает руками)

```bash
source /Users/vladislav/Documents/NotebookLM+Claude/plugins/notebooklm-rag/.venv/bin/activate && notebooklm login
```
Откроется браузер для Google OAuth. После логина:
```bash
stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" ~/.notebooklm/storage_state.json
# Дата должна быть сегодня.
```

**Агент сам логиниться НЕ может** (Google OAuth требует human). Если cookie истёк — просить юзера.

### Канонический ask

```bash
source /Users/vladislav/Documents/NotebookLM+Claude/plugins/notebooklm-rag/.venv/bin/activate
notebooklm ask "Точный конкретный вопрос про NOMS" \
  -n fa75f4de-96c2-4dc0-bc9d-0bf07bd992f5 --json
```

Без `--conversation-id <id>` = новая нить. С — follow-up.

**Когда НЕ использовать NLM:**
- Хочешь схему БД / pg_proc body / column default — **live psycopg2** даст canonical.
- Хочешь видеть **сегодня изменённый** код / migrations / functions — NLM может быть stale (sync ежедневно).
- Нужен binary fact (string match) — `grep -r claude-memory-compiler/knowledge/` точнее.

**Когда NLM — лучший выбор:**
- Cross-cutting архитектурные вопросы («как Channel A связана с One Menu UX»).
- Историческое расследование («когда был mig 161 и зачем»).
- «Назови RPC которые манипулируют XP» — NLM агрегирует по всем источникам.
- Перед началом большой миграции — read-back проверка.

## Recipe 3 — SSH + n8n API

**Connection:** `ssh root@89.167.86.20` (key auth, no password).

**n8n API одной командой:**
```bash
ssh root@89.167.86.20 'KEY=$(grep N8N_TARGET_API_KEY /home/noms/n8n/compose/.env | cut -d= -f2)
  curl -s -H "X-N8N-API-KEY: $KEY" http://127.0.0.1:5678/api/v1/workflows/<workflow_id>'
```

**n8n executions (история запусков workflow):** API endpoint `/executions` отдаёт **403 Forbidden** на community edition. Workaround — прямой SQLite на хосте:
```bash
ssh root@89.167.86.20 'sqlite3 /home/noms/n8n/data/database.sqlite \
  "SELECT id, status, mode, startedAt, stoppedAt FROM execution_entity \
     WHERE workflowId=\"7EqiiwUwlGs7dcHT\" ORDER BY startedAt DESC LIMIT 5"'
```

**n8n container logs:** `ssh root@89.167.86.20 "docker logs noms-n8n --since '10m' 2>&1 | tail -50"`.

**Большие PUT (>50KB):** scp файл → curl с `@file`. Inline shell escape ломается. Recipe — см. [[concepts/n8n-data-flow-patterns]] секция «Safe PUT».

**Python webhook logs:**
```bash
ssh root@89.167.86.20 "journalctl -u noms-webhooks --since '15min ago' --no-pager | grep 'tid=786301802'"
```

## Permission Modes (Claude Code)

Глобально в `~/.claude/settings.json`:
```json
"permissions": { "defaultMode": "bypassPermissions" }
```

Это обходит permission prompts для всех Bash/Edit/Write. Все агенты в этом окружении наследуют.

**Если коллега жалуется что блокирует** — проверь:
1. `cat ~/.claude/settings.json | grep defaultMode` → должно быть `"bypassPermissions"`.
2. Не в plan mode? (только Read/Grep/WebFetch разрешены).
3. CLI override flag? (`--permission-mode=ask` принудительно требует подтверждения).
4. Project-level `deny` rules в `/Users/vladislav/Documents/NOMS/.claude/settings.local.json`? (сейчас deny пустой).

## Related Concepts

- [[concepts/noms-architecture]]
- [[concepts/n8n-self-hosting]]
- [[concepts/release-protocol]]
- [[concepts/pre-migration-discovery-recipe]] — 10 psycopg2 queries которые делать перед каждой миграцией
- [[concepts/safe-create-or-replace-recipe]] — stale-base safe pattern для CREATE OR REPLACE FUNCTION
- [[concepts/n8n-data-flow-patterns]] — Safe PUT recipe для n8n workflows
- [[concepts/test-user-reset-recipe]] — test fixture для онбординг E2E
