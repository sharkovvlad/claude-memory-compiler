---
title: "Ambassador & Payout System"
aliases: [ambassador-program, payout-system, revshare, squad-v2, payout-requests]
tags: [referral, payments, gamification, supabase, ambassador]
sources:
  - "daily/2026-04-16.md"
  - "daily/2026-04-16.md (14:18 session)"
created: 2026-04-16
updated: 2026-04-16
---

# Ambassador & Payout System

Squad/Банда UX v2 — расширение реферальной программы до полноценной ambassador-программы с RevShare (25%+5%), системой вывода средств и ручным одобрением CEO. Разбито на 7 независимых units (migrations 068–074).

## Key Points

- **RevShare 25%+5%:** базовая комиссия 25% + 5% бонус за активных рефералов (ambassador tier)
- **`payout_requests` таблица** (migration 073): ledger заявок на вывод средств — не авто-выплата, только запись
- **3 новых RPC:** `get_ambassador_balance()`, `request_payout()`, `admin_review_payout()` — полный цикл вывода
- **Ручное одобрение:** заявки падают в закрытый admin-чат Telegram (chat_id `417002669`), CEO одобряет вручную — никаких авто-выплат
- **`min_payout_amount = 10` USD** записан в `app_constants`
- **7 units (migrations 068–074)** — независимые параллельные разработки; Units 1, 2, 4, 6 запущены в изолированных worktrees 2026-04-16

## Details

### Архитектура 7 units

| Unit | Migration | Содержание | Статус (2026-04-16) |
|------|-----------|-----------|---------------------|
| 1 | 068 | Локализованные суффиксы + 6 CTA-вариантов | В worktree ✅ |
| 2 | 069 | Механика 30-дн. награды (бесплатный PRO за 4 реферала) | В worktree ✅ |
| 3 | 070 | Push-уведомление о бесплатном месяце | Ожидает Units 2+4 |
| 4 | 071 | Автоапгрейд UI при 5 рефералах | В worktree ✅ |
| 5 | 072 | Ambassador Dashboard в n8n | Ожидает Units 2+4 |
| 6 | 073 | Payout Flow: таблица + RPC + переводы | В worktree ✅ |
| 7 | 074 | Payout Flow в n8n (UI) | Ожидает Unit 6 |

### Unit 1 (migration 068) — CTA варианты

Migration 068 добавляет:
- `referral.squad_count_suffix` — локализованный суффикс для счётчика участников банды
- `referral.earned_suffix` — локализованный суффикс для заработанной суммы
- 6 вариантов CTA от Sassy Sage с плейсхолдерами `{count}` и `{remaining}`:
  - Варианты для новичков (0 рефералов): мотивирующие
  - Варианты для активных (1–3 реферала): поддерживающие, с прогрессом `{remaining}` до цели
  - Варианты для топовых (4+ реферала): ambassador-тон, RevShare

Суффиксы нужны для правильной локализации: например, "3 человека" (ru) vs "3 people" (en) vs "3 人" (ja).

### Unit 6 (migration 073) — Payout система

**Таблица `payout_requests`:**

```sql
CREATE TABLE payout_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  telegram_id BIGINT NOT NULL REFERENCES users(telegram_id),
  amount_usd NUMERIC(10,2) NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
    -- pending → approved → paid | rejected
  payment_method TEXT,  -- 'ton', 'usdt', 'stripe'
  payment_details JSONB, -- wallet address, etc.
  admin_comment TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  reviewed_at TIMESTAMPTZ,
  reviewed_by BIGINT  -- admin telegram_id
);
```

**`get_ambassador_balance(p_telegram_id)` RPC:**
- Читает `coin_transactions` и `payout_requests`
- Возвращает: `total_earned_usd`, `pending_payout_usd`, `available_for_payout_usd`, `paid_out_usd`
- `available_for_payout_usd = total_earned_usd - pending - paid_out`

**`request_payout(p_telegram_id, p_amount_usd, p_payment_method, p_payment_details)` RPC:**
- Валидирует `p_amount_usd >= min_payout_amount` (из `app_constants`)
- Валидирует `p_amount_usd <= available_for_payout_usd`
- Создаёт запись в `payout_requests` со статусом `pending`
- Отправляет уведомление в admin-чат (`admin_chat_id` из `app_constants`)
- Возвращает `REQUEST_CREATED` или ошибку (`MIN_AMOUNT`, `INSUFFICIENT_BALANCE`)

**`admin_review_payout(p_request_id, p_admin_id, p_action, p_comment)` RPC:**
- `p_action`: `'approve'` или `'reject'`
- Обновляет статус `payout_requests`, записывает `reviewed_by`, `reviewed_at`, `admin_comment`
- При `approve` → создаёт транзакцию списания в `coin_transactions` (тип `payout`)
- Никакого автоматического перевода денег — только смена статуса в БД

### Approval flow (безопасность)

Пользователь самостоятельно разработал approval flow с акцентом на безопасность:

