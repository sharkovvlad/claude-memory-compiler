# Safe `CREATE OR REPLACE FUNCTION` Recipe — защита от stale-base regression

**Создано:** 2026-05-07. **Тип:** методичка (recipe). **Применимость:** любая правка существующей PostgreSQL функции в проекте NOMS, особенно крупных (`process_user_input`, `process_onboarding_input`, `dispatch_with_render`, `render_screen`, `cron_*`).

---

## Преамбула — почему это важно

В проекте NOMS **уже трижды** случалась одна и та же регрессия — **stale-base regression**. Агент брал базу для `CREATE OR REPLACE FUNCTION` из устаревшего источника (git-файла предыдущей миграции, своего снапшота из прошлой сессии, NLM-ответа), вносил изменения, применял миграцию — и **молча откатывал** работу другого агента, сделанную несколько часов или дней назад. Симптомы каждый раз появлялись только после деплоя в прод.

Хронология инцидентов:

| Mig | Функция | Что произошло | Цена |
|---|---|---|---|
| **042** (29.04) | `cron_check_streak_breaks` | Добавляли `is_bot=false`, скопировали тело из mig 011 — потеряли фикс mig 036 (`u.streak_freezes` qualified). PG 42702 ambiguous column. | Cron падал ~сутки, silent error в apscheduler (job=success, RPC=400). |
| **167** (3.05) | `cron_check_streak_breaks` (тот же baseline drift) | Добавляли `deleted_at IS NULL`, скопировали тело из mig 042 — оно всё ещё было сломанным. Пришлось делать mig 167 как объединяющий fix. | Двойная регрессия на одной функции. |
| **175** (5.05) | `process_onboarding_input` | Добавляли FSM-ветки `goal → speed → phenotype_quiz`. Сняли snapshot через `pg_get_functiondef` **ДО** того как другой агент применил mig 173 (или mig 173 ещё не отразилась в кэше). Snapshot вошёл в `CREATE OR REPLACE` — **молча откатил** ветку `cmd_edit_lang` из mig 173. | Critical bug "changing_language ghost status" + cmd_lang_uk выкидывает в главное меню. 4 миграции на починку (178, 180, 181 reverted, 182). 4 часа потерянного времени, пользователь видел тишину на /start. |

**Общий root cause всех трёх случаев:** агент не проверил, что его snapshot — **актуальное** живое состояние прода **в момент применения**, а не «было правдой пять минут назад».

**Цена:** каждый случай — production регрессия, видимая пользователям, плюс несколько часов на расследование + cherry-pick правильной версии. Это самый дорогой класс ошибок в NOMS.

> ⚠️ Этот recipe — **обязательное чтение** перед любым `CREATE OR REPLACE FUNCTION` на функцию длиннее ~50 строк или часто редактируемую (см. список «горячих» функций в начале файла). Не «if you have time». Не «когда вспомнишь». ВСЕГДА.

---

## Когда применять

Recipe нужен в следующих сценариях:

- **Точечное изменение одной ветки** в большой функции (`process_user_input` ~600 LOC, `process_onboarding_input` ~500 LOC) — типичный случай: «добавить FSM-ветку», «починить одну валидацию», «переписать один CASE».
- **Ремонт RPC, которая часто редактируется** разными агентами параллельно (`cron_check_streak_breaks`, `dispatch_with_render`, `render_screen`).
- **Комбинированные правки** — несколько агентов могут одновременно работать на одной функции в разных ветках.
- **Любая RPC `>= 50 строк`**, у которой история — больше одной миграции.

## Когда НЕ нужно

Recipe — overkill для:

- **Маленькие функции (< 50 LOC)**, которые целиком переписываются в файле миграции (например, новый setter `set_user_X` или новая helper-функция). В таком случае `CREATE OR REPLACE` пишется с нуля — нечему «откатывать».
- **Создание новой функции** (`CREATE FUNCTION`, не `CREATE OR REPLACE`). Snapshot не нужен — базы ещё нет.
- **Срочный rollback** (`DROP FUNCTION` + `CREATE` из known-good source). Здесь явно используется не-prod source — это осознанное действие.

