# Successor Briefing — для следующего агента (после 30.05)

**От:** Nutritionist Agent 10 + Sonnet session (28-30.05) — объединённый брифинг
**Кому:** агент-преемник (любой role — nutritionist 11 / generalist / payment / etc.)
**Status:** Production stable. 10+ PR merged за неделю. 5 UAT findings ждут разбора.

---

## 🎯 TL;DR (60 секунд чтения)

- **Production stable.** Все мои PR merged (#229/#230/#231/#232 + Sonnet 10 PRs). Migration HEAD = **379**. БД и код синхронизированы.
- **Stage 7 (Python AI Engine) — GLOBAL с 29.05.** Все юзеры на Python recognition. n8n `03_AI_Engine` idle. Stage 7c cleanup доступен после **~05.06** (7д stable window).
- **Track C нутрициологических долгов — закрыт** (4 из 5; Phase-aware Sage остался как safety-blocked).
- **5 UAT findings от Sonnet session** ждут следующего агента (детально ниже + в [2026-05-30_uat_followups_issue2_plus_4_prod_bugs.md](2026-05-30_uat_followups_issue2_plus_4_prod_bugs.md)).
- **2 мои PR ждут owner UAT** (#231 cycle + #232 xp_correction toast) — если найдёт баги, см. test plan в их PR bodies.
- ⚠️ **MEMORY раздулась** до 24 KB / 162 строк — флаг для `/anthropic-skills:consolidate-memory` когда удобно.

---

## 📊 Live state snapshot (verified через psycopg2 30.05 13:30 МСК)

```
Migration HEAD on origin/main: 379
Real users (is_bot=false):     13 total
  - registered:                10
  - new:                       2
  - registration_step_3:       1
Active real users last 7d:     6
NPC bots (is_bot=true):        119 (см. [[concepts/npc-bots-users-table]])

App constants verified:
  xp_correction_daily_cap = 3        ← mig 378 applied
  xp_correction_bonus_amount = 5     ← mig 378 applied
  handler_ai_engine_use_python = (deleted, Stage 7 global)
  ai_engine_beta_testers = (deleted, Stage 7 global)

Cycle tracking (mig 375):
  cycle_tracking_setup buttons:     7 ✓
  date placeholders interpolation:  works (verified DD.MM rendering)
  menopause guard:                  active (birth_date >= 55 → NULL)

RLHF audit table (mig 378):
  ai_correction_events rows:        0 (no edits with new patch yet)
  
Latest session daily entries:      daily/2026-05-29.md, daily/2026-05-30.md
```

---

## 🔴 Active priorities (что делать СЕЙЧАС)

### Priority 1 — Sonnet session UAT findings (5 items)

**Полное описание в [handover/2026-05-30_uat_followups_issue2_plus_4_prod_bugs.md](2026-05-30_uat_followups_issue2_plus_4_prod_bugs.md).** Краткое резюме:

| # | Issue | Scope | Difficulty |
|---|---|---|---|
| 1 | **Issue 2 follow-up** — «Авилес» (small Spanish city) AI confidence < 0.7 → bot выдал error 3 раза. Решение: A) lower threshold / B) better prompt / C) Geoapify forward fallback / D) combo | services/city_resolver.py | medium |
| 2 | **Delete account screen** — speaker bubble «Noms: «»» empty (translation missing) | i18n key audit + 1 mig | small |
| 3 | **Reply-kb persists** после удаления аккаунта — нужен `ReplyKeyboardRemove` в delete handler | handlers/onboarding_v3.py | small |
| 4 | **Welcome screen** — стикер ПОСЛЕ text+buttons (must be FIRST для proper UX flow) | ui_screens.meta или Python render order | small |
| 5 | **Welcome text rewrite** в Sage tone × 13 langs (first impression critical) | copywriter subagent + 1 mig | medium |

**Рекомендую начинать с 2-3-4** (small, visible, ловят первые жалобы новых юзеров). Issue 1 (city resolver) и 5 (welcome rewrite) требуют design discussion с owner.

### Priority 2 — Owner UAT моих 4 mig (если ещё не сделал)

Все PR merged + applied LIVE. Owner может протестить и report баги.

**PR #231 (cycle, mig 375)** — на тест-юзере 786301802 (Vlad, es, female):
- Profile → Salud femenina → Ciclo
- ✓ Dynamic dates («📅 Hoy (DD.MM)»)
- ✓ Новая «❓ No recuerdo bien» → silent skip toast
- ✓ Inline «⚙️ Duración: 28 días»
- ✓ НЕТ ✅ pre-selected на «Hace 7 días»

