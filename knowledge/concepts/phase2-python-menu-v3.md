# Phase 2 — Python `menu_v3` handler + Template Engine

**Статус:** ✅ В проде с 2026-04-30. Все корневые экраны (`profile_main`, `stats_main`, `progress_main`) и подменю (Settings, Shop, Friends, Quests, League, Ambassador Payout user side, Edit pickers) обслуживаются Python-обработчиком вместо n8n workflow `04_Menu_v3` (`0xJXA5M4wQUSiGXT`).

**Контекст:** второй этап миграции `n8n → Python`. Phase 0.5+1 (Dispatcher router в shadow-mode) задеплоен 28.04. Phase 2 — конечный handler. Variant B (authoritative cutover Диспетчера) включён 30.04 параллельно.

**Цель:** заменить ~1.8s end-to-end latency через n8n на ~60-90ms через нативный Python.

---

## 1. Архитектура

```
Telegram update
   ↓
webhook_server.telegram_webhook (port 8443)
   ↓ ack ≤10ms + 3 fire-and-forget tasks:
   ├─ maybe_send_indicator
   ├─ maybe_sync_user_profile
   └─ _route_or_forward(update, body, fwd_hdr, t0):
        ↓
        1. B-3 authoritative path (Variant B Диспетчера)
           — если флаг dispatcher_python_authoritative=true И admin gate passes
           — диспатчит в per-target n8n webhook ИЛИ зовёт handle_menu_v3
        ↓ если не handled →
        2. Phase 2 path
           — get_user_context(chat_id) → UserCtx
           — _menu_v3_flag_from_ctx(ctx) → bool (читает app_constants)
           — если flag ON и route(update, ctx).target == "menu_v3":
             ↓
             handle_menu_v3(update, ctx, decision)
                ↓
                1. Pre-validation (ADR-3) для action_type=text:
                   services.screen_validation.validate_text_input(status, text)
                   → если fail → error envelope с локализованным error_key, БЕЗ RPC
                ↓
                2. RPC call:
                   dispatch_with_render(p_telegram_id, p_action_type, p_payload,
                                        p_cb_context, p_skip_debounce=false)
                   → возвращает headless telegram_ui:
                     {render_strategy, text_key, keyboard, template_vars,
                      callback_message_id, last_bot_message_id, reply_keyboard?}
                ↓
                3. services.template_engine.render_envelope:
                   — резолв text_key через ctx.translations (Two-pass)
                   — резолв keyboard в inline_keyboard
                   — выбор Telegram-стратегии (delete_and_send_new / edit_existing /
                     send_new) на основе render_strategy + message_id'ов
                   — опциональный attach_reply_kb item если reply_keyboard в RPC
                ↓
             ResponseEnvelope (1-3 OutboundItem)
                ↓
             webhook_server._send_and_persist(envelope, telegram_id):
                — services.telegram_send.send(envelope)
                — если SendResult.last_message_id заполнен → save_bot_message RPC
        ↓ если не handled (flag OFF или не menu_v3) →
        3. forward_to_n8n(body, fwd_hdr) — legacy путь
```

---

## 2. Feature Flags (все hot-reload через `app_constants_cache` trigger)

| Ключ | Категория | Назначение | Owner |
|---|---|---|---|
| `handler_menu_v3_use_python` | `feature_flags` | Phase 2: when `true`, routes `target=menu_v3` updates to Python handler | Phase 2 |
| `dispatcher_python_shadow_mode` | `dispatcher` | Phase 1: shadow router runs in parallel with n8n (observation) | Диспетчер |
| `dispatcher_python_authoritative` | `dispatcher` | Variant B cutover: Python OWNS routing decision, bypasses 01_Dispatcher | Диспетчер |
| `dispatcher_python_authoritative_admin_only` | `dispatcher` | Staged rollout: authoritative Python serves ONLY ADMIN_TELEGRAM_ID=417002669 | Диспетчер |

Hot-reload: `UPDATE app_constants SET value='true' WHERE key='...';` — триггер обновляет кэш, Python читает свежее значение на следующем webhook'е (без рестарта `noms-webhooks`).

