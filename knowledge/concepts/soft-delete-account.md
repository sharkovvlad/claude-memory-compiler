---
title: "Soft Delete Account (GDPR-safe)"
aliases: [soft-delete, account-deletion, delete-account, restore-account, data-retention-cron]
tags: [feature, n8n, python, cron, gdpr, db, rpc, ux]
sources:
  - "daily/2026-04-18.md"
created: 2026-04-18
updated: 2026-04-19
---

# Soft Delete Account (GDPR-safe)

Полный цикл удаления аккаунта с 30-дневным grace-периодом восстановления и последующей GDPR-анонимизацией. Реализован в 4 фазах: Phase 1 (DB/RPC — migration 079), Phase 2 (04_Menu n8n wiring), Phase 3 (Dispatcher soft-delete gate + restore flow), Phase 4 (Data Retention GDPR cron).

## Key Points

- **Soft delete, не hard delete.** `delete_user_account` RPC устанавливает `deleted_at = NOW()`, не удаляет строку. Это позволяет восстановить аккаунт в 30-дневное окно.
- **Dispatcher-level gate (Phase 3)** блокирует любую активность удалённых аккаунтов. `/start` от удалённого юзера → экран выбора: восстановить или начать заново.
- **Subscription blocker.** Пользователям с `subscription_status IN ('premium', 'trial')` удаление заблокировано — показывается CTA на отмену подписки.
- **GDPR автоматизация (Phase 4):** `DataRetentionCron` дёргает RPC `cron_anonymize_deleted_users` ежедневно в 03:00 UTC — анонимизирует юзеров с `deleted_at > 30 дней назад`.
- **`deleted_at` передаётся в 04_Menu через Dispatcher `Prepare for 04` backpack** — 44-е поле (добавлено в Phase 2). `v_user_context` уже раскрывал `deleted_at` из migration 079.
- **Кнопка перемещена в Help** — `cmd_delete_account` показывается в Help sub-screen (не в Settings), чтобы снизить случайные удаления.

## Details

### Phase 2 — 04_Menu n8n wiring (08:07 UTC 2026-04-18)

**Изменения в Command Classifier:**
- `cmd_delete_account` удалён из `coming_soon` stub; добавлен маршрут → `delete_account_init`
- `cmd_confirm_delete` → `delete_account_confirm`

**Menu Router:** +2 outputs (было 27 → стало 28 branches): `delete_account_init`, `delete_account_confirm`.

**6 новых нод:**

| Нода | Тип | Назначение |
|------|-----|-----------|
| `Build Delete Confirmation` | Code | Рендерит `delete_account.title` + `delete_account.warning_body` с плейсхолдерами `{streak_days}`, `{xp}`, `{coins}` из `Merge Data` |
| `Edit Delete Confirmation (Inline)` | HTTP editMessageText | Stateful UI — заменяет текущее сообщение (One Menu pattern) |
| `Check Subscription Blocker` | IF | `subscription_status ∈ {premium, trial}` → blocker branch, иначе → RPC |
| `RPC Delete User Account` | HTTP POST | `POST /rest/v1/rpc/delete_user_account` (credential `Supabase NutritionBot` `5E9LfSxeVkSlYP3S`) |
| `Build Delete Account Result` | Code | Dual-branch: IF-true (blocker message с CTA `cmd_profile_subscription`) ИЛИ RPC-path (`success=true` → terminal action с `inline_keyboard: []`; `error='ACTIVE_SUBSCRIPTION'` → blocker fallback) |
| `Edit Delete Account Result (Inline)` | HTTP editMessageText | Финальный экран |

**Перенос кнопки:** `cmd_delete_account` перемещена из Settings в Help sub-screen. Текст берётся из `delete_account.help_button` (уже содержит ❌ — двойной эмодзи не добавляется).

**Dispatcher `Prepare for 04`:** +1 поле `deleted_at` (`stringValue`, fallback `''`). Итого: 43 → **44 поля**. `v_user_context` уже раскрывал `deleted_at` из migration 079 — изменений в БД не потребовалось.

### Phase 3 — Dispatcher soft-delete gate (08:14 UTC 2026-04-18)

`Route Classifier` обновлён: v1.6 → **v1.8**. Добавлен блок `"0.5 SOFT-DELETE GATE"` сразу после payment-routing. Логика:

```javascript
// 0.5 SOFT-DELETE GATE (v1.8)
if (user.deleted_at) {
  const isStart = text === '/start' || command === 'cmd_restore_account' || command === 'cmd_start_fresh';
  if (!isStart) return { route: 'account_blocked' };
  if (text === '/start') return { route: 'restore_choice' };
  if (command === 'cmd_restore_account') return { route: 'restore_execute' };
  if (command === 'cmd_start_fresh') return { route: 'start_fresh_execute' };
}
```

**Main Router:** +4 outputs (было 7 → **11 rules**): `account_blocked`, `restore_choice`, `restore_execute`, `start_fresh_execute`.

**7 новых нод:**

