# Checkmark Prefix Pattern — ✅ на текущем выборе

**Компилировано:** 2026-04-21 Session 10. User explicitly requested: "Эмодзи галочка должна как бы приклеиваться к тем эмодзи который так уже есть в нашей собранной кнопке". Это критический UX pattern — single source of truth в `profile-v5-screens-specs.md`.

## Что это

На любом picker-экране (inline_kb с выбором опции) — кнопка, соответствующая **текущему значению user's column**, должна рендериться с префиксом `✅` перед оригинальной иконкой.

**Example edit_goal для user с goal_type='gain':**
```
[ 📉 Похудение ]
[ ⚖️ Удержание ]
[ ✅ 📈 Набор ]    ← current, check prepended
[ ⬅ Назад ]
```

**НЕ:** `[ ✅ Набор ]` (icon replaced). Оригинальный `📈` должен сохраниться.

## Архитектура (split concerns)

### Layer 1: DB (render_screen RPC)
Responsibility: **detect current value + flag it**.

- `ui_screens.meta.current_value_col` = имя колонки users для сравнения (e.g. `'goal_type'`)
- `ui_screen_buttons.meta.save_value` = значение, которое эта кнопка сохраняет (e.g. `'gain'`)
- render_screen LOOP: для каждой кнопки извлекает `users.<current_value_col>` через `EXECUTE format('SELECT ($1.%I)::text', col) USING v_user`. Compares с `button.meta.save_value`. If equal → `is_current=true`.

**НЕ мутирует icon_const_key** — возвращает original + flag.

```sql
-- Pseudo-code (migration 115 Block C final state):
v_is_current := FALSE;
IF v_screen.meta ? 'current_value_col' AND v_button.meta ? 'save_value' THEN
    v_current_col := v_screen.meta->>'current_value_col';
    v_button_val := v_button.meta->>'save_value';
    EXECUTE format('SELECT ($1.%I)::text', v_current_col)
        INTO v_user_current_val USING v_user;
    v_is_current := (v_user_current_val IS NOT NULL AND v_user_current_val = v_button_val);
END IF;

-- Return button with ORIGINAL icon + is_current flag
v_current_row := v_current_row || jsonb_build_array(
    jsonb_build_object(
        'text_key', v_button.text_key,
        'callback_data', v_cb_final,
        'icon_const_key', v_button.icon_const_key,  -- keep original
        'is_current', v_is_current                   -- flag only
    )
);
```

### Layer 2: Frontend (04_Menu_v3 Dumb Renderer JS)
Responsibility: **render checkmark prefix**.

Dumb Renderer обычный порядок при композиции button text:
```javascript
let btnText = lookupKey(translations, btn.text_key) || btn.text_key;  // label
if (btn.icon_const_key && constants[btn.icon_const_key]) {
    btnText = constants[btn.icon_const_key] + ' ' + btnText;          // + icon prefix
}
// Session 10 addition:
if (btn.is_current && constants.icon_check) {
    btnText = constants.icon_check + ' ' + btnText;                    // + checkmark (outermost)
}
```

**Порядок prefix'ов (outer → inner):**
1. `✅` (check — только если is_current)
2. `📉` / `🏋` / etc. (icon_const_key)
3. `Похудение` / `Силовые` / etc. (label из translations)

Final: `✅ 🏋 Силовые` for current training_type.

## Wiring для нового picker

### Step 1 — ui_screens.meta
```sql
UPDATE ui_screens SET meta = COALESCE(meta,'{}'::jsonb) || jsonb_build_object(
    'current_value_col', 'users_column_name'
) WHERE screen_id = 'edit_XXX';
```

Valid column names — must exist в users table. Types: text, bigint, etc. render_screen casts to text for comparison.

### Step 2 — ui_screen_buttons.meta.save_value per option
```sql
UPDATE ui_screen_buttons SET meta = COALESCE(meta,'{}'::jsonb) || jsonb_build_object(
    'save_value', '<value>'
) WHERE screen_id='edit_XXX' AND callback_data='cmd_select_option1';
-- repeat per option
```

`save_value` = exact string value that ends up в users.<col> after RPC save. E.g.:
- cmd_select_lose → save_value='lose' (set_user_goal writes 'lose')
- cmd_speed_slow → save_value='slow'
- cmd_lang_en → save_value='en'

### Step 3 — app_constants.icon_check
```sql
INSERT INTO app_constants (key, value) VALUES ('icon_check', '✅')
ON CONFLICT (key) DO NOTHING;
```

