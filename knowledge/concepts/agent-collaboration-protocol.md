---
title: "Agent Collaboration Protocol — Shared rules для всех NOMS-агентов"
aliases: [collaboration-protocol, agent-rules, multi-agent-coord, agent-protocol]
tags: [meta, coordination, multi-agent, governance, kb]
sources:
  - "daily/2026-05-17.md (dialog agent-234 ↔ nutritionist)"
created: 2026-05-17
updated: 2026-05-17
---

# Agent Collaboration Protocol

10 правил для координации между специализированными агентами NOMS (mig-engineer, нутрициолог, копирайтер, native cultural reviewers). Зафиксированы после диалога 2026-05-17 при работе над mig 234 (age guards), когда два агента независимо планировали создать `safety-guard-ux-pattern.md` — типовой кейс конкурирующей работы.

**Применяется ко всем агентам, работающим над NOMS.** Каждый агент при старте сессии **обязан** прочитать этот документ.

## Контекст — почему нужны rules

NOMS используется в формате multi-agent: разные сессии с разными специализациями работают параллельно (mig-engineering, clinical decisions, translation, native cultural review, UX). Без shared vocabulary и ownership:

- Дублируется работа (два агента создают один и тот же KB концепт)
- Documentation contradictions (mig 234 hard-codes одно поведение, doc описывает другое)
- Migration collisions (два агента берут один NNN)
- Tone-deaf переводы (literal translation без cultural awareness)
- Loss-of-context при handoff между сессиями

Зафиксированные правила решают эти problems by design.

---

## Rule 1 — Severity vocabulary (единая для всех KB и migrations)

Используем 5-tier severity matrix без альтернативных синонимов («medium», «warning», «alert» как самостоятельных категорий **запрещены**).

| Severity | Что значит | Override юзерского намерения | Banner | Opt-out |
|---|---|---|---|---|
| **hard block** | Жизнь/здоровье/legal mandatory. Ребёнок не consent'ит (FTC/California). | Да | non-dismissible | Никогда |
| **hard regulated** | Долгосрочный медицинский риск, требует врач'а как gate. | Да | non-dismissible | Только врач + audit log |
| **soft override** | Risk, юзер может не знать, но может осознанно нарушить. | Да | dismissible | Voluntary с confirmation flow |
| **informational** | Точность снижена / контекст полезен, но цель не меняется. | Нет | dismissible | N/A |
| **silent accuracy** | Внутренний switch формулы для точности. Юзер не выбирал, ничего не теряет. | Нет | **НЕТ** | N/A |

Каждый новый guard / change в `calculate_user_targets` обязан указать severity по этой таблице.

Полные UX-последствия каждого tier'а — [[concepts/safety-guard-ux-pattern]] §3.

## Rule 2 — DEFAULT-policy для новых полей `users`

Решение между `DEFAULT NULL` vs `DEFAULT <typed-value>`:

**`DEFAULT NULL` когда:**
- Acute failure mode (silent harm) — `is_pregnant`, `is_lactating`, severe медконтекст
- Невозможность infer safe default из других полей
- Retrofit cron HIGH priority активен (см. Rule 9 на retrofit timing)

**`DEFAULT <typed-value>` когда:**
- Gradual failure mode (visible симптомы юзеру) — `diet_type='omnivore'`, `sleep_quality='unknown'`
- Retrofit cron работает / будет работать (короткий window collection)
- Возможен safe inference (например `cycle_phase` для cycle-aware женщин)

**Migration comment обязан содержать `-- WHY DEFAULT = X`** с обоснованием. Без этого commit blocked at review.

Полный pattern для новых полей с retrofit — [[concepts/user-data-collection-pattern]].

## Rule 3 — Naming conventions (унифицированы)

### JSON telemetry поля в RPC responses

Формат: `<trigger>_warning` (snake_case, без префиксов).

Примеры: `age_warning`, `bmi_warning`, `pregnancy_warning`, `red_s_warning`, `diet_break_warning`, `min_kcal_warning`.

