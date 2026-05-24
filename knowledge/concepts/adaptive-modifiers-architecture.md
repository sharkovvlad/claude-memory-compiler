# Adaptive Modifiers Architecture (Phase 3, mig 301+)

> **Status:** Phase 3a foundation merged 2026-05-21 (mig 301). **Phase 3b sleep UX merged 2026-05-23 (mig 310).** Sub-phases 3c/3d pending.
>
> **Roadmap:** [[concepts/calc-user-targets-roadmap]] §P2.4.

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

1. **Writer** считает deltas, проверяет `user_has_renewable_sub(tid)`. Если free — INSERT row с `applied=FALSE, suppressed=TRUE, suppression_reason='premium_required'`, deltas zero в столбцах, но **полные computed deltas сохранены в `metadata.locked_deltas`** для аудита + future premium activation.
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
4. **Canonical Premium check:** `user_has_renewable_sub(tid)` RPC. НЕ `users.subscription_status` (denormalized cache, drift-prone).
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
