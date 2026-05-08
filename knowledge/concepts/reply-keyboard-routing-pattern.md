---
title: "Reply-Keyboard vs Inline Callback Routing — Two-Path Architecture"
aliases: [reply-routing, reply-button-key, reply-keyboard-routing, two-path-routing]
tags: [n8n, routing, architecture, reply-keyboard, inline-callback, dispatcher]
sources:
  - "daily/2026-04-23.md"
created: 2026-04-23
updated: 2026-04-23
---

# Reply-Keyboard vs Inline Callback Routing

NOMS 04_Menu_v3 has **two completely separate routing pipelines** for reply-keyboard clicks vs inline callback clicks. Discovered during Stats screen Phase 3A migration (Session 11). Any feature wired only to one pipeline silently fails for the other.

## Two Paths

### Path A — Reply-Keyboard (e.g. "☀️ Мой день" button)

```
User taps reply-button "☀️ Мой день"
    → 01_Dispatcher
    → Is Reply for 04 check (true)
    → Sets field: reply_button_key = 'stats'
    → Go to 04_Menu_v3
        → Route Action Switch
            → output 'stats'
            → render_screen(stats_main)
```

Key field: `reply_button_key` — a string set in the Dispatcher before forwarding to 04_Menu_v3. The Route Action Switch in 04_Menu_v3 reads this field to dispatch to the right handler.

### Path B — Inline Callback (e.g. `cmd_get_stats` from an inline button)

```
User taps inline button [cmd_get_stats]
    → 01_Dispatcher
    → Route Classifier (JS code node)
    → Action Router (Switch node)
    → Go to 04_Menu_v3 (or legacy 04_Menu)
```

Key field: `callback_data` — routed by Route Classifier directly. Does NOT go through `Is Reply for 04` / `reply_button_key` logic.

## Fix Template (for any new screen)

To properly wire a screen that can be reached from BOTH a reply-keyboard button AND an inline callback:

### Step 1 — Dispatcher: add `reply_button_key` mapping

In 01_Dispatcher, find the section that sets `reply_button_key`. Add a mapping for the text values of the reply button in all languages:

```javascript
// 01_Dispatcher Route Classifier (JS code node)
const replyButtonMap = {
    // Russian
    'Мой день': 'stats',
    '☀️ Мой день': 'stats',
    // English
    'My day': 'stats',
    // ... all 13 language variants
};
```

### Step 2 — 04_Menu_v3: add Route Action output

In 04_Menu_v3, find the `Route Action` Switch node. Add a new output rule:

```
Output name: 'stats'
Condition: reply_button_key === 'stats'
```

Connect that output to `render_screen(stats_main)` node (or whichever handler).

### Step 3 — 04_Menu_v3: also handle inline callback

If the screen is also reachable via inline callback (e.g. `cmd_get_stats`), ensure the Route Classifier in 01_Dispatcher routes it to 04_Menu_v3 with the appropriate action, and that 04_Menu_v3 handles it separately from `reply_button_key`.

## Why Two Paths Exist

- **Reply-keyboard** buttons send plain text messages ("☀️ Мой день"), not structured callbacks. There is no `callback_data` field — the Dispatcher must match text → key.
- **Inline keyboard** buttons send structured `callback_query` with `callback_data` (e.g. `cmd_get_stats`). These go through the Route Classifier directly.

The `Is Reply for 04` check in Dispatcher gates the reply path. If a text message matches a known reply-button label → it's forwarded to 04_Menu_v3 with `reply_button_key` set. Otherwise it goes to the normal message handler.

## Current Mapping (as of 2026-04-23)

| reply_button_key | Triggers | Handler |
|-----------------|----------|---------|
| `profile` | "Профиль" + locale translations | `render_screen(profile_main)` |
| `stats` | "Мой день", "☀️ Мой день" + locale translations | `render_screen(stats_main)` |
| _(progress)_ | "Прогресс" + locale translations | legacy 04_Menu (not yet migrated) |
| _(add_food)_ | AI food text/photo | AI flow |

## Gotcha: Adding only one path = silent failure

If you add a screen to only one path:
- **Only inline callback:** reply-button tap does nothing (or falls through to wrong handler)
- **Only reply path:** inline `cmd_get_stats` from keyboard button does nothing

Both paths must be wired simultaneously when deploying a screen that can be reached from either interaction type.

## Related

- [[concepts/headless-architecture]] — Headless Architecture context
- [[concepts/stats-main-headless]] — Phase 3A: first use of this pattern
- [[concepts/dispatcher-callback-pipeline]] — Route Classifier internals
- [[concepts/n8n-data-flow-patterns]] — general n8n flow patterns
