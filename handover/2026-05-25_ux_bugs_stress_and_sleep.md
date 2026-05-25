# Handover — UX agent bugs (stress check-in + sleep UX tests)

**Date:** 2026-05-25
**From:** Python-AI-engine agent (Stage 7a canary owner)
**To:** UX-agent (Phase 3 stress/sleep/maternal owner)

---

## TL;DR

Two unrelated bugs surfaced incidentally during canary investigation today:

1. **`cmd_stress_high` callback not routed** — Phase 3c stress check-in button shadow-logs but never produces `AUTHORITATIVE_MENU_V3` response. User clicks → nothing happens.
2. **`tests/integration/test_phase3b_sleep_ux.py`** — 4 tests fail on `origin/main` (pre-existing, не от AI-engine cutover).

Neither blocks Stage 7a global cutover, but both degrade UX for users with Premium adaptive modifiers + Phase 3 features.

---

## Bug 1: `cmd_stress_high` silent drop

### Evidence (journalctl on prod, 2026-05-25 16:37 MSK)

```
16:37:14 SHADOW_ROUTE update_id=455701068 tid=417002669
         target=menu_v3 reason=profile_v5_callback cb_data=cmd_stress_high
         elapsed_ms=190.8
         ↑ shadow_route logged successfully
         ↓ NO matching AUTHORITATIVE_MENU_V3 line follows

16:37:18 SHADOW_ROUTE update_id=455701069 tid=417002669
         target=menu_v3 reason=profile_v5_callback cb_data=cmd_stress_high
         elapsed_ms=172.6
         ↑ user clicked AGAIN 4 seconds later — still no response
         ↓ NO AUTHORITATIVE_MENU_V3

16:37:23 SHADOW_ROUTE update_id=455701071 tid=417002669
         cb_data=cmd_wellbeing_today
         ↑ user gave up and navigated elsewhere
16:37:23 AUTHORITATIVE_MENU_V3 update_id=455701071 ... py=True elapsed_ms=328
         ↑ this one DID get response
```

Compare with adjacent callbacks (`cmd_stress_none`, `cmd_wellbeing_today`, `cmd_sleep_short`, `cmd_sleep_okay`, `cmd_sleep_great`) — every one of those has both SHADOW_ROUTE AND AUTHORITATIVE_MENU_V3 lines. **Only `cmd_stress_high` consistently misses the AUTHORITATIVE log**, meaning routing reaches `_try_authoritative_path` but the handler either:

- raises an exception silently (no traceback in logs — but Python error swallowing in `asyncio.create_task` would explain this)
- returns `False` early (which the dispatcher would log as something different than missing-line)
- enters the wrong branch and falls through to legacy (in which case we'd see a forward_to_n8n log)

### Reproduction

1. User with Phase 3 wellbeing enabled (`stats_main_wellbeing_entry`, mig 331).
2. Tap `[📊 Мой день]` → `[💚 Самочувствие]`.
3. On stress check-in screen, tap `[🔥 Высокий]` (callback `cmd_stress_high`).
4. Expected: stress level recorded → confirmation modal → return to My Day.
5. Actual: nothing happens. User taps again. Still nothing. User navigates elsewhere.

### Likely root cause

`cmd_stress_high` triggers the **hybrid modal routing pattern** (Phase 3c, MEMORY.md "Hybrid modal routing pattern"): handler is `_handle_stress_high` in `handlers/menu_v3.py` or similar, which does `save RPC + append async overlay modal after my_plan`. This is a special case because the handler must:
- write to `daily_metrics.stress_label_qualitative` via `set_user_stress_label(tid, 'high')`
- THEN re-render My Day
- THEN overlay a clinical safety modal (anti-spike for users with extreme caloric restriction)

If any of those three steps raises an uncaught exception, the chain breaks silently. The other `cmd_stress_*` (none/moderate) are headless save_rpc paths via `dispatch_with_render`, so they work via the standard flow.

### Suggested investigation

1. Grep: `grep -rn "cmd_stress_high\|_handle_stress_high" handlers/ dispatcher/` → find the dispatch entry.
2. Add `logger.exception` around the entire `_handle_stress_high` body to surface swallowed errors.
3. Trigger live test with admin (tid=417002669) and tail `journalctl -u noms-webhooks --since "1m ago" | grep stress`.
4. Check if `set_user_stress_label` RPC errors on extreme-caloric-restriction users (mig 317 added clinical safety hooks — maybe the modal trigger condition raises).

---

## Bug 2: `tests/integration/test_phase3b_sleep_ux.py` — 4 tests fail on main

### Evidence

PR #191 (meal_action rich UX, my work) subagent ran full pytest suite:

```
983 passed, 4 pre-existing failures, 1 unrelated payment routing test
```

The 4 failures are in `tests/integration/test_phase3b_sleep_ux.py`. Subagent verified они **pre-existing** через `git stash` + re-run on clean `origin/main` — same failures reproduce. Not caused by Stage 7a / canary work.

### Suggested investigation

Likely candidates per pattern:

- **Stale DB fixtures** — Phase 3b sleep integration tests assume specific `daily_metrics.sleep_quality_qualitative` state for admin's test tid. If admin's actual DB state diverges (because owner uses admin tid for live UAT, modifying state), tests fail.
- **TZ regression** — mig 329 was a TZ fix for `get_day_summary` (UX-agent's own work, 2026-05-24). If `cron_check_streak_breaks` or `apply_daily_modifier` has a similar TZ bug, the sleep tests fixed-time assertions would break.
- **mig 334 (Phase 3d luteal) interaction** — added new branch to `apply_daily_modifier`. Sleep test may have shared fixture or assertion on `daily_modifiers` table that now includes unexpected luteal rows.

### Files to inspect

- `tests/integration/test_phase3b_sleep_ux.py` (failing tests — read traceback for assertion details)
- `apply_daily_modifier` RPC body — if changed for Phase 3d, may have broken Phase 3b assumptions
- `cron_check_streak_breaks` — TZ handling
- `daily_metrics.sleep_quality_qualitative` — fixture isolation

---

## Bonus: emoji historical regression (NOT your scope, but related context)

Между 12:00 и 18:15 UTC сегодня (2026-05-25) `handlers/food_log.py` на проде имел **сломанное** emoji handling — `ai_parsed_result` колонка food_logs писалась как `NULL` для new logs. Root cause: PR #186 (Bug 1 hotfix для NULL meal_id) был сделан subagent'ом в stale worktree (5 дней без rebase); restored handler от старой базы потеряв emoji code из PR #180. Auto-deploy PR #191 (~18:15) restored правильный handler. Canary affected — только admin (417002669) since allowlist=[admin].

Lesson написан в KB. Не релевантно для твоих trackов, но heads-up: если ты дальше работаешь на этом проекте с longstanding branches — rebase обязателен каждый день. См. CLAUDE.md global §12.

---

## Sources

- journalctl on prod 2026-05-25 16:37 MSK (stress_high silent drop evidence)
- PR #191 subagent pytest report (sleep tests failures, pre-existing)
- daily/2026-05-25.md — Phase 3 ([UX agent], session continues)
- KB: `concepts/hybrid-modal-routing-pattern.md` (Phase 3c stress pattern docs)

—— Python AI engine agent
