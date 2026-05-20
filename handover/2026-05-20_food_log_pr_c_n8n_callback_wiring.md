# Handover: PR C — n8n callback wiring + cutover flag flip

> **Дата:** 2026-05-20.
> **Создан:** агентом PR A (mig 287) + PR B (handlers/food_log.py).
> **Адресат:** агент следующей сессии, реализующий Phase 3 — n8n `03_AI_Engine.json` Safe PUT с Switch + HTTP Request callback, deployment, flag flip.
> **Статус PR A/B:**
> - PR #129 (mig 287 SQL): **merged 2026-05-20**.
> - PR #130 (Python handler + endpoint): **open**, CI green, safe to merge.

---

## TL;DR

Phase 1+2 готовы. Phase 3 — wire n8n callback в Python:

1. **Deploy step:** добавить `FOOD_LOG_RENDER_TOKEN` в `.env` на VPS + restart обоих сервисов.
2. **`dispatcher/forward.py`:** прокинуть `use_python_renderer` boolean в payload (читается из `app_constants.handler_food_log_use_python`).
3. **n8n `03_AI_Engine.json` Safe PUT:** добавить Switch node на `$json.use_python_renderer`, HTTP Request на `POST /internal/food_log/render` с token header.
4. **Flag flip:** `UPDATE app_constants SET value='true' WHERE key='handler_food_log_use_python'` после E2E smoke.
5. **Monitor 30 min:** `journalctl -u noms-webhooks -f | grep food_log` — на errors → flip обратно в false.

---

## Phase 1+2 что лежит в проде (после merge PR B)

### БД (mig 287, уже merged)

`log_meal_transaction` RPC возвращает return JSONB с дополнительными полями:
```json
{
  ... existing fields ...,
  "mana_max": 2,                  // ← mig 287
  "subscription_status": "free",  // ← mig 287 (informational)
  "hide_mana_block": false,       // ← mig 287 (DUMB-RENDERER FLAG)
  "language_code": "ru",          // ← mig 287
  "input_source": "voice"         // ← mig 287 (pass-through)
}
```

`app_constants`:
```
icon_carbs        = '🌾'    -- changed from 🥖
icon_mana         = '🔋'    -- changed from 🧪 (affects paywall too)
icon_protein      = '💪'    -- new
handler_food_log_use_python = 'false'  -- cutover flag (this PR flips)
```

`ui_translations` (× 13 langs): `food_log.confirmation_text_with_mana` / `_no_mana` (full templates), `food_log.total_label` / `remaining_label` / `unit_g` / `header_logged_word` / `noms_comment_prefix` / `header_text_single` / `header_text_multi`, `macros.p_short` / `f_short` / `c_short`, `gamification.points_label` / `mana_label`.

### Python (PR B, ждёт merge)

- `handlers/food_log.py:render_food_log_confirmation(payload, *, ctx_loader=None) -> ResponseEnvelope`
- `webhook_server.py:1288` — `POST /internal/food_log/render`:
  ```python
  Headers: X-Food-Log-Render-Token: <secret from env FOOD_LOG_RENDER_TOKEN>
  Body: JSON payload (см. payload schema ниже)
  Response: 200 {ok: true, items: 1}  | 503 (token not configured) | 403 (token mismatch) | 400 (bad JSON / missing telegram_id)
  ```

---

## Payload schema (что n8n должен слать в Python)

Это ровно то, что `log_meal_transaction` уже возвращает + items + n8n-specific fields:

```json
{
  "telegram_id": 786301802,
  "meal_id": "uuid-from-rpc",
  "input_source": "text|voice|photo|fasting",
  "items": [
    {
      "food_name": "Coffee with milk",
      "portion": "250ml",
      "calories": 50,
      "protein": 2, "fat": 2, "carbs": 6,
      "emoji": "☕"          // n8n Parse AI узел уже определяет emoji per item
    }
  ],
  "total_kcal": 50,
  "protein": 2, "fat": 2, "carbs": 6,
  "noms_comment": null,        // optional Sage one-liner (LLM-generated)

  // RPC log_meal_transaction passthrough:
  "xp_gained": 25,
  "streak_message": "🏆 Серия: 3 дн.",  // готовая локализованная строка (mig 285)
  "mana_remaining": 1,
  "mana_max": 2,                       // mig 287
  "hide_mana_block": false,            // mig 287 (DUMB-RENDERER FLAG)
  "language_code": "ru",
  "remaining_kcal": 1950                // alias for remaining_daily_calories
}
```

