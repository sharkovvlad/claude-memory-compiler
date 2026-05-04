---
title: "UI Screens Map — Navigation Tree (canonical)"
aliases: [screens-map, navigation-map, ui-navigation-tree, screens-hierarchy]
tags: [reference, ui, navigation, headless, source-of-truth]
sources:
  - "DB-verified 2026-05-04 via psycopg2 (ui_screens + ui_screen_buttons, 48 rows)"
  - "concepts/ui-inventory.md"
  - "concepts/profile-v5-screens-specs.md"
  - "concepts/progress-hub-headless.md"
  - "concepts/one-menu-ux.md"
created: 2026-05-04
updated: 2026-05-04
status: approved (canonical) — DB-verified
---

# UI Screens Map — навигационное дерево NOMS

**Status:** canonical для всех агентов. **Source of truth:** этот файл — общая карта (что куда ведёт). Authority внутри файла — DB-поле `ui_screens.back_screen_id_default` (это куда уходит `cmd_back` — фактический parent в нав-стеке). Подробности по конкретному экрану — в специализированных KB-статьях (cross-link внизу каждой секции).

**Парадигма навигации:** **Stateful Mini App via `editMessageText`** — бот ведёт себя как полноценное приложение в одном сообщении, переходы между экранами = перерисовка через `editMessageText`, не отправка нового сообщения. Фундамент паттерна — [one-menu-ux](one-menu-ux.md) + [nav-stack-architecture](nav-stack-architecture.md). Reply-keyboard персистентна, inline-меню — ephemeral.

---

## 1. Глобальная reply-keyboard (4 root screen)

После онбординга reply-keyboard всегда видна. 4 кнопки, 2 строки:

```
┌──────────────────────┐
│   🍽️  Add food       │   ← row 1 (single, primary action)
├────┬────┬────────────┤
│My  │Pro │  Profile   │   ← row 2 (3 buttons)
│Day │gress│           │
└────┴────┴────────────┘
```

| Кнопка | Target screen | Тип |
|---|---|---|
| `🍽️ Add food` | `add_food_action` | Action (не screen — открывает AI Engine pipeline, фото/голос/текст) |
| `📊 My Day` | `stats_main` | Root screen |
| `🚀 Progress` | `progress_main` | Root screen |
| `👤 Profile` | `profile_main` | Root screen |

**Текст кнопок:** через `ui_translations.buttons.*` (13 языков). **Иконки:** через `app_constants.icon_*`. Никогда не хардкодить.

---

## 2. Дерево экранов — только навигационные узлы

Только узлы, между которыми реально ходят (по `back_screen_id_default` + `cmd_*` кнопкам). Terminal/state-экраны (`*_success`, `*_error_*`) — в §5. Cross-cutting jumps — в §6. DB-аномалии — в §7.

```
[Reply Keyboard — всегда видна, 4 кнопки]
    │
    ├─ 🍽️ Add food → [AI Engine pipeline, не screen]
    │
    ├─ 📊 stats_main (root)
    │      └─ [нет sub-screens — leaf root]
    │
    ├─ 🚀 progress_main (root)
    │      ├─ quests           [см. anomaly #1 в §7]
    │      ├─ league
    │      │     └─ league_info
    │      ├─ friends_info     (stateful — реферал + payout state machine)
    │      │     ├─ friends_how_it_works
    │      │     └─ payout_method_picker
    │      │           ├─ payout_phone_request   (input=reply_kb_request_contact)
    │      │           ├─ payout_phone_confirm
    │      │           └─ payout_wallet_input    (input=text_input)
    │      │                 └─ payout_confirm
    │      └─ shop
    │            ├─ buy_freeze_confirm
    │            └─ buy_mana_confirm
    │
    └─ 👤 profile_main (root)
           ├─ my_plan
           │     ├─ edit_goal
           │     ├─ edit_activity
           │     ├─ edit_training
           │     ├─ edit_speed       [см. anomaly #3 в §7]
           │     └─ personal_metrics
           │           ├─ ask_weight
           │           ├─ ask_height
           │           ├─ ask_age
           │           └─ edit_gender
           ├─ settings
           │     ├─ edit_lang
           │     ├─ edit_country     → country_picker  (peer in DB, sub-flow по UX)
           │     ├─ edit_timezone    → timezone_picker (peer in DB, sub-flow по UX)
           │     └─ edit_notifications_mode
           └─ help
                 └─ delete_account_confirm

[Глобальные transient screens — вне основного дерева]
    ├─ onboarding_welcome   (root, send_new, reply_kb — entry для нового юзера)
    └─ restore_choice       (root, send_new, inline_kb — soft-delete recovery)
```

