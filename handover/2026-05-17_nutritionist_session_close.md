# Handover — Clinical/Nutritionist Session Close (2026-05-17)

**Адресат:** следующий агент в роли clinical/nutritionist owner для `calculate_user_targets` roadmap. Тимлид-уровень координации между mig-engineer'ами, копирайтером, владельцем продукта.

**Срочность вхождения:** ≤30 минут чтения. Не нужно читать KB целиком — этот handover даёт всё критичное + указывает что читать дальше по необходимости.

---

## TL;DR — где мы сейчас (2026-05-17, вечер)

- **Prod:** mig 234 (v6) merged 2026-05-17, PR #86. Age guards baseline работает (`<18+lose` → forced maintain, `>75` → informational).
- **In-flight artifacts mig 234** (closing):
  - **Копирайтер запущен** owner'ом — пишет 156 entries (3 warnings × 4 surfaces × 13 langs) по brief'у в `handover/2026-05-17_mig234_copywriter_brief.md`
  - Storage migration N+1 — **подготовка на spawn** (см. ниже)
  - Python handler updates (Profile banner) — на mig-engineer'е после storage merged
- **Coordination protocol established 2026-05-17:**
  - [[concepts/agent-collaboration-protocol]] — 10 правил включая 5-tier severity + L1/L2 cultural review
  - [[concepts/safety-guard-ux-pattern]] v2 (mig-engineer primary)
  - [[concepts/calc-user-targets-roadmap]] **(твой primary)** — P0 narrowed до 4 задач
- **Готовые spawn-задачи** (chip'ы у owner'а):
  - Mono-mig P0.3+P0.4 «Safety baseline guards» (SQL пишется в worktree)
  - Storage migration N+1 (`shown_guards`/`user_overrides`/`guard_audit_log`)

---

## P0 sprint focus (твой scope)

| # | Задача | Severity | Status | Что нужно от тебя |
|---|---|---|---|---|
| **P0.1** ✅ | Age guards (mig 234) | hard block + informational | **DONE** | Ничего |
| **P0.3+P0.4** 🟡 | Mono-mig safety baseline guards | hard regulated + tiered | **spawn ready** | КТ-1 review SQL когда mig-engineer покажет |
| **P0.6** 🔴 | Pregnancy/lactation | hard block | **clinical spec готов** в [[concepts/pregnancy-lactation-clinical-spec]], UX = Option D approved | Spawn'ить mig-engineer'а с этим spec + retrofit cron coord |
| **P0.8** ✅ | UI surfaces + opt-out matrix | meta | частично закрыто `safety-guard-ux-pattern.md` v2 | Ничего (in-flight via mig 234 closing) |

P1+ задачи — backlog в roadmap, не трогать пока P0 не закрыт.

---

## Кто что owns (Rule 4 / Rule 5)

- **Ты (clinical/nutritionist):** clinical decisions (формулы, макро-наука), `calc-user-targets-roadmap` primary, `pregnancy-lactation-clinical-spec` primary, `user-data-collection-pattern` primary, `l1-cultural-sanity-brief` (твоя операционка для L1 review)
- **mig-engineer (agent 234 closed его branch, новый при spawn):** SQL migrations + sentinels + p95 + git discipline, `safety-guard-ux-pattern` primary, `agent-collaboration-protocol` primary
- **Копирайтер:** translations × 13 langs, Sassy Sage tone, `sassy-sage-multilingual-glossary` primary
- **L2 cultural reviewers (6 group reviewers):** flagged keys only, активируются тобой когда L1 flag

---

## In-flight спавненные task'и (chip'ы)

Когда они start'ятся — выполняй КТ-1/КТ-2 review (как в mig 234 cycle):

### Task 1: Storage migration N+1
- **Scope:** CREATE TABLE `user_overrides`, `guard_audit_log` + ALTER `users ADD shown_guards JSONB`
- **Apply:** ПЕРВОЙ (P0.3+P0.4 mono-mig от неё зависит — пишет в `guard_audit_log`)
- **Твоя роль:** statics review (чек таблицы соответствуют [[concepts/safety-guard-ux-pattern]] §6 schema)
- **Mig-engineer responsibilities:** sentinels, p95, PR

