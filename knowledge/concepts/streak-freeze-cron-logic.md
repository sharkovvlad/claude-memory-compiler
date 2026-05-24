---
title: "Streak / Freeze Cron Logic — last_log_date vs last_active_at + Milestone Unified"
aliases: [streak-cron-fix, last-streak-kept-date, last-log-date-vs-active, streak-freeze-cron, mig-187, streak-milestones, mig-205, mig-206]
tags: [cron, streak, gamification, supabase, bug-fix, architecture, stickers, channel-c]
sources:
  - "daily/2026-05-08.md"
  - "daily/2026-05-09.md"
  - "daily/2026-05-12.md"
created: 2026-05-08
updated: 2026-05-12
---

# Streak / Freeze Cron Logic — `last_log_date` vs `last_active_at`

Архитектурный фикс в cron `cron_check_streak_breaks` (мигр. 187): переход с `last_active_at` на `last_log_date` как дискриминатор для streak-событий, плюс новая колонка `last_streak_kept_date` для корректного продолжения стрика после freeze.

## Key Points

- **`last_active_at`** обновляется при **любом** касании бота (callback, меню, profile click, language switch) — НЕ только при логе еды. Использование для streak-cron означает: юзер мог не есть 5 дней, но один раз открыть профиль → cron его пропускал.
- **`last_log_date`** обновляется **только** при фактическом `log_meal_transaction` — единственный корректный дискриминатор для «юзер записал еду сегодня».
- **`last_streak_kept_date`** (новая колонка, мигр. 187) — **cron-owned**, записывается только `cron_check_streak_breaks` при списывании freeze. `log_meal_transaction` это поле **НЕ трогает**. Нужно для anchor: после freeze-save юзер должен видеть продолжение стрика, а не обнуление.
- **`log_meal_transaction v5`** блок Streaks использует `v_streak_anchor = GREATEST(last_log_date, COALESCE(last_streak_kept_date, '0001-01-01'))` — streak продолжается от более позднего из двух событий (лог или freeze-save).
- **p95 latency** `log_meal_transaction` post-fix: 53.9 ms (на ~12 ms бизнес-логики сверх 42 ms baseline RTT). Никакой регрессии.

## Details

### Цепочка обнаружения (08.05.2026)

Жалоба тимлида (tid=417002669): (1) freeze не списывается при многодневном пропуске логов; (2) стрик упал до 1 при max_streak=27.

**Bug A (cron):** `cron_check_streak_breaks` v3 фильтровал кандидатов по `last_active_at::date < today - 1`. Юзер мог не логировать еду 5 дней, но один раз кликнуть по профилю → `sync_user_profile` обновлял `last_active_at` → cron видел свежий timestamp → пропускал юзера. Streak freeze никогда не списывался, break никогда не срабатывал.

Подтверждено логами VPS: после починки мигр. 167 (ambiguity fix, 04.05) каждый час `Streak check: 0 frozen, 0 broken` на протяжении 4 дней — нулевая работа для cron, хотя в БД были юзеры с реальным gap.

**Bug B (RPC):** `log_meal_transaction` блок 7 (Streaks) — ELSE-ветка обнуляла `current_streak=1` при `gap > 1`, не учитывая ни `streak_freezes`, ни факт того что cron мог сохранить стрик через freeze. Юзер логировал еду после нескольких дней → streak=1 вместо продолжения.

**Bug C (исторический):** 02-04.05 cron падал HTTP 400 (PG 42702 ambiguous `streak_freezes` — stale-base regression мигр. 042→166→167). У юзера 417002669 в эти дни был gap → freezes не списывались до починки, накопились пропущенные ночи.

### Решение — мигр. 187

```sql
ALTER TABLE users ADD COLUMN last_streak_kept_date DATE;
-- Backfill: last_streak_kept_date = last_log_date для существующих юзеров с логами
```

**`cron_check_streak_breaks v4`:** оба CTE (`freeze_candidates`, `break_candidates`) переключены на `last_log_date < today_in_tz - 1` вместо `last_active_at`. При списывании freeze дополнительно `SET last_streak_kept_date = today_in_tz - 1`.

**`log_meal_transaction v5`:** блок Streaks теперь:
```sql
v_streak_anchor := GREATEST(
    v_user.last_log_date,
    COALESCE(v_user.last_streak_kept_date, '0001-01-01'::DATE)
);
-- Далее логика: today - v_streak_anchor = 1 → +1, = 0 → unchanged, > 1 → new streak
```

