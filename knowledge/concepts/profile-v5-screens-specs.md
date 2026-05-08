---
title: "Profile v5 — Источник Истины (UX каталог всего бота)"
tags: [ux, screens, catalog, onboarding, profile, headless]
sources:
  - "daily/2026-04-19.md"
  - "daily/2026-04-20.md"
created: 2026-04-19
updated: 2026-04-20
---

# Profile v5 — Источник Истины (макеты экранов)

**Политика:** Этот файл — источник истины по UX для Profile v5. Любые пользовательские правки (user corrections) перезаписывают файл. БД и шаблоны подгоняются под макеты, не наоборот.  
Если `ui_screens` / `ui_translations / app_constants` или какой-то другой расходятся с макетом — сначала дай пользователю представление текущего окна/меню, обсуди с ним и если он подтвердит \- планируй миграцию. Возможно послабление этого правила если для эмодзи если в `app_constants` уже есть похожие по смыслу иконки.   
Никаких хардкодов \- все данные берутся из Supabase, в n8n или code \- только отрисовка этих значений. Если есть где\-то \- менять по ходу миграций. 

> **⚠ Правило для агентов, редактирующих этот документ (добавлено 2026-04-21).**
> Документ стал большим (~2400+ строк, 18+ ЧАСТЕЙ). Перед любой правкой конкретного макета / раздела:
> 1. **Прочитай ТЕКУЩЕЕ состояние БД** по этому экрану (через NLM или psycopg2 из `DATABASE_URL` в `.env`): `ui_screens`, `ui_screen_buttons`, `ui_translations`, `app_constants`.
> 2. **Сверь с макетом в файле** — БД и файл должны совпадать по экранному виду. Если расходятся — НЕ правь файл молча.
> 3. **Если нашёл расхождение** — подсвети user'у ДО правки: «Сейчас в БД X, в файле Y, предлагаю привести к Z — подтверди». Только после approval трогай либо файл, либо миграцию (и то, и другое — по ситуации).
> 4. **Никаких тихих "фиксов"**: любая правка макета, текста, кнопки, Noms-фразы — через согласование с user'ом. Исключение — правки за самим user'ом (по его прямому сообщению).
> 5. **При генерации миграций** — deep-merge для существующих JSONB секций (никакого `content || '{"section":{...}}'` если `section` уже есть).

**Когда обновлять:** при каждом user feedback по любому экрану. Проставить дату и что изменилось.

**Источник данных:** SELECT из Supabase (ui\_screens, ui\_translations lang\_code='ru', ui\_screen\_buttons, app\_constants) от 2026-04-20.

### Сквозные UX-принципы (зафиксированы 2026-04-20)

1. **Python cron НЕ мигрирует на headless.** Cron-задачи (reminders, league_cycle, streak_checker, subscription_lifecycle, mana_reset) остаются в Python; в `ui_screens` для них `screen_id` нет. Но `ui_translations` и `app_constants` могут дорабатываться для них. В каталоге UX такие ЧАСТИ помечены «⚠ legacy by design».

2. **Кнопка [Отмена] ≡ [🔙 Назад] — везде ОДНА.** Унифицированный паттерн: `buttons.back = "Назад"` + `icon_back=🔙` + callback `cmd_back`. НЕ плодим `cmd_back_to_menu`, `cmd_back_to_progress`, `[❌ Отмена]`, `[🔙 Назад в меню]`. Поведение «назад» решается через `users.nav_stack` (миграции 076-078). Legacy экраны с `buttons.cancel`/`icon_cancel` → мигрируем при ближайшей правке.

3. **Видеостикеры — предпочтительный UX для transient / push.** У Noms есть набор стилизованных видеостикеров (анализирует еду / думает / завтрак-reminder и т.д.). Для wait-индикаторов (ЧАСТЬ 15) и cron push (ЧАСТЬ 14) стикер предпочтительнее текста. В макетах отмечаем: `🎥 [sticker: noms_<context>]` перед текстом. Со временем cron-уведомления поэтапно переходят на формат «стикер + короткий caption».

4. **Shared Screens (переиспользуемые экраны) — один `screen_id`, два контекста.** Экраны ввода (`ask_weight/age/height`) и pickers (`edit_goal/activity/training/phenotype/gender/lang/country/timezone`) вызываются из онбординга (`registration_step_*`) и из Profile v5 edit (`edit_*`). В БД — ОДНА запись на экран. Макет описывается один раз (ЧАСТЬ 2A), в ЧАСТЯХ 2 и 3 — ссылки с context-матрицей (откуда пришёл, куда back возвращает).

5. **Кнопка [⏭ Пропустить] — только для «улучшающих» полей.** В онбординге критичные поля (пол, возраст, вес, рост, активность, тренировки, цель, страна, таймзона) — **без Skip** (без них бот не посчитает норму калорий). Skip добавляется ТОЛЬКО на шагах, где дефолт приемлем: `goal_speed` (normal), `target_weight_kg` (0 = не задано), `phenotype_quiz` (default=standard). Пропущенные поля → cron `profile_incomplete` (ЧАСТЬ 14) мягко напоминает дозаполнить через 3 дня активности. Ключ `buttons.skip` — ✅ migration 102 applied 2026-04-20.

6. **Phone collection — Progressive Profiling в 3 точках** (TBD реализация, добавлено 2026-04-25). Phone собираем **только опционально**, в 3 контекстных местах, не в основном онбординге как обязательное поле:
   - **Точка 1:** опциональная reply-кнопка `[📱 Подтвердить регион номером]` рядом с `[📍 Отправить местоположение]` на шаге 10 онбординга (`onboarding:country`) — anti-fraud regional pricing.
   - **Точка 2:** обязательный экран `payout_phone_verify` (Макет 12.1.5) между Method Picker и Wallet Input — compliance/KYC при выводе средств. Confirm-режим если phone уже привязан.
   - **Точка 3:** условная кнопка `[🔒 Привязать телефон]` в `help` (ЧАСТЬ 3 §5), скрывается если phone уже привязан — добровольное account recovery.
   
   Полная стратегия, технические детали, anti-spoofing rules, RPC сигнатуры, миграция БД, GDPR — в [[phone-collection-strategy]]. **Любая правка макетов по phone должна согласовываться с этим документом, чтобы не плодить противоречий.**

---

## 🗺 Дорожная Карта Меню (Roadmap)

Самый быстрый способ считать структуру бота. Дерево всех веток (глазами юзера), со статусами описания каждого экрана. Cтатусы см. ниже под таблицей ЧАСТЕЙ.

### Главное меню (после онбординга, статус `registered`)

**Ветка 🆕 Онбординг (`/start` → `registered`)** — ЧАСТЬ 2 / ЧАСТЬ 2A
* `welcome` 🟡 (первый контакт нового пользователя) — TBD Пачка A
* `registration_step_1..5` 🟡 → pickers: пол, возраст, вес, рост, активность *(Shared с Profile edit)*
* `registration_step_training` 🟡 → picker тренировок
* `registration_step_goal` 🟡 → picker цели
* `registration_step_speed` 🟡 → picker темпа (slow/normal/fast) *(новый шаг, Skip разрешён)*
* ~~`registration_step_target_weight`~~ ❌ — **отказались 2026-04-21 окончательно**: убран из онбординга И из Profile → My Plan. Лишняя фича, противоречит anti-shaming / РПП safety. Колонка `users.target_weight_kg` в БД остаётся как артефакт (не чистим), но в UX НЕ экспонируется нигде.
* `registration_step_phenotype_quiz` 🟡 → квиз из 4 вопросов → `phenotype` *(новый шаг, Skip разрешён)*
* `onboarding:country` 🟡 → страна (auto / manual)
* `onboarding:timezone` 🟡 → таймзона
* `onboarding_success` 🟡 (завершение + first-menu hint)

