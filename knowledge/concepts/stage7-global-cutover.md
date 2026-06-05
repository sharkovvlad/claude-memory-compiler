---
title: "Stage 7 Python AI Engine — global cutover process (mig 299 → 373)"
aliases: [stage7-cutover, ai-engine-cutover, python-ai-recognition-global]
tags: [migration, cutover, ai-engine, python, n8n-deprecation, flag-removal]
sources:
  - "migrations/299_ai_engine_beta_testers.sql (canary intro)"
  - "migrations/373_stage7_global_cutover_drop_ai_engine_flags.sql (global)"
  - "handover/2026-05-25_python_ai_engine_complete.md (initial false claim)"
  - "handover/2026-05-29_stage7_status_reality_check.md (correction)"
  - "PR #192 (canary code), PR #227 (global cutover)"
created: 2026-05-29
status: active
severity: cutover-blueprint
---

# Stage 7 Python AI Engine — Cutover History + Process

> **TL;DR.** Stage 7 = миграция AI распознавания еды (text/voice/photo) из n8n `03_AI_Engine` в Python `handlers/food_log.handle_ai_input`. Cutover был **admin-only canary с 2026-05-21 (mig 299)** до **2026-05-29 (mig 373 global)**. До 29.05 MEMORY ошибочно утверждала «GLOBAL CUTOVER 25.05» — это [[concepts/memory-claim-vs-live-verification]] case study.

## Архитектура до и после

### До mig 373 (admin canary)

```
Юзер шлёт фотку еды
  ↓
webhook_server._try_authoritative_path
  ↓
gate: target=='ai' AND reason=food_media|text_food
      AND status in (registered, editing_meal)
      AND handler_ai_engine_use_python = true
      AND chat_id IN ai_engine_beta_testers
  ↓
  ├── owner (417002669) → handle_ai_input (Python OpenAI Vision)
  │                      → log_meal_transaction RPC
  │                      → render carрочки → send Telegram
  │
  └── другой юзер → forward_to_n8n('01_Dispatcher')
                    n8n Route Classifier → executeWorkflow('03_AI_Engine')
                    n8n: OpenAI Vision + log_meal_transaction RPC
                    n8n: HTTP POST /internal/food_log/render (Python endpoint)
                    Python render → send Telegram
```

Гибрид по юзеру. Для real users (4 человека на 29.05) — все через n8n. Для owner — Python.

### После mig 373 (global)

```
Юзер шлёт фотку еды
  ↓
gate: target=='ai' AND reason=food_media|text_food
      AND status in (registered, editing_meal)
  ↓
ВСЕ → handle_ai_input → Python OpenAI Vision → log_meal_transaction → render → send
```

n8n `03_AI_Engine` остаётся **active** на время Stage 7c (см. ниже), но больше не должен получать новые executions.

## История (lessons embedded)

| Дата | Event | Migration / PR |
|---|---|---|
| 2026-05-21 | Stage 7a canary launch — admin-only allowlist | mig 299 (introduced `handler_ai_engine_use_python`, `ai_engine_beta_testers=[417002669]`) |
| 2026-05-21 → 05-25 | Canary period: caught 4 P0 bugs (double sticker, generic emoji, wrong RPC key, NULL meal_id) + 1 UX (rich meal_action) | bugfixes |
| 2026-05-25 | PR #192 merged; daily/handover marked «GLOBAL CUTOVER» | **DOC ERROR**: allowlist всё ещё `[417002669]` |
| 2026-05-25 (post-merge) | Commit 203b798 «force dynamic Sage for n8n users» — author знал что non-admin = n8n | implicit acknowledgment of hybrid state |
| 2026-05-26 .. 2026-05-29 | Все handover'ы повторяли «Stage 7 global» по copy-paste из MEMORY | doc rot accumulated |
| 2026-05-29 | Nutritionist Agent 10 при подготовке Stage 7c обнаружил расхождение (через n8n SQLite execution_entity показал live трафик) | reality check |
| 2026-05-29 | Owner approved promote canary → global | PR #227 + mig 373 |

## Что сделано в mig 373 + PR #227

### Migration

`migrations/373_stage7_global_cutover_drop_ai_engine_flags.sql`:
- `DELETE FROM app_constants WHERE key IN ('handler_ai_engine_use_python', 'ai_engine_beta_testers')`
- Verification block: 0 rows remain
- Apply: BEGIN/COMMIT (owner policy 20.05: no backup tables)

### Python (webhook_server.py)

- Удалены функции `_read_handler_ai_engine_use_python` (24 строки) и `_user_in_ai_beta_allowlist` (24 строки) — итого -48 LOC
- Gate в `_try_authoritative_path` упрощён: убраны 2 строки `and _read_*(ctx)` + `and _user_in_*(chat_id, ctx)`
- Комментарий перед gate переписан: «Stage 7a PR C: AI Engine Python authoritative» → «Stage 7 GLOBAL: AI Engine Python authoritative (mig 373)»