Значение — enum string (например `underage_forced_maintain`, `underweight_lose_regulated`, `bmi_extreme_low_block`). NOT boolean (мы хотим знать what variant of warning, не just yes/no).

### Translation keys

Формат: `warning.<family>.<severity>.<surface>`

Где:
- `<family>` — `age`, `bmi`, `pregnancy`, `red_s`, `diet_break`, `min_kcal`, ...
- `<severity>` — match enum value из JSON warning (`underage_forced_maintain`, `underweight_lose_regulated`, ...)
- `<surface>` ∈ {`banner_title`, `banner_body`, `modal_full`, `opt_out_confirm`, `auto_resolved`}

Пример: `warning.age.underage_forced_maintain.banner_title`

### Storage — unified (НЕ per-field)

- `users.shown_guards JSONB` — log который guard и когда показан per user (one-time modal logic).
- **`user_overrides` table** — одна таблица для всех opt-outs (`telegram_id`, `trigger_name`, `override_value`, `reason_text`, `set_at`, `expires_at`). НЕ создавать per-field таблицы.
- **`guard_audit_log` table** — одна таблица для всех guard event'ов (`triggered`, `shown`, `opt_out`, `auto_resolved`, `tier_changed`). Для FTC/legal traceability.

## Rule 4 — Scope ownership (кто что owns)

| Зона | Owner | Конкретно |
|---|---|---|
| Клиническая формула / макро-наука | **Нутрициолог** | Mifflin/Schofield/Molnar/Lührmann выбор, fat_floor logic, vegan multipliers, EA thresholds, ABW formula, trimester-aware energy needs |
| Migration SQL / sentinels / p95 / git discipline | **Mig-engineer** | psycopg2 apply, SAVEPOINT pattern, snapshot strategy, rebase ПЕРЕД commit, sanity-check diff, PR creation |
| UX-pattern / banner UI / opt-out flow | **Mig-engineer + копирайтер** | `safety-guard-ux-pattern.md`, decision tree, banner specs, headless rendering meta |
| Translation тексты × 13 langs (L1 cultural) | **Нутрициолог + копирайтер** | Нутрициолог marks `cultural-clean` / `cultural-flag-<region>-<topic>`; копирайтер пишет per language family с Sassy Sage tone + Telegram SRE constraints |
| Native cultural review (L2, для flagged) | **Per-region native reviewer** | Только когда L1 flagged. Group reviewers: Romance (ES/PT/IT/FR), Germanic (DE/EN), Slavic (RU/PL/UK), Arabic-Persian (AR/FA), HI, ID. 6 reviewers max. |
| Roadmap KB updates | **Нутрициолог (P0 содержимое) + Mig-engineer (UX-arch блоки + cross-refs)** | Both touch the doc — coord through commit messages |

## Rule 5 — KB ownership per-concept

| KB concept | Primary owner | Кто ещё может редактировать |
|---|---|---|
| `agent-collaboration-protocol` | Mig-engineer | Нутрициолог добавляет clinical-specific extensions |
| `calc-user-targets-roadmap` | Нутрициолог | Mig-engineer — только UX-arch блоки + cross-refs, не клинические задачи |
| `safety-guard-ux-pattern` | Mig-engineer | Нутрициолог добавляет clinical rationale per guard |
| `user-data-collection-pattern` | Нутрициолог | Mig-engineer добавляет storage schema + cron patterns |
| `personalized-macro-split` | Нутрициолог | Mig-engineer пишет version sections post-apply (v6/v7/etc.) |
| `migration-collision-guard` | Mig-engineer | Любой агент с edge case в Edge cases section |
| `sassy-sage-multilingual-glossary` | Копирайтер | Native reviewers добавляют per-language insights |

**Edits в чужом primary концепте** — только с commit message `coord with @<owner>: <what>`. Владелец передаёт в чат другому агенту через message-relay.

## Rule 6 — Conflict escalation

Когда два агента расходятся по design-вопросу:

