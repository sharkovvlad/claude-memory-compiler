---
title: "Reminder + cron-notification inventory (источник правды по всем user-facing cron'ам)"
aliases: [reminder inventory, cron inventory, notification inventory, digest source]
tags: [cron, reminders, observability, audit, hub]
sources:
  - "main.py"
  - "crons/__init__.py"
  - "crons/reminders.py"
  - "migrations/506_reminder_digest_rpc.sql"
  - "daily/2026-06-08.md"
  - "daily/2026-06-09.md"
  - "daily/2026-06-12.md"
created: 2026-06-12
updated: 2026-06-12
---

# Reminder + cron-notification inventory (HUB 🔥)

Полный реестр всех cron-задач, которые **могут отправить сообщение пользователю**. Источник правды для дайджеста (`cron_get_reminder_digest_payload`, mig 506) и для отлова luteal-class багов («текст обещает X, код делает Y; пуш ушёл не той аудитории»).

> **Правило для агентов:** при добавлении нового `scheduler.add_job(...)` в `main.py`, который шлёт что-то юзеру, **обязательно добавь запись в эту таблицу в том же PR**. CI-страховка `pr-cron-inventory.yml` сравнивает зарегистрированные id с этим документом + с реестром `CRON_JOBS` в `main.py`. Расхождение блокирует merge.

## Snapshot (2026-06-12)

**19 cron-задач всего** в `main.py` `scheduler.add_job(...)`. Из них:
- **9 могут писать пользователю** (1 `reminders` с 11 ветками + 8 standalone) — таблица ниже.
- **10 серверные** (мана-regen, GDPR-анонимизация, FX, инфра-мониторинг, stars_digest [в админ-чат], etc.) — здесь не отслеживаются, но перечислены в § "Server-only crons".

## A. `reminders` cron (1 cron, 11 сценариев)

Один scheduler job `reminders` (hourly :20) внутри ветвится по 11 типам через `cron_get_reminder_candidates(p_reminder_type text)`. Все варианты пишут в `notification_log` через `cron_log_notifications_sent`. Все уважают `notifications_mode != 'zen'` (бинарный фильтр: zen=тихо vs всё-остальное=полный шквал; **Balanced и Beast обрабатываются одинаково** — это marketing-vs-code mismatch, см. § "Known gaps").