Сделано в Session 10 migration 113.

### Step 4 — Dumb Renderer PUT (04_Menu_v3)
Add block between icon_const_key prefix и `if (btn.callback_data === 'cmd_open_support_url')`:

```javascript
if (btn.is_current && constants.icon_check) {
    btnText = constants.icon_check + ' ' + btnText;
}
```

PUT via n8n API with fresh GET. deactivate + activate для cache refresh per CLAUDE.md Rule #10.

## Verification

```sql
-- User with goal_type='gain':
UPDATE users SET goal_type='gain' WHERE telegram_id=<tg>;

-- render_screen returns:
SELECT render_screen(<tg>, 'edit_goal');
-- Expected: keyboard row для cmd_select_gain имеет is_current=true,
-- icon_const_key='icon_goal_gain' (unchanged)
```

Finally — visual test через Telegram: открыть edit_goal, видеть `✅ 📈 Набор` на текущем goal.

## Anti-patterns (НЕ делай)

### ❌ Replace icon_const_key at render_screen level
Migration 113 initial attempt (reverted в 115):
```sql
-- DON'T:
v_final_icon_const := v_button.icon_const_key;
IF v_is_current THEN v_final_icon_const := 'icon_check'; END IF;
```

Проблема: teряется оригинальная иконка. User видит `✅ Набор` вместо `✅ 📈 Набор`. Нарушает "icon tells you what option it is" семантику.

### ❌ Hardcode emoji в translation value
```
answers.goal_gain = "📈 Набор"  -- NO
```

Emoji должен быть в `icon_const_key` via `app_constants`. Иначе Dumb Renderer + raw emoji → double emoji (`📈 📈 Набор` bug).

### ❌ Переключать save_value динамически в RPC
`save_value` в button.meta — static. Если саme RPC парсит multiple callback variants (e.g. `cmd_select_strength` AND `cmd_select_training_skip` → training_type='mixed'), в button.meta для обеих кнопок ставь `save_value='mixed'`. Visual consequence: обе кнопки покажут checkmark when user training_type='mixed'. Session 10 known issue для `cmd_select_training_skip` — defer.

### ❌ Hardcode icon_check key name
```javascript
if (btn.is_current) {
    btnText = '✅ ' + btnText;  // NO
}
```

Должно быть `constants.icon_check`. Если в будущем icon поменяется в `app_constants` — Dumb Renderer не увидит изменение.

## Business logic rules

### Rule 1: checkmark = observed current, not "locked-in"
User often interprets `✅` as "это уже выбрано и сохранено". **Это correct** — checkmark показывает actual `users.<col>` value.

Если user нажимает новую опцию — save immediately, checkmark переезжает. Atomic save per click.

### Rule 2: one option at a time (radio group)
Никогда multiple buttons с is_current=true одновременно (unless save_value collision, e.g. Session 10 training_skip=mixed).

### Rule 3: visible_condition works alongside
Button может быть hidden (через `visible_condition` — see training_skip example) но сохранять `save_value` + `meta`. render_screen skip'нет hidden buttons при iteration → не рендерит checkmark на ни.

## Session 10 applied state

**Screens с checkmark:**
- edit_goal (current_value_col='goal_type', options: lose/maintain/gain)
- edit_activity (activity_level: sedentary/light/moderate/heavy)
- edit_training (training_type: strength/cardio/mixed)
- edit_speed (goal_speed: slow/normal/fast)
- edit_gender (gender: male/female)
- edit_lang (language_code: 13 codes)
- edit_notifications_mode (notifications_mode: zen/balanced/beast)

**Skipped (dynamic_list — deferred Session 11):**
- edit_country
- edit_timezone

Dynamic list checkmark требует ещё одну логику — сравнение user.country_code с option's iso в list_rpc result. Not in scope Session 10.

## Связанные KB концепты

- [[headless-picker-pattern]] — полный recipe для picker creation
- [[headless-template-substitution]] — Dumb Renderer multi-pass interpolation
- [[edit-picker-dual-render]] — legacy chk*() pattern в pre-Headless 04_Menu (Session 9 era)

## Migration history

- Migration 113: initial checkmark via icon_const_key replace
- Migration 115 Block C: revert replace, keep original icon + is_current flag
- 04_Menu_v3 PUT 2026-04-21 18:53: Dumb Renderer prepend `✅` when is_current

Full changelog: `daily/2026-04-21.md` Session 10.
