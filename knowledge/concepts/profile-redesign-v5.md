---
title: "Profile Redesign v5.0 — Agent Dossier"
aliases: [profile-v5, agent-dossier, profile-redesign-v5, build-profile-text-v5, my-plan-screen, settings-screen]
tags: [n8n, ui, profile, migrations, onboarding]
sources:
  - "daily/2026-04-16.md"
  - "daily/2026-04-17.md"
created: 2026-04-16
updated: 2026-04-17
---

# Profile Redesign v5.0 — Agent Dossier

Полный редизайн экрана Профиля (миграции 068–070): новый "Agent Dossier" layout с 4 новыми под-экранами (Мой план, Личные метрики, Настройки, Помощь), условный рендеринг для Free/Premium, back-навигация из Location workflow в Settings.

## Key Points

- **Migration 068:** 28 `profile.*` + 9 `buttons.*` translation keys × 13 языков; 01_Dispatcher +7 полей (итого 43): display_name, first_name, username, created_at, target_protein_g, target_fat_g, target_carbs_g
- **Build Profile Text v5.0:** "Agent Dossier" layout — убраны Gamification/Localization/System блоки; добавлены: member_since, статус подписки, лимит логов, биометрия, цель, Sassy Sage фраза (3 варианта для free, 3 для premium)
- **4 новых под-экрана:** My Plan (цель+скорость+макросплит+Sage insight), Personal Metrics (вес+рост+возраст+пол), Settings (язык+страна+таймзона), Help (ссылка @AutoRiot из `profile.support_url`)
- **05_Location conditional Back:** кнопка "Назад" → `cmd_settings` показывается ТОЛЬКО в editing flow (`status startsWith 'editing:'`); для онбординга отсутствует
- **10_Payment Back conditional:** `subscription_source='profile'` → Back возвращает в `cmd_get_profile`; иначе → `cmd_back_to_progress`

## Details

### Migration 068 — translation keys

**28 `profile.*` ключей × 13 языков:**
- `profile.title_agent` — "Досье Агента" (заголовок экрана)
- `profile.member_since` — "Агент с: {date}"
- `profile.status_free/premium/trial` — статус подписки
- `profile.limit_logs` — "Лимит: {count} логов/день"
- `profile.bio_and_goal` — раздел биометрии и цели
- `profile.sage_free_1/2/3` — 3 Sage-фразы для free пользователей
- `profile.sage_premium_1/2/3` — 3 Sage-фразы для premium
- `profile.speed_label/deficit/surplus` — отображение скорости похудения/набора
- `profile.phenotype_standard/monw/athlete/obese` — метки телосложения
- `profile.my_plan_title/insight`, `profile.settings_title`, `profile.personal_metrics_title` — заголовки под-экранов

**9 `buttons.*` ключей × 13 языков:**
- `buttons.update_weight`, `buttons.help`, `buttons.my_plan`, `buttons.settings`
- `buttons.personal_metrics`, `buttons.manage_subscription`, `buttons.go_pro_unlimited`
- `buttons.notifications`, `buttons.delete_account`

### 01_Dispatcher Prepare for 04 — 43 поля

+7 новых полей добавлены к 36 существующим (было 36 → стало 43):
- `display_name` — `COALESCE(first_name, username, 'User')` из v_user_context
- `first_name`, `username` — для персонализации
- `created_at` — дата регистрации (для "Агент с: {date}")
- `target_protein_g`, `target_fat_g`, `target_carbs_g` — для экрана Мой план

### Build Profile Text v5.0 — Agent Dossier layout

**Старый layout (v4.1):** ID → Gamification (XP/уровень/стрик/монеты/мана) → Localization (язык/таймзона) → System (статус/уровень/дата) → Мой план (training/speed) + Keyboard