### Tests (tests/test_webhook_ai_engine_gate.py)

- Удалены 21 тестов которые покрывали удалённые функции (`test_read_flag_*`, `test_allowlist_*`, `test_ai_gate_flag_off_falls_through`, `test_ai_gate_not_in_allowlist_falls_through`)
- Сохранены тесты живой gate-семантики (idempotency, non-food target, non-registered status, mana=0, handler exception)
- **Главный новый тест:** `test_ai_gate_registered_user_text_input_invokes_handler[OWNER_ID|NON_OWNER_ID]` — параметризован, доказывает что любой registered user → Python handler

## Rollback

Если global cutover показал регрессию (24-48h monitoring window):

```bash
git revert <PR #227 commit> && git push
# GitHub Actions auto-deploys reverted Python.
```

После revert constant-rows из app_constants уже удалены (mig 373). Поведение:
- `_read_handler_ai_engine_use_python` вернётся в код, но constant row отсутствует → возвращает `False` → gate fails → **ВСЕ юзеры в n8n** (включая owner).
- Это строже чем admin canary но обратимо.

Если хочется именно admin canary обратно:
```sql
INSERT INTO app_constants(key, value, scope, description) VALUES
  ('handler_ai_engine_use_python', 'true', 'feature_flags', 'Stage 7 ROLLBACK admin canary'),
  ('ai_engine_beta_testers', '[417002669]', 'feature_flags', 'Allowlist при rollback');
```

## Stage 7c cleanup (после 7д стабильного global)

