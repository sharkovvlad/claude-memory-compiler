---
title: "Meals Picker — 2-stage edit/delete flow для любого приёма пищи"
aliases: [meals-picker, two-stage-meals, meal-action, cmd-show-meals, edit-any-meal]
tags: [ux, headless, food-log, screens, architecture]
sources:
  - "daily/2026-05-24.md"
created: 2026-05-24
updated: 2026-05-24
---

# Meals Picker — 2-stage edit/delete flow

Двухэкранный flow для редактирования/удаления **любого** приёма пищи (не только последнего). Заменяет одиночную кнопку `[Исправить → cmd_edit_last]` на полноценный picker с per-meal кнопками.

## Key Points

- **2 новых screen'а:** `meals_picker` (список сегодняшних meals с динамическими кнопками) + `meal_action` (действия для конкретного meal: edit / delete / back).
- **4 новых RPC:** `list_today_meals` (для meals_picker), `set_editing_meal_by_id` (ownership-checked), `delete_meal_by_id` (с revert pattern), `get_meal_action_data` (для meal_action business_data).
- **Parametric callback `cmd_select_meal_<uuid>`** — routes через existing `cmd_select_` prefix → `PROFILE_V5_PICKER_PREFIXES` → `target=menu_v3`.
- **Python interceptors в `handlers/menu_v3.py`:** 3 intercept points (cmd_show_meals → dynamic list, cmd_select_meal_* → meal_action, cmd_edit/delete_meal_now → action execution).
- **Template engine extension:** inline-kb buttons могут использовать `text` field напрямую (non-translatable per-meal labels). Backward compatible.

## Flow

```
stats_main [Исправить] cmd_show_meals
  ↓
meals_picker (динамические кнопки по сегодняшним meals)
  ├─ 🍳 08:30 — Омлет, 320 ккал  → cmd_select_meal_<uuid1>
  ├─ 🍎 11:00 — Яблоко, 80 ккал  → cmd_select_meal_<uuid2>
  └─ 🔙 Назад                     → cmd_back → stats_main
  ↓ (юзер кликнул meal)
meal_action
  ├─ [✏️ Исправить] → cmd_edit_meal_now → sets editing_meal_id → edit_food_prompt
  ├─ [🗑 Удалить]   → cmd_delete_meal_now → delete + navigate stats_main
  └─ [🔙 Назад]     → cmd_back → meals_picker
```

## Архитектура

### Dynamic button injection (Python handler)

`meals_picker` screen в DB имеет только `text_key` для заголовка + кнопку Back. Per-meal кнопки **генерируются Python handler'ом** через `list_today_meals` RPC:

```python
async def _handle_show_meals(ctx, decision, rpc_caller):
    meals = await rpc_caller("list_today_meals", {"p_telegram_id": ctx.telegram_id})
    # Build dynamic inline keyboard
    keyboard = []
    for meal in meals:
        label = f"{meal['input_icon']} {meal['time']} — {meal['summary']}, {meal['kcal']} ккал"
        keyboard.append([{"text": label, "callback_data": f"cmd_select_meal_{meal['meal_id']}"}])
    keyboard.append([{"text": "🔙 " + back_label, "callback_data": "cmd_back"}])
    # Override telegram_ui keyboard
    telegram_ui["keyboard"] = keyboard
```

### Template engine `text` field support

Расширение `services/template_engine.py:_build_inline_keyboard`: если button dict содержит `text` field (raw string), он используется напрямую (без lookup через `text_key` + translations). Backward compatible — buttons без `text` продолжают резолвить через `text_key`.

### Parametric callback routing

`cmd_select_meal_<uuid>` starts with `cmd_select_` → matches `PROFILE_V5_PICKER_PREFIXES` в `dispatcher/router.py` → `target=menu_v3`. Handler в `menu_v3.py` перехватывает по prefix:

```python
if decision.callback_data and decision.callback_data.startswith("cmd_select_meal_"):
    meal_id = decision.callback_data.replace("cmd_select_meal_", "")
    return await _handle_select_meal(ctx, decision, rpc_caller, meal_id)
```

### Security: ownership check

`set_editing_meal_by_id(p_tid, p_meal_id)` проверяет `WHERE telegram_id = p_tid AND meal_id = p_meal_id`. Чужой meal_id → `error='meal_not_found'`.

`delete_meal_by_id` читает из safely-set `ctx.editing_meal_id` (уже прошёл ownership check через `set_editing_meal_by_id`).

## Gotchas

### Meta copy trap (existing gotcha #4)

При добавлении `cmd_delete_last` на stats_main (PR #165) meta была `{}` — не скопирована из `_global_floating_actions` где `cmd_delete_last` имеет полный meta. Результат: `dispatch_with_render` не нашёл mapping → silent re-render → Telegram 400 «message not modified». Lesson: [[headless-button-creation-gotchas]] gotcha 4.

### visible_condition widening (existing gotcha #5)

`stats_main` col 0 `[Исправить]` имела `visible_condition: COUNT(meals) = 1`. После удаления col 1 `cmd_show_meals` (mig 321 revert) multi-meal юзеры видели пустую строку. Fix (mig 322): `= 1` → `>= 1`.

### Deploy ordering (existing pattern)

Mig 324 содержала additive (screens + RPCs) + breaking (UPDATE stats_main button callback). Breaking UPDATE applied до deploy Python interceptor → 30 мин мёртвая кнопка. Lesson: [[migration-deploy-ordering]].

## Миграция (mig 324)

```sql
-- 2 screens: meals_picker + meal_action
INSERT INTO ui_screens (screen_id, text_key, render_strategy, input_type, ...)
VALUES ('meals_picker', 'food_log.select_to_edit', 'replace_existing', 'inline_kb', ...),
       ('meal_action', 'food_log.meal_action_title', 'replace_existing', 'inline_kb', ...);

-- 4 RPCs
CREATE FUNCTION list_today_meals(p_tid BIGINT) RETURNS JSONB ...
CREATE FUNCTION set_editing_meal_by_id(p_tid BIGINT, p_meal_id UUID) RETURNS JSONB ...
CREATE FUNCTION delete_meal_by_id(p_tid BIGINT) RETURNS JSONB ...
CREATE FUNCTION get_meal_action_data(p_tid BIGINT) RETURNS JSONB ...

-- stats_main button rewire (BREAKING — deploy AFTER Python)
UPDATE ui_screen_buttons SET callback_data='cmd_show_meals', meta='{}'
WHERE screen_id='stats_main' AND row_index=0 AND col_index=0;
```

## Тесты

16 новых тестов, 303/303 total pass.

## Related Concepts

- [[concepts/stats-main-headless]] — stats_main screen (parent entry point)
- [[concepts/headless-button-creation-gotchas]] — gotcha 4 (meta copy), gotcha 5 (visible_condition)
- [[concepts/migration-deploy-ordering]] — additive vs breaking deploy
- [[concepts/food-log-python-cutover]] — food log confirmation card (sibling flow)
- [[concepts/headless-architecture]] — process_user_input + render_screen contract

## Sources

- [[daily/2026-05-24.md]] — PR #168 (mig 324): 2 screens, 4 RPCs, 3 Python interceptors, parametric callbacks, template_engine text field extension, 16 tests. PR #165 (mig 321): revert broken delete button. PR #166 (mig 322): visible_condition `=1` → `>=1` widening.
