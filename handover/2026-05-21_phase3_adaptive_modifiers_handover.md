# Handover — Phase 3 Adaptive Modifiers (mig 296+)

> Для агента-преемника. Подготовил **2026-05-20** после закрытия P1 Accuracy sprint trilogy (mig 291/292/295). Контекст с полей — критически важно прочитать **прежде чем** писать SQL.

## TL;DR

**Что ты делаешь:** Phase 3 из [[calc-user-targets-roadmap]] §P2.4 — adaptive macro modifiers (сон/стресс/лютеин). Бот учитывает физиологическое состояние пользователя и временно корректирует дневные таргеты.

**Это НЕ одна миграция.** Это **4 sub-phases**, каждая = отдельный mig + отдельный PR. Не пытайся склеить — sprint займёт 4-6 сессий, не одну.

**Очерёдность критически важна:** 3a (schema+engine) → 3b (sleep) → 3c (stress) → 3d (luteal). Без 3a остальные не работают.

**Severity ВСЕХ modifiers:** `informational` (banner show user) + `silent_accuracy` (для математики). Cм. [[safety-guard-ux-pattern]] §3 5-tier matrix.

**P1 sprint baseline:** все 3 PR смержены, mig HEAD = **295**.

---

## Состояние на старт сессии

### Закрыто (то, на чём ты строишься)

- **mig 291** (P1.2) — `users.diet_type` enum + `calculate_user_targets v9` DIAAS multiplier. PR #135 merged.
- **mig 292** (P1.5) — Schofield-HW / Molnar / Lührmann BMR formula switch (v10). PR #137 merged.
- **mig 295** (P2.1+P2.2+P2.3) — RFM + Katch-McArdle + waist + retrofit cron (v11). PR #140 merged. **Брока полностью удалена.**

### RPC signatures actuelles

- `calculate_user_targets(p_telegram_id BIGINT, p_save_to_db BOOLEAN DEFAULT FALSE) → JSONB` — **v11** (live). Возвращает `calculations.bmr_formula` enum (`mifflin` / `schofield_hw` / `molnar` / `luhrmann` / `katch_mcardle`), `calculations.diet_type` + `protein_diet_multiplier`, `calculations.lbm_kg`, `calculations.rfm_body_fat_pct`. **НЕ ПЕРЕПИСЫВАЙ его** — будет регрессия. Используй pattern «делегировать через RPC поверх» (см. ниже).
- `get_day_summary(p_telegram_id BIGINT) → JSONB` — **существует**, нужно **extend** под Phase 3 (добавить `adjusted_targets` block), не создавать новый.

### Schema находки — критически с полей

В `users` таблице **уже есть** cycle-related columns:
- `cycle_start_date DATE` (последний период)
- `cycle_avg_length INT` (длина цикла)
- `cycle_phase TEXT` (текущая фаза — может быть computed)

Это значит **infrastructure для луtейн модификатора partial готова**. Сэкономит scope. Но проверь:
- Откуда они заполняются? (Скорее всего onboarding или legacy quiz — выяснить).
- Их семантика? — `cycle_phase` это enum? какие значения?

**Sleep/stress колонок НЕТ** — добавляешь свои.

### Maternal exclusion

`is_pregnant`, `is_lactating`, `pregnancy_trimester`, `lactation_started` — все есть. **Луtейн модификатор обязан excluded для pregnant/lactating** (нет цикла). Sleep/stress — applicable для всех.

---

## Архитектурное предложение (на твоё решение, нужно approve у owner)

### Sub-phase 3a — Schema + Engine (mig 296)

**Это foundation. Без неё никакой modifier не работает.**

Что делаем:

1. **Schema:**
   - `ALTER users ADD COLUMN sleep_quality TEXT` (`short` / `okay` / `great` / NULL)
   - `ALTER users ADD COLUMN sleep_recorded_at TIMESTAMPTZ` (для auto-reset через 24h)
   - `ALTER users ADD COLUMN stress_level TEXT` (`none` / `moderate` / `high` / NULL)
   - `ALTER users ADD COLUMN stress_recorded_at TIMESTAMPTZ`
   - **Cycle columns уже есть** — не дублируй.
   
   **Альтернативная архитектура (рассмотри):** не хранить state в `users`, а **только** в `daily_modifiers` table per spec. Юзер свой `sleep_quality` сегодня — это row в `daily_modifiers WHERE date=today AND modifier_type='sleep'`. Более normalised, легче исторически анализировать. **Я бы рекомендовал этот путь.** Owner ТЗ предлагает именно его.

