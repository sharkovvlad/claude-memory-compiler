---
title: "Sage Food Log LLM Integration — gpt-4o-mini one-liner после каждого food log"
aliases: [sage-llm, noms-comment, food-log-sage, openai-integration, sage-food-log, sage-v2, noms-emotion-emoji]
tags: [llm, openai, food-log, sage, architecture, python]
sources:
  - "daily/2026-05-22.md"
  - "daily/2026-05-23.md"
  - "daily/2026-05-24.md"
  - "daily/2026-05-25.md"
created: 2026-05-22
updated: 2026-06-01
---

# Sage Food Log LLM Integration

Первый OpenAI API call в кодовой базе NOMS. gpt-4o-mini генерирует one-liner от Sassy Sage после каждого food log confirmation. Архитектурный паттерн: parallel `asyncio.create_task` + `wait_for(timeout)` с graceful fallback на pre-baked deterministic фразы.

## Key Points

- **Модуль:** `services/sage.py` (407 LOC) — reference implementation для всех будущих Python LLM calls в NOMS.
- **Интеграция:** `handlers/food_log.py:render_food_log_confirmation` → `asyncio.create_task(generate_noms_comment)` → `asyncio.wait_for(timeout)`. Вызывается из 3 точек: `handle_ai_input` (Stage 7a), `_handle_edit_meal_input` (Stage 7b), `/internal/food_log/render` endpoint (legacy n8n callback).
- **ZERO дополнительных RPC.** Все данные для safety-checks приходят из `ctx` (UserCtx) — mig 312 расширила `v_user_context` 6 полями: `is_pregnant`, `is_lactating`, `shown_guards`, `diet_type`, `last_log_date`, `cycle_phase`.
- **5 safety paths:** РПП guard → return None; pregnant/lactating → pre-baked maternal; age <18 → pre-baked underage; BMI <18.5 → pre-baked underweight; editing_meal → skip. Junction maternal+underweight → maternal wins.
- **Cost:** 114 logs/день × $0.0002 ≈ **$0.70/мес**. Flag-flippable: `app_constants.sage_food_log_enabled` + `sage_food_log_model`.
- **Timeout calibration (lesson):** initial 1500ms оказался оптимистичным — gpt-4o-mini с ~700 token prompt уходит в tail 1.5-2s от VPS Hetzner. Поднят до 2500ms hot-flip'ом через `app_constants` без деплоя.

## Details

### Архитектура

```
handlers/food_log.py:render_food_log_confirmation(update, ctx, rpc_result)
    ↓ asyncio.create_task(_generate_sage_comment(...))
    ↓ asyncio.wait_for(task, timeout=sage_food_log_timeout_ms + 50ms)
    ↓ join: если success → embed "💬 Noms: «{comment}»" в confirmation card
    ↓         если timeout/error → fallback pre-baked phrase или skip
    ↓
ResponseEnvelope → telegram_send
```

**Parallel по design:** LLM call не блокирует основной render path. Если таймаут — карточка рендерится без Sage блока. Graceful degradation подтверждена live-тестом 22.05.

### Safety paths (5 уровней)

| # | Условие | Поведение | Обоснование |
|---|---|---|---|
| 1 | `users.shown_guards` содержит `safety_guard_*` | return None (skip Sage) | Modal + banner + Sage = sensory overload для юзера с РПП/BMI-guard |
| 2 | `is_pregnant=TRUE` OR `is_lactating=TRUE` | Pre-baked maternal фраза | Medical context → deterministic, не generative |
| 3 | age <18 (из `ctx.birth_date`) | Pre-baked underage (growth-focused) | FTC/California legal — LLM не гарантирует child-safe |
| 4 | BMI <18.5 (proxy из weight/height) | Pre-baked underweight (no weight talk) | Anti-shame: LLM может ляпнуть "похудение" |
| 5 | status=`editing_meal` | Skip | Техническая корректировка, Sage не нужен |

**Junction rule:** pregnant + underweight → maternal wins (medical priority).

### Pre-baked fallback

Deterministic выбор через `hash(telegram_id + date)` из JSONB arrays в `ui_translations.sage.*`:

```python
idx = hash(f"{telegram_id}:{date.isoformat()}") % len(variants)
return variants[idx]
```

Per-day rotation — юзер видит одну фразу на протяжении дня, но разную на следующий день. Паттерн из [[concepts/sassy-sage-dialog-variants]].

