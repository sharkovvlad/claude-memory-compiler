---
title: "Multi-Agent n8n Workflow Editing Protocol"
aliases: [stale-base-put, concurrent-workflow-modification, fresh-get-before-put, put-protocol]
tags: [n8n, api, patterns, defensive-coding, multi-agent, bugs]
sources:
  - "daily/2026-04-18.md"
created: 2026-04-18
updated: 2026-04-19
---

# Multi-Agent n8n Workflow Editing Protocol

В проекте NOMS несколько агентов параллельно редактируют n8n workflows через API PUT. Без дисциплины — классические stale base проблемы: один агент затирает фиксы другого. Этот документ — обязательный протокол для всех агентов, которые делают PUT.

## Key Points

- **Всегда `GET /workflows/{id}` прямо ПЕРЕД PUT.** Не из начала сессии, не 5 минут назад, не после длинной цепочки операций — именно last-moment fresh snapshot.
- **Проверять `updatedAt` и `versionId` между GET и PUT.** Если между твоим GET и PUT прошло время (>10 сек) — повторный GET для проверки что никто не вклинился.
- **Diff'ы ВСЕГДА формировать от актуальной live версии.** Никогда от кэшированного snapshot из начала сессии.
- **Stale base PUT затирает фиксы.** Если ты базируешься на старом snapshot — твой PUT перезапишет все изменения сделанные другими агентами между твоим GET и PUT.
- **При обнаружении concurrent modification — re-plan.** Не применять свой diff слепо на новой базе — сначала проверить что твои изменения совместимы с изменениями параллельного агента.

## Details

### Реальный incident (2026-04-18)

Timeline:
- **08:04:07 UTC** — Agent A (этот) делает PUT: fix Rule[21] dedupe в Menu Router (outputKey='skip_meal' вместо дубликата 'back')
- **08:07:16 UTC** — Agent B (параллельный) делает PUT: добавляет Delete Account фичу (6 новых нод + 2 rules). **Но на основе GET сделанного ДО 08:04** → его diff не знал про мой dedupe fix → PUT затёр Rule[21] обратно к дубликату
- **08:05:12 UTC** — user нажал «Пройти тест», в этот момент мой фикс был активен (08:04-08:07 window). Но юзер увидел баг потому что Telegram UI cache / delay
- **08:21:40 UTC** — Agent A видит что «фикс не работает», применяет IF bypass как workaround (Variant A)

Root cause: **Agent B использовал стейл GET** от времени до моего PUT. Его diff был корректен относительно его базы, но применённый к более новой базе — перезаписал мои изменения.

### Обязательный PUT protocol

```python
import time

def safe_put_workflow(wf_id, api_key):
    # Step 1: Fresh GET
    live = GET(f"/workflows/{wf_id}")
    my_base_updated_at = live['updatedAt']
    my_base_version = live['versionId']
    
    # Step 2: Apply modifications to the live snapshot (NOT to stale copy)
    modified = apply_my_changes(live)
    
    # Step 3: Pre-flight concurrent modification check
    latest = GET(f"/workflows/{wf_id}")
    if latest['updatedAt'] != my_base_updated_at:
        raise ConcurrentModificationError(
            f"Workflow modified between my GET and PUT: "
            f"base={my_base_updated_at}, latest={latest['updatedAt']}. "
            f"Re-GET and re-plan."
        )
    
    # Step 4: Deactivate → PUT → Activate
    deactivate(wf_id)
    put_response = PUT(f"/workflows/{wf_id}", modified)
    time.sleep(1)  # rate limit guard
    activate(wf_id)
    
    return put_response['versionId']
```

### Что делать при concurrent modification detected

**НЕ применять свой diff слепо** на новой базе. Нужно:

1. **Скачать новую live версию** (`/tmp/live_fresh.json`)
2. **Посмотреть что изменилось:**
   ```python
   new_names = {n['name'] for n in fresh['nodes']}
   old_names = {n['name'] for n in my_base['nodes']}
   added = new_names - old_names
   removed = old_names - new_names
   ```
3. **Проверить пересечение** с моими изменениями. Если параллельный агент трогал те же ноды что и я — нужно merge manually, не auto-patch.
4. **Re-apply мой diff** только если он не конфликтует с новым содержимым.

### Симптомы концуррентной модификации

- `updatedAt` изменился между моим GET (начало работы) и моим PUT
- Node count изменился
- Появились новые ноды с именами которых не было
- Мой фикс «работал секунды назад» → «снова не работает»
- В Menu Router появились новые rules с незнакомыми `rightValue`

### Коммуникация между агентами

Если несколько агентов работают параллельно над одним workflow:

1. **Не монополизировать workflow.** Каждая сессия должна быть короткой — deactivate → patch → PUT → activate → выйти.
2. **Не откладывать между GET и PUT.** Чем короче окно — тем меньше риск конфликта.
3. **Не делать «длинные цепочки» модификаций** с промежуточными PUT без re-GET. Каждый PUT должен начинаться с fresh GET.
4. **Fixes + features отдельно.** Не смешивать архитектурные рефакторинги с мелкими фиксами — это растягивает окно PUT и увеличивает риск конфликта с другим агентом.

