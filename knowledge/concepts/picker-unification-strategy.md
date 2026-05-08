---
title: "Picker Unification Strategy (Onboarding ≡ Edit Profile)"
aliases: [unified-pickers, data-driven-pickers, onboarding-edit-duplication, registration-step-vs-edit, ui-pickers-table]
tags: [architecture, refactor, scalability, onboarding, profile, backlog, strategic]
sources:
  - "daily/2026-04-17.md"
  - "agent reports 2026-04-17 (a104a04223e51efc8, a57aeba3190a97d2f)"
created: 2026-04-17
updated: 2026-04-17
---

# Picker Unification Strategy

Стратегическая статья: **онбординг и edit-profile решают одну задачу** (получить от пользователя pol/vozrast/ves/rost/activity/training/goal/speed) двумя разными flows с двойным рендерингом, дублированием кода и риском рассинхронизации. Фиксация находок от 2026-04-17 + рекомендации для будущих сессий/агентов.

## Key Points

- **Один и тот же набор RPC используется из обоих flows.** `set_user_gender`, `set_user_age`, `set_user_weight`, `set_user_height`, `set_user_activity`, `set_user_training_type`, `set_user_goal`, `set_user_goal_speed` — вызываются **и из 02_Onboarding_v3 Generic RPC, и из 04_Menu Edit flow**. Хранение в БД уже унифицировано. Дублируется только **UI-слой**.
- **Жёсткое разделение статусов:** `registration_step_1..5/training/goal` (онбординг) vs `edit_gender/age/weight/height/activity/training/goal/speed` (edit). Каждый шаг знает "свой" next-status. После успешного сохранения: онбординг → next step, edit → `registered`.
- **UI-код дублируется в 3+ местах:** `02_Onboarding_v3 → Response Builder` (онбординг picker), `04_Menu → Build Ask Markup` (edit picker), `04_Menu → Build Profile Sub-Screen` (display-only рендер с текущим значением). Silent UI bug 2026-04-16: добавили ✅ mark только в одно место из двух.
- **NOMS имеет trial-режим для незарегистрированных:** 5 пробных логов до регистрации (`ui_translations.msg_trial_limit` / `msg_trial_ended`). Значит незарегистрированный user status='new' **не лишён функциональности** и бот для него "живой". Это влияет на UX решения: нельзя просто завернуть новичка в ограниченный welcome — он уже логирует еду, ему нужен доступ к базовой навигации.
- **Mana grant:** после completion onboarding — `grant_registration_mana` RPC даёт 5 бесплатных mana (`app_constants.mana_gift_registration=5`). Это отдельная тема от pickers, но релевантна для retention-логики (см. ниже).

## Details

### Карта дублирования (2026-04-17)

| Поле | Onboarding nodes | Edit nodes | RPC (общая) | status_after_save |
|---|---|---|---|---|
| Gender | Response Builder case `registration_step_1` | Build Ask Markup case `edit_gender` | `set_user_gender` | onboarding: `registration_step_2`; edit: `registered` |
| Age | numeric input handler | Build Ask Markup case `edit_age` | `set_user_age` | `registration_step_3` / `registered` |
| Weight | numeric input | Build Ask Markup `edit_weight` | `set_user_weight` / `sync_user_weight` | `registration_step_4` / `registered` |
| Height | numeric input | Build Ask Markup `edit_height` | `set_user_height` | `registration_step_5` / `registered` |
| Activity | Response Builder `registration_step_5` | Build Ask Markup `edit_activity` | `set_user_activity` | `registration_step_training` / `registered` |
| Training | Response Builder `registration_step_training` | Build Ask Markup `edit_training` | `set_user_training_type` | `registration_step_goal` / `registered` |
| Goal | Response Builder `registration_step_goal` | Build Ask Markup `edit_goal` | `set_user_goal` | → speed picker или `registered` |
| Speed | Speed picker (in Onboarding Engine isSpeedCallback) | Build Ask Markup `edit_speed` | `set_user_goal_speed` | `registered` |
| Phenotype | — (future) | Build Ask Markup `edit_phenotype` | — (planned) | `registered` |

**Итого: 8 дублированных UI-pickers × ~40 строк JS каждый = ~320 строк дублированного UI-кода.**

### Почему Response Builder ≠ Build Ask Markup

