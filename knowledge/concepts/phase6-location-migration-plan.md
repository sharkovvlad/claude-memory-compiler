---
title: "Phase 6 — миграция 02.1_Location в Python (план)"
aliases: [location-migration, phase6-location, phase6-plan]
tags: [phase6, migration-plan, n8n-cutover, location, headless]
status: PLAN (awaits product sign-off)
created: 2026-05-12
related:
  - phase4-onboarding-migration
  - variant-b-cutover
  - architecture-registry
  - n8n-route-classifier-edit-loc-patch
  - start-fresh-gaps-2026-05-11
  - ui-stickers-headless
  - one-menu-ux
  - n8n-subworkflow-contract
---

# Phase 6 — миграция 02.1_Location → Python

> **Финальный legacy n8n блок Onboarding-pipeline'а.** Phase 4 закрыла онбординг до phenotype quiz (status `new` → `registration_step_phenotype_quiz`); 02.1_Location обслуживает «последнюю милю» — country/timezone picker + первичный location pin + Profile v5 edit-flow для уже зарегистрированных. Phase 6 переводит его в Python authoritative path аналогично `handlers/onboarding_v3.py`.

## Что вынудило открыть план (12.05.2026)

Live UAT (юзер 786301802) после mig 192/203/204: пользователь видит «✅ Сохранено + 👌» вместо `onboarding_success` стикера и поздравительного сообщения после location pin.

**Корневая причина:** IF-нода «Onboarding Just Completed» в 02.1_Location проверяет `$('Init & Templates').first().json.return_status === 'registration_step_1'`. Init & Templates исходит из легаси-`return_status` map (унаследовано от старой схемы где `status='registration_step_1'` = «в процессе онбординга»). Phase 4 (mig 161) ввёл новые статусы `onboarding:country` / `onboarding:timezone`; mig 179 пометила их в gate'е `dispatch_with_render`, но Init & Templates'у никто не сказал, что для них надо отдавать «onboarding» return_status вместо «registered». Каждая ветка save_* → set_user_location уже переключает status в `'registered'` ДО finalize → finalize_onboarding_location видит status='registered' + xp=0, выдаёт XP/coins/level-up (mig 204), а на UI это не транслируется т.к. IF-нода сравнивает по другому полю.

**Workaround в полёте (Опция A — 12.05):** PUT 02.1_Location, IF-condition меняется на `$('Postgres: Finalize Onboarding').first().json.success === true`. Это buy time на ~1-2 недели. Phase 6 — окончательное решение.

**Глубже:** 02.1_Location это последний из «больших» legacy workflow'ов, который завязан на `$('Init & Templates').first().json.X` runtime-ссылки (см. variant-b-cutover.md «структурное ограничение»). Его нельзя просто перевести на webhook entry — нужно переписать downstream-логику. Раз надо переписывать — пишем на Python.

---

## 1. Полная инвентаризация 02.1_Location

> **Source of truth:** live n8n self-hosted (workflow id `7EqiiwUwlGs7dcHT`). Снапшот сделан 12.05.2026 через `curl http://127.0.0.1:5678/api/v1/workflows/7EqiiwUwlGs7dcHT`.
> **Размер:** 55 нод, 12 Code, 13 Postgres, 8 HTTP Request, 2 Webhook/Trigger, остальные — IF/Set/Sticky.

### 1.1 Граф потока (упрощённый)

```
Entry:
  Executed 05 (executeWorkflowTrigger)   ───┐
  Webhook B-1 Cutover (location)            ├──→  Adopt Cutover Payload  ──→  Init & Templates
                                            │                                  ↓
                                            │                          Action Classifier
                                            │                                  ↓
                                            │                            Router (Switch, 10 routes)
                                            │                                  ↓
   ┌─────────────────────┬───────────────────┬───────────────────┬─────────────┴───────────────┬──────────────┐
   ↓ ask_country         ↓ handle_country    ↓ handle_timezone   ↓ search_mode               ↓ show_*       ↓ cancel
   RPC:Get Countries     RPC:Get Details     Save: Timezone      Has Location? ─────────┐  RPC:Get *      Restore Main KB
   ↓                     ↓                   ↓                   ├─ Yes: Search Geo     │  ↓
   Build Country UI      Parse Country       Postgres:           ├─ No: Ask Location    │  Build * UI
   ↓                     ↓                    Finalize Onboarding   Permission           │  ↓
   Has Callback MsgId?   Smart Skip? ─┐                          ↓                       │  Has Callback MsgId?
   ↓ + Push Nav         ├─ Yes: Save:                            Send Reply Keyboard     │  ↓
   ↓                    │   Single Zone                                                  │  ↓
   Telegram: Edit UI    │   ↓                                                            │  ↓
   or Send UI           │   Postgres:                                                    │  …
                        │   Finalize Onboarding ──→ IF Onboarding Just Completed ─┐      │
                        │                                                         │      │
                        │                          ┌─ true: Render success →     │      │
                        │                          │   Send success → Render menu→
                        │                          │   Send success_menu          │      │
                        │                          └─ false: Notify TZ Saved ────┘      │
                        │                                       ↓                       │
                        │                                Restore Main KB                │
                        │                                                               │
                        └─ No: Save: Country Only ──→ Build Timezone UI ────────────────┘
```

