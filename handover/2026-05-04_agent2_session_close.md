# Handover: Agent 2 (Инспектор Инфраструктуры) — 2026-05-04 close

**Сессия:** worktree `claude/romantic-kilby-f4f44e`
**Длительность:** ~1.5 часа
**Статус:** ✅ MERGED & VERIFIED. Sessions closed.

## Что сделано

### 1. Миграция 166 — фильтр soft-deleted в 9 cron RPC (PR #5, MERGED)

- **Файл:** [migrations/166_filter_deleted_users_in_crons.sql](../../migrations/166_filter_deleted_users_in_crons.sql)
- **Merge commit:** `1b14f35` (2026-05-04T14:27Z, в main)
- **9 функций** покрыты добавлением `AND deleted_at IS NULL` (или `AND u.deleted_at IS NULL` с алиасом):
  - `cron_get_league_fomo_candidates`
  - `cron_check_streak_breaks` (оба CTE)
  - `cron_check_subscription_expiry`
  - `cron_unlock_referral_escrows` (оба алиаса referrer + referred)
  - `cron_process_league_week` (ranking-loop + `v_total` пересчёт)
  - `cron_regenerate_mana`
  - `cron_reset_daily_counters`
  - `cron_get_league_midweek_candidates`
  - `cron_get_renewal_candidates`
- `cron_get_reminder_candidates` уже фильтровал с мигр. 044 — не тронут.
- **Apply:** psycopg2 + DATABASE_URL → atomic `BEGIN; ... COMMIT;` → APPLIED OK.
- **Verify:** все 9 функций имеют ожидаемый filter_count в `pg_get_functiondef`. Проверено дважды (до и после merge).

### 2. Architecture Registry в KB

- **Файл:** [knowledge/concepts/architecture-registry.md](../knowledge/concepts/architecture-registry.md)
- **Index entry** добавлен в [knowledge/index.md](../knowledge/index.md).
- Living-doc «какой target обслуживает Python authoritative, какой fallthrough на legacy n8n». Содержит:
  - Таблицы handlers (Python authoritative: `menu_v3`, `onboarding`)
  - Таблица n8n fallback (add_food / location / payment / pre_checkout / admin_payout / error)
  - Точка входа `webhook_server._route_or_forward → _try_authoritative_path`
  - Флаги фич Variant B с DB column / env override / default
  - Cron jobs section + ссылка на migration 166
- **Не в git** — `claude-memory-compiler/` `.gitignore`'нут (KB — local layer, не shippable).

## Adversarial review важная находка

В `cron_process_league_week` фильтр в ranking-loop без правки `v_total = count(*) FROM league_memberships` сдвигал demote threshold `v_rank > (v_total - 5)`. Реальные юзеры в нижней части группы могли избежать демоута из-за «слотов» удалённых. Зафиксили: `v_total` теперь использует тот же JOIN+filter, что и ranking-loop. Поймано до apply через subagent adversarial review.

`UPDATE users SET league_xp_weekly=0 WHERE is_bot=false` (финальный reset) — намеренно НЕ тронут (idempotent harmless write, не вызывает спама).

## ⚠️ Honest observation «с полей»

На момент merge **реального инцидента не было**:
- `SELECT count(*) FROM users WHERE deleted_at IS NOT NULL` = **0**
- `notification_log` за последние 24h к deleted юзерам = **0** строк
- Активных non-bot юзеров всего 6 (маленькая dev/early-stage база)

Постановка от тимлида звучала как «критический баг — фиксим спам удалённым», но фактически это **preventive defense-in-depth**:
- Phase 4 onboarding только что задеплоился (02.05) → soft-delete recovery flow начинает разогреваться
- Когда юзеры начнут реально удалять аккаунты через `cmd_delete_account` — фильтр уже на месте
- На 31-й день после удаления `cron_anonymize_deleted_users` отработает → попытки писать в анонимизированные строки тоже теперь предотвращены

Фикс правильный и нужный, но это не fire-fighting, а готовность к будущей нагрузке.