**Env fallbacks:** `HANDLER_MENU_V3_USE_PYTHON`, `HANDLER_DISPATCHER_USE_PYTHON` — kill-switch на cold start или БД-down.

---

## 3. Template Engine (`services/template_engine.py`)

`dispatch_with_render` возвращает **headless** структуру (text_key + keyboard array с text_key/icon_const_key + template_vars), НЕ готовый Telegram payload. Template Engine резолвит её в финальный payload.

### Text resolution (Two-pass)

```python
text_key = "profile.main_text"
# 1. Достать template из ctx.translations через dot-path
template = ctx.translations["profile"]["main_text"]
# 2. Pass 1: {tr:section.key} → nested translations
template = re.sub(r"\{tr:([^}]+)\}", lookup_translation, template)
# 3. Pass 2: {var} → template_vars (P1) → ctx.constants (P2)
template = re.sub(r"\{([^{}:]+)\}", resolve_var, template)
```

**HTML escaping:** user-input поля (`first_name`, `last_name`, `name`, `display_name`, `username`) экранируются через `html.escape()` ДО подстановки — защита от инжекта при `parse_mode=HTML`.

**Fallback:** literal text_key / unmatched `{...}` остаётся в тексте (видим в логах missing translation).

### Keyboard build

| input_type | Telegram reply_markup |
|---|---|
| `inline_kb` (default) | `{inline_keyboard: [[btn,...],...]}` |
| `text_input` | `{remove_keyboard: true}` |
| `reply_kb_request_contact` | `ReplyKeyboardMarkup` с `request_contact:true` (для `payout_phone_request`) |

Каждая кнопка: `text = "{icon} {text}"` (с пробелом, trim если icon пуст). `is_current=true` → prefix `"{icon_check} "` (constants.icon_check, fallback `✅`).

### Render strategies

| Стратегия | Поведение |
|---|---|
| `send_new` | sendMessage |
| `edit_existing` | editMessageText(callback_message_id) |
| `edit_existing` без callback_message_id | **Fallback** на delete_and_send_new (mixed-trigger pattern из CLAUDE.md правило 7) |
| `delete_and_send_new` + last_bot_message_id | deleteMessage(old) + sendMessage |
| `delete_and_send_new` + last_bot_message_id NULL | sendMessage без delete (нормально для нового юзера) |
| `noop` | empty envelope |

**chat_id:** всегда `ctx.telegram_id` (NOMS = только private chats).
**parse_mode:** `HTML` (тексты в `ui_translations` используют `<b>`, `<blockquote expandable>`).

---

## 4. Reply-keyboard logic (Migration 159 + 160)

### Initial design (Migration 159, 30.04)
Безусловно возвращать `reply_keyboard` для корневых экранов (`profile_main`, `stats_main`, `progress_main` с `meta.reply_kb_entry=true`). Python создаёт `attach_reply_kb` item — отдельный sendMessage с минимальным text + ReplyKeyboardMarkup.

**Live test 30.04 18:11 MSK обнаружил проблему:**
- Видимый `·` пузырь после каждого захода на корневой экран
- Попытка скрыть через delete-after-send **убирает клавиатуру** (Telegram привязывает reply_markup к message_id, а НЕ к chat state как изначально казалось)

### Final design (Migration 160, 30.04)
**NOMS НЕ перепривязывает reply_keyboard на каждом render.** Telegram держит её через цепочки `editMessageText`. Re-attach нужен ТОЛЬКО когда что-то её сняло — а в Phase 2 это **только** `text_input` экраны (они шлют `remove_keyboard:true`).

```sql
-- В render_screen telegram_ui:
'reply_keyboard', CASE
    WHEN COALESCE(v_screen.meta->>'reply_kb_entry', '') = 'true'
     AND v_user.previous_status IN (
         SELECT ws.state_code FROM workflow_states ws
         JOIN ui_screens scr ON scr.screen_id = ws.screen_id
         WHERE scr.input_type = 'text_input'
     )
    THEN public.build_main_reply_keyboard()
    ELSE NULL END
```

**Эффекты:**
- Inline-навигация (`profile_main → cmd_settings → cmd_back → profile_main`): `reply_keyboard=NULL` → нет carrier'а → клавиатура остаётся через chat state ✓
- Transition `edit_weight → save → root`: `previous_status='edit_weight'` → carrier восстанавливает клавиатуру ✓
- Onboarding completion остаётся за `02_Onboarding_v3` "Send Main Menu" — первая установка через осмысленное сообщение ✓

