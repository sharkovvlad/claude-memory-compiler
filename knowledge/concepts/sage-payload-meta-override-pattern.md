---
title: "Sage payload-meta override — паттерн влияния на тон без правки системного промпта"
aliases: [payload-meta, sage-meta-override, meta-warning, time-meta-warning, variation-guard, rule-7-hard-guard]
tags: [sage, llm, prompt-engineering, architecture, python]
sources:
  - "daily/2026-05-29.md"
  - "daily/2026-06-07.md"
  - "daily/2026-06-08.md"
  - "daily/2026-06-09.md"
  - "daily/2026-06-12.md"
  - "handover/2026-06-08_sage-payload-meta.md"
  - "handover/2026-06-12_sage-tov-cycle.md"
created: 2026-06-08
updated: 2026-06-12
---

# Sage payload-meta override — паттерн

Способ скорректировать поведение LLM-генератора Sassy Sage **без правки системного промпта** (`_DEFAULT_SYSTEM_PROMPT_*` в `services/sage.py`). Используется когда системный промпт — это **бренд** и требует owner-approval на каждое изменение, а нужная коррекция — точечная и data-driven.

Применяется в 6 живых местах (по состоянию на 2026-06-12):

| META | Условие триггера | Когда добавлен |
|---|---|---|
| `time_meta_warning` | `local_hour >= 16` (my_day only) | 2026-05-29 (mig 29.05) — бот говорил «morning» в 18:57 |
| `closed-budget directive` / `budget_directive` | `remaining_kcal <= 0` (explicit) — всегда тегается в metas_fired | 2026-06-07 (PR закрытого бюджета) |
| `VARIATION GUARD` / `variation_guard` | `_PROTEIN_STAMP_RE` совпадает в ≥1 из последних 2 реакций (RPC `get_recent_sage_reactions` + race-fix `just_emitted_food_log` PR #383) | 2026-06-08 (PR #375), race-fix 2026-06-12 (PR #383) |
| `RULE 7 HARD GUARD` / `rule7_hard_guard` | `payload['protein'] >= 20` (food_log only) | 2026-06-08 (PR #375) |
| `COLD-START PHASE` / `cold_start_phase` | `meals_count == 0 AND meal_period != "breakfast"` | 2026-06-12 (PR #385) |
| `BAN LIST` / `ban_list` | foods из таблицы `_FOOD_MENTIONS` совпали в последних 2 реакциях (Agent 2's предложение, sharper чем VARIATION GUARD) | 2026-06-12 (PR #386) |

## Key Points

- **Место в payload:** в самый конец `user_prompt`, после `Response language` строки и существующих `FINAL DIRECTIVE` / `time_meta_warning`. gpt-4o-mini вешает на end-of-context max weight — это работает.
- **Формат:** `\n\n⚠️ META — <NAME>: <инструкция>`. Префикс `⚠️ META —` единый, чтобы при чтении журналов сразу видно «вот патч поведения, не часть основного промпта».
- **Фразировать позитивно (конкретный next-move), не запрет.** gpt-4o-mini надёжнее следует «pick a different lever — leafy greens, fibre», чем «do NOT suggest chicken». Голый запрет модель может проигнорировать.
- **Fail-safe.** Условие триггера → булевый флаг → `meta_text if flag else ""`. Любой сбой источника (RPC fail, exception, неожиданный shape) даёт пустую строку = identical-to-old behaviour. Это **обязательно** — META не должна блокировать генерацию.
- **Английский язык META** — единственный язык системного промпта Sage (mig 412 retired per-lang DB prompts). Модель пишет ответ в `Response language` независимо от языка META.
- **Не подменять системный промпт.** META — точечная коррекция; если **большая часть** реакций требует одного и того же поведения, это правка промпта, не META. Правило: 1 META = 1 узкое условие.
- **Видно в `journalctl`.** Все META попадают в `SAGE_MY_DAY_PROMPT` лог (с `\n` заменёнными на ` | `) — это и debug-поверхность, и proof-источник в KB.

## Implementation pattern (Python)

```python
# 1. Define META text as a function — keeps wording rotation-aware (no module-level f-string).
def _rule7_hard_guard_meta() -> str:
    return (
        "\n\n⚠️ META — RULE 7 HARD GUARD: <концретный next-move + 2-3 acknowledge-формулировки>"
    )

# 2. Compute trigger flag — fail-safe, never blocks.
try:
    just_logged_protein_g = float(payload.get("protein") or 0)
except (TypeError, ValueError):
    just_logged_protein_g = 0.0
rule7_hard_guard = just_logged_protein_g >= _RULE7_PROTEIN_G_THRESHOLD

# 3. Append to user_prompt builder (end of payload, last).
meta = _rule7_hard_guard_meta() if rule7_hard_guard else ""
return (
    f"... existing payload fields ..."
    f"{budget_directive}"
    f"{meta}"   # last → max LLM salience
)
```

## Order of MIGs in user_prompt (закон возрастания специфичности)

Чем специфичнее META, тем ближе к концу. На 2026-06-12 порядок такой:

**food_log path (`_build_user_prompt`):**
1. `Response language` (вечная строка)
2. `FINAL DIRECTIVE` (бюджет open/closed — общий)
3. `VARIATION GUARD` (репит-штамп лeверов — узкое)
4. `COLD-START PHASE` (0 логов + past breakfast — day-framing)
5. `BAN LIST` (конкретные foods из последних реакций — sharper guard) **NEW PR #386**
6. `RULE 7 HARD GUARD` (≥20 г Б в одном приёме — самое узкое)

**my_day path (`_build_my_day_prompt`):** rule7 не применим (no single-meal protein); остальное параллельно:
1. `Response language`
2. `time_meta_warning` (если `local_hour >= 16`)
3. `FINAL DIRECTIVE`
4. `VARIATION GUARD`
5. `COLD-START PHASE`
6. `BAN LIST`

Идея: если две META конфликтуют по смыслу, более специфичная (ниже в payload) выигрывает у модели.

## Когда НЕ использовать payload-meta

- Если коррекция нужна **большинству реакций** → это правка системного промпта, не META. META — для **меньшинства** случаев.
- Если триггер требует данных, которых нет в `ctx`/`payload` и подъём — **дорогой RPC ≥ 100 ms** → подумай дважды: SLA `click→render <700ms p95`. В PR #375 параллельный `asyncio.gather` (один RTT 44 ms) сделал стоимость нулевой; sequential второй RPC уже стоил бы +44 ms к p95.
- Если META повторяет то, что уже есть в системном промпте текстуально → модель проигнорирует обе. Помог только **конкретный** новый сигнал (не «не делай X», а «вот другой lever Y»).

## Live evidence — VARIATION GUARD / RULE 7 (2026-06-08, через 17 сек после deploy PR #375)

u786301802 (en, ES, female), 19:57:41 food_log на «Grilled chicken 825 ккал»:
- META: `RULE 7 HARD GUARD` приклеена (`payload['protein'] >= 20`).
- LLM-ответ: **«Protein landed! 🍗 Now, how about some leafy greens to round out the day?»** — модель **дословно** скопировала формулировку «protein landed» из META + выбрала другой lever (leafy greens), не курицу. Подтверждение, что МETA работает.

✅ **Resolved 2026-06-09 (PR [#376](https://github.com/sharkovvlad/noms-bot/pull/376))** — `VARIATION GUARD` не появлялся в `SAGE_MY_DAY_PROMPT`, потому что [services/sage.py:569](services/sage.py:569) `regen_my_day_insight_cache` вызывал `generate_my_day_insight(ctx, day_summary)` **без** пробрасывания `rpc_caller`. Default `rpc_caller=None` (был помечен `# reserved`) → `_fetch_recent_sage_reactions` сразу возвращал `[]` → META не приклеивалась. food_log-путь не страдал (handler прокидывал явно). Гипотезы из вчерашнего handover (SDK shape, фильтр `success=true`) **обе отметены**: `SupabaseClient.rpc` возвращает `response.json()` нативно, `success=t` для всех sage-логов на проде.

## Wiring gotcha — gотча pattern для всего семейства META

Любая новая META, которая зависит от RPC-данных (как `VARIATION GUARD`), требует:

1. **Optional `rpc_caller` параметр в leaf-функции** (`generate_*_comment`/`generate_*_insight`) — стандарт уже принят.
2. **ВСЕ оркестраторы выше по стеку** (`regen_*_cache`, handler-уровневые вызовы) пробрасывают `rpc_caller=rpc_caller` **явно**. Не «когда вспомнится», а с момента введения параметра.
3. **Wiring test, не leaf test.** Unit-тест с `rpc_caller=AsyncMock(...)` прямо в leaf-функцию доказывает «лист работает». Это **не доказывает**, что вызывающий код передаёт `rpc_caller`. Канонический шаблон — `test_regen_my_day_cache_forwards_rpc_caller_for_repeat_meta` (один моковый rpc-каллбэк отвечает на оба RPC, ассертится содержимое финального OpenAI-промпта).

Это конкретное применение общего правила из `feedback_integration_tests_rpc.md` (auto-memory): «unit-моки скрывают contract drift». Здесь drift был на уровне call-site, а не контракта RPC, но симптом тот же — все тесты зелёные, прод тихо отключён.

## Telemetry coverage gotcha — родственная грабля (PR [#379](https://github.com/sharkovvlad/noms-bot/pull/379), 2026-06-09)

Параллельный класс багов: META **работает**, генерация **работает**, но один из 9 return-путей `generate_food_log_comment` **не пишет в `ai_coach_logs`** → `/sage-tov` судья и `transcripts/sage_*.md` считают эти реакции «отсутствующими», хотя пользователь их видел (pre-baked fallback).

**Инциденты (false positives транскрипта):**
- 2026-06-07 13:12 u6378579500 — edit-флоу, hard-skip `editing_meal` → `return None`, без telemetry.
- 2026-06-08 19:29 u520145707 «Борщ» — gpt-4o-mini > 5050ms → handler `pick_food_log_fallback` → pre-baked ru-фраза показана, без telemetry.

**Корневое правило:** если у функции, генерирующей наблюдаемое поведение, **>1 return path**, КАЖДЫЙ user-visible путь обязан писать в общий sink (`ai_coach_logs`) с **различимым маркером**. Иначе observability — лотерея, и одна сессия исследования может пойти по ложной гипотезе («2 пустые реакции за 2 дня») вместо реальной картины («N невидимых fallback'ов в неделю»).

**Канонический шаблон (Sage):**

| Параметр | Happy path | Fallback path | Designed pre-baked (maternal/underage/underweight) |
|---|---|---|---|
| `context_type` | `sage_food_log` | `sage_food_log` (тот же — судья видит хронологически) | `sage_food_log` |
| `success` | `True` | `False` | `True` |
| `error` | `NULL` | `<branch_tag>` (`openai_err: TimeoutError`, `json_parse`, `sanity_reject`, `closed_budget_leak`, `handler_wait_for_timeout`, `safety_guard_skip`) | `NULL` |
| `model` | `gpt-4o-mini` | `pre_baked` | `pre_baked_guarded_<namespace>` |
| `cached` | `False` | `True` (derived from `model.startswith("pre_baked")`) | `True` |
| `ai_message` | LLM-текст | pre-baked текст, увиденный юзером | pre-baked maternal/etc текст |

**Implementation tip:** `_fire_sage_telemetry` принимает `success`/`error`, шим `_fire_food_log_fallback_telemetry(ctx, error=..., payload=..., pre_baked=...)` сокращает каждую ветку до одной строки. `cached` выводится из `model`, не передаётся отдельно — это держит таблицу консистентной без +1 параметра на каждом callsite. См. `services/sage.py` после PR #379 как референс.

**Wiring test:** unit-тест на каждый branch с `patch.object(sage, "_fire_sage_telemetry", spy)` + ассертом `spy.call_count == 1` и точного `error`-tag'а. Это **не** тест на леф (sage сам по себе уже покрыт), а тест на **observability-contract** — что branch X эмитит ровно одну строку с правильным маркером.

**Связь с wiring gotcha выше:** оба случая — class «leaf работает, oркестратор/обёртка молчит». В META-кейсе молчал `rpc_caller`, в telemetry-кейсе молчал `_fire_sage_telemetry`. Оба ловятся одинаковым подходом: тест на **wiring**, не на лист.

## Related Concepts

- [[concepts/sage-food-log-llm-integration]] — host архитектура Sage; META — один из её слоёв
- [[concepts/python-vs-n8n-template-grammar]] — payload-format vs system-prompt-format разница
- [[concepts/sassy-sage-dialog-variants]] — фоллбэки и вариативность Sage

## Sources

- `services/sage.py` — `_repeat_suppression_meta`, `_rule7_hard_guard_meta`, `_budget_directive`, `time_meta_warning`, `_fire_sage_telemetry`, `_fire_food_log_fallback_telemetry`
- `migrations/496_sage_recent_reactions_rpc.sql` — RPC за `VARIATION GUARD`
- `tests/services/test_sage_repeat_suppression.py` — coverage META-плумбинга
- `tests/services/test_sage.py` § «Telemetry on user-visible fallback paths» — wiring-тесты для каждого branch'а (PR #379)
- `handover/2026-06-08_sage-payload-meta.md` — 5-минутный брифинг
