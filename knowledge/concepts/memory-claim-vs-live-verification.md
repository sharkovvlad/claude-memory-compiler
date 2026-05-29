---
title: "MEMORY claim ↔ Live разрыв — handover-факты могут быть ложными, всегда verify live"
aliases: [memory-vs-live, handover-claim-trust, stale-memory-protocol, reality-check-discipline]
tags: [methodology, lessons-learned, anti-pattern, agent-discipline, p1-prevention]
sources:
  - "daily/2026-05-29.md (Nutritionist 10 reality check on Stage 7)"
  - "handover/2026-05-29_stage7_status_reality_check.md"
  - "MEMORY.md system reminder: «Memory records may become stale»"
created: 2026-05-29
status: active
severity: P1-prevention
---

# MEMORY Claim ↔ Live Verification Discipline

> **TL;DR.** Если MEMORY или handover делает **specific claim** про прод-state (миграция X сделана, flag Y = true, фича Z в global, юзеров N штук) — это **point-in-time observation**, не live truth. Перед тем как принять решение на основании этого claim'а, **обязательно verify через 2+ независимых источников** (БД через psycopg2, код через Read/grep, n8n через API/SQLite, git log). Если расхождение — всегда trust live, исправь memory.

## Anchoring case: Stage 7 «GLOBAL CUTOVER» 2026-05-29

