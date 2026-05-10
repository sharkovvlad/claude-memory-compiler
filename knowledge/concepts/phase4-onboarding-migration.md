# Phase 4: Миграция онбординга n8n → Python (29.04 — 04.05.2026)

**Статус:** ✅ В проде с 02.05.2026, флаг `handler_onboarding_use_python=true` на всех. Legacy `02_Onboarding_v3` и v1 деактивированы 04.05.

**Что закрыли:** последний крупный legacy блок n8n для регистрации новых пользователей. Все юзеры от первого `/start` до `status='registered'` идут через Python handler + SQL FSM.

---

## Архитектурная суть

Главное решение — **FSM (state machine) в SQL, Python handler — thin wrapper**.

```
Telegram /start или callback
    ↓
webhook_server.py
    ↓ (если флаг ON и status попадает в онбординг-диапазон)
handlers/onboarding_v3.py (~477 LOC, тонкий слой)
    ↓ ensure_user_exists → optional process_referral_join → dispatch_with_render
    ↓
SQL: dispatch_with_render → process_onboarding_input (новая RPC, FSM здесь)
    ↓
SQL: render_screen → text/buttons/payload
    ↓
ResponseEnvelope с OutboundItem[]
    ↓
services/telegram_send.py → Telegram API
```

**Альтернативой** была FSM в Python (рассматривалась как вариант v1) — отвергнута в пользу v2 ради соответствия RPC-first принципу проекта и консистентности с Phase 2 (`menu_v3`).

---

## Что создано

### SQL миграции
- **`161_phase4_onboarding_headless.sql`** (~688 LOC) — основная Phase 4 миграция:
  - RPC `process_onboarding_input(p_telegram_id, p_action_type, p_payload, p_cb_context, p_skip_debounce)` — FSM 10 состояний, ветвление step_5 (sedentary skip training), 2 message-payload completion.
  - RPC `ensure_user_exists(p_telegram_id, p_first_name, p_username, p_language_code)` — заменяет прямой INSERT из ноды n8n `Auto Create User`.
  - Inject в `dispatch_with_render` (CREATE OR REPLACE) — gate по статусу перед `process_user_input`.
  - 2 новых `ui_screens`: `onboarding_welcome`, `restore_choice` + 4 кнопки.
  - 39 переводов (3 ключа × 13 языков): `gamification.onboarding_xp`, `gamification.onboarding_coins`, `onboarding_success.personality_text`.
  - Placeholder в `bot_stickers` (`category='onboarding_welcome'`, `is_active=false`).
  - Запись `app_constants.handler_onboarding_use_python='false'` (потом UPDATE на true).
- **`165_isolate_indicator_message_id.sql`** — отдельная колонка `users.indicator_message_id` для Python-стикера (изоляция от One Menu UX `last_bot_message_id`).

### Python код
- **`handlers/onboarding_v3.py`** — handler (~477 LOC). Особые guard'ы:
  - `cmd_start_fresh` → `reset_to_onboarding(p_telegram_id)` RPC.
  - `cmd_restore_account` → `restore_user_account(p_telegram_id)` RPC.
  - Anonymized status guard (не давать восстанавливать `status='anonymized'`).
  - Двухшаговый referral pattern (после `ensure_user_exists` — отдельный вызов `process_referral_join`).
- **Правки `webhook_server.py`** (~+80 LOC) — Phase 4 branch в `_route_or_forward` и `_try_authoritative_path`, helper `_onboarding_flag_from_ctx()`.
- **Правки `dispatcher/router.py`** — секция `# 7) Onboarding entry` ловит `/start`, `cmd_select_*`, `cmd_speed_*`, `RESTORING_CALLBACKS`, status-based routing.

### Тесты
- **`tests/handlers/test_onboarding_v3.py`** — 34 кейса (2 добавлены в migration 170):
  - Полный FSM walk (gender → age → weight → height → activity → training → goal → registered)
  - Sedentary skip training
  - Validation errors через RPC error_key (не хардкод в Python)
  - Anonymized guard
  - Debounce
  - Two-step referral
  - cmd_start_fresh + cmd_restore_account
  - /start mid-onboarding → no error_key (migration 170)
  - /start ref_NNN mid-onboarding → referral processed, current screen rendered

---

## Что переиспользовано (а не создано заново)

### Существующие экраны из Profile v5 (НЕ копируем)
8 экранов имеют `visible_condition` для скрытия Back при онбординге — заложено в БД заранее:
- `edit_gender`, `ask_age`, `ask_weight`, `ask_height`, `edit_activity`, `edit_training`, `edit_goal`, `edit_speed`.

### Существующие RPCs
- `set_user_gender/age/weight/height/activity/training_type/goal/goal_speed` — все возвращают `{success, next_status}` или `{success:false, error_key}`. **Валидация — на стороне RPC**, не в Python.
- `complete_onboarding(p_telegram_id, p_goal_text)` — финальный шаг (XP/coins/mana grant + trial activation если referrer).
- `process_referral_join(p_referred_id, p_referrer_id)` — escrow rewards.
- `reset_to_onboarding(p_telegram_id)` — очистка биометрики, сброс к `registration_step_1`.
- `restore_user_account(p_telegram_id)` — восстановление soft-deleted (deleted_at=NULL).

---

## Ключевые gotchas (для будущих агентов)

### 1. `cmd_edit_*` — это Profile v5, НЕ онбординг

Кнопки `cmd_edit_gender`, `cmd_edit_age`, `cmd_edit_weight`, `cmd_edit_height`, `cmd_edit_activity`, `cmd_edit_goal`, `cmd_edit_speed` — это **callbacks из Profile v5 edit-flow для уже зарегистрированных юзеров** (нажал «изменить вес» в Profile → попал в `ask_weight`). Они работают через `04_Menu_v3` Phase 2 path.

**Не добавлять в `ONBOARDING_CALLBACKS` / `RESTORING_CALLBACKS`** — сломаешь Profile v5.

### 2. `cmd_select_*` уже маршрутизируются автоматически

В `dispatcher/router.py` секция «# 7) Onboarding entry» имеет проверку `"cmd_select_" in callback` — она ловит **все** select-callbacks (gender, activity, training, goal, lang, start). Не дублировать.

### 3. TARGET_TO_PATH в forward.py — только `menu_v3`

После hotfix'ов `68a223a`/`438ce1c` (около 1.05) словарь сужен специально:

```python
TARGET_TO_PATH: dict[str, str] = {
    "menu_v3": "menu_v3",   # ОНЛИ menu_v3
}
```

Причина: legacy n8n sub-workflows (включая `02_Onboarding_v3`) **не имеют webhook trigger** — их нельзя POST'ом дёрнуть. **Не возвращать `onboarding` в TARGET_TO_PATH** — Python handler вызывается напрямую из `_try_authoritative_path` через Phase 4 branch.

### 4. n8n self-hosted API 2.17.7 — ограниченный scope