| Нода | Тип | Назначение |
|------|-----|-----------|
| `Account Blocked Message` | Telegram sendMessage | `dispatcher.account_blocked`, без клавиатуры. ACQ гасится уже существующей параллельной `Is Callback? → Answer Callback` веткой |
| `Set Status Restoring` | HTTP PATCH | `status='restoring:choose'` через REST `/rest/v1/users?telegram_id=eq.*` |
| `Restore Choice Message` | Telegram sendMessage | Inline-keyboard: `cmd_restore_account` / `cmd_start_fresh`. Тексты из `$('Route Classifier').item.json.translations.restore.*` (т.к. HTTP ломает `$json`) |
| `RPC Restore Account` | HTTP POST | `POST /rest/v1/rpc/restore_user_account` |
| `Restore Success Message` | Telegram editMessageText | `restore.restored_ok`, редактирует то же сообщение |
| `RPC Reset To Onboarding` | HTTP POST | `POST /rest/v1/rpc/reset_to_onboarding` |
| `Prepare Post Reset` | Set | Восстанавливает поля из `$('Route Classifier')` (translations, constants, language_code, callback IDs) + `status='registration_step_1'` → ведёт в `Prepare for 02 → Has Referrer? → 02_Onboarding` |

**Connections:**
```
Main Router out[7]  → Account Blocked Message
Main Router out[8]  → Set Status Restoring → Restore Choice Message
Main Router out[9]  → RPC Restore Account → Restore Success Message
Main Router out[10] → RPC Reset To Onboarding → Prepare Post Reset → Prepare for 02
```

**Локальная копия:** `n8n_code_nodes/dispatcher_route_classifier_v1.8.js` (NEW).

### Phase 4 — Data Retention Cron (GDPR, 2026-04-18)

**Новый файл `crons/data_retention.py`** — `DataRetentionCron(BaseCron)` по шаблону `subscription_lifecycle.py`:
- Вызывает `supabase.rpc('cron_anonymize_deleted_users')`
- Логирует `anonymized_count` / `ran_at`
- Корректно обрабатывает пустой результат (0 записей к анонимизации)

**Регистрация в `main.py`:**
```python
scheduler.add_job(
    job_data_retention,
    CronTrigger(hour=3, minute=0),
    id='data_retention',
    misfire_grace_time=3600
)
```

**Smoke test (локально):**
```bash
python3 -c "import asyncio; from crons.data_retention import DataRetentionCron; asyncio.run(DataRetentionCron().run())"
```
Вернул `HTTP 200`, `No users to anonymize this cycle (ran_at=2026-04-18T08:18:03.429902+00:00)` ✅

**Изменённые файлы:** `crons/data_retention.py` (NEW), `crons/__init__.py` (+DataRetentionCron, +`__all__`), `main.py` (job registration), `CLAUDE.md` (cron table).

### RPCs (migration 079)

| RPC | Параметры | Что делает |
|-----|-----------|-----------|
| `delete_user_account(telegram_id)` | bigint | Устанавливает `deleted_at = NOW()` |
| `restore_user_account(telegram_id)` | bigint | Сбрасывает `deleted_at = NULL`, восстанавливает `status` |
| `reset_to_onboarding(telegram_id)` | bigint | Полный сброс к `registration_step_1`, обнуляет прогресс |
| `cron_anonymize_deleted_users()` | — | Анонимизирует юзеров с `deleted_at > NOW() - 30 days` |

### workflow_states задействованные

| State | Когда |
|-------|-------|
| `restoring:choose` | `/start` от удалённого юзера — выбор restore vs fresh |
| `deleting:confirm` | Показан экран подтверждения удаления в 04_Menu |
| `deleted` | После успешного `delete_user_account` (soft-delete state) |
| `anonymized` | После `cron_anonymize_deleted_users` (GDPR, необратимо) |

### Subscription Blocker — детали

`Check Subscription Blocker` IF-нода проверяет `subscription_status`. Если `premium` или `trial`:
1. В `Build Delete Account Result` рендерится blocker message с CTA `cmd_profile_subscription`
2. RPC `delete_user_account` НЕ вызывается
3. Пользователь направляется на экран управления подпиской для отмены

Это предотвращает ситуацию где юзер удаляет аккаунт с активной подпиской и теряет оплаченный период.

### Open items / Follow-ups

- **После RPC Restore Account** показывается только подтверждение (`editMessageText restore.restored_ok`). По ТЗ Phase 3 должен быть handoff в главное меню (reuse `cmd_get_menu` flow). **Требует follow-up** — отдельная ветка через `Prepare for 04` с синтетическим `command='cmd_get_menu'`.
- **Manual smoke test** с тестовым юзером `786301802`: `SELECT delete_user_account(786301802);` → `/start` → должен появиться restore-choice экран.
- **Деплой на VPS** Phase 4: `./deploy.sh` → `systemctl restart noms-cron` → `journalctl -u noms-cron -f` (проверить строку "Data Retention" в jobs list).
- **`cmd_start_fresh` пропускает referral linking** — expected для fresh start. Handoff идёт напрямую в 02_Onboarding минуя стандартный путь Dispatcher.

## Related

- [[concepts/supabase-db-patterns]] — migration 079, RPC применение через psycopg2
- [[concepts/n8n-stateful-ui]] — One Menu pattern, editMessageText
- [[concepts/dispatcher-callback-pipeline]] — `deleted_at` поле в Prepare for 04, 44 полей
- [[concepts/n8n-subworkflow-contract]] — Prepare for 04 contract (44 полей), `deleted_at` как защищённое поле
- [[concepts/profile-redesign-v5]] — Settings и Help sub-screens, кнопка перемещена в Help
- [[concepts/action-router-pattern]] — Menu Router Phase 2 deploy был синхронизирован с Action Router рефакторингом

## Sources

- [[daily/2026-04-18.md]] — Phase 2 (08:07), Phase 3 (08:14), Phase 4 — полный цикл реализации soft delete account
