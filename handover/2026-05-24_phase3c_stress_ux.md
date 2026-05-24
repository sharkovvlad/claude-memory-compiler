# Handover — Phase 3c Stress UX (mig 317)
**Date:** 2026-05-24  
**From:** Agent nice-mcnulty-f5e97d  
**To:** Next agent  

---

## State at handover

**PR #162** is open, not merged: https://github.com/sharkovvlad/noms-bot/pull/162

**Migration 317 is ALREADY APPLIED to prod DB** (applied before the PR was opened — standard pattern: apply first, then PR for Python code). The DB schema changes are live. The Python handler changes are in the PR branch.

**Branch:** `claude/mig317-phase3c-stress-ux`

---

## What Phase 3c delivered

| Component | Status |
|---|---|
| `daily_metrics.stress_label_qualitative` column | ✅ Live on prod |
| `apply_daily_modifier` stress UPSERT + gate 3c extended | ✅ Live on prod |
| `set_user_stress_label(tid, value)` wrapper RPC | ✅ Live on prod |
| `cron_get_reminder_candidates` stress_checkin branch (18h) | ✅ Live on prod |
| `stress_checkin` ui_screen + 4 buttons | ✅ Live on prod |
| i18n × 13 langs (15 key groups) | ✅ Live on prod |
| Python: `PROFILE_V5_CALLBACKS` + `_handle_stress_high` | ⏳ In PR #162 |
| Python: `main.py` REMINDER_TYPES + `crons/reminders.py` | ⏳ In PR #162 |
| 12 integration tests | ⏳ In PR #162 |

---

## How to test Phase 3c (manual UAT)

### What to ask the owner (tid=786301802) to do in Telegram chat

1. **Navigate to `stress_checkin` screen.** Ask him to send `/start` then navigate to "My plan" → he needs to access the stress_checkin screen somehow. Currently there is no navigation entry from `my_plan` to `stress_checkin` in the UX (the screen exists, but no entry button has been wired yet — stress_checkin is reached via the evening cron reminder or direct deep link). **If no navigation entry exists in my_plan, you need to either**: (a) wait for the 18:00 local cron to fire a reminder, or (b) wire a temporary entry button on `my_plan` for testing.

   **Quick test command for you (psycopg2):**
   ```python
   # Simulate what happens when owner clicks cmd_stress_none
   cur.execute("SELECT public.set_user_stress_label(786301802, 'none')")
   print(cur.fetchone()[0])
   # Expected: {"applied": true/false, "suppressed": ..., "modifier_type": "stress", ...}
   ```

2. **Test the 3 button paths:**
   - `cmd_stress_none` → should advance to `my_plan` headlessly (no modal)
   - `cmd_stress_moderate` → same headless, no modal
   - `cmd_stress_high` → should advance to `my_plan` THEN (if no clinical gate) no modal. If owner has RPP profile → modal appears

3. **Watch for the Python handler running.** After PR #162 is merged and deployed:
   ```bash
   ssh root@89.167.86.20 'journalctl -u noms-webhooks -f' | grep stress
   # Look for: "stress_high safety modal sent tid=..." (only for gated users)
   # Look for: "AUTHORITATIVE_MENU_V3 ... reason=menu_command"
   ```

4. **Test cron reminder (at 18:00 local for the owner):**
   - The cron fires at every :20 and checks who is at local 18:00
   - Owner tz: check `SELECT timezone FROM users WHERE telegram_id=786301802`
   - When the cron fires, owner should receive: "😤 How's your stress today?..."

### What to look for in logs after merge

```bash
# Check that stress callbacks are routing correctly (not falling to n8n)
ssh root@89.167.86.20 'journalctl -u noms-webhooks -f' | grep -E "stress|mig317"

# Watch cron stress_checkin
ssh root@89.167.86.20 'journalctl -u noms-cron -f' | grep stress_checkin

# No regression in daily errors
ssh root@89.167.86.20 'journalctl -u noms-webhooks --since "1 hour ago"' | grep -iE "ERROR|CRITICAL|Traceback"
```

### DB verification (already live)

