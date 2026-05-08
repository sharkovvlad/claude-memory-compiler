---
title: "UX Cross-Cutting Principles (NOMS Bot)"
aliases: [ux-principles, shared-screens, skip-rule, stateful-business-data-ui, onboarding-extension]
tags: [ux, architecture, patterns, onboarding, headless]
sources:
  - "daily/2026-04-20.md"
created: 2026-04-20
updated: 2026-04-21
---

# UX Cross-Cutting Principles (NOMS Bot)

Five architectural UX rules formalized on 2026-04-20 during the UX catalog sessions. These principles govern all new screen development and inform migration priorities for legacy screens. They complement the headless architecture and profile-v5-screens-specs catalog.

## Key Points

1. Python cron NEVER migrates to headless — cron jobs stay in Python
2. Single [Отмена/Назад] button everywhere via `buttons.back` + `icon_back` + `cmd_back`
3. Video stickers preferred for transient/push UI
4. Shared Screens: one `screen_id`, two contexts (onboarding + profile edit)
5. Skip button ONLY for "improving" fields — never for critical fields

---

## Details

### 1. Python Cron Never Migrates to Headless

Cron jobs (`reminders`, `league_cycle`, `streak_checker`, `subscription_lifecycle`, `mana_reset`) remain in Python APScheduler. They do NOT get `screen_id` entries in `ui_screens`. Rationale: cron push notifications are fire-and-forget with no interactive back navigation and no FSM state — the headless `process_user_input` / `render_screen` contract does not apply.

What IS allowed for cron: updating `ui_translations` (for notification text) and `app_constants` (for emoji). In the UX catalog, cron-push sections are marked **«⚠ legacy by design»**.

Applies to: `profile_incomplete` push, league FOMO push, streak warning, meal reminders — all stay in Python.

---

### 2. Single [Назад] / [Отмена] Button Everywhere

Universal pattern:

| Element | Value |
|---------|-------|
| Translation key | `buttons.back` = `"Назад"` |
| Icon constant | `icon_back = 🔙` |
| Callback data | `cmd_back` |
| Behavior resolver | `users.nav_stack` (JSONB, migrations 076–078) |

**Never create:** `cmd_back_to_menu`, `cmd_back_to_progress`, `[❌ Отмена]`, `[🔙 Назад в меню]`, `buttons.cancel`.

Legacy screens that still use `buttons.cancel` / `icon_cancel` → migrate at next scheduled touch.

The `cmd_back` handler pops the top frame from `users.nav_stack` and renders the previous screen. This makes "Назад" universally correct without context-specific callback naming.

---

### 3. Video Stickers for Transient / Push UI

NOMS has a set of character video stickers (Noms analysing food, thinking, breakfast reminder, etc.). Usage preference:

- **Wait indicators** (PART 15 of catalog): `🎥 [sticker: noms_thinking]` before response text
- **Cron push notifications** (PART 14): sticker preferred over plain text; format: sticker + short caption
- **Translation fallback**: `wait.*` keys in `ui_translations` for clients that cannot display stickers

In mockups stickers are annotated as: `🎥 [sticker: noms_<context>]`

Migration path: cron notifications gradually transition to "sticker + short caption" format over multiple sprints.

---

### 4. Shared Screens — One `screen_id`, Two Contexts

Input screens (`ask_weight`, `ask_age`, `ask_height`) and picker screens (`edit_goal`, `edit_activity`, `edit_training`, `edit_phenotype`, `edit_gender`, `edit_language`, `edit_country`, `edit_timezone`) are called from TWO entry points:

| Context | Entry point | Back target |
|---------|-------------|-------------|
| Onboarding | `registration_step_*` status | next onboarding step |
| Profile edit | `edit_*` callback from Settings | Settings screen |

**Implementation:** ONE row in `ui_screens` per screen. The `render_screen` RPC reads `users.nav_stack` to determine back behavior — no duplication of screen definitions. Context is passed via nav_stack frame, not via separate screen_id.

**Architectural impact:** This is the solution to picker duplication (see [[concepts/picker-unification-strategy]]). Previously the same picker existed in `02_Onboarding Response Builder` AND `04_Menu Build Ask Markup` — Shared Screens via headless eliminates this.

Mockup documentation convention: described ONCE in PART 2A of UX catalog, referenced with context-matrix in PART 2 (onboarding) and PART 3 (profile edit).

---

### 5. Skip Button — Only for "Improving" Fields

**Critical fields (NO Skip button):**

| Field | Step | Reason |
|-------|------|--------|
| gender | Step 1 | Required for macro calculations |
| age | Step 2 | Required for macro calculations |
| weight | Step 3 | Required for macro calculations |
| height | Step 4 | Required for macro calculations |
| activity_level | Step 5 | Required for macro calculations |
| training_type | Step 6 | Required for macro calculations |
| goal_type | Step 7 | Required for macro calculations |
| country | Step 10 | Required for timezone |
| timezone | Step 11 | Required for cron scheduling |

**Improving fields (Skip allowed, default applied):**

| Field | Step | Default | Translation key |
|-------|------|---------|----------------|
| goal_speed | Step 8 | `normal` | `buttons.skip` + `icon_skip` |
| phenotype | Step 9 | `standard` | `buttons.skip` + `icon_skip` |
| target_weight_kg | CANCELLED | n/a | — (anti-shaming) |

When a user skips an optional field, the default is applied silently. Skipped fields are tracked → trigger `profile_incomplete` cron push after 3 active days.

---

## Onboarding Extension (9 → 12 Steps)

The onboarding flow was redesigned to 12 steps (previously 9):

