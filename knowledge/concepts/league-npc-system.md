---
title: "League NPC Bot System"
aliases: [npc-bots, fake-competitors, league-bots, is_bot]
tags: [gamification, leagues, bots, engagement]
sources:
  - "daily/2026-04-08.md"
  - "daily/2026-04-09.md"
  - "daily/2026-04-13.md"
  - "daily/2026-04-16.md"
created: 2026-04-08
updated: 2026-04-16
---

# League NPC Bot System

NPC bots fill league groups to ensure competition exists even with few real users — inspired by Duolingo's approach. 25 bots with `telegram_id` from −1001 to −1025, later extended to 27 bots (telegram_id −1026, −1027) and updated with humanization features (migration 059).

## Key Points

- **Schema:** `users.is_bot = true`, `users.bot_xp_per_day INTEGER` — added in migration 042
- **Group fill:** `cron_create_league_groups` fills every group up to 20 participants (real users + bots)
- **Bot exclusions:** Bots never get promoted, never receive NomsCoins, never get notified, and are filtered from all cron RPCs with `WHERE is_bot = false`
- **XP formula v4 (migration 058):** `bot_xp_base_offset + bot_xp_per_day × days_since_monday` — Monday is not empty (offset), Sunday is highest
- **XP formula v5 (migration 059):** `base_offset(hash) + weekly_rate(seed) × days + daily_jitter(hash)` — humanized, changes each week
- **Invisible is_bot:** `is_bot` field is NOT returned in standings JSON — bots appear as real participants
- **Shadow bot:** Finds the nearest bot below the user; if gap > 40 XP → adjusts rate to `user_xp × 0.95` (min gap=10); visible only to that user

## Details

### Why NPC bots

With a small user base, league groups had only 1–2 real users, making competition meaningless. The Duolingo approach fills groups with convincing NPCs. Bots are assigned `telegram_id` values in the negative range (−1001 to −1025) so they never collide with real Telegram IDs.

Each bot has a `bot_xp_per_day` rate that determines how competitive they are. The XP is calculated on-the-fly in `get_league_standings` using `days_since_monday`, so there's no need to update the database daily.

### Bot distribution (migration 042, initial)

25 bots with varied activity levels to create a realistic spread:
- Slow bots: easy to beat at any activity level
- Medium bots: need consistent logging
- Fast bots: require effort to surpass

Further evolution of bot competitiveness and humanization happened in later migrations (046, 058, 059).

### Bot aggression upgrades (migration 046)

Elite bots upgraded: Kenji Y 75→92, Aisha N 68→85, Sofia D 58→68, Mia R 52→62, Marco V 50→58. Two ultra-bots added: Leo M (95 XP/day), Nina S (88 XP/day). Names changed from `Aisha_N` to `Aisha N` (underscore → space) to avoid Markdown parse errors in leaderboard.

### league_xp_weekly reset (migration 046)

`cron_process_league_week` had never run since launch — XP accumulated all-time (3765) rather than week-only. A one-time UPDATE recalculated `league_xp_weekly` from `xp_events` for the current week only (625 XP). `get_league_standings` v3 was updated to read `u.league_xp_weekly` instead of `lm.xp_earned` for real users.

### workflowInputs bug

The `Go to 09_League` node in 04_Menu had empty `workflowInputs {}` — sub-workflow 08.2_League received no data (undefined `telegram_id`) and silently returned nothing. Fixed by explicitly filling all required fields: `telegram_id`, `language_code`, `callback_message_id`, `translations`.

### Markdown escaping in leaderboard

Build Leaderboard Code node in 08.2_League gained an `escMd()` helper function that escapes `_*[]` characters in user/bot display names. Without this, names like `Aisha_N` caused Telegram Markdown parsing failures.

### Cron RPCs with is_bot filter

The `WHERE is_bot = false` guard was added to:
- `cron_regenerate_mana`
- `cron_reset_daily_counters`
- `cron_check_streak_breaks`
- `cron_get_reminder_candidates`
- `cron_check_subscription_expiry`

This prevents bots from consuming mana, triggering streaks, receiving reminders, or appearing in subscription checks.

