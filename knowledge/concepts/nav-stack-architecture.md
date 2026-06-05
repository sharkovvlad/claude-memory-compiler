---
title: "Nav Stack — Иерархическая навигация Назад (Bug 6)"
aliases: [nav-stack, hierarchical-back, cmd-back, push-nav, pop-nav, back-nav, reset-nav-to, bug-6, i-came-from]
tags: [n8n, architecture, navigation, ux, migrations, refactor]
sources:
  - "daily/2026-04-17.md"
  - "daily/2026-04-22.md"
  - "daily/2026-04-27.md"
  - "daily/2026-04-29.md"
created: 2026-04-17
updated: 2026-04-29
---

# Nav Stack — Иерархическая навигация Назад (Bug 6)

> ⚠️ **status: stale (2026-06-05)** — n8n-эра, >30д без активности в daily/handover; многое мигрировало в Python. Перепроверь против прода перед использованием.

Архитектурный рефакторинг навигации "Назад" в боте NOMS. Вместо хардкодированных callback'ов (`cmd_back_to_progress`, `cmd_get_profile`) введён универсальный `cmd_back` + JSONB-стек `users.nav_stack` с 4 RPCs. Реализовано за 8 фаз + R1 fix, затронуто 5 workflows, 26 кнопок мигрировано, 13 Push Nav HTTP нод добавлено.

## Key Points

