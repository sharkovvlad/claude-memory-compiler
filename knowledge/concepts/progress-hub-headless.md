---
title: "Progress Hub Headless Migration (Phase 3A Iterations 2-4)"
aliases: [progress-hub-headless, progress-main-headless, quests-headless, league-headless, shop-headless, friends-headless, stateful-friends-info]
tags: [headless, progress, migration, phase-3a, gamification, stateful-ui]
sources:
  - "daily/2026-04-24.md"
  - "daily/2026-04-28.md"
created: 2026-04-27
updated: 2026-05-10
status: "DEPLOYED — migrations 129-145 applied. Migration 144 (shop transactions): 8 screens, 2 wrapper RPCs (idempotency). Migration 145 (ambassador payout): 9 screens, 4 RPCs, balance reservation, anti-spoofing phone. Applied 2026-04-28."
---

# Progress Hub Headless Migration (Phase 3A Iterations 2-4)

Config-driven миграция Progress Hub: `progress_main` + 4 hub children (quests, league, friends_info, shop) + 2 info subscreens (league_info, friends_how_it_works). Applied across Sessions 13-14 (6 iterations) via migrations 129-143. All screens render via `render_screen` + `process_user_input` fastpath. Universal `cmd_back` navigation via `back_screen_id_default`.

## Key Points

- **15 migrations (129-143)** covering: wrapper RPCs (FLAT shape, eager translations), `ui_screens` seeds, `process_user_input` fastpath patches, `ui_translations × 13 langs`, nav_stack workaround + rollback, UX spec alignment, **Stateful UI** (friends_info Novice/Ambassador), League empty state, info subscreens, cleanup
- **Wrapper RPC pattern** (same as stats_main): FLAT top-level fields, eager-resolve composite strings per user language with EN fallback + RAISE EXCEPTION
- **jsonb_set intermediate key gotcha**: `jsonb_set(content, '{new_section,key}', val, true)` does NOT auto-create `new_section` if absent. Fix: `content || jsonb_build_object('new_section', jsonb_build_object('key', val))`
- **Stateful UI (friends_info):** один `screen_id` рендерит **два разных экрана** (Novice Band vs Ambassador Dashboard) через `visible_condition` на кнопках + RPC branching по `ambassador_tier`/`paid_referral_count`/`is_trainer`. COALESCE на `ambassador_tier` обязателен (NULL propagation bug найден на первом apply).
- **anchor_only ui_screens entries**: `premium_plans` seeded with `back_screen_id_default='shop'` and `meta.anchor_only=true` — phantom entry for nav_stack anchor fallback, renders via legacy 10_Payment
- **Session 12 Python Middleware validated**: First production Dispatcher PUT without webhook drift — Telegram Trigger disabled = no auto-setWebhook
- **p95 latency**: all screens < 210ms DB render; n8n+Telegram overhead = ~90% of user-perceived 1-3s click→response

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

## Iteration 4 — Stateful friends_info + League empty + Info subscreens (Migration 140/142)

> Migration originally numbered 140, renamed to 142 due to collision with parallel agent's debounce migrations (140-141). DB changes identical — rename was file-only.

### Migration 142 — 750 LOC, idempotent

**Part 1 — `app_constants`:** `icon_partner=💼` (Ambassador title). `icon_pro_goal` initially added as 🏆 but removed as duplicate of existing `icon_league=🏆` — semantic reuse.

**Part 2 — `ui_translations` (4 new keys × 13 langs):** `league.subtitle`, `league.until_monday`, `league.empty_tip`, `referral.how_it_works_text`.

**Part 3 — `get_friends_info_rpc` v3 (Stateful Novice/Ambassador):**

Одна из ключевых архитектурных реализаций сессии. Один RPC возвращает два принципиально разных layout'а:

```sql
v_is_ambassador := COALESCE(v_user.ambassador_tier, '') = 'active'
    OR v_user.paid_referral_count >= v_ambassador_threshold
    OR COALESCE(v_user.is_trainer, FALSE);
```

**⚠️ COALESCE обязателен** — без него `NULL = 'active'` даёт `NULL`, и `IF NOT v_is_ambassador` ошибочно роутит дефолтных Novice users в Ambassador path (баг найден на первом apply).

| Ветка | Содержимое | Кнопки (visible_condition) |
|---|---|---|
| Novice | structured stats (squad/active/pending/earned, всегда даже при count=0) + `🏆 PRO goal {paid}/{threshold}` + invite link + cta_newbie/active random | `[📤 Share]` + `[ℹ️ Info]` + `[🔙 Назад]` |
| Ambassador | subtitle + 4 stat lines (👥/📈/💰/💸) + promo code (или fallback на invite link) + noms_ambassador random | `[📤 Share code]` + `[💳 Payout]` + `[👥 Stats]` + `[🔙 Назад]` |

Threshold `5` хардкоден в `visible_condition` с inline-комментарием `mirrors app_constants.ambassador_referral_threshold` (ui_screen_buttons.visible_condition не делает sub-query lookup без потери performance).

**Part 4 — `get_league_rpc` v4 (empty state + ► marker):**

- Empty state branch: `my_rank IS NULL OR total = 0` → countdown days_until_monday (ISODOW) + `empty_block`
- Active state: `►` marker для self row (без `(TÚ)` суффикса per spec §10.1), 4-neighbor window (rank±2)
- `content_block` — единый placeholder, RPC сам компонует header + subtitle + window + your_rank. Убирает residual blank lines от пустых placeholder'ов
- **rtrim bug**: PostgreSQL `rtrim(text)` без 2-го аргумента трогает только пробелы — `\n` не убирает. Фикс: `rtrim(text, E' \t\n\r')`

**Part 5 — `get_friends_how_it_works_rpc` (NEW):**