**PR #232 (xp_correction toast, mig 376)** — edit meal flow:
- Залогать еду через AI → edit → toast «🎁 +5 XP»
- 4-я correction за день → silent (cap)

**PR #230 (DIAAS UX, mig 377)** — vegan/vegetarian юзер:
- diet_type='vegan' → /myplan показывает «🌿 Растительный белок усваивается на ~80%...»
- omnivore → этой строки НЕТ (conditional)

**PR #229 (RLHF audit, mig 378)** — backend smoke:
```python
import os, psycopg2; from dotenv import load_dotenv; load_dotenv()
conn = psycopg2.connect(os.environ['DATABASE_URL'])
with conn.cursor() as cur:
    cur.execute("SELECT * FROM ai_correction_events ORDER BY corrected_at DESC LIMIT 5;")
    for r in cur.fetchall(): print(r)
```
После edit meal — должна появиться строка с pre/post snapshots. Если 0 строк после edit — `replace_meal_transaction` patch не сработал.

---

## ⛔ Что НЕ делать без owner approval

| Действие | Почему |
|---|---|
| **Stage 7c deactivate n8n workflows** | Wait until ~2026-06-05 (7 дней stable global). Verification через `docker cp noms-n8n:database.sqlite + sqlite3` recipe в [[concepts/stage7-global-cutover]] §Stage 7c |
| **Phase-aware Sage commentary** | BLOCKED by safety review в `services/sage.py:685`. Нужен явный owner override после понимания РПП-trade-off |
| **Adaptive TDEE / Dynamic Katch clinical %fat** | Большие фичи, нужен design doc отдельной сессией с обсуждением окна усреднения / smoothing / safety floor |
| **Reset MEMORY / consolidate сам** | `/anthropic-skills:consolidate-memory` требует human review per CLAUDE.md rule |
| **Apply mig LIVE через psycopg2 ДО открытия PR** | Только если миграция идемпотентная И scope маленький. Иначе — open PR → owner merge → apply LIVE в той же сессии |

---

## 🟡 Backlog (когда-нибудь)

- **Menu latency optimization** — double `GET v_user_context` × 2 на callback. p95 330ms → можно 150ms. См. `project_menu_latency_watch.md`
- **`cmd_show_meals` «не с 1го раза» investigation** — нужен fresh repro от юзера
- **Drift protection для cycle tracking** — 60-day soft alert если cycle_start_date stale (deferred per owner — over-engineering для current scale)
- **L2 cultural review maternal** (Fiverr AR/FA/HI/ID ~$200) — optional, на усмотрение owner
- **Allergen tracking** — owner decision 29.05: defer, NOMS не делает meal planning, риск low

---

## 📚 Что прочитать первым (start here для нового агента)

### Если ты только зашёл в проект (cold start):
1. `/Users/vladislav/Documents/NOMS/CLAUDE.md` — operational guide (особенно §СТОП-ПРАВИЛО NLM-first, §Закрытие сессии, §Миграции БД)
2. `~/.claude/projects/-Users-vladislav-Documents-NOMS/memory/MEMORY.md` — current state (это **point-in-time**, всегда verify через live SQL)
3. `claude-memory-compiler/knowledge/index.md` — KB index, особенно «Start here for common tasks» секция + ⛔ EOS banner

### Если работаешь над cycle / женское здоровье:
- 🔥 [[concepts/cycle-tracking-ux-and-accuracy]] — full UX matrix + 4 decisions implemented mig 375
- 🔥 [[concepts/adaptive-modifiers-architecture]] — luteal / sleep / stress patterns
- [[concepts/safety-guard-ux-pattern]] — argued override для clinical recommendations
- [[concepts/pregnancy-lactation-clinical-spec]] — clinical safety gates

### Если работаешь над xp / gamification:
- [[concepts/xp-model]] — three-tier economy
- mig 378 (`ai_correction_events`), mig 376 (toast translations), CLAUDE.md §Closed-Loop Learning

### Если работаешь над n8n / cutover:
- 🔥 [[concepts/stage7-global-cutover]] — Stage 7 history + Stage 7c recipe
- 🔥 [[concepts/n8n-data-flow-patterns]] — Safe PUT
- [[concepts/architecture-registry]] — какие targets где

### Если делаешь big new feature (design doc):
- [[concepts/release-protocol]] §rebase-перед-commit
- 🔥 [[concepts/migration-collision-guard]] (§parallel subagents для multi-thread sessions)
- 🔥 [[concepts/subagent-live-apply-review-rule]] — orchestrator review pattern

