---
title: "Sassy Sage Dialog Variants System"
aliases: [dialog-variants, array-translations, sassy-sage-variants, variadic-responses]
tags: [translations, ux, patterns, supabase, i18n]
sources:
  - "daily/2026-04-21.md"
created: 2026-04-21
updated: 2026-04-21
---

# Sassy Sage Dialog Variants System

Система вариативных ответов Sassy Sage: вместо одной фиксированной строки — JSONB-массив из 3 вариантов в `ui_translations`. Детерминированный выбор в n8n (по индексу или случайно) обеспечивает живой тон бота без повторяемости. Реализована серией миграций 104–108 (2026-04-21).

## Key Points

- **Формат:** `ui_translations.content[lang_code][section][key]` = `["вариант 1", "вариант 2", "вариант 3"]` — JSONB array вместо scalar string
- **Deep-merge правило:** `jsonb_set(content, '{section,key}', '[...]'::jsonb)` — не `content || '{section:{key:[...]}}'::jsonb`. Shallow merge стирает соседние ключи в секции!
- **Два слоя:** массивы вариантов (новые) + legacy scalar ключи (обновлены в migration 107 до Sassy Sage тона). Код читает то что умеет — дублирования нет, стиль синхронизирован
- **Emoji-правило:** raw-эмодзи разрешены для декоративных (🔥🎉💎🏆), системные иконки через `{{icon_xxx}}` (✅→`{{icon_check}}`, ⚠️→`{{icon_warning}}`). Проверка: `rg '✅|⚠️'` → 0 в migration-файлах
- **Плейсхолдеры сохранены** во всех 13 языках: `{friend_name}`, `{streak}`, `{calories}`, `{remaining_trials}` — не переводятся, готовы для Template Engine

## Details

### Покрытие миграций (что создано)

| Миграция | Секции | Примеры ключей | Scale |
|---|---|---|---|
| 104 | `errors`, `payment`, `referral` | `ai_not_food[3]`, `success[3]`, `present_friend[3]` | 3 ключа × 13 langs |
| 105 | `gamification`, `cron_notifications` | `first_log[3]`, `streak_7[3]`, `morning[3]`, `comeback_2days[3]` | 10 ключей × 13 langs |
| 106 | `free_tier` (new), `pay` (new) | `trial_limit_3[3]`, `limit_reached[3]`, `paywall[3]` | 3 ключа × 13 langs |
| 107 | `errors`, `cron_notifications` | Обновление 5 scalar ключей до Sassy Sage тона | 5 ключей × 13 langs |
| 108 | `questions`, `answers`, `profile` | `goal_speed`, `speed_slow/normal/fast`, `noms_speed_intro[3]`, `speed_hint` | 7 ключей × 13 langs |

Итого серия: **19+ ключей × 13 языков × 3 варианта = 741+ строк** вариативного контента.

### Паттерн выбора варианта в n8n (Dumb Renderer)

```javascript
// Детерминированный выбор по индексу (sage_quote_index из get_profile_business_data)
const idx = parseInt(business_data.sage_quote_index) || 0;
const variants = Array.isArray(translation) ? translation : [translation];
const text = variants[idx % variants.length];
```

Индекс — вычисляемое поле в `get_*_business_data` RPC (например, `sage_quote_index` в `get_profile_business_data`). Детерминированный по telegram_id + day — один и тот же юзер видит одну и ту же фразу в течение дня, но разную на следующий день.

### Migration 107 — Self-referential UPDATE (legacy sync)

Для 3 из 5 ключей migration 107 использует self-referential UPDATE — копирует первый элемент массива из уже примененных 104/105:

```sql
UPDATE ui_translations
SET content = jsonb_set(
  content,
  '{errors, not_food}',
  content -> 'errors' -> 'ai_not_food' -> 0
)
WHERE lang_code = lang;
```

Это гарантирует что legacy scalar = variants[0] — никакого расхождения тона.

### Два слоя архитектуры

**Новые массивы** (из 104/105/106): для headless UI с детерминированным выбором в n8n через multi-pass Dumb Renderer. Читаются через `{tr:section.key}` → n8n resolves array → selects by index.

