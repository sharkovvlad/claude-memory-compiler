---
title: "Headless Architecture (Variant C) — Profile v5 Pilot"
aliases: [headless, config-driven-ui, dumb-renderer, process-user-input, ui-screens, phase-2-pilot]
tags: [architecture, headless, config-driven, pilot, phase-2, live]
sources:
  - "daily/2026-04-19.md"
  - "migrations/081-093"
  - ".claude/plans/buzzing-dreaming-brooks.md"
  - "daily/2026-04-25.md"
created: 2026-04-19
updated: 2026-04-29
status: "Phase 3A — progress_main + 4 children DEPLOYED (migrations 129-139); Migration 124 — lang refresh; Migration 142 — Quests headless; 143 — League info; 144 — Shop full headless (buy_freeze + buy_mana + 8 screens); 145 — Ambassador Payout flow (9 screens, FSM, anti-spoofing, balance reservation); 146 — back fallback → stats_main + nav_stack cap=7; 147 — back i-came-from path-walk + advisory_xact_lock + is_inline"
---

# Headless Architecture — Phase 3A Live (Stats + Progress Hub)

Config-driven UI migration: state machine + rendering moved from n8n to PostgreSQL. n8n = Dumb Renderer. Profile v5 — первый pilot (9 screens, sessions 7-9). Phase 3A — Stats Main Screen (Session 11) + Progress Hub (Sessions 13-14).

## Phase 3A — Stats Main (2026-04-23)

### stats_main screen DEPLOYED

- **Migration 122** — `get_stats_business_data` RPC + `stats_main` ui_screen seeded + 3 buttons + `stats.*` translation keys × 13 langs. Wrapper pattern: delegates to existing `get_day_summary` RPC.
- **Migration 123** — `report.*` translation keys gap fix. Legacy n8n JS had strings hardcoded in code nodes, not in `ui_translations`. 195+ inserts (15 report keys + 5 insight keys × 13 langs).
- **n8n: 01_Dispatcher PUT** — Added `reply_button_key='stats'` for all 13 language variants of "Мой день" reply button.
- **n8n: 04_Menu_v3 PUT** — Added `stats` output to Route Action Switch → connected to `render_screen(stats_main)`.

**Latency:** p50=72.7ms, p95=82.3ms ✅

**Critical discovery:** Reply-keyboard and inline callbacks use completely different routing pipelines. Full pattern: [[concepts/reply-keyboard-routing-pattern]].

**Deferred from Phase 3A:** Meal list rendering, `cmd_get_stats` inline routing, 04.2_Edit_StatsDaily decommission.

## Phase 3A — Progress Hub (2026-04-24, Sessions 13-14)

### Progress Hub DEPLOYED (migrations 129-139)

Full migration: `progress_main` + quests + league + friends_info + shop. All 5 screens headless with `cmd_back` → `back_screen_id_default='progress_main'`.

**Key facts:**
- Migration 125: Stats conditional edit button (cmd_edit_last for 1 meal, cmd_show_meals for ≥2). SQL-only fix.
- Migrations 129-139: see full details in [[concepts/progress-hub-headless]]
- Dispatcher PUT (Route Classifier v1.12): first PUT without webhook drift — Session 12 Python Middleware validated
- p95 latency: all 5 screens < 210ms DB render; n8n+Telegram = ~90% of user-perceived latency

### Migrated (28-29.04.2026)

