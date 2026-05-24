---
title: "Headless Button Creation Gotchas — meta.target_screen + double emoji + meta-copy trap"
aliases: [headless-button-gotchas, meta-target-screen, double-emoji-button, mig-271-272-273-lessons, button-meta-copy-trap, mig-318-meta-trap]
tags: [headless, ui, buttons, gotchas, patterns]
sources:
  - "daily/2026-05-18.md"
  - "daily/2026-05-24.md"
created: 2026-05-18
updated: 2026-05-24
---

# Headless Button Creation Gotchas

Gotcha-паттерны при создании / правке headless-кнопок (`ui_screen_buttons`). Каждый — «молчаливый баг» (работает без ошибок, но юзер видит неожиданный UX или вообще ничего).

## Key Points

- **Gotcha 1 — `meta.target_screen` обязателен.** Без него `process_user_input` COALESCE chain (L360-365) fallback'ит на `current_screen` → silent re-render текущего экрана. Юзер кликает — ничего не происходит.
- **Gotcha 2 — двойной эмодзи из `icon_const_key` + text_key emoji.** Если `text_key` value в `ui_translations` уже начинается с emoji (⚙️ Configurar plan) И `icon_const_key` тоже задан (icon_settings=⚙️) → renderer prefix'ит icon → `⚙️ ⚙️ Configurar plan`.
- **Gotcha 3 — FSM hardcoded screen_id в `process_onboarding_input`.** При перемещении кнопки на другой экран (mig 271: cmd_edit_phenotype из `my_plan` → `my_plan_settings`) — FSM-handler'ы с hardcoded `RETURN render_screen('my_plan')` продолжают возвращать к старому parent. Back-навигация ломается.
- **Gotcha 4 (2026-05-24) — копируешь `callback_data` между экранами → копируй и `meta`.** При повторном использовании готовой команды (типа `cmd_delete_last`) на новом экране через `INSERT INTO ui_screen_buttons` или `UPDATE callback_data=...` нужно ТАКЖЕ копировать `meta.save_via_callback`/`save_rpc`/`target_screen` из существующей записи. Иначе `dispatch_with_render` не найдёт mapping → silent no-op + `editMessageText` 400 «message is not modified». Lesson mig 318. Recipe ниже.
- **Gotcha 5 (2026-05-24) — `visible_condition` забыли расширить после удаления соседней кнопки.** На stats_main col 0 `[Исправить]` имела `visible_condition: (COUNT(meals today) = 1)` — изначально для single-meal case (col 1 `cmd_show_meals` handled multi-meal). После удаления col 1 (mig 321) условие осталось → multi-meal юзеры видели пустую строку без кнопок. Fix mig 322: widen `= 1` → `>= 1`. **Правило**: при удалении соседних кнопок всегда re-check `visible_condition` оставшихся.

## Details

### Gotcha 1 — `meta.target_screen` обязателен для dispatch

`process_user_input` COALESCE chain для определения `v_next_screen`:

```sql
v_next_screen := COALESCE(
    v_save_result->>'next_screen',         -- dynamic routing от save_rpc
    v_button.meta->>'target_screen',       -- ← ЭТОТ КЛЮЧ
    v_screen.next_on_submit,               -- screen-level default
    v_current_screen                       -- fallback = current (re-render)
);
```

Если `meta.target_screen` пустой/отсутствует, а `next_on_submit` тоже NULL → fallback на текущий screen → `editMessageText` с тем же содержимым → Telegram отвечает «message not modified» → **тишина**.

**Pre-flight:** при INSERT в `ui_screen_buttons` ВСЕГДА указывать `meta = jsonb_build_object('target_screen', '<screen_id>')` для навигационных кнопок.

```sql
INSERT INTO ui_screen_buttons (..., meta)
VALUES (..., jsonb_build_object('target_screen', 'my_plan_settings'));
```

### Gotcha 2 — двойной эмодзи из icon_const_key + text_key

**Как renderer строит text кнопки:**

```python
# services/template_engine.py:_build_button_text
text = _resolve_text(text_key, translations, {}, constants)  # «⚙️ Configurar plan»
if icon_const_key and constants.get(icon_const_key):
    text = constants[icon_const_key] + ' ' + text             # «⚙️ » + «⚙️ Configurar plan»
```

Если translation value уже содержит emoji — renderer добавляет ещё один через `icon_const_key`. Юзер видит `⚙️ ⚙️ Configurar plan`.

**Правило:** при создании headless buttons **проверять существующий pattern** для аналогичных кнопок:

```sql
-- Посмотреть как сделаны соседи
SELECT text_key, icon_const_key FROM ui_screen_buttons
WHERE callback_data LIKE 'cmd_%' AND screen_id = '<parent>';
```

Если у соседних кнопок `icon_const_key` задан, а в `ui_translations` text **без emoji prefix** — значит pattern «emoji from constants only». Тогда новая кнопка тоже: text без emoji + icon_const_key.

**Fix при обнаружении:** strip emoji prefix из `ui_translations` для всех 13 языков:

```sql
UPDATE ui_translations
SET content = jsonb_set(content, '{buttons,configure_plan}',
    to_jsonb(ltrim(content->'buttons'->>'configure_plan', '⚙️ '))::jsonb)
WHERE lang_code = '<lang>';
```

### Gotcha 3 — FSM hardcoded screen_id при перемещении кнопки

