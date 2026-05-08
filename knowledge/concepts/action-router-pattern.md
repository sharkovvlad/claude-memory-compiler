---
title: "Action Router Pattern (Code classifier → Switch router)"
aliases: [action-router, code-classifier-switch, route-classifier, onboarding-engine, menu-engine, noms-routing-pattern]
tags: [n8n, architecture, patterns, routing, best-practices]
sources:
  - "daily/2026-04-18.md"
created: 2026-04-18
updated: 2026-04-18
---

# Action Router Pattern

Стандартный паттерн роутинга в NOMS: **Code node (1 output) классифицирует запрос → Switch node (≤11 outputs) физически разделяет поток**. Применяется в 3 ключевых местах проекта: `Route Classifier` в 01_Dispatcher, `Onboarding Engine` в 02_Onboarding_v3, `Menu Engine` в 04_Menu (с 2026-04-18). Этот паттерн избегает багов больших Switch'ей (>15 outputs, duplicate outputKey) и предоставляет самодокументируемый граф.

## Key Points

- **Code node всегда 1 output.** Никогда не используй `numberOutputs > 1` — это против конвенции NOMS и n8n validator отклоняет `return [[item], [], ...]` signature
- **Switch node v3.4 — физический разделитель.** Матчит по полю которое Code поставил в `$json` (`route_target`, `action`, `menu_route`)
- **Sub-Router Switch для деталей.** Если Action Router имеет слишком много подкатегорий внутри одного action type — добавь Sub-Router Switch с полем `target_node`
- **≤8 outputs на Switch — safe zone.** Main Router в 01_Dispatcher работает с 11 outputs стабильно; идеально держать ≤8 для читаемости
- **Unique outputKey строго обязателен.** Дубликат outputKey в Switch v3.4 смещает все последующие rules (см. [[concepts/n8n-switch-duplicate-outputkey-bug]])

## Details

### Паттерн в 3 workflows NOMS

#### 1. `01_Dispatcher > Route Classifier → Main Router` (11 outputs)

Макро-роутинг по бизнес-модулям:

```javascript
// Route Classifier (Code, 1 output)
const user = $json;
// ... 200+ lines of logic
return { json: {...user, route_target: 'menu'|'ai'|'onboarding'|'location'|...} };
```

Main Router (Switch 3.4): 11 rules по `$json.route_target` → 11 downstream workflows.

#### 2. `02_Onboarding_v3 > Onboarding Engine → Action Router` (6 outputs)

Action-based роутинг по типу технического действия:

```javascript
// Onboarding Engine (Code, 1 output)
const result = {
  action: 'send_only' | 'rpc_then_send' | 'completion' | 'language_save' | 'status_and_send' | 'location',
  rpc_url: 'set_user_gender',
  rpc_body: {...},
  telegram_payload: {...},
  // ... context for downstream handlers
};
return [{ json: result }];
```

Action Router (Switch 3.4): 6 rules по `$json.action` → 6 generic handlers. Каждый handler читает payload (`rpc_url`, `telegram_payload`, etc) и действует.

#### 3. `04_Menu > Menu Engine → Action Router → Sub-Routers` (2-уровневая иерархия, с 2026-04-18)

Для 28 команд меню — двухуровневое разделение:

```javascript
// Menu Engine (Code, 1 output)
const ROUTING_MAP = {
  'profile':        { action: 'render_screen',     target_node: 'profile' },
  'shop':           { action: 'rpc_fetch_render',  target_node: 'shop' },
  'phenotype_quiz': { action: 'rpc_fetch_render',  target_node: 'phenotype_quiz' },
  'skip_meal':      { action: 'rpc_mutate',        target_node: 'skip_meal' },
  // ... 28 total
};
const routing = ROUTING_MAP[menu_route];
return [{ json: {...d, action: routing.action, target_node: routing.target_node} }];
```

Action Router (Switch 3.4): 7 outputs по `$json.action`.
Sub-Routers (Switch 3.4): для каждого action с multiple target_nodes — отдельный Sub-Router (≤8 outputs по `$json.target_node`).

Итоговая топология:
```
Menu Engine → Action Router (7)
                ├── render_screen      → Render Sub-Router (3)       → existing nodes
                ├── rpc_fetch_render   → RPC Fetch Sub-Router (8)    → existing nodes
                ├── rpc_mutate         → RPC Mutate Sub-Router (5)   → existing nodes
                ├── sub_workflow       → Sub-Workflow Sub-Router (4) → existing nodes
                ├── edit_picker        → Parse Edit Command (direct)
                ├── nav_back           → Back Nav (direct)
                └── terminal_ack       → Terminal Sub-Router (5)     → existing nodes
```

