---
title: "n8n Switch v3.4 Duplicate outputKey Bug"
aliases: [switch-slot-shift, outputkey-collision, menu-router-misroute, switch-v3-physical-slots]
tags: [n8n, bugs, patterns, routing, switch-node, defensive-coding]
sources:
  - "daily/2026-04-18.md"
  - "daily/2026-04-18-handoff.md"
created: 2026-04-18
updated: 2026-04-19
---

# n8n Switch v3.4 Duplicate outputKey Bug

Критический gotcha n8n Switch node `typeVersion 3.4`: если два rule имеют одинаковый `outputKey`, Switch создаёт только **один физический output slot** для них. Это сдвигает индексы всех последующих rules и ломает маршрутизацию — items уходят в соседние output slots.

## Key Points

- **Switch v3.4 с `renameOutput=true` создаёт output slots по УНИКАЛЬНЫМ `outputKey` values**, НЕ по индексу rule в массиве `rules.values`.
- **Дубликат outputKey → сдвиг -1** для всех rules после него. 1 дубликат = 6 misrouted rules; 2 дубликата = сдвиг -2.
- **Симптом:** items с определённым `menu_route` уходят в неправильную downstream ноду (обычно в соседнюю).
- **Pre-PUT валидатор:** перед любым PUT Switch node с добавлением rule — проверить `Counter([r.get('outputKey') for r in rules]).most_common()` на дубликаты.
- **Renaming через string вместо bool:** `"renameOutput": "custom_name"` — невалидный формат в v3.4, интерпретируется как **дубликат outputKey с шумом**. Всегда `renameOutput: true` + корректный `outputKey`.

## Details

### Как Switch v3.4 создаёт output slots

```javascript
// В JSON workflow schema:
{
  "rules": {
    "values": [
      { "outputKey": "back",   "conditions": {...}, "renameOutput": true },
      { "outputKey": "stats",  "conditions": {...}, "renameOutput": true },
      // ...
      { "outputKey": "back",   "conditions": {rightValue: "skip_meal"}, "renameOutput": "skip_meal" }  // ДУБЛИКАТ!
    ]
  }
}
```

Runtime поведение:
1. Парсер проходит по `rules.values` сверху вниз, собирает distinct `outputKey` в list
2. Создаёт физические output slots = количество distinct outputKey
3. При matching rule возвращает items в slot с индексом `distinct.index(rule.outputKey)`

**Если дубликат:** rules с одинаковым outputKey пишут в один slot. Все rules после первого дубликата имеют `distinct.index()` на -1 меньше чем их позиция в массиве.

### Пример (реальный case 2026-04-18 в Menu Router)

Было:
```
Rule[0]   outputKey='back'
Rule[21]  outputKey='back'  (дубликат, rightValue='skip_meal')
Rule[22]  outputKey='save_speed'
Rule[23]  outputKey='friends_info'
Rule[24]  outputKey='payout'
Rule[25]  outputKey='phenotype_quiz'  (new)
Rule[26]  outputKey='delete_account_init'
Rule[27]  outputKey='delete_account_confirm'
```

Runtime mapping:
| Rule | Slot (по distinct) | connections.main[slot] → | Результат |
|------|--------------------|-----------------------|-----------|
| [0] back | 0 | Back Nav | ✓ |
| [21] skip_meal | 0 (shared с Rule[0]) | Back Nav | ❌ idem в Back Nav |
| [22] save_speed | 21 | Typing Action (Fasting) | ❌ misroute |
| [23] friends_info | 22 | Prepare Speed Save | ❌ misroute |
| [24] payout | 23 | Build Info Text (Friends) | ❌ misroute |
| [25] phenotype_quiz | 24 | Build Payout Screen | ❌ misroute |
| [26] delete_account_init | 25 | Build Delete Confirmation | ❌ misroute (+1 shift) |
| [27] delete_account_confirm | 26 | Check Subscription Blocker | ❌ misroute |
| — | 27 (phantom) | Build Quiz Screen | никогда не получает items |

### Fix (одна строчка)

```diff
{
  "conditions": { "conditions": [{ "rightValue": "skip_meal", ... }] },
- "renameOutput": "skip_meal",
- "outputKey": "back"
+ "renameOutput": true,
+ "outputKey": "skip_meal"
}
```

После фикса:
- 28 distinct outputKey → 28 физических slots
- Каждый rule[N] → slot[N] (соответствует `connections.main[N]`)

### Pre-PUT валидатор (обязателен)

