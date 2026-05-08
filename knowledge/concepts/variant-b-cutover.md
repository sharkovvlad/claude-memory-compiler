# Variant B Cutover — паттерн постепенного переноса n8n → Python

**Status:** Phase 1 в проде с 2026-05-01 (только `menu_v3` target).
**Источники:** `handover/2026-04-30_session_close.md`, `handover/2026-05-01_variant_b_phase1_complete.md`, `daily/2026-04-29..2026-05-01.md`.

## Что это

Архитектурный паттерн для постепенной замены роли n8n `01_Dispatcher` на Python-роутер. Python становится authoritative source-of-truth для маршрутизации, при этом legacy n8n sub-workflows остаются работать как fallback для непереписанных таргетов.

Критическое преимущество — **fail-safe by design**: при любом сбое Python-ветки трафик автоматически возвращается на legacy 01_Dispatcher, юзер ничего не замечает.

## Когда применять

Когда нужно:
- Перенести бизнес-логику из n8n в Python без big-bang miграции
- Иметь возможность откатиться за секунды без deploy'я
- Работать staged rollout (admin → 1% → 10% → 100%)
- Сосуществовать с legacy кодом в течение месяцев

## Не применять

- Когда target sub-workflow использует `$('NodeName').item.json.X` runtime-ссылки на trigger ноды (см. секцию «Структурное ограничение» ниже)
- Когда нет Python-обработчика для конкретного target — лучше оставить через legacy
- Для разовых переездов (tier-1 cutover проще)

## Архитектура

```
Telegram Bot API
    ↓ webhook
[Python FastAPI :8443]
    ├─ ack 200 за <10ms (fire-and-forget)
    ├─ create_task(maybe_send_indicator)
    ├─ create_task(maybe_sync_user_profile)
    ├─ create_task(_route_or_forward) ← вся routing-логика тут
    └─ create_task(shadow_route)      ← мониторинг для parity_check

_route_or_forward (background task):
    ├─ _try_authoritative_path()       ← B-3 (Variant B Phase 1)
    │   ├─ flags = await get_flags()   ← DB-flags, cache 60s
    │   ├─ gate: authoritative + admin_only check
    │   ├─ ctx = await _ensure_user_for_authoritative()  ← ensure_user_exists RPC
    │   ├─ decision = route_update(update, ctx)
    │   ├─ MATCH decision.target:
    │   │   menu_v3   → handle_menu_v3() (Python) ИЛИ forward.send("menu_v3")
    │   │   onboarding → handle_onboarding() (когда Phase 6 готов)
    │   │   ...
    │   │   _ → return False (fall through)
    │   └─ on success: return True (skips legacy)
    └─ if not handled: forward_to_n8n(body)  ← legacy 01_Dispatcher
```

## Слои

### 1. DB layer (миграции)
- Все флаги в `app_constants` (key/value/category/description text)
- Один helper-RPC `get_dispatcher_flags()` возвращает все флаги одним JSONB
- Hot-reload через trigger `app_constants_cache` + Python TTL-кеш 60с
- Категория `dispatcher` для всех cutover-флагов

Примеры используемых флагов:
- `dispatcher_python_shadow_mode` — наблюдение
- `dispatcher_python_authoritative` — мастер-switch B-3
- `dispatcher_python_authoritative_admin_only` — staged rollout gate (whitelist по telegram_id)
- `handler_X_use_python` — per-handler fine control (Phase 2 / Phase 6 / etc.)

### 2. n8n layer (per-workflow webhooks)
Каждый sub-workflow получает дополнительный entry-point — Webhook trigger node + Adopt Code node:

```
[old]  Execute Workflow Trigger ─┐
                                  ├─→ first downstream node (Merge Data / Extract Payload / ...)
[new]  Webhook B-1 Cutover → Adopt Cutover Payload ─┘
```

Adopt Code:
```javascript
const expected = $env.N8N_DISPATCHER_SECRET;
const got = $json.headers?.['x-noms-dispatcher-secret'];
if (!expected || got !== expected) return [];  // silent drop
return [{ json: $json.body }];                   // re-emit body as $json
```

Idempotent injector script: `tools/n8n_inject_cutover_webhook.py`.