| Step | screen_id | Field | Skip | Notes |
|------|-----------|-------|------|-------|
| 1 | `registration_step_gender` | gender | ❌ | Critical |
| 2 | `registration_step_age` | age | ❌ | Critical |
| 3 | `registration_step_weight` | weight | ❌ | Critical |
| 4 | `registration_step_height` | height | ❌ | Critical |
| 5 | `registration_step_activity` | activity_level | ❌ | Critical |
| 6 | `registration_step_training` | training_type | ❌ | Critical |
| 7 | `registration_step_goal` | goal_type | ❌ | Critical |
| 8 | `registration_step_speed` | goal_speed | ✅ | NEW — default=normal |
| 9 | `registration_step_phenotype_quiz` | phenotype | ✅ | NEW — 4 questions, default=standard |
| 10 | `registration_step_country` | country | ❌ | Unchanged |
| 11 | `registration_step_timezone` | timezone | ❌ | Unchanged |

**CANCELLED:** `registration_step_target_weight` — permanently removed from onboarding AND from Profile → My Plan (confirmed 2026-04-21) because:
- Violates anti-shaming philosophy (asking for target weight implies judgment)
- Not needed for macro calculations (`calculate_user_targets` works without it)
- Drop-off risk: users may abandon onboarding when asked for a "goal weight"

**DB artifact:** `users.target_weight_kg` column stays in the database (default=0) as a harmless artifact — do NOT drop it. Future progress visualization uses delta from current weight only, no target number shown anywhere in UI.

Steps 8 and 9 are new Shared Screens — also accessible from Profile edit (`edit_goal_speed`, `edit_phenotype`).

---

## profile_incomplete Cron Push

A new cron push type triggered when users skip optional onboarding fields but remain active.

**Trigger conditions (ALL must be true):**
1. User has ≥1 food log in last 2 days (active user)
2. ≥3 days since `created_at` (registration)
3. At least one of `goal_speed` or `phenotype` is still at default AND was skipped (not explicitly set)

**Debounce:** max 1 notification per 7 days (tracked in `notification_log`)

**CTA button:** `[🎯 Доделать настройку]` → callback `cmd_my_plan`

**Translation keys** (migration 102, not yet applied × 13 langs):
- `cron_notifications.profile_incomplete_title`
- `cron_notifications.profile_incomplete_body`
- `cron_notifications.profile_incomplete_button`

**Migration 103** (not yet applied): adds `notifications_mode` column for per-type debounce tracking.

The push takes user to My Plan screen where they can fill in `goal_speed` and phenotype quiz.

---

## Stateful Business-Data UI Pattern

The same callback can render fundamentally different screens based on business data returned by RPC — without any branching in n8n.

**Canonical example: `cmd_friends_info` → Band Dashboard vs Ambassador Dashboard**

| State | Condition | Screen shown |
|-------|-----------|-------------|
| Band (Novice) | `ambassador_tier = null`, 0-4 paid referrals | Band Dashboard |
| Ambassador | `ambassador_tier = 'active'` OR `is_trainer = true` | Ambassador Dashboard with RevShare 25% |

**Implementation:**
1. `process_user_input(cmd_friends_info)` calls `get_referral_info` RPC
2. RPC returns: `ambassador_tier`, `paid_referral_count`, `ambassador_balance`
3. Dumb Renderer JS reads tier → selects layout template
4. No `if/else` or Switch nodes in n8n — all branching is in RPC response + template selection

**Pattern applicable to all "upgrade" screens:**
- `free → premium` (mana count, feature unlock)
- `band → ambassador` (RevShare dashboard)
- `basic → senior` (future)
- `trial → full` (payment CTA vs active user stats)

This keeps n8n truly "dumb" — only rendering, never deciding.

---

## Related Concepts

- [[concepts/headless-architecture]] — `process_user_input`, `ui_screens`, Shared Screens implemented here
- [[concepts/profile-v5-screens-specs]] — full 18-section UX catalog referencing these principles
- [[concepts/nav-stack-architecture]] — `cmd_back` universal navigation, nav_stack JSONB
- [[concepts/phenotype-quiz]] — shared screen for onboarding + profile edit
- [[concepts/picker-unification-strategy]] — Shared Screens is the architectural solution to picker duplication
- [[concepts/league-fomo-push]] — `profile_incomplete` follows same cron push pattern
- [[concepts/soft-delete-account]] — anti-shaming philosophy (target weight cancelled)

---

## Speed Picker UX (2026-04-21)

New `edit_speed` Shared Screen implemented as both onboarding step 8 and Profile → My Plan edit entry.

**Dynamic percentage display by goal_type:**

| Goal | Slow | Normal | Fast |
|------|------|--------|------|
| lose weight | -10% | -15% | -20% |
| gain weight | +8% | +10% | +15% |
| maintain | screen hidden entirely | | |

**Context-aware keyboard:**
- Onboarding: Skip button (default=normal) + no Back button (linear flow)
- Profile edit: Back button (returns to My Plan) + no Skip (already set)

Translation keys added in migration 108: `questions.goal_speed`, `answers.speed_slow/normal/fast`, `profile.noms_speed_intro[3]`, `profile.speed_hint`.

---

## Sources

- [[daily/2026-04-20.md]] — UX catalog sessions: 5 principles formalized, 12-step onboarding designed, profile_incomplete cron specified, Stateful Band→Ambassador pattern documented
- [[daily/2026-04-21.md]] — target_weight_kg permanent UX exclusion confirmed (onboarding + My Plan); DB column stays as artifact; Speed Picker UX with dynamic %
