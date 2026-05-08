# Pure Headless: разделение слоёв + template substitution

> **Статус:** активный паттерн (Session 9, 2026-04-20). Реализован на Profile v5 pilot. Будет раскатан на все 30+ экранов в Phase 3A/B.
>
> **Ключевые артефакты:** migration 100 (RPC), migration 101 (template), 04_Menu_v3 Dumb Renderer extended JS (Session 9 Phase 1 PUT).

---

## Single source of truth для каждого слоя

Это **главный архитектурный принцип** NOMS. Никакой слой не дублирует ответственность другого. Меняется иконка → 1 UPDATE. Добавляется язык → 1 INSERT. Новое поле в экране → 1 migration.

| Слой | Где хранится | Ответственность |
|---|---|---|
| **Бизнес-данные** | RPC `get_*_business_data` → `users`, `v_user_context` | Числа, enum-ключи, счётчики, вычисления. Никаких текстов, никаких эмодзи. |
| **Переводы** | `ui_translations.content[lang_code]` | Атомарные ключи (`profile.title_agent`, `profile.sage_premium_2`). Одна строка = одна фраза в одном языке. |
| **Иконки** | `app_constants` | Все эмодзи. Строковое значение (`icon_profile = '👤'`, `goal_lose = '📉'`). |
| **Layout** | `ui_translations.content.<screen>.main_text` | Шаблон с placeholders. Может быть **универсальный для всех 13 языков** если структура одинаковая. |
| **Склейка** | n8n Dumb Renderer (JS Code node) или будущий TMA client | Multi-pass substitution. Никакой бизнес-логики, только механическое замещение. |

Смотри [[headless-architecture]] для общего контекста Headless; этот документ — про **template + data contract**.

---

## Template syntax (Dumb Renderer в 04_Menu_v3)

Три вида placeholder'ов + nested braces:

| Syntax | Резолвит | Источник |
|---|---|---|
| `{var_name}` | значение из `template_vars` | RPC `business_data` JSON |
| `{{const_key}}` | значение из `app_constants` | таблица `app_constants` |
| `{tr:dotted.path}` | перевод на current language | `ui_translations[lang_code].content.dotted.path` |
| `{{goal_{goal_type}}}` | **nested** — сначала `{goal_type}`→"lose", потом `{{goal_lose}}`→📉 | комбинация |
| `{tr:profile.sage_{sage_tier}_{sage_quote_index}}` | nested в `{tr:}` — `{sage_tier}`→"premium", `{sage_quote_index}`→"2" → `{tr:profile.sage_premium_2}` | комбинация |

### Multi-pass interpolation (Dumb Renderer JS)

```javascript
function interpolate(text, tplVars) {
    if (!text) return '';
    let prev, iter = 0;
    do {
        prev = text;
        // {tr:path.to.key} — translations lookup; supports nested {var}
        text = text.replace(/\{tr:([\w.{}]+)\}/g, (m, key) => {
            const resolvedKey = key.replace(/\{(\w+)\}/g, (_, k) =>
                tplVars[k] != null ? String(tplVars[k]) : ''
            );
            if (resolvedKey.includes('{')) return m;  // defer
            return lookupKey(translations, resolvedKey);
        });
        // {{const_key}} — constants; supports nested {var}
        text = text.replace(/\{\{([\w{}]+)\}\}/g, (m, key) => {
            const resolvedKey = key.replace(/\{(\w+)\}/g, (_, k) =>
                tplVars[k] != null ? String(tplVars[k]) : ''
            );
            if (resolvedKey.includes('{')) return m;
            return constants[resolvedKey] || '';
        });
        iter++;
    } while (text !== prev && iter < 5);  // stability cap
    // Final pass: plain {var}
    text = text.replace(/\{(\w+)\}/g, (m, key) =>
        tplVars[key] != null ? String(tplVars[key]) : ''
    );
    return text;
}
```

**Почему multi-pass:** nested braces требуют iteration — сначала внутренний `{var}` резолвится → новая строка → опять ищем `{tr:...}` / `{{...}}`. Stop когда `prev === text` (стабильность).

**Почему iter<5:** защита от теоретических циклов (например если translation ключ содержит `{...}` внутри). Реально 1-2 passes достаточно.

**Порядок passes важен:** plain `{var}` в конце — иначе он "съест" внутренности `{tr:profile.sage_{sage_tier}}` раньше времени.