Eager-resolves `referral.info_step3` placeholders `{coins}/{xp}/{icon_coin}/{icon_xp}` + `{target}` в `info_step4` из `app_constants.referral_premium_threshold`. Reward amounts из `referral_escrow_coins=50` / `_xp=100`.

**Part 6-8 — Templates + ui_screens + ui_screen_buttons:**

- 2 новых экрана: `league_info` (text-only, back→league), `friends_how_it_works` (с business_data_rpc, back→friends_info)
- `friends_info` кнопки: DELETE 3 existing → INSERT 6 rows (2 Novice + 3 Ambassador + 1 Common Back), split по `visible_condition`

**Part 9 — `process_user_input` fastpath:** +`cmd_league_info → league_info`, +`cmd_friends_how_it_works → friends_how_it_works`.

### Bugs found & fixed during apply (migration 142)

| # | Bug | Fix |
|---|---|---|
| 1 | `v_is_ambassador` NULL propagation | `COALESCE(ambassador_tier, '') = 'active'` |
| 2 | `rtrim(text)` не убирает trailing `\n` | `rtrim(text, E' \t\n\r')` |
| 3 | Extra blank lines в active league template | RPC компонует body в `content_block`, template = title + content_block + Noms |

### Latency (post-migration 142)

| Screen | p95 (ms) |
|--------|----------|
| friends_info | 81 |
| league | 115 |
| league_info | 90 |
| friends_how_it_works | 83 |

### NLM verification (post-apply)

3 архитектурных вопроса подтвердили реализацию: Stateful UI via `visible_condition` confirmed as established pattern (precedent: `profile_main` free/premium, `stats_main` count-based, `shop` subscription split). Ambassador RPCs (`get_ambassador_stats/balance`, `get_referral_info`, `create_ambassador_code`) все существуют. `icon_pro_goal` duplicate confirmed removed, `icon_league` reused.

## Iteration 5 — Cleanup + ТЗ (Migrations 143-145)

### Migration 143 — process_user_input duplicate WHEN clauses

Repeated `pg_get_functiondef + REPLACE + EXECUTE` patches (from migrations 130/135/136/142) left duplicated WHEN-branches in `process_user_input` CASE. 26 WHEN-веток вместо 14 canonical.

Fix: `regexp_replace` с POSIX `{2,}` quantifier:

```sql
regexp_replace(
    v_src,
    '(\s*WHEN ''cmd_league_info''\s+THEN ''league_info''\s+WHEN ''cmd_friends_how_it_works''\s+THEN ''friends_how_it_works''){2,}',
    canonical_single_pair, 'g'
)
```

Post-cleanup: 19,323 → 18,206 chars, 14 canonical WHEN-ветки. Verification DO-block проверяет 9 fastpath callbacks → correct screen_id. Idempotent (re-apply notice "no cleanup needed").

**Functional impact pre-fix:** NONE — CASE WHEN matches first, дубли были dead branches. Чисто cosmetic + parsing overhead.

### Migration 144 — Shop transactions (confirmed applied by parallel agent)

8 headless screens для transaction flow: `buy_freeze_confirm/success`, `buy_mana_confirm/success`, `shop_error_no_coins/mana_full/recharge_limit/already_premium`. 2 wrapper RPCs (`shop_action_buy_freeze/buy_mana`) с 5-sec idempotency window через `coin_transactions` audit. `save_rpc` whitelist расширен: `set_user_% OR shop_action_%`. `meta.error_screen_map` — новый паттерн маршрутизации на error screen при `success=false`.

### Migration 145 — Ambassador Payout (spec ready, 9 screens)

ТЗ: `.claude/specs/migration_145_ambassador_payout_spec.md`. 9 headless screens (method picker → phone verify → wallet input → confirm → success/errors). FSM через `payout_draft jsonb`, anti-spoofing phone verification, balance reservation (race condition двойной заявки). `payout_action_request` wrapper с idempotency. Whitelist: `+ payout_action_% + set_payout_%`.

## Deferred

| Item | Status |
|------|--------|
| `cmd_buy_freeze`, `cmd_buy_mana` | ✅ Headless (migration 144) |
| `cmd_league_info`, `cmd_friends_how_it_works` | ✅ Headless (migration 142) |
| `cmd_premium_plans`, `cmd_profile_subscription` | Still legacy-routed (10_Payment) |
| `share_invite_link`, `share_ambassador_code` | Still legacy-routed |
| League zone emoji from app_constants | Hardcoded 🟢/⚪/🔴 in RPC |
| n8n+Telegram overhead profiling | click→render 1-3s |

## Related Concepts

- [[concepts/headless-architecture]] — overall headless architecture, process_user_input, render_screen
- [[concepts/stats-main-headless]] — Phase 3A predecessor (same wrapper RPC pattern, migration 124 canonical)
- [[concepts/dumb-renderer-interpolation-gotchas]] — Gotcha #3: jsonb_set intermediate key
- [[concepts/nav-stack-architecture]] — back_screen_id_default anchor fallback (migration 121 extended)
- [[concepts/dispatcher-webhook-reregistration]] — Session 12 fix validated in first prod PUT (Sessions 13-14)
- [[concepts/ux-crosscutting-principles]] — Stateful Business-Data UI Pattern (friends_info = canonical example)
- [[concepts/ambassador-payout-system]] — migration 145 extends payout flow to headless
- [[concepts/supabase-db-patterns]] — migrations 129-143

## Sources

- [[daily/2026-04-24.md]] — Sessions 13-14 (6 iterations): migration 125 (stats edit button), migrations 129-143 (Progress Hub full headless + Stateful friends_info + League empty + info subscreens + cleanup); UX alignment decisions; latency benchmarks; Bug A/B diagnosis; migration 144 confirmed; migration 145 spec ready
