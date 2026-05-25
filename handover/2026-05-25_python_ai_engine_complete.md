# Handover — Python AI Engine cutover COMPLETE

**Date:** 2026-05-25 (evening)
**From:** Python AI Engine agent (Stage 7 owner — 4 days)
**To:** Next agent picking up NOMS work
**Status:** ✅ Stage 7a + 7b complete, GLOBAL CUTOVER LIVE on all users

---

## TL;DR

**Стейдж 7 (миграция `03_AI_Engine` из n8n в Python) полностью переехал на production для ВСЕХ юзеров.** n8n `03_AI_Engine` workflow всё ещё активен как fallback, но больше **не вызывается** при стандартном flow — он будет деактивирован в Stage 7c через 1-2 недели stable global observation.

Если что-то сломается в Python AI flow — rollback **одной SQL командой**:
```sql
UPDATE app_constants SET value='false' WHERE key='handler_ai_engine_use_python';
```
Hot-reload через `app_constants_cache` trigger (60s TTL), no deploy needed, инстант возврат в n8n для всех.

---

## Production state (2026-05-25 21:00 MSK)

### Cutover flags
```
handler_ai_engine_use_python = true   ← GLOBAL CUTOVER LIVE
ai_engine_beta_testers       = [417002669]   ← audit trail только (gate removed)
handler_food_log_use_python  = true   ← render in Python (Phase 2, давно)
handler_menu_v3_use_python   = true   ← давно
handler_onboarding_use_python = true  ← давно
handler_location_use_python  = true   ← давно
handler_payment_use_python   = true   ← давно
```

### Migration HEAD
- **346** — meal_action rich data (UX-агент)
- Stage 7 own migrations: 296-299, 304, 308, 309, 336, 340

### Recent merged PRs (this agent)
| PR | What | Notes |
|---|---|---|
| #145 | Stage 7a PR A — foundation (mig 296-299) | ai_config extend, ai_prompts table, log_ai_request RPC, beta_testers row |
| #148 | Stage 7a PR B — Python AI orchestration | services/ai_recognition.py, ai_cache.py, sticker.py, ai_logging.py |
| #154 | Stage 7a PR C — cutover infrastructure | mig 308 processed_messages + is_idempotent_message RPC, gate in webhook_server |
| #155 | Stage 7b PR D — Edit Meal pipeline | _handle_edit_meal_input, mig 309 replace_meal_transaction |
| #177 | P0 hotfix — defensive idempotency self-block | parallel agent fixed our PR C bug |
| #180 | Canary fix — double sticker + emoji prompt | mig 336 v3 prompts |
| #182 | Canary fix — Остаток 0 ккал + force Sage for n8n | wrong RPC key remaining_kcal → remaining_daily_calories |
| #183 | Backlog cleanup — cascade_level + stale flag | mig 339 |
| #186 | Canary fix — NULL meal_id (BIG block) | uuid generation in handler, mig 340 backfill |
| #191 | UX — rich meal_action display | mig 346 |
| **#192** | **GLOBAL CUTOVER + observability** | **THE FINALE** |

### Critical RPCs (live signatures verified 2026-05-25)
| RPC | Signature | Notes |
|---|---|---|
| `log_meal_transaction` | `(p_telegram_id, p_food_items jsonb, p_input_source, p_meal_id uuid, p_raw_user_input, p_image_url)` | Returns **`remaining_daily_calories`** NOT `remaining_kcal`. `p_meal_id=NULL` → does NOT generate UUID (DEFAULT only fires when param omitted). Caller MUST generate UUID. |
| `replace_meal_transaction` | `(p_telegram_id, p_meal_id, p_food_items, p_input_source='edit', p_raw_user_input)` | UPSERT pattern via atomic DELETE+INSERT. Mig 328 preserves `consumed_at` from original meal. NO mana deduction. xp_gained=0 (correction XP via separate RPC). |
| `grant_correction_xp` | `(p_telegram_id)` | +5 XP for edit. Called separately after `replace_meal_transaction`. |
| `is_idempotent_message` | `(p_telegram_id, p_message_id)` | **CLAIM not check** — atomic INSERT ON CONFLICT DO NOTHING. Returns TRUE if duplicate (skip), FALSE if claimed (proceed). Called ONLY in webhook_server, NEVER in downstream handlers (anti-pattern, см. KB `claim-vs-check-idempotency-anti-pattern.md`). |
| `get_meal_action_data` | `(p_telegram_id)` | Reads `users.editing_meal_id`. Returns items[]+macros (post mig 346) + legacy fields (meal_time_local, meal_items_summary, meal_calories). |
| `get_day_summary` | `(p_telegram_id)` | Returns `meals[]` grouped by `meal_id` (`WHERE meal_id IS NOT NULL`). If you see empty meals[] for a user with non-zero totals → NULL meal_id bug recurred. |