**Level 1 — Direct dialog:**
Агент A пишет аргументированную позицию в message back (формат: ✅/🟡/🔴 per пункт с rationale). Агент B отвечает в том же формате. Большинство расхождений резолвятся здесь.

**Level 2 — Owner escalation:**
Если оба остаются at impasse → тэг владельца в формате:
```
🚨 conflict @owner: <one-line summary>
Position A (<agent_role>): <1-2 sentences>
Position B (<agent_role>): <1-2 sentences>
Tie-breaker need: <what specifically owner must decide>
```
Владелец принимает решение в 1-3 предложениях.

**Level 3 — KB fixation:**
Решение **фиксируется в KB как edge case** (никаких side-channel договоренностей в daily/ — daily НЕ authoritative для design decisions). Концептуальный owner добавляет note. Любой будущий агент, столкнувшийся с тем же вопросом, увидит решение.

## Rule 7 — Migration timing (защита от NNN collision)

**Pre-apply checklist:**
1. `git fetch origin main` + `ls migrations/ | tail -10` — последние номера на main.
2. `gh pr list --state open --json number,title,headRefName` — параллельные PRs.
3. **Спросить owner'а** о параллельных агентах с unpushed work (locally-in-flight миграции не видны через GH).
4. MEMORY **не trustable** для «следующий свободный NNN» — устаревает за 30 секунд при N+ agents.

**Pre-commit obligation:**
- `git rebase origin/main` **ДО** `git commit` миграции (не после).
- Конфликты разрешать руками, не bypass'ить.

**Pre-push obligation:**
- `git diff origin/main..HEAD --stat` sanity-check **ДО** `git push`.
- Если большое отрицательное число (>500 deletions) в файлах не из scope — **STOP**, не push'ить. Семантический rollback risk.

**Push:**
- Force-push **только** с `--force-with-lease` (защита от race с параллельным агентом на том же branch).

**Origin lesson:** 2026-05-08 catastrophic откат averted; 2026-05-17 mig 234 sanity-check averted 1432 deletions в чужих файлах. Полный protocol — [[concepts/migration-collision-guard]] + [[concepts/release-protocol]].

## Rule 8 — Silent accuracy switches ≠ guards

Когда формула меняется для повышения точности **без** override юзерского намерения — это **НЕ guard**.

Примеры:
- Mifflin → Schofield/Molnar для `<18` (внутренний BMR switch, юзер не выбирал Mifflin)
- Mifflin → Lührmann для `>75`
- target_weight → Adjusted Body Weight для obese
- Mifflin → Katch-McArdle при known LBM

**Что это означает на практике:**
- ✅ JSON telemetry поле обязательно (`bmr_formula='schofield_hw'`, `target_weight_method='abw'`)
- ❌ UI banner НЕТ — это visual noise без user value
- ❌ Translation keys НЕ нужны (нет user-facing text)
- ❌ Modal / shown_guards / user_overrides НЕ нужны
- ✅ `guard_audit_log` запись (для analytics — сколько юзеров на какой формуле)

**Severity tier:** `silent accuracy` (см. Rule 1).

Иначе агенты ошибочно прицепят banner к accuracy fixes → пользователь видит «формула изменилась» вместо «бот стал точнее» → confusion + потеря trust.

## Rule 9 — Cultural review per guard (two-layer model)

Translation 13 langs ≠ cultural appropriateness. Pregnancy framing в исламских странах / РПП-стигма в Индии-Японии / elderly framing в Latin vs Northern Europe — variable per culture.

### Two-layer model

**Layer 1 (L1): Clinical + first-pass cultural — Нутрициолог:**
- Проверяет clinical correctness переводов (например: trimester terminology, fasting context for Ramadan, halal/vegetarian flags)
- First-pass cultural sanity через [[concepts/sassy-sage-multilingual-glossary]] как guide
- Помечает каждый key одним из:
  - `cultural-clean` — safe to deploy
  - `cultural-flag-<region>-<topic>` — escalate to L2