### 1.2 Inventory нод по функциональным группам

#### A. Точки входа (2)
| Нода | Тип | Назначение |
|---|---|---|
| `Executed 05` | executeWorkflowTrigger | Legacy путь из 01_Dispatcher (`Go to 05_Location`). |
| `Webhook B-1 Cutover (location)` + `Adopt Cutover Payload (location)` | webhook + code | Variant B путь (не используется — `location` не в `TARGET_TO_PATH`). Adopt валидирует `X-NOMS-DISPATCHER-SECRET`, re-emit body. |

#### B. Парсер payload + классификатор (3)
| Нода | Тип | Назначение |
|---|---|---|
| `Init & Templates` | code (JS, ~120 LOC) | Парсит callback_data (`loc_country:CC`, `loc_tz:TZ:CC`, `loc_tz_more:CC`, `loc_tz_utc[:CC]`, `loc_utc_group:GID:CC`, `loc_utc_page:N`, `loc_utc_select:TZ`, `loc_other`, `loc_other_page:N`, `loc_no_country`, `loc_detect_geo`, `loc_back_to_list`, `loc_back_to_tz`). Определяет `action`, `data`, `extra`. Раскрывает text-templates `{{var}}`. Считывает `messageText` против `${icon_back} ${buttons.back}` → action='cancel_location'. Считывает `message.location.latitude` → action='search_mode'. **Возвращает в `$json` все user-context поля + 5 derived (action/data/extra/return_status/payload_*).** |
| `Action Classifier` | code (~50 LOC) | Mapping action → route (10 routes). Спецкейс: `(status ∈ {edit_timezone, editing:timezone}) AND countryCode AND action='start_location'` → route='handle_country'. |
| `Router` | switch (10 outputs) | По route: `ask_country` / `handle_country` / `handle_timezone` / `search_mode` / `show_more_tz` / `show_utc_list` / `handle_utc_select` / `show_utc_group` / `show_all_countries` / `cancel_location`. |

#### C. SQL вызовы (13 Postgres-нод)
| Нода | RPC / SELECT | Что делает |
|---|---|---|
| `RPC: Get Countries` | `set_user_location(uid, NULL, NULL, status-dependent_return_status)` + `get_location_setup(lang)` | (i) Помечает статус (editing/onboarding) (ii) возвращает suggested-список стран. |
| `RPC: Get Details` | `get_location_setup(lang, country_code, timezone_hint)` | Если timezone_hint совпал — auto_set=true; иначе либо single zone (auto_set=true), либо options[] для picker. |
| `RPC: Get More TZ` | `get_location_setup(lang, country_code)` | Тот же RPC, для следующей страницы (slice +6 в JS). |
| `RPC: Get UTC Zones` | `SELECT zone_name, utc_offset, label FROM ref_timezones WHERE country_code='ZZ' ORDER BY ...` | Сырые UTC зоны для группового просмотра. |
| `RPC: Get UTC Group Zones` | `SELECT ... FROM ref_timezones WHERE country_code='ZZ' AND utc_offset IN (group_set)` | Зоны конкретной группы. |
| `RPC: Get All Countries` | `SELECT code, flag_emoji, name FROM ref_countries WHERE code!='ZZ' AND is_active=true` | Полный список 43 стран (для пагинации 14/стр). |
| `Save: Single Zone` | `set_user_location(uid, CC, TZ, return_status)` | Auto-set после Geoapify / single zone. |
| `Save: Country Only` | `set_user_location(uid, CC, NULL, return_status_for_tz_step)` | Сохранить только страну (есть выбор TZ). |
| `Save: Timezone` | `set_user_location(uid, CC, TZ, return_status)` | Пользователь выбрал TZ из списка. |
| `Save: UTC Zone` | `set_user_location(uid, NULL, TZ, return_status)` | UTC zone без страны. |
| `Postgres: Finalize Onboarding` | `finalize_onboarding_location(uid)` | mig 179/203/204 — guard «xp>0 OR nomscoins>0», иначе complete_onboarding. |
| `Postgres: Render onboarding_success` | `render_screen(uid, 'onboarding_success')` | Headless render success-экрана со стикером (Channel A, mig 198/201). |
| `Postgres: Render onboarding_success_menu` | `render_screen(uid, 'onboarding_success_menu')` | Followup-экран с reply-kb (mig 159/160 «attach_main_kb_unconditional»). |

#### D. JS-Build UI (6 Code-нод)
Все строят inline-keyboard в формате `{chat_id, text, reply_markup, message_id}`. Резолвят иконки из `ui.constants.icon_*` и тексты из `ui.translations.buttons.*` / `ui.translations.onboarding.*`. Поддерживают пагинацию (страны, More TZ) и status-aware Back-кнопку (edit_* → cmd_back; иначе loc_back_to_list).

