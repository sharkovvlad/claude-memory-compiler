---
title: "n8n Sub-Workflow Data Contract"
aliases: [prepare-for, subworkflow-contract, executeWorkflow-passthrough, workflow-fields-mapping, v1-vs-v3-routing]
tags: [n8n, dispatcher, subworkflows, architecture, bugs, patterns]
sources:
  - "daily/2026-04-17.md"
  - "daily/2026-04-16.md"
created: 2026-04-17
updated: 2026-04-17
---

# n8n Sub-Workflow Data Contract

Какие поля проходят из Dispatcher в sub-workflows (02_Onboarding_v3, 04_Menu, 02.1_Location и т.д.) через `Prepare for *` ноды. Незнание этого контракта даёт silent bugs: поля кажутся доступными, но на самом деле `undefined` в child workflow.

## Key Points

- **`Prepare for *` typeVersion 3.2 использует `fields.values`, НЕ `assignments.assignments`.** Старая форма из v2 больше не применима. При grep/анализе искать `fields.values`. Если проверяешь через API и видишь пустой `assignments` — это не значит что нода пустая, перепроверь `fields.values`.
- **`includeOtherFields` отсутствует в v3.2.** Только поля из явного `fields.values` mapping попадают в output. Всё остальное — **отбрасывается**.
- **Никогда не полагаться на "оно как-то само попадёт".** Если child workflow (v3 Merge Data, 04_Menu Merge Data и т.д.) читает поле — это поле ОБЯЗАНО быть в соответствующем `Prepare for *` в Dispatcher.
- **`executeWorkflow` без `workflowInputs.value` (options: {}) = legacy passthrough.** Весь `$json` предшественника попадает в child's Execute Workflow Trigger. Но предшественник — именно `Prepare for *`, а не `Route Classifier`, поэтому фильтрация всё равно применяется.
- **Active vs inactive workflow и executeWorkflow:** inactive workflow всё ещё вызывается через executeWorkflow — `active=true` нужен только для триггеров (Webhook, Cron, Telegram Trigger). `02_Onboarding v1` (gffHvoRJI2018qle) inactive, но вызывается из 04_Menu → Go to Language. Однако **после первого входа** все дальнейшие user actions (текст/callback) идут в Dispatcher и роутятся в **активный** v3 (`Ksv1DhWKUIDtlhLy`). Не путать "где начинается flow" с "где продолжается".

## Details

### Актуальный контракт Dispatcher → v3 (2026-04-17)

`Prepare for 02` (typeVersion 3.2) передаёт **20 полей**:

```
telegram_id, message, status, translations, constants, previous_status,
language_code, callback_query, parsed_referrer_id, goal_speed, goal_type,
training_type, phenotype, target_weight_kg, callback_message_id,
callback_query_id, subscription_status, last_bot_message_id,
country_code, timezone     ← добавлены 2026-04-17 для Bug 2 Round 2
```

**Часто отсутствуют (добавлять при необходимости):**
- `weight_kg`, `height_cm`, `birth_date`, `gender`, `activity_level` — основная биометрия
- `target_calories`, `target_protein_g`, `target_fat_g`, `target_carbs_g` — макро-цели
- `xp`, `level`, `nomscoins`, `mana_current`, `league_id` — геймификация

### Actual checkflow для нового поля в child workflow

Если фича в v3 / 04_Menu / 02.1_Location требует новое поле из `v_user_context`:

1. **Открыть `Dispatcher → Prepare for *` (тот, что ведёт в нужный child)** через n8n API GET.
2. **Проверить `fields.values`** — есть ли нужное поле?
3. **Если нет — добавить:**
   ```json
   { "name": "new_field", "type": "stringValue",
     "stringValue": "={{ $json.new_field || 'fallback' }}" }
   ```
4. **Проверить child's Merge Data / Onboarding Engine** — оно ЯВНО читает `input.new_field`? Если нет — добавить в return `new_field: input.new_field || fallback`.
5. PUT обоих workflows + deactivate/activate для cache flush.

**Не пропускать шаг 3 или 4** — fix будет выглядеть работающим в одном ("оно передаётся!"), но ломаться в другом ("оно undefined").

### Карта Prepare* → child workflows