---

## 3. Типы экранов (semantics)

| Type | Поведение | Кнопка «Назад» | Пример |
|---|---|---|---|
| `root_screen` | Точка входа из reply-keyboard. Самый верхний уровень. | Нет (но reply-kb всегда доступна — это «Назад» по умолчанию) | `stats_main`, `progress_main`, `profile_main` |
| `menu` | Stateless inline-меню. Перерисовывается через `editMessageText` при нажатии. | Ведёт к **родителю** через `back_screen_id_default`. Унифицированный ключ перевода `buttons.back`. | `quests`, `my_plan`, `settings` |
| `stateful_menu` | Меню с persistent состоянием юзера (например, реферальный progress, payout state machine). | Аналогично menu, но с проверкой текущего workflow_state перед рендером. | `friends_info` |
| `input` | Экран запрашивает данные у юзера (text/contact). `input_type` в DB: `text_input`, `reply_kb_request_contact`. | Возврат к родителю без сохранения. | `ask_weight`, `payout_wallet_input`, `payout_phone_request` |
| `state` (terminal) | Финальный экран после действия (success/error). Не образует навигационных развилок — только `cmd_back` к parent. См. §5. | К parent через `back_screen_id_default`. | `buy_freeze_success`, `shop_error_no_coins`, `payout_success` |
| `payment_gateway` | Особый тип — открывает Stripe/Stars/TON pipeline через n8n. См. §6 для cross-cutting. | Возврат к anchor (DB `back_default`). | `premium_plans` |
| `transient` | Вне основного дерева. Не входит в reply-kb навигацию (`onboarding_welcome`, `restore_choice`). | Свой собственный flow. | `restore_choice` |