| # | reminder_type | local hour | tz-gate | premium-only? | audience filter (упрощённо) | what text promises | what cron really does | risk of false delivery |
|---|---|---|---|---|---|---|---|---|
| A1 | `meal_morning` | 09 (catch-up 10) | ✅ | нет | `meals_today=0`; NOT (freeze pending/used); NOT (premium AND h=9 AND нет sleep-модификатора) | «доброе утро, залогируй завтрак» — invite | invite, не пишет в БД | низкий: нейтрально |
| A2 | `meal_lunch` | 13 | ✅ | нет | `meals_today < 2` | «время обеда, не забудь залогировать» — invite | invite | низкий |
| A3 | `meal_dinner` | 19 | ✅ | нет | `meals_today < 3` | «время ужина» — invite | invite | низкий |
| A4 | `day_close` | 20 | ✅ | нет | `meals_today BETWEEN 1 AND 2` | «закрываем день, отдыхаем» — invite | invite | низкий (после mig 499 — раньше «Just 0 more» из-за `{meals_needed}=0`) |
| A5 | `streak_warning` | 21 | ✅ | нет | `current_streak ≥ 1 AND meals_today = 0` | «серия под угрозой, залогируй сегодня» | предупреждение, не действие | низкий |
| A6 | `quest_reminder` | 18 | ✅ | нет | есть незакрытые квесты сегодня | «у тебя есть невыполненные квесты» | invite + inline-кнопка на Quests | низкий |
| A7 | `inactivity` | 12 | ✅ | нет | `last_active_at < now()-3d` + dedup 3d | «соскучилась, покажи тарелку» | нейтральный poke | низкий, но проверь что `last_active_at` не апдейтится нашими отправками |
| A8 | `sleep_checkin` | 09 | ✅ | **да** (`user_has_active_access`) | нет sleep-модификатора сегодня; mute-окно после food_log | «нажми кнопку — подкручу макросы» | при tap → `apply_daily_modifier(sleep, ...)`. Без maternal/teen-фильтра в кандидатах. Кб-фоллбэк (если screen_keyboards пусто) → текст без кнопок | средний: maternal recipients увидят обещание, при tap получат soft-landing (mig 504) |
| A9 | `waist_retrofit` | 14 | ✅ | условно | `phenotype='obese' AND waist_circumference IS NULL` | «премиум-апгрейд: пришли обхват, пересчитаю по RFM» (mig 498) | приглашение ввести талию; cron не пересчитывает сам | низкий после mig 498 (раньше — английский на 13 langs + ложное «refine your plan») |
| A10 | `stress_checkin` | 18 | ✅ | **да** | нет stress-модификатора сегодня; mute-окно | «нажми — пересчитаю план» | при tap → `apply_daily_modifier(stress, level)`. teen/maternal суппрессит через `apply_daily_modifier`, но кандидат не фильтруется | средний: то же что A8 |
| A11 | `luteal_morning` | 08 | ✅ | **да** | `cycle_day BETWEEN 15 AND 28` через `compute_cycle_day_for_user` (которая сама гейтит gender='female' + cycle_tracking_enabled + NOT pregnant/lactating + age<55 + cycle_start_date IS NOT NULL) | «+{kcal_delta} ккал на лютеиновой фазе» | После mig 491 cron вызывает `apply_daily_modifier('luteal', luteal_phase)` ПЕРЕД отправкой. `applied=false` → текст НЕ шлётся | низкий (закрыто mig 490 + mig 491 + mig 494) |

## B. Standalone user-facing crons (8 шт)