Mig 312 засеяла 5 namespace'ов × 3-7 фраз × RU+EN:
- `sage.food_log_generic` — default
- `sage.food_log_guarded_maternal` — для беременных/кормящих
- `sage.food_log_guarded_underage` — для <18
- `sage.food_log_guarded_underweight` — для BMI <18.5
- `sage.food_log_editing` — skip (return None)

### Output sanity filter

Universal regex (не semantic):
```python
# Отвергаем если:
# - содержит HTML tags
# - содержит URL
# - содержит @ mention
# - длина > 200 chars
```

**НЕ** semantic РПП vocabulary filter. 13 langs taboo lexicon = unmaintainable; system prompt обязан не генерировать shame-content. Если генерирует — фикс в prompt, не в post-filter.

### Timeout calibration (lesson 22.05)

| Timeout | Результат canary |
|---|---|
| 1500ms (initial) | Sage блок НЕ появился — gpt-4o-mini tail latency 1.5-2s |
| 2500ms (hot-flip) | Sage блок появляется стабильно |

**Hot-flip pattern:** `UPDATE app_constants SET value='2500' WHERE key='sage_food_log_timeout_ms'` → cache trigger → `ctx.constants` подхватывает на следующем webhook'e (60s TTL). Никакого деплоя.

**Trade-off принят:** +2.5s к food log flow допустимо, потому что юзер и так ждёт 3-5s на AI parse (GPT-4o Vision). SLA <700ms p95 из CLAUDE.md относится к inline-button clicks (menu navigation), не к food log AI flow.

### Cost model

```
gpt-4o-mini pricing: $0.15/1M input, $0.60/1M output
Average call: ~600 input tokens (system) + ~100 (user) = ~700 in, ~50 out
Per-call: ($0.15 × 700 / 1M) + ($0.60 × 50 / 1M) = $0.000105 + $0.00003 ≈ $0.000135
Daily 114 logs: ~$0.015/day
Monthly: ~$0.46
```

Реальное $0.70/мес с margin — negligible. Model switchable через `app_constants.sage_food_log_model` для A/B с gpt-4o если tone unsatisfactory.

### Migration 312

Single TX, applied 2026-05-22 16:30 MSK:
1. `v_user_context` VIEW расширена +6 полей (DROP+CREATE) — `is_pregnant`, `is_lactating`, `shown_guards`, `diet_type`, `last_log_date`, `cycle_phase`
2. `app_constants` — 5 keys: `sage_food_log_enabled=false`, `sage_food_log_model=gpt-4o-mini`, `sage_food_log_timeout_ms=1500`, `sage_food_log_max_tokens=80`, `sage_food_log_temperature=0.9`
3. `ui_translations` — 5 namespace'ов × RU+EN = 10 key groups
4. Verification DO block — 6 view cols + 5 flags + 5×2 langs checked

### Key files

| File | LOC | Purpose |
|---|---|---|
| `services/sage.py` | 407 | LLM call + safety paths + pre-baked fallback |
| `tests/services/test_sage.py` | 394 | 26 unit tests |
| `handlers/food_log.py` | +42 | asyncio.create_task + wait_for join |
| `dispatcher/context.py` | +6 fields | UserCtx.is_pregnant/is_lactating/shown_guards/diet_type/last_log_date/cycle_phase |
| `migrations/312_sage_food_log_foundation.sql` | 412 | VIEW + translations + flags |

## Gotchas

- **`effective_goal_type` из `calculate_user_targets` НЕ зовётся.** Для one-liner tone selection достаточно proxy (raw `ctx.goal_type` + guards check). Не точно на 100% для edge cases (pregnancy force-maintain), но вызов RPC добавил бы +50ms на hot path. Lesson из [[concepts/safety-guard-ux-pattern]] §9b — для production-critical paths (Sage timeline, LLM recommendations) используй `effective_goal_type`, для one-liner допустим proxy.
- **`v_user_context` VIEW DROP+CREATE** при каждом расширении schema — нужен координационный коммент в миграции. Параллельный агент может тоже расширять VIEW.
- **System prompt не кешируется** — gpt-4o-mini не поддерживает prompt caching ≥1024 tokens (OpenAI announces, но не для mini). При переходе на gpt-4o — prompt caching сработает.

## Sage v2 — JSON mode + emotion→emoji + macros focus (2026-05-23)

### Overview

PR #160 (mig 314) + PR #161 (mig 315) — полный переход с «plain text one-liner» на **structured JSON response** с эмоциональным маркером. Sage теперь возвращает `tuple[str, str] | None` вместо `str | None`.

### JSON mode

`response_format={"type": "json_object"}` → LLM обязан вернуть валидный JSON:

