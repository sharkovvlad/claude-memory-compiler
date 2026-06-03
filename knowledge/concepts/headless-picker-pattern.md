# Headless Picker Pattern — полный recipe для inline-kb pickers

**Компилировано:** 2026-04-21 из `daily/2026-04-21.md` Session 10. Стабильный живой pattern после 6 миграций + 2 n8n PUTs. Используй как готовый шаблон для любого нового Headless picker (не копируй слепо — адаптируй названия).

**Обновлено 2026-04-22** — Session 10 TOTAL завершён (migrations 110-120), Session 11 items.

## Что это

Pattern для создания **inline-keyboard picker экрана** в Pure Headless Architecture:
- Triggered by `cmd_edit_*` button из родителя
- Показывает 3-N опций с unique icons + checkmark (`✅`) на текущем выборе
- Save через callback click → setter RPC → auto-navigate обратно
- Reuse с онбордингом (один screen_id, разные state_code в `workflow_states`)

**Примеры live после Session 10:** `edit_goal`, `edit_activity`, `edit_training`, `edit_speed`, `edit_gender`, `edit_lang`, `edit_notifications_mode`. Latency p95 < 165ms.

## Архитектурные слои

```
user click [🏋 Силовые] (inline)
    ↓ Telegram callback_query
[Python proxy] forwards to n8n
    ↓
[01_Dispatcher] Route Classifier v1.9
    • callback='cmd_select_strength', user.status='edit_training' (in PROFILE_V5_STATUSES)
    • callback.startsWith('cmd_select_') AND user.status in edit_* → route_target='menu_v3'
    ↓
[04_Menu_v3] executeWorkflow
    ↓ HTTP process_user_input RPC
    ↓
[Supabase PostgreSQL]
    process_user_input(tg, 'callback', {callback_data:'cmd_select_strength'})
    ├─ Resolve v_current_screen from nav_stack → 'edit_training'
    ├─ Match button in ui_screen_buttons WHERE screen_id='edit_training' AND callback_data='cmd_select_strength'
    │  → button.meta = {save_via_callback:true, save_rpc:'set_user_training_type',
    │                    target_screen:'my_plan', clear_status:true, save_value:'strength'}
    ├─ WHITELIST check: proname LIKE 'set_user_%' AND nspname='public' (SQL injection defense)
    ├─ EXECUTE format('SELECT public.%I($1,$2)', 'set_user_training_type') → training_type='strength'
    ├─ clear_status=true → users.status='registered'
    ├─ v_next_screen = 'my_plan' (from meta.target_screen)
    ├─ push_nav(my_plan); success_reaction='👌'
    └─ render_screen('my_plan') → returns keyboard w/ is_current flags
    ↓ JSONB: {telegram_ui: {keyboard, text_key, success_reaction:'👌', render_strategy}}
[04_Menu_v3 Dumb Renderer JS]
    • lookupKey(translations, text_key) → label
    • if btn.icon_const_key: prepend constants[key] + ' '
    • if btn.is_current AND constants.icon_check: prepend '✅ ' (Session 10 migration 115)
    • Final text e.g. "✅ 🏋 Силовые"
    ↓
[Switch Render Strategy] → editMessageText / deleteMessage+sendMessage / sendMessage
    ↓
[Is Success Reaction?] → Set Message Reaction (👌 on user message)
    ↓
user sees updated my_plan with new training_type
```

## DB recipe (minimum viable picker)

### 1. app_constants — icons (ON CONFLICT DO NOTHING)

```sql
INSERT INTO public.app_constants (key, value) VALUES
  ('icon_check', '✅'),
  ('icon_XXX_option1', '🎯'),  -- unique per option
  ('icon_XXX_option2', '🔥'),
  ('icon_XXX_option3', '💪')
ON CONFLICT (key) DO NOTHING;
```

### 2. ui_screens row

```sql
INSERT INTO public.ui_screens (
  screen_id, render_strategy, text_key, parent_screen_id,
  back_screen_id_default, input_type, save_rpc, next_on_submit, meta
) VALUES (
  'edit_XXX', 'replace_existing', 'questions.XXX', '<parent>',
  '<parent>', 'inline_kb', NULL, '<parent>',
  jsonb_build_object('current_value_col', 'users_column_name')
) ON CONFLICT (screen_id) DO UPDATE
  SET meta = ui_screens.meta || EXCLUDED.meta;
```

**Key fields:**
- `render_strategy='replace_existing'` — editMessageText (inline callback)
- `input_type='inline_kb'` — picker, not text
- `save_rpc=NULL` — save happens via button.meta, not screen-level
- `meta.current_value_col` — **critical** for checkmark logic. Points to `users.<column>`