`process_onboarding_input` содержит hardcoded `RETURN render_screen(p_telegram_id, 'my_plan')` в ветках `cmd_back` и `cmd_quiz_continue` для status='edit_phenotype'. Когда entry-point кнопка `cmd_edit_phenotype` переехала из `my_plan` → `my_plan_settings` (mig 271), FSM-handler продолжал возвращать к `my_plan`. Back-навигация ломалась (cmd_back из quiz → my_plan вместо my_plan_settings).

**Fix:** surgical edit в `process_onboarding_input` через `pg_get_functiondef` + REPLACE (mig 273). Idempotency guard через `position('marker' IN v_body) > 0`.

**Pre-flight при перемещении кнопок между экранами:**

1. `grep -n '<callback_data>' migrations/*.sql` — найти все мигриции упоминающие callback
2. `pg_get_functiondef` всех RPC упоминающих screen_id — проверить hardcoded returns
3. Если найден hardcoded `render_screen('<old_parent>')` → surgical edit в миграции

### Gotcha 4 — копируешь cb_data → копируй meta (mig 318 trap)

При повторном использовании готовой команды (например `cmd_delete_last`, `cmd_show_meals`) на новом экране через `INSERT INTO ui_screen_buttons` или `UPDATE callback_data = '<existing_cmd>'` — **обязательно** скопируй `meta` из существующей записи. Иначе:

- `dispatch_with_render` находит callback по `(screen_id, callback_data)` но `meta = '{}'`
- COALESCE chain не находит ни `save_via_callback`, ни `target_screen`
- → fallback: re-render current screen → Telegram `editMessageText` `400 message is not modified`
- → юзер видит «кнопка ничего не делает»

**Lesson** mig 318 (2026-05-24): col 1 stats_main был `cmd_show_meals` (no-op stub), я поменял на `cmd_delete_last` БЕЗ копирования meta. На `_global_floating_actions` тот же `cmd_delete_last` имеет полный meta:
```json
{"save_rpc": "delete_last_meal_with_revert",
 "target_screen": "delete_confirmed",
 "save_via_callback": true}
```

На моей `stats_main` записи `meta` остался `{}` → silent fail. Воспроизвели 4× в живых логах с интервалом ~секунда.

**Pre-flight перед `INSERT/UPDATE callback_data`:**

```sql
-- 1. Найти все существующие использования cmd_X
SELECT screen_id, meta FROM ui_screen_buttons WHERE callback_data = '<cmd>';
-- 2. Если в каком-то meta заполнен — копируй ТОТ ЖЕ meta в свой INSERT/UPDATE
-- 3. Если у тебя дублирование — расширь миграцию comment'ом «meta copied from <screen> per gotcha 4»
```

### Gotcha 5 — visible_condition забыли расширить (mig 322 trap)

При удалении соседних кнопок ВСЕГДА re-check `visible_condition` оставшихся кнопок в том же ряду / экране. Условия часто были написаны в predicate-form «когда нужна ЭТА кнопка, а не ТА» — после удаления «той» condition остаётся истинным только в узком случае.

**Lesson** mig 321 → 322 (2026-05-24): stats_main row 0 col 0 `[Исправить]` имела:
```sql
visible_condition: (SELECT COUNT(*) FROM food_logs ... CURRENT_DATE) = 1
```
Условие = «показывать только если ровно 1 приём пищи сегодня». Изначальный n8n design: col 1 `cmd_show_meals` handled multi-meal case. После удаления col 1 (mig 321) → multi-meal юзеры видели пустую строку без любых кнопок.

**Fix** (mig 322): `= 1` → `>= 1`. Одно изменение, мгновенный эффект (visible_condition резолвится на каждый render, без кеша).

**Pre-flight перед DELETE из ui_screen_buttons:**

```sql
-- 1. Перед удалением — посмотри visible_condition СОСЕДНИХ кнопок
SELECT row_index, col_index, callback_data, visible_condition
FROM ui_screen_buttons WHERE screen_id = '<screen>' ORDER BY row_index, col_index;
-- 2. Любое условие со скоупом «другая кнопка отсутствует» — потенциальный сломанный после твоего DELETE
```

## Чек-лист (для копирования в commit message)

```
[ ] meta.target_screen задан в INSERT ui_screen_buttons
[ ] text_key в ui_translations НЕ содержит emoji если icon_const_key задан (check pattern соседних кнопок)
[ ] grep по FSM-функциям (process_user_input, process_onboarding_input) — нет hardcoded render_screen('<old_parent>') для перемещённых кнопок
[ ] PROFILE_V5_CALLBACKS в dispatcher/router.py содержит новый callback
[ ] Live test: клик кнопки → ожидаемый экран (не re-render текущего)
[ ] Если копирую существующий callback_data — meta скопирован (Gotcha 4)
[ ] Если удаляю кнопку — re-check visible_condition соседних в том же ряду (Gotcha 5)
```

## Related Concepts

- [[concepts/headless-architecture]] — общая архитектура process_user_input + render_screen
- [[concepts/headless-picker-pattern]] — полный recipe для picker-экранов (включает meta conventions)
- [[concepts/checkmark-prefix-pattern]] — аналогичный pattern icon_const_key vs text_key (checkmark, не emoji)
- [[concepts/n8n-template-engine]] — double-emoji anti-pattern (legacy variant)
- [[concepts/safe-create-or-replace-recipe]] — surgical edit через pg_get_functiondef (Gotcha 3 fix method)

## Sources

- [[daily/2026-05-18.md]] — Mig 271 (Phase B0 my_plan settings submenu) + mig 272 (hotfix: double emoji + dead button) + mig 273 (hotfix: phenotype back nav FSM hardcode). 3 bugs discovered + fixed within 2 hours of deploy, all 3 = pre-flight-checkable.
