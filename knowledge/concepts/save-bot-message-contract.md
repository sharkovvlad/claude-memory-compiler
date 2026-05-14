---
title: "save_bot_message Contract — обязательство для всех воркфлоу"
aliases: [save-bot-message, last_bot_message_id-contract, one-menu-contract]
tags: [architecture, one-menu, n8n, python, contract]
sources:
  - "Tech debt #7 PR #37 smoke 2026-05-14 (tid=786301802 12:48)"
  - "services/telegram_send.py:_clear_stale_last_bot_message defensive (lesson 14.05)"
  - "concepts/one-menu-ux.md (исходный паттерн)"
created: 2026-05-14
updated: 2026-05-14
---

# Контракт `save_bot_message` — One Menu UX integrity

## TL;DR

**Любой воркфлоу (Python handler / n8n sub-workflow / cron / mass-notify), который отправляет финальное user-visible сообщение в чат бота, ОБЯЗАН вызывать `save_bot_message(p_telegram_id, p_message_id, p_message_type)` после успешного `sendMessage`.**

Без этого Python authoritative router не сможет удалить старое меню при следующей навигации → юзер видит «кашу из старых и новых сообщений» в чате.

## Сигнатура RPC

```sql
public.save_bot_message(
  p_telegram_id BIGINT,
  p_message_id BIGINT,        -- mid от Telegram sendMessage response.message_id
  p_message_type TEXT         -- 'menu' для меню (One Menu candidate)
) RETURNS void
```

Эффект: `UPDATE users SET last_bot_message_id = p_message_id, last_bot_message_type = p_message_type, last_active_at = NOW()`.

## Почему это критично

`services/template_engine.py` для render_strategy `delete_and_send_new` и `edit_existing` (fallback path) использует `users.last_bot_message_id` как target для `deleteMessage`. Если оно stale (указывает на mid которого нет в чате) — Telegram возвращает 400 «message to delete not found», старое визуально-актуальное сообщение **остаётся в чате**, новое отправляется отдельно → «two menus on screen».

## Lesson 2026-05-14 (Tech debt #7 smoke)

Юзер 786301802 12:05 отправил текст еды → форвард на legacy n8n `02.1_AI_Engine`. Workflow вернул AI-результат «Мой день» с цифрами. **AI Engine не вызвал** `save_bot_message` с финальным mid — в БД остался stale mid от какого-то промежуточного сообщения (вероятно indicator/typing message, mid=4913).

12:48:07 юзер кликнул reply-kb «Мой профиль» → Python authoritative path → `delete_and_send_new(mid=4913)` → 400 «message to delete not found» → fallback `sendMessage` создал новый профиль-экран, но **orphaned AI «Мой день»** остался в чате.

12:48:17 cmd_confirm_delete → soft-delete (`delete_user_account` ставит `last_bot_message_id=NULL` per mig 079).

12:48:46 /start → AUTHORITATIVE_RESTORE_FLOW → restore_choice экран. **Юзер видит**: orphaned «Мой день» (legacy AI) + «Account deleted» + restore_choice. Тимлид: «каша из старого и нового».

Это **архитектурный долг** в legacy n8n воркфлоу: они должны вызывать `save_bot_message`, но не вызывают.

## Текущее состояние (на 14.05)

| Слой | save_bot_message? | Где |
|---|---|---|
| Python `webhook_server._send_and_persist` | ✅ Вызывает для `send_new` и `delete_and_send_new` (любой OutboundItem с новым mid) | `webhook_server.py:444-462` |
| n8n `04_Menu_v3` (legacy fallback) | ✅ Нода `20. Save Bot Message` | n8n self-hosted |
| n8n `02.1_AI_Engine` | ❌ **НЕ ВЫЗЫВАЕТ** — главный нарушитель | Phase 6.4+ миграция |
| n8n `Add food` | ❌ Подозрение (не проверено) | Phase 6.4+ |
| n8n `02.1_Location` (геолокация) | Уже Python (Phase 6.3) — ✅ через `_send_and_persist` | — |
| Python cron'ы (reminders, league_fomo, smart_freeze) | ⚠️ Большинство шлёт через `services/telegram_send` но НЕ через `_send_and_persist` → save_bot_message пропускается | Аудит TODO Phase 6.4 |

