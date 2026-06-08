# Handover 2026-06-05 — Edit Meal → Python (Phase 5) + Stage 7c gate

## TL;DR
Edit Meal re-recognition (`reason='editing_meal'`) **переведён на Python** (PR #326, LIVE-verified). Отдельное spam-сообщение «+5 XP» убрано (PR #327, pending merge). **Stage 7c (физический DELETE n8n 03/06) ещё НЕЛЬЗЯ** — нужен мониторинг до 0 executions.

## Что было сделано

### 1. PR #326 — wire editing_meal в Python AI-гейт (MERGED + DEPLOYED)
- **Проблема:** Python edit-pipeline (`handlers/food_log._handle_edit_meal_input`, Stage 7b PR D `d6f4c72`) был смержен, но **мёртв в проде**: webhook AI-гейт пропускал только `reason.startswith(('food_media','text_food'))`, а роутер для редактирования ставит `reason='editing_meal'` → fall through в легаси n8n `03_AI_Engine`. Merged-but-unwired latent bug.
- **Fix:** `webhook_server.py` — reason-предикат гейта расширен на `'editing_meal'`; distinct лог `AUTHORITATIVE_AI_EDIT`. `handle_ai_input` уже диспатчил на edit-хендлер по `ctx.status=='editing_meal'`.
- **LIVE-verified** (tid=417002669, 2026-06-05 13:25): edit → `AUTHORITATIVE_AI_EDIT`, n8n 03 не вызывался.
- Все RPC (`replace_meal_transaction`/`grant_correction_xp`/`clear_editing_state`/`get_meal_by_id`) в проде. Миграций нет.

### 2. PR #327 — убрать дубль-сообщение «+5 XP» (pending merge, CI green)
- Edit слал 2 сообщения: карточка (footer «🌟 +5») + отдельный toast (mig 376). Anti-spam → toast убран, XP остаётся в карточке (`payload["xp_gained"]`).

### 3. (Контекст из 06-02) n8n деактивация + Switch cleanup
- `03_AI_Engine`+`06_Indicator_Clear` → `active=0` (SQLite UPDATE; API `/deactivate`=Forbidden на n8n 2.17.7). `04_Menu_v3` Switch — убраны мёртвые case onboarding/location.

## Что ОСТАЛОСЬ (для следующего агента) — Stage 7c

**Гейт: НЕ календарь, а 0 реальных executions.** После merge+deploy #326/#327 мониторить ~3-5 дней:
```bash
# Python edit работает:
ssh root@89.167.86.20 'journalctl -u noms-webhooks --since "<дата>" | grep -c AUTHORITATIVE_AI_EDIT'   # >0, растёт
# n8n 03 больше не зовётся:
ssh root@89.167.86.20 'docker cp noms-n8n:/home/node/.n8n/database.sqlite /tmp/n.sqlite && sqlite3 /tmp/n.sqlite "SELECT COUNT(*),datetime(MAX(startedAt)) FROM execution_entity WHERE workflowId=\"kjw4kkKMD0IqNALg\" AND startedAt>datetime(\"now\",\"-24 hours\")"'   # ожидаем 0
```
**Когда n8n 03 exec = 0 за чистые несколько дней:**
1. DELETE Python endpoint `/internal/food_log/render` (`webhook_server.py`) — он больше не нужен (Python global food-path использует `_send_and_persist`, edit — тоже Python). PR + deploy.
2. Safe PUT `01_Dispatcher` Route Classifier — убрать `Go to 03_AI` executeWorkflow branch (recipe [[concepts/n8n-data-flow-patterns]] §Safe PUT).
3. n8n DELETE workflows `03_AI_Engine` (`kjw4kkKMD0IqNALg`) + `06_Indicator_Clear` (`jQn0nTxThFal4Kpe`).

## Гайки / уроки
- **«Время прошло» ≠ «путь мёртв».** Verify-first перед DELETE поймал живой edit-трафик в n8n несмотря на день 7 и `active=0` (executeWorkflow игнорирует active). Гейт удаления = 0 executions.
- **n8n 2.17.7:** деактивация только SQLite `UPDATE workflow_entity SET active=0` на `/home/noms/n8n/data/database.sqlite` (API `/deactivate`=Forbidden, PUT не меняет active).
- **Улучшения Python edit vs n8n:** поддержка фото-edit (n8n деградировал в текст); edit без mana-gate (n8n блокировал mana=0). `edit_count`/`raw_user_input` closed-loop — follow-up.

Детали — daily/2026-06-05.md, KB [[concepts/stage7-global-cutover]] §поправка-06-05, [[concepts/architecture-registry]] §Phase5.

---
## ✅ ЗАКРЫТО 2026-06-08
Stage 7c выполнен полностью: n8n `03_AI_Engine`+`06_Indicator_Clear` DELETED; refs убраны Safe PUT (01_Dispatcher, 04_Menu_v3); render-endpoint удалён (PR #374 merged+deployed). n8n 7→5 workflow. Owner verified распознавание (786301802). AI Engine полностью в Python. Делать по этой теме больше нечего.
