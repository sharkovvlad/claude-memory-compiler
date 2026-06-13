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

Применяется в **10 живых местах** (по состоянию на 2026-06-13). Порядок в payload = возрастание специфичности; `language_lock` ВСЕГДА последний (end-of-context salience):

| META | Условие триггера | Когда добавлен |
|---|---|---|
| `time_meta_warning` | `local_hour >= 16` (my_day only) | 2026-05-29 (mig 29.05) — бот говорил «morning» в 18:57 |
| `closed-budget directive` / `budget_directive` | `remaining_kcal <= 0` (explicit) — всегда тегается в metas_fired | 2026-06-07 (PR закрытого бюджета) |
| `VARIATION GUARD` / `variation_guard` | `_PROTEIN_STAMP_RE` совпадает в ≥1 из последних 2 реакций (RPC `get_recent_sage_reactions` + race-fix `just_emitted_food_log` PR #383) | 2026-06-08 (PR #375), race-fix 2026-06-12 (PR #383) |
| `RULE 7 HARD GUARD` / `rule7_hard_guard` | `payload['protein'] >= 20` (food_log only) | 2026-06-08 (PR #375) |
| `COLD-START PHASE` / `cold_start_phase` | `meals_count == 0 AND meal_period != "breakfast"` | 2026-06-12 (PR #385) |
| `BAN LIST` / `ban_list` | foods из таблицы `_FOOD_MENTIONS` совпали в последних 2 реакциях (Agent 2's предложение, sharper чем VARIATION GUARD) | 2026-06-12 (PR #386) |
| `late_night_close` / `late_night_soft` | `local_hour >= 22` (flag `sage_late_night_close_enabled`); soft-ветка на my_day при severe_deficit+protein<60%+kcal<80% | 2026-06-12 evening (PR #392, mig 503) |
| `quiet_steady_no_push` | `day_status == 'quiet_steady'` (my_day only) — HARD guard no-push | 2026-06-13 (PR #396) |
| `silent_presence` | food_log: master flag `sage_silent_presence_enabled` + meal balanced (fat≤45% kcal) + day kcal ∈ [40,95]% + wellbeing не красное; suppressed при budget_closed/late_night. **food_log-параллель quiet_steady_no_push.** Default flag `false`. | 2026-06-13 (PR #401, mig 507) — [[concepts/sage-silent-presence-mode]] |
| `language_lock` | любой язык (always-on, always-LAST) — пинит output language под heavy context | 2026-06-13 (PR #396 hotfix Hindi→RU leak) |

**Generic-паттерн «voice card ≠ META»** (2026-06-13): большинство META ссылаются на **voice card** в системном промпте (Card D для quiet_steady, Card S для silent_presence, Card I-SOFT для late_night). Card = always-in-prompt **reference example** (как звучать). META = conditional **trigger** (когда входить в режим) + ссылка на нужную card. Карточка сама ничего не меняет — без META модель не знает, что пора. При добавлении нового режима тишины/тона — нужны ОБЕ части.

**Context-signal ≠ META, но требует prompt-инструкции** (PR-3c, 2026-06-13): `Goal`, `Last log`, `Recent pattern (7d)` — это НЕ META (не tail-cascade), а **context-строки** в теле payload. Но: **новый context-сигнал, добавленный без directive-инструкции в системном промпте КАК его использовать, под-весится моделью** — сильные rule'ы навигации побеждают. Live-кейс: weekly-pattern строка «large single logs NORMAL (keto)» игнорировалась → модель пушила углеводы кето-юзеру. Fix = блок `WEEKLY PATTERN AWARENESS` в обоих промптах (делает строку actionable). **Правило:** payload context-строка + соответствующая prompt-инструкция = пара (структурно как card+META). unit-тесты под-весивание НЕ ловят → MANDATORY dry-run. См. [[sage-silent-presence-mode]] и weekly-pattern (RPC `get_weekly_pattern`, mig 509, food_log+my_day surfaces).

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
7. `LATE-NIGHT CLOSE` (если `local_hour >= 22` — h-time gate, специфичнее всех meal-guard'ов)
8. `LANGUAGE LOCK` (always-on, max end-of-context salience)
9. `STREAK NAMING LOCK` (PR #402, 2026-06-13 EOD — самый last META; `lang != en` AND `streak_n > 0` AND lang ∈ {ru,uk,ar,es,fr,it,de,pt,pl})

**my_day path (`_build_my_day_prompt`):** rule7 не применим (no single-meal protein); остальное параллельно:
1. `Response language`
2. `time_meta_warning` (если `local_hour >= 16`)
3. `FINAL DIRECTIVE`
4. `VARIATION GUARD`
5. `COLD-START PHASE`
6. `BAN LIST`
7. `LATE-NIGHT CLOSE`
8. `QUIET STEADY NO PUSH` (если `day_status == 'quiet_steady'`)
9. `LANGUAGE LOCK`
10. `STREAK NAMING LOCK` (PR #402)

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

## Voice cards as primary tone anchor (PR #392, 2026-06-13)

**Suite of 6 META — но monoculture не лечилась.** К 06-12 у нас 6 META (rule7, variation_guard, ban_list, cold_start_phase, budget_directive, time_meta_warning) + 13 enum'ов `day_status` + сжатый my_day-prompt. Главная метрика «≤25% реакций с предписанием еды» не сдвинулась с 92→91% за месяц cycle'ов. `emotion=smirk` ВЫРОС с 80% → 100% (curse-of-instructions). Live triage 200 реакций показал: 31% «как насчёт», 31% «куриного филе», 30% «чтобы сбалансировать», 72% food emoji.

**Корневая проблема — диспропорция positive vs negative space в промптах.** Системные промпты на ~80% состоят из FORBIDDEN-блоков, DAY STATUS HINTS, anti-pattern-описаний. Positive space (как голос Номса реально звучит) — одна строка про 70/30 bro/scientist + 5 примеров TONE SHAPE — RULE 7b. Модель cargo-cult'ит дефолтный шаблон gpt-4o-mini под «friendly nutritional advice», а не character spec, потому что **примеров character spec в промпте почти нет**.

**Fix:** 8 voice cards между `YOUR CHARACTER` и `GENERATION RULES` в **обоих** системных промптах:
- food_log (Cards A–C): closed-budget close · Rule 7b balanced · open-budget varied push
- my_day (Cards D–H): quiet_steady (no push) · cold_start · target_met_fat_heavy · severe_deficit safety · fasting_logged

Cards написаны на русском (single-source per mig 412); output language — payload параметр `Response language`. **Никаких per-language `ui_translations` строк** для voice cards не нужно — это часть Python-промпта, не screen-level UI. Каждая card помечена `emotion=...` чтобы вынудить вариативность (D/E/G/H = sage, A/B/C/F = smirk) — это разрушает 100% smirk monoculture.

**Anti-patterns в эталонах (флагнуты на цикле 06-12):**
1. **Самореференс character'a** — «метаболическому навигатору тут ловить нечего» = breakage 4-й стены. Никогда не упоминать роль персонажа внутри ответа.
2. **«лишних калорий» / «лишний жир»** — anti-shame trigger, той же категории что «перебор» (уже в FORBIDDEN). Слово «лишний» в любой форме при еде → shame.
3. **Псевдонаучные «системы»** — «метаболическая система уходит на ночной покой» — такой системы в физиологии не выделяют. Sage scientist part обязан использовать настоящие термины (метаболизм, обмен веществ) или не использовать никакие.
4. **Functional medical claims** — «X поддержит мышцы и ЦНС» / «улучшает Y» — псевдомедицинский claim, нарушает FORBIDDEN-блок (anti-medical-claim policy).
5. **DB-операционные глаголы** — «Творог зафиксирован» звучит как лог-row, не как человек. Живые формулы — «Творог в деле», «Творог пошёл».

**Snapshot test:** `tests/services/test_sage_late_night_close.py::test_food_log_system_prompt_contains_voice_cards` ассертит конкретные строки эталонов в `_DEFAULT_SYSTEM_PROMPT_EN` / `_DEFAULT_SYSTEM_PROMPT_MY_DAY_EN`. Любая случайная правка (кто-то «упрощает» Card B) провалит тест и оповестит code review.

## late_night_close META — owner-mandated h≥22 cutoff (PR #392)

**Owner-фраза 2026-06-12:** «Я бы поправил ещё и то что наш Номс после 10 вечера не рекомендовал бы съесть ещё что-то.»

**Нутрициологическое обоснование:** Sutton 2018 / Cienfuegos 2020 / Chow 2020 (time-restricted eating) — eating window заканчивается за 2-4 часа до сна → улучшение glucose response, insulin sensitivity. NHANES Sun 2021 — energy intake ≥20-21:00 ассоциируется с худшим HbA1c, BMI, особенно при high glycemic load. Crispim 2011 — meals <2h до сна → fragmented sleep, GERD. Для среднего bed-time 23:30-00:30 — **h≥22 правильный default cutoff**.

**Critical safety nuance:** мы **не** говорим «не ешь» (это РПП-trigger для restriction-prone юзеров). Мы перестаём **пушить**. Команда «не ешь» = safety violation. Тишина = безопасно.

```python
def _late_night_close_meta(local_hour, *, day_status=None, protein_pct=None, kcal_pct=None):
    if local_hour < 22:
        return None
    soft_eligible = (
        day_status in ("severe_deficit", "under_target_evening")
        and protein_pct < 60.0 and kcal_pct < 80.0
    )
    if soft_eligible:
        return (SOFT_TEXT, "late_night_soft")    # «творог / йогурт без сахара» — soft
    return (HARD_TEXT, "late_night_close")        # next_meal_suggested=false принудительно
```

**Две ветки:**
- **HARD CLOSE** (default): force `next_meal_suggested=false`, character-driven close. Soft «утром продолжим» note allowed.
- **SOFT** (rare exception): when `day_status in (severe_deficit, under_target_evening) AND protein_pct<60 AND kcal_pct<80`. Условие срабатывает только если день реально тонкий по калориям И протеину, И юзер только что что-то залогировал. Одна optional фраза «если голод реальный — пара ложек творога» допустима, но `next_meal_suggested` остаётся `false` (условное, не предписание).

**food_log surface не имеет `day_status`** (вычисляется на my_day level через `_compute_day_status`). Поэтому food_log call всегда лендится в HARD CLOSE. SOFT-исключение работает только на my_day. Это acceptable: SOFT для thin-day цикла, который детектится на day level.

**Gate за `app_constants.sage_late_night_close_enabled`** (mig 503, default `true`). Rollback одной командой:
```sql
UPDATE public.app_constants SET value='false' WHERE key='sage_late_night_close_enabled';
```

**Telemetry tags:** `metas_fired` включает `late_night_close` (hard) ИЛИ `late_night_soft` (soft). Никогда оба одновременно.

**Order в META cascade** (по возрастанию специфичности, gpt-4o-mini weighs end-of-context):
1. `time_meta_warning` (h≥16, my_day only)
2. `budget_directive` (always)
3. `variation_guard` (recent reactions push protein)
4. `cold_start_phase` (0 logs + past breakfast)
5. `ban_list` (specific foods named recently)
6. `rule7_hard_guard` (food_log only, just-logged ≥20g protein)
7. `late_night_close` / `late_night_soft` (h≥22)
8. `quiet_steady_no_push` (my_day only, `day_status == 'quiet_steady'`)
9. `language_lock` (always-on, PR #392 cascade — primes output language at end)
10. `streak_naming_lock` (PR #402, 2026-06-13 EOD — **самая last META**, lexical guard поверх language-lock)

## STREAK NAMING META — token-copy defence (PR #402, 2026-06-13 EOD)

**Owner-observed bug:** 4/5 RU my_day реакций за 24h писали «Стreak»/«стрика»/«стрике» вместо canonical «серия» из KB-glossary. Root cause: payload-line `Streak: 42 days` сидит **рядом** с числом, gpt-4o-mini под heavy non-EN context копирует/транслитерирует токен. System-prompt FORBIDDEN clause существует (line 2322, 2437 services/sage.py), но погребена в ~500 токенах CULTURE GUARD + VOICE EXAMPLES — низкая salience для end-of-context-weighted модели.

**Двухчастный fix:**
1. **Payload rename** — убрать буквальный токен из data-section: `«Streak: N days»` → `«Day streak count: N»` в обоих `_build_user_prompt` (food_log) и `_build_my_day_prompt` (my_day). Не дать модели начать «копировать соседнее слово».
2. **`_streak_naming_meta(language, streak_n)`** — HARD GUARD приклеивается AFTER `_language_lock_meta` (самый tail). Содержит конкретное native-слово на языке юзера + явный банлист («стрик/стрика/стрике/Стreak/стрік/ستريك/استریک/Streak») + warning про mixed-script. Покрывает 9 langs из Sage-prompt FORBIDDEN clause: `ru/uk/ar/es/fr/it/de/pt/pl`. FA/HI/ID — fallback на existing FORBIDDEN clause (Sage prompt не пинит native для них; KB-glossary даёт mixed signals).

**Verification** (dry-run + ad-hoc):
- Dry-run × 2 на 8 baseline сценариях: **16/16 ✓ clean**. Scenario 2 (RU/quietsteady/streak=12) оба раза вернул «**серия**». Scenario 4 (AR/coldstart/streak=7) использовал «**سلسلة**» в pass-2.
- Ad-hoc 5× принципиальный repro owner-сценария (RU/streak=42/my_day/19h): **0/5 bad** (vs baseline 4/5).

**Durable lesson:** промпт-side FORBIDDEN clause **недостаточен** для gpt-4o-mini когда конкретный токен-источник сидит в payload рядом с ключевым числом. Reliable fix = **payload rename** (убрать токен) + **per-language tail-anchored HARD GUARD** (конкретное native + банлист). Pattern composable со всеми остальными META (language_lock, quiet_steady, late_night). Если в будущем добавится новая meaningful поле, рядом с которой может появиться меняющий tone token — повторить этот шаблон.

**Apply этого шаблона к будущим bug-классам:** любой случай «модель копирует токен из payload-name field вместо переписать его на target language» лечится этим pattern'ом. Tell-tale sign в `ai_coach_logs`: текст содержит токен из payload буквально или транслитерированно.

## Related Concepts

- [[concepts/sage-tone-dry-run-protocol]] **`🔥 MANDATORY pre-merge`** — Любая правка добавляемая в эту страницу (новая META, изменение системного промпта, изменение порядка cascade) обязана пройти dry-run протокол ДО merge. PR #396 = первое применение, поймало 2 critical bug которые unit-тесты не ловили.
- [[concepts/sage-food-log-llm-integration]] — host архитектура Sage; META — один из её слоёв
- [[concepts/python-vs-n8n-template-grammar]] — payload-format vs system-prompt-format разница
- [[concepts/sassy-sage-dialog-variants]] — фоллбэки и вариативность Sage

## Sources

- `services/sage.py` — `_repeat_suppression_meta`, `_rule7_hard_guard_meta`, `_budget_directive`, `_late_night_close_meta` (PR #392), `_language_lock_meta` / `_quiet_steady_no_push_meta` (PR-3a), `_streak_naming_meta` + `_STREAK_NATIVE_WORD` mapping (PR #402, 2026-06-13 EOD), `time_meta_warning`, `_fire_sage_telemetry`, `_fire_food_log_fallback_telemetry`, voice cards в `_DEFAULT_SYSTEM_PROMPT_EN` / `_DEFAULT_SYSTEM_PROMPT_MY_DAY_EN`
- `migrations/496_sage_recent_reactions_rpc.sql` — RPC за `VARIATION GUARD`
- `migrations/503_sage_late_night_close_flag.sql` — флаг late_night_close (PR #392)
- `migrations/508_streak_native_words_audit.sql` — UI-хардкоды `progress.skip_streak_chip` для UK/FA/HI/ID, native-слова из KB (PR #402; originally apply'нут как 507, renumbered после CI sanity-guard collision)
- `tools/audit_streak_literal.py` — reusable audit для streak-токенов в `ui_translations` (case-insensitive cyr-транслитерации)
- `tools/sage_dry_run_streak_only.py` — 5× repro owner-сценария RU/streak=42 (тип теста для аналогичных tone-bugs)
- `tests/services/test_sage_repeat_suppression.py` — coverage META-плумбинга
- `tests/services/test_sage_late_night_close.py` — coverage late_night branching + snapshot voice cards (PR #392)
- `tests/services/test_sage.py` § «Telemetry on user-visible fallback paths» — wiring-тесты для каждого branch'а (PR #379)
- `handover/2026-06-08_sage-payload-meta.md` — 5-минутный брифинг
- `handover/2026-06-12_sage-tov-cycle.md` — handover циклов 06-08…06-12
- `daily/2026-06-13.md` — PR #392 closeout
