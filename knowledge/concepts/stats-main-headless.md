---
title: "Stats Main Screen — Headless Phase 3A (Migrations 122–124)"
aliases: [stats-headless, stats-main, phase-3a, get_daily_stats_rpc, report-translations]
tags: [headless, stats, migration, phase-3a, translations, rpc]
sources:
  - "daily/2026-04-23.md"
created: 2026-04-23
updated: 2026-06-05
status: "DEPLOYED — Migration 124 canonical + migration 125 conditional edit button (Spec §6.6)"
---

# Stats Main Screen — Headless Phase 3A

First screen migrated to Headless Architecture outside of Profile v5. "Мой день" (Stats/My Day) screen now served from `ui_screens.stats_main` via `get_daily_stats_rpc` RPC. Latency p50=72.7ms, p95=81.9ms.

**⚠️ Migration 124 is the canonical version.** Migrations 122 and 123 were intermediate steps — migration 124 rewrote the RPC, template, and button set. The final RPC name is `get_daily_stats_rpc` (not `get_stats_business_data`).

## What Changed

### Migration 122 — `get_stats_business_data` + stats_main screen (intermediate)

**RPC:** `get_stats_business_data(p_telegram_id BIGINT) → JSONB`

Wrapper pattern: delegates entirely to the existing `get_day_summary` RPC, then enriches with `v_user_context` fields. Seeded `ui_screens.stats_main` with 3 buttons (add_food, history, edit_last) and `stats.*` × 13 langs.

**⚠️ Superseded by migration 124.** RPC was renamed and rewritten; this version is no longer in use.

### Migration 123 — `report.*` translation keys gap fix

**Root cause:** Legacy n8n stats screen had `report.*` translation strings embedded directly in JS code nodes — not stored as separate keys in `ui_translations`. When migrating to headless `{tr:report.*}` placeholders, those keys didn't exist in the table.

**Symptom:** User saw literal `{tr:report.unit_kcal}`, `{tr:report.unit_g}`, `{tr:report.streak_label}` in the rendered stats screen.

**Fix:** Migration 123 added 15 `report.*` keys + 5 insight keys × 13 languages (195+ inserts) using `jsonb_set` deep-merge pattern per NOMS convention.

**Keys added:**
- `report.unit_kcal`, `report.unit_g`, `report.unit_per_100g`
- `report.streak_label`, `report.no_streak`
- `report.status_deficit`, `report.status_surplus`, `report.status_maintain`
- `report.meals_header`, `report.no_meals_today`
- 5 insight keys: `report.insight_deficit`, `report.insight_surplus`, etc.

> **Note:** Migration 123 was also repurposed to add the `process_user_input` fast-path for `cmd_get_stats → stats_main`. See supabase-db-patterns for the split.

### Migration 124 — Full Stats Rewrite (Spec §25 Aligned) — CANONICAL

**File:** `migrations/124_stats_rewrite_spec_aligned.sql` (408 lines)

Root cause for the rewrite: migration 122 had two fatal bugs found only after apply (double-nested `template_vars` + `{tr:}` inside `{var}`), and the screen didn't match `profile-v5-screens-specs.md §25`.

**RPC:** `get_daily_stats_rpc(p_telegram_id BIGINT) → JSONB`

Returns 19 FLAT top-level placeholder fields — no nesting, no `template_vars` wrapper:

```sql
RETURN jsonb_build_object(
    'calories_consumed',  v_cal_consumed,
    'calories_target',    v_cal_target,
    'calories_pct',       v_cal_pct,
    'progress_bar',       ...,  -- filled from app_constants.progress_fill/empty × blocks
    'p_status',           ...,  -- ✅ or ⚠️ via CASE on macro_threshold_* from app_constants
    'f_status',           ...,
    'c_status',           ...,
    'meals_list_formatted', ..., -- string_agg with row_number(), unit_kcal eagerly resolved
    'no_meals_yet',       ...,  -- resolved from ui_translations per user language
    'current_date',       to_char(timezone(u.timezone, now()), 'DD.MM.YYYY'),
    'current_time',       to_char(timezone(u.timezone, now()), 'HH24:MI'),
    -- ... streak, xp, insight_text, display_name, etc.
);
```

