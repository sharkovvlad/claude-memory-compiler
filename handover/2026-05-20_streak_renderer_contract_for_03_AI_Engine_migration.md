# Handover для агента 03_AI_Engine n8n→Python migration

> **Дата:** 2026-05-20.
> **Создан:** агентом mig 285 + 286.
> **Адресат:** агент, который сейчас планирует миграцию n8n `03_AI_Engine.json` в Python.
> **Цель:** дать тебе stable contract по streak food-log composition, чтобы ты решил backward-compat vs structured.

---

## TL;DR

`log_meal_transaction` RPC теперь exposes **два** path'а для streak feedback:

1. **Backward-compat (working today):** `rpc.streak_message: text` — уже локализованная строка типа `"🏆 Серия: 3 дн."` (рендерится через ui_translations внутри RPC по `v_user.language_code`).
2. **Forward-clean (recommended для Python):** `rpc.streak_event: enum + rpc.streak: int` — структурные данные. Renderer сам делает SELECT translation + REPLACE.

Если ты выберешь **path 2** (recommended), вот тебе ready-to-use spec.

---

## Контекст (что произошло)

### Mig 285 (2026-05-20) — Streak food-log i18n

**Bug owner-observed:** RPC `log_meal_transaction` хардкодил RU строки прямо в PL/pgSQL:
```sql
v_streak_msg := v_icon_streak || ' Стрик: ' || v_new_streak || ' дн.';
v_streak_msg := '📅 Старт нового стрика!';
```
Все 13 langs пользователей получали RU. Phase 4 UX-копирайтинг (mig 231) audit'ил только `ui_translations` JSONB — не `pg_proc`.

**Fix (mig 285):**
- Добавлены 2 новых ключа в `ui_translations`:
  - `gamification.streak_kept` (с `{streak}` placeholder)
  - `gamification.streak_new_start` (без placeholder)
- RPC переписан: SELECT translation по `v_user.language_code` + REPLACE.
- **Backward-compat сохранён:** field `streak_message` всё ещё возвращается (n8n `03_AI_Engine` не трогали).
- **Forward-prep:** добавлен новый field `streak_event` enum + `streak` int.

---

## RPC contract (live, post-mig 285)

`SELECT public.log_meal_transaction(p_telegram_id, p_food_items, p_input_source, ...)` теперь возвращает JSONB с дополнительными полями:

```json
{
  "success": true,
  "meal_id": "...",
  "items_count": 3,
  "xp_gained": 75,
  "xp_breakdown": {"base": 25, "streak_keep": 50, "day_closed": 0},
  "xp_total": 12345,
  "old_level": 23,
  "new_level": 24,
  "level": 24,
  "leveled_up": true,
  "tamagotchi_stage": "...",
  "mana_remaining": 0,
  "mana_skipped": false,
  "spam_message": null,
  "streak": 18,
  "streak_event": "kept",          // ← NEW (mig 285)
  "streak_message": "🏆 Серия: 18 дн.",  // ← still present (backward-compat)
  "day_closed": false,
  "meals_today": 3,
  "daily_consumed": 420,
  "daily_target": 2000,
  "remaining_daily_calories": 1580,
  "nomscoins": 200
}
```

## `streak_event` enum (4 values)

| Value | Meaning | Renderer action |
|---|---|---|
| `kept` | юзер логировал вчера → серия выросла на +1 | Show `gamification.streak_kept` с {streak} = new streak |
| `new_start` | gap >1 день → серия сбросилась → начался новый отсчёт | Show `gamification.streak_new_start` (без {streak}, просто «Серия началась!») |
| `same_day` | юзер уже логировал сегодня → повторный лог | **Hide streak message** (тон: «не повторяемся») |
| `none` | unreachable в normal flow (default initial state) | Skip render |

---

## Translation keys (live, 13 langs)

### `gamification.streak_kept` — с `{streak}` placeholder

| Lang | Value (rendered with streak=3) |
|---|---|
| ru | 🏆 Серия: 3 дн. |
| en | 🏆 Streak: 3 days |
| es | 🏆 Racha: 3 días |
| de | 🏆 Streak: 3 Tage |
| fr | 🏆 Série : 3 jours |
| it | 🏆 Striscia: 3 giorni |
| pt | 🏆 Sequência: 3 dias |
| pl | 🏆 Passa: 3 dni |
| uk | 🏆 Стрік: 3 дн. |
| id | 🏆 Streak: 3 hari |
| hi | 🏆 Streak: 3 din |
| ar | 🏆 سلسلة: 3 أيام |
| fa | 🏆 پشت هم: 3 روز |

### `gamification.streak_new_start` — без placeholder