---

## Пример end-to-end: Profile Agent Dossier

### 1. RPC `get_profile_business_data(telegram_id)` возвращает raw JSON (33 поля):

```json
{
  "first_name": "Vladislav",
  "subscription_status": "premium",
  "goal_type": "lose",
  "weight_kg": 98,
  "target_calories": 2630,
  "member_since_month": 1,
  "member_since_year": 2026,
  "sage_quote_index": 2,
  "daily_log_limit": 2,
  "sage_tier": "premium",      // helper: 'free' or 'premium' (trial maps to premium)
  "limit_variant": "unlimited", // helper: 'free' or 'unlimited' (for limit_logs lookup)
  ... (26 existing fields)
}
```

**Helper-поля `sage_tier` и `limit_variant`** — pre-computed группировки. Спасают от missing translation keys когда subscription='trial' (нет `sage_trial_*`, есть только `sage_premium_*`). RPC маппит: premium OR trial → 'premium'/'unlimited'.

### 2. Template `profile.main_text` (один на все 13 языков):

```
{{icon_profile}} <b>{tr:profile.title_agent}: {first_name}</b>
{tr:profile.member_since} {tr:calendar.month_{member_since_month}} {member_since_year}

{{icon_premium}} {tr:profile.status_{subscription_status}}
{{icon_lightning}} {tr:profile.limit_logs_{limit_variant}}

{{icon_scales}} <b>{tr:profile.bio_and_goal}:</b>
▫️ {tr:profile.current_weight}: {weight_kg} {tr:units.kg}
▫️ {tr:profile.plan_label}: {{goal_{goal_type}}} {tr:answers.goal_{goal_type}}
▫️ {tr:profile.daily_norm}: {target_calories} {tr:units.kcal_per_day}

💬 Noms: "{tr:profile.sage_{sage_tier}_{sage_quote_index}}"
```

**Zero:** raw emoji, hardcoded слова, language-specific branches.

### 3. Dumb Renderer собирает (ru premium user):

**Pass 1:** `{tr:calendar.month_{member_since_month}}` → `{tr:calendar.month_1}` → "января"
**Pass 2:** `{tr:profile.status_{subscription_status}}` → `{tr:profile.status_premium}` → "NOMS Premium"
**Pass 3:** `{{goal_{goal_type}}}` → `{{goal_lose}}` → 📉
**Pass 4:** `{tr:profile.sage_{sage_tier}_{sage_quote_index}}` → `{tr:profile.sage_premium_2}` → "Премиум-агент на связи..."
**Pass 5:** plain `{first_name}` → "Vladislav", `{weight_kg}` → "98", etc.

### 4. Результат в Telegram:

```
👤 Досье Агента: Vladislav
В системе с января 2026

👑 NOMS Premium
⚡ Лимит логов: Безлимит

⚖️ Биометрия и Цель:
▫️ Текущий вес: 98 кг
▫️ План: 📉 Похудение
▫️ Норма: 2630 ккал/день

💬 Noms: "Премиум-агент на связи. Все системы работают на полную мощность!"
```

---

## Helper-поля для "groups" (trial/missing keys)

Часто возникает: в БД есть `profile.status_free` и `profile.status_premium`, но **не** `profile.status_trial`. Template `{tr:profile.status_{subscription_status}}` сломается для trial users.

**Два подхода:**

1. **Duplicate keys** — добавить `profile.status_trial = "NOMS Trial"` × 13 языков. Больше данных, каждая групповая концепция требует отдельных ключей.

2. **Helper field в RPC (предпочтительно):** RPC возвращает group-mapping field.
   ```sql
   'sage_tier', CASE WHEN subscription_status IN ('premium','trial') THEN 'premium' ELSE 'free' END
   ```
   Template использует `{sage_tier}` → уже готовая группа. Меньше translation keys, логика в одном месте.

Когда выбирать (2): если у groups стабильное семантическое значение (free vs paid). Когда (1): если группы могут разойтись (trial имеет свой оттенок голоса).

---

## Session 9 pipeline (spec-driven → external AI → review → apply)

Этот паттерн отлично работает для SQL-heavy миграций (шаблон + 13 языков + много seeded data):

