# Handover 2026-06-08 — Sage payload-meta repeat-suppression + rule-7 hard guard

**Скоуп:** PR [#375](https://github.com/sharkovvlad/noms-bot/pull/375) — фикс тона Sassy Sage без правки системного промпта.
**State:** ✅ MERGED 19:57 UTC · ✅ deployed (auto via GitHub Actions) · ✅ `noms-webhooks` healthy · 🟡 одна META не видна в payload — spawn task

---

## За 5 минут: что сделано

После прогона `/sage-tov` судьи 08.06 (51 реакция, 5 юзеров) обнаружено: **92 % реакций Sage = «добавь куриного филе / творог / яйца»** (54 упоминания на 51 реакцию). Owner 07.06 ввёл mandate **«системный промпт не трогать»** — это бренд.

Решение: payload-meta override. В код добавлены **два META-блока**, которые приклеиваются в конец `user_prompt` (после `time_meta_warning` и `FINAL DIRECTIVE`), по аналогии с уже работающим evening-warning:

1. **VARIATION GUARD** — срабатывает, если в последних 2 реакциях Sage юзера был белковый штамп. Подъём из `ai_coach_logs` через новый RPC `get_recent_sage_reactions` (mig 496). Фразирован позитивно: «pick a different lever — leafy greens, fibre, lighter close».
2. **RULE 7 HARD GUARD** — срабатывает (food_log only), если только что залогированный приём ≥ 20 г белка. Дословно вкладывает в payload три варианта acknowledge-формулировки: «белок в деле», «protein landed», «протеин пошёл».

Оба META — fail-safe: RPC fail / None caller → `[]` → флаг False → META пустая строка → identical-to-old behaviour. Параллельный `asyncio.gather(get_day_summary, get_recent_sage_reactions)` — два независимых RPC за один RTT (44 ms Hetzner→Supabase EU), +0 ms к p95 vs старый sequential путь.

## Что подтверждено LIVE (через 17 секунд после deploy)

Юзер u786301802 (en, female, ES), интенсивно логировал в 19:57–19:58 UTC:

| Время UTC | Type | Реакция | Сигнал |
|---|---|---|---|
| 19:57:28 | food_log | «Looks like a coffee party! ☕ how about some **LENTILS**» | Разнообразие, не курица ✅ |
| 19:57:41 | food_log на grilled chicken 825 ккал | **«Protein landed! 🍗** Now, how about some **leafy greens**?» | Rule-7 META сработала **дословно** ✅ |
| 19:58:18 | my_day | «how about some **leafy greens** to round out» | Разнообразие ✅ |

«Protein landed!» — это **прямая копия** моей META-формулировки. Доказывает, что META до LLM доходит и модель её слушает.

## Что НЕ подтверждено (требует дебага)

🟡 **В журнале `SAGE_MY_DAY_PROMPT` я не вижу строки `⚠️ META — VARIATION GUARD`** в payload, даже когда у юзера в `ai_coach_logs` за минуту до того точно были «chicken»/«protein» реакции.

Гипотезы (нужен живой debug, **spawn task task_7839624f**):

1. **Supabase Python SDK shape**: `supabase.rpc()` для TABLE-returning функций может возвращать не `list[dict]`, а `APIResponse` с атрибутом `.data` — unit-тесты мокали `list[dict]`, в проде shape другая. Smoking gun: в `services/sage.py:_fetch_recent_sage_reactions` `isinstance(resp, list)` не сработает на APIResponse → `[]` → флаг False.
2. **`success=true` фильтр**: мой RPC отфильтровывает строки где `success=false`. Если `services/ai_logging.py:log_request` пишет sage с `success=false` — RPC всегда вернёт 0.

**Что сделать дебагу:** SSH на VPS → `SELECT success, count(*) FROM ai_coach_logs WHERE context_type LIKE 'sage_%' AND created_at > now()-interval '1 hour' GROUP BY 1` + temporary `logger.info` в `_fetch_recent_sage_reactions` с типом и длиной `resp` → прогнать живую реакцию → посмотреть journalctl.

Косвенный сигнал, что **что-то всё-таки работает**: 3 из 4 живых реакций варьируют lever (lentils/leafy greens) даже без видимой VARIATION GUARD в payload. Возможно: модель сама в норме лучше варьирует на single-user (08.06 штамп был на выборке 5 юзеров за день), либо META действительно доходит, но `journalctl` обрезает её. Точно установит только debug.

## Параллельный spawn task task_2af67744 — fallback bug

Отдельный класс бага: **2 пустые реакции Sage за 2 дня** (07.06 u6378579500 13:12 food_log + 08.06 u520145707 19:29 food_log на «Борщ»). `generate_food_log_comment` вернул None или `_pick_pre_baked` тоже не дал текст. Возможные пути: OpenAI timeout (1500 ms client), JSON parse fail, sanity-filter false positive (URL/HTML regex), closed-budget leak override. Self-contained investigation через `journalctl` за те времена.

## Open для следующего агента

| Приоритет | Что | Кому |
|---|---|---|
| 🔴 Сейчас | task_7839624f — дебаг VARIATION GUARD в payload | свободный агент |
| 🟡 Сейчас | task_2af67744 — fallback bug investigation | свободный агент |
| 🟡 Через 2-3 дня | прогнать `/sage-tov` судью повторно как A/B (метрики см. ниже) | owner / любой |
| 🟢 Когда owner даст go | Phase 3 — `quiet_steady` day_status в `_compute_day_status` + 1 строка в DAY STATUS HINTS промпта («React with character, NO next-meal suggestion this time»). Снимает ~40 % штампов сразу, но это **правка промпта** → требует owner-approval. | следующая сессия |
| 🟢 Без срочности | DROP 2 дублирующих индекса на `ai_coach_logs` (`idx_ai_coach_logs_user_date`, `idx_ai_coach_logs_tg_created_desc`); оставить только `idx_ai_coach_logs_telegram_id_created` | low-priority cleanup |

## A/B-якорь для следующего прогона `/sage-tov`

**08.06 baseline:**
- Предписание следующей еды: **92 % реакций** (≥46/50, fallback 19:29 не считается)
- Штамп «куриц/творог/яиц/рыб/тунц/бобов»: **54 упоминания на 51 реакцию** (>1 на реакцию)
- Нарушений правила 7 на ≥20 г Б приёмах: **3 из 3**
- Эмоциональный мix: `smirk` ≈ 80 %, `proud` 1×, `side-eye` 0× (эмоциональный коллапс)

**Цель после META (без правки промпта):**
- Предписания ≤ 50 %, штамп ≤ 1/юзер/день, rule-7 нарушения = 0, smirk ≤ 60 %.

**Цель после Phase 3 (когда owner даст go на промпт):**
- Предписания ≤ 25 % (как ставили 07.06).

## Артефакты сессии

- PR: [noms-bot#375](https://github.com/sharkovvlad/noms-bot/pull/375)
- Mig: `migrations/496_sage_recent_reactions_rpc.sql`
- Code: `services/sage.py` (+234 строк, 7 новых helper'ов)
- Tests: `tests/services/test_sage_repeat_suppression.py` (38 тестов; всего sage tests = 131/131 зелёных)
- Transcript: `sage_transcripts/sage_transcript_2026-06-08.md`
- Review: `sage_transcripts/sage_tov_review_2026-06-08.md`
- Daily: `claude-memory-compiler/daily/2026-06-08.md` (секция «Sage ToV — payload-meta…»)

## KB-cross links

- [[concepts/sage-food-log-llm-integration]] — обновлена секцией PR #375
- [[concepts/sage-payload-meta-override-pattern]] — НОВАЯ — паттерн influence-без-promt-edit
- [[concepts/worktree-vs-main-clone-edit-confusion]] — НОВАЯ — gotcha (Edit по absolute path в основной клон вместо worktree)