---

## Stage 7c — what's next

**Когда:** После 1-2 недель global stable observation (so примерно 2026-06-08 if no regressions).

**What to do:**

1. **Verify global is stable**
   - `SELECT count(*) FROM ai_coach_logs WHERE created_at > NOW() - INTERVAL '7 days' AND NOT success` — should be < 1% of total
   - `SELECT count(DISTINCT telegram_id) FROM ai_coach_logs WHERE created_at > NOW() - INTERVAL '7 days'` — should match active users
   - journalctl 7 days: no recurring `ERROR|CRITICAL|Traceback` from `handle_ai_input` or `_handle_edit_meal_input`
   - User-reported bugs in admin chat (417002669) — none open

2. **Deactivate n8n workflows** (via n8n API)
   - `03_AI_Engine` (ID `kjw4kkKMD0IqNALg`) → `active=0`
   - `06_Indicator_Clear` (ID `jQn0nTxThFal4Kpe`) → `active=0` (replaced by Python sticker.py)
   - Keep snapshots in `n8n_workflows/03_AI_Engine.json` (already present)

3. **Cleanup `01_Dispatcher` executeWorkflow refs** via Safe PUT recipe (KB `n8n-data-flow-patterns.md`)
   - Remove "Go to 03_AI_Engine" branch from Route Classifier

4. **DELETE `/internal/food_log/render` endpoint** from `webhook_server.py`
   - It was the n8n → Python HTTP bridge for rendering. Now Python calls `render_food_log_confirmation` directly via Python function call. No more n8n caller.
   - Remove `FOOD_LOG_RENDER_TOKEN` env var if it was only for this endpoint

5. **DELETE workflows** via n8n API after 1 week deactivated stable:
   ```bash
   ssh root@89.167.86.20 'curl -X DELETE -H "X-N8N-API-KEY: $KEY" http://127.0.0.1:5678/api/v1/workflows/kjw4kkKMD0IqNALg'
   ```
   ⚠️ **Beware**: n8n 2.17 has FK `ON DELETE RESTRICT` on `workflow_published_version`. If 500 error → first manual DELETE from `workflow_published_version` + `workflow_publish_history` via host-side sqlite3 (recipe in KB `n8n-data-flow-patterns.md` § «Lesson 2026-05-21»).

6. **KB updates**
   - `architecture-registry.md` — remove 03_AI_Engine + 06_Indicator_Clear from active workflows table
   - Add `concepts/python-ai-orchestration.md` (lesson for future migrations: cascade pattern, prompt versioning, lazy zombie cleanup)

---

## Open issues (passed/pending)

### 🔴 cmd_show_meals «не с 1го раза»
- **Status:** Investigation read-only done, pattern found in journalctl
- **Evidence:** SHADOW_ROUTE log present, AUTHORITATIVE_MENU_V3 sometimes missing for same `cmd_show_meals` callback. User clicks multiple times before getting response.
- **Pattern:** `cmd_show_meals` goes through generic `dispatch_with_render` RPC (no special handler in `handlers/menu_v3.py:107+`).
- **Next step:** Need fresh repro with exact timestamp from owner. Then grep journalctl for that update_id and trace handler exit path.
- **Hypotheses:** (a) `dispatch_with_render` returns NULL silently sometimes; (b) `_send_and_persist` async task fails; (c) Telegram client-side double-tap dedup.

