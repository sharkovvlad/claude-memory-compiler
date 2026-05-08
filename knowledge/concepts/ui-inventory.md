---
title: "UI Inventory — All Screens, Callbacks, Menus"
aliases: [ui-inventory, screen-map, callback-catalog, menu-tree]
tags: [reference, ui, callbacks, workflow_states, headless-prep]
sources:
  - "daily/2026-04-19.md"
  - "n8n workflows 2026-04-18 snapshot"
created: 2026-04-19
updated: 2026-04-19
status: approved (partial) — user verified 2026-04-19; details on my discretion
---

# UI Inventory — NOMS Bot

**Статус:** `approved (partial)`. User верифицировал общую полноту списка callbacks и workflow_states (2026-04-19). Детальные решения по каждому экрану — на моё усмотрение при реализации. **Когда понадобится approval конкретного экрана — презентация целиком (схема + текст + визуальный preview keyboard)**, не в табличном формате.

**Future management:** после Phase 2, правки в `ui_screens`/`ui_screen_buttons` делаются через Supabase Studio (table editor) или Retool (custom admin UI для маркетологов). Никаких SQL миграций для операционных UI changes — только для структурных.

**Назначение:** референс при миграции на Headless Architecture. Каждый элемент здесь = 1 row в `ui_screens`/`ui_screen_buttons`.

## 1. Reply-Keyboard (Main Menu)

После завершения онбординга у user всегда видна reply-keyboard с 4 кнопками (2 строки):

| Row | Button | text_key | icon_const | Triggers route |
|-----|--------|----------|------------|----------------|
| 1 | Add food | `buttons.add_food` | `icon_add_food` | → AI Engine (03) |
| 2 | My Day | `buttons.stats` | `icon_myday` | → 04_Menu (stats) |
| 2 | Progress | `buttons.progress` | `icon_progress` | → 04_Menu (progress) |
| 2 | Profile | `buttons.profile` | `icon_profile` | → 04_Menu (profile) |

**Источник:** `onboarding_engine.js` lines 18-54, `04_Menu` node `Send Main Menu (Back)`.

**Special reply keyboards:**
- 13 language flags (onboarding) — только при `status='new'` или `changing_language`
- Timezone picker keyboard — `onboarding:timezone`
- Gender/Activity/Training/Goal — inline (не reply)

## 2. 85 Callback Data (группы)

### A. Onboarding Selection (cmd_select_*, cmd_speed_*) — 19 callbacks

| Callback | Status использования |
|----------|----------------------|
| `cmd_select_male`, `cmd_select_female` | `registration_step_1`, `edit_gender` |
| `cmd_select_sedentary`, `cmd_select_light`, `cmd_select_moderate`, `cmd_select_heavy` | `registration_step_5`, `edit_activity` |
| `cmd_select_strength`, `cmd_select_cardio`, `cmd_select_mixed`, `cmd_select_training_skip` | `registration_step_training`, `edit_training` |
| `cmd_select_lose`, `cmd_select_maintain`, `cmd_select_gain` | `registration_step_goal`, `edit_goal` |
| `cmd_speed_slow`, `cmd_speed_normal`, `cmd_speed_fast` | `edit_speed` |

### B. Menu Main (cmd_*) — 15 callbacks

| Callback | Route | Purpose |
|----------|-------|---------|
| `cmd_get_stats` | stats | Show "My Day" dashboard |
| `cmd_get_profile` | profile | Show Profile/Agent Dossier |
| `cmd_progress` | progress | Show Game Hub |
| `cmd_add_food` | add_food | Trigger AI food logging |
| `cmd_show_meals` | meals | List meals (04.2) |
| `cmd_edit_last` | edit_last | Edit last meal |
| `cmd_delete_last` | delete_last | Delete last meal |
| `cmd_cancel_edit`, `cmd_cancel` | cancel | Cancel edit |
| `cmd_back` | back | Generic back (nav_stack.pop) |
| `cmd_back_to_profile` | profile | Back to profile |
| `cmd_back_to_progress` | progress | Back to progress |
| `cmd_skip_meal` | skip_meal | Fasting log |
| `cmd_noop` | — | Decorative (coming soon) |
| `cmd_recharge_mana` | recharge_mana | Buy mana via shop |
| `cmd_unknown` | — | Fallback |

