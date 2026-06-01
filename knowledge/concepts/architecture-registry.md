# Architecture Registry — Python authoritative vs n8n fallback

**Status:** актуально на 2026-05-21 (n8n cleanup — 02_Onboarding_v3, 02.1_Location, 10_Payment удалены из n8n SQLite + executeWorkflow refs зачищены в 01_Dispatcher / 04_Menu / 04_Menu_v3). **Source of truth для агентов:** какой target обслуживает Python authoritative, какой fallthrough'ит на legacy n8n.

> **Как обновлять:** при cutover'е каждого нового target (см. [variant-b-cutover](variant-b-cutover.md)) — добавить строку в таблицу 1, удалить из таблицы 2, обновить раздел «Флаги фич».
>
> **Источники, которые надо смотреть live при сомнении:**
> - `dispatcher/forward.py` → `TARGET_TO_PATH` dict (что Python пересылает напрямую на n8n webhook target'a)
> - `dispatcher/router.py` → `route_update()` (как target определяется по callback/text/status)
> - `webhook_server.py:_route_or_forward + _try_authoritative_path` (точка решения)
> - `app_constants` SELECT по ключам `dispatcher_python_*` и `handler_*_use_python` (live значения флагов)

---

## 1. Python authoritative — Python владеет responsem

| Target | Handler файл | Что обслуживает | Включено флагом |
|---|---|---|---|
| `menu_v3` | [handlers/menu_v3.py](../../../handlers/menu_v3.py) | Profile v5 (`cmd_get_profile`, `cmd_my_plan`, `cmd_settings`, …), pickers (`cmd_select_*`, `cmd_speed_*`, `cmd_lang_*`), Shop (`cmd_buy_freeze`, `cmd_buy_mana`, `cmd_confirm_buy_*`), Payout (`cmd_start_payout`, `cmd_payout_*`), reply-keyboard синтез (`icon_profile`, `icon_myday`, `icon_progress`), free-text input в edit-статусах (`edit_weight`, `edit_age`, `edit_height`, …) | `app_constants.handler_menu_v3_use_python` (мигр. 155) / env `HANDLER_MENU_V3_USE_PYTHON` |
| `onboarding` | [handlers/onboarding_v3.py](../../../handlers/onboarding_v3.py) | Регистрация (status=`new` / `registration_step_1..5` / `restoring:choose`), `/start`, `/start ref_NNN`, language picker, numeric input validation, photo/voice в онбординге | `app_constants.handler_onboarding_use_python` (мигр. 161) / env `HANDLER_ONBOARDING_USE_PYTHON` |
| `location` | [handlers/location.py](../../../handlers/location.py) | Country/timezone picker (`loc_country_*`, `loc_tz_*`), geo-pin (`message.location` → reverse geocoding), Phase 6.3 closeout | `app_constants.handler_location_use_python` / env `HANDLER_LOCATION_USE_PYTHON` (2026-05-14) |
| `payment` | [handlers/payment.py](../../../handlers/payment.py) | `cmd_premium_plans`, `cmd_pay_*` (плейн + методы Stars/Card/Crypto), Stripe Checkout open, Stars invoice, regional pricing. `pre_checkout` / `successful_payment` — безусловно в Python (без флага). | `app_constants.handler_payment_use_python` (мигр. 275) — flipped к `true` 2026-05-19 ~17:00 |

**Контракт обоих handler'ов идентичен:** `(update + UserCtx + RouteDecision) → dispatch_with_render RPC → ResponseEnvelope`. Python владеет парсингом запроса и маршалингом ответа; SQL (`process_user_input` + `render_screen` через `dispatch_with_render`) владеет бизнес-логикой, FSM, отрисовкой.

---

## 2. n8n fallback — Python пересылает на legacy

Если target не входит в Python authoritative — Python вызывает `forward_to_n8n()` (legacy `01_Dispatcher` на `http://127.0.0.1:5678/webhook/...`). Внутри n8n стандартный sub-workflow путь.

| Target | n8n workflow | Почему ещё не Python | Где решается в Python |
|---|---|---|---|
| `add_food` / `ai` | `03_AI_Engine` (`kjw4kkKMD0IqNALg`) | GPT-4o Vision pipeline — большой код в JS, не переписан (Stage 7 в roadmap) | router.py: фото/голос/текст без edit-статуса |
| ~~`location`~~ | ~~`02.1_Location` (`7EqiiwUwlGs7dcHT`)~~ | **MIGRATED 2026-05-14 → Python `handlers/location.py`.** Workflow active=0, не вызывается в проде. Cleanup в Phase 6.4 (DELETE workflow + Route Classifier patch). | — |
| ~~`payment`~~ | ~~`10_Payment` (`T9753zO3ZyiYsgkp`)~~ | **MIGRATED 2026-05-19 (Stage 6) → Python `handlers/payment.py`.** Workflow `active=0` через SQLite UPDATE. Stripe live setup на `https://nomsbot.com/webhooks/stripe`. Cleanup (DELETE workflow + executeWorkflow refs) — TODO. | — |
| ~~`pre_checkout` / `successful_payment`~~ | ~~inline в `01_Dispatcher`~~ | **MIGRATED 2026-05-19 в Python безусловно (нет флага)** — Telegram Payments lifecycle нельзя терять. См. handlers/payment.py + handover `2026-05-19_stage6_payment_python.md`. | — |
| `admin_payout` | `08.3_Friends`/payout chain | Regex match `admin_payout_(approve|reject)_*` — handled в n8n payout_handler. `_try_authoritative_path` возвращает False для этого target, fallthrough на n8n. | router.py:388-391 |
| `error` / unknown | legacy 01_Dispatcher | sentinel — что-то непонятное, пусть n8n решает | router.py: default branch |

**Структурное ограничение** (см. [variant-b-cutover](variant-b-cutover.md)): legacy sub-workflows (`04_Menu`, `02.1_Location`, `03_AI_Engine`) НЕЛЬЗЯ просто перевести на Webhook entry — внутри они используют `$('Telegram Trigger').item.json.X` runtime-ссылки. Variant B расширяется только когда конкретный sub-workflow переписан в Python (как сделали для menu_v3 и onboarding_v3).

---

## 2.1. Live audit n8n workflows (2026-05-04)

**Source of truth:** `sqlite3 /home/noms/n8n/data/database.sqlite "SELECT id, active, name FROM workflow_entity"`. Не из NLM — он путается в показаниях.

### Active = 1 (8 workflows, реально работают)

| ID | Name | Кто вызывает | Статус |
|---|---|---|---|
| `7jVRdAvVlzOqIMEi` | **01_Dispatcher** | Webhook from Python (legacy fallback) | 🟢 KEEP |
| `kjw4kkKMD0IqNALg` | **03_AI_Engine** | 01_Dispatcher → "Go to 03_AI" | 🟢 KEEP — GPT-4o Vision pipeline, не переписан |
| `0xJXA5M4wQUSiGXT` | **04_Menu_v3** | 01_Dispatcher → "Go to 04_Menu_v3" + Python forward (`menu_v3` target в TARGET_TO_PATH) | 🟢 KEEP — headless dispatcher |
| `JQsipPWxijse3F0b` | **04_Menu** (legacy) | 01_Dispatcher → "Go to 04_Menu" | 🟡 KEEP — обслуживает Edit Meal flow → 04.2_Edit_StatsDaily |
| `wgY05rXde1PbszSk` | **04.2_Edit_StatsDaily** | 04_Menu → "Go to 04.2" | 🟡 KEEP — depends on 04_Menu |
| ~~`7EqiiwUwlGs7dcHT`~~ | ~~**02.1_Location**~~ | — | 🔴 **DELETED 2026-05-21**. Был мигрирован в Python `handlers/location.py` (Phase 6.3, 14.05), executeWorkflow ref в `01_Dispatcher` (node `Go to 05_Location`) и `04_Menu` (node `Go to 05`) удалены. Snapshot: `n8n_workflows/02.1_Location.json`. |
| ~~`T9753zO3ZyiYsgkp`~~ | ~~**10_Payment**~~ | — | 🔴 **DELETED 2026-05-21**. Был мигрирован в Python `handlers/payment.py` (Stage 6, 19.05), executeWorkflow refs в `04_Menu` (node `Go to 10_Payment`) и `04_Menu_v3` (node `Go to 10_Payment`) удалены. Snapshot: `n8n_workflows/10_Payment_final_pre_delete.json`. |
| `jQn0nTxThFal4Kpe` | **06_Indicator_Clear** | 03_AI_Engine → 3 ноды (Success/Error/Edit) | 🟢 KEEP — clear typing indicator после фото |

### Active = 0 (7 workflows, inactive)

| ID | Name | Замещён | Решение |
|---|---|---|---|
| ~~`wzjYmMOurCbp4czk`~~ | ~~**02_Onboarding_v3**~~ | Python `handle_onboarding` (Phase 4, 02.05) | 🔴 **DELETED 2026-05-21**. executeWorkflow ref в `01_Dispatcher` (node `02_Onboarding`) удалён. Safety net «emergency rollback через переключение флага» больше не работает для onboarding — переключение `handler_onboarding_use_python=false` теперь приведёт к ошибке (subworkflow not found). Snapshot: `n8n_workflows/02_Onboarding_v3.json`. |
| `JRaKFPb5sOFL3xlc` | **02_Onboarding** (v1) | мёртвый код, никто не вызывал даже до Phase 4 | 🔴 DELETE безопасно |
| `DlWx3ZYnT3xT0tv5` | **06_Indicator_Send** | Python proxy (`webhook_server.maybe_send_indicator`) | 🔴 DELETE безопасно |
| `uUvHjmfdfrT0Mxsn` | **08.1_Quests** | Headless `quests` экран в 04_Menu_v3 (мигр. 129-139, Phase 3B) | 🔴 DELETE безопасно |
| `bPQSUEDW2tfsSXR1` | **08.2_League** | Headless `league` экран в 04_Menu_v3 (мигр. 129-139, Phase 3B) | 🔴 DELETE безопасно |
| `su5JZbUXOgE614Lo` | **08.3_Friends** | Headless `friends_info` экран в 04_Menu_v3 (мигр. 129-139, Phase 3B) | 🔴 DELETE безопасно* |
| `yhpXMufXs1guvZY5` | **08.4_Shop** | Headless `shop` экран в 04_Menu_v3 (мигр. 129-139, Phase 3B) | 🔴 DELETE безопасно |

> ⚠️ ***DELETE 08.3_Friends caveat:** ambassador payout flow (`admin_payout_approve_*` / `admin_payout_reject_*`) — проверить, не остались ли callbacks в 08.3 которые нужны для admin notifications. Если payout_handler находится в другом месте — DELETE безопасно. Иначе → ARCHIVE.

### Граф вызовов

```
Telegram → Python webhook proxy
    ↓ menu_v3 target → forward.send → 04_Menu_v3 (Phase 2)
    ↓ остальное → forward_to_n8n → 01_Dispatcher
                                        ├─ Go to 03_AI → 03_AI_Engine → Indicator_Clear ×3
                                        ├─ Go to 04_Menu (legacy) → Go to 04.2_Edit_StatsDaily
                                        └─ Go to 04_Menu_v3 (headless)
   (2026-05-21: ветки 02_Onboarding / Go to 05_Location / Go to 10_Payment удалены — все три sub-workflows DELETE'нуты, refs зачищены.)
```

### Что значит «inactive sub-workflow всё равно работает»

Per CLAUDE.md правило 12: `executeWorkflow` обращается к sub-workflow напрямую через ID. `active=true` нужен только для **триггер-нод** (Telegram Trigger, Webhook). Поэтому:
- Inactive sub-workflow можно вызвать через executeWorkflow если caller решит туда пойти.
- Это safety net для emergency rollback: переключить флаг `*_use_python=false` → трафик вернётся в n8n даже без re-activate.
- Удаление workflow из БД n8n лишает этой safety net. Поэтому ARCHIVE > DELETE для недавно деактивированных (правило хорошее, но 21.05 для onboarding/location/payment safety net сознательно снят — Python handlers стабильны >1 нед каждый).

---

## 3. Точка входа: webhook → роутинг

```
POST /telegram/webhook  (webhook_server.py:578)
    ↓ ack 200 за <10ms
    ↓ background tasks (fire-and-forget):
    ├─ maybe_send_indicator(update)        — typing/sticker
    ├─ maybe_sync_user_profile(update)     — refresh профиля
    ├─ shadow_route(update)                — Phase 1, observation only
    └─ _route_or_forward(update, body, hdr, t0):     ← главное решение
         ↓
         _try_authoritative_path()         ← Phase B-3 (когда флаг ON)
              ├─ если target=menu_v3 + handler_menu_v3_use_python → handle_menu_v3()
              ├─ если target=onboarding + handler_onboarding_use_python → handle_onboarding()
              ├─ если target в TARGET_TO_PATH → forward на per-target n8n webhook
              └─ иначе return False → fallthrough
         ↓ (если authoritative вернул False или флаги off)
         Phase 2 menu_v3 path: если флаг handler_menu_v3_use_python → handle_menu_v3()
         ↓
         Phase 4 onboarding path: если флаг handler_onboarding_use_python → handle_onboarding()
         ↓
         forward_to_n8n() — legacy 01_Dispatcher (default fallback)
```

**Любое исключение в Python ветке** → catch в `webhook_server.py:_route_or_forward` → forward_to_n8n. Юзер ничего не замечает (fail-safe by design).

---

## 4. Флаги фич (Variant B Cutover)

DB-backed через `app_constants`, читаются `services/app_flags.py:get_flags()` с TTL 60с. Env override для emergency. **Live values — всегда SELECT'ом, не из памяти:**

```sql
SELECT key, value FROM app_constants WHERE key LIKE 'dispatcher_python_%' OR key LIKE 'handler_%_use_python';
```

| Ключ в `app_constants` | Env override | Default | Назначение |
|---|---|---|---|
| `dispatcher_python_shadow_mode` | `HANDLER_DISPATCHER_USE_PYTHON` | `false` | Phase 1: observation. Логирует match/mismatch, ничего не шлёт юзеру |
| `dispatcher_python_authoritative` | `HANDLER_DISPATCHER_AUTHORITATIVE` | `false` | Phase B-3: Python authoritative SoT, шлёт в per-target n8n webhook (или Python handler) |
| `dispatcher_python_authoritative_admin_only` | ~~`HANDLER_DISPATCHER_AUTHORITATIVE_ADMIN_ONLY`~~ | **REMOVED** (PR #60, 13.05) | ~~Safety gate~~. Канарейка снята 2026-05-13: DB-ключ остаётся, Python-код удалён (`app_flags.py` + `webhook_server.py` gate). Все юзеры через Python authoritative. DB-cleanup отложен до Phase 6.4. |
| `handler_menu_v3_use_python` | `HANDLER_MENU_V3_USE_PYTHON` | `false` | Phase 2: Python владеет menu_v3 response (вместо n8n 04_Menu_v3) |
| `handler_onboarding_use_python` | `HANDLER_ONBOARDING_USE_PYTHON` | `false` | Phase 4: Python владеет онбордингом (вместо n8n 02_Onboarding_v3) |
| `handler_location_use_python` | `HANDLER_LOCATION_USE_PYTHON` | `true` | Phase 6.3 (2026-05-14): Python владеет country/timezone picker (вместо n8n 02.1_Location) |
| `handler_payment_use_python` | `HANDLER_PAYMENT_USE_PYTHON` | `true` | Stage 6 (2026-05-19): Python владеет payment flow (вместо n8n 10_Payment). `pre_checkout` / `successful_payment` всегда в Python (без флага). |

Hot-reload: после загрузки UserCtx читается из `ctx.constants` dictionary; если ключ отсутствует — fallback на env. Не требует рестарта `noms-webhooks`.

---

## 5. Cron jobs (отдельный путь, не через Dispatcher)

Не входят в registry потому что не маршрутизируются через webhook. Все 12 крон-jobs — Python в `crons/*.py`, запускаются APScheduler в процессе `noms-cron`. Логика в RPC, Python — тонкая обёртка. См. [CLAUDE.md](../../../CLAUDE.md) → секция "Cron Jobs (Python)" для расписания и target RPC.

> **Важно для агентов (мигр. 166, 04.05):** все cron RPC обязаны фильтровать `users.deleted_at IS NULL` иначе шлют спам soft-deleted юзерам. На 04.05 покрыто 10/10 функций (`cron_get_reminder_candidates` фильтрует с мигр. 044, остальные 9 — мигр. 166).

---

## 6. TODO / inconsistencies

- `TARGET_TO_PATH` (`dispatcher/forward.py:77-80`) сейчас содержит только `menu_v3`. По мере переписывания каждого sub-workflow в Python — добавлять.
- onboarding гейтится дважды (в `_try_authoritative_path` и в Phase 4 path) — backward compat. После полного перехода на authoritative (когда `dispatcher_python_authoritative=true` для всех юзеров) — Phase 4 path можно удалить.
- `pre_checkout` / `successful_payment` обрабатываются inline в n8n 01_Dispatcher (не отдельный sub-workflow). При переписывании `payment` target в Python — учесть, что эти два callback-типа имеют свою логику.
- **04_Menu (legacy) пока нельзя выключить** — он обслуживает Edit Meal flow (через 04.2_Edit_StatsDaily) и старые routing'и Payment. Phase 5 cutover (Edit Meal в Python) разблокирует деактивацию обеих 04_Menu + 04.2.
- **Smoke-тест mutating RPC через `EXPLAIN` не выявляет runtime-ошибки** (lesson после мигр. 167, исправивший ambiguity в `cron_check_streak_breaks` — мой adversarial review мигр. 166 пропустил баг т.к. EXPLAIN не parse'ит column references на ambiguity). Использовать `SELECT public.<fn>(...)` для actual call даже при ожидаемых 0-row results.
- **Phase 6.4 (AI Engine migration) — обязательство по `save_bot_message` контракту:** при переписывании `02.1_AI_Engine` на Python агент Phase 6.4 ОБЯЗАН обеспечить вызов `save_bot_message(tid, final_mid, 'menu')` после финального user-visible sendMessage. Иначе orphaned bubble в чате после каждого food log — Tech debt #7 lesson 14.05. Полная спека — [[concepts/save-bot-message-contract]].

---

## 7. Cross-references

- [variant-b-cutover](variant-b-cutover.md) — pattern и why
- [phase2-python-menu-v3](phase2-python-menu-v3.md) — как переписали menu_v3
- [phase4-onboarding-migration](phase4-onboarding-migration.md) — как переписали onboarding
- [headless-architecture](headless-architecture.md) — `process_user_input` + `render_screen` контракт
- [python-vs-n8n-template-grammar](python-vs-n8n-template-grammar.md) — почему `{x}` vs `{{x}}` сосуществуют
- [payment-idempotency-pattern](payment-idempotency-pattern.md) — Stripe webhook dedup + Stars UQ + pre-checkout guard (mig 290, 2026-05-20)

---

## Состояние на 2026-05-20 (payment post-first-live audit)

После PR #134 (Stripe идёмпотентность + Stars referral parity, mig 290):

- **Новая таблица `stripe_webhook_events`** — Stripe webhook event-level dedup. Insert first, side-effects after. PK `event_id`.
- **`payment_events.telegram_payment_charge_id` теперь UNIQUE** (partial index `WHERE NOT NULL`) — Stars charge dedup.
- **Pre-checkout active-premium guard** — `webhook_server.py:pre_checkout_query` отбивает Telegram запрос `answer_pre_checkout_query(ok=False)` если `users.subscription_status='active'` и `expires_at > now()`. Защита от double-charge.
- **Stripe live keys в `/home/taskbot/noms/.env`** (Stripe Review «in progress», но платежи принимаются).
- **Stars success path → referral reward parity** — `process_referral_reward` теперь вызывается в обоих paths (Stripe + Stars).
- **Open tech debt (post-2026-06-01 audit):**
  - ~~P1: dunning UX~~ ✅ mig 402 + 420 (PR #276); ~~`/start payment_success` deep-link~~ ✅ mig 313 HTML-stub; ~~trial_7d auto-convert~~ ✅ REPLACED Soft Downgrade'ом (PR #273); ~~localised dates crypto~~ ✅ mig 423 (PR #282); ~~Stars success i18n~~ ✅ mig 290/306/307.
  - **P2 (отложено):** upgrade/downgrade Stripe proration, EU VAT automatic, receipt emails, refund mechanism — большие отдельные sprints.
  - ~~P3: one-menu pattern по payment screens, n8n 10_Payment cleanup~~ ✅ DONE 2026-05-21 + audit 2026-06-01 (envelope architecture, 10_Payment workflow удалён, Route Classifier zero executeWorkflow refs).
  - **Promo flow (отложено):** entry UI отключён, redesign воронки нужен. Owner: «требует ривизии как должно работать, что подтягивать из БД».
- ~~**Open issue (конец 20.05):** «Кнопка «Продлить подписку» не работает»~~ ✅ **Closed mig 219+225:** `cmd_renew_plan` whitelist в `dispatcher/router.py:353`.

Pattern detail — [[payment-idempotency-pattern]].

---

## Состояние на 2026-05-31 (AI Engine cutover — registered + onboarding на Python)

Таблицы выше (datestamp 21.05) показывали `ai / add_food → 03_AI_Engine` целиком в n8n. С тех пор AI Engine мигрирован в Python в два этапа:

- **Registered AI — Python с 2026-05-29 (Stage 7 GLOBAL).** `handle_ai_input` (handlers/food_log.py) обслуживает food (текст/фото/голос) для `status in (registered, editing_meal)` → `log_meal_transaction` + food-карточка. Гейт в `webhook_server.py:_try_authoritative_path`. Полная история — [[stage7-global-cutover]]. До этого admin-canary с 21.05 (mig 299→373).
- **Onboarding/unregistered food — Python с 2026-05-31 (PR #254, mig 404/405).** `handle_onboarding_food` (handlers/food_log.py) для `status='new'` / `registration_step_*` → `log_meal_onboarding` (mig 404 — изолированная RPC: food_logs + check_and_deduct_mana, **БЕЗ XP/streak/league** — соцкапитал только после регистрации) → nudge (`messages.onboarding_food_nudge`, mig 405 ×13) + `_rerender_current_screen`. Закрывает Strangler-Fig scope-сужение из [[no-mana-python-precheck]] (раньше unregistered-ветка сознательно оставалась в n8n `Send No Mana CTA`).
  - **Gotcha (проверено):** свой thinking-стикер в хендлере безопасен — `sticker.send_thinking` пишет в `indicator_message_id` (не `last_bot_message_id`), плюс proxy-индикатор для `registration_step_*` заглушён (telegram_proxy, UAT batch2 31.05) → mig 238 fire-and-forget race не применим.
- **n8n `03_AI_Engine` (`kjw4kkKMD0IqNALg`)** теперь только legacy fallback (Python exception → forward). Реальный трафик еды (registered + onboarding) идёт в Python. Cleanup (deactivate + Indicator_Clear) — Stage 7c, после стабильности.

**Итог:** `ai`/`add_food` target — **Python authoritative для всех статусов** (registered + onboarding). Таблицу 1 строку `ai` следует считать Python; таблица 2 строка `add_food / ai → 03_AI_Engine` — только аварийный fallthrough.