2. **`daily_modifiers` table** (per spec.md + owner ТЗ):
   ```sql
   CREATE TABLE daily_modifiers (
       id BIGSERIAL PRIMARY KEY,
       telegram_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
       date DATE NOT NULL,
       modifier_type TEXT NOT NULL CHECK (modifier_type IN ('sleep', 'stress', 'luteal')),
       trigger_value TEXT,           -- 'short'/'high'/'luteal_phase' etc.
       calories_delta INT DEFAULT 0,
       protein_delta_pct NUMERIC DEFAULT 0,
       fat_delta_pct NUMERIC DEFAULT 0,
       carbs_delta_pct NUMERIC DEFAULT 0,
       reason TEXT,
       created_at TIMESTAMPTZ DEFAULT NOW(),
       UNIQUE (telegram_id, date, modifier_type)  -- 1 record per type per day
   );
   CREATE INDEX idx_daily_modifiers_tid_date ON daily_modifiers (telegram_id, date DESC);
   ```

3. **`apply_daily_modifier(p_telegram_id, p_modifier_type, p_trigger_value)` RPC** — записывает row в `daily_modifiers` + вычисляет deltas по trigger. Здесь живёт бизнес-логика какой modifier какой delta.

4. **`get_day_summary` extend:** вернуть base targets (как сейчас) + `adjusted_targets` (base + sum of active modifiers' deltas) + `active_modifiers` array.

5. **`apply_daily_modifiers_engine(p_telegram_id, p_date)` internal helper** — собирает все active modifiers за date, возвращает merged delta. **Multi-modifier stack rules:**
   - **Calories deltas складываются** (max +500 kcal safety cap).
   - **Pct deltas складываются** (max ±25% safety cap).
   - **Sleep + stress + luteal могут coexist** — все additive.
   - Защита от exploitation: max ±25% per macro per day.

6. **Tests:** 5-8 sentinel cases — schema correctness, engine math, get_day_summary integration, multi-modifier compose, maternal exclusion для luteal trigger.

**НЕ делать в 3a:**
- UI / check-in modals
- Reminder cron entries
- Modifier business logic (применяется когда trigger).
- Это всё в 3b/3c/3d.

### Sub-phase 3b — Sleep modifier (mig 297)

1. **Daily check-in modal** — pushed через reminder cron, hour=9 local. «Как ты спал?» 3 кнопки (`short` / `okay` / `great`).
2. **`apply_daily_modifier(tid, 'sleep', 'short')`** — записывает delta: `protein +15%`, `carbs −15%`, `calories_delta=0`.
3. **Reminder cron** — add type `'sleep_check_in'` в `cron_get_reminder_candidates` (pattern из mig 295 `waist_retrofit`).
4. **i18n × 13 langs** через subagent.
5. **Banner на day_summary / my_plan** — show «учёл недосып: protein +15%».

### Sub-phase 3c — Stress modifier (mig 298)

1. **Check-in modal** (с empathy tone — Sassy Sage anti-shame).
2. **`apply_daily_modifier(tid, 'stress', 'high')`** — delta: `carbs +12.5%`, `fat −X%` для same total kcal.
3. **DR pivot:** stress carbs → **low-GI** (whole grains, oats). Это **не в spec.md**, но в roadmap §P2.4. **Применяй pivot.** Reason text должен подсказывать low-GI варианты.
4. **РПП safety guard** (critical!) — если у user'а active `underweight_lose_override` ИЛИ `extreme_cachexia_recommend_medical` guard И юзер заявляет stress=high — **escalate** через `guard_audit_log` event, не auto-apply modifier. Stress в restriction → high РПП risk. **Не делай modifier silent override — нужен extra confirmation.**

### Sub-phase 3d — Luteal phase modifier (mig 299)

1. **Cycle tracking opt-in** — у некоторых юзеров `cycle_start_date` уже заполнен (verify откуда). Для новых — opt-in flow с explicit privacy message.
2. **Computation:** `cycle_day = (current_date - cycle_start_date) % cycle_avg_length`. Luteal phase ≈ day 15-28 (or last 14 days of cycle).
3. **`apply_daily_modifier(tid, 'luteal', 'late_luteal')`** — delta: `calories_delta=+175`, `fat_delta_pct=+7%`. Carbs auto-balance.
4. **Maternal exclusion** (critical) — `is_pregnant=TRUE OR is_lactating=TRUE` → НЕ применять luteal modifier (нет цикла).
5. **Daily cron** evaluates cycle phase для всех female users (NOT pregnant/lactating, opt-in only) → automatically inserts `daily_modifiers` row если luteal phase active.
6. **UX** — destigmatize: «нормально хотеть больше — это прогестерон». Sassy Sage tone.

---

## Critical gotchas с полей (читай или огребёшь)

### 1. РПП safety risk в stress modifier

Stress modifier работает «добавь углеводов когда тревожно». Это может **подкрепить** disordered eating patterns если юзер сейчас в restricted episode. **Защита:**
- Если у юзера active `bmi_warning IN ('extreme_cachexia_recommend_medical', 'underweight_lose_override')` — stress modifier **НЕ apply** auto. Шли modal: «давай поговорим о профессиональной помощи» + link на support.
- Аналогично для `min_kcal_warning` (below floor).
- Audit все stress modifier applications в `guard_audit_log` event=`stress_modifier_applied` или `stress_modifier_suppressed`.

### 2. Maternal exclusion для luteal

`is_pregnant=TRUE` → нет цикла. `is_lactating=TRUE` → цикл может быть irregular/absent. **Hard skip** luteal modifier для них. Не выводить «бот не работает с беременностью» — просто молча skip.

### 3. Multi-modifier stack safety cap

Если все 3 modifier'а active одновременно (плохой сон + стресс + лютеин), их deltas складываются. **Защита:**
- `total_calories_delta` clamp ±500 kcal max.
- Per-macro pct clamp ±25% max.
- Документировать в `daily_modifiers.reason` если cap triggered.

### 4. Anti-shame / privacy для PMS

Лютеиновый модификатор — **opt-in only** с explicit privacy disclaimer. Anti-shame language обязателен. **Не использовать «женщины часто переедают» — это shame по умолчанию.** Tone: «прогестерон термогенез ~+200 kcal — это естественно».

### 5. Surgical edit `calculate_user_targets` НЕ ТРОГАТЬ

Phase 3 **не должен** менять `calculate_user_targets`. Modifiers — это **delta поверх** outputs RPC. Архитектура: RPC возвращает base, `get_day_summary` накладывает delta из `daily_modifiers`. Если будешь трогать `calculate_user_targets` — высокий risk регрессии mig 291/292/295.

### 6. Существующие cycle columns — verify semantics

`cycle_start_date`, `cycle_avg_length`, `cycle_phase` уже в `users`. **Проверь:**
- Когда заполняются? (onboarding? legacy quiz? manual?)
- `cycle_phase` — computed or stored? Если stored — какие значения? Cron evaluates?
- Если заполнены у юзеров — реюзай. Если empty — нужен opt-in flow.

### 7. `get_day_summary` extend, не replace

`get_day_summary` — критичный RPC, его юзает day-summary cron + UI. **Не переписывай** — `pg_get_functiondef` + surgical edit (как mig 291/292/295). Тесты обязательны на pre-modifier path (base targets unchanged).

### 8. Parallel agents едят mig номера

Я прошёл через **3 коллизии** в спринте: 293 → 294 → 295. Параллельные агенты merge mig'и быстрее чем планируется. **Перед каждым commit:**
```bash
git fetch origin main
git rebase origin/main
git diff origin/main..HEAD --stat  # sanity check scope
```

`pre-push.sh` migration collision guard ставится автоматически если `git config core.hooksPath .github/hooks` сделан (one-time).

### 9. i18n × 13 langs делегируется subagent

Pattern из mig 291/295: spawn subagent с full brief (NOMS conventions + Sassy Sage tone + Telegram SRE constraints + 13 lang_codes). Subagent возвращает clean JSON, post-process replace `&lt;b&gt;` → `<b>` (subagent любит escape HTML).

### 10. Sentinel tests TX/ROLLBACK на owner-юзере

Owner tid=786301802. Use `BEGIN; SAVEPOINT; ... ROLLBACK TO SAVEPOINT;` для всех мутирующих тестов. Pattern из `tests/integration/test_calc_user_targets_rfm.py`. Прод не задевать.

### 11. Multi-mig compat test обязательно

Каждый Phase 3 PR должен testить compatibility с mig 291/292/295:
- Vegan + stress modifier — protein × 1.25 AND carb adjustment работают.
- Adolescent + sleep modifier — Schofield BMR + protein +15%.
- Obese-with-waist + luteal — Katch-McArdle BMR + kcal +175.
- Pregnant + sleep — sleep modifier OK, luteal SKIPPED.

### 12. Severity matrix per safety-guard-ux-pattern

Adaptive modifiers попадают в категорию **informational** (banner, no override goal). Применяй pattern:
- Profile passive pill «🌙 Учёт сна» когда sleep modifier active.
- First-trigger card (модал) при первом применении модификатора — explain почему.
- Auto-resolve (modifier expires через 24h) — short message «модификатор снят».

См. [[safety-guard-ux-pattern]] §2 5 touch points (можно reuse adapter).

---

## Что я НЕ закрыл (наследие — твоё)

### Из mig 291 (DIAAS) follow-ups

- **Onboarding step `registration_step_diet`** — добавить новый шаг в FSM `process_onboarding_input` (576 LOC). Owner approved отложить до тех пор пока quiz будет переписываться (что сейчас уже произошло — mig 295 расширил `phenotype_result` entry button). Можешь сделать как side-quest или оставить в open tech debt.
- **profile_main entry point** + display current diet value — требует правки `get_profile_business_data`.
- **Retrofit cron** для diet_type — translation key уже на проде × 13 langs, wiring через `cron_get_reminder_candidates` пока не сделан.

### Из mig 292 (BMR formula switch) follow-ups

- **`<18 + goal=gain age 13-14` → force maintain** (пубертатная защита) — roadmap mentions, не закрыто. Safety guard, не formula switch.
- **`>75 + lose` → clamp speed на slow max** — то же.

Оба safety guards, не trivial — отдельный workstream если решим.

### Из mig 295 (RFM) follow-ups

Нет open items. Phase 3 — **самостоятельный** workstream поверх mig 295.

---

## Прочитай перед стартом (must-reads)

1. **`.claude/specs/adaptive_modifiers_spec.md`** — оригинальная spec (но **DR pivot** про low-GI carbs там не упомянут — см. roadmap §P2.4).
2. **`claude-memory-compiler/knowledge/concepts/calc-user-targets-roadmap.md`** §P2.4 — финальный план Phase 3 с pivot'ом.
3. **`claude-memory-compiler/knowledge/concepts/safety-guard-ux-pattern.md`** — 5 touch points + severity matrix (informational).
4. **`claude-memory-compiler/knowledge/concepts/user-data-collection-pattern.md`** — retrofit cron pattern (используется для check-ins).
5. **`claude-memory-compiler/daily/2026-05-20.md` sessions 7-10** — context P1 sprint, lessons learned (research subagent, surgical edit, parallel agents).
6. **`migrations/295_rfm_katch_mcardle_waist.sql`** — ref pattern для multi-section SQL migration (schema + RPC + screens + i18n + cron).
7. **`tests/integration/test_calc_user_targets_rfm.py`** — ref pattern для integration tests (TX/ROLLBACK + multi-mig compat).

---

## Tooling & access

- **DB:** psycopg2 + `DATABASE_URL` из `/Users/vladislav/Documents/NOMS/.env`.
- **VPS:** auto-deploy через GHA. После merge PR → deploy.
- **NLM:** notebook `NOMS Supabase Data` (ID `fa75f4de-96c2-4dc0-bc9d-0bf07bd992f5`). **STOP-RULE:** 3-4 NLM вопроса перед любым SQL/планом.
- **Subagent for i18n × 13 langs:** brief = NOMS conventions + Sassy Sage tone + Telegram SRE constraints + lang_codes list. Возвращает clean JSON.
- **Owner test user:** tid=786301802 (full profile, used for all sentinel tests).
- **Test user 417002669** (admin) — alternative for cross-verification.

---

## Sprint sequence — рекомендуемая разбивка

| PR | Mig | Scope | Estimated sessions |
|---|---|---|---|
| #1 | **296** | Schema + Engine (foundation) | 1 session |
| #2 | **297** | Sleep modifier (full UX + i18n + cron + tests) | 1-2 sessions |
| #3 | **298** | Stress modifier + РПП safety guard | 1-2 sessions |
| #4 | **299** | Luteal phase modifier + opt-in flow | 2 sessions (privacy-sensitive) |

**Если scope раздувается:** разбивай дальше. Не делай mono-mig — параллельные агенты съедят номера, regression risk высокий.

---

## Closing checklist для каждого PR

Перед merge каждой mig из Phase 3:

- [ ] **NLM-first** — 3-4 вопроса в NLM перед SQL.
- [ ] **`pg_get_functiondef` baseline** для `get_day_summary` (не из git, из живого прода).
- [ ] **Sentinel cases** ≥ 5 (включая multi-mig compat).
- [ ] **Integration tests** через TX/ROLLBACK на owner-юзере (прод не задет).
- [ ] **`git rebase origin/main` перед commit** (parallel agents).
- [ ] **`git diff origin/main..HEAD --stat`** sanity check scope.
- [ ] **PR description** с math + sources + sprint context.
- [ ] **Daily journal** `claude-memory-compiler/daily/YYYY-MM-DD.md` append.
- [ ] **MEMORY.md** update HEAD + Phase 3 progress.
- [ ] **KB roadmap.md** update P2.4 → ✅ DONE (с timestamp + lessons).

---

## Финал

P1 Accuracy sprint trilogy = технический foundation для Phase 3. Adaptive modifiers работают **поверх** уже точной формулы (vegan / pediatric / Katch / Mifflin). Без P1 — adaptive поверх неточного BMR = шумная адаптация на шумных данных.

Sprint завершён. Эстафета твоя. Удачи.

— Предшественник (P1 Accuracy sprint, 2026-05-20)