### C. Edit Profile (cmd_edit_*) — 11 callbacks

| Callback | Status Set | Pairing с Onboarding |
|----------|-----------|----------------------|
| `cmd_edit_weight`, `cmd_update_weight` | `edit_weight` | `registration_step_3` |
| `cmd_edit_age` | `edit_age` | `registration_step_2` |
| `cmd_edit_height` | `edit_height` | `registration_step_4` |
| `cmd_edit_gender` | `edit_gender` | `registration_step_1` |
| `cmd_edit_activity` | `edit_activity` | `registration_step_5` |
| `cmd_edit_training` | `edit_training` | `registration_step_training` |
| `cmd_edit_goal` | `edit_goal` | `registration_step_goal` |
| `cmd_edit_speed` | `edit_speed` | (NEW, не в онбординге) |
| `cmd_edit_lang` | `changing_language` | язык picker |
| `cmd_edit_country` | `onboarding:country` | location flow |
| `cmd_edit_timezone` | `onboarding:timezone` | location flow |
| `cmd_edit_phenotype` | `edit_phenotype` | (NEW, не в онбординге) |

### D. Location Picker (loc_*) — 14 callbacks

`loc_country`, `loc_detect_geo`, `loc_tz`, `loc_utc_select`, `loc_back_to_list`, `loc_back_to_tz`, `loc_other`, `loc_other_page`, `loc_tz_more`, `loc_tz_utc`, `loc_utc_page`, `loc_utc_group`, `loc_no_country`, `loc_action`

**Handler:** `02.1_Location` workflow (отдельный — мигрируем в Phase 3B, сложный pagination).

### E. Payment (cmd_pay_*, cmd_select_plan_*) — 13 callbacks

| Callback | Purpose |
|----------|---------|
| `cmd_premium_plans`, `cmd_premium_plans_list` | Show plans |
| `cmd_select_plan_monthly`, `cmd_select_plan_quarterly`, `cmd_select_plan_yearly` | Select plan |
| `cmd_pay_stars_monthly/quarterly/yearly` | Stars checkout |
| `cmd_pay_crypto_monthly/quarterly/yearly`, `cmd_pay_crypto` | USDT/TON |
| `cmd_enter_promo`, `cmd_apply_promo` | Promo code |
| `cmd_profile_subscription` | Manage subscription (from Profile) |

**Handler:** `10_Payment` workflow. UI screens мигрируем, webhook logic остаётся.

### F. Progress Hub (cmd_quests, cmd_league, ...) — 8 callbacks

`cmd_quests` → 08.1_Quests, `cmd_league` + `cmd_league_info` → 08.2_League, `cmd_friends` + `cmd_friends_info` → 08.3_Friends, `cmd_shop` + `cmd_buy_freeze` + `cmd_buy_mana` → 08.4_Shop.

### G. Profile v5 Sub-screens — 5 callbacks

`cmd_my_plan`, `cmd_settings`, `cmd_personal_metrics`, `cmd_help`, `cmd_profile_subscription`.

**Pilot target для Phase 2.**

### H. Ambassador Payout — 8 callbacks

`cmd_ambassador_payout`, `cmd_payout_usdt_ton`, `cmd_payout_usdt_trc20`, `cmd_payout_bank`, `cmd_payout_confirm`, `cmd_payout_cancel`, `admin_payout_approve_{id}`, `admin_payout_reject_{id}`.

### I. Phenotype Quiz — 6 callbacks

`cmd_start_phenotype_quiz`, `cmd_phenotype_q1_a..q4_c` (dynamic), `cmd_phenotype_skip`.

**Текущий статус:** Phase 1 DB готова (migration 062), но routing сломан (Switch cache bug). Будет починен автоматически в Phase 3B headless миграции.

### J. Soft Delete / Restore — 4 callbacks

`cmd_delete_account`, `cmd_confirm_delete`, `cmd_restore_account`, `cmd_start_fresh`.

### K. Dynamic Meal Management (04.2) — 5 callbacks

`cmd_view_meal_{id}`, `cmd_del_meal_{id}`, `cmd_start_edit_{id}` (dynamic UUID), `cmd_edit_last`, `cmd_delete_last`.