- **Migration 142 (Quests headless)** — quests screen + actions migrated.
- **Migration 143 (League info)** — `cmd_league_info` headless.
- **Migration 144 (Shop full headless)** — `cmd_buy_freeze` + `cmd_buy_mana` + 8 screens (incl. confirm, success, insufficient_coins). Replaces 08.4_Shop legacy callbacks.
- **Migration 145 (Ambassador Payout flow)** — 9 screens, FSM (`payout_status`), anti-spoofing (verify wallet via `payout_method_selected`), balance reservation. `cmd_start_payout`, `cmd_payout_method_*`, `cmd_payout_phone_*`, `cmd_confirm_payout`. Plus `admin_payout_*` regex routing in Dispatcher.
- **Dispatcher PROFILE_V5_CALLBACKS extended (29.04, n8n PUT + Python `dispatcher/router.py`):** added `cmd_league_info`, `cmd_friends_how_it_works`, `cmd_buy_freeze`, `cmd_buy_mana`, `cmd_confirm_buy_freeze`, `cmd_confirm_buy_mana` + 8 payout callbacks. See `daily/2026-04-29.md` "Catch-up commits".

### Not yet migrated → Phase 3B+

- `cmd_premium_plans`, `cmd_profile_subscription` — payment flows (forwards to 10_Payment).
- `share_invite_link` — legacy.
- All picker flows inside Settings / My Plan.

## Current State (2026-04-20, Agent Dossier live)

### Deployed (LIVE)
- **Migrations 081-093** applied ✅
  - 081: `ui_screens` (15 cols) + `ui_screen_buttons` (9 cols) + `workflow_states.screen_id/save_rpc`
  - 082: ~~CANCELLED~~ (render_template → remained in n8n JS per TMA contract)
  - 083: `render_screen(telegram_id, screen_id) → JSONB` (pure)
  - 084: `process_user_input(tg_id, action_type, payload, cb_ctx, skip_debounce) → JSONB` + 3 helpers
  - 085: 13 `get_*_business_data` wrappers
  - 086: INSERT 9 screens + 30 buttons + 6 translation keys × 13 langs + 3 workflow_states wired
  - 087 (v1..v4): Text templates for 6 screens × 13 langs (user iterated 4 versions)
  - 088: `meta.target_screen`/`set_status` for 9 buttons + process_user_input honors set_status
  - 089: **Critical fix** — `v_button.button_id IS NOT NULL` (RECORD IS NOT NULL gotcha)
  - 090: 4 missing button translations (edit_training/phenotype/language/confirm_delete)
  - 091: `get_my_plan_business_data` +`goal_type`; `get_personal_metrics_business_data` real impl (6 fields: weight_kg, height_cm, gender, birth_date, age, target_weight_kg)
  - 092: `process_user_input` cmd_back fix — resets `users.status='registered'` when back from `input_type='text_input'` screen; validates `v_next_screen` against `ui_screens` (fallback via `back_screen_id_default`); DATA: nav_stack cleanup 2 users (legacy 'profile' → 'profile_main')
  - 093: Markdown `**bold**` → HTML `<b>bold</b>` в 5 profile text template keys × 13 langs (соответствует hardcoded `parse_mode: 'HTML'` в Dumb Renderer)
  - 095: Critical RPC hotfixes — hybrid cascade (workflow_states → nav_stack->>-1 → profile_main), SELECT INTO + IF FOUND (RECORD 55000 gotcha), push_nav(v_next_screen), status reset extended (`input_type='text_input' OR save_rpc IS NOT NULL`), CHECK length(callback_data)<=64 на ui_screen_buttons
  - 096: Defensive guard — existence check nav_stack top against ui_screens; repeat nav_stack data cleanup (legacy 'profile' → 'profile_main')
  - 097: `render_strategy` override to `delete_and_send_new` when `p_action_type='text'` or cb_ctx empty (BUG 1 root cause fix)
  - 098: `success_reaction='👌'` emitted in `telegram_ui` when text save succeeds
  - 100: `get_profile_business_data` расширен до 33 полей (26 existing + 7 новых: `sage_tier`, `limit_variant`, `sage_quote_index`, `sage_quote_text`, `member_since_month`, `member_since_year`, `subscription_status_display`); calendar/units translations × 13 langs добавлены в `ui_translations`
  - 101: Universal template `profile.main_text` × 13 langs (Agent Dossier layout с nested placeholder syntax `{{goal_{goal_type}}}`, `{{sage_{sage_tier}}}` etc.); вся верстка Profile Main Screen перенесена в БД

