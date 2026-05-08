---
title: "Anti-Spam / Debounce — защита от повторных нажатий"
aliases: [debounce, anti-spam, cooldown, debounce-user-action]
tags: [n8n, dispatcher, patterns, performance, ux]
sources:
  - "daily/2026-04-15.md"
  - "daily/2026-04-25.md"
created: 2026-04-15
updated: 2026-04-25
---

# Anti-Spam / Debounce — защита от повторных нажатий

## Проблема

Пользователь может нажать reply-кнопку 3 раза за 0.5с → 3 параллельных execution → 3 одинаковых ответа. Или переключить Stats → Profile → Stats быстро → race condition, 3 меню в чате вместо одного.

## Key Points

- **Inline-кнопки уже защищены:** `answerCallbackQuery` + `editMessageText` убирают старые кнопки → повторное нажатие физически невозможно
- **Reply-кнопки НЕ защищены нативно:** persistent keyboard всегда доступна
- **`debounce_user_action(p_telegram_id, p_cooldown_ms)` RPC** (migration 061): проверяет `last_active_at`, cooldown 1500ms — возвращает FALSE если в cooldown → Dispatcher дропает запрос
- **Migration 061** также создала `idx_ui_translations_lang_code` — ускоряет JOIN в `v_user_context` в ~10x
- **Статус (2026-04-15):** RPC создан в БД ✅, нода в Dispatcher NOT YET WIRED — требует отдельной сессии

## Details

### debounce_user_action RPC

Создан в migration 061:

```sql
CREATE OR REPLACE FUNCTION debounce_user_action(
  p_telegram_id BIGINT, 
  p_cooldown_ms INT DEFAULT 1500
) RETURNS BOOLEAN AS $$
DECLARE v_last_active TIMESTAMPTZ;
BEGIN
  SELECT last_active_at INTO v_last_active FROM users WHERE telegram_id = p_telegram_id;
  IF v_last_active IS NOT NULL AND 
     EXTRACT(EPOCH FROM (NOW() - v_last_active)) * 1000 < p_cooldown_ms THEN
    RETURN FALSE; -- skip, debounced
  END IF;
  UPDATE users SET last_active_at = NOW() WHERE telegram_id = p_telegram_id;
  RETURN TRUE; -- proceed
END;
$$ LANGUAGE plpgsql;
```

Вызывается в Dispatcher ПЕРЕД `Get User Context`. Если `FALSE` → dead-end, запрос не обрабатывается.

### Решение по типу кнопки

**Inline-кнопки (callback_query) — уже защищены:**
1. `answerCallbackQuery` останавливает спиннер на кнопке
2. `editMessageText` заменяет сообщение → старые кнопки исчезают
3. Повторное нажатие на те же кнопки физически невозможно

**Риск:** Пользователь нажимает кнопки на РАЗНЫХ сообщениях. Минимизируется через One Menu UX (в чате одно активное меню).

**Reply-кнопки (reply keyboard) — защищены через debounce RPC:**
- Вызов RPC перед Get User Context
- Cooldown 1500ms
- Использует существующий `last_active_at` — обновляется `sync_user_profile` RPC при каждом сообщении

### Исключения из debounce

**Не применять к:**
- `pre_checkout_query` / `successful_payment` — платежи нельзя дропать
- Inline callbacks — у них своя защита
- Onboarding steps — пользователь может быть медленным

### Migration 061: индекс на ui_translations

```sql
CREATE INDEX idx_ui_translations_lang_code ON ui_translations(lang_code);
```

`v_user_context` делает JOIN `ui_translations ON lang_code = u.language_code`. До индекса — sequential scan по всем переводам (~2000+ строк × 13 языков). После индекса — index scan, ~10x ускорение JOIN.

Применено в той же сессии что и debounce RPC, через n8n temp workflow.

### Правило для новых хендлеров

**Каждый новый reply-button маршрут обязан проходить через debounce.** Исключения перечислены выше.

## Migration 140 — debounce 500ms workaround (2026-04-25)

