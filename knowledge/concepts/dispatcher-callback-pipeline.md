---
title: "Dispatcher Callback Pipeline"
aliases: [callback-pipeline, if-select-callback, paired-items, cb-msg-id, template-engine-phase4]
tags: [n8n, dispatcher, callbacks, bugs, architecture]
sources:
  - "daily/2026-04-15.md"
created: 2026-04-15
updated: 2026-04-15
---

# Dispatcher Callback Pipeline

Система передачи данных callback_query через Dispatcher (01_Dispatcher) в 04_Menu. После цепочки нод с IF и HTTP Request референсы на `$('Telegram Trigger')` ломаются из-за n8n paired items. Template Engine Phase 4 фиксирует это, сохраняя callback data в pipeline `$json`.

## Key Points

- **Корневая причина ломки:** `$('Telegram Trigger').item.json` возвращает `undefined` для callbacks, прошедших через `IF Select Callback output[1]` — n8n paired items ломают cross-node reference через IF-ноды
- **Template Engine Phase 4:** извлекает `_cb_data`, `_cb_msg_id`, `_cb_query_id`, `_tg_message` через `$('IF Select Callback').first().json` и сохраняет в `$json` для всех downstream нод
- **Route Classifier v1.7:** `callback = $json._cb_data || telegram.callback_query?.data || ''` — читает из pipeline, не из `$('Telegram Trigger')` напрямую
- **`_cb_msg_id` fallback ОБЯЗАН быть `''` (пустая строка), НИКОГДА `0`** — `stringValue` тип конвертирует `0` → `"0"` → `notEmpty` = true → Is Callback? маршрутизирует reply-кнопки в editMessageText с message_id="0" → Telegram 400
- **`message` objectValue fallback ОБЯЗАН быть `|| {}`** — для callback_query `$json.message` = undefined → n8n сериализует как невалидный JSON → Execute Workflow падает с "JSON parameter needs to be valid JSON"

## Details

### Цепочка нод в Dispatcher и где ломается reference

Полная цепочка обработки callback_query в Dispatcher:

```
Telegram Trigger
    → Is Callback? (IF)                    ← output[0] для callback_query
    → Answer Callback (Telegram node)      ← теряет pairedItem
    → IF Select Callback (IF)              ← output[1] для всего кроме cmd_select_*
    → Template Engine (Code)               ← здесь нужно читать callback data
    → Get User Context (HTTP Request)      ← заменяет $json данными из БД
    → Route Classifier (Code)              ← тут $('Telegram Trigger') ломается
    → Prepare for 04 (Set)                 ← тут тоже
```

Проблема: после `IF Select Callback output[1]` n8n теряет pairedItem. Далее `Get User Context` (HTTP Request) заменяет `$json` данными Supabase. К моменту когда Route Classifier читает `$('Telegram Trigger').item.json.callback_query?.data` — reference невалиден, возвращает undefined.

Это ломало все non-`cmd_select_*` callbacks: `cmd_speed_*`, `cmd_start_phenotype_quiz`, и потенциально другие.

### Template Engine Phase 4: сохранение callback data

Phase 4 добавлена в конец Template Engine (Code ноды), которая выполняется ДО Get User Context:

```javascript
// Phase 4: Preserve callback data in pipeline
const cbSource = (() => {
  try { return $('IF Select Callback').first().json; } catch(e) {}
  try { return $('Telegram Trigger').first().json; } catch(e) {}
  return {};
})();

const cbQuery = cbSource.callback_query || {};
_cb_data     = cbQuery.data || '';
_cb_msg_id   = cbQuery.message?.message_id ?? '';  // ОБЯЗАН быть '' не 0
_cb_query_id = cbQuery.id || '';
_tg_message  = cbQuery.message || cbSource.message || {};
```

После Phase 4 эти поля доступны через `$json._cb_data`, `$json._cb_msg_id` и т.д. во всех downstream нодах — включая Route Classifier и Prepare for 04.

### Route Classifier v1.7

```javascript
// Строка 13 — читает из pipeline, не из Telegram Trigger напрямую
const callback = $json._cb_data || (() => {
  try { return $('Telegram Trigger').first().json?.callback_query?.data || ''; } catch(e) { return ''; }
})();
```

Fallback на `$('Telegram Trigger')` обёрнут в try/catch — ломает gracefully, не крашит весь Route Classifier.

### Prepare for 04 — обновлённые поля

После Phase 4 fix нода "Prepare for 04" читает из pipeline:

| Поле | Выражение | Было |
|------|-----------|------|
| `command` | `$json._cb_data \|\| $('Telegram Trigger').item.json.callback_query?.data \|\| ''` | `$('Telegram Trigger').item.json.callback_query?.data` |
| `callback_message_id` | `$json._cb_msg_id \|\| ''` | `$json._cb_msg_id \|\| 0` ⛔ |
| `callback_query_id` | `$json._cb_query_id \|\| ''` | прямой reference |
| `message` | `$json.message \|\| {}` | `$json.message` ⛔ |

Также добавлены 4 новых поля из v_user_context: `training_type`, `goal_speed`, `phenotype`, `target_weight_kg`. Итого: 36 полей (было 32).

### Критические правила fallback

**Правило 1: `_cb_msg_id` и `callback_message_id` — fallback ОБЯЗАН быть `''`**

Инцидент 15 апреля: агент установил `_cb_msg_id` fallback = `0`. Dispatcher Set node (тип `stringValue`) конвертирует число `0` в строку `"0"`. Строка `"0"` ≠ пустая строка → `notEmpty` check = true → Is Callback? в 04_Menu маршрутизирует reply-кнопки (Мой день, Профиль, Прогресс) в ветку `editMessageText` с `message_id="0"` → Telegram возвращает 400 → тишина, ответ не приходит.

**Правило 2: `message` objectValue — fallback `|| {}`**

Для callback_query в Telegram webhook `$json.message` = `undefined` (message является частью `callback_query.message`, не верхнего уровня). n8n Set node с типом `objectValue` сериализует `undefined` как невалидный JSON. Execute Workflow нода при попытке передать этот payload падает с "JSON parameter needs to be valid JSON".

Оба правила задокументированы в CLAUDE.md в секции "Защищённые поля Dispatcher".

### Early Typing Action

Параллельно с Template Engine Phase 4 в Dispatcher добавлена нода `Early Typing Action` — HTTP Request fire-and-forget dead-end, подключённая параллельно от Telegram Trigger. Пользователь видит "typing..." через ~50ms вместо ~1с (раньше typing action был в 04_Menu, после всей цепочки Dispatcher).

## Related Concepts

- [[concepts/n8n-data-flow-patterns]] — правило #9: `$('Telegram Trigger')` ломается через IF-ноды; fix через pipeline
- [[concepts/n8n-stateful-ui]] — `callback_message_id`, Is Callback? pattern, editMessageText
- [[concepts/n8n-performance-optimization]] — Early Typing Action как параллельная ветка от Telegram Trigger

## Sources

- [[daily/2026-04-15.md]] — Root cause fix: Template Engine Phase 4, Route Classifier v1.7, Prepare for 04 обновление; инцидент `_cb_msg_id=0` → `"0"` ломает reply-кнопки; `message || {}` fallback; Early Typing Action