| Нода | Назначение |
|---|---|
| `Build Country UI` | Suggested 4-6 стран + «Определить» + «Другая страна». |
| `Build Timezone UI` | 6 TZ страны + «Другой пояс» + «Ещё» (если >6) + «Авто» + «Назад». |
| `Build More TZ UI` | TZ после 6-й + «Другой пояс» + «Авто» + «Назад к первой стр.». |
| `Build UTC UI` | 4 UTC-группы (minus_12_6 / minus_5_0 / plus_1_6 / plus_7_14) + «Авто» + «Назад». |
| `Build UTC Group Zones` | Конкретные TZ группы + «Авто» + «Назад к группам». |
| `Build All Countries UI` | Пагинация 14/стр + «Моей страны нет» + «Авто» + (опц. «Ещё») + «Назад». |
| `Ask Location Permission` | reply-keyboard `request_location: true` + Back-кнопка. |
| `Parse Country Details` | Слепляет результат `get_location_setup`, добавляет `geo_detected` флаг. |
| `Parse Geo Response` | Извлекает `country_code`/`timezone` из Geoapify ответа. |

#### E. HTTP Request / Telegram (8)
| Нода | Эндпоинт | Назначение |
|---|---|---|
| `Search Geo` | `https://api.geoapify.com/v1/geocode/reverse` | Геокодинг lat/lon → country_code + timezone. |
| `Push Nav (Country)` / `Push Nav (Timezone)` | `…/rpc/push_nav` | Вызов `push_nav` RPC через REST (мог бы быть Postgres-нодой). |
| `Telegram: Send UI` | sendMessage | Новое сообщение (когда callback_message_id отсутствует). |
| `Telegram: Edit UI` | editMessageText | Обновление существующего (One Menu UX). |
| `Telegram: Notify Auto` | sendMessage | Поздравительное «✅ {country_name} {flag}» после auto_set. |
| `Telegram: Notify TZ Saved` | sendMessage | Profile v5 edit-flow: «✅ Сохранено». |
| `Telegram: Send onboarding_success` | sendMessage | После Finalize Onboarding для нового юзера: текст success + sticker от render_screen. |
| `Telegram: Send onboarding_success_menu` | sendMessage | Followup с reply-keyboard «Главное меню». |
| `Telegram: Restore Main KB` | sendMessage | 👌-carrier + reply_markup main_kb (при cancel_location и при Notify TZ Saved). |

#### F. Управляющие / utility (5)
| Нода | Назначение |
|---|---|
| `Has Callback MsgId?` | IF-нода: callback_message_id truthy → Edit UI; иначе Send UI. |
| `Smart Skip?` | IF: `auto_set===true` → Save: Single Zone (skip TZ picker); иначе Save: Country Only + Build Timezone UI. |
| `Has Location?` | IF: message.location.latitude truthy → Search Geo; иначе Ask Location Permission. |
| `If` / `If Auto Continue` | Контроль legacy «02_Continue Onboarding» route (мёртвый код, executeWorkflow на деактивированный workflow). |
| `IF: Onboarding Just Completed` | **СЛОМАННАЯ нода (12.05).** Сейчас сверяется с `return_status==='registration_step_1'`. Опция A workaround: меняем на `finalize.success === true`. |

### 1.3 Карта callback_data ↔ route

| callback_data | action | route | side-effect |
|---|---|---|---|
| `loc_country:CC` | loc_country | handle_country | `set_user_location(CC,NULL,...)` → если TZ единственный — sng zone + finalize; иначе → Build Timezone UI. |
| `loc_tz:TZ:CC` | loc_tz | handle_timezone | `set_user_location(CC,TZ,return_status)` → finalize. |
| `loc_tz_more:CC` | loc_tz_more | show_more_tz | пагинация. |
| `loc_tz_utc[:CC]` | loc_tz_utc | show_utc_list | UTC-группы. |
| `loc_utc_group:GID:CC` | loc_utc_group | show_utc_group | зоны группы. |
| `loc_utc_select:TZ` | loc_utc_select | handle_utc_select (≡ Save UTC Zone) | `set_user_location(NULL,TZ,...)` → finalize. |
| `loc_utc_page:N` | loc_utc_page | (часть show_utc_*) | переключение страницы. |
| `loc_other[+ _page:N]` | loc_other / loc_other_page | show_all_countries | пагинация. |
| `loc_no_country` | loc_no_country | show_utc_list | пользователь не нашёл свою. |
| `loc_detect_geo` | loc_detect_geo | (через Init & Templates стартовый action `start_location`) → ask_country | По сути «начать сначала», но через geo-button. Реальный поток геолокации — message.location pin. |
| `loc_back_to_list` | loc_back_to_list | ask_country | Назад к suggestions. |
| `loc_back_to_tz` | loc_back_to_tz | handle_country | Назад к таймзонам страны. |
| `cmd_back` (reply-text) | cancel_location | cancel_location | Patch v4. 👌 + Restore Main KB. |
| (геолокация в message) | search_mode | search_mode | Geoapify → handle_country. |

### 1.4 3 контекста использования (A / B / C)