**MEMORY говорила:** «2026-05-25 (evening) Stage 7 Python AI Engine **GLOBAL CUTOVER** (PR #192). All 1000+ users on Python AI orchestration.»

**Nutritionist 9 handover повторил claim:** «Stage 7 переехал, Stage 7c cleanup — easy operational hygiene через 1-2 недели».

**Реальность 2026-05-29 (через 4 независимых источника):**

| Источник | Данные |
|---|---|
| `app_constants` table | `ai_engine_beta_testers = [417002669]` — owner only |
| `webhook_server.py:1626` gate | требует `_user_in_ai_beta_allowlist` |
| n8n SQLite `execution_entity` | `03_AI_Engine` = 13 executions / 2 дня (last 16:26 МСК сегодня) |
| food_logs split 24h | others=9 (via n8n), owner=3 (Python) — 75% non-Python |
| git log commit 203b798 | "force dynamic Sage **for n8n users**" — author *knew* non-admin = n8n |

**Stage 7 был admin-only canary с 21.05**, global cutover **никогда не происходил**. Если бы Nutritionist 10 поверил MEMORY и пошёл по плану Stage 7c deactivate — сломал бы recognition для всех не-admin юзеров (75% трафика).

## Корневая причина (почему MEMORY ошибается)

1. **Daily/handover пишутся в конце сессии** — agent отчитывается о намерении, не о post-merge verification.
2. **Cron'ы и фичи могут быть rolled back** между сессиями, никто не пишет «откатил».
3. **«PR merged» != «работает global»** — flag-based deployments часто канарейка, и agent забывает обновить, когда расширяет allowlist.
4. **Compiler merges concepts** — ошибочные claim'ы из одной daily/handover могут попасть в KB-снапшот как fact.

## Дисциплина: 5 классов claim'ов которые ОБЯЗАНЫ verify

### 1. Cutover / migration / feature-flag статус
**Pattern claim:** «X переехал в Y» / «cutover complete» / «flag Z = true» / «GLOBAL».

**Verify:**
- `SELECT key, value FROM app_constants WHERE key LIKE '%use_python%' OR key LIKE '%beta%';` — все active flags + их values
- Grep по живому коду — gate condition, allowlist check
- Если есть n8n — `docker cp noms-n8n:/home/node/.n8n/database.sqlite + sqlite3 execution_entity` — узнать last execution per workflow (n8n API `/executions?workflowId=...` отдаёт пустоту, это known quirk)
- food_logs / любой другой downstream table — split by relevant key

### 2. «Сделано» в claim про i18n / 13 langs
**Pattern claim:** «keys X добавлены × 13 langs».

**Verify:**
```sql
SELECT language_code, content -> 'X' IS NOT NULL AS present
FROM ui_translations
WHERE language_code IN ('ar','de','en','es','fa','fr','hi','id','it','pl','pt','ru','uk');
```

или конкретнее с jsonb path:
```sql
SELECT language_code, content #> '{X,Y}' AS value
FROM ui_translations WHERE language_code = 'ru';
```

«13 langs done» часто означает «в наброске», не «в проде» — особенно после P0 incidents с rollback (mig 359 wipe пример).

### 3. User counts / engagement metrics
**Pattern claim:** «N active users», «N% adoption».

**Verify:**
- ОБЯЗАТЕЛЬНО `WHERE is_bot = false` ([[concepts/npc-bots-users-table]])
- Если время-зависимо — sanity по NOW() vs created_at distribution
- Кросс-чек по food_logs / notification_log / другой downstream table

### 4. RPC сигнатура / function definition
**Pattern claim:** «RPC X возвращает Y».

**Verify:**
```sql
SELECT pg_get_functiondef(p.oid)
FROM pg_proc p
JOIN pg_namespace n ON p.pronamespace = n.oid
WHERE n.nspname = 'public' AND p.proname = 'X';
```

KB [[concepts/pre-migration-discovery-recipe]] объясняет почему — git-файлы могут устать после `CREATE OR REPLACE` правок прямо в проде. Production = truth.

### 5. n8n workflow active/inactive state
**Pattern claim:** «n8n workflow X deactivated».

**Verify:**
```bash
ssh root@89.167.86.20 'curl -s -H "X-N8N-API-KEY: $KEY" http://127.0.0.1:5678/api/v1/workflows?limit=250 | python3 -c "import sys, json; [print(w[\"id\"], w[\"active\"], w[\"name\"]) for w in json.load(sys.stdin)[\"data\"]]"'
```

`active: true` = трафик принимает (если есть triggers). Также проверяй SQLite executions table — может быть `active: false` но успел отработать недавно.

## Что делать когда нашёл расхождение

1. **НЕ паника** — это нормально, MEMORY декорирует время-в-моменте.
2. **Остановись, не делай destructive operation** на основании stale claim'а.
3. **Документируй расхождение в daily** того дня, чтобы дать audit trail.
4. **Исправь MEMORY.md** — конкретные claim'ы перепиши на live state с явным указанием «verified YYYY-MM-DD».
5. **Создай handover-стаб** если расхождение блокирует чей-то план (как `2026-05-29_stage7_status_reality_check.md`).
6. **Создай KB-статью** если паттерн ошибки recurrent (как эта статья).

## Pre-flight checklist для destructive operations

Перед `n8n PUT active:false`, `DELETE FROM app_constants`, `DROP TABLE`, `git revert` известных функций, или любого «cleanup based on claim X is true»:

- [ ] Прочитал ли я claim в свежем (≤24h) daily? Если в старом — мог уже измениться.
- [ ] Проверил ли я claim через ≥2 независимых источника live?
- [ ] Что произойдёт если claim ложен и я сделаю операцию? Если «обратимо» — go. Если «5+ юзеров сломаются» — STOP.
- [ ] Документирована ли rollback процедура? Если нет — STOP, документируй сначала.

## Связано с

- [[concepts/pre-migration-discovery-recipe]] — verify RPC definitions через `pg_get_functiondef` LIVE
- [[concepts/architecture-registry]] — source of truth для cutover state (но тоже verify, особенно для admin canary fields)
- [[concepts/release-protocol]] §rebase-перед-commit — параллельная работа усугубляет stale-state
- [[concepts/n8n-data-flow-patterns]] §Safe PUT — verify GET перед PUT
- [[concepts/npc-bots-users-table]] — конкретный пример где stale claim («1000 users») рушится через is_bot filter
