---
title: "League UX v2 — Duolingo-style Smart Leaderboard"
aliases: [league-ux-v2, smart-list-v2, build-leaderboard-v2, league-zones, tamagotchi-avatars]
tags: [n8n, gamification, leagues, ux, migrations]
sources:
  - "daily/2026-04-16.md"
created: 2026-04-16
updated: 2026-04-16
---

# League UX v2 — Duolingo-style Smart Leaderboard

Редизайн экрана лиги (migration 067): Smart List v2 с визуальными зонами повышения/понижения, тамагочи-аватарками из `app_constants`, онлайн-индикатором и CTA-кнопкой. Бот получил v6-формулу с "ленивыми днями" и спайками, имитируя поведение реальных людей.

## Key Points

- **`get_league_standings` v6**: боты больше не растут линейно — daily multiplier 0.3x (lazy) / 1.0x (normal) / 1.4x (active) / 1.8x (spike); `last_seen_hours_ago` (фейковое, hash-based 0-11h, меняется каждый час)
- **Smart List v2 — 8-12 строк вместо 4:** promote zone (top-5) + separator + mid-zone neighbors + separator + demote zone (bottom-3)
- **Тамагочи-аватарки** (🥚🐣🐥🐔🦅🦉🐉) рядом с именами из `app_constants` (ключи `stage_emoji_*`) — нет хардкода
- **Визуальные зоны:** `— 🟢 Зона повышения —` / `— 🔴 Зона понижения —` из переводов (`league.promote_zone` / `league.demote_zone`)
- **🟢 онлайн-индикатор** рядом с участниками у которых `last_seen_hours_ago < 2`
- **CTA-кнопка** `[📸 Записать еду]` (`cmd_add_food`) под лидербордом — конверсия из лиги в логирование
- **04_Menu выросла до 101 ноды** (была 99); Python: добавлен `league_midweek.py` + `main.py` зарегистрировал 3 league jobs

## Details

### get_league_standings v6 — Bot Spikes

До v6 боты росли предсказуемо: `base_offset + weekly_rate * days`. Пользователи замечали паттерн, интерес снижался. В v6 каждый бот получает ежедневный тип активности:

| Тип | Множитель | Описание |
|-----|-----------|---------|
| lazy | 0.3x | "Ленивый день" — мало логов |
| normal | 1.0x | Обычный день |
| active | 1.4x | Активный день |
| spike | 1.8x | Всплеск активности |

Тип дня определяется через `hashtext(telegram_id::text || current_date::text)` — детерминированно (одинаково для всех, но меняется каждый день). Это создаёт видимость человеческого поведения: бот может "лениться" два дня и потом дать спайк.

`last_seen_hours_ago` — псевдо-поле для ботов: `hashtext(telegram_id::text || date_part('hour', now())::text) % 12` даёт значение 0–11, меняется каждый час. Для реальных пользователей — реальная разница от `last_active_at`.

**Верификация v6 (2026-04-16):** Nina S показала 660 XP, Leo M — 675, что свидетельствует о разных дневных паттернах спайков (раньше Leo M всегда был выше). Поле `stage` возвращается корректно. ✅

### Smart List v2 — структура лидерборда

До v2: 4 строки (top-4 + пользователь). Неинформативно, нет контекста зоны.

После v2 (8-12 строк):

```
— 🟢 Зона повышения —
🥚 1. Leo M          🟢  675 XP
🐣 2. Nina S         🟢  660 XP
🐥 3. Vladislav      ★   421 XP   ← жирный, без "(ТЫ)"
🐔 4. Kenji Y             390 XP
🦅 5. Maria L             310 XP
—————————————————————
🦉 7. Chen X              201 XP   ← соседи пользователя
🦉 8. David K             189 XP
—————————————————————
— 🔴 Зона понижения —
🐉12. Anna V              98 XP
🐉13. Mark T              71 XP
🐉14. Yuki P              43 XP
```

**Правила отображения:**
- Promote zone: всегда top-5 (места 1–5)
- Mid-zone: до 3 соседей вокруг текущего пользователя (если пользователь не в зоне)
- Demote zone: всегда bottom-3 (последние 3 места)
- Строка пользователя: жирный шрифт (`<b>`), символ `★` вместо "(ТЫ)"
- Разделители — строки из переводов `league.promote_zone` / `league.demote_zone`

**Тамагочи-аватарки:** берутся из `app_constants` по ключу `stage_emoji_{N}` где N = stage пользователя из `get_league_standings`. Стадии: 0=🥚, 1=🐣, 2=🐥, 3=🐔, 4=🦅, 5=🦉, 6=🐉. Отражают XP-прогресс всей истории, не только текущей недели.

**Онлайн-индикатор:** 🟢 добавляется к имени если `last_seen_hours_ago < 2`. Создаёт ощущение живой конкуренции.

### CTA-кнопка под лидербордом

Inline keyboard под лидербордом содержит одну кнопку:

```json
[{ "text": "📸 Записать еду", "callback_data": "cmd_add_food" }]
```

Логика: пользователь смотрит на лидерборд → видит что проигрывает → кнопка сразу конвертирует его в лог еды. Кнопка присутствует всегда, независимо от позиции.

### n8n 04_Menu — 101 нода

Migration 067 потребовала изменений только в JS-коде ноды `Build Leaderboard`, в нодах не добавлялось — только JS логика переписана.

Новые Python файлы:
- `crons/league_midweek.py` — `LeagueMidweekCron(BaseCron)`, см. [[concepts/league-fomo-push]]
- `main.py` — зарегистрированы 3 league jobs: `league_cycle` (Пн 12:00), `league_midweek` (Ср 19:00), `league_fomo` (каждый час, Sunday filter внутри RPC)

### Translation keys добавленные в migration 067

| Ключ | Описание | Пример (RU) |
|------|---------|-------------|
| `league.promote_zone` | Разделитель зоны повышения | "— 🟢 Зона повышения —" |
| `league.demote_zone` | Разделитель зоны понижения | "— 🔴 Зона понижения —" |
| `league.midweek_push` | Midweek уведомление | "Середина недели! Ты #{rank} в {league}. Не сбавляй!" |

Ключ `league.midweek_push` содержит плейсхолдеры `{rank}` и `{league}`.

## Related Concepts

- [[concepts/league-npc-system]] — get_league_standings v6 bot spikes; is_bot; shadow bot; hashtext formula
- [[concepts/league-fomo-push]] — Sunday FOMO + midweek push — три touchpoint'а вовлечённости
- [[concepts/xp-model]] — stage_emoji_* тамагочи стадии связаны с XP progression
- [[concepts/n8n-stateful-ui]] — editMessageText, inline keyboards, parse_mode HTML
- [[concepts/supabase-db-patterns]] — migration 067, sargable queries

## Sources

- [[daily/2026-04-16.md]] — Migration 067: get_league_standings v6 (bot spikes, last_seen), Smart List v2 (zones, tamagotchi, CTA), 3 league jobs в main.py; верификация Nina S/Leo M спайки ✅
