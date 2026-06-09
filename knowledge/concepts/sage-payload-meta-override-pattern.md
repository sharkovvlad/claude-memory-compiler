---
title: "Sage payload-meta override — паттерн влияния на тон без правки системного промпта"
aliases: [payload-meta, sage-meta-override, meta-warning, time-meta-warning, variation-guard, rule-7-hard-guard]
tags: [sage, llm, prompt-engineering, architecture, python]
sources:
  - "daily/2026-05-29.md"
  - "daily/2026-06-07.md"
  - "daily/2026-06-08.md"
  - "daily/2026-06-09.md"
  - "handover/2026-06-08_sage-payload-meta.md"
created: 2026-06-08
updated: 2026-06-09
---

# Sage payload-meta override — паттерн

Способ скорректировать поведение LLM-генератора Sassy Sage **без правки системного промпта** (`_DEFAULT_SYSTEM_PROMPT_*` в `services/sage.py`). Используется когда системный промпт — это **бренд** и требует owner-approval на каждое изменение, а нужная коррекция — точечная и data-driven.

Применяется в 4 живых местах (по состоянию на 2026-06-08):

| META | Условие триггера | Когда добавлен |
|---|---|---|
| `time_meta_warning` | `local_hour >= 16` | 2026-05-29 (mig 29.05) — бот говорил «morning» в 18:57 |
| `closed-budget directive` | `remaining_kcal <= 0` (explicit) | 2026-06-07 (PR закрытого бюджета) |
| `VARIATION GUARD` | `_PROTEIN_STAMP_RE` совпадает в ≥1 из последних 2 реакций (RPC `get_recent_sage_reactions`) | 2026-06-08 (PR #375) |
| `RULE 7 HARD GUARD` | `payload['protein'] >= 20` (food_log only) | 2026-06-08 (PR #375) |

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

Чем специфичнее META, тем ближе к концу. На 2026-06-08 порядок такой:

1. `Response language` (вечная строка)
2. `time_meta_warning` (если evening)
3. `FINAL DIRECTIVE` (бюджет open/closed — общий)
4. `VARIATION GUARD` (репит-штамп — узкое)
5. `RULE 7 HARD GUARD` (≥20 г Б в одном приёме — самое узкое)

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

## Related Concepts

- [[concepts/sage-food-log-llm-integration]] — host архитектура Sage; META — один из её слоёв
- [[concepts/python-vs-n8n-template-grammar]] — payload-format vs system-prompt-format разница
- [[concepts/sassy-sage-dialog-variants]] — фоллбэки и вариативность Sage

## Sources

- `services/sage.py` — `_repeat_suppression_meta`, `_rule7_hard_guard_meta`, `_budget_directive`, `time_meta_warning`
- `migrations/496_sage_recent_reactions_rpc.sql` — RPC за `VARIATION GUARD`
- `tests/services/test_sage_repeat_suppression.py` — coverage META-плумбинга
- `handover/2026-06-08_sage-payload-meta.md` — 5-минутный брифинг