```
Пользователь запрашивает вывод
  → request_payout() создаёт запись со статусом 'pending'
  → Уведомление в закрытый Telegram admin-чат (chat_id 417002669)
  → CEO просматривает, верифицирует реферальную активность
  → CEO вызывает admin_review_payout() через admin-интерфейс (или вручную через SQL)
  → При approve: запись обновляется, CEO вручную делает перевод
  → При reject: пользователю приходит уведомление с причиной
```

**Принципы:**
- **Никаких авто-выплат** — Stripe/TON API не вызывается автоматически
- **Ручная верификация** — защита от фрода, накрутки рефералов
- **Аудит-трейл** — каждое действие фиксируется (`reviewed_by`, `reviewed_at`)

### Ambassador tier и RevShare

RevShare структура:
- **Base (1–4 реферала):** стандартное вознаграждение за каждого PRO-реферала (фиксированное, в NomsCoins)
- **Ambassador (5+ рефералов):** RevShare 25% от ежемесячной подписки реферала
- **Senior Ambassador (10+ активных рефералов):** RevShare 30% (базовый 25% + бонус 5%)

Начисление через `coin_transactions` с типом `referral_commission`. Конвертация NomsCoins → USD по фиксированному курсу из `app_constants`.

### Ограничения для agентов

**`gh pr create` блокируется** системой разрешений — агенты в worktrees могут пушить ветки, но создавать PR не могут. PR нужно создавать вручную после проверки:
- Ветка `worktree-agent-af0b6285` → migration 068 (Unit 1)
- Ветка `worktree-agent-aa15b101` → migration 073 (Unit 6)

Агенты успешно следовали SQL-паттернам из migration 066: `jsonb_set` + `||` merge, `BEGIN;`/`COMMIT;` блоки.

### Переводы Unit 6 (9 ключей × 13 языков)

| Ключ | Описание |
|------|---------|
| `payout.title` | Заголовок экрана вывода |
| `payout.balance` | "Доступно для вывода: ${amount}" |
| `payout.min_amount` | "Минимум: $10" |
| `payout.request_button` | "Запросить вывод" |
| `payout.pending` | "Ожидает подтверждения: ${amount}" |
| `payout.approved` | "Одобрено! Ожидайте перевод." |
| `payout.rejected` | "Отклонено: {reason}" |
| `payout.insufficient` | "Недостаточно средств" |
| `payout.success` | "Заявка отправлена! Ответим в течение 48ч." |

## Завершение реализации (14:18, 2026-04-16)

Все 7 units реализованы, протестированы и задеплоены. Обновлённая таблица статусов:

| Unit | Migration | Содержание | Финальный статус |
|------|-----------|-----------|-----------------|
| 1 | 068 | Суффиксы + 6 CTA-вариантов | ✅ Применено |
| 2 | 069 | Механика 30-дн. награды | ✅ Применено |
| 3 | 070 | Push-уведомление о бесплатном месяце | ✅ Применено |
| 4 | 071 | Автоапгрейд UI при 5 рефералах | ✅ Применено |
| 5 | 072 | Ambassador translations × 13 langs | ✅ Применено |
| 6 | 073 | Payout Flow: таблица + RPC + переводы | ✅ Применено |
| 7 | 074 | workflow_states + conversation translations | ✅ Применено |

### Unit 2 (migration 069) — 30-дневная награда

- Добавлен план подписки `referral_reward_30d` (30 дней, $0, тип `referral`)
- Переписан `process_referral_payment_reward`:
  - Было: `activate_trial` (7 дней)
  - Стало: `activate_subscription` (30 дней, `referral_reward_30d` план)
  - One-time guard: проверяет что подписка с типом `referral_reward_30d` не выдана повторно

### Unit 3 (migration 070) — Уведомление о бесплатном PRO

3 варианта поздравительного сообщения × 13 языков:
- `referral_got_premium_1` — "БОМБА! 4 друга оформили PRO — бесплатный месяц!"
- `referral_got_premium_2` — более спокойный вариант
- `referral_got_premium_3` — Ambassador tone

Отправляется при срабатывании `process_referral_payment_reward` — пользователь получает уведомление в момент активации бесплатной подписки.

### Unit 4 (migration 071) — Auto-upgrade при 5 рефералах

**`check_and_promote_ambassador(p_telegram_id)` RPC:**
- Подсчитывает active referrals (paid PRO рефералы)
- Если count ≥ 5 и users.ambassador_tier IS NULL → устанавливает `ambassador_tier='basic'`
- Автоматически создаёт промокод `NOMS{telegram_id}` с 10% скидкой в таблице `promo_codes`
- Возвращает: `PROMOTED` (первое повышение) / `ALREADY_AMBASSADOR` / `NOT_ENOUGH_REFERRALS`

**Интеграция:** `process_referral_join` теперь вызывает `check_and_promote_ambassador` после каждого нового реферала.

**Обновление `get_referral_info`:**
- Добавлено поле `ambassador_tier` (null / 'basic' / 'senior')
- Оптимизация: 4 отдельных SELECT'а → 1 запрос с агрегацией

### Unit 5 (migration 072) — Ambassador translations