**Wishlist (отдельная фаза):** перенести re-attach из render_screen в save-toasts (`messages.saved`, `edit_food.cancelled`) — NLM-ideal архитектура.

---

## 5. Validation (Phase 2)

**Pre-validation для numeric input** (ADR-3, `services/screen_validation.py`):
- Lazy-loaded TTL-кеш (5 мин) загружает `ui_screens.validation_rules` + `workflow_states.state_code → screen_id`
- Для `action_type=text`, status в text_input статусах — type cast + min/max ДО RPC
- Fail → error envelope с локализованным `error_key` БЕЗ network roundtrip (~46ms экономии)
- SQL-сторона (`validate_text_input` внутри `process_user_input`) ВСЕГДА перепроверяет — Python — оптимизация, не security
- Fail-open при ошибке загрузки кеша → пропускаем в SQL

---

## 6. One Menu UX persistence

**save_bot_message RPC** (тот же контракт, что узел "20. Save Bot Message" в n8n 04_Menu_v3):

```python
# webhook_server._send_and_persist:
result = await telegram_send(envelope)
if result.last_message_id is not None:
    await supabase.rpc("save_bot_message", {
        "p_telegram_id": telegram_id,
        "p_message_id": result.last_message_id,
        "p_message_type": "menu",
    })
```

`SendResult.last_message_id` обновляется ТОЛЬКО для:
- `send_new` (новый message_id)
- `delete_and_send_new` (новый message_id после delete + send)

НЕ обновляется для:
- `edit_existing` (тот же message_id)
- `send_sticker` (стикеры не считаются "меню")
- `answer_callback_only` (нет message)
- `attach_reply_kb` (carrier не должен перетирать last_message_id основного inline-сообщения)

---

## 7. Артефакты Phase 2

### SQL миграции
- **156** `phase2_menu_v3_feature_flag.sql` — `handler_menu_v3_use_python` в app_constants
- **159** `main_reply_keyboard.sql` — `build_main_reply_keyboard()` helper + `render_screen` patch + `UPDATE profile_main.meta`
- **160** `reply_keyboard_conditional_attach.sql` — условный re-attach по `previous_status`

### Python модули
- `handlers/menu_v3.py` — `handle_menu_v3()` entrypoint
- `services/template_engine.py` — Two-pass text resolution, keyboard build, render_envelope
- `services/screen_validation.py` — TTL-кеш + pre-validation
- `services/envelope.py` — `OutboundStrategy` literal + `attach_reply_kb` стратегия + `SendResult.last_message_id`
- `services/telegram_send.py` — диспетч стратегий через httpx, message_id extraction
- `webhook_server.py` — `_route_or_forward` async helper + `_send_and_persist` обёртка + `_menu_v3_flag_from_ctx`

### Тесты (всего 60+)
- `tests/handlers/test_menu_v3.py` (~40 кейсов)
- `tests/services/test_template_engine.py` (34 кейса)
- `tests/services/test_screen_validation.py` (30 кейсов)
- `tests/services/test_telegram_send.py` (25 кейсов, +5 для attach_reply_kb)
- `tests/test_webhook_helpers.py` (20 кейсов)
- `tests/integration/test_dispatch_render_e2e.py` (6 кейсов, skip без `DATABASE_URL`)

---

## 8. Lessons learned (инциденты дня)

### Инцидент #1 — 14:39 MSK: 400 Bad Request на каждом клике после первого включения флага
**Корневая причина:** unit-тесты мокали готовый Telegram payload в RPC return, реальный RPC возвращает headless шаблон. `parse_render_response()` из `services/render.py` (старая) не делала резолв text_key/keyboard.
**Решение:** новый `services/template_engine.py` (commit `c7b1671`).
**Lesson:** интеграционный тест против реального RPC обязателен для всех новых RPC-обёрток.

