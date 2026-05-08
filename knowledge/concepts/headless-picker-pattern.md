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