Семантика `+1 / unchanged / 1` не меняется — меняется только источник «когда был последний день стрика».

### Архитектурное правило

**Для streak-логики НИКОГДА не использовать `last_active_at`**. Это поле — про любую активность в боте, не про лог еды. Для всех cron'ов и UI-индикаторов streak → `last_log_date`. Для freeze-continuation → `last_streak_kept_date`.

| Поле | Кто пишет | Что означает | Для streak? |
|---|---|---|---|
| `last_active_at` | `sync_user_profile`, `debounce_user_action`, любой touch | Любая активность юзера в боте | **НЕТ** |
| `last_log_date` | `log_meal_transaction` | Последний фактический лог еды | **ДА** — основной anchor |
| `last_streak_kept_date` | `cron_check_streak_breaks` ТОЛЬКО | Когда cron «спас» streak через freeze | **ДА** — secondary anchor |

### Ownership rule

`last_streak_kept_date` — поле **принадлежит ТОЛЬКО** `cron_check_streak_breaks`. Никакой другой код его не должен писать. Если появится новая RPC, сохраняющая стрик помимо лога еды (например, ручная компенсация админом), она должна писать `last_streak_kept_date = today_in_tz - 1`, а не `last_log_date`.

### Лиги — проверено, багов нет

Подозрение «лига Chili не демоутила» оказалось недоразумением: юзер 417002669 перешёл в Chili через промоушн, текущая неделя ещё идёт (`is_processed=false`), обработка в Пн 12:00 UTC. Логика `cron_process_league_week` (мигр. 011/042/166) корректна: top-5 → promote, bottom-5 → demote, для группы 20.

### Тесты

4 интеграционных теста через SAVEPOINT/ROLLBACK (zero prod side-effects):
- T1: лог вчера → streak +1.
- **T2 (ключевой):** freeze-saved continuation — `last_streak_kept_date` anchor работает.
- T3: long-gap → новый streak.
- T4: cron-фильтр на `last_log_date` с negative control.

5 league-тестов:
- L1-L5: NPC-only, Onion/Lotus edge cases, real user promoted, idempotency.

## Anti-patterns

- **`last_active_at::date` для streak-решений** — любая UX-активность маскирует пропущенные логи.
- **Direct `WHERE last_log_date IS NULL`** для «не логировал» — не проверяет last_streak_kept_date.
- **Двойная запись `last_streak_kept_date`** из разных RPC — нарушает single-writer principle, race condition.
- **EXPLAIN вместо SELECT для smoke-test cron RPC** — EXPLAIN не ловит runtime column ambiguity (урок мигр. 167).

## Связанные концепты

- [[concepts/cron-silent-failure-alerting]] — мигр. 167 ambiguity fix + BaseCron alerting (root cause Bug C).
- [[concepts/xp-model]] — streak как компонент 3-tier геймификации (XP + NomsCoins + Mana).
- [[concepts/league-npc-system]] — league logic, NPC bots, `cron_process_league_week`.
- [[concepts/safe-create-or-replace-recipe]] — stale-base regression цепочка (мигр. 042→166→167), из-за которой cron падал 02-04.05.
- [[concepts/anti-spam-debounce]] — `last_active_at` vs `last_action_ms` (аналогичная проблема: одно поле для двух целей).
- [[concepts/smart-freeze-notification-delivery]] — **follow-up** мигр. 191: UX-delivery freeze-уведомления (Hybrid D: cron ставит pending-флаг, доставка утром или при первом взаимодействии, anti-spam с meal_morning).

## Streak Milestone Unified (mig 205 + 206, 2026-05-12)

Duolingo-style серия streak milestones: coin reward + sticker push (Channel C) на порогах **3/7/14/30/100** (заменяет старые 25/50/75/100 coin-only). Каждый новый стрик пере-стреляет серию: при break cron чистит `stickers_shown` → юзер может получить те же стикеры заново.

### Mig 205 — Data seed (6 rows `bot_stickers`)

Channel C rows для streak milestones + healed (quest-based recovery). Только `streak_milestone_3` с реальным `file_id` и `is_active=true`, остальные 5 — placeholder `TODO_*` с `is_active=false`. Активация placeholder → одна SQL-команда `UPDATE bot_stickers SET file_id='<real>', is_active=true WHERE sticker_key='streak_milestone_N'`, эффект через ≤60с TTL кэша `services/stickers_cache`.

