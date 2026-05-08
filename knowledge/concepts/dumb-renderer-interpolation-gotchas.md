# Dumb Renderer Interpolation — Gotchas

> **Статус:** активный паттерн, compiled 2026-04-23 (Session 11, Migration 124 bug-fix). Дополняет [[headless-template-substitution]] (общий паттерн) 2 подводными камнями, выявленными на живом production.
>
> **Контекст:** Session 11 migration 124 (Stats Headless rewrite) прошла 2 инцидента из-за недопонимания механики Dumb Renderer. Эта статья — "пост-маркет" observations для следующих headless экранов (Phase 3A/B).

---

## Gotcha 1 — `{var}` pass работает ВНЕ multi-pass цикла

### Что реально делает `interpolate()` в 04_Menu_v3

```javascript
function interpolate(text, tplVars) {
    if (!text) return '';
    let prev, iter = 0;
    do {                                                    // ← ЦИКЛ (до 5 итераций)
        prev = text;
        text = text.replace(/\{tr:([\w.{}]+)\}/g, ...);    // {tr:path} — internal loop
        text = text.replace(/\{\{([\w{}]+)\}\}/g, ...);    // {{const}} — internal loop
        iter++;
    } while (text !== prev && iter < 5);
    // Final pass — ВНЕ loop, выполняется ОДИН раз:
    text = text.replace(/\{(\w+)\}/g, (m, key) =>
        tplVars[key] != null ? String(tplVars[key]) : ''
    );
    return text;
}
```

### Следствие

**`{tr:...}` и `{{...}}` внутри цикла ре-обрабатываются** — поэтому nested `{{goal_{goal_type}}}` резолвится за 2 прохода (сначала `{goal_type}` → `lose`, потом `{{goal_lose}}` → 📉). Это работает.

**НО `{var}` pass выполняется ОДИН раз, в конце, после выхода из цикла.** Значит:

- Если `{meals_list_formatted}` в `tplVars` содержит `"1. 08:08 — Оладушки (320 {tr:report.unit_kcal})"`,
- то `{var}` pass подставит эту строку в текст **целиком, включая литерал `{tr:report.unit_kcal}`**,
- а следующего прохода `{tr:...}` больше не будет — цикл уже завершился.

**Результат: юзер видит `"(320 {tr:report.unit_kcal})"` literal.**

### Почему это by design (likely)

`{var}` интерполяция — «terminal» операция по контракту: RPC подготовил готовые значения, Dumb Renderer их механически подставляет. Разрешить `{tr:...}` и `{{...}}` внутри `{var}` substitution'а означало бы неограниченные passes (template inside template inside template) и потенциальный infinite loop.

Safety first — final pass один.

### Fix pattern: eager resolve в RPC

Когда `{var}` содержит composite-строку с встроенными плейсхолдерами, **RPC должен резолвить их заранее** через lookup в `ui_translations` / `app_constants` по user's `language_code`:

```sql
-- ВМЕСТО:
v_meals_list := string_agg('... (320 {tr:report.unit_kcal})', E'\n');   -- ❌ literal в UI

-- ДЕЛАЙ:
SELECT language_code INTO v_lang FROM users WHERE telegram_id = p_telegram_id;
SELECT content->'report'->>'unit_kcal' INTO v_unit_kcal
  FROM ui_translations WHERE lang_code = v_lang;
IF v_unit_kcal IS NULL THEN
    SELECT content->'report'->>'unit_kcal' INTO v_unit_kcal
      FROM ui_translations WHERE lang_code = 'en';   -- fallback
END IF;
IF v_unit_kcal IS NULL THEN
    RAISE EXCEPTION 'ui_translations missing report.unit_kcal for lang=% (no en fallback either)', v_lang;
END IF;

v_meals_list := string_agg('... (320 ' || v_unit_kcal || ')', E'\n');   -- ✅ "ккал" в UI
```