В этих случаях достаточно обычного code review + verify post-apply (`pg_get_functiondef` после apply должен совпасть с тем, что в файле миграции).

---

## Step-by-step recipe

### Step 1 — Snapshot живого прода в файл с timestamp

```python
import os, datetime, psycopg2
from dotenv import load_dotenv
load_dotenv('/Users/vladislav/Documents/NOMS/.env')

func_signature = 'public.process_onboarding_input(bigint, text, jsonb, jsonb, boolean)'
ts = datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')
snapshot_path = f'/tmp/process_onboarding_input_snapshot_{ts}.sql'

with psycopg2.connect(os.environ['DATABASE_URL']) as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT pg_get_functiondef(%s::regprocedure)",
        (func_signature,),
    )
    body = cur.fetchone()[0]

with open(snapshot_path, 'w') as f:
    f.write(body)

print(f'snapshot saved: {snapshot_path} ({len(body)} chars)')
```

> ⚠️ **Сигнатуру нужно указывать с типами аргументов** — `regprocedure` отличает overload-ы. Если функция перегружена, snapshot без аргументов либо не найдёт функцию, либо найдёт другую перегрузку. Перед snapshot — `\df+ public.func_name` или `SELECT proname, pg_get_function_arguments(oid) FROM pg_proc WHERE proname = '...'`.

**Сохрани timestamp** — он попадёт в commit message и в шапку миграции.

### Step 2 — Diff snapshot против git-version (опционально, но **рекомендуется**)

Если функция уже редактировалась в migrations — найди последнюю миграцию, которая её трогала, и сравни тела:

```bash
# Найти последнюю миграцию, трогавшую функцию
grep -l "CREATE OR REPLACE FUNCTION public.process_onboarding_input\|FUNCTION process_onboarding_input" \
  migrations/*.sql | sort -V | tail -1

# Diff
diff -u /tmp/process_onboarding_input_snapshot_<ts>.sql migrations/178_fix_onboarding_lang_picker_no_changing_language.sql
```

**Что искать в diff:**

- ❓ **Расхождения в теле функции** между snapshot и последним git-файлом — флаг. Возможно:
  - Кто-то правил функцию **вне миграций** (через Supabase Studio напрямую) — это anti-pattern в проекте, нужно расследовать;
  - Миграция **не была применена**, но в файле есть;
  - Параллельный агент применил свою миграцию **между** твоим планированием и snapshot — нужно прочитать его файл и понять, не конфликтует ли с твоей правкой.
- ✅ **Snapshot и git совпадают** — можно работать.

> ⚠️ Если diff большой и непонятный — **STOP, спроси координатора** или прочитай свежие `daily/*.md` за последние 2-3 дня. Возможно, твоя задача уже частично сделана другим агентом.

### Step 3 — Записать snapshot timestamp + commit SHA в commit message и шапку миграции

В **шапке миграции** (комментарий после `-- Migration NNN`):

```sql
-- Migration 178: process_onboarding_input — корректная смена языка в онбординге
--
-- База функции: pg_get_functiondef(161473) живого прода 2026-05-06 14:32 UTC,
--                length=24407 chars, OID 161473.
-- Stale-base правило (KB: safe-create-or-replace-recipe.md): СТРОГО pg_get_functiondef
--   живого прода, НЕ файл из репо.
-- Параллельная активность: проверены daily/2026-05-05 и daily/2026-05-06 — нет
--   незакрытых работ на process_onboarding_input.
```

В **commit message**:

```
fix(onboarding): rewrite process_onboarding_input language switch

base: pg_get_functiondef from prod 2026-05-06 14:32 UTC, length=24407 chars
related: mig 173 (push_nav onboarding_welcome), mig 175 (FSM goal→speed)
fixes: 3rd stale-base regression case (changing_language ghost status)
```

**Зачем:** если регрессия повторится — будущий агент сможет проверить, какая версия была в проде в момент твоего snapshot, и откуда расхождение.

### Step 4 — ПОВТОРНЫЙ snapshot ПЕРЕД apply (критический шаг)