```python
# Run from Mac via psycopg2:
import os, psycopg2
from dotenv import load_dotenv
load_dotenv('/Users/vladislav/Documents/NOMS/.env')
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()

# 1. Column exists
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='daily_metrics' AND column_name='stress_label_qualitative'")
print("Column:", cur.fetchone())

# 2. Screen exists  
cur.execute("SELECT screen_id, render_strategy, next_on_submit FROM ui_screens WHERE screen_id='stress_checkin'")
print("Screen:", cur.fetchone())

# 3. Buttons
cur.execute("SELECT callback_data, meta->>'save_via_callback' FROM ui_screen_buttons WHERE screen_id='stress_checkin' ORDER BY row_index")
print("Buttons:", cur.fetchall())
# Expected: cmd_stress_none='True', cmd_stress_moderate='True', cmd_stress_high=None/False, cmd_back=None

# 4. EN translations
cur.execute("SELECT content #>> '{stress_checkin,title}', content #>> '{modifier,suppressed,rpp_guard}' FROM ui_translations WHERE lang_code='en'")
row = cur.fetchone()
print("Title:", row[0])
print("RPP guard (first 80):", row[1][:80] if row[1] else None)
```

---

## Architecture summary: hybrid routing

The key architectural decision for Phase 3c: `cmd_stress_high` uses **hybrid routing** instead of headless `save_via_callback`. Reason: the SQL gate can return `show_modal=TRUE` (RPP guard or teen escalation), which Python must read to display an async overlay modal.

```
cmd_stress_none/moderate → save_via_callback=TRUE → SQL headless (no Python needed)
cmd_stress_high → PROFILE_V5_CALLBACKS → menu_v3 Python
                  → _handle_stress_high:
                      1. answer_callback immediately
                      2. set_user_stress_label(tid, 'high') → check show_modal
                      3. dispatch_with_render(cmd_stress_high) → my_plan
                      4. if show_modal: append OutboundItem(send_new, modal_text)
```

See KB `[[concepts/hybrid-modal-routing-pattern]]` for full recipe.

**Gate 3c isolation (verified):** `IF p_modifier_type IN ('luteal', 'stress')` — sleep is NOT in this list. Mig 310 maternal behaviour for sleep is 100% unchanged.

---

## What's NOT done yet (next phases)

### Phase 3d — luteal opt-in flow + privacy disclaimer (mig 318+)
- Luteal modifier currently requires `cycle_tracking_enabled=TRUE` (gate 3d)
- No UI for opt-in exists yet
- `edit_cycle_tracking` screen + consent modal + privacy disclaimer
- See `adaptive_modifiers_spec.md` for full Phase 3d spec

### Navigation entry for stress_checkin
- The screen exists but has no navigation entry from `my_plan`
- Cron is the primary entry (18:00 reminder)
- Consider adding a "How are you feeling?" pill or contextual button on `my_plan` (Phase 3c follow-up or Phase 3d)

### sticker category `reminder_stress` and `stress_checkin_intro`
- These sticker categories are referenced in code but no sticker records exist in `bot_stickers`
- Cron will send text-only (graceful fallback: empty list = no sticker, works fine)
- Upload stress-themed stickers and add to `bot_stickers` with these categories

### Teen gate modal testing
- T6 (teen gate) passes in integration, but hard to test live (owner is adult)
- To test: temporarily set owner's birth_date to 15 years ago, tap stress_high, verify modal appears, rollback

---

## Files in PR #162

```
migrations/317_stress_modifier_ux.sql          ← SQL (already applied to DB)
tests/integration/test_phase3c_stress_ux.py   ← 12 tests
handlers/menu_v3.py                           ← _handle_stress_high + dispatch guard
dispatcher/router.py                          ← cmd_stress_* in PROFILE_V5_CALLBACKS
main.py                                       ← stress_checkin in REMINDER_TYPES
crons/reminders.py                            ← 3 dict entries
```

---

## Merge procedure

This is already rebased on main (last rebase: 2026-05-24 morning). Before merging, do:

