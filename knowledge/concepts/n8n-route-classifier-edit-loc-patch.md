# 01_Dispatcher Route Classifier — edit-location reply-back early branch (patch v9, 08.05.2026)

> ⚠️ **status: legacy-n8n** — описывает n8n-механику. Соответствующая фича/target мигрирована в Python (Variant B cutover, 2026-04...05). Документ полезен для понимания n8n-эры; новые правки идут в Python handlers.

**Контекст:** временный fix между Phase 4 (онбординг в Python) и Phase 6.2 (location edit-flow migration в Python). **✅ REMOVED в PR #59 (2026-05-13) — секция Phase 6.2 ниже.**

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

## n8n PUT v13 (12.05.2026, 14:17 UTC) — band-aid resolve text_key

**Triggered by:** live UAT 786301802 в 13:57 UTC показал что `IF: Onboarding Just Completed` теперь корректно идёт по true-branch (v12 fix сработал), но `Telegram: Send onboarding_success` падает с Telegram API 400 `Bad Request: message text is empty`. SQLite `execution_entity[id=1290] status=error`.

**Root cause:** `render_screen` (Phase 4 headless contract) возвращает `telegram_ui` с `text_key='onboarding.finished'` + `template_vars={xp,mana,name,...}` БЕЗ `text` ключа. Python `template_engine.render_envelope` resolve'ит это автоматически. **n8n** просто читал `$json.ui.text` (undefined) → пустой text → 400.

**Конкретные ноды поправлены (Phase 4 headless mismatch):**
- `Telegram: Send onboarding_success` text expression
- `Telegram: Send onboarding_success_menu` text expression

Новый inline expression:
```javascript
={{ (function() {
  const ui = $json.ui || {};
  const tr = $('Init & Templates').first().json.translations || {};
  let raw = ui.text;
  if (!raw && ui.text_key) {
    let cur = tr;
    for (const k of ui.text_key.split('.')) { cur = cur && cur[k]; }
    raw = typeof cur === 'string' ? cur : (Array.isArray(cur) ? cur[Math.floor(Math.random()*cur.length)] : '');
  }
  if (!raw) return ui.carrier_text || '';
  const vars = ui.template_vars || {};
  return String(raw).replace(/\{(\w+)\}/g, (m, k) => vars[k] !== undefined ? vars[k] : m);
})() }}
```

**Что НЕ покрывает band-aid:** `sticker_category` поле. `mig 198/201` Channel A sticker emission работает только через Python `template_engine.render_envelope`. n8n `02.1_Location` НЕ имеет `sendSticker` ноды для `onboarding_success` — стикер не показывается, только текст. Полный fix sticker delivery — **Phase 6**.

**Важная коррекция предыдущего утверждения**: «onboarding_success никогда не показывался». Stickers_shown.onboarding_success set в БД (mig 201 атомарно в render_screen) — но это **не означает доставку юзеру**. У 32 юзеров (на 12.05) marker в БД, но execution_entity показывает что 100% этих executions падали с 400 «message text is empty». **Сообщение действительно никогда не доходило**, БД marker — false positive.

**Файлы patch v13:** workflow `7EqiiwUwlGs7dcHT` updatedAt `2026-05-12T14:17:32Z`, 55 nodes preserved.

---

## Дополнительный n8n PUT v12 (12.05.2026)

Live UAT 12.05 показал что **`IF: Onboarding Just Completed`** в 02.1_Location всегда шла по false-branch потому что `Postgres: Finalize Onboarding` (`typeVersion 2.4`) возвращает column-wrapped `{finalize_onboarding_location: {...}}`, а IF проверяла `$json.success` (undefined). Юзер видел «Сохранено» вместо onboarding_success-стикера + поздравительного сообщения.

**Patch v12** (10:10 UTC):
- `IF: Onboarding Just Completed` leftValue: `{{ $json.success }}` → `{{ $json.finalize_onboarding_location.success }}`.
- `02_Continue Onboarding` workflowId: `JRaKFPb5sOFL3xlc` (deleted, blocked PUT) → `0xJXA5M4wQUSiGXT` (04_Menu_v3 active, safe pointer — нода никогда не достигается через legacy dead `If`-ветки).

Полный анализ — [[concepts/start-fresh-gaps-2026-05-11]] секция «Gap 5».

Phase 6 cleanup: удалить весь dead-code path (`If`, `If Auto Continue`, `Prepare for 02 Continue`, `02_Continue Onboarding`) — после переноса 02.1_Location в Python.

## ✅ REMOVED — Phase 6.2 (PR #59, 2026-05-13)

**Patch v9 удалён** из `dispatcher/router.py` в PR #59 (Phase 6.2 location edit-flow → Python). Секция `4e-pre` (`LOC_EDIT_STATUSES` early branch) заменена пояснительным комментарием со ссылкой на Python handler `handlers/location.py`.

**Причина удаления:** Phase 6.2 перенёс обработку `edit_country`/`edit_timezone` loc_* callbacks в Python authoritative handler. Reply-text «🔙» в edit-context больше не маршрутизируется руками — после Phase 6.2 handler сам строит envelope без reply-kb, и back обрабатывается SQL FSM через стандартный `cmd_back` meta dispatch.

**NLM-сюрприз:** Phase 6.2 не потребовала SQL миграции. NLM-консультация выявила что `loc_country_<CC>` и `loc_tz_<TZ>` — динамические callbacks (генерируются Python handler'ом на лету), их физически нет в `ui_screen_buttons`. `process_user_input` их не обрабатывает. Вся логика — в Python через раздельные сеттеры `set_user_country` + `set_user_timezone` + `clear_editing_state`.

Полный architectural rationale — [[concepts/headless-fsm-vs-dynamic-handler-separation]].

## Связанные миграции / patches

- **mig 179** (`migrations/179_phase4_onboarding_country_timezone.sql`) — Tech debt #13 closure (Phase 4 онбординг через dirty-hop в legacy 02.1_Location).
- **PR #20** — `dispatcher/router.py` 4e-pre branch (Python-side coverage для admin authoritative path).
- **PR #21** — `telegram_proxy.py` NO_INDICATOR_STATUSES (skip thinking-sticker for location-edit statuses).
- **n8n PUT v9** (08.05) — Route Classifier early branch.
- **n8n PUT v11** (08.05) — Prepare for 05 callback_message_id.
- **n8n PUT v10** (08.05) — Build All Countries UI Back-button cb_data status-aware.
- **n8n PUT v7** (08.05) — Telegram: Restore Main KB inline JS Telegram-format expression.