Между Step 1 и моментом apply может пройти 30 минут — несколько часов (написание миграции, review). За это время другой агент мог применить свою миграцию на ту же функцию. Поэтому:

```python
# Прямо перед `apply` миграции:
with psycopg2.connect(os.environ['DATABASE_URL']) as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT pg_get_functiondef(%s::regprocedure)",
        (func_signature,),
    )
    fresh_snapshot = cur.fetchone()[0]

with open(snapshot_path) as f:
    original_snapshot = f.read()

if fresh_snapshot != original_snapshot:
    print('🛑 STOP — функция изменилась с момента snapshot!')
    print('   Кто-то применил миграцию параллельно. Не применяй свою!')
    print(f'   Сравни: diff {snapshot_path} <(echo "$fresh_snapshot")')
    raise SystemExit(1)

print('✅ snapshot still fresh — apply OK')
```

**Если разные** — НЕ применяй миграцию. Вместо этого:

1. Сохрани свежий snapshot отдельно (`/tmp/<func>_snapshot_<NEW_ts>.sql`).
2. Прочитай diff между старым и свежим snapshot — пойми, что добавил параллельный агент.
3. **Перепиши свою миграцию** — твои изменения теперь должны накладываться на свежую базу, а не на старую.
4. Повтори Steps 1-4.

> ⚠️ **Пропуск Step 4 — главная причина всех трёх случаев в NOMS.** Не пропускай его, даже если snapshot был сделан «5 минут назад». 5 минут хватает чтобы другой агент успел применить миграцию.

### Step 5 — Apply через psycopg2 в transaction

```python
with psycopg2.connect(os.environ['DATABASE_URL']) as conn:
    conn.autocommit = False
    cur = conn.cursor()
    try:
        with open(f'migrations/{NNN}_<name>.sql') as f:
            cur.execute(f.read())
        conn.commit()
        print('✅ migration applied')
    except Exception as e:
        conn.rollback()
        print(f'🛑 ROLLBACK: {e}')
        raise
```

Если миграция упала — `ROLLBACK` гарантирует, что прод остался в состоянии **до** apply (т.е. в состоянии snapshot из Step 4). Никакого frankenstein-state.

### Step 6 — Verify post-apply

```python
with psycopg2.connect(os.environ['DATABASE_URL']) as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT pg_get_functiondef(%s::regprocedure)",
        (func_signature,),
    )
    new_body = cur.fetchone()[0]

# Проверь что наши изменения в проде
assert 'нашa новая ветка cmd_lang_uk' in new_body, \
    'STOP — наши изменения не попали в прод!'

# Сохрани post-apply snapshot для следующих агентов
with open(f'/tmp/<func>_snapshot_AFTER_{NNN}.sql', 'w') as f:
    f.write(new_body)

print(f'✅ verify ok — new body {len(new_body)} chars')
```

**Зачем:** убедиться, что `CREATE OR REPLACE` действительно применился (не упал на каком-то DDL до него) и что наша версия — в проде. Без этого шага можно жить в иллюзии «деплой прошёл», пока следующий агент не обнаружит проблему.

---

## Anti-patterns — НЕ делай так

❌ **Брать snapshot ИЗ git-файла** (`migrations/161_phase4_onboarding_headless.sql` или любого другого). Этот файл — **зафиксированный момент прошлого**. Между ним и сейчас могло пройти 5 миграций, которые модифицировали ту же функцию.

❌ **`CREATE OR REPLACE` на основе памяти / снапшота из прошлой сессии**. Даже снапшот пятиминутной давности — устаревший, если за это время другой агент успел применить миграцию (Step 4 — об этом).

❌ **Apply без verify post-apply** (Step 6). Можно деплоить и думать, что всё ок, пока пользователь не сообщит о баге. Verify занимает 2 секунды.

❌ **Параллельные миграции от разных агентов на одну функцию без координации**. Если ты видишь свежий handover или daily-log, где другой агент трогал ту же функцию — координируйся через ребейз/merge на main, не делай свою миграцию изолированно.

