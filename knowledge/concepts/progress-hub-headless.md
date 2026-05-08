---
title: "Progress Hub Headless Migration (Phase 3A Iteration 2)"
aliases: [progress-hub-headless, progress-main-headless, quests-headless, league-headless, shop-headless, friends-headless]
tags: [headless, progress, migration, phase-3a, gamification]
sources:
  - "daily/2026-04-24.md"
created: 2026-04-27
updated: 2026-04-27
status: "DEPLOYED — migrations 129-139 applied (Sessions 13-14)"
---

# Progress Hub Headless Migration (Phase 3A Iteration 2)

Full headless migration of Progress Hub: `progress_main` + 4 children (quests, league, friends_info, shop). Applied across Sessions 13-14 via migrations 129-139. All screens render via `render_screen` + `process_user_input` fastpath. Universal `cmd_back` navigation via `back_screen_id_default='progress_main'`.

## Key Points

- **9 migrations (129-139)** covering: wrapper RPCs (FLAT shape, eager translations), `ui_screens` seeds, `process_user_input` fastpath patches, `ui_translations × 13 langs`, nav_stack workaround + rollback, UX spec alignment
- **Wrapper RPC pattern** (same as stats_main): FLAT top-level fields, eager-resolve composite strings per user language with EN fallback + RAISE EXCEPTION
- **jsonb_set intermediate key gotcha**: `jsonb_set(content, '{new_section,key}', val, true)` does NOT auto-create `new_section` if absent. Fix: `content || jsonb_build_object('new_section', jsonb_build_object('key', val))`
- **anchor_only ui_screens entries**: `premium_plans` seeded with `back_screen_id_default='shop'` and `meta.anchor_only=true` — phantom entry for nav_stack anchor fallback, renders via legacy 10_Payment
- **Session 12 Python Middleware validated**: First production Dispatcher PUT without webhook drift — Telegram Trigger disabled = no auto-setWebhook
- **p95 latency**: all 5 screens < 210ms DB render; n8n+Telegram overhead = ~90% of user-perceived 1-3s click→response

## Migration Sequence

### Migration 129 — progress_main headless

`get_progress_rpc(p_telegram_id BIGINT) → JSONB` — wrapper over existing `get_progress_business_data` + `get_progress_insight`. Returns FLAT top-level: `streak`, `mana_current`, `mana_max`, `xp`, `nomscoins`, `league_icon`, `league_display`, `league_position_text` (eager-resolved per user lang), `progress_insight` (eager-resolved), `display_name`.

Seeded `ui_screens.progress_main` with 4 inline buttons: cmd_quests, cmd_league, cmd_friends_info, cmd_shop. `back_screen_id_default=NULL` (root screen, no parent).

### Migration 130 — process_user_input fastpath

Patched `process_user_input` using `pg_get_functiondef + REPLACE + EXECUTE` pattern: `cmd_progress → progress_main`. Also: reply-text detection via `icon_progress` in Dispatcher Route Classifier v1.12.

### Migration 131 — mana_display premium branch

Premium users → `{tr:progress.mana_unlimited}` (eager-resolved per lang). Free users → `"{mana_current}/{mana_max}"` literal. New key `progress.mana_unlimited × 13 langs`.

### Migration 132 + 138 — nav_stack workaround + rollback

**Migration 132 (workaround):** After migration 129, Back from legacy children (quests/league/etc) went to legacy Progress not headless `progress_main`. Workaround: `cmd_progress` fastpath seeded `nav_stack='["progress_main"]'` instead of `'[]'`. Legacy children push onto `["progress_main"]` → Back pops → `parent='progress_main'` → Back Target Router 'progress' output → headless `progress_main` render.

**Migration 138 (rollback):** After children migrated to headless (133-136), nav_stack workaround became unnecessary (and incorrectly doubled nav_stack entries for new progress visits). Rolled back to `nav_stack='[]'` on `cmd_progress` fastpath.

### Migrations 133-136 — 4 children headless

All 4 follow identical pattern:
1. Wrapper RPC: `get_quests_rpc` / `get_league_rpc` / `get_friends_info_rpc` / `get_shop_rpc` — FLAT shape + eager translations
2. `ui_screens` seed with `back_screen_id_default='progress_main'`
3. Single Back button: `[🔙 {buttons.back} → cmd_back]`
4. `ui_translations.{screen}.main_text × 13 langs`
5. `process_user_input` fastpath patch

**Migration 135 bug (jsonb_set intermediate key):** `friends_info` section was new in `ui_translations`. `jsonb_set(content, '{friends_info,main_text}', val, true)` silently failed — `friends_info` key didn't exist so `main_text` was NULL for all 13 langs. Fix: `content || jsonb_build_object('friends_info', jsonb_build_object('main_text', tmpl) || (content->'friends_info'))`.

### Migration 137 — premium_plans anchor

