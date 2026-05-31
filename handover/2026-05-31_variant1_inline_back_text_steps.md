# Handover — Variant 1: инлайн-«Назад» на text_input шагах онбординга

**From:** Opus 4.7 session 2026-05-31 (длинная сессия My Day + onboarding back-nav).
**To:** Следующий агент.
**Status:** НЕ начато. Спроектировано, есть точный план + ловушки. Owner одобрил («бери если позволяет контекст») — контекст исчерпан, рисковать на исходе сессии не стал.

---

## Что нужно сделать (цель)

Показать видимую инлайн-кнопку «Назад» на текстовых шагах онбординга **возраст / вес / рост** (`ask_age` / `ask_weight` / `ask_height`), чтобы юзер мог вернуться на предыдущий шаг и исправить уже введённое. Сейчас на этих шагах кнопки «Назад» НЕТ (по дизайну рендерера — см. ниже).

Owner предпочёл этот вариант (а не 2-message pattern).

## Почему сейчас её нет (механика)

`text_input`-экраны рендерятся с `reply_markup={remove_keyboard:true}` ([services/template_engine.py:433](services/template_engine.py:433) `_build_reply_markup`), и **инлайн-кнопки из БД игнорируются**. Жёсткое правило Telegram: в одном сообщении нельзя одновременно `inline_keyboard` И `remove_keyboard`. Подробно — KB [[concepts/one-time-attach-pattern]] + [[concepts/profile-redesign-v5]] §Stale Language keyboard fix.

## Что УЖЕ готово (не делать заново)

1. **RPC `process_onboarding_input` (mig 390)** уже обрабатывает `cmd_back` для `registration_step_2` (age→gender), `registration_step_3` (weight→branch), `registration_step_4` (height→weight). Логика «назад» для этих шагов РАБОТАЕТ — не хватает только видимой кнопки + правильного роутинга.
2. **Кнопки в БД:** у `ask_age`/`ask_weight`/`ask_height` уже есть row `cmd_back` с `text_key='buttons.back'` (переименованы из `buttons.cancel` в mig 390). `buttons.back`='Назад' × 13 langs существует.

## Что НУЖНО сделать — 2 изменения + тесты

### 1. РОУТЕР (Python, нужен деплой) — dispatcher/router.py

Сейчас `cmd_back` на этих статусах маршрутизируется НЕ туда (проверено через `route()`):
- `registration_step_2` (age) → `target='ai'` ❌
- `registration_step_3` (weight) → `target='ai'` ❌
- `registration_step_4` (height) → ??? (проверить, вероятно 'ai')