### 3. workflow_states — either UPDATE existing OR INSERT

```sql
-- If state_code exists (typical):
UPDATE workflow_states
SET screen_id='edit_XXX', save_rpc='set_user_XXX'
WHERE state_code='edit_XXX';

-- Else INSERT (new state):
INSERT INTO workflow_states (state_code, description, screen_id, next_step_code, save_rpc)
VALUES ('edit_XXX', '<desc>', 'edit_XXX', 'registered', 'set_user_XXX')
ON CONFLICT (state_code) DO UPDATE SET
  screen_id=EXCLUDED.screen_id, save_rpc=EXCLUDED.save_rpc;
```

### 4. ui_screen_buttons — trigger + options

```sql
-- UPDATE existing trigger button in parent (e.g. my_plan):
UPDATE ui_screen_buttons
SET meta = COALESCE(meta,'{}'::jsonb) || jsonb_build_object(
    'target_screen', 'edit_XXX',
    'set_status', 'edit_XXX'
)
WHERE screen_id='my_plan' AND callback_data='cmd_edit_XXX';

-- INSERT option buttons (use existing cmd_select_* per RPC ground truth):
INSERT INTO ui_screen_buttons (screen_id, row_index, col_index, text_key, callback_data, icon_const_key, meta)
VALUES
  ('edit_XXX', 0, 0, 'answers.option1', 'cmd_select_option1', 'icon_XXX_option1',
    jsonb_build_object(
      'save_via_callback', true,
      'save_rpc', 'set_user_XXX',
      'save_value', 'option1',
      'target_screen', '<parent>',
      'clear_status', true)),
  ('edit_XXX', 1, 0, 'answers.option2', 'cmd_select_option2', 'icon_XXX_option2',
    jsonb_build_object(...)),
  ('edit_XXX', 99, 0, 'buttons.back', 'cmd_back', 'icon_back',
    jsonb_build_object('target_screen', '<parent>', 'clear_status', true))
ON CONFLICT (screen_id, row_index, col_index) DO UPDATE
  SET callback_data=EXCLUDED.callback_data, meta=EXCLUDED.meta,
      text_key=EXCLUDED.text_key, icon_const_key=EXCLUDED.icon_const_key;
```

**Callback convention RULE:** use `cmd_select_*` префикс (существующие setter RPCs парсят его). Для `set_user_goal_speed` исключение — `cmd_speed_*`. **Всегда grep RPC body** (`pg_get_functiondef`) до invention новых prefixes.

**row_index=99 для back** — sentinel для dynamic_list (back всегда последним).

### 5. setter RPC (если ещё нет)

Copy pattern from `set_user_goal` (migration 063):

```sql
CREATE OR REPLACE FUNCTION public.set_user_XXX(p_telegram_id bigint, p_input_text text)
 RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
AS $$
DECLARE v_value TEXT;
BEGIN
    v_value := CASE
        WHEN p_input_text = 'cmd_select_option1' THEN 'option1'
        WHEN p_input_text = 'cmd_select_option2' THEN 'option2'
        WHEN p_input_text IN ('option1', 'option2') THEN p_input_text
        ELSE NULL
    END;
    IF v_value IS NULL THEN
        RETURN jsonb_build_object('ok', false, 'error_key', 'errors.invalid_XXX');
    END IF;
    UPDATE public.users SET XXX_column=v_value, updated_at=NOW()
     WHERE telegram_id=p_telegram_id;
    RETURN jsonb_build_object('ok', true, 'field', 'XXX_column',
                              'value', v_value, 'reaction', '👌');
END$$;

GRANT EXECUTE ON FUNCTION public.set_user_XXX TO service_role;
```

### 6. translations (× 13 langs, deep-merge!)

```sql
UPDATE public.ui_translations
SET content = jsonb_set(
    COALESCE(content, '{}'::jsonb),
    '{questions,XXX}',
    to_jsonb('<localized question>'::text)
)
WHERE lang_code='ru';
-- repeat for 13 langs
```

**CRITICAL:** `jsonb_set` + `COALESCE`, **never** `content || '{...}'::jsonb` (shallow merge уничтожит существующие секции). See migration 102 incident + 108 pattern.

**No raw emoji в answers.***: emoji только в `icon_const_key` или `app_constants`. Иначе Dumb Renderer будет дублировать (🐢🐢 Медленный bug из Session 10).

**Исключение: `answers.lang_*`** — intentionally содержит native flag+label (design doc §1.6).

