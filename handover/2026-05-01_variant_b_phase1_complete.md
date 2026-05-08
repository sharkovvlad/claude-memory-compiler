# Variant B Phase 1 — cutover завершён (handover для следующих агентов)

**Автор:** Агент Диспетчер (Claude), сессия 30.04 — 01.05.2026.
**Аудитория:** агент, который продолжит работу над n8n→Python миграцией.
**Кросс-ссылки:**
- `daily/2026-05-01.md` — таймлайн сегодняшних работ
- `knowledge/concepts/variant-b-cutover.md` — переиспользуемый паттерн
- Предыдущий handover: `handover/2026-04-30_session_close.md`
- Master plan: `/Users/vladislav/.claude/plans/groovy-marinating-eclipse.md`

---

## TL;DR — что в проде на 01.05 12:00 MSK

**B-3 Authoritative Router работает в production для одного таргета — `menu_v3`.**
Все остальные клики (Add food / AI / Onboarding / Location / Payment) — через legacy 01_Dispatcher как до 30.04. Foundation (6 webhooks + forward.py + DB-флаги + parity_check) задеплоена и готова к расширению по мере того, как новые sub-workflows будут переписываться в Python.

```
main HEAD: 438ce1c hotfix: narrow B-3 TARGET_TO_PATH to menu_v3 only
Tests:     327 passed, 1 skipped (empty parametrize)
```

---

## Что было построено за 2 дня

### DB layer (5 миграций — все applied)
| # | Что | Применена |
|---|---|---|
| 155 | `ensure_user_exists` RPC + 2 dispatcher-флага в app_constants + `get_dispatcher_flags()` helper | ✅ |
| 156 | `handler_menu_v3_use_python` flag (Phase 2) | ✅ |
| 157 | `dispatcher_python_authoritative_admin_only` flag | ✅ |
| 158 | Расширение `get_dispatcher_flags()` до 4 полей | ✅ |
| 159 | `attach_reply_kb` infrastructure (Phase 2) | ✅ |
| 160 | Conditional reply_keyboard re-attach (без `·` пузырей) | ✅ |

### n8n layer (6 webhook'ов в sub-workflows — live)
Все добавлены через `tools/n8n_inject_cutover_webhook.py` — он умеет GET → inject Webhook + Adopt Code → PUT → smoke. Идемпотентен.

| Path | Workflow | Downstream |
|---|---|---|
| `POST /webhook/dispatcher/menu_v3` | `0xJXA5M4wQUSiGXT` | Extract Payload |
| `POST /webhook/dispatcher/menu_legacy` | `JQsipPWxijse3F0b` | Merge Data |
| `POST /webhook/dispatcher/onboarding_v3` | `wzjYmMOurCbp4czk` | Merge Data |
| `POST /webhook/dispatcher/location` | `7EqiiwUwlGs7dcHT` | Init & Templates |
| `POST /webhook/dispatcher/ai_engine` | `kjw4kkKMD0IqNALg` | Check Editing Mode |
| `POST /webhook/dispatcher/payment` | `T9753zO3ZyiYsgkp` | Merge Data |

⚠️ **5 из 6 простаивают** — см. секцию «Известные ограничения». Сейчас активно используется только `/webhook/dispatcher/menu_v3` (когда `menu_v3_use_python=false`).

Аутентификация — header `X-NOMS-DISPATCHER-SECRET`, валидируется в Adopt-ноде (silent drop при невалидном секрете). Секрет — env `N8N_DISPATCHER_SECRET` в `/home/taskbot/noms/.env` и `/home/noms/n8n/compose/.env`.

