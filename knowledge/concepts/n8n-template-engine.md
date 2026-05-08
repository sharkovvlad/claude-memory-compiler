---
title: "n8n Template Engine"
aliases: [template-engine, icon-substitution, double-brace, icon-placeholder, double-emoji]
tags: [n8n, ui, localization, patterns]
sources:
  - "daily/2026-04-09.md"
created: 2026-04-09
updated: 2026-04-09
---

# n8n Template Engine

The Dispatcher-level substitution system that replaces `{{icon_xxx}}` and `{name}` placeholders in `ui_translations` strings before they reach sub-workflows.

## Key Points

- **Double-brace required:** Template Engine processes `{{icon_xxx}}` only — single-brace `{icon_xxx}` is treated as literal text and shown raw to the user
- **Phase 1:** `{{icon_xxx}}` → emoji from `app_constants` (e.g., `{{icon_premium}}` → 👑)
- **Phase 2:** `{name}` → `display_name` from context (`first_name → username → 'User'`)
- **Phase 3 (migration 054):** `cleanText()` — `\\n → \n` normalization, centralized in Dispatcher; removed from 5 sub-workflows
- **Double-emoji anti-pattern:** If a translation key already contains `{{icon_xxx}}`, NEVER prepend the icon from code — this produces doubled emoji
- **Python crons bypass n8n:** `reminders.py`, `league_cycle.py`, `streak_checker.py` do `.replace("{name}", display_name)` directly since they don't go through the Dispatcher

## Details

### Why double-brace

The `ui_translations` table stores strings like `"{{icon_premium}} Go PRO!"`. When inserting new translations via SQL, single-brace mistakes (`{icon_premium}`) look correct at write time but produce literal `{icon_premium}` in the bot's output. This mistake has been made multiple times. Always verify new translations use double-braces for icon placeholders.

The bug was discovered in migration 046 when `payment.plans_title` and `payment.go_premium_button` showed `{icon_premium}` literal in the UI. Fixed with an UPDATE replacing `{icon_premium}` → `{{icon_premium}}` for all 13 languages.

### Double-emoji incident (2026-04-09)

Build Profile Text code had:

```js
const btnText = (data.icon_premium || '👑') + ' ' + s.go_premium_button
```

The `s.go_premium_button` translation was `"{{icon_premium}} Премиум"`. After Phase 1 substitution, this became `"👑 Премиум"`. The code then prepended another `👑 `, producing `"👑 👑 Премиум"`. The same bug appeared in Build Shop Text.

**Fix:** use the translation key directly without prepending the icon:
```js
const btnText = s.go_premium_button  // translation already contains {{icon_premium}}
```

**General rule:** Before adding an icon prefix in code, check whether the translation key contains `{{icon_xxx}}`. If it does — don't add a prefix.

### cleanText() centralization (migration 054)

Before migration 054, every sub-workflow's Merge Data node ran `cleanText()` to convert `\\n` literal backslash-n sequences to real newlines. This was redundant work done in 5 separate workflows. Phase 3 moved this to the Dispatcher's Template Engine, so sub-workflows receive already-clean text.

## Related Concepts

- [[concepts/n8n-data-flow-patterns]]
- [[concepts/user-profile-personalization]]
- [[concepts/payment-integration]]
- [[concepts/supabase-db-patterns]]

## Sources

- [[daily/2026-04-09.md]] — Double-brace fix for `{icon_premium}` → `{{icon_premium}}` in migration 046; double-emoji bug in Profile/Shop PRO buttons; Template Engine Phase 2 (`{name}`) added