1. **Spec в Markdown** (`.claude/specs/migration_NNN_spec.md`) — писать в понятной форме для external AI:
   - Контекст архитектуры (Headless принципы, CLAUDE.md правила)
   - Reference к существующим миграциям
   - Список полей / правил со ссылками на типы
   - Чек-лист anti-patterns (что запрещено)
   - Verification block (RAISE NOTICE)

2. **Main agent review** — построчно против spec:
   - Сохранены ли все existing fields?
   - Нет ли hardcoded emoji / localized strings?
   - Правильный syntax placeholder'ов?
   - Все referenced translation keys существуют?

3. **NLM verification** — sanity-check БД-специфики (кол-во языков, missing keys, типы колонок). Решение apply/no-apply.

4. **Subagent fix** — если main review нашёл серьёзные issues: не переписывать с нуля, а дать subagent'у конкретный list правок + reference к existing файлам. Быстрее чем новая генерация.

5. **Pre-apply sanity** — через psycopg2 SELECT: проверить что все translation keys существуют, есть ли нужные колонки в view.

6. **Apply** — psycopg2 autonomous, каждая миграция отдельным commit.

7. **Verification пост-apply** — DO-block NOTICE + ручной SELECT.

Session 9 этот pipeline предотвратил **2 apply неправильного SQL**: первая попытка (external AI) — hardcoded emojis, monolithic text; вторая (subagent fix) — missing keys `sage_trial_*` / `limit_logs_premium`. Main agent + NLM поймали все.

### Чек-лист качества для external AI (финальный)

Повторяй в spec'ах:
- [ ] Zero raw emoji в SQL (только `{{icon_xxx}}` ссылки)
- [ ] Zero hardcoded localized words в RPC
- [ ] RPC возвращает только raw data (числа, enum-ключи, group-mappings)
- [ ] Layout в `ui_translations.content.*.main_text`, один universal шаблон если структура одинаковая
- [ ] Placeholders: `{var}`, `{{const}}`, `{tr:path}` только
- [ ] HTML `<b>` (НЕ Markdown `**`)
- [ ] `CREATE OR REPLACE FUNCTION` (не DROP)
- [ ] `STABLE SECURITY DEFINER SET search_path = public` для read-only RPCs
- [ ] `COALESCE` на все nullable fields
- [ ] Один `BEGIN; ... COMMIT;` на миграцию
- [ ] `::text` cast на dollar-quoted strings в `to_jsonb()` (иначе DatatypeMismatch)
- [ ] DO-block verification с RAISE NOTICE
- [ ] GRANT EXECUTE сохраняется/восстанавливается
- [ ] COMMENT ON FUNCTION со ссылкой на migration number

---

## Почему этот паттерн

1. **TMA-ready:** будущий Telegram Mini App (React/Vue) дёргает тот же RPC → получает чистый JSON → рендерит сам через i18next. **Не надо рефакторить RPC** когда пойдём в TMA.
2. **Единая правка "косметики":** сменить 👤 на 📂 — один UPDATE `app_constants`. Все 13 языков автоматом.
3. **Минимум translation keys:** один template на 13 языков (разница в layout только если word order реально разный). Обычно 1 string × 13 = 13 строк, не 13 × 20 = 260.
4. **SQL не склеивает строки:** PostgreSQL великолепен в индексных SELECT'ах и math, плох в string concat на 13 языков. Склейка в JS — O(1) hashmap lookups.
5. **Добавить 14-й язык:** один INSERT в `ui_translations`, не трогаем n8n, не меняем RPC.

---

## Связанные концепты

- [[headless-architecture]] — общая картина Headless (Variant C), ui_screens + process_user_input + render_screen
- [[reaction-on-param-save-ux]] — 👌 паттерн для text save (Session 8)
- [[one-menu-ux]] — last_bot_message_id, save_bot_message, One Menu principle
- [[n8n-data-flow-patterns]] — правила n8n: HTTP clobbers $json, fire-and-forget branches
- [[n8n-template-engine]] — legacy template engine (до Headless, для справки)

---

## Changelog

- **2026-04-20 (Session 9):** паттерн введён. Migration 100 (RPC raw data + 26 existing + 7 new fields), Migration 101 (universal template × 13 langs). Dumb Renderer JS extended (3-pass interpolation). Dispatcher Phase 5 (reply "Профиль" → v3). Legacy Build Profile Text в 04_Menu отключена для Profile screens. Live verified на premium user: Agent Dossier renders correctly с genitive months, localized units, sage quote deterministic rotation.