## 01_Dispatcher Route Classifier

Добавить callback в `PROFILE_V5_CALLBACKS` set + state_code в `PROFILE_V5_STATUSES`. Важно — также routing block для option callbacks когда user в edit_* state:

```javascript
// Picker option saves — route cmd_select_*/cmd_speed_*/etc to menu_v3 when user in edit_* state
if (callback && PROFILE_V5_STATUSES.has(user.status) && (
    callback.startsWith('cmd_select_') ||
    callback.startsWith('cmd_speed_') ||
    callback.startsWith('cmd_lang_')
)) {
    return { json: { ...user, route_target: 'menu_v3', route_reason: 'profile_v5_picker_save' }};
}
```

После PUT — **ВСЕГДА deactivate + activate** per CLAUDE.md Rule #10 (n8n Cloud кэш).

## Dumb Renderer (04_Menu_v3) — что он делает для каждой кнопки

```javascript
let btnText = lookupKey(translations, btn.text_key) || btn.text_key;
if (btn.icon_const_key && constants[btn.icon_const_key]) {
    btnText = constants[btn.icon_const_key] + ' ' + btnText;
}
// Session 10: checkmark prefix
if (btn.is_current && constants.icon_check) {
    btnText = constants.icon_check + ' ' + btnText;
}
```

Порядок: `✅ <original icon> <label>`. НЕ `✅ <label>` (icon replaced).

## render_screen checkmark logic (самое важное)

В render_screen RPC в keyboard build LOOP:

```sql
-- Detect "current" option by cross-referencing user's column with button's save_value
v_is_current := FALSE;
IF v_screen.meta ? 'current_value_col' AND v_button.meta ? 'save_value' THEN
    v_current_col := v_screen.meta->>'current_value_col';
    v_button_val := v_button.meta->>'save_value';
    BEGIN
        EXECUTE format('SELECT ($1.%I)::text', v_current_col)
            INTO v_user_current_val USING v_user;
    EXCEPTION WHEN OTHERS THEN v_user_current_val := NULL;
    END;
    v_is_current := (v_user_current_val IS NOT NULL AND v_user_current_val = v_button_val);
END IF;

-- Keep original icon_const_key (migration 115 revert from 113)
v_current_row := v_current_row || jsonb_build_array(
    jsonb_build_object(
        'text_key', v_button.text_key,
        'callback_data', v_cb_final,
        'icon_const_key', v_button.icon_const_key,  -- unchanged
        'is_current', v_is_current                   -- flag for Dumb Renderer
    )
);
```

**Key insight:** `current_value_col` mapping живёт в `ui_screens.meta`, `save_value` живёт в `button.meta`. Picker screen знает "какую колонку смотреть", button знает "какое значение он сохраняет". render_screen сравнивает.

## process_user_input extensions (migration 110 Block H)

### save_via_callback handling с whitelist validation

```sql
-- Inside callback branch, после FOUND button matching:
IF v_button.meta ? 'save_via_callback'
   AND COALESCE((v_button.meta->>'save_via_callback')::boolean, FALSE) THEN
    v_save_rpc_name := v_button.meta->>'save_rpc';
    -- SECURITY: whitelist — only set_user_* in public schema
    IF NOT EXISTS (
        SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname='public' AND p.proname=v_save_rpc_name
          AND p.proname LIKE 'set\_user\_%' ESCAPE '\'
    ) THEN
        RAISE EXCEPTION 'Invalid save_rpc: %', v_save_rpc_name;
    END IF;
    -- Dynamic EXECUTE
    BEGIN
        EXECUTE format('SELECT public.%I($1,$2)', v_save_rpc_name)
            INTO v_save_result USING p_telegram_id, v_callback;
        v_save_ok := TRUE;
    EXCEPTION WHEN OTHERS THEN
        RETURN jsonb_build_object('status','error','error_code','save_rpc_failed',
                                  'details',SQLERRM,'save_rpc',v_save_rpc_name);
    END;
END IF;
```

**NEVER skip the whitelist** — prevents SQL injection even though meta is server-controlled.

### clear_status handling

```sql
IF v_button.meta ? 'clear_status'
   AND COALESCE((v_button.meta->>'clear_status')::boolean, FALSE) THEN
    UPDATE users SET status='registered', last_active_at=NOW()
     WHERE telegram_id=p_telegram_id;
END IF;
```

### cmd_back unconditional reset для edit_*/editing:*

