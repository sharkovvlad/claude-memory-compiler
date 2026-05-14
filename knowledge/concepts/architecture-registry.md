# Architecture Registry — Python authoritative vs n8n fallback

**Status:** актуально на 2026-05-04. **Source of truth для агентов:** какой target обслуживает Python authoritative, какой fallthrough'ит на legacy n8n.

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

**Контракт обоих handler'ов идентичен:** `(update + UserCtx + RouteDecision) → dispatch_with_render RPC → ResponseEnvelope`. Python владеет парсингом запроса и маршалингом ответа; SQL (`process_user_input` + `render_screen` через `dispatch_with_render`) владеет бизнес-логикой, FSM, отрисовкой.

---

## 2. n8n fallback — Python пересылает на legacy

Если target не входит в Python authoritative — Python вызывает `forward_to_n8n()` (legacy `01_Dispatcher` на `http://127.0.0.1:5678/webhook/...`). Внутри n8n стандартный sub-workflow путь.

| Target | n8n workflow | Почему ещё не Python | Где решается в Python |
|---|---|---|---|
| `add_food` / `ai` | `03_AI_Engine` (`kjw4kkKMD0IqNALg`) | GPT-4o Vision pipeline — большой код в JS, не переписан | router.py: фото/голос/текст без edit-статуса |
| `location` | `02.1_Location` (`7EqiiwUwlGs7dcHT`) | Country/timezone picker workflow завязан на `$('Telegram Trigger')` runtime ссылки | router.py: status=`location_setup`, `loc_*` callbacks |
| `payment` | `10_Payment` (`T9753zO3ZyiYsgkp`) | Stripe / Stars / TON inline payments | router.py: `cmd_pay_*`, `cmd_premium_plans`, pre_checkout, successful_payment |
| `pre_checkout` / `successful_payment` | inline в `01_Dispatcher` | Telegram Payments callback shape — обрабатывается inline в Dispatcher Code node | router.py:316-326 (short-circuit до общего пайплайна) |
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
| `7EqiiwUwlGs7dcHT` | **02.1_Location** | 01_Dispatcher → "Go to 05_Location" | 🟢 KEEP — country/timezone picker |
| `T9753zO3ZyiYsgkp` | **10_Payment** | 04_Menu + 04_Menu_v3 → "Go to 10_Payment" | 🟢 KEEP — Stripe/Stars/TON |
| `jQn0nTxThFal4Kpe` | **06_Indicator_Clear** | 03_AI_Engine → 3 ноды (Success/Error/Edit) | 🟢 KEEP — clear typing indicator после фото |

### Active = 0 (7 workflows, inactive)

| ID | Name | Замещён | Решение |
|---|---|---|---|
| `wzjYmMOurCbp4czk` | **02_Onboarding_v3** | Python `handle_onboarding` (Phase 4, 02.05) | 🟡 ARCHIVE — деактивирован 04.05 (Агент 1). 01_Dispatcher всё ещё имеет executeWorkflow ссылку на него (если флаг `handler_onboarding_use_python` переключат → executeWorkflow inactive sub-workflow всё равно сработает, см. CLAUDE.md правило 12). Удалить через 1-2 недели стабильности. |
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
                                        │                          → Go to 10_Payment
                                        ├─ Go to 04_Menu_v3 → Go to 10_Payment
                                        ├─ Go to 05_Location → 02.1_Location
                                        └─ 02_Onboarding → 02_Onboarding_v3 (INACTIVE — branch фактически не достигается т.к. handler_onboarding_use_python=true)
```

### Что значит «inactive sub-workflow всё равно работает»

Per CLAUDE.md правило 12: `executeWorkflow` обращается к sub-workflow напрямую через ID. `active=true` нужен только для **триггер-нод** (Telegram Trigger, Webhook). Поэтому:
- 02_Onboarding_v3 (inactive) можно вызвать через executeWorkflow если 01_Dispatcher решит туда пойти.
- Это safety net для emergency rollback: переключить флаг `handler_onboarding_use_python=false` → трафик вернётся в n8n даже без re-activate.
- Удаление workflow из БД n8n лишает этой safety net. Поэтому ARCHIVE > DELETE для недавно деактивированных.

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
| `dispatcher_python_authoritative_admin_only` | `HANDLER_DISPATCHER_AUTHORITATIVE_ADMIN_ONLY` | `true` | Safety gate: authoritative фактически работает только для admin `417002669`, остальные — legacy |
| `handler_menu_v3_use_python` | `HANDLER_MENU_V3_USE_PYTHON` | `false` | Phase 2: Python владеет menu_v3 response (вместо n8n 04_Menu_v3) |
| `handler_onboarding_use_python` | `HANDLER_ONBOARDING_USE_PYTHON` | `false` | Phase 4: Python владеет онбордингом (вместо n8n 02_Onboarding_v3) |

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
