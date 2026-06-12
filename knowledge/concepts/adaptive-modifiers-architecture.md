# Adaptive Modifiers Architecture (Phase 3, mig 301+)

> **Status:** Phase 3 ALL DONE 2026-05-25. 3a foundation (mig 301), 3b sleep (mig 310), 3c stress (mig 317), **3d luteal (mig 334-335)**. Sprint stabilization closed parallel (mig 330-333).
>
> **Roadmap:** [[concepts/calc-user-targets-roadmap]] §P2.4 — DONE.

## Что это

Daily macro deltas, накладываемые на базовые таргеты `calculate_user_targets` в зависимости от физиологического состояния пользователя:

- **Sleep** (sleep_quality): adult/teen branches с разными magnitude.
- **Stress** (stress_label): low-GI углеводы.
- **Luteal phase** (cycle_phase): прогестерон термогенез.

**Key principle:** modifier — это **delta поверх** RPC output, не замена. `calculate_user_targets` остаётся source of truth для базы.

## Архитектурные решения

### 1. Physical table `daily_modifiers` (НЕ JSONB-blob, НЕ реюз `daily_metrics`)

**Tech-lead решение:** immutable audit journal — отдельная физическая таблица с строгими столбцами для медицинского аудита. `daily_metrics` остаётся orthogonal для raw user observations (sleep_hours, stress_level int, mood_score, etc).

