# Python `services/template_engine.py` vs n8n Dumb Renderer — две грамматики, одно `ui_translations`

> **Статус:** активный паттерн, compiled 2026-05-02, обновлён 2026-05-04 (миграции 168-169 + рефактор `03_AI_Engine` Send error).
>
> **Зачем:** в проде одновременно живут **два разных шаблонизатора** для одного и того же `ui_translations` content. Они **несовместимы**. Глобальный `UPDATE ui_translations` сломает половину бота. Эта статья фиксирует разницу и правила миграции.
>
> **Дополняет:** [[headless-template-substitution]] (n8n grammar), [[dumb-renderer-interpolation-gotchas]] (n8n quirks).

---

## TL;DR — две сосуществующие грамматики

| Renderer | Грамматика | Какие экраны | Файл/нода |
|---|---|---|---|
| **Python (Phase 2)** | `{icon_x}` (одинарные) + `{tr:section.key}` без вложений + flat `{var}` | `target=menu_v3`, `target=onboarding_v3` (с 02.05) — handlers/menu_v3.py, handlers/onboarding_v3.py | `services/template_engine.py:_resolve_text` |
| **n8n Dumb Renderer** | `{{icon_x}}` (двойные) + `{tr:path.{var}}` (nested OK) + multi-pass loop | Всё остальное: `04_Menu`, `02.1_Location`, `03_AI_Engine`, `10_Payment`, etc. | JS Code node "Dumb Renderer" в каждом workflow |

Один и тот же ключ `ui_translations.content.<lang>.<screen>.main_text` рендерится **разным движком** в зависимости от того, через какой target юзер пришёл на экран.

---

## Чем именно отличаются грамматики

### 1. Скобки иконок

| Pattern | n8n рендерит | Python рендерит |
|---|---|---|
| `{{icon_stats}}` | `📊` ✅ | `{📊}` ❌ (внутренние `{ }` матчатся, внешние остаются литералом) |
| `{icon_stats}` | `{📊}` ❌ (n8n ищет `{{...}}`) | `📊` ✅ |

**Источник асимметрии — regex Python:**
```python
_VAR_PLACEHOLDER_RE = re.compile(r"\{([^{}:]+)\}")
```
Character class `[^{}:]` исключает `{` внутри placeholder — поэтому `{{icon}}` распадается на `{ + {icon} + }`, внутренний `{icon}` матчится и заменяется, внешние скобки остаются.

### 2. Вложенная интерполяция

| Pattern | n8n | Python |
|---|---|---|
| `{tr:profile.status_{subscription_status}}` | ✅ multi-pass loop резолвит за 2 итерации | ❌ Pass-1 (tr) ДО Pass-2 (var) — ищет ключ с буквальным `{subscription_status}` в пути |
| `{{goal_{goal_type}}}` | ✅ за 2 итерации | ❌ |

**Источник:** Python — два последовательных regex pass без цикла. n8n — `do { ... } while (text !== prev && iter < 5)`.

### 3. Композитные строки от RPC

Если RPC возвращает `meals_list_formatted` который содержит `{tr:report.unit_kcal}` внутри:
- n8n — оставит литерал `{tr:report.unit_kcal}` (final var-pass идёт **после** выхода из loop, см. [[dumb-renderer-interpolation-gotchas]]).
- Python — то же самое (Pass-1 уже отработал на основном шаблоне, в подставленной строке его уже не будет).

**Решение для обоих:** RPC должна резолвить `{tr:...}` ВНУТРИ композитных строк до их вставки (паттерн уже применён в `get_daily_stats_rpc` для `unit_kcal` / `no_meals_yet`).

---

## Почему так получилось

- **20.04 (миграции 100-101):** заложен flat-headless паттерн — `profile_main` через RPC `get_profile_business_data` + шаблон `profile.main_text`. Грамматика `{{...}}` + nested `{tr:...{var}...}` была выбрана под n8n Dumb Renderer (тогда единственный движок). Комментарий в [migrations/101_profile_main_text_headless_template.sql](../../../migrations/101_profile_main_text_headless_template.sql) явно ссылается на "n8n Dumb Renderer" как ground-truth.
- **28.04 (миграция 156, B-3 cutover):** Phase 2 cutover для `target=menu_v3` — Python `services/template_engine.py` стал основным renderer'ом для headless экранов профиля/stats/progress/quests/league/friends/shop. Но грамматика regex Python была реализована **строже** (одинарные скобки, нет multi-pass loop) — оптимизация под Two-pass семантику для предсказуемости.
- **01.05 (B-3 проде):** юзеры начали видеть `{📊}` и литералы `{tr:profile.status_premium}` на профиле/stats. Закрыто миграциями 162-164 (02.05, ветка `claude/ui-templates-fix`).