**Universal back rule** ([CLAUDE.md UX](../../../CLAUDE.md#uxui-stateful-mini-app)): кнопка «Назад» **всегда ведёт к вышестоящему меню** через `back_screen_id_default`, не к предыдущей операции. Один ключ перевода для всех случаев — НЕ создавать специализированные варианты.

---

## 4. Canonical JSON spec (machine-readable)

Только навигационные узлы. State-screens — в §5, cross-cutting — в §6.

```json
{
  "navigation_paradigm": "Stateful Mini App via editMessageText",
  "global_reply_keyboard": ["add_food_action", "stats_main", "progress_main", "profile_main"],
  "screens": {
    "stats_main": { "type": "root_screen", "sub_screens": [] },
    "progress_main": {
      "type": "root_screen",
      "sub_screens": [
        { "id": "quests", "type": "menu", "note": "physical_parent=NULL, logical_parent=progress_main via back_default + meta.parent — см. §7" },
        { "id": "league", "type": "menu", "children": ["league_info"] },
        {
          "id": "friends_info",
          "type": "stateful_menu",
          "children": [
            "friends_how_it_works",
            {
              "id": "payout_method_picker",
              "type": "menu",
              "children": [
                "payout_phone_request",
                "payout_phone_confirm",
                { "id": "payout_wallet_input", "type": "input", "children": ["payout_confirm"] }
              ]
            }
          ]
        },
        { "id": "shop", "type": "menu", "children": ["buy_freeze_confirm", "buy_mana_confirm"] }
      ]
    },
    "profile_main": {
      "type": "root_screen",
      "sub_screens": [
        {
          "id": "my_plan",
          "type": "menu",
          "children": [
            "edit_goal", "edit_activity", "edit_training", "edit_speed",
            { "id": "personal_metrics", "type": "menu", "children": ["ask_weight", "ask_height", "ask_age", "edit_gender"] }
          ]
        },
        {
          "id": "settings",
          "type": "menu",
          "children": ["edit_lang", "edit_country", "country_picker", "edit_timezone", "timezone_picker", "edit_notifications_mode"]
        },
        { "id": "help", "type": "menu", "children": ["delete_account_confirm"] }
      ]
    }
  },
  "global_transient_screens": ["onboarding_welcome", "restore_choice"]
}
```

---

## 5. Terminal/state screens

Реальные rendered-экраны в БД (`input=inline_kb`, `strategy=replace_existing`, имеют `cmd_back` → возврат к parent). Не образуют развилок, не должны добавляться в основное дерево §2 / JSON §4.

| screen_id | parent (`back_default`) | Когда показывается |
|---|---|---|
| `payout_no_balance` | `friends_info` | `cmd_start_payout` при `balance=0` |
| `payout_success` | `friends_info` | После успешного `payout_confirm` |
| `payout_error_already_pending` | `friends_info` | Уже есть pending payout |
| `payout_error_wallet_invalid` | `payout_wallet_input` | Невалидный wallet address на input |
| `buy_freeze_success` | `shop` | После `cmd_confirm_buy_freeze` |
| `buy_mana_success` | `shop` | После `cmd_confirm_buy_mana` |
| `shop_error_no_coins` | `shop` | Недостаточно NomsCoins на покупку |
| `shop_error_mana_full` | `shop` | Mana уже полная — recharge не нужен |
| `shop_error_recharge_limit` | `shop` | Дневной лимит mana recharges |
| `shop_error_already_premium` | `shop` | Юзер уже premium при попытке купить premium-only |

**Правило:** новый state-screen — добавлять сюда (не в §2/§4), `back_screen_id_default = <parent>` обязателен.

---

## 6. Cross-cutting jumps (один target — несколько entry points)

Узлы, в которые есть переход более чем из одного места дерева. Не дублируются в §2 — вынесены сюда.

| Target | Тип | Откуда входы (callback → entry screen) | Примечание |
|---|---|---|---|
| `premium_plans` | `payment_gateway` | `cmd_premium_plans` на: `profile_main`, `shop`, `shop_error_no_coins`, `shop_error_recharge_limit` | DB: `parent=shop`, `back=shop`, `meta.canonical=false`, `meta.anchor_only=true`, `meta.rendered_by=10_Payment`. Это глобальный платёжный gateway; в DB он anchored на `shop` только для back_nav fallback при stack underflow. Реально рендерится n8n `10_Payment`. |
| `ask_weight` | `input` | `personal_metrics` (button), `profile_main` (`cmd_update_weight` shortcut) | Один screen — два legitimate входа. Back всегда к `personal_metrics` (back_default жёстко зашит) — независимо от пути входа. |
| `cmd_profile_subscription` | (no ui_screens row) | `profile_main`, `shop` | НЕ диспатчится через headless — открывает n8n `10_Payment` subscription flow напрямую. См. anomaly #4 в §7. |

---

## 7. DB anomalies & dangling references

Найдены при DB-верификации 2026-05-04 (psycopg2 dump `ui_screens` + `ui_screen_buttons`).

### 1. `quests` — root в DB, но child по back-навигации

- `parent_screen_id = NULL` (физически root)
- `back_screen_id_default = 'progress_main'`
- `meta = {"parent": "progress_main", "canonical": true}`

Логически живёт под `progress_main`, физически — root. Скорее всего, артефакт исторического сидинга (миграции 122-139). Back-навигация работает корректно через `back_default`, поэтому пользовательского бага нет.

**Watchlist:** при чистке roots — НЕ удалять `quests`. При построении tree from `parent_screen_id` — учитывать `meta.parent` как override. Желательная миграция: `UPDATE ui_screens SET parent_screen_id='progress_main' WHERE screen_id='quests'` (нужно проверить что не сломает FSM-роутинг).

### 2. `cmd_edit_phenotype` — dangling button (no screen)

- В `ui_screen_buttons`: row `(screen_id=my_plan, callback_data=cmd_edit_phenotype, text_key=buttons.edit_phenotype)`
- В `ui_screens`: **нет** ни `edit_phenotype`, ни `phenotype_quiz`

Клик кнопки никуда не ведёт (или падает в fallback диспетчера). User-facing bug. Соответствует roadmap-пункту "Phenotype Quiz (Phase 2)" в [CLAUDE.md](../../../CLAUDE.md#roadmap) — кнопку добавили заранее, screen ещё не реализован.

**Решение:** либо реализовать `phenotype_quiz` screen, либо временно скрыть кнопку через `visible_condition`. Записать в [Известные технические долги](../../../CLAUDE.md#известные-технические-долги).

### 3. `edit_speed` — orphan screen (no inbound button)

- В `ui_screens`: row существует (parent=`my_plan`, back=`my_plan`)
- В `ui_screen_buttons`: **нет** `cmd_edit_speed` ни на одном экране (включая `my_plan`)

Войти через UI невозможно — только direct callback (например, deep-link). Скорее всего, был задуман для my_plan меню, но кнопку забыли добавить.

**Решение:** добавить row в `ui_screen_buttons` для `my_plan` (рядом с `cmd_edit_goal`/`cmd_edit_activity`/`cmd_edit_training`), либо удалить screen.

### 4. `cmd_profile_subscription` — callback без ui_screens row

Кнопка есть на `profile_main` и `shop`, но screen-а с таким именем в headless нет. Диспатчится напрямую в n8n `10_Payment` subscription flow. Это интенциональный legacy fallthrough (см. [architecture-registry](architecture-registry.md)), но создаёт асимметрию: всё остальное в Profile/Shop — headless, subscription — n8n.

**Решение:** при миграции `10_Payment` в Python (см. roadmap [groovy-marinating-eclipse](file:///Users/vladislav/.claude/plans/groovy-marinating-eclipse.md)) — добавить `subscription_*` screens в `ui_screens`.

---

## 8. Где это реально живёт в коде / БД

| Карта | Реализация |
|---|---|
| Reply-keyboard | Ставится в Python через `attach_reply_kb` SQL infrastructure (мигр. 159, conditional re-attach 160). Текст из `ui_translations.buttons.*`, иконки из `app_constants`. |
| Иерархия `ui_screens` | Postgres-таблица `ui_screens` + `ui_screen_buttons` (Headless Architecture, мигр. 122-139). Каждый узел = 1 row. Authority — `back_screen_id_default` для back-навигации, `parent_screen_id` для иерархии (с оговоркой anomaly #1). |
| Рендер экрана | `dispatch_with_render` RPC (мигр. 149) bundle: `process_user_input` (FSM) + `render_screen` (компилирует payload + reply_markup). Python handler шлёт через `telegram_send`. |
| Навигация «Назад» | Hierarchical `users.nav_stack` JSONB ([nav-stack-architecture](nav-stack-architecture.md)). 8 фаз, deployed 2026-04-27. Унифицированный `cmd_back` для всех экранов. Fallback при stack underflow → `back_screen_id_default`. |
| Стейт между переходами | `users.workflow_state` (text), `users.last_bot_message_id` (для One Menu UX), `users.nav_stack` (для Back). |

---

## 9. Кто обслуживает каждый экран сейчас (2026-05-04)

| Экран / ветка | Authoritative | Workflow |
|---|---|---|
| `stats_main` + `progress_main` + все progress sub-screens (включая state-screens из §5) | **Headless** | `04_Menu_v3` n8n (через `dispatch_with_render`). Phase 2 Python forward когда `handler_menu_v3_use_python=true` → `handlers/menu_v3.py` |
| `profile_main` + my_plan/settings/help + все pickers + личные input-экраны | **Headless** | То же, что выше |
| `premium_plans` (cross-cutting, §6) + `cmd_profile_subscription` (§7 #4) | **n8n legacy** | `10_Payment` workflow (Stripe/Stars/TON inline) |
| Edit Meal flow (открывается из `stats_main` → meal_id) | **n8n legacy** | `04_Menu` (legacy) → `04.2_Edit_StatsDaily`. В `ui_screens` отсутствует — намеренно, не headless. |
| `🍽️ Add food` | **n8n legacy** | `03_AI_Engine` (GPT-4o Vision). Не screen. |
| `onboarding_welcome` + onboarding flow | **Headless (Python)** | `handlers/onboarding_v3.py` (Phase 4, cutover 2026-05-02). См. [phase4-onboarding-migration](phase4-onboarding-migration.md). |
| `restore_choice` (soft-delete recovery) | **Python** | `dispatcher/router.py` через `RESTORING_CALLBACKS` ветку. См. daily/2026-05-04. |

См. [architecture-registry](architecture-registry.md) для полной карты Python authoritative vs n8n fallback.

---

## 10. Watchlist для агентов

1. **Не создавать новые root screens** без согласования. Глобальная reply-keyboard зафиксирована — 4 кнопки, иначе ломается muscle memory юзеров.
2. **При добавлении нового sub-screen** — ОБЯЗАТЕЛЬНО:
   - Добавить row в `ui_screens` с правильным `parent_screen_id` И `back_screen_id_default` (обычно одинаковые, кроме anomaly #1)
   - Добавить кнопку в `ui_screen_buttons` на parent screen (иначе orphan — см. anomaly #3)
   - Добавить узел в JSON-схему этого файла §4 + визуальное дерево §2
   - Использовать существующий `cmd_back` (не создавать специализированный)
   - Если экран меняет state → `workflow_state` setter + reset когда юзер уходит выше по дереву
3. **При добавлении terminal/state screen** (success/error) — добавлять в §5 таблицу, НЕ в §2/§4. Обязательно `back_screen_id_default = <parent>`.
4. **При добавлении кнопки с новым `cmd_*`** — проверить что target screen ИЛИ существует в `ui_screens`, ИЛИ есть intentional n8n fallthrough (как `cmd_profile_subscription`). Иначе — dangling button (anomaly #2).
5. **`payment_gateway` тип** — особый. При добавлении новых платёжных flow — НЕ менять контракт `premium_plans`, лучше добавить параллельный экран. Текущая реализация — n8n fallthrough.
6. **Soft-delete recovery** (`cmd_start_fresh` / `cmd_restore_account`) обслуживается отдельной веткой через `RESTORING_CALLBACKS` в `dispatcher/router.py` — это НЕ часть основной screens map, а transient flow (см. §2 нижний блок). См. daily/2026-05-04 (Routing fix soft-delete recovery).
7. **DB authority overrides documentation.** При расхождении этого файла и `ui_screens`/`ui_screen_buttons` — доверять БД, обновлять файл. Не наоборот.

---

## 11. Cross-references

- [one-menu-ux](one-menu-ux.md) — One Menu pattern (`last_bot_message_id`, delete+send vs editMessageText)
- [nav-stack-architecture](nav-stack-architecture.md) — hierarchical Back через `users.nav_stack`
- [headless-architecture](headless-architecture.md) — `process_user_input` + `render_screen` контракт
- [profile-v5-screens-specs](profile-v5-screens-specs.md) — детали Profile v5 (18 частей, callbacks, специфика)
- [progress-hub-headless](progress-hub-headless.md) — детали Progress (quests/league/friends/shop)
- [stats-main-headless](stats-main-headless.md) — детали Stats (мигр. 124-125)
- [ui-inventory](ui-inventory.md) — полный каталог 85 callbacks (детально, ниже уровня этой карты)
- [ux-crosscutting-principles](ux-crosscutting-principles.md) — 5 универсальных UX-правил
- [architecture-registry](architecture-registry.md) — Python authoritative vs n8n fallback (parallel-axis: где обслуживается)
- [phase4-onboarding-migration](phase4-onboarding-migration.md) — детали онбординга (transient flow от `onboarding_welcome`)