| Lang | Value |
|---|---|
| ru | 📅 Серия началась! |
| en | 📅 Fresh streak begins! |
| es | 🌱 ¡Nueva racha empieza! |
| de | 🌱 Neuer Streak — los geht's! |
| fr | 🌱 Nouvelle série, c'est parti ! |
| it | 🌱 Nuova striscia, si parte! |
| pt | 🌱 Nova sequência, bora! |
| pl | 🌱 Nowa passa rusza! |
| uk | 📅 Новий стрік — стартуємо! |
| id | 🌱 Streak baru dimulai! |
| hi | 🌱 Nayi streak shuru! |
| ar | 🌱 سلسلة جديدة تبدأ! |
| fa | 🌱 سری جدید شروع شد! |

---

## Recommended Python pattern (path 2 — structured)

```python
async def render_streak_block(translations: dict, streak_event: str, streak: int) -> str:
    """
    Render localized streak feedback line for food-log reply.
    
    Args:
        translations: pre-loaded ui_translations.content for user's language_code
        streak_event: from RPC (kept | new_start | same_day | none)
        streak: from RPC, number of days
    
    Returns:
        '' if streak_event in ('same_day', 'none') — hide block
        Localized string otherwise
    """
    if streak_event == 'kept':
        tmpl = translations.get('gamification', {}).get('streak_kept', '🏆 Streak: {streak} days')
        return tmpl.replace('{streak}', str(streak))
    elif streak_event == 'new_start':
        return translations.get('gamification', {}).get('streak_new_start', '📅 Fresh streak begins!')
    else:
        return ''  # same_day or none — hide
```

Pre-existing pattern — `v_user_context.content` уже подгружает translations + constants pre-aggregated в один SELECT. Use it.

---

## Backward-compat path (path 1)

Если хочешь оставить как сейчас (минимум изменений на старте, чистка потом):

```python
streak_msg = rpc_result.get('streak_message', '')
if streak_msg:
    text += '\n' + streak_msg
```

RPC сам делает SELECT translation by language_code, так что результат уже локализован. **Works today, n8n тоже так работает.**

**Trade-off:** RPC знает про i18n (architecturally неидеально). Будущая чистка — drop `streak_message` field после того как все consumers перешли на `streak_event`/`streak`.

---

## Что я предлагаю

**Сейчас:** в первой версии Python `03_AI_Engine` использовать **path 2** (structured). RPC уже отдаёт `streak_event` + `streak`, translations доступны через `v_user_context.content.gamification.streak_*`. Renderer Python владеет composition. Чище для long-term.

**Когда migration `03_AI_Engine` смерджен и stable (≥7 дней):** убрать `streak_message` field из RPC. Это будет **B2 step** (см. mig 285 daily log) — финальная чистка architecture: RPC возвращает только структурные данные.

---

## Зависимые knobs

- `app_constants.sys_icon_streak` = '🏆' — используется в backward-compat path как fallback. Если Python renderer берёт path 2, эмодзи уже в template (`🏆` в `gamification.streak_kept`).
- `users.last_streak_kept_date` (mig 187) — затрагивает streak_anchor logic. Не трогать без понимания cron interplay.
- `users.current_streak`, `users.last_log_date` — обновляются RPC'ой, читаются renderer'ом из `users` напрямую если не используешь `rpc.streak`.

---

## Test fixtures (sentinel)

Если хочешь регрессионно тестировать после Python rewrite — взять с mig 285 daily test pattern:

```python
# BEGIN..ROLLBACK для каждого branch без побочных эффектов:
# kept: UPDATE users SET last_log_date = today - 1, current_streak = 5
# new_start: UPDATE users SET last_log_date = today - 5
# same_day: UPDATE users SET last_log_date = today
# Затем SELECT log_meal_transaction(...) и проверить streak_event
```

13 langs sentinel verified в mig 285 PR [#127](https://github.com/sharkovvlad/noms-bot/pull/127). Если нужен код — `/tmp/streak_branch_test.py` в worktree (если ещё лежит).

---

## Контакт

- PR mig 285: [#127](https://github.com/sharkovvlad/noms-bot/pull/127)
- PR mig 286: [#128](https://github.com/sharkovvlad/noms-bot/pull/128)
- Daily lessons: `daily/2026-05-20.md` (mig 285 + 286)
- KB lesson (i18n-rpc-audit): pending — добавлен в TODO для consolidate-memory

Удачи с миграцией. Если streak_event enum нужно расширить (например `frozen` или `milestone`) — extend `log_meal_transaction.v_streak_event` switch в новой миграции, **не** меняй существующие 4 values.