Код-проверка перед PUT любого Switch с множественными rules:

```python
from collections import Counter
import json

wf = json.load(open('workflow.json'))
for node in wf['nodes']:
    if node['type'] == 'n8n-nodes-base.switch':
        rules = node['parameters'].get('rules', {}).get('values', [])
        outputs = [r.get('outputKey') for r in rules]
        dups = {k:v for k,v in Counter(outputs).items() if v > 1}
        if dups:
            raise ValueError(f"Switch '{node['name']}' has duplicate outputKeys: {dups}")
```

### Как это происходит в реальности (anti-pattern)

Typical case — копирование rule через deepcopy при добавлении новой фичи:
1. Агент добавляет новую кнопку (Skip Meal, Delete Account и т.д.)
2. Копирует rule-шаблон соседнего rule в Menu Router
3. **Забывает** обновить `outputKey` — оставляет как у шаблона
4. PUT проходит, workflow активен, но latent bug: новая функция работает рандомно (идёт в чужую ноду)
5. Никто не замечает пока не добавится ещё один rule после — смещение накапливается

### Как выявить существующий баг

Если workflow уже в проде и подозрение на misroute:

```python
# 1. Check for duplicates
Counter([r['outputKey'] for r in rules]).most_common()

# 2. Compare predicted slot vs connections
distinct = []
seen = set()
for k in outputs:
    if k not in seen:
        distinct.append(k); seen.add(k)

for i, ok in enumerate(outputs):
    expected_slot = distinct.index(ok)
    if i != expected_slot:
        print(f"⚠️ Rule[{i}] ({ok}) shifts to slot {expected_slot}")
        conn_at_expected = wf['connections']['Switch Name']['main'][expected_slot]
        print(f"   items for rule[{i}] actually go to: {[t['node'] for t in conn_at_expected]}")
```

### Связанные баги в NOMS (известные на 2026-04-18)

- `10_Payment` → Payment Router: дубликат `outputKey='plans'` в rules `cmd_premium_plans` и `cmd_premium_plans_list` (обнаружено NLM, не фикшено)
- `04_Menu` → Menu Router: Rule[21] `skip_meal` имел `outputKey='back'` — **удалён полностью 2026-04-18** через миграцию на Action Router pattern (см. [[concepts/action-router-pattern]])

### Resolution для 04_Menu (2026-04-18)

**Bug fix через Switch dedupe** не сработал — параллельные агенты делали stale base PUT которые откатывали Rule[21] fix. Даже после успешного dedupe runtime cache держал старый slot mapping.

**Финальное решение:** миграция на Action Router pattern — полная замена Menu Router Switch (28 outputs) на:
- `Menu Engine` Code node (1 output, ROUTING_MAP классификатор)
- `Action Router` Switch (7 outputs, unique outputKey)
- 5 × Sub-Router Switches (≤8 outputs each, unique outputKey)