**Note:** Python handler читает `payload['mana_remaining']` (не `mana_current`) — это field name из RPC. Также `payload['remaining_kcal']` — handler возьмёт от такого имени. n8n должен передавать `remaining_daily_calories` из RPC как `remaining_kcal`.

---

## Step 1: Deployment (FOOD_LOG_RENDER_TOKEN)

На VPS `root@89.167.86.20`:

```bash
# Generate secure token
TOKEN=$(openssl rand -hex 32)
echo "FOOD_LOG_RENDER_TOKEN=$TOKEN" >> /home/taskbot/noms/.env

# CLAUDE.md rule: restart BOTH services (иначе cron со старым env)
systemctl restart noms-webhooks noms-cron

# Verify endpoint live
curl -i http://127.0.0.1:8443/internal/food_log/render -X POST  # → 403 (no token)
curl -i http://127.0.0.1:8443/internal/food_log/render -X POST \
     -H "X-Food-Log-Render-Token: $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{}'  # → 400 (missing telegram_id)
```

**ВАЖНО:** записать TOKEN в **n8n credential** (новый Generic API Key) — Phase 3 nodes будут читать из credential, не из ENV. Имя: `food_log_render_token`.

---

## Step 2: `dispatcher/forward.py` — flag injection

Прежде чем отправлять payload в n8n trigger, Python должен прокинуть флаг:

```python
# В функции build_payload(update, decision, ctx) или равноценной:
payload['use_python_renderer'] = (
    str(ctx.constants.get('handler_food_log_use_python', 'false')).lower() == 'true'
)
```

`ctx.constants` уже загружен в `dispatcher/context.py:get_user_context()` — без дополнительных DB hit. n8n трейггер получит `use_python_renderer: true|false` как обычное поле в payload.

См. `dispatcher/forward.py` для текущего payload-build pattern.

---

## Step 3: n8n `03_AI_Engine.json` Safe PUT

**Workflow:** self-hosted n8n на VPS `127.0.0.1:5678`. Workflow ID = `vpsLwafBNAFAIbXl` (проверь через `curl`).

Recipe — [[concepts/n8n-data-flow-patterns]] Safe PUT (workflow > 50 KB):

```
1. GET /api/v1/workflows/<wf_id> — fresh state
2. Parse JSON, find "Build Gamification Reply" + следующий "Send Telegram Message" pair
3. Insert pattern:
   • Switch node "Use Python Renderer?" reading {{$json.use_python_renderer}}:
     - true → ветка A (new HTTP Request)
     - false → ветка B (legacy Build Gamification Reply → Send Telegram, untouched)
4. Branch A:
   • Node "Build Python Payload" (Set node) — собирает payload по schema выше
   • Node "POST /internal/food_log/render" (HTTP Request):
     - URL: http://127.0.0.1:8443/internal/food_log/render
     - Method: POST
     - Headers: X-Food-Log-Render-Token: {{$credentials.food_log_render_token}}
     - Body: JSON (={{ $('Build Python Payload').item.json }})
   • НЕТ Send Telegram (Python отправит сам)
5. Whitelist {name, nodes, connections, settings} → PUT body
6. scp + curl PUT через VPS API
7. GET после PUT для verify
8. Manual trigger test через тестовый Telegram аккаунт (free + premium)
```

**Безопасность Safe PUT:** workflow > 50 KB → `--data @file`, не `--data '...'` (shell escape сломает большой JSON).

**Audit refs перед PUT:** `python n8n_workflows/_audit_refs.py` — на свежих версиях n8n PUT отклоняется HTTP 400 если есть dangling executeWorkflow refs ([[concepts/n8n-data-flow-patterns]] секция «PUT validation 10.05»).

---

## Step 4: Cutover flag flip

После успешного smoke (test аккаунт получает новый screen):

```sql
UPDATE app_constants SET value='true' WHERE key='handler_food_log_use_python';
```

`dispatcher/forward.py` начнёт класть `use_python_renderer=true` в payload → n8n Switch routes в новый branch → Python рендерит.

**Cache TTL:** `app_constants` имеет hot-reload через trigger (mig 198? — verify). Если flag не подхватился сразу — `curl POST /internal/stickers/reload` НЕ помогает (это для stickers); проверь через psycopg2 `SELECT value FROM app_constants WHERE key='handler_food_log_use_python'`.

---

## Step 5: Monitor + rollback