### 3. Python layer
- `services/app_flags.py` — TTL-кешированный reader флагов с env override
- `dispatcher/forward.py` — async httpx pool с retry, `TARGET_TO_PATH` map, `build_payload` собирает flat-shape совместимый с downstream-нодами
- `dispatcher/shadow.py` — observer-only роутер для parity-валидации (логи `SHADOW_ROUTE update_id=...`)
- `webhook_server.py::_try_authoritative_path` — главная функция. Помещается ВНУТРИ `_route_or_forward` background task, чтобы не блокировать ACK
- `webhook_server.py::_ensure_user_for_authoritative` — порт legacy «Auto Create User» через RPC `ensure_user_exists`

### 4. Tooling
- `tools/n8n_inject_cutover_webhook.py` — добавление webhook'а в любой workflow
- `tools/parity_check.py` — diff `SHADOW_ROUTE` логов vs n8n executions по `update_id` (verdict 🟢/🟡/🔴)

## Staged rollout — последовательность

1. **Foundation (один раз):** миграции, флаги, app_flags.py, forward.py, 6 webhooks. Все флаги OFF.
2. **Shadow mode:** `dispatcher_python_shadow_mode=true`, копим SHADOW_ROUTE логи без side-effects. Запускаем `parity_check.py --hours 24` — должен показать 🟡 (мало данных для оценки).
3. **Admin-only authoritative:** `dispatcher_python_authoritative=true` + `admin_only=true`. Только telegram_id админа идёт через Python для тех таргетов, что в `TARGET_TO_PATH`. Лично кликаем все ветки.
4. **Расширить scope** — `parity_check.py --hours 24` показывает 🟢 (≥99.5% match) → `admin_only=false` → ВСЕ юзеры через Python.
5. **Deactivate 01_Dispatcher** (после 7+ дней stable 100%): backup workflow JSON + `UPDATE workflow_entity SET active=0`.

## ⚠️ Структурное ограничение (открытие 2026-05-01)

**Legacy n8n sub-workflows, спроектированные под `Execute Workflow Trigger` entry, СТРУКТУРНО НЕСОВМЕСТИМЫ с Webhook entry**, если их downstream-ноды используют n8n expression `$('NodeName').item.json.X` для доступа к данным trigger-ноды.

n8n expression `$('NodeName')` = runtime ссылка на конкретный узел в текущей execution graph. Если узел не выполнялся в этой execution — `ExpressionError: Node hasn't been executed`.

Прод-инцидент 2026-05-01: при заходе через `Webhook B-1 Cutover → Adopt → Merge Data` в `04_Menu` — нода `Execute Workflow Trigger` не выполняется → 40+ downstream-нод (использующих `$('Execute Workflow Trigger').item.json.translations` и т.п.) падают с ExpressionError. То же для `03_AI_Engine` (`$('Execute Workflow Trigger 03')`).

### Рассмотренные и отвергнутые workaround'ы

| Опция | Почему не подходит |
|---|---|
| Renaming hack: переименовать Adopt Code в имя legacy trigger'а | n8n не разрешает дубликаты имён + ломает legacy путь для не-админов при staged rollout |
| Дублирование downstream-нод (по комплекту на каждый entry-point) | По сути та же работа что переписать с нуля |
| Переписать все downstream `$('NodeName')` → `$json` | 40+ правок, высокий риск регрессии legacy при остаточной работе старого пути |

### Принятое решение

Variant B авторитативный путь работает **только** для тех таргетов, для которых УЖЕ есть Python-обработчик. По мере того как sub-workflows переписываются в Python (Phase 2 → menu_v3, Phase 6 → onboarding, …), они просто добавляются в `TARGET_TO_PATH`. Старые sub-workflows доживают свой век через legacy 01_Dispatcher.

## Связанные документы

- `n8n-data-flow-patterns.md` — правило 9 про `$('Telegram Trigger')` (родственная проблема)
- `n8n-subworkflow-contract.md` — контракт Prepare-нод 01_Dispatcher
- `dispatcher-callback-pipeline.md` — Template Engine + paired items
- `n8n-multi-agent-workflow-editing.md` — координация параллельных агентов
- `headless-architecture.md` — целевая архитектура headless menu/render
