# cmd_start_fresh — как работает в текущей системе

> Подготовлено chip разведки для chip #2-execute (миграция онбординга).
> Дата: 2026-04-29. Источники: GET 01_Dispatcher (`7jVRdAvVlzOqIMEi`), dispatcher/router.py, SQL к Supabase.

---

## TL;DR

`cmd_start_fresh` вызывает существующую RPC `reset_to_onboarding(p_telegram_id)`, которая очищает все данные профиля/геймификации soft-deleted юзера и переводит его в статус `registration_step_1`. После этого поток передаётся в `02_Onboarding_v3` — т.е. юзер проходит онбординг заново. **RPC существует — переиспользовать.**

---

## n8n flow (01_Dispatcher)

### Кто показывает экран restore/choice

Вход: `/start` при `users.deleted_at IS NOT NULL`

1. **Route Classifier** (v1.8) → `route_target = 'restore_choice'`
2. **Main Router** (output index 8) → `Account Blocked Message` (dead-end для прочего трафика при deleted)
3. Параллельно (Main Router output index 9) → **Set Status Restoring**
   - Нода делает `PATCH users SET status='restoring:choose'`
   - Затем → **Restore Choice Message** — шлёт `sendMessage` с двумя inline-кнопками:
     - `♻️ Restore account` → `callback_data: cmd_restore_account`
     - `🆕 Start fresh` → `callback_data: cmd_start_fresh`
   - Тексты берутся из `translations.restore.prompt_title`, `button_restore`, `button_fresh` (с fallback на hardcoded EN)

### cmd_start_fresh callback

Вход: callback `cmd_start_fresh` при `users.deleted_at IS NOT NULL`

1. **Route Classifier** → `route_target = 'start_fresh_execute'`
2. **Main Router** (output index 11) → **RPC Reset To Onboarding**
   - POST к `https://pymmeubsoeuglivywhhv.supabase.co/rest/v1/rpc/reset_to_onboarding`
   - Body: `{ p_telegram_id: $json.telegram_id }`
3. **Prepare Post Reset** (пустой Set-нод, passthrough)
4. → **Prepare for 02** → **02_Onboarding_v3** (`wzjYmMOurCbp4czk`)
   - Юзер сразу видит вопрос step_1 (Gender), т.к. статус уже `registration_step_1`

### cmd_restore_account callback (для полноты картины)

1. **Route Classifier** → `route_target = 'restore_execute'`
2. **Main Router** (output index 10) → **RPC Restore Account**
   - POST к `/rpc/restore_user_account`
3. → **Restore Success Message** (editMessageText с confirmation)
4. Нет перехода в onboarding — юзер остаётся `registered` и видит confirmation.

---

## Существующие RPC

| RPC | Сигнатура | Что делает | Подходит для start_fresh? |
|---|---|---|---|
| `reset_to_onboarding` | `(p_telegram_id bigint) RETURNS jsonb` | Сбрасывает `deleted_at=NULL`, `status='registration_step_1'`, обнуляет биометрику (gender/birth_date/weight_kg/height_cm/activity_level/goal_type/goal_speed/training_type/phenotype/все target_*), сбрасывает геймификацию (xp=0, level=1, nomscoins=0, streak=0, mana_current=0, tamagotchi_stage='egg', league_id=NULL), чистит UI-стейт (last_bot_message_id=NULL, nav_stack=[]). **Сохраняет:** telegram_id, first_name, username, language_code, referrer_id, subscription, created_at, food_log историю. | **Да — использовать** |
| `restore_user_account` | `(p_telegram_id bigint) RETURNS jsonb` | Только сбрасывает `deleted_at=NULL`, `status='registered'`. Данные профиля сохраняются. Проверяет: NOT_FOUND, NOT_DELETED, WINDOW_EXPIRED (> 30 дней). | Нет — это восстановление, не сброс |
| `delete_user_account` | `(p_telegram_id bigint) RETURNS jsonb` | Soft-delete: пишет `deleted_at`. | Нет |

---

## Рекомендация для chip #2-execute

**Вариант A: переиспользовать `reset_to_onboarding`** (рекомендуется).

RPC полностью готова и реализует нужную логику. В Python-handler нужно:

1. Вызвать `reset_to_onboarding(p_telegram_id)` через psycopg2/Supabase REST
2. Получить ответ: `{success: true}` или `{success: false, error: 'USER_NOT_FOUND'}`
3. При success → рендерить экран `registration_step_1` (Gender picker), аналогично тому как 02_Onboarding_v3 его показывает
4. При error → fallback сообщение

Сигнатура:
```sql
SELECT reset_to_onboarding($1::bigint)  -- возвращает jsonb
```

### Edge cases

| Кейс | Как обработать |
|---|---|
| Юзер не soft-deleted (deleted_at IS NULL), но нажал cmd_start_fresh | **Не может случиться в production** — Route Classifier пропускает cmd_start_fresh только если `user.deleted_at` не пустой. Если юзер каким-то образом нажал кнопку без deleted_at — RPC вернёт success (функция не проверяет deleted_at перед сбросом!). Это потенциальный баг: можно добавить guard в RPC или в Python-handler (проверить `user.deleted_at` перед вызовом). |
| Юзер уже anonymized (>30 дней после soft-delete) | `reset_to_onboarding` не проверяет этот случай (в отличие от `restore_user_account`). Технически может сработать для anonymized-юзера — это нужно проверить/защитить. Добавить guard: если `status='anonymized'` → показать отдельное сообщение "нельзя восстановить". |
| status = 'restoring:choose' при следующем /start | Юзер увидит пустой экран (этот статус нигде не обрабатывается в onboarding). В Python-handler нужно либо не ставить промежуточный статус, либо обработать 'restoring:choose' как синоним restore_choice. |
| Translations ключи | `translations.restore.prompt_title`, `restore.button_fresh`, `restore.button_restore` — нужно убедиться что существуют в `ui_translations` для всех 13 языков. В n8n есть EN fallback строки. |
| Потеря league после reset | `league_id=NULL` после reset — юзер не состоит ни в какой лиге. `complete_onboarding` не включает league assignment. Нужно убедиться что при завершении нового онбординга юзер попадает в лигу (по логике существующего cron или отдельного вызова). |

### Что не нужно создавать

`reset_to_onboarding` уже существует и задеплоена. Python-handler просто вызывает её через REST API или psycopg2.

---

## Связанные ноды в n8n (для ориентира при миграции)

| n8n нода | Python-аналог |
|---|---|
| `Set Status Restoring` (PATCH status='restoring:choose') | Опциональный промежуточный статус; в Python можно пропустить |
| `Restore Choice Message` (sendMessage + inline KB) | `handlers/restore_choice.py` → отправить сообщение с двумя кнопками |
| `RPC Reset To Onboarding` (POST /rpc/reset_to_onboarding) | `supabase_client.rpc('reset_to_onboarding', {...})` |
| `Prepare Post Reset` (пустой passthrough) | не нужен |
| → `Prepare for 02` → `02_Onboarding_v3` | → рендер `registration_step_1` экрана (Gender picker) |

## Related Concepts

- [[concepts/onboarding-v3-map]] — общая карта 02_Onboarding_v3 (FSM + переходы)
- [[concepts/phase4-onboarding-migration]] — финальный cutover в Python (включая `cmd_start_fresh` exclusion guard в router)
- [[concepts/soft-delete-account]] — soft-delete flow, восстановление через `restore_user_account`
- [[concepts/router-prefix-collision]] — `cmd_start_fresh` как пример коллизии префиксов