**Key design choices:**

| Feature | Implementation |
|---------|---------------|
| Светофоры (p/f/c_status) | CASE: `< macro_threshold_low` → ⚠️, else ✅. Thresholds from `app_constants.macro_threshold_*` (no hardcodes) |
| meals_list_formatted | `string_agg` + `row_number()` with `unit_kcal` eagerly resolved from `ui_translations` per user language |
| `{tr:}` inside `{var}` | FORBIDDEN — RPC pre-resolves all translation-embedded strings. See [[concepts/dumb-renderer-interpolation-gotchas]] |
| Stats template | `stats.main_text` × 13 langs — single universal template with blockquote expandable meals list |
| One button | `[✏️ Исправить]` with `visible_condition` on meals > 0 |
| Zero hardcodes | All emoji from `app_constants`, all strings from `ui_translations`, all thresholds from `app_constants` |

**Also in migration 124:**
- `DROP FUNCTION get_stats_business_data` (replaces with `get_daily_stats_rpc`)
- Updated `ui_screens.stats_main.business_data_rpc` → `get_daily_stats_rpc`
- Replaced 3 buttons → 1 button `edit_last` with `visible_condition`

**Verification on user 417002669:**

```
calories 1190/2483 (48%), progress_bar ▓▓▓▓▓░░░░░
p/f/c: 47⚠️/54✅/142✅ г
date 23.04.2026, time 16:29 (Europe/Madrid)
streak 18 дн, xp 90
meals_list: "1. 08:08 — Оладушки, Кофе с молоком (320 ккал)\n2. 12:26 — Шоколад, Борщ (870 ккал)"
insight: report.insight_eating_little (<50% calories)
p95 latency: 81.9ms ✅
```

## Adversarial Review — Pre-Apply Catches

Three blockers caught before apply of migration 122:

| Blocker | What was wrong | Fix |
|---------|---------------|-----|
| Hardcoded `💬` emoji | Literal emoji in template string | Replace with `{{icon_speech}}` |
| Hardcoded `⭐` emoji | Literal emoji in template string | Replace with `{{icon_stars}}` |
| `validation_rules NULL` | `ui_screens.validation_rules` is `JSONB NOT NULL` with default `'{}'::jsonb` | Add explicit `'{}'::jsonb` value |

**Pattern:** External AI generates SQL → adversarial review (subagent) → dry-run `BEGIN;...ROLLBACK;` → apply. Three blockers caught before touching prod proves this protocol's ROI.

## Reply-Keyboard Routing Discovery

**Critical finding during Phase 3A:** Reply-keyboard clicks ("☀️ Мой день") go through a completely different pipeline from inline callbacks.

See dedicated article: [[concepts/reply-keyboard-routing-pattern]]

**Fix required two separate changes:**
1. **01_Dispatcher:** Add `reply_button_key='stats'` mapping for "Мой день" text variants (all 13 language versions)
2. **04_Menu_v3 Route Action Switch:** Add `stats` output → connected to `render_screen(stats_main)` node

## Latency Benchmarks

| RPC call | p50 (ms) | p95 (ms) | Статус |
|----------|----------|----------|--------|
| `render_screen(stats_main)` via migration 122 | 72.7 | 82.3 | — (intermediate) |
| `render_screen(stats_main)` via migration 124 | ~72 | 81.9 | ✅ well under 500ms threshold |

Comparable to Profile v5 pilot benchmarks (p50=80-95ms).

## Translation Gap Pattern (Anti-pattern to watch for)

When migrating **any** legacy n8n screen to headless `{tr:...}` placeholders:

1. Audit ALL strings currently rendered in the n8n JS code nodes
2. For each string: check if it exists in `ui_translations` with a proper key
3. Strings hardcoded in JS → **must be added to `ui_translations`** before the headless version goes live

