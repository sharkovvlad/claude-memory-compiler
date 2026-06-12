---
title: "Subagent Live-Apply Review Rule — SQL human-review BEFORE psycopg2 execution"
aliases: [subagent-sql-review, live-apply-gate, taskstop-not-rollback, parallel-vs-sequential-subagents]
tags: [agent-collaboration, safety, lessons-learned, p0-prevention]
sources:
  - "daily/2026-05-26.md — P0 incident postmortem"
  - "migrations/360_recovery_buttons_onboarding.sql — recovery from unreviewed apply"
  - "daily/2026-06-12.md — parallel-isolation vs sequential lesson (PR #385 vs #386)"
created: 2026-05-26
updated: 2026-06-12
status: active
severity: P0-prevention
---

# Subagent Live-Apply Review Rule

> **TL;DR.** If a subagent is authorized to apply changes LIVE to prod (`psycopg2 + .env` or equivalent), the orchestrating agent MUST read the subagent's SQL before authorization. The brief phrase "apply via psycopg2 + verify" is NOT review — it's a permission, not a checkpoint. Additionally, `TaskStop` kills the process but does NOT roll back DB writes already committed; always audit live state after stopping a DB-writing agent.

## What broke (2026-05-26)

Orchestrating agent (this session's main agent) wrote a subagent brief for mig 359 ending with:
> «Apply via psycopg2 + verify via SAVEPOINT. Main agent reviews + creates PR.»

The subagent generated SQL containing `ut.content || ns.payload` (shallow JSONB merge — see [[jsonb-shallow-merge-antipattern]]). The subagent applied LIVE without orchestrating agent reading the SQL. 5 hours later, owner UAT screenshot revealed 182 broken buttons across 13 langs.

Root cause analysis (orchestrating agent's accountability):
1. **No pre-apply review.** Brief said "verify via SAVEPOINT" — but SAVEPOINT alone catches syntax/RPC errors, NOT semantic data-overwrite bugs. Need human SQL review for any non-trivial write.
2. **`TaskStop` confidence misplaced.** When first subagent (earlier in session) hit a different scope issue, orchestrating agent called `TaskStop`. Verified "no changes applied" via column count check. But subagent had ALREADY committed cycle_period_choice column + meta updates. The "no changes" assumption was wrong — orchestrator only checked some artifacts, missed others.

## The rule

### Layer 1: Brief design (orchestrator's responsibility)

**Default:** subagent returns SQL + verification log + plan. Orchestrator reviews + applies (or asks subagent to apply with reviewed SQL).

**Exception:** subagent applies LIVE only when:
- Touching is well-understood single-key UPDATE (no merge logic)
- OR orchestrator has explicit instructions from owner permitting autonomous apply
- AND change is auditable post-hoc via simple DIFF query

For anything touching:
- JSONB content with nested namespaces (`ui_translations.content`)
- RPC bodies (`CREATE OR REPLACE FUNCTION`)
- Schema mutations (`ALTER TABLE` / `CREATE TABLE`)
- Trigger / constraint changes

→ **Subagent MUST return SQL for human review BEFORE apply.** Orchestrator reads the SQL before authorizing apply. Phrases like "apply via psycopg2" without a review step are anti-patterns.

### Layer 2: TaskStop audit (orchestrator's safety net)

After `TaskStop` on any agent that had DB execution privileges:

```sql
-- Generic audit (adapt per scope of agent's work):
SELECT
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name='users' AND column_name='cycle_period_choice') AS new_col_exists,
    (SELECT meta FROM ui_screens WHERE screen_id='cycle_tracking_setup') AS screen_meta,
    -- + any RPC/screen/translation namespaces the agent might have touched
    ...
```

Orchestrator runs this BEFORE assuming "stopped = no changes". If artifacts exist → either:
- Roll them back manually (write a counter-mig), OR
- Treat them as accepted state and continue (with file-level update to match)

### Layer 3: Mig file authority

**Even when a subagent applies LIVE, the migration FILE in `migrations/` must be reviewed before PR merge.** The file is the canonical record. If file diverges from live state, future re-apply re-introduces the bug. Always pull live RPC source post-apply via `pg_get_functiondef` and re-generate the mig file to match (KB: [[pre-migration-discovery-recipe]]).

## Concrete prompt patterns

### ❌ Anti-pattern brief

> «Build migration 359. Apply via psycopg2 + verify via SAVEPOINT. Main agent reviews + creates PR.»

Result: subagent applies broken SQL before review.

### ✅ Safe brief

> «Build migration 359. Return SQL + verification log. Do NOT apply LIVE — main agent reviews SQL, then applies after sign-off.»

OR for trusted-scope work:

> «Build migration 357. SQL must use ONLY [explicit patterns: jsonb_set per leaf]. NO `||` shallow merges (anti-pattern [[jsonb-shallow-merge-antipattern]]). Apply via psycopg2 after writing SQL — main agent will audit live state diff post-apply.»

The second form pre-constrains the SQL shape, making post-hoc audit possible.

## Related concepts

- [[jsonb-shallow-merge-antipattern]] — the specific bug this rule's incident surfaced
- [[agent-collaboration-protocol]] — broader subagent contract (this rule extends it)
- [[pre-migration-discovery-recipe]] — pull-live-state guard against stale base
- [[safe-create-or-replace-recipe]] — sibling recipe for RPC mutations

## Incident summary

| Step | Subagent action | Orchestrator check | Outcome |
|---|---|---|---|
| Mig 359 brief | "apply via psycopg2 + verify" | none of SQL itself | Subagent applied `||` shallow merge |
| Mid-session pivot | First subagent stopped before owner decision change | Column-count check missed partial writes | Cycle_period_choice column persisted |
| 5h later UAT | — | Owner screenshot exposed broken UI | mig 360 recovery (2h work) |

**Lessons codified in this concept** to prevent re-occurrence in next sessions.

## Parallel worktree-isolation vs sequential in-place (2026-06-12 lesson)

Расширение правила — relevant для code-задач (не SQL): когда выгодно spawn'ить субагентов **параллельно с `isolation: "worktree"`** vs **последовательно в текущем worktree без isolation**.

### Incident — утро 2026-06-12 (PR #385)

Главный агент запустил два субагента **параллельно** в worktree-isolation:
- Subagent A: `cold_start_phase` META — новая функция + триггер.
- Subagent B: `metas_fired` observability — трекать все существующие META включая ту что добавила A.

Оба родились от чистого `main` (не друг от друга). B попытался искать `cold_start_phase` в коде → 0 hits → НЕ написал тест на её тегирование. Cherry-pick'ом главного агента: 6 conflict markers в `services/sage.py` (одни и те же 3 функции — signatures, docstrings, return-блоки). Manual resolve + добавить 2 missing теста на `cold_start_phase` × `metas_fired` интеграцию.

### Fix — вечер 2026-06-12 (PR #386)

Спавн A→B→C **последовательно в одном моём worktree без isolation**:
- Каждый subagent видел git log + код предыдущих коммитов.
- A: trim my_day prompt. B: quiet_steady threshold. C: ban-list META (видит `_fetch_recent_sage_reactions` и тегирование из B).
- 0 conflicts, 0 manual merge, 194 sage-тестов green.

### Правило

| Сценарий | Стратегия |
|---|---|
| Truly-independent изменения в **разных файлах** (например docs + tests + new module) | **Parallel с `isolation: "worktree"`** — speedup от параллелизма, конфликтов нет |
| B зависит от знания «что добавил A» (например observability трекающая фичу из A) | **Sequential без isolation** — каждый видит предыдущие коммиты в git log |
| Несколько фич в **одном** файле (`services/sage.py`, `handlers/X.py`) | **Sequential без isolation** — иначе конфликт-маркеры гарантированы |
| Большие independent рефакторинги в разных директориях | **Parallel с `isolation: "worktree"`** + main agent cherry-pick'ит когда оба готовы |

### Тест перед spawn'ом

Перед `Agent({isolation: "worktree", ...})` спроси себя:
1. **Будет ли subagent B читать код subagent'а A?** → если да, **не parallel**.
2. **Будут ли A и B менять одни и те же функции / классы / файлы?** → если да, **не parallel**.
3. **Если A и B — completely separate scope (например A: миграция SQL, B: правка handler'а), но в одном PR?** → **parallel ok, но cherry-pick в одну ветку, не merge worktree branches**.

### Cleanup после parallel-isolation

Worktree'ы агентов: `/Users/vladislav/Documents/NOMS/.claude/worktrees/agent-<id>/`. Auto-cleanup если subagent ничего не закоммитил; иначе остаются. Чистить вручную: `git worktree remove <path>` после cherry-pick'а.
