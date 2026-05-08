# Supplement: Pre-implementation audit (Block 1-4)

> Дата: 2026-04-29. Подготовлено chip #1.5. Закрывает риски карты `onboarding-v3-map.md` секции 7.

---

## Блок 1 — User creation: что переиспользуем

### Существующие RPC связанные с users

| RPC | Сигнатура | Что делает | Используем для ensure_user_exists? |
|---|---|---|---|
| `sync_user_profile` | `(p_telegram_id bigint, p_first_name text DEFAULT NULL, p_username text DEFAULT NULL)` | UPDATE users SET first_name, username, last_active_at WHERE telegram_id = p_telegram_id AND is_bot=false. **Только UPDATE, не INSERT.** | Нет — только апдейт. Нужна отдельная ensure_user_exists. |
| `restore_user_account` | `(p_telegram_id bigint)` | Восстанавливает soft-deleted пользователя (сбрасывает deleted_at, статус). Не создаёт нового. | Нет |
| `delete_user_account` | `(p_telegram_id bigint)` | Soft-delete: пишет deleted_at. | Нет |

**Вывод:** В БД **нет ни одной RPC** для создания пользователя (ensure_user_exists, register_user, create_user, init_user — всё отсутствует). Текущая логика — прямой INSERT в n8n (`Auto Create User`). Для Python-замены нужно создать `ensure_user_exists` с нуля.

### Что делает Auto Create User сейчас (n8n, точный код)

Нода вставляет **5 полей**:
```
telegram_id  = message.chat.id
first_name   = message.from.first_name
username     = message.from.username || null
status       = 'new'
language_code = нормализован (см. ниже)
```
Все остальные поля берут дефолты из DDL.

### Колонки users при первом INSERT

| column | type | nullable | default | Заполняется при первом /start? |
|---|---|---|---|---|
| telegram_id | bigint | NOT NULL | — | Да (явно) |
| first_name | text | YES | NULL | Да (явно) |
| username | text | YES | NULL | Да (явно, может быть null) |
| status | text | YES | `'new'` | Да (явно, хардкод 'new') |
| language_code | text | YES | `'es'` | Да (явно, нормализованный) |
| is_bot | boolean | NOT NULL | `false` | Нет (дефолт false) |
| nav_stack | jsonb | NOT NULL | `'[]'` | Нет (дефолт []) |
| notifications_mode | text | NOT NULL | `'balanced'` | Нет (дефолт) |
| xp | integer | YES | `0` | Нет (дефолт 0) |
| level | integer | YES | `1` | Нет (дефолт 1) |
| nomscoins | integer | YES | `0` | Нет (дефолт 0) |
| mana_current | integer | YES | `2` | Нет (дефолт 2) |
| mana_max | integer | YES | `2` | Нет (дефолт 2) |
| goal_type | text | YES | `'maintain'` | Нет (дефолт) |
| subscription_status | text | YES | `'free'` | Нет (дефолт) |
| country_code | text | YES | `'US'` | Нет (дефолт) |
| timezone | text | YES | `'UTC'` | Нет (дефолт) |
| referrer_id | bigint | YES | NULL | Нет (всегда NULL при INSERT) |
| training_type | text | YES | `'mixed'` | Нет (дефолт) |
| phenotype | text | YES | `'default'` | Нет (дефолт) |
| goal_speed | text | YES | `'normal'` | Нет (дефолт) |
| league_id | integer | YES | `1` | Нет (дефолт 1) |
| league_xp_weekly | integer | YES | `0` | Нет (дефолт 0) |
| tamagotchi_stage | text | YES | `'egg'` | Нет (дефолт) |
| created_at | timestamptz | YES | `now()` | Нет (auto) |
| last_active_at | timestamptz | YES | `now()` | Нет (auto) |
| ... остальные ~40 колонок | various | YES | NULL | Нет |

> ⚠️ **Аномалия:** `language_code` DEFAULT = `'es'` (не `'en'`). Это, похоже, старый дефолт. В n8n-логике создания fallback явно `'en'`. Для `ensure_user_exists` fallback языка должен быть `'en'`, игнорируя DDL default.

### Language normalization

