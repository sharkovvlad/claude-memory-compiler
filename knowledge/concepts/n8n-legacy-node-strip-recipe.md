---
title: "n8n Legacy Node Strip Recipe — хирургическое удаление фиче-нод из live workflow"
aliases: [n8n-strip, legacy-strip, node-strip-recipe, phenotype-strip, cutover-strip]
tags: [n8n, architecture, operational, cutover, python-migration]
sources:
  - "daily/2026-05-10.md"
created: 2026-05-10
updated: 2026-05-10
---

# n8n Legacy Node Strip Recipe

Операционный recipe для хирургического удаления feature-specific нод из live n8n workflow после переноса фичи в Python headless. Впервые применён 2026-05-10 при strip'е 6 phenotype-quiz нод из `04_Menu` (PR #39). Шаблон переиспользуется для будущих strip'ов (Add food / AI Engine / Payment legacy).

## Key Points

- **Strip = удаление legacy n8n нод** после того как Python authoritative handler полностью обслуживает фичу. Legacy ноды — мёртвый код, но их присутствие (a) мешает replay headless-миграций (`{icon_X}` placeholder'ы не резолвятся legacy JS), (b) создаёт ложный fallback-путь
- **Dangling executeWorkflow refs** блокируют PUT в n8n 2.17.7+. Перед strip — обязательный audit всех `executeWorkflow` нод против существующих workflow. Dead refs → `disabled: true` (минимальный scope)
- **Predictable Python-side cascade** после strip'а: 4 категории fix'ов всегда нужны (status normalization, PROFILE_V5_CALLBACKS, ONBOARDING_STATUSES, template engine resolution)
- **«Strip then replay» pattern**: если headless-миграция была откачена из-за legacy-incompatibility (например `{icon_X}` не резолвится в n8n JS) — strip legacy → replay той же миграции (теперь safe, только Python рендерит)
- **Tooling scripts**: `_strip_<feature>.py` (transform + PUT body builder), `_audit_refs.py` (executeWorkflow validation), `_verify_post.py` (post-PUT sanity check) — сохраняются в репо как шаблон

## Details

### Когда strip'ить

Strip оправдан когда:
1. Python handler **полностью владеет** обработкой фичи (все callbacks → Python through dispatcher)
2. Legacy n8n ноды для фичи **мёртвый код** — callbacks туда больше не роутятся
3. Нужно **разблокировать** headless-миграцию, которая несовместима с legacy renderer'ом (например `{icon_X}` placeholders работают только в Python `_resolve_text`)
4. Legacy ноды создают **ложную безопасность** — кажется что rollback на n8n возможен, хотя Python path уже единственный

Strip НЕ нужен когда:
- Legacy ноды **shared** (используются и другими фичами) — strip удалит чужой код
- Python handler **ещё не обслуживает** 100% callbacks фичи
- Legacy fallback **реально нужен** для staged rollout (Phase 2-style admin-only)

### Recipe (6 шагов)

#### 1. Pre-strip snapshot

```bash
ssh root@89.167.86.20 "KEY=\$(grep N8N_TARGET_API_KEY /home/noms/n8n/compose/.env | cut -d= -f2) && \
  curl -s -H 'X-N8N-API-KEY: '\$KEY http://127.0.0.1:5678/api/v1/workflows/<WF_ID>" \
  > n8n_workflows/_backups/<workflow>_pre_<feature>_strip_$(date +%Y-%m-%d).json
```

Snapshot gitignored (`n8n_workflows/_backups/` в `.gitignore`), но сохраняется локально для rollback.

#### 2. Identify target nodes (feature-specific ONLY)

Классификация нод на **feature-specific** (удаляемые) и **shared** (НЕ удаляемые):

| Категория | Признак | Действие |
|---|---|---|
| **Feature-specific** | Имя содержит feature-slug; НЕ упоминается другими ветками Menu Router/Command Classifier | DELETE |
| **Shared** | Merge Data, Edit Type Router, Build Profile Sub-Screen, Back Target Router — общие для многих фич | НЕ ТРОГАТЬ (dead code paths внутри — harmless) |
| **Router branches** | Command Classifier JS-код, Menu Router outputKey, Edit Type Router outputKey | Удалить только конкретную ветку/case |

Пример (phenotype strip): удалены 6 нод (`Build Quiz Screen`, `Push Nav (Quiz)`, `Is Classify?`, `RPC Classify Phenotype`, `Build Quiz Result`, `Edit Phenotype Screen`), 7 connections. Сохранены 9 shared нод с phenotype-remnants в коде.

#### 3. Audit dangling executeWorkflow refs

```python
existing = {w["id"]: w["name"] for w in GET("/workflows?limit=100")["data"]}
for n in wf["nodes"]:
    if n.get("type") == "n8n-nodes-base.executeWorkflow":
        wid = n["parameters"].get("workflowId")
        if isinstance(wid, dict): wid = wid.get("value")
        if wid not in existing:
            print(f"DEAD: {n['name']} -> {wid}")
```

n8n 2.17.7+ **отклоняет PUT** если хоть одна executeWorkflow нода ссылается на удалённый sub-workflow. Решение для dead ref'ов:

- **`disabled: true`** — если нода unreachable (callback мигрирован в Python). Минимальный scope
- **Update workflowId** — если sub-workflow переименован/пересоздан
- **Удалить ноду** — если путь полностью dead (расширяет scope, отдельный commit)

#### 4. Build PUT body + apply

PUT body whitelist: `{name, nodes, connections, settings}`. Settings whitelist per CLAUDE.md правило 13.

Для workflow > 50 KB — scp на VPS + `curl --data @file`. См. [[concepts/n8n-data-flow-patterns]] секция «Safe PUT recipe».

```bash
scp /tmp/<feature>_strip_body.json root@89.167.86.20:/tmp/
ssh root@89.167.86.20 "KEY=\$(grep N8N_TARGET_API_KEY /home/noms/n8n/compose/.env | cut -d= -f2) && \
  curl -s -X PUT -H 'Content-Type: application/json' -H 'X-N8N-API-KEY: '\$KEY \
  --data @/tmp/<feature>_strip_body.json http://127.0.0.1:5678/api/v1/workflows/<WF_ID>"
```

#### 5. Post-strip verification

4 metric-проверки через GET после PUT:

```python
post = GET(f"/workflows/{wf_id}")
# 1. Feature-specific ноды отсутствуют
assert not any(n["name"] in FEATURE_NODES for n in post["nodes"])
# 2. Router branches удалены
js = next(n for n in post["nodes"] if n["name"] == "Command Classifier")
assert "cmd_phenotype_q" not in js["parameters"]["jsCode"]
# 3. Node/connection count
assert len(post["nodes"]) == expected_count
assert len(sum(c["main"] for c in post["connections"].values() if "main" in c)) == expected_conn
# 4. updatedAt changed
assert post["updatedAt"] != pre_updated_at
```

#### 6. Fix Python-side cascade

**После strip'а legacy нод** callbacks, которые раньше маскировались legacy, теперь проявляют скрытые half-measures в Python. 4 предсказуемых категории fix'ов:

| Категория | Что ломается | Где чинить | Пример (phenotype) |
|---|---|---|---|
| **Status normalization** | `process_onboarding_input` возвращает `render_screen()` без `status` field → handler интерпретирует как error | Handler: backport нормализации `status=None+telegram_ui→render` | gotcha #26 в [[concepts/phase4-onboarding-migration]] |
| **PROFILE_V5_CALLBACKS** | Новый callback не в set → fallthrough в legacy `target=menu` → после strip'а — void | `dispatcher/router.py:PROFILE_V5_CALLBACKS += <new_callback>` | gotcha #27 |
| **ONBOARDING_STATUSES** | Новый FSM-статус не в set → section 4l catch-all перехватывает callback'и раньше section 9 | `dispatcher/router.py:ONBOARDING_STATUSES += <new_status>` | gotcha #29 |
| **Template engine** | `_build_button_text` не резолвит `{icon_X}` → literal в кнопках | `_build_button_text` через `_resolve_text` вместо raw lookup | gotcha #28 |

### «Strip then replay» pattern

Когда headless-миграция (например mig 193 с `{icon_X}` placeholder'ами) **уже была откачена** из-за legacy-incompatibility:

1. **Rollback** (mig 194): regexp_replace удаляет placeholder'ы
2. **Strip** legacy нод (этот recipe)
3. **Replay** той же миграции как mig 195 (теперь safe — только Python рендерит)
4. Идемпотентность replay: `value LIKE '{icon_%'` guard в SQL

### Tooling scripts (шаблон для переиспользования)

Три скрипта из phenotype strip сохранены как template:

| Скрипт | Назначение | Идемпотентность |
|---|---|---|
| `_strip_<feature>.py` | Загружает workflow GET, удаляет target-ноды/connections/branches, формирует PUT body | Идемпотентен на pre-strip JSON (нет target-нод → no-op) |
| `_audit_refs.py` | Сканирует все executeWorkflow refs vs список существующих workflows | Read-only, можно запускать повторно |
| `_verify_post.py` | POST-PUT GET + 4 metric-проверки | Read-only |

Расположение: `n8n_workflows/` (в основном NOMS репо).

## Gotchas

- **Shared ноды с dead code paths** (Build Profile Sub-Screen имеет `phenoMap` dict — теперь unreachable но active). Не ломает ничего, cleanup при следующем full pass. Не расширять scope strip'а до shared нод.
- **Go to Language disabled** — n8n PUT валидирует ВСЕ executeWorkflow refs, включая ноды которые НИКОГДА не достигаются в текущем routing. Legacy ref на удалённый workflow = blocker. Fix: `disabled: true` на ноде + commit message explaining scope.
- **deploy.yml smoke false positive** — strip может совпасть с transient health-check WARNING при restart. Не путать с реальной ошибкой. См. [[concepts/release-protocol]] lesson 2026-05-17.

## Применимость к будущим strip'ам

| Target | Workflow | Scope | Ожидаемые ноды |
|---|---|---|---|
| Add food / AI Engine | `03_AI_Engine` (138 KB) | GPT-4o Vision pipeline | ~40 нод (Phase 7) |
| Edit Meal | `04.2_Edit_StatsDaily` | Meal editing flow | ~20 нод (Phase 5) |
| Payment legacy | `10_Payment` | Already inactive, cleanup DELETE | Весь workflow |

Для каждого — те же 6 шагов + predictable Python-side cascade.

## Related Concepts

- [[concepts/n8n-data-flow-patterns]] — Safe PUT recipe (базовый шаблон для PUT), dangling executeWorkflow refs gotcha
- [[concepts/phenotype-quiz]] — Phase 2 cutover с этим strip'ом (первое применение recipe)
- [[concepts/phase4-onboarding-migration]] — gotchas #26-29 (Python-side cascade после strip'а)
- [[concepts/python-vs-n8n-template-grammar]] — почему strip нужен ДО `{icon_X}` placeholder'ов (legacy JS не резолвит Python-grammar)
- [[concepts/variant-b-cutover]] — upper-layer pattern (routing cutover); этот recipe — lower-layer (rendering cutover)
- [[concepts/architecture-registry]] — карта Python authoritative vs n8n legacy (определяет что strip'ить)

## Sources

- [[daily/2026-05-10.md]] — 4 сессии phenotype quiz Phase 2 cutover: mig 193 rollback → mig 194 → strip 6 нод из 04_Menu → mig 195 replay → 4 Python-side fixes (status normalization, PROFILE_V5_CALLBACKS, ONBOARDING_STATUSES, button text resolution). Total: 5 PRs (#36, #38, #39, #40, #41, #42), 399 tests passed.