❌ **Хранить snapshot в БД** (типа отдельной таблицы `function_snapshots`). PostgreSQL уже хранит prosrc в `pg_proc` — `pg_get_functiondef` это и читает. Дополнительная таблица — overhead и потенциальный второй источник правды (= источник конфликтов).

❌ **`\!` PostgreSQL command для shell-out** (например, чтобы автоматически сохранять snapshot через `\!`). В Supabase pooler это **не работает** — нет shell-доступа. Snapshot делается из Python через psycopg2.

❌ **Заблокировать функцию через `LOCK TABLE`**. PostgreSQL не lock'ит функции — он lock'ит **таблицы** (rows). На уровне `pg_proc` гарантия атомарности `CREATE OR REPLACE` уже есть (DDL statement = свой commit), но **не** взаимного исключения с другим агентом, который применит свой `CREATE OR REPLACE` секундой позже.

❌ **`BEFORE UPDATE` trigger на `pg_proc`**. PostgreSQL не имеет триггеров на системных каталогах. Не пытайся защитить функции от перезаписи через триггер — этот путь закрыт.

❌ **`pg_dump` для одной функции** — overkill. `pg_get_functiondef` отдаёт ровно то, что нужно, в одной строке.

❌ **`CREATE OR REPLACE FUNCTION` при изменении signature без DROP старой версии** (Lesson 2026-05-14, mig 224 → 226 hotfix). PostgreSQL `CREATE OR REPLACE FUNCTION` **не заменяет** функцию когда signature другая — он создаёт **отдельную перегрузку**. Старая остаётся.

Симптом: после `CREATE OR REPLACE public.foo(bigint, boolean)` (новая) старая `public.foo(bigint)` (mig N-1) **остаётся в pg_proc**. Вызов `SELECT public.foo(123)` падает:
```
ERROR: 42725: function public.foo(integer) is not unique
HINT: Could not choose a best candidate function. You might need to add explicit type casts.
```

**Fix:** добавь `DROP FUNCTION IF EXISTS public.foo(<old_signature>);` ПЕРЕД `CREATE OR REPLACE` (или в той же мигре сразу после CREATE). Проверь через `SELECT pg_get_function_identity_arguments(oid) FROM pg_proc WHERE proname='foo'` что осталась ровно одна перегрузка post-apply.

Если signature не меняется (только тело) — DROP не нужен, `CREATE OR REPLACE` работает корректно.

Pre-mig checklist для signature change: какие callers есть в коде (`grep -rn "rpc_caller(\"foo\""` Python, `EXECUTE 'SELECT.*foo'` SQL, n8n nodes)? Все ли они работают с новым DEFAULT'ом? Иначе нужны два шага: (1) deploy новой версии + старая остаётся → callers переезжают postpone, (2) DROP старой когда все callers перевести.

---

## Пример — гипотетическая правка `set_user_age`

Допустим, нужно ужесточить валидацию: вместо `13 <= age <= 100` сделать `16 <= age <= 100` (взрослые пользователи только).

```python
# Step 1 — snapshot живого прода
import os, datetime, psycopg2
from dotenv import load_dotenv
load_dotenv('/Users/vladislav/Documents/NOMS/.env')

ts = datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')
snap_path = f'/tmp/set_user_age_snapshot_{ts}.sql'
with psycopg2.connect(os.environ['DATABASE_URL']) as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT pg_get_functiondef('public.set_user_age(bigint, integer)'::regprocedure)"
    )
    body = cur.fetchone()[0]
with open(snap_path, 'w') as f:
    f.write(body)
print(f'saved {len(body)} chars to {snap_path}')

# Step 2 — diff против git
# (manual: bash -c "diff -u $snap_path migrations/142_set_user_age.sql")
# Допустим diff чистый — git и прод совпадают.

# Step 3 — пишем migrations/199_tighten_age_validation.sql
# ── шапка миграции:
#   База функции: pg_get_functiondef('public.set_user_age(bigint, integer)')
#   живого прода 2026-05-07 12:00 UTC, length=1842 chars.
#   Изменение: 13 → 16 lower bound.
# ── тело миграции — копия snapshot с одним изменением (13 → 16) в IF.

# Step 4 — повторный snapshot прямо перед apply
with psycopg2.connect(os.environ['DATABASE_URL']) as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT pg_get_functiondef('public.set_user_age(bigint, integer)'::regprocedure)"
    )
    fresh = cur.fetchone()[0]
with open(snap_path) as f:
    if fresh != f.read():
        raise SystemExit('🛑 функция изменилась — переписать миграцию')

# Step 5 — apply
with psycopg2.connect(os.environ['DATABASE_URL']) as conn:
    conn.autocommit = False
    cur = conn.cursor()
    with open('migrations/199_tighten_age_validation.sql') as f:
        cur.execute(f.read())
    conn.commit()

# Step 6 — verify
with psycopg2.connect(os.environ['DATABASE_URL']) as conn:
    cur = conn.cursor()
    cur.execute(
        "SELECT pg_get_functiondef('public.set_user_age(bigint, integer)'::regprocedure)"
    )
    new_body = cur.fetchone()[0]
assert 'p_age < 16' in new_body, 'наша правка не попала в прод'
print('✅ done')
```

