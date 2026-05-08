---
title: "Phone Collection Strategy — Progressive Profiling в 3 точках"
aliases: [phone-binding, request-contact, user-phone, anti-fraud-phone]
tags: [onboarding, profile, ambassador-payout, anti-fraud, kyc, gdpr, ux-strategy]
sources:
  - "/Users/vladislav/.claude/plans/unified-sniffing-treehouse.md (2026-04-25)"
created: 2026-04-25
updated: 2026-04-25
---

# Phone Collection Strategy — Progressive Profiling

Стратегия сбора телефонных номеров в NOMS через `KeyboardButton.request_contact=true`. Phone собираем **только опционально**, в **3 контекстных точках**, не в основном онбординге как обязательное поле. Закрывает: anti-fraud regional pricing, ambassador payout compliance, account recovery, B2B/WhatsApp задел.

> **⚠️ Status:** утверждённая стратегия, ожидает реализации. Никакая из 3 точек ещё не построена. Колонки `phone_*` в `users` **отсутствуют** на 2026-04-25.

> **Связано с:** [[profile-v5-screens-specs]] (ЧАСТЬ 2 шаг 10, ЧАСТЬ 3 §5 help, ЧАСТЬ 12 payout), [[ambassador-payout-system]], [[soft-delete-account]] (GDPR), [[reply-keyboard-routing-pattern]] (Dispatcher routing).

## Key Points

- **3 точки сбора (Progressive Profiling), не одна:** опциональная кнопка на шаге страны в онбординге; обязательная верификация перед ambassador payout; добровольная привязка в Help (только если phone ещё не привязан).
- **Не собираем в основном онбординге как обязательное поле** — +5-10% drop-off без ROI.
- **Telegram Login Widget / Native SDK неприменим к боту** — это OIDC для внешних web/mobile приложений. Внутри Telegram phone собирается через `KeyboardButton.request_contact=true` в reply-клавиатуре. Inline-кнопки `request_contact` НЕ поддерживают.
- **🔒 Anti-spoofing критичен:** Telegram позволяет шарить ЧУЖОЙ контакт из адресной книги. Без проверки `Message.contact.user_id == Message.from.id` злоумышленник привяжет чужой номер.
- **Главная ценность — anti-fraud + compliance**, не AI и не платежи Stars/TON. AI-распознавание phone не улучшает; Stars/TON работают по `telegram_id`. Phone критичен для: ambassador payout KYC, regional pricing antifraud, premium trial anti-abuse, account recovery.
- **Dispatcher должен научиться роутить `message.contact`** — сейчас обрабатываются только `text` + `callback_query`. Это новая ветка в Route Classifier.

## Details

### Что отвергнуто

| Вариант | Почему нет |
|---|---|
| Phone как **обязательное поле** в основном онбординге | +5-10% drop-off ради фичи, которой пользуются <30% юзеров. Юзер ещё не понял ценность бота — выглядит как спам-бот. |
| Quest «+200 NomsCoins за привязку телефона» | 200 coins разбалансируют экономику (Streak Freeze стоит 50). Имеет смысл только при конкретном B2B/WhatsApp roadmap. Откладываем. |
| Telegram Login Widget / Native SDK | OIDC-механизм для **внешних** web/mobile приложений. Не применим к боту. Релевантен только когда появится Trainer Dashboard как web-surface. |

### Точка 1: Опциональная кнопка на шаге страны (Onboarding)

**Где:** workflow [[profile-v5-screens-specs]] ЧАСТЬ 2 шаг 10 (`onboarding:country`), хэндлится в **05_Location** workflow `7asj99vPQB5VCjXl`. Локальный JSON: `02.1_Location.json`, узел построения country-picker'а.

**Логика:** на шаге страны уже есть **reply-кнопка `[📍 Отправить местоположение]`** (request_location) + inline `[📋 Выбрать из списка]`. Добавляем **третью опцию — reply-кнопку `[📱 Подтвердить регион номером]`** (request_contact) рядом. Юзер волен:

- Тапнуть страну вручную через `cmd_list_countries` (как сейчас)
- Поделиться геолокацией → определяем country автоматически (как сейчас)
- **Поделиться телефоном** → определяем `country_code` из E.164 префикса (+34 → ES, +7 → RU и т.д.) **И** сохраняем `phone_number`
- Проигнорировать кнопку

**Зачем именно тут:**

1. **Antifraud regional pricing.** Сейчас `country_code_declared` самодекларируется → юзер может выбрать страну с самой низкой ценой подписки. Phone country code — независимый сигнал. При несовпадении (выбрал ES, но phone +7) → флаг `country_phone_mismatch` для tier-pricing decision (soft warning / hard block / просто лог — TBD compliance review).
2. **Естественность UX.** Уже есть паттерн `request_location` рядом — `request_contact` выглядит органично, не вызывает подозрений. Юзер уже психологически готов к "поделиться чем-то с ботом".
3. **Низкий риск drop-off.** Кнопка опциональная, не блокирует онбординг. Skip-rule сохранён ([[ux-crosscutting-principles]] правило 5: Skip только для улучшающих полей; страна остаётся обязательной).