`POST /workflows/{id}/deactivate` возвращает **403**. Workaround:
- Прямой `UPDATE active=0` в SQLite `/home/noms/n8n/data/database.sqlite`.
- n8n читает БД без кэша, изменения мгновенно отражаются в API.
- Альтернативно — рестарт n8n контейнера для гарантии.
- Endpoint `POST /workflows/{id}/activate` работает без 403.

### 5. Двойной thinking-стикер — был багом, починен

Симптом: каждое сообщение → 2 стикера, один удаляется, второй висит. Root cause: `webhook_server.py` имел два независимых вызова `maybe_send_indicator(update)` — на строке 527 (основной handler) и 307 (внутри `_try_authoritative_path`). Sticker 2 message_id перезаписывал sticker 1 в `users.indicator_message_id` → Clear удалял только последний.

**Фикс:** commit `b2cac2a` (удалены строки 307-308) + деактивирован legacy n8n `06_Indicator_Send` (`DlWx3ZYnT3xT0tv5`).

Если симптом вернётся — проверить количество вызовов `maybe_send_indicator` в `webhook_server.py`.

### 6. Welcome-стикер — placeholder

В `bot_stickers` запись `category='onboarding_welcome'` с `is_active=false`. Когда владелец пришлёт file_id фирменного стикера — `UPDATE bot_stickers SET file_id='...', is_active=true WHERE sticker_key='onboarding_welcome_1'` (одна команда, без deploy).

### 7. Legacy workflow деактивированы, не удалены

- `02_Onboarding_v3` (`wzjYmMOurCbp4czk`) — `active=false`.
- `02_Onboarding` v1 (`JRaKFPb5sOFL3xlc`) — `active=false` (был мёртвый код, никто не вызывал).

**Rollback:** `POST http://127.0.0.1:5678/api/v1/workflows/{id}/activate` через self-hosted API.

### 8. Исправления в CLAUDE.md (для контекста)

В правиле #12 раздела «n8n Data Flow Patterns» утверждалось что `02_Onboarding_v1` вызывается из `04_Menu`. **Это было неверно** уже на момент Phase 4 разведки — никто его не вызывал. Сейчас правило отражает реальность.

### 9. Секции router.py имеют ПОРЯДОК — soft-delete recovery + onboarding inline учили этому больно

Когда добавляешь новый callback в секцию `# 7) Onboarding entry` — **проверь не перехватывает ли его раньше секция `# 4a`, `# 4b` или `# 4l`**.

**Случай 1 (4.05):** `cmd_start_fresh` / `cmd_restore_account` ловились 4l (`"cmd_" in callback`). Фикс: `RESTORING_CALLBACKS` guard + commit `52c69ff`.

