---
title: "i18n RPC Audit Pattern — scan pg_proc separately from ui_translations"
aliases: [i18n-rpc-audit, rpc-hardcoded-strings, pg-proc-cyrillic-scan, phase4-rpc-cleanup]
tags: [i18n, rpc, audit, lessons-learned, copywriter, migration]
sources:
  - "daily/2026-05-20.md"
created: 2026-05-20
updated: 2026-05-20
---

# i18n RPC Audit Pattern

При i18n-rollout'е (Phase 4+) `ui_translations` JSONB — лишь **часть** i18n-surface. SQL RPC bodies (`pg_proc`) — **вторая часть**, часто забываемая. Без coupled audit'а хардкоженные локализованные строки в теле SQL-функций остаются необнаруженными, и юзеры на не-RU языках видят RU-текст.

## Key Points

- **Два источника истины.** `ui_translations` (JSONB словарь) + `pg_proc` (тела функций с inline `'Стрик: ' || v_streak || ' дн.'`). Phase 4 копирайтинг audit'ил только первый — пропустил второй.
- **Owner-observable bug.** `log_meal_transaction` хардкодил RU «Стрик: N дн.» и «Старт нового стрика!» → 12 не-RU языков получали RU-строки. Бот говорил по-русски с испанским юзером.
- **Scan recipe.** `grep -iP "[\x{0400}-\x{04FF}]" <(pg_get_functiondef)` для Cyrillic; strip line comments `--` перед scan'ом (RU-комментарии = OK, RU-литералы в `'...'` = violation).
- **Fix pattern.** Добавить ключ в `ui_translations` × 13 langs → RPC читает через `SELECT content #>> path FROM ui_translations WHERE lang_code = v_lang` → REPLACE placeholders в PL/pgSQL.
- **Закрыто 2026-05-20.** Mig 285 (streak food-log, 2 ключа × 13 = 26 entries) + mig 286 (4 RPC cleanup, 23 ключа × 13 = 299 entries). Phase 4 i18n cleanup полностью завершён.

## Details

### Как обнаруживается

Phase 4 копирайтинг (mig 231-251) провёл массовую культурную адаптацию ~286 ключей × 13 языков через `ui_translations`. Audit шёл через JSON-path сканы — пропускал строковые литералы внутри SQL-функций. Owner-observable симптом: после food log бот говорил «🏆 Стрик: 18 дн.» всем юзерам независимо от языка.

### Root cause chain

```
log_meal_transaction (PL/pgSQL):
  L240: v_streak_msg := v_icon_streak || ' Стрик: ' || v_new_streak || ' дн.';
  L256: v_streak_msg := '📅 Старт нового стрика!';
```

Эти строки — **double violation**:
1. No-hardcode rule (CLAUDE.md §2): тексты должны быть из `ui_translations`.
2. i18n broken: один RU-язык для всех 13.

Phase 4 не мог найти эти строки потому что они не существовали как ключи в `ui_translations` — конкатенация собиралась inline в SQL.

### Scan recipe (для будущих i18n-rollout'ов)

```python
import re, psycopg2

CYRILLIC_IN_LITERAL = re.compile(r"'[^']*[\u0400-\u04FF]+[^']*'")

conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()

# Все user-facing функции (set_user_*, get_*_business_data, log_*, cron_*, apply_*, etc.)
cur.execute("""
    SELECT proname, pg_get_functiondef(oid) 
    FROM pg_proc 
    WHERE pronamespace = 'public'::regnamespace
      AND prokind = 'f'
""")

for name, body in cur.fetchall():
    # Strip line comments (Russian comments = OK)
    clean = re.sub(r'--[^\n]*', '', body)
    matches = CYRILLIC_IN_LITERAL.findall(clean)
    if matches:
        print(f"⚠️ {name}: {len(matches)} hardcoded RU literals")
        for m in matches:
            print(f"   {m[:80]}")
```

**Critical:** `regexp_replace(body, '--[^\n]*', '', 'g')` обязателен — RU-комментарии (`-- Блок стрика`) не являются нарушением. Только `'литерал'` строки в SQL-коде.

### Fix pattern (canonical)

```sql
-- 1. Добавить ключ в ui_translations × 13 langs
UPDATE ui_translations SET content = jsonb_set(content, 
    '{gamification,streak_kept}', 
    to_jsonb('🏆 Серия: {streak} дн.'::text), true)
WHERE lang_code = 'ru';
-- ... repeat × 13

-- 2. В RPC: SELECT per user language
SELECT content #>> '{gamification,streak_kept}' 
INTO v_streak_template
FROM ui_translations 
WHERE lang_code = v_user.language_code;

-- Fallback
IF v_streak_template IS NULL THEN
    SELECT content #>> '{gamification,streak_kept}' 
    INTO v_streak_template
    FROM ui_translations WHERE lang_code = 'en';
END IF;

-- 3. REPLACE placeholders
v_streak_msg := REPLACE(v_streak_template, '{streak}', v_new_streak::text);
```

### Inventory closed (2026-05-20)

| Mig | RPC | Ключей × 13 | Что было |
|---|---|---|---|
| 285 | `log_meal_transaction` | 2 × 13 = 26 | Streak kept + new start — inline RU concat |
| 286 | `apply_discount_code` | 4 × 13 = 52 | 4 error/success messages — only RU |
| 286 | `get_personal_metrics_business_data` | 3 × 13 = 39 | Пол «Мужской/Женский/Не указан» — RU+EN |
| 286 | `get_women_health_business_data` | 5 × 13 = 65 | Pregnancy/lactation status — RU+EN |
| 286 | `get_my_plan_business_data` | 11 × 13 = 143 | Goal type/speed labels — 13 langs hardcoded в CASE |