```sql
IF v_callback = 'cmd_back' THEN
    IF v_user.status LIKE 'edit\_%' ESCAPE '\' OR v_user.status LIKE 'editing:%' THEN
        UPDATE users SET status='registered', last_active_at=NOW()
         WHERE telegram_id=p_telegram_id;
    END IF;
    -- ...original cmd_back logic
END IF;
```

### Top-level fast-path (migration 114)

```sql
IF v_callback IN ('cmd_get_profile','cmd_my_plan','cmd_settings',
                  'cmd_personal_metrics','cmd_help','cmd_delete_account') THEN
    v_next_screen := CASE v_callback
        WHEN 'cmd_get_profile'      THEN 'profile_main'
        WHEN 'cmd_my_plan'          THEN 'my_plan'
        WHEN 'cmd_settings'         THEN 'settings'
        WHEN 'cmd_personal_metrics' THEN 'personal_metrics'
        WHEN 'cmd_help'             THEN 'help'
        WHEN 'cmd_delete_account'   THEN 'delete_account_confirm'
    END;
    -- Top-level nav always starts clean; prevents "Profile → edit_speed" fallback
    UPDATE users SET nav_stack='[]'::jsonb, last_active_at=NOW()
     WHERE telegram_id=p_telegram_id;
    IF v_user.status LIKE 'edit\_%' ESCAPE '\' OR v_user.status LIKE 'editing:%' THEN
        UPDATE users SET status='registered' WHERE telegram_id=p_telegram_id;
    END IF;
ELSIF v_callback = 'cmd_back' THEN
    ...
```

## Gotchas

1. **Shallow vs deep merge translations.** Migration 102 уронил секции `questions`, `answers` в одной из lang_codes using `||`. Always `jsonb_set(content, '{path}', value)`.

2. **input_type для dynamic_list.** CHECK constraint enum не включает `'list_rpc'` — используй `dynamic_list` + отдельно заполни `ui_screens.list_rpc`.

3. **render_strategy enum не допускает `multi-step`.** edit_phenotype (4Q quiz) deferred в Session 11, потому что CHECK constraint `IN ('replace_existing','delete_and_send_new','send_new')`.

4. **Raw emoji в translation values ≠ Dumb Renderer пренсет icon.** Session 10 discovered: `answers.speed_slow = '🐢 Медленный'` + `icon_const_key='icon_speed_slow'='🐢'` → `🐢 🐢 Медленный`. Strip raw emoji OR не ставь icon_const_key.

5. **FSM naming drift:** в БД coexist `edit_*` (underscore) и `editing:*` (colon) паттерны. Session 10 решил использовать `edit_*` consistently, оставить legacy `editing:country/timezone` deprecated.

6. **nav_stack overflow при click'ах без pop.** push_nav добавляет при каждом отличном screen transition. Если не pop (cmd_back) — накапливается. Top-level fast-path (migration 114) clears stack при canonical navigation.

7. **delete_and_send_new + save_reaction race.** deleteMessage выполняется до setMessageReaction → reaction на удалённом сообщении невидима. Session 11 fix — либо delay delete, либо реаct on новом bot message.

## Sanity E2E checks before shipping

```sql
-- 1. Screen + buttons wired
SELECT s.screen_id, s.meta->>'current_value_col' AS col,
       COUNT(b.*) AS btns
FROM ui_screens s
LEFT JOIN ui_screen_buttons b ON b.screen_id=s.screen_id
WHERE s.screen_id='edit_XXX' GROUP BY s.screen_id, s.meta;

-- 2. Option save_values match RPC CASE branches
SELECT callback_data, meta->>'save_value' AS save_value
FROM ui_screen_buttons WHERE screen_id='edit_XXX' ORDER BY row_index;

-- 3. Render returns is_current correctly
-- (set user's column to one of the options first)
UPDATE users SET XXX_column='option1' WHERE telegram_id=<test_tg>;
SELECT render_screen(<test_tg>, 'edit_XXX');  -- option1 button should have is_current=true

-- 4. Setter end-to-end through process_user_input
UPDATE users SET status='edit_XXX' WHERE telegram_id=<test_tg>;
SELECT process_user_input(<test_tg>, 'callback',
    '{"callback_data":"cmd_select_option1"}'::jsonb);
-- Expected: screen_id=<parent>, success_reaction='👌', users.XXX_column='option1'

-- 5. Latency benchmark (p95 < 300ms target)
-- 10 runs of render_screen(<test_tg>, 'edit_XXX')
```

## Связанные KB концепты

