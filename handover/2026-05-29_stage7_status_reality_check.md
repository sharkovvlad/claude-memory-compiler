# Handover: Stage 7 (Python AI Engine) Status Reality Check

**Дата:** 2026-05-29
**От:** Nutritionist Agent 10 (continuation of Nutritionist 9 handover)
**Кому:** следующий агент, который возьмёт Stage 7c cleanup или решит global cutover
**Owner:** Vladislav

---

## TL;DR простыми словами

**MEMORY.md и handover Nutritionist 9 утверждали:** «Stage 7 Python AI Engine — GLOBAL CUTOVER, все 1000+ юзеров уже на Python». На основании этого предполагалось, что Stage 7c (выключение n8n `03_AI_Engine` + `06_Indicator_Clear`) — это безопасный cleanup через 1-2 недели.

**Реальность 29.05:**
- Python обрабатывает AI-распознавание **только для owner-а** (`telegram_id=417002669`)
- Остальные ~97 активных юзеров (за 7 дней) до сих пор едут через n8n `03_AI_Engine`
- n8n зовёт Python `/internal/food_log/render` endpoint, чтобы отрендерить карточку еды
- Это **гибридная** архитектура, не «Python всюду»

**Поэтому Stage 7c (выключение n8n) сейчас сломает 75% распознаваний еды.** Прежде чем cleanup — нужно сначала **global cutover** (Python для всех) и 7 дней без регрессий.

---

## Доказательства (за 2 минуты можно проверить себе)

### 1. БД флаги

```bash
python3 -c "
import os, psycopg2
from dotenv import load_dotenv; load_dotenv()
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute(\"SELECT key, value FROM app_constants WHERE key LIKE '%ai_engine%';\")
for r in cur.fetchall(): print(r[0], '=', r[1])
"
```
Возвращает:
```
ai_engine_beta_testers = [417002669]      ← ТОЛЬКО owner
handler_ai_engine_use_python = true
```

### 2. Gate в коде

[webhook_server.py:1621-1627](webhook_server.py:1621):
```python
if (
    target == "ai"
    and (decision.reason or "").startswith(("food_media", "text_food"))
    and (ctx.status or "") in ("registered", "editing_meal")
    and _read_handler_ai_engine_use_python(ctx)
    and _user_in_ai_beta_allowlist(chat_id, ctx)     # ← KEY GATE
):
```

`_user_in_ai_beta_allowlist` ([webhook_server.py:1221](webhook_server.py:1221)) проверяет, есть ли `chat_id` в `ai_engine_beta_testers` JSONB-массиве. Если нет — функция возвращает `False`, и юзер падает в `return False` ниже → forward в n8n.

### 3. Live n8n executions (29.05, 20:00 МСК)

Через SQLite БД n8n (`/home/node/.n8n/database.sqlite` внутри `noms-n8n` контейнера):

```
workflowId        cnt  first_seen           last_seen
----------------  ---  -------------------  -------------------
7jVRdAvVlzOqIMEi   16  2026-05-27 17:31:06  2026-05-29 17:10:52  (01_Dispatcher)
kjw4kkKMD0IqNALg   13  2026-05-27 17:31:07  2026-05-29 16:26:48  (03_AI_Engine)
jQn0nTxThFal4Kpe    4  2026-05-27 17:33:32  2026-05-29 16:24:26  (06_Indicator_Clear)
```

(API endpoint `/api/v1/executions?workflowId=...` отдаёт пустой массив — это известный n8n self-hosted quirk. Достоверный источник — SQLite напрямую.)

### 4. food_logs split за 24ч

```
('others', 9)   ← 9 успешных распознаваний еды не-owner юзерами через n8n
('owner', 3)    ← 3 распознавания owner-а через Python
```

### 5. Git smoking gun

Коммит 203b798 (25.05): «feat(ai-engine): force dynamic Sage **for n8n users** via /internal/food_log/render».

Автор этого коммита **прямо знал**, что non-admin юзеры всё ещё идут через n8n — он специально добавил трюк, чтобы они получили dynamic Sage комментарий через Python-render-endpoint. Это **prove** что архитектура гибридная by-design сейчас.

---

## Текущая фактическая архитектура (29.05)

```
Юзер шлёт фотку еды
    ↓
Telegram → Caddy :443 → Python webhook_server :8443
    ↓
_route_or_forward_locked
    ↓
target='ai', reason='food_media'
    ↓
    ├── chat_id == 417002669 (owner) ─→ handlers/food_log.handle_ai_input
    │                                    OpenAI Vision + log_meal_transaction
    │                                    + render carрочки + send Telegram
    │
    └── другой юзер ─→ forward_to_n8n('01_Dispatcher')
                       n8n Route Classifier → executeWorkflow '03_AI_Engine'
                       OpenAI Vision + log_meal_transaction RPC
                       ↓
                       HTTP POST /internal/food_log/render (Python)
                       Python рендерит карточку + send Telegram
```

То есть **разделение по юзеру**: 1 юзер — full-Python, остальные — hybrid (n8n recognition + Python render).

---

## Что значит «Stage 7 global cutover»

Это **раскатать Python recognition path на всех**, отключить n8n recognition. Шаги (рекомендованные):

### A. Расширить allowlist пошагово (3-7 дней)

Не один кликом, а волнами:

