---
title: "Day Summary UX (☀️ Мой день)"
aliases: [my-day, stats, get-day-summary, progress-bar, build-stats-text]
tags: [ux, stats, n8n, gamification, rpc]
sources:
  - "daily/2026-04-09.md"
  - "daily/2026-04-10.md"
created: 2026-04-09
updated: 2026-04-10
---

# Day Summary UX (☀️ Мой день)

The main stats screen showing daily nutrition progress, XP, streak, and meal history. Accessed via the "☀️ Мой день" reply keyboard button.

## Key Points

- **`get_day_summary` RPC** returns calories/macros consumed + personalized targets, meal list, `xp_today` (SUM from xp_events), `streak_current` — all in one call, all queries sargable
- **Progress bar:** `█░` blocks (10 blocks total, configurable via `app_constants.stats_bar_blocks`) visualizes calorie progress at a glance
- **Macro status icons:** blank (<30% target), `✅` (30–85%), `⚠️` (85–110%), `🔴` (>110%) — all thresholds stored in `app_constants`, never hardcoded in JS
- **Rule-based insight:** Priority chain of localized Sassy Sage messages — sourced from `ui_translations report.insight_*` keys (8 keys × 13 languages)
- **Expandable blockquote:** `<blockquote expandable>` shows meal history in reverse chronological order; requires `parse_mode: HTML` on the Edit Stats node
- **Typing indicator:** `sendChatAction(typing)` fires as parallel branch from Menu Router before any RPC call — user sees "печатает..." immediately on button tap

## Details

### RPC evolution

**v1 (original):** Only returned calories and macro totals — no XP, no streak, no insight data.

**v2 (migration 050):** Added `xp_today` (SUM of xp_events for today in user's timezone) and `streak_current` (from users table).

**v3 (migration 055):** Added personalized macro targets (`target_protein_g`, `target_fat_g`, `target_carbs_g`) from users table, computed by `calculate_user_targets` RPC based on `training_type` and `phenotype`. Macros now display as `actual/target g` instead of a fixed percentage split.

### Sargability fix (migration 053)

After adding food_logs performance indexes (migration 052), PostgreSQL still couldn't use them because `get_day_summary` used `DATE(created_at AT TIME ZONE 'UTC') = CURRENT_DATE` — a non-sargable expression that wraps the column in a function, preventing index use.

Migration 053 rewrote all 4 internal queries to use range conditions:
```sql
consumed_at >= v_day_start AND consumed_at < v_day_end
```
Day boundaries are computed once in `DECLARE`, then reused. This makes all queries eligible for index scans on `idx_food_logs_user_consumed`. The xp_events query uses `created_at` with `idx_xp_events_user_date` (which already existed).

### Build Stats Text versions

**v3.0 (2026-04-09):** Complete rewrite — progress bar, macro rows with status icons, rule-based Sassy Sage insight, expandable blockquote meal history, streak + XP footer.

**v3.1 (2026-04-10):** Removed `📉` icon (confusing at 0% = morning with no meals), added fallback `streak_label` ('Стрик' → 'Streak'). Macro status: blank for <30% instead of a misleading down-arrow.

**v3.2 (2026-04-10):** Single-line header (`📊 Мой день  ▫️ 2026-04-10 🕐 15:50`); XP footer with localized label (`🌟 +25 XP за сегодня`); mana display for free users (`🧪 Мана: 1/2`), hidden for premium users; localized `report.xp_today_label` and `report.mana_label` keys added to `ui_translations`.

**v4 (migration 055, 2026-04-10):** Macros display as `actual/personalTarget g` using values from `get_day_summary` v3. Targets now user-specific (e.g., 120g protein for sedentary user vs 150g for strength trainer).

### Macro threshold constants

Stored in `app_constants` (not hardcoded in JS):

| Key | Value | Meaning |
|-----|-------|---------|
| `macro_threshold_ok_pct` | 30 | Below this = no status icon |
| `macro_threshold_warn_pct` | 85 | Above this = ⚠️ |
| `macro_threshold_over_pct` | 110 | Above this = 🔴 |
| `stats_bar_blocks` | 10 | Bar width in characters |

### Insight priority chain

The insight system selects one message from a priority-ranked chain based on the user's data state. All messages come from `ui_translations` with keys like `report.insight_over_calories`, `report.insight_low_protein`, `report.insight_no_meals`, etc. Falls back to English if translation key is missing for a language.

### is_registered bug

The status `edit_activity` was not in the `REGISTERED_STATUSES` whitelist in the Route Classifier. Users in this state saw a CTA/onboarding prompt instead of [Исправить/Удалить] buttons after logging food. Fixed by inverting the logic to use `ONBOARDING_STATUSES` as an exclusion list rather than `REGISTERED_STATUSES` as an inclusion list. Also: DB reset `status='edit_activity'` → `'registered'` for the affected user.

## Related Concepts

- [[concepts/xp-model]]
- [[concepts/supabase-db-patterns]]
- [[concepts/n8n-stateful-ui]]
- [[concepts/n8n-template-engine]]
- [[concepts/personalized-macro-split]]
- [[concepts/n8n-performance-optimization]]

## Sources

- [[daily/2026-04-09.md]] — Migration 050 + Build Stats Text v3.0: xp_today and streak_current in RPC, progress bar, Sassy Sage insight system, expandable blockquote
- [[daily/2026-04-10.md]] — Migration 053 (sargability fix), Build Stats Text v3.1/v3.2/v4: personalized macro targets, macro threshold constants in app_constants, mana display, XP footer, typing indicator, is_registered bugfix