- [[headless-architecture]] — базовая архитектура ui_screens/workflow_states/nav_stack
- [[headless-template-substitution]] — Dumb Renderer multi-pass {var}/{{const}}/{tr:path} interpolation
- [[edit-picker-dual-render]] — Session 9 legacy pattern для Profile edit в 04_Menu (pre-Headless)
- [[nav-stack-architecture]] — push_nav / back_nav / peek_nav
- [[n8n-multi-agent-workflow-editing]] — fresh GET перед PUT + deactivate/activate

## Applied migrations (reference)

### Session 10 (migrations 110-120) — TOTAL

**Migrations 110-115** (daily/2026-04-21): 9 pickers seed + process_user_input ext, setter RPCs, send_new fallback, checkmark logic + unique icons + post-save nav, top-level nav + emoji strip, goal_speed reset + skip visibility + checkmark revert. 2 n8n PUTs: Dispatcher Route Classifier v1.9 + Dumb Renderer checkmark prefix.

**Migrations 116-120** (daily/2026-04-22, Session 10 final):
- **116:** Dispatcher PUT — picker callbacks всегда → menu_v3 без `user.status` guard. Timezone `UTCSG0002:00` → `UTC+02:00` fix. Revert Dumb Renderer 👌 на `delete_and_send_new`.
- **117:** `cmd_back` priority = `back_screen_id_default` FIRST (hierarchy), затем `nav_stack` fallback. Notif options unique icons (🧘/⚖️/🔥). CLAUDE.md safeguard для webhook.
- **118:** Убрана `success_reaction` эмиссия для callback saves (нет пользовательского сообщения для реакции). Stripped `{pct}%` literal из `profile.speed_deficit/surplus`.
- **119:** `cmd_select_none` ("Нет тренировок") → отдельное real value; `set_user_training_type` расширен. Country/timezone triggers unhidden. `cmd_back` hidden в онбординге на всех `edit_*` экранах.
- **120:** `edit_country`/`edit_timezone` → inline_kb 2-button entry screen (📍 Auto / 📋 Выбрать список). Translations × 13. Dispatcher Route Classifier: `cmd_auto_location`/`cmd_list_countries`/`cmd_list_timezones` → legacy 05_Location workflow.

**Session 10 TOTAL итог:**
- 11 миграций (110-120) + 5+ n8n PUTs + 5 KB concepts + Dispatcher v1.10 + CLAUDE.md webhook safeguard
- Latency: median p95 = 105ms, max 161ms, 0 screens > 500ms

**9 Profile v5 inline pickers — live & tested:**
| Picker | Статус |
|--------|--------|
| edit_goal | ✓ live |
| edit_activity | ✓ live |
| edit_training (+`none` real option) | ✓ live |
| edit_speed | ✓ live |
| edit_gender | ✓ live |
| edit_lang | ✓ live |
| edit_notifications_mode | ✓ live |
| edit_country | ✓ 2-button entry (list via legacy 05_Location) |
| edit_timezone | ✓ 2-button entry (list via legacy 05_Location) |

### edit_country / edit_timezone — 2-button entry pattern (migration 120)

Вместо прямого рендеринга длинного списка стран/таймзон в Dumb Renderer (нет поддержки `list_rpc` — dynamic list deferred) — промежуточный экран с 2 кнопками:

```
📍 Авто (по IP) → cmd_auto_location → 05_Location
📋 Выбрать из списка → cmd_list_countries → 05_Location
```

Dispatch правило в Route Classifier (migration 120): `cmd_auto_location`, `cmd_list_countries`, `cmd_list_timezones` → маршрут в legacy 05_Location workflow.

### Session 11 — deferred items

1. **Reply-keyboard refresh после `set_user_language`** — stale keyboard при смене языка
2. **👋 wave emoji mystery** — источник неизвестен
3. **edit_phenotype multi-step 4Q quiz** — `render_strategy` CHECK constraint не включает `multi-step`. Требует либо ALTER TABLE constraint, либо отдельный workflow
4. **Dynamic list rendering в Dumb Renderer** — `list_rpc` expansion для country/timezone (сейчас роутится в legacy 05_Location)
5. **Dynamic pct в speed labels** — `{pct}%` stripped в migration 118, dynamic расчёт не реализован
6. **02_Onboarding_v3 → Headless migration (Phase 3B)**
7. **04_Menu legacy decommission (Phase 3B)**

---

## edit_diet — паттерн «screen built, entry never wired» (mig 425, 2026-06-02)

**Ловушка для следующего агента:** прежде чем строить «новый» picker — `grep` живой БД.
Часто экран + опции + setter RPC + переводы УЖЕ существуют от предыдущей миграции,
а не подключена только **кнопка-вход**.

