---
title: "My Day LLM Insight — cache-on-write архитектура для stats_main"
aliases: [my-day-insight, my-day-llm, sage-my-day, stats-llm-insight, cache-on-write-insight]
tags: [llm, openai, stats, sage, architecture, python, cache]
sources:
  - "daily/2026-05-24.md"
created: 2026-05-24
updated: 2026-05-25
---

# My Day LLM Insight — cache-on-write для stats_main

Sassy Sage LLM-комментарий на экране «📊 Мой день» (`stats_main`). В отличие от food-log one-liner'а (fire-and-forget per meal), My Day insight **кешируется в `users`** и обновляется piggy-back на food_log path. View (открытие stats_main) — **0ms LLM** (cache hit → inject, cache miss → static SQL fallback).

## Key Points

- **Cache-on-write:** LLM call происходит **после** каждого food log (`asyncio.create_task(regen_my_day_insight_cache)`), не при открытии «Мой день». Юзер видит готовый insight мгновенно.
- **4 колонки кеша в `users`:** `my_day_insight_text`, `my_day_insight_emotion`, `my_day_insight_at`, `my_day_insight_locale`. **Свежесть (mig 389, 2026-05-30):** тот же локальный календарный день И та же фаза дня (утро<12 / день 12-17 / вечер 17-22 / ночь>22, в tz пользователя), выводится из `my_day_insight_at` — заменил прежний 4h TTL. Плюс locale match (язык мог смениться). Причина смены: insight завязан на время суток, 4h TTL давал контекстно неверную фразу (утренняя к вечеру) ИЛИ ранний откат на static. Теперь фраза пересоздаётся ровно на границе фазы дня.
- **10-enum `day_status`** как tone anchor для LLM: `cold_start | night_overflow | over_target | severe_deficit | under_target_evening | perfect_unicorn | protein_drought | carbs_overload | near_target | in_progress`. Покрывает 7 канонических Noms-сценариев.
- **Prompt guardrails (mig 323):** 4 жёстких правила: ≥50% kcal → никогда «warming up»; last log <2h → запрет «иди поешь»; macro ≥100% → redirect на баланс; streak acknowledgement. Защита от LLM-«шизофрении» (payload says X, LLM says opposite).
- **Master kill-switch:** `app_constants.sage_my_day_enabled` (hot-reload 60s). Flag flip без деплоя.
- **Graceful degradation:** cache miss → существующий SQL `insight_key` (8 static variants per lang). LLM failure → no regression, юзер видит старый формат.

## Архитектура

```
[Food log path — write-time]
handlers/food_log.py:render_food_log_confirmation
    ↓ asyncio.create_task(regen_my_day_insight_cache(ctx))
    ↓ (fire-and-forget, не блокирует food card)
services/sage.py:regen_my_day_insight_cache(ctx):
    1. RPC get_day_summary(tid)
    2. _compute_day_status(summary) → enum
    3. _build_my_day_prompt(ctx, summary, day_status)
    4. OpenAI gpt-4o-mini → {"text": "...", "emotion": "smirk|proud|side-eye|sage"}
    5. RPC set_my_day_insight_cache(tid, text, emotion, locale)

[View path — read-time]
handlers/menu_v3.py:handle_menu_v3
    ↓ dispatch_with_render → telegram_ui
    ↓ _maybe_inject_my_day_insight(telegram_ui, ctx)
    ↓ if screen_id == 'stats_main' AND cache fresh:
        replace static {insight_localized} in template_vars
        inject noms_emoji from cache emotion
    ↓ render_envelope → editMessageText
```

## `_compute_day_status` — 10-enum tone anchor

| Status | Условие | Tone |
|---|---|---|
| `cold_start` | 0 meals today | Мотивирующий «начни день» |
| `night_overflow` | local hour ≥22 + over target | Лёгкая ирония |
| `over_target` | kcal% > 110% | Reassurance (не shame) |
| `severe_deficit` | kcal% < 40% + hour ≥ 15 | Concern + push |
| `under_target_evening` | kcal% 40-75% + hour ≥ 18 | Мягкий nudge |
| `perfect_unicorn` | kcal% 95-105% + all macros 80-120% | Celebration |
| `protein_drought` | protein% < 50% of target | Macro-specific advice |
| `carbs_overload` | carbs% > 150% of target | Macro-specific |
| `near_target` | kcal% 75-110% | Поддержка |
| `in_progress` | всё остальное | Нейтральный |

Status передаётся в LLM prompt как контекст — LLM НЕ выбирает status, он получает его от Python.

## Prompt Guardrails (mig 323, lesson 2026-05-24)

После live-теста юзер с 79% kcal + 8 meals получил «пустой желудок, иди поешь». LLM не галлюцинировал — отсутствовали жёсткие правила.

Добавлен блок LOGIC GUARDRAILS в system prompt:

```
1. If kcal_percent >= 50 → NEVER use phrases like "warming up", "empty stomach",
   "start your day". The user has ALREADY eaten significantly.
2. If last_meal_minutes_ago < 120 → NEVER suggest eating now.
3. If any macro >= 100% of target → redirect commentary to balance/quality.
4. If streak_status = "active" → MUST acknowledge (don't ignore streak).
```