Функциональных различий почти нет:
1. **Text content:** онбординг — "Ваш пол?"; edit — "Укажите пол" (но переводы часто совпадают)
2. **Current value mark ✅:** в edit picker нужен чекмарк на текущем значении. В онбординге — не нужен (значение ещё не выбрано).
3. **Back button target:** онбординг — нет Back (linear flow); edit — Back → Profile/Sub-Screen (теперь через nav_stack).
4. **Next-status routing:** онбординг — linear → next step; edit — всегда → `registered`.

Всё это можно выразить через **конфиг**, а не через дублированный код.

### Предлагаемая архитектура: data-driven `ui_pickers` table

```sql
CREATE TABLE ui_pickers (
  picker_key TEXT PRIMARY KEY,     -- 'gender', 'activity', 'goal', 'training', 'speed'
  field_column TEXT NOT NULL,      -- 'gender', 'activity_level', 'goal_type', ...
  input_type TEXT NOT NULL,        -- 'single_choice' | 'numeric'
  options JSONB,                   -- [{key, icon_const, label_translation_key}, ...]
  question_key TEXT NOT NULL,      -- ui_translations key для заголовка picker
  save_rpc TEXT NOT NULL,          -- 'set_user_gender' etc
  icon_const TEXT                  -- app_constants emoji key
);

-- Пример строки:
INSERT INTO ui_pickers VALUES (
  'gender',
  'gender',
  'single_choice',
  '[
    {"key":"male","icon":"icon_male","label":"answers.male"},
    {"key":"female","icon":"icon_female","label":"answers.female"}
  ]',
  'questions.gender',
  'set_user_gender',
  'icon_gender'
);
```

**RPC `get_picker_config(picker_key, lang)`** возвращает уже локализованный конфиг для рендера — одна Code-нода в n8n формирует inline_keyboard из этого конфига.

**Flow:**
```
Онбординг Response Builder (status='registration_step_1'):
  picker_key='gender' (из map[status→picker]) → get_picker_config → render

Edit in 04_Menu (status='edit_gender'):
  picker_key='gender' (из map[status→picker]) → get_picker_config → render + ✅ mark on current value

Oба используют ОДНУ Code-ноду builder'а. Отличия — через флаги (isEdit, currentValue).
```

**Добавление нового edit-поля сейчас:** 8 touch points (4 места в коде + workflow_states + ui_translations + 2 Prepare fields).
**После refactor:** INSERT в `ui_pickers` + переводы → 2 touch points.

## UX проблема: Settings vs Welcome для нового юзера

### Находка (Agent 1, 2026-04-17)

Bug 2 `isBack` ветка в Onboarding Engine v3 рендерит Settings payload (Language/Country/Timezone/Delete account) для **любого** Back-клика из Language picker, даже если `previous_status='new'` (незарегистрированный).

**Функционально:** БД не ломается, returnStatus логика корректна. **UX:** новичок видит меню зарегистрированного.

### Контекст retention/engagement (важно)

Пользователь (2026-04-17) озвучил: бот имеет **trial-режим на 5 логов еды для незарегистрированных** (см. Key Points). Это значит:

- **Welcome screen новичка не должен быть голым.** У него уже есть доступ к AI-логированию еды.
- **Запирать новичка в ограниченном welcome при нажатии 🔙 Back из Language** — плохо для retention.
- **Но Settings (Country/Timezone/Delete account) — тоже неправильно:** юзер ещё не имеет country/timezone (NULL), и "Delete account" бессмысленна.

### Рекомендация (для будущей сессии)

Создать **третий payload** в isBack ветке: "Welcome+Language" для `returnStatus='new'`:
```js
if (returnStatus === 'new') {
  // render: приветствие + reply keyboard [▶️ Start] [🌐 Language]
  // текст: "Язык обновлён! Начнём?" — не Settings
} else if (returnStatus === 'registered') {
  // render: Settings screen (текущее поведение после Bug 2)
} else {
  // status === 'registration_step_*' — вернуть в тот же шаг
  // render: re-ask question (вопрос про pol/vozrast/...) на новом языке
}
```

Реализация: 10-15 строк в Onboarding Engine, output `status_and_send`.

### Retention: mana gift + trial

Не менять на этом этапе. Trial 5 логов + registration mana 5 — это уже корректная retention-воронка. Задача refactor — не трогать **бизнес-поведение**, только **архитектуру UI**.

## Trade-offs: unification vs текущая структура