**Текст инструкции:** "Поделись номером — я подтвержу регион автоматически (или выбери страну вручную)."

**`phone_source = 'onboarding'`**.

### Точка 2: Ambassador payout (compliance)

**Где:** [[profile-v5-screens-specs]] ЧАСТЬ 12 — Ambassador payout. Между Макет 12.1 (Method Picker) и Макет 12.2 (Wallet Input) — новый экран `payout_phone_verify`.

**Логика:** ВСЕГДА (даже если phone уже привязан в Точке 1) показывать экран подтверждения номера перед вводом реквизитов. Это сознательное решение: при финансовой операции надёжность важнее UX-краткости.

**Поведение:**

- **Если `phone_number IS NULL`:** показываем reply-клавиатуру `[📱 Поделиться номером]` + `[🔙 Назад]`. Юзер делится → сохраняем → переход к 12.2.
- **Если `phone_number IS NOT NULL`:** показываем confirm-экран: "Подтверди свой номер +34...XXXX (последние 4 цифры). Это твой?" с кнопками `[✅ Да, мой → cmd_payout_phone_confirm]` / `[📱 Привязать другой номер → request_contact reply-кнопка]` / `[🔙 Назад]`. Юзер выбирает.

**Зачем:**

1. **Compliance / KYC signal.** Выплаты регулируются — phone базовый KYC-компонент при выводе реальных денег.
2. **Автозаполнение реквизитов.** Если payout method = Bizum (ES) / Revolut / Sberbank — phone и есть реквизит. Один шаг вместо двух (но wallet input всё равно показывается для card / IBAN / crypto адреса).
3. **Защита от payout fraud.** Один phone = один payout-канал, блокирует множественные выводы через подставные аккаунты.
4. **Защита от смены SIM.** Если юзер сменил Telegram аккаунт между Точкой 1 и Точкой 2 — confirm-шаг ловит расхождение.

**Этот шаг — must-have, не пропускаемый.** Без подтверждённого phone payout не выполняется.

**`phone_source = 'payout'`** (если phone впервые попадает через эту точку).

### Точка 3: Help → "🔒 Привязать телефон" (recovery, добровольно)

**Где:** [[profile-v5-screens-specs]] ЧАСТЬ 3 §5 (`help` screen).

> **⚠️ Архитектурная заметка:** в текущей спеке Profile v5 [⚙️ Настройки] (`settings`) и [⚠️ Помощь] (`help`) — **равноправные соседи** в `profile_main`, а **не** Help внутри Settings. Эта статья размещает phone-кнопку именно в `help` (peer экран), что подтверждено user'ом 2026-04-25.

**Текущая клавиатура `help`:** Row 0: `[💬 Связаться с поддержкой → URL]` Row 1: `[🗑 Удалить аккаунт → cmd_delete_account]` Row 2: `[🔙 Назад → cmd_back]`.

**Новая клавиатура `help` (после внедрения):** условный рендер.

- **Если `phone_number IS NULL`** — добавляется Row 1.5: `[🔒 Привязать телефон → cmd_bind_phone]` (между Поддержкой и Удалением).
- **Если `phone_number IS NOT NULL`** — кнопка **НЕ показывается**. Опционально: статусная строка в тексте `help`: "🔒 Телефон привязан".

**Текст от Sage (TBD migration, ключ `profile.sage_phone_bind_invite`):**

> "Telegram-аккаунты иногда крадут. Дай номер, и я всегда узнаю тебя, даже если зайдёшь с другого профиля."

**Зачем:**

1. **Account recovery.** Если юзер сменил Telegram (новый аккаунт на тот же SIM) — по phone восстанавливаем подписку и историю.
2. **Без негатива.** Юзер сам приходит, сам решает, сам тапает. Discovery низкий, но drop-off нулевой.
3. **Estuary case.** Часть юзеров волнуются о потере данных — этот сценарий закрывает их страх.

**Не главный механизм, а fallback** для пользователей, которые не прошли через Точки 1 и 2.

**`phone_source = 'settings'`** (исторически называли так, хотя кнопка в Help — оставляем для обратной совместимости поля).

### Сводная матрица 3 точек

