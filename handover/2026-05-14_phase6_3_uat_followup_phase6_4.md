# Handover — Phase 6.3 UAT follow-up + Phase 6.4 prep

> **Создано:** 2026-05-14 ~10:35 MSK после live UAT тимлида и hotfix PR #67. Контекст моего worktree («elastic-newton-045da5») сильно нагружен (5 PR за сессию: #58, #59, #60, #66, #67). Передаю эстафету.
>
> **Аудитория:** агент-преемник, который (a) подтянет UAT-loop Phase 6.3 после operational fix VPS env, (b) спланирует Phase 6.4 (decommission n8n 02.1_Location + canary cleanup).

---

## 0. Первые 15 минут — обязательное чтение

| # | Файл | Зачем |
|---|---|---|
| 1 | `/Users/vladislav/Documents/NOMS/CLAUDE.md` | NOMS правила (NLM-first, RPC-first, no-hardcode, release-protocol). |
| 2 | `/Users/vladislav/.claude/CLAUDE.md` | Глобальная git-дисциплина при параллельной работе (§12). |
| 3 | `/Users/vladislav/.claude/projects/-Users-vladislav-Documents-NOMS/memory/MEMORY.md` | Состояние на 14.05 + 13.05 (mig HEAD, активные канарейки, gotchas). |
| 4 | `claude-memory-compiler/RULES.md` | KB правила — куда класть, что не класть. |
| 5 | `claude-memory-compiler/knowledge/concepts/canonical-hybrid-location-picker.md` | **Phase 6.3 архитектурный паттерн**, написан мной 14.05. |
| 6 | `claude-memory-compiler/knowledge/concepts/phase6-location-migration-plan.md` | Master plan Phase 6.1-6.4. Phase 6.3 отмечен CLOSED, 6.4 pending. |
| 7 | `claude-memory-compiler/knowledge/concepts/headless-fsm-vs-dynamic-handler-separation.md` | Принципы (Phase 6.2): статика → SQL FSM, динамика → Python; setters ≠ FSM. |
| 8 | `claude-memory-compiler/daily/2026-05-14.md` | Полный recap сегодняшней сессии — Canonical Hybrid implementation + UAT bugs. |
| 9 | `claude-memory-compiler/knowledge/concepts/access-credentials.md` | psycopg2 / NLM / SSH рецепты + permissions troubleshooting. |
| 10 | `claude-memory-compiler/knowledge/concepts/safe-create-or-replace-recipe.md` | Stale-base recipe для CREATE OR REPLACE FUNCTION. |

---

## 1. Состояние прода на момент handover (2026-05-14 ~10:35 MSK)

### Прошедшие за сегодня