Legacy n8n screens often embed translation strings in JS without storing them as separate keys, because the old system built strings directly in code nodes. The headless system requires every string to be addressable via `{tr:section.key}`.

## Migration 125 — Conditional Edit Button (Spec §6.6 Aligned)

**File:** `migrations/125_stats_main_edit_routes_to_meals_list.sql` (95 LOC)

**Problem:** Button `[✏️ Исправить → cmd_edit_last]` always opened edit for the LAST meal. When user had ≥2 meals on Stats screen, they should see a meal list to select which to edit (spec §6.6 Макет 6.6).

**Fix (SQL-only, no n8n PUT):** Split single button into two mutually-exclusive buttons:

| `visible_condition` | `callback_data` | col_index | Behavior |
|---------------------|----------------|-----------|---------|
| `meals_today = 1` | `cmd_edit_last` | 0 | Direct edit (no ambiguity) |
| `meals_today >= 2` | `cmd_show_meals` | 1 | List → select → detail → edit |
| `meals_today = 0` | (both hidden) | — | No edit available |

Both buttons at `row_index=0`. UNIQUE constraint `(screen_id, row_index, col_index)` required different `col_index` values (0 and 1). Only one is visible at runtime — Telegram renders as a single button with no empty slots.

`cmd_show_meals` routes to legacy `04.2_Edit_StatsDaily` which already had full meal list flow (`get_meals_today` → `Build List Message` → `cmd_view_meal_{id}` → detail → `cmd_start_edit_{id}`). No 04.2 or 04_Menu_v3 changes required.

**Note:** `food_log_result` buttons (`[✏️ Исправить → cmd_edit_last]`) were intentionally NOT changed — freshly logged meal = last meal, no ambiguity.

**Pattern for future:** DELETE + INSERT idempotent pattern ensures migration can be reapplied safely.

## Deferred Items (Iteration 2+)

| Item | Status |
|------|--------|
| 04.2_Edit_StatsDaily decommission | Deferred (still handles legacy flow) |
| Phase 3A continuation: progress_main / quests / league / friends / shop | ✅ DONE — see [[concepts/progress-hub-headless]] |

## Root Cause Deep-Dives

### Double-nested template_vars (Migration 124 fix)

Migration 122's RPC returned `{'template_vars': {...}}` as the top-level key. `render_screen` then wrapped business_data into `telegram_ui.template_vars` — producing `template_vars.template_vars.calories_consumed`. Dumb Renderer looks for `{calories_consumed}` (flat), found nothing → all `{var}` showed blank.

**Rule:** RPC returns FLAT top-level fields. `render_screen` handles the wrapping. Never wrap in `template_vars` inside the RPC.

### `{tr:}` inside `{var}` not resolved (Migration 124 fix)

`(320 {tr:report.unit_kcal})` appeared literal in meals_list because the Dumb Renderer processes passes sequentially: multi-pass loop for `{tr:}` and `{{const}}` exits first, then `{var}` is substituted once outside the loop. Any `{tr:}` tokens inside a `{var}` value are never re-processed.

**Rule:** RPC must eagerly resolve all translation-embedded strings (e.g., `unit_kcal`) from `ui_translations` per user language, with fallback to `en` + `RAISE EXCEPTION` if the key is missing.

See: [[concepts/dumb-renderer-interpolation-gotchas]]

## File References

| File | Purpose |
|------|---------|
| `migrations/122_stats_main_headless.sql` | Initial `get_stats_business_data` RPC + stats_main seed + `stats.*` keys (intermediate) |
| `migrations/123_stats_report_translations.sql` | `report.*` + insight keys × 13 langs + `cmd_get_stats` fast-path in process_user_input |
| `migrations/124_stats_rewrite_spec_aligned.sql` | **Canonical**: `get_daily_stats_rpc` FLAT + template + 1 button + светофоры + meals_list |
| `.claude/specs/migration_122_stats_main_spec.md` | Spec written before migration 122 (partially outdated post-124) |
| `.claude/specs/migration_124_stats_rewrite_spec.md` | Spec for migration 124 rewrite |

