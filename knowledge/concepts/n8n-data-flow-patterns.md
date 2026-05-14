---
title: "n8n Data Flow Patterns"
aliases: [data-flow, n8n-patterns, http-request-json, passthrough]
tags: [n8n, patterns, data-flow, architecture]
sources:
  - "daily/2026-04-08.md"
  - "daily/2026-04-09.md"
  - "daily/2026-04-11.md"
  - "daily/2026-04-13.md"
  - "daily/2026-04-25.md"
  - "daily/2026-04-27.md"
  - "daily/2026-05-04.md"
created: 2026-04-08
updated: 2026-05-04
---

# n8n Data Flow Patterns

Rules for working with data flows in n8n workflows. These patterns prevent silent bugs caused by how n8n handles `$json` after HTTP Request nodes.

## Key Points

- **HTTP Request overwrites `$json`:** After any HTTP Request node, `$json` contains the API response — not the data from previous nodes. Access upstream data with `$('Node Name').item.json`
- **Passthrough pattern:** Restore original data after a side-effect HTTP call: `return [{ json: $('Merge Data').item.json }]`
- **No `fetch()` in Code nodes:** Only HTTP Request nodes can make API calls; `fetch()` is not available in n8n Code nodes
- **callback_message_id is mandatory:** Always pass `callback_message_id` in Prepare/Merge Data payloads for sub-workflows that may need `editMessageText`
- **Fire-and-forget in parallel branches:** Side-effect nodes (typing indicator, notification log, `save_bot_message`) must run in a parallel dead-end branch — never in the main chain, or they will clobber `$json`
- **PUT API: always GET first:** Before any `PUT /api/v1/workflows/{id}`, GET the current live workflow. Never use a local JSON file as the base — another agent may have changed it
- **PUT body whitelist (CLAUDE.md правило 13):** body = `{name, nodes, connections, settings}`; `settings` ограничен whitelist'ом `{executionOrder, saveManualExecutions, callerPolicy, executionTimeout, timezone, saveExecutionProgress, saveDataSuccessExecution, saveDataErrorExecution, errorWorkflow}` — все остальные top-level поля (`active`, `meta`, `versionId`, `staticData`, `pinData`, etc.) **отбрасывать**, иначе HTTP 400 «must NOT have additional properties»
- **PUT large payloads via scp+ssh:** workflows >50 KB не проходят через стандартный shell escape в `curl --data '...'`. Паттерн: `scp body.json root@vps:/tmp/body.json` → `ssh ... curl ... --data @/tmp/body.json`. `03_AI_Engine` — 138 KB, требует этот путь
- **RETURNS TABLE creates multiple items:** A `RETURNS TABLE` PostgreSQL function returns N rows; Supabase PostgREST creates N n8n items; every downstream node executes N times
- **JSON.stringify anti-pattern:** When using `specifyBody: json` in HTTP Request, do NOT wrap the expression in `JSON.stringify({...})`. n8n already serializes the expression object. Double-wrapping produces an empty body (Supabase returns 404 "function not found without parameters")

## Details

### The `$json` clobber problem

n8n's HTTP Request node replaces `$json` with its response body. This is the most common source of silent bugs: a developer adds a fire-and-forget notification node inline, and suddenly the next node sees Supabase's `{}` response instead of the meal data.

The fix is always to run side-effects as parallel branches with a dead-end (no outgoing connections in the main flow). n8n allows one node's output to connect to multiple targets — use this to branch:

```
Source ─┬→ Main Flow Node      ($json preserved)
        └→ Side-effect Node    (dead-end, fire-and-forget)
```

### PUT API stale base incident

An incident occurred where Agent A added `last_bot_message_id` to the Dispatcher. Agent B took a stale copy of the Dispatcher (without that field), added `callback_query_id`, and PUT it — `last_bot_message_id` was deleted, breaking the "One Menu" feature. Rule: always GET immediately before PUT, never use a session-start or pre-session copy.

### Parallel HTTP nodes race condition

When multiple HTTP Request nodes run in parallel and a downstream node reads from all of them, n8n does NOT guarantee that all parallel branches have completed before the downstream node executes. Example: 3 parallel price-fetch nodes feeding into `Build Plans Text` — the build node may run before `Get Price Quarterly` or `Get Price Yearly` have finished, causing `Node '...' hasn't been executed` errors.