Хранение: `ui_translations.{ru,en}.sage.system_prompt_my_day` (hot-reload через DB). Python constant `_DEFAULT_SYSTEM_PROMPT_MY_DAY_EN` — cold-start fallback.

## Normaliser gotcha (P0, mig 322)

`_normalise_day_summary` предполагал flat keys (`raw["total_kcal"]`), но `get_day_summary` RPC отдаёт nested:
- `stats.{total_calories, total_protein, total_fat, total_carbs}`
- `streak_current` (не `streak`)
- `last_meal_at` → derive из `meals[-1].meal_time`

5 из 12 полей silently возвращали 0 → LLM получал «0 калорий» → корректно говорил «пустой день». Юзер видел галлюцинацию, реально — broken payload.

**Правило (добавлено в [[pre-migration-discovery-recipe]]):** при wiring RPC → LLM payload первый шаг — `psycopg2.execute('SELECT <rpc>(...)')` + `json.dumps(indent=2)` живого ответа. Mapper пишется ПОСЛЕ видения реальной shape.

## Cache lifecycle

| Событие | Действие |
|---|---|
| Food log add/edit (text/photo/voice) | `regen_my_day_insight_cache` (fire-and-forget) |
| Food **delete** (`_handle_delete_meal_now`, mig 389) | Инвалидация in-memory кеша (`replace(ctx, my_day_insight_at=None)`) → этот рендер stats_main = fallback, `_maybe_inject` сам ставит фоновый regen. До mig 389 delete кеш НЕ обновлял (фраза ссылалась на удалённый приём). |
| View stats_main | Read from `ctx.my_day_insight_*`. Fresh = inject. Stale/miss = static fallback + фоновый regen |
| Language change | Cache stale (locale mismatch) → static fallback → regen |
| Goal/weight change | TODO: wire `clear_my_day_insight_cache` в profile handlers |
| Смена фазы дня (утро/день/вечер/ночь, mig 389) | Cache stale (phase mismatch) → static fallback → фоновый regen с фразой под новую фазу |
| Day rollover (midnight local) | Cache stale (другая дата) → fallback + regen |

## Emoji format (v3 rollback, 2026-05-24)

Noms feedback: «3D-эмодзи в инлайн-размере не читаются». Откат `<tg-emoji>` → unicode:

```python
EMOTION_TO_EMOJI = {
    "smirk":    "😏",
    "proud":    "🤩",
    "side-eye": "🤨",
    "sage":     "🧘‍♂️",
}
```

Display format: `NOMS {emoji}: "{text}"` (вместо `💬 Noms:`).

## Тесты

- 24 unit (sage my_day) + 16 integration (menu_v3 cache injection) = 40 новых
- 5 normaliser real-shape regression
- 3 emoji injection
- 150/150 pass total

## Файлы

| Файл | LOC delta | Назначение |
|---|---|---|
| `services/sage.py` | +426 | `generate_my_day_insight`, `regen_my_day_insight_cache`, `_compute_day_status`, `_build_my_day_prompt`, `_normalise_day_summary` |
| `handlers/menu_v3.py` | +73 | `_maybe_inject_my_day_insight`, `_my_day_cache_fresh` |
| `handlers/food_log.py` | +10 | `asyncio.create_task(regen...)` |
| `dispatcher/context.py` | +7 | 4 cache fields in UserCtx |
| `migrations/319_my_day_insight_cache.sql` | 412 | Schema + RPCs + v_user_context refresh |
| `migrations/320_sage_my_day_flag.sql` | — | Kill-switch constant |
| `migrations/323_my_day_prompt_guardrails.sql` | — | Prompt text in ui_translations |

## System prompt length reduction (mig 349, 2026-05-25)

Owner feedback: Sage comments too verbose on mobile. Mig 349 reduced `system_prompt_my_day` from 100-250 chars to **80-150 chars** across all 13 languages. Per-lang substring rewrite (not truncation — each was re-authored to fit). Cache invalidation through `app_constants` flag flip.

## Related Concepts

- [[concepts/sage-food-log-llm-integration]] — food-log one-liner (sibling LLM integration, same safety gates)
- [[concepts/stats-main-headless]] — stats_main screen architecture (where insight renders)
- [[concepts/pre-migration-discovery-recipe]] — gotcha: LLM payload normaliser vs live RPC shape
- [[concepts/headless-template-substitution]] — template_vars injection pattern
- [[concepts/adaptive-modifiers-architecture]] — wellbeing hub widget uses get_day_summary (same RPC)

## Sources

- [[daily/2026-05-24.md]] — PR #164 (mig 319+320): cache-on-write architecture, 10-enum day_status, _normalise_day_summary, 40 tests. PR #166 (mig 322): normaliser P0 fix (nested stats shape). PR #167 (mig 323): prompt guardrails (4 rules). PR #163: emoji rollback + timeout bump 2.5→5s.
- [[daily/2026-05-25.md]] — Mig 349 (PR #197): system_prompt_my_day length reduction 100-250→80-150 chars × 13 langs.
