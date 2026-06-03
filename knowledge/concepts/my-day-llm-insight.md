---
title: "My Day LLM Insight — cache-on-write архитектура для stats_main"
aliases: [my-day-insight, my-day-llm, sage-my-day, stats-llm-insight, cache-on-write-insight]
tags: [llm, openai, stats, sage, architecture, python, cache]
sources:
  - "daily/2026-05-24.md"
  - "daily/2026-06-01.md"
  - "daily/2026-06-03.md"
created: 2026-05-24
updated: 2026-06-03
---

# My Day LLM Insight — cache-on-write для stats_main

Sassy Sage LLM-комментарий на экране «📊 Мой день» (`stats_main`). В отличие от food-log one-liner'а (fire-and-forget per meal), My Day insight **кешируется в `users`** и обновляется piggy-back на food_log path. View (открытие stats_main) — **0ms LLM** (cache hit → inject, cache miss → static SQL fallback).

## Key Points

- **Cache-on-write:** LLM call происходит **после** каждого food log (`asyncio.create_task(regen_my_day_insight_cache)`), не при открытии «Мой день». Юзер видит готовый insight мгновенно.
- **4 колонки кеша в `users`:** `my_day_insight_text`, `my_day_insight_emotion`, `my_day_insight_at`, `my_day_insight_locale`. **Свежесть (mig 389, 2026-05-30):** тот же локальный календарный день И та же фаза дня (утро<12 / день 12-17 / вечер 17-22 / ночь>22, в tz пользователя), выводится из `my_day_insight_at` — заменил прежний 4h TTL. Плюс locale match (язык мог смениться). Причина смены: insight завязан на время суток, 4h TTL давал контекстно неверную фразу (утренняя к вечеру) ИЛИ ранний откат на static. Теперь фраза пересоздаётся ровно на границе фазы дня.
- **12-enum `day_status`** как tone anchor для LLM: `cold_start | night_overflow | over_target | severe_deficit | under_target_evening | perfect_unicorn | protein_drought | carbs_overload | target_met | target_met_fat_heavy | near_target | in_progress`. (`target_met*` добавлены 2026-06-01.)
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

## `_compute_day_status` — 12-enum tone anchor

Условия — фактические пороги кода `services/sage.py:_compute_day_status` (порядок проверок сверху вниз; первый сработавший выигрывает).

| Status | Условие | Tone |
|---|---|---|
| `cold_start` | 0 meals today | Мотивирующий «начни день» |
| `night_overflow` | kcal% ≥120 + meal_period=late_night | Лёгкая ирония |
| `over_target` | kcal% ≥120 | Reassurance (не shame) |
| `severe_deficit` | kcal% <25 + dinner/late_night | Concern + push |
| `under_target_evening` | kcal% <50 + afternoon_snack/dinner/late_night | Мягкий nudge |
| `perfect_unicorn` | kcal% 95-105 + все макросы 90-110 | Celebration |
| `protein_drought` | protein% <70 + kcal% ≥80 | Macro-specific advice |
| `carbs_overload` | carbs% ≥130 | Macro-specific |
| `target_met` | kcal% 100-119, fat% <130 | Краткий гордый кивок; **приёмов больше не предлагать** |
| `target_met_fat_heavy` | kcal% 100-119 + fat% ≥130 | Назвать жировой перекос нейтрально; **FORBIDDEN** хвалить как «баланс/огонь»; ребаланс на завтра |
| `near_target` | kcal% 90-99 | Поддержка; лёгкий ужин уместен |
| `in_progress` | всё остальное (kcal% <90) | Нейтральный |

