---
title: "Fasting / Skip Meal Feature"
aliases: [skip-meal, fasting, log-fasting, cmd-skip-meal, already-fasted]
tags: [features, gamification, fasting, n8n, rpc, translations]
sources:
  - "daily/2026-04-13.md"
created: 2026-04-13
updated: 2026-04-13
---

# Fasting / Skip Meal Feature

The "Skip Meal / Fasting" feature allows users to explicitly mark a period as intentional fasting rather than forgetting to log food. Implemented via a dedicated RPC, inline button on the Add Food prompt, and 4 translation keys.

## Key Points

- **`log_fasting_meal(p_telegram_id)`** RPC: wraps `log_meal_transaction` with `input_source='fasting'`, enforces 1-per-day limit, returns `ALREADY_FASTED` on repeat
- **`icon_fasting = '🤐'`** added to `app_constants`
- **4 translation keys × 13 languages:** `progress.skip_button`, `progress.skip_confirm`, `progress.skip_already`, `progress.skip_no_mana`
- **`cmd_skip_meal`** callback on the Add Food prompt inline keyboard
- **5 new nodes in 04_Menu:** Typing Action (fasting), RPC Log Fasting, Check Fasting Result (IF), Edit Fasting Confirm, Edit Fasting Error
- **Backend was ready since Phase 1:** `log_meal_transaction` always supported `input_source='fasting'` — only the UI was missing

## Details

### log_fasting_meal RPC

```sql
CREATE OR REPLACE FUNCTION log_fasting_meal(p_telegram_id BIGINT)
RETURNS JSONB AS $$
DECLARE
  v_result JSONB;
  v_today_start TIMESTAMPTZ;
  v_today_end   TIMESTAMPTZ;
BEGIN
  -- Sargable range query for today's fasting logs
  v_today_start := date_trunc('day', now() AT TIME ZONE 'UTC');
  v_today_end   := v_today_start + interval '1 day';

  -- 1-per-day dedup check
  IF EXISTS (
    SELECT 1 FROM food_logs
    WHERE telegram_id = p_telegram_id
      AND input_source = 'fasting'
      AND consumed_at >= v_today_start
      AND consumed_at < v_today_end
  ) THEN
    RETURN jsonb_build_object('status', 'ALREADY_FASTED');
  END IF;

  -- Delegate to existing transaction function
  v_result := log_meal_transaction(
    p_telegram_id := p_telegram_id,
    p_food_name   := 'Fasting',
    p_calories    := 0,
    p_protein_g   := 0,
    p_fat_g       := 0,
    p_carbs_g     := 0,
    p_input_source:= 'fasting'
  );

  RETURN v_result;
END;
$$ LANGUAGE plpgsql;
```

Key design decisions:
- **Sargable range query** (not `DATE(consumed_at) = CURRENT_DATE`) — uses the `idx_food_logs_user_consumed` index from migration 052
- **Delegates to `log_meal_transaction`** — reuses mana check, XP award, soft cap logic
- **Returns `ALREADY_FASTED`** — distinct from `log_meal_transaction`'s `NO_MANA` error, allowing UI to show the correct message

### Add Food prompt conversion

The `Send Add Food Prompt` node in 04_Menu was converted from a Telegram `sendMessage` node to an HTTP Request node so that an `inline_keyboard` could be attached. This is required because n8n Telegram nodes do not support arbitrary keyboard JSON.

New keyboard:
```json
{
  "inline_keyboard": [[
    { "text": "🤐 {{icon_fasting}} Skip / Fasting", "callback_data": "cmd_skip_meal" }
  ]]
}
```

Note: The emoji string `🤐` was embedded using the PostgreSQL `chr()` trick to avoid n8n double-brace `{{ }}` collision with Template Engine substitution. Direct emoji literals in string concatenation inside n8n Code nodes can conflict with the `{{...}}` template syntax.

### chr() trick for emoji in n8n SQL

When building dynamic text in n8n Code nodes that will be passed to Telegram, emoji literals can collide with n8n's template engine `{{emoji}}` syntax if the emoji happens to contain characters that look like braces. The safe pattern:

```javascript
// Instead of embedding emoji directly in a string with {{ }}:
const skipText = `${chr(129296)} Skip`; // chr(129296) = 🤐

// Or pre-escape:
const skipText = "🤐 Skip"; // only safe if no {{ }} in same expression
```

This issue specifically arises when the string is constructed inside a Code node and contains both emoji and `{{variable}}` template expressions.

### n8n flow: 5 new nodes

04_Menu grew from 90 to 95 nodes. New nodes added to the `cmd_skip_meal` branch:

1. **Typing Action (fasting)** — parallel dead-end: `POST sendChatAction {action: "typing"}` — fires immediately when `cmd_skip_meal` is detected
2. **RPC Log Fasting** — HTTP Request: `POST /rest/v1/rpc/log_fasting_meal` with `{ "p_telegram_id": telegram_id }`
3. **Check Fasting Result** — IF node: `$json.status === 'ALREADY_FASTED'` → True branch = error path, False = success
4. **Edit Fasting Confirm** — HTTP Request: `editMessageText` with `progress.skip_confirm` translation + `icon_fasting`
5. **Edit Fasting Error** — HTTP Request: `editMessageText` with either `progress.skip_already` (already fasted today) or `progress.skip_no_mana` (mana depleted) depending on the RPC status

### Translation keys (4 × 13 languages)

| Key | Usage | Example (EN) |
|-----|-------|-------------|
| `progress.skip_button` | Inline keyboard button label | "🤐 Skip Meal" |
| `progress.skip_confirm` | Confirmation after successful fasting log | "🤐 Fasting logged! Rest well." |
| `progress.skip_already` | When user tries to log fasting a second time today | "You already marked fasting today." |
| `progress.skip_no_mana` | When mana is depleted | "No mana left. Come back tomorrow!" |

### Backend history

The `log_meal_transaction` function has always accepted `input_source='fasting'` — this was part of the original Phase 1 schema design. The feature was dormant because no UI exposed it. Migration 057 added `log_fasting_meal` as a convenience wrapper (enforcing the 1-per-day limit) and the n8n changes added the inline button entry point.

## Related Concepts

- [[concepts/supabase-db-patterns]]
- [[concepts/n8n-stateful-ui]]
- [[concepts/xp-model]]

## Sources

- [[daily/2026-04-13.md]] — Full implementation: log_fasting_meal RPC, icon_fasting constant, 4 translation keys × 13 langs, cmd_skip_meal inline button, 5 new 04_Menu nodes, chr() trick