- **n8n workflows:**
  - `04_Menu_v3` (ID `ju0h4WStPZX54EfR` cloud / `0xJXA5M4wQUSiGXT` self-hosted после миграции 27.04, 19 nodes, `callerPolicy='any'`) — Dumb Renderer
  - `01_Dispatcher` versionId `d4f62a3e` — patched Route Classifier + Main Router + Prepare for 04_v3 + Go to 04_Menu_v3 (self-hosted ID `7jVRdAvVlzOqIMEi`)
  - `04_Menu_v3` updated: 15 → 19 nodes (Session 8):
    - Switch Render Strategy: `mode="rules"` → `mode="expression"` (fixes n8n cache routing bug where delete_and_send_new routed to output 0)
    - Early Answer Callback Query (parallel from Extract Payload, not after RPC)
    - Set Message Reaction: parallel branch, `setMessageReaction` with `👌` on user message_id
    - Save Bot Message: fire-and-forget after sendMessage
    - HTTP sendChatAction typing indicator: parallel fire-and-forget from Extract Payload
  - `04_Menu_v3` (Session 9 PUT) — Dumb Renderer JS расширен: 3-pass multi-pass interpolation (`{var}`, `{{const}}`, `{tr:path}`, nested braces до iter < 5); helper-поля `sage_tier`/`limit_variant` обрабатываются как обычные `{var}` — group mapping решён на SQL стороне
  - `01_Dispatcher` (Session 9 PUT) — Phase 5: reply text "Профиль" (и переводы icon_profile × 13 langs) теперь роутится в `menu_v3` (Headless v3), не в legacy 04_Menu; Готча решена: guard проверяет main-menu labels ДО routing в v3, чтобы не захватить "Мой день" / "Прогресс"

- **Routing (Profile v5 callbacks → 04_Menu_v3):**
  - `cmd_get_profile`, `cmd_my_plan`, `cmd_settings`, `cmd_personal_metrics`, `cmd_help`
  - `cmd_update_weight`, `cmd_edit_weight/age/height`, `cmd_delete_account`, `cmd_confirm_delete`
  - `cmd_back` when status IN (edit_weight, edit_age, edit_height)
  - **text input** when status IN (edit_weight, edit_age, edit_height) **AND message is NOT main-menu reply button**

### Latency Benchmarks (Phase 2 Pilot, 10 runs, psycopg2 direct)

| RPC call | p50 (ms) | p95 (ms) | Статус |
|----------|----------|----------|--------|
| `render_screen(profile_main)` | 80 | 98 | ✅ |
| `render_screen(my_plan)` | 80 | 570 | ⚠️ outlier (1/10), 9 остальных < 100ms |
| `render_screen(personal_metrics)` | 80 | 216 | ✅ |
| `render_screen(settings)` | 95 | 183 | ✅ |
| `process_user_input(cmd_my_plan)` | 80 | 174 | ✅ |

Все под порогом 1s — **Plan B caching не нужен**. E2E добавит ~300-500ms (n8n + Telegram). `my_plan` на watchlist: если p95 outlier повторится в продовых замерах → materialized view для `calculate_user_targets`.

### Not yet migrated (legacy 04_Menu handles)
- `cmd_get_stats` (Мой день), `cmd_progress` — reply-keyboard buttons
- `cmd_profile_subscription` → forwards to 10_Payment (works через legacy)
- `cmd_edit_lang/country/timezone/notifications` (inside Settings screen)
- `cmd_edit_goal/activity/training/phenotype/gender` (inside My Plan screen)
- Game Hub (progress/quests/league/friends/shop) — Phase 3A

## Key Design Decisions

