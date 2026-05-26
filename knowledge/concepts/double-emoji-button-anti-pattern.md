---
title: "Double Emoji Anti-Pattern — emoji prefix in i18n value + icon_const_key = double render"
aliases: [double-emoji, button-icon-double-prefix, icon-vs-value-prefix]
tags: [ux, i18n, anti-pattern, copywriter, button-rendering, lessons-learned]
sources:
  - "CLAUDE.md §Архитектурные принципы #2 — Запрет хардкода (existing rule)"
  - "daily/2026-05-26.md (mig 360 recovery surfaced 19 keys this way)"
created: 2026-05-26
status: active
---

# Double Emoji Button Rendering

> **TL;DR.** If a `ui_screen_buttons` row has `icon_const_key` set (e.g. `icon_settings`), the button's `text_key` value in `ui_translations` must NOT have an emoji prefix. The Python renderer prepends `constants[icon_const_key] + ' '` automatically. Including emoji in the i18n value too → double emoji like `⚙️ ⚙️ Настройки`.

## Existing CLAUDE.md rule (§Архитектурные принципы #2)

> «**Двойные эмодзи:** если ключ перевода содержит `{{icon_xxx}}`, **не добавлять** prefix `icon_xxx + ' '` из кода.»

This concept doc generalizes the rule: **same principle applies for `icon_const_key` on buttons.** If button has `icon_const_key` set, the renderer adds emoji; the translation value must be a plain text label.

## How rendering composes (Python `services/template_engine.py`)

```
final_button_label = (
    constants[btn.icon_const_key] + ' '   # ← outer prefix (if set)
    + resolved_translation_value          # ← inner; must NOT start with emoji
)
```

If the translation value is `⚙️ Настройки` and `icon_const_key='icon_settings'` (resolves to `⚙️`), the user sees `⚙️ ⚙️ Настройки`.

## Detection / inventory query

```sql
-- Find buttons where icon_const_key is set
SELECT DISTINCT split_part(text_key,'.',2) AS key, icon_const_key
  FROM ui_screen_buttons
 WHERE text_key LIKE 'buttons.%' AND icon_const_key IS NOT NULL
 ORDER BY key;
```

For each (key, icon_const_key) pair: check the translation values for emoji prefix:
```sql
SELECT lang_code, content #>> '{buttons,<key>}'
  FROM ui_translations
 WHERE content #>> '{buttons,<key>}' ~ '^[\U0001F000-\U0001FFFF]';
```

If non-empty → strip emoji from values.

## Strip query (idempotent recovery)

```python
import re
emoji_prefix = re.compile(r'^[\U0001F000-\U0001FFFF⌀-➿︀-️]+\s*')

for lang in langs:
    for key in keys_with_icon:
        cur.execute("SELECT content #>> %s FROM ui_translations WHERE lang_code=%s",
                    ('{buttons,'+key+'}', lang))
        val = cur.fetchone()[0]
        if val and emoji_prefix.match(val):
            new_val = emoji_prefix.sub('', val)
            cur.execute("UPDATE ui_translations SET content = jsonb_set(content, %s, to_jsonb(%s::text)) WHERE lang_code=%s",
                        ('{buttons,'+key+'}', new_val, lang))
```

## When emoji IS allowed in the value

Three cases where emoji-in-value is correct:
1. **Button has NO `icon_const_key`.** No prepend happens, value carries the emoji.
2. **Reply-keyboard root buttons.** These often use emoji-in-value as visual identity (e.g. `🚀 Прогресс`).
3. **Data-rich button labels with placeholders.** Example: `🤰 Беременность: {pregnancy_display}` — emoji is part of the labelled stat, not redundant with icon.

## Inventory bookmark (2026-05-26 audit)

19 keys had `icon_const_key` set AND emoji prefix in value (RU + 12 other langs, all stripped in mig 360 post-fix):

```
confirm_delete, confirm_payout_action, confirm_yes_buy, confirm_yes_phone,
delete_account, done, edit_last, go_pro_unlimited, help, language,
manage_subscription, my_plan, notifications, personal_metrics, settings,
show_meals, start, support, update_weight
```

7 keys with NO `icon_const_key` (emoji-in-value is correct):
```
women_health, cycle_state, cycle_state_active, cycle_state_locked,
pregnancy_state, lactation_state, recharge_mana, safety_pill
```

## Common reason this anti-pattern appears

Agents hand-crafting i18n values for new buttons often default to "make it visual" by adding emoji. This works when no `icon_const_key` exists yet. But when later someone wires `icon_const_key` on the button without checking translation values, the double-render emerges silently.

**Rule of thumb for copywriter subagents:** ask «does this button have `icon_const_key` set?» before adding emoji to the label. Default to bare text — icon is the renderer's job.

## Related concepts

- [[copywriter-playbook]] — i18n workflow, references this rule
- [[ui-translations-bulk-update-recipe]] — applies the strip pattern
- CLAUDE.md §Архитектурные принципы #2 — original rule statement (n8n-era `{{icon_xxx}}` syntax)