### bot_xp_base_offset and formula v4 (migration 058)

**Problem:** With the original formula `bot_xp_per_day × days_since_monday`, all bots show 0 XP on Monday morning. The leaderboard looks empty and uncompetitive at the start of each week.

**Solution:** New column `bot_xp_base_offset INTEGER DEFAULT 0`. Bots are given a starting XP value representing "pre-week activity" that makes the leaderboard populated from Monday morning.

**Formula v4:**
```sql
bot_xp_base_offset + bot_xp_per_day * days_since_monday
```

Range: `bot_xp_base_offset` values from 0 to 45 XP. Monday at 08:00 UTC Leo M shows ~105 XP (base_offset=105, days=0, but see Monday drip below).

3 bots promoted to Pickle league: Leo M (170 XP/day), Kenji Y (140), Nina S (110).

### Manual cron run and cron bug fix

`cron_process_league_week` had been failing since April 6 with the error: `"UPDATE requires a WHERE clause"`. Root cause: migration 011 contained `UPDATE users SET league_xp_weekly = 0` without a WHERE clause — Supabase RLS blocked the bare UPDATE entirely (no policy matched `UPDATE` on all rows for service_role via RPC context).

Fixed in migration 042 by adding a proper WHERE condition. Manual catch-up runs performed:
```sql
SELECT cron_process_league_week('2026-04-06');  -- backfill missed week
SELECT cron_create_league_groups('2026-04-13'); -- create groups for current week
```
Result: 2 groups created, 40 participants.

### Localized league names in Build Leaderboard

