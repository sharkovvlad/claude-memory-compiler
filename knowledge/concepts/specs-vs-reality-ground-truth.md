# Specs vs Reality — Ground Truth Protocol

**Компилировано:** 2026-04-21 Session 10. Prevented критичный Session 10 SQL migration от генерации с неправильным callback convention.

## Правило

**Ground truth priority (в порядке убывания доверия):**

1. **Реальные RPC bodies** (`pg_get_functiondef`) — что код **фактически парсит/возвращает**
2. **Реальные DB schemas + constraints** (`information_schema.columns`, `pg_constraint`)
3. **Реальные live workflow JSONs** (`curl n8n API`)
4. **Applied migrations** (`/migrations/*.sql`)
5. **Knowledge Base** (`claude-memory-compiler/knowledge/concepts/*.md`)
6. **Specs / Design docs** (`profile-v5-screens-specs.md`) — **может быть устаревшей**
7. **Mockups / user memory** — самый ненадёжный

## Когда применять

- Перед генерацией SQL migration
- Перед PUT n8n workflow
- Перед ответом user'у "это баг" vs "это by design"
- Когда specs и observed behavior не совпадают

## Recipe: RPC body grep

```python
import os, psycopg2
from dotenv import load_dotenv
load_dotenv('/Users/vladislav/Documents/NOMS/.env')
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()

for fn in ['set_user_goal', 'set_user_training_type']:
    cur.execute("SELECT pg_get_functiondef(oid) FROM pg_proc WHERE proname=%s", (fn,))
    row = cur.fetchone()
    if row:
        body = row[0]
        print(f"\n=== {fn} ===")
        for i, line in enumerate(body.split('\n')):
            if any(k in line for k in ['WHEN ', "'cmd_", "'set_", 'v_goal_type', 'RETURN']):
                print(f"  L{i}: {line.strip()[:150]}")
```

**Что искать:**
- `WHEN p_X = 'cmd_select_Y' THEN 'Y'` — actual callback parsing
- `RAISE EXCEPTION '<msg>' WHEN ...` — actual validation rules
- `UPDATE users SET col = v_value` — actual column names
- `RETURN jsonb_build_object(...)` — actual return shape

## Recipe: specs cross-check

Когда generate migration / design doc:

### Step 1 — read specs first
```bash
grep -A5 "cmd_select_" /path/profile-v5-screens-specs.md | head -50
```

Extract claimed convention.

### Step 2 — verify against RPC body
Dump setter functions → grep CASE branches (see above).

### Step 3 — discrepancy resolution
Если specs `cmd_set_goal_lose` но RPC парсит `cmd_select_lose`:

**RULE: use RPC's parsing** (code is running production). Specs are secondary.

Документируй расхождение в plan file + notify user.

### Step 4 — optionally update specs после user sign-off
User's message (Session 10): *"если видишь расхождение с specs — после правок внеси в этот файл. Это библия UX дизайна"*.

**Do NOT automatically update** — wait for explicit user approval. Specs могут быть WIP и содержать aspirational design.

## Session 10 example

| Area | Specs said | RPC grep revealed | Decision |
|------|-----------|-------------------|----------|
| Goal picker callbacks | `cmd_set_goal_lose/maintain/gain` | `cmd_select_lose/maintain/gain` | Used RPC convention. Noted for specs update. |
| Activity | `cmd_set_act_sedentary/light/moderate/heavy` | `cmd_select_sedentary/light/moderate/heavy` | RPC wins. |
| Training | `cmd_set_train_strength/cardio/mixed/none` | `cmd_select_strength/cardio/mixed/training_skip` | RPC wins. Note: `training_skip` (underscore, not `none`). |
| Speed | `cmd_set_speed_slow/normal/fast` | `cmd_speed_slow/fast` (normal via ELSE) | Different prefix! `cmd_speed_*` NOT `cmd_select_speed_*`. |
| notifications_mode enum | `zen/balanced/beast` | CHECK constraint `IN ('zen','balanced','beast')` | Match. |
| users.country | Column name | Actual column is `country_code` | RPC/schema wins (subagent Session 10 auto-fixed during generation). |