- **3 базовые миграции (076–078):** `users.nav_stack JSONB DEFAULT '[]'::jsonb` + 6 RPCs: `push_nav` (дедуп + cap), `pop_nav`, `peek_nav`, `clear_nav`, `back_nav` (атомарный pop+peek), `reset_nav_to` (clear+push для top-level)
- **Migration 146 (29.04):** `push_nav` cap 10→7, `back_nav` absolute fallback → `stats_main` (было `profile_main`), RAISE WARNING при каждом срабатывании fallback для observability
- **Migration 147 (29.04) — I-came-from path-walk:** `push_nav` truncate-on-existing (дубли в стеке невозможны), `process_user_input` input-source-aware через `is_inline` в `p_cb_context` (Reply KB wipe vs Inline push), Priority 1/2 инвертированы (сначала stack pop, потом tree fallback), `pg_advisory_xact_lock` для защиты от concurrent agents
- **Семантика (после 147):** Reply KB → wipe stack (юзер «пришёл домой»); Inline KB → push destination (I-came-from history до 7 уровней); `cmd_back` → Priority 1 stack pop → Priority 2 `back_screen_id_default` → Priority 3 `stats_main` absolute root
- **Push Nav (*)** ноды всегда fire-and-forget **параллельно с Build * Text** (до HTTP Request). Если подключить после HTTP Request — `$json` уже clobbered, `menu_route` = undefined (n8n Data Flow Rule #1)

## Details

### Миграции 076–078

**Migration 076 — `users.nav_stack` + 4 базовых RPC:**

```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS nav_stack JSONB DEFAULT '[]'::jsonb;

-- push_nav: дедуп (top == screen → no-op) + cap 10 элементов
-- pop_nav: снимает верхний элемент, возвращает его
-- peek_nav: читает верхний элемент без удаления
-- clear_nav: очищает стек полностью
```

`push_nav` с дедупом — если top стека уже равен `p_screen`, повторный push не происходит. Cap 10 элементов защищает от утечки памяти при навигационных циклах.

**Migration 077 — `back_nav(p_telegram_id)` helper:**

Атомарный RPC: pop текущий screen + peek parent за одно обращение к БД. Возвращает `{popped, parent, stack}`. Упрощает n8n flow: вместо 2 последовательных HTTP запросов (pop + peek) — один.

**Migration 078 — `reset_nav_to(p_telegram_id, p_screen)`:**

Атомарно очищает стек + пушит один screen. Используется при нажатии reply-кнопок (Profile/Stats/Progress). Обосновано One-Menu правилом: reply-button клик удаляет старое меню через deleteMessage → inline-кнопки старого top-level мертвы → стек от него бесполезен.

### Phase 0+1+1.5: Infrastructure + Profile↔Settings POC + top-level reset

**04_Menu (109→116 нод):**
- **Back Nav** (HTTP POST rpc/back_nav) — заменяет legacy Menu Router[0] → Send Main Menu (Back)
- **Route After Back** (Code) — читает `{parent}` из RPC, sets `$json.menu_route = parent || 'profile'` (fallback)
- **Back Target Router** (Switch): profile → Build Profile Text; default → Send Main Menu (Back)
- **Reset Nav (Profile/Stats/Progress)** — 3 fire-and-forget ноды параллельно Edit/Send render. Вызывают `reset_nav_to`
- **Push Nav (Sub-Screen)** — dynamic `p_screen: $json.menu_route` для settings/my_plan/personal_metrics/help
- **Settings Back**: `cmd_get_profile` → `cmd_back` (первая миграция на универсальный Back)

**3 top-level screens (reply-buttons):** `profile`, `stats`, `progress`. Распознаются в Dispatcher Route Classifier через `isMenuButton`. `add_food` — действие AI parse, не меню. Shop/Friends/League/Quests — inline внутри Progress, не reply-buttons.

### Phase 2: Edit pickers + edit_phenotype dead-end fix

**04_Menu (116→117 нод):**
- Build Ask Markup: 8 мест `'cmd_back_to_profile'` → `'cmd_back'` (9 edit pickers + default)
- **Push Nav (Ask)** — dynamic `p_screen: $json.edit_type` (edit_weight/edit_speed/edit_phenotype/...)
- Back Target Router: +1 OR rule `sub_screen` — `parent ∈ {my_plan, personal_metrics, settings, help}` → Build Profile Sub-Screen

**Bug в Phase 2.5:** Push Nav (Sub-Screen) был подключён к `Edit Sub-Screen (Inline)[0]` — **после** HTTP Request, `$json.menu_route` = undefined → no-op. Fix: переподключение на `Build Profile Sub-Screen[0]` (параллельно, до HTTP). Урок: Push Nav (*) должен идти параллельно с **Build * Text**, НЕ с Edit/Send.

**edit_phenotype dead-end fix:** ранее из `status='edit_phenotype'` невозможно было выйти кнопками. Теперь Back из Phenotype screen работает через `cmd_back` → back_nav → parent=my_plan → Build Profile Sub-Screen.

### Phase 3: Location (Country/Timezone)

**02.1_Location (44→46 нод):**
- Build Country UI / Build Timezone UI: `'cmd_settings'` → `'cmd_back'`
- **+ Push Nav (Country/Timezone)** — fire-and-forget параллельно к Build *UI

**Hotfix paired items:** Push Nav (Country) возвращал `{error: "Paired item data unavailable..."}`. Выражение `$('Executed 05').item.json.telegram_id` не резолвилось через Postgres RPC chain (правило 9 CLAUDE.md). Fix: использовать `$json.chat_id` вместо paired-items lookup (private chats: chat_id ≡ telegram_id).

**Emoji fix:** Build Country UI не имел иконки на Back-кнопке. Добавлен `icon_back` из `app_constants` с fallback '🔙'.

### Phase 3.5: Level-4 Back (edit_speed → edit_goal)

**Проблема:** Speed Confirmation → Back → уходил в Профиль (fallback). `back_parent ∈ edit_*` не имел rule в Back Target Router.

**04_Menu (117→118 нод):**
- **Build Edit Context from Back** (new Code) — маппит `back_parent` → `status`, `command`, `edit_type`. Passthrough остальных полей Merge Data
- **Back Target Router** +Rule[2] `edit_picker` с OR над 9 edit_* screens → Build Edit Context from Back → Set User Status → Build Edit Question → Edit Type Router → Build Ask Markup

**Build Speed Confirmation hotfix:** Back callback `'cmd_get_profile'` → `'cmd_back'` (был упущен в Phase 2 — отдельный render-путь).

### D5: Unified save confirmation + push_nav для 02_Onboarding_v3

**Проблема:** Speed picker Back callback в Response Builder = `cmd_back_to_profile` (legacy), и `edit_speed` никогда не пушился в стек (рендерится в v3, не в 04_Menu где есть Push Nav).

**02_Onboarding_v3 (15→17 нод):**
- **`backInlineKB()` helper** — inline keyboard с `🔙 Назад` / `cmd_back` вместо `mainMenuKB()` (reply keyboard)
- Speed picker Back: `cmd_back_to_profile` → `cmd_back` + `payload._push_nav_screen = 'edit_speed'`
- Activity/Training/Goal save confirmations: `mainMenuKB()` → `backInlineKB()` — одно сообщение с выбранным значением + inline Back
- **Has _push_nav_screen?** (IF) + **Push Nav (v3)** (HTTP) — fire-and-forget, запускается только когда `_push_nav_screen` задан

**Hotfix activity_key:** set_user_activity RPC возвращает `activity_key` (не `activity_level`). Response Builder проверял `rpc?.activity_level` → false → fallback. Исправлено на `activity_key`.

### Phase 4: Language v3 — return to Settings после save

**UX change:** после выбора нового языка → Settings screen с обновлённым langName (вместо "Готово! Язык обновлён" + main menu). Best practice iOS/Android.

**02_Onboarding_v3 After-Lang Builder:**
- Branch `returnStatus === 'registered'`: Settings payload с `langName` через `Intl.DisplayNames([newLang])`, `countryName` через `Intl.DisplayNames([newLang], {type: 'region'})`. Inline keyboard Settings. Confirmation header `"✅ Language updated: Español"` из `freshT.messages.language_changed`
- Branch `isBack === true`: без header (ничего не меняли)

**Stale Language keyboard fix:** reply keyboard Language picker'а не убирается при переходе на Settings (inline + remove_keyboard нельзя в одном сообщении). Fix: After-Lang Builder отправляет **2 payloads**: 1) dismiss msg с `remove_keyboard: true` + confirmation text, 2) Settings screen с inline keyboard.

Push_nav('language_picker') **НЕ добавлен**: Language picker использует reply keyboard с изолированным Back через `isBack` ветку Onboarding Engine (не через 04_Menu hub).

### Phase 5: Payment — убирает subscription_source hack

**10_Payment (34→35 нод):**
- Build Plans Text: 2× Back callback → `cmd_back` (был `subscription_source === 'profile' ? 'cmd_get_profile' : 'cmd_back_to_progress'`)
- **+ Push Nav (Plans)** — `p_screen='premium_plans'` параллельно Build Plans Text

**04_Menu:**
- Back Target Router +Rule[3] `progress` → RPC Progress Insight (entry point Progress render pipeline)

**Pre-existing bug fix:** 4 ноды Get *Price использовали `JSON.stringify({...})` в jsonBody → n8n double-serialization → Supabase 404 "без параметров" для free юзеров. Fix: plain object `{...}` без JSON.stringify. Также Get All Prices читал `$json.telegram_id` от пустого Extract Sub output → fix: `$('Merge Data').item.json.telegram_id`.

### Phase 6: Shop/Friends/League/Quests

**04_Menu (118→123 нод):**
- 8 occurrences `cmd_back_to_progress` → `cmd_back` в 7 нодах (Shop, Friends, Quests, League, Freeze Result, Mana Result, Coming Soon)
- 5 новых Push Nav HTTP нод: Shop, Friends, Quests, League, Friends Info
- Back Target Router +Rule[4] `shop` → Build Shop Text (для Progress → Shop → Premium → Back → Shop)

### Phase 7: 08.4_Shop standalone

3 замены `cmd_back_to_progress` → `cmd_back` в standalone workflow 08.4_Shop.

### Phase 8: Cleanup deprecated callbacks

3 замены legacy Back callbacks в Build Profile Sub-Screen: `my_plan/personal_metrics/help` → `cmd_back`.

### R1: Newcomer Language Back → Welcome

`status='new'` юзер → Language picker → Back → Welcome screen (не Settings). Return Path Router +Rule[0] `status='new' && isBack=true` → 02_Onboarding (welcome screen).

### Canonical screen_names

```
profile, stats, progress, my_plan, settings, personal_metrics, help,
shop, friends, league, quests, friends_info,
premium_plans, payment_method, crypto_instructions,
language_picker, country_picker, timezone_picker,
edit_weight, edit_height, edit_age, edit_gender, edit_activity,
edit_goal, edit_training, edit_speed, edit_phenotype,
speed_confirm, edit_stats_daily, meal_detail
```

### Паттерн для других агентов

- **Новый top-level?** → Reset Nav (Name) + `p_screen='name'` + connect parallel к Edit/Send render
- **Новый sub-screen?** → Push Nav (Sub-Screen) может быть переиспользован с dynamic `$json.menu_route`, или создать статический Push Nav (X)
- **Новый Back button?** → `callback_data: 'cmd_back'` (универсальный). Menu Router[0] уже подключён к Back Nav → Route After Back → Back Target Router
- **Каждый новый screen** → добавить output в Back Target Router (rule `parent=='screen_name'` → render_node)
- **Push Nav должен идти параллельно с Build * Text**, НЕ с Edit/Send (Data Flow Rule #1)
- **`p_telegram_id` в Push Nav** — брать из `$json.chat_id` или `$('Merge Data').item.json.telegram_id`, НЕ из paired-items lookup к предку через IF/Postgres

### Back Target Router — финальная карта

| Rule | parent value | Output | → Render node |
|------|-------------|--------|--------------|
| [0] | `profile` | profile | Build Profile Text |
| [1] | `settings\|my_plan\|personal_metrics\|help` | sub_screen | Build Profile Sub-Screen |
| [2] | `edit_*` (9 screens) | edit_picker | Build Edit Context from Back → Set User Status → Build Ask Markup |
| [3] | `progress` | progress | RPC Progress Insight pipeline |
| [4] | `shop` | shop | Build Shop Text |
| [5] | fallback | — | Send Main Menu (Back) |

### Migration 121 — back_nav anchor fallback (2026-04-22)

**Проблема:** после `meta.clear_status=true` (например, `cmd_lang_ru` на `edit_lang`) `users.status='registered'` и `nav_stack=[]`. В этом состоянии `back_nav` возвращал `parent=NULL` → UI "зависал" без навигации назад.

**Цепочка до фикса:**
1. Пользователь нажимает picker option (`cmd_lang_ru` на экране `edit_lang`)
2. `clear_status=true` → `users.status='registered'`, `nav_stack=[]`
3. Пользователь нажимает `cmd_back`
4. `v_current_screen` резолвится из `workflow_states[status='registered']` → `screen_id=NULL`
5. `nav_stack=[]` → нет pop
6. `back_screen_id_default=NULL` для `profile_main`
7. `back_nav` возвращает `{parent: NULL}` → caller не знает куда идти

**Новая сигнатура (migration 121):**

```sql
back_nav(p_telegram_id bigint, p_current_screen text DEFAULT NULL) RETURNS jsonb
```

Добавлен необязательный параметр `p_current_screen` — hint для anchor fallback. `process_user_input` передаёт `v_current_screen` который вычислен ДО clear_status.

**Логика 3 приоритетов:**

```
1. stack non-empty → pop
   Edge case: pop → stack пуст AND parent=NULL
     → use ui_screens[popped].back_screen_id_default as parent
     → source: 'anchor_after_pop'

2. stack empty + p_current_screen provided
     → use ui_screens[p_current_screen].back_screen_id_default as parent
     → source: 'anchor_from_param'

3. stack empty + no p_current_screen
     → try workflow_states[users.status].screen_id
     → validate against ui_screens
     → use its back_screen_id_default as parent
     → source: 'anchor_from_status'

Fallback: {parent: NULL, source: 'empty_no_anchor'}  ← caller обрабатывает
```

**Поле `source` в возвращаемом JSONB:**

| source | Когда |
|--------|-------|
| `stack` | нормальный pop из непустого стека |
| `anchor_after_pop` | pop → стек пуст → parent из `back_screen_id_default` поднятого экрана |
| `anchor_from_param` | стек пуст, p_current_screen задан |
| `anchor_from_status` | стек пуст, нет hint, резолвлено из `workflow_states[status]` |
| `empty_no_anchor` | стек пуст, нет hint, нет screen по статусу |
| `user_not_found` | пользователь не найден |

**Патч `process_user_input`:**

```sql
-- Было:
v_back_result := back_nav(p_telegram_id);

-- Стало:
v_back_result := back_nav(p_telegram_id, v_current_screen);
```

2 строки изменены, idempotent DO block. `v_current_screen` вычислен до любых изменений статуса.

**7 сценариев E2E на ephemeral user (telegram_id=99999999991):**

| # | Условие | Ожидаемый результат | Статус |
|---|---------|---------------------|--------|
| 1 | `stack=[]`, `p_current='settings'` | `parent=profile_main / anchor_from_param` | ✓ |
| 2 | `stack=[]`, `status='edit_lang'`, no hint | `parent=settings / anchor_from_status` | ✓ |
| 3 | `stack=[]`, `status='registered'`, no hint | `parent=NULL / empty_no_anchor` | ✓ (caller fallback) |
| 4 | `stack=[profile_main,settings,edit_lang]` | `parent=settings / stack` | ✓ |
| 5 | `stack=[settings]` (pop → empty) | `parent=profile_main / anchor_after_pop` | ✓ |
| 6 | Несуществующий пользователь | `parent=NULL / user_not_found` | ✓ |
| 7 | `back_nav(id)` одним аргументом | backward compatible | ✓ |

**Coverage:** anchor работает для 17 из 18 экранов. Исключение: `profile_main` имеет `back_screen_id_default=NULL` — это root, у него нет родителя. Сценарий 3 (стек пуст + status=registered + нет hint) возвращает NULL — expected, caller использует hard fallback `profile_main`.

**Dispatcher изменения (migration 116):**

Picker callbacks теперь всегда роутятся в `menu_v3` **без** guard `user.status`, чтобы сохранить `v_current_screen` до clear_status в `process_user_input`.

### Known edge cases (deferred)

- **Friends → Info → Back** → Main Menu fallback (parent=friends нет rule). Минорное — defer Phase 7/8
- **picker → picker переходы:** стек `['profile','my_plan','edit_goal','edit_speed']` → Back из edit_speed → edit_goal ✅. Но edit_goal → edit_speed → edit_gender (гипотетическая 3-уровневая цепочка) не тестировалась
- **Language picker reply keyboard** не убирается через nav_stack — используется 2-message pattern (remove_keyboard + Settings)
- **Echo-сообщение "Question: Answer ✓"** — источник не идентифицирован (D3 plan item)

### Взаимодействие с One-Menu UX

nav_stack покрывает **логическую навигацию** (откуда я пришёл → куда вернуться). One-Menu UX покрывает **физические сообщения** (deleteMessage старого меню). Это комплементарные, но независимые слои:

- `reset_nav_to` чистит стек, но физическое sub-screen сообщение может остаться (known gap в [[concepts/one-menu-ux]])
- `last_bot_message_id` отслеживает только top-level messages. Pickers/sub-screens не tracked
- Для полного решения нужно расширять One-Menu на sub-screens (см. [[concepts/one-menu-ux]] Known gap)

### Итоговые числа

| Метрика | Значение |
|---------|---------|
| Кнопок "Назад" мигрировано | 26 |
| Push Nav HTTP нод добавлено | 13 |
| Back Target Router rules | 5 + fallback |
| Workflows задеплоено | 5 (04_Menu, 08.4_Shop, 10_Payment, 02_Onboarding_v3, 02.1_Location) |
| Миграций | 3 (076, 077, 078) |
| 04_Menu node count | 109 → 123 |

### Migration 146 — back fallback → stats_main + push_nav cap 7 (2026-04-29)

**Bug:** «Назад иногда уводит в Профиль вместо Прогресса». Root cause — hardcoded `profile_main` в Priority 3 fallback `process_user_input` (когда stack пуст и `back_screen_id_default` = NULL).

**Аудит surface:** из 44 ui_screens, 41 имеют `back_screen_id_default` ✓. 3 без (profile_main / progress_main / stats_main) — root-screens, у которых нет cmd_back кнопок. **Real bug surface = 0 в current config**, но theoretical risk для future screens.

**UX-директива тимлида:** «Кнопка Назад должна работать всегда. До 7 подуровней. Stay-put нельзя.» → fallback = `stats_main` (безопасный дашборд, минимум побочных эффектов).

**Изменения:**

1. **`push_nav` cap 10 → 7:** полный rewrite через `CREATE OR REPLACE`. Loop drops oldest пока stack >= cap (защита на случай уменьшения cap).
2. **`back_nav` absolute root fallback:** 2 места (Path 1 после pop + Path 2 stack пустой) — оба `parent='stats_main'` с `source='absolute_root_fallback'`. RAISE WARNING при каждом срабатывании для observability.
3. **`process_user_input` Priority 3:** `profile_main` → `stats_main` + RAISE WARNING.

### Migration 147 — I-came-from path-walk navigation (2026-04-29)

**Проблема:** migration 146 закрыл fallback, но глубина истории = 1: fastpath callbacks вытирали `nav_stack='[]'` до `push_nav` (L325). Нет реальной I-came-from навигации при Inline-переходах.

**Архитектурный pivot:** переход от tree-walk (`back_screen_id_default` first) к **path-walk** (`nav_stack` as real history first).

**4 изменения:**

1. **`push_nav` — truncate-on-existing:** если pushing screen уже в стеке, обрезает до его индекса (включительно). Закрывает циклы A→B→C→B → push B truncate to [A, B]. Закрывает save-and-return (Settings → edit_lang → save → push Settings → truncate to [Profile, Settings]).

2. **`process_user_input` fastpath — input-source-aware (БЕЗ хардкода имён):**
   - Reads `(p_cb_context->>'is_inline')::boolean` (default TRUE для backward compat).
   - TRUE (Inline KB): keep stack → push destination → I-came-from history.
   - FALSE (Reply KB synth): wipe stack → новый корень. SQL не знает имена callbacks.

3. **`process_user_input` cmd_back — Priority 1/2 инвертированы:**
   - **Priority 1 NEW:** nav_stack pop через back_nav (path-walk, I-came-from).
   - **Priority 2 NEW:** `back_screen_id_default` (tree fallback когда стек пуст).
   - **Priority 3:** `stats_main` absolute root + WARNING (146 preserved).

4. **Advisory lock + Read-after-Lock:** `pg_advisory_xact_lock(147147147)` ПЕРЕД `pg_get_functiondef`. Защита от concurrent execution другими агентами.

**До/После поведения:**

| Сценарий | До 147 | После 147 |
|---|---|---|
| profile → progress → friends → shop, 3× Back | shop → progress (back_default) → profile (back_default) → stats_main fallback | shop → friends → progress → profile (stack pop'ы — реальный путь) |
| Reply KB «Профиль» в середине пути (после Python deploy) | push profile_main → стек растёт | wipe stack → стек = [profile_main] → Назад = stats_main (Priority 3) |
| Save-and-return (Settings → Edit Lang → Save) | возможен дубликат в стеке | truncate-on-existing → стек правильный |

**Verify (9 сценариев):** push_nav truncate ✅, linear I-came-from path ✅, cmd_back walks back 4 levels ✅, Priority 2 tree fallback ✅, Priority 3 absolute root ✅, Reply KB wipe ✅, backward compat (no is_inline = inline behavior) ✅.

**Python handover (commit `eb3c93d`):** `dispatcher/router.py` получил поле `cb_context` в `RouteDecision`. В 3 synth_callback ветках (profile/stats/progress reply-text) ставится `{"is_inline": False}`. Direct inline callbacks оставляют `cb_context=None` (default TRUE подхватит). 135/135 тестов.

## Related Concepts

- [[concepts/one-menu-ux]] — физический слой (deleteMessage/save_bot_message) vs логический (nav_stack); known gap sub-screens не tracked
- [[concepts/n8n-data-flow-patterns]] — Rule #1 (HTTP Request clobbers $json) критичен для Push Nav placement; paired items bug в 02.1_Location
- [[concepts/n8n-stateful-ui]] — editMessageText, callback_message_id, inline vs reply keyboard
- [[concepts/profile-redesign-v5]] — Agent Dossier UI, 4 под-экрана, Bug 2 Language Back → Settings
- [[concepts/edit-picker-dual-render]] — 9 edit cases в Build Ask Markup; Phase 2 мигрировала все на cmd_back
- [[concepts/payment-integration]] — Phase 5 убрала subscription_source hack; pre-existing JSON.stringify bug fix
- [[concepts/n8n-subworkflow-contract]] — D5 push_nav в v3 через _push_nav_screen; Phase 4 After-Lang Builder
- [[concepts/variant-b-cutover]] — is_inline handover для Python Dispatcher Phase 0.5+1

## Sources

- [[daily/2026-04-17.md]] — Bug 6 полный цикл (Phase 0-8 + R1): migrations 076-078, 26 кнопок на cmd_back, 13 Push Nav нод, Back Target Router 5 rules, Phase 3 paired items hotfix, Phase 3.5 edit_speed→edit_goal fix, D5 unified save confirmation + backInlineKB в v3, Phase 4 Language→Settings + stale keyboard 2-msg fix, Phase 5 subscription_source removal + JSON.stringify 404 fix, Phase 6 Shop/Friends/League/Quests, Phase 7 08.4_Shop, Phase 8 cleanup, R1 newcomer welcome
- [[daily/2026-04-22.md]] — Migration 121: back_nav anchor fallback (new signature + p_current_screen hint), 3-priority fallback chain, source debug field, 7-scenario E2E verification, process_user_input 2-line patch; migration 116: picker callbacks → menu_v3 без status guard; migration 117: cmd_back priority = back_screen_id_default FIRST (hierarchy), nav_stack fallback second
- [[daily/2026-04-27.md]] — Deployment confirmation: Phases 5-8 + R1 задеплоены и smoke-tested. Phase 5 (Payment): subscription_source hack заменён на cmd_back + nav_stack + BTR Rule[3] progress. Phase 6: 8 замен + 5 Push Nav нод + BTR Rule[4] shop. Phase 7: 08.4_Shop. Phase 8: Profile Sub-Screen cleanup. R1: newcomer Language → Back → Welcome через regKB() в Onboarding Engine
- [[daily/2026-04-29.md]] — Migration 146: back fallback stats_main + push_nav cap 7, 6-scenario verify. Migration 147: I-came-from path-walk (truncate-on-existing, is_inline source-aware, Priority 1/2 invert, advisory lock), 9-scenario verify, Python handover commit eb3c93d (cb_context + is_inline=False для reply-kb synth)