### Инцидент #2 — 14:39 MSK: ack_ms=200-620мс вместо <10мс
**Корневая причина:** `await get_user_context` + `await handle_menu_v3` inline в webhook handler перед `return Response(200)`.
**Решение:** вынос всей логики в `asyncio.create_task(_route_or_forward(...))` — fire-and-forget pattern (commit `a735647`).

### Инцидент #3 — 17:00 MSK: 6-секундный elapsed_ms на save_bot_message
**Корневая причина:** `supabase_client.rpc()` считал HTTP 204 No Content ошибкой (для VOID функций PostgREST возвращает 204) → retry × 3 с экспоненциальной паузой.
**Решение:** explicit `if response.status_code == 204: return None` (commit `47d70dd`).

### Инцидент #4 — 18:11 MSK: reply-keyboard пропадает после клика
**Корневая причина:** delete-after-send паттерн (для скрытия `·`) убирает клавиатуру (Telegram привязывает reply_markup к message_id, не chat state).
**Решение:** revert delete + Migration 160 с условным re-attach (commit `aace114`).
**Lesson:** "reply_keyboard это chat state" — частично верно. Удаление **carrier**-сообщения убирает клавиатуру; `editMessageText` другого сообщения — нет.

### Конфликты миграционных номеров (3 за день)
Параллельная работа двух агентов (Phase 2 + Variant B Диспетчера) на main без feature-branches → конфликты имён файлов миграций:
- 155: занят Диспетчером → Phase 2 → 156
- 157: занят Диспетчером → Phase 2 159
- 158: занят Диспетчером

**Lesson:** при параллельной работе агентов рекомендуется feature branches + PR — конфликты будут видны через GitHub до push в main.

---

## 9. Pending / Wishlist

1. **Save-toast reply_keyboard re-attach** — переместить из render_screen в save flow (`messages.saved`, `edit_food.cancelled`). Архитектурно правильнее, но требует переделки save flow в SQL/Python.
2. **UI шаблоны cleanup** — в `ui_translations` есть literal плейсхолдеры типа `{👤}`, `{tr:calendar.month_1}`, `{{goal_lose}}` которые не резолвятся (data-layer issue, обнаружено при live test).
3. **`forward` status в menu_v3** — RPC иногда возвращает `status="forward"` который не должен случаться для menu_v3. Сейчас логируем и noop. Если повторится в логах — копать.
4. **`AUTHORITATIVE_MENU_V3 ack_ms~200мс`** — Variant B Диспетчер обернул мой fire-and-forget в синхронный wrapper. Если Тимлид хочет вернуться к 0мс ack — Диспетчеру обернуть свой call в task.

---

## 10. Соотношение с Variant B (Диспетчер)

**Не конфликтуют, разные ярусы:**
- **Variant B** заменяет **Оркестратор/Роутер** (`01_Dispatcher` → `dispatcher/forward.py` + B-1 webhooks в 5 sub-workflows)
- **Phase 2** заменяет **конечный Хендлер** (`04_Menu_v3` → `handlers/menu_v3.py`)

**Когда оба включены** (как сейчас):
1. Webhook принимает update
2. B-3 authoritative path (Variant B): Python OWNS routing decision
3. Если target == "menu_v3" → зовёт мой `handle_menu_v3()`
4. Если другой target → forward в per-target n8n webhook (через `dispatcher/forward.py`)

---

## Ссылки

- [headless-architecture](headless-architecture.md) — общий паттерн Headless UI
- [headless-template-substitution](headless-template-substitution.md) — Two-pass resolution детали
- [n8n-template-engine](n8n-template-engine.md) — n8n Dumb Renderer (referenced as ground-truth)
- [python-telegram-adapter](python-telegram-adapter.md) — telegram_send.py детали
- [n8n-data-flow-patterns](n8n-data-flow-patterns.md) — правило 7 "Mixed triggers" + другие паттерны
- [dispatcher-callback-pipeline](dispatcher-callback-pipeline.md) — callback pipeline в n8n (legacy reference)
- [migrations/156](../../../migrations/156_phase2_menu_v3_feature_flag.sql)
- [migrations/159](../../../migrations/159_main_reply_keyboard.sql)
- [migrations/160](../../../migrations/160_reply_keyboard_conditional_attach.sql)
- [daily/2026-04-30](../../daily/2026-04-30.md) — день Phase 2 в проде