### 1. TMA-ready contract: `{business_data, telegram_ui}` split
- **Business data RPCs** (`get_*_business_data`) return clean domain data — TMA consumes directly
- **`render_screen`** adds `telegram_ui` block (text_key, keyboard, render_strategy) — только n8n consumes
- n8n Dumb Renderer does **final interpolation** of `{placeholder}` → business_data values
- Template Engine stays in n8n JS (decision after external ИИ #2 review — Postgres slower for string ops + TMA doesn't need pre-rendered text)

### 2. Render strategies
- `replace_existing` → editMessageText (inline callbacks)
- `delete_and_send_new` → deleteMessage old + sendMessage new (terminal like delete_account)
- `send_new` → sendMessage (onboarding, errors)

### Migration 124 — Language refresh extension (2026-04-25)

When `save_rpc = 'set_user_language'`, `process_user_input` now performs a fresh SELECT of `v_user_context` after the save and includes three extra fields in the response:

```json
{
  "translations_override": { ... full translations for new language ... },
  "reply_keyboard_refresh": true,
  "language_code_new": "en"
}
```

**Why needed:** The Dispatcher's `translations` payload is a snapshot taken before the language change. Without `translations_override`, the rendered screen after language selection would use the old language.

**Dumb Renderer contract:** `const translations = data.translations_override || trigger.translations || {}`. When `reply_keyboard_refresh === true`, Dumb Renderer prepends a `sendMessage` item with a new reply keyboard built from the fresh translations.

Full details: [[concepts/language-switch-headless-ux]].

### 3. 5 output shapes of `process_user_input`
```json
{status: 'render', screen_id, business_data, telegram_ui, meta}
{status: 'forward', forward_to, payload}  // photo/voice→03_AI_Engine, payment→10_Payment
{status: 'debounced', cooldown_remaining_ms}
{status: 'validation_error', error_key, retry_screen_id}
{status: 'error', error_code, details}
```

## ⚠️ Critical Gotchas (lessons learned during deployment)

### Gotcha 1: PL/pgSQL `RECORD IS NOT NULL` requires ALL fields non-null

**Symptom:** `IF v_button IS NOT NULL THEN ... END IF;` block skipped even when loop matched a row.

**Cause:** PostgreSQL composite-type semantics: `record IS NULL` = all fields NULL, `record IS NOT NULL` = all fields non-null. `ui_screen_buttons` has nullable columns (`visible_condition`, `icon_const_key`) → matched row can have `v_button.visible_condition = NULL` → `v_button IS NOT NULL` returns **FALSE**.

**Fix (Migration 089):** Use PK-based check: `IF v_button.button_id IS NOT NULL THEN` (PK is always non-null when row assigned).

**Where to check:** all `FOR record IN SELECT ... LOOP` patterns where following `IF rec IS NOT NULL`. Safer pattern — use a dedicated `v_found BOOLEAN` flag.

### Gotcha 2: Extract Payload must read Dispatcher field names

**Symptom:** `process_user_input` returns `missing_callback_data` error.

**Cause:** `Dispatcher.Prepare for 04_v3` (copy of legacy `Prepare for 04`) puts callback string into `command`/`_cb_data`/`callback_query` (as string). Subagent-generated Extract Payload code read `$json.callback_data` → always empty.

**Fix:** read priority `d.command || d._cb_data || d.callback_query` (string form or object.data).

### Gotcha 3: Main Router connections — insert rule requires shifting `connections.main[]`

**Symptom:** After inserting 'menu_v3' rule at index 2 of Main Router, all downstream routes (onboarding/ai/location/pre_checkout/...) pointed to wrong nodes → onboarding broken for new users.

**Cause:** When inserting a Switch rule at position N, you MUST shift all `connections.main[N..]` entries by +1. Simply `connections.main[N] = new_target` overwrites existing rules' target.

**Fix pattern:**
```python
# REBUILD connections from scratch — map each rule.outputKey → correct target node
correct_mapping = {'error': 'Get Translations (Error)', 'menu': 'Prepare for  04', ...}
new_main = [[{"node": correct_mapping[r['outputKey']], "type": "main", "index": 0}] for r in rules]
```

### Gotcha 4: `meta.target_screen` mandatory for inline buttons

**Symptom:** Every inline button re-renders current screen → Telegram "Bad Request: message is not modified".

**Cause:** `process_user_input` resolves `v_next_screen := COALESCE(button.meta->>'target_screen', screen.next_on_submit, current_screen)`. If both NULL, fallback is current_screen (re-render).

**Fix (Migration 088):** populate `ui_screen_buttons.meta` = `{"target_screen": "...", "set_status": "..."}` for every navigating button.

### Gotcha 5: Stuck in edit_* status blocks reply-keyboard buttons

**Symptom:** After cancel from ask_weight, user stuck in `status='edit_weight'`. Clicking "Профиль" reply-button sends text "Профиль" → Route Classifier sees `PROFILE_V5_STATUSES.has(status)` → routes to menu_v3 → save_rpc='set_user_weight' fails validation → message_id 404.

**Fix (Dispatcher Route Classifier patch):**
```javascript
if (!callback && message && PROFILE_V5_STATUSES.has(user.status)) {
    // Guard: main-menu reply-keyboard labels must bypass
    const mainBtnTexts = [...t.buttons.{stats|progress|profile|add_food}, hardcoded fallbacks];
    const isMainBtn = mainBtnTexts.some(b => msgText.includes(b));
    if (!isMainBtn) {
        return { route_target: 'menu_v3', ...};
    }
    // else: fall through to isMenuButton check (legacy)
}
```

**FIXED in migration 092:** `process_user_input` теперь при cmd_back из `input_type='text_input'` экрана делает `UPDATE users SET status='registered'`. Также добавлена валидация `v_next_screen` против таблицы `ui_screens` с fallback через `back_screen_id_default`.

### Gotcha 6: Native URL inline buttons via `meta.url` (миграция 176, 2026-05-05)

**Problem:** Кнопка `cmd_open_support_url` была DEAD (5+ сек таймаут, найден E2E-краулером 04.05). `meta = {}`, callback не в top-level nav whitelist, нет специального хендлера. URL поддержки orphan'но висел в `ui_translations.profile.support_url` (мигр. 069) — никем не читался.

**Принцип:** для внешних ссылок (поддержка, доки, соцсети, Web App) headless-движок поддерживает Telegram URL inline buttons через `ui_screen_buttons.meta.url`. Никаких routing-таблиц / спецхендлеров не нужно: Telegram-клиент открывает URL сам, callback_query на бот не приходит.

**Контракт:**
1. `ui_screen_buttons.meta.url` — абсолютный URL с протоколом (`https://`, `tg://`, `mailto:`).
2. `render_screen` (мигр. 176) эмитит поле `'url', v_button.meta->>'url'` в каждом keyboard-объекте (NULL если нет meta.url).
3. `services/template_engine.py:_build_inline_keyboard` — если `btn.get('url')` непустая строка → отдаёт `{text, url}` Telegram'у; иначе `{text, callback_data}`.
4. Telegram InlineKeyboardButton требует РОВНО ОДИН из `{url, callback_data, web_app, login_url, ...}` — в финальном payload эмитим только одно из двух.

**НЕ смешивать `meta.url` и `meta.target_screen` в одной кнопке** — `url` выигрывает в template_engine, `target_screen` будет проигнорирован (и пользователь никогда не пройдёт на target screen потому что callback не отстреливается). Если нужно и URL и переход — это два разных UI-кейса.

**Watchlist для агентов:** при добавлении URL-кнопок — только запись в `ui_screen_buttons.meta.url`, никаких изменений Python/RPC.

## Missing Functionality (Phase 2 scope gaps → TODO)

| Issue | Screen affected | Priority | Fix |
|-------|-----------------|----------|-----|
| ~~`cmd_back` in ask_* doesn't reset status~~ | ask_weight/age/height | ✅ **FIXED** migration 092 | `process_user_input`: cmd_back из `input_type='text_input'` → `UPDATE users SET status='registered'`; валидация target vs ui_screens с fallback |
| ~~Text input save shows no confirmation~~ | ask_weight/age/height | ✅ **FIXED** Session 8 (migrations 097-098 + 04_Menu_v3 PUT) | reaction 👌 + delete prompt + render updated screen |
| `cmd_profile_subscription` → still legacy | profile_main | Low | Phase 3 |
| `cmd_edit_lang/country/timezone/notifications` (in Settings) | settings | Medium | Phase 3 (these are sub-picker flows) |
| `cmd_edit_goal/activity/training/phenotype/gender` (in My Plan) | my_plan | Medium | Phase 3 |
| Reply-kb label detection uses hardcoded fallbacks | Route Classifier | Low | Read from translations[lang].buttons.* proper |

## Debug Workflow (for future agents)

1. **Check user.status** first: `SELECT status, last_active_at FROM users WHERE telegram_id=X`
2. **If stuck in edit_*:** `UPDATE users SET status='registered' WHERE telegram_id=X` — unstick
3. **Recent executions** (self-hosted с 27.04 — через SSH к VPS):
   ```bash
   # 04_Menu_v3 (self-hosted ID 0xJXA5M4wQUSiGXT)
   ssh root@89.167.86.20 'curl -H "X-N8N-API-KEY: $N8N_TARGET_API_KEY" "http://127.0.0.1:5678/api/v1/executions?workflowId=0xJXA5M4wQUSiGXT&limit=10"'
   # 01_Dispatcher (self-hosted ID 7jVRdAvVlzOqIMEi)
   ssh root@89.167.86.20 'curl -H "X-N8N-API-KEY: $N8N_TARGET_API_KEY" "http://127.0.0.1:5678/api/v1/executions?workflowId=7jVRdAvVlzOqIMEi&limit=10"'
   ```
   На VPS `N8N_TARGET_API_KEY` — в `/home/noms/n8n/compose/.env`. Локальная подкачка через SSH-туннель: `ssh -L 5678:127.0.0.1:5678 root@89.167.86.20`.
4. **Error details:** `executions/{id}?includeData=true` → `data.resultData.error`
5. **Direct RPC test:**
   ```sql
   UPDATE users SET status='registered' WHERE telegram_id=417002669;
   SELECT public.process_user_input(417002669, 'callback',
       '{"callback_data":"cmd_my_plan"}'::jsonb, '{}'::jsonb, TRUE);
   -- Expected: {status:render, screen_id:my_plan, ...}
   ```

## Открытые вопросы (после Sessions 7-9, 2026-04-20)

1. ~~**Reply-click "Профиль" (text) → legacy 04_Menu**~~ — **✅ RESOLVED Session 9.** Dispatcher Phase 5 PUT: reply "Профиль" (и locale-переводы) теперь идёт в menu_v3. Agent Dossier live-verified на premium user — отображает корректно.

2. **`parse_mode` contract** — Dumb Renderer hardcodes `parse_mode: 'HTML'`. Migration 093 converted Profile keys. Phase 3A: add `parse_mode` as field in `ui_screens` OR fix all keys at add-time.

3. **my_plan p95 outlier** — 570ms on psycopg2 benchmark (1/10 runs). Not reproduced in Session 7 live smoke. Watchlist: if prod outliers repeat → materialized view for `calculate_user_targets`.

4. **Save Bot Message coverage** — noda exists in 04_Menu_v3 but only fires after `sendMessage` branch. editMessageText path not covered. If One Menu tracking needed for edit path → add branch.

5. **04_Menu_v4 rebuild (optional)** — v3 = 19 nodes (tech debt from 5 sessions). v4 blueprint (9 nodes) in `.claude/plans/elegant-swimming-boot.md`. Not priority.

## File references

| File | Purpose |
|------|---------|
| `migrations/081_ui_screens_tables.sql` | Schema foundation |
| `migrations/083_render_screen_rpc.sql` | Pure render function |
| `migrations/084_process_user_input_rpc.sql` | Entry point + helpers |
| `migrations/085_business_data_rpcs.sql` | 13 wrappers |
| `migrations/086_ui_screens_profile_pilot.sql` | 9 screens + 30 buttons |
| `migrations/087_ui_screens_profile_v4_final.sql` | Text templates (user's final version) |
| `migrations/088_fix_inline_button_routing.sql` | meta.target_screen + set_status |
| `migrations/089_fix_record_is_null_gotcha.sql` | button_id IS NOT NULL fix |
| `migrations/090_missing_button_translations.sql` | 4 missing button keys |
| `migrations/091_profile_pilot_business_data_fixes.sql` | goal_type в my_plan + personal_metrics real impl |
| `migrations/092_process_user_input_back_fixes.sql` | cmd_back status reset + nav_stack validation + data cleanup |
| `migrations/093_profile_markdown_to_html.sql` | Markdown → HTML в 5 profile text template keys × 13 langs |
| `migrations/095_hotfix_routing_and_records.sql` | Hybrid cascade + RECORD gotcha fix + push_nav semantics + status reset + CHECK 64 |
| `migrations/096_rpc_validate_screen_exists.sql` | Defensive screen existence guard + nav_stack data cleanup |
| `migrations/097_rpc_override_strategy_for_text.sql` | render_strategy override for text input (BUG 1 fix) |
| `migrations/098_rpc_success_reaction.sql` | success_reaction='👌' emission on text save |
| `migrations/100_profile_business_data_extended.sql` | get_profile_business_data 26→33 fields + calendar/units translations |
| `migrations/101_profile_main_text_template.sql` | profile.main_text universal template × 13 langs (Agent Dossier layout) |
| `claude-memory-compiler/knowledge/concepts/ui-inventory.md` | Full 85 callbacks catalog |
| `.claude/plans/buzzing-dreaming-brooks.md` | Full approved plan |

## Related

- [[concepts/ui-inventory]] — 85 callbacks, 26 workflow_states, screen hierarchy
- [[concepts/phenotype-quiz]] — will auto-unfreeze in Phase 3B
- [[concepts/n8n-switch-duplicate-outputkey-bug]] — original driver of this migration
- [[concepts/nav-stack-architecture]] — reused as-is
- [[concepts/n8n-template-engine]] — stays in JS (TMA architectural decision)

---

## Update 2026-05-13 (UAT edit-meal series) — Virtual Screens + url_template

Два расширения headless-контракта закреплены тимлидом + Архитектором по итогам UAT 13.05 (5 PR'ов #61-#65).

### Virtual Screens (`_<name>` namespace) + PUI lookup fallback chain

**Когда:** inline-кнопка показывается **из standalone-сообщения** (не из конкретного screen в headless tree). Пример — карточка лога еды от 03_AI_Engine `sendMessage` с inline_keyboard содержит `cmd_edit_last` / `cmd_delete_last`. Юзер может быть на любом current_screen (Банда, Прогресс, Профиль…) когда кликает.

**Проблема:** стандартный PUI lookup `SELECT b.* FROM ui_screen_buttons WHERE screen_id=v_current_screen` промазывает → fallthrough → re-render «текущего» экрана (то что юзер видит — не related screen).

**Решение (mig 211 Option B, отвергнут НЛМ-совет forward_to_n8n):**

1. **INSERT virtual screen** с `_<name>` prefix. Convention `_<name>` зарезервирована под lookup-only utility. Mig 211 ввёл первый — `_global_floating_actions`:
   ```sql
   INSERT INTO ui_screens (screen_id, text_key, render_strategy, input_type, ...)
   VALUES ('_global_floating_actions', NULL, 'noop', 'inline_kb', ...);
   ```
   `render_strategy='noop'` гарантирует — если кто-то вызовет render_screen на этом screen_id, вернётся пустой UI (safe degradation, не падение).

2. **ALTER CONSTRAINT** `ui_screens_screen_id_check` regex `^[a-z][a-z0-9_:]{1,62}$` → `^[a-z_][a-z0-9_:]{1,62}$` чтобы поддержать underscore prefix. Lowercase letter ⊂ `[a-z_]`, existing rows pass.

3. **PUI lookup fallback chain** (mig 211 patch в `process_user_input`):
   ```sql
   SELECT b.* INTO v_button FROM ui_screen_buttons b
    WHERE b.screen_id = v_current_screen
      AND matches_callback_template(b.callback_data, v_callback);
   
   IF NOT FOUND THEN
       SELECT b.* INTO v_button FROM ui_screen_buttons b
        WHERE b.screen_id = '_global_floating_actions'
          AND matches_callback_template(b.callback_data, v_callback);
   END IF;
   ```
   Остальная логика (save_via_callback, target_screen, clear_status, error_screen_map) переиспользуется без изменений.

4. **Кнопки в virtual screen** получают standard `meta` keys:
   ```sql
   INSERT INTO ui_screen_buttons (screen_id, ..., meta) VALUES (
     '_global_floating_actions', ..., jsonb_build_object(
       'save_via_callback', true,
       'save_rpc', 'set_editing_last_meal',
       'target_screen', 'edit_food_prompt'
     )
   );
   ```

**Anti-pattern (отвергнут):** `meta.action` универсальный dispatcher с CASE-блоками в PUI — тимлид охарактеризовал как «архитектурная мина» (хардкод спам, рост surface area по мере добавления callbacks). Virtual screens переиспользуют existing `save_via_callback` контракт (40+ кнопок уже работают по этой схеме).

### `meta.url_template` — динамические URL-кнопки

Расширение existing `meta.url` (mig 176) на template-name'ы которые Python резолвит через `services/template_engine._URL_TEMPLATE_RESOLVERS`. Используется когда URL зависит от user-state (telegram_id, language, etc) или содержит non-ASCII (кириллица в `text` параметре share-ссылок).

**Зачем не SQL:** percent-encoding кириллицы + спецсимволов в БД-side небезопасно. `urllib.parse.quote` в Python — стандарт.

**Запись в БД** (mig 209):
```sql
UPDATE ui_screen_buttons
   SET meta = jsonb_build_object('url_template', 'share_invite')
 WHERE callback_data='share_invite_link';
```

**Резолвер в Python** (`services/template_engine.py`):
```python
_URL_TEMPLATE_RESOLVERS = {
    "share_invite": _resolve_share_invite_url,
}

def _resolve_share_invite_url(telegram_id, translations, constants):
    bot = constants.get("bot_username", "").lstrip("@")
    deep_link = f"https://t.me/{bot}?start=ref_{telegram_id}"
    share_text = translations.get("referral", {}).get("share_text", "")
    return ("https://t.me/share/url?url=" + quote(deep_link, safe="")
            + "&text=" + quote(share_text, safe=""))
```

**Расширение `render_screen`** — добавить `'url_template', v_button.meta->>'url_template'` в keyboard JSON рядом с `'url', v_button.meta->>'url'` (mig 209 Block E, см. baseline `_baseline_render_screen_2026-05-13_post_mig209.sql`).

**Расширение `_build_inline_keyboard`** — приоритет `url > url_template > callback_data`. Если url_template есть но resolver вернул None — **дроп кнопки** (broken share-кнопка без URL бесполезна), НЕ fallback на callback.

Добавление нового template: одна функция в `_URL_TEMPLATE_RESOLVERS` dict + UPDATE meta нужной кнопки. Без правок render_screen / PUI.
