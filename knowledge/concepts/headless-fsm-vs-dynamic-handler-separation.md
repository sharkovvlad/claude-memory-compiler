---
title: "Разделение ответственности — Headless FSM (SQL) vs Dynamic Handler (Python)"
aliases: [headless-vs-handler, fsm-handler-separation, dynamic-vs-static-callbacks]
tags: [architecture, headless, python, sql, fsm, callbacks, principles]
sources:
  - "Phase 6.2 implementation (2026-05-13, PR #59)"
  - "Tech-lead 2026-05-13: «Оставь статические кнопки базе данных»"
  - "NLM-консультация 2026-05-12: process_user_input работает через lookup в ui_screen_buttons"
related:
  - headless-architecture
  - phase6-location-migration-plan
  - phase4-onboarding-migration
  - one-menu-ux
  - variant-b-cutover
created: 2026-05-13
---

# Headless FSM ↔ Python handler — разделение ответственности

> **Принцип:** в Headless-архитектуре NOMS есть **два слоя** обработки UI-входа: статические кнопки (с зафиксированным `meta` в `ui_screen_buttons`) обрабатывает SQL FSM (`process_user_input` / `process_onboarding_input`); динамические кнопки (генерируемые Python'ом на лету) обрабатывает Python handler. Эти слои **не должны смешиваться**: handler не должен дублировать FSM-логику для статических кнопок, FSM не способна обработать динамические.

## Контекст — почему правило появилось

В Phase 6.2 (location edit-flow → Python) первоначальный план агента включал перехват `cmd_back` в `handlers/location.py` с явным сбросом status='registered' и render('settings'). Тимлид остановил: «Оставь статические кнопки базе данных».

Кнопка `cmd_back` на экранах `edit_country`/`edit_timezone` уже зашита в DB:

```sql
SELECT screen_id, meta FROM ui_screen_buttons 
WHERE screen_id IN ('edit_country','edit_timezone') AND callback_data='cmd_back';
-- edit_country  | {'clear_status': True, 'target_screen': 'settings'}
-- edit_timezone | {'clear_status': True, 'target_screen': 'settings'}
```

При клике `cmd_back`:
1. Router (`dispatcher/router.py` section 4l `is_menu_callback`) маршрутизирует на `target=menu`.
2. `handlers/menu_v3.py` → `process_user_input` → SQL FSM читает `meta`, **атомарно** делает `UPDATE users SET status='registered' WHERE telegram_id=...` + `render_screen('settings')`.

Если же Python-handler начнёт перехватывать `cmd_back` — получаем **two sources of truth**:
- DB говорит «target_screen=settings, clear_status».
- Handler делает то же руками, но в случае рассинхрона (например, тимлид меняет `target_screen` в DB) — handler продолжит ходить в settings, игнорируя DB-конфигурацию.

Это нарушает Headless-принцип — конфигурация UI должна жить в DB, не в коде.

## Правила разделения

| Тип кнопки | Где обрабатывается | Пример |
|---|---|---|
| **Статическая** (есть в `ui_screen_buttons`, может иметь `meta`) | SQL FSM через `process_user_input` / `process_onboarding_input` | `cmd_back`, `cmd_edit_country`, `cmd_select_male`, `cmd_speed_1` |
| **Динамическая** (генерируется Python handler'ом на лету, нет в `ui_screen_buttons`) | Python handler ловит до SQL FSM | `loc_country_<CC>`, `loc_tz_<TZ>`, `loc_country_page_<N>`, `loc_tz_page_<N>` |

**Тест:** если кнопку можно найти `SELECT * FROM ui_screen_buttons WHERE callback_data=<value>` — это статическая, и SQL FSM знает что с ней делать. Если нельзя (например, потому что `<CC>` — переменная) — Python handler должен перехватить.

## Setters ≠ FSM

Второй принцип разделения — **отдельные RPC для data и для FSM**:

| RPC | Что делает | Что НЕ делает |
|---|---|---|
| `set_user_country(p_telegram_id, p_input_text)` | UPDATE `users.country_code` | Не меняет status |
| `set_user_timezone(p_telegram_id, p_input_text)` | UPDATE `users.timezone` | Не меняет status |
| `set_user_location(p_telegram_id, p_country_code, p_timezone, p_new_status)` | UPDATE country + tz + status вместе (Phase 4 mig 207 pattern) | Для онбординга — атомарный transition |
| `clear_editing_state(p_telegram_id)` | UPDATE status → registered | Не меняет data |
| `complete_onboarding(...)` | Status → registered + grant XP/coins/level | Финал онбординга |

**В Profile v5 edit-flow** (`status='edit_*'`) — использовать **раздельные** сеттеры + `clear_editing_state` в финале:

```python
# Edit-flow финал:
await rpc_caller("set_user_country", {"p_telegram_id": tid, "p_input_text": cc})
await rpc_caller("set_user_timezone", {"p_telegram_id": tid, "p_input_text": tz})
await rpc_caller("clear_editing_state", {"p_telegram_id": tid})
# Status теперь 'registered' — render('settings') через editMessageText.
```

**Запрет на смешивание в edit-flow:** `set_user_location(..., 'registered')` объединяет data + FSM transition в одну RPC. Это допустимо для онбординга (где transition — естественный шаг), но в edit-flow семантически портит контракт: setter не должен решать судьбу FSM.

## Прецеденты

| Сценарий | Тип | Решение |
|---|---|---|
| Юзер выбирает страну в онбординге (`loc_country_<CC>`) | Динамический callback | Python: `set_user_location(cc, NULL, 'onboarding:timezone')` — единая RPC ok (онбординг разрешён). |
| Юзер выбирает страну в Profile v5 edit (`loc_country_<CC>` под status='edit_country') | Динамический callback | Python: `set_user_country(cc)` — только data, БЕЗ FSM transition. Status переход — отдельно в финале. |
| Юзер кликает `cmd_back` в picker | Статическая кнопка | SQL FSM через `process_user_input` читает `meta.target_screen`. Никаких Python-перехватов. |
| Юзер выбирает gender в онбординге (`cmd_select_male`) | Статическая кнопка | SQL FSM. Кнопка в `ui_screen_buttons.meta = {save_rpc: 'set_user_gender', ...}`. |
| Юзер выбирает язык (`cmd_lang_uk`) | Статическая кнопка | SQL FSM. `meta = {save_rpc: 'set_user_language', ...}`. |
| Юзер вводит вес «85» (text input) | Free-text, не кнопка | Router маршрутизирует по `status in NUMERIC_INPUT_STATUSES` → onboarding handler → `process_onboarding_input` обрабатывает. |

## Когда НЕ применимо

- **Бизнес-логика без UI** (cron jobs, фоновые batches, scheduled tasks) — там нет FSM-конфликта, всё в SQL/Python независимо.
- **Не-callback входы** (photo, voice, location pin) — handler-driven по природе. Например, `geo-pin` (Phase 6.3) идёт сразу в Python `_handle_geo_pin`.
- **Workflow с большой бизнес-логикой по callback'у** (Cron alerts, payment flow) — может потребоваться Python пред-обработка перед SQL FSM. Это допустимо, но Python НЕ должен дублировать `target_screen` / `clear_status` логику.

## Чек-лист при правке handler'а

1. Кнопка статическая или динамическая? `SELECT * FROM ui_screen_buttons WHERE callback_data='<key>'` — если есть row, она статическая.
2. Если статическая — handler **только** возвращает `_forward_to_legacy_envelope` или fall-through. SQL FSM сама обработает.
3. Если динамическая — handler ловит и вызывает соответствующие сеттеры. Никаких `set_user_location(..., 'registered')` в edit-flow — использовать раздельные сеттеры + `clear_editing_state`.
4. Финальный экран — через `render_screen` RPC (а не self-built envelope), чтобы template_engine resolve все references из DB (`text_key`, `ui_translations`, `render_strategy`).

## Файлы (Phase 6.2 implementation)

- [handlers/location.py](handlers/location.py) — `_LOCATION_HANDLER_STATUSES` гард, branching в `_handle_country_selected`/`_finalize_with_timezone`.
- [dispatcher/router.py:549-556](dispatcher/router.py:549) — удалён section 4e-pre (patch v9): reply-text "🔙" больше не маршрутизируется руками.
- `clear_editing_state` RPC — атомарный `UPDATE users SET status='registered'` (psycopg2 verify 2026-05-13: `clear_editing_state(p_telegram_id bigint)`).

## Cross-references

- [headless-architecture](headless-architecture.md) — общая логика config-driven UI.
- [phase6-location-migration-plan](phase6-location-migration-plan.md) — раздел Phase 6.2 «Architecture decision: разделение DB / Python».
- [n8n-subworkflow-contract](n8n-subworkflow-contract.md) — контракт SQL FSM ↔ n8n / Python.
- [one-menu-ux](one-menu-ux.md) — render('settings') через editMessageText контракт.
