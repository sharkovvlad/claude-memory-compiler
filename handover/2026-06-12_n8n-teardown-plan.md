# Handover 2026-06-12 — План полного выключения n8n (Variant B teardown, A→D)

## TL;DR
Owner хочет **завершить переезд n8n→Python и выключить n8n совсем**. Сейчас n8n=2 dormant workflow, Python обслуживает ~100%. Осталось закрыть редкие «провалы в legacy» и снести n8n. План — 4 этапа. **Этап A сделан (PR #390, pending merge).**

## Текущее состояние (2026-06-12)
- **n8n = 2 workflow**, оба простаивают:
  - `01_Dispatcher` (`7jVRdAvVlzOqIMEi`) — legacy fallback. forward_to_n8n ≈ 1/2дня.
  - `04_Menu_v3` (`0xJXA5M4wQUSiGXT`) — menu_v3 Python-native (`handler_menu_v3_use_python=true`), 0 executions. Чистый redundant.
- **ВСЕ `handler_*_use_python` = true + `dispatcher_python_authoritative` = true** → все «флаг off → forward» ветки в webhook_server = мёртвый код.
- Ничто не требует n8n. 01_Dispatcher's executeWorkflow-цели почти все DELETED (Go to 03_AI, Go to 04_Menu) → forward = silent drop.

## Этапы

### ✅ Этап A — food-media escape generalized (PR #390, pending merge)
photo/voice/image-doc = еда в любом статусе кроме онбординга (`_is_food_media_escape`, webhook_server.py ~1633). Закрыл главный класс потерь фото.

### Этап B — catch-all forward → Python graceful (ПОСЛЕ merge A + 2-3д мониторинга)
**НЕ слепо.** Сначала собрать на логах что РЕАЛЬНО ещё форвардится после Этапа A:
```bash
ssh root@89.167.86.20 'journalctl -u noms-webhooks --since "<deploy A>" | grep -B6 "TIMING forward_to_n8n" | grep -oE "target=[a-z_]+ reason=[a-z_]+|no_ctx" | sort | uniq -c'
```
Ожидаю единицы: text_food в odd-state, no_ctx (новый юзер), unknown.
Затем заменить:
- `webhook_server.py:474` (`if not handled: forward_to_n8n`) — финальный catch-all в `_route_or_forward`.
- `webhook_server.py:~1310` no_ctx (новый юзер без row) → Python `ensure_user` + onboarding.
- На что менять: graceful Python (render stats_main / safe ack / ensure_user). **Прецедент уже есть:** `target=error junk_content → spam_protect message` (webhook_server.py:1786, «n8n is being decommissioned. We own this response now, in Python»). Осторожно: не спамить меню на service-update'ы (reactions/edited) — no-op для не-user-meaningful.

### Этап C — dead-code cleanup
Удалить все «if not flag_use_python: forward_to_n8n» ветки (флаги навсегда on) + заменить `except → return False → forward` (handle_ai_input throw, webhook_server.py:1687) на graceful Python error (n8n пуст → сейчас silent drop).

### Этап D — DELETE n8n
После forward_to_n8n=0 несколько дней:
1. Safe PUT 01_Dispatcher: убрать `Go to 04_Menu_v3` executeWorkflow ref (последняя живая).
2. DELETE 04_Menu_v3 + 01_Dispatcher — **через обход `workflow_published_version` FK** (см. [[n8n-data-flow-patterns]]§published_version: backup → `DELETE FROM workflow_published_version WHERE workflowId=...` на живой БД → API DELETE).
3. `docker stop`/disable n8n контейнер. **n8n = 0. Переезд завершён.**

## Гейт между этапами
Каждый этап — отдельный PR + тесты + smoke. n8n DELETE (D) — только после подтверждённого forward_to_n8n=0 за чистое окно. Деплой Python — owner merge → GitHub Actions.

## Durable
- Принцип «photo/voice = еда в любом статусе кроме онбординга» в коде (Этап A).
- Git: backtick в `commit -m "..."` (double-quote) исполняется zsh → `commit -F file`.
- §12 stale-base: длинные сессии = main уходит, rebase+sanity-diff обязательны.