**Новый layout v5.0:**
```
🕵️ Досье Агента
{display_name} | Агент с: {member_since}

━━━━━━━━━━━━━━━━━━━━
📋 СТАТУС: 🆓 Бесплатный | лимит 2 лога/день

📐 Биометрия: {weight}кг / {height}см / {age}л / {gender}
🎯 Цель: Похудеть (медленно)

💬 "{Sassy Sage фраза}" (рандомная из 1/2/3)
━━━━━━━━━━━━━━━━━━━━
```

**Keyboard (условный):**
- Ряд 1: [⭐ Стать PRO] (free) / [💳 Управление подпиской] → `cmd_profile_subscription` (premium)
- Ряд 2: [⚖️ Обновить вес] + [🎯 Мой план]
- Ряд 3: [📊 Личные метрики] + [⚙️ Настройки] + [🆘 Помощь]

### 4 новых под-экрана

**My Plan (`cmd_my_plan` → route `my_plan`):**
- Цель + скорость (% дефицита/профицита из app_constants)
- Активность + тип тренировок + телосложение
- Персональный макросплит: target_protein_g / target_fat_g / target_carbs_g (г/день)
- Sassy Sage insight (`profile.insight` translation key)

**Personal Metrics (`cmd_personal_metrics` → route `personal_metrics`):**
- Вес, рост, возраст, пол из v_user_context
- Кнопка [⚖️ Обновить вес] → `cmd_update_weight` → маппинг на `edit_weight` в Parse Edit Command

**Settings (`cmd_settings` → route `settings`):**
- Язык → кнопка `cmd_edit_language`
- Страна → кнопка `cmd_edit_country`
- Таймзона → кнопка `cmd_edit_timezone`
- Coming-soon stubs: `cmd_notifications`, `cmd_delete_account`

**Help (`cmd_help` → route `help`):**
- Текст кнопки из `profile.support_button` (migration 069)
- URL из `profile.support_url` = `https://t.me/AutoRiot` (для всех языков)

### Bug Fix Session 2 (Migration 069)

**Migration 069 — Support button:**
- `profile.support_button` × 13 языков ("💬 Связаться с поддержкой")
- `profile.support_url` = `https://t.me/AutoRiot` — URL берётся из перевода, не хардкодится в n8n

**cmd_profile_subscription routing:**
- Build Profile Text v5.0: Premium кнопка → `cmd_profile_subscription` (было `cmd_premium_plans`)
- Command Classifier: `cmd_profile_subscription` → route `payment` с флагом `subscription_source='profile'`
- 10_Payment Back button: `subscription_source === 'profile'` → `cmd_get_profile`, иначе → `cmd_back_to_progress`

**02_Onboarding Response Builder fix:**
- Speed picker после goal→speed step теперь показывает ✅ на текущей `goal_speed`
- Merge Data в 02_Onboarding обновлён: добавлены `goal_speed`, `goal_type`, `training_type`, `phenotype` из v_user_context

### Bug Fix Session 3 (Migration 070)

**Migration 070 — Edit labels:**
- `edit.country` × 13 языков (Страна / Country / País / ...)
- `edit.timezone` × 13 языков (Часовой пояс / Timezone / ...)
- Нужны для Build Country UI / Build Timezone UI в 05_Location

**05_Location — conditional Back button:**

```javascript
// Build Country UI — добавляется ТОЛЬКО при editing:
if (status.startsWith('editing:')) {
  keyboard.push([{ text: translations['buttons.back'], callback_data: 'cmd_settings' }]);
}

// Build Timezone UI — callback условный:
const backCmd = status.startsWith('editing:') ? 'cmd_settings' : 'loc_back_to_list';
keyboard.push([{ text: translations['buttons.back'], callback_data: backCmd }]);
```

Dispatcher маршрутизирует `cmd_settings` → 04_Menu → Settings screen. Для онбординга кнопки нет — там некуда возвращаться.

**04_Menu Go to 10_Payment fix:**
- workflowInputs расширены: добавлены `subscription_source` + `last_bot_message_id` (было только 8 полей)
- Без этого флаг `subscription_source='profile'` не долетал до 10_Payment → Back всегда вёл в Progress