| Контекст | Trigger | Стартовый статус | Конечный статус | Финальный экран |
|---|---|---|---|---|
| **A. Онбординг location** | После phenotype quiz: `process_onboarding_input` ставит `status='onboarding:country'` + возвращает forward marker `target='location'`. Юзер видит `edit_country` (mig 192). Клик «Авто (геолокация)» → router 4f → 02.1_Location | `onboarding:country` → `onboarding:timezone` (если страна saved, TZ не определён) | `registered` (через `complete_onboarding` в `finalize_onboarding_location`) | `onboarding_success` (со стикером, Channel A) + `onboarding_success_menu` (reply-kb) |
| **B. Profile v5 edit-flow** | Settings → «Страна» → `cmd_edit_country` → menu_v3 ставит `status='edit_country'` через `process_user_input` meta-dispatch + рендерит `edit_country` экран. Клик «Авто» → router 4f → 02.1_Location | `edit_country` / `edit_timezone` (≡ `editing:country` / `editing:timezone` для старых юзеров) | `registered` (через `set_user_location(..., return_status='registered')`) | Notify TZ Saved (sendMessage) + Restore Main KB |
| **C. Geolocation pin** | Юзер в любом контексте присылает location pin (lat/lon) | произвольный → парсится через router section 1 (`has_location` → target=location) | то же что A или B, в зависимости от `status` | то же что A или B |

`return_status` (поле в `Init & Templates`) сейчас:
```javascript
// эта логика в Init & Templates JS:
const onboardingStatuses = ['onboarding:country', 'onboarding:timezone'];
const editStatuses       = ['edit_country', 'edit_timezone', 'editing:country', 'editing:timezone'];
if (onboardingStatuses.includes(status)) return_status = 'registered';   // финальный статус после complete
else if (editStatuses.includes(status))   return_status = 'registered';   // тоже, но без grants
else                                       return_status = 'registered';  // catch-all
```
**Это то место, где IF «Onboarding Just Completed» ломается:** код в Init & Templates ставит return_status='registered' для онбординг-контекста, а IF проверяет `=== 'registration_step_1'` (legacy semantics предыдущей версии).

### 1.5 Live дефекты / hacks в текущем workflow

1. **IF «Onboarding Just Completed» сломан** для Phase 4 онбординга → нет success-стикера + поздравительного сообщения. Workaround Опция A в полёте.
2. **`return_status` всегда == 'registered'** — Init & Templates исторически разделял onboarding/edit, теперь оба ведут в 'registered' (set_user_location делает direct UPDATE). Нелогично, но не сломано — finalize guard mig 204 разделяет по xp/nomscoins.
3. **Mig 192 dirty-hop:** `process_onboarding_input` для `status='onboarding:country'`/`onboarding:timezone'` рендерит `edit_country`/`edit_timezone` экраны напрямую (без forward marker). Юзер видит экран, кликает «Авто» → попадает в 02.1_Location через router 4f.
4. **Geoapify hardcoded** в HTTP Request node (api key через env переменную инстанса). Никакого fallback.
5. **`02_Continue Onboarding` executeWorkflow** на деактивированный sub-workflow (02_Onboarding_v3, inactive с 04.05) — мёртвый код, не вызывается на текущем routing'е.
6. **JSON build_*_UI ноды дублируют логику** (4 разных JS Code для UTC / countries / timezone / more) — суммарно ~400 LOC только в build-UI.
7. **`Push Nav (Country)` / `Push Nav (Timezone)` через REST** — HTTP Request к `…/rpc/push_nav` вместо Postgres node. Avoidable RTT (~30-44ms).
8. **Hardcoded labels в `Build UTC UI`** (русские «🌙 UTC -12:00 ... -06:00» — не локализуются).
9. **Patch v9** в 01_Dispatcher Route Classifier (`LOC_EDIT_STATUSES` early branch) — workaround для reply-back в edit_country/timezone, **подлежит удалению после Phase 6**.
10. **Prepare for 05 в 01_Dispatcher** — отдельный Set-блок, проксирующий 9 полей в 02.1_Location. После Phase 6 → удалить.

---

## 2. SWOT текущей реализации

**Strengths:**
- Headless паттерн уже частично сделан (RPC `set_user_location`, `finalize_onboarding_location`, `get_location_setup` — вся бизнес-логика в SQL).
- 6 RPC покрывают 100% бизнес-логики; n8n — только Telegram-транспорт.
- Geoapify-интеграция работает стабильно.

**Weaknesses:**
- **Контракт-drift:** IF-нода смотрит на `return_status==='registration_step_1'` (legacy semantics), которое умерло в Phase 4.
- 4 build-UI Code-ноды (~400 LOC JS) дублируют рендеринг кнопок, который у нас уже есть в `services/template_engine.py`.
- 13 Postgres-нод, многие — простые SELECT через REST (lat вместо TCP).
- Init & Templates Code-нода — 120 LOC текстовой парсинг callback_data (`loc_country:`, `loc_tz:`, …) — анти-паттерн против `process_user_input` который читает headless meta.
- Сейчас headless экраны `edit_country` / `edit_timezone` (mig 192) и legacy JS-build UI (`Build Country UI`, `Build Timezone UI`) **сосуществуют** для одних и тех же экранов. Build UI делает то же что мог бы render_screen → cleanup.
- `Build UTC UI` хардкодит «🌙», «🌅», «☀️», «🌆» вне `app_constants` — нарушение no-hardcode rule.
- Sticker `onboarding_success` (Channel A) рендерится через **второй вызов** `render_screen` после finalize → лишний RTT.

