---
status: 🔥 HUB
domain: Onboarding / FSM
last_verified: 2026-05-30
---

# FSM state whitelist discipline

> **HARD RULE.** Adding a new `registration_step_*` (or any onboarding FSM state) to `workflow_states` is **not enough**. You MUST also register it in the appropriate `dispatcher/router.py` frozensets in the same migration, or callbacks/text in that state will silently fall to `target=menu` (legacy n8n drop) → user sees no response.

## Why this keeps happening

Live recurrences (audit 2026-05-30):

| Date | Mig | State added | Whitelist forgotten | Symptom | Lesson agent |
|---|---|---|---|---|---|
| 2026-05-13 | 259 | `registration_step_maternal*` | BUTTON_ONLY_STATUSES + ONBOARDING_STATUSES | `cmd_onb_maternal_*` dropped → menu_v3 has no handler | First time codified |
| 2026-05-13 | 187 | `registration_step_phenotype_quiz` | BUTTON_ONLY_STATUSES | `cmd_quiz_q1_*` text in quiz mode routed to AI food log | mig 187 inline comment |
| 2026-05-29 | 359 | `registration_step_cycle` | BUTTON_ONLY_STATUSES + ONBOARDING_STATUSES | `cmd_save_cycle_*` dropped during onboarding | inline mig 359 comment |
| 2026-05-30 | 382 | `registration_step_diet` | BUTTON_ONLY_STATUSES + ONBOARDING_STATUSES | All 4 `cmd_diet_*` callbacks silently dropped → owner UAT blocked → required PR #240 hotfix | This concept |
| 2026-05-30 | 386 | `registration_step_cycle_length_input` + `_start_date_input` | NUMERIC_INPUT_STATUSES (text input flow) — wrongly added to BUTTON_ONLY | `"30"` for cycle length routed to AI food | mig 386 fix in #239, again refined in #240 |

3+ recurrences over 2 weeks. **This is the single most expensive recurring lesson in NOMS onboarding.**

## The four router frozensets and when each matters

`dispatcher/router.py` keeps three small frozensets that gate FSM dispatch. Picking the right one(s) for a new state is the whole job.

### `BUTTON_ONLY_STATUSES` — line 73

> «User on this screen is **expected to tap an inline button**. Free-form text is treated as food log fallback (`text_food_from_button_step`).»

Add state here when the screen is `input_type='inline_kb'` AND has no callable text path. Examples: gender pick, maternal status, cycle question (Yes/Skip/Explain), diet (omnivore/vegetarian/vegan/skip), phenotype quiz, goal pick.

If you forget: `cb_data=cmd_X` falls into section 4l `is_menu_callback` → `target=menu_v3` → 4xx (no handler) → user sees nothing.

### `NUMERIC_INPUT_STATUSES` — line 63

> «User on this screen is **expected to type a number**. Non-numeric text is treated as food log.»

Add state here when the screen is `input_type='text_input'` with a numeric `save_rpc` (set_user_age / weight / height / cycle_length / etc.).

If you forget: section 8 (NUMERIC_RE match → onboarding) doesn't fire → text falls to section 11 catch-all → AI food engine → user sees «не еда?».

### `ONBOARDING_STATUSES` — line 361

> «User is mid-onboarding. Don't route them through registered-user paths (PROFILE_V5_CALLBACKS, menu_v3 commands, etc.).»

Add state here for ALL `registration_step_*` and `onboarding:*` states. This is the «am I in the funnel» guard used by sections 4h.5, 4f, 10.5 to prevent leaks.

If you forget: random callbacks (cmd_safety_center, cmd_my_plan) start working mid-onboarding → broken FSM transitions.

### `NO_INDICATOR_STATUSES` — `telegram_proxy.py:63`

> «Suppress the thinking-sticker on this screen because the response is fast OR the state expects specific text we don't want to look like food.»

Add when render is instant (button picker, inline preview) AND user might type something like `📋 Выбрать из списка`. Rare. Don't reflex-add.

After 2026-05-30 round 4: with global `delete_thinking` in `webhook_server._send_and_persist`, this set is now LESS necessary — even a false-positive indicator gets cleaned up post-render.

## Checklist when adding a new `registration_step_*` state

Copy-paste into your migration PR description:

```
- [ ] state added to workflow_states (FK to ui_screens)
- [ ] state in process_onboarding_input FSM (text + callback branches)
- [ ] state in ONBOARDING_STATUSES — ALWAYS for registration_step_*
- [ ] state in BUTTON_ONLY_STATUSES — if screen is inline_kb only
- [ ] state in NUMERIC_INPUT_STATUSES — if screen is text_input expecting a number
- [ ] state in NO_INDICATOR_STATUSES — only if response is <50ms (rare)
- [ ] new cmd_* callbacks in HEADLESS_CALLBACKS — if dispatched via dispatch_with_render save_via_callback
- [ ] python router test covering target resolution for this state
```

The first 4 lines catch 95% of recurrences. If you skip them, expect owner UAT to find the bug within hours.

