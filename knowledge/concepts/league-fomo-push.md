---
title: "League FOMO Push and Rich League Notifications"
aliases: [fomo-push, league-fomo, sunday-push, league-results, rich-notifications]
tags: [gamification, leagues, notifications, cron, engagement]
sources:
  - "daily/2026-04-13.md"
  - "daily/2026-04-16.md"
created: 2026-04-13
updated: 2026-04-16
---

# League FOMO Push and Rich League Notifications

Sunday FOMO push notifications for league competition, and enriched weekly league result messages with XP and rank data. Implemented via migration 060, a new cron job, and updated league result translations.

## Key Points

- **`cron_get_league_fomo_candidates()`** RPC: returns users eligible for Sunday FOMO push (local Sunday, deduped via `notification_log`)
- **4 FOMO translation keys × 13 langs:** `league_fomo_leader`, `league_fomo_promote`, `league_fomo_demote`, `league_fomo_safe` with `{name}`, `{rank}`, `{gap}` placeholders
- **3 updated league result keys × 13 langs:** `league_promoted`, `league_demoted`, `league_result` now include `{xp}` and `{rank}` placeholders
- **New file `crons/league_fomo.py`:** `LeagueFomoCron(BaseCron)` — RPC candidates → per-user standings → zone detection → template fill → batch send
- **`league_cycle.py` extended:** `{xp}`, `{rank}` filled in result messages; `_load_league_stickers` function added (optional, from `bot_stickers` table)
- **Main schedule:** New job `League FOMO (Sunday)` at `:25` hourly (filter inside RPC handles Sunday-only logic)
- **`config.py`:** `NOTIFY_LEAGUE_FOMO` toggle (default `True`)

## Details

### FOMO push strategy

The Sunday push is designed to maximize league engagement in the final hours before Monday's reset. Users who might not be actively logging on Sunday receive a push notification reminding them of their competitive position and what they stand to win or lose.

Four zones are detected per user:
1. **Leader zone:** User is #1 in their group → celebrate + urgency to hold
2. **Promotion zone:** User is in top 5 (promotion spots) → stay the course
3. **Demotion zone:** User is in bottom 5 (demotion spots) → urgency to log more
4. **Safe zone:** User is in the middle → awareness + mild engagement

### cron_get_league_fomo_candidates() RPC

```sql
-- Returns users eligible for Sunday FOMO push:
-- 1. Current local time is Sunday
-- 2. Hour matches FOMO_SEND_HOUR from app_constants (typically 10-14 local time)
-- 3. Not already sent today (dedup via notification_log)
-- 4. is_bot = false (bots never notified)
-- Returns: telegram_id, language_code, display_name, timezone
```

The hour filter uses `app_constants` so the send time can be tuned without code changes. Deduplication uses `notification_log` with `notification_type = 'league_fomo'` — same pattern as other reminder types.

### crons/league_fomo.py

New cron file following the `BaseCron` pattern:

```python
class LeagueFomoCron(BaseCron):
    async def run(self):
        # Step 1: Get candidates from RPC
        candidates = await self.rpc('cron_get_league_fomo_candidates')
        
        for user in candidates:
            # Step 2: Get live standings for this user's group
            standings = await self.rpc('get_league_standings', {
                'p_telegram_id': user['telegram_id']
            })
            
            # Step 3: Detect zone (leader/promote/demote/safe)
            zone = self._detect_zone(user['telegram_id'], standings)
            
            # Step 4: Build message from translation template
            msg = self._build_fomo_message(user, standings, zone)
            
            # Step 5: Send
            await self.send_batch([{
                'telegram_id': user['telegram_id'],
                'message': msg
            }])
```

Zone detection logic:
- `rank == 1` → `league_fomo_leader`
- `rank <= 5` → `league_fomo_promote` (with `{rank}` and `{gap}` to 6th place)
- `rank > len(standings) - 5` → `league_fomo_demote` (with `{rank}` and `{gap}` to safety)
- Otherwise → `league_fomo_safe`

### Rich league result notifications (league_cycle.py)

Previously `league_promoted`, `league_demoted`, `league_result` messages had only `{name}` and league name. Updated to also include:
- `{xp}` — final XP earned this week
- `{rank}` — final rank in the group

This gives users a concrete summary of their performance: "You finished #3 with 420 XP — promoted to Avocado! 🥑"

