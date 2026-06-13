---
title: "Handover 2026-06-13 — PR #400 reminder-digest LIVE, что делать дальше"
aliases: [handover pr400, reminder digest followup, notification mode redesign brief]
created: 2026-06-13
session-output: "PR #400 (mig 506) + KB hub [[reminder-types-inventory]]"
---

# Handover — после PR #400 (admin reminder-digest)

Брифинг для следующего агента. Полная картина — KB hub [[reminder-types-inventory]].

## Что закрыто в этой сессии

| PR | Что | LIVE |
|---|---|---|
| **#381** (mig 498) | waist_retrofit i18n + honest framing | ✅ merged |
| **#382** (mig 499) | day_close `{meals_needed}` fix | ✅ merged |
| **#400** (mig 506) | admin reminder-digest cron + KB hub + CI guard | ⏳ open, mig applied LIVE |
| spawn `task_4e91bf82` | maternal soft-landing popup (mig 504 / PR #393) | open независимо |
| spawn `task_729b31c3` | 13-lang audit всех cron-push'ей | работает в отдельном окне |

## Что ждёт владельца на merge

1. **PR #400** — финальный обзор + merge. Auto-deploy перезапустит `noms-cron`. Первый tick дайджеста — **next 09:00 UTC после merge**. Проверь админ-чат.
2. **PR #393** (maternal soft-landing) — после merge'a в RPC `cron_get_reminder_digest_payload` можно удалить INFO rule `maternal_modifier_orphan_promise` (станет obsolete). Не P0, сделать в следующей маленькой миграции.

## Что зафиксировано в KB для будущей работы

[[reminder-types-inventory]] (🔥 HUB) — полная таблица 19 cron'ов с promise/actual/audience/honors-mode/risk колонками. **Главный артефакт сессии.** Любой будущий cron-аудит начинается оттуда. CI guard `pr-cron-inventory.yml` + `CRON_JOBS` dict в `main.py` enforce'ят consistency.

## 🔴 P1 tech-debt (рекомендую следующие 1-2 сессии)

### 1. `notifications_mode` redesign — продуктовое решение + код

**Problem.** UI тринарный (Zen/Balanced/Beast), code бинарный (zen vs не-zen). Из 9 user-facing cron'ов только 2 уважают настройку. Лейбл «Zen — тихо, только вечером» не реализован (нет time-filter в RPC).

**Что нужно решить с owner + Номсом:**
- Beast vs Balanced — что они делают по-разному? Beast = +stress/sleep checkin? Balanced = только meal-цикл? Совсем другое?
- Zen «только вечером» — реально делать (добавить `evening_hour BETWEEN 18 AND 21` фильтр), или поменять лейбл на «полная тишина»?
- Какие из 7 standalone-cron'ов должны добавить zen-уважение (subscription_lifecycle / league_* / streak_check / trial_expiry)?

**Что делать когда план есть:**
- Миграция в `cron_get_*_candidates` RPC'ах с фильтром по `notifications_mode` + (если zen-evening) тайм-фильтром
- Обновить `streak_frozen_pusher` логику если нужно
- Дайджест автоматически перестанет показывать `zen_mode_uncovered_by_cron` для добавленных cron'ов

### 2. `notification_log` coverage — добавить INSERT во все user-facing cron'ы

**Problem.** Дайджест слепой к: `subscription_lifecycle`, `trial_expiry`, `streak_check` milestones, `referral_unlock`, `ton_payment_check`. За последние 7 дней их пуши не видно в `notification_log` (или они не пишут, или не шлют — нужна проверка).

**Что делать:**
- Для каждого из 5 cron'ов: найти место в Python (или в RPC) где происходит send, добавить `INSERT INTO notification_log (telegram_id, notif_type, sent_at) VALUES (...)`. Использовать осмысленные `notif_type`: `subscription_dunning_d7`, `trial_downgrade`, `streak_milestone_30`, `referral_activated`, `ton_payment_confirmed`.
- Обновить KB hub таблицу — колонка «writes to notification_log?» с ❌ на ✅.
- В mig 506 при необходимости добавить новые типы в `v_zen_honoring` (если эти cron'ы должны уважать zen — см. P1 #1) — но это уже после #1 redesign.

### 3. Подозрительные luteal-class в group B (audit needed)

**KB hub § "Known gaps" #2** перечисляет cron'ы, которые обещают действие в тексте — но не проверено, делают ли они его. Кандидаты на ручной audit:
- `trial_expiry` — обещает «I'll downgrade you» — реально downgrade'ит `subscription_status` в БД?
- `subscription_lifecycle` D-7/D-3/D-1 — обещает «I'll auto-downgrade» — RPC реально проводит downgrade?
- `referral_unlock` — обещает «+N coins escrow unlocked» — реально начисляет coins?

Метод audit'а тот же что для luteal/waist:
1. Прочитать текст в `ui_translations.cron_notifications.<key>` на всех 13 langs
2. Прочитать Python в `crons/<cron>.py` + RPC body через `pg_get_functiondef`
3. Сравнить: что текст обещает vs что реально пишется в БД
4. Если расхождение — выпустить миграцию по образу mig 491 (luteal cron реально пишет модификатор).

## 🟡 Менее приоритетные

- **`last_active_at` self-bump для inactivity** (KB hub § "Known gaps" #5) — проверить, обновляется ли поле на outgoing-cron-пушах. Если да — inactivity-юзер никогда не превзойдёт 3-day порог.
- **Daily digest content tuning** — после первых нескольких реальных tick'ов выяснить, какие срезы реально полезны, какие шум. Например `age_unknown` высокий для всех типов (NULL birth_date у тестовых юзеров) — возможно убрать из render'а.
- **Phase-aware Sage commentary** заблокирован (РПП по cycle_phase) — остаётся в roadmap.

## Что НЕ делать

- Не пытайся «починить» `notifications_mode` без продуктового разговора с owner+Номсом. Это не bug, это UX-стейтмент vs implementation gap. Сначала решение, потом код.
- Не удаляй `zen_mode_uncovered_by_cron` INFO rule из mig 506 — она останется полезной даже после P1 #1 redesign'а (там же покажет cron'ы которые **всё ещё** не уважают mode, если что-то останется out-of-scope).

## Связанные KB

- [[reminder-types-inventory]] — главный hub
- [[cron-user-local-tz-pattern]] — почему `timezone='UTC'` per-trigger
- [[cron-reminder-suppression-tunables]] — pattern «настройки cron'а в app_constants, не в RPC body»
- [[adaptive-modifiers-architecture]] — suppressions (maternal_exclusion, teen_stress_escalate) в `apply_daily_modifier`
- [[release-protocol]] § Confirmation 2026-06-13 — incident-факт что PR Sanity Audit поймал stale-base после rebase в начале сессии (не перед push'ом)