## Recurrence 2026-05-31 — un-hidden button без routing-check (mig 390 → fix #248)

mig 390 **показал** кнопку «Назад» (снял visible_condition) на `edit_speed` в онбординге, но `registration_step_speed` **отсутствовал в BUTTON_ONLY_STATUSES** → `cmd_back` маршрутизировался в `target='ai'` (food engine) вместо onboarding → юзер видел мусор. goal/activity/training там были (повезло), speed — нет. Fix #248: + `registration_step_speed` в BUTTON_ONLY.

**Два новых правила из этого рецидива:**
1. **Показываешь inline-кнопку на статусе → проверь, что статус в правильном whitelist.** Un-hide кнопки = новый callback-путь, которого раньше не было. «Кнопка есть в БД, но скрыта» = routing никогда не тестировался.
2. **🔴 Тестируй back-навигацию через `dispatcher.router.route()` (ПОЛНЫЙ путь), а НЕ прямой вызов `process_onboarding_input`.** mig 390 тестировался прямым вызовом RPC → переходы верны, но пропущено, что роутер вообще не доводит `cmd_back` до RPC (уходит в 'ai'). Прямой-RPC тест = **ложная зелёнка**. Минимум: `route(callback, ctx) → target` + `route(text, ctx) → target`.

Открытый риск (handover 2026-05-31): text-шаги `registration_step_2/3/4` (age/weight/height) тоже route cmd_back → 'ai'. Не баг пока (text_input → remove_keyboard, кнопки нет). Но variant-1 (инлайн-back на text-шагах) обязан сперва добавить их в routing.

## Related

- [[concepts/headless-fsm-vs-dynamic-handler-separation]] — broader FSM vs handler architecture
- [[concepts/action-router-pattern]] — router design
- [[concepts/router-prefix-collision]] — sibling gotcha (callback prefix matching)
- [[concepts/onboarding-v3-map]] — FSM state map
- mig 259 (canonical first codification of this lesson)
- mig 382 + 386 (latest recurrences fixed)

## Рецидив (2026-05-31): suppression индикатора должна совпадать с гейтом обработчика

Тот же класс рассинхрона, но между **telegram_proxy `maybe_send_indicator`** и **`handle_onboarding_food`** (webhook gate), не только router'ом.