Кейс diet_type: mig 291 (DIAAS protein multiplier) создала `edit_diet` (3 опции
`cmd_diet_*` + Back, `save_rpc=set_user_diet_type` который сам зовёт
`calculate_user_targets(.., TRUE)`), переводы `questions.diet_question`/`answers.diet_*`
×13 и `profile.diet_label` — но `ui_screen_buttons` нигде не содержал кнопки с
`meta.target_screen='edit_diet'`. Экран был недостижим. Задача «вывести тип питания
в меню» свелась к **1 кнопке + 4 строкам роутера**, а не к постройке с нуля.

**Чек перед постройкой нового edit-экрана:**
```sql
-- экран уже есть?
SELECT screen_id, meta FROM ui_screens WHERE screen_id ILIKE '%<feature>%';
-- кнопка-вход уже есть? (если пусто — экран висит в воздухе)
SELECT screen_id, callback_data FROM ui_screen_buttons WHERE meta->>'target_screen' = '<screen>';
-- setter RPC уже есть и зовёт ли пересчёт?
SELECT pg_get_functiondef('public.set_user_<feature>'::regproc);  -- ищи calculate_user_targets
```

**Что нужно для подключения висящего picker-экрана (минимум):**
1. **`workflow_states` строка** `<screen>` — ОБЯЗАТЕЛЬНА, иначе `set_status='<screen>'`
   падает по FK `users.status → workflow_states.state_code` (23503). edit_diet её не имел
   (в отличие от edit_training), хотя экран был.
2. **Кнопка-вход** на родителе: `callback_data=cmd_edit_<x>`, `meta={set_status:'<screen>', target_screen:'<screen>'}`, `icon_const_key`, `text_key`.
3. **Лейбл ×13** (deep-merge `jsonb_set(content,'{buttons}', COALESCE(...)||jsonb_build_object(...), true)` — sibling-safe). Tip: если есть готовая отревьюенная метка-поле (`profile.<x>_label`), переиспользуй её минус двоеточие — кнопка читается как поле, новой L1 не требует.
4. **Router (Python, cutover global)** — 4 точки:
   - `<screen>` → `BUTTON_ONLY_STATUSES` (inline-only, текст не в AI) + `PROFILE_V5_STATUSES` (picker-saves роутятся в menu_v3);
   - `cmd_edit_<x>` → `PROFILE_V5_CALLBACKS` (entry routes to menu_v3);
   - `cmd_<x>_` → `PROFILE_V5_PICKER_PREFIXES` (option saves).
   - **Коллизия-гард:** если тот же `cmd_<x>_` префикс используется в онбординге (напр.
     `cmd_diet_*` в `registration_step_diet`), убедись что онбординг-статус ∈ `ONBOARDING_STATUSES`
     — picker-секция 4b стоит на `status not in ONBOARDING_STATUSES`, так что онбординг не перехватится. Verified mig 425.

**edit_diet live (2026-06-02):** routing 4/4, omnivore 139г→vegan 174г белка (×1.25),
✅ через `current_value_col=diet_type`, p95 VPS render 41ms / set+recalc 48ms. PR #288.

### ⚠️ Setter-RPC контракт: парсь callback, не жди save_value (mig 429, 2026-06-02)

**P1 bug, скрытый 1 день после mig 425.** `process_user_input` save_via_callback
dispatch (≈стр.331) передаёт сеттер-RPC **сырой `callback_data`**, НЕ `save_value`:
```sql
EXECUTE format('SELECT public.%I($1,$2)', save_rpc) USING p_telegram_id, v_callback;
```
→ `set_user_diet_type(tid, 'cmd_diet_vegetarian')`. Поэтому КАЖДЫЙ рабочий сеттер
(`set_user_training_type`, `set_user_goal`, …) внутри парсит префикс `cmd_*`:
```sql
v_value := CASE
    WHEN p_input = 'cmd_select_strength' THEN 'strength'
    WHEN p_input IN ('strength','cardio',...) THEN p_input  -- backward-compat
    ...
```
`set_user_diet_type` (mig 291) был написан как `IN ('omnivore','vegetarian','vegan')`
БЕЗ парсинга — `'cmd_diet_vegetarian'` → `INVALID_DIET_TYPE`, **UPDATE не выполнялся**.
Симптом коварен: навигация (`clear_status`/`target_screen`) применяется **независимо
от успеха save** → юзер молча уезжает на parent-screen, галочка не двигается, нет
ошибки. Выглядит как «UI-баг рендера», а на деле save — тихий no-op.