| Точка | Экран | Когда показывается | Опционально? | Условие пропуска при наличии phone | `phone_source` |
|---|---|---|:---:|---|---|
| 1. Onboarding | `onboarding:country` (шаг 10) | Один раз в онбординге | ✅ Да | n/a (только новички) | `onboarding` |
| 2. Payout | `payout_phone_verify` (новый, между 12.1 и 12.2) | Перед каждым выводом средств | ❌ Нет (must-have) | Confirm-экран вместо ввода (упрощённый flow) | `payout` |
| 3. Help | `help` (ЧАСТЬ 3 §5) | Юзер сам открывает | ✅ Да | **Кнопка скрыта**, если phone привязан | `settings` |

### Технические детали

#### Миграция БД (новая, номер TBD на момент реализации)

```sql
ALTER TABLE users
  ADD COLUMN phone_number TEXT,
  ADD COLUMN phone_verified_at TIMESTAMPTZ,
  ADD COLUMN phone_source TEXT
    CHECK (phone_source IN ('onboarding','payout','settings','quest'));

-- Anti-abuse: один phone = один аккаунт. NULL разрешён для legacy юзеров.
CREATE UNIQUE INDEX users_phone_number_uniq
  ON users (phone_number) WHERE phone_number IS NOT NULL;
```

#### RPC `set_user_phone(p_telegram_id, p_phone, p_source, p_contact_user_id)`

- Валидация формата E.164: `^\+[1-9]\d{6,14}$`
- **🔒 Anti-spoofing:** `IF p_contact_user_id != p_telegram_id THEN RAISE EXCEPTION 'foreign_contact_rejected'`
- Anti-collision: `UPDATE users SET phone_number = p_phone WHERE telegram_id = p_telegram_id`. При unique constraint violation → `RAISE EXCEPTION 'phone_already_used'` (ловит fraud signal).
- При несоответствии `country_code_declared` vs prefix(`p_phone`) → возвращать flag `country_phone_mismatch=true` для tier-pricing decision (не блокировать на уровне RPC).
- `phone_verified_at = NOW()` — Telegram уже верифицировал номер на своей стороне, доп. проверка не нужна.
- `phone_source` обновляется только при первом сохранении (последующие изменения сохраняют исходный source — для аналитики).

#### 🔒 КРИТИЧНО: Anti-spoofing (обязательно во всех 3 точках)

**Telegram позволяет пользователю шарить ЧУЖОЙ контакт из адресной книги.** Без проверки злоумышленник привяжет чужой номер.

**Защита на уровне n8n обработчика contact:**

```javascript
if ($json.message.contact.user_id !== $json.message.from.id) {
  return { error: 'foreign_contact', message: 'Можно делиться только своим номером' };
}
```

И **продублировано** на уровне RPC (`p_contact_user_id` параметр).

#### n8n паттерн (общий для 3 точек)

1. Триггер (callback / status: `onboarding:country` / payout flow / `cmd_bind_phone`) → `editMessageText` заменяем сообщение на инструкцию
2. `sendMessage` с **ReplyKeyboardMarkup**:
   ```json
   {
     "keyboard": [[
       {"text": "📱 Поделиться номером", "request_contact": true}
     ], [
       {"text": "🔙 Назад"}
     ]],
     "one_time_keyboard": true,
     "resize_keyboard": true
   }
   ```
3. Юзер тапает → Telegram нативный диалог → отправляет `Message.contact`
4. **Dispatcher** должен иметь роут для `message.contact` — новая ветка в Route Classifier (~1 IF-нода + 1 Set-нода). См. [[reply-keyboard-routing-pattern]] для аналогичного two-path routing подхода.
5. Anti-spoofing проверка `contact.user_id == from.id`
6. RPC `set_user_phone(telegram_id, phone, source, contact_user_id)`
7. `ReplyKeyboardRemove` → возвращаем inline-меню следующего шага

#### Privacy / GDPR

- Phone — PII. Текст кнопки/инструкции должен явно говорить **зачем** (Точка 1: подтверждение региона; Точка 2: для выплат; Точка 3: восстановление).
- Добавить `phone_number` в `cron_anonymize_deleted_users` (см. [[soft-delete-account]] Phase 4 GDPR cron) — обнуление через 30 дней после soft delete.
- Хранение plain text в `users.phone_number` ОК (Supabase шифрует at-rest на уровне диска).
- Privacy Policy — обновить упоминание сбора phone и целей использования.

### Связи с другими частями проекта