### 🟢 cmd_stress_high (Phase 3c) silent drop
- **Status:** Discovered during investigation, **handed over to UX-agent**.
- **Handover:** `handover/2026-05-25_ux_bugs_stress_and_sleep.md`
- **Evidence:** `cmd_stress_high` shadow-logs but consistently misses AUTHORITATIVE_MENU_V3 (adjacent `cmd_stress_none`, `cmd_sleep_*` work fine).
- **Likely cause:** Hybrid modal routing pattern (Phase 3c) handler swallows exception.

### 🟢 `test_phase3b_sleep_ux.py` — 4 tests fail on main
- **Status:** Pre-existing on origin/main, NOT from AI engine cutover.
- **Handover:** Same file as above.
- **Hypothesis:** Stale admin DB fixtures OR mig 334 (Phase 3d luteal) added unexpected `daily_modifiers` rows that break Phase 3b assertions.

### 🟢 `dispatcher_python_authoritative_admin_only` cleanup
- **Status:** ✅ DONE via mig 339 (PR #183). Row deleted from app_constants, RPC `get_dispatcher_flags()` no longer returns the field.

### 🟢 cascade_level=0 telemetry artifact
- **Status:** ✅ DONE via PR #183. `ai_recognition.py` now iterates full cascade with absolute index, skipping cache inline.

### 🟡 `ai_engine_beta_testers` allowlist row
- **Status:** **Kept as audit trail** (which tids were canary). Helper `_user_in_ai_beta_allowlist` in webhook_server.py kept for potential future canaries. Can be deleted in Stage 7c if you want clean state.

### 🟡 11 non-EN/RU translations use Latin macro labels in meal_action
- **Status:** Subagent's note — non-blocking UX nit. Copywriter polish can address.

### 🟡 Non-emoji translations DE/FR/IT/PL/PT/ES/ID/HI (rich meal_action template)
- **Status:** Same — minimal UX impact, defer to copywriter sprint.

---

## Critical lessons learned (READ THIS)

### Lesson 1 — NLM RPC contracts may be stale
Hit twice in 2 days:
1. NLM said `log_meal_transaction(p_meal_id)` does UPSERT → реально returns DUPLICATE_MEAL. Fix: created `replace_meal_transaction` (mig 309).
2. NLM said RPC returns `remaining_kcal` → реально `remaining_daily_calories`. Fix: handler reads with fallback chain (PR #182).

**Rule:** Before writing any RPC mapper code, run `pg_get_functiondef('public.<rpc>')` AND `psycopg2.execute('SELECT <rpc>(...)' ) + json.dumps()` to capture LIVE shape. Don't trust NLM for RPC field names or behavior. UX-агент documented this in KB `pre-migration-discovery-recipe.md` § «LLM payload normaliser must validate against LIVE RPC shape».

### Lesson 2 — Stale worktree = production breakage
Hit twice in 2 days:
1. PR B subagent's worktree was 5 days stale. Did `git checkout origin/main -- <file>` to restore missing files BUT lost router.py Phase 3 callbacks (22 lines). Caught in pre-push sanity.
2. PR #186 subagent's worktree similarly stale. Restored `handlers/food_log.py` from older base, lost emoji handling code from PR #180. Result: ~6 hours of broken emoji writes on canary admin only. Auto-deploy of PR #191 incidentally restored handler.

**Rule:** Any long-running worktree (>1 day idle) MUST do `git fetch origin main && git rebase origin/main` before any feature branch. Run `git diff origin/main..HEAD --stat` BEFORE every push (catches semantic rollback). Subagents need explicit instruction "rebase before commit" in your spec.

### Lesson 3 — Defensive idempotency = anti-pattern
PR C added `is_idempotent_message` defensive guard in handler (after webhook layer already claimed). Self-blocked all food logs for 6+ hours. Parallel agent (`wonderful-keller-8af0e2`) caught and removed in PR #177.

**Rule:** `is_idempotent_message` is a **claim** (atomic INSERT), not a **check**. Only ONE caller per (tid, msg_id) — the entry point (webhook_server). Downstream handlers must trust upstream claim. Don't add "defensive double-check" — it's self-blocking. KB: `claim-vs-check-idempotency-anti-pattern.md`.

### Lesson 4 — Maternal Sage safety guard is a FEATURE not a bug
`services/sage.py:_hard_skip_namespace` returns `"guarded.maternal"` for users with `is_pregnant OR is_lactating = TRUE`. Skips LLM, uses pre-baked phrases from `ui_translations.{lang}.sage.guarded.maternal[]`. This is **clinical safety** (anti-shame, no risky completions). If a user wants dynamic LLM Sage and has pregnancy flag → flip flag through profile UI.

---

## Health check queries

```sql
-- AI engine cascade distribution (last hour)
SELECT cascade_level, model, success, count(*) AS n,
       avg(latency_ms)::int AS avg_ms,
       avg(confidence)::numeric(3,2) AS avg_conf
FROM ai_coach_logs WHERE created_at > NOW() - INTERVAL '1 hour'
GROUP BY 1,2,3 ORDER BY 4 DESC;
-- Healthy: cascade_level distributed across 0 (cache), 2 (mini), 3 (gpt-4o)
-- Red flag: only cascade_level=3 (always gpt-4o = cost leak, mini broken)

-- meal_id integrity (should be 0 NULL for new food_logs)
SELECT count(*) FROM food_logs
WHERE meal_id IS NULL AND created_at > NOW() - INTERVAL '1 hour';
-- Healthy: 0. If >0 → handler regression (PR #186 fix dropped)

-- Idempotency activity (should be small)
SELECT count(*) FROM processed_messages
WHERE processed_at > NOW() - INTERVAL '1 hour';
-- Healthy: matches food log count + a few duplicates from Telegram retries

-- Active flag state
SELECT key, value FROM app_constants
WHERE key LIKE 'handler_%_use_python' OR key = 'ai_engine_beta_testers'
ORDER BY key;
```

```bash
# journalctl health
ssh root@89.167.86.20 'journalctl -u noms-webhooks --since "1 hour ago" --no-pager | \
  grep -cE "^\w+\s+ERROR|Traceback"'
# Healthy: 0

# emoji observability — verify emoji is being filled by AI
ssh root@89.167.86.20 'journalctl -u noms-webhooks --since "30 min ago" --no-pager | \
  grep -E "handle_ai_input:" | tail -10'
# Look for "emoji_filled=N" where N matches items count
# If N=0 consistently → AI prompt regressed (check mig 336 v3 active)
```

---

## Files map (where things live)

### Stage 7 Python code
- `services/ai_recognition.py` — cascade orchestration (cache → fatsecret-hook → mini@0.80 → gpt-4o), Pydantic `FoodItem`/`ParsedFoodResult`
- `services/ai_cache.py` — `ai_food_cache` table read/write (text-only)
- `services/sticker.py` — thinking sticker with lazy zombie cleanup
- `services/ai_logging.py` — `log_ai_request` RPC wrapper, fire-and-forget
- `services/sage.py` — UX-agent's territory, Sage `noms_comment` LLM (Phase 3 wellbeing)
- `handlers/food_log.py` — `handle_ai_input` (new log) + `_handle_edit_meal_input` (edit) + `render_food_log_confirmation` (presentation, called by both Python and n8n via HTTP endpoint while it exists)
- `webhook_server.py:1525+` — `_try_authoritative_path` gate (NO allowlist anymore after PR #192)

### Stage 7 migrations
| # | What |
|---|---|
| 296 | ai_config extend (temperature, max_tokens, etc.) |
| 297 | ai_prompts table + 3 placeholder seeds |
| 298 | log_ai_request RPC + ai_coach_logs telemetry columns |
| 299 | handler_ai_engine_use_python flag + ai_engine_beta_testers |
| 304 | users.indicator_set_at + save_indicator_state v2 + real ai_prompts v2 |
| 308 | processed_messages + is_idempotent_message RPC |
| 309 | replace_meal_transaction RPC (edit UPSERT pattern) |
| 336 | ai_prompts v3 (per-item emoji instruction) |
| 339 | DROP dispatcher_python_authoritative_admin_only row + RPC refresh |
| 340 | backfill NULL meal_ids for admin (group by exact microsecond) |

UX-agent migrations (parallel team, not Stage 7 but related):
- 316-323 — Sage system prompts × 13 langs, My Day LLM
- 324, 326 — meals_picker 2-stage flow
- 325, 327 — translations fixes
- 328 — replace_meal_transaction preserve consumed_at (bug fix on mig 309)
- 329 — get_day_summary timezone fix
- 330 — cron premium filter + mutex
- 331-333 — wellbeing entry from stats_main
- 334-335 — Phase 3d luteal foundation + i18n
- 341-345 — Phase 3 toast/strip + back navigation + mobile compaction
- 346 — meal_action rich data (my PR #191)

### KB articles relevant to Stage 7
- `concepts/architecture-registry.md` — canonical Python-vs-n8n target map
- `concepts/pre-migration-discovery-recipe.md` — LIVE RPC shape verification recipe (READ before any RPC mapper code)
- `concepts/claim-vs-check-idempotency-anti-pattern.md` — why double-claim is anti-pattern
- `concepts/release-protocol.md` — deploy + rebase discipline
- `concepts/n8n-data-flow-patterns.md` — Safe PUT recipe + FK delete trap
- `concepts/migration-collision-guard.md` — pre-push hook for migration NNN collisions
- `concepts/edit-picker-dual-render.md` — superseded by headless-picker-pattern (info only)
- `concepts/headless-architecture.md` — Phase 3A/3B foundation
- `handover/2026-05-25_ux_bugs_stress_and_sleep.md` — bugs handed to UX-agent

---

## Tactical recommendations for next agent

1. **Don't immediately do Stage 7c** — wait at least 1 week of stable global. Observe `ai_coach_logs` cascade distribution + journalctl error rate. If you see anomalies, debug ON Python flow before deactivating n8n (it's the only fallback).

2. **First thing each session:** Read today's `daily/YYYY-MM-DD.md` + yesterday's. The project has 3-5 agents working in parallel — state changes hourly.

3. **Before any RPC code:** `pg_get_functiondef` LIVE. Don't trust NLM for RPC contracts. Two production incidents in 2 days were from this.

4. **Before any git push:** `git diff origin/main..HEAD --stat`. If you see deletions in files you didn't touch — STOP, rebase. Two incidents in 2 days from stale worktrees.

5. **Migration numbers:** check `gh pr list --state open` for in-flight migrations. Multiple agents commit migrations daily.

6. **Apply migrations** through psycopg2 with `DATABASE_URL` from `.env`. Files have `BEGIN/COMMIT` inside. Verify via SELECT after apply.

7. **Subagent specs:** explicitly include "rebase from origin/main before any edits" and "pg_get_functiondef before any RPC mapper code". I assumed they'd know — they don't.

8. **Maternal Sage** (`is_pregnant` / `is_lactating`) skips LLM by design. Don't treat as bug if you see pre-baked phrases for that user.

9. **`/internal/food_log/render` endpoint** is the last bridge to n8n for food log render. It's still used by n8n flow (now nobody, since global cutover, but the endpoint exists). Delete it in Stage 7c, not before.

10. **Rollback procedure** — single SQL row. Don't deploy if you panic, just flip the flag. Hot-reload via trigger.

---

## Signature thing

Bot is `@nomsaibot` (8291189502). Admin chat 417002669. Production VPS `89.167.86.20`. Deploy via PR merge → GitHub Actions auto-rsync + restart `noms-webhooks` + `noms-cron` systemd services + smoke test.

If you need to talk to the team:
- Owner: tg 417002669 (admin chat)
- UX-agent (Sassy Sage, Phase 3): see daily logs `wonderful-keller-8af0e2` agent ID
- Other parallel agents: see `daily/2026-05-2X.md` for the day

Good luck. Stage 7 was a 4-day push. The bot now does AI orchestration entirely in Python end-to-end. Stage 7c cleanup is the celebratory final lap.

— Python AI Engine agent, 2026-05-25
