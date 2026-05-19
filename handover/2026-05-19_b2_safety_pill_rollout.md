# Handover — Phase B2 Safety Pill Rollout (profile_main + personal_metrics)

**Адресат:** next agent — реализует B2 mig (next free ≥ 277) через 3-5 дней после merge PR #117.
**Срочность вхождения:** 10 минут чтения + 30 мин coding.
**Status:** B1-B integration в PR #117 (open → ожидает merge + 3-5 day post-deploy wait).

---

## ⚡ Quick state (30 sec)

- B1-A landed (mig 274 / PR #113, merged) — RPC + helper + screen + 13 langs.
- B1-B landed (mig 276 / PR #117, awaiting merge) — pill в my_plan + body cards в safety_center + headless dispatch + visibility helper.
- B2 = pill rollout на 2 оставшихся surface: `profile_main` + `personal_metrics`. Затем decommission deprecated banner_block helper (mig 268).

---

## 🎯 B2 Goal

Pill `[🛡️ Твоя безопасность 〉]` + safety_pill_block placeholder должны быть видимы на ВСЕХ 3 surfaces где юзер видит/меняет goal (per safety-guard-ux-pattern §2 distributed enforcement):
- ✅ `my_plan` — done в B1-B
- ⏳ `profile_main` — B2
- ⏳ `personal_metrics` — B2

После B2: `build_safety_guard_banner_block` (mig 268) не имеет ни одного caller'а — можно decommission'ить.

---

## 📋 B2 scope (mig 277 или next free)

### 1. Update `profile_main` business_data RPC
Проверь: какая RPC формирует business_data для profile_main? Likely `get_profile_main_business_data` или аналогичная. Surgical patch (через pg_get_functiondef + marker) — добавить:
- `v_safety_pill := public.build_safety_pill_block(p_telegram_id, v_lang, NULL);` (или v_calc если уже есть)
- В template_vars: `'safety_pill_block', v_safety_pill`

### 2. Update `personal_metrics` business_data RPC
Аналогично — найти RPC, добавить safety_pill_block field. Если business_data_rpc не существует — создать, либо использовать существующий путь через `dispatch_with_render`.

### 3. Update translations `profile.profile_main_text` + `profile.personal_metrics_text`
Если они уже содержат `{banner_block}` placeholder (которым пользовался mig 256/268) — заменить на `{safety_pill_block}`. Если нет — добавить `{safety_pill_block}` в начало body.

**Pre-check для всех 13 langs:**
```sql
SELECT lang_code,
       content -> 'profile' ->> 'profile_main_text' AS profile_text,
       content -> 'profile' ->> 'personal_metrics_text' AS pm_text
FROM ui_translations WHERE lang_code='ru';
```

### 4. INSERT pill button on profile_main + personal_metrics
Same pattern как mig 276 на my_plan:
- `text_key='buttons.safety_pill'` (existing key from mig 276, no new translation needed)
- `callback_data='cmd_safety_center'`
- `meta='{"target_screen":"safety_center"}'`
- `visible_condition='public.has_active_safety_guards(u.telegram_id)'`

Place at appropriate row (before back button, after main content). Check current layout first.

### 5. Decommission `build_safety_guard_banner_block` (optional, defer to mig 278)
После step 1-4: grep по миграциям и RPC bodies для проверки нет ли других callers. Если clean — DROP function:
```sql
DROP FUNCTION IF EXISTS public.build_safety_guard_banner_block(BIGINT, TEXT, JSONB);
```
**Defer этот step** до confirmation что все 3 surfaces используют safety_pill_block (post-deploy verification).

### 6. Sentinels
Same pattern как mig 276 — на tid=786301802 verify pill renders на всех 3 surfaces, click pill → safety_center работает откуда угодно.

---

## ⚠️ Pre-B2 gates (НЕ начинать без проверки)

1. **PR #117 merged** + auto-deploy passed smoke test.
2. **3-5 days post-deploy** прошло — это owner-locked в KB safety-center-implementation-plan §B1 decisions table.
3. **Render-rate CTR check** (proxy для click analytics):
   ```bash
   ssh root@89.167.86.20 'journalctl -u noms-webhooks --since "3 days ago" | grep -E "render_screen.*safety_center" | wc -l'
   ssh root@89.167.86.20 'journalctl -u noms-webhooks --since "3 days ago" | grep -E "render_screen.*my_plan" | wc -l'
   ```
   Sane ratio: safety_center renders > 0 (юзер видит pill и кликает), но не аномально высокий (отсутствие user confusion).
4. **No tickets** «куда пропало предупреждение» / «безопасность не работает» в admin chat 417002669.

Если любой gate fails → диагностировать + fix + repeat. Не начинать B2 пока B1-B не settled.

---

## 🛠 Implementation template (для mig 277)

Reuse pattern из mig 276 §D (surgical patch get_my_plan_business_data) — applied to 2 other business_data RPCs:
```sql
DO $patch_profile_main$
DECLARE
    v_body TEXT;
    v_marker TEXT := '-- mig 277 marker: safety_pill_block';
BEGIN
    v_body := pg_get_functiondef('public.<rpc_name>'::regproc);
    IF position(v_marker IN v_body) > 0 THEN
        RAISE NOTICE 'mig 277: already applied'; RETURN;
    END IF;
    -- find exact anchor strings via pg_get_functiondef before writing
    -- (lesson mig 276: anchors must match exact whitespace)
    ...
END $patch_profile_main$;
```

---

## ⚠️ Gotchas / lessons from B1-A → B1-B

1. **Migration number collisions are real.** mig 275 был занят PR #115 (payment) когда B1-B handover требовал 275. Took 276 instead. **Pattern:** в handover'е писать «next free ≥ NNN», не хардкодить номер. Перед apply — `git fetch origin main && ls migrations/` для текущего max.

2. **`CREATE OR REPLACE FUNCTION` НЕ изменяет parameter list.** Adding optional `p_calc DEFAULT NULL` создаёт новый overload вместо replace, ломая single-arg calls с `AmbiguousFunction`. **Pattern:** `DROP FUNCTION IF EXISTS public.<name>(<old_sig>)` перед `CREATE OR REPLACE` с новой сигнатурой.

3. **`jsonb_set` silent no-op для missing intermediate keys.** Для NEW top-level keys (типа `pill` в mig 274) использовать `content || jsonb_build_object('top', jsonb_build_object('sub', value))`. Existing keys (типа `profile`, `buttons`) — `jsonb_set` работает.

4. **render_screen patterns** (verified empirically):
   - `text_key` для buttons передаётся в Python template engine as-is — НЕТ placeholder substitution в button labels (L189, L214)
   - `callback_data` поддерживает `{var}` substitution из business_data (L147-153)
   - `visible_condition` — SQL fragment под EXECUTE с `u` row context — поддерживает function calls (L131-135)
   - `business_data_rpc` вызывается single-arg `($1)` — все RPC должны работать с 1 BIGINT (defaults для optional)

5. **`get_my_plan_business_data` принимает 1 arg** (BIGINT), не 2. Если patch требует дополнительных параметров — менять сигнатуру нельзя (breaking change для render_screen). Внутри RPC использовать NULL для optional helper params.

6. **`v_calc` pass-through** для performance: `calculate_user_targets` heavy (~200 lines). Чтобы избежать 2× recompute в одной RPC call chain, добавить optional `p_calc JSONB DEFAULT NULL` в helpers — calling RPC передаёт уже-computed v_calc.

---

## 🎯 First action для B2 agent

1. **Verify gates** (см. выше): PR #117 merged + 3-5 day wait + CTR check + no tickets.
2. **`git fetch origin main && ls migrations/`** — узнать current max number.
3. **Branch:** `git checkout -b claude/migNNN-b2-safety-pill-rollout origin/main` (NNN = next free).
4. **Locate RPCs:** `grep -l "profile_main" migrations/*.sql` + `grep -l "personal_metrics" migrations/*.sql` найдёт actual business_data RPCs.
5. **Read live bodies** via `pg_get_functiondef` — необходимы для surgical anchors.
6. **Write migration** по template выше.
7. **Apply + sentinels** на all 3 surfaces.
8. **VPS p95 bench** (CLAUDE.md mandate after RPC changes).
9. **Open PR** for B2.

---

## Connection — где B2 affects code

- **Python:** NO changes. Headless dispatch + visible_condition fully cover navigation.
- **n8n:** unaffected (legacy banner_block → safety_pill_block is SQL-only).
- **SQL:**
  - Surgical patch profile_main + personal_metrics business_data RPCs.
  - Update profile.profile_main_text + profile.personal_metrics_text translations (13 langs each).
  - INSERT 2 pill buttons (1 per screen) + bump back row_index if needed.
  - Optionally: DROP build_safety_guard_banner_block helper.

---

## Related KB

- [safety-center-implementation-plan](../knowledge/concepts/safety-center-implementation-plan.md) §B2 + §3 «Banner_block compatibility window»
- [safety-guard-ux-pattern](../knowledge/concepts/safety-guard-ux-pattern.md) §2 «Distributed enforcement» — почему pill нужна на ВСЕХ 3 surfaces
- [release-protocol](../knowledge/concepts/release-protocol.md) — deploy через GHA
- [headless-architecture](../knowledge/concepts/headless-architecture.md) — meta.target_screen + business_data_rpc
- [pre-migration-discovery-recipe](../knowledge/concepts/pre-migration-discovery-recipe.md) — stale-base proof через pg_get_functiondef

---

## Closing note от B1-B агента

PR #117 — 6 sentinels green, end-to-end workflow готов: my_plan → pill text + button → safety_center с per-guard cards → back. Latency local p95=187ms, VPS будет sub-100ms RPC. Все 5 owner-approved решений отражены в коде.

Найдено и задокументировано важное **engine limitation для B3**: render_screen НЕ поддерживает dynamic button generation из business_data. Для B3 per-guard click-to-modal потребуется engine extension — это не trivial mig, а work на уровне render_screen. Это самый большой риск для B3 timeline.

Удачи на B2!