---

## Правила для агентов

### Перед массовым `UPDATE ui_translations` — определи renderer

Глобальный sweep `REPLACE(content::text, '{{', '{')` или массовая замена nested `{tr:...{var}...}` **сломает все экраны**, которые до сих пор обслуживаются n8n.

**Алгоритм определения renderer'а для конкретного ключа:**

1. Найди `screen_id` который использует ключ: `SELECT screen_id, business_data_rpc FROM ui_screens WHERE text_key = 'shop.main_text'`.
2. Найди какой `target` приводит на этот screen — обычно через `process_user_input` action types. Если screen открывается из `04_Menu` callback (cmd_*), target = `menu_v3` → **Python**. Если из payment/onboarding/location — обычно **n8n**.
3. Подтверди по `app_constants` флагу: `handler_<target>_use_python` (например `handler_menu_v3_use_python=true`, `handler_onboarding_use_python=true` — оба сейчас `true` на проде, 02.05).
4. Если screen рендерится через **Python** → fix по паттерну миграций 162-164 (см. ниже).
5. Если через **n8n** → НЕ ТРОГАТЬ, грамматика `{{...}}` + nested работает правильно.

### Паттерн миграции "n8n grammar → Python grammar" (для одного экрана)

1. **Identify все вложенные интерполяции** в шаблоне: `{tr:foo.bar_{var}}`, `{{prefix_{var}}}`, `{tr:{insight_key}}` итп.
2. **Перенеси резолвинг в RPC.** Добавь готовое flat-поле в return JSONB:
   - `_localized` суффикс для текстов (`status_localized`, `insight_localized`).
   - `_icon` суффикс для эмодзи из `app_constants` (`goal_icon`).
   - Lookup делай с fallback на 'en' (паттерн в [migrations/162_profile_main_v6_flat_template.sql](../../../migrations/162_profile_main_v6_flat_template.sql)).
   - Если перевод сам содержит `{var}` placeholder (как `profile.limit_logs_free` с `{limit}`) — REPLACE внутри RPC.
