---
title: "Cron user-local timezone pattern (биоритмы)"
aliases: [биоритмы, ночные пуши, scheduler timezone, MSK quirk, tz-gate]
tags: [cron, ux, timezone, tech-debt]
sources:
  - "daily/2026-06-08.md"
  - "main.py"
created: 2026-06-08
updated: 2026-06-08
---

# Cron user-local timezone pattern (биоритмы)

Как делать cron'ы, шлющие сообщения юзерам в разных часовых поясах, чтобы никому не прилетело ночью.

## Принцип

**Не привязывай cron к одному UTC-времени для всех юзеров.** У NOMS-аудитории часовые пояса от Лос-Анджелеса (UTC−7) до Сиднея (UTC+10) — любой фиксированный UTC-час кому-то будет ночью.

**Правильно:** cron жужжит **каждый час**, а внутри RPC фильтрует юзеров по их **local hour**:

```sql
WHERE EXTRACT(HOUR FROM (now() AT TIME ZONE users.timezone)) BETWEEN 9 AND 21
```

Тогда московскому юзеру письмо прилетает в 10:00 MSK, лосанджелесскому — в 10:00 PT, серверный UTC-час становится неважен.

## Cron'ы которые ПРАВИЛЬНО юзают паттерн

| Cron | Расписание | RPC tz-gate |
|---|---|---|
| Reminders (meal/streak/quest/sleep/stress/luteal) | hourly | local hour 9..21 |
| Trial Expiry | hourly :15 | local hour 9..21 |
| Freeze Notification Pusher | hourly :15 | deliver если local-time ≥ 9 утра |
| League FOMO (Sunday) | hourly :25 | RPC фильтрует по local Sunday + hour |
| League Midweek (Wednesday) | hourly :30 | RPC фильтрует по local Wednesday + hour |

Эти cron'ы **timezone-agnostic** на уровне scheduler'а: жужжат каждый час, RPC решает кому что слать.

## Cron'ы которые НЕ юзают паттерн (🟡 tech-debt)

| Cron | Расписание | Проблема |
|---|---|---|
| **Subscription Lifecycle** | daily 12:00 UTC (реально 09:00 UTC из-за scheduler MSK quirk) | шлёт dunning **всем** активным юзерам без tz-фильтра → LA получает в 02:00 ночь ❌ |
| **League Weekly Cycle** | Monday 12:00 UTC (реально Mon 09:00 UTC) | шлёт **всем** еженедельные результаты лиги в один момент |

**Решение (open tech-debt):** переделать оба на hourly + добавить tz-gate в RPC по образу `cron_get_reminder_candidates`. Это не quick-fix миграции scheduler timezone — это **архитектурный refactor** двух RPC: их надо превратить из «один прогон в день обрабатывает всех» в «hourly прогон обрабатывает только тех у кого сейчас правильный local-час и они ещё не получили на этой неделе/дне».

## Когда tz-gate НЕ нужен

- **Cron не шлёт сообщения юзерам.** Data Retention, Safety Guard auto-resolve, FX Rate Update — server-side cleanup/data, юзер не видит.
- **Cron шлёт в админ-чат.** Stars Daily Digest — owner получает в свой удобный час, не нужно fan-out по часовым поясам.
- **Cron жёстко привязан к внешнему UTC-событию.** Например FX Rate Update **обязан** стрелять после ECB publish 14:15 UTC — здесь UTC-time не свобода, а требование внешнего источника.

## Scheduler timezone quirk (MSK)

VPS работает в `Europe/Moscow` (`/etc/localtime → /usr/share/zoneinfo/Europe/Moscow`). `AsyncIOScheduler(timezone="UTC")` в `main.py` **unhonor'ится** для cron jobs без explicit per-trigger timezone:

```
Subscription Lifecycle: next run at 2026-06-09 12:00:00+03:00  ← MSK, не UTC
Data Retention:         next run at 2026-06-09 03:00:00+03:00  ← MSK
Stars Daily Digest:     next run at 2026-06-09 06:30:00+03:00  ← MSK
```

Комментарии в коде говорят «UTC», логи показывают MSK. **Все ежедневные cron'ы стреляют на 3 часа раньше намеченного.**

Это **давно** так. Менять глобально на UTC = сдвинуть всё на 3 часа, что может сломать привычки owner'а (Stars Digest сейчас приходит в 06:30 MSK; после fix будет 09:30 MSK).

**Когда сама природа cron требует точного UTC** (как мой FX rate cron — внешний ECB-event в 14:15 UTC) — явно передавай `timezone='UTC'` в `CronTrigger`, это перебивает scheduler default:

```python
CronTrigger(hour=16, minute=0, timezone='UTC')  # ← explicit override
```

Не пытайся починить весь scheduler одной строкой — поломаешь привычки.

## Anti-pattern: чинить биоритмы через scheduler TZ

Соблазн: «переведу scheduler с MSK на UTC и проблема ночных пушей решится». **Нет.** Это просто сдвинет момент рассылки на 3 часа — юзеры в LA как получали ночные пуши от Subscription Lifecycle, так и будут получать, просто в другое время ночи.

Биоритмы — это **per-user local hour filter в RPC**, не scheduler trigger time.

## Related

- [[release-protocol]] — деплой сервисов, рестарт `noms-cron`
- [[cron-silent-failure-alerting]] — алерты при failure cron'ов
- Subscription Lifecycle RPC — кандидат на refactor под этот паттерн
- League Weekly Cycle RPC — кандидат на refactor под этот паттерн