Status передаётся в LLM prompt как контекст — LLM НЕ выбирает status, он получает его от Python. **`target_met` / `target_met_fat_heavy` добавлены 2026-06-01** (PR #274/#279) — см. lesson ниже.

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

Хранение: с mig 412 — **только** Python constant `_DEFAULT_SYSTEM_PROMPT_MY_DAY_EN` (per-lang DB `sage.system_prompt_my_day` retired, был drift-trap). Язык ответа = `Response language` строка в user-prompt.

## Lesson 2026-06-01 — два бага «слепоты», оба чинились детерминированно (PR #274/#279/#281)

Owner-тест на 417002669 (день 104% ккал, жир 185%). Два провала подряд — и оба **не** «LLM галлюцинирует», а **противоречивый детерминированный якорь**. Метод диагностики: снять реальный payload с VPS (`journalctl -u noms-webhooks | grep SAGE_MY_DAY_PROMPT`) — он показывает, что именно увидела модель.

1. **«Вперёд к обеду!» при 104% (PR #274).** `_compute_day_status` бакетил 100-119% как `near_target`, чей хинт = «light dinner closer». Модель **исполнила** инструкцию. Фикс: новый `target_met` (100-119), `near_target` сужен до 90-99. Урок: **чини в `_compute_day_status`, не пятым абзацем в промпте** (в промпте уже было ≥4 запрета на «звать есть» — пятый усугубил бы перегруз).

2. **«Баланс огонь!» при жире 185% (PR #279).** `target_met` хвалил добор калорий, игнорируя жировой перекос (Goal-Achieved Blindness). Фикс — той же формы: развилка `target_met` / `target_met_fat_heavy` (fat ≥130). Плюс убраны **две скрытые коллизии**, найденные локальным eval: (а) `GUARDRAIL #3` буквально говорил «suggest BALANCE» → модель брала слово и хвалила; (б) `CHRONOBIOLOGY #2` **безусловно** гнал «point toward the NEAREST upcoming meal» → перебивал запрет при закрытом бюджете. Оба → гейтированы по `kcal% < 100`.

**Anti-pattern (важно):** не менять шейминг на противоположный провал — рестрикцию/медицинский алармизм («прекрати есть», «органы надрываются»). Это бьёт по РПП / anti-restriction safety. Нейтрально назвать факт + максимум один мягкий совет на завтра.

**Verification-паттерн — локальный LLM-eval** (`tools/sage_my_day_fat_heavy_eval.py`): реальные вызовы gpt-4o-mini с точным баг-payload, **прикреплённым к реальному сценарию** (pin `_local_time_context` на 16:08), N прогонов. Тестирует промпт **без деплоя и кэша**. Регекс-скрининг груб (ловит «ребаланс завтра» как «похвалу», стрик-«огонь», прошлые приёмы) — финальный вердикт по чтению текстов. Остаток: gpt-4o-mini ~1/8 роняет мягкое упоминание след. приёма — предел слабой модели, не противоречие промпта.

### Гайка верификации на проде: 4ч/фазовый кэш МАСКИРУЕТ промпт-изменения
**Первый ре-тест после деплоя #274 вернул СТАРУЮ плохую фразу.** Причина — insight кэшируется (`users.my_day_insight_*`, свежесть = тот же календарный день + та же фаза дня). Деплой прошёл, но кэш от 15:35 (старый промпт) был ещё свеж → отдался снова. **Правило: после деплоя любого sage-промпт-изменения кэш надо инвалидировать** (`UPDATE users SET my_day_insight_at = NULL WHERE telegram_id=...`), затем **два** открытия «Мой день» (1-е protмикает фоновый regen новым промптом, 2-е показывает свежую фразу). Иначе тестируешь старьё.

## Meals-history cap → app_constants (PR #281, 2026-06-01)

`_format_meals_history` хардкодил `limit=8` → при 10+ логах **утро выпадало** из payload LLM, ломая правила промпта «повтор кофе / early big breakfast» (дневные ИТОГИ всегда полные — резался только нарратив). Вынесено в **`app_constants.sage_meals_history_limit`** (mig 422, дефолт 20, hot-reload). Прокинут в оба билдера (food_log day-context + my_day). Подтверждено: ключ долетает в `v_user_context.constants` (whitelist'а нет).

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

## Stale-insight-on-delete bug — freshness by TIME not CONTENT (mig 440, 2026-06-03, PR #302)

**Симптом (репро owner'а):** залогировал первый приём → удалил его (кнопка) → открыл «Мой день» → фраза Номса всё ещё описывает удалённую еду, при том что live-цифры показывают 0 ккал. Классическое «число на экране ≠ слова Номса».

**Корень — фундаментальный изъян модели свежести.** `_my_day_cache_fresh` (`menu_v3.py`) считает кэш валидным по трём критериям: текст непустой + локаль совпадает + `my_day_insight_at` в пределах **4 часов**. **Содержимое дня в проверку не входит.** Фраза, сгенерённая 3 минуты назад про приём №1, остаётся «свежей» даже после его удаления → отдаётся как есть. Хуже: на этом открытии regen даже не запускается (кэш ведь «свежий» по времени).

**Почему путь удаления не спасал:**
1. `_handle_delete_meal_now` (`menu_v3.py:926`) чистил кэш **только в in-memory ctx** запроса (`replace(ctx, my_day_insight_at=None)`) — это НЕ персистится в БД. Следующее открытие грузит ctx из `v_user_context` заново = старое значение.
2. Реальная инвалидация полагалась на fire-and-forget `regen_my_day_insight_cache`, который **(а)** гонится со следующим тапом юзера и **(б)** молча `return False` (НЕ пишет кэш) при любом сбое — LLM error / JSON parse / text rejected (`sage.py:403, 323, 334, 352`). При любом из этих исходов БД-строка со старой фразой и свежим timestamp остаётся.

**Fix (Решение A, mig 440, RPC-only — Python не трогали):** инвалидировать кэш **атомарно внутри mutation-RPC** `delete_meal_by_id`:
```sql
WITH deleted AS (DELETE FROM food_logs WHERE meal_id = p_meal_id RETURNING telegram_id)
SELECT count(*)::int, max(telegram_id) INTO v_deleted_count, v_telegram_id FROM deleted;
IF v_telegram_id IS NOT NULL THEN
    UPDATE users SET my_day_insight_at = NULL WHERE telegram_id = v_telegram_id;
END IF;
```
NULL-им только timestamp (freshness-гейт падает на `at IS NULL` → правдивый static fallback + async regen); stale-текст безвреден, перезапишется. `food_logs` = плоская таблица приёмов (нет отдельной `meals`), FK=`telegram_id bigint`, `meal_id` группирует строки; hard delete. `max(telegram_id)` над удалёнными строками = единственный владелец. Verified ROLLBACK-txn: `deleted_count=2`, `at→NULL`.

**Durable lesson (переносимый на любой кэш):**
- **Свежесть по времени ≠ свежесть по содержимому.** Если кэш зависит от мутируемого состояния — TTL не гарант корректности. Любая мутация состояния обязана инвалидировать кэш.
- **In-memory ctx-инвалидация не персистится** — следующий запрос грузит из БД заново.
- **Fire-and-forget regen ненадёжен** как механизм инвалидации: гонка + silent no-op на ошибке.
- **Место инвалидации — сама mutation-RPC (атомарно с изменением)**, не Python-хендлер и не фоновая задача.

**Решение B (бэклог) — content-aware freshness:** штамповать кэш «отпечатком дня» (`meals_count`+`last_meal_at`, или day-version счётчик, инкрементящийся на add/edit/delete). `_my_day_cache_fresh` сверяет сохранённый отпечаток с текущим состоянием дня → mismatch=stale. Закрывает ВСЕ пути мутации (add/edit/delete) единым правилом вместо точечной инвалидации в каждой RPC. A достаточно для репорта; B — «сделать правильно».

## Related Concepts

- [[concepts/sage-food-log-llm-integration]] — food-log one-liner (sibling LLM integration, same safety gates)
- [[concepts/stats-main-headless]] — stats_main screen architecture (where insight renders)
- [[concepts/pre-migration-discovery-recipe]] — gotcha: LLM payload normaliser vs live RPC shape
- [[concepts/headless-template-substitution]] — template_vars injection pattern
- [[concepts/adaptive-modifiers-architecture]] — wellbeing hub widget uses get_day_summary (same RPC)

## Sources

- [[daily/2026-05-24.md]] — PR #164 (mig 319+320): cache-on-write architecture, 10-enum day_status, _normalise_day_summary, 40 tests. PR #166 (mig 322): normaliser P0 fix (nested stats shape). PR #167 (mig 323): prompt guardrails (4 rules). PR #163: emoji rollback + timeout bump 2.5→5s.
- [[daily/2026-05-25.md]] — Mig 349 (PR #197): system_prompt_my_day length reduction 100-250→80-150 chars × 13 langs.