### Перед EOS обязательно:
- 🔥 [[concepts/session-close-discipline]] — 5-step checklist. Без него следующий агент потеряет 20-40 мин на разбор завалов

---

## 🧠 Open questions для owner (нужны его решения)

1. **Stage 7c timing** — owner хочет deactivate n8n строго через 7д stable (~05.06), или раньше если zero traffic? Smoke test recipe ready.
2. **Phase-aware Sage** — override safety policy или formally close-by-design? Если override — нужно phased plan (text-only first, no LLM dynamic phase commentary до confidence build).
3. **Adaptive TDEE design** — окно усреднения (14/21/30 дней)? smoothing factor (EWMA / linear)? safety floor (BMR × 1.0 / 1.1)?
4. **Clinical %жира UI** — нужно ли? кто реально вводит данные DEXA/BodPod? возможно low-priority учитывая small premium %.
5. **Allergen tracking** — owner на 29.05 сказал defer, но если хочется добавить безопасности — нужен design (5-10 most common allergens или free-text?).

---

## ⚠️ Gotchas которые могут сжечь время (если не знаешь)

| Gotcha | Cost если не знаешь | Где задокументировано |
|---|---|---|
| **NPC bots в users** (119 строк с `is_bot=true`) → любой aggregate **обязан** `WHERE is_bot=false` | counts искажены на ≈30% | 🔥 [[concepts/npc-bots-users-table]] |
| **MEMORY claims могут быть stale** (Stage 7 пример: 4 дня неверных GLOBAL claim) | принимаешь решения на ложном baseline | 🔥 [[concepts/memory-claim-vs-live-verification]] |
| **Reset через psycopg2 НЕ убирает Telegram reply-kb** (требует ghost_remove API call) | UAT broken, юзер видит висящую старую kb | [[concepts/test-user-reset-recipe]] §reply-kb gotcha |
| **Migration collision при parallel subagents** в shared worktree | force-with-lease rename + amend | [[concepts/migration-collision-guard]] §parallel subagents |
| **n8n API `/executions?workflowId=X` возвращает пусто** даже когда executions есть | wrong conclusions из API проверки | [[concepts/stage7-global-cutover]] §n8n SQLite quirk |
| **JSONB shallow merge `content \|\| payload`** wipes nested namespaces | P0 incident (mig 359 wiped 300+ keys × 13 langs) | 🔥 [[concepts/jsonb-shallow-merge-antipattern]] |
| **Subagent claims могут быть неверными** (3 случая за сессию 29.05) | действуешь на основе hallucinated claim | [[concepts/memory-claim-vs-live-verification]] §subagent risks |

---

## 🏁 Перед твоим EOS — обязательно

Прежде чем напишешь «готово» в финале сессии, сделай **self-check** через 🔥 [[concepts/session-close-discipline]]:

1. ☐ Daily-журнал `daily/YYYY-MM-DD.md` обновлён?
2. ☐ Handover нужен (cutover / большой рефакторинг / 3+ PR)? Если да — написан?
3. ☐ KB lesson (gotcha / новый pattern)? Добавлен в `concepts/` + index.md?
4. ☐ MEMORY.md state обновлён (mig HEAD / закрытые задачи / новые flags)?
5. ☐ MEMORY size OK? Если > 20KB / 150 строк → flag owner-у.

Без этих 5 пунктов **не закрывай сессию.**

Это правило **owner explicit flagged 29.05** как боль — «каждая новая сессия 20-40 мин на разбор завалов». Не повтори.

---

## 📜 Источники / связанные handover'ы

| Файл | Что покрывает |
|---|---|
| `2026-05-29_nutritionist10_session_close.md` | мой session close — 4 PR / Track C / cycle UX / xp_correction / DIAAS / RLHF |
| `2026-05-29_stage7_status_reality_check.md` | reality check Stage 7 (canary vs global confusion) |
| `2026-05-30_uat_followups_issue2_plus_4_prod_bugs.md` | Sonnet session UAT findings (5 items) — **start here для immediate work** |
| `2026-05-28_nutritionist_9_handover.md` | предшественник (handover Track C / nutritional debts) |
| `2026-05-26_p0_recovery_and_phase3d_close.md` | P0 recovery context (mig 359 → 360) |

---

**EOS этого handover:** 2026-05-30 ~13:35 МСК
**Автор:** Nutritionist Agent 10 (orchestrator) — Sonnet session author параллельно
**Контактная точка для preемника:** прочитать этот handover + Sonnet handover + index.md ⛔ banner = 5 минут до productive work

Удачи! 🌸