Build Leaderboard Code node in 08.2_League was updated to use `league.name_X` translation keys (where X is the user's language code) instead of the English `display_name` column. This ensures the league name appears in the user's language (e.g., "Лук" for Russian users in the Onion league).

### Bot humanization and v5 formula (migration 059)

**Problem with fixed rates:** With `bot_xp_per_day = 170` for Leo M, the leaderboard is perfectly predictable. Users figure out the pattern quickly, reducing engagement.

**New columns (migration 059):**
- `bot_xp_rate_min INTEGER` — minimum daily rate
- `bot_xp_rate_max INTEGER` — maximum daily rate
- `bot_weekly_seed INTEGER` — randomized each Monday; determines weekly rate

**Rate ranges instead of fixed rates:** Leo M: 90–170 (instead of fixed 170). Each week the seed is randomized, so different bots lead in different weeks.

**Formula v5 using hashtext():**
```sql
-- weekly_rate: deterministic from seed, but changes each week
bot_xp_rate_min + 
  (hashtext(bot_weekly_seed::text) % (bot_xp_rate_max - bot_xp_rate_min + 1))::INT
    AS weekly_rate

-- daily_jitter: ±5% based on telegram_id hash, deterministic per day
(hashtext(telegram_id::text || current_date::text) % 11 - 5) AS daily_jitter

-- final XP:
base_offset + weekly_rate * days_since_monday + daily_jitter
```

`hashtext()` is PostgreSQL-native, deterministic (same seed = same result), and avoids `random()` which would change on every read.

### Six bot tiers (migration 059)

| Tier | Rate Range | Count | Description |
|------|-----------|-------|-------------|
| Slow | 12–25 XP/day | 8 | Easily beaten at any activity level |
| Medium | 25–45 XP/day | 10 | Need consistent logging |
| Fast | 40–70 XP/day | 3 | Requires effort |
| Mid-Pickle | 55–90 XP/day | 3 NEW | David K(−1019), Mia R(−1020), Chen X(−1021) |
| Elite | 90–145 XP/day | 4 | Serious competition |
| Adaptive | 90–170 XP/day | 2 | Leo M, Nina S — the top threat |

3 new bots promoted to Pickle league: David K (−1019), Mia R (−1020), Chen X (−1021). Total: 6 bots now in Pickle league.

### Monday drip mechanic

For `days_since_monday = 0` (Monday itself), using `days_since_monday` directly gives 0 XP (only base_offset). To create a "drip" effect on Monday morning, the formula uses fractional days:

```sql
CASE WHEN days_since_monday = 0 
  THEN EXTRACT(EPOCH FROM (now() - date_trunc('week', now()))) / 86400
  ELSE days_since_monday
END AS effective_days
```

Result: Leo M shows ~105 XP at 08:00 UTC Monday (8 hours = 0.33 days × 170 rate + base_offset), making the leaderboard feel active from the start of the week.

### Shadow bot mechanic

The shadow bot creates personalized competition pressure for each user:

1. Find the nearest bot in standings whose XP is **below** the current user's XP
2. If the gap between the user and that bot is > 40 XP → adjust the bot's effective XP to `user_xp × 0.95` (minimum gap = 10 XP)
3. The adjusted XP is visible **only to that user** — other users see the real XP

This ensures every user always has "someone right behind them" regardless of how many real competitors exist. The shadow bot is selected per user by the `get_league_standings` v5 RPC and the adjustment is applied in the response JSON only for that `p_telegram_id`.

### rotate_bot_weekly_seeds RPC

```sql
CREATE OR REPLACE FUNCTION rotate_bot_weekly_seeds()
RETURNS VOID AS $$
BEGIN
  UPDATE users
  SET bot_weekly_seed = (EXTRACT(EPOCH FROM now())::INT % 10000 + telegram_id::INT * 7) % 9999
  WHERE is_bot = true;
END;
$$ LANGUAGE plpgsql;
```

Called as Step 3 in `league_cycle.py` (added after migration 059):
```python
# Step 3: Rotate bot seeds for next week
await self.rpc('rotate_bot_weekly_seeds')
```

### is_new_week flag

`get_league_standings` v5 returns an `is_new_week` boolean in the response:

```json
{
  "standings": [...],
  "is_new_week": true
}
```

This flag is used by the n8n Build Leaderboard node to optionally show a "New week started!" message or highlight weekly reset. Populated as `TRUE` when `days_since_monday = 0`.

## Related Concepts

- [[concepts/xp-model]]
- [[concepts/noms-architecture]]
- [[concepts/league-fomo-push]]

### get_league_standings v6 — Bot Spikes (migration 067)

**Проблема v5:** боты росли линейно (base_offset + weekly_rate × days). Пользователи замечали предсказуемый паттерн после нескольких дней наблюдения.

**v6:** добавлен ежедневный тип активности — multiplier на основе `hashtext`:

| Тип | Множитель | Частота |
|-----|-----------|---------|
| lazy | 0.3x | ~25% дней |
| normal | 1.0x | ~40% дней |
| active | 1.4x | ~25% дней |
| spike | 1.8x | ~10% дней |

Тип дня: `hashtext(telegram_id::text || current_date::text) % 100` → диапазон → тип. Детерминированно, но непредсказуемо с точки зрения пользователя.

**`last_seen_hours_ago`** — новое поле в response `get_league_standings`. Для ботов: `hashtext(telegram_id::text || date_part('hour', now())::text) % 12` (0–11 часов, меняется каждый час). Для реальных пользователей: разница от `last_active_at`. Используется в n8n Build Leaderboard для онлайн-индикатора 🟢.

**Связь с Build Leaderboard v2:** v6 response добавил поле `stage` (тамагочи-стадия) и `last_seen_hours_ago`. Оба потребляются в [[concepts/league-ux-v2]].

## Sources

- [[daily/2026-04-08.md]] — Migration 042: initial NPC bot system with 25 bots and cron filters
- [[daily/2026-04-09.md]] — Migration 045–046: XP standings fix, league_xp_weekly reset, bot aggression upgrades, Markdown escaping, workflowInputs bug fix
- [[daily/2026-04-13.md]] — Migration 058: bot_xp_base_offset + formula v4; migration 059: bot humanization (rate_min/max/seed), 6 tiers, hashtext v5 formula, Monday drip, shadow bot, rotate_bot_weekly_seeds; manual cron run; localized league names
- [[daily/2026-04-16.md]] — Migration 067: get_league_standings v6 — daily spike multiplier (0.3x/1.0x/1.4x/1.8x), last_seen_hours_ago field; верификация Nina S vs Leo M разные паттерны