| # | job_id (main.py) | расписание (UTC если не указано) | tz-gate | honors `notifications_mode`? | premium-only? | what it sends | writes to `notification_log`? | risk class |
|---|---|---|---|---|---|---|---|---|
| B1 | `freeze_pusher` | hourly :15, delivers local ≥9 | ✅ | ✅ только `<> zen` | нет | «использовали freeze ❄️, серия спасена» (через `streak_frozen` notif_type) | ✅ да (`streak_frozen`) | низкий |
| B2 | `streak_check` | hourly :05 | НЕ имеет (детекция в час 0 — внутри RPC) | ❌ нет | нет | milestone-награды (`streak_milestone_*`), pending freeze flags | возможно (нужна проверка — см. § "Known gaps" #4) | средний — pending freeze setup, рассылка через B1 |
| B3 | `trial_expiry` | hourly :15, RPC tz-gates local 9..21 | ✅ через RPC | ❌ нет | trial-only | trial soft-downgrade пуш + `trial_expired_*` варианты | неизвестно — нужна проверка | средний: возможен luteal-class gap (текст обещает downgrade, RPC реально его делает?) |
| B4 | `subscription_lifecycle` | daily 12:00 UTC (14:00 Madrid) | ❌ нет (fires for all in one UTC tick) | ❌ нет | premium-only | dunning D-7 / D-3 / D-1, `payment_failed`, `subscription_cancelled` | неизвестно | средний: дополнительно tz-gap (часть юзеров получит в 04:00 local) |
| B5 | `league_process` | Mon 12:00 UTC | ❌ нет | ❌ нет | нет | недельные результаты лиги: `league_promoted`, `league_demoted`, `league_stayed`, NPC-рассылка | возможно | низкий: контент стандартный |
| B6 | `league_midweek` | hourly :30, RPC filters Wed + local hour | ✅ через RPC | ❌ нет | нет | mid-week-стэндинги | ✅ да (`league_midweek`) | низкий |
| B7 | `league_fomo` | hourly :25, RPC filters Sun + local hour | ✅ через RPC | ❌ нет | нет | воскресный FOMO лиги | ✅ да (`league_fomo`) | низкий |
| B8 | `ton_payment_check` | every 5 minutes | ❌ нет (по требованию) | ❌ нет | n/a | подтверждение TON-платежа (`payment_activated`, mig 500) | возможно | низкий: контент строго транзакционный |

## C. Server-only crons (10 шт — для справки, не пишут юзерам)

| job_id | расписание | purpose |
|---|---|---|
| `mana_regen` | hourly :00 | восстанавливает ману, сбрасывает дневные счётчики |
| `referral_unlock` | hourly :10 | разблокировка escrow (может слать «реферал активирован» — нужна проверка, см. § Known gaps #5) |
| `data_retention` | daily 03:00 UTC | GDPR-анонимизация удалённых юзеров |
| `safety_guard_resolver` | daily 03:15 UTC | auto-resolve safety touch-points |
| `webhook_health` | every minute | мониторинг HTTPS edge, fallback в n8n при 3 fails |
| `webhook_url_monitor` | every minute | алерт админу если URL дрейфит |
| `stars_digest` | daily 06:30 UTC | агрегат по Stars в **админ-чат** (не юзерам) |
| `fx_rate_update` | daily 16:00 UTC explicit | ECB EUR/USD snapshot для амбассадорской комиссии |
| `reminder_digest` (новый, mig 506) | daily 09:00 UTC explicit | ЭТО — дайджест по reminder/cron-push'ам в **админ-чат** |

## Known gaps (то самое что должен ловить дайджест)

### Gap 1: `notifications_mode` mechanism is binary, UI promises trinary

- UI кнопка «Как мне тебя пинать?» предлагает Zen / Balanced / Beast.
- Reality: только `cron_get_reminder_candidates` и `cron_get_freeze_notification_candidates` уважают `notifications_mode <> 'zen'`. Balanced и Beast обрабатываются **идентично**.
- 7 из 8 standalone-cron'ов **не уважают** настройку вообще.
- Лейбл «Zen — тихо, только вечером» обещает evening-only — реальность = полная тишина для reminders+freeze, но dunning / league / streak пройдут даже в zen.
- **Дайджест ловит:**
    - CRITICAL `zen_mode_breached` — zen-юзер получил пуш через reminder/freeze (никогда не должно быть).
    - INFO `zen_mode_uncovered_by_cron` — zen-юзер получил пуш через subscription/league/streak (cron не уважает настройку).
- **Open для redesign-сессии** (не сделано в этой PR): unify Beast vs Balanced (что они должны делать по-разному?), zen-evening-only (реально или сменить копи?), добавить zen-уважение в league/subscription.

### Gap 2: «Что обещает текст vs что cron реально делает» — luteal-class

Исторический шаблон ([daily 2026-06-08](../daily/2026-06-08.md)): cron-уведомление обещало «I added +175 kcal», но `apply_daily_modifier` не вызывался — `daily_modifiers` пуст за 30 дней, цели не двигались. Закрыто mig 491.

Аналогично закрыто:
- mig 498: `waist_retrofit` (текст «refine your plan» → cron не пересчитывает) → переписан в честную форму
- mig 499: `day_close` плейсхолдер `{meals_needed}` всегда `0` → удалён

**Подозрительные оставшиеся** (требуют ручной аудит, не закрыто в этой PR):
- `trial_expiry`: что текст обещает / что cron реально делает с `subscription_status`?
- `subscription_lifecycle` D-7 / D-3 / D-1: обещает «I'll auto-downgrade» — реально downgrade-ит?
- `referral_unlock`: «escrow разблокировано, +N coins» — реально начисляет?

### Gap 3: `notification_log` coverage неполная

Пишут точно: `reminders` (через `cron_log_notifications_sent`), `freeze_pusher`, `league_midweek`, `league_fomo`. Видно в последних 7 днях.

**Не видно в notification_log за последние 7 дней:**
- `trial_expiry` — пуши были (1 trial-юзер существует) или их не было? Если были — почему нет в логе?
- `subscription_lifecycle` — dunning ни разу не сработал? Или сработал, но не пишет?
- `streak_check` milestones — был ли milestone достигнут за 7 дней? Не видно.
- `ton_payment_check`, `referral_unlock` — подтверждение/escrow notif'ов нет.

**Дайджест слепой к этим cron'ам.** Если они шлют — мы не увидим. Это P1-tech-debt: до того как полагаться на дайджест в проде, нужно ассертить что каждый cron из таблицы B/C, который потенциально шлёт юзеру, делает `INSERT INTO notification_log` с правильным `notif_type`.

### Gap 4: Phantom keys / orphan keys в `cron_notifications` (mig 502 + дайджест-spawn)

Mig 502 уже дропнул 2 orphan-ключа в `ui_translations.content->cron_notifications`. Аудит на 13-языковое покрытие запущен отдельной сессией (см. [daily 2026-06-12](../daily/2026-06-12.md) raw notes если есть). Дополнительные находки могут породить PR-ы с собственными миграциями.

### Gap 5: `last_active_at` self-bump

Реминдер `inactivity` фильтрует юзеров с `last_active_at < now()-3d`. Если наши собственные отправки обновляют `last_active_at`, инактив-юзер никогда не превзойдёт порог. Открытая проверка: `sync_user_profile` в `webhook_server.py` — где апдейт триггерится. Если на любом наш-исходящем — баг.

## Дайджест-cron'а контракт

**Файл:** `crons/reminder_digest.py`
**Расписание:** daily 09:00 UTC explicit (KB `cron-user-local-tz-pattern` § "Когда UTC требуется явно")
**RPC:** `cron_get_reminder_digest_payload(p_window_hours int default 24)` (mig 506)
**Куда шлёт:** `config.ADMIN_CHAT_ID` (`417002669`)
**Молчит когда:** `total_sent = 0` в окне (matches `stars_digest` pattern)
**Hot-reload kill switch:** `app_constants.reminder_digest_enabled = 'false'` (без redeploy)
**Окно:** `app_constants.reminder_digest_window_hours` (default 24, clamp 1..168)

**Что показывает:**
1. Total messages / distinct recipients / distinct types
2. CRITICAL block — 6 правил (gender_not_female для luteal, maternal_recipient, non_premium для waist, minor для stress, npc_bot для любого, zen_mode_breached для reminder/freeze)
3. INFO block — 2 правила (maternal_modifier_orphan_promise для sleep/stress, zen_mode_uncovered для других cron'ов)
4. Per-type dump (volume + segments: gender / age / tier / mode / maternal / bot)

## Связанные KB-концепты

- [[cron-user-local-tz-pattern]] — биоритмы (когда UTC, когда local-hour gate)
- [[adaptive-modifiers-architecture]] — `apply_daily_modifier` supressions (maternal_exclusion, teen_stress_escalate)
- [[sage-payload-meta-override-pattern]] — META-override в `services/sage.py`
- [[i18n-rpc-audit-pattern]] — phantom keys / fallback EN class
- [[release-protocol]] — §12 git-дисциплина при правках main.py

## История изменений

- **2026-06-08:** luteal-инцидент → mig 490+491+494 → концепт документирован как ground-truth для аудита.
- **2026-06-09:** mig 498 (waist_retrofit) + mig 499 (day_close `{meals_needed}`) — два luteal-class fix.
- **2026-06-12:** mig 506 — дайджест-RPC + Python cron. Этот документ становится hub'ом для всех будущих cron-аудитов. CI-страховка `pr-cron-inventory.yml` + `CRON_JOBS` dict в `main.py` enforce'ят consistency между этой таблицей и реально зарегистрированными scheduler-job'ами.