### Техническая детализация

**Почему n8n Cloud не защищает от этого:** n8n API PUT не поддерживает optimistic locking (`If-Match: <versionId>` header). Любой агент может PUT в любой момент — сервер всегда применяет. Ответственность полностью на клиенте.

**Почему даже deactivate/activate не спасает от stale base:** эти операции сбрасывают runtime state, но не проверяют что клиентская база актуальна. PUT всегда применяет body → workflow на сервере становится равен клиентскому body.

**Почему timestamp `updatedAt` — надёжный индикатор:** n8n автоматически обновляет его при каждом успешном PUT. Если `updatedAt` изменился — значит произошёл хотя бы один PUT от кого-то другого.

## Checklist для агентов

Перед каждым PUT workflow:

- [ ] GET `/workflows/{id}` прямо сейчас (не более 30 секунд назад)
- [ ] Применяю diff на **полученной** live версии, не на кэше
- [ ] Перед PUT: повторный GET → сверяю `updatedAt` со стартовым
- [ ] `updatedAt` изменился? → re-plan, не PUT
- [ ] После PUT: проверяю `updatedAt` в ответе → соответствует моему diff
- [ ] Логирую `versionId` до/после для возможности отката

### Клонирование workflow не обходит cache (Variant B, Session 2, 2026-04-18)

Отдельный агент проверил гипотезу: если создать новый workflow через POST `/workflows` (clone), новый workflow_id даст чистый cache namespace → сломанный Switch заработает.

**Результат: гипотеза опровергнута.**

Ключевые выводы:

1. **POST `/workflows` сохраняет node UUIDs 1:1.** Все поля `id` внутри `nodes[]` копируются из источника. n8n не регенерирует UUID при клонировании через API.

2. **Runtime cache Switch v3.4 привязан к node UUID, не к workflow ID.** Клон `LgoqJtuosQxQ4PWo` — новый workflow_id, но старый node UUID `menu-router-5690fc82` → тот же битый кэш. Items ушли в `main[23]` (shift -4) вместо `main[27]` — тот же класс бага что в оригинале.

3. **callerPolicy при клонировании через API.** POST создаёт workflow с `settings.callerPolicy = 'workflowsFromSameOwner'` (из источника или default). Это блокирует вызов от Dispatcher, созданного через UI (другой owner scope). **Обязательно делать** дополнительный PUT с `settings.callerPolicy = 'any'` перед активацией.

4. **Единственное надёжное решение** — создавать **новые ноды** (новые UUIDs), а не клонировать существующие. Action Router pattern (полная замена Menu Router Switch на новые ноды с новыми UUIDs) именно поэтому сработал там, где clone + PUT не сработали.

5. **Сдвиг значения shift между попытками.** В попытках 4-7: всё в `main[0]` (shift -27). В Variant B: `main[23]` (shift -4). Deactivate/activate циклы частично обновляют кэш, но не сбрасывают его полностью — это указывает на многоуровневое кэширование в n8n Cloud.

**Последовательность при необходимости clone:**

```python
# Шаг 1: Получить source workflow
source = GET(f"/workflows/{source_id}")

# Шаг 2: Регенерировать UUIDs нод (обязательно для cache-safe clone)
import uuid
for node in source['nodes']:
    node['id'] = str(uuid.uuid4())

# Шаг 3: POST clone с явным callerPolicy
source['settings']['callerPolicy'] = 'any'
clone = POST("/workflows", body=source)

# Шаг 4: Проверить callerPolicy в ответе
assert clone['settings']['callerPolicy'] == 'any'
```

## Связанные файлы

- `/tmp/04_pre_integration.json` — снимок базы до PUT (для отката)
- `/tmp/04_final.json` — снимок после PUT (для верификации)
- `/tmp/04_menu_v2_created.json` — Variant B clone response (workflow `LgoqJtuosQxQ4PWo`)
- `/tmp/exec_9394.json` — Variant B smoking gun execution (cache bug в клоне)

## Related

- [[concepts/n8n-switch-duplicate-outputkey-bug]] — именно stale base PUT откатил dedupe фикс; Variant B node UUID cache insight
- [[concepts/n8n-subworkflow-contract]] — PUT API allowed fields, `{name, nodes, connections, settings}` whitelist
- [[concepts/phenotype-quiz]] — реальный инцидент где обнаружили этот паттерн; Variant B session
- [[concepts/action-router-pattern]] — архитектурное решение через новые ноды (чистые UUID)

## Sources

- [[daily/2026-04-18.md]] — детали инцидента 08:04 → 08:07 stale base PUT откатил Rule[21] dedupe; Session 2 Variant B: clone callerPolicy, node UUID cache binding