- **13 поддерживаемых lang_code** (из `ui_translations`): `ar, de, en, es, fa, fr, hi, id, it, pl, pt, ru, uk`
- **Логика в n8n Auto Create User:**
  ```js
  const raw = from.language_code || 'en';
  const base = raw.split('-')[0].toLowerCase();
  const supported = ['en','es','ru','pt','uk','de','fr','it','pl','id','hi','ar','fa'];
  return supported.includes(base) ? base : 'en';
  ```
- **Edge cases:** `de-AT` → `de`, `pt-BR` → `pt`, `zh-CN` → `en` (fallback), `null` → `en`
- **Для Python ensure_user_exists:** воспроизвести точно ту же логику (split('-')[0], lowercase, проверка по списку, fallback 'en')

### Решение

`ensure_user_exists` нужно **создать с нуля** как новую SQL-функцию. Сигнатура:
```sql
ensure_user_exists(
    p_telegram_id BIGINT,
    p_first_name TEXT DEFAULT NULL,
    p_username TEXT DEFAULT NULL,
    p_language_code TEXT DEFAULT 'en',  -- уже нормализованный
    p_referrer_id BIGINT DEFAULT NULL   -- опционально сразу при создании
) RETURNS jsonb  -- {created: bool, status: text}
```
Логика: `INSERT INTO users (telegram_id, first_name, username, status, language_code) VALUES (...) ON CONFLICT (telegram_id) DO UPDATE SET last_active_at=now() RETURNING status`.

`sync_user_profile` переиспользуется **отдельно** — как fire-and-forget апдейт имени/юзернейма при каждом обновлении (уже так работает в `webhook_server.py`).

---

## Блок 2 — Referrer flow

### Где referrer_id пишется (источники истины)

| Место | Компонент | Что делает |
|---|---|---|
| **01_Dispatcher** → нода `Has Referrer?` → нода `Link Referral` | n8n HTTP Request | Проверяет `parsed_referrer_id != empty`, вызывает `process_referral_join(p_referred_id=$json.telegram_id, p_referrer_id=parseInt($json.parsed_referrer_id))` |
| **`process_referral_join`** | RPC | `UPDATE users SET referrer_id=p_referrer_id WHERE telegram_id=p_referred_id` + escrow rewards |
| `crons/referral_unlock.py` | Python cron | Только читает (разблокировка escrow), не пишет |
| `02_Onboarding_v3`, `02_Onboarding_v1` | n8n | Не пишут referrer_id |

### Как работает поток в 01_Dispatcher

1. `Auto Create User` (INSERT) — **referrer_id не пишет**, пользователь создаётся с `referrer_id = NULL`
2. Нода `Has Referrer?` — IF `$json.parsed_referrer_id` notEmpty
3. Нода `Link Referral` — POST к `process_referral_join` с `p_referred_id` и `p_referrer_id`
4. `process_referral_join` — UPDATE users + INSERT referral_rewards (pending escrow)

**Порядок:** сначала создание юзера → потом отдельный вызов `process_referral_join`. Это правильно — функция проверяет `v_referred.referrer_id IS NOT NULL` (ALREADY_REFERRED guard).

### Что делает process_referral_join

Сигнатура: `process_referral_join(p_referred_id bigint, p_referrer_id bigint) RETURNS jsonb`

Логика (полная):
1. Проверка self-referral → ошибка `SELF_REFERRAL`
2. Проверка referrer exists → ошибка `REFERRER_NOT_FOUND`
3. Проверка referred exists → ошибка `REFERRED_NOT_FOUND`
4. Проверка `referrer_id IS NOT NULL` → ошибка `ALREADY_REFERRED`
5. `UPDATE users SET referrer_id = p_referrer_id` (referred пользователь)
6. `UPDATE users SET referral_count = referral_count + 1` (referrer)
7. INSERT в `referral_rewards` (pending escrow): coins=50, xp=100
8. Вызов `check_and_promote_ambassador(p_referrer_id)` — проверка перехода в амбассадор
9. Возврат `{success: true, referrer_name, ambassador_promoted}`

### Вердикт