| Prepare nod | Dispatcher position | → Child workflow |
|---|---|---|
| `Prepare for 02` | Main Router[2] → Has Referrer? → `02_Onboarding` | `Ksv1DhWKUIDtlhLy` (v3, active) |
| `Prepare for  04` | Main Router[?] → `Go to 04_Menu` | `sxzbSc61YuHFbV4i` (04_Menu) |
| `Prepare Data 03` | Main Router[?] → `Go to 03_AI` | `24ZOwWEmdGOYS2EH` (AI Engine) |
| `Prepare for 05` | Main Router[?] → `Go to 05_Location` | `7asj99vPQB5VCjXl` (02.1_Location) |

**Замечание про имена:** `Prepare for  04` содержит ДВА пробела (исторический артефакт). При grep/search использовать точное имя.

### v1 vs v3 Language routing gotcha

`02_Onboarding` имеет два workflow'а:

- **v1 `gffHvoRJI2018qle`** — inactive, содержит `Return Path Router`, `Parse Language`, `Confirm Registered`, `Send Language Selection` и др. (46 нод).
- **v3 `Ksv1DhWKUIDtlhLy`** — active, содержит `Onboarding Engine`, `Action Router`, `Send Telegram` (15 нод). Это **настоящий production handler** онбординга/языка/статусов.

Routing Language flow (первое открытие picker):
```
User: 👤 Профиль → ⚙️ Настройки → 🌐 Язык (inline callback)
  → 04_Menu → Go to Language (executeWorkflow → gffHvoRJI2018qle)
  → v1 Send Language Selection (reply keyboard)
```

Routing **всех последующих** action:
```
User clicks flag OR 🔙 Назад (reply keyboard text)
  → Telegram → Dispatcher
  → Route Classifier: status='changing_language' AND (flag || back) → route_target='onboarding'
  → Prepare for 02 → Has Referrer? → 02_Onboarding executeWorkflow → Ksv1DhWKUIDtlhLy
  → v3 Onboarding Engine (JS classifier) → Action Router
```

**Урок:** если баг в Language flow — фикс скорее всего нужен в **v3**, не в v1. v1 только показывает picker. Все decisions — в v3.

### Action Router v3 — универсальные ветки

v3 `Action Router` имеет 6 outputs. При добавлении новых flows (Back, error handling, redirect) — не добавлять новую ветку, а использовать существующие:

| Output | `result.action` value | Следующие ноды |
|---|---|---|
| [0] send_only | `'send_only'` | → Send Telegram |
| [1] rpc_then_send | `'rpc_then_send'` | → Generic RPC → Response Builder → Send Telegram |
| [2] completion | `'completion'` | → Complete Onboarding RPC → Response Builder → Send Telegram |
| [3] language_save | `'language_save'` | → Save Language DB → Fetch Translations → After-Lang Builder → Send Telegram |
| [4] status_and_send | `'status_and_send'` | → Update User Status → Send Telegram |
| [5] location | `'location'` | → Go to 02.1 |

**`status_and_send` — самая гибкая** ("update status + show arbitrary screen"). Использовалась для Bug 2 fix: изменили `isBack` branch в `Onboarding Engine` с `language_save` на `status_and_send` + полный Settings payload. Никаких новых нод.

### executeWorkflow typeVersion: passthrough vs explicit mapping

n8n `Execute Workflow` ноды имеют два режима передачи данных — определяется полем `typeVersion`:

| typeVersion | Режим | Поведение |
|---|---|---|
| `1` (legacy) | Passthrough | Весь `$json` предшественника передаётся в child workflow без фильтрации |
| `1.3+` | Explicit mapping | В child попадают ТОЛЬКО поля из `workflowInputs.value` |

**Опасный паттерн:** `typeVersion 1.3` + пустой `workflowInputs.value: {}` → child workflow получает пустой объект. Внешне нода "выглядит нормально", но child видит `undefined` для всех полей. Исторически `Go to 05_Location` имел эту ошибку — 05_Location вообще не получал данных от 04_Menu.