### Python layer
- **`services/app_flags.py`** — DB-driven flag reader с TTL-кэшем 60с. Env-overrides сохранены как kill-switch.
- **`dispatcher/forward.py`** — async httpx pool с retry на 5xx. `build_payload` производит **flat** payload-shape (44 поля) — мэппинг из live GET 01_Dispatcher's "Prepare for *" Set-нод (см. docstring файла).
- **`dispatcher/shadow.py`** — async + DB-flag + `update_id` в логах для parity-валидатора.
- **`webhook_server.py::_try_authoritative_path`** — главная B-3 функция. Внутри `_route_or_forward` (фоновый task → ACK 0мс).
- **`webhook_server.py::_ensure_user_for_authoritative`** — порт Auto Create User для нового /start.
- **`tools/parity_check.py`** — SHADOW_ROUTE логи vs n8n executions diff по update_id. Verdict 🟢/🟡/🔴.
- **`tools/n8n_inject_cutover_webhook.py`** — идемпотентный injector новых webhook'ов в любой workflow.

---

## DB-флаги — таблица состояния

Читаются через `SELECT public.get_dispatcher_flags()` или Python `services.app_flags.get_flags()` (cached 60с).

| Ключ в `app_constants` | Текущее значение в проде | Что делает | Категория |
|---|---|---|---|
| `dispatcher_python_shadow_mode` | `true` | shadow_route наблюдает (логи `SHADOW_ROUTE update_id=...`) | dispatcher |
| `dispatcher_python_authoritative` | `true` | Включает B-3. Когда false — весь трафик через legacy n8n | dispatcher |
| `dispatcher_python_authoritative_admin_only` | `true` | Гейт. true = только telegram_id 417002669 идёт через B-3, остальные legacy | dispatcher |
| `handler_menu_v3_use_python` | `true` | true = `menu_v3` через `handle_menu_v3` (Python full ownership), false = forward в n8n /webhook/dispatcher/menu_v3 | feature_flags |

**Hot-reload:** изменения через `UPDATE app_constants SET value=...` подхватываются за 60с (TTL кеша Python) или мгновенно через trigger `app_constants_cache` (для ctx.constants).

**Env overrides** (emergency kill-switch, требует `systemctl restart noms-webhooks`):
- `HANDLER_DISPATCHER_USE_PYTHON`
- `HANDLER_DISPATCHER_AUTHORITATIVE`
- `HANDLER_DISPATCHER_AUTHORITATIVE_ADMIN_ONLY`
- `HANDLER_MENU_V3_USE_PYTHON`

---

## Как работает routing сейчас (упрощённая схема)

```
Telegram → POST /telegram/webhook (FastAPI, webhook_server.py)
    ↓ ack 200 за 0мс (fire-and-forget create_task)
    ├─ create_task(maybe_send_indicator)
    ├─ create_task(maybe_sync_user_profile)
    ├─ create_task(_route_or_forward)            ← вся routing-логика тут
    └─ create_task(shadow_route)                 ← мониторинг для parity_check

_route_or_forward (background):
    ├─ _try_authoritative_path()                 ← B-3 (Variant B Phase 1)
    │   ├─ flags = await get_flags()             ← DB cache 60с
    │   ├─ if not flags.authoritative: return False
    │   ├─ if flags.admin_only and chat_id != 417002669: return False
    │   ├─ ctx = await _ensure_user_for_authoritative(...)  ← ensure_user_exists RPC fallback
    │   ├─ decision = route_update(update, ctx)  ← классификатор
    │   ├─ if decision.target == "menu_v3":
    │   │     if menu_v3_use_python:
    │   │         envelope = await handle_menu_v3(...)   ← Python full ownership
    │   │         create_task(_send_and_persist(envelope))
    │   │     else:
    │   │         create_task(forward.send("menu_v3", build_payload(...)))  ← n8n webhook
    │   │     return True
    │   ├─ elif target in TARGET_TO_PATH:        ← пусто кроме menu_v3 (на 01.05)
    │   │     create_task(forward.send(target, build_payload(...)))
    │   │     return True
    │   └─ return False                          ← admin_payout/error/legacy → fall through
    │
    ├─ Phase 2 menu_v3 fast-path                 ← дублирует B-3 для случая authoritative=false
    │     (читает ctx.constants.handler_menu_v3_use_python — hot-reload)
    │     если фича включена и target==menu_v3 → handle_menu_v3 + send
    │
    └─ forward_to_n8n(body)                      ← legacy: апдейт в /webhook/01_Dispatcher
```

