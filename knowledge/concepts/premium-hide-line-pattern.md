# Premium-Hide Line Pattern

**Captured:** 2026-05-25 (использован в 4 mig подряд — mig 343/348/353/354/355).

## Problem

Headless screens содержат строки, релевантные только для **подмножества юзеров** — например:
- `🔋 Логов в день: 1/2` показывается free, но для premium «безлимит» → zero-info noise → нужно скрыть.
- `🌙 Сон: Мало · 🌀 Стресс: Высокий` (wellbeing strip) показывается только premium.
- `🔋 Мана: 312/500` показывается free, premium «Безлимит» → noise.

Headless `template_engine.py` использует **plain string substitution** (`{var}` → value). Нет conditional `{{#if}}` синтаксиса. Если template содержит:
```
{icon_premium} {status_localized}
{logs_limit_line}
{icon_scales} ...
```
и `logs_limit_line = ''` (premium), результат:
```
👑 NOMS Premium
                ← orphan blank line
⚖️ Текущий вес: ...
```
**Орфан blank line ломает плотный mobile layout.**

## Solution — pre-resolve в SQL, sub-line carries own newline

**Layer 1 (SQL business_data RPC):** строка резолвится полностью в business_data RPC. **С leading или trailing `\n` встроенным в строку.** Пустая строка — без `\n`.

```sql
-- Pattern variant A (LEADING \n) — line идёт ПОСЛЕ предыдущей
IF v_premium THEN
    v_mana_line := '';
ELSE
    v_mana_line := E'\n' || v_icon_mana || ' ' || v_label || ': <b>' || v_value || '</b>';
END IF;

-- Pattern variant B (TRAILING \n) — line идёт ПЕРЕД следующей
IF v_premium THEN
    v_logs_limit_line := '';
ELSE
    v_logs_limit_line := v_icon_battery || ' ' || v_label || ': ' || v_remaining || '/' || v_limit || E'\n';
END IF;
```

**Layer 2 (template):** placeholder в template **БЕЗ окружающих `\n`** — newline уже встроен в строку.

```
-- LEADING-\n style (variant A):
{icon_xp} XP: <b>{xp}</b>  ·  {icon_coin} <b>{nomscoins}</b>{mana_line}

{icon_league} ...

-- TRAILING-\n style (variant B):
{icon_premium} {status_localized}
{logs_limit_line}{icon_scales} {tr:profile.current_weight}: ...
```

Когда `_line = ''`, template renders без gap. Когда `_line = '\nXXX'` или `'XXX\n'`, line появляется визуально на своём месте.

## Когда использовать LEADING vs TRAILING

**LEADING `\n`** (`E'\n' || ...`) — line встроена между двумя других строк, и нужно чтобы при empty case БЛИЖАЙШИЙ предыдущий контент не получал orphan EOL. Пример: mana под XP/coins на progress_main (mig 354):
```
{icon_xp} XP: ...  {icon_coin} ...{mana_line}    ← без \n до {mana_line}
                                                  ← если non-empty, начинается своим \n
{icon_league} ...
```

**TRAILING `\n`** (`... || E'\n'`) — line идёт перед другой контентной строкой, и пустая должна просто исчезнуть без gap:
```
{icon_premium} {status_localized}
{logs_limit_line}{icon_scales} ...               ← logs_limit_line carries \n когда non-empty
```

## SQL implementation checklist

1. **DECLARE** новой переменной (`v_<name>_line TEXT`).
2. **Pre-resolve dependencies** в SQL: `v_icon_X := app_constants.X`, `v_label_X := ui_translations.<lang>.X` (с en fallback). Pass1 `{tr:...}` substitution НЕ применяется к содержимому переменных (это inner sub-string), все translation lookups делать в SQL.
3. **CASE** для empty vs non-empty:
   ```sql
   IF <condition_for_hide> THEN
       v_X_line := '';
   ELSE
       v_X_line := <leading_or_trailing_newline> || <icon> || ' ' || <label> || ': <b>' || <value> || '</b>';
   END IF;
   ```
4. **Return jsonb** — добавить `'X_line', v_X_line` в финальный `jsonb_build_object`.
5. **Template UPDATE** — заменить старую inline-форму на placeholder `{X_line}` без окружающих `\n`.

## Anti-patterns

### ❌ `'\n' if X else ''` в Python после render

Template_engine не предусматривает post-processing per-placeholder. Если делать post-trim в Python — нарушение layered architecture (RPC-first), плюс template_engine может закешировать промежуточный result.

### ❌ Conditional template variant via meta

Можно сделать `meta.template_variant = 'free' | 'premium'` + два разных `profile.main_text_free` / `_premium` ключа. **Удваивает translation load × 13 langs**, дрейф между вариантами легко возникает (одна строка обновляется в одном, забывают в другом). Pre-resolved SQL = single source.

### ❌ Whitespace token instead of empty string

Если оставить line как `' '` или `'·'` для premium «чтобы не пусто» — это carrier-bubble антипаттерн (lesson `one-menu-ux.md`, Telegram bare-dot bubbles). Better: actual empty + carry-own-newline.

## Тестирование

В migration DO $$ block — SAVEPOINT/ROLLBACK для каждого случая:

```sql
DO $$
DECLARE v_result jsonb;
BEGIN
    -- Premium case → line empty
    SELECT public.get_X_business_data(<admin_tid>) INTO v_result;
    IF (v_result->>'X_line') <> '' THEN
        RAISE EXCEPTION 'premium-hide failed: %', v_result->>'X_line';
    END IF;

    -- Free case via SAVEPOINT (rolled back after test)
    SAVEPOINT t;
    UPDATE users SET subscription_status='free' WHERE telegram_id=<test_tid>;
    SELECT public.get_X_business_data(<test_tid>) INTO v_result;
    IF (v_result->>'X_line') NOT LIKE E'\n%' THEN  -- LEADING variant
        RAISE EXCEPTION 'free user should have LEADING-\n line';
    END IF;
    ROLLBACK TO SAVEPOINT t;
END $$;
```

## Применения в проде (по состоянию 2026-05-25)

| Mig | Line | Variant | Hide condition |
|---|---|---|---|
| 343 | `active_modifiers_strip` (stats_main) | LEADING | empty modifiers list |
| 348 | `active_modifiers_strip` (stats_main, moved to TOP) | TRAILING | empty modifiers list + non-premium |
| 353 | `logs_limit_line` (profile_main) | TRAILING | `subscription_status IN ('premium','trial')` |
| 353 | `phenotype_line` (profile_main) | LEADING | `phenotype='default'` (deprecated in mig 355 — always shown now) |
| 354 | `mana_line` (progress_main) | LEADING | `subscription_status='premium'` |

## Related KB

- [[headless-template-substitution]] — почему template_engine не делает Pass 2 для `{tr:...}` внутри переменных
- [[headless-button-creation-gotchas]] — другие места где SQL pre-resolution критичен
- [[one-menu-ux]] — почему orphan carrier-bubble нельзя оставлять
- [[python-vs-n8n-template-grammar]] — variant resolution rules
