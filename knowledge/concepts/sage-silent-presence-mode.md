---
title: "Sage silent-presence mode — режим тишины на food_log surface"
aliases: [silent-presence, sage-silent-mode, no-advice-mode, character-only-ack]
tags: [sage, llm, prompt-engineering, payload-meta, ux]
sources:
  - "daily/2026-06-13.md"
created: 2026-06-13
updated: 2026-06-13
status: ACTIVE
---

# Sage silent-presence mode

Owner mandate (2026-06-13, PR-3b): **«если совета нет — может лучше меньше слов, просто поддержать в стиле Sage»**. Реализован как новая payload-META на food_log surface — параллель `quiet_steady_no_push` на my_day.

## Семантика — что юзер видит

Юзер логирует **сбалансированный приём** (умеренный жир, белок есть) на **спокойном дне** (не недобор, не перебор), и Sage **не лезет с советом**. Просто короткая character-only фраза 6-12 слов, без `next_meal_suggested`, без 👏, без «как насчёт». «Ровно. Без лишнего.» / «Clean log. The day runs on its own track.»

**Зачем:** уменьшает шум → каждый совет когда он реально нужен, весит больше. Тип «adult relationship», не лектора.

## Когда срабатывает (4 условия одновременно)

| Условие | Источник | Threshold (app_constants) |
|---|---|---|
| Master flag enabled | `sage_silent_presence_enabled` | по умолчанию `'false'` (safe rollout) |
| Just-logged meal не жирный | `fat × 9 / meal_total_kcal × 100` ≤ `sage_silent_presence_just_logged_fat_pct_max` | default `45` |
| Day kcal в средней зоне | `day_kcal_pct` ∈ [`kcal_pct_min`, `kcal_pct_max`] | default [`40`, `95`] |
| Wellbeing не красное | `sleep != "short" AND stress != "high"` | hard-coded (semantic boundary, не tunable) |

**Wellbeing для free-users:** wellbeing не логируется (premium feature), `wb_dict = None` → guard не блокирует, остальные 3 условия проверяются нормально. Свободный юзер тоже может попасть в режим тишины.

## Где НЕ срабатывает (auto-suppression)

В caller (`_build_user_prompt`) silent_presence НЕ вызывается, если:
- **Budget closed** (`remaining_kcal <= 0`) — `budget_directive` уже закрывает loop
- **Late-night active** (`local_hour >= 22` + flag enabled) — late_night close имеет свою логику

Это значит cascade order: `silent_presence` идёт **после** `late_night_meta`, **перед** `language_lock` (always last).

## Как менять / тюнить

Все 4 порога в `app_constants` с hot-reload через trigger — **без деплоя**.

| Сценарий | Что подкрутить |
|---|---|
| Слишком часто триггерится | Сузить kcal-диапазон (раздвинуть max или поднять min), снизить fat_max |
| Никогда не триггерится | Активировать master flag `sage_silent_presence_enabled` = 'true' |
| Жирные приёмы попадают в тишину | Снизить `just_logged_fat_pct_max` (с 45 до 35) |
| Хочется тишину и в зеленом плюсе | Поднять `kcal_pct_max` с 95 до 110 |

## Как тестировать

Mandatory pre-merge gate — `tools/sage_dry_run.py` (см. [[sage-tone-dry-run-protocol]]). Минимум 2 сценария для silent_presence:

- **food_log RU ru in_progress 14h** + balanced meal (eggs+arugula) + day kcal=60% + wellbeing ok → **silent_presence срабатывает**, no next_meal_suggestion
- **food_log RU ru in_progress 14h** + same meal + day kcal=60% + wellbeing sleep="short" → **silent_presence НЕ срабатывает** (red wellbeing)

После активации master flag — наблюдать `ai_coach_logs.day_context.metas_fired` — должен появиться tag `silent_presence`.

## Связь с другими META

- **`_quiet_steady_no_push_meta`** ([[sage-payload-meta-override-pattern]] §QSP) — параллель на **my_day** surface. Триггер: `day_status == 'quiet_steady'`. Тот же эффект (no push, character only). silent_presence закрывает дыру для food_log где `day_status` не вычисляется.
- **Rule 7b** (в системном промпте `_DEFAULT_SYSTEM_PROMPT_EN` rule 7b) — частично пересекается: «protein + vegetable в одном приёме → no push». Rule 7b чисто meal-based; silent_presence шире — учитывает день + wellbeing.
- **Card S** в VOICE EXAMPLES — reference voice для модели. Текст: «Clean log. The day runs on its own track.» Это PATTERN, не текст; output language transposes auto.

## Файлы

- `services/sage.py:_silent_presence_meta` — функция META
- `services/sage.py:_build_user_prompt` — caller, condition checks (budget_closed / late_night_active / flag) и parsing `day_kcal_pct` + `wellbeing` из `day_context_block`
- `services/sage.py:_DEFAULT_SYSTEM_PROMPT_EN` — Card S в VOICE EXAMPLES
- `migrations/507_sage_silent_presence_constants.sql` — 4 keys в `app_constants`
- `tests/services/test_sage_silent_presence.py` — 6 unit cases

## Изменение паттернa поведения для нутрициологии

Это первый META, который **запрещает** Sage давать совет на основании **позитивного** состояния (юзер ВСЁ делает правильно), а не на основании опасности/limits. До PR-3b весь cascade был защитный — `quiet_steady_no_push` единственный «не пуш» режим (и только на my_day). Silent presence — это **доверие к юзеру**: «ты справляешься, моё мнение не нужно».

## Связанные KB концепты

- [[sage-payload-meta-override-pattern]] — общий паттерн META cascade
- [[sage-food-log-llm-integration]] — общая архитектура food_log surface
- [[sage-tone-dry-run-protocol]] — MANDATORY pre-merge gate
- [[sassy-sage-multilingual-glossary]] — словарь native foods / streak / etc по 13 langs