```json
{"text": "Углеводный удар в полночь — твой инсулин сейчас в шоке.", "emotion": "side-eye"}
```

4 возможных emotion: `smirk | proud | side-eye | sage`. Каждая маппится на `telegram_custom_emoji_id` + fallback char через `EMOTION_TO_EMOJI` dict в `sage.py`.

**Преимущества JSON mode vs plain text:**
- Гарантированный parseable output (OpenAI validates JSON schema)
- Emotion field отделён от text → нет «prompt injection через emoji в тексте»
- Fallback при parse error → pre-baked phrase (graceful)

### Emotion → Telegram Custom Emoji

```python
EMOTION_TO_EMOJI = {
    "smirk":    ("<tg_custom_emoji_id_smirk>",    "😏"),
    "proud":    ("<tg_custom_emoji_id_proud>",     "💪"),
    "side-eye": ("<tg_custom_emoji_id_side_eye>",  "👀"),  # ID pending from owner
    "sage":     ("<tg_custom_emoji_id_sage>",      "🧠"),  # ID pending from owner
}
```

В HTML рендеринге food log confirmation: `<tg-emoji emoji-id="...">fallback</tg-emoji>` обёртка. Telegram-клиент показывает custom emoji если поддерживает, fallback char если нет.

**Pending owner action:** `side-eye` + `sage` custom emoji IDs ещё не предоставлены. До предоставления — fallback chars `👀` / `🧠`.

### Macros Focus computation

Новый helper `_compute_macros_focus()` определяет доминирующий макро-нутриент по % от калорий:

| Условие | Focus label |
|---|---|
| protein_pct > 35% | `High Protein` |
| carbs_pct > 60% | `High Carbs` |
| fat_pct > 45% | `High Fat` |
| все в пределах | `Balanced` |
| total_kcal < 200 | `Low Calories` |

Focus передаётся в LLM prompt как контекст для tone selection — high protein meal от фитнесиста → proud; midnight carb binge → side-eye.

### Расширенный user prompt

`_build_user_prompt` переписан, теперь включает:
- **User Local Time** (для meal-phase-aware tone)
- **Meal Phase** (breakfast/lunch/dinner/late-night — вычисляется из local hour)
- **Food Summary** (items + kcal)
- **Macros Focus** (из `_compute_macros_focus`)
- **Daily Remaining** (kcal left)
- **Streak** (текущий)
- **Diet** (`diet_type` из ctx)
- **Notifications Mode** (zen/balanced/beast — определяет verbose level)
- **Silent Context** (pregnancy/lactation/underweight → tone softener)

`tamagotchi_stage` **УБРАН** из prompt — Noms prohibits Pet references в LLM output (character redesign).

### Mig 314 — header prefix update

- Убрана header line из food log confirmation (Sage comment теперь единственный commentary)
- `noms_comment_prefix` обновлён `"💬 Noms"` → `"Noms 💬"` × 13 langs
- `_MAX_OUTPUT_CHARS` поднят 200→280 (30-char headroom над 250 target)

### Mig 315 — Fallback phrases × 13 languages

Заменены старые mig 312 «Pet-style» fallback (ru+en only) на Noms v2 «neurons overloaded» brand voice. 5 вариаций на каждый из 13 языков (65 строк total). Пример (ru):

1. «Нейросети перегрелись, дайте секунду...»
2. «Мои алгоритмы задумались. Это нормально.»
3. «Процессор думает. Подожди, не убегай.»
4. «Система перезагружается. Шучу, просто тормоз.»
5. «Вычислительная мощность закончилась. Как и мана.»

### Hot DB tuning (applied to prod, no migration)

| Constant | Old | New | Reason |
|---|---|---|---|
| `sage_food_log_temperature` | 0.9 | 0.7 | Менее random, более consistent tone |
| `sage_food_log_max_tokens` | 80 | 300 | Cyrillic tokenization ~1.5 tokens/char; 80 tokens = ~53 chars, обрезал выводы |
| `sage_food_log_timeout_ms` | 2500 | 2500 | Не менялся; VPS→OpenAI RTT ~968ms, 1500ms was too tight |

### Migration collision lesson

Mig 314 изначально пронумерована 313 → столкнулась с `mig 313 delete-account-blocker` от параллельного агента в main. Renumbered to 314 через стандартный collision-guard процесс.

### Key file changes