`ambassador.*` ключи × 13 языков:
- `ambassador.title` — "Ты Амбассадор NOMS!"
- `ambassador.subtitle` — описание программы RevShare
- `ambassador.stats` — статистика заработка
- `ambassador.promo` — "Твой промокод: NOMS{id}"
- `ambassador.noms_ambassador_1/2/3` — Sassy Sage фразы для ambassador уровня

### Unit 7 (migration 074) — Payout conversation flow

3 новых `workflow_states` (FK в `users_status_fkey`):
- `payout_method` — пользователь выбирает метод выплаты (TON / USDT / Stripe)
- `payout_wallet` — пользователь вводит адрес кошелька (free-text input)
- `payout_confirm` — подтверждение суммы и реквизитов

17 `payout.*` conversation переводов × 13 языков:
- `payout.select_method`, `payout.enter_wallet`, `payout.confirm_details`, `payout.amount_prompt`
- `payout.method_ton`, `payout.method_usdt`, `payout.method_stripe`
- `payout.wallet_placeholder`, `payout.confirm_button`, `payout.cancel_button`
- И другие строки диалогового flow

### n8n deployment (все изменения)

**01_Dispatcher Route Classifier:**
- Добавлен `payout_wallet` status routing (паттерн как у promo code — free-text input)
- Добавлен `admin_payout_*` callback routing (одобрение/отклонение CEO через Telegram)
- `payout_method`, `payout_confirm` добавлены в `buttonOnlyStatuses`

**04_Menu (114 нод → финально):**
- Command Classifier: 5 новых payout routes (`payout`, `payout_method_selected`, `payout_wallet_input`, `payout_action`, `admin_payout`)
- Menu Router: 29 outputs (было 24, +5 payout)
- **Build Friends Text:** полностью переписан с автопереключением по `ambassador_tier`:
  - `ambassador_tier` is set → Ambassador Dashboard (промокод `NOMS{id}`, баланс RevShare, sassy Ambassador фразы)
  - Обычный Squad: рандомные CTA варианты (из migration 068 cta_newbie_1/2/3, cta_active_1/2/3) + суффиксы
- **Edit Friends Message:** условный keyboard:
  - Ambassador: [Share Code] + [💰 Вывести средства]
  - Regular: [Поделиться] + [Подробнее]
- **Payout nodes (MVP):** Build Payout Screen, Edit Payout Screen, Is Payout Confirm?, Build Payout Cancel, Edit Payout Cancel

### Python deployment (VPS)

**Новые файлы:**
- `payout_handler.py` — dependency injection pattern:
  - `send_payout_request_to_admin(request_data)` — форматирует и отправляет в admin chat
  - `handle_admin_payout_callback(callback_data, admin_id)` — обрабатывает Approve/Reject
  - `send_referral_premium_notification(telegram_id, lang_code)` — уведомление о бесплатном PRO

**Изменения:**
- `webhook_server.py`: импорт payout_handler, новый endpoint `/api/payout-request`, вызов `send_referral_premium_notification` в `handle_checkout_completed`
- `config.py`: `ADMIN_CHAT_ID = 417002669`

**VPS статус:**
- `noms-cron`: 9 jobs ✅ (league_midweek добавлен ранее в тот же день)
- `noms-webhooks`: active, health OK, port 8443 ✅
- Первый запуск упал на `ModuleNotFoundError: payout_handler` → systemd retry сработал

### Backlog (следующие сессии)

- [ ] Полный payout flow: wallet input → confirm → RPC → admin notification (MVP routing есть, реальный баланс $0 пока нет ambassador commissions)
- [ ] Admin callback handling: кнопки Approve/Reject в admin чате → Python handler готов, n8n routing для `admin_payout_*` не протестирован
- [ ] `noms-webhooks` systemd: добавить `Restart=always RestartSec=2` для надёжного auto-retry
- [ ] Git: merge worktree branches (`worktree-agent-af0b6285`, `worktree-agent-aa15b101`) в main

### Worktree паттерн — выводы

- **Изоляция SQL:** worktree отлично подходит для параллельной разработки SQL-миграций — агенты создают независимые файлы
- **n8n API:** worktree бесполезен для n8n изменений — все PUT идут к одному живому workflow; последовательная работа координатора надёжнее
- **Agents и gh pr create:** `gh pr create` блокируется системой разрешений — агенты пушат ветки, PR нужно создавать вручную

## Related Concepts

- [[concepts/squad-referral-screen]] — Squad screen v1; реферальная механика backend существует с Phase 1; v2 расширяет UI
- [[concepts/payment-integration]] — PRO-подписки как основа RevShare начислений
- [[concepts/supabase-db-patterns]] — migrations 068–074; payout_requests таблица; RPC-first паттерн
- [[concepts/xp-model]] — NomsCoins как intermediary currency для referral rewards
- [[concepts/supabase-security]] — admin_review_payout: service_role only, аудит-трейл

## Sources

- [[daily/2026-04-16.md]] — Session 13:23: 7-unit архитектура Squad v2, Unit 6 (migration 073) payout_requests + 3 RPC + 9 translation keys, approval flow через admin Telegram chat, min_payout=$10, Units 1/2/4/6 запущены параллельно в worktrees