3. **Сохрани обратную совместимость:** старые поля (`insight_key`, `subscription_status`, `goal_type`) **оставь** в return JSONB — они нужны TMA / analytics.
4. **Перепиши шаблон:** `{{x}}` → `{x}`, вложенные `{tr:...{var}...}` → flat-переменная.
5. **Verification внутри миграции:** DO-блок проверяет regex'ом (`text LIKE '%{{%'`, `text ~ '\{tr:[^}]*\{'`) + smoke-вызов RPC с `tg_id=417002669` (admin).
6. **End-to-end render:** прогон `render_screen(admin, screen_id)` вручную через Python с симуляцией template_engine.py логики (см. рецепт в daily/2026-05-02.md).
7. **p95 bench:** 12 runs persistent psycopg2 conn с VPS (CLAUDE.md правило 7). Lookup'ы в RPC прибавляют ~1-2ms на каждый — в пределах нормы.

### Что НЕ делать

- ❌ Не делать глобальный sweep одной командой. Только point-fix по одному экрану.
- ❌ Не использовать `{tr:foo_{var}}` или `{{prefix_{var}}}` в новых шаблонах для **Python-обслуживаемых** экранов — Python это не понимает.
- ❌ Не удалять старые поля из RPC при добавлении `_localized` — TMA и аналитика читают raw enum'ы.
- ❌ Не путать `target=menu_v3` (Python) и любой другой target (n8n). Список Python-обслуживаемых targets: `dispatcher/forward.py:TARGET_TO_PATH`.

---

## Inventory оставшихся проблемных ключей (на 04.05)

| Дата | Закрыто | Осталось `{{...}}` leaf-ключей |
|---|---|---|
| 02.05 (миграции 162-164) | profile_main / stats_main / progress_main | ~34 |
| 04.05 (миграция 168) | shop.* (8 ключей), quests.main_text, league.info_text_full, referral.how_it_works_text — 11 ключей × 13 langs = **286 occurrences** `{{icon_*}}` устранено | ~23 |

Принцип ремонта: при cutover каждого следующего sub-workflow на Python (Add food / Payment / Location / AI Engine) — переписать его шаблоны по паттерну выше **в одной и той же миграции** что и Python-handler. Не отдельной волной.

**Важная находка миграции 168 (04.05):** sub-ключи, на которые ссылаются `{tr:simple.path}` (без переменной в path), **НЕ нужно править** — Python `_TR_PLACEHOLDER_RE` Pass 1 их корректно резолвит. Перед миграцией обязательна разведка: SELECT всех target-ключей + sub-ключей, поиск вложенных `{tr:foo_{var}}` (в 11 ключах Гамификации их 0 — спецификация задачи переоценила scope).

---

## Variant-массивы (Sassy Sage variation): APPEND ≠ REPLACE

> Добавлено 04.05 после миграции 169 + рефактор `03_AI_Engine` ноды Send error.

Часть ключей в `ui_translations` хранятся как **JSONB-массивы из 3+ вариантов** (anti-shaming variation Sassy Sage character). Текущий inventory:

- `errors.ai_failed` — 3 варианта (после 169 — `[Variant1, Variant2, Variant3]`)
- `errors.ai_not_food` — 3 варианта
- `errors.junk_content` — 3 варианта
- `errors.no_credits` — 3 варианта
- `wait.updating_variants` — 3 варианта

**Renderer выбирает случайный элемент** через random-pick (`arr[Math.floor(Math.random() * arr.length)]`), реализация в JS Code/Expression на стороне n8n или в Python handler.

### Правило APPEND vs REPLACE

Если задача звучит «добавить новый текст ошибки» / «обновить fallback message» — **сначала SELECT текущее значение** ключа и проверь `jsonb_typeof()`:

| Тип в БД | Что делать |
|---|---|
| `string` | OK заменить через `jsonb_set` с `to_jsonb(text)::jsonb` |
| `array` | **APPEND** новый элемент через `array || to_jsonb(...)` ИЛИ построить новый массив и `jsonb_set`; **НЕ перезаписывать** строкой — потеря variation = регрессия Sassy Sage |

### Грамматика для variant-массивов следует тому же правилу renderer-ownership

Миграция 169 (errors.ai_failed) **намеренно использовала `{{icon_brain}}` (n8n grammar)**, потому что нода `Send error` обслуживается **n8n** (`03_AI_Engine` legacy, не cutover на Python). Если бы Send error был Python-handler — нужны были бы одинарные `{icon_brain}`. Renderer-ownership определяется **владельцем экрана**, не БД-ключом.

### Pattern: random-pick + inline icon substitution в n8n Expression

Канонический snippet для `parameters.text` ноды-телеграма (см. `03_AI_Engine` Send error после refactor PR #9, 04.05):

```javascript
={{ (function(){
  const ctx = $('Execute Workflow Trigger 03').item.json || {};
  const lang = (ctx.language_code || 'en').toLowerCase();
  const trs = ctx.translations || {};
  const consts = ctx.constants || {};
  const arr = (trs[lang] && trs[lang].errors && trs[lang].errors.ai_failed)
           || (trs.en && trs.en.errors && trs.en.errors.ai_failed) || [];
  if (!Array.isArray(arr) || !arr.length) {
    return 'Хм, не получилось распознать. Попробуй ещё раз или напиши текстом.';
  }
  let txt = arr[Math.floor(Math.random() * arr.length)];
  if (typeof txt !== 'string') return String(txt);
  return txt.replace(/\{\{(icon_[a-z_]+)\}\}/g, function(_, k){ return consts[k] || ''; });
})() }}
```

**Зависимости:** родительский workflow (обычно `01_Dispatcher`) должен передавать `translations` + `constants` в child через Set-ноду «Prepare Data». В `01_Dispatcher` нода `Prepare Data 03` уже это делает — для других sub-workflows проверяй явно перед использованием snippet'а.

---

## Файлы-якоря

- [services/template_engine.py:76-78](../../../services/template_engine.py) — regex'ы Python движка
- [services/template_engine.py:108-147](../../../services/template_engine.py) — `_resolve_text` Two-pass logic
- [migrations/101_profile_main_text_headless_template.sql](../../../migrations/101_profile_main_text_headless_template.sql) — историческое заявление n8n grammar (legacy)
- [migrations/162_profile_main_v6_flat_template.sql](../../../migrations/162_profile_main_v6_flat_template.sql) — образец fix'а (RPC + template, 6 localized полей)
- [migrations/163_stats_main_flat_template.sql](../../../migrations/163_stats_main_flat_template.sql) — образец fix'а с одним localized полем
- [migrations/164_progress_main_flat_template.sql](../../../migrations/164_progress_main_flat_template.sql) — fix только шаблона (RPC уже корректна)
- [dispatcher/forward.py](../../../dispatcher/forward.py) — `TARGET_TO_PATH` определяет какие targets идут в Python
- `app_constants` ключи `handler_*_use_python` — runtime флаги Python cutover