Правила:
1. **Всегда fallback на `'en'`** — если целевой language не имеет ключа. English считается universal base.
2. **RAISE EXCEPTION если и en нет** — fail-fast, а не silent empty string. (User's rule: "хардкоды запрещены" → не использовать hardcoded fallback "kcal").
3. **Cache в DECLARE scope функции** — один lookup на один call RPC, реюзать v_unit_kcal для всех composite строк.

### Когда применять

- `meals_list_formatted` (composite string из meals × unit + separator)
- `food_log_result` items (когда `{N. item (X ккал)}` собирается как одна строка)
- Любые pre-formatted list inside `{var}` placeholder'а
- `daily_insight` если строится как composite

### Когда НЕ нужно

- Top-level usage: template напрямую содержит `{tr:report.unit_kcal}` как отдельный placeholder — резолвится в цикле. Проблема ТОЛЬКО когда вложен в composite `{var}`.

---

## Gotcha 2 — `render_screen` оборачивает business_data в `template_vars`

### Что делает render_screen

Без прямого чтения кода `render_screen` PL/pgSQL можно увидеть эффект через:

```python
cur.execute("SELECT render_screen(417002669, 'stats_main')")
result = cur.fetchone()[0]
print(result['telegram_ui']['template_vars'].keys())
# → ['language', 'level', 'mana', 'meals', 'name', 'nomscoins', 'stats',
#    'telegram_id', 'template_vars', 'xp', 'first_name', 'calories_consumed', ...]
```

`render_screen`:
1. Читает `v_user_context` fields (language, level, mana, name, ...)
2. Вызывает `business_data_rpc(telegram_id)`
3. **MERGES оба объекта в один flat dict** и помещает под `telegram_ui.template_vars`

### Anti-pattern который ломает UI

Если RPC возвращает:

```sql
-- ❌ WRONG: оборачивает в template_vars key
RETURN jsonb_build_object(
    'template_vars', jsonb_build_object('calories_consumed', 1190, 'percent', 48),
    'meals', ...
);
```

То после merge получится:

```jsonc
"telegram_ui": {
  "template_vars": {
    "language": "ru",  // from v_user_context
    "level": 20,
    "template_vars": { "calories_consumed": 1190, "percent": 48 }  // ← DOUBLE NEST
  }
}
```

Dumb Renderer ищет `{calories_consumed}` на top-level `tplVars` — не находит → пустая строка в UI. Симптом: "🔥  /  ккал" вместо "🔥 1190/2483 ккал".

### Fix: business_data FLAT top-level

```sql
-- ✅ RIGHT: все template placeholders на top-level, никакой обёртки
RETURN jsonb_build_object(
    -- Flat placeholders (для Dumb Renderer {var} substitution)
    'calories_consumed', 1190,
    'calories_target',   2483,
    'percent',           48,
    'progress_bar',      '▓▓▓▓▓░░░░░',
    'p', 47, 'f', 54, 'c', 142,
    'p_status', '⚠️', 'f_status', '✅', 'c_status', '✅',
    'current_date', '23.04.2026',
    'current_time', '16:29',
    -- Вспомогательные business-data поля (для TMA / debug — не используются template)
    'stats',   v_ds->'stats',
    'meals',   v_ds->'meals',
    'targets', jsonb_build_object('calories', 2483, ...)
);
```

`render_screen` смержит всё это с `v_user_context` под `telegram_ui.template_vars` — все placeholder-ы flat-accessible.

### Verification pattern (для DO-блока в migration)

```sql
DO $verify$
DECLARE
    v_bd JSONB;
    v_render JSONB;
BEGIN
    -- Direct RPC: не должно быть `template_vars` key
    v_bd := public.get_daily_stats_rpc(417002669);
    IF v_bd ? 'template_vars' THEN
        RAISE EXCEPTION 'business_data must NOT contain template_vars key (render_screen wraps itself)';
    END IF;

    -- render_screen: template_vars flat + требуемые ключи доступны top-level
    v_render := public.render_screen(417002669, 'stats_main');
    IF v_render->'telegram_ui'->'template_vars' ? 'template_vars' THEN
        RAISE EXCEPTION 'render_screen produced nested template_vars.template_vars (double-nest bug)';
    END IF;
    IF v_render->'telegram_ui'->'template_vars'->>'calories_consumed' IS NULL THEN
        RAISE EXCEPTION 'calories_consumed not flat in telegram_ui.template_vars';
    END IF;
END $verify$;
```

Эта verification должна быть в **каждой headless миграции** — ловит double-nest bug до выхода в продакшн.

---

---

## Gotcha 3 — `jsonb_set` не создаёт промежуточные JSONB ключи

> **Контекст:** Session 14, migration 135 (friends_info headless). Новая секция `friends_info` отсутствовала в `ui_translations.content`. Все 13 языков вернули `NULL` для `main_text`.

### Что происходит

```sql
-- ❌ НЕВЕРНО: если 'friends_info' ключ не существует в content — jsonb_set тихо провалится
UPDATE ui_translations
  SET content = jsonb_set(content, '{friends_info,main_text}', to_jsonb(tmpl_text), true)
  WHERE lang_code = v_lang;
-- Результат: content остался без friends_info.main_text (NULL при SELECT)
```

`jsonb_set` с `create_missing=true` создаёт только ПОСЛЕДНИЙ компонент пути, если его нет. Промежуточные узлы (`friends_info` в данном случае) **уже должны существовать**.

Если `friends_info` отсутствует → `jsonb_set` silently no-ops или создаёт только terminal key на несуществующем пути — результат непредсказуем.

### Fix pattern: top-level merge

```sql
-- ✅ ВЕРНО: явно строить весь объект секции и мержить на top-level
UPDATE ui_translations
  SET content = content || jsonb_build_object(
    'friends_info',
    jsonb_build_object('main_text', tmpl_text)
    -- если секция частично существует и нужно сохранить другие ключи:
    -- jsonb_build_object('main_text', tmpl_text) || COALESCE(content->'friends_info', '{}'::jsonb)
  )
  WHERE lang_code = v_lang;
```

### Когда применять

- Любая новая секция в `ui_translations` (раньше секция не существовала ни в одной строке)
- Любая новая sub-key в существующей секции, где нет гарантии что parent key уже есть у всех langs

### Диагностика

```sql
-- Проверить: есть ли секция у нужных языков
SELECT lang_code, content ? 'friends_info' AS has_section,
       content->'friends_info'->>'main_text' AS main_text
FROM ui_translations
WHERE lang_code IN ('ru', 'en', 'de')
ORDER BY lang_code;
```

### Связь с другими готчами

- Это не проблема Dumb Renderer — проблема при записи в БД (миграция), не при чтении/рендере.
- Контрастирует с Gotcha 2 (RPC wrapping): обе возникают при работе с JSONB, но на разных уровнях.

---

## Рекомендованный discovery step перед написанием RPC

**Перед генерацией ТЗ для external AI** — сними snapshot существующего headless RPC (profile_main) и посмотри **фактический shape**:

```python
cur.execute("SELECT render_screen(417002669, 'profile_main')")
result = cur.fetchone()[0]
print("telegram_ui.template_vars keys:", list(result['telegram_ui']['template_vars'].keys())[:30])
print("nested? template_vars in template_vars:", 'template_vars' in result['telegram_ui']['template_vars'])
```

Если `nested=False` и все бизнес-поля на top-level — **новая RPC должна давать такой же shape** (flat).

---

## Lessons из Session 11

- **Migration 122** (первая попытка stats headless): RPC обернул в `template_vars` → double-nest → все `{var}` empty → user увидел "🔥  /  ккал" вместо чисел.
- **Migration 124 (fix #1):** убрал обёртку → flat top-level → числа рендерятся.
- **Migration 124 (fix #2):** `{meals_list_formatted}` содержал `{tr:report.unit_kcal}` → `{var}` pass выполнился ПОСЛЕ цикла → литерал в UI → RPC теперь резолвит unit_kcal eagerly per user language.
- **Verification DO-block** в migration 124 — теперь template для всех будущих headless миграций. RAISE EXCEPTION на nested + missing keys.

---

## Related KB

- [[headless-template-substitution]] — общий паттерн interpolate() (multi-pass, nested braces). **Читай первым.**
- [[headless-architecture]] — process_user_input + render_screen pipeline, business_data contract.
- [[pre-migration-discovery-recipe]] — Phase 0 discovery (включает проверку RPC signature + схемы).
- [[specs-vs-reality-ground-truth]] — правило "RPC body grep > specs > memory".
- [[profile-v5-screens-specs]] §25 — stats_main spec с post-Session-11 updates.

---

## Rule summary

1. **`{var}` substitution — terminal.** Не может содержать `{tr:...}` или `{{...}}` внутри своего значения. Если нужно — RPC резолвит per user language заранее.
2. **RPC возвращает FLAT top-level.** Никакого `template_vars` ключа-обёртки. `render_screen` сам обернёт.
3. **Verification DO-блок** с двумя проверками: `NOT ? 'template_vars'` (RPC output) + `NOT ? 'template_vars'` на уровне `telegram_ui.template_vars` (render_screen output).
4. **`jsonb_set` не создаёт промежуточные ключи.** При добавлении новой секции в `ui_translations` — использовать `content || jsonb_build_object('section', jsonb_build_object('key', val))` вместо `jsonb_set(content, '{section,key}', val, true)`.
