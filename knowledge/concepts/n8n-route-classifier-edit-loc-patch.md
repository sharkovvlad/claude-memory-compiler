# 01_Dispatcher Route Classifier — edit-location reply-back early branch (patch v9, 08.05.2026)

**Контекст:** временный fix между Phase 4 (онбординг в Python) и Phase 5 (location migration в Python). Будет removed после Phase 5.

## Проблема, которую решает

Юзер на `cmd_edit_country` / `cmd_edit_timezone` (Profile v5 status `edit_country`/`edit_timezone`) кликает «Авто (геолокация)» → попадает в `02.1_Location` → `Ask Location Permission` рендерит reply-keyboard «📍 Send Location» + «🔙 Back».

Когда юзер кликает «🔙 Back» reply-button — Telegram отправляет text `${icon_back} ${buttons.back}` БЕЗ callback_query. Router 01_Dispatcher (legacy) ловил это в ветке `profile_v5_text_input` (PROFILE_V5_STATUSES + text → menu_v3), но menu_v3 не имеет handler'а для arbitrary text в edit_* статусе → silent drop. Ни 👌 carrier, ни восстановление main reply_kb не происходило. Юзер застревал с 2-кнопочной reply-keyboard до явного `/start`.

## Решение

В `01_Dispatcher` workflow `Route Classifier` JS-нода (typeVersion 1.8) — **early branch** ДО `profile_v5_text_input`:

```javascript
// Profile v5 EDIT location reply-back text intercept (mig 179 follow-up):
// when status ∈ {edit_country, edit_timezone, editing:country, editing:timezone}
// AND user tapped the reply-keyboard "🔙 Back" button inside Ask Location Permission flow
// (text starts with constants.icon_back), forward to 02.1_Location which has a
// cancel_location route that emits 👌 + restores the main reply_kb.
//
// TODO (PHASE 5 LOCATION MIGRATION): Remove this early branch.
// Python authoritative router will handle cmd_back natively.
const LOC_EDIT_STATUSES = new Set(['edit_country','edit_timezone','editing:country','editing:timezone']);
const iconBackForLoc = constants.icon_back || '🔙';
if (!callback && text && LOC_EDIT_STATUSES.has(status) && text.startsWith(iconBackForLoc)) {
    return { json: { ...user, route_target: 'location', route_reason: 'edit_loc_reply_back' }};
}
```

Дополнительно, чтобы 02.1_Location корректно ловил «🔙 Back» reply-text внутри `Init & Templates` JS:

```javascript
// existing block
if (messageText === backButtonText.trim()) {
  action = 'cancel_location';  // patch v4 (mig 179 follow-up)
}
```

И в `Action Classifier`:
```javascript
case 'cancel_location':
    route = 'cancel_location';  // patch v4
    break;
```

И новая 10-я route в Switch (Router) → Postgres: Build Main KB Body → Telegram: Restore Main KB ноды (patches v4/v7).

## Дополнительно — Prepare for 05 callback_message_id (patch v11)

Pre-existing gap: `Prepare for 05` (Set node в 01_Dispatcher) проксировал **9 полей** в 02.1_Location, **БЕЗ** `callback_message_id`. У Prepare for 02/04/04_v3 это поле было. Когда юзер кликает inline-кнопку в country picker → 02.1_Location рендерит `Telegram: Send UI` который пытается editMessageText (если message_id есть), иначе sendMessage.

Без callback_message_id editMessageText путь никогда не активировался → каждый клик создавал **новое сообщение** в чате (ломало One Menu UX).

Fix:
```
Prepare for 05.fields.values += {
  name: "callback_message_id",
  type: "stringValue",
  stringValue: "={{ $('Validate Secret').item.json.callback_query?.message?.message_id || '' }}"
}
```

## Архитектурный паттерн (reusable)

**Когда добавлять early branch в 01_Dispatcher Route Classifier**:
- Сценарий когда reply-keyboard текст должен идти НЕ в menu_v3 (text-input) а в специфический legacy workflow.
- Узкий predicate (несколько condition) — высокая специфичность, минимум impact.
- TODO marker для Phase X cleanup когда target migrates в Python.

**Когда добавлять поле в Prepare for *** :
- Если sub-workflow ожидает поле которое не доходит автоматически (например callback_message_id, callback_query_id).
- Mirror pattern from существующих Prepare for 02/04/04_v3 (они имеют 20-45 fields включая ALL Telegram + user state).

## Watchlist для будущих агентов

1. **node --check ВСЕХ Code-нод перед PUT** в любой workflow. Patch v5 нашёл 4 pre-existing broken JS (`message_id: ui.callback_message_id || \\'\\'` — лишний escape) которые сидели невидимо годами до момента когда patch v4 направил роутинг в эти ноды. Без node --check они бы упали в проде.

2. **При добавлении нового status code** в систему (workflow_states), проверить:
   - Route Classifier 01_Dispatcher — есть ли case или fall-through?
   - Prepare for * — нужно ли проксировать новое поле?
   - Init & Templates / Action Classifier в sub-workflow — handle case?

3. **build_main_reply_keyboard SQL** возвращает headless contract (`{rows: [[{text_key, icon_const_key}]]}`), НЕ Telegram-format. Резолвер ОБЯЗАН быть на транспорте:
   - Python: `services/template_engine.py:build_main_reply_keyboard_markup(contract, ctx)`.
   - n8n inline expression: `={{ JSON.stringify({ keyboard: [[{text: $('Init & Templates').first().json.constants.icon_X + ' ' + $('Init & Templates').first().json.translations.buttons.Y}]], ... }) }}`.
   - SQL function которая возвращает Telegram-format = антипаттерн (нарушает Dumb Renderer + добавляет 50-300ms latency).

## Removal plan (Phase 5)

После Phase 5 (location → Python `handlers/location.py`):
1. Удалить early branch из Route Classifier (искать `LOC_EDIT_STATUSES` или `edit_loc_reply_back`).
2. Удалить `callback_message_id` из Prepare for 05 (если 02.1_Location workflow совсем удаляется).
3. Удалить TD-#15 / TD-D из watchlist'а.

## Связанные миграции / patches

- **mig 179** (`migrations/179_phase4_onboarding_country_timezone.sql`) — Tech debt #13 closure (Phase 4 онбординг через dirty-hop в legacy 02.1_Location).
- **PR #20** — `dispatcher/router.py` 4e-pre branch (Python-side coverage для admin authoritative path).
- **PR #21** — `telegram_proxy.py` NO_INDICATOR_STATUSES (skip thinking-sticker for location-edit statuses).
- **n8n PUT v9** (08.05) — Route Classifier early branch.
- **n8n PUT v11** (08.05) — Prepare for 05 callback_message_id.
- **n8n PUT v10** (08.05) — Build All Countries UI Back-button cb_data status-aware.
- **n8n PUT v7** (08.05) — Telegram: Restore Main KB inline JS Telegram-format expression.