## Session 11 anti-example — specs IGNORED

**Incident:** Migration 122 (Stats Headless) реализована **без чтения** `profile-v5-screens-specs.md §25`. Agent взял дизайн из NLM-описания legacy + impovised layout.

**Consequences:**
- Template с неправильными variable names (`{total_calories}` вместо spec-указанных `{calories_consumed}`)
- 3 кнопки вместо 1 (spec прямо отмечает "упрощено 2026-04-21 по user feedback — одна кнопка")
- Нет `current_date/time` вверху
- Нет светофоров `{p_status}/{f_status}/{c_status}`
- Нет `<blockquote expandable>{meals_list_formatted}</blockquote>`
- RPC named `get_stats_business_data` (spec: `get_daily_stats_rpc`)

User при live-test сверил новый экран с legacy screenshot и отметил регресс UX — пришлось писать migration 124 rewrite. Стоимость: +2 часа work, +5 inline bug-fixes, ~100 строк spec update.

**Root cause:** СТОП-правило "NLM первым делом" (CLAUDE.md) применено буквально — но NLM **НЕ знает** о существовании `.md` spec файлов в KB. Они не проиндексированы в нем.

**Prevention rule (Session 11 addendum):**

> **Specs = source of truth для UX/screens. `/nlm` — для БД/RPC discovery. Оба обязательны.**
>
> Перед генерацией любой headless миграции:
> 1. `grep -A30 "<screen_id>" profile-v5-screens-specs.md` — прочитать spec entry целиком
> 2. Если в spec-e указан `business_data_rpc` / layout / keyboard — использовать ИМЕННО их
> 3. Если spec кажется устаревшим — **спросить user** ("spec говорит X, current БД — Y, как поступить?")
> 4. ТОЛЬКО ПОТОМ — `/nlm` для БД/RPC details

**Hand-off rule (для Session 12+):** новый agent обязан ОЖИДАТЬ явного указания на source-of-truth spec файл в Session Handoff, читать его ПЕРЕД Phase 0 discovery.

## Session 11 — как БЫ нужно было сделать

**Правильный порядок** для migration 122 (Stats):

1. ✅ Read `profile-v5-screens-specs.md` §25 — extract layout, business_data_rpc name, keyboard spec
2. ✅ `/nlm` — 5 вопросов про existing RPCs (`get_day_summary` returns what? meals shape? etc.)
3. ✅ psycopg2 Phase 0 — verify app_constants, translation keys, thresholds
4. ✅ Написать ТЗ **начиная с spec layout**, не с impovisation
5. ✅ Adversarial review: "spec говорит RPC `get_daily_stats_rpc` — используется? keyboard 1 button — тоже?"
6. ✅ Dry-run + apply

Подтверждаю в migration 124 ex-post fact — все 6 шагов теперь соблюдены.

## Similar patterns elsewhere

### 04_Menu Dumb Renderer vs KB description
KB `headless-template-substitution.md` описывает multi-pass JS interpolation. Реально — прочитай `parameters.jsCode` ноды "Dumb Renderer" через n8n API. Могут быть tweaks не зафиксированные в KB.

### n8n node UUIDs vs workflow ID
KB workflow IDs stable, но UUIDs нод меняются при PUT / clone. Grep by `name` не `id`.

### Translation keys vs deployed state
KB / specs могут упоминать ключ, but `ui_translations` table не содержит. Always `content->'X'->>'Y'` check per lang.

## Связанные KB концепты

- [[pre-migration-discovery-recipe]] — Phase 0 discovery (includes RPC grep step)
- [[supabase-db-patterns]] — schema patterns
- [[n8n-data-flow-patterns]] — n8n workflow live vs cached state
- [[notebooklm-code-sync]] — NLM staleness warning

## Rule summary

**Когда specs говорит X, а код делает Y — доверяй коду, патчь specs позже (по user approval).**

Это особенно критично для: callback_data conventions, column names, RPC return shapes, enum values, CHECK constraints. Эти поля не имеют "correct abstract value" — only "correct observed value".