**Layer 2 (L2): Native cultural reviewer per language family — activated only on L1 flag:**
- Romance (ES, PT, IT, FR) — 1 reviewer
- Germanic (DE, EN) — 1 reviewer
- Slavic (RU, PL, UK) — 1 reviewer
- Arabic-Persian (AR, FA) — 1 reviewer
- HI — 1 reviewer
- ID — 1 reviewer
- **6 reviewers max per guard** (не 13 individual translators)

### Tier'инг по severity (когда L1/L2 обязательны)

| Severity | L1 review | L2 review |
|---|---|---|
| hard block | **Mandatory** | Mandatory if L1 flags |
| hard regulated | **Mandatory** | Mandatory if L1 flags |
| soft override | **Mandatory** | Optional (если бюджет позволяет) |
| informational | **NOT required** (glossary self-screen достаточно) | NOT required |
| silent accuracy | **N/A** (нет user-facing) | N/A |

### Anti-pattern: literal translation

❌ Прогон через Google Translate / DeepL без cultural pass.
✅ Adapted message per language with idiom-awareness, gender policy, Telegram SRE constraints, cultural taboos.

Полный glossary с per-language anti-patterns — [[concepts/sassy-sage-multilingual-glossary]].

## Rule 10 — Retrofit cron priority + canary rollout

Для new fields в `users` или новых guards с auto-reset условиями — retrofit cron pattern. Полная спецификация — [[concepts/user-data-collection-pattern]] §4.

### Priority tier (определяется severity guard'а который использует это поле)

| Severity using field | Retrofit priority | Throttling rule |
|---|---|---|
| hard block (e.g. `is_pregnant`) | **HIGH** — first 7 days после регистрации, не общая очередь | По-человечески первый день |
| hard regulated (e.g. BMI extreme) | MEDIUM — first 14 days | 500-1000/day |
| soft override / informational | LOW — общая очередь | <1k base = за день / 1k-10k = 500/day / 10k+ = 1000/day |

### Adaptive throttling

```
IF total_users < 1000:
  throttle = ALL_ELIGIBLE_per_day (one-shot rollout)
ELIF total_users < 10_000:
  throttle = 500_per_day
ELSE:
  throttle = 1000_per_day with priority by severity
```

### Canary 10% rule

Перед массовым retrofit (>1000 users):
1. **10% canary** — random sample of eligible users.
2. **24-48h наблюдение** churn rate vs baseline (отписки / удаление аккаунта / opt-out).
3. **Если churn delta > +5%** — откат, пересмотр messaging с копирайтером, retry.
4. Иначе — full rollout.

### Translation-ready gate

Cron `enabled := TRUE` ставится **только** когда все 13 translation keys для retrofit prompt готовы в `ui_translations`. Если language X missing — fallback на EN = плохой UX для AR/HI/PT юзера. Gate проверяется auto через `SELECT COUNT(*) FROM ui_translations WHERE key LIKE 'retrofit.<field>.%'` = 13 × N keys для активации.

---

## Когда правила меняются

Этот документ — living. Любой агент с предложением revision:

1. Argue в KB edit с commit message `coord with @<owner>: revision Rule N`
2. Если все primary owners (mig-engineer + нутрициолог + копирайтер) ✅ — merge.
3. Если кто-то 🔴 — Level 2 escalation (Rule 6).

Changelog в конце файла (TBD при первой revision).

---

## Связанные концепты

- [[concepts/safety-guard-ux-pattern]] — UX pattern для guards (использует Rule 1 severity, Rule 9 L1/L2)
- [[concepts/calc-user-targets-roadmap]] — roadmap P0-P3 (использует Rule 1 severity per task)
- [[concepts/user-data-collection-pattern]] — retrofit для new fields (использует Rule 2 DEFAULT, Rule 10 priority)
- [[concepts/migration-collision-guard]] — защита от NNN collision (детали Rule 7)
- [[concepts/release-protocol]] — git discipline (детали Rule 7)
- [[concepts/sassy-sage-multilingual-glossary]] — tone + cultural glossary (база для Rule 9 L1)
- [[concepts/python-vs-n8n-template-grammar]] — translation grammar (Python vs n8n renderers)
