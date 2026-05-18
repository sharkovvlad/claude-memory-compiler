# Handover — Nutritionist Session Close (2026-05-18)

**Адресат:** следующий nutritionist owner или mig-engineer, продолжающий P0 sprint closure (translations + UX + retrofit для P0.6/P0.4).

**Срочность вхождения:** ≤20 минут. Этот handover + проверить состояние [PR #96](https://github.com/sharkovvlad/noms-bot/pull/96) = всё что нужно.

---

## TL;DR — где мы (2026-05-18 15:30 UTC, FINAL post-mig 260)

**Session deliverables (6 SQL migrations + 1 Python file, +3010 lines, applied на prod):**
- mig 252 — banner injection my_plan (PR #96 merged)
- mig 253+254 — pregnancy/lactation schema + v8 RPC (PR #96 merged)
- **PR #98 OPEN** — содержит mig 256+257+258+259+260+router.py:
  - mig 256 banner extension → personal_metrics + profile_main
  - mig 257 `🌸 Женское здоровье` Progressive Disclosure UI
  - mig 258 maternal translations 13 langs (156 entries)
  - mig 259 onboarding maternal step F/15-50 (3 buttons + recalc)
  - mig 260 Profile picker prefer-not cleanup
  - dispatcher/router.py — 3 maternal statuses в BUTTON_ONLY + ONBOARDING frozensets

**P0 status:**
- ✅ Item #2 Teen <18 — end-to-end **verified live** (owner screenshot 13:30 UTC)
- ✅ Item #1 Pregnancy/lactation — full closeout: schema + calc + UI + onboarding + i18n
- ✅ Item #3 Kcal floor — backend ready; banner текст pending bmi/min_kcal copywriter session
- ⏳ Item #4 EA — deferred P2 ([energy-availability-design-decision.md](../knowledge/concepts/energy-availability-design-decision.md))

**После PR #98 merge auto-deploy** — router.py попадёт на VPS; новые F/15-50 юзеры начнут видеть maternal onboarding step при /start.

## TL;DR — где мы (2026-05-18 14:30 UTC, historical post-PR #98 init)

**С момента первоначального handover'а (13:00) добавлено:**
- ✅ PR #98 open — mig 256+257+258 (banner extension + female health UI + maternal i18n) applied на prod
- ✅ Banner injection теперь на 3 screens: `my_plan` + `personal_metrics` + `profile_main` (закрывает bug owner'а от live-test'а)
- ✅ `🌸 Женское здоровье` Progressive Disclosure UI — F users могут установить is_pregnant/is_lactating через Profile
- ✅ Maternal translations 13 langs applied (156 entries)
- ✅ Pregnancy + gain clinical decision ALLOW confirmed by owner + zapisан в clinical spec §6b
- ⏳ Onboarding maternal step для F/15-50 — agent в фоне работает (mig 259+)

**Live-test verified 2026-05-18 ~13:30 UTC:** owner подтвердил banner работает на «🚀 Мой план» для 786301802 (16yo F maintain) с текстом «Считаю по подростковым формулам». Item #2 P0 officially end-to-end в продакшене.

## TL;DR — где мы (2026-05-18 13:00 UTC, historical)

P0 sprint roadmap'а `calculate_user_targets` **практически закрыт на SQL уровне**:

| P0 item | Status |
|---|---|
| **1. Pregnancy/lactation** | ✅ Schema (mig 253) + RPC v8 (mig 254) applied + integration verified. Переводы + UX — следующие сессии. |
| **2. Защита <18** | ✅ Full end-to-end (mig 234 RPC + mig 240/241/242 переводы + mig 252 banner rendering). **Готово к live-test в боте.** |
| **3. Хард-лимит kcal 1200/1500** | ✅ RPC end-to-end (mig 246 v7 + mig 252 banner rendering); **переводы для bmi/min_kcal banner текстов — TBD** (copywriter сессия, brief готов). |
| **4. EA > 30 ккал/кг LBM** | ⏳ **Deferred to P2** — rationale в [[concepts/energy-availability-design-decision]] (EA-lite даёт false negatives на active F). |

[PR #96](https://github.com/sharkovvlad/noms-bot/pull/96) **open**, 3 миграции, +1173 строк, applied транзакционно на prod 2026-05-18 12:35-13:00 UTC. Owner может merge'нуть в любой момент — git sync с реальностью (миграции уже на проде).

---

## Что НЕ закрыто и блокирует «успешные тесты в боте» 4 пунктов P0

### A. Live-test (зайди в бот сам)

Я не делал — нет test-аккаунта в этой сессии. Кратчайший путь для owner'а:

```sql
-- 1. Сделать любой свой test telegram_id 16-летним временно
UPDATE users 
SET birth_date = (CURRENT_DATE - INTERVAL '16 years')::DATE,
    goal_type = 'lose',
    goal_speed = 'normal'
WHERE telegram_id = <твой test_tid>;
```

Затем в Telegram бот → **🥑 Профиль → Мой план**. Ожидать:
- Banner вверху: `🛡️ Under 18 — set to maintain` (или RU/etc по lang_code юзера) + body
- Goal label: `Maintain` (не `Lose weight`!)
- Целевые калории: уменьшены до maintenance

После проверки revert:
```sql
UPDATE users SET birth_date = <original>, goal_type = <original>, goal_speed = <original> WHERE telegram_id = ...;
```

**Что должен увидеть test для каждой family:**
- `age (teen lose)`: `🛡️ Under 18 — set to maintain` + maintenance kcal
- `age (elderly)`: только нужен 76+ возраст + любая цель → `After 75, formulas less precise` (informational)
- `bmi/min_kcal`: **banner текст ПУСТОЙ** (переводов нет ещё). RPC возвращает enum, banner_block loop их пропускает — в JSON `bmi_warning='extreme_cachexia_recommend_medical'`, но в UI ничего. Это **ожидаемо** до copywriter session.
- `pregnancy`: то же — RPC возвращает `pregnancy_warning`, banner_block пустой до maternal переводов

### B. Translations для bmi/min_kcal (351 entries × 13 langs)

**Brief готов:** [handover/2026-05-18_bmi_min_kcal_copywriter_brief.md](2026-05-18_bmi_min_kcal_copywriter_brief.md)

Содержит:
- Точная схема ключей (`warning.bmi.<enum>.<surface>` + `warning.min_kcal.<enum>.<surface>`)
- EN reference (готовые тексты, базовая отправная точка)
- Severity emoji prefix matrix
- Scientific anchors per enum
- L1/L2 cultural review matrix
- 10-шаговый pipeline per ui-translations-bulk-update-recipe

**Spawn:** general-purpose агента в новой сессии с этим brief'ом + `concepts/sassy-sage-multilingual-glossary.md` + `concepts/ui-translations-bulk-update-recipe.md`.

### C. Translations для maternal (221 entries × 13 langs)

17 ключей перечислены в [[concepts/pregnancy-lactation-clinical-spec]] §5. Pattern идентичен B. Можно объединить с copywriter session B (одна сессия, разные families) или раздельно.

L1+L2 mandatory: severity = hard block + hard regulated → AR/FA/HI/ID особенно (medical authority register, halal nutrition, maternal privacy в религиозных контекстах).

### D. Onboarding UX + Profile toggle для maternal status (Option D)

**Approved:** combo A (onboarding step для F/15-50) + B (retrofit popup) + C (Profile toggle).

**Implementation depends on cutover state:**
- Profile UI сейчас в headless Python (mig 252 я писал именно через RPC). Toggle добавить как новый `ui_screens` row с `business_data_rpc='get_maternal_status'` + form.
- Onboarding шаг в Python `handlers/onboarding_v3.py` уже мигрирован. Добавить FSM шаг после goal selection.
- Retrofit popup — отдельный cron worker.

Перед spawn'ом — проверить **n8n vs Python cutover state** для onboarding (это могло измениться с предыдущей сессии).

### E. Retrofit cron worker

**Schema готов:** `idx_users_maternal_protective` partial index (mig 253) на F/15-50 с unknown status + birth_date NOT NULL.

**Worker (Python APScheduler):**
- Расписание: hourly batch, throttle 500/day
- Logic: SELECT кандидатов через partial index → отправить one-time popup → INSERT в `user_prompt_log` чтобы не спросить дважды
- Pattern: [[concepts/user-data-collection-pattern]] §4 HIGH priority retrofit

### F. Auto-reset cron

Daily cron:
- `WHERE pregnancy_due_date + INTERVAL '30 days' < CURRENT_DATE AND is_pregnant = TRUE` → prompt «всё ещё беременна или родила?»
- `WHERE lactation_started + INTERVAL '24 months' < CURRENT_DATE AND is_lactating = TRUE` → prompt «всё ещё кормишь?»

После confirmed change — UPDATE users (clear flags) + `guard_audit_log INSERT event='auto_resolved'`.

### G. First-trigger modal (touch-point #3 per safety-guard-ux-pattern)

Сейчас закрыт **только passive banner #2** (always shows on my_plan). Для **первого** trigger — full-screen modal с `modal_full` translation key и кнопкой «Понял».

**Implementation:** Python hook в webhook_server.py или handler — проверяет `users.shown_guards` JSONB, если warning enum НЕ там — отправляет `modal_full` text как отдельное сообщение перед основным экраном, потом `UPDATE users SET shown_guards = shown_guards || jsonb_build_object(<enum>, NOW())`.

Pattern: brief в [handover/2026-05-17_age_warnings_python_handler_brief.md](2026-05-17_age_warnings_python_handler_brief.md) §D.

---

## Open clinical question (для nutritionist owner)

**`is_pregnant=TRUE + goal=gain`** — v8 RPC применяет trimester kcal bonus (+340/+452) но **не** force'ит maintain. Spec §2 описывает только `lose` case явно.

**Clinical context:** 12-16 kg gain over pregnancy is normal (IOM 2009 weight gain guidelines for BMI 18.5-25). Поддержание goal=gain клинически валидно. Force-maintain здесь бы означало запретить здоровую прибавку веса — обратный гард.

**Default agent'ом сделан выбор:** keep gain logic intact, just add kcal bonus. Если согласен — close question. Если не согласен — small follow-up mig.

---

## Coordination protocol — что подхватить из predecessor handover'ов

Из [2026-05-17_nutritionist_session_close.md](2026-05-17_nutritionist_session_close.md):

- **5-tier severity vocabulary** — закреплено в [[concepts/agent-collaboration-protocol]] Rule 1
- **L1 + L2 cultural review** — обязательно для hard block / hard regulated banners. Я (этой сессии) не делал L1 review для maternal translations — их ещё нет. Это работа следующей сессии.
- **DEFAULT NULL для safety-critical полей** — Rule 2, соблюдено в mig 253
- **`<trigger>_warning` JSON naming** + `warning.<family>.<severity>.<surface>` translation — соблюдено

---

## Что НЕ трогать (защита от scope creep)

- **mig 235 формулы Schofield/Molnar/Lührmann** — это P1 backlog (silent accuracy, не safety). НЕ начинать пока P0 closure не доделан (translations + UX).
- **`phenotype='athlete'` no-op** — P1 backlog
- **MacroFactor adaptive TDEE** — P3, 6-9 мес horizon
- **Phase 3 adaptive modifiers (сон/стресс/ПМС)** — P2, после Phase 2 quiz expansion

---

## Артефакты сессии

| Файл | Назначение |
|---|---|
| `migrations/252_my_plan_safety_guard_banners.sql` | Banner injection family-agnostic |
| `migrations/253_users_pregnancy_lactation_schema.sql` | Pregnancy schema |
| `migrations/254_calculate_user_targets_v8_maternal.sql` | v8 RPC с maternal guard |
| `concepts/energy-availability-design-decision.md` | EA deferral rationale |
| `handover/2026-05-18_bmi_min_kcal_copywriter_brief.md` | Brief для copywriter session |
| `daily/2026-05-18.md` (новая секция «Mig 252+253+254») | Daily history |

PR: [#96](https://github.com/sharkovvlad/noms-bot/pull/96) — open.

---

## Watchlist

- **MEMORY.md > 20KB** (306 lines / 40KB). Per CLAUDE.md правила нужен `/anthropic-skills:consolidate-memory` run. **Не запускать сам** — это требует human review (риск удалить важное). Флагнуть тимлиду.
- **PR #94 stale `gh pr list` кэш** — он был merged утром 18.05 но `gh pr list` показал OPEN. Кеш обновляется не сразу. Lesson: `git log origin/main` авторитетен.
- **5 prod users delta=0 после v8 apply** — все 8 registered (включая 2 female) не попадают под protective mode. Когда появятся реальные F/15-50 lose users — retrofit cron должен спросить статус.

---

Удачи. Если упрёшься в clinical edge case без roadmap — escalate owner через 🚨 protocol (Rule 6).