**Legacy скалярные ключи** (из 107 refresh): для текущего кода (Python cron, legacy n8n code nodes). Синхронизированы с Sassy Sage тоном — variants[0]. Когда код мигрирует на новые ключи — legacy можно задепрекейтить без стилевого диссонанса.

### Emoji-правило (важно для копирайтеров и агентов)

| Тип | Пример | Правило |
|---|---|---|
| Декоративные | 🔥🎉💎🏆✨☕️🔒 | Raw UTF-8 в SQL — разрешено |
| Системные иконки | ✅⚠️🧠📊 | `{{icon_check}}`, `{{icon_warning}}` — обязательно |
| Плейсхолдеры | `{name}` `{streak}` | Оставить как есть — Template Engine заменит |

Проверка перед apply: `rg '✅|⚠️|🧠|📊' migration_NNN.sql` → 0 matches.

### Применение и верификация

1. **dry-run** через psycopg2 с rollback — проверка 13 lang_codes × N ключей
2. **real apply** — BEGIN; UPDATE×13; COMMIT;
3. **post-commit verification** — независимый connect, `jsonb_array_length(content->section->key) = 3` для всех ключей × 13 langs

Scale verification 2026-04-21: 247 проверок (19 ключей × 13 языков), все прошли.

## Related Concepts

- [[concepts/headless-template-substitution]] — Dumb Renderer multi-pass, `{tr:path}` resolution читает эти массивы
- [[concepts/n8n-template-engine]] — legacy Template Engine, `{{icon_xxx}}` правило
- [[concepts/supabase-db-patterns]] — Deep-merge `jsonb_set` паттерн, migration apply через psycopg2
- [[concepts/ux-crosscutting-principles]] — Sassy Sage tone of voice — сквозной принцип всего контента

## Sources

- [[daily/2026-04-21.md]] — Migrations 104-108: полная серия dialog variants. Emoji-правило. Self-referential legacy sync. Two-layer architecture. 741+ строк контента

---

## 2026-05-13 — Python `_resolve_text` JSONB-array support

С момента введения паттерна (mig 104-108) рендерер JSONB-array variants жил **только в legacy n8n** (`Dumb Renderer` JS делал random pick). Когда Phase 2 menu_v3 → Python (28.04), `services/template_engine._resolve_text` **не умел JSONB-arrays** — возвращал text_key как literal.

**UAT 13.05 evidence:** юзер кликнул «Исправить» под карточкой → mig 209 render_screen('edit_food_prompt') с text_key='edit_food.prompt_variants' → Python `_resolve_text` ожидал string → видел list → возвращал `'edit_food.prompt_variants'` как text → юзер видел literal ключ.

### Fix (mig 213 PR #63)

Новый helper `_coerce_translation_value` в template_engine.py:

```python
def _coerce_translation_value(value, text_key):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        candidates = [v for v in value if isinstance(v, str) and v]
        if not candidates:
            return None  # caller fallback на text_key literal
        return random.choice(candidates)
    return None
```

Применён в **трёх точках**:
1. `_resolve_text` (основной render path).
2. Nested `_tr_replace` callback (для `{tr:section.key}` references — там тоже может быть array).
3. `resolve_translation_text` public helper (для handlers которые шлют отдельные сообщения).

### Параллельный gotcha — double-brace

Раньше `_resolve_text` НЕ нормализовал `{{icon_X}}` → `{icon_X}` (только `resolve_translation_text` это делал). После mig 213 module-level `_DOUBLE_BRACE_ICON_RE` применён в обоих entry-points. Без этого `edit_food.meal_deleted='{{icon_delete}} Удалено'` (legacy n8n format) рендерилось бы как literal `{{icon_delete}} Удалено`.

### Rule for future agents

- При добавлении новых JSONB-array variants в `ui_translations` — никакого SQL-side random pick (`render_screen` не делает). Python обрабатывает автоматически.
- Если ключ изначально string и потом меняется на array — Python continue работать (helper handles both).
- APPEND ≠ REPLACE rule сохраняется для UPDATE через jsonb_set (`(content->'section'->'key') || jsonb_build_array(<new>)`) — random pick из расширенного массива.
- **Hand-off case** — Python `_resolve_text` подгружается из ctx.translations (per-user lang), random.choice идёт на per-request basis → каждый клик даёт новый вариант (живой character Noms).