**Почему не всплыло раньше:** онбординг-diet идёт через onboarding-handler
(`process_onboarding_input`), а не через `process_user_input` save_via_callback —
там значение извлекается иначе. RPC впервые вызвали этим dispatch'ем только когда
mig 425 подключила profile-кнопку `edit_diet`.

**Правило (durable):** новый picker-сеттер ОБЯЗАН принимать ОБЕ формы —
сырой `cmd_<prefix>_<value>` И чистое `<value>`:
```sql
v_normalized := LOWER(TRIM(p_value));
IF v_normalized LIKE 'cmd_<prefix>_%' THEN
    v_normalized := SUBSTRING(v_normalized FROM 'cmd_<prefix>_(.*)');
END IF;
-- затем валидация + UPDATE
```
**Тест-гейт:** проверять picker не прямым вызовом сеттера (`set_user_x(tid,'vegan')`
проходит!), а через `dispatch_with_render(tid,'callback',{callback_data:'cmd_<prefix>_x'},…)`
— только он воспроизводит реальный путь клика. Прямой вызов с чистым значением
ЗЕЛЁНЫЙ, а реальный клик — КРАСНЫЙ. Это и пропустила верификация mig 425.

### ⭐ PATTERN B — РЕКОМЕНДОВАННЫЙ ДЕФОЛТ для edit-pickers (owner-mandated 2026-06-02)

> **🟢 OWNER DIRECTIVE (2026-06-02):** «Вариант B теперь надо использовать как лучший,
> и чтобы другие агенты в своей работе принимали его». Pattern B = **дефолт** для
> ЛЮБОГО нового/правимого edit-picker'а (diet/training/goal/phenotype/activity/speed/…),
> НЕ опция. Owner протестировал на edit_diet вживую: «пересчитывает очень быстро белок
> и это наглядно для пользователя». Старый «save → navigate to parent» — legacy;
> при касании такого экрана **мигрируй его на B**, если нет причины обратного.
> Toast-вариант «A» (исчезающая плашка) — fallback только если live-число показать негде.

**Суть:** после выбора юзер ОСТАЁТСЯ на picker-экране, ✅ переезжает на новый выбор,
а строка с пересчитанным значением обновляется live (editMessageText in-place).
Нагляднее исчезающего toast — видно само число и его сдвиг. Latency пересчёта быстрый
(set_*+recalc p95 ~48ms VPS).

**Рецепт (data-only, без Python):**
1. **Опции-кнопки:** `target_screen=<self_screen>` + УБРАТЬ `clear_status`
   (статус остаётся в edit-режиме → picker продолжает ловить клики). `push_nav`
   НЕ задублирует nav_stack: `process_user_input` пушит только если
   `next_screen IS DISTINCT FROM current_screen` (стр.~460).
2. **Свой text_key** (НЕ shared с онбордингом!) с плейсхолдером результата, напр.
   `📊 Белок: {target_protein_g} г/день`.
3. **`ui_screens.business_data_rpc`** = RPC(telegram_id)→jsonb, отдающий нужные
   поля. render_screen мёржит их в `template_vars` (`base_vars || business_data`,
   render_screen SQL стр.~110); `template_engine._resolve_text` подставляет
   `{placeholder}` Python-side. Reuse существующего (напр. `get_my_plan_business_data`).
4. **Back-кнопка** не трогается: nav-pop сам уводит на экран-родитель (откуда вошли).

**Gotcha:** значение из modifier-aware RPC (get_my_plan_business_data, mig 424)
показывает реальную дневную цель С модификаторами (sleep/stress/luteal), не «голую»
базу из `users.target_*`. Обычно это и нужно (что юзер реально ест), но помни о
расхождении с голым числом.

**Тест:** только через `dispatch_with_render` + прогон `template_engine._resolve_text`
с живыми translations — увидеть ФИНАЛЬНЫЙ текст. render_screen отдаёт text_key +
template_vars (подстановка Python-side), сырой payload показывает плейсхолдер, а не число.

### ⛔ ПЕРЕСМОТР (mig 442, 2026-06-03): числовой text-input → ВОЗВРАТ НА HUB, НЕ stay