- **PR #66** (Phase 6.3 — geo-pin + Canonical Hybrid) — **merged 07:22 UTC**, auto-deploy success.
- **Mig 210** (Phase 6.3 SQL: ask_country merge + ask_share_location delete + buttons.share_location + process_onboarding_input rewrite) — **applied на проде** через psycopg2 (subagent написал, я review'нул + applied).
- **PR #67** (hotfix Phase 6.3 — JSONB-array translation lookup + one_time_keyboard:true + remove carrier «·») — **awaiting merge**.

### Открытые pending items

| Item | Статус | Action |
|---|---|---|
| **PR #67 merge** | awaiting | Тимлид merge → auto-deploy 3 min |
| **`GEOAPIFY_API_KEY` отсутствует на VPS** | ❌ **operational fix** | См. секцию 2 ниже |
| **Admin UAT Phase 6.3 (после #67 + VPS env fix)** | pending | Per PR #67 описание — reset тестового tid → онбординг → ожидание Sassy reply-kb prompt + geo-pin finalize |
| **p95 benchmark Phase 6.3 цепочки** | pending | С VPS, persistent psycopg2 |
| **Phase 6.4** (decommission n8n 02.1_Location + canary cleanup) | pending | Не раньше 3-5 дней stability 6.3 |
| **`\\n` literal fix в onboarding.msg_trial_*** | pending | Отдельный PR (не Phase 6 scope, lesson другого агента busy-volhard) |

### Активные канарейки / cutover flags

```sql
SELECT key, value FROM app_constants WHERE key LIKE 'dispatcher_python_%' OR key LIKE 'handler_%_use_python';
-- dispatcher_python_authoritative          = true
-- dispatcher_python_authoritative_admin_only = false  (✅ снята 13.05, PR #60)
-- dispatcher_python_shadow_mode            = true
-- handler_location_use_python              = true
-- handler_menu_v3_use_python               = true
-- handler_onboarding_use_python            = true
```

### Mig HEAD на проде = **215** (+ applied 210 в gap)

Файл `migrations/210_phase6_3_geo_pin_python.sql` в `origin/main` (от PR #66 merge). На диске: 210/211/213/214/215 (gaps: 212/216+).

---

## 2. КРИТИЧНЫЙ Operational Item — добавить `GEOAPIFY_API_KEY` на VPS

**Текущее состояние** (verified через SSH):
```bash
ssh root@89.167.86.20 'grep -c ^GEOAPIFY /home/taskbot/noms/.env'
# → 0  (ключа НЕТ)
```

**Симптом в логах**:
```
2026-05-14 10:26:08 [noms.services.geolocation] ERROR: GEOAPIFY_API_KEY not set — reverse_geocode disabled
2026-05-14 10:26:08 [noms.handlers.location] INFO: geo_pin Geoapify no match tid=786301802 ... — fallback to picker
```

**Как исправить:**

1. Достать ключ из n8n credential «Geoapify» (UI: SSH-туннель `ssh -L 5678:127.0.0.1:5678 root@89.167.86.20`, открыть `http://localhost:5678/credentials` → «Geoapify» → reveal API key).
   - Альтернатива: посмотреть SQLite n8n credentials прямо (зашифровано — лучше через UI).
   - Альтернатива: попросить тимлида прислать ключ.
2. Добавить в VPS `.env`:
   ```bash
   ssh root@89.167.86.20 'echo "GEOAPIFY_API_KEY=<actual-key>" >> /home/taskbot/noms/.env'
   ```
3. Restart **оба** сервиса (cron остаётся со старым env иначе):
   ```bash
   ssh root@89.167.86.20 'systemctl restart noms-webhooks noms-cron'
   ```
4. Verify через 60s:
   ```bash
   ssh root@89.167.86.20 'journalctl -u noms-webhooks --since "1 min ago" | grep -E "GEOAPIFY|geocoding"'
   # Не должно быть "GEOAPIFY_API_KEY not set"
   ```

**Без этого fix** geo-pin продолжит graceful fallback на manual picker. Functional, но без UX-преимущества Phase 6.3.

---

## 3. UAT-loop Phase 6.3 (после PR #67 merge + VPS env fix)

Тимлид сообщил 5 проблем:

| # | Bug | Status |
|---|---|---|
| 1 | One Menu нарушен (2× "Choose your country") | ✅ Fixed in PR #67 (one_time_keyboard:true → Telegram сам hides reply-kb после клика, нет дублей) |
| 2 | «Choose your country:» EN literal | ✅ Fixed in PR #67 (`_resolve_ask_country_text` direct array access + random.choice) |
| 3 | Точка «·» лишняя | ✅ Fixed in PR #67 (carrier удалён, one_time_keyboard заменяет) |
| 4 | После geo-pin приходит country picker (не finalize) | ⚠️ Geoapify fallback **из-за missing VPS env** — fix в секции 2 |
| 5 | «Нет reply-kb» (UAT screenshot 10:24) | ✅ Был следствием #1+#2 (handler упал на fallback path, не построил reply-kb с правильным text). Fixed by PR #67 |

**После merge PR #67 + VPS env fix, ожидаемый UAT (test-user 786301802 или 417002669):**

```sql
SELECT public.reset_to_onboarding(<tid>);  -- очистить test user
```

1. `/start` → онбординг → biometry → phenotype quiz → completion → entering `status='onboarding:country'`.
2. **Ожидание**: 1 сообщение с **merged Sassy text** (один из 3 RU variants, например «Я умею отличать хамон от докторской колбасы... Жми 📍 внизу или выбери страну из списка»). Снизу — reply-kb с двумя кнопками: [📍 Отправить местоположение] + [Выбрать из списка].
3. **Path A** — click 📍 + Spain coords:
   - Geoapify reverse → ES/Europe/Madrid → `_finalize_with_timezone` → onboarding_success.
   - Stickered Sassy completion + main reply-kb (registered user state).
   - Reply-kb сама исчезает (one_time_keyboard).
   - **Не должно быть** «·» точек.
4. **Path B** — click «Выбрать из списка»:
   - reply-kb hides (one_time_keyboard).
   - Inline-picker стран с пагинацией.
   - User выбирает страну (или ZZ) → loc_country_<CC> callback → standard Phase 6.1 path.

---

## 4. Phase 6.4 — план (pending, не раньше 3-5 дней stability)

### Что декомиссионируется

1. **n8n workflow `02.1_Location`** (`workflowId=7EqiiwUwlGs7dcHT`):
   - Деактивация через SQLite UPDATE (n8n self-hosted API 403 на /deactivate, lesson Phase 4 gotcha #4):
     ```bash
     ssh root@89.167.86.20 'sqlite3 /home/noms/n8n/data/database.sqlite \
       "UPDATE workflow_entity SET active=0 WHERE id=\"7EqiiwUwlGs7dcHT\""'
     ```
   - Safety net 3-5 дней.
   - После этого — `DELETE` через n8n API (этот endpoint работает).
2. **n8n `01_Dispatcher` cleanup**:
   - Удалить `Prepare for 05` Set-ноду (проксировала 9 полей в 02.1_Location).
   - Удалить branch Route Classifier который шёл на `executeWorkflow → 02.1_Location`.
   - Удалить мёртвый `02_Continue Onboarding` executeWorkflow.
   - Использовать Safe PUT recipe (`n8n-data-flow-patterns.md`) для workflows >50KB.
3. **VPS / `.env`**:
   - **Не** удалять `GEOAPIFY_API_KEY` (Python authoritative продолжает использовать).
4. **БД cleanup**:
   - `DELETE FROM app_constants WHERE key='dispatcher_python_authoritative_admin_only'` (canary удалена 13.05, см. PR #60).
   - `DROP FUNCTION get_dispatcher_flags` rewrite — убрать поле `authoritative_admin_only` из RPC return (Python уже игнорирует через `result.get()`).
5. **KB updates**:
   - `architecture-registry.md` — переключить `location` на «Python authoritative» (везде).
   - `phase6-location-migration-plan.md` — добавить completion notes.
   - Новая статья `concepts/phase6-decommission-summary.md` — lessons learned.
   - `n8n-route-classifier-edit-loc-patch.md` — отметить «REMOVED 2026-05-13».

### Ожидаемый effort Phase 6.4

~0.5 дня — основная работа уже сделана.

### Опционально для тимлида

После 6.4 — рассмотреть **Phase 7** (Add food / AI Engine / Payment migration с n8n в Python).

---

## 5. Архитектурные знания (для preserve)

### Canonical Hybrid two-state pattern (Phase 6.3)

Полная статья: [[concepts/canonical-hybrid-location-picker]]. TL;DR:
- **Default state**: 1 sendMessage с merged Sassy text + ReplyKeyboardMarkup [📍 request_location:true, 📋 text-button], **`one_time_keyboard:true`** (Telegram сам hides после first action — никаких ручных ReplyKeyboardRemove).
- **List state**: триггер reply-text matching `buttons.manual_list` → router section 10.4 synth `cmd_list_countries` → handler рендерит inline-picker (без carrier, kbd уже скрыта).
- **Geo-pin path**: handler перехватывает `message.location` → Geoapify reverse → `_finalize_with_timezone` (Phase 6.2 branch is_edit) → onboarding_success.

### Handler-side intercept by screen_id (Phase 6.3)

`handlers/onboarding_v3._envelope_from_rpc_result` после получения result от `process_onboarding_input` проверяет `result.screen_id`:
- `'onboarding_country_picker'` → делегирует в `handlers.location._render_geo_request_prompt`.
- `'onboarding_timezone_picker'` → `handlers.location._render_timezone_picker`.

SQL render_screen не умеет строить custom reply-kb с `request_location:true`. Решение — Python intercept по screen_id. **Text всё ещё из БД** (`onboarding.ask_country`), layout — Python.

### `_resolve_ask_country_text` pattern (PR #67 hotfix)

`_lookup_translation` фильтрует не-str (для compat с историческими string-only translations). Для JSONB-array нужен **прямой доступ** к `ctx.translations.onboarding.ask_country`:

```python
node = ctx.translations.get("onboarding", {}).get("ask_country")
if isinstance(node, list) and node:
    import random
    text = random.choice(node)
```

Если будут другие JSONB-array translations (например `ask_timezone` тоже array), нужен **generic `_lookup_translation_with_variants`** helper.

### Setters ≠ FSM (Phase 6.2)

Для финала edit-flow: `set_user_country` + `set_user_timezone` + `clear_editing_state` (3 RPC). НЕ `set_user_location(..., 'registered')` (смешивает data + FSM transition; допустимо для онбординга, не для edit). KB [[concepts/headless-fsm-vs-dynamic-handler-separation]].

### Stale-base recipe (Phase 6 + другие)

Перед любым `CREATE OR REPLACE FUNCTION` на функцию >50 LOC: `pg_get_functiondef('public.<name>(<types>)'::regprocedure)` ЖИВОГО прода в момент apply — НЕ git-файл, НЕ snapshot из памяти. KB [[concepts/safe-create-or-replace-recipe]].

### Pre-mig number check (lesson 11.05)

Перед `git push` миграции **обязательно** `git fetch origin main && ls migrations/` + `gh pr list --state open`. Параллельные агенты могут забронировать тот же номер. Lesson: коллизия mig 200 (sticker vs phenotype) 11.05. Mig 210 в Phase 6.3 — был gap-номер (заняты были 209, 211, 213-215).

### Subagent для крупных миграций (per тимлид)

При >200 LOC SQL или >100 LOC multi-block migrations — spawn `general-purpose` subagent с **детальным brief** (NLM-first, no-hardcode, single-brace icons, JSONB array variants APPEND ≠ REPLACE, stale-base recipe). После — **обязательно** main-agent review через `diff` + spot-check. **Lesson 14.05**: subagent написал технически корректный SQL, но я **не проверил Python-side handling** новый screen_id ДО psycopg2 apply. Audit после apply обнаружил отсутствие обработки → preemptive rollback Block D → реализован Python intercept → re-apply. **Pattern**: после `subagent SQL ready`, до `psycopg2 apply`, **обязательно grep по Python** на ссылки на новый screen_id / RPC name.

---

## 6. Tools & access (повторяю для удобства)

### psycopg2 (canonical для миграций)
```python
import psycopg2, os
from dotenv import load_dotenv
load_dotenv('/Users/vladislav/Documents/NOMS/.env')
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
```
**Read-only** — agent autonomy. **Mutating** — тимлид дал явное разрешение в моей сессии (передаётся по handover).

### NLM
```bash
source /Users/vladislav/Documents/NotebookLM+Claude/plugins/notebooklm-rag/.venv/bin/activate
notebooklm ask "вопрос" -n fa75f4de-96c2-4dc0-bc9d-0bf07bd992f5 --json
```

### gh CLI
```bash
gh pr list --state open
gh pr view 67  # см. PR описание + статус
gh pr merge 67 --merge  # обычно тимлид сам, но можно через API workaround если 'main' busy in worktree
gh api -X PUT repos/sharkovvlad/noms-bot/pulls/67/merge -f merge_method=merge
gh run watch --repo sharkovvlad/noms-bot  # watch deploy
```

### SSH к VPS
```bash
ssh root@89.167.86.20 'journalctl -u noms-webhooks --since "10 min ago" | grep "tid=786301802"'
ssh root@89.167.86.20 'KEY=$(grep N8N_TARGET_API_KEY /home/noms/n8n/compose/.env | cut -d= -f2); curl -s -H "X-N8N-API-KEY: $KEY" http://127.0.0.1:5678/api/v1/workflows/7EqiiwUwlGs7dcHT'
```

---

## 7. Стартовый промт для тебя (агента-преемника)

```
1. Спот-check (5 минут):
   - psycopg2: app_constants flags + mig HEAD (ls migrations/).
   - gh pr list --state open (есть ли PR #67 открыт ещё?).
   - ssh root@VPS 'grep -c ^GEOAPIFY /home/taskbot/noms/.env' → 0 значит env ещё не добавлен.
   - journalctl --since "10 min ago" | grep tid=786301802 (последняя UAT активность).

2. Спроси тимлида:
   - PR #67 merged? Если нет — нужен ли мой review/правки?
   - Можно ли добавить GEOAPIFY_API_KEY в VPS .env (либо ключ от тимлида,
     либо доступ к n8n credential UI для извлечения)?
   - UAT Phase 6.3 (после env fix) — когда удобно прогнать?

3. Если PR #67 merged + GEOAPIFY env добавлен → отслеживай UAT.
   Если UAT pass → начинай планирование Phase 6.4 (~0.5 дня effort).

4. Если в UAT обнаружится новый bug — диагностика через journalctl tid=<test_tid>
   + psycopg2 spot-check translations/ui_screens.
```

---

## 8. Что точно НЕ делать

⛔ Не удалять `migrations/210_*.sql` (он уже в main).
⛔ Не удалять `GEOAPIFY_API_KEY` env с VPS — Phase 6.4 предполагает что Python путь продолжает использовать.
⛔ Не делать manual UPDATE прод-юзеров для «починки» — pattern half-measure (lesson Phase 4 gotcha #24). Используй `reset_to_onboarding(<tid>)` для catch-up.
⛔ Не trigger'ить Phase 6.4 раньше 3-5 дней stability 6.3 — нужен ровно safe rollback window.
⛔ Не флипать feature flag без explicit approval тимлида (правило handover §5 ranks).
⛔ Не trust subagent SQL output без grep по Python codebase на новые screen_id / RPC name (lesson 14.05).

---

## 9. Контакт

Тимлид: `sharkov.vlad@gmail.com`. Telegram admin chat_id=417002669 (Test user tid=786301802 тоже его). Бот `@nomsaibot`. VPS `root@89.167.86.20`.

Если в процессе обнаружишь что-то важное — сообщай явно с цитатой кода / логов. Тимлид ценит «информацию с полей».

Удачи! 🚀