**Total: 23 ключа × 13 langs = 325 entries.** Полный Cyrillic-scan после mig 286 вернул 0 hits (кроме RU-комментариев).

### Taxonomy decisions (для будущих ключей)

| Namespace | Когда |
|---|---|
| `payment.promo_*` | Промо-код error/success (payment-related) |
| `profile.goal_type_*` / `profile.goal_speed_*` | Локализованные labels для picker values |
| `profile.gender_*` | Гендерные метки |
| `profile.pregnancy_*` / `profile.lactation_*` | Материнский статус |
| `gamification.streak_*` | Streak-сообщения в food log |

### Writer→critic pipeline для RPC i18n (расширенный)

6-axis critic (owner-mandated для sensitive keys):
1. naturalness
2. sassy_sage_tone
3. **anti_shame** (mandatory 5/5 — hard gate)
4. brevity
5. **cross_language_comprehension** (NEW — каждый перевод понятен носителю без контекста)
6. **clinical_respectfulness** (для pregnancy/lactation/gender — медицинский, но не stiff)

## Правило для агентов

> **При любом i18n-rollout'е (Phase 4+):**
> 1. Scan `ui_translations` JSONB — standard pipeline.
> 2. **Scan `pg_proc`** отдельно — recipe выше.
> 3. Закрыть оба surface'а в одном PR (или двух consecutive).
> 4. Без coupled audit'а Phase 4 НЕ считается завершённым.

## Related Concepts

- [[concepts/copywriter-playbook]] — entry point для translation sessions (добавить step: scan pg_proc)
- [[concepts/python-vs-n8n-template-grammar]] — две грамматики одного ui_translations (RPC surface — третий)
- [[concepts/sassy-sage-multilingual-glossary]] — tone reference per language
- [[concepts/pre-migration-discovery-recipe]] — Phase 0 discovery (добавить pg_proc Cyrillic scan)
- [[concepts/ui-translations-bulk-update-recipe]] — 10-step pipeline (дополняет, но не заменяет RPC audit)

## Sources

- [[daily/2026-05-20.md]] — Mig 285: streak food-log i18n (2 RU-hardcoded strings → 26 i18n entries). Mig 286: 4 RPCs cleanup (23 keys × 13 langs = 299 entries). Phase 4 i18n cleanup полностью завершён. Lesson: pg_proc scan обязателен отдельно от ui_translations JSONB.

---

## Addendum 2026-06-12 — cron-notifications i18n-coverage audit

i18n surface = `ui_translations` + `pg_proc` (см. выше) **+ Python cron-кода**:
строки которые код `text.replace("{X}", val)` берёт из `cron_notifications.*`,
`payment.*` и шлёт юзерам напрямую (без RPC посередине). Это **третий слой**,
который Phase 4 не сканировал.

### Симптом

`crons/ton_payment_checker.py:338` после успешного USDT/TON-платежа читал
`payment.activated_body`. Ключ **отсутствовал во всех 13 langs** — все юзеры
получали hardcoded EN fallback. Тихий 0/13 — нет error log'а, нет CI alert'а.
Аналогичный случай был с `cron_notifications.reminder_waist_retrofit` (mig 498).

### Recipe (reusable) — `/tmp/cron_i18n_audit*.py`

Простой скрипт psycopg2, ~150 строк. Прогон ~3 сек:

1. **Phase A — Coverage:** для каждого `(namespace, key)` из EXPECTED_KEYS:
   ```sql
   SELECT lang_code, content #> %s FROM ui_translations
   ```
   Проверь 13/13 → present. Меньше → phantom-key или legacy.

2. **Phase B — Placeholder mismatch:** code expects `{name}`, `{streak}` etc.
   Регексп `\{([a-z_][a-z0-9_]*)\}` по `collect_strings(val)`. **Внимание:**
   большинство mismatch'ей — false positives (копирайтер интенциональный:
   Sage ≤35 chars/line часто без `{name}`). Только missing placeholders в EN
   (canonical) — настоящий баг.

3. **Phase C — Orphan keys:** `jsonb_object_keys(content->'cron_notifications')`
   − ключи в коде. Что-то осталось от mig 067/102/338, не показывается юзерам.

4. **Phase D — Fine-grained EN-leak:** per-string set match non-EN vs EN.
   Допусти cognates (Stress/Cardio/OK/Mana/XP/kcal/Premium).

5. **Phase E — Phantom-Pet:** regex `\b(Pet|Пет)\b`. CI guard
   `pr-phantom-pet-guard` уже ловит, но скрипт даёт отчёт за один проход.

### Когда запускать

- При добавлении нового cron-уведомления → проверить что новый ключ есть в всех
  13 langs ДО Python-кода. Не «hardcoded fallback на первое время».
- Периодически (раз в месяц или после batch i18n-миграций) — поймать orphans.
- После любого scalar↔array consumer-shift — Phase B mismatch покажет ломаные
  placeholder'ы.

### Защита от phantom-key fallback

**Pattern:** при добавлении нового user-facing cron-ключа, первая миграция = INSERT
ключа во все 13 langs (даже как «owner-supplied draft EN + 12 langs TODO»),
**отдельным PR ДО** Python-кода который читает этот ключ. Никакого
`get(key) or "..."` hardcoded fallback — иначе тихий regression до следующего
аудита (8 месяцев в случае luteal/waist_retrofit/activated_body).

### Связанные мигации

- mig 498 (PR #381) — `waist_retrofit` key mismatch fix.
- mig 499 (PR #382) — `day_close` `{meals_needed}` placeholder.
- mig 500 (PR #388) — `activated_body` phantom-key 0/13 langs.