```sql
CREATE TABLE daily_modifiers (
    id BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT NOT NULL,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    modifier_type TEXT NOT NULL,    -- 'sleep'|'stress'|'luteal'
    trigger_value TEXT NOT NULL,

    -- Computed deltas (frozen at apply-time)
    calories_delta INT,
    protein_delta_pct NUMERIC(5,2),
    fat_delta_pct NUMERIC(5,2),
    carbs_delta_pct NUMERIC(5,2),

    -- Outcome
    applied BOOLEAN,
    suppressed BOOLEAN DEFAULT FALSE,
    suppression_reason TEXT,        -- 'rpp_guard_active'|'teen_stress_escalate'|'maternal_exclusion'|'opt_in_required'

    -- Headless reason (CLAUDE.md rule #2)
    reason_i18n_key TEXT,
    reason_fallback_text TEXT,
    metadata JSONB DEFAULT '{}',

    -- Append-only journal
    superseded BOOLEAN DEFAULT FALSE,
    supersedes_id BIGINT REFERENCES daily_modifiers(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 2. Append-only + superseded pattern

Если user меняет ответ в течение дня (sleep=short → корректирует на okay):

1. UPDATE old row SET `superseded=TRUE`.
2. INSERT new row, `supersedes_id = old.id`.
3. Engine reads `WHERE applied=TRUE AND NOT superseded`.
4. Partial UNIQUE: `(tid, date, type) WHERE NOT superseded AND applied=TRUE`.

Полный journal «было X, стало Y в hh:mm» для аудита.

### 3. Clinical safety gates

`apply_daily_modifier` имеет 4 gate'а перед write — каждый возвращает suppressed row + audit log:

| Gate | Trigger | Behavior |
|---|---|---|
| **3a РПП/Cachexia** | stress=high + `bmi_warning ∈ (extreme_cachexia, underweight_lose_override)` или `min_kcal_warning ≠ NULL` | suppressed=TRUE, suppression_reason='rpp_guard_active', show_modal=TRUE, audit `event='suppressed_by_rpp_guard'` |
| **3b Teen Stress** | stress=high + age<18 | suppressed=TRUE, suppression_reason='teen_stress_escalate', escalate_to='trusted_adult_resource', show_modal=TRUE, audit `event='suppressed_teen_stress'` |
| **3c Maternal** | luteal + is_pregnant OR is_lactating | suppressed=TRUE, suppression_reason='maternal_exclusion', **show_modal=FALSE** (silent skip — UX не обижаем pregnancy) |
| **3d Opt-in** | luteal + cycle_tracking_enabled=FALSE | suppressed=TRUE, suppression_reason='opt_in_required', show_modal=FALSE |

mig 301 закладывает hook (signature + return shape). Real modal escalation вызов — mig 302+.

### 4. Age-aware deltas

| Modifier | Adult (≥18) | Teen (<18) | Rationale |
|---|---|---|---|
| Sleep='short' | P+15%, C−15% | **P+25%, C−20%** (1.67×) | Growth + GH во время deep sleep — стоимость недосыпа выше у teen |
| Stress='high' | F−7.5%, C+12.5% (low-GI) | **BLOCKED+ESCALATE** | Teen+stress = elevated mental-health risk |
| Luteal | calories+175 (late), +100 (early) | apply if menstruating | — |

### 5. Headless reason (CLAUDE.md rule #2 — no hardcoded strings)

```
reason_i18n_key     = 'modifier.stress_low_gi'   # resolves через ui_translations
reason_fallback_text = 'stress: prefer low-GI...' # admin log only
metadata.products    = ['oatmeal','buckwheat','quinoa']  # per-locale replacement
```

mig 302+ заполнит `ui_translations` rows × 13 langs. Per-locale products replacement: Турция → bulgur, Япония → гречневая лапша.

### 6. Safety caps (inline в compute_daily_modifier_stack)

- Total kcal delta: ±500 max
- Per-macro pct: ±25% max
- При cap → `capped=TRUE` в response → UI banner «достигнут лимит модификации».

## RPC reference

| RPC | Purpose |
|---|---|
| `apply_daily_modifier(tid, type, value)` | Writer + clinical gates + audit |
| `compute_daily_modifier_stack(tid, date)` | Aggregate active modifiers + clamp |
| `compute_cycle_day_for_user(tid)` | `(today - cycle_start_date) % cycle_avg_length` для luteal auto-detect |
| `get_day_summary(tid)` | Existing + `adjusted_targets` + `active_modifiers` + `modifier_caps_triggered` |

## Multi-mig compat

Mig 301 стоит поверх P1 Accuracy trilogy (mig 291/292/295). Verified:

- Vegan teen + sleep short → DIAAS ×1.25 base × Schofield BMR × force-maintain goal + protein delta +25% → correctly stacks.
- Pregnant + sleep modifier → sleep OK, luteal silently skipped.
- Cachexia + stress=high → suppressed, modal recommended.

См. `tests/integration/test_adaptive_modifiers_foundation.py` T16 для канонического multi-mig test.

## Gotchas с полей

### `daily_metrics` уже существует, но НЕ реюзаем

`public.daily_metrics` (32 rows на момент 2026-05-21) — таблица для raw user observations (sleep_hours numeric, stress_level int, cycle_day, mood_score, energy_level, symptoms[]). Predecessor handover (`handover/2026-05-21_phase3_adaptive_modifiers_handover.md`) предлагал её реюзать.

**Tech-lead reverted:** computed deltas хранятся в отдельной таблице `daily_modifiers` (immutable audit), `daily_metrics` остаётся orthogonal для raw input. Не путать семантику. Future raw-numerical input (sleep tracker integration) — будет писать в `daily_metrics`, бизнес-логика deltas — в `daily_modifiers`.

### `users.cycle_*` columns были dormant

`cycle_start_date / cycle_avg_length=28 default / cycle_phase TEXT` существовали в schema давно, но zero users with populated values, no writer, no cron. Mig 301 owns семантику:
- Add `cycle_tracking_enabled BOOLEAN DEFAULT FALSE` (explicit opt-in).
- Add CHECK on `cycle_phase IN ('follicular','ovulation','luteal_early','luteal_late')`.

### `get_day_summary` baseline через `pg_get_functiondef`

Surgical edit pattern — НЕ git-файл, НЕ NLM, **live source**. Mig 301 surgical edit добавил 3 keys, preserved 10 existing — backward-compat checked в T15.

### `calculate_user_targets.calculations.protein_diet_multiplier`

Field name — `protein_diet_multiplier`, не `diet_type_multiplier`. Common gotcha — handover говорил «DIAAS multiplier» но в реальном RPC output ключ другой. Verify через `pg_get_functiondef` или live SELECT перед написанием тестов.

### Outcome consistency CHECK

`daily_modifiers` имеет constraint:
```
(applied=TRUE AND suppressed=FALSE AND suppression_reason IS NULL)
OR
(applied=FALSE AND suppressed=TRUE AND suppression_reason IS NOT NULL)
```

Запрещает inconsistent rows (applied=TRUE + suppressed=TRUE). Гарантирует journal честный.

## p95 latency impact

Post-mig 301: `get_day_summary` p95 = 116ms (baseline ~50ms). +60ms overhead от `compute_daily_modifier_stack` SELECT. В пределах targets <200ms p95.

## Future work

- ✅ Phase 3b (mig 310 merged 2026-05-23) — Sleep UX + Premium teaser + maternal supportive banner + waist_retrofit cron fix. См. секцию ниже.
- Phase 3c (mig 311+) — Stress UX + actual РПП modal escalation вызов (Python handler читает `show_modal=TRUE` → renders modal) + teen escalate modal + ui_translations × 13 langs.
- Phase 3d (mig 313+) — Luteal opt-in flow + privacy disclaimer + cron auto-detect luteal phase (mig 312 занят Sage).

---

## Phase 3b — Sleep UX + Premium teaser (mig 310, 2026-05-23)

### Architectural pivot vs mig 301

Premium check переехал из reader (`compute_daily_modifier_stack`) в writer (`apply_daily_modifier`):

1. **Writer** считает deltas, проверяет entitlement. Если нет активного премиума — INSERT row с `applied=FALSE, suppressed=TRUE, suppression_reason='premium_required'`, deltas zero в столбцах, но **полные computed deltas сохранены в `metadata.locked_deltas`** для аудита + future premium activation.

   ⚠️ **mig 424 (2026-06-02): предикат исправлен на `user_has_active_premium(tid)`** (было `user_has_renewable_sub` — баг). См. секцию «mig 424» ниже.
2. **Reader** (`compute_daily_modifier_stack`) группирует rows на 2 buckets:
   - `active_modifiers[]` — `applied=TRUE AND NOT superseded`
   - `premium_locked_modifiers[]` — `suppression_reason='premium_required' AND NOT superseded`
3. **Teaser variant B (per PM Q1):** возвращает `qualitative_descriptor` (например `protein_boost_for_recovery`), НЕ precise numeric deltas. Защита от reverse-engineering формулы через API proxy.

### Free-tier lifestyle logging (per PM polishing #1)

UPSERT в `daily_metrics.sleep_quality_qualitative` — **UNCONDITIONAL**, выполняется ДО Premium gate. Free user может вести календарь сна бесплатно (лестница привычки); компенсаторные macro-deltas — только Premium feature.

### Maternal supportive banner (per PM polishing #1)

Изменён gate 3c (mig 301 silent skip → mig 310 supportive metadata):
- `metadata.show_supportive_banner = TRUE`
- `metadata.banner_i18n_key = 'modifier.maternal_protective.<modifier_type>'`
- Return добавляет `show_supportive_banner=TRUE` для UI hook
- `show_modal` остаётся FALSE (не модалка, а passive banner)

UX: вместо «бот молчит» когда беременная нажимает «спала плохо» — supportive banner «Вижу, ночь была непростой 🌙 Твой план под протоколом беременности — нутриенты под медицинским контролем ❤️».

#### Wiring history — было half-wired 20 дней (mig 504 closure)

**Эпохи:**
- **mig 317 (2026-05-24):** SQL начал эмитить `banner_i18n_key` и `show_supportive_banner` в return для stress maternal case. i18n ключи `modifier.maternal_protective.{sleep,stress,luteal}` заполнены 13 langs.
- **2026-05-24 → 2026-06-13 (20 дней):** **Python НЕ читал `banner_i18n_key`.** `_handle_stress_high` ([handlers/menu_v3.py](handlers/menu_v3.py)) проверял только `show_modal=TRUE` — для maternal оно FALSE → branch skip → юзер ничего не видел. Headless save_via_callback (`cmd_stress_none/moderate`) ничего из save_result в response не выносил → SQL показывал generic toast `modifier.toast.logged` («✅ Учтено!»), хотя `applied=false`. Лживая UX.
- **mig 504 (2026-06-13, PR [#393](https://github.com/sharkovvlad/noms-bot/pull/393)):**
  - `process_user_input` save_via_callback ветка → `v_telegram_ui || {'maternal_soft_landing_key': v_save_result->>'banner_i18n_key'}` если suppressed+maternal_exclusion.
  - `_envelope_from_rpc_result` читает `telegram_ui.maternal_soft_landing_key` → append `send_new` OutboundItem.
  - `_handle_stress_high` → новый `elif save_result.suppressed AND reason='maternal_exclusion'` после `if show_modal`.
  - Текст `modifier.maternal_protective.stress` обновлён в 13 langs на owner-approved soft-landing (acknowledges saved · names phase · explains safety rule · sign-off 🤍). Старый generic текст за 20 дней 0 раз показан юзеру.

**Durable урок:** SQL emit + Python consume — две поверхности одного контракта. Code-review обязан проверять обе при добавлении нового signal-поля. Quick check: `grep -rn "<new_field>" handlers/ services/` при добавлении новой колонки в RPC return. Если consumer не найден — либо TODO в commit либо инлайн-комментарий `-- TODO Python consumer: <handler>.py` чтоб не пропало.

**Sleep НЕ в этом гейте** ([mig 474 line 900](migrations/474_protein_calibration_gain_floor_sleep.sql)): `IF p_modifier_type IN ('luteal', 'stress')`. Sleep+maternal → `applied=true` (Premium) или `premium_required` (free), никогда `maternal_exclusion`. Owner-mandated isolation. При расширении гейта на новый `modifier_type` — добавить i18n ключ `modifier.maternal_protective.<type>` в 13 langs ДО раскатки SQL, иначе fallback в Python (`_MATERNAL_SOFT_LANDING_FALLBACK_EN` в [handlers/menu_v3.py](handlers/menu_v3.py)) — EN-leak, не Sage-tone.

### One-Menu UI Contract (per PM polishing #2)

`sleep_checkin` screen: `render_strategy='replace_existing'` + `next_on_submit='my_plan'` + `meta.one_menu_terminal=TRUE`. После клика на short/okay/great старая клавиатура гаснет, мгновенный re-render `my_plan` (юзер сразу видит новую плашку или Premium teaser).

### Reminder cron

`cron_get_reminder_candidates('sleep_checkin')` — target hour 09 local. Skip eligibility: пользователь уже ответил today (есть row в `daily_modifiers WHERE modifier_type='sleep' AND NOT superseded`).

### Wrapper RPC pattern

UI button save_rpc принимает 2 args `(p_telegram_id, p_value)`. Для apply_daily_modifier (3 args) сделан wrapper:
```sql
set_user_sleep_quality(p_tid, p_value) → apply_daily_modifier(p_tid, 'sleep', p_value)
```

### i18n keys (15 × 13 langs, applied 2026-05-23)

- `sleep_checkin.{title, question, button_short, button_okay, button_great}`
- `modifier.sleep_short.{adult, teen}`, `modifier.sleep_okay`, `modifier.sleep_great`
- `modifier.locked_teaser.{sleep_short, sleep_okay, sleep_great}`
- `modifier.maternal_protective.sleep`
- `modifier.premium_required.banner`
- `reminder_sleep_checkin`

Anti-shame tone, gender-neutral, Telegram SRE ≤18 chars/button. Apply pattern: per-key `jsonb_set` с явным созданием parents (PG не создаёт intermediate objects автоматически).

### Bonus: waist_retrofit cron debt (boy scout rule)

`waist_retrofit` reminder type был в `cron_get_reminder_candidates` (mig 295), но `main.py:REMINDER_TYPES` пропустил — cron его никогда не дёргал. Fixed в этой же mig.

### p95 latency post-mig 310

`get_day_summary` p95 = 183ms (mig 301 baseline 116ms, +67ms на compute_stack split + EXISTS check для locked_modifiers). В пределах <200ms target.

### Test regression breaking change

Fixture в `test_adaptive_modifiers_foundation.py` + `test_v12_personas.py` теперь устанавливает Premium=True по умолчанию (rolled back на teardown). Без этого engine tests fail на Premium gate. Pattern также применён в `tools/digital_twin_export.py`.

### Gotchas

1. **`ui_screens` schema** — нет `screen_type`/`layout`/`sort_order` полей. Use `render_strategy` + `input_type` (e.g. `'replace_existing'` + `'inline_kb'`). Buttons: `row_index`+`col_index`+`text_key`+`callback_data`+`meta` (NO `sort_order`/`button_label_key`).
2. **`ui_translations`** — JSONB per language, не key-value rows. Schema: `(lang_code TEXT, content JSONB)`. Для nested keys нужен deep merge или per-key `jsonb_set` с явным созданием parents.
3. **`user_subscriptions` нельзя DELETE** — FK на `payment_events`. Toggle Premium через UPDATE existing row.
4. **Canonical entitlement check:** `user_has_active_premium(tid)` RPC (mig 424) — это тир **A** (paid-only). НЕ `user_has_renewable_sub` (см. ниже — «продлится ли», не «есть ли доступ»). Полная матрица 3 предикатов (A paid / B active-incl-trial `user_has_active_access` / C renewability) — KB [[subscription-management-headless]] §«Entitlement predicates — SSOT» (mig 434).

   ⚠️ **mig 424 lesson — renewable ≠ entitlement.** До mig 424 гейт стоял на `user_has_renewable_sub(tid)`, который требует `cancelled_at IS NULL`. Юзер, отменивший автопродление но с активным оплаченным доступом (`status='active'`, `cancelled_at` set, `expires_at` в будущем), молча терял adaptive-модификаторы — `applied=FALSE/premium_required`, КБЖУ не пересчитывалось, хотя на экране подписки «Премиум до <дата>». Правильный entitlement-предикат = `status='active' AND payment_method != 'trial' AND expires_at > now()` (отмена НЕ влияет на доступ — KB [[subscription-management-headless]] §«status остаётся active после cancel»). `user_has_renewable_sub` остаётся только для button `visible_condition` (resume/cancel), где «продлится ли» — правильный вопрос. Свапнут в `apply_daily_modifier` + `get_daily_stats_rpc` (mig 348 premium strip).
- Mig 301 НЕ интегрирован с UI — handlers/menu_v3 read `get_day_summary['adjusted_targets']` появится в Phase 3b+.

См. также: [[concepts/safety-guard-ux-pattern]] §3 (5-tier severity matrix — adaptive modifiers = `informational`).

## Phase 3c — Stress UX (mig 317, 2026-05-24)

### Overview

Closes stress workflow end-to-end. Phase 3a (mig 301) created the DB engine; Phase 3c adds UX.

**Delivered:**
- `stress_checkin` screen (3 buttons + Back, inline_kb, `one_menu_terminal=TRUE`)
- `daily_metrics.stress_label_qualitative TEXT` — unconditional lifestyle log (free-tier)
- `set_user_stress_label(tid, value)` — 2-arg wrapper RPC
- `cron_get_reminder_candidates` stress_checkin branch (18:00 local, post-workday)
- Gate 3c extended: `IN ('luteal', 'stress')` — maternal protection for stress
- i18n × 13 langs — 15 key groups

### Hybrid modal routing pattern

`save_via_callback=TRUE` headless pipeline does NOT surface RPC return to Python (only advances to next_on_submit). For `cmd_stress_high` which may get `show_modal=TRUE` (RPP/teen gates), we use hybrid routing:

- `cmd_stress_none/moderate` → `save_via_callback=TRUE` → SQL headless (no Python needed)
- `cmd_stress_high` → NO `save_via_callback` → Python `_handle_stress_high` in `menu_v3.py`:
  1. Calls `set_user_stress_label` directly → reads `show_modal + reason`
  2. Calls `dispatch_with_render(cmd_stress_high)` → navigates to `my_plan` (SQL skips save_rpc since no save_via_callback)
  3. Appends clinical modal overlay to ResponseEnvelope as `OutboundItem(strategy="send_new", ...)` AFTER my_plan

This is the **async overlay modal pattern** — modal sent as a separate message after my_plan renders. Not blocking navigation.

### Gate 3c isolation

`IF p_modifier_type IN ('luteal', 'stress')` — sleep (`'sleep'`) is NOT in the list. Mig 310 sleep maternal behaviour completely unchanged. Verified by T5 in phase3b_sleep_ux (cachexia + sleep = no RPP gate, still passing post-mig-317).

### Router whitelisting

All three stress callbacks in `PROFILE_V5_CALLBACKS` → `target=menu_v3` (Python). Without this, they fall to section 4l → `target=menu` → n8n. Sleep buttons (`cmd_sleep_short/okay/great`) are NOT in PROFILE_V5_CALLBACKS and work via n8n, but stress_high specifically needs Python.

### Wrapper RPC

```sql
set_user_stress_label(p_telegram_id BIGINT, p_value TEXT)
→ apply_daily_modifier(p_telegram_id, 'stress', p_value)
```

### i18n keys (15 groups × 13 langs, applied 2026-05-24)

- `stress_checkin.{title, question, button_none, button_moderate, button_high}`
- `modifier.{stress_none, stress_moderate, stress_low_gi}`
- `modifier.locked_teaser.stress_high`
- `modifier.suppressed.{rpp_guard, teen_stress}` (clinical — critic 5/5, HTML formatted)
- `modifier.maternal_protective.stress`
- `cron_notifications.reminder_stress_checkin`

Clinical keys (`rpp_guard`, `teen_stress`) use `<b>...</b>` HTML tags (proper HTML, not HTML-escaped). Stored in JSONB as raw strings, rendered with `parse_mode="HTML"` in Python.

### p95 post-mig 317

`get_day_summary` p95 = 66ms (Mac baseline; VPS baseline ~183ms from mig 310). No regression in `apply_daily_modifier` or `cron_get_reminder_candidates` performance.

### Tests

12 cases in `test_phase3c_stress_ux.py`. Key coverage:
- T5: RPP gate fire + guard_audit_log check + lifestyle log still written
- T8: ordering — lifestyle log written BEFORE Premium gate (free user gets it)
- T12: cron dedup — user who answered today not in candidates

## Phase 3d — Luteal Cycle Tracking (mig 334-335, 2026-05-25)

### Overview

Closes the final sub-phase of Adaptive Modifiers. Luteal phase = прогестерон термогенез → +150-200 kcал (late) / +100 (early). Opt-in для cycle-aware женщин, auto-disable при беременности/лактации.

**Delivered (mig 334, 706 LOC SQL):**
- `phase_from_cycle_day(day, length)` SQL helper — single source of truth для фазы цикла (follicular/ovulation/luteal_early/luteal_late)
- Auto-disable: `set_user_pregnancy_flag` + `set_user_lactation_flag` обнуляют `cycle_tracking_enabled=FALSE` при maternal flag=TRUE (C1 decision тимлида)
- `save_user_cycle_data` — single-callback save RPC (`cmd_save_cycle_<today|7d_ago|14d_ago>`), упрощение vs staging design. `cycle_avg_length=28` fixed, custom length через future edit screen.
- 2 новых screens: `cycle_tracking_intro` (privacy + ценность opt-in) + `cycle_tracking_setup` (3 кнопки date offset)
- Populate existing `personal_metrics_cycle_premium_upsell` (был dormant)
- Wire-up `cmd_cycle_premium`: visible_condition `gender='female' AND ¬pregnant AND ¬lactating` + Premium/free split
- Cron `luteal_morning` @ 08:00 local в `cron_get_reminder_candidates` — DRY через `compute_cycle_day_for_user` (уже инкапсулирует maternal+opt-in gate)
- Widget integration в `wellbeing_today`: `business_data_rpc=get_day_summary` (reuse existing, не плодить новый RPC)
- EN+RU placeholder × 16 ключей
- 19/19 sentinel tests PASS

### Architecture: single-callback save

Изначальный design включал `staging` через `user_status_data` column (не существовала). Cleanup на лету: **single-callback** save pattern — `cmd_save_cycle_<today|7d_ago|14d_ago>` → RPC вычисляет `cycle_start_date = CURRENT_DATE - offset` → write. Никаких intermediate states, никаких промежуточных screens. Cleaner UX (3 кнопки → save → return).

### Luteal cron integration

`cron_get_reminder_candidates('luteal_morning')` — target hour 08 local. Eligibility:
- `cycle_tracking_enabled=TRUE`
- Premium/trial (`COALESCE(subscription_status,'free') <> 'free'`)
- Не pregnant / не lactating (gate inside `compute_cycle_day_for_user`)
- `apply_daily_modifier` не applied today (dedup through existing pattern)
- Phase = `luteal_early` или `luteal_late` (computed from `cycle_start_date + cycle_avg_length`)

### i18n × 13 langs (mig 335, 143 строки)

Anti-РПП reframe per language — critic 5/5:
- DE: «kein Kontrollverlust»
- FR: «pas un manque de discipline»
- UK: «не зриви»
- AR: «ليس ضعف إرادة» (secular medical MSA)
- FA: «ضعف اراده نیست» (ZWNJ preserved)
- HI: «kamzori nahin» (Hinglish-Latin per glossary)
- ID: «bukan kelemahan» (halal-safe, Ramadan-adjacent clean)

Button labels shortened for conversion per Номсова правка (DE/ES/FR/PT/UK — «короткие глаголы конвертят лучше»).

### Scientific basis для +100/+175 ккал (audit 2026-06-08)

Цифры долго жили в коде без явной цитаты. Audit 2026-06-08 закрыл этот пробел:

- **Первоисточник:** *Resting metabolic rate fluctuations across the menstrual cycle: a systematic review* — PMC13066135 (2024). Прирост RMR в лютеиновой фазе vs фолликулярной: **+5–10 %**, абсолют **+100…+300 ккал/день**.
- **Поддержано локальными нутрициологическими аудитами** в `~/Documents/NOMS/Нутрициолог (другой ИИ)/`:
  - `Глубокий анализ формулы расчета целей NOMS.md:91` — «Фундаментально обосновано, прогестерон термогенез, +150–200 kcal + fat +5–10%», прямая ссылка на PMC13066135.
  - `диетолог_Оптимизация расчета калорий...docx:567` — «100–300 ккал/сутки, +5–10% жиров».
  - `Разработка алгоритмов питания...docx:446` — то же.
- `~/Documents/NOMS/Нутрициолог (аудит расчётов v13)/` — про цикл не пишет (фокус на EA-floor, MSJ vs Cunningham).

**Вердикт по trigger_value:**

| trigger_value | kcal_delta | fat_pct | обоснованно? |
|---|---|---|---|
| `follicular` | 0 | 0 | да, baseline; в коде dead-branch — RPC `apply_daily_modifier` ветки `IF p_trigger_value = 'follicular'` нет, проходит мимо `IF/ELSIF` с нулями |
| `ovulation` | 0 | 0 | да, кратковременный пик не значим для дневной нормы; тоже dead-branch |
| `luteal_early` (15–21) | +100 | +3 % | да, нижняя половина научного коридора; консервативно, защищает lose-юзеров от overshoot |
| `luteal_late` (22–28) | +175 | +7 % | да, центр диапазона; совпадает с PMC13066135 и тремя локальными доками |

Поднимать до 150/200 (как предлагает `Глубокий анализ`) **не нужно** — текущие значения осознанно консервативны.

### 2026-06-08 incident & defence-in-depth (mig 491 + 494)

**Что случилось:** male admin (`telegram_id=417002669`) получил пуш «🌸 Лютеиновая фаза активна. Добавил +175 ккал». Те же сутки настоящая женщина 786301802 (cycle_day=20) получила тот же текст. Аудит: 0 luteal-строк в `daily_modifiers` за 30 дней — `apply_daily_modifier` ни разу не вызывался, дневная норма ни у кого не сдвигалась.

**Три независимых root cause:**

1. **Stale data.** Owner ранее тестировал смену пола → `cycle_tracking_enabled=true` + `cycle_start_date` остались на male-юзере. Нигде в БД не было каскада «при смене пола обнулить женские поля».
2. **Нет gender-гейта в `compute_cycle_day_for_user` (mig 375).** Проверял `cycle_tracking_enabled`, `is_pregnant`, `is_lactating`, возраст ≥55 — но не `gender='female'`. Возвращал валидный cycle_day для мужчины.
3. **Cron luteal_morning — info-only.** Шёл с комментарием «нет screen'а, юзер не отвечает» — но текст «added +175» обещал действие, которого не было. Плюс цифра 175 жёстко зашита, хотя для `luteal_early` правильный delta = 100.

**Fix:**

- **mig 491 (PR #367, MERGED 2026-06-08):** `cron_get_reminder_candidates` JSON output расширен — добавлены `luteal_phase` и `luteal_kcal_delta` per candidate. `crons/reminders.py` — для `luteal_morning` сначала зовёт `apply_daily_modifier(tid, 'luteal', luteal_phase)`, шлёт текст **только при `applied=true`**. Replace `+175` / `+۱۷۵` на `+{kcal_delta}` placeholder в 13 переводах.
- **mig 494 (PR #366, MERGED 2026-06-08):** trigger `trg_users_cascade_clear_female` на `BEFORE UPDATE OF gender, birth_date, is_pregnant, is_lactating` — обнуляет 11 женских полей при невалидных переходах. `compute_cycle_day_for_user` — добавлен `gender='female'` гейт. Backfill: 1 строка (тот самый admin).

**Defence layers в порядке исполнения:**
1. `gender='female'` гейт в `compute_cycle_day_for_user`
2. Аудиторный фильтр в `cron_get_reminder_candidates` (Premium + day 15–28)
3. `apply_daily_modifier` валидирует cycle_tracking + pregnancy/lactation, возвращает `suppressed=true` для непригодных
4. Python проверяет `applied is True` перед `sendMessage`

**Durable lessons:**

- **Связанные поля = каскад на уровне БД.** Поля, осмысленные только при определённом значении другого поля (cycle_* при gender='female', pregnancy_* при is_pregnant=true), требуют либо triggered cascade clean-up, либо CHECK constraint. Доверять «никто не оставит грязное состояние» нельзя.
- **`applied=false` ≠ `error` в Postgres jsonb-RPC.** RPC часто возвращают `{"applied":false,"suppressed":true,"reason":"..."}` для «мягких» отказов. Python-проверка только по `error` — ложно-положительный success. Всегда проверять `applied is True`.
- **Текст-обещание = действие.** Любое cron-сообщение «added +N» / «applied X» требует, чтобы код перед `sendMessage` записал то самое действие, и проверил что запись применилась. Иначе годами шлёшь ложь и узнаёшь об этом случайно.
- **Hard-coded цифры в i18n-переводах ломаются при изменении business-логики.** «+175» в 13 языках не покрывало `luteal_early=100`. Placeholder `{kcal_delta}` решает раз и навсегда.

### Closed tech debt (mig 495, 2026-06-08, PR #371)

- ✅ **Hoist luteal деталей в `app_constants`** (4 ключа: `modifier_luteal_early|late_kcal_delta|fat_pct`). RPC читает через `COALESCE` с fallback на 100/175/3/7. Hot-reload работает (live-verified). Калибровка значений теперь — `UPDATE app_constants SET value=...`, без миграции функции.
- ✅ **CHECK сужен до `IN ('luteal_early','luteal_late')`** + RPC валидация синхронно. Backfill не понадобился (0 строк с follicular/ovulation за всё время). Будущая Phase 3e расширяет осознанной миграцией.

**Остающееся:** `get_day_summary` + `compute_daily_modifier_stack` cap ±500 уже работает (mig 467) — luteal delta уважает общий потолок.

**Durable pattern (mig 474 + mig 495):** medical-дельты модификаторов живут в `app_constants` как `modifier_<type>_<trigger>_<kind>` ключи, RPC читает через `COALESCE((SELECT value::<type> FROM app_constants WHERE key='...'), <hardcoded_fallback>)`. Следующая фаза модификаторов должна следовать этому паттерну.

## My Day wellbeing line (mig 410, 2026-06-01)

До mig 410 залогованное самочувствие в карточке «Мой день» (`stats_main`) **не
отображалось** — был только Premium-gated `active_modifiers_strip` (applied-дельты,
вверху карточки) + хаб 🧬 Самочувствие для ввода. Owner запросил видимый at-a-glance
статус.

### Что добавлено

Новое поле `wellbeing_line` в `get_daily_stats_rpc` + плейсхолдер `{wellbeing_line}`
в `stats.main_text` ×13 — строка **под блоком БЖУ**: `🌙 Сон: 🥱 · 🌀 Стресс: 🤯`.

- **Free-tier** (в отличие от `active_modifiers_strip`): качественный лог сна/стресса
  бесплатный (лестница привычки), макро-дельты остаются Premium. Без premium-gate.
- Читает `daily_metrics.{sleep_quality_qualitative,stress_label_qualitative}` за
  СЕГОДНЯ (`date = (timezone(v_tz, now()))::date`, UNIQUE(tid,date)). Пусто если
  ничего не залогано → trailing `\n\n` только когда непусто → плейсхолдер схлопывается
  (паттерн `active_modifiers_strip`).

### UX-решения (durable)

1. **Значение = ЭМОДЗИ, не слово.** Telegram body — пропорциональный шрифт; «вторую
   колонку» справа от Б/Ж/У выровнять нельзя (ragged + макро-буквы локализованы:
   Б/Ж/У vs P/F/C vs П/Ж/В). Слова-значения («Спокойно»/«Нормально») не влезают в
   ≤35 chars на части языков. Эмодзи-значение снимает обе проблемы → одинаково на
   всех устройствах/языках. **Не делать right-column layout в Telegram-тексте.**
2. **Single source эмодзи** — `app_constants` (`icon_sleep_*`/`icon_stress_*`); те же
   эмодзи на check-in кнопках. Категория-лейбл («🌙 Сон»/«🌀 Стресс») берётся из
   `wellbeing.button_sleep/button_stress`.
3. **Эмодзи-набор без коллизий** (owner-approved): Сон 🥱/🙂/😎, Стресс 😌/😬/🤯.
   Заменил 😴/✨/🌀/🔥. Критерии: 😴 (спящее лицо) ≠ «мало сна»; 🌀 дублировал иконку
   категории «🌀 Стресс»; 🔥 конфликтовал со 🔥 стрика на той же карточке. Урок:
   проверяй, не занят ли эмодзи другим смыслом на ТОМ ЖЕ экране.

stored values: sleep ∈ {short,okay,great}, stress ∈ {none,moderate,high}. Python-кода
не трогали — `stats_main` уже читает `get_daily_stats_rpc`, рендерер резолвит `{wellbeing_line}`.

## Sprint stabilization (mig 330-333, 2026-05-25)

4 parallel P0 fixes closed in one session:

### mig 330 — Premium-filter + soft mutex

- **Premium-filter:** sleep_checkin / stress_checkin push для active-access юзеров (вкл. trial). Изначально (mig 330) `COALESCE(subscription_status,'free') <> 'free'`; с mig 434 → `user_has_active_access(c.subscription_status)` (тир B, тот же набор premium+trial, поведение-нейтрально). НЕ `user_has_renewable_sub` (исключает trial).
- **Soft mutex sleep > meal_morning:** окно meal_morning расширено до [9, 10] local. В 9:00 meal_morning suppressed если Premium юзер pending sleep_checkin. В 10:00 — догоняем. **Один пуш в утренний слот**, не два.

### mig 331 — stats_main wellbeing entry + hub

Новые screens:
- `wellbeing_today` — hub с [🌙 Сон] [🌀 Стресс] buttons
- `wellbeing_premium_teaser` — free CTA
- stats_main row=0: col=0 [Исправить] + col=1 [🧬 Самочувствие] (Premium) + col=2 [🔒 Самочувствие] (free) — mutually exclusive visible_condition

### mig 333 — CRITICAL sleep cron bug + 13 langs

**CRITICAL bug найден и закрыт:** `cron_notifications.reminder_sleep_checkin` = NULL во всех 13 langs. Mig 310 не залила payload, mig 317 не сделала back-fill. Закрыло баг «утренний пуш сна приходит на EN-заглушках / не приходит вовсе».

Также: 😤→🌀 emoji swap × 39 strings, RU/UK gender-leak fix, AR title bidi swap. **144 strings total** across 11 langs.

### Phase 3 Roadmap — CLOSED 2026-05-25

| Sub-phase | Mig | Closed | Что закрыто |
|---|---|---|---|
| 3a Foundation | 301 | 2026-05-21 | daily_modifiers table + 4 clinical gates + age-aware deltas |
| 3b Sleep UX | 310 | 2026-05-23 | sleep_checkin screen + Premium teaser + maternal banner + i18n |
| 3c Stress UX | 317 | 2026-05-24 | stress_checkin + hybrid modal routing + i18n |
| **3d Luteal** | **334-335** | **2026-05-25** | cycle tracking opt-in + auto-disable maternal + cron luteal_morning + widget + i18n |
| **Stabilization** | **330-333** | **2026-05-25** | Premium-filter + soft mutex + wellbeing hub + CRITICAL sleep cron NULL fix |