## Defensive guard в Python (added 14.05)

`services/telegram_send.py:_clear_stale_last_bot_message` — fire-and-forget cleanup при получении 400 «message to delete not found»:

```python
asyncio.create_task(_clear_stale_last_bot_message(chat_id))
# → save_bot_message(tid, None, None) → last_bot_message_id := NULL
```

Эффект: следующий navigate начнётся с чистого state и НЕ зациклится на призраке. **НО**: orphaned bubble в чате одноразово остаётся — Python не знает его mid. Полный фикс — заставить legacy n8n писать корректный mid (см. ниже).

## Чек-лист для агента Phase 6.4+ (миграция AI Engine на Python)

Когда переписываешь legacy n8n воркфлоу на Python handler:

1. **Не использовать `_post('sendMessage', ...)` напрямую** для финального user-visible сообщения. Использовать `ResponseEnvelope` + `_send_and_persist` (он сам зовёт `save_bot_message`).
2. **Если без envelope** (например, в кроне на массовую рассылку) — после успешного `sendMessage` явно: `await supabase.rpc("save_bot_message", {"p_telegram_id": tid, "p_message_id": mid, "p_message_type": "menu"})`.
3. **Indicator/typing/loading сообщения** — НЕ сохранять через save_bot_message. Они эфемерные, их удаляет сам отправитель. Иначе они залезут в `last_bot_message_id`.
4. **Стикеры** — не сохранять (см. `telegram_send.py:_dispatch_item` line 233-234: «стикеры не считаем меню»).
5. **Ghost-сообщения** (⏳ remove_keyboard) — не сохранять, они удаляются сразу.

## Migration audit script (для Phase 6.4)

После каждого Python-переписывания старого n8n воркфлоу — прогнать smoke:

```sql
-- Live UAT: вызвать новый воркфлоу для тестового юзера, потом проверить
SELECT last_bot_message_id, last_bot_message_type, last_active_at
FROM users WHERE telegram_id = <test_tid>;
-- Затем послать новое сообщение через бота → должно быть `delete_and_send_new`
-- → НЕ должно быть 400 «message to delete not found»
```

## Связанные KB

- [[concepts/one-menu-ux]] — исходный паттерн `last_bot_message_id` + RPC `save_bot_message`.
- [[concepts/one-time-attach-pattern]] — reply-kb lifecycle (mig 184/186 + Tech debt #7 closed).
- [[concepts/n8n-data-flow-patterns]] — `$json` clobber, PUT-get-first, save_bot_message position.
- [[concepts/architecture-registry]] — карта Python authoritative vs legacy n8n targets.

## Open TODOs

- **Phase 6.4 (AI Engine миграция):** при переписывании `02.1_AI_Engine` на Python — обеспечить save_bot_message для финального мил-карточки сообщения. Это автоматически закроет orphaned-bubble baseline.
- **n8n audit (можно сделать до Phase 6.4):** для всех оставшихся legacy воркфлоу (Add food, AI Engine, оставшиеся nodes 01_Dispatcher) — найти все финальные `sendMessage` ноды и добавить PG-нодой `save_bot_message`. Это «купит время» до полной миграции.
- **Cron audit:** все Python cron'ы (`crons/*.py`) — проверить что они либо НЕ шлют user-visible меню, либо вызывают `save_bot_message`. Особенно: `cron_get_reminder_candidates`, `cron_league_fomo_push`, `cron_league_midweek_push`, `cron_check_streak_breaks` (smart freeze notifications).
