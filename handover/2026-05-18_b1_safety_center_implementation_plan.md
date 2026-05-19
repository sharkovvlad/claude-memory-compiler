# Handover — Phase B1 Safety Center Implementation Plan

**Адресат:** next agent — реализует first PR по B1 после merge PR #111.
**Срочность вхождения:** 10-15 минут чтения + 30 мин coding для mig 274.
**Status:** owner-approved 2026-05-18 evening, B0 complete (после PR #111 merge), B1 unblocked.

---

## ⚡ Quick state (30 sec)

- B0 done end-to-end после PR #111 merge: `my_plan` cleaned (4 buttons), submenu `my_plan_settings` works, back navigation works from all leaf screens.
- B1 decisions locked в [[concepts/safety-center-implementation-plan]] §B1 decisions:
  - Pill text: `🛡️ Активная защита: [N] 〉` (13-lang spec ready)
  - Empty state: full hide
  - Click depth: pill → safety_center → modal_full
  - B2 timing: 3-5 days after B1 deploy
- B1 implementation = **3 separate PRs recommended** (foundation → integration → translations).

---

## 🎯 B1 Goal

Replace inline `{banner_block}` injection в `my_plan` (currently 7-9 lines pushing main content off-screen) с компактным pill `[🛡️ Активная защита: 2 〉]` ведущим на отдельный `safety_center` screen.

Backend infrastructure уже готова:
- `_safety_guard_severity` RPC (mig 264) — severity matrix per (family, enum)
- `users.shown_guards` JSONB — per-user shown state
- `warning.{age,maternal,bmi,min_kcal}.*` translations — все 13 langs (mig 240/258/270)
- `build_safety_guard_banner_block` (mig 268) — current banner helper (severity-sorted)

---

## 📋 B1 PR breakdown — 3 PRs recommended

### PR B1-A (mig 274): Foundation — RPC + helper + screen + pill translations

**Scope:**
1. New RPC `get_safety_center_data(p_telegram_id, p_lang)` → JSONB
   - Returns list of active guards с severity rank, translations resolved
   - Skips informational severity (per mig 263)
2. New helper `build_safety_pill_block(p_telegram_id, p_lang)` → TEXT
   - Returns empty string if 0 non-informational guards
   - Returns `🛡️ Активная защита: N 〉` if ≥1
3. New screen `safety_center` (kind=`inline_kb`, business_data_rpc=`get_safety_center_data`)
4. New button `safety_center.back` → cmd_back, full-width
5. Translations 13 langs × 2 keys = 26 entries:
   - `pill.active_safety` (single key, format `🛡️ Активная защита: {count} 〉`)
   - `safety_center.title` (single key)
   - Body text rendered dynamically from `get_safety_center_data` per-guard cards

**Files:**
- `migrations/274_safety_center_foundation.sql`
- No Python changes needed (pure headless)

**Verification:**
- Sentinel: user with age + maternal guards → pill text rendered correctly
- `safety_center` screen renders list of guards as expected
- Empty state user (no guards) → pill empty string

### PR B1-B (mig 275): Integration — my_plan template switch

**Scope:**
1. Replace `{banner_block}` → `{safety_pill_block}` в `profile.my_plan_text` translations (13 langs)
2. Update `get_my_plan_business_data` RPC — replace `v_banner_block := build_safety_guard_banner_block(...)` с `v_safety_pill := build_safety_pill_block(...)`
3. Add `safety_pill_block` placeholder в template_vars JSON return
4. **Не трогаем** profile_main + personal_metrics — это B2 scope

**Files:**
- `migrations/275_my_plan_safety_pill_integration.sql`

**Verification:**
- Live-test ES user: my_plan no longer shows 7-line banner — single pill instead
- Click pill → safety_center opens

### PR B1-C (mig 276): Translations — per-guard action hints (deferred, B3 scope)

Этот PR можно отложить до B3. Изначально safety_center body renders `banner_title + banner_body` для каждого guard'а — это уже работает с existing translations. Action hints per severity (B3) — добавочный copywriter scope.

---

## 🛠 PR B1-A skeleton (mig 274 SQL)

### RPC `get_safety_center_data`

Pattern: adapt `build_safety_guard_banner_block` (mig 268). Instead of concatenating titles+bodies, return JSONB array.

```sql
CREATE OR REPLACE FUNCTION public.get_safety_center_data(
    p_telegram_id BIGINT,
    p_lang TEXT
)
RETURNS JSONB
LANGUAGE plpgsql
STABLE SECURITY DEFINER
SET search_path TO 'public'
AS $function$
DECLARE
    v_calc JSONB;
    v_calculations JSONB;
    v_translations JSONB;
    v_age_warning TEXT;
    v_bmi_warning TEXT;
    v_min_kcal_warning TEXT;
    v_pregnancy_warning TEXT;
    v_lactation_warning TEXT;
    v_informational_enums TEXT[] := ARRAY[
        'age:underage_disclaimer',
        'age:elderly_less_accurate',
        'bmi:extreme_obesity_informational'
    ];
    v_guards JSONB := '[]'::jsonb;
    v_rec RECORD;
BEGIN
    -- Calculate user targets для warnings
    BEGIN
        v_calc := public.calculate_user_targets(p_telegram_id, FALSE);
    EXCEPTION WHEN OTHERS THEN
        RETURN jsonb_build_object('success', false, 'error', SQLERRM);
    END;

    IF v_calc IS NULL OR COALESCE((v_calc->>'success')::BOOLEAN, FALSE) IS NOT TRUE THEN
        RETURN jsonb_build_object('success', false, 'guards', '[]'::jsonb, 'count', 0);
    END IF;

    v_calculations := v_calc->'calculations';
    v_age_warning := v_calculations->>'age_warning';
    v_bmi_warning := v_calculations->>'bmi_warning';
    v_min_kcal_warning := v_calculations->>'min_kcal_warning';
    v_pregnancy_warning := v_calculations->>'pregnancy_warning';
    v_lactation_warning := v_calculations->>'lactation_warning';

    -- Load translations
    SELECT content INTO v_translations
      FROM public.ui_translations
     WHERE lang_code = COALESCE(p_lang, 'en');
    v_translations := COALESCE(v_translations, '{}'::jsonb);

    -- Iterate guards in severity order (CTE adapted from mig 268)
    FOR v_rec IN
        WITH active AS (
            SELECT 'age'::TEXT AS family, v_age_warning AS enum WHERE v_age_warning IS NOT NULL
            UNION ALL
            SELECT 'bmi', v_bmi_warning WHERE v_bmi_warning IS NOT NULL
            UNION ALL
            SELECT 'min_kcal', v_min_kcal_warning WHERE v_min_kcal_warning IS NOT NULL
            UNION ALL
            SELECT 'maternal', COALESCE(v_pregnancy_warning, v_lactation_warning)
                WHERE COALESCE(v_pregnancy_warning, v_lactation_warning) IS NOT NULL
        ),
        ranked AS (
            SELECT family, enum,
                public._safety_guard_severity(family, enum) AS severity,
                CASE public._safety_guard_severity(family, enum)
                    WHEN 'hard_block'      THEN 1
                    WHEN 'hard_regulated'  THEN 2
                    WHEN 'soft_override'   THEN 3
                    WHEN 'informational'   THEN 4
                    ELSE 5
                END AS rank
            FROM active
        )
        SELECT family, enum, severity, rank
        FROM ranked
        WHERE (family || ':' || enum) <> ALL(v_informational_enums)  -- skip informational per mig 263
        ORDER BY rank ASC, family ASC
    LOOP
        v_guards := v_guards || jsonb_build_object(
            'family',       v_rec.family,
            'enum',         v_rec.enum,
            'severity',     v_rec.severity,
            'rank',         v_rec.rank,
            'banner_title', v_translations->'warning'->v_rec.family->v_rec.enum->>'banner_title',
            'banner_body',  v_translations->'warning'->v_rec.family->v_rec.enum->>'banner_body',
            'modal_full',   v_translations->'warning'->v_rec.family->v_rec.enum->>'modal_full'
        );
    END LOOP;

    RETURN jsonb_build_object(
        'success', true,
        'guards',  v_guards,
        'count',   jsonb_array_length(v_guards),
        'highest_severity',
            CASE WHEN jsonb_array_length(v_guards) > 0
                 THEN v_guards->0->>'severity'
                 ELSE NULL END
    );
END
$function$;
```

### Helper `build_safety_pill_block`

```sql
CREATE OR REPLACE FUNCTION public.build_safety_pill_block(
    p_telegram_id BIGINT,
    p_lang TEXT
)
RETURNS TEXT
LANGUAGE plpgsql
STABLE SECURITY DEFINER
SET search_path TO 'public'
AS $function$
DECLARE
    v_data JSONB;
    v_count INTEGER;
    v_pill_template TEXT;
BEGIN
    v_data := public.get_safety_center_data(p_telegram_id, p_lang);
    v_count := COALESCE((v_data->>'count')::INTEGER, 0);

    -- Empty state: hide pill entirely (owner-approved: Apple Health pattern)
    IF v_count = 0 THEN
        RETURN '';
    END IF;

    -- Resolve pill template — single key, count placeholder
    SELECT content -> 'pill' ->> 'active_safety'
      INTO v_pill_template
      FROM public.ui_translations
     WHERE lang_code = COALESCE(p_lang, 'en');

    IF v_pill_template IS NULL THEN
        v_pill_template := '🛡️ Active safety: {count} 〉';  -- EN fallback
    END IF;

    RETURN replace(v_pill_template, '{count}', v_count::TEXT);
END
$function$;
```

### Screen `safety_center`

```sql
INSERT INTO ui_screens (
    screen_id, render_strategy, text_key, parent_screen_id,
    back_screen_id_default, business_data_rpc, input_type, validation_rules, meta
) VALUES (
    'safety_center',
    'replace_existing',
    'safety_center.body_text',
    'my_plan',
    'my_plan',
    'get_safety_center_data',  -- ← business_data drives body rendering
    'inline_kb',
    '{}'::jsonb,
    '{}'::jsonb
);

INSERT INTO ui_screen_buttons (
    button_id, screen_id, row_index, col_index, text_key, callback_data,
    visible_condition, icon_const_key, meta
) VALUES (
    gen_random_uuid(),
    'safety_center',
    0, 0,
    'buttons.back',
    'cmd_back',
    NULL,
    'icon_back',
    '{}'::jsonb
);
```

### Translations (26 entries, jsonb_set pattern)

Pill text per lang (per [[concepts/safety-center-implementation-plan]] §B1 decisions):

```sql
-- ru
UPDATE ui_translations
SET content = jsonb_set(content, '{pill,active_safety}', '"🛡️ Активная защита: {count} 〉"'::jsonb)
WHERE lang_code='ru';
-- en, uk, es, pt, de, fr, it, pl, id, hi, ar, fa (13 total)
```

Safety center body text rendering template (server-side composes from get_safety_center_data result):

```sql
-- ru
UPDATE ui_translations
SET content = jsonb_set(content, '{safety_center,body_text}',
    '"🛡️ <b>Твоя безопасность</b>\n\n{guards_list}"'::jsonb)
WHERE lang_code='ru';
-- ... 12 more langs
```

**Note:** `{guards_list}` placeholder rendering нужно интегрировать в `render_screen` или сделать через template engine. Альтернатива — render каждый guard как отдельный block через `business_data_rpc=get_safety_center_data` + template engine processing.

**Recommendation для PR B1-A:** keep простую body — just title + count. Detailed per-guard cards в PR B1-B integration (когда видны интеграционные нюансы render_screen).

---

## 🎯 First action для next agent

1. **Read** этот handover полностью + [[concepts/safety-center-implementation-plan]] §B1 decisions
2. **Verify** PR #111 merged (mig 273 phenotype back nav fix)
3. **Check current state:** `git fetch origin main && git log --oneline -3` — последний коммит должен включать mig 273
4. **Branch:** `git checkout -b claude/mig274-b1-safety-center-foundation origin/main`
5. **Implement** mig 274 per skeleton выше
6. **Apply** transactionally + sentinel verification
7. **Open PR** for B1-A

**Estimated time PR B1-A:** 45-60 минут focused work (RPC ~100 lines + helper ~50 + screen INSERTs + 26 translations + verification).

---

## 🧪 Verification queries для B1-A

### Sentinel A: user with 2 active guards
```sql
SAVEPOINT s1;
UPDATE users SET goal_type='lose', goal_speed='normal', is_pregnant=NULL, shown_guards='{}'::jsonb
WHERE telegram_id=786301802;

SELECT get_safety_center_data(786301802, 'ru');
-- expected: guards array with 2 entries (age hard_block first, maternal hard_regulated second),
--   count=2, highest_severity='hard_block'

SELECT build_safety_pill_block(786301802, 'ru');
-- expected: '🛡️ Активная защита: 2 〉'

ROLLBACK TO SAVEPOINT s1;
```

### Sentinel B: empty state
```sql
SAVEPOINT s2;
UPDATE users SET goal_type='maintain', goal_speed='normal', is_pregnant=FALSE, shown_guards='{}'::jsonb
WHERE telegram_id=786301802;

SELECT build_safety_pill_block(786301802, 'ru');
-- expected: '' (empty string, full hide)

ROLLBACK TO SAVEPOINT s2;
```

### Sentinel C: ES + DE pill translations
```sql
SAVEPOINT s3;
UPDATE users SET goal_type='lose', goal_speed='normal', is_pregnant=NULL
WHERE telegram_id=786301802;

SELECT build_safety_pill_block(786301802, 'es');
-- expected: '🛡️ Protección activa: 2 〉'

SELECT build_safety_pill_block(786301802, 'de');
-- expected: '🛡️ Aktiver Schutz: 2 〉'

ROLLBACK TO SAVEPOINT s3;
```

---

## ⚠️ Gotchas to avoid

1. **`COMMENT ON FUNCTION` full signature** — PostgreSQL требует все параметры включая default'ed. process_user_input и process_onboarding_input имеют 5-arg signatures. Lesson mig 273.

2. **Idempotency guard** для `CREATE OR REPLACE FUNCTION` migrations — добавлять marker check, чтобы re-apply was no-op (lesson mig 272). Например в start function body: `-- mig 274 marker`.

3. **Snapshot baseline** перед surgical edits — `pg_get_functiondef` save в `migrations/_baseline_*_pre_migN.sql` для emergency rollback.

4. **Headless button rules** (lesson mig 271/272):
   - icon_const_key есть → text БЕЗ emoji prefix
   - meta.target_screen ОБЯЗАТЕЛЕН для headless dispatch (не достаточно router whitelist)

5. **process_user_input dispatch flow** — для cmd_safety_center callback нужно ИЛИ:
   - Add to hardcoded CASE block в process_user_input (lines 132-159) — legacy fast-path для reply-kb-synth
   - ИЛИ button.meta.target_screen='safety_center' — canonical headless (recommended)

   Для pill click из my_plan: button будет в `ui_screen_buttons` for screen my_plan, callback `cmd_safety_center`, meta.target_screen='safety_center'. Это PR B1-B scope (integration).

---

## Connection — где B1 affects other code

- **Python:** **NO changes**. B1 fully headless, через DB config.
- **Router:** add `cmd_safety_center` в `PROFILE_V5_CALLBACKS` (PR B1-B scope при integration)
- **n8n:** unaffected (banner_block legacy → safety_pill_block; helper API change is SQL-only)

---

## Related KB

- [safety-center-implementation-plan](../knowledge/concepts/safety-center-implementation-plan.md) — owner-approved 4-phase plan
- [safety-banner-ux-redesign-2026-05-18](../knowledge/concepts/safety-banner-ux-redesign-2026-05-18.md) — original Plan A vs B research
- [safety-guard-ux-pattern](../knowledge/concepts/safety-guard-ux-pattern.md) — severity matrix + touch points
- [headless-architecture](../knowledge/concepts/headless-architecture.md) — render_screen + business_data_rpc pattern

---

## Closing notes from current agent

Сессия 2026-05-18 evening доставила 7 PRs (102/103/104/105/107/110/111). B0 фактически complete после merge PR #111. B1 — натуральный next step, но spec большой и заслуживает focused session со свежим контекстом. mig 274 skeleton выше — это working starting point для следующего агента.

Все B1 decisions залочены, спецификация полная, gotchas документированы. Удачи!