### Как добавить новую команду в 04_Menu

**3 шага:**

1. **Command Classifier** (уже существующая Code node): добавить route
   ```javascript
   else if (command === 'cmd_new_feature') {
     route = 'new_feature';
   }
   ```

2. **Menu Engine ROUTING_MAP**: определить action type + target_node
   ```javascript
   'new_feature': { action: 'rpc_fetch_render', target_node: 'new_feature' },
   ```

3. **Соответствующий Sub-Router**: добавить rule
   ```javascript
   // в RPC Fetch Sub-Router (Switch 3.4)
   { leftValue: "={{ $json.target_node }}", rightValue: "new_feature", outputKey: "new_feature" }
   ```
   + connection к downstream handler ноде.

**НЕ нужно трогать** Action Router Switch — он уже имеет все нужные 7 outputs для action types.

### Code node — правильный syntax

**Всегда single output**, используй явное массив-wrapping:
```javascript
return [{ json: result }];
// или
return [{ json: {...input, new_field: value} }];
```

**НЕ** используй:
```javascript
// ❌ Multi-output — против конвенции NOMS
return [[{json: item}], [{json: item}], ...];

// ❌ numberOutputs > 1 — n8n validator отклоняет
```

**mode:** `runOnceForAllItems` — для классификаторов (один item → один item).

### Action types: стандартные для NOMS

| Action | Семантика | Handler pattern |
|--------|-----------|-----------------|
| `render_screen` | Локальный рендер UI (нет RPC) | Build X Text + Typing Action → Edit/Send |
| `rpc_fetch_render` | GET из БД + рендер | RPC Get X → Build X Text → Edit/Send |
| `rpc_mutate` | POST/PATCH в БД (fasting, save) | RPC Call → result toast/ack |
| `sub_workflow` | Передать управление другому workflow | Prepare for N → executeWorkflow |
| `edit_picker` | Общий edit flow для cmd_edit_* | Parse Edit Command → Build Ask Markup |
| `nav_back` | Универсальный Back via nav_stack | Back Nav RPC → Back Target Router |
| `terminal_ack` | Ack без дальнейшего flow | Answer callback / simple send |

**Семантика из 02_Onboarding_v3 Action Router** (чуть другая):
- `send_only`, `rpc_then_send`, `completion`, `language_save`, `status_and_send`, `location`

Action types всегда **привязаны к своему workflow** — в каждом workflow свой набор actions. Не унифицировать между workflows (разные контексты).

### Почему не один большой Switch (28 outputs)

Был **антипаттерн** в 04_Menu до 2026-04-18: Menu Router Switch с 28 rules. Проблемы:
1. **Duplicate outputKey** легко возникает при копировании rule-template (см. [[concepts/n8n-switch-duplicate-outputkey-bug]])
2. **Runtime cache issues** — n8n Cloud может держать stale slot mapping, deactivate/activate не всегда помогает
3. **Трудно читать** — 28 rules в одном Switch не self-documenting, в отличие от `Action Router (7) → Sub-Router (5)`
4. **Трудно добавлять** — новая команда требует редактирования 28-output Switch, риск ошибки высок
5. **Stale base PUT** — чем больше Switch, тем больше шанс что параллельный агент перезатрёт

### Миграция 04_Menu (2026-04-18)

Была: `Command Classifier → Menu Router Switch (28 outputs) → 28 downstream`
Стала: `Command Classifier → Menu Engine Code → Action Router Switch (7) → 5 Sub-Routers → 28 downstream`

**Downstream nodes НЕ меняются** — только роутер. Это важно т.к.:
- Меньше риск
- Параллельные агенты не задевают
- Rollback элементарный

### Ограничения паттерна

- **Sub-Routers делают граф глубже** — на 1 уровень (для случаев много target_nodes). В 04_Menu — acceptable, в простых workflows не нужно.
- **ROUTING_MAP в коде, не в БД** — для config-driven подхода см. **Variant 3 (planned)**: вынести в таблицу `ui_screens` + `ui_commands`.
- **Нельзя легко изменить action type команды в runtime** — только через PUT Code node. Config-driven решает и это.

## Related

- [[concepts/n8n-switch-duplicate-outputkey-bug]] — баг больших Switch'ей, причина миграции
- [[concepts/n8n-multi-agent-workflow-editing]] — PUT protocol, stale base
- [[concepts/n8n-data-flow-patterns]] — общие принципы потоков в n8n
- [[concepts/phenotype-quiz]] — фича активированная через Action Router
- [[concepts/nav-stack-architecture]] — `nav_back` action type использует Back Nav RPC

## Sources

- [[daily/2026-04-18.md]] — миграция 04_Menu Menu Router → Action Router, причины, timeline
