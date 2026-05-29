# Cron Reminder Suppression Tunables

**Status:** ACTIVE
**Owner intent:** future agents должны быстро находить точки тюнинга для cron-уведомлений
**Established:** 2026-05-29 (mig 369)

## Принцип

**Любое timing/threshold-значение, влияющее на suppression cron-уведомлений (включая mute-windows, hour cutoffs, percent thresholds, cooldown durations) должно жить в `app_constants` с категорией `'cron'` или `'ux'` — НЕ хардкодом внутри RPC.**

Три причины:

### 1. Discoverability для будущих агентов

Когда юзер жалуется «крон пришёл не вовремя» / «крон не пришёл когда должен», следующий агент бежит по знакомым местам:
- `crons/*.py` — Python orchestration
- `cron_get_reminder_candidates` body — SQL filter logic
- `app_constants WHERE category IN ('cron','ux')` — **точки тюнинга**

Если значение в коде RPC — приходится читать 200 строк SQL чтобы найти `INTERVAL '30 minutes'`. Если в `app_constants` — один SELECT и видно.

### 2. Tuning без deploy

`UPDATE app_constants SET value = '45' WHERE key = 'reminder_activity_mute_minutes';`
→ следующий cron tick (hourly :20) **подхватывает без redeploy**, потому что RPC читает константу свежей каждый вызов (нет PostgreSQL function-level кэша на SELECT в `app_constants`).

Это ценно когда:
- Owner просит «увеличь окно мьюта до 60 мин» — 5 секунд работы вместо CREATE OR REPLACE FUNCTION + deploy
- A/B testing значения без миграций
- Hotfix race condition без новой mig в очереди

### 3. Audit trail

`app_constants` имеет `category` + `description`. Через `/nlm` блокнот видно все tunables проекта в одном месте — что есть, для чего, default value.

Хардкод в RPC body — невидим для NLM-блокнота (он индексирует таблицы данных, не источники RPC).

## Anti-pattern (нельзя)

```sql
-- mig 366 (BEFORE mig 369 fix): хардкод × 4 в RPC
AND NOT EXISTS (
    SELECT 1 FROM public.food_logs fl
    WHERE fl.telegram_id = c.telegram_id
      AND fl.created_at > now() - INTERVAL '30 minutes'  -- ❌ хардкод
)
```

## Pattern (нужно)

### Step 1 — INSERT const

```sql
INSERT INTO public.app_constants (key, value, category, description)
VALUES (
    'reminder_activity_mute_minutes', '30', 'cron',
    'Окно (мин) активности юзера, в течение которого *_checkin '
    'reminders суппрессятся (mig 366 activity-mutex). Менять через UPDATE → '
    'следующий cron tick (:20) подхватит без deploy.'
)
ON CONFLICT (key) DO UPDATE
    SET value = EXCLUDED.value, description = EXCLUDED.description, category = EXCLUDED.category;
```

### Step 2 — DECLARE + SELECT в RPC

```sql
DECLARE
    v_mute_minutes INT;
BEGIN
    SELECT value::INT INTO v_mute_minutes
      FROM public.app_constants
     WHERE key = 'reminder_activity_mute_minutes';
    IF v_mute_minutes IS NULL OR v_mute_minutes <= 0 THEN
        v_mute_minutes := 30;  -- safe fallback если константа удалена / битая
    END IF;
    ...
```

### Step 3 — Использование

```sql
AND NOT EXISTS (
    SELECT 1 FROM public.food_logs fl
    WHERE fl.telegram_id = c.telegram_id
      AND fl.created_at > now() - (v_mute_minutes || ' minutes')::INTERVAL  -- ✅ dynamic
)
```

`(int || ' minutes')::INTERVAL` — стандартный PostgreSQL pattern. Работает чисто.

### Step 4 — Safe fallback в Python

Если значение читается на стороне Python (не SQL):

```python
constants = ctx.constants if isinstance(ctx.constants, dict) else {}
try:
    mute_min = int(constants.get("reminder_activity_mute_minutes", 30))
except (TypeError, ValueError):
    mute_min = 30
```

Pattern одинаковый: **внешнее значение → fallback default → use**.

## Существующие cron tunables (29.05.2026)

| Key | Value | Где используется |
|---|---|---|
| `reminder_activity_mute_minutes` | 30 | `cron_get_reminder_candidates` — sleep_checkin / stress_checkin suppression при свежей активности |
| `macro_warn_hour_cutoff` | 15 | `handlers/menu_v3.py:_maybe_suppress_macro_warn_under_cutoff` — hour-gate для ⚠️ на UNDER-target БЖУ |

(Список не исчерпывающий — `SELECT key FROM app_constants WHERE category IN ('cron','ux','gameplay')` даст актуальный.)

## Когда **НЕ** выносить в app_constants

- Алгоритмическая структура (CASE branches, JOIN paths) — это код, не tunable
- Магические числа в business logic без timing/threshold смысла (массивы координат, кодовые константы) — пусть остаются в коде
- Внутренние константы Python-helper'ов которые не должны меняться (типа TTL'ов сервисных кэшей) — оставлять в коде, не плодить app_constants noise

Тест: «Захочет ли owner / другой агент это поменять без redeploy?» Если да — `app_constants`. Если нет — код.

## Links

- mig 366 (sleep/stress activity mutex, hardcoded version) — superseded by mig 369
- mig 369 — tunable refactor (этот KB)
- mig 368 — macro_warn_hour_cutoff (другая tunable из этой же сессии)
- [[copywriter-playbook]] — для UX текстов reminder'ов
- [[checkmark-prefix-pattern]] — другой example app_constants-driven UI behavior
