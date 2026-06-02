#!/usr/bin/env python3
"""Stop hook — nudge the agent to run /kb-close when today's daily log is missing.

Why a Stop hook: CLAUDE.md is loaded at session *start*, but by the end of a long
session the instruction inertia is gone and the agent skips session-close. This
fires on every turn-end and is the deterministic enforcement layer the
session-close-discipline concept asked for.

Design choices that keep it from being annoying:
  - Self-terminating: once /kb-close creates daily/<today>.md, this stays silent
    forever for that day. The very act of closing the session turns it off.
  - Rate-limited (once / 20 min): in a chat-only session the block fires at most
    once; the agent reads the escape hatch ("if only discussion, just stop again")
    and the next stop inside the window is allowed through. So at worst one extra
    turn, never an infinite loop.
  - Stdlib only + plain python3 (no `uv run`): this runs every turn, so it must be
    near-instant.

Output contract: a Stop hook that emits {"decision": "block", "reason": ...} feeds
`reason` back to the agent so it actually acts (a plain echo the agent never sees
would defeat the purpose).
"""

import json
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # claude-memory-compiler/
TODAY = date.today().isoformat()
daily = ROOT / "daily" / f"{TODAY}.md"

# Already logged today → the agent knows the discipline; don't nag.
if daily.exists():
    sys.exit(0)

# Rate-limit so we block at most once per window.
marker = ROOT / "scripts" / ".close-reminder-last"
WINDOW_SECONDS = 1200  # 20 min
now = time.time()
try:
    if marker.exists() and now - marker.stat().st_mtime < WINDOW_SECONDS:
        sys.exit(0)
    marker.write_text(str(now))
except OSError:
    pass  # never let bookkeeping failure block the agent

reason = (
    f"Session-close check: сегодняшнего daily-журнала "
    f"(claude-memory-compiler/daily/{TODAY}.md) ещё нет. "
    "Если в этой сессии менялся код / миграции / флаги / архитектура, или был "
    "gotcha / новый паттерн — запусти /kb-close (daily → concept+index → MEMORY), "
    "чтобы следующий агент не потратил 20-40 минут на разбор завалов. "
    "Если это было только обсуждение без изменений — просто заверши ещё раз."
)
print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
sys.exit(0)