- **Гейт обработчика** онбординг-еды: `status == "new" OR status LIKE "registration_step_%"`.
- **Suppression индикатора** в proxy покрывала только `registration_step_*` — **`new` был пробелом**. На первом шаге онбординга (status `new`) еда → proxy слал food-текст «Анализирую еду» + handle_onboarding_food слал СВОЙ стикер → `clear_indicator_message` удалял стикер, food-текст орфанился (UAT 31.05, PR #257).
- **Fix:** в suppression добавлен `new` (полное совпадение с гейтом). Плюс контент-исключение для location (ей индикатор нужен — стикер, не food-текст).

**Правило расширено:** когда новый обработчик ловит набор статусов, **все компоненты, фильтрующие по статусу** (router BUTTON_ONLY/ONBOARDING, NO_INDICATOR_STATUSES в proxy, и т.п.) должны покрывать ТОТ ЖЕ набор. Рассинхрон → двойные/потерянные side-effects. Проверяй полный путь, не один компонент.

## Рецидив (2026-06-12): post-registered AI gate в webhook_server, маскированный legacy n8n

**Второй blast-сайт того же класса.** До этого все рецидивы — router'ные frozensets (BUTTON_ONLY_STATUSES / NUMERIC_INPUT_STATUSES / ONBOARDING_STATUSES). Это **первый кейс whitelist'а в `webhook_server._try_authoritative_path`**.

### Симптом (live tid=417002669, 22:24)

User → меню Профиль → ⚙ Настройки → Уведомления (`cmd_edit_notifications_mode` ставит `users.status='edit_notifications_mode'` через `process_user_input`). Шлёт фото еды. В чате — прежний рендер «Настройки», `food_logs` пуст. `journalctl`:

```
AUTHORITATIVE skip tid=... target=ai reason=food_media — fall through to legacy
```

### Корень

Stage 7 AI gate ([`webhook_server.py:1631`](webhook_server.py)) принимал `food_media` только при `status in (registered, editing_meal, waiting_barcode_portion)`. Profile-v5 substates (`edit_notifications_mode`, `edit_country`, `edit_lang`, `edit_timezone`, `edit_gender`, `edit_diet`, `edit_weight`, ...) **не в whitelist'е** — фото отвергалось → forward_to_n8n → **n8n `03_AI_Engine` DELETED 06-08** → silent drop.

Router'у не за что винить: он корректно классифицировал `target=ai reason=food_media` (см. `dispatcher/router.py:1070`).

### Почему не было видно раньше

До 06-08 `03_AI_Engine` существовал — `fall through to legacy` означало «n8n обработает». После DELETE — означает «silent drop». **Cutover N+1 правило:** удаление legacy-таргета — это семантическое изменение всех `return False` веток в `_try_authoritative_path`, которые на него рассчитывали. Перед удалением workflow:

```bash
grep -n "fall through to legacy" webhook_server.py
```

Для каждого — спроси: «когда сюда попадает, n8n правда умеет обработать?». Если нет (workflow deleted) — fall-through надо ИЛИ закрывать в Python, ИЛИ явно отбрасывать с user-facing ошибкой, НЕ молча.

### Фикс ([#387](https://github.com/sharkovvlad/noms-bot/pull/387))

1. Import `PROFILE_V5_STATUSES` из `dispatcher.router`.
2. Новый флаг `_is_profile_v5_food_escape` (`target=ai` AND `reason=food_media` AND `status ∈ PROFILE_V5_STATUSES`) → расширяет гейт.
3. Внутри ветки — fire-and-forget `set_user_status('registered')` чтобы picker не висел для NEXT запроса.
4. `text_food` ИЗ escape ИСКЛЮЧЁН: numeric input «88» в `edit_weight` мог бы перехватиться как food. Router и так такой текст уводит на `menu_v3 → profile_v5_text_input` — defence in depth.
5. Лог-метка `AUTHORITATIVE_AI_PROFILE_ESCAPE` для телеметрии.

### Durable правила (расширение HUB)

1. **Whitelist'ов с FSM-статусами — несколько blast-сайтов**, не только router'ные frozensets:
   - `dispatcher/router.py`: `BUTTON_ONLY_STATUSES`, `NUMERIC_INPUT_STATUSES`, `ONBOARDING_STATUSES`, `PROFILE_V5_STATUSES`.
   - `webhook_server.py:_try_authoritative_path`: hard-coded tuple в Stage 7 AI gate.
   - `telegram_proxy.py:NO_INDICATOR_STATUSES`.
   - Возможно ещё. Перед добавлением нового статуса — `grep -rn '"<status>"\|status\s*==\s*"' --include="*.py" .` чтобы найти все коды-проверки.

2. **«Fall through to legacy» log site = TODO до окончания cutover'а.** Когда конкретный legacy-таргет удаляется, каждое использование должно стать ИЛИ обработкой в Python, ИЛИ user-facing ошибкой. `grep -n "fall through to legacy" webhook_server.py` перед каждым n8n DELETE.

3. **При запуске нового FSM-статуса для уже-существующего реал-юзера** (не онбординг — а profile-edit, payment-wait и т.п.) — тестируй ВСЕ типы input'а из этого статуса:
   - inline-callback клик ✓
   - текст (если применимо) ✓
   - **фото / голос** ← наиболее часто забываемое
   - location pin ← забывается так же часто

   Photo/voice от взрослого юзера — клёвая нагрузка пользовательских ожиданий, и должна работать ВСЕГДА (юзер хочет залогать еду, неважно где он сидит в FSM).

---

## Generalization 2026-06-12 (Этап A n8n-teardown): food-media escape для ВСЕХ статусов

Рецидивы FSM-whitelist (#387 profile-v5, и до того mig 187b/257/276) — все один класс: **новый FSM-статус не в AI-гейте → фото проваливается**. Вместо whitelist-по-одному (вечная гонка) — обобщили принцип в коде:

**Photo/voice/image-doc от взрослого юзера = ЕДА в ЛЮБОМ статусе, КРОМЕ онбординга.**

`webhook_server._try_authoritative_path` (~1633, PR #390):
```python
_is_food_media_escape = (
    target == "ai" and _ai_reason == "food_media"
    and _status not in ("registered", "editing_meal", "waiting_barcode_portion")
    and _status not in ONBOARDING_STATUSES   # ← единственное исключение
)
```
+ fire-and-forget `set_user_status('registered')` (сброс зависшего picker/quiz).

**Почему онбординг — исключение:** food-фото при регистрации обрабатывается ОТДЕЛЬНОЙ веткой `AUTHORITATIVE_ONB_FOOD` (`handle_onboarding_food` → `log_meal_onboarding`, без XP/streak, возврат на шаг онбординга). Reset в `registered` там НЕ делается — иначе сломал бы регистрацию.

**Почему text_food НЕ обобщён:** текст в edit-статусе может быть числовым вводом («88» в `edit_weight`) — router и так уводит его в menu_v3 (`profile_v5_text_input`). Обобщать только media (однозначный food-сигнал).

**Архитектурный факт:** router классифицирует ЛЮБОЕ фото → `target=ai reason=food_media` в секции 6 (router.py ~1069) ДО онбординг-секции 7 → **AI-гейт в webhook_server = единственное место гейтинга фото по статусу.** Поэтому одна правка там покрывает все FSM-статусы (в отличие от whitelist'ов которые надо править в N местах).

## Git gotcha (process, 2026-06-12)
Бэктики в `git commit -m "...текст с \`code_identifier\`..."` через **double-quotes** ИСПОЛНЯЮТСЯ zsh как command-substitution → имена переменных молча съедаются из commit-сообщения («command not found»). Для сообщений с code-идентификаторами/backtick → **`git commit -F file`** (heredoc в файл, single-quote delimiter).