**Реальный баг: НЕТ.** Механизм реферала рабочий. `referrer_id` пишется правильно — двухшаговый процесс: INSERT нового юзера (шаг 1) + вызов `process_referral_join` (шаг 2, только если `parsed_referrer_id` присутствует).

**Важно для Python-замены:** при миграции `ensure_user_exists` нужно сохранить этот двухшаговый паттерн. Либо:
- Вариант A: `ensure_user_exists` принимает `p_referrer_id` и вызывает `process_referral_join` внутри — одна RPC
- Вариант B (рекомендуется): Python сначала вызывает `ensure_user_exists`, потом если `referrer_id` передан — отдельный вызов `process_referral_join` (воспроизводит текущую n8n логику)

---

## Блок 3 — Legacy v1 + 04_Menu Go-to-Language

### v1 (JRaKFPb5sOFL3xlc) — что умеет

v1 имеет **46 нод** и обрабатывает **те же статусы** что и v3 (Status Router: 21 выход):
- Онбординг: new → step_1 → gender → age → weight → height → activity → goal
- Edit-flow: edit_gender, edit_age, edit_weight, edit_height, edit_activity, edit_goal
- Смена языка: changing_language → Language Menu → Parse Language → Save Language
- Country/timezone (Go to 02.1 Location, workflowId=`7EqiiwUwlGs7dcHT`)
- Gamification: Grant Onboarding XP + Grant Welcome Coins + Grant Registration Mana

**Ключевое отличие v1 от v3:**
- v1 **не имеет** шага `registration_step_training` (нет вопроса про тип тренировок)
- v1 **не имеет** `set_user_training_type` RPC
- v1 Status Router: `Handle Activity` → `Handle Goal` (прямо, без training)
- v1 имеет hardcoded send-ноды (Telegram API), v3 — Response Builder через JS

### Кто вызывает v1

Проверено по live workflow через API:
- **01_Dispatcher** (`7jVRdAvVlzOqIMEi`): **НЕ ссылается** на v1. Dispatcher напрямую вызывает v3 (`wzjYmMOurCbp4czk`)
- **04_Menu_v3** (`0xJXA5M4wQUSiGXT`): **НЕ ссылается** на v1. Имеет ноду `Go to 02_Onboarding_v3` → workflowId=`wzjYmMOurCbp4czk`

> **CLAUDE.md утверждает:** "v1 вызывается ТОЛЬКО из 04_Menu → Go to Language". Это **неверно для текущего состояния**. Live-проверка показала: 04_Menu_v3 вызывает **v3**, не v1. v1 является мёртвым кодом — никто его не вызывает.

### Влияние на миграцию

**v3 можно деактивировать безопасно** после миграции в Python — ни 01_Dispatcher, ни 04_Menu_v3 не ссылаются на v3 или v1 через executeWorkflow кроме как для передачи управления.

v1 (JRaKFPb5sOFL3xlc) — **полностью мёртвый код**, никто не вызывает. Можно деактивировать отдельно.

---

## Блок 4 — Translations coverage

### Корректировка карты

Карта `onboarding-v3-map.md` неверно указывала `messages.welcome_back` как отсутствующий ключ. **Реальный ключ** — `onboarding.msg_welcome_back` — существует и покрыт всеми 13 языками. Путаница из-за разных path (nested vs flat).

### Покрытие ключей × языков