## Related

- [[concepts/headless-architecture]] — overall headless architecture
- [[concepts/reply-keyboard-routing-pattern]] — two-path routing (reply vs inline)
- [[concepts/adversarial-review-protocol]] — pre-apply review process
- [[concepts/headless-template-substitution]] — `{tr:...}` placeholder resolution
- [[concepts/supabase-db-patterns]] — migrations 122-123 entry

## Migration 467 — БРИФ E: Ж/У диапазоны + направленный статус-эмодзи (2026-06-05)

«Мой день» теперь показывает жир/углеводы как **коридор «79—105 г»** (em-dash) со статус-эмодзи по направлению, а не одиночный таргет с бинарным ✅/⚠️.

**Поведение:**
- **Ж/У:** в коридоре [min;max] → ✅ · ниже → ⬆️ (утром до cutoff скрыт) · выше → ⬇️ · выше +`macro_over_alarm_pct`% (15) → ⚠️.
- **Белок:** нет коридора (цель + научный потолок). <`protein_target_floor_pct`% (90) цели → ⬆️ · ≤потолок → ✅ · >потолок → ⬇️ · >потолок+15% → ⚠️. Закрывает «съел 300г белка — молчок».
- Утренний gate (mig 368) сохранён, **cutoff 15→12** (`macro_warn_hour_cutoff`, планировать обед). Эмодзи нейтральные (`icon_macro_under` ⬆️ / `icon_macro_over` ⬇️ / `icon_warning` ⚠️ / `icon_check` ✅).

**🔑 Архитектура — 3-RPC цепочка (важно понимать поток данных):**
```
calculate_user_targets  → СОХРАНЯЕТ в users: target_{fat,carbs}_{min,max}_g (mig 462) + target_protein_max_g (mig 467 потолок Helms)
        ↓ (users columns, RAW v15)
get_day_summary         → читает RAW колонки, отдаёт ADJUSTED коридоры: min/max × (1 + lifestyle_delta_pct/100)
                          ТА ЖЕ %-дельта, что и точечные таргеты (luteal/сон/стресс) → коридор консистентен с целью
        ↓ (v_ds JSON)
get_daily_stats_rpc     → коридор-токены under|in_range|over|over_much + range-строки 'target_f_range'/'target_c_range'
        ↓ (business_data, полный merge в template_vars)
render_screen → stats.main_text (×13: {target_f}→{target_f_range}, {target_c}→{target_c_range}; белок {target_p} без изменений)
        ↓
Python _maybe_suppress_macro_warn_under_cutoff → гасит токен 'under' до cutoff (только презентация, time-dependent → не в SQL для cache-idempotency)
```

**Durable-уроки:**
- **Коридор масштабируется lifestyle-дельтой в get_day_summary**, не берётся сырым — иначе у premium-юзера с luteal/сон/стресс коррекцией коридор разошёлся бы с отображаемой целью. Точка и границы двигаются одной %-дельтой.
- **Потолок белка для алярма = научный потолок из calc** (Helms 3.1 г/кг FFM / 2.5 ref), сохранён в `users.target_protein_max_g`. Не выдуманный множитель. Нормальный перебор (180-200) = ✅, реальный избыток (300) = ⚠️.
- **render_screen делает полный merge** `jsonb_build_object(...) || business_data` → новые поля RPC доходят до template без whitelist.
- **Python-гейт реагирует ТОЛЬКО на токен 'under'** — расширение словаря (ok→in_range, +over_much) его не ломает; нужен был только сдвиг cutoff (через app_constants, не код).
- Schema: `ui_translations` = headless JSONB (`content` per lang_code), не key-row. Правка шаблона — `jsonb_set(content,'{stats,main_text}', replace(...))` по всем langs сразу.

Verify: 4 сценария токенов в транзакции + render_screen реально отдаёт 'target_f_range' с em-dash. p95 46.8ms (VPS). PR #338, daily 2026-06-05.
