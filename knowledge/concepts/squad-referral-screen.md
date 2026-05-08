---
title: "Squad Referral Screen"
aliases: [squad-screen, friends-screen, referral-ui, cmd-friends-info, banда]
tags: [n8n, ui, referral, squad, migrations]
sources:
  - "daily/2026-04-14.md"
  - "daily/2026-04-16.md"
created: 2026-04-14
updated: 2026-04-16
---

# Squad Referral Screen

Экран "Твоя Банда" (Squad) — первый UI для реферальной системы NOMS. Реферальная механика была полностью реализована в БД ещё в Phase 1; этот экран впервые делает её видимой пользователям. Включает инфо-экран "Как работает Банда?" с 4 шагами.

## Key Points

- **Migration 066** (`066_squad_referral_screen.sql`): обновлён `get_referral_info` RPC (добавлен `paid_referral_count`), 4 новых `app_constants` иконок, 13 новых translation keys × 13 языков
- **Реферальная система готова с Phase 1:** весь backend (RPCs, translations, escrow) существовал — Squad screen лишь впервые открывает его для пользователей
- **Навигация:** Progress → [👥 Банда] → Squad stats → [Подробнее] → Info (4 шага) → [Назад] → Squad → [Назад] → Progress
- **Parse mode HTML** (был Markdown — мигрировано)
- **Info-экран статический:** не требует RPC, работает только на переводах

## Details

### Migration 066

**Обновление `get_referral_info` RPC:**
- Добавлено поле `paid_referral_count` — количество рефералов, оформивших PRO-подписку; нужно для отображения прогресса к цели "0/4 до бесплатного PRO"

**Новые `app_constants` (иконки):**
- `icon_pending`: ⏳
- `icon_link`: 🔗
- `icon_share`: 📤
- `icon_speech`: 💬

**Переименование (× 13 языков):**
- `referral.title`: "Friends" → "Your Squad", "Друзья" → "Твоя Банда"

**Новые translation keys (13 ключей × 13 языков):**
- `squad_count` — "В банде: {count}"
- `earned_label` — "Заработано: {amount}"
- `pro_goal` — "До бесплатного PRO: {current}/{target}"
- `cta_newbie` — CTA от Noms для пользователей без рефералов (0)
- `cta_active` — CTA от Noms для активных (1+ рефералов)
- `cta_invite` — текст кнопки "Поделиться"
- `info_button` — текст кнопки "Подробнее"
- `info_title` — заголовок инфо-экрана "Как работает Банда?"
- `info_step1..info_step4` — 4 шага объяснения

### Изменения n8n 04_Menu

**Command Classifier:**
- Добавлен маршрут `cmd_friends_info` → route `friends_info`

**Menu Router:**
- Добавлен output `friends_info` (index 23)

**`Build Friends Text` переписан:**
- **Parse mode:** HTML (был Markdown)
- **Блок статистики:** "В банде / Заработано / До бесплатного PRO (0/4)"
- **Реферальная ссылка:** отображается в `<code>` блоке (tap-to-copy в Telegram)
- **Sassy CTA от Noms:** два варианта в зависимости от активности:
  - `cta_newbie` (0 рефералов) — мотивирующий призыв
  - `cta_active` (1+ рефералов) — поддерживающий тон
- **3 кнопки:** Поделиться (URL share), Подробнее (`cmd_friends_info`), Назад

**Новые ноды:**
- `Build Info Text (Friends)` — генерирует статический инфо-текст с 4 шагами из переводов
- `Edit Info Message (Friends)` — editMessageText со статичным инфо-экраном; кнопка [Назад] возвращает на Squad

**`Edit Friends Message`:** parse_mode Markdown → HTML; добавлена кнопка `cmd_friends_info`

### Навигационный флоу

```
Progress
  └→ [👥 Банда] → Squad Screen (stats + CTA + ссылка)
                    ├→ [Поделиться] → telegram.me/share URL (внешний)
                    ├→ [Подробнее] → Info Screen (4 шага, без RPC)
                    │                 └→ [Назад] → Squad Screen
                    └→ [Назад] → Progress Screen
```

### Бэкенд-примечание

Реферальная система была полностью реализована в БД (RPCs, переводы, escrow-механика) ещё в Phase 1. Squad screen — это первый UI, который её открывает. Единственное новое в backend: поле `paid_referral_count` в `get_referral_info`. Escrow (блокировка реферального вознаграждения до первого дня использования рефералом) работал давно — теперь пользователь впервые видит этот прогресс.

### Squad UX v2 (запланировано, 2026-04-16)

Squad/Банда UX v2 спроектирован как 7 независимых units (migrations 068–074). Детали реализации — см. [[concepts/ambassador-payout-system]].

**Ключевые улучшения v2:**
- Unit 1 (migration 068): 6 CTA-вариантов от Sassy Sage с плейсхолдерами `{count}` и `{remaining}`; локализованные суффиксы для счётчика участников
- Unit 2 (migration 069): механика 30-дн. бесплатного PRO за 4 премиум-реферала
- Unit 4 (migration 071): автоматический апгрейд UI при достижении 5 рефералов
- Unit 5 (migration 072): Ambassador Dashboard с RevShare 25%+5%
- Unit 6 (migration 073): система вывода средств (payout_requests таблица + 3 RPC)

## Related Concepts

- [[concepts/xp-model]] — NomsCoins, которые зарабатываются через рефералы
- [[concepts/payment-integration]] — PRO-подписка как цель реферальной программы (0/4 до бесплатного PRO)
- [[concepts/progress-screen-redesign]] — кнопка "Банда" добавлена на Progress-экран в той же сессии
- [[concepts/n8n-stateful-ui]] — editMessageText паттерн, HTML parse_mode, One Menu
- [[concepts/supabase-db-patterns]] — get_referral_info RPC, escrow разблокировка
- [[concepts/ambassador-payout-system]] — Squad v2: ambassador tier, RevShare, payout flow

## Sources

- [[daily/2026-04-14.md]] — Migration 066: paid_referral_count в get_referral_info, 4 новых иконки, Squad translations; `Build Friends Text` переписан; новые ноды Info screen; HTML parse_mode
- [[daily/2026-04-16.md]] — Squad v2 архитектура: 7 units (migrations 068–074), Units 1/2/4/6 запущены параллельно в worktrees; Ambassador Program + RevShare + Payout system