Translation key examples (EN):
- `league_promoted`: "🎉 {name}, you're promoted! 🏆 Rank #{rank} · {xp} XP — welcome to {league}!"
- `league_demoted`: "😔 {name}, you dropped to rank #{rank} ({xp} XP). You've been moved to {league}. Bounce back next week!"
- `league_result`: "Week over, {name}! You finished #{rank} with {xp} XP. Keep going in {league}!"

### _load_league_stickers (league_cycle.py)

Optional sticker-sending after league result notifications:
```python
def _load_league_stickers(self) -> dict:
    """Load sticker file_ids from bot_stickers table. Returns {} if table doesn't exist."""
    try:
        # GET /rest/v1/bot_stickers?select=league,sticker_file_id
        ...
    except:
        return {}
```

If `bot_stickers` table exists and contains entries for league names, the cron sends a sticker after the text result. Falls back gracefully if the table is missing or empty.

### main.py schedule

```python
# League FOMO (Sunday)
scheduler.add_job(
    league_fomo_cron.run,
    'cron',
    minute=25,   # :25 to avoid crowded :00/:30 slots
    id='league_fomo'
)
```

The job runs every hour at :25. The RPC internally filters for Sunday-only candidates — on non-Sunday days, the RPC returns 0 rows and the cron exits immediately.

### config.py toggle

```python
NOTIFY_LEAGUE_FOMO = os.getenv('NOTIFY_LEAGUE_FOMO', 'true').lower() == 'true'
```

Allows disabling FOMO push without code changes, e.g., during A/B testing or debugging.

### FOMO translation keys (4 × 13 languages)

| Key | Placeholders | Description |
|-----|-------------|-------------|
| `league_fomo_leader` | `{name}`, `{xp}`, `{gap}` | User is #1, gap to 2nd place |
| `league_fomo_promote` | `{name}`, `{rank}`, `{xp}`, `{gap}` | User in top 5, gap to stay in promotion zone |
| `league_fomo_demote` | `{name}`, `{rank}`, `{xp}`, `{gap}` | User in bottom 5, gap to escape demotion |
| `league_fomo_safe` | `{name}`, `{rank}`, `{xp}` | User in safe middle zone |

All keys translated into all 13 languages: `ar, de, en, es, fa, fr, hi, id, it, pl, pt, ru, uk`.

### Midweek Push (migration 067, 2026-04-16)

Третий touchpoint вовлечённости — среда в 19:00 local time.

**`cron_get_league_midweek_candidates()` RPC:** возвращает пользователей для среднесезонного push'а:
- Текущий local день = среда (Wednesday)
- Час = 19:00 ± окно из `app_constants` (MIDWEEK_SEND_HOUR)
- Дедупликация через `notification_log` (тип `league_midweek`)

**`crons/league_midweek.py`:** `LeagueMidweekCron(BaseCron)` — аналог `league_fomo.py`. Читает standing, определяет rank, заполняет шаблон, отправляет.

**Translation key:** `league.midweek_push` × 13 языков. Плейсхолдеры: `{rank}`, `{league}`, `{name}`. Пример (RU): "Середина недели! Ты #{rank} в {league}. Не сбавляй! 🔥"

**main.py:** добавлен третий league job — `league_midweek` (каждый час в :37, RPC фильтрует по дню). Итого 3 league jobs: `league_cycle` (Пн 12:00) + `league_midweek` (Ср 19:00) + `league_fomo` (Вс). ✅ зарегистрированы на VPS.

### Расписание League Push (три touchpoint'а)

| Touchpoint | Время | Статус |
|-----------|-------|--------|
| Week Start (TODO) | Пн 10:00 local | Запланировано |
| Midweek Push | Ср 19:00 local | ✅ готово (migration 067) |
| Sunday FOMO | Вс ≈18:00 local | ✅ готово (migration 060) |

## Related Concepts

- [[concepts/league-npc-system]]
- [[concepts/xp-model]]
- [[concepts/supabase-db-patterns]]
- [[concepts/user-profile-personalization]]
- [[concepts/league-ux-v2]] — визуальные зоны повышения/понижения связаны с push-стратегией

## Sources

- [[daily/2026-04-13.md]] — Migration 060: cron_get_league_fomo_candidates RPC, 4 FOMO keys × 13 langs, 3 updated result keys; crons/league_fomo.py new file; league_cycle.py extended; main.py + config.py updated
- [[daily/2026-04-16.md]] — Migration 067: LeagueMidweekCron (crons/league_midweek.py), cron_get_league_midweek_candidates RPC, league.midweek_push × 13 langs, 3 league jobs в main.py ✅
