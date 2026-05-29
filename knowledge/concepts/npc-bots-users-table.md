---
title: "NPC bots живут в `users` table — `is_bot=true` + telegram_id `-1XXX`"
aliases: [npc-bots, league-npc-users, is-bot-filter, fake-users]
tags: [data-layer, gamification, anti-pattern, league, sql-discipline]
sources:
  - "MEMORY.md project_npc_bots_league.md (canonical topic file)"
  - "users.is_bot column (mig refs in users schema baseline)"
  - "daily/2026-05-29.md (Nutritionist Agent 10 obnaružil + zafiksiroval)"
created: 2026-05-29
status: active
severity: data-discipline
---

# NPC Bots в `users` Table

> **TL;DR.** 119 NPC-ботов сидят в `users` рядом с настоящими юзерами для фичи «Лиги». Маркер — `users.is_bot = true`. У них **отрицательный telegram_id** формата `-1XXX` (`-1100..-1199` диапазон). **Любой** `SELECT COUNT(*) FROM users` или GROUP BY без `WHERE is_bot=false` искажает реальность на ≈30%.

## Кто это

8 лиг (Onion → Lotus). В каждой должно быть достаточно competitors, иначе weekly ranking outwit'ит юзера (он один в лиге → автоматически 1-е место без challenge). NPC-боты заполняют лиги синтетическими игроками с псевдослучайным XP-генератором.

Это **не Telegram-боты** (не реагируют на webhook'и). Это просто строки в БД, которые `cron_process_league_week` обновляет каждый понедельник.

## Идентификация

| Признак | Значение |
|---|---|
| `is_bot` | `true` (**канонический маркер, используй ЭТО**) |
| `telegram_id` | негативный 4-значный (`-1100..-1199` сейчас, 119 штук) |
| `status` | всегда `'new'` (не проходят онбординг) |
| `league_id` | 1..8 (распределены по всем лигам) |
| `last_active_at` | НЕ обновляется при cron-генерации XP |
| `first_name` | человеческие имена (Volodymyr, Chiara, Omar B., Catarina, ...) — для immersion |

**`telegram_id::text` имеет 5 символов** из-за `-` префикса — `LENGTH(telegram_id::text)=5` не отличает NPC от реальных юзеров с 5-значным id. Полагайся на `is_bot`.

## Bot-specific колонки в `users` (НЕ имеют смысла у real users)

| Колонка | Назначение |
|---|---|
| `is_bot` | bool marker |
| `bot_weekly_seed` | seed для воспроизводимости weekly XP |
| `bot_xp_base_offset` | базовое значение XP |
| `bot_xp_per_day` | XP rate per day |
| `bot_xp_rate_min` | нижняя граница random rate |
| `bot_xp_rate_max` | верхняя граница random rate |

Все это используется `cron_process_league_week` (понедельник 12:00 UTC) для генерации weekly XP NPC-ботам с distribution соответствующей лиге. См. KB [[concepts/league-npc-system]] для детали (если ещё актуальна — проверь через NLM).

## Типичные ошибки агентов

### 1. `SELECT COUNT(*) FROM users` без фильтра
**Симптом:** «Я думал у нас 1000+ юзеров, по факту active last 7d = 5 real».
**Реальность:** total `users` rows ≈ NPC bots + real users. NPC dominate count.

### 2. Распределение по `language_code` без фильтра
**Симптом:** распределение языков выглядит как 30% uk, 25% it, 20% ar — потому что у NPC `language_code` назначены при создании от seed.
**Фикс:** `WHERE is_bot = false`.

### 3. Анализ `status='new'` без фильтра
**Симптом:** «92 active 'new' за неделю — у нас огромный funnel!»
**Реальность:** NPC все `status='new'` (никогда не онбордятся). Real `status='new'` last 7d = 2.

**КОНКРЕТНЫЙ КЕЙС (2026-05-29):** Nutritionist agent 10 при первом аудите Stage 7 cutover написал «active users last 7d = 97». При фильтре `is_bot=false` оказалось **5 real users**. Решение в Stage 7 global cutover это не изменило (всё равно нужно было промоутить), но `cron_process_league_week` UAT-ы / engagement metrics / churn analysis — ВСЁ искажалось.

### 4. `WHERE last_active_at IS NULL` для «не приходили никогда»
**Симптом:** попадают NPC ботов, потому что cron не обновляет `last_active_at` (он апдейтит только `bot_xp_*` поля).
**Фикс:** `WHERE last_active_at IS NULL AND is_bot = false`.

## Safe-запросов шаблоны

```sql
-- Real users only (canonical)
SELECT COUNT(*) FROM users WHERE is_bot = false;

-- Active real users last 7 days
SELECT COUNT(*) FROM users
WHERE is_bot = false
  AND last_active_at > NOW() - INTERVAL '7 days';

-- Real users status breakdown
SELECT status, COUNT(*) FROM users
WHERE is_bot = false GROUP BY status ORDER BY 2 DESC;

-- Language distribution real users only
SELECT language_code, COUNT(*) FROM users
WHERE is_bot = false GROUP BY 1 ORDER BY 2 DESC;

-- Bots for league diagnostics (rare, when investigating league NPC)
SELECT telegram_id, league_id, bot_xp_per_day, first_name
FROM users WHERE is_bot = true ORDER BY league_id, telegram_id;
```

## Python side

В webhook-пути `is_bot=true` юзеров **не должно появляться** (NPC webhooks не генерируют). Если в `dispatcher/forward.py` или `handlers/` приходит ctx с `is_bot=true` — это аномалия (тестовый fixture, ошибочный INSERT, прямое API-обращение). Обычно безопасно `return` без обработки.

`food_logs`, `daily_modifiers`, `notification_log` — у NPC отсутствуют (cron не пишет в эти таблицы для ботов). Поэтому aggregations по этим таблицам безопасны без `is_bot` filter (NPC естественно отфильтровываются JOIN'ом).

## Что НЕ делать

- ❌ Удалять NPC-ботов «для чистоты данных» — это сломает feature «Лиги»
- ❌ Создавать новых NPC через UI/handlers — они генерятся через отдельный seeding скрипт
- ❌ Отображать NPC в `cmd_show_meals`, my_day, history — они не имеют intake data, будет пусто/null
- ❌ Включать NPC в emails, push notifications — у них нет Telegram chat

## Связано с

- [[concepts/league-npc-system]] — XP-генерация, distribution по лигам (если актуально)
- [[concepts/xp-model]] — общая XP economy (real users)
- topic file `project_npc_bots_league.md` — дублирует основные facts на стороне memory
