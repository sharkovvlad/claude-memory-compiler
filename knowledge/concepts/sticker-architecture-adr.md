# ADR 0001: Sticker Architecture — 4 Channels with Single Source of Truth

- **Status:** Accepted (Stage 1 + 1.1 live; Stage 2 in review; Stage 3 backlog)
- **Date:** 2026-05-11
- **Migrations:** `198_stickers_unified_foundation.sql` + `200_sticker_one_time_semantics.sql`
- **Stages:**
  - 1.0 (mig 198, PR #45 merged) — Channel A headless infrastructure
  - 1.1 (mig 200, PR #47 — this branch) — one-time-per-user semantics for UI stickers
  - 2.0 (PR #46 in review) — Channel C/D code consolidation onto common cache
  - 3.0 (backlog) — Channel B event facade for AI-Engine reactions

## Context

NOMS (`@nomsaibot`) currently has **three disconnected ways** of sending Telegram stickers, planted as quick tactical solutions over Q1–Q2 2026:

1. **Thinking/processing indicator** — direct `httpx.post('/sendSticker')` fire-and-forget from `telegram_proxy.py`; local in-memory cache (`_stickers_cache`, TTL 3600s) of `bot_stickers WHERE category='processing'`; rotation via `users.last_indicator_index`; deletion after AI response via `users.indicator_message_id` (mig 165).

2. **Smart Freeze push** (mig 191) — direct `httpx.post` from `crons/freeze_notification_pusher.py`; local cache `_freeze_sticker_cache` of `bot_stickers WHERE category='freeze'`.

3. **Onboarding UI stickers** (mig 161, placeholder) — declared in `ui_screens.meta = {show_sticker:true, sticker_category:'…'}`, but `render_screen` did not read the flag and `template_engine` did not resolve `file_id`. Dead declaration for ~10 days — sticker never reached users.

Product plans ~30–40 stickers across 5+ semantic classes (onboarding, achievement, league, push, AI reactions, Sage mood). Without a unified foundation each new sticker becomes another tactical hack, parallel agents create regressions in each other's caches, and the headless-architecture invariant (mig 161 Phase 4) erodes.

PgBouncer in transaction mode (Supabase pooler `:6543`) rules out `LISTEN/NOTIFY` cache invalidation — we need a polling model.

## Decision

Adopt a **4-channel sticker architecture** with `bot_stickers` as the single source of truth and `services/stickers_cache.py` as the single in-memory cache. Each sticker is assigned to exactly one channel by its semantics:

### Channel A — UI Content (this ADR's stage 1 scope)

Sticker is part of a screen's content (welcome, success, level-up, achievement). Visibility tied to a `screen_id`.

- **Source of truth for "when":** `ui_screens.meta.show_sticker = true` + `sticker_category`.
- **Path:** SQL `render_screen` emits `telegram_ui.sticker_category` → Python `template_engine.render_envelope` resolves `file_id` via cache → adds `OutboundItem(strategy='send_sticker')` **before** the main item → `telegram_send` sends via `await`.
- **Order in chat:** guaranteed (sticker above text) by sequential `await` in `telegram_send`. **`asyncio.create_task` is forbidden here** — see Consequences.
- **Persistence:** Trophy (no deletion).

### Channel B — Event side-channel (Stage 3, deferred)

Reaction to a side-effect (food recognized by AI, water logged). Not tied to a screen; can fly over the current menu.

- **Path:** Explicit Python call `await stickers.send_event(chat_id, category)` from handlers/cron, bypasses envelope.
- **Persistence:** optional `meta.auto_delete_after_ms`.

### Channel C — Push (with sticker, Stage 2)

Cron-driven push notification combining a sticker and a text body.

- **Path:** Sequential `await` (sticker, then text) from cron job.
- **Persistence:** Trophy.

### Channel D — Transient indicator (existing, Stage 2 consolidation)

Thinking / analyzing indicator during long operations.

- **Path:** Fire-and-forget from `telegram_proxy.py`; ok to race because the artifact is transient.
- **Persistence:** Deleted after AI response.

### Shared infrastructure

- **Table `bot_stickers`** with extensions in mig 198:
  - new `meta jsonb` (future per-sticker options like `auto_delete_after_ms`)
  - new `updated_at timestamptz` + `trg_set_updated_at` trigger
  - partial index `(category, sort_order) WHERE is_active`
  - explicitly **rejected** columns: `language_code`, `send_count`, `deprecated_at` (YAGNI / hot-row risk).
- **`services/stickers_cache.py`**:
  - In-memory dict `category → [(sort_order, file_id)]`
  - `prewarm()` on FastAPI startup with 3× exponential-backoff retry, fail-open
  - Background refresher every **60 seconds** (rejected: 15-minute TTL — too slow for active development of 20+ stickers; rejected: LISTEN/NOTIFY — incompatible with PgBouncer transaction mode)
  - **Keep-stale** on transient network error (welcome sticker must survive pooler blips)
  - Synchronous `lookup()` to be callable from synchronous `render_envelope`
  - DI: `query_fn` injection point for tests
  - Manual reload via `POST /internal/stickers/reload` with `X-Stickers-Reload-Token` header (env var; endpoint returns 503 if token absent).

### Headless contract (Channel A)

This is **symmetric to `attach_reply_kb`** (mig 157): declarative field in `telegram_ui` maps to an `OutboundItem` in the envelope. Business rule ("which screen should show a sticker?") lives in `ui_screens.meta`, not in `handlers/`.

```
ui_screens.meta.show_sticker=true
    ↓
SQL render_screen Step 8b + Step 9
    ↓
telegram_ui.sticker_category = '<text>' | null
    ↓
template_engine.render_envelope() Channel A block
    ↓
items[ACQ?, send_sticker?, main_item, attach_reply_kb?]
    ↓
telegram_send sequential await
```

## Consequences

### Positive

- **Single source of truth** (`bot_stickers`). New sticker = 2 SQL INSERTs / UPDATEs (one row, one `ui_screens.meta` update). Zero Python changes for adding a sticker to an existing screen pattern.
- **Headless preserved.** `ui_screens.meta.show_sticker` lives next to other Phase 4 declarations (`no_back`, `canonical`, `reply_kb_entry`). Sticker policy is reviewable as a SQL diff.
- **No race conditions in Channel A.** Strict `await` chain in `telegram_send`. Order "sticker above text" is guaranteed by TCP/HTTP request initiation order plus Telegram processing each message atomically.
- **Fail-open cache.** Pooler blips do not break visible UX — stale cache continues serving. Hard-failure (cache empty AND can't refresh) is observable via `stats().last_status='error'`.
- **Hot-reload during development.** `POST /internal/stickers/reload` instantly refreshes; 60s TTL bounds passive lag.
- **Testability.** `StickersCache(query_fn=...)` DI removes Supabase dependency from unit tests.

### Negative

- **Cache latency vs SQL lookup.** SQL emits `category` (text), not `file_id` — keeps `render_screen` p95 at ~70ms (vs. +3–8ms had we JOIN'd `bot_stickers`). Trade-off: cache miss is now a "graceful skip" rather than a SQL error, but `lookup()` returns `None` only if either the category is unknown or the cache failed completely; either case is correctly logged and rendered without the sticker.
- **TTL of 60s.** Updated `file_id` becomes visible up to 60s after `UPDATE bot_stickers`. Manual reload endpoint mitigates for ops; for product changes 60s is acceptable.
- **Lazy import in `template_engine`.** `from services import stickers_cache` happens inside `render_envelope` to avoid circular imports at module load. Cost is one dict lookup per render; acceptable.
- **Channels C/D not yet consolidated.** Stage 1 leaves `telegram_proxy.py:_stickers_cache` / `_freeze_sticker_cache` parallel to the new cache. Stage 2 will collapse them. Coexistence is intentional — protects thinking indicator during Channel A rollout.

### Risks

- **Cold-start window.** Between FastAPI startup and `prewarm` completion (~150ms typical), `lookup()` returns `None` for all categories. Channel A handles this as graceful skip; first user might miss a welcome sticker if traffic arrives in this window. Acceptable: shutdown→startup is a deliberate operation.
- **Force-push to `bot_stickers.file_id`.** A malformed update (bad string, deleted sticker pack) propagates to user-facing failure within 60s. Mitigations: `Telegram API` returns 400 on invalid `file_id` → `telegram_send` logs warning, main message still goes out (sticker is optional). No bot crash.

## Alternatives Considered

### Alt 1 — "Just dot the i" (tactical fix only)

Fill `file_id` for `onboarding_welcome_1`, add `onboarding_success_1`, write 7 lines in `template_engine` to read `sticker_file_id` (not category). Skip the cache / 4-channel model.

**Rejected because:** every subsequent sticker (18+ planned) requires a similar one-off code path. Within 2–3 sprints we'd have a fragmented graveyard mirroring today's situation. The fundamental decision (cache layer, channel taxonomy, single source of truth) was the same effort regardless of whether 2 or 20 stickers were live at the time.

### Alt 2 — SQL emits `file_id` directly, no Python cache

`render_screen` LEFT JOINs `bot_stickers` per render call.

**Rejected because:** adds +3–8ms p95 per screen render. With 1000+ active users and 25 msg/sec peak, that's wasted RTT under load. The cache write-path is trivial (60s polling); the read-path benefit (~0ms in-memory dict) is meaningful.

### Alt 3 — Telegram-proxy fire-and-forget for all stickers (extend Channel D)

Use `asyncio.create_task` everywhere, including Channel A welcome/success.

**Rejected because:** Telegram balancers do not guarantee request ordering. `sendSticker` and `sendMessage` issued in parallel can be received in reverse order, putting the celebration sticker **below** the "Готово!" text. For thinking-indicator (Channel D) this is fine (the sticker is transient and removed after the AI response anyway). For UI-content (Channel A) order is part of the contract — Trophy-mode means whatever lands stays in the chat forever.

### Alt 4 — `LISTEN/NOTIFY` for cache invalidation

Postgres trigger on `bot_stickers` UPDATE fires `NOTIFY stickers_cache_invalidate`; Python `LISTEN` thread invalidates immediately.

**Rejected because:** Supabase pooler in **transaction mode** does not support session-level features like `LISTEN/NOTIFY`. Switching to session mode for one feature is disproportionate; a 60s TTL plus manual reload endpoint achieves equivalent operational hygiene.

### Alt 5 — `language_code` column on `bot_stickers`

Allow per-language sticker variants (Russian celebration sticker ≠ English celebration sticker).

**Rejected (YAGNI):** product decision is that stickers are universal (no text on the image; localized text follows as a separate message). Can be added later without a destructive migration.

### Alt 6 — `send_count` increment on every show

Track popularity in `bot_stickers.send_count` via SQL.

**Rejected:** hot-row UPDATEs on a frequently-rendered row create lock contention. Aggregate analytics belong in structured logs (Datadog/Grafana), not in the source-of-truth table.

## Open Questions / Stage 2+ Backlog

1. **Channel B facade** (`services/stickers.py:send_event`) — postponed until AI-Engine migrates from n8n to Python.
2. **Channel D consolidation** — `telegram_proxy._stickers_cache` → `services/stickers_cache` migration. Will require parallel coexistence for safe rollout.
3. **Per-screen sticker rotation** — currently `lookup(rotation_index=0)` always picks `sort_order=0`. If product wants random rotation for Sage mood, expose a `random_rotation` flag in `ui_screens.meta`.
4. **Multilingual stickers** — re-evaluate `language_code` if product changes mind.

## References

- KB: `claude-memory-compiler/knowledge/concepts/ui-stickers-headless.md`
- KB: `claude-memory-compiler/knowledge/concepts/headless-architecture.md`
- KB: `claude-memory-compiler/knowledge/concepts/telegram-proxy-indicator.md` (Channel D pattern)
- Migration: `migrations/198_stickers_unified_foundation.sql`
- Baseline: `migrations/_baseline_render_screen_2026-05-11.sql`
- Code: `services/stickers_cache.py`, `services/template_engine.py` (Channel A block), `webhook_server.py` (prewarm + reload endpoint)

---

# ADR 0001 — Stage 1.1 Amendment: One-Time Semantics for UI Stickers

- **Status:** Accepted (mig 200, PR #47)
- **Date:** 2026-05-11
- **Trigger:** Live observation on test account 267703 — welcome sticker fired multiple times because `cmd_select_lang` in `status='new'` re-renders `onboarding_welcome` without advancing FSM.

## Context (amendment)

Stage 1.0 assumed FSM-state transitions naturally guarantee one-time sticker emission: «после первого нажатия статус сменится с new». This was **incorrect**: language selection (and any other in-status callback) re-renders the same screen at the same status → SQL emits `sticker_category` again → another `OutboundItem(send_sticker)`.

For Trophy-mode stickers (Channel A: persistent UI content) any re-emission is a visible UX bug — the chat history accumulates redundant celebration stickers.

## Decision (amendment)

Introduce **per-user per-category tracking** via `users.stickers_shown jsonb` and opt-in flag `ui_screens.meta.show_sticker_once = true`. Inside `render_screen` Step 8b:

1. If `meta.show_sticker_once = true` AND `users.stickers_shown ? sticker_category` → emit `NULL` (graceful skip; template_engine renders without the sticker).
2. Otherwise → emit `sticker_category` AND atomically `UPDATE users.stickers_shown = stickers_shown || {sticker_category: now()}` in the same transaction.

The atomic UPDATE inside what looks like a read-shaped function is a deliberate trade-off — see «Consequences» below.

### Self-documenting Channel marker

`bot_stickers.meta.channel` (`A` / `C` / `D`; `B` reserved) is set for every existing row. This lets future agents and KB searches see at a glance which channel each row belongs to, without grepping calling code. The marker is descriptive, not functional — Python and SQL ignore it.

### Backfill

Existing users who already finished onboarding must not see the stickers again at next /start. Mig 200 backfills:
- `onboarding_welcome` → all users where `status != 'new'`
- `onboarding_success` → all users where `status = 'registered'`

## Consequences (amendment)

### Positive

- **No more redundant stickers** during onboarding language-switch / status-stay callbacks.
- **Generalizable** — any new Channel A sticker gets `show_sticker_once: true` in its `ui_screens.meta` declaration, zero Python changes needed.
- **Atomic** — read-and-mark inside one transaction precludes a race where two concurrent renders both see "not shown" and emit twice.
- **Reset-friendly** — if product wants a user to see a sticker again (e.g. account-restore flow), one SQL: `UPDATE users SET stickers_shown = stickers_shown - 'sticker_category' WHERE telegram_id = X`.

### Negative

- **Side-effect inside read-shaped RPC.** `render_screen` now mutates `users.stickers_shown`. This violates the convention that RPCs whose names start with `render_` are pure reads. Mitigation: the function is `SECURITY DEFINER` and runs in a single Postgres transaction; mutation is bounded to one row and one jsonb key. Diagnostic SELECT calls (without sticker meta) are unaffected — UPDATE only fires when `show_sticker_once = true` AND `sticker_category` would be emitted.
- **Bypass for non-render path.** If code paths invoke `process_user_input` / `dispatch_with_render` and then **separately** call `render_screen` for a side-rendered screen (e.g. `handlers/onboarding_v3.py:681` for `onboarding_success_menu`), each call marks its own categories. This is the correct behavior: each rendered screen is its own one-time event. No additional bookkeeping needed.

## Alternatives Considered (amendment)

### Alt 1 — Mark on Python side (after template_engine emits)

Have `template_engine.render_envelope` (or `telegram_send`) write back to `users.stickers_shown` after the sticker item is dispatched.

**Rejected:** leaks business state into the dumb renderer. Phase 4 invariant (`SQL = WHAT, Python = HOW`) explicitly puts "should this sticker be shown?" in SQL. Cross-transaction marking would also introduce a small window where the same render path concurrently emits two stickers before the mark lands.

### Alt 2 — Use `users.previous_status` to detect "first render"

Only emit when transitioning to the screen for the first time.

**Rejected:** `previous_status` overwrites on every transition. `cmd_select_lang` does not change status, so `previous_status` is irrelevant for in-status re-renders. Doesn't solve the bug.

### Alt 3 — Add a separate `users.welcome_sticker_seen_at` column per sticker

**Rejected:** doesn't scale to 20+ planned stickers. One `jsonb` map is structurally cleaner and works for unbounded categories.

## References (amendment)

- Migration: `migrations/200_sticker_one_time_semantics.sql`
- Baseline: `migrations/_baseline_render_screen_2026-05-11_post_mig198.sql`
- PR: #47 (`claude/sticker-one-time-fix`)
- Live evidence: test account 267703, `/start` + `cmd_select_lang` on 2026-05-11