| Подход | Pros | Cons |
|---|---|---|
| **A. Полная unification (ui_pickers table + единый builder)** | Добавление поля = INSERT в БД. Нет silent bugs. UI консистентен. | Крупный refactor (2-3 сессии). Нужна миграция данных. Возможно нужен ещё 1 sub-workflow. |
| **B. Shared Code node (вынести Build Ask Markup logic в common node, вызывать из обоих)** | Меньше кода (~40% экономии). Быстрее реализовать (1 сессия). | Всё ещё нужно править в 1 месте. Не убирает хардкод. |
| **C. Не трогать. Сохранить статус-кво.** | Ноль рисков. | Каждое новое поле = двойная работа + риск silent UI bug (уже был 2026-04-16 с ✅). |

**Рекомендация:** **Вариант A** после завершения Bug 6 (nav_stack везде). Почему:
- nav_stack — это infra для Back. Unified pickers — infra для add/edit flow. Разные слои.
- Вариант A без nav_stack = тех-долг: picker рендерит cmd_back, а назад не работает.
- После nav_stack + unified pickers = "чистая" архитектура для добавления любых полей.

## Пересечение с Bug 6 nav_stack

nav_stack (migrations 076-078) покрывает **навигацию между screens**. Unified pickers покрывают **рендеринг одного экрана из конфига**. Оба паттерна комплементарны:

- **nav_stack:** "откуда я пришёл" → куда вернуться. Чистит хардкод Back target.
- **ui_pickers:** "что показать" → из конфига. Чистит дублирование Build Ask Markup / Response Builder.

При планировании рефакторинга: **nav_stack сначала (в процессе), ui_pickers потом** — иначе unified picker получит нерабочий Back.

## Action items для будущих сессий

1. **Fix R1 (regression новичка из Bug 2):** 10-15 строк в Onboarding Engine `isBack` ветке, разделение welcome / settings / re-ask по `returnStatus`. **Приоритет: высокий.** Можно делать в любой сессии, не блокирует.

2. **Завершить Bug 6 (Phase 3-8).** Нужно до unification, чтобы unified pickers имели рабочий Back.

3. **Migration 079: `ui_pickers` table + `get_picker_config` RPC.** Seed 8 строк (gender/age/weight/height/activity/training/goal/speed). Migration idempotent.

4. **Extract 04.3_Edit_Profile workflow** (шаг 4 из Agent 2 roadmap). Использует `get_picker_config`. Replaces Build Ask Markup + 9 case-веток.

5. **Refactor 02_Onboarding_v3 Response Builder** — использует тот же `get_picker_config`. Убрать дублирование.

6. **Deprecate 16 статусов:** `registration_step_*` (8) + `edit_*` (8) можно свести к **одному полю** `users.current_picker TEXT` (значения 'gender'/'age'/...) + флагу `users.is_onboarding BOOLEAN`. Но это tier-2 рефакторинг, после unification.

## Для других агентов

- **Не писать новый picker через старый способ.** Если приходит задача "добавить edit_X" — проверить есть ли уже unified pickers. Если нет — сначала обсудить с пользователем делать ли unification сейчас.
- **Не копипастить Build Ask Markup case.** Если нужно расширить — добавь строку в `ui_pickers`, не новый case.
- **Прежде чем менять UI-код pickers в одном месте** — проверить дубль во втором (Response Builder vs Build Ask Markup). Иначе silent UI bug.

## Related

- [[n8n-subworkflow-contract]] — v1 vs v3 routing, Action Router outputs (нужны для unified picker routing)
- [[n8n-data-flow-patterns]] — HTTP Request overwrites $json (урок из Phase 2.5 bugfix — actual для unified flow)
- [[one-menu-ux]] — last_bot_message_id tracking (НЕ обработан для pickers — см. Known gap там)
- [[user-profile-personalization]] — sync_user_profile, display_name — sibling pattern для унификации
- [[profile-redesign-v5]] — Agent Dossier UI, conditional Back (Premium plans subscription_source hack — убирается через nav_stack + unified pickers)

## Метрики успеха (после unification)

- **Добавление нового edit-поля:** с 8 touch points до 2 (INSERT + перевод)
- **Silent UI bugs:** с "два места рендера" до нуля (одно место)
- **Node count в 04_Menu:** ~117 → ~85 после Phase 4 рефакторинга (см. Agent 2 roadmap)
- **Единый place для подсказок/✅/hints** (сейчас надо править в 2-3 местах)