> **🛑 ПОПРАВКА 2026-06-05 — реальный блокер 7c НЕ календарь, а немигрированный Edit Meal путь (Phase 5):**
> Verify-first перед удалением 03/06 поймал, что n8n `03_AI_Engine` **ПРОДОЛЖАЛ исполняться** (7 успешных exec 06-03…06-05, последний сегодня), несмотря на `active=0` — потому что **повторное распознавание еды при редактировании (`reason='editing_meal'`) НЕ было в Python**. Это НЕ fallback от ошибки (0 Python AI-failures) и НЕ остаток — живой функциональный путь (registered-юзер редактирует приём → шлёт новое фото/голос/текст → re-recognize). Если бы удалили 03 по календарю — **сломали бы редактирование еды**.
> - **Корень:** Python edit-pipeline (`handlers/food_log._handle_edit_meal_input`, Stage 7b PR D `d6f4c72`) был СМЕРЖЕН, но **никогда не доходил до прода** — webhook AI-гейт пропускал только `startswith(('food_media','text_food'))`, а роутер ставит `reason='editing_meal'` → не матчит → silently fall through в n8n. Классический «merged-but-unwired» latent bug. `handle_ai_input` уже диспатчил на `_handle_edit_meal_input` по `ctx.status=='editing_meal'` — не хватало только пропустить reason в гейт.
> - **Fix:** PR #326 (2026-06-05) — расширен reason-предикат гейта на `'editing_meal'` + distinct лог `AUTHORITATIVE_AI_EDIT`. Все RPC (`replace_meal_transaction`/`grant_correction_xp`/`clear_editing_state`/`get_meal_by_id`) уже в проде, миграций нет. Fail-safe сохранён.
> - **7c РАЗБЛОКИРУЕТСЯ ТОЛЬКО ПОСЛЕ deploy+monitoring PR #326:** `AUTHORITATIVE_AI_EDIT` растёт И n8n `03_AI_Engine` executions → 0 за чистые несколько дней. До этого 03/06 НЕ удалять (они ещё обслуживают edit через executeWorkflow, игнорируя `active=0`). **Урок: «время прошло» ≠ «путь мёртв» — гейт удаления = 0 реальных executions, а не календарь.**
>
> **⏩ Прогресс 2026-06-02 (день 4 из 7, частично выполнено досрочно по решению owner'а):**
> - ✅ **Шаг 2 (deactivate 03_AI_Engine + 06_Indicator_Clear) — СДЕЛАНО.** `active=0` в live SQLite. Verified: SQLite SELECT + API GET оба показывают `active=false`.
> - ⛔ **Шаг 3 (DELETE `/internal/food_log/render`) — НЕ делали.** Endpoint оставлен живым: 03_AI_Engine хоть и `active=0`, всё ещё вызывается через `executeWorkflow` (fallback) и зовёт этот endpoint для рендера. Удалять только когда 03 будет физически DELETE'нут (шаг 5).
> - 🟡 **Шаги 1 (свежий 0-exec чек за чистые 7д), 4 (Route Classifier executeWorkflow refs), 5 (DELETE workflows) — pending**, после ~05-06.
> - **Метод деактивации (важный gotcha, n8n 2.17.7):** публичные API endpoints `/workflows/{id}/activate` и `/deactivate` отдают **`{"message":"Forbidden"}`** на этой сборке/лицензии. Обычный `PUT /workflows/{id}` работает (200), но **не меняет `active`** (read-only в API). Единственный рабочий способ — **прямой `UPDATE workflow_entity SET active=0` на live `/home/noms/n8n/data/database.sqlite`** (bind-mount; в контейнере sqlite3 нет, на хосте есть). Прецедент: 10_Payment деактивировали так же.
> - **Рестарт n8n НЕ делали.** Для этих executeWorkflow-sub-workflow'ов `active` почти косметический: fallback (`01_Dispatcher → Go to 03_AI → Execute Workflow Trigger`) работает независимо от флага. После SQLite UPDATE: API GET и SQLite уже консистентны (`active=false`); in-memory webhook-триггеры 03/06 (`Webhook B-1 Cutover ai_engine`, MCP-вебхуки) остаются зарегистрированы до следующего рестарта n8n, но Python их не вызывает (`ai` нет в `TARGET_TO_PATH`) → безвредно. Следующий деплой/рестарт reconcile'ит.
> - **Заодно (2026-06-02):** `04_Menu_v3 → Switch Forward To` — убраны 2 мёртвых case (`02_Onboarding_v3`, `02.1_Location`, без outgoing connections) через Safe PUT. Оставлены `03_AI_Engine` (живой output[0] → `Go to 03_AI_Engine`) и `10_Payment` (payment вне scope сессии). Verified fresh GET.

**Не делать сразу.** Дать 7 дней global без регрессий, потом:

1. **n8n executions verify** (SQLite, не API):
   ```bash
   ssh root@89.167.86.20 'docker cp noms-n8n:/home/node/.n8n/database.sqlite /tmp/n.sqlite && sqlite3 /tmp/n.sqlite "SELECT COUNT(*) FROM execution_entity WHERE workflowId IN (\"kjw4kkKMD0IqNALg\", \"jQn0nTxThFal4Kpe\") AND startedAt > datetime(\"now\", \"-24 hours\");"'
   ```
   Ожидаем `0`.

2. **n8n PUT active:false** для `03_AI_Engine` (`kjw4kkKMD0IqNALg`) и `06_Indicator_Clear` (`jQn0nTxThFal4Kpe`). Safe PUT recipe — [[concepts/n8n-data-flow-patterns]] §Safe PUT.

3. **DELETE `/internal/food_log/render` endpoint** в `webhook_server.py:1836-1918` (~80 строк). Это endpoint который n8n зовёт для рендера карточки еды — после deactivate n8n он мёртвый.

4. **Cleanup `01_Dispatcher` executeWorkflow refs** — Route Classifier node ссылается на 03_AI_Engine. Через Safe PUT удалить эти branches.

5. **n8n DELETE workflows** через API после ещё одной недели deactivated.

## Метрики для monitoring (post-cutover)

| Metric | Source | Target |
|---|---|---|
| `AUTHORITATIVE_AI ... return True` rate | `journalctl -u noms-webhooks` grep | > recognition baseline (старые n8n + owner Python) |
| `AUTHORITATIVE_AI ... handler failed` count | `journalctl` grep `handler failed` | 0 или единичные (< 1% от recognitions) |
| n8n `03_AI_Engine` executions | n8n SQLite `execution_entity` | падает до 0 в 24-48ч |
| `food_logs` throughput за 24ч | psycopg2 `COUNT(*)` | не падает baseline |
| OpenAI Vision API errors | OpenAI dashboard или error logs | baseline |
| User-reported «не распознал» complaints | Telegram support | ≤ baseline |

## n8n SQLite execution_entity quirk (важно знать)

n8n API `/api/v1/executions?workflowId=X` **возвращает пустой массив** даже когда executions есть. Это known self-hosted quirk (возможно permissions или pagination bug). Достоверный источник:

```bash
ssh root@89.167.86.20 \
  "docker cp noms-n8n:/home/node/.n8n/database.sqlite /tmp/n.sqlite && \
   sqlite3 -header -column /tmp/n.sqlite \
     'SELECT workflowId, COUNT(*) cnt, datetime(MIN(startedAt)) first, datetime(MAX(startedAt)) last \
      FROM execution_entity GROUP BY workflowId ORDER BY MAX(startedAt) DESC;'"
```

Также `noms-n8n` container часто показывает **"Up Xdays (unhealthy)"** — это healthcheck misconfiguration (wget на wrong port), не реальная неработоспособность. n8n работает.

## Связано с

- [[concepts/memory-claim-vs-live-verification]] — почему MEMORY показывала «GLOBAL» 4 дня подряд, и как ловить такие ошибки
- [[concepts/architecture-registry]] — источник truth о cutover state (но Stage 7 пример где registry тоже соврал)
- [[concepts/n8n-data-flow-patterns]] §Safe PUT — обязательно для Stage 7c deactivate
- [[concepts/release-protocol]] — общая release дисциплина
- [[concepts/claim-vs-check-idempotency-anti-pattern]] — идемпотентность которую Stage 7 правильно реализует (`is_idempotent_message` RPC)
- [[concepts/pre-migration-discovery-recipe]] — `pg_get_functiondef` LIVE для verify RPC signatures