**Fix:** Replace multiple parallel HTTP calls with a single RPC that returns all data in one response. Single call = no race condition, and usually faster due to reduced network overhead.

### Get Subscription → Payment Router incident (2026-04-11)

A `Get Subscription` HTTP Request node was inserted between `Merge Data` and the `Payment Router` Switch node in 10_Payment. Immediately the Payment Router stopped matching any conditions — all 7 outputs produced 0 items, yet execution status was `success` (no error raised).

Root cause: Data Flow Rule #1. After `Get Subscription`, `$json` contained the Supabase response body (a subscription array), not the command string from `Merge Data`. All 7 switch conditions read `$json.command`, which was now `undefined`.

Fix: Every condition in the Switch node changed from `$json.command` to `$('Merge Data').item.json.command`. This is the correct pattern whenever a Switch node has any HTTP Request node upstream of it in the same chain.

**General rule:** After adding any HTTP Request node to a flow, audit all downstream Switch/IF conditions for bare `$json` references and replace them with explicit node references.

### Stale PUT base: cmd_premium_plans routing clobbered twice

The `cmd_premium_plans` routing fix (Build Profile Text: `isPro ? 'cmd_noop' : 'cmd_premium_plans'` → always `'cmd_premium_plans'`) was applied on 2026-04-10, then silently reverted when a subsequent PUT on 2026-04-11 used a session-start copy of the workflow as the base rather than a fresh GET. The fix had to be reapplied.

This is a second real-world confirmation of the stale PUT base rule: **always GET immediately before PUT**. A copy from even 30 minutes earlier may be missing changes made by another deploy in that window.

### Safe PUT recipe для крупных n8n workflows (2026-05-04)

