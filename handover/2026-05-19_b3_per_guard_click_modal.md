# Handover — Phase B3 Per-Guard Click-to-Modal (Safety Center)

**Адресат:** next agent — реализует Phase B3 после merge PR #123 + 3-5 day post-deploy stability check.
**Срочность вхождения:** 15 минут чтения (это сложнее B1-B/B2 из-за engine extension).
**Status:** B1+B2 завершены через PR #117/#119/#123. Pill working на 3 surfaces, Safety Center с body_text cards в проде.

---

## ⚡ Quick state

После PR #123 в проде:
- ✅ Pill «🛡️ Активных защит: N» на my_plan + profile_main + personal_metrics
- ✅ Pill → Safety Center hub (статичная Back кнопка)
- ✅ Safety Center body — **текстовые карточки** активных guards (banner_title + banner_body)
- ❌ Per-guard кnопка в Safety Center для перехода в **modal_full** — ОТСУТСТВУЕТ
- ✅ First-trigger modals (mig 264, Tier 1) — работают independently для одноразовых push

---

## 🎯 B3 Goal

Сделать каждый активный guard в Safety Center **clickable**: tap → большая модалка с полным detailed text (`modal_full` из `ui_translations.warning.<family>.<enum>.modal_full`) в стиле Sassy Sage.

**Текущее ограничение** (verified empirically в B1-B/B2): `render_screen` не поддерживает dynamic button generation из `business_data` array. Кнопки берутся статически из `ui_screen_buttons` per screen_id. У каждого юзера РАЗНЫЙ набор активных guards → static buttons не работают.

---

## 📋 Architectural options для B3

### Option A — Engine extension (canonical, но большая работа)

Расширить `render_screen` чтобы поддерживать «dynamic buttons from business_data»:

1. Новый ui_screens поле или meta key, например `meta.dynamic_buttons_source: 'guards'` или `meta.dynamic_buttons_array_key`
2. render_screen после загрузки static buttons из ui_screen_buttons — добавляет dynamic buttons из `v_business_data->'guards'` (array)
3. Каждый guard becomes button с:
   - text_key: dynamically built (e.g. `'🔞 До 18 〉'`) ИЛИ static label «Подробнее» с context emoji per family
   - callback_data: `'cmd_show_guard_<family>_<enum>'` (use existing template `{var}` substitution в L147-153)
   - meta.target_screen: NEW screen `guard_modal` (single screen rendering modal_full)

**Pro:** clean, reusable для других «dynamic list» surfaces в будущем
**Con:** требует patch render_screen — самой критичной функции (стале-base regression risk). Возможно требует extension process_user_input для resolution `cmd_show_guard_<family>_<enum>` (template callback с substitution).

### Option B — Pre-allocated N «slot» buttons (workaround, fragile)

10 предзаготовленных static buttons в ui_screen_buttons (slot_0 ... slot_9):
- Каждый с visible_condition: `(get_safety_center_data(u.telegram_id)->'guards'->><N>) IS NOT NULL`
- text_key + callback_data — dynamically computed via meta lookup
- При >10 guards — overflow strategy («показать ещё»)

**Pro:** не трогаем engine
**Con:** fragile (limit 10), ugly visible_condition, performance hit (10× RPC calls per render for visibility eval — мig 276 visible_condition уже expensive)

### Option C — Separate Telegram messages per guard (anti-pattern)

При render Safety Center отправлять N separate messages — каждое со своим Back + inline button.

**Pro:** zero engine changes
**Con:** ломает Mini-App UX («one menu» principle, CLAUDE.md). Не пройдёт UX review.

**Рекомендация:** Option A. Затраты больше, но canonical и снижает риск future debt.

---

## 🛠 Option A — implementation outline

### 1. Extend render_screen
**Insertion point:** L196 / Step 7 (after static buttons iteration).
**Pattern:**
```sql
-- ★ Migration <next>: dynamic buttons from business_data.
-- If screen.meta has 'dynamic_buttons_source' key, iterate
-- v_business_data->meta.dynamic_buttons_source array and append
-- inline_kb buttons. Each item must have 'callback_data',
-- 'text_key', 'target_screen' fields (or `text` for static).
v_dyn_source := v_screen.meta->>'dynamic_buttons_source';
IF v_dyn_source IS NOT NULL AND length(v_dyn_source) > 0 THEN
    FOR v_dyn_btn IN
        SELECT * FROM jsonb_array_elements(
            COALESCE(v_business_data->v_dyn_source, '[]'::jsonb))
    LOOP
        -- append к v_current_row / новой row
    END LOOP;
END IF;
```

**Test before patch:** `pg_get_functiondef('public.render_screen'::regproc)` snapshot to baseline (`migrations/_baseline_render_screen_<date>.sql`). Stale-base proof обязательна.

### 2. Extend get_safety_center_data
Добавить в каждый guard JSONB entry (mig 282/284):
- `callback_data`: e.g. `'cmd_guard_modal_age_underage_forced_maintain'`
- `text_key`: emoji + short title for button label (max 18 chars)
- `target_screen`: `'guard_modal'`

### 3. New screen `guard_modal`
- `business_data_rpc`: `get_guard_modal_data(BIGINT, TEXT, TEXT, TEXT)` — берёт family + enum из callback substitution
- Body template: `{modal_full_text}` — substituted from business_data
- Static Back button → `safety_center`