**Ветка 👤 Профиль (Agent Dossier)** — [ЧАСТЬ 3](#-часть-3--главное-меню--profile-v5)
* [`profile_main`](#1-profile_main-профиль--главный) ✅ (досье агента, 9 экранов headless)
  * [`ask_weight`](#6-ask_weight-ввод-веса) ✅ *(Shared — ЧАСТЬ 2A)*
  * [`my_plan`](#2-my_plan-мой-план) ✅ (подменю плана)
    * `edit_goal` ✅ (Session 10, migration 110) / `edit_activity` ✅ (Session 10, migration 110) / `edit_training` ✅ (Session 10, migration 110) / `edit_speed` ✅ (Session 10, migrations 108+110) / `edit_phenotype` 📝 (deferred Session 11 — multi-step)
    * [`personal_metrics`](#4-personal_metrics-личные-метрики) ✅
      * [`ask_weight`](#6-ask_weight-ввод-веса) / [`ask_height`](#8-ask_height-ввод-роста) / [`ask_age`](#7-ask_age-ввод-возраста) ✅ *(Shared)* / `edit_gender` ✅ (Session 10, migration 110) *(Shared)*
  * [`settings`](#3-settings-настройки) ✅
    * `edit_lang` ✅ (Session 10, migration 110+111 RPC) / `edit_country` 🔄 (Session 10 partial — DB ready, dynamic_list rendering deferred Session 11) / `edit_timezone` 🔄 (Session 10 partial — DB ready, dynamic_list rendering deferred Session 11) *(Shared)*
    * `edit_notifications_mode` ✅ (Session 10, migration 110) (Zen / Balanced / Beast)
  * [`help`](#5-help-помощь) ✅
    * [`delete_account_confirm`](#9-delete_account_confirm-подтверждение-удаления) ✅ ([ЧАСТЬ 13](#-часть-13--soft-delete--restore) — restore flow)

**Ветка ☀️ Мой день (Daily Dashboard)** — [ЧАСТЬ 5](#-часть-5--мой-день--stats)
* [`stats_main`](#25-stats_main-главный-экран-дня) 📝 (КБЖУ текущего дня)
  * `edit_last_log` 🟡 → [ЧАСТЬ 6](#-часть-6--ai-food-logging-фото--голос--текст) `editing:food`
  * `day_history` 🟡
* [`food_log_result`](#26-food_log_result-результат-записи-еды) 📝 (после записи еды)

**Ветка 🚀 Прогресс (Game Hub)** — [ЧАСТЬ 4](#-часть-4--progress-hub)
* [`progress_main`](#20-progress_main-главный-экран-прогресса) 📝
  * [`quests`](#21-quests-ежедневные-задания) 📝 → ЧАСТЬ 4/10 (active / all_done)
  * [`league`](#22-league-лидерборд-лиги) 📝 → [ЧАСТЬ 10](#-часть-10--детали-лиги) (leaderboard, `league_info`, promote/demote celebrations)
  * [`friends_info`](#23-friends_info-банда--рефералы) 📝 → [ЧАСТЬ 11](#-часть-11--рефералы--банда-stateful-ui-novice--ambassador) — Stateful UI: **Novice Band** (0-4 paid) **→ Ambassador Dashboard** (5+ paid или `is_trainer=true`, entry в [ЧАСТЬ 12](#-часть-12--ambassador-payout) payout)
  * [`shop`](#24-shop-магазин-и-заморозки) 📝 → [ЧАСТЬ 9](#-часть-9--магазин-с-transaction-confirmations) (`buy_freeze`, `buy_mana`, `insufficient_coins`, transaction success/fail)

### Сквозные (вызываются из многих мест)

**🍽 Food logging (фото / голос / текст / штрих-код)** — ЧАСТЬ 6 + ЧАСТЬ 7
* `processing` 🟡 (🎥 стикер `noms_analyzing`, пока GPT думает)
* `food_log_result` 📝 (success, уже в ЧАСТИ 5)
* `not_food_error` 🟡 (Noms саркастично: «это не еда»)
* `rate_limit_paywall` 🟡 (0 маны → Free paywall, CTA → ЧАСТЬ 8)
* `editing:food` 🟡 / `editing:food_manual` 🟡 / `editing:food_retry` 🟡 (correction loop)
* `scanning:barcode` 🟡 (ЧАСТЬ 7)

**💎 Оплата / Premium** — ЧАСТЬ 8
* tier picker → checkout (Stars / Stripe / TON) → promo → **success** / **failure** → manage
* `subscription_expiry` push (ЧАСТЬ 14, полный макет)

**💰 Ambassador payout** — ЧАСТЬ 12
* `payout_method` → `payout_wallet` → `payout_confirm` → admin approve в чате `417002669`

**🗑 Soft delete & restore** — ЧАСТЬ 13
* `delete_account_confirm` (в ЧАСТИ 3 §9) → `deleted` (30-day window)
* `restoring:choose` 🟡 (welcome-back: restore vs fresh start)
* `anonymized` (терминальный, без UI)

**🔔 Push-уведомления (Python cron)** — ЧАСТЬ 14 *(⚠ legacy by design — НЕ мигрируем на headless)*
* Reminders × 7 (meal_morning/lunch/dinner, day_close, streak_warning, quest, inactivity)
* League × 6 (promotion, demotion, fomo × 4)
* Streak × 2 (frozen, broken)
* Economy × 1 (mana_recharged)
* Payment × 2 (expiry, renewal_reminder)
* 🆕 Profile × 1 (profile_incomplete — когда юзер skipped поля онбординга)
* 🆕 Referral × 1 (referral_activated — squad celebration)

**⚠ Error / edge / wait** — ЧАСТЬ 15
* Errors (`errors.*`), system messages (`messages.*`), wait-индикаторы (🎥 стикеры Noms вместо текста), gate `account_blocked`, validation hints.

**🎉 Celebrations** — ЧАСТЬ 16
* Level-up (60 уровней, tamagotchi stages), streak milestone, league promotion.

---

## 🗺 Полная карта UX (Master UX Map)

Tech-вью: таблица всех ЧАСТЕЙ каталога с готовностью описания и архитектурным статусом. Дополняет дерево выше.

**Легенда статусов:**

- ✅ — экран описан полностью (макет + клавиатура + meta + Noms commentary) И соответствует реальной БД / n8n.
- 📝 — черновик: макет есть, но требует миграции или расходится с текущей БД («TBD migration NNN»).
- 🟡 — placeholder: заголовок ЧАСТИ есть, детали ждут пачки макетов.
- ⚠ — legacy-рендер: экран живёт в n8n workflow / Python cron, `screen_id` в БД нет.
- 🔄 — есть в n8n, планируется миграция на headless `ui_screens`.

### Карта 19 ЧАСТЕЙ

| ЧАСТЬ | Название | Ветка | Экранов | Готовность | Архитектура |
|---:|---|---|---:|:---:|---|
| 0 | Политика обновления + сквозные принципы | system | — | ✅ | meta |
| 1 | Дорожная карта + Master UX Map | system | — | ✅ | meta |
| 2 | Онбординг: welcome → done | /start | 5-6 | 🟡 | ⚠ n8n (02_Onboarding) |
| 2A | 🔁 Shared Screens (pickers + text_input) | cross-ветка | 11 | 🟡 | 🔄 3 из 11 в `ui_screens` |
| 3 | Главное меню / Profile v5 | 👤 Profile | 19 | 📝 частично | 🔄 9 из 19 в `ui_screens` |
| 4 | Progress Hub | 🚀 Progress | 5 | 📝 черновик | ⚠ n8n (08_Progress) |
| 5 | Мой день / Stats | ☀️ Stats | 2+ | 📝 черновик | ⚠ n8n (04_Menu stats) |
| 6 | AI food logging (фото/голос/текст) | input → log | 8-10 | 🟡 | ⚠ n8n (03_AI_Engine) |
| 7 | Сканер штрих-кода | camera | 3 | 🟡 | ⚠ n8n (scanning:barcode) |
| 8 | Оплата / Premium (+transaction states) | 💎 paywall | 8-12 | 🟡 | ⚠ n8n (10_Payment) |
| 9 | Магазин (freeze, mana, +confirmations) | 🛒 shop | 8 | ✅ | headless (migrations 136, 144) |
| 10 | Детали лиги (leaderboard, how-to) | 🏆 league | 3-4 | 🟡 | ⚠ n8n (08.2_League) |
| 11 | Рефералы / Друзья | 👥 friends | 3-4 | 🟡 | ⚠ n8n (08.3_Friends) |
| 12 | Ambassador payout | 💰 payout | 9 | ✅ | headless (migration 145, БД готова, sender pipeline в handover) |
| 13 | Soft delete & restore | GDPR | 2 | 🟡 | ⚠ n8n (01_Dispatcher) |
| 14 | Cron push-уведомления | background | 17 | 🟡 | ⚠ legacy by design |
| 15 | Error / edge states + wait (🎥 стикеры) | system | 4-6 | 🟡 | ⚠ везде |
| 16 | Celebrations геймификации | 🎉 in-flow | 2-3 | 🟡 | ⚠ n8n (04_Menu) |
| 17 | Таблицы локализации enum'ов | meta | — | 📝 частично | — |
| 18 | Known Deviations (БД vs spec) | meta | — | 📝 частично | — |

### Зафиксированные форматные решения

Применяются при добавлении макетов — не переделываем:

1. **ЧАСТЬ 14 (Cron push) — гибрид:** компактная таблица по всем 14 типам (триггер / шаблон / пример) ПЛЮС полные макеты `╭─ NOMSaibot ─╮` для 2-3 push с CTA-кнопками (`subscription_expiry`, `league_promotion`, `streak_broken`).
2. **ЧАСТЬ 15 (Wait-индикаторы) — компактная таблица** без рамок: «тип / когда срабатывает / текст».
3. **ЧАСТЬ 2 (Онбординг) — welcome + шпаргалка:** полные макеты только для `welcome` (первый контакт) и `onboarding_success` (завершение). Середина — таблица: шаг → FSM `state_code` → вопрос → варианты ответов → иконки → тон Noms.

### Источники данных

- **Headless-слой:** `ui_screens` (9 строк), `ui_screen_buttons` (26 записей), `ui_translations` (ru, 28 секций) — через NLM (блокнот «NOMS Supabase Data»).
- **Legacy n8n:** локальные JSON в `n8n_workflows/` + self-hosted API на VPS (`http://127.0.0.1:5678` через SSH; cloud `vlad1.app.n8n.cloud` отменён 2026-04-30).
- **Cron push:** `crons/reminders.py`, `league_cycle.py`, `streak_checker.py`, `subscription_lifecycle.py`, `mana_reset.py`.
- **FSM:** таблица `workflow_states` (37 `state_code` на 2026-04-20).

---

## 🗂 ЧАСТЬ 2 — Онбординг: welcome → done

**Статус:** 🟡 placeholder. Будет заполнен в Пачке A (welcome макет + compact table середины + onboarding_success макет).

**Цель онбординга — 100% заполненный профиль**, чтобы никогда не просить «дозаполнить» после. Критичные поля — обязательны. «Улучшающие» (темп, цель-вес, фенотип) — с кнопкой `[⏭ Пропустить]`, далее сработает cron `profile_incomplete` (ЧАСТЬ 14).

**Что войдёт:**
- Welcome-экран (`/start` для нового пользователя, `status='new'`).
- Compact flow table: **12 шагов онбординга** (9 критичных + 3 улучшающих с Skip) — вопрос / варианты ответов из `answers.*` / иконки / тон / Skip разрешён?
- Экран `onboarding_success` (завершение → статус `registered` + первая подсказка меню).
- Onboarding reminders (Python cron для брошенного онбординга — 6 шаблонов).

**Шаги онбординга** (полный список для заполнения):

| # | FSM state_code | Поле в `users` | Picker / Input | Skip? | Комментарий |
|---:|---|---|---|:---:|---|
| 1 | `registration_step_1` | `gender` | picker (male/female) | ❌ | критично для BMR |
| 2 | `registration_step_2` | `birth_date` | text_input (возраст) | ❌ | критично для BMR |
| 3 | `registration_step_3` | `weight_kg` | text_input | ❌ | критично |
| 4 | `registration_step_4` | `height_cm` | text_input | ❌ | критично для BMR |
| 5 | `registration_step_5` | `activity_level` | picker (4 вариант) | ❌ | критично для TDEE |
| 6 | `registration_step_training` | `training_type` | picker (4 варианта) | ❌ | влияет на норму белка |
| 7 | `registration_step_goal` | `goal_type` | picker (lose/maintain/gain) | ❌ | критично |
| 8 | `registration_step_speed` 🆕 | `goal_speed` | picker (slow/normal/fast) | ✅ | default `normal` если skip |
| ~~9~~ | ~~`registration_step_target_weight`~~ | ~~`target_weight_kg`~~ | ❌ **отказались** | — | См. «Решение про target_weight» ниже |
| 9 | `registration_step_phenotype_quiz` 🆕 | `phenotype` + `phenotype_answers` | 4-вопросный квиз → picker results | ✅ | default `standard` если skip |
| 10 | `onboarding:country` | `country_code_declared` | picker (auto / manual list) | ❌ | для региональных цен + timezone |
| 11 | `onboarding:timezone` | `timezone_declared` | picker (auto / manual list) | ❌ | для cron push в правильное время |

**Переводы:** `answers.*` (17), `onboarding_reminders.*` (6), `onboarding_success.*` (1), корневые (`ask_timezone`, `timezone_auto`, `ask_share_location`), `buttons.skip` (✅ migration 102 applied 2026-04-20), `onboarding.skip_hint` (TBD 102).
**FSM `state_code`:** `new`, `registration_step_1..5`, `registration_step_training`, `registration_step_goal`, **`registration_step_speed` 🆕**, **`registration_step_phenotype_quiz` 🆕**, `onboarding:country`, `onboarding:timezone`. Новые state_code — TBD migration (добавление в `workflow_states`).

### Решение про `target_weight_kg` (2026-04-21 — окончательно)

**НЕ собираем НИГДЕ в UX** — ни в онбординге, ни в Profile → My Plan, ни в Stats. Лишняя фича, предложена агентом без проверки целесообразности. Колонка `users.target_weight_kg` в БД остаётся как артефакт (default=0 = «не задано»), но **не экспонируется пользователю**.

**Причины:**
1. **Противоречит safety-ethics философии NOMS** (anti-shaming, РПП detection из CLAUDE.md). Конкретная цифра-цель — классический триггер обсессии пищевого поведения.
2. **Не участвует в расчётах.** `calculate_user_targets` использует `goal_type` + `goal_speed` + текущий `weight_kg`. `target_weight_kg` нигде в математике норм не нужен.
3. Юзеры часто ставят нереалистичные цифры → требуется BMI-filter → раздражает.
4. Лишний шаг = drop-off.

**Progress-визуализация** (если когда-то понадобится) — как дельта от текущего веса («-3 кг за месяц»), **без фиксированной target-цифры**.

**Итого шагов онбординга:** 11 (было 12 в предыдущей итерации).
**Воркфлоу:** `02_Onboarding` (Ksv1DhWKUIDtlhLy, v3) + `05_Location` (7asj99vPQB5VCjXl).
**Shared screens:** pickers 1, 5, 6, 7, 8, 10, 11, 12 и text_inputs 2, 3, 4, 9 — это те же экраны, что вызываются из Profile v5 edit. Макеты в ЧАСТИ 2A. Эта ЧАСТЬ покрывает только welcome + onboarding_success + compact flow-table.
**Связанный cron:** `profile_incomplete` (ЧАСТЬ 14) — отправляется если юзер skipped один или больше шагов 8/9/10 И активен (логирует еду) И прошло ≥3 дня с `registered`. Кнопка CTA → `cmd_my_plan`.

---

### 🎬 Макет 2.1 — Welcome (первый /start)

**Тригер:** статус `new`. Видеостикер НЕ используется (текст + reply_keyboard). Ключ `onboarding.welcome` (ru) — *буквальный текст из БД*:

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ Привет! Я — твой AI-нутрициолог.           │
│                                            │
│ Отправляй мне фото еды.                    │
│ Говори голосовыми.                         │
│                                            │
│ Но сначала — настройка профиля!            │
╰────────────────────────────────────────────╯
```

Reply-клавиатура (2 кнопки):
- `[▶️ Поехали]` — (`buttons.start` ✅ в БД)
- `[🌐 Язык]` — (`buttons.language` ✅ в БД, открывает `edit_lang` picker)

После `Поехали` — автоматический переход в `registration_step_1` (пол).

*Noms-комментарий к welcome-тексту — TBD (можем расширить: «Никакого shame, только факты и саркастичные камни в твой огород.»).*

---

### 📋 Макет 2.2 — Compact Flow Table (шаги 1-12)

Все буквальные тексты — из БД (`questions.*` + `answers.*`), верифицировано через psycopg2 на 2026-04-20 после применения migration 102.

| # | Шаг (FSM) | Prompt (буквальный ru) | Варианты / формат ввода | Skip? |
|---:|---|---|---|:---:|
| 1 | `registration_step_1` | «Укажи свой пол» | `[🧔 Мужчина → cmd_select_male]`  `[👩 Женщина → cmd_select_female]` | ❌ |
| 2 | `registration_step_2` | «Твой возраст (например: 41):» | text_input (int 13-120) → `set_user_age` | ❌ |
| 3 | `registration_step_3` | «Твой вес (кг):» | text_input (num 20-300) → `set_user_weight` | ❌ |
| 4 | `registration_step_4` | «Твой рост (см):» | text_input (num 50-250) → `set_user_height` | ❌ |
| 5 | `registration_step_5` | «Как проходит твой обычный день?» | `[💻 Сижу (Офис/IT)]` `[🚶 Стою/Хожу (Магазин)]` `[⚡ В движении (Курьер)]` `[🏋️ Тяжёлый труд]` → `cmd_select_sedentary/light/moderate/heavy` | ❌ |
| 6 | `registration_step_training` | «Какой тип тренировок тебе ближе?» | `[💪 Силовые]` `[🏃 Кардио]` `[🔄 Смешанные]` `[⏭ Пропустить]` → `cmd_select_strength/cardio/mixed/training_skip` | ✅ *(train_skip — историческое Skip, не новое)* |
| 7 | `registration_step_goal` | «Твоя цель?» | `[📉 Похудение → cmd_select_lose]` `[⚖️ Удержание → cmd_select_maintain]` `[📈 Набор → cmd_select_gain]` | ❌ |
| 8 🆕 | `registration_step_speed` | «Каким темпом двигаемся к цели?» | `[🐢 Медленный] [⚖️ Нормальный] [🚀 Быстрый] → cmd_select_speed_slow/normal/fast`, + `[⏭ Пропустить]` | ✅ |
| 9 🆕 | `registration_step_phenotype_quiz` | *(запускает 4-вопросный квиз, тексты `phenotype.q1-4` ✅ в БД)* | 4 inline pickers (см. ЧАСТЬ 2A § Phenotype Quiz Flow) | ✅ |
| 10 | `onboarding:country` | `ask_share_location` (3 варианта, random) — «Не листай список вручную. Нажми кнопку внизу ⬇️ — я сам всё найду!» и ещё 2 варианта | reply-кнопка «📍 Отправить местоположение» + reply-кнопка «📱 Подтвердить регион номером» 🆕 *(см. [[phone-collection-strategy]] Точка 1)* + `[📋 Выбрать из списка → cmd_list_countries]` | ❌ |
| 11 | `onboarding:timezone` | `ask_timezone` (3 варианта, random) — «Ого, какая большая страна! Уточни город, чтобы твой прогресс дня не сбрасывался раньше времени.» и ещё 2 варианта | `[🧙 Авто определил: {timezone}]` (`timezone_auto`) + `[📋 Выбрать вручную → cmd_list_timezones]` | ❌ |

**Подсказка Skip (ключ `onboarding.skip_hint` ✅ migration 102):** «Можешь пропустить и настроить позже в Профиле.» — отображается под pickers шагов 8/9/10 мелким курсивом.

---

### 🎬 Макет 2.3 — Onboarding Success (статус → `registered`)

**Ключ `onboarding.finished` (ru)** — *буквальный текст БД*:

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 🎉 Готово! Профиль создан.                 │
│                                            │
│ 🎯 {target_calories} ккал/день             │
│ 📊 🥩 {protein_g}г  🥑 {fat_g}г  🥖 {carbs_g}г│
│                                            │
│ {icon_mana} {mana} Мана — подарок!         │
│                                            │
│ Пришли мне фото первого приема пищи!       │
╰────────────────────────────────────────────╯
```

Кнопки:
- `[🍽 Добавить еду → cmd_add_food]` (CTA)

После — reply_keyboard: `[☀️ Мой день]` `[👤 Профиль]` `[🚀 Прогресс]` (main menu).

**Второе сообщение (menu_hint, ключ `onboarding_success.menu_hint`):**

```
💬 NOMSaibot: Или используй меню ниже ⬇️
```

**Gaps найдены (могут быть в миграциях 104-105 от другого агента):**
- `msg_welcome` (root-level) — не найден в БД
- `onboarding_success.personality_text` (упоминается в коде `response_builder.js`, но в БД отсутствует) — ожидаемый текст «Кинь фотку еды — покажу, на что способен»
- `gamification.onboarding_xp` — отсутствует
- `gamification.onboarding_coins` — отсутствует
- Prompt для нового шага 8 (`questions.goal_speed`) — не создан (target_weight исключён из онбординга)

---

### ⏰ Макет 2.4 — Onboarding Reminders (Python cron, 6 шаблонов)

Триггер: юзер начал онбординг, но не ответил на шаг. Cron `crons/reminders.py` отправляет один из 6 текстов-шпаргалок (ключ `onboarding_reminders.*`):

| Ключ (БД) | Текст (ru, буквальный) | Триггер |
|---|---|---|
| `onboarding_reminders.gender` | «✨ Осталось: выбрать пол» | status=`registration_step_1`, простой ≥2h |
| `onboarding_reminders.age` | «✨ Осталось: указать возраст 🎂» | `registration_step_2`, ≥2h |
| `onboarding_reminders.weight` | «✨ Осталось: указать вес ⚖️» | `registration_step_3`, ≥2h |
| `onboarding_reminders.height` | «✨ Осталось: указать рост 📏» | `registration_step_4`, ≥2h |
| `onboarding_reminders.activity` | «✨ Осталось: выбрать активность 🏃» | `registration_step_5`, ≥2h |
| `onboarding_reminders.goal` | «✨ Осталось: выбрать цель 🎯» | `registration_step_goal`, ≥2h |

Max 1 reminder per step, debounce 24h. Отправляется видеостикером (🎥) — кандидат на Noms-стикер «указательный перст» + caption.

---

## 🗂 ЧАСТЬ 2A — 🔁 Shared Screens (переиспользуемые pickers и text_inputs)

**Статус:** 🟡 placeholder (Пачка A, вместе с ЧАСТЬЮ 2).

**Концепция:** один `screen_id` в `ui_screens` — два контекста вызова (онбординг и Profile edit). Back-поведение решается через `users.nav_stack` (миграции 076-078). Макет описывается один раз здесь, ЧАСТИ 2 и 3 ссылаются.

**Список shared-экранов и контекст-матрица** (будет заполнена в Пачке A):

| screen_id | Тип | Онбординг (FSM → next_step) | Profile edit (FSM → back) | save_rpc | Skip? | Headless? |
|---|---|---|---|---|:---:|:---:|
| `ask_weight` | text_input | `registration_step_3` → `step_4` | `edit_weight` → `personal_metrics` | `set_user_weight` | ❌ | ✅ |
| `ask_age` | text_input | `registration_step_2` → `step_3` | `edit_age` → `personal_metrics` | `set_user_age` | ❌ | ✅ |
| `ask_height` | text_input | `registration_step_4` → `step_5` | `edit_height` → `personal_metrics` | `set_user_height` | ❌ | ✅ |
| `edit_gender` | picker | `registration_step_1` → `step_2` | `edit_gender` → `personal_metrics` | `set_user_gender` | ❌ | 📝 |
| `edit_activity` | picker | `registration_step_5` → `step_training` | `edit_activity` → `my_plan` | `set_user_activity` | ❌ | 📝 |
| `edit_training` | picker | `registration_step_training` → `step_goal` | `edit_training` → `my_plan` | `set_user_training` | ❌ | 📝 |
| `edit_goal` | picker | `registration_step_goal` → `registration_step_speed` | `edit_goal` → `my_plan` | `set_user_goal` | ❌ | 📝 |
| `edit_speed` 🆕 | picker (slow/normal/fast) | `registration_step_speed` → `step_phenotype_quiz` | `edit_speed` → `my_plan` | `set_user_goal_speed` | ✅ | 📝 |
| ~~`ask_target_weight`~~ | ~~text_input~~ | ❌ **отказались 2026-04-21** (убран и из онбординга, и из Profile). Колонка в БД остаётся как артефакт. | ❌ | — | — | — |
| `edit_phenotype` | picker (quiz start, 4 вопроса) | `registration_step_phenotype_quiz` → `onboarding:country` | `edit_phenotype` → `my_plan` | `set_user_phenotype` | ✅ | 📝 |
| `edit_lang` | picker (13 flags) | *(можно показать при `/start`, auto from Telegram)* | `edit_lang` → `settings` | `set_user_language` | — | 📝 |
| `edit_country` | picker (auto / manual) | `onboarding:country` → `onboarding:timezone` | `editing:country` → `settings` | `set_user_country` | ❌ | 📝 |
| `edit_timezone` | picker (auto / manual) | `onboarding:timezone` → `registered` | `editing:timezone` → `settings` | `set_user_timezone` | ❌ | 📝 |

**Различия welcome vs edit контекста:**
- **Prompt text:** онбординг — вежливо-знакомительный («Привет! Давай знакомиться. Сколько тебе лет?»). Edit — прямой («Введи новый возраст»). Реализовано через `business_data` контекстный флаг или через разные translation keys для одного экрана.
- **Back behavior:** онбординг — back запрещён или возвращает на предыдущий шаг. Edit — back возвращает в `my_plan`/`personal_metrics`.
- **Cancel:** онбординг — нет кнопки Назад (обязательное заполнение). Edit — есть `[🔙 Назад → cmd_back]`.

**Переводы:** `answers.*` (17) — варианты ответов для pickers; `profile.ask_*_prompt` (TBD) — текст prompts; `errors.invalid_*` — валидация.
**Источник истины макетов:** описывается здесь, НЕ в ЧАСТИ 3 §6-§8 (те становятся ссылками на 2A).

---

### 🏃 Speed Picker (`edit_speed`) — Shared (онбординг шаг 8 + Profile edit)

**Статус:** 📝 draft. **✅ migration 108 applied 2026-04-21** (субагент генерит: `questions.goal_speed`, `answers.speed_slow/normal/fast`, `profile.noms_speed_intro[3]`, `profile.speed_hint`).

**Правила показа:**
- Онбординг: показывается после `registration_step_goal`, только если `goal_type ∈ {lose, gain}`. Если `maintain` — шаг пропускается автоматически (темпа нет), переход сразу в `registration_step_phenotype_quiz`.
- Profile edit: вход по кнопке `[🏃 Темп]` в `my_plan` (cmd_edit_speed).
- Значения процентов берутся динамически из `app_constants`: `goal_speed_slow_deficit=10`, `goal_speed_normal_deficit=15`, `goal_speed_fast_deficit=20`, `goal_speed_slow_surplus=8`, `goal_speed_normal_surplus=10`, `goal_speed_fast_surplus=15` (см. ЧАСТЬ 17 enum-table).

**Макет (обе версии goal_type, одна схема):**

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 🏃 Темп (Скорость)                         │
│                                            │
│ Насколько быстро движемся к цели?          │
│ Помни: стабильность важнее скорости.       │
│                                            │
│ Текущий: 🟢 Нормальный (-15%)  ← (если set)│
│                                            │
│ 💬 Noms: "{random noms_speed_intro[0..2]}"  │
╰────────────────────────────────────────────╯
```

**Заголовок:** `profile.speed_header` = «🏃 Темп (Скорость)» *(или use icon_speed из app_constants если есть)*.
**Prompt:** `questions.goal_speed` ≈ «Каким темпом движемся к цели?» + `profile.speed_hint` = «Помни: стабильность важнее скорости. Выбери комфортный режим.»
**Current indicator:** `profile.current_speed` = «Текущий: {icon} {label} ({pct})» — только в Profile edit режиме (в онбординге ещё не выбран).
**Noms-коммент:** random из 3 `profile.noms_speed_intro[0..2]`.

**Клавиатура:** (Рендерится динамически, знак и процент зависят от `goal_type`)

```text
[🐢 Медленный (±X%) → cmd_select_speed_slow]
[⚖️ Нормальный (±Y%) → cmd_select_speed_normal]
[🚀 Быстрый (±Z%) → cmd_select_speed_fast]
[🚫 Отмена → cmd_my_plan]
```

Единый набор labels для обоих goal_type (lose/gain). Решение 2026-04-22: отказ от gain-specific «Плавный/Агрессивный» labels. Для `maintain` экран не показывается.

**Индикатор текущего выбора (Profile edit):** `✅ ` префикс на кнопке выбранного варианта (паттерн ЧАСТЬ 0 из edit_screen_ux принципа).

**Финальная кнопка (контекст-зависимая):**
- Онбординг: `[⏭ Пропустить → cmd_skip_step]` (`buttons.skip` ✅ migration 102, остаётся default `normal`)
- Profile edit: `[🔙 Назад → cmd_back]` (`buttons.back`)

**save_rpc:** `set_user_goal_speed(telegram_id, speed)` — сохраняет `goal_speed` + пересчитывает `target_speed_percent` + пересчитывает `calculate_user_targets`.

**FSM переход:**
- Онбординг: `registration_step_speed` → `registration_step_phenotype_quiz` (или `onboarding:country` если phenotype тоже skip)
- Profile edit: `edit_speed` → (реакция 👌 + render обновлённого `my_plan`)

**Переводы:** `questions.goal_speed`, `answers.speed_slow/normal/fast`, `profile.noms_speed_intro[3]`, `profile.speed_hint`, `profile.current_speed`, `profile.speed_header` — **✅ migration 108 applied 2026-04-21** (субагент в процессе). Плюс существующие: `profile.speed_deficit` / `profile.speed_surplus` (шаблоны % — уже в БД).

**Источники Noms-вариантов (3 шт) в миграции 108:**

1. «Быстро поедешь — быстро сорвёшься. Я рекомендую Нормальный темп, но решать тебе, гонщик. 🏎️»
2. «Стабильность > скорость. Нормальный темп — как дыхание: ровное и не заметное. Но если хочешь ускориться — не отговариваю.»
3. «Выбирай так, чтобы не ненавидеть меня через неделю. Нормальный темп — друг марафонца. Быстрый — друг спринтера (и травм).»

---

### 🧬 Phenotype Quiz Flow (Shared — онбординг шаг 9 + Profile edit)

6 экранов (intro + 4 вопроса + результат). Все тексты **уже в БД** (миграция 062, ключи `phenotype.*` + `profile.phenotype_*`).

Запускается кнопкой `[🚀 Пройти тест]` на экране `edit_phenotype` (ЧАСТЬ 3 §14) ИЛИ автоматически на шаге `registration_step_phenotype_quiz` онбординга.

**Экран A — Intro (`edit_phenotype`):**

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 🧬 Тип телосложения (Фенотип)              │
│                                            │
│ Твой текущий тип: {phenotype_label}        │
│                                            │
│ Пройди короткий тест (4 вопроса), чтобы    │
│ оптимизировать макро под твоё телосложение.│
│                                            │
│ 📊 Результат влияет на расчёт белка        │
│    по безжировой массе тела.               │
│                                            │
│ 💬 Noms: "Не бывает широкой кости, бывают  │
│ неправильные макросы. Давай разберёмся,    │
│ кто ты: эктоморф или просто любишь хлеб."  │
╰────────────────────────────────────────────╯
```
Кнопки (контекст-зависимые):
- Всегда: `[🚀 Пройти тест → cmd_start_phenotype_quiz]` (text: `profile.start_test`)
- Profile edit только: `[🔄 Сбросить на Стандартное → cmd_select_phenotype_default]`
- Онбординг только: `[⏭ Пропустить → cmd_skip_step]` *(migration 102 ✅ applied)*
- Profile edit только: `[🔙 Назад → cmd_back]`

**Ключи текста в БД:** `profile.phenotype_hint`, `profile.phenotype_detail`, Noms commentary — из спеки §14 (существующий текст).

---

**Экран B — Q1/4 (`phenotype.q1_prompt`):**

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 🧬 Тип телосложения                        │
│                                            │
│ В1/4 — Где облегающая футболка             │
│ давит сильнее всего?                       │
│                                            │
│ Реальное тело прямо сейчас,                │
│ не идеальное.                              │
╰────────────────────────────────────────────╯
```
Кнопки (из `phenotype.q1_a/b/c`):
- `[Плечи и грудь → phen_q1_a]`
- `[Равномерно везде → phen_q1_b]`
- `[Живот и талия → phen_q1_c]`
- `[🔙 Назад → cmd_back]`

---

**Экран C — Q2/4 (`phenotype.q2_prompt`):**

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 🧬 Тип телосложения                        │
│                                            │
│ В2/4 — Силовые тренировки                  │
│ за последний год?                          │
│                                            │
│ Честно — это не оценка, это математика.    │
╰────────────────────────────────────────────╯
```
Кнопки (из `phenotype.q2_a/b/c`):
- `[Не тренируюсь / только кардио → phen_q2_a]`
- `[Иногда (1-2 раза в неделю) → phen_q2_b]`
- `[Регулярно 3+ раз в неделю → phen_q2_c]`
- `[🔙 Назад]`

---

**Экран D — Q3/4 (`phenotype.q3_prompt`):**

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 🧬 Тип телосложения                        │
│                                            │
│ В3/4 — Пощупай руку или бедро              │
│ в расслабленном состоянии.                 │
│ Как ощущается?                             │
╰────────────────────────────────────────────╯
```
Кнопки (из `phenotype.q3_a/b/c`):
- `[Мягко — мышц почти нет → phen_q3_a]`
- `[Обычно — жир и тонус вместе → phen_q3_b]`
- `[Плотно и упруго — мышцы видны → phen_q3_c]`
- `[🔙 Назад]`

---

**Экран E — Q4/4 (`phenotype.q4_prompt`):**

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 🧬 Тип телосложения                        │
│                                            │
│ В4/4 — Вес за последние 3–5 лет?           │
╰────────────────────────────────────────────╯
```
Кнопки (из `phenotype.q4_a/b/c`):
- `[Йо-йо — терял и набирал → phen_q4_a]`
- `[Стабильный (±2 кг) → phen_q4_b]`
- `[Постепенно набираю целенаправленно → phen_q4_c]`
- `[🔙 Назад]`

---

**Экран F — Результат (динамический, 4 варианта):**

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 🧬 Твой тип телосложения:                  │
│                                            │
│ {phenotype_label}                          │
│                                            │
│ {phenotype.result_explanation_{default|monw│
│  |obese|athlete}}                          │
│                                            │
│ 📊 Макросы пересчитаны под твоё тело.      │
╰────────────────────────────────────────────╯
```

4 возможных текста результата (из БД, `phenotype.result_explanation_*`):

| Фенотип | Лейбл | Объяснение (ru, буквальный текст БД) |
|---|---|---|
| `default` (standard) | Стандартное | «Ты в нормостенической зоне — сбалансированный жир и мышцы. Цели считаются по реальному весу. Чинить нечего — просто поддерживай привычки.» |
| `monw` | MONW (Худой полный) | «Вес нормальный снаружи, но жировой процент выше, чем кажется, а мышц меньше. Я подкорректировал цель по белку — здесь важнее состав, а не цифра на весах.» |
| `obese` | Модифицированное | «Вес концентрируется в области живота — это меняет расчёт тощей массы. Использую консервативную формулу, чтобы цель по белку не была завышена. Маленькие постоянные победы — вот стратегия.» |
| `athlete` | Атлетическое | «Плотная мышечная масса, мало жира — твоё тело это метаболическая машина. Цели выставлены так, чтобы защитить мышцы. Не экономь на белке.» |

Кнопки (контекст-зависимые):
- Онбординг: `[✅ Отлично → onboarding:country]` (auto-переход к следующему шагу)
- Profile edit: `[✅ Принять → cmd_my_plan]` + `[🔄 Пройти заново → cmd_start_phenotype_quiz]`

**Сохранение:** RPC `set_user_phenotype` (записывает `phenotype` + `phenotype_answers` JSONB + пересчитывает макросы через `calculate_user_targets`).
**Миграции:** 062 (phenotype quiz backend + переводы ×13), 055 (calculate_user_targets с учётом phenotype).
**Статус:** ✅ тексты в БД готовы (ru + ещё 12 языков). 📝 headless-описание в `ui_screens` — TBD migration (на данный момент quiz запускается через n8n `02_Onboarding` / `04_Menu`).

---

## 🗂 ЧАСТЬ 3 — Главное меню / Profile v5

Исходное описание веток Profile v5 (§1-§19). Первые 9 — headless (`ui_screens`), §10-§19 — черновики, требуют миграций 097-100.

## 1\. profile\_main (Профиль — главный)

**Мета:** `input_type=inline_kb`, `render_strategy=replace_existing`, `business_data_rpc=get_profile_business_data`, `back_screen_id_default=NULL` (корневой экран Profile).

**Целевой текст (session 6 mockup — TBD migration 098):**

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 👤 Досье Агента: {first_name}              │
│ В системе с {member_since_month} {year}    │
│                                            │
│ 💎 {status_free | status_premium}          │
│ ⚡ {limit_logs_free | limit_logs_unlimited}│
│                                            │
│ ⚖️ Биометрия и Цель:                       │
│ ▫️ Текущий вес: {weight_kg} кг             │
│ ▫️ План: {goal_icon} {goal_type_label}     │
│ ▫️ Норма: {target_calories} ккал/день      │
│                                            │
│ 💬 Noms: "{sage_free_N | sage_premium_N}"  │
╰────────────────────────────────────────────╯
```

Все нужные ключи **уже существуют** в `ui_translations`: `profile.title_agent`, `profile.member_since`, `profile.status_free`, `profile.status_premium`, `profile.limit_logs_free`, `profile.limit_logs_unlimited`, `profile.bio_and_goal`, `profile.current_weight`, `profile.plan_label`, `profile.daily_norm`, `profile.sage_free_1..3`, `profile.sage_premium_1..3`. Нужна только миграция, которая соберёт их в `profile.main_text` и расширит `get_profile_business_data` полями `first_name`, `member_since_*`, `weight_kg`, `goal_icon`, `goal_type_label`, `target_calories`, `sage_quote`.

**Клавиатура (реальная из `ui_screen_buttons`):**

Row 0 (две кнопки, по `visible_condition`):

- `[⭐ Включить PRO (Безлимит) → cmd_premium_plans]` — при `u.subscription_status='free'` (`buttons.go_pro_unlimited`, icon `icon_stars=⭐`)  
- `[💳 Управление подпиской → cmd_profile_subscription]` — при `u.subscription_status<>'free'` (`buttons.manage_subscription`, icon `icon_card=💳`)

Row 1: `[⚖️ Обновить вес → cmd_update_weight]` `[🔔 Помощь → cmd_help]` (кнопки: `buttons.update_weight`\+`icon_weight`, `buttons.help`\+`icon_bell` — ⚠ `icon_bell` отсутствует в `app_constants`)

Row 2: `[🎯 Мой план → cmd_my_plan]` `[⚙️ Настройки → cmd_settings]` (кнопки: `buttons.my_plan`\+`icon_goal=🎯`, `buttons.settings`\+`icon_settings=⚙️`)

---

## 2\. my\_plan (Мой План)

**Мета:** `input_type=inline_kb`, `render_strategy=replace_existing`, `business_data_rpc=get_my_plan_business_data`, `back_screen_id_default=profile_main`.

**Целевой текст (session 6 mockup — TBD migration 097):**

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 🎯 Мой План                                │
│                                            │
│ 📉 Цель: {goal_type_label}                 │
│ 🚶 Темп: {speed_indicator} {goal_speed_label}│
│         ({speed_pct_label})                │
│ 🏃 Активность: {activity_label}            │
│ 💪 Тренировки: {training_label}            │
│          ({protein_g_per_kg}г/кг белка)    │
│                                            │
│ 🧬 Телосложение: {phenotype_label}         │
│                                            │
│ 📊 Норма: {target_calories} ккал           │
│   🥩 {protein_g}г  🥑 {fat_g}г  🍞 {carbs_g}г│
│                                            │
│ 💬 Noms: "{noms_commentary}"               │
╰────────────────────────────────────────────╯
```

Нужные ключи для расширения (TBD migration 097):

- `profile.activity_label_{sedentary|light|moderate|active|very_active}` — отсутствуют, TBD.  
- `profile.training_label_{strength|cardio|mixed|none}` — отсутствуют, TBD.  
- `profile.noms_commentary_plan_{lose|maintain|gain}` — отсутствуют, TBD. Пример для `goal_type=lose`: `"План надёжный, как швейцарские часы. Если начнёшь двигаться чаще — дай знать, накину тебе белка, чтобы мышцы не сгорели!"`

Уже существующие: `profile.training_type`, `profile.body_type`, `profile.speed_deficit`, `profile.speed_surplus`, `profile.phenotype_*`, `profile.daily_norm`.

**Клавиатура (реальная):** Row 0: `[🎯 Изменить цель → cmd_edit_goal]` `[🏃 Активность → cmd_edit_activity]` Row 1: `[💪 Тренировки → cmd_edit_training]` `[🧬 Тип тела → cmd_edit_phenotype]` Row 2: `[📊 Личные метрики → cmd_personal_metrics]` *(target\_screen=personal\_metrics)* Row 3: `[🔙 Назад → cmd_back]`

Реальные icons: `icon_goal=🎯`, `icon_activity=🏃`, `icon_training` ⚠ (missing в app\_constants), `icon_body_type=🧬`, `icon_stats=📊`, `icon_back=🔙`.

**Session 6 правка:** добавить Noms commentary в конце текста, стиль зависит от `goal_type`.

---

## 3\. settings (Настройки)

**Мета:** `input_type=inline_kb`, `render_strategy=replace_existing`, `business_data_rpc=get_settings_business_data`, `back_screen_id_default=profile_main`.

**Целевой текст (session 6 — TBD migration 099):**

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ ⚙️ Настройки                               │
│                                            │
│ 🌐 Язык: {current_language_display}        │
│ 🌍 Страна: {current_country_display}       │
│ 🕐 Часовой пояс: {current_timezone_display}│
│                                            │
│ 💬 Noms: "{profile.sage_settings}"         │
╰────────────────────────────────────────────╯
```

Noms quote уже есть: `profile.sage_settings` \= *"Настрой меня так, чтобы я был полезным другом, а не назойливым будильником."* — нужно встроить в `profile.settings_text`. Также `get_settings_business_data` должен вернуть `current_country_display`.

**Клавиатура (реальная):** Row 0: `[🌐 Язык → cmd_edit_lang]` `[🌍 Страна → cmd_edit_country]` Row 1: `[🕐 Часовой пояс → cmd_edit_timezone]` `[🔔 Уведомления → cmd_notifications]` Row 2: `[🔙 Назад → cmd_back]`

Реальные icons: `icon_lang=🌐`, `icon_globe=🌍`, `icon_clock=🕐` (⚠ в app\_constants `icon_clock=⏰`, не `🕐` — расхождение эмодзи), `icon_bell` ⚠ missing, `icon_back=🔙`.

---

## 4\. personal\_metrics (Личные метрики)

**Мета:** `input_type=inline_kb`, `render_strategy=replace_existing`, `business_data_rpc=get_personal_metrics_business_data`, `back_screen_id_default=my_plan` ✅ (иерархия: Back ведёт в my\_plan, а не в profile\_main).

**Целевой текст (session 6 — TBD migration 099):**

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 📊 Личные метрики                          │
│                                            │
│ ⚖️ Вес: {weight_kg} кг                     │
│ 📏 Рост: {height_cm} см                    │
│ 🎂 Возраст: {age}                          │
│ 👨 Пол: {gender_label}                     │
╰────────────────────────────────────────────╯
```

RPC `get_personal_metrics_business_data` возвращает `age`, `gender`, `birth_date` (миграция 091). *(Поле `target_weight_kg` в RPC может быть — в UX не используем по решению 2026-04-21, см. ЧАСТЬ 2 § «Решение про target_weight_kg».)* Нужно расширить текст шаблона.

**Клавиатура:** Row 0: `[⚖️ Изменить вес → cmd_edit_weight]` `[📏 Изменить рост → cmd_edit_height]` Row 1: `[🎂 Изменить возраст → cmd_edit_age]` `[🚻 Изменить пол → cmd_edit_gender]` Row 2: `[🔙 Назад → cmd_back]`

Icons: `icon_weight=⚖️`, `icon_height=📏`, `icon_age=🎂`, `icon_gender=🚻`, `icon_back=🔙`.

Meta row 0-1: `target_screen='ask_weight'|'ask_height'|'ask_age'`, `set_status='edit_weight'|'edit_height'|'edit_age'`. У `cmd_edit_gender` нет target\_screen (ожидается отдельный gender picker — TBD).

---

## 5\. help (Помощь)

**Мета:** `input_type=inline_kb` (с URL-кнопкой), `render_strategy=replace_existing`, `business_data_rpc=NULL`, `back_screen_id_default=profile_main`.

**Целевой текст (session 6 — TBD migration 099):**

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ ❓ Помощь и Поддержка                      │
│                                            │
│ Нужна помощь? Свяжись с нашей командой.    │
│                                            │
│ 💬 Noms: "{profile.sage_help}"             │
╰────────────────────────────────────────────╯
```

Noms quote готов: `profile.sage_help` \= *"Заблудился в калориях или нашёл баг? Моя команда поддержки уже греет кофе."*

**Клавиатура:** Row 0: `[💬 Связаться с поддержкой → URL: {profile.support_url}]` (URL из `ui_translations.profile.support_url` \= `https://t.me/AutoRiot`; callback\_data в ui\_screen\_buttons \= `cmd_open_support_url`, icon\_const\_key=NULL) Row 1: `[🔒 Привязать телефон → cmd_bind_phone]` 🆕 *(условный рендер: показывается только если `users.phone_number IS NULL`. См. [[phone-collection-strategy]] Точка 3)* Row 2: `[🗑 Удалить аккаунт → cmd_delete_account]` *(target\_screen=delete\_account\_confirm)* — в БД `icon_const_key='icon_trash'` ⚠ missing в app\_constants (fallback на `icon_delete=🗑️` или на пусто). Row 3: `[🔙 Назад → cmd_back]`

**Session 6 правка:** Noms обязателен.

**🆕 Phone binding (TBD):** при `phone_number IS NOT NULL` — кнопка `🔒 Привязать телефон` скрывается, опционально в тексте `help` появляется статусная строка «🔒 Телефон привязан». Текст приглашения от Sage (TBD migration, ключ `profile.sage_phone_bind_invite`): *«Telegram-аккаунты иногда крадут. Дай номер, и я всегда узнаю тебя, даже если зайдёшь с другого профиля.»* Полная стратегия: [[phone-collection-strategy]].

---

## 6\. ask\_weight (Ввод веса)

**Мета:** `input_type=text_input`, `render_strategy=replace_existing`, `validation_rules={type:'numeric', min:20, max:300, error_key:'errors.invalid_weight'}`, `save_rpc=set_user_weight`, `back_screen_id_default=personal_metrics`.

**Текст (TBD — ключ `ask_weight.prompt` отсутствует в БД):**

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ ⚖️ Введи вес (кг):                         │
│                                            │
│   ⌨️  [бот ждёт текстовое сообщение]        │
╰────────────────────────────────────────────╯
```

Сообщение об ошибке: `errors.invalid_weight` \= *"Введи число от 20 до 300"* ✅ существует.

**Клавиатура (реальная):** `[❌ Отмена → cmd_back]` (button: `buttons.cancel` \= "Отмена", icon `icon_cancel=❌`)

**Session 6 правка:** на FSM-экранах кнопка выхода называется **"🚫 Отмена"**, психологически — юзер прерывает процесс. Callback `cmd_back` не меняется. В БД сейчас — `icon_cancel=❌`, а не 🚫. Статус: либо ок (❌ тоже "отмена"), либо TBD migration 100 (поменять icon на 🚫).

**Статус:** текст prompt — TBD migration 100 (добавить ключ `ask_weight.prompt`). Клавиатура — ✅ функционально, ⚠ emoji отличается от mockup.

---

## 7\. ask\_age (Ввод возраста)

**Мета:** `input_type=text_input`, `render_strategy=replace_existing`, `validation_rules={type:'integer', min:13, max:120, error_key:'errors.invalid_age'}`, `save_rpc=set_user_age`, `back_screen_id_default=personal_metrics`.

**Текст (TBD — ключ `ask_age.prompt` отсутствует):**

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 🎂 Напиши свой возраст (например: 41)      │
│                                            │
│   ⌨️  [бот ждёт число]                      │
╰────────────────────────────────────────────╯
```

Сообщение об ошибке: `errors.invalid_age` \= *"Введи возраст от 13 до 120"* ✅.

**Клавиатура:** `[❌ Отмена → cmd_back]`

**Session 6 правка:** юзер вводит просто возраст (целое число), а не дату рождения. `save_rpc=set_user_age` сам конвертирует в `birth_date` под капотом. Формат YYYY-MM-DD использовать НЕ нужно. `validation_rules.type` в БД уже `integer` ✅.

**Статус:** текст prompt — TBD migration 100\. Validation — ✅. Клавиатура — ✅.

---

## 8\. ask\_height (Ввод роста)

**Мета:** `input_type=text_input`, `render_strategy=replace_existing`, `validation_rules={type:'numeric', min:50, max:250, error_key:'errors.invalid_height'}`, `save_rpc=set_user_height`, `back_screen_id_default=personal_metrics`.

**Текст (TBD — ключ `ask_height.prompt` отсутствует):**

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 📏 Введи рост (см):                        │
│                                            │
│   ⌨️  [бот ждёт текстовое сообщение]        │
╰────────────────────────────────────────────╯
```

Сообщение об ошибке: `errors.invalid_height` \= *"Введи рост от 50 до 250 см"* ✅.

**Клавиатура:** `[❌ Отмена → cmd_back]`

**Статус:** текст prompt — TBD migration 100\. Validation — ✅. Клавиатура — ✅.

---

## 9\. delete\_account\_confirm (Подтверждение удаления)

**Мета:** `input_type=inline_kb`, `render_strategy=delete_and_send_new` (terminal), `business_data_rpc=get_profile_business_data` (переиспользуется — уже возвращает current\_streak \+ xp \+ nomscoins), `back_screen_id_default=help`.

**Текст в БД сейчас** (`delete_account.warning_body` ru):

```
╔═══════════════════════════════════════════════╗
║ 💬 NOMSaibot                                  ║
╠═══════════════════════════════════════════════╣
║  ⚠️ Удаление аккаунта                         ║
║                                               ║
║  Это действие навсегда удалит:                ║
║    • Твой стрик: {current_streak} дней        ║
║    • Твой XP: {xp}                            ║
║    • Твои NomsCoins: {nomscoins}              ║
║                                               ║
║  Отменить можно только в течение 30 дней.     ║
╚═══════════════════════════════════════════════╝
```

**Клавиатура (реальная):** Row 0: `[🗑 Да, удалить навсегда → cmd_confirm_delete]` (button: `buttons.confirm_delete` \= "Да, удалить навсегда"; icon `icon_trash` ⚠ missing, fallback `icon_delete=🗑️`) Row 1: `[🔙 Отмена → cmd_help]` (button: `buttons.cancel` \= "Отмена"; icon `icon_back=🔙`; callback возвращает в help)

**Статус:** текст ✅ соответствует mockup (с лёгкими стилевыми правками можно улучшить — двойная рамка ⚠ DELETE ⚠ в mockup была декоративной, не обязательной). Клавиатура ✅.

---

### **📝 Новые экраны для Profile v5 (Блок 1: Выбор параметров)**

*Скопируй этот блок и вставь в конец своего документа.*

---

### **10\. edit\_goal**

**Meta:** input\_type=inline\_kb, render\_strategy=replace\_existing, business\_data\_rpc=get\_my\_plan\_business\_data

**Text:**

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 🎯 Твоя Цель                               │
│                                            │
│ Куда мы движемся? От этого зависит расчет  │
│ твоей нормы калорий и дефицита.            │
│                                            │
│ Текущая: {goal_type_label}                 │
│                                            │
│ 💬 Noms: "Выбирай с умом. Если хочешь      │
│ кубики пресса — нам вниз, если массу       │
│ как у Халка — вверх."                      │
╰────────────────────────────────────────────╯
```

**Keyboard:** \[📉 Похудение → cmd\_set\_goal\_lose\]

\[⚖️ Поддержание → cmd\_set\_goal\_maintain\]

\[📈 Набор массы → cmd\_set\_goal\_gain\]

\[🚫 Отмена → cmd\_my\_plan\]

---

### **11\. edit\_activity**

**Meta:** inline\_kb, replace\_existing, get\_my\_plan\_business\_data

**Text:**

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 🏃 Уровень активности                      │
│                                            │
│ Как много ты двигаешься в течение дня      │
│ (не считая тренировок)?                    │
│                                            │
│ 💬 Noms: "Будь честен. Если ты офисный     │
│ ниндзя, не пиши 'Тяжелый труд', иначе      │
│ я насчитаю тебе лишнего."                  │
╰────────────────────────────────────────────╯
```

**Keyboard:**

\[💻 Сидячий (Офис) → cmd\_set\_act\_sedentary\]

\[🚶 Легкий (Прогулки) → cmd\_set\_act\_light\]

\[⚡️ Средний (Весь день на ногах) → cmd\_set\_act\_moderate\]

\[🏋️ Тяжелый (Физ. труд) → cmd\_set\_act\_heavy\]

\[🚫 Отмена → cmd\_my\_plan\]

---

### **12\. notifications**

**Meta:** inline\_kb, replace\_existing, get\_settings\_business\_data

**Text:**

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 🔔 Режим уведомлений                       │
│                                            │
│ Выбери, как часто мне тебя пинать:         │
│                                            │
│ 🧘 Zen: Только отчет вечером.              │
│ ⚖️ Balanced: Утро + Вечер + Важное.        │
│ 🦁 Beast: Напоминаю о каждом приеме пищи.  │
│                                            │
│ 💬 Noms: "Не хочешь слышать меня часто?    │
│ Ставь Zen. Но потом не ной, что забыл      │
│ записать обед!"                            │
╰────────────────────────────────────────────╯
```

**Keyboard:**

\[🧘 Zen\] \[⚖️ Balanced\] \[🦁 Beast\] (три в ряд)

\[← Назад → cmd\_settings\]

---

### **13\. edit\_training**

**Meta:** inline\_kb, replace\_existing, get\_my\_plan\_business\_data

**Text:**

Plaintext

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 💪 Тип тренировок                            │
│                                            │
│ Чем занимаешься в зале (или дома)? Это     │
│ влияет на расчет нормы белка.              │
│                                            │
│ 💬 Noms: "Не ври мне. Если твой спорт —    │
│ это шахматы, выбирай 'Нет тренировок'.     │
│ Я всё равно узнаю по твоему метаболизму."  │
╰────────────────────────────────────────────╯
```

**Keyboard:** \[🏋️ Силовые (Тренажерный зал) → cmd\_set\_train\_strength\]

\[🏃 Кардио (Бег, Вело, Плавание) → cmd\_set\_train\_cardio\]

\[🤸 Смешанные (Кроссфит, Единоборства) → cmd\_set\_train\_mixed\]

\[🛋️ Нет тренировок → cmd\_set\_train\_none\]

\[🚫 Отмена → cmd\_my\_plan\]

---

### **14\. edit\_phenotype**

**Meta:** inline\_kb, replace\_existing, get\_my\_plan\_business\_data

**Text:**

Plaintext

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 🧬 Тип телосложения (Фенотип)                │
│                                            │
│ Твой текущий тип: {phenotype_label}        │
│                                            │
│ Хочешь, чтобы я точнее настроил твои макро-│
│ нутриенты? Пройди короткий тест из 4       │
│ вопросов, чтобы я понял твою генетику.     │
│                                            │
│ 💬 Noms: "Не бывает широкой кости, бывают  │
│ неправильные макросы. Давай разберемся,    │
│ кто ты: эктоморф или просто любишь хлеб."  │
╰────────────────────────────────────────────╯
```

**Keyboard:** \[🚀 Начать тест (4 вопроса) → cmd\_start\_phenotype\_quiz\]

\[🔄 Сбросить на Стандартное → cmd\_set\_phenotype\_default\]

\[🚫 Отмена → cmd\_my\_plan\]

---

### **15\. edit\_gender**

**Meta:** inline\_kb, replace\_existing, get\_personal\_metrics\_business\_data

**Text:**

Plaintext

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 🚻 Выбор пола                                │
│                                            │
│ Базовый метаболизм (BMR) рассчитывается    │
│ по-разному для мужчин и женщин.            │
│                                            │
│ 💬 Noms: "Только биология, ничего личного. │
│ Гормоны решают, как быстро горят калории." │
╰────────────────────────────────────────────╯
```

**Keyboard:** \[👨 Мужской → cmd\_set\_gender\_male\]  \[👩 Женский → cmd\_set\_gender\_female\]

\[🚫 Отмена → cmd\_personal\_metrics\]

---

### **16\. edit\_lang**

**Meta:** inline\_kb, replace\_existing, get\_settings\_business\_data

**Text:**

Plaintext

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 🌐 Язык / Language                           │
│                                            │
│ Выбери язык общения.                       │
│ Текущий: {current_language_display}        │
│                                            │
│ 💬 Noms: "I speak 13 languages, amigo.     │
│ Выбирай любой, я всё равно буду            │
│ подкалывать тебя с акцентом."              │
╰────────────────────────────────────────────╯
```

**Keyboard:** *(Генерируется динамически из 13 языков, сетка 2хX)*

\[🇬🇧 English → cmd\_set\_lang\_en\]  \[🇪🇸 Español → cmd\_set\_lang\_es\]

\[🇷🇺 Русский → cmd\_set\_lang\_ru\]  \[🇫🇷 Français → cmd\_set\_lang\_fr\]

*(...остальные языки...)*

\[🚫 Отмена → cmd\_settings\]

---

### **17\. edit\_country**

**Meta:** inline\_kb, replace\_existing, get\_settings\_business\_data

**Text:**

Plaintext

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 🌍 Страна проживания                         │
│                                            │
│ Влияет на базу продуктов и валюту оплаты.  │
│ Текущая: {current_country_display}         │
│                                            │
│ 💬 Noms: "Переехал? Обнови локацию, чтобы  │
│ я не искал хамон в московской Пятерочке."  │
╰────────────────────────────────────────────╯
```

**Keyboard:** \[📍 Определить по геолокации (Авто) → cmd\_auto\_location\]

\[📋 Выбрать из списка → cmd\_list\_countries\]

\[🚫 Отмена → cmd\_settings\]

---

### **18\. edit\_timezone**

**Meta:** inline\_kb, replace\_existing, get\_settings\_business\_data

**Text:**

Plaintext

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 🕐 Часовой пояс                              │
│                                            │
│ Чтобы уведомления и сброс стриков          │
│ происходили в правильное время.            │
│ Текущий: {current_timezone_display}        │
│                                            │
│ 💬 Noms: "Настрой время, иначе я буду      │
│ кричать 'Пора завтракать!' в три ночи."    │
╰────────────────────────────────────────────╯
```

**Keyboard:** \[📍 Синхронизировать по гео → cmd\_auto\_location\]

\[📋 Выбрать вручную → cmd\_list\_timezones\]

\[🚫 Отмена → cmd\_settings\]

---

### **19\. edit\_speed**

**Meta:** inline\_kb, replace\_existing, get\_my\_plan\_business\_data

**Text:**

Plaintext

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 🏃 Темп (Скорость)                           │
│                                            │
│ Насколько быстро ты хочешь достичь своей   │
│ цели: {goal_type_label}?                   │
│                                            │
│ 💬 Noms: "Быстро поедешь — быстро сорвешься. │
│ Я рекомендую Нормальный темп, но решать    │
│ тебе, гонщик."                             │
╰────────────────────────────────────────────╯
```

**Keyboard:** *(Рендерится динамически в зависимости от goal\_type)*

*Если Похудение (lose):*

\[🟡 Медленно (-10%) → cmd\_set\_speed\_slow\]

\[🟢 Нормально (-15%) → cmd\_set\_speed\_normal\]

\[🔴 Быстро (-20%) → cmd\_set\_speed\_fast\]

\[🚫 Отмена → cmd\_my\_plan\]

*Если Набор массы (gain):*

\[🟡 Плавно (+8%) → cmd\_set\_speed\_slow\]

\[🟢 Нормально (+10%) → cmd\_set\_speed\_normal\]

\[🔴 Агрессивно (+15%) → cmd\_set\_speed\_fast\]

\[🚫 Отмена → cmd\_my\_plan\]

---

---

## 🗂 ЧАСТЬ 4 — Progress Hub

**Статус:** 📝 черновик (5 экранов: progress_main, quests, league, friends_info, shop). Все legacy, в `ui_screens` отсутствуют. Будет дополнено в Пачке D: `quests_detail` (active / all_done), `league_info`, `friends_how_it_works`, `shop_insufficient_coins`.

### **Блок 2: Ветка «Прогресс» (Game Hub)**

### **20\. progress\_main (Главный экран Прогресса)**

**Meta:** input\_type=inline\_kb, render\_strategy=replace\_existing, business\_data\_rpc=get\_progress\_business\_data

**Text (Free user):**

Plaintext

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 🚀 Твой Прогресс                           │
│                                            │
│ 🔥 Стрик: {current_streak} дней  | 🔋 Мана: {mana_current}/{mana_max} │
│ 🌟 XP: {xp}         | 💎 {nomscoins} Coins│
│                                            │
│ 🏆 Лига: {league_icon} {league_display}      │
│ 👑 {league_position_text}                  │
│                                            │
│ 💬 Noms: "{progress_insight}"              │
╰────────────────────────────────────────────╯
```

*(Прим: progress\_insight динамически подставляется из БД в зависимости от того, близок ли юзер к потере стрика или повышению в лиге).*

**Keyboard:** \[📜 Квесты → cmd\_quests\] \[🏆 Моя Лига → cmd\_league\]

\[👥 Банда (Друзья) → cmd\_friends\_info\] \[🛒 Магазин → cmd\_shop\]

---

### **21\. quests (Ежедневные задания)**

**Meta:** inline\_kb, replace\_existing, `get_quests_rpc` (migration 133, обновлён 139).

**Status:** ✅ live (migration 139). Headless с 3 секциями.

**Реальный layout** (применено 2026-04-24, по решению user — legacy section headers):

```
📋 Твои квесты

⬜ {daily_1_title} (+{xp} XP)
⬜ {daily_2_title} (+{xp} XP)
⬜ {daily_3_title} (+{xp} XP)

📅 Недельные:
✅ {weekly_1_title} (+{xp} XP)
✅ {weekly_2_title} (+{xp} XP)

🏅 Достижения:
... (если есть one-time квесты)

💬 Noms: "{insight}"   ← either all_done или insight_remaining "Ещё N — ты справишься!"
```

*(Прим: ⬜/✅ checkboxes динамические по `is_completed` flag. Section headers `quests.section_weekly` / `section_achievements` — existing keys в БД).*

**Keyboard:** `[🔙 Назад → cmd_back]` (универсальный, не дублируем `cmd_back_to_progress` — back_screen_id_default=`progress_main`).

---

### **22\. league (Лидерборд Лиги)**

**Meta:** inline\_kb, replace\_existing, `get_league_rpc` (migration 134, обновлён 139, 140).

**Status:** ✅ live (migration 140). Headless с двумя branches: active (4-neighbor window) и empty (countdown до понедельника).

**Active state — реальный layout** (применено 2026-04-24, по решению user — 4-neighbor window вместо full zone split):

```
🏆 Таблица лиги

Твоя лига: 🥑 Авокадо
Неделя: 27.04 — 03.05
⏰ До конца: 6d 4h

Топ-5 переходят в следующую лигу.

► 1. Vladislav — 1060 🌟    ← self с ► marker (per spec §10.1)
2. Sofia — 890 🌟
3. {neighbor} — {xp} 🌟
4. {neighbor} — {xp} 🌟
5. {neighbor} — {xp} 🌟

Твоё место: #1 из 20

💬 Noms: "{insight}"          ← insight_leader / insight_close / collect_xp
```

**Empty state** (`my_rank IS NULL` — нет членства в league_memberships):

```
🏆 Таблица лиги

Вступишь в лигу в понедельник!

До понедельника: 7д

А пока — копи XP и готовься!

💬 Noms: "Вступишь в лигу в понедельник!"
```

**Keyboard:** `[ℹ️ Как работают лиги? → cmd_league_info]` + `[🔙 Назад → cmd_back]` (универсальный).

*(Прим: subtitle, until_monday, empty_tip — новые ключи migration 140 × 13 langs).*

---

### **23\. friends\_info (Банда / Рефералы) — STATEFUL UI**

**Meta:** inline\_kb, replace\_existing, `get_friends_info_rpc` (migration 135, v3 — migration 140).

**Status:** ✅ live (migration 140). **Stateful UI** — один screen_id рендерит 2 разных экрана:

| Условие (computed в RPC) | Layout | Buttons |
|---|---|---|
| `ambassador_tier IS DISTINCT FROM 'active' AND paid_referral_count < 5 AND NOT is_trainer` | **Novice** (см. ниже) | Share invite + Info + Back |
| `ambassador_tier = 'active' OR paid_referral_count >= 5 OR is_trainer = true` | **Ambassador** (см. §11.3) | Share code + Payout + Stats + Back |

**Novice layout** (per spec §11.1, structured zero state — даже при count=0):

```
👥 Твоя Банда

В банде: {total_invited} агентов
Активных: {active_count}
Ожидают: {pending_count}
Заработано: {earned_coins} NomsCoins

🏆 До бесплатного PRO: {paid_count}/4    ← target из app_constants.referral_premium_threshold

🔗 Твоя ссылка:
{referral_link}

💬 Noms: "{cta}"      ← cta_newbie_1 (count=0) / cta_active_1 (count>=1)
```

**Ambassador layout** (см. §11.3 в этом файле — описан там).

**Keyboard split via `visible_condition`:**
- Novice: `[📤 Поделиться → share_invite_link]` + `[ℹ️ Подробнее → cmd_friends_how_it_works]` + `[🔙 Назад → cmd_back]`
- Ambassador: `[📤 Поделиться кодом → share_ambassador_code]` + `[💳 Вывести средства → cmd_start_payout]` + `[👥 Статистика → cmd_ambassador_stats]` + `[🔙 Назад → cmd_back]`

*(Прим: 🏆 prefix перед PRO goal — `app_constants.icon_pro_goal`. 🔗 prefix — `app_constants.icon_link`. Threshold 4 — `app_constants.referral_premium_threshold`. Threshold 5 для Ambassador — `app_constants.ambassador_referral_threshold`. Reward amounts 50/100 в `friends_how_it_works` (§11.2) — `app_constants.referral_escrow_coins/xp`).*

---

### **24\. shop (Магазин и Заморозки)**

**Meta:** inline\_kb, replace\_existing, get\_shop\_business\_data

**Text:**

Plaintext

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 🛒 Магазин NOMS                            │
│                                            │
│ 💳 Твой баланс: 💎 {nomscoins} Coins       │
│ 🔋 Энергия: {mana_current}/{mana_max} Маны │
│ ❄️ В инвентаре: {streak_freezes} Заморозок │
│                                            │
│ 💬 Noms: "Мана на нуле? Купи пополнение    │
│ или заморозь стрик, пока мы не упали на    │
│ дно рейтинга!"                             │
╰────────────────────────────────────────────╯
```

**Keyboard:** \[🔋 Восстановить Ману (💎 300\) → cmd\_buy\_mana\]

\[❄️ Купить Заморозку (💎 500\) → cmd\_buy\_freeze\]

\[⭐ Купить Безлимит (PRO) → cmd\_premium\_plans\] *(Кнопка скрыта, если статус Premium)*

\[🔙 Назад в Прогресс → cmd\_progress\]

---

---

## 🗂 ЧАСТЬ 5 — Мой день / Stats

**Статус:** 📝 черновик (2 экрана: `stats_main`, `food_log_result`). Legacy в n8n (`04_Menu` stats блок + `03_AI_Engine` для food_log_result). Будет дополнено: `day_history` (прошлые дни), `edit_last_log`.

### **Блок 3: Оперативный дашборд «Мой день»**

### **25\. stats\_main (Главный экран дня)**

**Статус:** ✅ Live (migration 122 + 124, 2026-04-23). Headless, единый template на 13 языков.

**Meta:** input\_type=inline\_kb, render\_strategy=replace\_existing, business\_data\_rpc=**get\_daily\_stats\_rpc** (migration 124 переименовала из get\_stats\_business\_data).

**Template** (в `ui_translations.*.content.stats.main_text`, идентичен для всех 13 языков — локализация через `{tr:...}` placeholder'ы):

```
{{icon_stats}} <b>{tr:buttons.stats}</b>
{{deco_list}} {current_date}  {{icon_clock}} {current_time}

{{icon_kcal}} <b>{calories_consumed} / {calories_target}</b> {tr:report.unit_kcal}
{progress_bar}  <b>{percent}%</b>  ·  {tr:report.remaining_label} {calories_left}

{{icon_protein}} <b>{p}</b>{tr:report.unit_g} {p_status}   {{icon_fat}} <b>{f}</b>{tr:report.unit_g} {f_status}   {{icon_carbs}} <b>{c}</b>{tr:report.unit_g} {c_status}

{{icon_speech}} Noms: "{tr:{insight_key}}"

{{icon_streak}} {tr:report.streak_label}: <b>{streak}</b> {tr:progress.streak_days}  ·  {{icon_xp}} XP: <b>+{xp_today}</b> {tr:report.xp_today_label}

<blockquote expandable>{meals_list_formatted}</blockquote>
```

**Rendered preview (ru, user 417002669 пример 2026-04-23):**

```
📊 Мой день
▫️ 23.04.2026  ⏰ 16:29

🔥 1190 / 2483 ккал
▓▓▓▓▓░░░░░  48%  ·  осталось 1293

🥩 47г ⚠️   🥑 54г ✅   🥖 142г ✅

💬 Noms: "Что-то скромно. Пообедай — стрик на воздухе не держится."

🔥 Дней в ударе: 18 дн.  ·  🌟 XP: +90 за сегодня

[blockquote expandable]
1. 08:08 — Оладушки, Кофе с молоком (320 ккал)
2. 12:26 — Шоколад, Борщ с мясом (870 ккал)
[/blockquote]
```

**Дизайн-решения (migration 124):**

1. **Заголовок = `{tr:buttons.stats}`** — автоматически равен тексту reply-кнопки во всех 13 языках ("Мой день" / "Mi Día" / "My Day" / ...).
2. **"Стрик" заменён на "Дней в ударе"** через ключ `report.streak_label` (переведён на все 13 языков).
3. **Светофоры {p_status}/{f_status}/{c_status}** — CASE по процентам от target:
   - pct < `macro_threshold_ok_pct` (30) → `icon_warning` (⚠️) — недобор
   - pct >= `macro_threshold_over_pct` (110) → `status_warn` (🔴) — перебор
   - иначе → `icon_check` (✅) — в норме
4. **`<blockquote expandable>`** — Telegram HTML-совместимо, сворачивает список приёмов пищи.
5. **`meals_list_formatted`** — собирается в RPC через `string_agg` + `row_number()`, формат `N. HH:MM — {items_summary} (XX ккал)`. Unit "ккал" резолвится RPC через user's language (Dumb Renderer резолвит `{tr:...}` ДО `{var}` pass — literal placeholder внутри `{var}` не распознаётся, поэтому RPC резолвит заранее).
6. **Empty state** (`meals_count=0`): `meals_list_formatted := {tr:report.no_meals_yet}` резолвленный в RPC → "Пока пусто — отправь фото или напиши что съел".

**Business data (`get_daily_stats_rpc` output) — FLAT top-level (render_screen сам оборачивает в `template_vars`):**

`calories_consumed, calories_target, calories_left, percent, progress_bar, p, f, c, p_status, f_status, c_status, status_key, insight_key, current_date, current_time, streak, xp_today, meals_count, meals_list_formatted` + вспомогательные `stats, meals, targets` (для TMA).

**Keyboard (упрощено 2026-04-21 по user feedback):** одна кнопка действия — Исправить. Ведёт к выбору конкретной записи для правки.

Row 0: `[{{icon_edit}} {tr:buttons.edit_last} → cmd_edit_last]` — `visible_condition`: `COUNT(food_logs today) > 0`.

*(Ранее было 3 кнопки: «🍽 Добавить еду», «✏️ Исправить запись», «📅 История». Упрощение: добавление еды доступно через reply-клавиатуру `[Add food]`, история вынесена в подменю Прогресс, основной use-case на этом экране — исправить свежую запись.)*

---

### **26\. food\_log\_result (Результат записи еды)**

**Meta:** input\_type=inline\_kb, render\_strategy=send\_new, business\_data\_rpc=get\_last\_log\_rpc

**Text:**

Plaintext

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ {input_icon} Записал {items_count} поз.:           │
│                                            │
│ {items_list_formatted}                     │
│                                            │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━                │
│ 📊 Итого: {meal_calories} ккал             │
│ 🥩 {meal_p}г  🥑 {meal_f}г  🥖 {meal_c}г      │
│                                            │
│ 🌟 +10 XP  🧪 {total_xp}                   │
╰────────────────────────────────────────────╯
```

*(Прим: {input\_icon} меняется: 🎤 — голос, 📸 — фото, ⌨️ — текст. {total\_xp} — твой текущий уровень энергии или общий прогресс).*

**Keyboard:** \[✏️ Редактировать → cmd\_edit\_last\]  \[🗑 Удалить → cmd\_delete\_last\]

\[☀️ Мой день → cmd\_get\_stats\]

---

### **🧠 UX/UI Обоснование (Блок 3):**

1. **Expandable Quote (Сворачиваемый список):** Использование тега \<blockquote\> в Telegram — это спасение для дашборда. Если у юзера было 6 перекусов, они не «вытолкнут» кнопки за пределы экрана. Юзер видит главное (КБЖУ), а детали открывает кликом.  
2. **Visual Status (Светофор):** Мы добавили {p\_status} (✅/⚠️/🔴) прямо рядом с граммами. Юзеру не нужно знать, что «122г — это 90% от нормы» (% могут быть другими \- см БД), он просто видит галочку и понимает, что он молодец.  
3. **Core Action (Добавить еду):** На экране stats\_main это самая широкая и удобная кнопка. Это то, ради чего бот существует.  
4. **Loss Aversion в логе:** В экране food\_log\_result мы сразу показываем \+10 XP. Это мгновенное дофаминовое вознаграждение за «труд» по записи еды.

---

## 🗂 ЧАСТЬ 6 — AI food logging (фото / голос / текст)

**Статус:** 🟡 placeholder (Пачка B).

**Что войдёт** (полный жизненный цикл лога еды):

1. **Prompt** — бот ждёт ввод (фото / голос / текст). Тексты из переводов + 🎥 стикер Noms (`noms_waiting_food`).
2. **Processing** — 🎥 стикер `noms_analyzing` (лупа / думает), отправляется пока GPT-4o парсит. Заменяет текстовый wait-индикатор типа «Анализирую фото…».
3. **Success** — `food_log_result` (уже в ЧАСТИ 5 §26). С +10 XP, итогом КБЖУ, кнопками.
4. **Not Food Error** — Noms саркастично: «Это не еда, дружище. Пришли что-то съедобное». Триггер: GPT-4o вернул флаг `is_food=false`. Перевод `errors.not_food`.
5. **Rate Limit Paywall** — экран «Энергия исчерпана» для Free-юзеров с 0 маны. Блокирует ввод, CTA → ЧАСТЬ 8 (Premium / Shop mana recharge). Перевод `gamification.premium_limit_reached`.
6. **Editing flow** (кнопка `[✏️ Исправить запись]` на `food_log_result` или `stats_main`):
   - `editing:food` — prompt «Окей, давай исправим! Напиши что конкретно не так: количество, блюдо или калории?» + показывает текущий парсинг (позиции + КБЖУ). *(Уже реализовано в `03_AI_Engine`, найти и описать макет.)*
   - `editing:food_retry` — повторная попытка парсинга (пользователь исправил текстом/голосом).
   - `editing:food_manual` — ручной ввод КБЖУ (если GPT стабильно фейлит).
   - `cancel_edit` — пользователь отказался, возврат к `food_log_result`.

**Переводы:** `food_log.*` (9), `wait.*` (4), `edit_food.*` (14), `errors.not_food`, `gamification.premium_limit_reached`. Все подтверждены в БД 2026-04-20.
**FSM `state_code`:** `editing_meal`, `editing:food`, `editing:food_manual`, `editing:food_retry`, `cancel_edit`.
**Воркфлоу:** `03_AI_Engine` (24ZOwWEmdGOYS2EH), `04.2_Edit_StatsDaily` (YebaQhipJrKZcGRO).
**Стикеры (TBD каталог):** `noms_waiting_food`, `noms_analyzing`, `noms_not_food_smug`.

---

### 🎬 Макет 6.1 — Processing State (бот думает)

Сразу после получения фото/голоса/текста — бот отправляет стикер вместо текстового wait-индикатора (сквозной принцип ЧАСТИ 0 № 3).

```
🎥 [sticker: noms_analyzing]
```
*(лупа + Noms смотрит в тарелку, ~2 сек анимация)*

Fallback на текст (если стикер не загрузился) — один из ключей в зависимости от типа ввода (все ✅ в БД):

| Тип ввода | Ключ | Текст (ru) |
|---|---|---|
| Фото | `wait.analyzing_photo` | «🧠 Анализирую фото...» |
| Голос / текст | `wait.calculating` | «🔢 Считаю калории...» |
| Поиск в базе | `wait.searching` | «🔍 Ищу в базе...» |
| При edit | `wait.updating_variants` | random из 3: «⚙️ Вношу данные. Дай мне время подумать...» / «⚙️ Понял, пересчитываю...» / «⚙️ Секунду, обновляю запись...» |

После распознавания — сообщение **processing удаляется** (через `deleteMessage`), на его место отправляется результат (макет 6.2 или ошибка).

---

### 🎬 Макет 6.2 — Success (food_log_result)

Уже описан в **ЧАСТИ 5 §26**. Дополнение: заголовок формируется из `food_log.header_{input_type}_{single|multi}` (8 вариантов).

| Input | Single / Multi | Ключ | Текст (ru) |
|---|---|---|---|
| Текст | single | `food_log.header_text_single` | «✏️ Записал:» |
| Текст | multi | `food_log.header_text_multi` | «✏️ Записал {count} позиций:» |
| Фото | single | `food_log.header_photo_single` | «📸 Записал:» |
| Фото | multi | `food_log.header_photo_multi` | «📸 Записал {count} позиций:» |
| Голос | single | `food_log.header_voice_single` | «🎤 Записал:» |
| Голос | multi | `food_log.header_voice_multi` | «🎤 Записал {count} позиций:» |

Футер — `food_log.total` + `food_log.macros`:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Итого: {calories} ккал
🥩 {protein}г  🥑 {fat}г  🥖 {carbs}г
```

Кнопки: `[✏️ Исправить → cmd_edit_last]` `[🗑 Удалить → cmd_delete_last]` `[☀️ Мой день → cmd_get_stats]`.

---

### 🎬 Макет 6.3 — Not Food Error (GPT вернул `is_food=false`)

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ {random errors.ai_not_food[0..2]}          │
╰────────────────────────────────────────────╯
```

Ключи (обновлено migration 107 + 104):
- `errors.not_food` (scalar, legacy, для старого n8n кода) = «Упс, это точно еда? 🤔 Я вижу тут что-то другое. Попробуй еще раз!» ✅
- `errors.ai_not_food` (array[3], для нового headless random-выбора) ✅ migration 104:
  1. «Упс, это точно еда? 🤔 Я вижу тут что-то другое. Попробуй еще раз!»
  2. «Ммм... это не похоже на еду. 😅 Давай попробуем с фоткой еды!»
  3. «Это не еда. Может, тебе хотелось отправить это в другой чат? 😉»

Кнопок нет — юзер просто пересылает новый ввод. Стикер-кандидат: `noms_not_food_smug` (ироничный взгляд).

---

### 🎬 Макет 6.4 — Rate Limit Paywall (Free-tier лимит)

Триггер: Free-юзер исчерпал лимит (daily AI запросов). Попытка залогировать еду блокируется. **Решение 2026-04-21:** используем новый ключ `free_tier.limit_reached` (3 варианта Sassy Sage, ✅ migration 106) вместо legacy `gamification.premium_limit_reached`.

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ {random free_tier.limit_reached[0..2]}     │
╰────────────────────────────────────────────╯
```

**3 варианта Sassy Sage** (из БД migration 106):

1. «Использованы все бесплатные запросы сегодня 🎯

   Хочешь больше? Оформи подписку:
   {{icon_check}} Безлимит запросов
   {{icon_check}} Распознавание по фото
   {{icon_check}} ...»
2. «Опа! Бесплатные разборы на сегодня всё. NOMS хочет кушать, чтобы считать твою еду. Оформи подписку за цену чашки кофе! ☕️»
3. «Бесплатные запросы на сегодня закончились 🔒. Можешь подождать до завтра, или получить Premium и продолжить прямо сейчас. Решение за тобой!»

**Pre-warning (за 3 запроса до лимита)** — ключ `free_tier.trial_limit_3` (3 варианта):
1. «Осталось {remaining_trials} попытки 🎯 Заполни профиль — получишь безлимит.»
2. «Ещё {remaining_trials} попытки! 🔥 Заверши профиль и снимешь ограничения.»
3. «{remaining_trials} попытки осталось {{icon_warning}} Дозаполни профиль — и логируй без лимитов!»

**CTA-кнопки** (реальный Headless UX, не просто чат-текст как было в legacy):
- `[⭐ Получить Premium → cmd_premium_plans]` → entry в ЧАСТЬ 8 (paywall flow). Текст для paywall — `pay.paywall[3]` ✅ migration 106.
- `[🔋 Купить Ману (500 💎) → cmd_buy_mana]` → ЧАСТЬ 9 Shop
- `[⏭ Жду завтра]` — просто закрыть.

**Legacy fallback:** `gamification.premium_limit_reached` остаётся в БД (старый n8n код), но новые воркфлоу используют `free_tier.limit_reached` + CTA-кнопки.

---

### 🎬 Макет 6.5 — Editing Flow (пример пользователя «яблоко-груша»)

Триггер: юзер нажал `[✏️ Исправить → cmd_edit_last]` или `[✏️ Исправить запись]` на Stats. Статус переходит в `editing:food`.

**Экран (replacing старого food_log_result через editMessageText):**

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ Окей, давай исправим! ✏️                   │
│ Напиши, что конкретно не так:              │
│ количество, блюдо или калории?             │
│                                            │
│ ▫️ Яблоко — 80 ккал                        │
│ ▫️ Груша — 100 ккал                        │
│                                            │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━                │
│ 📊 Итого: 180 ккал                         │
│ 🥩 1г  🥑 0г  🥖 49г                        │
╰────────────────────────────────────────────╯
```
Текст верхней строки — random из 3 вариантов `edit_food.prompt_variants` (все в БД):
- «Окей, давай исправим! ✏️ Напиши, что конкретно не так: количество, блюдо или калории?»
- «Понял, мой косяк 😅 Опиши правильный вариант текстом, я пересчитаю.»
- «Исправляем! Напиши, что изменить: название блюда, граммовку или состав?»

Кнопки:
- `[✅ Нет, всё ок! → cmd_edit_cancel]` — `edit_food.btn_all_ok` ✅
- `[🔙 Назад → cmd_back]`

После того как юзер напишет/скажет исправление — статус `editing:food_retry` + processing стикер `noms_analyzing` + повторный GPT-вызов.

**Подтекст: статусы и их тексты**

| FSM | Текст (буквально из БД) | Действие |
|---|---|---|
| `editing:food` | `edit_food.prompt` = «Что исправить? Напиши новое название или вес» *(альтернативная короткая форма)* | Ждём текст/голос |
| `editing:food` | `edit_food.processing` = «🔄 Исправляю...» | Промежуточный (если processing медленный) |
| `editing:food_retry` | `edit_food.retry` = «Хм, попробую ещё раз с более мощным AI 🤖» | GPT-4o с расширенным промптом |
| `editing:food_manual` | `edit_food.manual_prompt` = «Не могу точно определить 🤔 Введи калории вручную (число):» | text_input number |
| `editing:food` → success | `edit_food.success` = «✅ Готово! Обновил» | Показ обновлённого food_log_result |
| `editing:food` → not found | `edit_food.not_found` = «🤔 Не нашёл» | Fallback на manual |
| `cancel_edit` | `edit_food.cancelled` = «Окей, оставляем как было! ✅» | Возврат к оригиналу |
| delete meal | `edit_food.deleted` = «🗑️ Удалил» | Запись удалена |

**Источник истины flow в n8n:** воркфлоу `03_AI_Engine` (основной парсинг) + `04.2_Edit_StatsDaily` (UI правки).

---

### 🎬 Макет 6.6 — Выбор приёма пищи для правки (из Stats)

Триггер: юзер нажал `[✏️ Исправить запись]` на `stats_main` и сегодня ≥2 записи (нужно выбрать какую).

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ Выбери что исправить:                      │
╰────────────────────────────────────────────╯
```
Ключ: `edit_food.select_to_edit` ✅ в БД.

Клавиатура — список сегодняшних meals (inline):
- `[🍳 08:30 — Омлет, 320 ккал → cmd_view_meal_{id}]`
- `[🍎 11:00 — Яблоко и груша, 180 ккал → cmd_view_meal_{id}]`
- `[🔙 Назад → cmd_back]`

Если записей 0: `edit_food.no_meals_today` = «Сегодня ещё нет записей 🍽».

---

## 🗂 ЧАСТЬ 7 — Сканер штрих-кода

**Статус:** 🟡 placeholder (Пачка B).

**Что войдёт:** prompt «пришли фото штрих-кода», результат «найдено» (с деталями продукта) / «не найдено» (fallback на ручной ввод), переход к логу.

**Переводы:** `barcode.*` (3: `barcode.prompt`, `barcode.found`, `barcode.not_found`).
**FSM `state_code`:** `scanning:barcode`.
**Воркфлоу:** `03_AI_Engine` в режиме scanning.

---

## 🗂 ЧАСТЬ 8 — Оплата / Premium

**Статус:** 🟡 placeholder (Пачка C).

**Что войдёт** (полный transaction flow):

1. **Tier Picker** — Yearly / Monthly / Trial. Региональные цены (Spain-based).
2. **Plan Details** — детали выбранного тарифа, что входит.
3. **Payment Method** — ⭐ Stars / 💳 Stripe / 💎 TON.
4. **Promo Code Input** — ввод промокода.
5. **Success** (`✅ Оплата прошла! Premium активирован до DD.MM.YYYY`) — подтверждение транзакции.
6. **Failure** (`❌ Оплата не прошла. Попробуй ещё раз или выбери другой способ.`) — обработка ошибки.
7. **Manage Subscription** (`cmd_profile_subscription`) — активный план, дата продления, кнопка отмены.
8. **Subscription Expired Gate** — по истечении (связка с cron push `subscription_expiry`).
9. **Trial Activated** — отдельный экран для триала.

**Переводы:** `payment.*` (36 ключей, включая `success_title`, `failure_title`, `trial_activated`).
**Callback:** `cmd_premium_plans`, `cmd_pay_stars_*`, `cmd_pay_crypto_*`, `cmd_enter_promo`, `cmd_apply_promo`, `cmd_profile_subscription`.
**Воркфлоу:** `10_Payment` (xYKmBTWI4c0VoSqs).

### 🎬 Макет 8.1 — Paywall Tier Picker (Sassy Sage random, migration 106 ✅)

Используется на шаге «Tier Picker» (пункт 1 выше) — витрина тарифов ДО выбора способа оплаты.

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ {random pay.paywall[0..2]}                 │
╰────────────────────────────────────────────╯
```

3 варианта из БД (`pay.paywall`, migration 106 ✅):

1. «🔓 Premium открывает:
   {{icon_check}} Безлимитное логирование
   {{icon_check}} Фото по AI
   {{icon_check}} Голосовой ввод
   {{icon_check}} Подробная аналитика

   Выбери тариф:»
2. «Хочешь больше? 🚀

   ✨ Premium даёт:
   • Безлимит логов
   • Распознавание по фото
   • Голосовые заметки
   • Детальная статистика

   Выбери подписку:»
3. «Разблокируй всё! 💎

   {{icon_check}} Без ограничений на логи
   {{icon_check}} AI по фото еды
   {{icon_check}} Голосовой ввод
   {{icon_check}} Полная аналитика

   Оформить:»

### 🎬 Макет 8.2 — Success (Sassy Sage random, migration 104 ✅)

Используется на шаге 5 «Success» — после подтверждения успешной транзакции.

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ {random payment.success[0..2]}             │
╰────────────────────────────────────────────╯
```

3 варианта из БД (`payment.success`, migration 104 ✅):

1. «Красава! 🔥 Подписка активирована. Теперь безлимит, фото, голос — всё твоё. Поехали!»
2. «Готово! ✨ Premium активен. Все ограничения сняты. Пришли фото завтрака — проверим суперсилы!»
3. «Ура! 🎉 Ты теперь в Premium-клубе! Все фичи разблокированы. Давай залогируем что-нибудь вкусное?»

Кнопка: `[🍽 Добавить еду → cmd_add_food]`.

---

## 🗂 ЧАСТЬ 9 — Магазин (с transaction confirmations)

**Статус:** ✅ live (migrations 136 hub-render + 144 transaction flow, 2026-04-28).

**Headless screens (8):**
1. **`shop`** (§9.1) — Hub: баланс 💎 + мана + заморозки + 4 кнопки (Buy Freeze / Buy Mana / Go PRO / Manage Sub).
2. **`buy_freeze_confirm`** (§9.2) — `❄️ Купить Заморозку?\n+ description\nСтоимость: 500 💎\nТвой баланс: {coins} 💎` + `[✅ Да, купить → cmd_confirm_buy_freeze] / [🔙 Назад]`.
3. **`buy_freeze_success`** (§9.3) — `✅ Заморозка куплена!\n+1 Заморозка добавлена.\nНовый баланс: {coins} 💎\nЗаморозок: {n} ❄️` + `[🔙 Назад]`.
4. **`buy_mana_confirm`** (§9.5) — аналогично freeze + строка "Пополнений сегодня: {a}/{b}".
5. **`buy_mana_success`** (§9.6) — `✅ Мана пополнена!\nМана: {current}/{max} 🧪\nПополнений сегодня: {a}/{b}`.
6. **`shop_error_no_coins`** (§9.4) — `❌ Недостаточно монет\nУ тебя: {coins} 💎\nЗарабатывай логами или подключи Premium` + `[⭐ Купить Premium → cmd_premium_plans] / [🔙 Назад]`.
7. **`shop_error_mana_full`** — `🧪 Мана уже полна\nТекущая мана: {current}/{max}`.
8. **`shop_error_recharge_limit`** — `⏳ Лимит пополнений\nПополнений сегодня: {a}/{b}\nСчётчик сбросится в полночь` + `[⭐ Купить Premium] / [🔙 Назад]`.
9. **`shop_error_already_premium`** (edge) — `👑 У тебя Premium — мана пополняется автоматически`.

**Wrapper RPCs (action_rpc pattern):**
- `shop_action_buy_freeze(BIGINT, TEXT)` — wraps `buy_streak_freeze` + 5-sec idempotency window.
- `shop_action_buy_mana(BIGINT, TEXT)` — wraps `recharge_mana_with_coins` + idempotency.

Оба возвращают `{success, error, error_code, required_cost, ...}`. Idempotency через query на `coin_transactions` за последние 5 секунд по `tx_type IN ('streak_freeze','mana_recharge')`. При повторном клике в окне → `idempotent_repeat=true`, без двойного списания.

**Framework extension:**
- **`save_rpc` whitelist** в `process_user_input` расширен: `set_user_% OR shop_action_%`.
- **`meta.error_screen_map`** на кнопке (новый паттерн) → если `save_rpc` вернул `success=false`, маршрутизация на screen из карты вместо `next_on_submit`. Например для buy_mana: `{INSUFFICIENT_COINS: shop_error_no_coins, MANA_ALREADY_FULL: shop_error_mana_full, MAX_RECHARGES_TODAY: shop_error_recharge_limit, ALREADY_PREMIUM: shop_error_already_premium}`.
- **Универсальный `cmd_back`** — все 8 экранов используют `back_screen_id_default='shop'`. Никаких `cmd_back_to_shop`.

**Переводы:** `shop.*` (40 ключей: 31 существующих + 8 новых из 144 + `buttons.confirm_yes_buy`).
**Callback:** `cmd_shop`, `cmd_buy_freeze`, `cmd_buy_mana`, `cmd_confirm_buy_freeze`, `cmd_confirm_buy_mana`, `cmd_premium_plans` (anchor → 10_Payment).
**Воркфлоу:** `08.4_Shop` (`yhpXMufXs1guvZY5`) — **DEPRECATED** после migration 144 deploy. Hub + transactions полностью headless.

---

## 🗂 ЧАСТЬ 10 — Детали лиги

**Статус:** ✅ live (migration 140, 2026-04-24).
- §10.1 League Main — реализовано как **4-neighbor window** (вместо full 3-zone split — компромисс с legacy UX), с ► marker для self.
- §10.2 League Info — headless screen `league_info` (text from `league.info_text` + `league.groups_form`).
- §10.3 League Empty — countdown до понедельника + sage tip (новые ключи `league.until_monday` + `league.empty_tip` × 13 langs).
- §10.4 Promotion/Demotion celebration — остаётся в Python crons (legacy by design).

**Переводы:** `league.*` (25 ключей) — все ✅ в БД, `league_results.*` (из cron).
**Callback:** `cmd_league`, `cmd_league_info`, `cmd_back_to_progress`.
**Воркфлоу:** `08.2_League` (tLtlAByEChVRtMRx) + `crons/league_cycle.py`.
**Данные:** RPC `get_league_standings` (живой лидерборд + NPC-боты, migration 042).

**8 имён лиг из БД (`league.name_1..8`):** Лук, Огурчик, Авокадо, Чили, Тофу, Сашими, Трюфель, Лотос.

---

### 🎬 Макет 10.1 — League Main (Лидерборд)

Триггер: `cmd_league` (из Progress Hub). Формируется из `league.*` буквальных текстов БД.

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 🏆 Таблица лиги                            │
│                                            │
│ Твоя лига: 🥑 Авокадо                       │
│ Неделя: 14 апр — 20 апр                    │
│ До конца: 2д 4ч                            │
│                                            │
│ 🟢 Зона повышения                          │
│ 1. Алекс — 1450 XP                         │
│ 2. Маша — 1320 XP                          │
│ 3. Джон — 1280 XP                          │
│ ...                                        │
│                                            │
│ ⚪ Безопасная зона                         │
│ 6. Анна — 1050 XP                          │
│ ► 7. ТЫ — 980 XP                           │
│ 8. Том — 920 XP                            │
│ ...                                        │
│                                            │
│ 🔴 Зона понижения                           │
│ 16. Пол — 120 XP                           │
│ ...                                        │
│                                            │
│ 💬 Noms: {insight}                         │
╰────────────────────────────────────────────╯
```

**Динамические вставки** (буквально из БД):
- Заголовок: `league.title` = «🏆 Таблица лиги»
- Лига: `league.your_league` = «Твоя лига: {icon} {name}»
- Неделя: `league.week_label` = «Неделя: {start} — {end}»
- Таймер: `league.timer_label` = «До конца» + вычисленное время
- Зоны: `league.promote_zone` / `league.safe_zone` / `league.demote_zone`
- Метка юзера: `league.you_label` = «ТЫ»
- Место: `league.your_rank` = «Твоё место: #{rank} из {total}»
- Noms insight (динамический):
  - Если #1 → `league.insight_leader` = «Ты на 1-м месте! Так держать!»
  - Если близко к топу → `league.insight_close` = «{name} впереди всего на {gap} XP. Запиши перекус!»
  - Default → `league.collect_xp` = «Собирай XP, чтобы подняться выше!»

Кнопки:
- `[ℹ️ Как работают лиги? → cmd_league_info]` — `league.info_button`
- `[🔙 Назад → cmd_back]` — `buttons.back`

---

### 🎬 Макет 10.2 — League Info (Как работают лиги?)

Триггер: `cmd_league_info`. `editMessageText` заменяет 10.1.

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 🏆 Каждую неделю ты соревнуешься с ~20     │
│ игроками. Топ-5 повышаются, последние 5    │
│ понижаются. Логируй еду для XP!            │
│                                            │
│ 🏅 Лиги (8 ступеней):                      │
│ 🧅 Лук → 🥒 Огурчик → 🥑 Авокадо → 🌶 Чили  │
│ → 🍲 Тофу → 🍣 Сашими → 🍄 Трюфель →        │
│ → 🪷 Лотос                                  │
│                                            │
│ 📅 Группы формируются каждый понедельник.  │
╰────────────────────────────────────────────╯
```

Ключи (все из БД):
- `league.info_text` = «🏆 Каждую неделю ты соревнуешься с ~20 игроками. Топ-5 повышаются, последние 5 понижаются. Логируй еду для XP!»
- `league.groups_form` = «Группы формируются каждый понедельник»
- Имена лиг: `league.name_1..8`

Кнопка: `[🔙 Назад → cmd_back]`.

---

### 🎬 Макет 10.3 — League empty (до понедельника)

Если юзер только зарегистрировался и ещё не попал в лигу:

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 🏆 Таблица лиги                            │
│                                            │
│ Вступишь в лигу в понедельник!             │
│                                            │
│ До понедельника: {days}д                   │
│                                            │
│ А пока — копи XP и готовься!               │
╰────────────────────────────────────────────╯
```
Ключ: `league.no_group` = «Вступишь в лигу в понедельник!» ✅ в БД.
Кнопки: `[🔙 Назад → cmd_back]`.

---

### 🎬 Макет 10.4 — Promotion / Demotion Celebration (cron push)

Отправляется `crons/league_cycle.py` в понедельник после ранжирования. Ссылка из ЧАСТИ 14.

**Promotion** (попал в топ-5):
```
🎥 [sticker: noms_league_promote]
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 🎉 Поздравляю! Ты перешёл в лигу           │
│ 🌶 Чили!                                   │
│                                            │
│ {league_results.promotion_bonus_text}      │
│ 💎 +100 NomsCoins                          │
╰────────────────────────────────────────────╯
```
Кнопка: `[🏆 Посмотреть лигу → cmd_league]`.

**Demotion** (попал в bottom-5):
```
🎥 [sticker: noms_league_demote]
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 😔 В этой неделе ты в бронзе 🥉            │
│                                            │
│ Лига Авокадо уступила — ты вернулся в       │
│ 🥒 Огурчик.                                 │
│                                            │
│ На следующей неделе — реванш!              │
╰────────────────────────────────────────────╯
```
Кнопка: `[💪 Вперёд → cmd_league]`.

---

## 🗂 ЧАСТЬ 11 — Рефералы / Банда (Stateful UI: Novice → Ambassador)

**Статус:** ✅ live (migration 140, 2026-04-24). Stateful UI реализован — один screen_id `friends_info` рендерит Novice или Ambassador экран в зависимости от `users.ambassador_tier`/`paid_referral_count`/`is_trainer`. Buttons split via `visible_condition`. См. §23 для context-матрицы.

- §11.1 Band Novice — реализовано (structured 0/0/0/0 zero state по решению user). Reward amounts 50/100 не хардкодены, идут из `app_constants.referral_escrow_coins/xp`.
- §11.2 Rules `friends_how_it_works` — headless screen `friends_how_it_works` (wrapper RPC `get_friends_how_it_works_rpc` eager-resolves `info_step3` placeholders).
- §11.3 Ambassador Dashboard — реализовано (один screen_id, RPC ветвится). `get_ambassador_stats` + `get_ambassador_balance` + `create_ambassador_code` reused.
- §11.4–11.5 Cron pushes — legacy by design (Python crons).

**Ключевая концепция: Stateful UI.** По одному callback `cmd_friends_info` рендерятся ДВА разных экрана в зависимости от `users.ambassador_tier`:

| `ambassador_tier` | Условие | Экран | Фокус |
|---|---|---|---|
| `'none'` (default) | `paid_referral_count < 5` | **Band Dashboard** (Novice / 0–4 paid друзей) | Мотивация получить бесплатный PRO за 4 друзей |
| `'active'` | `paid_referral_count >= 5` ИЛИ `is_trainer=true` | **Ambassador Dashboard** (Партнёрская панель) | Реальные деньги: RevShare 25% + 5% от суб-рефералов |

**Экран 11.1 — Band Dashboard (Novice)** — 0–4 paid друзей:
- Статус банды (агентов / монет / до PRO)
- Реферальная ссылка
- Noms-коммент в стиле «трое осталось — PRO твой»
- Кнопки: `[📤 Поделиться]`, `[ℹ️ Как это работает? → cmd_friends_how_it_works]`, `[🔙 Назад]`

**Экран 11.2 — Rules (`friends_how_it_works`)** — правила: Escrow → Вербовка → Свои люди → Босс Банды. 4 ступени воронки с 1️⃣ 2️⃣ 3️⃣ 4️⃣. Упоминает RevShare 25% как тизер на 4-й ступени.

**Экран 11.3 — Ambassador Dashboard** — `ambassador_tier='active'`:
- Заголовок «Панель Партнёра (RevShare 25%)» (`ambassador.title` ✅ в БД, migration 072)
- Статистика: привлечено / конверсия / баланс $ USDT / выплачено всего
- Промокод партнёра (`ambassador.promo_label`)
- Noms-коммент (`ambassador.noms_ambassador_1/2/3`, random)
- Кнопки: `[📤 Поделиться кодом]`, `[💳 Вывести средства → ЧАСТЬ 12]`, `[👥 Статистика учеников]`, `[🔙 Назад]`

**Squad celebration** — отдельный push при активации нового друга (ЧАСТЬ 14: `referral_activated`).

**Переводы:** `referral.*` (32 ключа — Novice), `ambassador.*` (14 ключей ✅ migration 072 — Active tier).
**Callback:** `cmd_friends_info` (роутит на 11.1 или 11.3 через business_data_rpc), `cmd_friends_how_it_works`, `share_invite_link`, `cmd_ambassador_payout` → ЧАСТЬ 12, `cmd_ambassador_stats`.
**Воркфлоу:** `08.3_Friends` (D8E22eJU33Xq3LqE).
**Данные:** `users.ambassador_tier`, `users.ambassador_commission_rate`, `users.paid_referral_count`, `users.referral_count`, RPC `get_ambassador_stats`, `get_ambassador_balance`.

---

### 🎬 Макет 11.1 — Band Novice Dashboard (0–4 paid друзей)

Триггер: `cmd_friends_info` + `ambassador_tier='none'` (или `paid_referral_count < 5`).

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 👥 Твоя Банда                              │
│                                            │
│ В банде: 2 агентов                         │
│ Активных: 1                                │
│ Ожидают: 1                                 │
│ Заработано: 100 NomsCoins                  │
│                                            │
│ 🏆 До бесплатного PRO: 1/4                 │
│                                            │
│ 🔗 Твоя ссылка:                            │
│ `https://t.me/nomsaibot?start=ref_12345`   │
│                                            │
│ 💬 Noms: {random cta_newbie/active/_123}   │
╰────────────────────────────────────────────╯
```

**Буквальные ключи (все ✅ в БД):**
- Заголовок: `referral.title` = «Твоя Банда»
- Счётчики: `referral.squad_count` = «В банде: {count}» + `referral.squad_count_suffix` = «агентов»; `referral.stats_active` = «Активных: {count}»; `referral.stats_pending` = «Ожидают: {count}»; `referral.earned_label` = «Заработано: {count}» + `referral.earned_suffix` = «NomsCoins»
- Цель: `referral.pro_goal` = «До бесплатного PRO: {current}/{target}»
- Ссылка: `referral.your_link` = «Твоя ссылка:»
- Если `count=0`: `referral.no_invites` = «Приглашай друзей и получай награды!»

**Noms CTA — random из 3 по состоянию:**

Если `count=0` — random из `referral.cta_newbie_1..3`:
1. «Худеть в одиночку — отстой. Собирай банду, вместе веселее срываться на пиццу... ой, то есть идти к цели! 4 друга с PRO = месяц PRO тебе бесплатно.»
2. «Приглашай друзей! Когда они начнут логировать еду, вы оба получите монеты и XP. 4 друга с PRO = бесплатный месяц!»
3. «Твоя банда пуста. Серьёзно? Даже у моей бабушки тут больше друзей. Начинай приглашать!»

Если `count>0` — random из `referral.cta_active_1..3`:
1. «Уже {count} в банде! Продолжай — бесплатный PRO всё ближе с каждым другом.»
2. «{count} агентов завербовано. Банда растёт! Ещё {remaining} друга с PRO до бесплатного месяца.»
3. «Ого, строишь империю! {count} друзей и это не предел. Бесплатный PRO на расстоянии вытянутой руки.»

**Кнопки:**
- `[📤 Поделиться → share_invite_link]` — `referral.share_button` = «Поделиться». Share text: `referral.share_text` = «Попробуй NOMS — умный трекер еды!»
- `[ℹ️ Подробнее → cmd_friends_how_it_works]` — `referral.info_button`
- `[🔙 Назад → cmd_back]`

---

### 🎬 Макет 11.2 — Rules «Как работает Банда?»

Триггер: `cmd_friends_how_it_works`. `editMessageText` поверх 11.1.

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ ℹ️ Как работает Банда?                     │
│                                            │
│ 1️⃣ Отправь свою ссылку другу               │
│ 2️⃣ Друг регистрируется и записывает еду    │
│    за 1-й день                             │
│ 3️⃣ Вы оба получаете 50 💎 и 100 🌟          │
│ 4️⃣ 4 друга с PRO → месяц PRO бесплатно!    │
│                                            │
│ 💸 За каждого друга после первого дня:     │
│   +50 💎 и +100 🌟                          │
│                                            │
│ 👑 5+ оплативших → Амбассадор (RevShare 25%│
│    реальными деньгами)                     │
╰────────────────────────────────────────────╯
```

**Буквальные ключи (все в БД):**
- Заголовок: `referral.info_title` = «Как работает Банда?»
- Шаги: `referral.info_step1..4` — буквальные тексты выше.
- Блок наград: `referral.reward_info` + `referral.reward_detail` = «+{coins} {icon_coin} и +{xp} {icon_xp}»
- 4-я ступень + Ambassador тизер — текст блока.

Кнопка: `[🔙 Назад → cmd_back]`.

---

### 🎬 Макет 11.3 — Ambassador Dashboard (Stateful UI: `ambassador_tier='active'`)

Триггер: `cmd_friends_info` + `ambassador_tier='active'` (5+ paid или `is_trainer=true`). Экран **мутирует** — полностью заменяет Band Novice.

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 💼 Панель Партнёра                         │
│                                            │
│ Твоя банда приносит реальный доход. Ты     │
│ получаешь 25% с каждой оплаты и 5% с их    │
│ друзей!                                    │
│                                            │
│ 📊 Статистика:                             │
│ 👥 Привлечено: 142 (из них 18 PRO)         │
│ 📈 Конверсия: 12.6%                         │
│ 💰 Баланс: $135.50                         │
│ 💸 Всего выплачено: $450                   │
│                                            │
│ 🎟 Твой промокод (даёт 10% скидку):         │
│ `FITNESS_ALEX`                             │
│                                            │
│ 💬 Noms: {random noms_ambassador_1/2/3}    │
╰────────────────────────────────────────────╯
```

**Буквальные ключи (все ✅ migration 072):**
- Заголовок: `ambassador.title` = «Панель Партнёра»
- Subtitle: `ambassador.subtitle` = «Твоя банда приносит реальный доход. Ты получаешь 25% с каждой оплаты и 5% с их друзей!»
- Статы: `ambassador.stats_invited` = «Привлечено: {total} (из них {paid} PRO)»; `ambassador.stats_conversion` = «Конверсия: {rate}%»; `ambassador.stats_balance` = «Баланс: ${balance}»; `ambassador.stats_total_paid` = «Всего выплачено: ${total}»
- Промокод: `ambassador.promo_label` = «Твой промокод (даёт {discount}% скидку):»
- Noms — random из 3:
  - `ambassador.noms_ambassador_1` = «Ты не просто лидер банды, ты бизнес-партнёр. Продолжай в том же духе!»
  - `ambassador.noms_ambassador_2` = «Банда растёт и баланс тоже. Так рождаются легенды.»
  - `ambassador.noms_ambassador_3` = «Каждый друг — это деньги в кармане. Буквально бизнес-гений.»

**Кнопки:**
- `[📤 Поделиться кодом → share_ambassador_code]` — `ambassador.share_button` = «Поделиться кодом». Share text: `ambassador.share_code_text` = «Используй мой код {code} для {discount}% скидки на NOMS Premium!»
- `[💳 Вывести средства → cmd_start_payout]` — `ambassador.payout_button` = «Вывести средства». Entry → ЧАСТЬ 12.
- `[👥 Статистика → cmd_ambassador_stats]` — `ambassador.stats_button` = «Статистика»
- `[🔙 Назад → cmd_back]`

---

### 🎬 Макет 11.4 — Squad Celebration Push (новый активный друг)

Отправляется `crons/referral_unlock.py` (или аналог) когда реферал прошёл первый день и unlock'нул escrow. Ссылка из ЧАСТИ 14 (тип `referral_activated`).

```
🎥 [sticker: noms_squad_grow]
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 🎉 {friend_name} присоединился к твоей      │
│ банде!                                      │
│                                            │
│ +50 💎 и +100 🌟 — твоя награда уже          │
│ начислена.                                  │
│                                            │
│ В банде: {count} агентов                    │
│ До бесплатного PRO: {current}/{target}     │
╰────────────────────────────────────────────╯
```
Кнопка: `[👥 Моя Банда → cmd_friends_info]`.

---

### 🎬 Макет 11.5 — Present from Friend (когда друг переходит в новую Лигу и шэрит приз)

Триггер: `referral_present` cron-push — когда друг-реферал перешёл в новую лигу и активировал функцию «поделиться победой». Получатель — сам реферер (или другой участник банды).

```
🎥 [sticker: noms_squad_grow]
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ {random referral.present_friend[0..2]}     │
╰────────────────────────────────────────────╯
```

3 варианта из БД (`referral.present_friend`, migration 104 ✅):

1. «🎁 Ты получил подарок от {friend_name}!

   7 дней Premium-доступа. Твой друг перешёл в новую Лигу и решил поделиться победой с тобой. Активируй сейчас!»
2. «Сюрприз! 🏆

   Твой друг {friend_name} достиг новой Лиги и дарит тебе 7 дней Premium! Распаковываем подарок?»
3. «Подарок для тебя! ✨

   Твой друг-чемпион {friend_name} перешёл в новую Лигу и оставил тебе бонус — неделю Premium. Забирай!»

Кнопка: `[🎁 Активировать → cmd_activate_present]` → на 7 дней Premium включается.

---

## 🗂 ЧАСТЬ 12 — Ambassador payout

**Статус:** ✅ live — БД готова (migration 145, 2026-04-28). Sender pipeline (Telegram reply kb, admin chat listener, ReplyKeyboardRemove, wallet validation fast path) — handover для Python Dispatcher агента.

**Entry point:** кнопка `[💳 Вывести средства]` на **Ambassador Dashboard** (ЧАСТЬ 11, экран 11.3). Видна только при `ambassador_tier='active'` или `paid_referral_count >= 5` или `is_trainer=true`. Callback `cmd_start_payout` → fastpath в `process_user_input` → screen `payout_method_picker`.

**Headless screens (9):**
1. **`payout_method_picker`** (§12.1) — баланс + 4 метода: `[💳 Карта]` / `[💎 USDT TON]` / `[🪙 USDT TRC-20]` / `[🧾 Инвойс B2B]` + `[🔙 Назад]`. business_data_rpc=`get_payout_business_data`. Если `available_balance < min_payout_amount` ($10) — save_rpc возвращает `next_screen='payout_no_balance'`.
2. **`payout_no_balance`** — error screen «Минимальный вывод: $X, у тебя: $Y».
3. **`payout_phone_request`** (§12.1.5 Phone Verify, scenario A) — `input_type='reply_kb_request_contact'` (NEW). Reply kb с `[📱 Поделиться номером (request_contact:true)]` + `[🔙 Назад]`. Renderер — Python (special handling).
4. **`payout_phone_confirm`** (§12.1.5 scenario B) — inline_kb «Твой номер: {phone_masked}. Использовать?» + `[✅ Да, мой → cmd_payout_phone_confirm_yes]` / `[📱 Привязать другой → cmd_payout_phone_change]` / `[🔙 Назад]`.
5. **`payout_wallet_input`** (§12.2) — text_input. Promp адаптивный по методу. save_rpc=`set_payout_wallet`. Defense-in-depth regex: bank `^[0-9]{16,19}$`, ton `^(EQ|UQ)[A-Za-z0-9_-]{46}$`, trc20 `^T[A-Za-z0-9]{33}$`, invoice `.{1,200}`. Invalid → `error_screen_map: WALLET_INVALID → payout_error_wallet_invalid`.
6. **`payout_confirm`** (§12.3) — inline_kb «Метод: X, Сумма: $Y. Подтвердить?». save_rpc=`payout_action_request` через button meta. error_screen_map: `NO_DRAFT → payout_error_already_pending`.
7. **`payout_success`** (§12.4) — «Заявка отправлена! Обработка до 24 часов.» + `[👥 Моя Банда]` + `[🔙 Назад]`.
8. **`payout_error_already_pending`** — «У тебя уже есть заявка в обработке. Сумма: $X».
9. **`payout_error_wallet_invalid`** — «Неверный формат реквизитов» + список форматов по методам.

**Wrapper RPCs (action_rpc + save_rpc patterns):**
- `set_payout_method(BIGINT, TEXT)` — parse method из callback `cmd_payout_method_*`, cleanup expired drafts (>24h → 'abandoned'), INSERT draft, return `next_screen` (dynamic routing: bank+phone NULL → phone_request, bank+phone есть → phone_confirm, crypto/invoice → wallet_input).
- `set_payout_wallet(BIGINT, TEXT)` — defense-in-depth regex per draft method, UPDATE draft.wallet_address.
- `set_user_phone_from_contact(BIGINT, TEXT, TEXT, BIGINT)` — DIRECT call от Python (не через save_rpc framework). 🔒 STRICT EQUALITY anti-spoofing: `IF p_contact_user_id <> p_telegram_id THEN RAISE foreign_contact_rejected`. E.164 + anti-collision.
- `payout_action_request(BIGINT, TEXT)` — wrapper для `cmd_confirm_payout`. Atomic UPDATE draft→pending RETURNING id (NULL = idempotent NO_DRAFT). pg_notify('payout_request_created') для admin sender.

**🔒 Balance Reservation Fix (КРИТИЧЕСКИЙ — закрытие race condition двойной заявки):**
- `get_ambassador_balance` расширен: `total_pending` (SUM amount WHERE status IN 'pending','approved') + `available_balance` (= balance - total_pending).
- ВСЕ financial callers переключены на `available_balance`: `set_payout_method`, `get_payout_business_data`, `get_friends_info_rpc` (Ambassador Dashboard).
- Drafts (`status='draft'`) НЕ считаются holds — юзер ещё не submit'нул.

**Framework extension (process_user_input patches, idempotent):**
- Whitelist: `set_user_% OR shop_action_% OR payout_action_% OR set_payout_%`.
- COALESCE для v_next_screen: добавлен `v_save_result->>'next_screen'` (dynamic routing из save_rpc).
- error_screen_map: prefer `error_code` (newer), fallback to `error` (144-compat).
- Fastpath: `cmd_start_payout`, `cmd_payout_phone_confirm_yes`, `cmd_payout_phone_change`.

**CHECK constraints (схема):**
- `payout_requests.status IN ('draft','abandoned','pending','approved','paid','rejected')` (defense-in-depth).
- `users.phone_source IN ('onboarding','payout','settings','quest')` (analytics per KB).
- `ui_screens.input_type` extended on `'reply_kb_request_contact'`.

**Колонки добавлены в public.users (КОРРЕКЦИЯ ground truth: phone* живут в `auth.users`, не `public.users`):** `phone TEXT`, `phone_confirmed_at TIMESTAMPTZ`, `phone_source TEXT`. Unique partial index — defer (audit-миграция 146+).

**Translations:** existing 17 `payout.*` keys + 14 новых × 13 langs (composite text templates, phone keys, button labels).

**Callbacks (для Python Dispatcher PROFILE_V5_CALLBACKS):**
- `cmd_start_payout`, `cmd_payout_method_bank/usdt_ton/usdt_trc20/invoice`, `cmd_payout_phone_confirm_yes/change`, `cmd_confirm_payout`.
- `admin_payout_(approve|reject)_{uuid}` — pattern match (regex), already handled в `payout_handler.py`.

**FSM `state_code`:** `payout_method` → screen=`payout_method_picker`, `payout_wallet` → screen=`payout_wallet_input` save_rpc=`set_payout_wallet`, `payout_confirm` → screen=`payout_confirm`. Phone screens — без отдельных state codes (routing через `next_screen` save_rpc return).

**Таблица:** `payout_requests` (id, telegram_id, amount, currency='USDT', payout_method, wallet_address, bank_details, **status** (CHECK enforced), admin_notes, requested_at, reviewed_at, paid_at). Drafts — same table, status='draft'.

**Миграции:** 068-074 (база) + **145** (headless conversion).

**Defense-in-depth audit (после deploy Python):**
- Wallet validation в Python Proxy первой линией (regex match local), БД second line.
- Anti-spoofing: Layer 1 Python (`if contact.user_id != message.from.id`), Layer 2 БД RPC RAISE.

---

### 🎬 Макет 12.1 — Method Picker

Триггер: `[💳 Вывести средства]` на Ambassador Dashboard (11.3). Pre-check — если `balance < $50`:

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ ⚠️ Минимальный вывод: $50                  │
│                                            │
│ Текущий баланс: $35                        │
│                                            │
│ Пригласи ещё друзей — и выведем сразу!     │
╰────────────────────────────────────────────╯
```
Ключ: `payout.min_error` = «Минимальный вывод: ${min}» ✅ БД.
Кнопки: `[🔙 Назад → cmd_back]`.

Если `balance ≥ $50`:

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 💰 Выберите способ вывода:                 │
│                                            │
│ Баланс: $135.50                            │
╰────────────────────────────────────────────╯
```
Ключ: `payout.method_prompt` = «Выберите способ вывода:» ✅ БД.

**Кнопки (все ключи в БД):**
- `[💳 Банковская карта → payout_method_bank]` — `payout.method_bank`
- `[💎 USDT (сеть TON) → payout_method_usdt_ton]` — `payout.method_usdt_ton`
- `[🪙 USDT (TRC-20) → payout_method_usdt_trc20]` — `payout.method_usdt_trc20`
- `[🧾 Инвойс B2B → payout_method_invoice]` *(для юрлиц, TBD перевод)*
- `[🔙 Назад → cmd_back]`

FSM → `payout_method` (уже в workflow_states, migration 074).

---

### 🎬 Макет 12.1.5 — Phone verify (🆕 compliance/KYC)

Триггер: метод выбран. Перед вводом реквизитов — обязательный шаг подтверждения телефона. **Никогда не пропускается** (даже если phone уже привязан в онбординге — показываем confirm). FSM → `payout_phone_verify`.

**Полная стратегия и обоснование:** [[phone-collection-strategy]] Точка 2.

**Сценарий A — `users.phone_number IS NULL` (первый запрос):**

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 📱 Подтверди номер для выплаты             │
│                                            │
│ Шеф, куда платить? Дай номер для           │
│ верификации и привязки чека.               │
│                                            │
│ Один номер — один payout-канал.            │
╰────────────────────────────────────────────╯
```

Reply-клавиатура (TBD ключи `payout.phone_request_prompt`, `buttons.share_phone`):
- `[📱 Поделиться номером → request_contact=true]`
- `[🔙 Назад → cmd_back]` (возврат на 12.1 Method Picker)

**Сценарий B — `users.phone_number IS NOT NULL` (confirm):**

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 📱 Подтверди номер для выплаты             │
│                                            │
│ Это твой номер?                            │
│   +34...XXXX  *(последние 4 цифры)*        │
│                                            │
│ Если да — продолжаем. Если нет —           │
│ можешь привязать другой.                   │
╰────────────────────────────────────────────╯
```

Inline-клавиатура (TBD ключи `payout.phone_confirm_prompt`, `payout.phone_confirm_yes`, `payout.phone_change`):
- `[✅ Да, мой → cmd_payout_phone_confirm]` → переход на 12.2
- `[📱 Привязать другой номер → cmd_payout_phone_rebind]` → reply-клавиатура `request_contact` (как в Сценарии A)
- `[🔙 Назад → cmd_back]` → возврат на 12.1

**🔒 Anti-spoofing:** на `Message.contact` обязательна проверка `contact.user_id == from.id`. Без неё — `payout.phone_foreign_rejected` ошибка. Полные детали в [[phone-collection-strategy]].

**После успешной верификации** (Сценарий A → save phone, Сценарий B → confirm):
- RPC `set_user_phone(telegram_id, phone, 'payout', contact_user_id)` (только в A; в B — phone не меняется)
- ReplyKeyboardRemove если был reply
- FSM → `payout_wallet`
- Переход на 12.2

---

### 🎬 Макет 12.2 — Wallet / реквизиты input

Триггер: выбран метод. FSM → `payout_wallet`.

**Для карты:**
```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 💳 Банковская карта                         │
│                                            │
│ Введите номер карты или IBAN:              │
╰────────────────────────────────────────────╯
```
Ключ: `payout.bank_prompt` = «Введите номер карты или IBAN:» ✅ БД.

**Для крипты (TON / TRC-20):**
```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 💎 USDT (сеть TON)                          │
│                                            │
│ Введите адрес кошелька:                    │
╰────────────────────────────────────────────╯
```
Ключ: `payout.wallet_prompt` = «Введите адрес кошелька:» ✅ БД.

Кнопка: `[❌ Отменить → cmd_back]` — `payout.cancel_button` = «Отменить» ✅ БД. *(Заметка: по сквозному правилу ЧАСТИ 0 № 2 кнопка должна быть «🔙 Назад». Перевод есть, миграция для унификации не срочная.)*

---

### 🎬 Макет 12.3 — Confirm

Триггер: реквизиты введены. FSM → `payout_confirm`.

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ ✅ Подтвердить: вывести $135.50 на         │
│ UQB3...XYZ4?                               │
│                                            │
│ Обработка — до 24 часов после одобрения.   │
╰────────────────────────────────────────────╯
```
Ключ: `payout.confirm_prompt` = «Подтвердить: вывести ${amount} на {address}?» ✅ БД.

**Кнопки:**
- `[✅ Подтвердить → cmd_confirm_payout]` — `payout.confirm_button` ✅
- `[🔙 Назад → cmd_back]`

---

### 🎬 Макет 12.4 — Success (pending admin approval)

После клика Подтвердить:

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ ✅ Заявка на вывод отправлена!             │
│ Обработаем в течение 24 часов.             │
╰────────────────────────────────────────────╯
```
Ключ: `payout.success` = «Заявка на вывод отправлена! Обработаем в течение 24 часов.» ✅ БД.

Параллельно — создаётся запись в `payout_requests` (status=`pending`), отправляется admin card в чат `417002669`.

---

### 🎬 Макет 12.5 — Admin Approval Card (чат 417002669)

Сообщение CEO / admin:

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 🔔 Новая заявка на вывод                    │
│                                            │
│ 👤 Юзер: Алекс (@alexeycode, id 417002669) │
│ 💰 Сумма: $135.50                          │
│ 💳 Метод: USDT (TON)                       │
│ 📮 Адрес: UQB3...XYZ4                      │
│ 📅 Создана: 2026-04-20 18:42               │
│                                            │
│ 📊 Статистика юзера:                        │
│ • Всего привлечено: 142                    │
│ • Активных PRO: 18                         │
│ • Всего выплачено ранее: $450              │
╰────────────────────────────────────────────╯
```
Ключ: `payout.admin_title` = «Новая заявка на вывод» ✅ БД.

**Кнопки (admin actions):**
- `[✅ Одобрить и выплатить $135.50 → admin_payout_approve_{payout_id}]` — `payout.admin_approve` = «Одобрить»
- `[❌ Отклонить → admin_payout_reject_{payout_id}]` — `payout.admin_reject` = «Отклонить»

**После клика admin:**

*Approve:* обновить `payout_requests.status='paid'`, обнулить `ambassador_balance`, push юзеру (12.6).
*Reject:* обновить `status='rejected'`, push юзеру (12.7).

---

### 🎬 Макет 12.6 — Approved Notification (юзеру)

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 🎉 Твой вывод $135.50 одобрен!             │
│ Средства отправлены.                       │
╰────────────────────────────────────────────╯
```
Ключ: `payout.admin_approved_notify` = «Ваш вывод ${amount} одобрен! Средства отправлены.» ✅ БД.

---

### 🎬 Макет 12.7 — Rejected Notification (юзеру)

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ ⚠️ Твоя заявка на вывод отклонена.         │
│ Свяжись с поддержкой: @AutoRiot            │
╰────────────────────────────────────────────╯
```
Ключ: `payout.admin_rejected_notify` = «Ваша заявка на вывод отклонена. Свяжитесь с поддержкой.» ✅ БД.

---

### 🎬 Макет 12.8 — No balance error

Попытка нажать `[💳 Вывести средства]` при 0 балансе:

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ ⚠️ Нет средств для вывода                  │
╰────────────────────────────────────────────╯
```
Ключ: `payout.no_balance` = «Нет средств для вывода» ✅ БД.

Кнопка: `[📤 Поделиться кодом → share_ambassador_code]` (мотивация привести ещё друзей).

---

## 🗂 ЧАСТЬ 13 — Soft delete & restore

**Статус:** 📝 draft (обновлено 2026-04-21). *(ЧАСТЬ 3 §9 `delete_account_confirm` — первый экран уже описан.)*

**Что войдёт:** welcome-back gate для удалённого аккаунта (выбор restore vs fresh start), экран подтверждения восстановления (`restored_ok`), экран «свежий старт» (`fresh_ok`), dispatcher blocker (нельзя писать пока не выбрал).

**Переводы:** `restore.*` (5: `prompt_title`, `button_restore`, `button_fresh`, `restored_ok`, `fresh_ok`), `dispatcher.account_blocked`.
**FSM `state_code`:** `deleted`, `restoring:choose`, `anonymized`.
**Воркфлоу:** `01_Dispatcher` (account-blocked gate) + `DataRetentionCron` (03:00 UTC anonymize).
**Миграция:** 079.

---

### 🎬 Макет 13.1 — Blocked gate (вход после soft delete)

**Триггер:** юзер удалил аккаунт (статус `deleted`), теперь любой `/start`, reply-текст или нажатие кнопки ведёт на этот экран — до истечения 30-дневного окна или окончательной анонимизации (`anonymized`).

**Prompt-ключи:** `dispatcher.account_blocked` (fallback) / `restore.prompt_title` (главный).

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ Аккаунт удалён. У тебя есть 30 дней,       │
│ чтобы восстановить его.                    │
│                                            │
│ Что будем делать?                          │
╰────────────────────────────────────────────╯
```

**Клавиатура (inline):**
- `[🔄 Восстановить → cmd_restore_account]` — ключ `restore.button_restore`
- `[🆕 Начать заново → cmd_fresh_start]` — ключ `restore.button_fresh`

**FSM:** `deleted` → `restoring:choose` (после любого ввода Dispatcher перенаправляет сюда).

---

### 🎬 Макет 13.2 — Restored OK

**Триггер:** юзер нажал `cmd_restore_account`. Сервер снимает soft-delete флаг, все данные возвращаются (стрик, XP, NomsCoins, план, подписка).

**Ключ текста:** `restore.restored_ok`.

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ С возвращением! Всё на месте — стрик, XP,  │
│ NomsCoins, план. Продолжаем.               │
╰────────────────────────────────────────────╯
```

**Клавиатура (inline):** `[☀️ Мой день → cmd_get_stats]` — переход в [stats_main](#-часть-5--мой-день--stats).

**FSM:** `restoring:choose` → `registered`.

---

### 🎬 Макет 13.3 — Fresh start

**Триггер:** юзер нажал `cmd_fresh_start`. Сервер немедленно анонимизирует старые данные (без ожидания 30-дневного окна) и ведёт на онбординг.

**Ключ текста:** `restore.fresh_ok`.

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ Окей, с чистого листа. Твои старые данные  │
│ удалены, добро пожаловать заново.          │
╰────────────────────────────────────────────╯
```

**Клавиатура (inline):** `[▶️ Поехали → cmd_start_onboarding]` — reroute на `/start` flow → [welcome](#-часть-2--онбординг-welcome--done).

**FSM:** `restoring:choose` → `anonymized` → `onboarding:welcome`.

---

**Примечания:**
- `DataRetentionCron` (03:00 UTC daily) — окончательно анонимизирует аккаунты старше 30 дней в статусе `deleted`.
- Dispatcher blocker применяется ко **всем** входящим сообщениям при `users.deleted_at IS NOT NULL` — перехватывается до роутера.
- Миграция 079 (soft delete core) + Phase 2 от 2026-04-18 (добавила `deleted_at` в 44 защищённых полей Dispatcher).

---

## 🗂 ЧАСТЬ 14 — Cron push-уведомления (гибридный формат)

**Статус:** 🟡 placeholder (Пачка F). **⚠ legacy by design** — cron НЕ мигрирует на headless `ui_screens`. Правки только в `ui_translations` (тексты) и `app_constants` (пороги/иконки). Логика остаётся в Python.

**Формат (зафиксирован в ЧАСТИ 1):**
1. **Компактная таблица** по всем 17 push — тип / триггер / ключ шаблона / пример текста / кнопки (если есть) / кандидат на стикер (да/нет).
2. **Полные макеты** `╭─ NOMSaibot ─╮` для 2-3 push с CTA-кнопками: `subscription_expiry`, `league_promotion`, `streak_broken` (там где важен conversion-клик).
3. **Кандидаты на замену видеостикером:** reminders (meal_morning/lunch/dinner, day_close) — короткие, эмоциональные, идеальны для стикерных push с минимальным caption. Отмечаем в таблице.

**17 push-типов (Python cron):**
- Reminders: (текст обновлён 2026-04-21, Sassy Sage — см. подпараграф Reminders text refresh ниже). Ключи: `reminder_meal_morning`, `reminder_meal_lunch`, `reminder_meal_dinner`, `reminder_day_close`, `reminder_streak_warning`, `reminder_quest`, `reminder_inactivity`.
- League: `league_promotion`, `league_demotion`, `league_fomo_*` (leader / promote / safe / demote).
- Streak: `streak_frozen`, `streak_broken`.
- Economy: `mana_recharged`.
- Payment: `subscription_expiry`, `subscription_renewal_reminder`.
- **🆕 Profile:** `profile_incomplete` — напоминание дозаполнить skipped поля онбординга (`goal_speed`, `phenotype`). *(target_weight_kg исключён из UX решением 2026-04-21.)* Триггер: юзер активен (≥1 лог еды за последние 2 дня) И прошло ≥3 дня с `registered` И есть skipped поля. Дебаунс: максимум 1 раз в 7 дней. Кнопка CTA: `[🎯 Доделать настройку → cmd_my_plan]`. Переводы: `cron_notifications.profile_incomplete_{title,body,button}` (✅ migration 102 applied 2026-04-20). Candidate на стикер (💭 Noms с клипбордом).
- **🆕 Referral:** `referral_activated` — squad celebration для реферера, когда новый друг прошёл первый день и unlock'нул escrow.
- **🆕 Comeback × 2:** `comeback_2days`, `comeback_7days` (pause after 2 / 7 days of inactivity).

**Переводы:** `cron_notifications.*` (24 ключа), `payment.expired_title`, `payment.renewal_reminder_*`, `league_results.*`.
**Источники:** `crons/reminders.py`, `crons/league_cycle.py`, `crons/streak_checker.py`, `crons/subscription_lifecycle.py`, `crons/mana_reset.py`.

### Reminders text refresh (2026-04-21, миграции 104-107)

Legacy scalar-ключи обновлены под Sassy Sage тон (migration 107 refresh):

| Ключ | Новый текст (ru) |
|---|---|
| `cron_notifications.reminder_meal_morning` | «Доброе утро! ☀️ Новый день — новые возможности. Записываем завтрак?» |
| `cron_notifications.reminder_meal_lunch` | «🍽️ Обед сам себя не залогирует. Давай, я жду» |
| `cron_notifications.reminder_meal_dinner` | «Как прошел день? 🌙 Если еще не записан ужин — самое время!» |
| `cron_notifications.reminder_inactivity` | «👀 {name}, пропал без вести. Живой? Покажи тарелку» |

Плюс добавлены **новые array[3] ключи** (migration 105, для headless Sassy Sage random):

- `cron_notifications.morning[3]` — 3 варианта на утренний push
- `cron_notifications.evening[3]` — 3 варианта вечер
- `cron_notifications.comeback_2days[3]` — 3 варианта 2-дневный comeback
- `cron_notifications.comeback_7days[3]` — 3 варианта 7-дневный comeback

### Comeback push-ветка (новая, 2026-04-21)

**Comeback_2days** — юзер пропал на 2 дня без логов. Варианты:
1. «Эй, давно не виделись! 👋 Стрик сгорел, но это не страшно. Жизнь бывает сложной. Давай начнем заново?»
2. «С возвращением! 😊 Я скучал. Ничего страшного — главное, что ты снова здесь. Записываем сегодняшнюю еду?»
3. «Привет! Давненько не общались 👋 Бывают перерывы — это нормально. Давай продолжим с того места, где остановились?»

**Comeback_7days** — юзер пропал на 7+ дней. Варианты:
1. «Ну ты даёшь! Целая неделя пропала 😅 Жизнь бывает сложной, я понимаю. Готов вернуться к трекингу?»
2. «С возвращением! 😊 Я скучал. Ничего страшного — главное, что ты снова здесь. Записываем сегодняшнюю еду?»
3. «Привет! Давненько не общались 👋 Бывают перерывы — это нормально. Давай продолжим с того места, где остановились?»

---

## 🗂 ЧАСТЬ 15 — Error / edge states + wait-индикаторы (🎥 стикеры)

**Статус:** 📝 draft (обновлено 2026-04-21). Компактная таблица «ключ / тип / текст (ru) / стикер-кандидат».

Live-значения из `ui_translations` (lang_code=ru). Sassy Sage random arrays помечены `array[N]`.

### Errors

| Ключ | Тип | Текст (ru) | Стикер-кандидат? |
|---|---|---|---|
| `errors.not_food` | scalar | «Упс, это точно еда? 🤔 Я вижу тут что-то другое. Попробуй еще раз!» | ✅ `noms_confused` |
| `errors.ai_not_food` | array[3] | 1) «Упс, это точно еда? 🤔 Я вижу тут что-то другое. Попробуй еще раз!» 2) «Ммм... это не похоже на еду. 😅 Давай попробуем с фоткой еды!» 3) «Это не еда. Может, тебе хотелось отправить это в другой чат? 😉» | ✅ `noms_confused` |
| `errors.invalid_age` | scalar | «Введи возраст от 13 до 120» | ❌ (inline hint) |
| `errors.invalid_height` | scalar | «Введи рост от 50 до 250 см» | ❌ |
| `errors.invalid_weight` | scalar | «Введи число от 20 до 300» | ❌ |
| `errors.not_a_number` | scalar (param `{example}`) | «Эй, мне нужно число! 😅 Напиши, например: {example}» | ❌ |
| `errors.invalid_gender` | ⛔ отсутствует в БД | — inline UX через picker, текст не нужен | — |
| `errors.invalid_activity` | ⛔ отсутствует | inline picker | — |
| `errors.invalid_training` | ⛔ отсутствует | inline picker | — |
| `errors.invalid_goal` | ⛔ отсутствует | inline picker | — |
| `errors.invalid_country` | ⛔ отсутствует | inline picker | — |
| `errors.invalid_timezone` | ⛔ отсутствует | inline picker | — |

### Messages (system)

| Ключ | Тип | Текст (ru) | Стикер-кандидат? |
|---|---|---|---|
| `messages.deleted` | scalar | «Удалено» | ❌ (toast) |
| `messages.spam_protect` | scalar | «🚫 Этот тип контента не поддерживается. Отправьте фото еды, голосовое сообщение или текст.» | ❌ |
| `messages.complete_profile_prompt` | scalar | «✨ Я посчитал это! Но чтобы следить за твоей нормой, давай закончим настройку профиля? Напиши свой возраст:» | ❌ (CTA flow) |
| `messages.no_credits` | scalar | «Кредиты закончились. Пополните баланс 💳» | ❌ |

### Wait-индикаторы (🎥 стикеры предпочтительны)

| Ключ | Тип | Текст (ru) | Стикер-кандидат? |
|---|---|---|---|
| `wait.searching` | scalar | «🔍 Ищу в базе...» | ✅ `noms_thinking` |
| `wait.calculating` | scalar | «🔢 Считаю калории...» | ✅ `noms_calculating` |
| `wait.analyzing_photo` | scalar | «🧠 Анализирую фото...» | ✅ `noms_analyzing` (приоритет) |
| `wait.updating_variants` | array[3] | 1) «{{icon_settings}} Вношу данные. Дай мне время подумать...» 2) «{{icon_settings}} Понял, пересчитываю...» 3) «{{icon_settings}} Секунду, обновляю запись...» | ✅ `noms_thinking` |

### Gate

| Ключ | Тип | Текст (ru) | Стикер-кандидат? |
|---|---|---|---|
| `dispatcher.account_blocked` | scalar | «Ваш аккаунт удалён. Нажмите /start, чтобы восстановить или начать заново.» | ❌ — см. [ЧАСТЬ 13](#-часть-13--soft-delete--restore) |

### Validation (hints / inline)

| Ключ | Текст (ru) |
|---|---|
| `validation.hint_age` | «Например: 25» |
| `validation.hint_height` | «Например: 175» |
| `validation.hint_weight` | «Например: 70 или 70.5» |
| `validation.invalid_age` | «Введите возраст от 1 до 120 лет» |
| `validation.invalid_height` | «Введите рост от 50 до 300 см» |
| `validation.invalid_weight` | «Введите вес от 20 до 300 кг» |
| `validation.invalid_number` | «Введите число (например: 75 или 75.5)» |
| `validation.complete_registration` | «Сначала завершите регистрацию! 👇» |

**Переводы:** `errors.*` (5 scalar + 1 array), `messages.*` (4), `wait.*` (3 scalar + 1 array), `validation.*` (8), `dispatcher.account_blocked`.
**Стикеры (TBD каталог):** `noms_analyzing`, `noms_thinking`, `noms_calculating`, `noms_confused`.

**Замечание:** 6 ключей `errors.invalid_{gender,activity,training,goal,country,timezone}` отсутствуют в БД — эти категории используют inline pickers (кнопки), поэтому свободный ввод невалиден и текст не нужен.

---

## 🗂 ЧАСТЬ 16 — Celebrations геймификации

**Статус:** 📝 draft (обновлено 2026-04-21 миграциями 104-107).

**Что войдёт:** level-up (60 уровней с tamagotchi stages из `levels_config`), streak milestone (7/30 дней), daily goal reached, first_log celebration, league promotion (см. ЧАСТЬ 10 §10.4).

**Переводы (все ✅ migration 105, JSONB array[3] для Sassy Sage random):**

### 🎬 Макет 16.1 — First Log Celebration

Триггер: юзер записал ПЕРВЫЙ приём пищи в жизни (после онбординга).

```
🎥 [sticker: noms_first_log]
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ {random gamification.first_log[0..2]}      │
╰────────────────────────────────────────────╯
```

3 варианта:
1. «🎉 Первый прием пищи записан! Тобой только что основан путь к осознанному питанию. Продолжай в том же духе!»
2. «Бум! 💥 Первая запись сделана! Теперь ты знаешь, что было загружено в твой организм. Завтра узнаешь, как это повлияло на твою цель. Держи темп!»
3. «🎓 Поздравляю! Первый шаг сделан. Твой NOMS разбужен! Продолжай кормить его — он голоден!»

---

### 🎬 Макет 16.2 — Daily Goal Reached

Триггер: юзер достиг дневной нормы калорий (не перебрал, не недобрал — попал в диапазон).

```
🎥 [sticker: noms_daily_win]
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ {random gamification.daily_goal_reached}   │
╰────────────────────────────────────────────╯
```

3 варианта:
1. «Попадание в цель! 🎯 Сегодня было съедено столько, сколько нужно. Так держать!»
2. «🎉 Идеальный день! Дневная норма была достигнута. NOMS гордится тобой!»
3. «Бинго! 🎲 Дневная цель выполнена. Ты на правильном пути. Продолжай в том же духе!»

---

### 🎬 Макет 16.3 — Streak 7 days

Триггер: 7-дневный стрик логирования.

```
🎥 [sticker: noms_streak_7]
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ {random gamification.streak_7[0..2]}       │
╰────────────────────────────────────────────╯
```

3 варианта:
1. «🔥 ЛЕГЕНДА! {streak} дней подряд! Ты кормишь своего NOMS'a {streak} дней подряд. Твой метаболизм танцует макарену. Держи новый бейдж!»
2. «🏆 НЕДЕЛЯ СТРИКА! Большинство сдаются на 3-й день. Ты — нет. Ты — чемпион. Продолжай!»
3. «💪 ВАУ! {streak} дней без перерыва! Знаешь, что это значит? Ты уже формируешь привычку. Продолжай в том же духе!»

Плюс NomsCoins-награда.

---

### 🎬 Макет 16.4 — Streak 30 days

Триггер: 30-дневный стрик.

```
🎥 [sticker: noms_streak_30]
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ {random gamification.streak_30[0..2]}      │
╰────────────────────────────────────────────╯
```

3 варианта:
1. «ВАУ! {streak} дней 💎 подряд! NOMS эволюционировал до нового уровня!»
2. «Месяц ежедневного трекинга! 🎉 Твой Метабол-пет растёт. Ты официально крут!»
3. «{streak} дней подряд! 🚀 Ты устроил настоящий марафон. NOMS гордится!»

---

### 🎬 Макет 16.5 — Level-up (из `levels_config`)

Триггер: юзер набрал достаточно XP для следующего уровня (60 уровней).

```
🎥 [sticker: noms_level_up]
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ 🎉 Новый уровень: {level}!                 │
│                                            │
│ {tamagotchi_message из levels_config}      │
│                                            │
│ 💎 +{reward_coins} NomsCoins                │
╰────────────────────────────────────────────╯
```

Кнопка: `[🚀 Прогресс → cmd_progress]`.

**Источники:**
- `gamification.*` (2 legacy + 4 новых array[3]): `onboarding_mana` (старый), `premium_limit_reached` (старый), `first_log[3]`, `daily_goal_reached[3]`, `streak_7[3]`, `streak_30[3]`.
- `profile_gamification.*` (7 ключей).
- `levels_config` таблица (60 строк с `level_num`, `xp_required`, `tamagotchi_stage`, `tamagotchi_message`, `reward_coins`).
- Воркфлоу `04_Menu` (вставляется в ответ на `log_meal_transaction.leveled_up=true`), `crons/league_cycle.py`, `crons/streak_checker.py`.

**Стикеры (TBD каталог):** `noms_first_log`, `noms_daily_win`, `noms_streak_7`, `noms_streak_30`, `noms_level_up`.

---

## 🗂 ЧАСТЬ 17 — Таблицы локализации enum'ов

### `users.goal_type`

| enum | icon (app\_constants) | ru (переводы) | en |
| :---- | :---- | :---- | :---- |
| lose | `goal_lose` \= 📉 | Похудение | Lose weight |
| maintain | `goal_maintain` \= 🔄 | Поддержание | Maintain |
| gain | `goal_gain` \= 💪 | Набор | Gain weight |

### `users.goal_speed` (зависит от goal\_type)

| goal\_type | speed | indicator | ru label | pct label (из app\_constants) |
| :---- | :---- | :---- | :---- | :---- |
| lose | slow | 🟡 | Медленно | `goal_speed_slow_deficit=10` → −10% |
| lose | normal | 🟢 | Нормально | `goal_speed_normal_deficit=15` → −15% |
| lose | fast | 🔴 | Быстро | `goal_speed_fast_deficit=20` → −20% |
| gain | slow | 🟡 | Медленно | `goal_speed_slow_surplus=8` → \+8% |
| gain | normal | 🟢 | Нормально | `goal_speed_normal_surplus=10` → \+10% |
| gain | fast | 🔴 | Быстро | `goal_speed_fast_surplus=15` → \+15% |
| maintain | — | — | — | — |

Шаблоны процента: `profile.speed_deficit` \= *"Дефицит {pct}%"*, `profile.speed_surplus` \= *"Профицит {pct}%"*.

**Noms-варианты** (random при каждом показе, migration 108 applied 2026-04-21):
Ключ `profile.noms_speed_intro` (JSONB array[3]) — 3 варианта интро при показе speed picker'а, Sassy Sage tone.
Подсказка `profile.speed_hint` \= *«Помни: стабильность важнее скорости. Выбери комфортный режим.»*

### `activity_level`

| enum | ru label (ключ `answers.act_*`) | en (label) |
| :---- | :---- | :---- |
| sedentary | `answers.act_sedentary` \= *"Сижу (Офис/IT)"* | Sit (Office/IT) |
| light | `answers.act_light` \= *"Стою/Хожу (Магазин)"* | Stand/Walk (Retail) |
| moderate | `answers.act_moderate` \= *"В движении (Курьер)"* | Active (Courier) |
| heavy | `answers.act_heavy` \= *"Тяжелый труд"* | Heavy labour |

⚠ В БД enum называется `heavy` (не `active`/`very_active` — исторические имена из старых миграций). 4 значения, не 5.

### `training_type`

| enum | ru label (ключ `answers.train_*`) | `protein_g_per_kg` (из `calculate_user_targets()` migration 055) |
| :---- | :---- | :---- |
| strength | `answers.train_strength` \= *"Силовые"* | 2.0 |
| cardio | `answers.train_cardio` \= *"Кардио"* | 1.4 |
| mixed | `answers.train_mixed` \= *"Смешанные"* | 1.6 |
| skip | `answers.train_skip` \= *"Пропустить"* | 1.2 (fallback на базовый уровень) |

⚠ В БД enum — `skip` (не `none`), значение соответствует UX «не тренируюсь / пропустить шаг».

### `phenotype` (реальные ключи из ui\_translations ru)

| enum | ru label (ui\_translations) |
| :---- | :---- |
| default (standard) | `profile.phenotype_standard` \= *"Стандартное"* |
| athlete | `profile.phenotype_athlete` \= *"Атлетическое"* |
| monw | `profile.phenotype_monw` \= *"MONW (Худой полный)"* |
| obese | `profile.phenotype_obese` \= *"Модифицированное"* |

### `gender`

| enum | icon (app\_constants) | ru | en |
| :---- | :---- | :---- | :---- |
| male | `icon_male` \= 👨 | Мужской | Male |
| female | `icon_female` \= 👩 | Женский | Female |

---

## 🗂 ЧАСТЬ 18 — Known Deviations (БД vs. session 6 spec)

Snapshot: 2026-04-20 (после миграций 091-096).

| Экран | Что есть сейчас в БД | Что должно быть по spec |
| :---- | :---- | :---- |
| profile\_main | Простой текст (Уровень / стрик / XP / Coins / Mana). Нет Agent Dossier format, нет Free/Premium маркера, нет Bio and goal блока, нет Noms commentary. | Полный Agent Dossier (§1). Все ключи `profile.title_agent`, `profile.bio_and_goal`, `profile.sage_free_*`, `profile.sage_premium_*`, `profile.status_*`, `profile.limit_logs_*` уже существуют — нужно только пересобрать `profile.main_text`. TBD migration 098\. |
| my\_plan | 3 строки с локализованными labels (Цель / Темп / Калории). 6 кнопок ✅. Нет activity/training/phenotype/macros/Noms. | Полный текст §2. Нужны новые ключи `profile.activity_label_*`, `profile.training_label_*`, `profile.noms_commentary_plan_*`. TBD migration 097\. |
| settings | 2 строки (Язык / Часовой пояс). Нет Country, нет Noms. | Добавить Country \+ Noms (§3). Ключ `profile.sage_settings` уже есть. TBD migration 099\. |
| personal\_metrics | Только Вес \+ Рост. Нет Age / Gender. Back→my\_plan ✅. | Age \+ Gender (§4). RPC уже возвращает эти поля (миграция 091). TBD migration 099\. |
| help | Короткий текст без Noms. | Добавить Noms (§5). Ключ `profile.sage_help` уже есть. TBD migration 099\. |
| ask\_weight/age/height | Ключи `ask_*.prompt` отсутствуют в `ui_translations`. Тексты хардкодены в n8n либо отдельной нодой. Кнопка: `[❌ Отмена → cmd_back]`. | Добавить ключи (§6-8). Emoji кнопки можно оставить ❌ или поменять на 🚫 (session 6 предлагает 🚫). TBD migration 100\. |
| ask\_age | validation `integer 13-120` ✅. | Соответствует (§7). `save_rpc=set_user_age` конвертирует в birth\_date под капотом. |
| delete\_account\_confirm | Текст близок к spec ✅. | Minor wording правки если найдутся. |

### Applied migrations 2026-04-20..21 — закрытые гэпы

| Миграция | Что закрыла | Применена |
|---|---|---|
| 102 | `buttons.skip`, `onboarding.skip_hint`, `cron_notifications.profile_incomplete_{title,body,button}` — 13 языков | 2026-04-20 ✅ |
| 103 | Колонка `users.notifications_mode text NOT NULL DEFAULT 'balanced' CHECK IN (zen,balanced,beast)` | 2026-04-20 ✅ |
| 104 | `errors.ai_not_food[3]`, `payment.success[3]`, `referral.present_friend[3]` — Sassy Sage random массивы | 2026-04-21 ✅ (параллельный агент) |
| 105 | `gamification.first_log/daily_goal_reached/streak_7/streak_30` (array[3]), `cron_notifications.morning/evening/comeback_2days/comeback_7days` (array[3]) | 2026-04-21 ✅ |
| 106 | Новые секции `free_tier` (`trial_limit_3`, `limit_reached`) и `pay` (`paywall`) — array[3] | 2026-04-21 ✅ |
| 107 | Refresh 5 legacy scalar ключей под Sassy Sage (`reminder_meal_morning/lunch/dinner`, `reminder_inactivity`, `errors.not_food`) | 2026-04-21 ✅ |
| 108 | `questions.goal_speed`, `answers.speed_slow/normal/fast`, `profile.noms_speed_intro[3]`, `profile.speed_hint` — 13 языков | 2026-04-21 ✅ |

> **Target_weight_kg** окончательно исключён из UX решением 2026-04-21 — колонка `users.target_weight_kg` остаётся в БД как артефакт, но не экспонируется пользователю (см. [ЧАСТЬ 2 § Решение про target_weight_kg](#-часть-2--онбординг-welcome--done)).

---

## 📝 Session 10 Changelog (2026-04-22)

**Session 10 deployed:** 6 migrations (110-115) + 2 n8n PUTs (01_Dispatcher Route Classifier v1.9, 04_Menu_v3 Dumb Renderer checkmark prefix). 9 inline pickers Headless.

### Architectural decisions (authoritative going forward)

1. **Callback convention = RPC ground truth**, не specs mockup. Setter RPCs парсят `cmd_select_*` (4 RPCs) и `cmd_speed_*` (speed). Specs теперь outline canonical conventions (см. Task 1.C).

2. **Checkmark prefix pattern:** `✅ 🐢 Медленный` — checkmark ПЕРЕД оригинальной иконкой. render_screen RPC emits `is_current: true` flag; Dumb Renderer prepends `{constants.icon_check} ` перед icon+label. Split concerns (DB detects, Frontend renders). См. KB `concepts/checkmark-prefix-pattern.md`.

3. **Picker save via callback:** button.meta содержит `save_via_callback:true, save_rpc:<name>, save_value:<val>, target_screen:<return>, clear_status:true`. process_user_input с whitelist validation (`pg_proc WHERE proname LIKE 'set\_user\_%'`) перед EXECUTE.

4. **FSM state naming:** `edit_*` (underscore) consistently. Legacy `editing:country/timezone` deprecated.

5. **goal_speed auto-reset:** при смене goal_type через set_user_goal, goal_speed='slow' (минимум). User может переопределить. Migration 115 Block A.

6. **cmd_select_training_skip visibility:** только в online онбординге (`visible_condition: u.status LIKE 'registration_step_%'`). Migration 115 Block B.

7. **Top-level fast-path:** cmd_get_profile/my_plan/settings/personal_metrics/help/delete_account forced canonical screen + clear nav_stack. Prevents "Profile → edit_speed" bug at stack accumulation. Migration 114.

8. **Raw emoji в answers.***: strip. Icons из app_constants через icon_const_key. Исключение — `answers.lang_*` (native flag+label design). Migration 114 Block A.

### Deferred Session 11

- `edit_phenotype` — multi-step 4Q quiz (render_strategy enum не допускает "multi-step")
- `edit_country` / `edit_timezone` — dynamic_list rendering (Dumb Renderer extension)
- Reaction timing fix at delete_and_send_new (reaction на удалённое сообщение invisible)
- 02_Onboarding_v3 → Headless migration (Phase 3B + 04_Menu legacy decomm)
- Ambassador Dashboard / Payout Headless

### KB concepts captured (Session 10)

- `concepts/headless-picker-pattern.md` — full recipe
- `concepts/pre-migration-discovery-recipe.md` — Phase 0 protocol
- `concepts/specs-vs-reality-ground-truth.md` — RPC grep priority
- `concepts/adversarial-review-protocol.md` — pre-apply critical pass
- `concepts/checkmark-prefix-pattern.md` — checkmark split concerns

### User preferences 2026-04-22

- Speed emojis unified: 🐢 / ⚖️ / 🚀 (applied to app_constants.icon_speed_*)
- No gain-specific labels ("Плавный/Агрессивный" rejected — single set applies both lose/gain)
- 04_Menu legacy → kill в Phase 3B (не параллельный — sequential после Stats/Progress/Shop/League/Friends Headless migration)
- 02_Onboarding_v3 → Headless в Phase 3B (unlock реальный Shared Screens reuse)

---