Это ТА ЖЕ ловушка, что убила «Назад» на скорости (см. #248 / [[concepts/fsm-state-whitelist-discipline]]). Нужно, чтобы `cmd_back` на этих статусах шёл в `onboarding`.

⚠️ **ОСТОРОЖНО:** эти статусы — **text_input** (есть в наборе строк 64-79 router.py, вероятно NUMERIC/ONBOARDING set для маршрутизации ТЕКСТА в onboarding). Если добавить их в `BUTTON_ONLY_STATUSES` — проверь, что **текстовый ввод** (набранное число) ВСЁ ЕЩЁ маршрутизируется в onboarding для сохранения (а не ломается). Возможно, нужен не BUTTON_ONLY, а отдельная обработка cmd_back. **Тестируй ОБА: и `cmd_back`-callback, и текст-число — через `route()`.**

### 2. РЕНДЕРЕР — показать инлайн-«Назад» на этих text_input экранах

`_build_reply_markup` (template_engine.py:433) для `text_input` всегда возвращает `{remove_keyboard:true}`. Нужно: для ПОМЕЧЕННЫХ экранов отдавать `inline_keyboard` с кнопкой «Назад» вместо `remove_keyboard`.

**Рекомендуемый подход — per-screen meta-флаг** (НЕ менять поведение для всех text_input):
- Добавить в `ui_screens.meta` флаг (напр. `show_back_inline=true`) для `ask_age`/`ask_weight`/`ask_height` (миграция).
- В `_build_reply_markup`: если `input_type=='text_input'` И флаг → строить `inline_keyboard` из `keyboard` (как для inline_kb), иначе прежний `{remove_keyboard:true}`.
- Инлайн-кнопки НЕ мешают вводу текста — юзер может либо нажать «Назад», либо впечатать число.

⚠️ **НЕ применять флаг к:** `cycle_start_date_input`/`cycle_length_input` (у них своя логика), `country/timezone` (там ЕСТЬ reply-kb с share-location — нельзя терять remove_keyboard бездумно), профильным правкам (`ask_*` используются и в профиле — но там `personal_metrics` теперь reply_kb_entry, mig 392, после правки kb возвращается; если показать инлайн-back в профиле — проверь, что не сломает remove_keyboard logic). **Лучше: флаг + дополнительно проверять `status LIKE 'registration_step_%'`**, чтобы инлайн-back показывался ТОЛЬКО в онбординге, а в профиле остался remove_keyboard.

### 3. ТЕСТЫ (обязательно, через FULL PATH)

**Урок этой сессии (KB fsm-state-whitelist-discipline):** я тестировал mig 390 вызывая `process_onboarding_input` НАПРЯМУЮ → пропустил, что роутер шлёт cmd_back не туда (баг на скорости #248). **Тестируй через `dispatcher.router.route()`** (полный путь), не только RPC.

Для КАЖДОГО шага (age/weight/height):
- `route(cmd_back, status)` → `target='onboarding'`.
- `route(text='30', status)` → всё ещё в onboarding (сохранение не сломано).
- Полный прогон: cmd_back → правильный предыдущий экран (через process_onboarding_input, mig 390 logic).
- Рендер экрана: инлайн-«Назад» присутствует (а reply-kb logic не сломана).
- Профиль (status=edit_weight/edit_age): убедиться, что там поведение НЕ изменилось (remove_keyboard сохранён, mig 392 re-attach работает).
- psycopg2 в транзакции с ROLLBACK — не мутировать юзеров.

## Текущее состояние проекта (на 2026-05-31)

- **mig HEAD = 392 LIVE.** Все применены к БД руками (psycopg2).
- **Merged:** #244 (mig 389 My Day phase-aware + Python deployed), #246 (mig 390 onboarding back), #247 (mig 391 quiz/maternal back), #248 (router speed back fix — Python, deployed b0da952).
- **Open PR:** #249 (mig 392 profile reply-kb re-attach — данные, LIVE, ждёт merge; деплой не нужен).
- **Тест-аккаунт 786301802:** female 30, owner прогнал онбординг — всё работает (вкл. «Назад» на кнопочных шагах + «Авилес»).
- **Реальный аккаунт owner: 417002669** (registered).

## Открытые задачи (бэклог, не варинат-1)

- **Длина онбординга (UX-аудит находка #2)** — owner: «потом». Подготовить design-предложение «что отложить на после первого лога».
- **«Авилес» edge case** — НЕ закрыт детерминированно (31.05 сработал случайно, city_resolver не менялся, порог 0.7). При рецидиве — Geoapify forward-fallback / ниже порог / лучше промпт.
- **Чужие красные тесты** (не блокеры, не наши): `test_router.py` (onboarding:country→location, city_resolver), `test_telegram_send.py` error. Стоит почистить отдельно.
- **CI hardening:** шаг `[6/6] Verifying services` в deploy.yml хрупкий (SSH-обрыв = ложный красный деплой). Retry или убрать (smoke-тест и так бьёт /health).

## Ключевые KB для этой задачи
- 🔥 [[concepts/fsm-state-whitelist-discipline]] — роутер-whitelist, тестируй через route().
- [[concepts/one-time-attach-pattern]] — reply-kb lifecycle, remove_keyboard, Telegram constraints.
- [[concepts/phase2-python-menu-v3]] — text_input → remove_keyboard правило.

EOS — Opus 4.7, 2026-05-31.

---

## DE-RISK UPDATE (агент angry-liskov, 2026-05-31, после mig 393/394)

Подтверждённые фактами неизвестные (чтобы исполнитель не перепроверял):

1. **Router СЕЙЧАС misroute'ит cmd_back на step_2/3/4 → `ai`** (проверено `route()`):
   `route(cmd_back, registration_step_2/3/4)` → `target='ai' reason='text_food'`.
   Текст («30») → `onboarding reason='numeric_answer'` (корректно, NUMERIC-фаза раньше).
   → Нужно добавить `registration_step_2/3/4` в `BUTTON_ONLY_STATUSES`. **Проверить через route(), что текст ВСЁ ЕЩЁ → onboarding** (numeric_answer фаза должна срабатывать до button-only; подтвердить, что добавление в BUTTON_ONLY не перехватывает текст).

2. **`ask_age/ask_weight/ask_height` — ОБЩИЕ screen_id** для онбординга и профиля:
   `workflow_states`: `edit_age→ask_age`, `edit_weight→ask_weight`, `edit_height→ask_height` (профиль) И `registration_step_2/3/4` рендерят те же экраны (онбординг).
   → Screen-level meta-флаг (`show_back_inline`) затронет ОБА контекста. **ОБЯЗАТЕЛЕН status-гейт в render_screen** (`v_user.status LIKE 'registration_step_%'`), иначе профильные edit_weight/age/height потеряют `remove_keyboard` → reply-kb регрессия (боль mig 392).

3. **RPC back-логика (mig 390) для step_2/3/4 — в LIVE**, не трогать.

### Точный change-list (execute-ready)
- **render_screen (RPC mig):** в Step 9 (telegram_ui assembly) добавить поле, напр. `text_input_inline_back` = `(v_screen.input_type='text_input' AND COALESCE(v_screen.meta->>'show_back_inline','')='true' AND v_user.status LIKE 'registration_step_%')`. Anchor-replace по live `pg_get_functiondef` (Pattern 4). ⚠️ render_screen — самый shared RPC, любой anchor-промах = глобально.
- **template_engine.py `_build_reply_markup` (services/template_engine.py:433):** `if input_type=='text_input':` → если `telegram_ui.get('text_input_inline_back')` → вернуть `{'inline_keyboard': _build_inline_keyboard(keyboard,...)}`, иначе прежний `{'remove_keyboard': True}`. (keyboard уже в telegram_ui — содержит cmd_back-кнопку.)
- **router.py:** `registration_step_2/3/4` в `BUTTON_ONLY_STATUSES`. Verify текст не ломается.
- **data mig:** `ui_screens.meta || '{"show_back_inline":true}'` для `ask_age/ask_weight/ask_height` ТОЛЬКО.
- **тесты (FULL PATH route()):** для каждого step — cmd_back→onboarding + text→onboarding (не сломан); render: онбординг ask_weight → inline_keyboard с «Назад»; **профиль edit_weight (status=edit_weight) → ВСЁ ЕЩЁ remove_keyboard** (регресс-страховка); cycle/country text_input не затронуты.

**Почему не сделано в этой сессии:** owner pre-approved, но change затрагивает render_screen (shared) + hot-path шаблонизатора + профиль как regression-поверхность. Контекст-бюджет сессии (bugs A/B + research) исчерпан; shared-renderer лучше делать фокусной сессией со свежим контекстом. Risk-консенсус: предыдущий handover-автор + UX-research-агент + этот агент.