1. **Wave 1 (+5 power users)** — добавить 5 trusted юзеров в `ai_engine_beta_testers`. Мониторить 24ч:
   - Нет роста error rate в logger.exception в webhook_server
   - food_logs создаются (psycopg2 SELECT за час, сравнить с baseline)
   - Время от send до карточки <2 сек (telegram_send.py logs)

2. **Wave 2 (+20 active users)** — если Wave 1 чистый. Снова 24ч мониторинга.

3. **Wave 3 (all active users last 7d)** — добавить всех `last_active_at > now() - 7d`. 48ч мониторинга.

### B. Заменить gate на `true` (clean removal)

Когда Wave 3 прошёл — убрать allowlist gate целиком. Опции:

**Option B1 — DB-only:**
```sql
UPDATE app_constants SET value = 'all' WHERE key = 'ai_engine_beta_testers';
```
И в `_user_in_ai_beta_allowlist` (webhook_server.py:1221) добавить check: `if raw == 'all': return True`. Минимальное изменение кода.

**Option B2 — code removal:**
Удалить `_user_in_ai_beta_allowlist` функцию + удалить `and _user_in_ai_beta_allowlist(chat_id, ctx)` из gate. Удалить `ai_engine_beta_testers` row из `app_constants`. Это «правильно», но требует Python deploy.

Рекомендую **B1** для быстрого global, **B2** только когда уверены и хотим cleanup.

### C. 7 дней stable (мониторинг)

Метрики:
- food_logs за 24ч > baseline (95% от среднего за неделю до)
- 0 P0 incidents в logger.exception (grep `AUTHORITATIVE_AI ... handler failed`)
- Юзеры не пишут «бот не понял фотку» (можно прокси-мониторить через `cmd_show_meals` логи или Telegram support)

### D. Stage 7c (выключение n8n) — то, что я сегодня хотел сделать

Только когда C прошёл:

1. **Verify n8n executions = 0 за 24ч** для `03_AI_Engine` и `06_Indicator_Clear` (через SQLite, не API)
2. **n8n PUT active:false** для обоих workflows (Safe PUT recipe — KB [[concepts/n8n-data-flow-patterns]])
3. **DELETE `/internal/food_log/render`** endpoint в `webhook_server.py:1836-1918` (~80 строк)
4. **Cleanup `_read_handler_ai_engine_use_python` + `_user_in_ai_beta_allowlist`** функции (webhook_server.py:1202-1244)
5. **Cleanup gate** в webhook_server.py:1611-1667 — убрать условие, оставить только сам handle_ai_input (теперь всегда)
6. **Cleanup tools/parity_check.py, tools/_n8n_03_ai_engine_modify.py, tests/test_webhook_ai_engine_gate.py** — fossil files
7. **n8n DELETE workflows** через API (после 1 нед deactivated)

---

## Альтернатива global cutover — оставить гибрид

Если global cutover пугает (валидно, n8n recognition стабилен 9 месяцев — Python новый), можно **сохранить гибрид** и:

- Удалить из MEMORY ложный claim про «GLOBAL CUTOVER»
- Пометить Stage 7c как **WONTFIX / DEFERRED** до окончания всей миграции
- Документировать гибрид как намеренное архитектурное решение

В этом случае ничего не делать. Просто факты обновить.

---

## Smoke-test recipe (чтобы убедиться что юзер действительно на n8n)

Если хочешь проверить лично сейчас (не owner-овым аккаунтом):

```sql
SELECT telegram_id, status, last_active_at
FROM users
WHERE last_active_at > NOW() - INTERVAL '24 hours'
  AND telegram_id <> 417002669
  AND status = 'registered'
ORDER BY last_active_at DESC LIMIT 5;
```

Взять любой `telegram_id`, попросить юзера прислать фотку еды, посмотреть в логах:

```bash
ssh root@89.167.86.20 "journalctl -u noms-webhooks --since '5 minutes ago' | grep -E 'AUTHORITATIVE_AI|forward_to_n8n|03_AI_Engine'"
```

Если видишь `forward_to_n8n` → юзер прошёл n8n путём. Если `AUTHORITATIVE_AI ... return True` → Python путь.

---

## Связанные неточности в MEMORY (которые я починил)

| Было | Стало |
|---|---|
| Migration HEAD: 360 | 371 |
| «Stage 7 GLOBAL CUTOVER, all 1000+ users» | admin-only canary, ~97 active users last 7d |
| «BMI/min_kcal warnings — copywriter pending» | ✅ DONE через mig 270 |
| «Maternal sub-menu labels — 11 langs EN fallback» | ✅ DONE через mig 269+286+361 |
| «Stage 7c cleanup after 1-2 нед stable global» | BLOCKED — global не было, decision нужен |

---

## Что я НЕ изменил (потому что трогать руками опасно)

- **Сам код Stage 7 path** (handlers/food_log.handle_ai_input + endpoint /internal/food_log/render) — работает, не трогаю
- **БД флаги** — никаких UPDATE без owner approval
- **n8n workflows** — никаких PUT без owner approval

---

## Что нужно от owner-а

Один из 3 ответов:

**(1) «Промоутить Stage 7 в global сейчас»** — расширить allowlist волнами, мониторинг, через ~7-10 дней Stage 7c cleanup.

**(2) «Оставить гибрид»** — обновить документацию, пометить Stage 7c как WONTFIX, дальше живём как есть.

**(3) «Не сейчас, обсудим позже»** — текущий state корректно документирован, можно продолжать другими задачами (Adaptive TDEE, dynamic Katch-McArdle clinical, и т.д.).

— Nutritionist Agent 10