---

## Helper: `scripts/safe_create_or_replace.py`

Для автоматизации Steps 1, 2, 4, 6 — есть helper в `scripts/`:

```bash
# 1. Snapshot перед написанием миграции:
python3 scripts/safe_create_or_replace.py snapshot \
  'public.process_onboarding_input(bigint, text, jsonb, jsonb, boolean)'
# Saves to /tmp/process_onboarding_input_snapshot_<ts>.sql, prints path.

# 2. Verify snapshot freshness прямо перед apply:
python3 scripts/safe_create_or_replace.py verify-fresh \
  /tmp/process_onboarding_input_snapshot_<ts>.sql \
  'public.process_onboarding_input(bigint, text, jsonb, jsonb, boolean)'
# Exit 0 = fresh, exit 1 = drift detected (refuse apply).

# 3. Verify post-apply (после миграции):
python3 scripts/safe_create_or_replace.py verify-after \
  'public.process_onboarding_input(bigint, text, jsonb, jsonb, boolean)' \
  --contains 'нашa новая ветка cmd_lang_uk'
# Exit 0 = changes deployed, exit 1 = rollback or stale.
```

См. файл `scripts/safe_create_or_replace.py` (~80 LOC, без зависимостей кроме psycopg2 + python-dotenv, уже установленных в проекте).

---

## Связанные KB articles

- **[phase4-onboarding-migration.md](phase4-onboarding-migration.md)** — gotcha #19 описывает третий случай stale-base (mig 175 откатил mig 173). Хорошее чтение для понимания, как stale-base ломает FSM на проде.
- **[pre-migration-discovery-recipe.md](pre-migration-discovery-recipe.md)** — Phase 0 protocol перед миграциями. Stale-base правило упомянуто в gotchas-таблице (последняя строка); этот recipe — расширение.
- **[n8n-data-flow-patterns.md](n8n-data-flow-patterns.md)** — аналогичная проблема для n8n PUT API (правило «GET перед PUT»). Та же идея: брать актуальное состояние **прямо перед** применением, никогда — заранее закэшированное.
- **[n8n-multi-agent-workflow-editing.md](n8n-multi-agent-workflow-editing.md)** — координация между параллельными агентами (включая правки SQL функций).

## Чек-лист (для копипаста в commit message)

```
[ ] Step 1 — snapshot saved: /tmp/<func>_snapshot_<ts>.sql
[ ] Step 2 — diff против git: clean / drift расследован
[ ] Step 3 — base ts + length записан в шапку миграции и commit
[ ] Step 4 — повторный snapshot прямо перед apply: matches Step 1
[ ] Step 5 — apply в transaction (commit/rollback)
[ ] Step 6 — verify post-apply: наши изменения в pg_get_functiondef
```

---

> ⚠️ **Если на ревью этого commit нет одного из пунктов чек-листа — reviewer обязан запросить explanation.** Три случая stale-base в проекте — это уже паттерн, не случайность. Отдельный пункт в release-protocol при merge PR с миграциями RPC.