**Problem:** User opens Plans screen via subscription expiry push notification → `cmd_premium_plans` without prior `push_nav(shop/my_plan)` → nav_stack = `['premium_plans']` → Back → `back_nav` returns `parent=NULL` → fallback to main menu (wrong).

**Fix:** Insert `premium_plans` as anchor-only entry in `ui_screens`:
- `back_screen_id_default='shop'`
- `meta.anchor_only=true, meta.rendered_by='10_Payment'`
- `render_strategy='replace_existing'` (CHECK constraint compliance only — not actually used by headless)

`back_nav(uid, 'premium_plans')` → `{parent: 'shop', source: 'anchor_after_pop'}` ✅

### Migration 139 — UX spec alignment (550 LOC)

User-approved decisions per spec §22/23/24:

| Screen | Key Decision |
|--------|-------------|
| Quests | Section headers: `📅 <b>{section_weekly}</b>` + `🏅 <b>{section_achievements}</b>` |
| League | 4-neighbor window (rank±2), edge-shifted to 5 rows. Bold HTML for user row |
| Friends | Spec §11.1: stats_active + stats_pending + earned_label + pro_goal. reward_block removed |
| Shop | Free/premium branch split: premium → `{tr:shop.mana_unlimited}`, free → `current/max`. Inline prices in button labels |

**Back button universal:** `cmd_back` everywhere (not `cmd_progress`). Relies on `ui_screens.back_screen_id_default='progress_main'`.

**New translation keys × 13 langs:** `shop.mana_unlimited`, `shop.btn_buy_freeze` (with inline price), `shop.btn_buy_mana` (with inline price).

**Mutually exclusive buttons (shop free/premium):** use different `col_index` (0/1) to satisfy UNIQUE constraint `(screen_id, row_index, col_index)`. Only one is visible per render due to `visible_condition`.

## Bugs Fixed

### Bug A — Банда shortcut opened secondary screen
`[👥 Банда]` opened friends_info secondary info screen instead of main Friends hub. Caused by Dispatcher Route Classifier missing `cmd_friends_info` in `PROFILE_V5_CALLBACKS`. Fixed in Route Classifier PUT (migration 135 + Dispatcher v1.12) — user retest requested post-deploy.

### Bug B — Shop → Продлить → Back → wrong screen
Edge case: user arrived at Plans screen via subscription expiry push notification → `nav_stack=['premium_plans']` → Back → `back_nav` returned `parent=NULL` → fallback to main menu. Fixed with migration 137 (anchor-only `premium_plans` entry).

### Premium mana display bug
Premium users saw "434/500" instead of "Безлимит". Fixed in migration 131 (eager-resolve per lang into `{tr:progress.mana_unlimited}`).

## Latency Benchmarks

| Screen | p50 (ms) | p95 (ms) |
|--------|----------|----------|
| progress_main | 93.3 | 182.3 |
| quests | 93.9 | 152 |
| league | 80.7 | 109 |
| friends_info | 70 | 206 (1 outlier) |
| shop | 86.2 | 194 |

All < 210ms DB render. n8n+Telegram overhead = ~1-2.5s additional (90% of click→render). Profiling deferred.

## Dispatcher Updates (n8n PUT, Route Classifier v1.12)

- `PROFILE_V5_CALLBACKS` += cmd_quests, cmd_league, cmd_friends_info, cmd_shop
- Reply-text detection: `text.includes(constants.icon_progress)` → `command='cmd_progress'` → v3
- First production PUT without webhook drift — validates Session 12 Python Middleware migration

## Deferred

| Item | Status |
|------|--------|
| `cmd_league_info`, `cmd_friends_how_it_works` | Still legacy-routed |
| `cmd_buy_freeze`, `cmd_buy_mana`, `cmd_premium_plans`, `cmd_profile_subscription` | Still legacy-routed |
| `share_invite_link` | Still legacy-routed |
| Shop action buttons headless | Need save_rpc + confirmation screens pattern |
| League zone emoji from app_constants | Hardcoded 🟢/⚪/🔴 in RPC |
| n8n+Telegram overhead profiling | click→render 1-3s |

## Related Concepts

- [[concepts/headless-architecture]] — overall headless architecture, process_user_input, render_screen
- [[concepts/stats-main-headless]] — Phase 3A predecessor (same wrapper RPC pattern, migration 124 canonical)
- [[concepts/dumb-renderer-interpolation-gotchas]] — Gotcha #3: jsonb_set intermediate key
- [[concepts/nav-stack-architecture]] — back_screen_id_default anchor fallback (migration 121 extended)
- [[concepts/dispatcher-webhook-reregistration]] — Session 12 fix validated in first prod PUT (Sessions 13-14)
- [[concepts/supabase-db-patterns]] — migrations 129-139

## Sources

- [[daily/2026-04-24.md]] — Sessions 13-14: migrations 125, 129-139; UX alignment decisions; latency benchmarks; Bug A/B diagnosis