| key | en | ru | ar | de | es | fa | fr | hi | id | it | pl | pt | uk | missing langs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `onboarding.welcome` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | none |
| `onboarding.finished` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | none |
| `onboarding.msg_welcome_back` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | none ✅ ИСПРАВЛЕНИЕ |
| `onboarding_success.menu_hint` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | none |
| `onboarding_success.personality_text` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ALL 13 |
| `messages.welcome_back` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ALL 13 (НЕ ИСПОЛЬЗУЕТСЯ — мёртвый ключ) |
| `gamification.onboarding_xp` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ALL 13 |
| `gamification.onboarding_coins` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ALL 13 |
| `gamification.onboarding_mana` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | none |
| `questions.gender/age/weight/height/activity/training_type/goal` | ✅×7 | ✅×7 | ✅×7 | ✅×7 | ✅×7 | ✅×7 | ✅×7 | ✅×7 | ✅×7 | ✅×7 | ✅×7 | ✅×7 | ✅×7 | none |
| `answers.male/female` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | none |
| `answers.act_sedentary/light/moderate/heavy` | ✅×4 | ✅×4 | ✅×4 | ✅×4 | ✅×4 | ✅×4 | ✅×4 | ✅×4 | ✅×4 | ✅×4 | ✅×4 | ✅×4 | ✅×4 | none |
| `answers.train_strength/cardio/mixed/skip` | ✅×4 | ✅×4 | ✅×4 | ✅×4 | ✅×4 | ✅×4 | ✅×4 | ✅×4 | ✅×4 | ✅×4 | ✅×4 | ✅×4 | ✅×4 | none |
| `answers.goal_lose/maintain/gain` | ✅×3 | ✅×3 | ✅×3 | ✅×3 | ✅×3 | ✅×3 | ✅×3 | ✅×3 | ✅×3 | ✅×3 | ✅×3 | ✅×3 | ✅×3 | none |
| `buttons.start/language/back` | ✅×3 | ✅×3 | ✅×3 | ✅×3 | ✅×3 | ✅×3 | ✅×3 | ✅×3 | ✅×3 | ✅×3 | ✅×3 | ✅×3 | ✅×3 | none |

### Финальный список для миграции

**3 ключа** нужно добавить (не 4, как в карте — `messages.welcome_back` мёртвый):

| key | langs | приоритет | примечание |
|---|---|---|---|
| `gamification.onboarding_xp` | 13 | **КРИТИЧНО** | "+{N} XP" строка в completion экране |
| `gamification.onboarding_coins` | 13 | **КРИТИЧНО** | "+{N} NomsCoins" строка в completion |
| `onboarding_success.personality_text` | 13 | Низкий | Текст под success-экраном, fallback `''` — UX неполный, но не ломает |

**Итого: 39 строк** (3 ключа × 13 языков).

> `messages.welcome_back` не нужно добавлять — реальный ключ `onboarding.msg_welcome_back` уже есть (13/13). В Python handler'е использовать `translations['onboarding']['msg_welcome_back']`.

---

## Итоговые решения для chip #2

### 1. ensure_user_exists — создать с нуля

```sql
-- Сигнатура
ensure_user_exists(
    p_telegram_id BIGINT,
    p_first_name TEXT DEFAULT NULL,
    p_username TEXT DEFAULT NULL,
    p_language_code TEXT DEFAULT 'en'
) RETURNS jsonb  -- {created: bool, status: text}

-- Логика:
-- INSERT INTO users(telegram_id, first_name, username, status, language_code)
-- VALUES (p_telegram_id, p_first_name, p_username, 'new', p_language_code)
-- ON CONFLICT (telegram_id) DO UPDATE SET last_active_at = now()
-- RETURNING (xmax = 0) AS created, status
```

Python handler нормализует `language_code` перед вызовом (split('-')[0], lowercase, check list, fallback 'en').

### 2. referrer_id — двухшаговый паттерн (не менять)

```python
# 1) ensure_user_exists(telegram_id, first_name, username, lang_code)
# 2) Если parsed_referrer_id:
#    process_referral_join(p_referred_id=telegram_id, p_referrer_id=parsed_referrer_id)
```

### 3. welcome_back key — правильный путь

Использовать `translations['onboarding']['msg_welcome_back']`, а **не** `translations['messages']['welcome_back']` (тот не существует).

### 4. v3 деактивация — безопасна

После миграции в Python обе ноды (`02_Onboarding_v3` в 01_Dispatcher и `Go to 02_Onboarding_v3` в 04_Menu_v3) будут ссылаться на Python endpoint. Workflow `wzjYmMOurCbp4czk` можно деактивировать. v1 (`JRaKFPb5sOFL3xlc`) уже мёртвый, деактивировать параллельно.

## Related Concepts

- [[concepts/onboarding-v3-map]] — основная карта 02_Onboarding_v3 (FSM + переходы)
- [[concepts/phase4-onboarding-migration]] — финальный cutover, gotchas
- [[concepts/start-fresh-flow]] — `cmd_start_fresh` reuse pattern
- [[concepts/variant-b-cutover]] — общий паттерн миграции