### Сейчас в проде (admin only, menu_v3 only)
- Админский клик «Профиль» → B-3 → handle_menu_v3 → быстрый ответ
- Админский «Add food» → B-3 returns False → forward_to_n8n → 01_Dispatcher → 04_Menu (как раньше)
- Не-админский любой клик → B-3 returns False (admin_only gate) → legacy
- Все юзеры menu_v3-callbacks → если admin_only=false (когда расширим) → handle_menu_v3 для всех

---

## ⚠️ Известные ограничения (КРИТИЧНО для следующего агента)

### Legacy sub-workflows структурно несовместимы с Webhook entry

Найдено 01.05 (prod incident). Ноды в 04_Menu, 02_Onboarding_v3, 02.1_Location, 03_AI_Engine используют n8n expression `$('Execute Workflow Trigger').item.json.X` или `$('Merge Data').item.json.X` — **runtime ссылки на конкретные ноды по имени**. При запуске через мой Webhook B-1 Cutover → Adopt Code → ..., нода `Execute Workflow Trigger` не выполняется в этой execution graph → ExpressionError → workflow падает.

**Scope** (NLM provided): 40+ нод суммарно ссылаются на trigger-ноды. См. `daily/2026-05-01.md` для конкретики.

**Что НЕ сработало (рассмотрено и отвергнуто):**
- ❌ Hack с переименованием Adopt → имя trigger'а — конфликт имён в n8n; ломает legacy путь когда `admin_only=true` (трафик не-админов идёт через старый Execute Workflow Trigger, который теперь `_Legacy`, downstream не находит)
- ❌ Дублирование downstream — по сути та же работа что переписать с нуля
- ❌ Переписать 40+ нод вручную — высокий риск регрессии legacy

**Что работает (текущее решение):**
- ✅ Сузить B-3 scope до таргетов с готовым Python-обработчиком (сейчас menu_v3, потом onboarding и т.д.)
- ✅ Legacy sub-workflows доживают свой век через 01_Dispatcher (как до 30.04)
- ✅ Foundation готова — добавление таргета = одна строка в `TARGET_TO_PATH`

### admin_payout target не имеет обработчика

Python router возвращает `target=admin_payout` для callback'ов `admin_payout_approve_*` / `admin_payout_reject_*` (admin chat). B-3 для них возвращает False → fall-through на legacy. Но legacy 01_Dispatcher тоже не знает этот target (он Python invention). Реальный handler — `payout_handler.handle_admin_payout_callback`. Пока gap — нужен явный вызов из B-3 для `admin_payout` target. **Низкая частота, не блокер.**

### `pre_checkout_query` / `successful_payment` обрабатываются ИНЛАЙН в 01_Dispatcher

Не идут в 10_Payment workflow — это `Process Payment` Code node + `Send Payment Success` Telegram node прямо в 01_Dispatcher. **НЕ возвращать их в `TARGET_TO_PATH`** даже когда 10_Payment будет переписан в Python — payment events это отдельная ветка.

---

## Roadmap расширения B-3

### Phase 6 (следующий) — переписать onboarding в Python
Когда `handlers/onboarding_v3.py` готов (по аналогии с Phase 2 menu_v3):
1. Добавить `"onboarding": "onboarding_v3"` в `TARGET_TO_PATH` (если хотим n8n fallback) ИЛИ напрямую вызвать `handle_onboarding_v3` в B-3 веткой `if target == "onboarding"`.
2. Добавить новый флаг `handler_onboarding_use_python` в `get_dispatcher_flags()` — по аналогии с migration 158.
3. Расширить `_try_authoritative_path` симметричной веткой для onboarding.
4. **Никаких изменений в legacy 02_Onboarding_v3 не нужно** — он остаётся живым для случая когда новый флаг false.

### Phase 7-9 — location / ai / menu_legacy
Та же схема. Каждый sub-workflow — отдельная PM-сессия.

### Конечная цель: deactivate 01_Dispatcher
После того как ВСЕ legacy targets переписаны в Python и 100% трафика идёт через B-3:
1. `dispatcher_python_authoritative_admin_only=false` → 1% rollout → 100%
2. После 7+ дней stable: `UPDATE workflow_entity SET active=0 WHERE id='7jVRdAvVlzOqIMEi'` (01_Dispatcher)
3. Backup workflow JSON в `/home/noms/n8n/backups/01_Dispatcher_DEPRECATED_<date>.json`

