---
title: "Migration Deploy Ordering — split additive vs breaking schema changes"
aliases: [deploy-ordering, mig-breaking-change, schema-deploy-race, mig-324-trap]
tags: [deploy, migrations, ordering, race-conditions, ci-cd]
sources:
  - "daily/2026-05-24.md"
created: 2026-05-24
updated: 2026-05-24
---

# Migration Deploy Ordering — additive vs breaking

NOMS deploy pipeline (`deploy.sh` header):
> Prereqs: SQL migrations already run in Supabase SQL Editor.

То есть **миграции и код деплоятся независимо** — это намеренный дизайн. GitHub Actions деплоит только Python код через `rsync + systemctl restart`. Apply миграций — отдельный шаг (psycopg2 или Supabase SQL Editor, обычно вручную).

Это даёт гибкость, но создаёт класс ошибок: **breaking schema change применённый до deploy кода** → live UX ломается на время между apply и deploy.

## Key Points

- **Additive** mig changes (новые tables/columns/RPCs/screens/buttons/translations) — **безопасно** применить до deploy. Старый код их игнорирует.
- **Breaking** mig changes (UPDATE существующей кнопки на новый callback, переименование RPC параметра, удаление колонки) — **обязательно** apply ПОСЛЕ deploy кода, который их поддерживает.
- **Split migrations**: если mig содержит и additive, и breaking → выделить breaking в **отдельный** apply step и явно отметить в PR body `DEPLOY ORDER`.
- **Idempotent UPDATE** для recovery: если перепутал порядок и сделал hotfix-rollback в DB — миграция должна converge re-apply без condition'а, который теперь false.
- **Live mutations через psycopg2 — не нарушение**, если миграция уже в merged PR. Это intended workflow per `deploy.sh`. Нарушение = делать DDL/DML которое НЕ в файле миграции.

## The mig 324 trap (2026-05-24)

Mig 324 содержала:
1. **Additive**: 2 новых screens (`meals_picker`, `meal_action`), 4 RPCs, 3 кнопки meal_action, RU/EN translations
2. **Breaking**: `UPDATE stats_main col 0 SET callback_data = 'cmd_show_meals' WHERE callback_data = 'cmd_edit_last'`

Я применил **всю** миграцию до того как PR #168 (содержащий Python interceptor для `cmd_show_meals`) был merged + deployed. Результат:
- Live DB: `stats_main` col 0 cb = `cmd_show_meals`
- Live code: нет handler для `cmd_show_meals` (старый no-op stub из mig 211)
- Юзер кликает `[Исправить]` → `editMessageText 400 message is not modified`
- **Юзер видит мёртвую кнопку ~30 минут**, пока я не сделал hot-revert

### Recovery pattern

Когда поймал такое — НЕ паниковать. Сделать **минимальный hot-revert** в DB чтобы вернуть UX к предыдущему рабочему состоянию (даже если функционально хуже):

```sql
-- Hot revert на минимум functional UX (правда, single-meal edit only)
UPDATE ui_screen_buttons
   SET callback_data = 'cmd_edit_last',
       meta = jsonb_build_object(
           'save_rpc', 'set_editing_last_meal',
           'target_screen', 'edit_food_prompt',
           'save_via_callback', true
       )
 WHERE screen_id = 'stats_main' AND row_index = 0 AND col_index = 0
   AND callback_data = 'cmd_show_meals';
```

Затем подождать merge + deploy → re-apply breaking UPDATE.

### Idempotent migration fix

Чтобы избежать повтора — **убрать condition `cmd_edit_last`** из миграции:

```sql
-- BAD (conditional — не сработает после hot-revert если мы не вернёмся к cmd_edit_last):
UPDATE ui_screen_buttons
   SET callback_data = 'cmd_show_meals'
 WHERE screen_id='stats_main' AND row_index=0 AND col_index=0
   AND callback_data = 'cmd_edit_last';  -- ← фрагильный predicate

-- GOOD (unconditional — converges к desired state regardless):
UPDATE ui_screen_buttons
   SET callback_data = 'cmd_show_meals',
       meta = '{}'::jsonb
 WHERE screen_id='stats_main' AND row_index=0 AND col_index=0;
```

WHERE keys (`screen_id, row_index, col_index`) уникально идентифицируют ряд → безопасно.

## Pre-flight checklist для нового migration

```
Содержит ли mig:
[ ] CREATE TABLE / CREATE INDEX / ADD COLUMN nullable?           → ADDITIVE — apply anytime
[ ] CREATE OR REPLACE FUNCTION (новая)?                          → ADDITIVE — apply anytime
[ ] INSERT INTO ui_screens / ui_screen_buttons / ui_translations  → ADDITIVE (если screen ещё не виден юзеру)
[ ] UPDATE существующего ui_screen_buttons.callback_data?         → BREAKING — split в отдельный apply ПОСЛЕ deploy
[ ] DROP COLUMN / RENAME COLUMN / RENAME RPC?                     → BREAKING — split в отдельный apply
[ ] CREATE OR REPLACE FUNCTION где сигнатура изменилась?          → BREAKING — split в отдельный apply
[ ] UPDATE существующего ui_translations.{screen}.* где screen уже видим? → BREAKING (UX visible immediate)

Если есть breaking changes:
[ ] PR body содержит секцию `DEPLOY ORDER` с явным порядком: «merge → deploy → apply breaking UPDATE»
[ ] Breaking UPDATE — unconditional (idempotent re-apply возможен)
[ ] Если есть recovery path → описать его в PR body
```

## Where the line is

```
ADDITIVE                                  BREAKING
─────────                                ─────────
CREATE TABLE                       ←→    DROP TABLE
ADD COLUMN nullable                ←→    ADD COLUMN NOT NULL без default
CREATE INDEX (CONCURRENTLY)        ←→    DROP INDEX
CREATE OR REPLACE FUNCTION (новая) ←→    Изменение signature существующей
INSERT INTO ui_screen_buttons      ←→    UPDATE callback_data существующей
                                          UPDATE ui_translations видимого screen
                                          DELETE FROM ui_screen_buttons (если visible_condition'ы соседей зависят)
```

## Related Concepts

- [[concepts/release-protocol]] — общий deploy protocol, force-with-lease etc.
- [[concepts/headless-button-creation-gotchas]] — gotcha 4 (meta copy trap) часто причина «breaking» эффекта
- [[concepts/migration-collision-guard]] — pre-push hook для номеров (другая категория проблем)

## Sources

- [[daily/2026-05-24.md]] — Mig 324 stats_main button rewire был applied до deploy → multi-meal users видели мёртвую кнопку 30 минут. Recovery via hot-revert + idempotent edit в follow-up commit.
