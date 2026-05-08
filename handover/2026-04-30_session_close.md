# NOMS Session Close — 2026-04-30 (Tech Lead handover)

**Author:** Tech Lead AI agent (Claude), session 29-30.04.
**Audience:** следующий AI-агент, который подхватит работу с этого места.
**Кросс-ссылки:**
- `daily/2026-04-29.md` — детали Migration 146→154 + n8n cleanup
- `daily/2026-04-30.md` — Phase 2 PM-агент: handlers/menu_v3.py, branch `claude/phase2-menu-v3`
- `tests/live/CALIBRATION_REPORT.md` — Telethon E2E findings F2/F3/F4/F5
- Plan: `/Users/vladislav/.claude/plans/users-vladislav-claude-plans-dynamic-ji-generic-wren.md`

---

## TL;DR — статус системы на 30.04 утро

**Production бот работает.** Все вчерашние фиксы live (миграции 146-154 + n8n правки + калибрация). Главный user-side баг S6 («Назад из глубокой иерархии уводит в Мой день») закрыт. 0% errors в n8n executions vs утренние 52% (баг ACQ).

**Phase 2 готова к деплою, но НЕ задеплоена.** PM-агент завершил `handlers/menu_v3.py` в ветке `claude/phase2-menu-v3`. 170/170 pytest тестов зелёных. Latency benchmark: dispatch_with_render p50=46ms vs текущие n8n end-to-end ~1800ms (ожидание -20-30× после flag flip). Feature flag `HANDLER_MENU_V3_USE_PYTHON` пока OFF.

**User имеет 2 открытых блока вопросов** (см. ниже секцию «User open questions»):
1. Сомнения по Phase 0.5+1 Dispatcher Python
2. Замечания к E2E тестам — «картина не полная, не все экраны и кнопки ведут себя ожидаемо»

User не дал точных деталей — следующий агент должен **первым делом запросить у user конкретику** через AskUserQuestion.

---

## Что сделано за сессию (chronological)

### 28.04 — start of session
- Phase 0.5+1 уже была задеплоена (commits ff5b543..bf437e2, см. daily/2026-04-28.md). Shadow flag OFF на проде.
- ACQ fix утром (chip subagent): `Has Callback ID?` + `Is Not Callback?` IF-guards в `04_Menu_v3` → ошибки «query is too old» упали с 52% до 0%.

### 29.04 — Headless cleanup marathon

**Migrations applied** (в хронологическом порядке):
| # | Файл | Что |
|---|---|---|
| 146 | `back_fallback_stats_main_root.sql` | Priority 3 fallback `profile_main` → `stats_main` |
| 147 | `back_i_came_from_navigation.sql` | I-came-from path-walk Back, truncate-on-existing в `push_nav`, advisory_xact_lock 147147147, input-source-aware fastpath через `p_cb_context.is_inline` |
| 148 | `per_callback_debounce.sql` | `last_action_signature` JSONB (3-arg `debounce_user_action`), 9/9 verifies |
| 149 | `dispatch_with_render_bundle.sql` | bundled RPC, p50=96ms vs 181ms раздельных |
| 150 | `debounce_idempotent_callbacks.sql` | helper `is_idempotent_action()`, cmd_back bypass debounce. **Verdict: KEEP** (verified A1) |
| 151 | `fastpath_wipe_then_push_root.sql` | Force push после fastpath wipe (закрыло часть S6) |
| 152 | `register_location_pickers.sql` | country_picker / timezone_picker в ui_screens с back_default=settings |
| 153 | `wipe_for_all_reply_kb_roots.sql` | identity-based wipe trigger (3 reply-kb roots) — **закрыло S6 полностью** |
| 154 | `fallback_root_screen_constant.sql` | `app_constants.fallback_root_screen='stats_main'`, helper `get_fallback_root_screen()`, L94 + Priority 3 patches |

**Сriticality:** все 9 миграций applied через psycopg2 + DATABASE_URL. Все verifies прошли. Идемпотентны (position guards + advisory_xact_lock).