**Особенность:** динамический UUID в callback. Headless requires template `cmd_view_meal_{meal_id}` в ui_screen_buttons + substitution в render_screen + runtime length check.

## 3. Screen Hierarchy

```
MAIN MENU (reply KB)
├── stats (My Day)
│   ├── [cmd_edit_last] → edit_last flow
│   └── [cmd_delete_last] → delete confirm
│
├── progress (Game Hub)
│   ├── quests
│   ├── league ─→ league_info
│   ├── friends ─→ friends_info
│   └── shop ─→ buy_freeze / buy_mana
│
└── profile (Agent Dossier v5)   ← PILOT Phase 2
    ├── my_plan
    ├── settings
    │   ├── language_picker
    │   ├── country_picker
    │   ├── timezone_picker
    │   └── ask_weight (reuses onboarding screen)
    ├── personal_metrics
    ├── help
    ├── phenotype_quiz_intro → phenotype_q1..q4 → phenotype_result
    ├── payout_method → payout_wallet → payout_confirm
    ├── subscription (→ 10_Payment)
    └── delete_account → delete_confirm

ONBOARDING (from /start)
ask_gender → ask_age → ask_weight → ask_height → ask_activity
  → ask_training → ask_goal → onboarding:country → onboarding:timezone → registered
```

## 4. workflow_states (все 26+ статусов)

| state_code | Phase | next_step_code | Input Type |
|------------|-------|----------------|------------|
| `new` | Onboarding | `registration_step_1` | text (/start) |
| `registration_step_1` | Onboarding | `registration_step_2` | inline (cmd_select_male/female) |
| `registration_step_2` | Onboarding | `registration_step_3` | text (numeric age) |
| `registration_step_3` | Onboarding | `registration_step_4` | text (numeric weight) |
| `registration_step_4` | Onboarding | `registration_step_5` | text (numeric height) |
| `registration_step_5` | Onboarding | `registration_step_training` | inline (activity) |
| `registration_step_training` | Onboarding | `registration_step_goal` | inline (training) |
| `registration_step_goal` | Onboarding | `onboarding:country` | inline (goal) |
| `onboarding:country` | Onboarding | `onboarding:timezone` | location/loc_* |
| `onboarding:timezone` | Onboarding | `registered` | loc_tz_* |
| `registered` | Main | — | callback/text |
| `changing_language` | Transient | back to previous | language flag |
| `edit_gender`, `edit_age`, `edit_weight`, `edit_height` | Edit | `registered` | varies |
| `edit_activity`, `edit_training`, `edit_goal` | Edit | `registered` | inline |
| `edit_speed` | Edit | `registered` | inline (cmd_speed_*) |
| `edit_phenotype` | Edit (Quiz) | `registered` | 4 inline questions |
| `payout_method` | Ambassador | `payout_wallet` | inline |
| `payout_wallet` | Ambassador | `payout_confirm` | text (wallet address) |
| `payout_confirm` | Ambassador | `registered` | inline confirm |
| `deleting:confirm` | Soft Delete | `deleted` | inline confirm |
| `restoring:choose` | Soft Delete | `registered`/`new` | inline choice |
| `deleted` | Soft Delete | (30-day ttl → anonymized) | — |
| `anonymized` | Soft Delete | — | — |

**Вопросы для user:**
- Все ли статусы перечислены? Есть `entering_promo`, `editing_meal_inline` которые упоминаются в коде?
- `subscription_source='profile'` — это поле или статус?

## 5. Translation Sections (ui_translations)

| Root key | Scope | ~Keys |
|----------|-------|-------|
| `profile.*` | Agent Dossier v5 | 28 |
| `buttons.*` | Navigation labels | 9+ |
| `questions.*` | Onboarding prompts | 8+ |
| `answers.*` | Answer options | 16+ |
| `payment.*` | Plans, methods | 15+ |
| `progress.*` | Game Hub | 10+ |
| `league.*` | League system | 12+ |
| `shop.*` | Shop items | 8+ |
| `quest.*` | Daily quests | 6+ |
| `friends.*` | Referral system | 5+ |
| `payout.*` | Ambassador | 7+ |
| `phenotype.*` | Body types | 22 (migration 062) |
| `edit.*` | Edit profile | 12+ |
| `food_log.*` | Meal tracking | 8+ |
| `report.*` | Daily insights | 10+ |
| `onboarding.*` | Welcome/completion | 6+ |
| `messages.*` | Errors, confirmations | 5+ |