**Случай 2 (5.05, повтор gotcha #9):** После migration 172 (inline кнопки) `cmd_select_start` и `cmd_edit_lang` ловились:
- 4a (`PROFILE_V5_CALLBACKS`): `cmd_edit_lang` in set → `target=menu_v3`
- 4b (`PROFILE_V5_PICKER_PREFIXES`): `cmd_select_*` → `target=menu_v3`
- 4l (`"cmd_" in callback`): остальные `cmd_*` → `target=menu`
…ДО того как дошло до секции 7 (onboarding entry). menu_v3 не знает `onboarding_welcome` → code=error.

**Правильный паттерн:** при изменении callback_data кнопок на экранах онбординга (reply→inline, переименование) — **сразу добавить status-guard в 4a/4b/4l**:

```python
# ONBOARDING_STATUSES guard в трёх местах:
# 4a:
if callback in PROFILE_V5_CALLBACKS and status not in ONBOARDING_STATUSES: ...
# 4b:
if any(cb.startswith(p) for p in PREFIXES) and status not in ONBOARDING_STATUSES: ...
# 4l:
is_menu_callback = (
    "cmd_" in callback
    and not callback.startswith("cmd_select_")
    and callback not in RESTORING_CALLBACKS
    and status not in ONBOARDING_STATUSES  # ← добавить
)
```

`ONBOARDING_STATUSES` frozenset в router.py: `new`, `changing_language`, `registration_step_1..5`, `registration_step_training/goal/speed/phenotype_quiz`, `onboarding:country/timezone`.

Зафиксировано в commit `9cbe85e` (5.05), migration 173.

### 10. `/start` в середине онбординга = перерендер текущего экрана (migration 170, 04.05)

`process_onboarding_input` теперь intercept'ит `(status LIKE 'registration_step_%' AND text='/start')` в самом начале — пропускает блок валидации, рендерит текущий экран без `error_key`.

**Почему:** до migration 170 для шагов 2-4 (числовой ввод возраста/веса/роста) команда `/start` пролетала через числовой валидатор → `error_key='invalid_number'` → юзер видел экран шага с ошибкой «введите число».

**Намеренное отличие от legacy n8n:** старый `02_Onboarding_v3` workflow при `/start` от незарегистрированного юзера сбрасывал `status='new'` и показывал welcome (legacy паттерн). Phase 4 ADR (04.05) принял **обратное решение** — НЕ терять прогресс. Юзер на шаге 4 (рост) после `/start` всё ещё на шаге 4.

**CASE-таблица status → screen_id:**

| status | screen_id |
|---|---|
| `registration_step_1` | `edit_gender` |
| `registration_step_2` | `ask_age` |
| `registration_step_3` | `ask_weight` |
| `registration_step_4` | `ask_height` |
| `registration_step_5` | `edit_activity` |
| `registration_step_training` | `edit_training` |
| `registration_step_goal` | `edit_goal` |

**Edge case:** `/start ref_XYZ` в середине онбординга — referrer обрабатывается отдельно (Python handler парсит `parsed_referrer_id` ДО `dispatch_with_render`, опциональный `process_referral_join` вызов). После этого SQL FSM рендерит текущий экран. Прогресс не теряется.

**Watchlist для агентов:** при будущих изменениях `process_onboarding_input` — сохранить intercept в начале функции (после загрузки `v_user`, до валидации). Stale-base правило применяется (см. gotcha #6 в этом файле + CLAUDE.md правило из gotcha #3 о stale-base regression).

### 11. Reply-кнопки на onboarding_welcome отменены (migration 172, 05.05)

**Проблема:** `onboarding_welcome` использовал `keyboard_type='reply'` для кнопок "Поехали" и "Язык". Это вызывало:
- Carrier `·` пузырёк при `attach_reply_kb`
- text→callback маппинг bugs (reply-кнопки шлют text, не callback)
- 2-row layout (каждая кнопка на отдельной строке)

**Решение:** Migration 172 — UPDATE `ui_screen_buttons.onboarding_welcome`:
- `buttons.start`: row=0, col=0, keyboard_type=`inline`
- `buttons.language`: row=0, col=1, keyboard_type=`inline`

**ADR:** Для статусов `new`/`deleted` (не root-screens) — inline вместо reply. Reply-кнопки только для root-screens с `attach_reply_kb` (stats_main, profile_main, progress_main).

### 12. cmd_edit_lang + nav_stack для status='new' (РЕШЕНО в migration 173, 05.05)

~~`cmd_edit_lang` для `status='new'` возвращает `onboarding_welcome` с `reply_keyboard` (не language picker screen).~~ **РЕШЕНО.**

**Migration 173 решение:**
- Кнопка "Язык" на `onboarding_welcome` переключена на `cmd_edit_lang` (было `cmd_select_lang`)
- `process_onboarding_input` ветка status='new' + `cmd_edit_lang` → `push_nav('onboarding_welcome')` + `render('edit_lang')`
- cmd_back на `edit_lang` (status='new') → peek+pop nav_stack → `onboarding_welcome`
- Fallback `back_screen_id_default='settings'` у `edit_lang` остаётся для registered-юзеров (Profile v5)

**Важно: back_nav vs peek+pop:**
`back_nav(tid, current)` возвращает экран ПЕРЕД верхним в стеке (для иерархической навигации). Для паттерна "вернись куда пришёл" (стек = `['welcome']` → `cmd_back` → `welcome`) нужен прямой peek+pop через `nav_stack->>(len-1)` и `nav_stack - -1`. См. gotcha #15.

### 13. Ghost Message pattern для cmd_confirm_delete (05.05)

`_handle_confirm_delete` в `handlers/menu_v3.py` теперь вызывает `ghost_remove_reply_keyboard(chat_id)` из `services/telegram_send.py` ПЕРЕД финальным `send_new`. 

**Ghost Message:** `sendMessage(text="⏳", reply_markup={"remove_keyboard": True})` → `deleteMessage` в try/except (graceful failure).

**ВАЖНО:** Работает ТОЛЬКО для `remove_keyboard=True` команд. Удаление `attach_reply_kb` carrier УБИВАЕТ keyboard (smoke test 30.04 — Telegram привязывает reply_markup к message_id).

### 14. FSM ветка status='new' в process_onboarding_input — перехватывай ВСЕ callback'и явно (05.05)

Ветка `IF v_status = 'new' THEN RETURN render_screen('onboarding_welcome')` перехватывала **любое** действие и возвращала welcome screen. После migration 172 (inline кнопки) это стало видимым — `cmd_select_start` попадал в бесконечный цикл через menu_v3 (router 4b).

**Правило:** в каждой FSM-ветке явно обрабатывать все ожидаемые callback'и. Не использовать catch-all return без фильтра.

**После migration 173 ветка status='new':**
1. `cmd_select_start` → UPDATE status='registration_step_1' + render 'edit_gender'
2. `cmd_edit_lang` / `cmd_select_lang` → push_nav('onboarding_welcome') + render 'edit_lang'
3. `cmd_back` → peek+pop nav_stack → render поpped screen (fallback: 'onboarding_welcome')
4. всё остальное → render 'onboarding_welcome'

### 19. Третий случай stale-base regression — mig 175 откатил mig 173 (lesson 6.05)

`process_onboarding_input` (OID 161473) в проде на 5.05 содержал ветку
`status='new' + cmd_edit_lang → SET status='changing_language'`, чего НЕТ
ни в файле mig 173, ни в файле mig 175. Скорее всего mig 175
(`CREATE OR REPLACE` через `pg_get_functiondef` снапшот ДО mig 173)
сохранила какую-то ещё более раннюю версию — откатив mig 173 ветки.

**Почему пропустили:** verify mig 173 показал PASS на момент применения
(daily 5.05 говорит `Test 2 cmd_edit_lang: nav_stack=['onboarding_welcome'] PASS`),
но потом mig 175 затёрла. Это **третий случай** stale-base в проекте:
- mig 042 — cron_check_streak_breaks (4.05)
- mig 167 — streak_freezes ambiguity (3.05)
- mig 175→178 — process_onboarding_input changing_language (6.05)

**Watchlist:** при любом `CREATE OR REPLACE` на функцию которая уже редактировалась
сегодня — обязательно `SELECT pg_get_functiondef(...)` ЖИВОГО прода как база,
а не файл из репо. **Никогда** не копировать тело из git-файла.

**Fix:** mig 178 переписал `process_onboarding_input`. См. daily/2026-05-06.

### 20. Language Lag — stale ctx в template_engine (lesson 6.05 QA)

После `set_user_language` БД содержит свежий `users.language_code`, но
`UserCtx`, загруженный webhook'ом ДО dispatch_with_render, хранит старый
язык. `services/template_engine.py:render_envelope` берёт translations из
`ctx.translations` → юзер видит экран на СТАРОМ языке. Следующий клик
работает на свежем языке (потому что webhook грузит ctx заново).

**Внешне:** «бот тормозит на один шаг» при смене языка.

**Watchlist для агентов:** `render_screen` (SQL) **никогда** не резолвит
текст — это всегда делает Python. Всякий раз, когда RPC меняет
`users.language_code` (ИЛИ другие поля, влияющие на `v_user_context`),
Python handler ОБЯЗАН перечитать ctx ИЛИ template_engine должен
читать lang/translations из `telegram_ui` (а не из ctx).

**Fix (handlers/onboarding_v3.py):** в `_envelope_from_rpc_result` —
сравнение `telegram_ui.language_code` против `ctx.language_code`,
условный refresh через `get_user_context`. Обходится в +44 ms RTT
ТОЛЬКО при реальной смене языка.

### 21. Silent Validation — validation_error флаг игнорируется на render path (lesson 6.05 QA)

SQL setter вернул `render_screen('ask_height') ||
jsonb_build_object('validation_error', true, 'error_key', 'invalid_height')`.

В Python `_envelope_from_rpc_result`:
```python
raw_status = result.get("status")  # None — render_screen не возвращает status
if raw_status is None and isinstance(result.get("telegram_ui"), dict):
    status = "render"  # ← попадаем сюда
if status in ("validation_error", "error"): ...  # пропускаем — статус 'render'
# рендерим экран — БЕЗ показа error_key
```

Юзер ВИДИТ перерисованный вопрос, но НЕ видит сообщение об ошибке.

**Watchlist:** при возврате `render_screen() || {validation_error: true, ...}`
из любой SQL функции (Phase 4 онбординг + любые будущие FSM обёртки)
Python handler ДОЛЖЕН проверять `result.get('validation_error')` после
рендера и аппендить error item.

**Defensive lookup error_key:** SQL setters возвращают error_key БЕЗ
префикса (`invalid_height`), но в `ui_translations` он лежит nested под
`{errors: {invalid_height: ...}}`. Lookup должен пробовать оба:
1. `error_key` как есть (для dotted типа `errors.validation_generic`)
2. `errors.<error_key>` (для bare типа `invalid_height`)
3. `errors.validation_generic` (generic fallback)

**Fix:** см. mig 178 + handlers/onboarding_v3.py изменения 6.05.

### 22. NUMERIC_RE и AI fallback — 4+ digit ввод утекал в legacy AI (lesson 6.05 QA)

`dispatcher/router.py:NUMERIC_RE = re.compile(r"^\d{1,3}([.,]\d{1,2})?$")`
позволял только **1-3 цифры**. Юзер ввёл `10000` на шаге веса → router
section 10 (`text_food_from_numeric_step`) → AI engine → хардкоженный
RU-fallback `'Хм, не получилось распознать. Попробуй ещё раз или напиши текстом.'`
в `n8n_workflows/03_AI_Engine.json` JS Code node (Build Failed Reply).

**Fix:** `NUMERIC_RE = re.compile(r"^\d{1,5}([.,]\d{1,2})?$")`. После этого
числа до 99999 уходят в onboarding handler → set_user_weight → штатный
`error_key='invalid_weight'` через Task 5 фикс.

**Граница:** 6-значные числа (100000+) всё ещё уходят в AI как
text_food_from_numeric_step — это правильно (рекордов веса/возраста/роста
в 6+ цифр не существует, явная food-фраза).

### 15. back_nav семантика: возвращает экран ПЕРЕД верхним (не сам верхний)

`back_nav(tid, current_screen)` для иерархической навигации Profile v5: pop → parent = следующий в стеке (или anchor). Для стека `['onboarding_welcome']`: pop → `popped='onboarding_welcome'`, stack=`[]`, parent = `back_screen_id_default` от onboarding_welcome = NULL → fallback `stats_main`.

**Паттерн "вернись куда пришёл"** (stack = место откуда пришли):
```sql
-- peek top
v_top := v_stack->>(jsonb_array_length(v_stack) - 1);
-- pop
UPDATE users SET nav_stack = nav_stack - -1 WHERE ...;
-- render top
RETURN render_screen(tid, v_top);
```

**Когда какой паттерн:**
- Profile v5 глубокая иерархия (edit_age, edit_goal, etc.) → `back_nav` (parent в дереве)
- Shared Screen из нестандартного контекста (edit_lang из онбординга) → peek+pop (вернуть origin)

### 23. set_user_training_type не продвигал status в онбординге (mig 190, lesson 9.05)

**Симптом (live UAT 786301802 9.05 12:53):** юзер выбрал activity=light → status='registration_step_training' (set_user_activity OK). Юзер выбрал training=cardio → `set_user_training_type` сохранил `training_type='cardio'`, но status **остался** `'registration_step_training'`. FSM render('edit_goal'), но в БД status=training. Юзер выбрал goal=lose → FSM попадает опять в ветку `IF v_status='registration_step_training'` → `set_user_training_type(tid, 'cmd_select_lose')` → 'lose' не валидный training_type → render('edit_training'). **Циклится.**

**Root cause:** в `set_user_training_type` `next_status` определялся как:
```sql
v_next_status := CASE WHEN v_current_status = 'edit_training' THEN 'registered' ELSE v_current_status END;
```

То есть только Profile retake продвигался. Онбординг — нет. Все остальные `set_user_*` (gender/age/weight/height/activity) имеют ELSE-ветку на `registration_step_X+1`.

**Fix (mig 190):**
```sql
v_next_status := CASE
    WHEN v_current_status = 'edit_training' THEN 'registered'
    WHEN v_current_status = 'registration_step_training' THEN 'registration_step_goal'
    ELSE v_current_status
END;
```

**Watchlist для будущих RPC:** при добавлении нового `set_user_<новое_поле>` обязательно паттерн как в `set_user_activity` (handle оба контекста — edit_X и registration_step_X). Аудит остальных существующих RPC на полноту pattern — отдельный TODO.

### 24. ⛔ Half-measures (manual UPDATE юзеров) — anti-pattern (lesson 9.05)

**Контекст:** юзер 786301802 после Phase 4 quiz (mig 187/188/189) застрял на `status='onboarding:country'` — legacy n8n `02.1_Location` workflow не активировался после Python forward'a (HTTP 200 OK, но юзер молчит). Я применил manual hotfix:
```sql
UPDATE users SET status='registered', xp = xp + 50, nomscoins = nomscoins + 100,
    mana_current = LEAST(mana_current + 500, 500), country_code='ES', timezone='Europe/Madrid'
WHERE telegram_id=786301802;
```

**Тимлид явно отверг такой подход:**
> «Я против таких половинчатых мер: 'обойти location, complete_onboarding вручную'. Нам надо решать проблемы, а не затыкать течи. Важно расследовать n8n 02.1_Location workflow и предложить лучшее решение, например, переход на Питон.»

**Правило для будущих агентов:**

| Сценарий | Можно manual hotfix? |
|---|---|
| Bot stuck из-за неизвестного бага, root cause не найден | ❌ **НЕТ.** Сначала копать root cause (n8n routing / SQL FSM / Python handler), чинить там. |
| Root cause fix задеплоен, нужно вытащить **уже пострадавших** юзеров | ✅ Да — это catch-up, а не workaround. |
| Root cause требует много времени, юзер ждёт | ❌ Нет. Лучше сообщить юзеру явно «есть баг, чиним», чем дать ложное «работает». |

Manual hotfixes маскируют проблему, ставят precedent для других агентов делать так же, и оставляют **untracked invariant violations** в БД. Каждый half-measure — кредит, который потом возвращать с процентами при следующем баге.

**Текущий открытый вопрос:** legacy 02.1_Location → Python migration (Variant B Phase 6) — следующий таргет `TARGET_TO_PATH` после onboarding handler. Spawn task создан 9.05 (см. daily/2026-05-09.md «Phase 4 onboarding hotfixes session»).

### 25. Phenotype quiz UX flow — finalized (mig 187b/188/189, 8-9.05)

Финальная архитектура after migrations 187b/188/189:

**Онбординг flow:**
```
goal=lose/gain → speed → edit_phenotype (Q1, Skip available) →
  Skip → forward to location (phenotype='default')
  Q1 ans → phenotype_q2 → Q3 → Q4 → classify_phenotype + forward to location (NO result screen, mig 189)
```

**Profile retake flow** (через `cmd_edit_phenotype` на `my_plan`):
```
my_plan → cmd_edit_phenotype (meta: set_status='edit_phenotype', target_screen='edit_phenotype')
        → process_user_input → render edit_phenotype (Back available, Skip hidden)
        → Q1 → Q2 → Q3 → Q4 → classify_phenotype + render('phenotype_result')
        → Continue → my_plan, status='registered'
```

**Shared screens** (5 экранов на оба контекста): `edit_phenotype, phenotype_q2/q3/q4, phenotype_result`. Кнопки conditional через `visible_condition`:
- Skip: `u.status = 'registration_step_phenotype_quiz'` (col=0 на row=3)
- Back: `u.status = 'edit_phenotype'` (col=1 на row=3, mig 188 — UNIQUE constraint screen+row+col требует разный col)

**dispatch_with_render gate** (mig 187/189): онбординг path для статусов `new`, `registration_step_*`, `restoring:choose`, `edit_phenotype`, `onboarding:country`, `onboarding:timezone`. Гарантирует FSM в `process_onboarding_input` для shared phenotype quiz ветки.

**Result screen text** (Profile retake only): `text_key='phenotype.result_template'` = literal `'{result_html}'` (одинарные скобки! Иначе `_VAR_PLACEHOLDER_RE` оставляет внешние `{` `}` literally в тексте — mig 189 fix). business_data.result_html — pre-rendered HTML composite (title + explanation_<phenotype> + recalculated, locale-aware).

**Translation `buttons.edit_phenotype` deprecated** (mig 188): кнопка `cmd_edit_phenotype` на `my_plan` теперь использует canonical `text_key='profile.body_type'` (переведён на все 13 языков, в отличие от `buttons.edit_phenotype` который был только на ru). Старый ключ остаётся orphan для backward compat.

**onboarding_success message** — после full Phase 4 flow (location + timezone) `finalize_onboarding_location` (mig 179) вызывает `complete_onboarding` → status='registered' + grants + render('onboarding_success'). Currently заблокирован на legacy 02.1_Location path (см. gotcha #24). После переноса location в Python — onboarding_success message появится корректно.

---

### 26. menu_v3 vs onboarding_v3 status normalization asymmetry (lesson 10.05, после 04_Menu strip)

**Симптом:** юзер `417002669` в `status='edit_phenotype'` кликает reply «👤 Профиль» → бот шлёт «⚠️ Что-то пошло не так. Попробуй ещё раз.». Второй клик отрабатывает нормально (status уже `'registered'` после первого как side-effect).

**Цепочка:**
1. Юзер в `edit_phenotype` (зашёл в Profile retake quiz через my_plan).
2. Reply tap «👤 Профиль» → telegram_proxy синтезирует `cmd_get_profile` → диспетчер `reason=profile_v5_reply_text` → target=`menu_v3`.
3. `menu_v3` зовёт `dispatch_with_render` → SQL onboarding-gate (mig 188 расширил gate на `edit_phenotype`) → `process_onboarding_input` catch-all (L341-344): `UPDATE status='registered'` + `RETURN public.render_screen('profile_main')`.
4. `render_screen` возвращает структуру **без `status` field** (контракт), `process_onboarding_input` пробрасывает as-is.
5. `menu_v3._envelope_from_rpc_result` (`handlers/menu_v3.py:290`): `status = result.get("status") or "error"` → status=`"error"` → error envelope с локализованным «errors.generic».

**Корневая проблема — asymmetry handlers:**

- `handlers/onboarding_v3.py:518-526` **уже умеет** нормализовать: `if raw_status is None and isinstance(result.get("telegram_ui"), dict): status = "render"`. Комментарий явно фиксирует контракт: «render_screen returns a dict WITHOUT an explicit status field. process_onboarding_input calls render_screen directly and propagates its result».
- `handlers/menu_v3.py:290` — той же нормализации НЕ имеет. До 10.05 пути `menu_v3 → process_onboarding_input` не было в проде: legacy n8n 04_Menu обрабатывал phenotype-callbacks для `edit_phenotype` юзеров, Python onboarding-gate не активировался.
- **04_Menu phenotype strip (10.05, PR #39)** удалил legacy путь → menu_v3 для `edit_phenotype` юзеров теперь стабильно попадает в `process_onboarding_input` → bug стал воспроизводимым.

**Pre-existing scope:** контракт «process_onboarding_input возвращает render без status field» — задокументирован ещё в mig 187 (комментарий в onboarding_v3.py). Asymmetry была pre-existing с 02.05, замаскирована legacy 04_Menu. Не уникален для `cmd_get_profile` — потенциально срабатывает для любого callback от юзера в `edit_phenotype` / `onboarding:country` / `onboarding:timezone` который роутится через menu_v3.

**Fix (PR #39, 10.05):** backport нормализации из `onboarding_v3.py:518-526` в `menu_v3.py:_envelope_from_rpc_result`:

```python
# render_screen returns a dict WITHOUT an explicit "status" field. When the
# user's status hits the dispatch_with_render onboarding gate (mig 188: edit_phenotype,
# mig 189: onboarding:country/timezone), process_onboarding_input propagates
# render_screen result directly — status is None even though telegram_ui is present.
# Treat that as "render" so we don't false-positive into the generic error envelope.
raw_status = result.get("status")
if raw_status is None and isinstance(result.get("telegram_ui"), dict):
    status = "render"
else:
    status = raw_status or "error"
```

**Альтернатива (отвергнута):** SQL fix — обернуть все 43 `RETURN public.render_screen(...)` в `process_onboarding_input` через `|| jsonb_build_object('status', 'render')`. 4 из 43 — validation_error paths (телeграм UI + `validation_error: true` + `error_key`), требуют status=`'validation_error'`. Большой surface, риск семантического сдвига. Python fix — 4 строки, mirror'ит существующий контракт onboarding_v3, не трогает SQL.

**Recipe для будущих handlers:** если новый handler зовёт `dispatch_with_render` для статусов в onboarding-gate (mig 188 список) — обязательно ту же нормализацию `status is None + telegram_ui present → 'render'`. Контракт `render_screen` (no top-level status) — стабилен, не меняем (или меняем сразу для всех 4+ consumers, что дорого).

### 27. Headless meta dispatch требует callback в `PROFILE_V5_CALLBACKS` (lesson 10.05)

**Симптом** (после deploy menu_v3 status normalization fix): юзер кликает «🧬 Тип тела» на my_plan → бот не реагирует (раньше показывал ошибку, теперь тишина).

**Диагноз через логи** (`journalctl -u noms-webhooks`):
```
SHADOW_ROUTE update_id=... target=menu reason=menu_command synth=-
AUTHORITATIVE skip — fall through to legacy
```

Callback `cmd_edit_phenotype` → `target=menu` (legacy 01_Dispatcher → 04_Menu), а **не** `target=menu_v3`. После 10.05 strip legacy 04_Menu больше не имеет phenotype branch (Command Classifier / Menu Router / Edit Type Router зачищены) → callback уходит в void.

**Корневая причина — half-measure в mig 187b:**

Mig 187b (08.05) настроил **headless meta dispatch** для кнопки cmd_edit_phenotype на my_plan:
```sql
UPDATE ui_screen_buttons
   SET meta = jsonb_build_object('set_status', 'edit_phenotype', 'target_screen', 'edit_phenotype')
 WHERE screen_id = 'my_plan' AND callback_data = 'cmd_edit_phenotype';
```

`process_user_input` уже умеет читать `meta.set_status` + `meta.target_screen` (L332-340 в живой версии): применяет UPDATE users + рендерит target_screen. **НО:** для этого callback должен попасть в `process_user_input`, что требует роутинга через `target=menu_v3` в Python диспатчере.

Mig 187b забыл добавить `cmd_edit_phenotype` в `dispatcher/router.py:PROFILE_V5_CALLBACKS` set. До 10.05 это было замаскировано legacy 04_Menu: cмd_edit_phenotype попадал в `target=menu` → 01_Dispatcher → 04_Menu (`Edit Type Router` branch `edit_phenotype` → `Edit Phenotype Screen` → переход в quiz) → работало. После strip'а — путь в legacy остался, но edit_phenotype branch там удалён → silent failure.

**Fix (PR #39, 1 commit):** добавить `"cmd_edit_phenotype"` в `PROFILE_V5_CALLBACKS` в `dispatcher/router.py`. После: диспетчер роутит → menu_v3 → dispatch_with_render → process_user_input (status='registered' до клика, gate не срабатывает) → meta dispatch:
- `set_status='edit_phenotype'` (UPDATE users)
- `target_screen='edit_phenotype'` (render Q1)
- Push 'edit_phenotype' в nav_stack автоматически.

Последующие cmd_quiz_q* клики (status='edit_phenotype' уже) роутятся через **section 9 BUTTON_ONLY_STATUSES** → target='onboarding' → onboarding_v3 handler (уже работает корректно с нормализацией статуса).

**Verify-after** (live savepoint, юзер 417002669, имитация my_plan стека):
```sql
UPDATE users SET status='registered', nav_stack='["profile_main","my_plan"]' WHERE telegram_id=417002669;
SELECT public.dispatch_with_render(417002669, 'callback',
    '{"callback_data":"cmd_edit_phenotype"}'::jsonb, '{}'::jsonb, true);
-- expect: status='render', screen_id='edit_phenotype',
--         text_key='phenotype.q1_prompt', keyboard=[cmd_quiz_q1_a/b/c, cmd_back],
--         user.status → 'edit_phenotype', nav_stack += 'edit_phenotype'
```

**Recipe для headless meta dispatch buttons:**

Когда добавляешь `ui_screen_buttons.meta = {set_status, target_screen}` для нового callback'а — **обязательно** добавь callback в `dispatcher/router.py:PROFILE_V5_CALLBACKS`. SQL meta только описывает что делать в `process_user_input`, но не управляет роутингом Python ↔ legacy n8n. Без route'а callback падает в legacy `target=menu`, что после полного n8n cutover превратится в silent void.

Это две разные ответственности (SQL FSM + Python dispatcher), миграция должна обновлять обе одновременно. Test для регрессии: pytest `test_route_decisions_for_callback_table` (если есть) или live savepoint repro как выше.

### 28. `_build_button_text` не резолвил `{icon_*}` placeholder'ы (lesson 10.05)

**Симптом** (после PR #40 deploy): Phenotype Q1 рендерится, шапка `👕 В1/4 — Где облегающая футболка...` корректна, но **inline-кнопки** показывают literal placeholder'ы: `{icon_pheno_q1_a} Плечи и грудь`, `{icon_scales} Равномерно везде`, `{icon_pheno_q1_c} Живот и талия`.

**Причина — asymmetry в `services/template_engine.py`:**

- `_resolve_text` (для шапки сообщения) делает **два прохода**: Pass 1 `{tr:section.key}` → translations lookup, Pass 2 `{var}` → template_vars (P1) + constants (P2). `{icon_pheno_q1}` → Pass 2 находит в `constants` → подставляет `👕`. ✓
- `_build_button_text` (для inline-кнопок) делал просто `_get_nested(translations, text_key)` — **raw text без substitution**. `{icon_pheno_q1_a}` оставался literal. ✗

Asymmetry pre-existing с момента создания template_engine'а. Замаскирована тем, что:
1. До mig 187b/193/195 (08-10.05) в `ui_translations.content` placeholder'ов почти не было — иконки кнопок собирались через `icon_const_key` префикс (отдельное поле в `ui_screen_buttons`).
2. Phenotype quiz (mig 187b) внёс новый паттерн: `icon_const_key=NULL` + `{icon_pheno_*}` placeholder в text для централизации эмодзи через `app_constants`. Это контракт «headless emoji» — text содержит свой icon, NULL в `icon_const_key` чтобы избежать «правила двойных эмодзи».
3. Тестировалось в legacy 04_Menu (JS code ноды) до 10.05 — они тоже не резолвили `{icon_*}`. Откатил mig 193 → 194. После strip'а 04_Menu (PR #39) + replay mig 195 phenotype путь полностью на Python → `_build_button_text` начал получать text с `{icon_*}` placeholder'ом → literal выплыл наружу.

**Fix (PR #40 follow-up commit, 4 строки):** заменить `_build_button_text` raw text lookup на `_resolve_text(text_key, translations, {}, constants)`. template_vars не пробрасываем (кнопочный text не использует `{var}` сейчас; при необходимости расширим signature). `icon_const_key` префиксование оставлено как есть — для legacy кнопок без placeholder'ов.

**Safety guard:** если кнопка имеет одновременно `icon_const_key` И `{icon_*}` placeholder в text → двойной эмодзи (правило CLAUDE.md). Mig 187b установил контракт: для phenotype-кнопок `icon_const_key=NULL`. Live check:
```sql
SELECT screen_id, callback_data, text_key, icon_const_key FROM ui_screen_buttons
 WHERE callback_data LIKE 'cmd_quiz_q%';
-- expect: icon_const_key=NULL для всех 12 quiz answer buttons
```

**Verify-after (live)** (`scripts/_verify_button_rendering.py`): `dispatch_with_render(cmd_edit_phenotype)` → `_build_inline_keyboard(keyboard, translations, constants)` → ожидаемый output:
```
text='👕 Плечи и грудь'        cb='cmd_quiz_q1_a'
text='⚖️ Равномерно везде'     cb='cmd_quiz_q1_b'
text='🍔 Живот и талия'        cb='cmd_quiz_q1_c'
text='🔙 Назад'                cb='cmd_back'  (icon_const_key='icon_back' path сохранён)
```

**Pytest:** `tests/services/test_template_engine.py` (42 теста) и full suite (399 passed) — без регрессий. Существующие тесты для кнопок без placeholder'ов проходят как раньше; placeholder paths теперь резолвятся корректно.

**Recipe для будущих headless кнопок:** контракт явно зафиксирован в `_build_button_text` docstring — text может содержать `{icon_*}` / `{tr:*}` placeholder'ы, Python резолвит через `_resolve_text`. Не хардкодить эмодзи через `icon_const_key` если текст уже содержит placeholder (двойной эмодзи). При добавлении новых headless экранов проверять `_verify_button_rendering.py` шаблон для регрессионного теста.

**Verify-after** (live savepoint на проде, юзер `417002669`):
```sql
BEGIN; SAVEPOINT s;
UPDATE users SET status='edit_phenotype' WHERE telegram_id=417002669;
SELECT (public.dispatch_with_render(417002669, 'callback',
        '{"callback_data":"cmd_get_profile"}'::jsonb, '{}'::jsonb, true))
       ? 'status' AS has_status_field;
-- false (SQL контракт);
-- но menu_v3 после fix нормализует → status='render' → ResponseEnvelope с render
ROLLBACK TO SAVEPOINT s; ROLLBACK;
```

## TODO для будущих сессий (бэклог)

### TODO #1 — Интегрировать `process_onboarding_input` через `process_user_input` для auto-push nav_stack

**Контекст (зафиксировано пользователем 05.05 после live QA):** мы в следующей фазе разработки перепишем SQL-функцию `process_onboarding_input` чтобы она научилась **сама раскидывать хлебные крошки** (push_nav в nav_stack) — точно так же, как делает Главное меню через `process_user_input` (mig 147 `back_i_came_from_navigation`). Сделает систему «защищённой от дурака» (bulletproof).

**Текущее состояние (5.05, после mig 173):** `dispatch_with_render` вызывает либо `process_onboarding_input` (онбординг-статусы), либо `process_user_input` (остальное) — **две независимые ветки**. Auto-push в nav_stack есть только в `process_user_input`. В `process_onboarding_input` любой Shared Screen (edit_lang сейчас, любой будущий потом) требует **точечной явной вставки `push_nav('parent_screen_id')`** в SQL-теле функции.

**Точечный workaround в mig 173:** для transition `onboarding_welcome → edit_lang` явный `push_nav('onboarding_welcome')` встроен в SQL FSM. Это работает, но:
- Каждый новый Shared Screen в онбординге требует ручной правки `process_onboarding_input`.
- Risk «забыли push» = регрессии типа «Back ушёл не туда».

**Целевое состояние:** одна точка входа FSM. Варианты реализации:
- (A) `process_onboarding_input` становится **внутренней helper-функцией** которую вызывает `process_user_input` через CASE по статусу. Auto-push гарантирован.
- (B) Общий wrapper-RPC `process_fsm_input` диспатчит на onboarding или main FSM, push_nav и debounce делаются **до** диспатча.
- (C) push_nav выносится в отдельную RPC, которую обе функции вызывают первой строкой.

**Польза:** «защита от дурака» — следующие фичи (Phenotype Quiz, Location pickers, любой Shared Screen в новых onboarding-ветках) **автоматически** получают правильные хлебные крошки без явной вставки.

**Сложность:** средняя. Нужно сохранить backward compatibility с существующим caller (`dispatch_with_render`) и не сломать Profile v5 nav_stack который уже работает.

**Зависимые точки очистки после рефактора:** mig 173 содержит явный `push_nav('onboarding_welcome')` — после рефактора эту вставку убрать (auto-push покроет). Аналогично всем будущим точечным `push_nav` в `process_onboarding_input`.

### ~~TODO #2 — Старая reply-keyboard остаётся у юзера status='new' (UX)~~ — DONE (коммит 4985279, 5.05) → УТОЧНЁН (коммит b4d8954, 5.05 вечер)

**Симптом (наблюдение пользователя 5.05 17:14, скриншот зафиксирован):** при `/start` для юзера в `status='new'` снизу остаются **старые reply-кнопки** («▶️ Поехали» / «🌐 Язык» от ДО mig 172 либо main reply-keyboard от прошлых сессий). Inline-кнопки welcome работают корректно, но reply-keyboard остаётся chat-state-ом и юзер видит **дубликат** — inline под сообщением + reply-keyboard внизу.

**Root cause:** Telegram reply_keyboard — **chat state**, остаётся до явного `remove_keyboard=True` или новой reply_keyboard. После mig 172 welcome имеет только inline (`reply_markup={inline_keyboard:[[...]]}`), reply-keyboard не сбрасывается.

**Первый фикс (5.05, коммит 4985279):** ghost trigger в `render_envelope()`. Удалён по решению тимлида (5.05 вечер, коммит b4d8954) — не был согласован с владельцем, создавал UX-задержку на каждом /start.

**Текущее состояние (коммит b4d8954):** ghost trigger удалён из `template_engine.py`. `ghost_remove_reply_keyboard` helper в `telegram_send.py` **ОСТАЁТСЯ** — используется в `cmd_confirm_delete` flow. Reply-keyboard у новых юзеров может остаться видна до первого шага онбординга — принято как acceptable UX.

### ~~TODO #3 — Back с edit_lang создаёт новое welcome-сообщение (вместо edit existing)~~ — DONE (коммит 4985279, 5.05)

**Симптом (наблюдение 5.05 17:13-17:14):** юзер на welcome → нажал «🌐 Язык» (`cmd_edit_lang`) → попал на edit_lang screen → выбрал язык → **Back** → появилось **новое welcome-сообщение** в чате (welcome message #2), а ожидалось `editMessageText` на existing welcome message #1.

**Root cause:** SQL `render_screen()` ставит `callback_message_id=NULL` в telegram_ui — это намеренно, SQL stateless по отношению к Telegram API message_id. Python транспортный слой не inject'ил `callback_message_id` из `decision` → `template_engine` не мог построить `edit_existing` → деградировал в `send_new` или `delete_and_send_new`.

**Фикс (5.05, коммит 4985279):** `_envelope_from_rpc_result()` и `_rerender_current_screen()` в `handlers/onboarding_v3.py` inject'ят `decision.callback_message_id` в telegram_ui (shallow copy) ПЕРЕД вызовом `render_envelope()`. Все онбординг-экраны кроме welcome имеют `render_strategy='replace_existing'` → при inject'е `edit_existing` строится автоматически. Передаётся также `screen_id=result.get('screen_id')` для Ghost trigger.

**Архитектурная заметка:** `render_screen()` returns `callback_message_id=NULL` ВСЕГДА (намеренно). Python handler inject'ит его из `decision.callback_message_id` после RPC. Без inject'а все `replace_existing` экраны деградируют в `delete_and_send_new`. Это **Gotcha #16** — задокументировано в daily log 5.05.

**Связано с TODO #1** — после рефактора `process_onboarding_input` через `process_user_input` welcome сможет использовать общую One Menu инфраструктуру автоматически.

### ~~TODO #4 — FSM goal → skip speed → registered~~ — DONE (коммит b4d8954, mig 175, 5.05 вечер)

**Симптом (live QA 5.05 19:11):** `registration_step_goal` → `complete_onboarding` напрямую — пропускает step_speed и step_phenotype_quiz.

**Root cause:** Блок 10 в `process_onboarding_input` вызывал `complete_onboarding` напрямую при `cmd_select_*`. Ветки `registration_step_speed` и `registration_step_phenotype_quiz` отсутствовали. `workflow_states.next_step_code` для goal содержал `'registered'` (вместо `'registration_step_speed'`).

**Фикс (mig 175):** CREATE OR REPLACE `process_onboarding_input` из pg_get_functiondef (stale-base rule). Добавлены ветки:
- `registration_step_goal`: lose/gain → status='registration_step_speed', render 'edit_speed'; maintain → complete_onboarding напрямую (skip speed)
- `registration_step_speed` (NEW): `cmd_speed_slow/normal/fast` → `set_user_goal_speed()` → `complete_onboarding()` → 'onboarding_success'
- `registration_step_phenotype_quiz` (NEW): placeholder → auto complete_onboarding (реальный quiz — будущая сессия)
- `workflow_states.next_step_code`: goal → `registration_step_speed`

**Gotcha #18:** FSM transitions Phase 4 для `registration_step_goal` **хардкоден inline** в `process_onboarding_input` (не в `workflow_states`). `workflow_states` — flat автомат без branching по context. Для добавления нового шага после goal — патчить SQL функцию через CREATE OR REPLACE.

### ~~TODO #5 — HTTP 400 "inline keyboard expected" → тихие transitions~~ — DONE (коммит b4d8954, 5.05 вечер)

**Симптом (координатор 5.05 19:00):** в журнале prod HTTP 400 «inline keyboard expected» на каждый callback после первого click. Бот молчит на переходах.

**Root cause:** `editMessageText` фейлит с 400 когда target message не имеет inline keyboard (был text-input экраном — ask_age, ask_weight, ask_height). `_post()` возвращал `(False, None)` без fallback.

**Фикс:** `services/telegram_send.py` — `_post()` теперь возвращает parsed body при HTTP 4xx. В `edit_existing` стратегии: при 400 + description содержит `"inline keyboard expected"` (case-insensitive) → fallback `deleteMessage + sendMessage`. WARNING-логирование для observability.

**Gotcha #17:** One Menu pattern требует HTTP 400 fallback на edit text-input messages. Иначе тихие transitions.

### TODO #6 — Hardcoded RU fallback в n8n 03_AI_Engine (зафиксировано 6.05)

**Контекст:** `n8n_workflows/03_AI_Engine.json:181` Build Failed Reply Code-нода
содержит JS-fallback:

```js
if(!Array.isArray(arr)||!arr.length){
  return 'Хм, не получилось распознать. Попробуй ещё раз или напиши текстом.';
}
```

Используется когда `trs[lang].errors.ai_failed` пуст или не array. Для
`es/de/fr/...` массив вариантов есть, для `ar/fa/hi/it/pl/pt/...` —
нужна проверка отдельно.

**Почему НЕ трогаем сейчас (решение тимлида 6.05):** риск положить
legacy AI engine (стабильно обрабатывает реальные food-логи) выше, чем
выигрыш. После Task 4A (NUMERIC_RE до 5 цифр) AI engine больше не получает
числовые опечатки в онбординге → этот fallback редко достижим.

**Когда чинить:** при полной миграции AI Engine с n8n на Python (этап 5
master-roadmap'а). Тогда параллельно:
- Заменить hardcoded fallback на `errors.validation_generic[lang]` lookup
- Гарантировать что `errors.ai_failed` array существует для всех 13 языков
- Удалить n8n 03_AI_Engine workflow

### Приоритет TODO

При следующей фазе разработки:
1. **TODO #1** (refactor) — закрывает архитектурную причину гэпа. Большая работа, но снимает class регрессий.
2. ~~TODO #2~~ DONE — коммит 4985279 (уточнён b4d8954)
3. ~~TODO #3~~ DONE — коммит 4985279
4. ~~TODO #4~~ DONE — mig 175, коммит b4d8954
5. ~~TODO #5~~ DONE — коммит b4d8954

---

## Производительность

p95 latency `process_onboarding_input` (10 прогонов VPS Hetzner → Supabase EU pooler, persistent psycopg2):
- p50 = **44ms**
- p95 = **47ms**

Практически чистый RTT. Baseline `dispatch_with_render` без онбординга — 46ms p50. Дополнительная FSM-логика онбординга **не добавляет заметного оверхеда**.

---

## Ссылки на материалы разведки

Перед реализацией Phase 4 разведку проводили 3 chip-агента. Их карты — обязательное чтение для любого агента, который будет править онбординг:

- **`onboarding-v3-map.md`** — карта legacy `02_Onboarding_v3`: FSM (10 состояний), 9 RPC, экраны, edge cases, mermaid-граф.
- **`onboarding-v3-map-supplement.md`** — pre-implementation audit (4 блока): user creation, referral, legacy v1, translations coverage.
- **`start-fresh-flow.md`** — `reset_to_onboarding` RPC (для `cmd_start_fresh`).

## Ссылки на планы

- **`~/.claude/plans/logical-drifting-fox.md`** — высокоуровневый план Phase 4.
- **`~/.claude/plans/onboarding-impl.md`** — v1 детальный план (FSM в Python, отвергнут — но содержит полный SQL для `ensure_user_exists` который мы реально использовали).
- **`~/.claude/plans/onboarding-second-opinion-brief.md`** — бриф для внешнего ревью архитектурных развилок.
- **`~/.claude/plans/groovy-marinating-eclipse.md`** — мастер-план миграции n8n → Python (Phase 4 здесь = этап 4 общего плана).

## Daily логи

- `daily/2026-05-01.md` — реализация (chip #2-execute), миграция 161 применена.
- `daily/2026-05-02.md` — cutover (merge, deploy, флаг ON), hotfix двойного стикера.
- `daily/2026-05-04.md` — деактивация v1+v3, soft-delete recovery routing fix.
- `daily/2026-05-05.md` — 4-блоковый фикс (mig 171), финальный: mig 172 inline кнопки + \n fix + Ghost Message. Вечер: финальный 3-блоковый (mig 175, ghost off welcome, HTTP 400 fallback). Ночь: единый релиз — объединение 3 параллельных команд в main (mig 176 URL buttons + mig 177 payment isolation).

---

## N. ⛔ ЗАПРЕЩЕНО `./deploy.sh` из feature-веток

**Правило (lesson 5.05 — race condition между 3 командами):**

`./deploy.sh` выполняет rsync **локального checkout** на VPS. Если ты запустил
deploy из feature-ветки (или worktree) — **перетрёшь работу любого другого
агента** который раньше задеплоил из своей ветки. Их код пропадёт с VPS,
бот сломается, никто не узнает почему.

**Канонический инцидент 5.05:** 3 команды работали параллельно:
1. Онбординг fix (наша ветка) — деплоилась 5.05 утром.
2. URL buttons (brave-nobel-0ae50d, uncommitted!) — deploy.sh ~21:00 → перетёр онбординг fix.
3. Payment isolation (romantic-allen-27194c) — точечный SCP router.py.

VPS остался в рассогласованном состоянии: template_engine от Команды 2,
router от Команды 3, остальное от main (без онбординг fix). Юзер видел
«полная тишина» на /start (нашли 404 на get_user_context — наш фикс был
откачен). За 1 день потеряли 4 часа на расследование + reconciliation.

**Правило для всех агентов:**
1. **НЕ запускать `./deploy.sh` из feature-ветки или worktree.**
2. **ОБЯЗАТЕЛЬНО merge feature-branch → main → push origin/main → deploy с main.**
3. **Если нужно срочно** (hotfix без merge): точечный `scp file.py root@VPS:` —
   но только для одного файла. Никакого rsync.
4. **Перед каждым deploy:** `git diff origin/main..HEAD` должен быть пустым
   на feature-ветке (= ветка смерджена). Если не пустой — сначала merge.

**За нарушение** — откат продакшена. Полное расследование + cherry-pick.