**n8n changes (3 PUT'а в `04_Menu_v3` workflow `0xJXA5M4wQUSiGXT`):**
1. ACQ fix (28.04 утро): порядок connections перестроен, IF-guards добавлены.
2. is_inline patch в Extract Payload: `is_inline = !!(d._cb_data || d.callback_query?.data)`. Reply-kb teleport начал работать на проде.
3. Bundle switch: HTTP-нода вызова `/rpc/process_user_input` → `/rpc/dispatch_with_render`. n8n flow проще + 1 RTT save.

**n8n changes в `04_Menu` (legacy `JQsipPWxijse3F0b`):**
- 3 ноды `Reset Nav (Profile/Stats/Progress)` удалены (split-brain wipe устранён).
- Добавлены `Extract Menu ID (Add Food)` + `Save Menu ID (Add Food)` после `Send Add Food Prompt` — фикс утечки `last_bot_message_id`.

**n8n: legacy 08.x deactivated** (Quests/League/Friends/Shop) через SQL UPDATE на `workflow_entity` (active=0, activeVersionId=NULL — известный quirk draft/published n8n 2.x).

**Python changes:**
- `dispatcher/router.py` — добавлено поле `cb_context: dict | None` в `RouteDecision`, синтетические reply-kb callbacks устанавливают `is_inline=False` (commit `eb3c93d`).
- `dispatcher/router.py` — расширены `PROFILE_V5_CALLBACKS` (миграции 142-145 callbacks: cmd_league_info, cmd_friends_how_it_works, cmd_buy_*, cmd_*payout*, и т.д.).
- `dispatcher/router.py` — новый routing target `admin_payout` + regex `ADMIN_PAYOUT_RE` для admin chat callbacks (bypass menu/menu_v3).
- `telegram_proxy.py` — `check_n8n_reachable()` теперь использует env `N8N_HEALTH_URL` (default `http://127.0.0.1:5678/healthz`), убран хардкод cloud URL. Закрыло «бомбу 30.04».
- `webhook_server.py` — feature flag `HANDLER_DISPATCHER_USE_PYTHON` (shadow mode), фикс для Bug 5 sync_user_profile (от другого агента, я закоммитил).
- `services/envelope.py + render.py + telegram_send.py + nav_stack.py` — Phase 0.5 контракты, frozen.

**Git cleanup:**
- 148 dirty файлов закоммичены в 4 семантических батча: gitignore agent-state + 107 миграций + удаление obsolete планировочных доков + production hot-fixes.
- Origin/main линейная история. Worktree `/Users/vladislav/Documents/NOMS/.claude/worktrees/elated-cannon-6004dd/` синхронизирован.

**E2E tests:**
- `tests/live/e2e_runner.py` (NomsE2ERunner async context manager) — Telethon driver кликает кнопки от user 417002669 (ArchiShark), снапшотит nav_stack через psycopg2.
- `tests/live/scenarios/back_button.yaml` — 7 сценариев, **calibrated** против live прода: 26/26 шагов PASS, 17.91s/scenario.
- `tests/live/CALIBRATION_REPORT.md` — детали + findings.

**KB updates:**
- `daily/2026-04-29.md` — детальные секции по сегодняшним работам.
- `daily/2026-04-30.md` — Phase 2 (написал PM-агент).
- `concepts/n8n-selfhost-migration.md` — добавлено правило про deactivation (`active=0` + `activeVersionId=NULL`).
- Техдолг #1 (cloud probe hardcode в `telegram_proxy.check_n8n_reachable`) закрыт.

### 30.04 — Phase 2 PM-агент

PM-агент в отдельной сессии с дочерней worktree на ветке `claude/phase2-menu-v3` создал:
- `handlers/menu_v3.py` (322 LOC) — главный обработчик route_target=menu_v3.
- `tests/handlers/test_menu_v3.py` — 35 параметризованных кейсов.
- `tests/handlers/bench_menu_v3.py` — latency бенчмарк.
- `webhook_server.py` — добавлен feature flag `HANDLER_MENU_V3_USE_PYTHON` + early-routing block.

**Latency результаты:**
```
SELECT 1 baseline: p50=42ms p95=43ms
dispatch_with_render: p50=46ms p95=64ms (cmd_settings)
                      p50=46ms p95=52ms (cmd_buy_freeze)
                      p50=47ms p95=48ms (cmd_back)
```

vs текущие n8n end-to-end ~1800ms → ожидание ~60-90ms после flag flip = **20-30× ускорение**.

**Tests:** 170/170 passed (35 новых + 135 существующих). mypy --strict clean на новых файлах.

**Branch:** `claude/phase2-menu-v3` запушена. **НЕ задеплоено.** Не смерджена в main. User должен сделать review + merge.

---

## User open questions (CRITICAL — спросить ОБЯЗАТЕЛЬНО следующему агенту)

User закрывал сессию с двумя блоками вопросов:

### Block 1: Phase 0.5+1 Dispatcher Python — сомнения
> «у меня есть вопросы и по Phase 0.5 + 1: Dispatcher в Python»

User не уточнил что именно беспокоит. Возможные направления:
- **Контракт RouteDecision** — ясность полей, корректность маршрутизации?
- **Shadow mode trustability** — как верифицировать что Python даёт те же decisions что и n8n под нагрузкой?
- **Cutover roadmap** — когда переключать `HANDLER_DISPATCHER_USE_PYTHON=1`, что мерять, что откатывать?
- **Coverage табличных тестов** — все ли n8n routing branches покрыты в Python?
- **Backward compat** — старые callbacks (cmd_recharge_mana, cmd_add_food) корректно роутятся в legacy menu?
- **`admin_payout` target wired correctly** — webhook_server.py не диспатчит сейчас на этот target в shadow mode (он только route, не действует), но Phase 1 finalize должен это закрыть.

**Действие следующего агента:** через AskUserQuestion (multiSelect=true) спросить какие из этих тем волнуют. НЕ предполагать.

### Block 2: E2E тесты — картина не полная
> «замечания к Е2Е тестам - на мой взгляд картина не полная, не все экраны, кнопки ведут себя ожидаемо с моей точки зрения»

User не назвал конкретные экраны. Возможные пробелы:
- **Сценарии в `back_button.yaml` покрывают только Back-навигацию.** НЕ покрыты:
  - Save flows: ввод текста (edit_weight 85, edit_age 30) → сохранение → return
  - Photo / voice (логирование еды)
  - Ambassador payout flow (cmd_start_payout → method picker → wallet input → confirm)
  - Onboarding (новый юзер /start)
  - Edge cases: timeout от Telegram, флуд-контроль, malformed callbacks
- **Калибровка обнаружила F2/F3 поведения, которые user может считать «не правильным»** — см. CALIBRATION_REPORT.
  - F2: cmd_league_info / cmd_buy_freeze REPLACE стек single-item'ом (но Back через back_default спасает).
  - F3: mid-flow reply-kb push vs cold-flow wipe inconsistency.
- **Калибровка не покрыла rapid clicks** — user сам жаловался что 3 reply-кнопки подряд оставляют stale messages в чате. E2E тест на rapid-click не написан.

**Действие следующего агента:** AskUserQuestion с конкретными опциями («какие сценарии не покрыты», «какие экраны ведут себя странно»). После ответа — расширить YAML scenarios + добавить новые.

---

## Architecture state (как реально работает сейчас)

```
Telegram (user click)
    ↓ webhook
Python proxy (webhook_server.py :8443) — на прод-VPS Hetzner
    ├─ ack 200 OK ≤10ms
    ├─ asyncio.create_task(maybe_send_indicator) — фоновый стикер/typing
    ├─ asyncio.create_task(maybe_sync_user_profile) — Bug 5 fix (RPC sync_user_profile fire-and-forget)
    ├─ asyncio.create_task(forward_to_n8n) — основной forward
    └─ if HANDLER_DISPATCHER_USE_PYTHON=1:
          asyncio.create_task(shadow_route(update)) — shadow logging only
          [сейчас НЕ включено]

n8n self-hosted (VPS, port 5678)
    01_Dispatcher (id 7jVRdAvVlzOqIMEi)
        Validate Secret → Get User Context (v_user_context)
        Auto Create User (новые)
        Template Engine (paired-items fix, Profile v5 callbacks Set)
        Route Classifier v1.8 (44+ branches)
        Main Router → 12 outputs:
            menu, menu_v3, onboarding, ai, location,
            pre_checkout, successful_payment,
            account_blocked, restore_choice, restore_execute, start_fresh_execute,
            error
    
    04_Menu_v3 (id 0xJXA5M4wQUSiGXT) — POST /rpc/dispatch_with_render
        ↓ возвращает {status, screen_id, telegram_ui, business_data}
        Telegram API (sendMessage / editMessageText)
    
    04_Menu (legacy id JQsipPWxijse3F0b) — для cmd_recharge_mana, cmd_add_food, и пр. legacy paths
    02_Onboarding_v3, 02.1_Location, 03_AI_Engine, 10_Payment — без изменений сегодня
    
    Deactivated (08.1-08.4): Quests, League, Friends, Shop — заменены headless через 04_Menu_v3

Supabase PostgreSQL EU pooler
    process_user_input (после миграций 146-154 + 153 patch для S6)
        ├─ Path A: per-callback debounce (148/150) — same callback в 500ms = block, cmd_back bypass
        ├─ L94 fallback: COALESCE(get_fallback_root_screen(), 'profile_main')
        ├─ Fastpath block (147/151/153): wipe + push для 3 reply-kb roots, иначе keep stack
        ├─ cmd_back logic (147): Priority 1 nav_stack pop, P2 back_screen_id_default, P3 fallback constant
        └─ End: вызов render_screen внутри (telegram_ui ready)
    dispatch_with_render (149) — wrapper passthrough процесса pui + defensive render fallback
    push_nav (147 truncate-on-existing) / back_nav (146 root_fallback)
    debounce_user_action 3-arg (148/150 idempotent_bypass)
    
    ui_screens (post-152: country_picker / timezone_picker registered)
    app_constants ('fallback_root_screen' key, post-154)
```

---

## Где что лежит (file locator для следующего агента)

### Migrations
- `migrations/146_back_fallback_stats_main_root.sql`
- `migrations/147_back_i_came_from_navigation.sql`
- `migrations/148_per_callback_debounce.sql`
- `migrations/149_dispatch_with_render_bundle.sql`
- `migrations/150_debounce_idempotent_callbacks.sql`
- `migrations/151_fastpath_wipe_then_push_root.sql`
- `migrations/152_register_location_pickers.sql`
- `migrations/153_wipe_for_all_reply_kb_roots.sql`
- `migrations/154_fallback_root_screen_constant.sql`

### Python (Phase 0.5+1, в проде в shadow + Phase 2 в ветке `claude/phase2-menu-v3`)
- `services/envelope.py` — frozen contract
- `services/telegram_send.py` — outbound dispatcher (own httpx pool)
- `services/render.py` — `render_screen` RPC adapter + `parse_render_response` (переиспользован Phase 2)
- `services/nav_stack.py` — peek/push/pop/clear обёртки
- `dispatcher/router.py` — Route Classifier port (PROFILE_V5_CALLBACKS, ADMIN_PAYOUT_RE, ...)
- `dispatcher/context.py` — UserCtx dataclass + get_user_context
- `dispatcher/secret.py` — `validate_secret` (env-driven)
- `dispatcher/shadow.py` — observation-only runner (live в проде с flag OFF)
- `handlers/menu_v3.py` — **только в ветке `claude/phase2-menu-v3`**, не в main

### Tests
- `tests/services/*.py`, `tests/dispatcher/*.py` — 135 unit tests, all green в main
- `tests/handlers/test_menu_v3.py` — **35 кейсов в ветке `claude/phase2-menu-v3`**
- `tests/handlers/bench_menu_v3.py` — latency бенчмарк, ветка Phase 2
- `tests/live/e2e_runner.py` — Telethon E2E driver (main)
- `tests/live/scenarios/back_button.yaml` — 7 calibrated сценариев (main)
- `tests/live/CALIBRATION_REPORT.md` — F2/F3/F4/F5 findings (main)

### KB / docs
- `claude-memory-compiler/daily/2026-04-29.md` — все вчерашние сессии
- `claude-memory-compiler/daily/2026-04-30.md` — Phase 2 details
- `claude-memory-compiler/handover/2026-04-30_session_close.md` — этот документ
- `claude-memory-compiler/knowledge/concepts/headless-architecture.md` — архитектурный паттерн
- `claude-memory-compiler/knowledge/concepts/n8n-selfhost-migration.md` — VPS / n8n self-host правила (включая deactivation quirk)
- `CLAUDE.md` — операционные правила (правило 7 p95 latency, правило 13 PUT body whitelist, etc.)

### Plans
- `/Users/vladislav/.claude/plans/users-vladislav-claude-plans-dynamic-ji-generic-wren.md` — последний план тимлида (29.04)
- `/Users/vladislav/.claude/plans/groovy-marinating-eclipse.md` — изначальный roadmap n8n→Python

### Production VPS
- `root@89.167.86.20`
- `/home/taskbot/noms/` — основной проект (deploy.sh из репо льёт сюда)
- `/home/taskbot/noms/.env` — все credentials (включая Telethon creds, NOMS_DISPATCHER_SECRET, DATABASE_URL)
- `/home/noms/n8n/` — n8n self-hosted compose dir
- `/home/noms/n8n/data/database.sqlite` — n8n executions БД
- `/home/noms/n8n/backups/` — daily backups + pre-PUT snapshots от вчерашних chip'ов
- `/home/noms/n8n/compose/.env` — N8N_TARGET_API_KEY

### Telethon E2E credentials
В `.env` основного проекта:
- `TELEGRAM_API_ID=34863896`
- `TELEGRAM_API_HASH=72e7bcd65b50016399896d84ca190520`
- `TELEGRAM_SESSION_PATH=/Users/vladislav/Documents/NotebookLM+Claude/telethon_session.session`

Session shared с PingWin / NotebookLM tooling. **Не коммитить** в git (gitignored через `*.session`).

### Git
- `origin/main` HEAD: `7f8d149` — последний коммит вчера (calibration report)
- `origin/claude/phase2-menu-v3` HEAD: ветка Phase 2 (PM-агент запушил)
- `origin/claude/elated-cannon-6004dd` — рабочая worktree-ветка тимлида (содержит всё включая phase 0.5+1, может быть смерджена с main)

---

## Findings (из калибровки — wishlist для следующих сессий)

### F2 — асимметрия nav_stack (UX smell, не breaking)
| Callback | До | После |
|---|---|---|
| `cmd_edit_timezone` | `[settings]` | `[settings, edit_timezone]` ✅ push |
| `cmd_league_info` | `[league]` | `[league_info]` ⚠️ replace |
| `cmd_buy_freeze` | `[shop]` | `[buy_freeze_confirm]` ⚠️ replace |

Settings sub-screens иерархичны, info-/confirm-экраны лиги/магазина — нет.

**User-impact:** Back из league_info уходит на root через Priority 2 back_default (а не path-walk через стек). Технически корректно, но Phase 2 PM-агент в Python унаследует то же поведение из SQL.

**Fix:** в `dispatch_with_render` (или прямо в `process_user_input`) после determined v_next_screen — если v_next_screen имеет `parent_screen_id`, и parent ещё не на top of stack — push parent ПЕРЕД пушем destination. Это закроет асимметрию.

### F3 — wipe inconsistency
Mid-flow reply-kb (стек непустой) → push, **не** wipe.
Cold reply-kb (стек пустой) → wipe-then-push.

Поведение зависит от стартового состояния, что user видит как «непредсказуемо». Migration 153 закрыла главный кейс (S6), но edge cases остались.

**Действие:** explicit decision — либо ALL reply-kb всегда wipe (даже из глубокого стека), либо никогда (всегда keep + push). Сейчас гибрид через `is_inline` плюс identity check 153, что мутно.

### F4 — spec drift
- `cmd_edit_lang` (не `cmd_edit_language` как в старом spec).
- Реальный status `edit_timezone` (не `editing:timezone` как в CLAUDE.md «Недавно добавленные states (2026-04-16)»).
- `cmd_edit_lang` (язык-picker) **не пишет в nav_stack** — shared screen вне обычного pipeline.

**Действие:** обновить CLAUDE.md или добавить `editing:timezone` в `workflow_states` чтобы привести в соответствие.

### F5 — root экраны без Back
By design. profile_main / stats_main / progress_main — нет cmd_back кнопок. Не баг.

---

## Что НЕ трогать без острой нужды

- **`services/envelope.py`** — frozen Phase 0.5 контракт, любая правка ломает все handlers.
- **`dispatcher/router.py`** — foundation для Phase 1 cutover. Patches OK, переписывание — нет.
- **Migrations 146-154** — applied, проверено, в проде. Откат только через explicit migration N+M.
- **n8n `04_Menu_v3` workflow** — пока flag не flipped, это live путь. Любая правка ломает прод.
- **Phase 2 `claude/phase2-menu-v3` branch** — НЕ мерджить без user'а. PR-review нужен.

---

## Рекомендуемый порядок действий следующего агента

### Шаг 1 — синхронизация контекста + опрос user'а
- Прочитать этот handover целиком + `daily/2026-04-29.md` + `daily/2026-04-30.md` + `tests/live/CALIBRATION_REPORT.md`.
- AskUserQuestion с 2 вопросами:
  1. **Phase 0.5+1 Dispatcher concerns** — multiSelect: contract / shadow trust / cutover plan / coverage / backward compat / admin_payout wiring / Other.
  2. **E2E gaps** — multiSelect: save flows / photo+voice / payment flow / onboarding new user / edge cases / rapid clicks / Other.

### Шаг 2 — действовать по ответам user'а
- Если concern про Phase 0.5+1 — детальный разбор + возможно расширить tests/dispatcher/test_router.py.
- Если concern про E2E — расширить `tests/live/scenarios/` под новые группы (save flows, photo, payment, onboarding).

### Шаг 3 — Phase 2 finalize
**Не блокировать на user concerns.** Параллельно:
- Code review ветки `claude/phase2-menu-v3` (handlers/menu_v3.py — 322 LOC).
- Smoke smoke local (без flag): `python3 -m pytest tests/handlers/ -v` → 35/35.
- Если user даёт OK — мердж в main + flip flag на VPS:
  ```bash
  ssh root@89.167.86.20 'echo HANDLER_MENU_V3_USE_PYTHON=1 >> /home/taskbot/noms/.env && systemctl restart noms-webhooks noms-cron'
  ```
  ⚠️ ОБА сервиса (правило свежее в CLAUDE.md, инцидент 27.04 22:15).
- 24h наблюдение через journalctl + n8n executions (должно быть нулевое для menu_v3 paths после flip).

### Шаг 4 — F2/F3 cleanup (опционально, по приоритету user'а)
- Migration 155 — fix asymmetric stack push.
- Migration 156 (если нужно) — make wipe contract explicit (always or never).

### Шаг 5 — Phase 1 finalize roadmap
- Когда menu_v3 на Python стабилен 7+ дней → flip `HANDLER_DISPATCHER_USE_PYTHON=1` (Dispatcher cutover).
- ⚠️ Перед flip нужны:
  - SQL RPC `ensure_user_exists` (для auto-create user) — НЕ написана пока.
  - SQL RPCs `nav_stack_peek/push/pop/clear` — НЕ написаны (Python wrappers готовы в `services/nav_stack.py`).
- Спавн DB-агента сделать обе.

### Шаг 6 — extended phases (Phase 3-7)
По плану `groovy-marinating-eclipse.md`:
- Phase 3: 04.2_Edit_StatsDaily, 06_Indicator_Clear, 08.* hubs (тривиально).
- Phase 4: 02_Onboarding_v3.
- Phase 5: 02.1_Location.
- Phase 6: 10_Payment.
- Phase 7: 03_AI_Engine.

Каждая фаза — отдельная PM-сессия со своим chip'ом. Pattern уже отработан в Phase 2.

---

## Что user может прокликать чтобы лично проверить (sanity check)

| Сценарий | Что должно произойти | Если не так — это баг |
|---|---|---|
| Прогресс → Лиги → Как работают лиги → Назад → Назад | league_info → league → progress_main | F2 fired, но Back через back_default OK; см. CALIBRATION_REPORT |
| Прогресс → Магазин → купить mana → Confirm → Назад | success → shop | F2 — Back idет на root через back_default, не на confirm screen |
| Профиль → Настройки → Часовой пояс → Выбрать из списка → Назад → Назад → Назад | timezone_picker → edit_timezone → settings → profile_main | Если уходит в Мой день — отправь сценарий следующему агенту |
| Reply-kb «Профиль» mid-flow (когда юзер на любом экране кроме root) → Назад | profile_main → stats_main (Priority 3 fallback) | Перед migration 153 уходило на league/shop |
| Reply-kb «Прогресс» 2 раза подряд за <1 сек | Только одна реакция (debounced второй) | По migration 148 |
| Прожать 3 разных reply-kb за <1 сек | Все 3 срабатывают (per-callback debounce) | По migration 148/150 |
| 2 раза подряд cmd_back быстро | Оба срабатывают (idempotent_bypass migration 150) | Раньше второй блокировался |
| Добавить еду → новое меню (любое) → Add Food промт удалился? | Да (migration n8n save_menu_id) | Если промт остался — баг в save_menu_id node |

---

## Open TODOs (не критичные, для следующих сессий)

- [ ] CLAUDE.md sync с реальным состоянием БД (cmd_edit_lang, edit_timezone status).
- [ ] `concepts/headless-architecture.md` "Open вопросы (после Sessions 7-9)" — устаревший раздел, rewrite.
- [ ] `concepts/headless-architecture.md` "File references" таблица — расширить до migration 154.
- [ ] cmd_add_food wipe — добавить в fastpath (deferred per migration 153 header).
- [ ] Error screens push в nav_stack (`shop_error_no_coins` и пр.) — отдельный кандидат на fix через `meta.no_push=true`.
- [ ] F2 fix через push parent before destination в SQL.
- [ ] F3 explicit wipe contract decision.
- [ ] Telethon E2E: расширить scenarios для save flows / photo / payment / onboarding.
- [ ] E2E: rapid-click тест.
- [ ] Stripe ключи на VPS (.env STRIPE_SECRET_KEY / STRIPE_WEBHOOK_SECRET) — пока stub.
- [ ] Cron monitor для n8n executions с error% alerting.

---

## ⚡ ADDENDUM (после первоначального handover, 30.04 поздно)

После того как я подготовил handover, user (или параллельный агент) **продвинул работу значительно дальше**:

### Migrations 155-158 applied
- `155_dispatcher_python_cutover_foundation.sql` — основа для Phase 1 cutover
- `156_phase2_menu_v3_feature_flag.sql` — `app_constants.handler_menu_v3_use_python` (hot-reload через app_constants_cache trigger)
- `157_dispatcher_python_authoritative_admin_only.sql` — DB flag `dispatcher_python_authoritative` + admin-only gate
- `158_get_dispatcher_flags_add_menu_v3_use_python.sql` — extended `get_dispatcher_flags()` RPC

### Phase 2 menu_v3 ЖИВ в production webhook_server.py
- `_route_or_forward(update, body, fwd_hdr, t0)` — fire-and-forget task, не блокирует webhook ack
- Logic:
  1. **B-3 authoritative path** (если `dispatcher_python_authoritative=true` И user в admin gate) → Python routes напрямую в per-target n8n webhook ИЛИ handle_menu_v3, **минуя 01_Dispatcher**
  2. **Phase 2 menu_v3 path** (если flag from `ctx.constants.handler_menu_v3_use_python` ИЛИ env fallback) → handle_menu_v3 → telegram_send → save_bot_message
  3. **Fallthrough** → forward_to_n8n как раньше
- Любое exception в Python путях → fallthrough на n8n. Безопасный rollback.
- `_send_and_persist` — обёртка над `telegram_send.send` + сохранение `last_bot_message_id` через RPC `save_bot_message` (тот же контракт что узел "20. Save Bot Message" в n8n 04_Menu_v3 — One Menu UX preserved).

### Новые Python модули (которых НЕ было в моей сессии)
- `dispatcher/forward.py` — авторитарный per-target dispatcher (B-3)
- `services/app_flags.py` — `get_flags()` для DB-флагов

### Что это значит для следующего агента

1. **Phase 1 cutover уже частично деплоен.** Не «pending»: код в `webhook_server.py` уже поддерживает B-3 path. Активация — через DB-флаг + admin-gate (migration 157).
2. **Phase 2 menu_v3 уже не «в ветке».** Wiring в webhook_server.py произошёл. Скорее всего ветка `claude/phase2-menu-v3` смерджена в main.
3. **deploy.sh обновлён** — `--include='handlers/***'` добавлен в rsync whitelist.

### Что проверить первым делом

```bash
cd /Users/vladislav/Documents/NOMS
git log --oneline origin/main -10                    # увидеть 155-158 + менуv3 wiring коммиты
ls migrations/15{5,6,7,8}*.sql                        # все 4 на месте
grep "_try_authoritative_path\|dispatcher_python_authoritative" webhook_server.py  # wiring
ssh root@89.167.86.20 'grep HANDLER_MENU_V3_USE_PYTHON /home/taskbot/noms/.env'  # env fallback flag?
ssh root@89.167.86.20 'export $(grep ^DATABASE_URL /home/taskbot/noms/.env); psql "$DATABASE_URL" -c "SELECT key, value FROM app_constants WHERE key LIKE '\''handler_%'\'' OR key LIKE '\''dispatcher_%'\''"'  # current DB flags
```

Эти 4 запроса дадут полную картину: что в коде, что в env, что в БД, кто rules сейчас.

### Open вопрос: статус rollout

User **не сказал явно** — Phase 2 уже включена для всех пользователей (`app_constants.handler_menu_v3_use_python=true`)? Или только для админ-айди (через B-3 gate из 157)? Или вообще выключена и ждёт review?

**Действие:** проверить через psycopg2 после AskUserQuestion'а в начале следующей сессии.

---

## Финальное послание следующему агенту

Сегодняшний день (29-30.04) закрыл:
- **Главный user-side баг** S6 («Назад уводит в Мой день»)
- **Headless архитектурный долг** (split-brain wipe устранён)
- **9 SQL миграций (146-154) + 4 свежих (155-158)**
- **4 n8n правки** (ACQ + is_inline + bundle + Reset Nav cleanup + add_food save_menu_id)
- **Phase 0.5+1 Python Dispatcher** (в проде в shadow + готов к flip)
- **Phase 2 menu_v3 Python handler** (wired в webhook_server.py, hot-reloadable via app_constants)
- **B-3 authoritative routing** (Phase 1 cutover foundation, admin-only gated)
- **Telethon E2E runner** (7 сценариев calibrated 7/7)
- **Latency** dispatch_with_render p50=46ms (vs n8n end-to-end ~1800ms = 20-30× speedup ceiling)

User закрыл сессию с **двумя блоками вопросов** (см. секцию «User open questions» выше). **Первое что делает следующий агент** — AskUserQuestion с конкретными опциями.

Phase 1 cutover (Variant B Phase 1 = B-3 = `dispatcher_python_authoritative`) — готов к активации через DB-флаг + admin gate. Это огромный milestone: Python становится authoritative router, n8n остаётся только для исполнения хендлеров (постепенно мигрирующих).

Удачи. 🚀
