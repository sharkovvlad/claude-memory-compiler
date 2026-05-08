# Pre-Migration Discovery Recipe — Phase 0 protocol

**Компилировано:** 2026-04-21 Session 10. Saved 5 critical bugs before they reached prod (adversarial finding rate в Phase 3 review).

## Зачем

Перед написанием миграции для NOMS (ui_screens / workflow_states / RPCs) — **всегда** пройти Phase 0: полный discovery текущего состояния DB + n8n + proxy. Экономит 2-3 часа отладки багов которые "казались тривиальными".

**Правило:** никогда не писать миграцию по specs без cross-check DB state. Specs mockups могут лгать (callback_data conventions), NLM snapshot может устареть (migrations 102-109 missed при Session 10 start), API keys env var names различаются.

## Phase 0 queries — полный список (execute via psycopg2 + DATABASE_URL from .env)

```python
import os, psycopg2
from dotenv import load_dotenv
load_dotenv('/Users/vladislav/Documents/NOMS/.env')
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
```

### 1. Existing ui_screens landscape

```sql
SELECT screen_id, render_strategy, input_type, save_rpc, back_screen_id_default, list_rpc
FROM ui_screens ORDER BY screen_id;
```

Проверь какие уже существуют — не дублируй. Проверь constraint CHECK:

```sql
SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
WHERE conrelid='ui_screens'::regclass;
```

Знай наизусть enums:
- `render_strategy` ∈ `{replace_existing, delete_and_send_new, send_new}` — НЕТ `multi-step`
- `input_type` ∈ `{inline_kb, reply_kb, text_input, dynamic_list, terminal, location, payment, photo_voice, sub_workflow}` — **НЕТ `list_rpc`** (это отдельная колонка)
- `screen_id` regex `^[a-z][a-z0-9_:]{1,62}$`

### 2. Existing ui_screen_buttons cmd_edit_*

```sql
SELECT screen_id, callback_data, meta
FROM ui_screen_buttons
WHERE callback_data LIKE 'cmd_edit_%'
ORDER BY screen_id;
```