| File | Change |
|---|---|
| `services/sage.py` | JSON mode, `_compute_macros_focus`, `EMOTION_TO_EMOJI`, tuple return |
| `handlers/food_log.py` | Tuple unpacking, tg-emoji HTML render, rounded macros |
| `dispatcher/context.py` | `notifications_mode` field added to UserCtx |
| `migrations/314_food_log_ux_header_prefix.sql` | Header removal + prefix swap × 13 langs |
| `migrations/315_sage_fallback_13langs.sql` | 5 fallback variants × 13 langs |

60 tests pass (расширение suite с 26 до 60 — покрытие JSON parse, emotion mapping, macros focus, fallback selection).

## Sage v3 — timeout fix + emoji rollback + always-fallback (2026-05-24)

### Timeout bump 2.5→5s (mig 321)

Outer `asyncio.wait_for(sage_task, timeout=2.55s)` иногда срабатывал ДО inner OpenAI client `timeout=2.5s`. 50ms headroom тесный при network jitter → handler писал `skip comment` → food card рендерился **без Noms-comment**.

Fix: `sage_food_log_timeout_ms` hot-flip `2500→5000` через `app_constants` (мгновенный, без деплоя). Допустимо: юзер и так ждёт 3-5s на AI parse (GPT-4o Vision), +2.5s не заметно при наличии thinking-стикера.

### Always-fallback pattern

Новая public функция `pick_food_log_fallback(ctx)` — wrapper над `_pick_pre_baked(ctx, "food_log_fallback")`. Handler в `except asyncio.TimeoutError` вызывает её sync'но → per-language pre-baked (mig 315: 13 langs × 5 variants). **Карточка НИКОГДА не рендерится без Noms-comment** — ни при timeout, ни при LLM error, ни при parse failure.

### Emoji rollback: tg-emoji → unicode

Noms feedback: «3D-эмодзи в инлайн-размере не читаются». Откат `<tg-emoji>` HTML обёрток. Новый плоский `EMOTION_TO_EMOJI: dict[str, str]`:

```python
EMOTION_TO_EMOJI = {
    "smirk":    "😏",
    "proud":    "🤩",   # было 😤 → 🤩 (positive, not angry)
    "side-eye": "🤨",
    "sage":     "🧘‍♂️",
}
```

Display format: `NOMS {emoji}: "{text}"` (вместо `💬 Noms:`).

### persist_as_menu fix (PR #165)

`_send_and_persist` теперь принимает `persist_as_menu=False` kwarg. Food log endpoint передаёт `False` → карточка НЕ пишет себя в `users.last_bot_message_id` → следующий `delete_and_send_new` её не стирает. Per One-Menu principle: карточка лога еды = content (trophy), не navigation menu.

### My Day insight integration

Sage теперь генерирует ВТОРОЙ тип комментария — `generate_my_day_insight` для stats_main. Архитектура cache-on-write (piggy-backed на food_log path). Полное описание — [[concepts/my-day-llm-insight]].

### Tests

60/60 sage + food_log pass после v3 fixes.

## Fog-prompt regression fix (PR #194, 2026-05-25)

**Bug:** After Stage 7a cutover (PR C), `handle_ai_input` and `_handle_edit_meal_input` silently returned `ResponseEnvelope.empty()` when GPT-4o classified input as `is_food=False`. User saw only the thinking sticker — no error message, no «это не еда» response.

**Root cause:** Both handlers had early-return paths for `is_food=False` that didn't resolve any translation. The `errors.ai_not_food` / `errors.ai_failed` keys existed in DB (JSONB array[3] per lang) but were never reached.

**Fix:** Both handlers now resolve `errors.ai_not_food` (or `errors.ai_failed`) via `resolve_translation_text` — including variant random-pick + `{{icon_brain}}` substitution. Confirmed on live with 2 not-food events for admin account.

## Deferred

- ~~11 lang prompts~~ **Partially closed** (mig 315 — fallback × 13 langs done; system prompt still ru+en only)
- A/B framework + cohort field (38 active users — statistical insignificance)
- ~~Pet stage tone variation~~ **CANCELLED** — tamagotchi_stage убран из prompt (character redesign)
- Closed-loop telemetry `sage_responses_log` (RLHF отдельный PR)
- ~~Custom emoji IDs для side-eye + sage~~ **REPLACED** — rollback to unicode emoji (v3, 2026-05-24)

## Day-context (сквозная память дня) + English-only system prompt (2026-06-01, mig 412, PR #267)

Owner: убрать «клиповое мышление» — Sage должен видеть ВЕСЬ день, не один приём пищи.
Оба инсайта (food-log comment + my-day) теперь получают в user-prompt:
`today_meals_history` (история блюд за сегодня), `wellbeing_today {sleep, stress}`,
running day totals %. Это позволяет увязывать недосып→грелин, повторный кофе→ЦНС,
стресс→кортизол, и связывать новое блюдо с уже съеденным.

