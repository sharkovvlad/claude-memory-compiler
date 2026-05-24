# My Day → LLM Insight (architecture proposal)

> Сформирован 2026-05-24 в ответ на ТЗ Noms «персонализировать экран 📊 Мой день LLM-ом
> вместо статичных фраз `report.insight_*`». Сегодня закрыты 3 P0 баги (PR #163);
> Task 2 этого ТЗ требует отдельного PR — этот документ = пред-implementation review.

## Текущая архитектура (как есть)

1. Юзер жмёт «📊 Мой день» → callback (типа `cmd_get_stats`).
2. `webhook_server.py:_route_or_forward` → `handle_menu_v3(update, ctx, decision)`.
3. `handle_menu_v3` строит payload и зовёт **`dispatch_with_render` RPC** (mig 149 bundle: process_user_input + render_screen за один RTT, p50 46ms).
4. Внутри RPC:
   - `stats_main` business_data = `get_stats_main_business_data` (mig 124 + 163).
   - RPC вычисляет `v_insight_key` enum на основании `% от target`:
     - 0 meals → `report.insight_cold_start`
     - ≥120% → `report.insight_calorie_over`
     - <50% → `report.insight_eating_little` ← вот эта фраза в скрине
     - protein <70% → `report.insight_protein_low`
     - ≥100% → `report.insight_balanced`
     - else → `report.insight_calorie_almost_full`
   - Резолвит из `ui_translations.{lang}.report.{key}` → `v_insight_localized` (текст).
   - Кладёт в business_data: `{insight_key, insight_localized, ...}`.
5. `render_screen` рендерит шаблон с `{insight_localized}` → готовый text для Telegram.
6. Handler → `services.telegram_send.send`.

**Latency бюджет:** click→render p95 <700ms (CLAUDE.md line 244).
**LLM call ~700-2500ms** — нельзя втыкать синхронно в RPC.

## Спец-требования Noms

> Payload для LLM: время, КБЖУ (съедено/осталось), профиль (phenotype, goal,
> notifications_mode), стрик. Тон + system prompt = как food_log Sage.

И ключевое: «Сделай так, чтобы UX не пострадал от долгих загрузок».

## Recommended pattern: Cache-on-write-after-meal-log

### Принцип

LLM call происходит **не на view, а на write** — после того как юзер залогировал
очередной приём пищи. Когда юзер открывает «📊 Мой день», читаем из кеша.

Это работает потому что:
- Контент My Day-инсайта зависит ОТ суммы КБЖУ за день → каждый food_log
  меняет состав, каждый food_log делает старый кеш stale.
- LLM call уже происходит на food_log path (Sage one-liner). Добавление второго
  LLM call в parallel — почти бесплатно (~$0.0002 extra).
- На view (часто, hot path) — zero LLM latency.

### Cache invalidation

Кеш живёт пока:
- Локаль не сменилась (`ctx.language_code == cache.locale`).
- Последний food_log не свежее кеша (`max(food_logs.consumed_at) <= cache.at`).
- TTL не прошёл (например 4h — на случай долгого простоя, чтобы юзер видел
  свежий tone после простой).

Если все 3 OK → cache hit, рендерим из кеша.
Иначе → cache miss → используем static `insight_localized` (legacy fallback,
никогда не пустой) + **kick off async regen** (fire-and-forget) чтобы при
следующем открытии было свежее.

### Что меняется

**Migration NNN** (mig 319 или следующий свободный при apply):
```sql
ALTER TABLE users
  ADD COLUMN my_day_insight_text TEXT,
  ADD COLUMN my_day_insight_emotion TEXT,        -- smirk/proud/side-eye/sage
  ADD COLUMN my_day_insight_at TIMESTAMPTZ,
  ADD COLUMN my_day_insight_locale TEXT;          -- сравнить с ctx.language_code

CREATE INDEX users_my_day_insight_at_idx
  ON users (my_day_insight_at)
  WHERE my_day_insight_at IS NOT NULL;
```

`v_user_context` view — расширить аналогично (4 fields).

**`services/sage.py`** — новая функция:
```python
async def generate_my_day_insight(
    ctx: UserCtx,
    day_summary: dict,                  # из RPC get_day_summary
) -> tuple[str, str] | None:
    """Generate LLM Noms phrase for My Day screen.

    Same system prompt + tone modes как food_log Sage.
    Payload: local_time, kcal_in/target/remaining, macros %, phenotype,
    goal, notifications_mode, streak, # meals today.
    Returns (text, emotion) or None on timeout/error.
    """
```

Re-use:
- `_get_client`, `_resolve_tr`, `_pick_pre_baked`
- `_local_time_context`, `_compute_macros_focus`
- `EMOTION_TO_EMOJI`
- Sanity filter (length, HTML, URL, @)
- JSON mode + same response schema

Key difference: payload **не упоминает конкретное блюдо**, а описывает день
целиком («залогировано 6 приёмов, 1956 ккал из 2638 на текущий час дня»).

**Handler hook** (`handlers/menu_v3.py` extension OR new wrapper):
```python
async def maybe_inject_my_day_insight(ctx, business_data):
    """Override business_data['insight_localized'] with cached LLM phrase
    if fresh. Kick off async regen if stale. Always non-blocking."""
    if not _cache_fresh(ctx):
        # Cache miss → kick off regen in background (don't await)
        asyncio.create_task(_regen_my_day_cache(ctx, business_data))
        return  # legacy static insight stays
    business_data["insight_localized"] = ctx.extra.get("my_day_insight_text")
    business_data["insight_emotion"] = ctx.extra.get("my_day_insight_emotion") or "smirk"
```

**Cache write** (in `handlers/food_log.py:render_food_log_confirmation`):
```python
# Sage food_log call уже запущена parallel'но.
# Стартуем ВТОРОЙ task: My Day insight для следующего view.
my_day_task = asyncio.create_task(
    _regen_my_day_insight_async(ctx, day_summary_post_log)
)
# Не await — это fire-and-forget. Запишется в users.my_day_insight_*
# через RPC `set_my_day_insight_cache(tid, text, emotion)`.
```

### Feature flag

`app_constants.sage_my_day_enabled = 'false'` initially. Включаем после live smoke.
Юзер не замечает рассинхрона: при выключенном флаге `maybe_inject` no-op, static
insight остаётся (legacy path не сломан).

## Альтернативы (отвергнуты)

### Альтернатива A: Sync LLM call в menu_v3 handler

❌ Breaks SLA (700ms p95). Каждый клик «Мой день» = +700-2500ms latency.

### Альтернатива B: Cache TTL 1-2h без regen-on-write

❌ Несвежий кеш — юзер логирует обед в 14:00, открывает «Мой день» в 14:01,
видит инсайт от утра («Скромно поел») вместо актуального («Норм обед!»).
Cognitive dissonance.

### Альтернатива C: SQL-only без LLM (статика остаётся)

❌ Это и есть текущее состояние, которое Noms забраковал («убивает характер»).

## Effort estimate

- Migration + view refresh: ~30 min
- `services/sage.py::generate_my_day_insight` (re-use code из food_log path): ~1h
- Handler hook + regen path: ~2h
- Tests (sage unit + handler unit + cache invalidation): ~2h
- Translations (system prompt уже multi-lingual из mig 316, fallback нужен новый × 13 langs): ~1h
- Live smoke + flag flip: ~30 min

**Total: ~7h** (1 рабочий день).

## Risks

| Risk | Mitigation |
|---|---|
| Cache stale после weight/goal change (профиль меняет targets) | Invalidate also on goal/weight write — добавить `clear_my_day_cache(tid)` RPC и звать из profile handlers |
| Async regen блокирует Sage food_log (race) | Запускать через `asyncio.create_task` независимо — оба независимы, gather не нужен |
| Cost удвоится (LLM call на каждый food_log + на каждый view miss) | Текущее ~$0.70/мес → ~$1.40/мес. Trivial. |
| Двойной LLM call в food_log handler (Sage + my_day) увеличит расход токенов | Реально 2× cost от food_log path. На текущем scale = ничто. Можно дальше batch'ить в один call если станет дорого. |

## Open questions для тимлида

1. **OK ли удваивать LLM calls в food_log path?** Cost = trivial, но количество
   запросов к OpenAI 2×. Альтернатива: synchronous LLM call **только** на view с
   таймаутом 1.5s + fallback на статику. Хуже UX, но 1× OpenAI calls.

2. **Куда писать кеш — `users` table или новая `my_day_insight_cache` таблица?**
   Я предлагаю `users` (4 поля), потому что:
   - v_user_context уже join'ает users — нет лишнего round trip
   - Cleanup автоматический (delete_user → cascade)
   - Один writer (RPC) на одну таблицу

   Отдельная таблица была бы лучше если планируем history (но не нужно — single
   current insight достаточно).

3. **TTL?** Я предлагаю 4h. Слишком мало = частые миссы при простое. Слишком
   много = после долгого перерыва юзер видит вчерашний tone.

## Action items

- [ ] Тимлид: review proposal + Q1-Q3
- [ ] Если approved: создать PR `claude/sage-my-day-insight` с mig NNN + service + handler
- [ ] After merge: flag flip + canary owner tid 786301802 + watch p95

## Pointers

- Current static insight RPC: `migrations/124_stats_rewrite_spec_aligned.sql:160` and `migrations/163_stats_main_flat_template.sql:156`
- Sage food_log path: `services/sage.py:generate_food_log_comment` + `handlers/food_log.py:render_food_log_confirmation`
- Headless menu_v3 entry: `handlers/menu_v3.py:handle_menu_v3`
- system prompts (multi-lingual ready): `ui_translations.{lang}.sage.system_prompt_food_log` (mig 312 + 316)
- Pre-baked fallback × 13 langs: `ui_translations.{lang}.sage.food_log_fallback` (mig 315)