### Bug Fix Round 2 (23:50, 2026-04-16) — после живого тестирования

Живые тесты выявили 5 багов, не найденных ранее.

**Bug 5 (subscription_source не долетал до 10_Payment):**
`10_Payment Merge Data` не включал `subscription_source` и `last_bot_message_id` в return объект. Добавлены оба поля — теперь `Build Plans Text` читает `d.subscription_source === 'profile'` корректно и Back ведёт в Профиль.

**Bug 7 (страна на нативном языке):**
`Build Profile Sub-Screen` использовал хардкод-мапу `countryNames` — "España" показывалась русскоязычному пользователю. Заменено на `Intl.DisplayNames`:

```javascript
const countryName = new Intl.DisplayNames([language_code], {type: 'region'}).of(country_code);
// ru + 'ES' → "Испания"; en + 'ES' → "Spain"; fr + 'ES' → "Espagne"
```

Работает в n8n Cloud (Node.js с Full ICU). Убирает необходимость в 13×50 translation keys для стран.

**Bug 3 (Back без иконки в 05_Location):**
`Build Country UI` добавлял Back-кнопку без иконки. Исправлено: `(ui.constants.icon_back || '🔙') + ' ' + btn_back`.

**Bug 1 (✅ не на текущей скорости в picker'е):**
`goal_speed` не доходил до `02_Onboarding` — `Prepare for 02` в Dispatcher имел `include: none` с только 9 явными полями, и `goal_speed` в них не входил. Добавлены 9 полей в `Prepare for 02`:
`goal_speed`, `goal_type`, `training_type`, `phenotype`, `target_weight_kg`, `callback_message_id`, `callback_query_id`, `subscription_status`, `last_bot_message_id`.

**Bug 4 (05_Location отправлял новое сообщение вместо edit):**
`05_Location` не имел ветки `editMessageText` для inline-кнопок. Добавлены 2 новых ноды:
- `Has Callback MsgId?` (IF: `callback_message_id` notEmpty)
- `Telegram: Edit UI` (HTTP POST `editMessageText`)

Все 6 `Build*UI` нод (Country, Timezone, More TZ, UTC, UTC Group, All Countries) передают `message_id: ui.callback_message_id || ''`. Паттерн: IF callback_message_id → Edit / else → Send. `05_Location` вырос до **44 нод** (было 42).

**executeWorkflow typeVersion pattern:**
- `typeVersion 1` (legacy) = **passthrough**: весь `$json` предшественника передаётся в child workflow без фильтрации
- `typeVersion 1.3+` = **explicit mapping**: только поля из `workflowInputs.value` попадают в child
- `Go to 05_Location` имел пустой `value: {}` (typeVersion 1.3) → 05_Location получал ничего. Исправлено: добавлен явный mapping 9 полей включая `callback_message_id`.

**Паттерн для будущих рефакторингов:**
- При `typeVersion 1.3+` + пустой `value: {}` — child workflow "глохнет" (не получает данных)
- `Intl.DisplayNames` применимо везде где нужны локализованные имена стран/языков без дополнительных DB-таблиц
- One-Menu IF паттерн (callback_message_id → edit/send) применим к 04.2, 08.1, 08.2, 08.3, 08.4

### Bug 2 Fix — Language Back → Settings (2026-04-17)

**Проблема:** После Round 2, при переходе Профиль → Настройки → Язык → 🔙 Назад пользователь видел "Готово! Язык обновлён" вместо возврата в Settings.

**Root cause:** `gffHvoRJI2018qle` (v1, inactive) вызывается из `04_Menu → Go to Language` только для показа picker (reply keyboard). Все последующие действия (выбор флага, нажатие Back) идут через Dispatcher → Route Classifier → route_target='onboarding' → `Ksv1DhWKUIDtlhLy` (v3, active). В v3 `Onboarding Engine`, секция `status='changing_language'`, при `isBack` устанавливалось `action='language_save'` + `is_back=true`. Action Router v3 не различал `language_save` vs `language_save+is_back` — всегда запускал Save Language DB → After-Lang Builder → "Готово!".

**Fix — один Code node в v3 (Onboarding Engine):**

`isBack` branch изменён с `action='language_save'` на `action='status_and_send'`. Action Router ветка [4] `status_and_send` → `Update User Status → Send Telegram` — ноды уже существовали, новых нод не добавлялось. Payload для Send Telegram = полный Settings screen (inline keyboard идентичен `04_Menu Build Profile Sub-Screen settings case`).

**Также:** `v3 Merge Data` расширена на 3 поля: `country_code`, `timezone`, `last_bot_message_id` — без них Build Settings в Engine не мог отрендерить "Страна / Часовой пояс".

**Важный debt:** Settings screen payload дублирован внутри Onboarding Engine и в `04_Menu Build Profile Sub-Screen (settings case)`. При смене Settings UI нужно обновлять **оба места**. TODO при refactor 04_Menu: вынести в shared sub-workflow `Build Settings Screen`.

### Bug 2 Round 2 — Settings показывал "Страна: —, Часовой пояс: UTC" (2026-04-17)

**Выявлено через E2E:** Back → Settings screen отображался, но поля страны и таймзоны были пустыми ("—" / "UTC").

**Root cause:** `Dispatcher → Prepare for 02` (typeVersion 3.2, `fields.values`) не включал `country_code` и `timezone`. Итого было 18 полей → добавлены 2 → стало 20. `Merge Data` в v3 читала `input.country_code` → undefined → fallback `''` → Build Settings показывал "—".

**Fix:** добавлены 2 поля в `Prepare for 02 → fields.values`:
```js
{ name: 'country_code', type: 'stringValue', stringValue: "={{ $json.country_code || '' }}" }
{ name: 'timezone',     type: 'stringValue', stringValue: "={{ $json.timezone || 'UTC' }}" }
```

### Profile UX Polish Session (2026-04-17)

Три косметических/UX фикса после подтверждения Round 2.

**Fix A — ✅ на edit pickers (goal/training/activity/gender):**

`chk*()` helpers добавлены в **двух местах**: `02_Onboarding → Response Builder` (для inline пикеров) и `04_Menu → Build Ask Markup` (для reply keyboard edit cases). `isEdit = engine.is_edit === true || status.startsWith('editing:') || status.startsWith('edit_')`. При онбординге (`isEdit=false`) — ✅ не появляется. Полный паттерн см. [[concepts/edit-picker-dual-render]].

**Fix B — Settings keyboard 2-в-ряд:**
```
[Язык][Страна]
[Часовой пояс][Уведомления]
[❌ Удалить аккаунт]
[🔙 Назад]
```
Деструктивные действия (Удалить) вынесены на отдельную строку.

**Fix C — Timezone display формат:**

Было: `"Europe/Madrid (GMT+2)"`. Стало: `"Madrid, GMT+2"`.

```js
const tzCity = md.timezone.split('/').pop().replace(/_/g, ' ');
const offsetStr = new Intl.DateTimeFormat('en-US', {
  timeZone: md.timezone, timeZoneName: 'shortOffset'
}).formatToParts(new Date()).find(p => p.type === 'timeZoneName')?.value || '';
tzDisplay = tzCity + (offsetStr ? (', ' + offsetStr) : '');
```

Ограничение: город остаётся на латинице (ICU не локализует city names). Решение в будущем: словарь `TZ_CITY_NAMES × 13 langs` или таблица `timezones_i18n` в БД.

### Phase 4: Language save → Settings (2026-04-17)

UX change: после выбора нового языка бот возвращает в Settings screen (вместо "Готово! Язык обновлён" + main menu). Best practice iOS/Android.

**02_Onboarding_v3 After-Lang Builder:**
- Branch `returnStatus === 'registered'`: Settings payload с `langName` через `Intl.DisplayNames([newLang])`, `countryName` через `Intl.DisplayNames([newLang], {type: 'region'})`. Confirmation header `"✅ Language updated: Español"` из `freshT.messages.language_changed`. При `is_back === true` header не показывается.

**Stale Language keyboard fix:** reply keyboard Language picker'а не убирается при inline Settings (Telegram API: inline + remove_keyboard нельзя в одном сообщении). Fix: After-Lang Builder отправляет **2 payloads**: 1) dismiss msg с `remove_keyboard: true` + confirmation text, 2) Settings screen с inline keyboard.

### D5: Unified save confirmations (2026-04-17)

Все edit save confirmations в 02_Onboarding_v3 (Activity/Training/Goal/Speed) унифицированы:
- `mainMenuKB()` (reply keyboard) → `backInlineKB()` (inline `cmd_back`)
- Одно сообщение с выбранным значением + inline Back вместо двух ("Вопрос: ответ ✓" + "Сохранено!")
- Speed picker: `_push_nav_screen = 'edit_speed'` для корректного nav_stack

Полная архитектура nav_stack: [[concepts/nav-stack-architecture]].

### Deferred (оставшееся)

- **Bug 6 закрыт ✅** — 8 фаз реализованы (см. [[concepts/nav-stack-architecture]])
- **edit_phenotype dead-end закрыт ✅** — Phase 2 nav_stack добавила Back handling
- **Refactor 04_Menu:** 54 HTTP Request нод → 8-12 (typing action консолидация через IF-ноду); Settings screen дублирование
- **One-Menu IF паттерн** применить к 04.2/08.1/08.2/08.3/08.4 (inline кнопки без edit/send ветвления)
- **D1 (жирное имя `<b>`):** требует HTML parse_mode audit всех Profile Send/Edit нод
- **D3 (echo-сообщение "Question: Answer ✓"):** источник не идентифицирован

## Related Concepts

- [[concepts/personalized-macro-split]] — My Plan под-экран отображает calculate_user_targets результаты (training_type, goal_speed, macro split)
- [[concepts/n8n-stateful-ui]] — editMessageText, HTML parse_mode, conditional keyboards
- [[concepts/dispatcher-callback-pipeline]] — Prepare for 04 теперь 43 поля; subscription_source передача
- [[concepts/payment-integration]] — subscription_source hack убран через nav_stack (Phase 5)
- [[concepts/nav-stack-architecture]] — Bug 6 hierarchical back navigation; Phase 4 Language + D5 unified confirmations
- [[concepts/user-profile-personalization]] — display_name, first_name, created_at — персонализация Agent Dossier
- [[concepts/supabase-db-patterns]] — migrations 068–070
- [[concepts/edit-picker-dual-render]] — dual render pattern для edit pickers; chk*() helpers; Fix A
- [[concepts/n8n-subworkflow-contract]] — Prepare for 02 теперь 20 полей (Bug 2 Round 2); status_and_send для Bug 2 Back fix

## Sources

- [[daily/2026-04-16.md]] — Profile Redesign v5.0: Agent Dossier layout, 4 новых под-экрана, 37 translation keys × 13 langs, 01_Dispatcher 43 поля; Bug Fix Sessions 2-3 (migrations 069–070); Bug Fix Round 2 (Intl.DisplayNames, Prepare for 02 +9 полей, 05_Location edit/send branching 44 нод, subscription_source Merge Data fix, executeWorkflow typeVersion pattern)
- [[daily/2026-04-17.md]] — Bug 2 fix (Language Back → Settings via status_and_send в v3 Onboarding Engine); Bug 2 Round 2 (Prepare for 02 +country_code/timezone = 20 полей); Polish fixes A/B/C (✅ edit pickers, Settings 2-в-ряд, Timezone display с Intl.DateTimeFormat); Phase 4 Language→Settings + stale keyboard 2-msg fix; D5 unified save confirmations + backInlineKB; Bug 6 + edit_phenotype dead-end закрыты