## Ad-hoc applied RPC найдены и зафиксированы в миграции

`cron_get_league_midweek_candidates` и `cron_get_renewal_candidates` существовали в проде, но **не имели исходника в `migrations/`** — кто-то применил их ad-hoc (наиболее вероятно через psycopg2 или Supabase Studio). После миграции 166 их актуальные тела теперь в файле как `CREATE OR REPLACE` — следующий migration export будет источником правды.

**Watchlist для агентов:** при апдейте этих 2 RPC в будущем — обновлять и через миграцию (НЕ ad-hoc). Иначе следующая регенерация миграций перезатрёт изменения.

## Watchlist для будущих агентов

1. **Любой новый cron RPC** в `crons/*.py` (через `await supabase.rpc(...)`) — обязательно фильтровать `users.deleted_at IS NULL` в SELECT/UPDATE WHERE. Иначе:
   - Спам soft-deleted юзерам (реальный риск после раскачки delete flow)
   - Лишний compute
   - На 31-й день — попытки writes в анонимизированные строки (cron_anonymize_deleted_users)
2. **Architecture Registry** — обновлять при каждом cutover'е нового target (см. variant-b-cutover): добавить строку в "Python authoritative" таблицу, удалить из "n8n fallback".
3. **`claude-memory-compiler/` .gitignore'нут** — это намеренно. KB живёт локально для координации между агентами, не уезжает в репо.

## Следующие шаги (не входят в эту сессию)

- Дождаться следующего срабатывания каждого cron (mana каждый час, streak :05, subscription 06:00 UTC) и проверить `journalctl -u noms-cron -f` на отсутствие RAISE/exception.
- Когда первый юзер реально удалит аккаунт — спот-чек: его telegram_id не появляется в `notification_log` после удаления.
- Phase 5 (следующий cutover target) — добавить в `TARGET_TO_PATH` + Registry.

## Артефакты

- PR: https://github.com/sharkovvlad/noms-bot/pull/5 (MERGED)
- Merge commit: `1b14f35`
- Daily log: [daily/2026-05-04.md](../daily/2026-05-04.md) (разделы «Миграция 166» + «n8n полный аудит + чистка»)
- Registry: [knowledge/concepts/architecture-registry.md](../knowledge/concepts/architecture-registry.md) (секция 2.1 «Live audit» добавлена)
- Index: [knowledge/index.md](../knowledge/index.md) (новая запись на верхней строке)

## Дополнение: n8n cleanup (после первого закрытия — тимлид отозвал)

**DELETE 5 мёртвых workflows:** 02_Onboarding v1, 06_Indicator_Send, 08.1_Quests, 08.2_League, 08.4_Shop. Применено через sqlite3 на проде. Backup pre-DELETE сохранён: `/home/noms/n8n/backups/database_20260504_1656_pre_delete.sqlite.gz` (28 MB).

**ARCHIVE (НЕ удалены):** 02_Onboarding_v3 (rollback safety net), 08.3_Friends (admin payout dependencies — проверить отдельно).

**FK Gotcha** для будущих агентов: n8n 2.x таблица `workflow_published_version` имеет **RESTRICT** FK на `workflow_entity.id` — блокирует DELETE workflow без предварительного `DELETE FROM workflow_published_version WHERE workflowId = ...`. Также SQLite CLI по умолчанию не enforce FK — нужно `PRAGMA foreign_keys = ON;`. Подробности — в daily log + registry.

**Healthcheck post-DELETE:** все зелёные (`/telegram/health`, n8n `/healthz`, оба systemd сервиса active).

**Lesson learned (для прозрачности):** мой adversarial review мигр. 166 пропустил ambiguity bug в `cron_check_streak_breaks` (унаследован из 042). Агент 3 пофиксил мигр. 167. Smoke через `EXPLAIN` не выявляет runtime ambiguity errors — будущие агенты должны использовать `SELECT public.<fn>()` для actual call даже при ожидаемых 0-row results. Зафиксировано в registry секция 6.