**Критично:** check `meta` — если пустой `{}`, надо UPDATE `meta.target_screen` + `meta.set_status` (Session 10 Adversarial Finding #1: пустой meta → `process_user_input` re-render current screen → Telegram "message not modified").

Existing valid meta pattern:
```json
{"target_screen": "edit_X", "set_status": "edit_X"}
```

### 3. workflow_states schema + existing states

**Schema проверка (PK = state_code, НЕ status):**
```sql
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name='workflow_states' ORDER BY ordinal_position;
```

**Existing state_codes:**
```sql
SELECT state_code, screen_id, next_step_code, save_rpc
FROM workflow_states
WHERE state_code LIKE 'edit_%'
   OR state_code LIKE 'editing:%'
   OR state_code LIKE 'registration_step_%'
ORDER BY state_code;
```

**users_status_fkey existence** (влияет на INSERT strategy):
```sql
SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
WHERE conrelid='users'::regclass AND conname LIKE '%status%';
```

Если `users_status_fkey → workflow_states.state_code` существует — **новые state_codes должны быть INSERTed ДО любого UPDATE users.status**.

### 4. RPC landscape — какие setters существуют, сигнатуры + CASE branches

```sql
SELECT proname, pg_get_function_arguments(oid), pg_get_function_result(oid)
FROM pg_proc
WHERE proname LIKE 'set\_user\_%' OR proname LIKE 'get\_%business\_data' OR proname LIKE 'list\_%_for_%'
ORDER BY proname;
```

**ЗАТЕМ для КАЖДОГО setter** — `pg_get_functiondef` + grep CASE/WHEN:

```python
for fn in ['set_user_goal', 'set_user_activity', ...]:
    cur.execute("SELECT pg_get_functiondef(oid) FROM pg_proc WHERE proname=%s", (fn,))
    body = cur.fetchone()[0]
    for line in body.split('\n'):
        if 'WHEN ' in line and 'THEN' in line:
            print(f"  {fn}: {line.strip()}")
```

**Это ground truth для callback_data convention.** Specs mockups могут лгать — grep RPC body единственная правда.

Session 10 discovery:
- `set_user_goal`: parses `cmd_select_lose/maintain/gain`
- `set_user_activity`: `cmd_select_sedentary/light/moderate/heavy`
- `set_user_training_type`: `cmd_select_strength/cardio/mixed/training_skip`
- `set_user_gender`: `cmd_select_male/female`
- `set_user_goal_speed`: `cmd_speed_slow/fast` (normal via ELSE) — **другой prefix!**

### 5. users table — columns referenced

```sql
SELECT column_name, data_type, udt_name, is_nullable, column_default
FROM information_schema.columns
WHERE table_name='users'
  AND column_name IN ('<list relevant cols>');
```

Знай actual names — Session 10 hit `users.country_code` (не `country`) discrepancy.

### 6. app_constants — existing icons/keys

```sql
SELECT key, value FROM app_constants WHERE key LIKE 'icon_%' ORDER BY key;
```

Не дублируй — check до INSERT.

### 7. ref_* tables для dynamic lists

```sql
-- Check ref_countries, ref_timezones structure
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name IN ('ref_countries','ref_timezones')
ORDER BY table_name, ordinal_position;
```

Session 10 discovery: `ref_countries.code` (2-letter ISO, PK), `ref_countries.translations` (jsonb per lang), `ref_timezones.id` (bigint numeric ID). Callback convention `loc_tz_{id}` — numeric, не zone_name (avoids / in callback data + 64-byte limit).

### 8. Last applied migration number

```sql
SELECT MAX(version) FROM supabase_migrations.schema_migrations;
-- OR fallback:
ls migrations/ | sort -V | tail -5
```

Нумеруй следующие подряд. Если параллельный агент работает — сверь перед apply.

### 9. n8n workflows snapshots

```bash
# n8n self-hosted на VPS — доступ через SSH (cloud отменён 2026-04-30)
for id in 6XzdbQqpoUG0nsLe ju0h4WStPZX54EfR Ksv1DhWKUIDtlhLy; do
    ssh root@89.167.86.20 "curl -s -H 'X-N8N-API-KEY: \$N8N_TARGET_API_KEY' \
        http://127.0.0.1:5678/api/v1/workflows/$id" \
        > /tmp/wf_${id}_pre.json
done
```

Проверь:
- `name`, `active`, `nodes.length`, `updatedAt`
- После PUT — verify `updatedAt` изменился, `nodes.length` соответствует expected

Backup в `.claude/rollback/<session>/<workflow>_BEFORE.json`.

### 10. Python Telegram proxy state

```bash
curl -s "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

Expected (if proxy healthy):
```json
{"url": "https://<vps>:8443/telegram/webhook", "has_custom_certificate": true, "pending_update_count": 0}
```

Если URL не равен Python proxy (`https://<vps>:8443/telegram/webhook`) — WebhookHealthCron fallback triggered ИЛИ параллельный агент переключил. Coordinate перед изменениями webhook config. (n8n cloud URL legacy, отменён 2026-04-30.)

Проверь `telegram_proxy.py` status whitelist:
```bash
grep -nE "registration_step|edit_" /Users/vladislav/Documents/NOMS/telegram_proxy.py
```

Знай ограничения: новые `editing:*` statuses обычно НЕ в whitelist → typing-indicator не показывается на picker screens (acceptable, render ~80ms).

## Common gotchas обнаруженные в Session 10 Phase 0

| Gotcha | Observation | Impact |
|--------|-------------|--------|
| **env var name** | В `.env` нет `TELEGRAM_BOT_TOKEN`, только `N8N_API_KEY`+`SUPABASE_*`+`DATABASE_URL` | getWebhookInfo fails с 404 — token habeas hardcoded в CLAUDE.md (8291189502) |
| **DNS transient на Supabase pooler** | `aws-1-eu-west-1.pooler.supabase.com` периодически fails | `sleep 3 && retry` |
| **Python 3.14 dotenv bug** | `find_dotenv()` AssertionError | Always `load_dotenv('/absolute/path/.env')` |
| **Process_user_input body size** | 10-15K chars, 350+ lines | Save `/tmp/pui_before_<migration>.sql` перед CREATE OR REPLACE |
| **NLM snapshot stale** | NLM знает migrations 081-101 but не 102-109 | Phase 1 resync via `/nlm-noms` + `/nlm-noms-code` ОБЯЗАТЕЛЬНО |
| **users.country_code (NOT country)** | NOMS schema | Grep DB schema не специфику |
| **specs vs RPC ground truth** | `profile-v5-screens-specs.md` использовал `cmd_set_*`, RPCs парсят `cmd_select_*` | RPC body grep = ground truth, specs — может быть устаревшей |
| **workflow_states.PK=state_code** | Not `status` | Adversarial finding #5 |
| **FSM state naming drift** | `edit_*` underscore vs `editing:*` colon в БД одновременно | Choose one consistently (new Session 10 — `edit_*`) |
| **Stale-base regression при `CREATE OR REPLACE FUNCTION`** | 3-кратная регрессия на `cron_check_streak_breaks`: фикс 036 (qualified `u.streak_freezes`) → 042 при добавлении `is_bot=false` скопировала тело из 011 (broken) → 166 при добавлении `deleted_at IS NULL` скопировала тело из 042 (всё ещё broken) → 167 объединила. Прод падал на PG 42702 ambiguous минимум сутки, silent error в `apscheduler` (job=success, RPC=400). | **Стартовая база при правке существующей RPC — `pg_get_functiondef('public.<rpc>')` ЖИВОГО прода**, не git-файл из ранней миграции. Сохраняй в `/tmp/<rpc>_before_<migration>.sql`, `git diff` против него после правок. Применимо ко всем RPC, не только process_user_input. См. [daily/2026-05-04.md](../../daily/2026-05-04.md) — раздел «Миграция 167». |

## Output format для Phase 0 report

Обязательные поля в summary (передавать design subagent'у в Phase 2):

```markdown
## Phase 0 Discovery — <Session N>

### ui_screens (existing)
- Count: X
- Relevant: <list>

### workflow_states (existing + needed)
- Existing: <count + state_codes>
- Needed INSERT: <list>
- Needed UPDATE: <list>

### RPCs
- Existing setters: <list with signatures>
- Existing list_*: <list>
- MISSING (needed in this migration): <list>

### Callback ground truth (from RPC body grep)
- <rpc_name>: <CASE branches>

### Constraints
- render_strategy: <enum>
- input_type: <enum>
- users.status FK target: <workflow_states.state_code | none>

### n8n state
- 01_Dispatcher: <nodes.length> (updated <timestamp>)
- Relevant sub-workflows: <list>

### Python proxy
- Webhook URL: <current>
- telegram_proxy.py whitelist: <list statuses>

### Last migration
- On disk: <number>
- Applied in DB: <number>
```

## Связанные KB концепты

- [[n8n-multi-agent-workflow-editing]] — coordination protocol
- [[supabase-db-patterns]] — CHECK constraints, sargable queries
- [[headless-architecture]] — ui_screens / workflow_states / nav_stack base
- [[notebooklm-code-sync]] — NLM sync scripts для validation

## Applicable to

Любая migration Session в NOMS:
- Новый Headless screen (picker / text_input / dynamic_list)
- Новый setter RPC
- Extension существующей RPC (render_screen / process_user_input)
- n8n workflow PUT (01_Dispatcher / 04_Menu_v3 / 02_Onboarding_v3)

Пропускать Phase 0 — накапливать technical debt + критические баги. Session 10 found 5 critical + 7 high findings в Phase 0 + adversarial review ДО prod apply. All prevented.