Сложность — `business_data_rpc` сейчас single-arg (line 83 render_screen). Возможно расширить чтобы dispatch_with_render передавал callback_vars в RPC. Либо использовать `users.last_safety_guard_clicked` temporary state field (анти-паттерн).

**Alternative cleaner:** dispatch_with_render stores `callback_vars` в `users.session_state` JSONB per request, screen `guard_modal` business_data_rpc reads from there.

### 4. Add `cmd_guard_modal_<family>_<enum>` to PROFILE_V5_CALLBACKS via template
В dispatcher/router.py — нужен pattern match. Either:
- Add explicit все enums в whitelist (fragile, list растёт с каждым новым guard)
- ИЛИ wildcard pattern matching (новый код в router.py для prefix `cmd_guard_modal_`)
- ИЛИ существующий `matches_callback_template` (process_user_input L281) уже умеет — проверь

### 5. Sentinels
- User с 2 guards → Safety Center показывает 2 inline buttons + Back
- Click guard button → guard_modal screen с правильным modal_full
- Back с guard_modal → safety_center

### 6. Latency
Engine patch затронет ALL screens. p95 bench на 5+ screen renders (my_plan, profile_main, menu_v3, safety_center, guard_modal) — verify нет regression.

---

## ⚠️ Risks для B3

1. **render_screen — критический путь.** Patch требует careful surgical edit с rollback plan. Stale-base proof обязателен. Если что-то ломается — affects все экраны.

2. **process_user_input wildcard callback resolution** — нужно verify что matches_callback_template handles `cmd_guard_modal_<family>_<enum>` (template с двумя {var}'ами).

3. **callback_data 64-byte limit** (Telegram). `cmd_guard_modal_maternal_maternal_status_unknown_protective_maintain` = 64 bytes. Tight. May need shorter naming convention (`cmd_gm_<short_id>`).

4. **Multi-RPC compute per render**: business_data_rpc=get_safety_center_data → contains heavy `calculate_user_targets`. + visible_condition has_active_safety_guards calls it again. + (potentially) guard_modal RPC. Может нужна caching (materialized view? or in-request memoization).

---

## ✅ Pre-B3 gates

1. **PR #123 merged** + auto-deploy passed smoke test
2. **3-5 days** owner-locked wait — собрать proxy CTR через journalctl render rate (`grep "safety_center.*render"` / `grep "my_plan.*render"`) и monitor sentry-level errors
3. **No regression tickets** в admin chat 417002669 («где предупреждения», «Темп пропал», и т.п.)
4. **Owner approve** Option A (engine extension) over Option B/C

Если ANY gate fails — диагностировать ДО B3.

---

## 🎯 First action для B3 agent

1. **Verify PR #123 merged** + smoke OK + 3-5 days прошло
2. **Read** этот handover полностью + KB `safety-center-implementation-plan.md` §B3
3. **Owner alignment**: подтвердить Option A путь (engine extension) — это блок-вопрос
4. **Snapshot baseline** render_screen body: `pg_get_functiondef('public.render_screen'::regproc)` → save в `migrations/_baseline_render_screen_pre_b3.sql`
5. **Locate matches_callback_template** + verify wildcard pattern handling
6. **Decide callback naming** (avoid 64-byte limit)
7. **Implement** в multi-migration sequence (engine patch / new screen / RPCs / sentinels)
8. **VPS p95 bench**

---

## Connection — где B3 affects code

- **SQL (heaviest):**
  - `render_screen` engine extension (cascade risk)
  - New `get_guard_modal_data` RPC
  - New `guard_modal` screen + static back button
  - Extended `get_safety_center_data` to include callback per guard
- **Python:** Possibly router.py — wildcard pattern for `cmd_guard_modal_*` (verify if existing matches_callback_template handles)
- **Translations:** modal_full content already exists (mig 258, 269, 270, 267) — no new translations needed beyond per-guard button labels

---

## Related KB

- [safety-center-implementation-plan](../knowledge/concepts/safety-center-implementation-plan.md) §B3 + §3 click_depth
- [safety-guard-ux-pattern](../knowledge/concepts/safety-guard-ux-pattern.md) — 5 touch points, modal_full as touch #4
- [headless-architecture](../knowledge/concepts/headless-architecture.md) — render_screen + business_data_rpc
- [pre-migration-discovery-recipe](../knowledge/concepts/pre-migration-discovery-recipe.md) — stale-base proof для render_screen
- Daily 2026-05-19 sessions 1-4 — full B1-A → B1-B → B2 history

---

## Closing notes от B1-B/B2 agent

После 4 сессий за день (B1-A → B1-B → hotfixes → B2 + decommission) Safety Center готов в проде. Все 3 surfaces показывают pill, click работает, body shows cards. Bug 2 закрыт UX-консистентным правилом (no pace для maintain в любом случае).

B3 — это реальное engine work, не миграция БД. Возможно стоит делать с careful pair-programming session vs solo. Estimated 4-8 часов focused work. Risk medium-high из-за render_screen.

Если B3 пугает — альтернатива: оставить Safety Center as-is (text cards), а **first-trigger modal flow** (mig 264, Tier 1) уже доставляет modal_full при срабатывании guard'а — функционально достаточно для legal/safety. B3 = nice-to-have UX improvement, не critical.

Удачи!
