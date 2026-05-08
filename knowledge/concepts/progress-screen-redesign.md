---
title: "Progress Screen Redesign"
aliases: [progress-redesign, build-progress-text, progress-inline]
tags: [n8n, ui, progress, migrations, gamification]
sources:
  - "daily/2026-04-14.md"
created: 2026-04-14
updated: 2026-04-14
---

# Progress Screen Redesign

Редизайн экрана Progress (inline) в рамках обновления геймификации: новые иконки, Premium-маркер, формат отображения стрика и маны, личность Sassy Sage в инсайтах. Standalone workflow `08_Progress` деактивирован — Progress теперь встроен исключительно в `04_Menu`.

## Key Points

- **Migration 064** (`064_progress_redesign.sql`): обновлены иконки, добавлены 3 новых translation key, `buttons.friends` переименован в 13 языках (Friends→Squad, Друзья→Банда)
- **Premium header:** у премиум/пробных пользователей к заголовку добавляется суффикс 👑; мана отображается как "Безлимит" вместо 500/500
- **`08_Progress` standalone деактивирован:** устаревший workflow оставлен как резерв, но не удалён; Progress обслуживается только через `Build Progress Text (inline)` в `04_Menu`
- **Parse mode HTML:** `Send Progress (inline)` переключён с Markdown на HTML (несовместимость была из-за `Build Progress Text` генерирующего HTML-разметку)

## Details

### Migration 064

**Изменения `app_constants`:**
- `icon_friends`: 🎁 → 👥 (группа людей)
- `icon_streak`: 🏆 → 🔥 (огонь, паттерн Duolingo — было дублирование с `icon_league`)
- `icon_premium`: 👑 добавлен как новая константа

**Новые translation keys (× 13 языков):**
- `progress.level_label` — метка уровня
- `progress.mana_unlimited` — "Безлимит" для премиум-пользователей
- `progress.streak_days` — "дн." / "days" и т.д.

**Переименование кнопки (× 13 языков):**
- `buttons.friends`: Friends → Squad, Друзья → Банда, Friends → Bande (fr), Amigos → Banda (es), и т.д.

**Обновлённые инсайты (× 13 языков):** три ключа получили Sassy Sage-личность:
- `insight_leader`: "Crown's looking good on you. Don't let it slip."
- `insight_xp_gap`: "Only {gap} XP to #{rank}? One snack and {name} is toast."
- `insight_no_league`: "No league yet? Monday's your shot."

### Изменения n8n 04_Menu — `Build Progress Text (inline)`

Полностью переписан JavaScript для генерации Progress-экрана:

**Формат для Premium/Trial пользователей:**
- Заголовок: `🚀 Твой Прогресс 👑` (суффикс берётся из `icon_premium`)
- Стрик + мана на одной строке: `🔥 Стрик: 9 дн.  |  🧪 Мана: Безлимит`
- Уровень добавлен к строке XP: `🌟 Ур 17 — XP: 4685  |  💎 390`
- Инсайт с префиксом `💬` (маркер личности)

**Исправления иконок (fallback в коде):**
- `icon_mana` fallback: 🔋 → 🧪 (зелье, согласно migration 027)
- `icon_friends` fallback в кнопках: 🎁 → 👥

**Parse mode:** HTML (inline)

### Финальный рендер (Premium, ru)

```
🚀 Твой Прогресс 👑

🔥 Стрик: 9 дн.  |  🧪 Мана: Безлимит
🌟 Ур 17 — XP: 4685  |  💎 390

🏆 Лига: 🥒 Огурчик

💬 Корона тебе идёт. Не урони.
```

Кнопки: `[📜 Квесты] [🏆 Лига] / [👥 Банда] [🛒 Магазин]`

### Деактивация `08_Progress` standalone

Standalone workflow `08_Progress` был деактивирован (deprecated):

**Причины:**
1. Использовал `parse_mode: Markdown` вместо HTML — несовместимо с `Build Progress Text`
2. Не передавал `subscription_status` в Merge Data — Premium-маркер не работал
3. Двойная нагрузка на поддержку — любое изменение Progress нужно было делать дважды

**Решение:** Progress встроен непосредственно в `04_Menu` → `Build Progress Text (inline)` → `Edit Progress (inline)`. Standalone workflow оставлен как backup и может быть удалён в будущем.

## Related Concepts

- [[concepts/day-summary-ux]] — get_day_summary RPC, аналогичный подход к статистике
- [[concepts/xp-model]] — XP, NomsCoins, Mana экономика отображаемые на Progress
- [[concepts/n8n-stateful-ui]] — editMessageText, parse_mode HTML паттерны
- [[concepts/n8n-template-engine]] — двойные скобки `{{icon_xxx}}`, fallback-значения
- [[concepts/league-npc-system]] — иконки лиги, отображаемые на Progress-экране
- [[concepts/squad-referral-screen]] — кнопка "Банда" на Progress ведёт на Squad-экран

## Sources

- [[daily/2026-04-14.md]] — Migration 064: иконки, translations, Sassy Sage инсайты; `Build Progress Text (inline)` переписан; деактивация `08_Progress`; parse_mode HTML fix