### Task 2: Mono-mig P0.3+P0.4 «Safety baseline guards»
- **Scope:** min kcal floor `GREATEST(target, 1200/1500, BMR)` + BMI tiered guards (14/18.5/60)
- **Apply:** ВТОРОЙ после storage merge (Stale-base rule защитит если порядок нарушится)
- **Твоя роль:** clinical review (cutoffs правильные? формулы соответствуют roadmap?), sentinel scope review (8 кейсов покрывают все 3 BMI tier'а + min kcal trigger?)
- **Open question для тебя:** mig-engineer может предложить feature flags (`safety_guard_bmi_14_enabled`, etc) для granular rollback — accept или объединить под один флаг?

### Future Task 3 (после P0.3+P0.4 merged): P0.6 Pregnancy spawn
- **Clinical spec:** [[concepts/pregnancy-lactation-clinical-spec]] (готов)
- **UX:** Option D approved (onboarding + retrofit popup + Profile toggle)
- **Заблокирована** до closing P0.3+P0.4 (sequential apply, race condition risk)

---

## Что от тебя ожидается как clinical owner

1. **КТ-1 review** SQL миграций от mig-engineer'а перед apply. Особенно clinical cutoffs.
2. **L1 cultural review** translation output от копирайтера mig 234 (используя [[concepts/l1-cultural-sanity-brief]] как операционный checklist). Flag → escalation L2.
3. **Spawn P0.6** mig-engineer'а когда P0.3+P0.4 merged.
4. **Coordinate** с owner если возникают clinical edge cases (например high-risk pregnancy detection requires medical specialist intervention).
5. **Update [[concepts/calc-user-targets-roadmap]]** когда каждая P0 задача закрывается (mark ✅ + переносить в done section).

---

## Что НЕ трогать (защита от scope creep)

- **mig 235 formulas (Schofield/Molnar/Lührmann)** — в P1 backlog, не P0. Spawn только после P0 закрыт.
- **Phase 3 Adaptive Modifiers** — P2, после Phase 2 quiz расширения.
- **Pregnancy edge cases** (multiples, high-risk, bariatric) — banner mention достаточно, не пытаться clinical handling.
- **Translations в `proud-tickling-willow.md` pipeline** — это **другая команда** (UX terminology, не safety messaging). Не координировать с ними по нашим guards.

---

## Decisions reference (что уже зафиксировано — не пересматривать)

| Decision | Source |
|---|---|
| 5-tier severity (hard block / hard regulated / soft override / informational / silent accuracy) | agent-collaboration-protocol Rule 1 |
| `DEFAULT NULL` для safety-critical полей (acute failure) | Rule 2 |
| Naming: `<trigger>_warning` JSON + `warning.<family>.<severity>.<surface>` translation | Rule 3 |
| Unified storage tables (не per-field) | Rule 3 |
| L1+L2 cultural review (L1 mandatory hard/soft, optional informational, N/A silent) | Rule 9 |
| Retrofit HIGH priority (first 7 days) для hard block fields | Rule 10 |
| Canary 10% rollout с 24-48h наблюдением | Rule 10 |
| Translation-ready gate перед cron.enabled | Rule 10 |
| Min kcal floor compromise: `GREATEST(target, 1200/1500, BMR)` | roadmap P0.3 |
| BMI tiered policy (не RETURN ERROR) | roadmap P0.4 |
| P0.2 formulas → P1 (silent accuracy, не safety) | roadmap reclassification 2026-05-17 |
| Pregnancy UX = Option D (combination A+B+C) | owner decision 2026-05-17 |
| Mono-mig P0.3+P0.4 (объединены, не разделены) | agent 234 proposal accepted |
| Apply order: storage migration ПЕРВОЙ, mono-mig ВТОРОЙ | dependency analysis |

Эти решения **закрыты**. Не открывай дискуссию если нет нового evidence.

---

## Что читать в первую очередь

**Critical (≤30 минут):**
1. **Этот handover** (читаешь сейчас)
2. **[[concepts/calc-user-targets-roadmap]]** §P0 ACTIVE SPRINT — твой план

**By need (когда задача всплывает):**
3. [[concepts/agent-collaboration-protocol]] — Rules 1, 4, 5 особенно
4. [[concepts/pregnancy-lactation-clinical-spec]] — когда P0.6 spawn
5. [[concepts/l1-cultural-sanity-brief]] — когда копирайтер вернёт output для review

**Reference только (не читать целиком):**
6. [[concepts/safety-guard-ux-pattern]] — для понимания UX framework, но primary не твой
7. [[concepts/user-data-collection-pattern]] — для P0.6 retrofit pattern
8. [[concepts/sassy-sage-multilingual-glossary]] — ОЧЕНЬ большой (~3500 строк), читай только секции конкретного языка когда L2 escalation

---

## История последних 3 дней (для контекста)

- **2026-05-15:** mig 227 (v4) apply — PAL fusion + 'none' coefs + conditional clamp. Digital twin verified.
- **2026-05-16:** mig 230 (v5) apply — gender carbs floor (women=100, men=50). Deep research handoff составлен. NotebookLM digital twin v6.3 verified against 2 live users in Telegram bot UI.
- **2026-05-17 утром:** Agent 234 написал mig 234 (age guards). Dialog mig-engineer ↔ nutritionist:
  - Round 1: 12/13 правок принято
  - Round 2: 14/15 (+severity reclassification, mono-mig consolidation)
  - Round 3: 4/4 (5-tier severity finalized, L1+L2 model finalized)
- **2026-05-17 вечером:** mig 234 merged. Coordination protocol зафиксирован в KB. Pregnancy clinical spec написан. L1 cultural brief составлен. Two task'а spawned (storage + mono-mig).

---

## Связанные artifacts

- **PR #86** (mig 234) — merged
- **Brief копирайтера:** `handover/2026-05-17_mig234_copywriter_brief.md` (agent 234 primary, я referenced)
- **Deep research:** `handover/2026-05-16_deep_research_handoff.md` (60 KB, owner может перенести в new clinical research session если нужно)
- **Migrations 227, 230, 234** в `migrations/` — read только если нужно понять текущее состояние формулы

---

Удачи, преемник. Если попадёшь в edge case которого нет в roadmap — escalate owner через 🚨 protocol (Rule 6). Не пытайся резолвить clinical decisions в одиночку — координация дороже скорости.