**Languages:** 13 (en, ru, uk, es, de, fr, it, pt, pl, id, hi, ar, fa).

## 6. Terminal/Special Screens (вне main hierarchy)

| Screen | Trigger | Keyboard Cleared |
|--------|---------|------------------|
| Level Up | RPC `log_meal_transaction` XP threshold | ✅ |
| Day Close | cron streak check, 3+ meals | ✅ |
| Food Logged | AI Engine after recognition | Edit/Delete persistent |
| Quest Completed | RPC `complete_quest` | ✅ |
| League Promotion | Monday 12:00 UTC cron | ✅ |
| Subscription Activated | 10_Payment webhook | ✅ |
| Delete Confirmation | cmd_delete_account | ✅ |

## 7. Неявные / Implicit UI Concerns

**Что может быть упущено — нужна верификация:**

1. **Photo/Voice** — technically UI entry, но обрабатываются в 03_AI_Engine. В Headless: `process_user_input('photo')` → `forward_to: '03_AI_Engine'`.
2. **Geolocation** — когда user шарит геопозицию (native Telegram feature). Handler в 02.1_Location.
3. **Pre-checkout** — Telegram Stars payment flow. Handler в 10_Payment, не UI.
4. **Successful payment** — post-checkout Telegram event. Renders subscription activated screen.
5. **Start command `/start`** — bot command. Special handler в 01_Dispatcher.
6. **Bot tagged in reply** — не UI callback, а text input. Handler через Merge Data.
7. **Admin commands** (если есть) — могут минуют debounce. Spec unclear.

## 8. Workflows-participants

| Workflow | Role в Headless |
|----------|-----------------|
| 01_Dispatcher | Classifier (remains, minimal changes) |
| 02_Onboarding_v3 | **Упрощается** — Onboarding Engine удаляется |
| 02.1_Location | Остаётся (сложный pagination) — мигрирует в Phase 3B |
| 03_AI_Engine | **Не трогаем** — business logic. Вызывает render_screen в конце |
| 04_Menu | **Заменяется** на 04_Menu_v3 (Dumb Renderer, ~15 нод) |
| 04.2_Edit_StatsDaily | **Заменяется** в Phase 3B (dynamic_list input_type) |
| 06_Indicator_* | Остаётся (typing indicator) |
| 08.*_Quests/League/Friends/Shop | **Заменяются** на render_screen вызовы |
| 10_Payment | Остаётся (webhooks), но Payment UI screens мигрируют |

## 9. Что user должен проверить

1. Все ли 85 callbacks перечислены?
2. Все ли 26+ workflow_states в таблице? Чего не хватает?
3. Pairing onboarding ↔ edit — правильный?
4. Pilot scope (Profile v5 — 9 screens) — включает правильные sub-screens?
5. Дополнительные screens которые я пропустил: admin-экраны, debugging, onboarding welcome screen, quiz intro screen?
6. callback_data для subscription_source='profile' flow — как корректно фиксировать?
7. Meal edit inline correction flow — нужны ли спец.screens (для edit_count tracking для RLHF)?

**После верификации:** status → `approved`. Используется как референс при INSERT в ui_screens (migrations 086-094).

## Related

- [[concepts/headless-architecture]] — архитектура миграции
- [[concepts/nav-stack-architecture]] — 30 canonical screen_names уже используются
- [[concepts/phenotype-quiz]] — будет unified через ui_screens
- [[concepts/profile-redesign-v5]] — pilot scope детали
- [[concepts/picker-unification-strategy]] — исходная мотивация (8 дубликатов pickers)

## Sources

- Agent exploration 2026-04-19: n8n workflows `json архив/n8n_2026.04.18/`, JS code nodes, migrations 000-084
- Master Blueprint v3.0 workflow map
- dispatcher_route_classifier_v1.8.js, onboarding_engine.js
