# Handover — Phase B1-B Safety Center Integration

**Адресат:** next agent — реализует mig 275 после merge PR #113 (B1-A).
**Срочность вхождения:** 5-10 минут чтения + 30-45 мин coding.
**Status:** B1-A foundation в PR #113 (open, ready to merge), B1-B unblocked после merge.

---

## ⚡ Quick state (30 sec)

- B1-A landed **dormant**: RPC `get_safety_center_data` + helper `build_safety_pill_block` + screen `safety_center` + back button + 13 langs × 2 keys translations.
- Никаких изменений в `my_plan` template или router. Пользователь B1-A в UI не увидит.
- B1-B = integration: my_plan template switch + pill button + router callback + analytics.

---

## 🎯 B1-B Goal (mig 275)

Заменить inline `{banner_block}` (7-9 lines) в `my_plan` на compact pill `[🛡️ Активная защита: N 〉]`, ведущий на `safety_center`.

---

## 📋 mig 275 scope

### 1. my_plan template switch (13 langs)
В `profile.my_plan_text` translations найти `{banner_block}` placeholder и заменить на `{safety_pill_block}`. Через `jsonb_set` pattern (как в mig 271) или `regexp_replace` на content.

**Pre-check:**
```sql
SELECT lang_code, content -> 'profile' ->> 'my_plan_text'
FROM ui_translations
WHERE content -> 'profile' ->> 'my_plan_text' LIKE '%{banner_block}%';
-- expected: 13 rows
```

### 2. RPC `get_my_plan_business_data` patch (surgical)
Live function (mig 268 baseline) computes `v_banner_block := build_safety_guard_banner_block(...)`. Заменить на:
```sql
v_safety_pill := public.build_safety_pill_block(p_telegram_id, p_lang);
```
И в RETURN объекте: добавить `safety_pill_block` в template_vars, удалить `banner_block`.

**WARNING (stale-base regression, lesson 04.05):** база — ТОЛЬКО из `pg_get_functiondef('public.get_my_plan_business_data'::regproc)` живого прода. Не из git. Использовать pattern из mig 268 (`DO $patch$ ... pg_get_functiondef ... replace ... EXECUTE $body$`).

**Idempotency guard:** добавить marker `-- mig 275 safety pill switch` в новое тело, проверять `position(marker IN body) > 0` — skip surgical edit if уже applied (lesson mig 268).

### 3. Add pill button на my_plan screen
Сейчас в my_plan 4 buttons (per mig 271):
- r0c0 edit_goal
- r1c0 personal_metrics
- r2c0 configure_plan (my_plan_settings)
- r3c0 back

**Решение по pill location:** pill — это **inline_kb button**, не часть body text. Но handover B1 описывает её как "compact pill в тексте". Если решение — кнопка, добавить в row 0 (top) full-width:
- r0c0 safety_center (visibility: `users.shown_guards.* IS NOT NULL OR active_guards > 0`)
- r1c0 edit_goal (shifted)
- r2c0 personal_metrics
- r3c0 configure_plan
- r4c0 back

**Альтернатива** (handover §B1 implies): pill — текстовая строка в `{safety_pill_block}` placeholder ВЕРХУ body. Empty string при count=0 collapses row. **Это canonical interpretation owner-approved 2026-05-18.**

→ Pill реально pure-text, без отдельной кнопки. Click handling через… **stop, problem:** нет кнопки → нет click. Текстовая строка в Telegram inline_kb не clickable.

**Resolution (предлагается):** pill — это **inline_kb кнопка** в row 0 my_plan (full-width). visible_condition использует `business_data.safety_pill_block <> ''` (empty pill → button hidden). callback_data='cmd_safety_center', meta={"target_screen":"safety_center"}.

Если owner предпочитает другой layout — обсудить ДО mig 275.

### 4. Router: `cmd_safety_center` в PROFILE_V5_CALLBACKS
В `dispatcher/forward.py` или `dispatcher/router.py` (зависит от текущей раскладки) — add `cmd_safety_center` в whitelist. Pattern: button.meta.target_screen='safety_center' canonical headless dispatch.

**Pre-check:** `grep PROFILE_V5_CALLBACKS dispatcher/` чтобы найти точное местоположение whitelist.

### 5. Click analytics instrumentation (продакт #3)
Логировать pill click для CTR измерения (B2 decision input). Варианты:
- a) Standard headless logging — если уже есть `log_button_click` или эквивалент в process_user_input
- b) Add to `guard_audit_log` (mig 239) event='pill_clicked' с metadata={family, severity}
- c) Otel/Prometheus counter — если есть infra

**Recommended:** (b) — переиспользует существующую таблицу + `mark_guards_shown` style API. Простой `INSERT INTO guard_audit_log (telegram_id, trigger_name, event, metadata, occurred_at) VALUES (..., 'safety_pill_click', ...)` в обработчике `cmd_safety_center`.

### 6. VPS p95 benchmark
После apply + push к main + auto-deploy:
- Через psycopg2 на VPS: 10 прогонов `dispatch_with_render` от ввода до render для пользователя с активными guards.
- Target: p95 < 700ms (UX latency rule из CLAUDE.md).
- Если p95 > 700ms — investigate Plan B materialized view.

---

## 🛠 Verification sentinels для B1-B

