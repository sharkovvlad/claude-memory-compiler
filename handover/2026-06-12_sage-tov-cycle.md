# Sage ToV iteration cycle — 2026-06-12 handover

5-минутный брифинг для следующего агента, который будет работать над Sage tone-of-voice. День 12.06 закрыл цикл из 4 PR'ов на основе owner ToV review; на хвосте — измерения и watch-итемы.

## Что сделано за день (4 PR'а)

| PR | Что | Status |
|---|---|---|
| [#383](https://github.com/sharkovvlad/noms-bot/pull/383) | Rule 7b balanced-meal no-push + race-fix food_log→my_day (`just_emitted_food_log` через память) + bump `sage_food_log_timeout_ms` 5→7s | **MERGED** |
| [#384](https://github.com/sharkovvlad/noms-bot/pull/384) | TD-#18 bridge removal (add_food pre-delete) — не Sage, но в этом же дне | **MERGED** |
| [#385](https://github.com/sharkovvlad/noms-bot/pull/385) | `cold_start_phase` META (закрывает дыру `time_meta_warning`) + `metas_fired` + `budget_state` observability в `ai_coach_logs.day_context` | **MERGED** |
| [#386](https://github.com/sharkovvlad/noms-bot/pull/386) | Trim `_DEFAULT_SYSTEM_PROMPT_MY_DAY_EN` −19% + Phase 3.1 `quiet_steady` 30→20% + ban-list META (Agent 2's предложение) | **OPEN** |

После merge #386 у нас 4 META payload-уровня (`budget_directive`, `variation_guard`, `rule7_hard_guard`, `cold_start_phase`, `ban_list`, плюс my_day-only `time_meta_warning`) + 13 enum'ов `day_status` + сокращённый my_day-prompt.

## Самое важное

### 1. Live numbers есть — наблюдаемость работает

После #379 (telemetry hole closed) + #385 (`metas_fired`+`budget_state`) в `ai_coach_logs.day_context` для каждой happy-path реакции лежит:
```json
{
  "prompt": "...full user_prompt...",
  "metas_fired": ["budget_directive", "variation_guard", "ban_list"],
  "budget_state": "open"
}
```
И для fallback'ов: `success=false, error='openai_err: APITimeoutError'|'json_parse'|'sanity_reject'|'closed_budget_leak'|'handler_wait_for_timeout'|'safety_guard_skip'|'no_api_key'`.

**SQL рецепты для следующего агента:**

```sql
-- META activation rate
SELECT day_context->'metas_fired', count(*)
FROM ai_coach_logs
WHERE context_type='sage_food_log' AND success=true
  AND created_at > now()-interval '24 hours'
GROUP BY 1 ORDER BY 2 DESC;

-- timeout rate by context
SELECT context_type, error, count(*)
FROM ai_coach_logs
WHERE context_type LIKE 'sage_%'
  AND created_at > now()-interval '72 hours'
GROUP BY 1,2 ORDER BY 3 DESC;

-- META сработала vs штамп прошёл (the holy grail)
SELECT
  ('variation_guard' = ANY(ARRAY(SELECT jsonb_array_elements_text(day_context->'metas_fired')))) AS guard_fired,
  ('chicken' ~* ai_message OR 'кур' ~* ai_message OR 'cottage' ~* ai_message OR 'твор' ~* ai_message) AS still_pushed_protein,
  count(*)
FROM ai_coach_logs
WHERE context_type='sage_food_log' AND success=true
  AND created_at > now()-interval '24 hours'
GROUP BY 1,2 ORDER BY 3 DESC;
```

### 2. Open watch-items после merge #386

| Метрика | Текущая | Цель | Действие если не достигли |
|---|---|---|---|
| my_day timeout rate | 21% (06-12 today) | ≤3% | Ввести отдельный `sage_my_day_timeout_ms` 9000ms + менять `_get_client` сигнатуру (принимает `context_type`) |
| `cold_start_phase` daily activations | unknown | ≥5/день | Расширить триггер с `meal_period != breakfast` на `local_hour >= 11` |
| `ban_list` daily activations | unknown | ≥10/день | Расширить `_FOOD_MENTIONS` table (Agent 2 видел broader regex) |
| `emotion=smirk` доля | 100% (P2 watch) | ≤50% | Гипотеза: META-стек → curse-of-instructions. Trim #386 может помочь — measure first. |
| protein-stamp rate в реакциях | 64% / 0.64-tokens/reaction | ≤30% / ≤0.5-tokens | Если выше — расширить `ban_list` regex или добавить few-shot examples в payload |

### 3. Метрики baseline для измерения эффекта

| Метрика | 08.06 baseline | 12.06 (post-PR-#385) | Цель |
|---|---|---|---|
| Предписания еды | 92% | 91% | ≤25% |
| Штамп protein-foods | 1.06/реакция | 0.64/реакция | ≤0.5 |
| Rule-7 нарушений | 3/3 (100%) | 0/1 (0%) | 0 |
| Telemetry coverage | 0% | 100% | 100% |
| emotion smirk | 80% | 100% | ≤50% |
| my_day timeout rate | n/a (невидим) | 21% | ≤3% |

Замер после merge #386 — через 24-48ч (timeouts) + через 3-4 дня (тон-эффекты, `/sage-tov` rerun).

## Архитектурный контекст

### Payload-META cascade (порядок в финальном промпте)

В `_build_user_prompt` (food_log) — порядок специфичности (по возрастанию, более специфичная META ближе к концу — gpt-4o-mini weighs end-of-context):
```
{Response language}
{budget_directive}           ← always fires
{variation_guard?}           ← if recent reactions push same protein lever
{cold_start_phase?}          ← if 0 logs AND not breakfast (PR #385)
{ban_list?}                  ← if specific foods named in recent (PR #386 NEW)
{rule7_hard_guard?}          ← if protein >= 20g in just-logged meal
```

В `_build_my_day_prompt` (my_day) — параллельно, без rule7 (не применим на day-level):
```
{Response language}
{time_meta_warning?}         ← if local_hour >= 16 (evening)
{budget_directive}
{variation_guard?}
{cold_start_phase?}
{ban_list?}
```

### Race-fix `just_emitted_food_log` (PR #383)

`handlers/food_log.py` спавнит `regen_my_day_insight_cache(ctx, just_emitted_food_log=payload['noms_comment'])`. my_day prepend'ит этот текст к `recent_reactions` ПЕРЕД `_detect_repeat_protein_stamp` И `_extract_banned_foods`. Это **memory-based fix**, не SQL-окно — БД не нужна (`_fetch_recent_sage_reactions` returns empty при race).

## Owner-mandate (брендовые правила)

- **Системный промпт = бренд owner'а.** Trim PR #386 был **явно одобрен** на основе live timeout-данных. Без явного approval — НЕ трогать.
- **«Дадим ИИ больше воли, если может — то пусть делает складно».** Owner-фраза вшита в Rule 7b TONE SHAPE как «if there is something real to riff on, use it». Любые новые META должны давать модели **позитивную инструкцию** (что делать), а не голый запрет.

## Отвергнутые предложения других агентов (на случай возврата)

- **Agent 2 cross-context fix (3 reactions/30 мин окно)** — функционально эквивалентен `just_emitted_food_log` race-fix из #383. Не делать; уже решено deriv-ным способом.
- **Agent 1 separate `sage_my_day_timeout_ms`** — пока bump shared 5→7s. Вариант если timeout остаётся >3% после #386 trim.
- **`/anthropic-skills:consolidate-memory`** — высокий риск без human review. Может запустить owner вручную.
- **Phase 3.1 absolute `kcal_in >= 400`** — Agent 1 предложил «20% OR абсолютные 400 ккал». Я выбрал только 20% (простота). Если кейс с маленьким kcal-target вылезет — добавить второй OR.

## Где смотреть в KB

- [[concepts/sage-payload-meta-override-pattern]] — паттерн payload-META, после #385 расширен секциями «Wiring gotcha» (rpc_caller forwarding) + «Telemetry coverage gotcha».
- [[concepts/sage-food-log-llm-integration]] — host архитектура Sage.
- `sage_transcripts/sage_tov_review_2026-06-12.md` — последний A/B-отчёт судьи (07.06 vs 12.06 baseline).
- `daily/2026-06-12.md` — детали по сегодняшним 4 PR'ам.
- `daily/2026-06-09.md` — PR #379 (telemetry hole) детали.
- `handover/2026-06-08_sage-payload-meta.md` — предыдущий handover на ToV.

## Что НЕ менять без owner approval

- `_DEFAULT_SYSTEM_PROMPT_EN` (food_log) — было trim'нуто в #383 добавлением Rule 7b, дальше без явного approval.
- `_DEFAULT_SYSTEM_PROMPT_MY_DAY_EN` — было trim'нуто в #386. Owner одобрил «только дубликаты + verbose enum описания», не смысловые правила.
- `_PROTEIN_STAMP_RE`, `_FOOD_MENTIONS` — расширение regex'ов на новые foods OK (Agent 2 этого хотел); refactor паттернов в YAML/JSON — нет (минимизируем surface).