### Mig 206 — Cron + translations + mark_sticker_shown RPC

**`app_constants` rewards (геометрическая прогрессия):** `streak_milestone_coins_3=5 / 7=15 / 14=30 / 30=75 / 100=500`.

**`cron_check_streak_breaks` v5 (CREATE OR REPLACE из stale-base live):**
- При `current_streak → 0` чистит ключи `streak_milestone_*` из `users.stickers_shown` (Duolingo-style reset — каждая новая серия начинает серию заново).
- Старые пороги 25/50/75 deprecated (app_constants сохранены для audit-aux).

**`mark_sticker_shown(p_telegram_id, p_sticker_key) → boolean` — новый RPC:**
- Атомарный insert-if-absent в `users.stickers_shown` JSONB.
- `TRUE` = впервые показали (caller пушит стикер + coin reward). `FALSE` = уже было (skip).
- Заменяет client-side read-modify-write через `coin_transactions` SELECT (race-safe).

**`crons/streak_checker.py` — rewrite `_check_milestones`:**
- `MILESTONE_COIN_KEYS = {3, 7, 14, 30, 100}`.
- Per-streak guard через `mark_sticker_shown` RPC (не `coin_transactions`).
- Sticker lookup через `services.stickers_cache.lookup(category)` (Channel C). Placeholder `TODO_*` → text-only (graceful skip).
- Per-milestone translation keys (`cron_notifications.streak_milestone_3/7/14/30/100/healed` × 13 langs = 78 переводов).
- `telegram.send_batch` с `sticker_file_id` (sticker → text sequential await, Channel C ADR 0001 contract).

**Тесты (13 passed):**
- 8 unit (MILESTONE_COIN_KEYS replacement, sticker lookup TODO guard / real / None, happy path, already-shown skip, placeholder text-only, legacy thresholds not queried).
- 5 integration (mark_sticker_shown atomic, cron clears keys on break, app_constants values, 78 translations).

**p95:** `cron_check_streak_breaks` 205ms, `mark_sticker_shown` 100ms (Mac RTT; VPS estimate ~70ms / ~40ms).

**Поведение для existing юзеров:** юзеры на streak 25-29 при деплое — НЕ получат backfill за 25. Получат milestone 30 когда дойдут. Юзер на streak 100 — получит 100 (ключа `streak_milestone_100` в `stickers_shown` ещё нет).

## Related Concepts

- [[concepts/xp-model]] — streak как компонент 3-tier геймификации (XP + NomsCoins + Mana).
- [[concepts/league-npc-system]] — league logic, NPC bots, `cron_process_league_week`.
- [[concepts/safe-create-or-replace-recipe]] — stale-base regression цепочка (мигр. 042→166→167), из-за которой cron падал 02-04.05.
- [[concepts/anti-spam-debounce]] — `last_active_at` vs `last_action_ms` (аналогичная проблема: одно поле для двух целей).
- [[concepts/smart-freeze-notification-delivery]] — **follow-up** мигр. 191: UX-delivery freeze-уведомления (Hybrid D: cron ставит pending-флаг, доставка утром или при первом взаимодействии, anti-spam с meal_morning).
- [[concepts/ui-stickers-headless]] — Channel C cron-side integration, `bot_stickers` single source of truth, `services/stickers_cache` shared cache.
- [[concepts/sticker-architecture-adr]] — ADR 0001, Channel C семантика push-стикеров.

## Sources

- [[daily/2026-05-08.md]] — Session «streak/league bug investigation»: мигр. 187, `last_streak_kept_date` колонка, cron v4 switch на `last_log_date`, `log_meal_transaction` v5 dual-anchor `GREATEST(last_log_date, last_streak_kept_date)`, 4+5 integration tests, p95 53.9ms, data fixture восстановления 417002669.
- [[daily/2026-05-09.md]] — Session «Smart Freeze Notifications»: мигр. 191, follow-up по UX-доставке (pending_freeze_notification_at + 2 канала + anti-spam). Также session «Phase 4 onboarding hotfixes»: мигр. 190 fix `set_user_training_type` FSM advance (связан — обнаружен при streak-investigation UAT).
- [[daily/2026-05-12.md]] — Mig 205 (streak milestone stickers seed — 6 Channel C rows) + mig 206 (streak milestone unified — cron rewrite на пороги 3/7/14/30/100, `mark_sticker_shown` RPC, Duolingo-style reset при break, 78 переводов, 13 tests).