---

## File locator (для следующего агента)

### Migrations
- `migrations/155_dispatcher_python_cutover_foundation.sql`
- `migrations/157_dispatcher_python_authoritative_admin_only.sql`
- `migrations/158_get_dispatcher_flags_add_menu_v3_use_python.sql`
(159, 160 — Phase 2 от Профиль-Агента)

### Python source
- `services/app_flags.py` — DispatcherFlags + get_flags() с TTL cache
- `services/nav_stack.py` — peek_nav/push_nav/pop_nav/clear_nav обёртки (фикс RPC имён 30.04)
- `dispatcher/forward.py` — TARGET_TO_PATH + send + build_payload (flat shape)
- `dispatcher/shadow.py` — async shadow_route с update_id в логах
- `webhook_server.py:_try_authoritative_path` (строки ~250-340) — B-3 логика
- `webhook_server.py:_ensure_user_for_authoritative` — Auto Create User port

### Tests (327 PASS)
- `tests/services/test_app_flags.py` — 13 кейсов
- `tests/dispatcher/test_forward.py` — TARGET_TO_PATH + build_payload contract
- `tests/dispatcher/test_shadow.py` — async + update_id
- `tests/test_b3_authoritative_path.py` — все B-3 ветки (gate, menu_v3, fall-through)

### Tooling
- `tools/n8n_inject_cutover_webhook.py` — идемпотентный injector
- `tools/parity_check.py` — SHADOW_ROUTE vs n8n executions diff

### Knowledge
- `claude-memory-compiler/handover/2026-05-01_variant_b_phase1_complete.md` — этот документ
- `claude-memory-compiler/daily/2026-05-01.md` — таймлайн дня
- `claude-memory-compiler/knowledge/concepts/variant-b-cutover.md` — паттерн cutover

---

## Аварийные команды

### Полный rollback B-3 (~60с TTL)
```bash
cd /Users/vladislav/Documents/NOMS && PGPASSWORD_FROM_ENV=$(grep '^DATABASE_URL=' .env | cut -d= -f2-) python3 -c "
import os, psycopg2
c = psycopg2.connect(os.environ['PGPASSWORD_FROM_ENV'])
c.cursor().execute(\"UPDATE app_constants SET value='false' WHERE key='dispatcher_python_authoritative'\")
c.commit()
"
```

### Мгновенный rollback (без TTL)
```bash
ssh root@89.167.86.20 'systemctl restart noms-webhooks'  # +env override flag в .env если нужно
```

### Posthumous rollback Phase 2 menu_v3 (если handle_menu_v3 опять забагует)
```bash
... UPDATE app_constants SET value='false' WHERE key='handler_menu_v3_use_python'
```

---

## Финальное послание следующему агенту

Variant B Phase 1 — это не конец cutover'а, это **фундамент** для постепенного переноса. Сейчас работает только menu_v3, но архитектурный паттерн отработан и готов к масштабированию: пиши Python-обработчик любого workflow по образу `handlers/menu_v3.py`, добавляй ветку в `_try_authoritative_path`, расширяй `TARGET_TO_PATH` при необходимости fallback'а — всё, новый таргет в проде.

**Главные грабли (на которые я наступил):**
1. Old rsync deploy.sh может откатить Python-файлы если ветки агентов рассинхронизированы → ВСЕГДА пушить main и деплоить serially (Тимлид это уже знает, разводит агентов по времени)
2. Legacy sub-workflow ноды используют `$('NodeName')` ссылки → `Webhook → Adopt → downstream` НЕ работает для них → не пытайся форвардить в legacy webhook'и
3. n8n не позволяет два узла с одинаковым именем → renaming-хак не катит при staged rollout
4. shadow_enabled() / get_flags() — async, но кешированы (TTL 60с) → cold-start первый запрос ~30мс, потом микросекунды

Удачи. 🚀