**Opportunities:**
- Полный перенос location-flow в headless архитектуру: `edit_country`, `edit_timezone`, `all_countries_page_N`, `utc_groups`, `utc_zones_<group>` → ui_screens + render_screen + template_engine.
- Удалить 02.1_Location + Prepare for 05 + Route Classifier patch v9. **−1 entire n8n workflow + 1 set node + 1 JS branch.**
- Объединить два RPC-вызова finalize + render_screen в один через `dispatch_with_render`-стиль bundle (1 RTT вместо 2-3).
- Использовать Channel A sticker (уже mig 198/201) автоматически из render_envelope.
- Перевести UTC-группы из hardcoded в `app_constants` (icons) + `ui_translations` (labels).

**Threats:**
- 02.1_Location обслуживает **3 разных контекста** (A/B/C) с разной логикой завершения — миграция должна сохранить все три без регрессий.
- `set_user_location` сейчас вызывается с 4 разными комбинациями (CC only / TZ only / CC+TZ / status-only) — Python должен делать аналогично.
- Контракт IF-ноды `Onboarding Just Completed` уже сломан **сейчас** — миграция должна явно проверять `finalize.success===true` (не return_status).
- Geoapify api_key хранится в n8n env. При переносе → надо в `.env` на VPS добавить + в `app_constants` ничего не класть (он не для секретов).
- E2E тестирование локационных flows тяжелее чем онбординга — нельзя в pytest легко эмулировать `message.location.latitude` с правдоподобными координатами.

---

## 3. Гранулярность миграции — варианты

### Option 1 — Big-bang (один PR, одна неделя)

Один PR, одна миграция (`migrations/20X_phase6_location_headless.sql`), один новый `handlers/location.py`, один merge.

**Плюсы:**
- Минимум координации с параллельными агентами.
- Сразу удаляются Prepare for 05 + Route Classifier patch v9.

**Минусы:**
- Большой surface — высокий риск skipped edge-case (любая из 13 переходов).
- Если что-то сломается на live — fallback на n8n требует `handler_location_use_python=false` + полный rollback миграции (Channel A sticker logic уже завязан на render_screen).
- Не лезет в pattern Phase 2/4 (там было постепенно: shadow → admin-only → 100%).

### Option 2 — Phased (3-4 PR, две недели) — **РЕКОМЕНДОВАНО**

**Phase 6.1 — Foundation + Onboarding context (A) только.**
- Новая миграция: `process_onboarding_input` для `status ∈ {onboarding:country, onboarding:timezone}` обрабатывает все loc_* callbacks + finalize + render onboarding_success. Через `complete_onboarding`-цепочку (которая уже работает).
- Новый Python handler `handlers/location.py` — обрабатывает onboarding-контекст (status в `{onboarding:country, onboarding:timezone}`).
- Router section 1 + 2 + 4f gated по status: онбординг → новый handler; edit → старый n8n путь (как сейчас).
- Feature flag `handler_location_use_python` (only для onboarding-context).