```bash
# From MAIN clone (NOT from worktree):
gh api -X PUT repos/sharkovvlad/noms-bot/pulls/162/merge -f merge_method=merge

# GitHub Actions auto-deploys on merge to main.
# Watch:
gh run watch --repo sharkovvlad/noms-bot

# After deploy, smoke check:
ssh root@89.167.86.20 'systemctl status noms-webhooks noms-cron'
ssh root@89.167.86.20 'journalctl -u noms-webhooks --since "2 minutes ago" | grep -iE "ERROR|CRITICAL|Traceback"'
```

---

## Test suite reference

```bash
# Phase 3c only (from worktree or main):
python3 -m dotenv -f /Users/vladislav/Documents/NOMS/.env run \
  pytest tests/integration/test_phase3c_stress_ux.py -v

# Full regression (69 tests):
python3 -m dotenv -f /Users/vladislav/Documents/NOMS/.env run \
  pytest tests/integration/test_phase3c_stress_ux.py \
         tests/integration/test_phase3b_sleep_ux.py \
         tests/integration/test_adaptive_modifiers_foundation.py \
         tests/integration/test_v12_personas.py \
         tests/integration/test_calc_user_targets_rfm.py \
         tests/integration/test_v11_personas.py -q
# Expected: 69 passed
```

---

## Key gotchas discovered this session

### 1. `save_via_callback` return value is opaque to Python

The headless pipeline `save_via_callback=TRUE` → `process_user_input` SQL → advance to `next_on_submit`. Python never sees the save_rpc return value. If you need to react to what the RPC returned (show_modal, qualitative_descriptor, etc.), you CANNOT use `save_via_callback`. You need the hybrid routing pattern.

**Pattern:** hybrid — button has NO `save_via_callback`; Python calls RPC directly, reads result, then calls `dispatch_with_render` for navigation.

### 2. PROFILE_V5_CALLBACKS is mandatory for Python modal handlers

`cmd_*` callbacks NOT in `PROFILE_V5_CALLBACKS` fall through section 4l `is_menu_callback` → `target="menu"` → legacy n8n. The Python `handle_menu_v3` is NEVER called. If your clinical handler is in menu_v3.py but the callback isn't in `PROFILE_V5_CALLBACKS`, nothing works and there's no error — Telegram gets the n8n response instead.

**Check:** Always verify the callback is in `PROFILE_V5_CALLBACKS` when adding a Python handler in menu_v3.

### 3. Sleep buttons are NOT in PROFILE_V5_CALLBACKS (by design)

`cmd_sleep_short/okay/great` work via n8n → `dispatch_with_render` SQL headless. This is correct for sleep because there's no Python-side logic needed. Stress buttons WERE added to PROFILE_V5_CALLBACKS because of the hybrid modal pattern. These are two parallel working patterns — don't assume all new modifier buttons need PROFILE_V5_CALLBACKS.

### 4. `dispatch_with_render` called with a button that has no `save_via_callback`

When Python calls `dispatch_with_render` with a callback_data that points to a button WITHOUT `save_via_callback=TRUE`, SQL's `process_user_input` does NOT call the save_rpc. It just handles navigation (target_screen, next_on_submit). This is exactly what we want in `_handle_stress_high` step 3 — avoid double-saving.

### 5. Callback answer must be FIRST OutboundItem

If you add `answer_callback_only` AFTER navigation items, Telegram shows spinner for ~30s then clears. Always answer callback first in the items list.

### 6. HTML in JSONB clinical modal texts

Clinical modal translations contain `<b>...</b>` HTML tags (proper HTML, not `&lt;b&gt;` HTML-encoded). This is correct — stored as raw strings in JSONB, rendered by Python with `parse_mode="HTML"`. A copywriter subagent sometimes returns HTML-escaped versions — always check and fix before applying.

---

## MEMORY.md and KB state

- **MEMORY.md** updated: Phase 3c section added (mig 317, PR #162, 69 tests, p95)
- **KB** updated: 
  - `concepts/adaptive-modifiers-architecture.md` — §Phase 3c appended
  - `concepts/hybrid-modal-routing-pattern.md` — NEW article
  - `knowledge/index.md` — hybrid-modal-routing-pattern entry added
- **Daily log:** `daily/2026-05-24.md` created