Из refactor `03_AI_Engine` ноды Send error (PR #9). Workflow = 138 KB, blast radius = прод n8n.

**Шаги:**
1. **GET PRE backup** — сохрани полный raw response в `/tmp/n8n_backup/<workflow>_PRE_<change>.json`. Это твоя точка отката.
2. **Inspect target node** — найди по `name`, проверь `type`, `typeVersion`, точные имена полей в `parameters` (например в Telegram-ноде text-поле = `parameters.text`, а не `parameters.message` — нюанс).
3. **Modify in-memory** — меняй ТОЛЬКО целевое поле, остальные `parameters` ноды и все 48 других нод не трогай.
4. **Build PUT body** — фильтруй top-level через whitelist `{name, nodes, connections, settings}`; `settings` дополнительно фильтруй через allowlist (см. Key Points).
5. **Upload via scp** — `scp /tmp/body.json root@89.167.86.20:/tmp/body.json`. Большой shell escape сломает payload.
6. **PUT через ssh + `--data @file`** — `curl -X PUT -H ... --data @/tmp/body.json http://127.0.0.1:5678/api/v1/workflows/<id>`. Проверь что ответ содержит новый `updatedAt` и `versionId`.
7. **GET POST verify** — сравни response с PRE backup: должна измениться **ровно одна нода** (или сколько ты планировал). Используй `json.dumps(node, sort_keys=True)` для каждой ноды + сравнение с pre_by_id.
8. **Save snapshot в репо** — `n8n_workflows/<workflow>.json` (только `{name, nodes, connections, settings, staticData, meta, pinData}`, без volatile полей `versionId`, `updatedAt`, `active`). Закоммить отдельно — это git-tracking, не deploy.
9. **answerCallbackQuery linkages (правило 4 CLAUDE.md):** если в workflow есть ACQ-нода — проверь `connections` после PUT, что её linkage не оборвался. В `03_AI_Engine` ACQ нет, поэтому пункт неприменим — **проверяй каждый раз**.

**Anti-pattern:** правка локального JSON в `n8n_workflows/<workflow>.json` + git push + `./deploy.sh` **не обновляет прод n8n**. `deploy.sh` rsync'ит код Python, не workflows. `n8n_workflows/` — это snapshot для документации/git-tracking, не источник правды для runtime n8n. Runtime живёт в SQLite на VPS, обновляется только через API или UI.

#### Gotcha: PUT блокируется dangling executeWorkflow refs (2026-05-10)

В новых версиях n8n (по крайней мере на `n8nio/n8n:latest` 10.05.2026) PUT валидирует все executeWorkflow ноды и **отказывается публиковать** workflow если хоть одна нода ссылается на удалённый sub-workflow:

```
HTTP 400: Cannot publish workflow: Node "Go to Language" references workflow JRaKFPb5sOFL3xlc which is not published.
```

При этом **раньше работавший `active=true` workflow с такими же мёртвыми ссылками продолжает крутиться** — валидация только на PUT, не на runtime. Поэтому проблема всплывает в первый раз когда ты делаешь любое легитимное изменение в workflow с pre-existing мёртвой ссылкой.

**Recipe (расширение Safe PUT шаг 2.5):**

После загрузки GET response — **audit все executeWorkflow refs** против списка существующих workflow:

```python
existing = {w["id"]: w["name"] for w in GET("/workflows?limit=100")["data"]}
for n in wf["nodes"]:
    if n.get("type") == "n8n-nodes-base.executeWorkflow":
        wid = n["parameters"].get("workflowId")
        if isinstance(wid, dict): wid = wid.get("value")
        if wid not in existing:
            print(f"DEAD: {n['name']} -> {wid}")
```

**Resolution для каждой dead ноды (выбор зависит от роли):**

1. **Disable** (`node["disabled"] = True`) — если нода уже неreachable (callback мигрирован в Python authoritative path) или вызов sub-workflow закомментирован выше по цепочке. Минимальный scope, безопасный default.
2. **Update workflowId** на актуальный ID — если sub-workflow был переименован/пересоздан с новым ID.
3. **Удалить ноду** + связанные connections — только если уверен что путь полностью dead. Расширяет scope изменения, требует отдельного KB-объяснения в commit message.

**Важно:** не объяснять команде «починил n8n» как side effect — пометить в commit/PR явно («kept scope minimal: disabled `Go to Language` to unblock PUT, dead ref pre-dates this strip»).

**Контекст обнаружения:** session 2026-05-10 surgical strip phenotype quiz из `04_Menu` (PR #39). Нода `Go to Language` ссылалась на удалённый workflow `JRaKFPb5sOFL3xlc`. Language editing был мигрирован в Python (`cmd_edit_lang` через menu_v3 target), нода — dead код. Disable разблокировал PUT без расширения scope.

### editMessageText vs sendMessage routing

When a node can be triggered by both a reply-keyboard tap (text message) and an inline-button tap (callback_query), use an IF node:
- Condition: `{{ $json.callback_message_id }}` is truthy
- True branch: HTTP Request `editMessageText`
- False branch: Telegram `sendMessage` node

### RETURNS TABLE creates multiple n8n items (2026-04-13)

**Problem:** PostgreSQL `RETURNS TABLE` functions (e.g., `get_all_plan_prices`) return one row per result. Supabase PostgREST returns these as a JSON array. n8n's HTTP Request node creates **one n8n item per array element**. Every downstream node then executes once per item.

Example: `get_all_plan_prices` returns 3 rows (monthly, quarterly, yearly) → n8n creates 3 items → `editMessageText` executes 3 times → screen flickers; `sendInvoice` executes 3 times → 3 invoices sent to the user.

**Fix: Limit 1 Code node** placed immediately after the HTTP Request:
```javascript
return [$input.first()];
```

This collapses N items back to 1. Place one `Limit 1` node after each HTTP Request that calls a `RETURNS TABLE` RPC.

**Exception:** Code nodes that need all rows for aggregation (e.g., building a keyboard from all 3 plan prices) should use `$('Get All Prices').all()` — cross-node references bypass the item count. The `Limit 1` only affects what flows downstream in the item chain.

**Scope in payment flow (4 Limit 1 nodes):**
- After `Get All Prices` (Plans screen)
- After `Get Stars Price` (Stars invoice)
- After `Get Crypto Price` (USDT instructions)
- After `Get Sub Details` (premium screen)

This pattern is required for any `RETURNS TABLE` or RPC that returns multiple rows.

### JSON.stringify double-serialization anti-pattern (2026-04-27)

**Problem:** HTTP Request nodes with `specifyBody: json` accept a JavaScript expression object as the body. Some developers wrap the object in `JSON.stringify({...})` thinking n8n needs a string. n8n parses the expression, sees a string, and sends that string as-is — but the string is not JSON: it's the result of `JSON.stringify` which produces a literal `"{"p_telegram_id":123}"`. Supabase PostgREST receives an empty or malformed body and returns HTTP 404 "Could not find function without parameters".

**Discovery:** 4 nodes in 10_Payment (Get All Prices, Get Card Price, Get Stars Price, Get Crypto Price) had this bug from their original creation — pre-dating Phase 5 nav_stack migration. Free users were unable to activate subscriptions. Initially suspected to be a Phase 5 regression; root-caused as pre-existing via logs of affected user 786301802 (free), not the testing account 417002669 (premium).

**Fix:** Remove `JSON.stringify()` wrapper entirely:

```javascript
// WRONG — double-serialization, empty body sent to Supabase
$json.body = JSON.stringify({ p_telegram_id: $json.telegram_id, p_plan: 'monthly' })

// CORRECT — n8n serializes the object automatically
$json.body = { p_telegram_id: $json.telegram_id, p_plan: 'monthly' }
```

**Secondary bug (found in same session):** After removing `JSON.stringify`, Get All Prices was reading `$json.telegram_id` from the Extract Sub node output. For free users, Extract Sub returns `{}` (no active subscription), so `$json.telegram_id` was `undefined`. Fix: always reference the canonical data source: `$('Merge Data').item.json.telegram_id`.

**Lesson:** When debugging a Supabase 404 "Could not find function without parameters" — check jsonBody expressions for `JSON.stringify` wrappers before assuming schema problems. Also, always inspect logs for the **specific affected user type** (free vs premium) — the bug was only triggered for free users.

### `continueOnFail` on HTTP deleteMessage (2026-04-25)

**Problem:** The "One Menu" pattern deletes the previous menu message via HTTP `deleteMessage` before sending a new one. If the message was already deleted (race, double-tap, or stale `last_bot_message_id`), Telegram returns HTTP 400. An n8n HTTP Request node without `continueOnFail` will throw on this 400 — stopping the workflow branch. The subsequent `sendMessage` node never executes, the user sees nothing.

**Fix:** Every HTTP `deleteMessage` node in n8n MUST have:
- `continueOnFail: true`
- `onError: 'continueRegularOutput'`

This routes the 400 error response to the normal output instead of stopping execution, allowing the next node (sendMessage) to run.

```
⚠️ Rule: ANY HTTP deleteMessage node MUST have continueOnFail + onError:continueRegularOutput.
   Stale message IDs are routine in Telegram bots; 400 is expected, not exceptional.
   Without this, the "One Menu" pattern silently fails for a large fraction of users.
```

**Where to apply:** all `deleteMessage` calls in 04_Menu_v3, 01_Dispatcher "Delete Old Menu" branches, any future screen that uses delete-and-send-new render strategy.

## Related Concepts

- [[concepts/n8n-stateful-ui]]
- [[concepts/noms-architecture]]
- [[concepts/access-credentials]]
- [[concepts/payment-integration]]
- [[concepts/one-menu-ux]] — deleteMessage as part of One Menu pattern
- [[concepts/save-bot-message-contract]] — n8n воркфлоу ОБЯЗАНЫ вызывать save_bot_message после финального user-visible sendMessage. Иначе Python router не сможет удалить старое меню (Tech debt #7 lesson 14.05).
- [[concepts/language-switch-headless-ux]] — Bug 6: deleteMessage blocking; continueOnFail fix

## Sources

- [[daily/2026-04-08.md]] — Rules codified after multiple data-flow bugs; added to CLAUDE.md as "n8n Data Flow Patterns" section
- [[daily/2026-04-09.md]] — Parallel HTTP race condition discovered in Plans flow; fixed by replacing 3 parallel price calls with single `get_all_plan_prices` RPC
- [[daily/2026-04-11.md]] — Get Subscription → Payment Router $json clobber incident; stale PUT base clobbering cmd_premium_plans fix a second time
- [[daily/2026-04-13.md]] — RETURNS TABLE multiple items bug: `get_all_plan_prices` 3 rows → 3 n8n items → triple editMessageText/sendInvoice; fix: Limit 1 Code nodes after each RETURNS TABLE HTTP Request
- [[daily/2026-04-25.md]] — `continueOnFail: true` + `onError: continueRegularOutput` on HTTP deleteMessage nodes required to prevent silent workflow stoppage on Telegram 400 (stale message ID)
- [[daily/2026-04-27.md]] — JSON.stringify anti-pattern: `specifyBody=json` + `JSON.stringify({...})` → double-serialization → empty body → Supabase 404. Found in 4 Get *Price nodes (pre-existing since original creation). Secondary: `$json.telegram_id` from Extract Sub `{}` for free users → fix to `$('Merge Data').item.json.telegram_id`
- [[daily/2026-05-04.md]] — Safe PUT recipe + scp+ssh для крупных payload (>50 KB), settings whitelist (правило 13), refactor `03_AI_Engine` Send error через GET-modify-PUT API (PR #9). Anti-pattern: коммит локального JSON ≠ деплой на runtime n8n. `n8n_workflows/` — git-tracking, не источник правды

---

## 2026-05-13 — execution_entity SQLite diagnostic + Command Classifier syntax hotfix

### Diagnostic recipe — find 100% fail rate workflow

n8n self-hosted SQLite на VPS содержит полную историю executions. Для быстрого triage «работает / нет» по workflow:

```bash
ssh root@89.167.86.20 'docker exec n8n-n8n-1 sqlite3 /home/node/.n8n/database.sqlite \
  "SELECT status, COUNT(*) FROM execution_entity \
   WHERE workflowId='\''<id>'\'' \
     AND startedAt > datetime('\''now'\'', '\''-48 hours'\'') \
   GROUP BY status;"'
```

Если result типа `error: 18` без `success` — workflow зацикливается на crash. Lookup error через `execution_data` table:

```bash
ssh root@89.167.86.20 'docker exec n8n-n8n-1 sqlite3 /home/node/.n8n/database.sqlite \
  "SELECT data FROM execution_data WHERE executionId=<id>;"'
```

JSON большой. `jq -r '.executionData.resultData.lastNodeExecuted, .executionData.resultData.error.message'` извлекает relevant.

### Lesson — UAT 13.05 inquest: `Command Classifier` JS syntax error

Сценарий: тимлид + НЛМ предлагали откатить mig 211 на `forward_to_n8n cmd_edit_last` (через legacy 04_Menu). Я не доверился без верификации — диагностика обнаружила что 04_Menu сломан с 11.05 19:18 UTC (100% error rate, 18/18 fail за 48ч).

Корень — пустой `else` без body в JS Command Classifier (lines 170-173):
```js
}
else                              // L170 — пустой else (no body)
                                  // L171 — empty line
// ── Coming soon stubs ──         // L172 — comment
else if (command === 'cmd_notifications') {  // L173 — SyntaxError: Unexpected token 'else'
```

JS-парсер видит `else else if` → нода падает на КАЖДОМ исполнении до того как `menu_route` устанавливается. Никакая ветка Menu Router не достигается.

### Hotfix через PUT (single-node surgical patch)

Recipe — PUT workflow с измененённым **только одним нодом**, остальные verbatim. Body whitelist `{name, nodes, connections, settings}`. Settings whitelist (см. секцию «Safe PUT»).

1. GET workflow → save in `/tmp/`. sha256 + size + updatedAt.
2. Python script: find node by id (id = UUID из `Command Classifier` ноды, не name — name может меняться).
3. Patch `parameters.jsCode`: точная regex `}\n        else\n\n        // ── Coming soon stubs ──\n        else if` → `}\n        // ── Coming soon stubs ──\n        else if` (убрали пустой `else\n\n`).
4. Local sanity: `node --check` если установлен Node.js на маке (можно skip — PUT validation поймает).
5. scp payload (175 KB > 50 KB threshold) на VPS → `curl --data @file PUT`.
6. Verify: fresh GET, diff против baseline, **только 1 node changed**. updatedAt новый, versionId новый.
7. Trigger через user click — нельзя touch'нуть напрямую (real users). Мониторим `execution_entity` после PUT: следующий клик → status=success.

**Single-node surgical = no scope creep.** Все 129 других нод нетронуты. Risk минимальный, PUT validation чистая (без dangling executeWorkflow refs blocked).

### General rule — when to fix legacy n8n vs migrate

Legacy n8n workflows которые **уже работают** — не трогать (KB n8n-self-host-migration risk). Workflows которые **100% fail** — точечный hotfix через PUT, не переписывание на Python (Phase X — большая задача). Hotfix защищает остальные команды которые legacy всё ещё обслуживает (cmd_notifications, cmd_delete_account etc) пока их не мигрируют.