| Часть проекта | Workflow ID / Файл | Что меняется при реализации |
|---|---|---|
| **02_Onboarding_v3** | `Ksv1DhWKUIDtlhLy` | Не меняется напрямую (логика страны делегируется в 05_Location), но `Prepare for *` контракт может потребовать `phone_collected` поле. См. [[n8n-subworkflow-contract]]. |
| **04_Menu_v3** | `sxzbSc61YuHFbV4i` (legacy) / `ju0h4WStPZX54EfR` (transitional) | Условная кнопка `🔒 Привязать телефон` в Help screen (точка 3). Render зависит от `phone_number IS NULL`. |
| **05_Location** | `7asj99vPQB5VCjXl` | Точка 1: опциональная reply-кнопка `request_contact` рядом с inline-списком стран и существующей `request_location`. |
| **01_Dispatcher** | `6XzdbQqpoUG0nsLe` | Новая ветка в Route Classifier для `message.contact` updates. Anti-spoofing проверка `contact.user_id == from.id`. |
| **Profile v5 (`help` screen)** | спека [[profile-v5-screens-specs]] ЧАСТЬ 3 §5 | Условная кнопка + текст-приглашение от Sage |
| **Ambassador payout flow** | [[ambassador-payout-system]], миграции 068-074, ЧАСТЬ 12 спеки | Точка 2: новый экран `payout_phone_verify` между 12.1 (Method) и 12.2 (Wallet) |
| **БД миграция** | `migrations/NNN_add_users_phone.sql` (номер TBD) | `phone_number`, `phone_verified_at`, `phone_source` + unique partial index |
| **RPC** | новая `set_user_phone(...)` | E.164 validation, anti-spoofing, anti-collision, `country_phone_mismatch` flag |
| **Cron** | `cron_anonymize_deleted_users` ([[soft-delete-account]]) | Добавить `phone_number = NULL` в SQL обнуления |

## Verification (смоук-тест после реализации)

1. **Точка 1 (Onboarding country):** пройти онбординг, на шаге страны тапнуть `📱 Подтвердить регион номером` → проверить `users.phone_number` заполнен, `phone_source='onboarding'`, `country_code_declared` совпадает с E.164 префиксом. Затем повторить с пропуском кнопки → онбординг прошёл без проблем, phone остался NULL.

2. **Точка 2 (Ambassador payout) — новичок:** инициировать payout без phone → показывается экран `payout_phone_verify` с reply-кнопкой `📱 Поделиться номером`. После шеринга — `users.phone_number` заполнен, `phone_source='payout'`, payout продолжается на 12.2.

3. **Точка 2 (Ambassador payout) — phone уже есть:** инициировать payout с привязанным phone → показывается **confirm-экран** "Это твой номер +34...XXXX?" с inline-кнопками. Тап `[✅ Да, мой]` → переход на 12.2 без re-collection.

4. **Точка 3 (Help recovery):** при `phone_number IS NULL` — кнопка `🔒 Привязать телефон` ВИДНА в Help. После привязки — кнопка скрыта при следующем заходе. `phone_source='settings'`.

5. **Anti-spoofing test:** в Telegram desktop поделиться контактом ДРУГОГО юзера из адресной книги → бот отклоняет с "Можно делиться только своим номером". `users.phone_number` остаётся NULL.

6. **Anti-collision test:** два юзера пытаются привязать один и тот же phone → второй получает `phone_already_used` exception, в логах fraud signal.

7. **Antifraud regional pricing:** юзер выбирает country=ES, phone=+7 → флаг `country_phone_mismatch=true` в response RPC. Поведение для tier pricing — TBD (отдельное решение compliance review).

8. **GDPR:** юзер делает soft delete → через 30 дней `cron_anonymize_deleted_users` обнуляет `phone_number`. Проверка SQL после cron run.

## Open Questions

- ⏳ Когда реализуется ambassador payout workflow в n8n? (точка 2 встраивается туда; UI блок из [[ambassador-payout-system]] Unit 7)
- ⏳ Поведение при `country_phone_mismatch=true`: soft warning, hard block low-tier pricing, или просто лог для аналитики? — compliance/business decision.
- ⏳ Хеширование phone vs plain text — финальное решение по compliance review (для recovery нужен plain; для дедупликации можно hash + salt).
- ⏳ Текст ключа `profile.sage_phone_bind_invite` — финальная редакция Sassy Sage tone.
- ⏳ Translation keys для всех 13 языков (Точка 1 prompt, Точка 2 confirm dialog, Точка 3 invite + status строка).

## See Also

- [[profile-v5-screens-specs]] — Source of Truth для UX (ЧАСТЬ 2 шаг 10 country, ЧАСТЬ 3 §5 help, ЧАСТЬ 12 payout)
- [[ambassador-payout-system]] — payout system, куда встраивается Точка 2
- [[soft-delete-account]] — GDPR cron, куда добавляется обнуление phone
- [[reply-keyboard-routing-pattern]] — two-path routing pattern для reply-keyboard vs inline callback (Dispatcher routing)
- [[n8n-subworkflow-contract]] — `Prepare for *` контракт для передачи `phone_collected` между workflow
- [[ux-crosscutting-principles]] — Skip-rule integrity (правило 5: phone не нарушает требование критичности страны)