- **Источник данных:** `get_day_summary` отдаёт `meals` (time_local/items_summary/
  total_calories) + (mig 412) `wellbeing_today {sleep, stress}` из `daily_metrics` за
  сегодня (user-local date, free-tier). Единый источник для обоих путей.
- **my-day:** `_normalise_day_summary` пробрасывает `today_meals_history`+`wellbeing_today`;
  `_build_my_day_prompt` печатает строками.
- **food-log:** `generate_food_log_comment(ctx, payload, rpc_caller=...)` — при наличии
  `rpc_caller` тянет `get_day_summary` → `_build_day_context_lines`. Прод-вызов
  `render_food_log_confirmation` передаёт `rpc_caller=supabase.rpc` (внутри timeout-bounded
  `sage_task`). Unit-тесты НЕ передают rpc_caller → нет network, блок пустой.
- **Промпт-блоки (English, в коде):** food-log `DAY CONTEXT AWARENESS`; my-day
  `WELLBEING & CHRONOBIOLOGY` (не забегать по времени суток — хронобиология).

### 🏛 Архитектура системного промпта (durable best-practice)

**Системный промпт = ОДИН английский источник в коде** (`_DEFAULT_SYSTEM_PROMPT_EN` /
`_DEFAULT_SYSTEM_PROMPT_MY_DAY_EN`). Язык ответа — **параметр** `Response language:
{users.language_code}` в user-prompt (уже был). Это Big-Tech норма: модели надёжнее
следуют инструкциям на английском, output-язык управляется отдельно.

**Анти-паттерн, который убрали (mig 412):** системный промпт переводили ×13 в
`ui_translations.sage.system_prompt_*`. Это **drift-trap** — `system_prompt_food_log`
жил только в 2/13 langs, остальные 11 молча уходили на код-дефолт (рассинхрон, который
никто не замечал). + каждая правка × 13 + L1-review для текста, который юзер НЕ видит.
mig 412 удалил мёртвые DB-ключи; код читает только константу.

**Правило:** переводить ×13 только то, что видит юзер (output / UI-строки). Системные
промпты / инструкции LLM — английский, в коде, под version control. Hot-edit промпта
через DB — тоже анти-паттерн (prompt-governance хочет git-историю + PR-review).

## Related Concepts

- [[concepts/sassy-sage-dialog-variants]] — JSONB array variant system (pre-baked fallback uses same infrastructure)
- [[concepts/food-log-python-cutover]] — Stage 7a handler architecture where Sage integrates
- [[concepts/safety-guard-ux-pattern]] — §9b effective_goal_type lesson; §3 severity matrix informs safety paths
- [[concepts/python-vs-n8n-template-grammar]] — template resolution for pre-baked phrases
- [[concepts/cron-reminder-suppression-tunables]] — same `app_constants` hot-flip pattern for timeout tuning
- [[concepts/sassy-sage-multilingual-glossary]] — tone reference per language (used for mig 315 fallback localization)
- [[concepts/my-day-llm-insight]] — sibling LLM integration for stats_main (cache-on-write, same safety gates)

## Sources

- [[daily/2026-05-22.md]] — PR #156, mig 312: first OpenAI call in NOMS. Architecture plan v3 (parallel asyncio, 5 safety paths, pre-baked fallback). 26 tests. Cost $0.70/мес. Timeout calibration 1500→2500ms via hot-flip. Canary test с тимлидом.
- [[daily/2026-05-23.md]] — PR #160 (mig 314): Sage v2 — JSON mode, emotion→tg-emoji, macros focus, header prefix swap. PR #161 (mig 315): fallback phrases × 13 langs. Hot DB tuning (temperature 0.9→0.7, max_tokens 80→300). 60 tests.
- [[daily/2026-05-24.md]] — PR #163: Sage v3 — timeout 2.5→5s, always-fallback `pick_food_log_fallback`, emoji rollback tg-emoji→unicode (😏/🤩/🤨/🧘‍♂️). PR #165: `persist_as_menu=False` for food card (One-Menu fix). PR #164: My Day LLM insight integration (cache-on-write sibling).
- [[daily/2026-05-25.md]] — PR #194: fog-prompt regression fix (handle_ai_input + _handle_edit_meal_input silent empty envelope for is_food=False → now resolves errors.ai_not_food/ai_failed with variant pick + icon substitution). PR #193: cmd_stress_high TypeError fix (SimpleNamespace dict-spread → dataclasses.replace).