**Правило:** При `typeVersion 1.3+` всегда явно перечислять все нужные поля в `workflowInputs.value`. Минимальный набор для 05_Location: `telegram_id`, `status`, `translations`, `constants`, `language_code`, `callback_message_id`, `callback_query_id`, `subscription_status`, `last_bot_message_id`.

**Верификация:** если child workflow получает `undefined` для полей — проверить `typeVersion` и `workflowInputs.value` в вызывающей ноде. Не искать сначала в child's Merge Data.

### Intl.DisplayNames — локализация стран/языков без DB-таблиц

Node.js `Intl.DisplayNames` API работает в n8n Cloud (Full ICU). Убирает необходимость в N×50 translation keys для списка стран.

```javascript
// Локализованное название страны
const countryName = new Intl.DisplayNames([language_code], {type: 'region'}).of(country_code);
// ru + 'ES' → "Испания"; en + 'ES' → "Spain"; fr + 'ES' → "Espagne"; ar + 'ES' → "إسبانيا"

// Локализованное название языка
const langName = new Intl.DisplayNames([language_code], {type: 'language'}).of(lang_code);
// ru + 'fr' → "французский"; en + 'fr' → "French"
```

**Когда применять:** для любого UI где нужны названия стран или языков. Заменяет хардкод-маппинги вида `const countryNames = { 'ES': { ru: 'Испания', en: 'Spain', ... } }`.

**Ограничения:** требует Full ICU в Node.js. n8n Cloud имеет Full ICU по умолчанию. Self-hosted n8n может иметь только small-icu (проверить).

### n8n API PUT gotchas

- **`settings` must be filtered.** n8n Cloud API PUT отвергает `settings` со "additional properties" (HTTP 400). Whitelist safe keys:
  ```python
  ALLOWED = {'executionOrder','saveManualExecutions','callerPolicy','executionTimeout',
             'timezone','saveExecutionProgress','saveDataSuccessExecution',
             'saveDataErrorExecution','errorWorkflow'}
  ```
  Передавать `settings: {k:v for k,v in orig.items() if k in ALLOWED}` в PUT body.
- **Rate limit на activate.** После PUT сразу deactivate → activate для cache flush. Activate иногда даёт 429 "Too Many Requests: retry after 1" — sleep 1s и retry.
- **PUT тело — минимальное.** `{name, nodes, connections, settings}`. Остальные поля (`active`, `id`, `versionId`, `createdAt` и т.д.) — API отвергает.

### Emoji surrogates в JSON dump gotcha

При генерации Python кода для insertion в n8n Code node — **не использовать** `\uXXXX` surrogate pairs (например `\ud83c\udf10` для 🌐). Python 3 `json.dumps(..., ensure_ascii=False)` падает с `UnicodeEncodeError: surrogates not allowed`. Использовать **raw UTF-8 characters** напрямую в source код (🌐, 🔙) — работает в n8n и в `json.dumps`.

## Sources

- [[daily/2026-04-17.md]] — Dispatcher Prepare for 02/04 fields.values contract, v3.2 typeVersion, v1/v3 routing, Action Router outputs, PUT API gotchas, emoji surrogates; Bug 2 fix (status_and_send для Language Back); Bug 2 Round 2 (country_code+timezone → Prepare for 02 = 20 полей); Intl.DateTimeFormat для timezone display (shortOffset)
- [[daily/2026-04-16.md]] — executeWorkflow typeVersion 1 passthrough vs 1.3+ explicit mapping; Intl.DisplayNames для стран/языков; Prepare for 02 +9 полей (Round 2 profile bugs); Go to 05_Location workflowInputs fix

## Related

- [[concepts/dispatcher-callback-pipeline]] — Template Engine Phase 4 и paired items bug
- [[concepts/n8n-data-flow-patterns]] — `$json` clobber, passthrough, fire-and-forget
- [[concepts/one-menu-ux]] — `last_bot_message_id` + `save_bot_message` RPC
- [[concepts/n8n-stateful-ui]] — editMessageText, callback_message_id
- [[concepts/profile-redesign-v5]] — Round 2 bugs раскрыли typeVersion/Intl.DisplayNames паттерны; Bug 2 fix через status_and_send
- [[concepts/edit-picker-dual-render]] — chk*() helpers требуют cur* полей из Prepare for 02/04 в Merge Data