```bash
# 30 minutes watch:
ssh root@89.167.86.20 'journalctl -u noms-webhooks -f | grep -iE "food_log|FOOD_LOG_RENDER"'
```

При **>2 errors / 5 min** → flip обратно:
```sql
UPDATE app_constants SET value='false' WHERE key='handler_food_log_use_python';
```

Telegram-алерт в админ-чат `417002669` setup'нут через `crons/base.py` (5+ ERROR за 30s → alert).

---

## Edge cases / gotchas

### A. items emoji — где определяется?

В n8n `03_AI_Engine` нода `Parse AI` (JS code) определяет emoji per item на основе AI-распарсенного `food_name`. PR C agent должен убедиться что **n8n Build Python Payload** node прокидывает `emoji` field в каждый item. Если AI не определила — мой Python `_format_items_block` fallback'ит на `🍽️`.

### B. noms_comment — отдельный LLM-call или встроено в Vision?

Currently не реализовано в n8n. PR C agent может прокинуть `null` (мой handler graceful обрабатывает — block не рендерится). **TODO в отдельной сессии:** Sage dynamic insights (flash-model promo $≤0.01/req, context window = composition + remaining kcal + time of day).

### C. leveled_up — куда?

RPC возвращает `leveled_up: bool` + `new_level: int`. Mой Phase 2 handler **игнорирует** их (по плану TODO). PR C agent тоже не должен слать в Python — это будет отдельный экран с GIF/sticker в TODO-сессии.

### D. RPC поле `remaining_daily_calories` vs payload `remaining_kcal`

В моем handler я читаю `payload['remaining_kcal']` (для краткости). n8n Build Python Payload node должен **переименовать** `remaining_daily_calories` (из RPC) в `remaining_kcal` (для Python).

Альтернатива: можно правки в handler сделать чтобы он принимал оба имени (короткий fallback). Но Phase 3 agent выбирает что проще на n8n side.

### E. Legacy ветка должна остаться рабочей

Switch с `false` → старая Build Gamification Reply ноду → Send Telegram. Это safety net на случай если Python падает (flag flip в false возвращает legacy за секунды).

**Не удаляй** legacy ноды в этом PR — это Phase 4 cleanup (после 7+ дней stable production).

---

## Test plan (PR C session)

1. **Pre-merge tests (на staging если есть, иначе production tid=786301802):**
   - flag = false → юзер видит legacy n8n screen (unchanged).
   - flag = true → юзер видит новый Python screen.
   - 3 input source'а (text/voice/photo) → правильный input-icon (⌨️/🎤/📸).
   - Free tier → mana block visible. Premium tier → mana block hidden.
   - Logged streak (kept) → "🏆 Серия: N дн." present. Same-day re-log → no streak line.
   - Multi-item meal (2-3 items) → header shows count.
   - Edit/Delete buttons clickable → callback_data `food_log:edit:meal_id` (existing menu_v3 handler уже понимает).

2. **p95 benchmark** ([[feedback_latency_p95.md]]):
   - End-to-end (Telegram click → Python render → Telegram message visible) target < 700ms p95.
   - Internal endpoint latency: < 100ms median (loopback HTTP).

3. **Translation critic re-pass на live render** (можно skip если confident в mig 287 critic):
   - Skim RU + EN + 1-2 non-EN langs (AR/HI for RTL/Devanagari edge cases) — text wraps OK на mobile portrait.

---

## Owner-policy reminders

- **Snapshots:** PR C — pure n8n + config + flag flip. No DB changes (кроме UPDATE 1 row флага). No snapshots needed.
- **Деплой Python:** auto через GitHub Actions при merge PR B. Не делай `./deploy.sh` руками.
- **Деплой n8n:** Safe PUT через VPS API (`curl PUT /api/v1/workflows/{id}` с whitelist body). НЕ через коммит JSON в git и deploy.sh (last не обновляет runtime).
- **Force-push:** только `--force-with-lease`.

---

## Связано

- [[concepts/n8n-data-flow-patterns]] — Safe PUT recipe (workflow > 50 KB)
- [[concepts/architecture-registry]] — добавить новый callback endpoint после PR C merge
- [[handover/2026-05-20_food_log_pr_b_python_handler_brief]] — PR B brief (ныне реализован)
- [[handover/2026-05-19_stage6_payment_python]] — Stage 6 precedent (analogous cutover flow)
- `/Users/vladislav/.claude/plans/sharded-swinging-parnas.md` — full 3-PR plan
- `daily/2026-05-20.md` — PR A + PR B sessions