Это **устранило root cause** — не просто обошло дубликат, но исключило саму возможность такого бага (малые Switch'ы с ≤8 outputs легко проверить на uniqueness).

### Главный урок

**Не множить outputs в одном Switch node.** Если нужно >10 routes:
- Использовать **Code classifier + Switch** pattern (1 output Code возвращает discriminator, Switch разделяет)
- Для сложных случаев (28+) — **2-уровневая иерархия**: Action Router → Sub-Routers
- Каждый Switch ≤8 outputs, все outputKey уникальны
- Pre-PUT validator: `Counter(outputKey).most_common()` — 0 дубликатов обязательно

### Runtime Cache Total Failure (more severe form)

Более тяжёлая форма бага наблюдалась 2026-04-18 после нескольких PUT-попыток на одном workflow. Switch **полностью перестал проверять `rightValue`** — ВСЕ items шли в `main[0]` независимо от action value.

**Симптом:** executions 9324–9342 — user нажал «Квесты», `Menu Engine` выставил `action='rpc_fetch_render'`, Action Router Rule[1] имел `rightValue='rpc_fetch_render'` (уникальный outputKey) — но items пришли в `main[0]` (Render Sub-Router).

**Отличие от slot-shift:** slot-shift предсказуем (сдвиг -N). Total failure — 100% попадание в `main[0]` для любого input, даже при правильно уникальных outputKey.

**Причина:** накопление stale runtime state после 5+ PUT операций с частичными rollback'ами. Один deactivate/activate цикл не всегда сбрасывает этот кэш.

**Решение:** если deactivate/activate не помогает — clone workflow (новый execution context без накопленного stale state). В NOMS проблема была решена через полную замену Menu Router на Action Router pattern (новые ноды = чистый кэш).

**Диагностика:** если slot-shift объясняет часть misroutes (предсказуемый паттерн), а полный routing failure объясняет все misroutes (всё в main[0]) — это total failure. Нужно создать новый workflow или добавить совершенно новые Switch ноды, а не фиксить rules в существующих.

### Прецеденты

Баг в `04_Menu` Menu Router появился 2026-04-13 при добавлении фичи Fasting (migration 057). Агент копировал template rule, забыл поменять `outputKey` и `renameOutput`. **Не был замечен полмесяца** потому что:
- Skip Meal button редко жмётся юзерами  
- Items уходят в `Back Nav` (shared slot) — что рендерит fallback экран, выглядит как нормальное поведение «Назад в меню»

Накопительный эффект (2026-04-13 → 2026-04-18): добавление новых rules (friends_info, payout, delete_account_*, phenotype_quiz) постепенно ломало всё больше функций из-за shift.

### Variant B: клон workflow не решает проблему (Session 2, ~12:00 UTC 2026-04-18)

После успешного деплоя Action Router pattern (итерация 7) отдельный агент провёл исследовательскую сессию — проверить гипотезу что runtime cache привязан к workflow ID.

**Гипотеза:** новый workflow ID = новый cache namespace → Switch работает чисто.

**Что сделано:** POST `/workflows` → clone `04_Menu` → новый `workflow_id = LgoqJtuosQxQ4PWo` (versionId `ee216eaf`). Все 135 нод, все connections, все credentials — идентичны оригиналу.

**Проблема #1 (устранена):** `SubworkflowPolicyDenialError` — клон унаследовал `callerPolicy: 'workflowsFromSameOwner'`, который блокировал вызов от Dispatcher. Fix: PUT клона с `settings.callerPolicy = 'any'`.

**Проблема #2 (blocker):** тот же баг воспроизвёлся. Execution 9394: `cmd_start_phenotype_quiz` → Menu Router → `main[23]` (Friends Info) вместо `main[27]`. Shift = -4.

```
Menu Router (clone LgoqJtuosQxQ4PWo) → out[23] ❌ (должен быть out[27])
JSON структура клона идеальна — 0 дубликатов, connections.main[27] → Build Quiz Screen ✓
```

**Ключевой инсайт:** POST клонирования **сохраняет node UUIDs 1:1**. Node `menu-router-5690fc82` в клоне имеет тот же `id` что и в оригинале → runtime cache привязан к **UUID ноды**, не к workflow ID.

**Поведение shift изменилось:** в попытках 4-7 все items шли в `main[0]` (shift = -27). В Variant B items пошли в `main[23]` (shift = -4). Это означает что deactivate/activate циклы **частично обновляют** кэш, но не сбрасывают его полностью.

**Итог:** гипотеза опровергнута. Rollback за 3 минуты — деактивировать клон, активировать оригинал, вернуть Dispatcher workflowId.

**Урок 5 (новый):** Cache bug Switch v3.4 в n8n Cloud привязан к **node UUID**, не к workflow ID. Клонирование без регенерации node UUIDs не помогает.

**Урок 6 (новый):** При POST `/workflows` обязательно явно указывать `settings.callerPolicy='any'` — default/inherited `workflowsFromSameOwner` блокирует вызов от Dispatcher, созданного через UI (другой owner scope).

Надёжное решение — **создавать новые ноды** (новые UUIDs), а не клонировать существующие. Именно поэтому Action Router pattern (полная замена Menu Router Switch новыми нодами) сработал там, где clone + PUT не сработали.

## Related

- [[concepts/n8n-multi-agent-workflow-editing]] — stale base PUT откатывает фиксы, требование GET-ПЕРЕД-PUT; Variant B: clone callerPolicy issue
- [[concepts/nav-stack-architecture]] — Menu Router rule[0] back критичен для back navigation
- [[concepts/phenotype-quiz]] — задача где баг был обнаружен; Variant B session описана
- [[concepts/n8n-subworkflow-contract]] — PUT API gotchas
- [[concepts/action-router-pattern]] — финальное решение через новые Switch-ноды (новые UUIDs)

## Sources

- [[daily/2026-04-18.md]] — Phase 2 phenotype_quiz deploy: обнаружение бага, первый фикс (rule[21] dedupe) откатился параллельным агентом, повторный фикс через MenuRouter integration; Session 2 Variant B: clone workflow эксперимент, node UUID cache insight