> **Owner-тест 2026-06-03 отменил Pattern-B-stay для числового text-input.** Stay
> для числа = **ловушка «спрашивает дважды»**: после ввода экран ре-рендерит
> инструкцию-промпт (`questions.waist_question_edit` — «Окружность талии в см.
> Измеряем...») → выглядит как повторный запрос числа; любой следующий текст
> («sdlfksdf») ловится как талия → ошибка not_a_number. Выйти можно только
> [Назад]. Для ПИКЕРА stay хорош (выбор кнопкой остаётся, ✅ переезжает), для
> ЧИСЛА — нет (re-prompt + нельзя выйти текстом).
>
> **Канон для числового text-input (вес/рост/возраст/талия):** вести себя как
> вес/рост/возраст — после ввода **возврат на hub** (`personal_metrics`), recalc
> показать в **тосте**, не in-place. Owner approved (mockup→AskUserQuestion).
>
> **3 провода (mig 442 на edit_waist):**
> 1. `workflow_states.<edit_status>.next_step_code = 'registered'` (НЕ self-loop).
>    `process_user_input` text-path (стр.441) перезаписывает status на это значение
>    даже если сеттер сам не advance — **сеттер можно не трогать** (важно если он
>    общий с онбордингом, как `set_user_waist_circumference`: онбординг гонит FSM
>    через `process_onboarding_input`, меню — через dispatcher next_step_code).
> 2. `ui_screens.<screen>`: `next_on_submit` / `parent_screen_id` /
>    `back_screen_id_default` → `personal_metrics` (hub). После status=registered
>    (registered.screen_id=NULL) dispatcher берёт экран из `next_on_submit`.
>    personal_metrics имеет `meta.reply_kb_entry=true` → reply-kb приезжает от
>    рендера хаба бесплатно (делает reply-kb-костыли тоста для этого поля
>    избыточными — append-спецслучай убирается, единый prepend как у веса).
> 3. **Recalc в тост** (сохранить наглядность, ради которой держали stay): свой
>    ключ с плейсхолдерами `messages.<x>_saved` ×13 (напр. `✅ Талия: {waist} см ·
>    Белок: {protein} г/день`). Python `_maybe_build_save_toast` строит для этого
>    статуса спец-текст: waist из `decision.text` (нормализ.), protein из
>    `get_my_plan_business_data` (1 RPC на редком save-пути). Кнопка
>    `[<поле>: <новое> ]` на хабе = доп.подтверждение.
>
> **Онбординг-шаг того же поля (registration_step_waist)** НЕ трогается этим — он
> advance'ит FSM сам (`process_onboarding_input` → следующий шаг), ловушки нет.
>
> **Durable:** числовой text-input ≠ picker. Pattern-B-stay остаётся дефолтом
> для ПИКЕРОВ (кнопки). Для числа — return-to-hub + recalc-тост.

---

### Pattern B для TEXT-INPUT — ИСХОДНАЯ версия (edit_waist, mig 438, 2026-06-02) — ОТМЕНЕНА mig 442 ↑

> ⚠️ Описание ниже — историческое (как было до mig 442). Stay для числа породил
> баг «спрашивает дважды». НЕ применять для числовых полей; см. ПЕРЕСМОТР выше.

Pattern B изначально для **picker'ов** (кнопки + save_via_callback, target_screen=self). Для **text-input** edit-экранов (юзер вводит число: талия/вес/рост) механика «stay + live recalc» другая — навигацией после сохранения рулит не `button.meta.target_screen`, а **`workflow_states[status].next_step_code`** (process_user_input text-path, стр.~441):

1. **Stay:** `workflow_states.<edit_status>.next_step_code = '<edit_status>'` (само-петля) + **сеттер НЕ advance статус** (`v_next_status := v_current_status`). После ввода status остаётся в edit-режиме → re-render того же экрана с пересчётом. (Если сеттер пишет 'registered' И next_step_code='registered' — будет прыжок в родителя = старый UX.)
2. **Live recalc-строка:** `business_data_rpc=get_my_plan_business_data` + `text_key` с `{target_protein_g}`/`{target_calories}`. Reuse Sage-тон: `waist_question_edit = waist_question || E'\n\n' || split_part(diet_question_edit, E'\n\n', 2)` — не нужна новая L1-копия.
3. **[Назад] ОБЯЗАТЕЛЬНА** (на text-input экране её часто забывают — у edit_waist было 0 кнопок!): `cmd_back`, `meta={clear_status:true, target_screen:'<родитель>'}`. Без неё передумавший юзер заперт в text-input (любой текст уходит в сеттер).

**Durable урок (owner 2026-06-02):** text-input edit-экран = picker по части UX. ВСЕГДА: (а) кнопка [Назад] с clear_status; (б) Pattern B stay (next_step_code=self + setter no-advance) + live recalc-строка; (в) проверять e2e через `dispatch_with_render` (клик→ввод→Назад), а не только сеттер. edit_waist (mig 438) — канонический пример.