### Sentinel A: my_plan renders pill (active guards)
```sql
SAVEPOINT s1;
-- tid=786301802 already has 2 active guards (current state lose+fast+pregnant+lactating)
SELECT (get_my_plan_business_data(786301802) -> 'template_vars') ->> 'safety_pill_block';
-- expected: '🛡️ Активная защита: 2 〉'

-- via dispatch_with_render (full path)
SELECT dispatch_with_render(786301802, 'cmd_my_plan');
-- expected: text contains '🛡️ Активная защита: 2', NOT 7-line banner
ROLLBACK TO SAVEPOINT s1;
```

### Sentinel B: pill click → safety_center
```sql
-- Simulate cmd_safety_center callback
SELECT process_user_input(786301802, NULL, 'cmd_safety_center', ...);
-- expected: state changed to safety_center, render shows screen body
```

### Sentinel C: empty state in my_plan
```sql
SAVEPOINT s3;
UPDATE users SET goal_type='maintain', goal_speed='normal',
                 is_pregnant=FALSE, is_lactating=FALSE, weight_kg=65,
                 birth_date='1995-05-15'
WHERE telegram_id=786301802;

SELECT (get_my_plan_business_data(786301802) -> 'template_vars') ->> 'safety_pill_block';
-- expected: '' (empty string, no pill row)
ROLLBACK TO SAVEPOINT s3;
```

---

## ⚠️ Gotchas / lessons из B1-A

1. **`jsonb_set` silently no-ops для missing intermediate keys.** Если ключ `top.sub` — new, и `top` не существует ни в одной строке, `jsonb_set('{top,sub}', ...)` молча возвращает input unchanged. Используй `content || jsonb_build_object('top', jsonb_build_object('sub', '...'))`. Для my_plan_text замены `{banner_block}` → `{safety_pill_block}` — это **существующий** key, поэтому `jsonb_set` сработает; но если будут новые ключи — учти.

2. **Stale-base regression при `CREATE OR REPLACE FUNCTION`** — обязательно `pg_get_functiondef` живого прода, не git-файл. Особенно для `get_my_plan_business_data` (часто patch'ится).

3. **Idempotency marker** — добавлять в патч-body чтобы re-apply was no-op.

4. **`COMMENT ON FUNCTION` full signature** — все параметры включая default'ed.

5. **back_screen_id_default vs meta.target_screen** — `back_screen_id_default` для `cmd_back`, `meta.target_screen` для forward dispatch. Не путать (была confusing intuition в B1-A review).

6. **Schema columns:** users table использует `birth_date` (DATE), `gender` ('female'/'male'/etc.), не `age`/`sex`. Sentinel queries в B1-A handover'е имели несоответствующие имена — исправить если копируешь.

---

## 🎯 First action для next agent

1. **Verify PR #113 merged.** `git fetch origin main && git log --oneline -3` должно показать mig 274 в merged state.
2. **Branch:** `git checkout -b claude/mig275-b1b-safety-center-integration origin/main`
3. **Decide pill layout** — pure text in body via `{safety_pill_block}` placeholder OR pill as inline_kb button. Re-read B1 §click_depth decision: `pill → safety_center → modal_full`. Кnопка нужна для click. **Recommendation:** pill as inline_kb button в row 0 my_plan (full-width).
4. **Decide analytics target** — `guard_audit_log` event='safety_pill_click' looks like canonical fit.
5. **Implement** mig 275 + router.py changes + apply.
6. **Sentinels** A/B/C above.
7. **VPS p95** benchmark после deploy.
8. **Open PR** for B1-B.

**Estimated time:** 60-90 минут (RPC surgical patch + button INSERT + router + translations + sentinels + bench).

---

## Connection — где B1-B affects code

- **Python:** `dispatcher/router.py` или `forward.py` — add `cmd_safety_center` callback.
- **n8n:** unaffected.
- **SQL:**
  - `get_my_plan_business_data` patch (surgical, stale-base via pg_get_functiondef).
  - `profile.my_plan_text` translations switch (13 langs).
  - `ui_screen_buttons` — INSERT new pill button on my_plan (if button route chosen).

---

## Related KB

- [safety-center-implementation-plan](../knowledge/concepts/safety-center-implementation-plan.md) — owner-approved 4-phase plan
- [safety-guard-ux-pattern](../knowledge/concepts/safety-guard-ux-pattern.md) — severity matrix + touch points
- [pre-migration-discovery-recipe](../knowledge/concepts/pre-migration-discovery-recipe.md) — stale-base proof
- [headless-architecture](../knowledge/concepts/headless-architecture.md) — meta.target_screen + business_data_rpc
- [release-protocol](../knowledge/concepts/release-protocol.md) — deploy via GHA, sanity check

---

## Closing note from B1-A agent

mig 274 PR #113 — все sentinels green, dormant foundation готова. Translations работают на всех 5 проверенных языках (ru/es/de/ar/fa); остальные 8 не проверял live но pattern идентичный. Latency baseline acceptable, VPS bench будет в B1-B.

Один важный nuance документирован в PR body: `jsonb_set` quirk для new top-level keys — это паттерн, который мог бы пойти в KB (decision: not creating new KB entry, gotcha упомянут в этом handover + PR description, достаточно для следующего агента).

Удачи на B1-B!