**Контекст:** Дебаунс 1500ms был слишком агрессивным — пользователи, нажимающие кнопки через 1-1.4с, получали тишину. Быстрый фикс без рефактора колонок: заменить `DEFAULT 1500` на `DEFAULT 500` через `pg_get_functiondef` REPLACE.

```sql
-- migrations/140_debounce_window_500ms.sql
CREATE OR REPLACE FUNCTION debounce_user_action(
  p_telegram_id BIGINT,
  p_cooldown_ms INT DEFAULT 500  -- было 1500
) ...
```

## Migration 141 — atomic debounce via `last_action_ms` (2026-04-25)

**Проблема:** Race condition между `Sync Profile` n8n-нодой и `debounce_user_action`. `Sync Profile` обновлял `last_active_at` параллельно с основным потоком. `debounce_user_action` читал `last_active_at` (SELECT) и затем писал (UPDATE) — не атомарно. Если `Sync Profile` обновил поле между SELECT и UPDATE, дебаунс видел свежий timestamp и возвращал FALSE → запрос дропался.

**Корень проблемы:** использование `last_active_at` для двух целей одновременно: (1) debounce guard + (2) cron/streak tracking. Конкурентные записи делали (1) ненадёжным.

**Решение:**

```sql
-- migrations/141_debounce_dedicated_column.sql

-- 1. Новая колонка только для debounce:
ALTER TABLE users ADD COLUMN last_action_ms BIGINT;

-- 2. Атомарная функция через UPDATE WHERE (нет отдельного SELECT):
CREATE OR REPLACE FUNCTION debounce_user_action(
  p_telegram_id BIGINT,
  p_cooldown_ms INT DEFAULT 500
) RETURNS BOOLEAN AS $$
DECLARE
  v_now_ms BIGINT := EXTRACT(EPOCH FROM NOW()) * 1000;
  v_found  INT;
BEGIN
  UPDATE users
  SET    last_action_ms = v_now_ms
  WHERE  telegram_id = p_telegram_id
    AND  (last_action_ms IS NULL
          OR last_action_ms < v_now_ms - p_cooldown_ms);

  GET DIAGNOSTICS v_found = ROW_COUNT;
  RETURN v_found > 0;  -- TRUE = proceed; FALSE = debounced
END;
$$ LANGUAGE plpgsql;
```

**Гарантии:**
- Нет race window между read и write — PostgreSQL UPDATE WHERE атомарен на уровне строки
- `last_active_at` остаётся нетронутым — cron/streak читают его без конкуренции
- `Sync Profile` перемещён из n8n в Python proxy (`maybe_sync_user_profile`) — убирает источник гонки параллельных записей в `last_active_at`

### Исключения из debounce

**Не применять к:**
- `pre_checkout_query` / `successful_payment` — платежи нельзя дропать
- Inline callbacks — у них своя защита
- Onboarding steps — пользователь может быть медленным

## Связанные концепции

- [[concepts/one-menu-ux]] — одно активное меню в чате, дополнительная защита от дублей
- [[concepts/n8n-performance-optimization]] — `idx_ui_translations_lang_code` как часть того же migration 061
- [[concepts/n8n-stateful-ui]] — typing actions, answerCallbackQuery для inline кнопок
- [[concepts/dispatcher-callback-pipeline]] — Dispatcher архитектура, где должен стоять debounce
- [[concepts/telegram-proxy-indicator]] — `maybe_sync_user_profile()` как замена `Sync Profile` n8n-ноды
- [[concepts/language-switch-headless-ux]] — Bug 5: debounce race был первопричиной silent drops при language switch

## Sources

- [[daily/2026-04-15.md]] — Migration 061: `debounce_user_action` RPC + `idx_ui_translations_lang_code`; паттерн anti-spam по типу кнопки; статус: RPC в БД, нода не подключена
- [[daily/2026-04-25.md]] — Migration 140: cooldown 1500ms→500ms workaround. Migration 141: `last_action_ms BIGINT` + атомарный `UPDATE WHERE` — устранение race condition с `Sync Profile` n8n-нодой