**Phase 6.2 — Profile v5 edit (B) context.** ✅ **CLOSED 2026-05-13 (PR #59).**

⚠️ **Architecture decision на финале планирования (2026-05-13):** Phase 6.2 НЕ требует SQL миграции (изначальный plan §3 handover'а предполагал mig 209 для расширения `process_user_input`).

**NLM-консультация выявила**, что `loc_country_<CC>` и `loc_tz_<TZ>` — **динамические** callbacks (генерируются Python-handler'ом на лету). Их физически нет в `ui_screen_buttons`, поэтому `process_user_input` (работающий через lookup в этой таблице) их не обрабатывает. Вся логика edit-flow — в Python-handler'е через `set_user_country` + `set_user_timezone` + `clear_editing_state` сетторы.

`cmd_back` на `edit_country`/`edit_timezone` — **статическая** кнопка с `meta = {clear_status: true, target_screen: 'settings'}` (per psycopg2 spot-check). Её SQL FSM обрабатывает через menu_v3 path — Python handler в это не лезет.

**Setters ≠ FSM** (тимлид 2026-05-13): для финала edit-flow использовать разделённые сеттеры + `clear_editing_state`, а не `set_user_location(..., 'registered')` (последний смешивает data + FSM transition — допустимо для онбординга, не для edit).

Реализовано в PR #59:
- `handlers/location.py` — расширение `_LOCATION_HANDLER_STATUSES`, branching в `_handle_country_selected`/`_finalize_with_timezone` по `is_edit`.
- `dispatcher/router.py` — удалён section 4e-pre (patch v9). Reply-text «🔙» в edit-status больше не маршрутизируется руками — после Phase 6.2 он в edit-context не возникает (handler не строит reply-kb).
- `tests/handlers/test_location.py` +6 кейсов / -2 устаревших guard.

Полная семантика разделения — KB [[concepts/headless-fsm-vs-dynamic-handler-separation]].

**Phase 6.3 — Geolocation pin + UTC groups headless.**
- Перенос Geoapify HTTP вызова в Python.
- Переносим UTC-groups, all-countries-pagination на ui_screens + ref_timezones SELECT через RPC.
- Удаляем 4 build-UI JS-ноды.

**Phase 6.4 — Cleanup.**
- Деактивируем 02.1_Location (active=false, не удаляем — safety net 7 дней).
- Удаляем Prepare for 05 из 01_Dispatcher.
- Удаляем `02_Continue Onboarding` мёртвый executeWorkflow.
- KB updates: architecture-registry, n8n-route-classifier-edit-loc-patch (закрыто).

**Плюсы:**
- Каждая фаза самостоятельно проверяется. Mismatch — fallback одной фазы без откатывания других.
- Параллельные агенты могут продолжать работать в чужих файлах.
- Знакомый паттерн (Phase 2 menu_v3 + Phase 4 onboarding делали так же).

**Минусы:**
- 3-4 деплоя вместо 1.
- Patch v9 удаляется только в 6.2 — две недели его держим.

**Выбор:** Option 2 (phased).

---

## 4. Финальный план

### 4.1 SQL миграции

**migration `20X_phase6_location_step_a_onboarding.sql` (Phase 6.1):**

```sql
-- Step 1. ui_screens для UTC-групп / all_countries page (headless).
-- Каждый экран → render_screen рендерит через template_engine.
-- 4 экрана для UTC groups: utc_group_minus_12_6, utc_group_minus_5_0, utc_group_plus_1_6, utc_group_plus_7_14.
-- 1 экран для UTC groups index: utc_groups.
-- 1 экран для all_countries: all_countries (с пагинацией через meta.pagination).
-- 1 экран для ask_location_permission (reply_keyboard, request_location=true).

-- Step 2. Расширение process_onboarding_input для status='onboarding:country'/'onboarding:timezone':
--   - cmd_auto_location → render(edit_country) с уже-имеющимся reply-kb pattern (mig 192).
--   - cmd_list_countries → render(all_countries) (page=0).
--   - loc_country:CC → set_user_location(CC, NULL, ...) + decide (single TZ → finalize, multi → render edit_timezone for that country).
--   - loc_tz:TZ:CC → set_user_location(CC, TZ, 'registered') + finalize_onboarding_location + render onboarding_success (Channel A автоматом).
--   - loc_other_page:N → render(all_countries) с meta.page=N.
--   - loc_no_country → render(utc_groups).
--   - loc_utc_group:GID:CC → render(utc_group_<GID>).
--   - loc_utc_select:TZ → set_user_location(NULL, TZ, 'registered') + finalize + render onboarding_success.
--   - loc_back_to_list → render(edit_country).
--   - loc_back_to_tz → render(edit_country) — назад к TZ страны через тот же путь что loc_country:CC.
--   - location pin (action_type='location') → Geoapify геокодинг идёт в Python (не в SQL).

-- Step 3. Новый RPC `get_country_list_paginated(p_lang, p_page, p_page_size)` — для all_countries экрана.
-- Step 4. Новый RPC `get_utc_groups()` — статичный список 4 групп, локализованных.
-- Step 5. Новый RPC `get_utc_group_zones(p_lang, p_group_id)` — зоны конкретной группы.
-- Step 6. feature flag: INSERT INTO app_constants (key, value, category) VALUES ('handler_location_use_python', 'false', 'dispatcher');
```

**migration `20Y_phase6_location_step_b_edit.sql` (Phase 6.2):**

```sql
-- Расширение process_user_input для:
--   - status='edit_country'/'editing:country' + loc_country:CC → set_user_location → finalize_or_skip
--   - status='edit_timezone' + loc_tz:TZ:CC → set_user_location + render success
-- Финал для B-context: `set_user_location(..., 'registered')` + render(settings) или render(profile_main).
-- НЕТ вызова finalize_onboarding_location (он отказывает по xp>0 guard'у).
```

**migration `20Z_phase6_location_step_c_geo.sql` (Phase 6.3):**

```sql
-- Возможные SQL-доработки:
--   - `get_location_setup` оптимизация для timezone_hint (single SELECT).
--   - `app_constants` UTC group icons: icon_utc_minus_12_6, icon_utc_plus_1_6, ...
--   - `ui_translations.utc_groups.label_minus_12_6` etc. — локализованные labels.
```

**migration `20W_phase6_decommission.sql` (Phase 6.4):**

```sql
-- Удаление dead `app_constants.dispatcher_python_authoritative_admin_only` если на 100% catchall.
-- Регистрация в app_constants: location_legacy_workflow_id = '7EqiiwUwlGs7dcHT' для аудита (опц).
```

### 4.2 Python артефакты

**Новые файлы:**

| Файл | LOC оценка | Назначение |
|---|---|---|
| `handlers/location.py` | ~400 | Единый handler для всех 3 контекстов (A/B/C). Структура зеркалит `onboarding_v3.py`: точка входа `handle_location(update, ctx, decision)` → ensure_user не нужен (location handler видит только registered/onboarding-аккаунты) → routing по action_type → dispatch_with_render. Спецветка: location pin → Geoapify reverse geocode → set_user_location + finalize/render. |
| `services/geocoding.py` | ~80 | Wrapper над Geoapify (или альтернативой). 1 функция: `async reverse(lat, lon) -> {country_code, timezone, city}`. С httpx pool, retry, timeout. **GEOAPIFY_API_KEY** в `.env`. |
| `tests/handlers/test_location.py` | ~600 | См. секцию 4.4 ниже. |

**Изменения в существующих файлах:**

| Файл | Изменения |
|---|---|
| `dispatcher/router.py` | (i) В section 1 (`has_location`) — после mig 6.1 location pin для онбординг-юзера идёт в Python handler. (ii) Section 2 (`callback.startswith('loc_')`) — same. (iii) Section 4f — same. (iv) **Удалить** `LOCATION_LEGACY_BUTTONS` после 6.4 (cmd_auto_location/cmd_list_countries/cmd_list_timezones автоматически попадут через section 4a). |
| `webhook_server.py` | Добавить branch в `_route_or_forward` + `_try_authoritative_path`: `target=='location'` + `handler_location_use_python` → handle_location. Аналог Phase 4 branch. |
| `dispatcher/forward.py` | `TARGET_TO_PATH` после 6.4 удалить ничего — он уже не содержит `location`. |

### 4.3 Архитектурный choice: один handler vs три

**Выбор:** **один handler `handlers/location.py`** для всех трёх контекстов (A/B/C).

**Обоснование:**

1. **Phase 4 прецедент.** `onboarding_v3.py` обрабатывает 13 разных статусов (`new`, `registration_step_1..5`, `registration_step_training/goal/speed/phenotype_quiz`, `onboarding:country/timezone`) одним handler'ом. Бизнес-логика в SQL FSM (`process_onboarding_input`). Python — тонкий transport. Тот же паттерн для location.
2. **3 контекста делят 80% callbacks** (loc_country/loc_tz/loc_utc_*/loc_other/loc_no_country). Если делить на 3 handler'а — 3-кратное дублирование маршрутизации.
3. **Status discriminator уже работает на стороне SQL.** `process_user_input` (Profile v5) + `process_onboarding_input` (Phase 4 онбординг). Status → ветка FSM. Никаких трёх Python-функций не надо.
4. **Тест-плоскость проще:** один handler с табличными тестами на все 3 контекста.

**Однако** SQL FSM для location следует разбить:
- Loc-callbacks **в** онбординге → `process_onboarding_input` (как сейчас mig 192).
- Loc-callbacks **в** edit-flow → `process_user_input` (Profile v5).
- Location pin (geo-message) → специальный пред-обработчик в Python (Geoapify → set_user_location → потом обычный path).

Это **симметрично существующему разделению** «process_onboarding_input vs process_user_input» — оно уже есть в DB.

### 4.4 Тесты

```python
# tests/handlers/test_location.py — ~25-30 кейсов

# A. Онбординг context (status=onboarding:country/timezone)
- test_loc_country_single_timezone_finalizes_onboarding
- test_loc_country_multi_timezones_renders_edit_timezone
- test_loc_tz_finalizes_onboarding_emits_sticker
- test_loc_other_renders_all_countries_page_0
- test_loc_other_page_renders_next_page
- test_loc_no_country_renders_utc_groups
- test_loc_utc_group_renders_zones
- test_loc_utc_select_finalizes_onboarding
- test_loc_back_to_list_renders_edit_country
- test_geo_pin_auto_finalizes_for_single_tz_country
- test_geo_pin_multi_tz_renders_edit_timezone
- test_geoapify_failure_falls_back_to_picker  # graceful

# B. Profile v5 edit (status=edit_country/edit_timezone)
- test_edit_country_loc_country_saves_and_renders_settings
- test_edit_timezone_loc_tz_saves_and_renders_settings
- test_edit_cmd_back_returns_to_settings
- test_edit_no_finalize_called  # guard mig 204 mocked

# C. Cross-cutting
- test_already_completed_blocked_by_guard
- test_anonymized_status_blocked
- test_legacy_workflow_status_falls_through  # flag off → forward to n8n

# D. Sticker (Channel A)
- test_onboarding_success_sticker_emitted_once  # stickers_shown updated
- test_onboarding_success_sticker_not_emitted_twice

# E. Integration — реальный dispatch_with_render
# tests/integration/test_location_dispatch.py (~10 кейсов с реальным DB через savepoint+rollback)
```

### 4.5 KB / docs

| Артефакт | Что сделать |
|---|---|
| `concepts/architecture-registry.md` | Перевести `location` из «n8n fallback» в «Python authoritative» (после 6.4). |
| `concepts/variant-b-cutover.md` | Если применяется паттерн — добавить Phase 6 в timeline. |
| `concepts/n8n-route-classifier-edit-loc-patch.md` | Mark as «removed in Phase 6.2». |
| `concepts/phase6-location-migration-plan.md` (этот файл) | Live document, обновлять по мере фаз. |
| **Новый** `concepts/phase6-location-migration.md` | После прохода — completion notes, lessons learned. |
| `MEMORY.md` | Cutover активного target. |

---

## 5. Risk assessment + rollback

| Риск | Вероятность | Impact | Mitigation | Rollback |
|---|---|---|---|---|
| Geoapify API down | low | high (location pin не работает) | Graceful fallback на picker (already в n8n). Timeout=3s + retry 1. | Юзер видит «не получилось определить, выбери вручную» — graceful UX. |
| Sticker `onboarding_success` не показывается | medium | high (UX регрессия) | Tests E2E через savepoint, проверяем что `stickers_shown` updates + send_sticker OutboundItem. | Mig 201 `stickers_shown - 'onboarding_success'` для конкретных юзеров. |
| `finalize_onboarding_location` guard mig 204 ломается | low | high | Тесты в test_location.py имитируют edit-flow (xp>0) и онбординг (xp=0). | Mig 204 уже applied + tested 12.05. Не трогаем. |
| Profile v5 edit-flow возвращает в settings вместо profile_main | medium | medium | Тестируем оба пути. По умолчанию — settings (как сейчас в `Telegram: Notify TZ Saved` → restore_main_kb). | Easy SQL patch на target_screen. |
| Параллельный агент трогает router.py / webhook_server.py | high | medium | См. CLAUDE.md §12: rebase перед commit, sanity diff, force-with-lease. Phase 6.1 не должен совпадать по времени с другими расширениями router. | Rebase + повторный merge. |
| Stale-base regression в `process_onboarding_input` / `process_user_input` | high | high | safe-create-or-replace recipe: `pg_get_functiondef` ЖИВОГО прода перед apply, не из git. | Re-apply мига с правильной базой. |
| flag `handler_location_use_python=true` рано → юзеры стопорятся | medium | high | Phase 6.1 = admin-only сначала (admin chat 417002669), потом whitelist, потом 100%. Параллельный мониторинг `journalctl -u noms-webhooks -f`. | `app_constants UPDATE … 'false'` — hot-reload TTL 60s. |
| n8n 01_Dispatcher Route Classifier удалили patch v9 рано (до 6.2) | medium | high | Patch v9 удаляется ТОЛЬКО в Phase 6.2 миграционным PR, не раньше. | n8n PUT обратно. |

**Rollback strategy в общем:** `app_constants UPDATE key='handler_location_use_python' SET value='false'` — мгновенный откат всех 3 контекстов в legacy n8n. 60s TTL. n8n 02.1_Location остаётся активным до Phase 6.4 (4-я фаза, не раньше +7 дней stable 100%).

---

## 6. Estimated effort

| Phase | SQL LOC | Python LOC | Tests LOC | Время (dev + review) |
|---|---|---|---|---|
| 6.1 — Onboarding context | ~400 | ~350 | ~400 | 2 дня |
| 6.2 — Edit context | ~150 | ~50 (расширение handler) | ~200 | 0.5 дня |
| 6.3 — Geo + UTC headless | ~250 | ~100 (geocoding.py + RPC calls) | ~200 | 1.5 дня |
| 6.4 — Cleanup | ~50 | удаления | — | 0.5 дня |
| **Итого** | **~850** | **~500** | **~800** | **~4.5 дня** + 1 день мониторинга |

Шкала ориентирована на Phase 4 (≈688 SQL + 477 Python LOC + 30 тестов; ~5 дней с 02.05 по 05.05 включая live-bugfix'ы).

---

## 7. Открытые вопросы для тимлида (требуют решения перед началом)

1. **Geoapify vs альтернатива.** Сейчас в n8n hardcoded `https://api.geoapify.com/v1/geocode/reverse`. Перенести as-is, или сразу заменить (timezonefinder + offline ref_countries lookup → no external API)? Offline = быстрее (<10ms vs 200-400ms), но точность ниже на границах временных зон.

2. **Profile v5 edit финальный экран.** Сейчас `Notify TZ Saved` шлёт «✅ Сохранено» (sendMessage) + reply-kb restore. **Альтернатива** — render(settings) через editMessageText (One Menu UX). Тимлидская предпочтительность?

3. **UTC groups локализация.** Сейчас в `Build UTC UI` хардкод emoji+text «🌙 UTC -12:00 ... -06:00». Должны быть в `app_constants` (icons) + `ui_translations` (labels) на 13 языков, или хардкод сохранить?

4. **`return_status` legacy field.** Init & Templates исторически выставляла `return_status`. В Python handler этого поля нет — set_user_location/finalize читают status напрямую. Подтверждение: можно полностью удалить?

5. **`02.1_Location` после Phase 6.4: ARCHIVE или DELETE?** Phase 4 архив: 02_Onboarding_v3 деактивирован, но не удалён (rollback safety). Аналогично — деактивировать через `active=false` 7 дней наблюдения, потом DELETE? Или сразу DELETE?

6. **Pagination page_size.** Сейчас all_countries — 14/стр, more_tz — slice +6. Унифицировать в `app_constants.location_page_size`?

7. **Test environment для location pin.** pytest сложно эмулировать `message.location.latitude`. Использовать ли Telethon-based live testing (как `tests/live/e2e_crawler.py`) для location flow, или достаточно unit-моков Geoapify?

---

## 8. Cross-references

- [variant-b-cutover](variant-b-cutover.md) — паттерн staged rollout
- [phase4-onboarding-migration](phase4-onboarding-migration.md) — прецедент с 33 gotcha'ами
- [architecture-registry](architecture-registry.md) — обновить после 6.4
- [n8n-route-classifier-edit-loc-patch](n8n-route-classifier-edit-loc-patch.md) — patch v9 (будет removed в 6.2)
- [start-fresh-gaps-2026-05-11](start-fresh-gaps-2026-05-11.md) — корневая mig 204 history, почему finalize guard сейчас на xp/nomscoins
- [ui-stickers-headless](ui-stickers-headless.md) — Channel A для `onboarding_success` стикера
- [one-menu-ux](one-menu-ux.md) — editMessageText контракт
- [safe-create-or-replace-recipe](safe-create-or-replace-recipe.md) — stale-base regression
- [release-protocol](release-protocol.md) — git discipline при параллельных агентах
