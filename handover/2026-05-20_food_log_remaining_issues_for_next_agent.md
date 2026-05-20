# Handover: food log UX — remaining issues + TODO continuation

> **Дата:** 2026-05-20.
> **Создан:** агентом PR A/B/C/D (mig 287 / handlers/food_log.py / n8n surgery / mig 293).
> **Адресат:** агент следующей сессии, который продолжит ревизию + добивает TODO.
> **Статус инфраструктуры:** Food log Python cutover **LIVE с 17:15 MSK 2026-05-20**. PR #129/130/131/138 — все merged. Flag `handler_food_log_use_python=true`.

---

## TL;DR — что ещё расходится с ТЗ

После 4 PR'ов основной flow работает (Python branch активируется, items рендерятся, blockquote сворачивается на 5+ items, mana hide для premium). Но **2 issues** видны в live тестах 19:11 / 19:14:

1. **🔴 Sticker «думающего Номса» не удаляется.** Мой `POST Food Log Render → Delete Thinking Sticker` wire в n8n не сработал. Юзер видит **два сообщения**: первое — стикер (остаётся в чате), второе — Python-рендер.
2. **🔴 Streak block отсутствует.** Footer: `🌟 +0 очков  ·  ` (trailing `·`, серия не показана). Мой Python fallback (compose из `gamification.streak_kept` template) не активируется live.

Owner-просьба: **сравни рендер с ТЗ + найди причины** + если есть контекст — внедри что-то из TODO списка.

---

## Каноническое ТЗ — то к чему стремимся

Original owner-task (полный текст в `/Users/vladislav/.claude/plans/sharded-swinging-parnas.md`):

```
╭─ 💬 NOMSaibot ─────────────────────────────╮
│ {icon} Записано:                            │
│                                             │
│ ☕️ Кофе с молоком (250ml) — 50 ккал         │
│ 🥐 Круассан (80g) — 320 ккал                │
│                                             │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━                 │
│ 📊 Записано: 370 ккал                       │
│ 💪 Б: 12г  | 🥑  Ж: 18г  | 🌾  У: 42г       │
│                                             │
│ 🎯 Остаток на день: 1 250 ккал              │
│                                             │
│ 💬 Noms: "Кофе с круассаном? Парижский      │
│ вайб засчитан! Но углеводов мы бахнули      │
│ прилично, на ужин лучше поискать стейк."    │
│                                             │
│ 🌟 +25 очков | 🔥 Дней в ударе: 3 | 🔋 Мана: 1/2
╰─────────────────────────────────────────────╯
[ ✏️ Изменить ]  [ 🗑 Удалить ]
```

**Требования из ТЗ (полный чек-лист):**
- ⌨️ `{icon}` зависит от input: 📸 фото, 🎤 голос, ⌨️ текст. ✅ работает.
- 🥩→💪 (белок), 🥖→🌾 (углеводы), 🥑 оставляем (жиры). ✅ работает.
- Б/Ж/У (RU) + P/F/C (EN) буквенные префиксы. ✅ работает.
- "Итого" → "Записано". ✅ работает.
- "XP" → "очков". ✅ работает.
- 🧪 → 🔋 для маны. ✅ работает.
- Mana hidden для premium/trial. ✅ работает.
- Уровень убран из этого экрана (отдельный level-up event с GIF). ✅ работает (handler ignores `leveled_up`).
- XP консолидация (70+50→120). ❌ НЕ реализована (RPC возвращает raw + xp_breakdown, Python показывает `xp_gained`).
- 🎯 Остаток на день. ✅ работает (через RPC `remaining_daily_calories` → payload `remaining_kcal`).
- 💬 Noms комментарий (Sage dynamic). ❌ НЕ реализован (placeholder skipped когда `noms_comment=null`).
- Mana onboarding в 3 касания. ❌ НЕ реализован.

**Тестовые рендеры (live 19:11, tid=786301802):**

```
[19:11] NOMSaibot: <thinking sticker>     ← НЕ УДАЛЁН ❌
[19:11] NOMSaibot:
⌨️ Записано:                              ✅
🍟 Картошка фри (150g) — 365 ккал         ✅
━━━━━━━━━━━━━━━
📊 Записано: 365 ккал                     ✅
💪 Б: 4г  ·  🥑 Ж: 18г  ·  🌾 У: 49г       ✅
🎯 Остаток на день: 1685 ккал              ✅
🌟 +0 очков  ·                            ❌ streak missing, trailing `·`
```

5-item test (19:14, tid=786301802): blockquote expandable работает ✅.

---

## Issue #1: Thinking sticker не удаляется

### Что я сделал

В `tools/_n8n_03_ai_engine_modify.py` v5 добавил connection:
```python
connections['POST Food Log Render'] = {
    "main": [
        [{"node": "Delete Thinking Sticker", "type": "main", "index": 0}]
    ]
}
```

PUT'нул workflow. GET verified connection wired. Но в live тесте sticker остаётся.

### Гипотезы для diagnosis

1. **Connection wired, но Delete node не выполняется** — Switch routed correctly, POST succeeded, но Delete не запустился. Pull последнее execution и проверь `runData['Delete Thinking Sticker']`.

2. **Delete node выполняется, но ловит wrong message_id**. Node body:
   ```json
   "jsonBody": "={ \"chat_id\": {{ $('Execute Workflow Trigger 03').item.json.telegram_id }}, \"message_id\": {{ $('Send Thinking Sticker').first().json.message_id || 0 }} }"
   ```
   `$('Send Thinking Sticker')` ссылается на upstream node. В Python branch путь:
   `Send Thinking Sticker → Switch router → Parse AI → ... → RPC Log Meal → Check RPC Result → Is Python Renderer? (true) → Build Python Payload → POST Food Log Render → Delete Thinking Sticker`.
   Может ли `$('Send Thinking Sticker').first()` не возвращать данные если path прошёл через branch который не include'ает Send Thinking Sticker как direct ancestor?

3. **POST Food Log Render возвращает HTTP error** → Delete не запускается (n8n stops on error в default mode). Maybe Python returns 200 OK but n8n считает что error.

4. **Timing race** — Python отправляет new message → save_bot_message обновляет `users.last_bot_message_id` на новое сообщение → n8n Delete сразу после удаляет sticker — но `last_bot_message_id` уже изменён. Это unlikely (Delete использует sticker's message_id, не last_bot_message_id).

### Recommended diagnosis sequence

```bash
# Pull latest execution (тестовый run от owner)
ssh root@89.167.86.20 'sqlite3 /home/noms/n8n/data/database.sqlite "SELECT id, status, datetime(startedAt) FROM execution_entity WHERE workflowId='\''kjw4kkKMD0IqNALg'\'' ORDER BY startedAt DESC LIMIT 3"'

# Pull execution_data for latest
ssh root@89.167.86.20 'sqlite3 /home/noms/n8n/data/database.sqlite "SELECT data FROM execution_data WHERE executionId=<latest>"' > /tmp/exec.txt

# Parse runData — что выполнялось:
python3 <<EOF
import json
d = json.loads(open('/tmp/exec.txt').read().strip())
def resolve(ref):
    if isinstance(ref, str) and ref.isdigit() and int(ref) < len(d): return d[int(ref)]
    return ref
rundata = resolve(d[2].get('runData'))
print('nodes that ran:', list(rundata.keys()))
# Check if Delete Thinking Sticker is there
EOF
```

If `Delete Thinking Sticker` in runData → check its error/output.
If NOT in runData → connection не fires (POST Food Log Render must succeed first).

### Quick fix ideas

- **Move Delete Thinking Sticker inside Python handler** — handler сам делает Telegram `deleteMessage` через `_telegram_post`. Передаём sticker message_id через payload (`thinking_sticker_message_id` field). Чище: Python владеет всем ответом. Требует update payload в n8n + update handler + add Telegram API call.

- **n8n side: try `continueOnFail` на POST Food Log Render** — даже если POST вернёт error, Delete всё равно запустится. Quick patch.

---

## Issue #2: Streak block отсутствует

### Что я сделал

В `handlers/food_log.py` добавил fallback:
```python
streak_message = payload.get("streak_message") or ""
streak_num = payload.get("streak")
if not streak_message and isinstance(streak_num, int) and streak_num > 0:
    tmpl = _resolve_tr(ctx, _STREAK_FALLBACK_KEY, "🏆 Streak: {streak} days")
    streak_message = tmpl.replace("{streak}", str(streak_num))
```

`_STREAK_FALLBACK_KEY = "gamification.streak_kept"` — key есть в БД (mig 285) × 13 langs.

Footer template:
```
🌟 +<b>{xp_gained}</b> {tr:gamification.points_label}  ·  {streak_message}  ·  {icon_mana} ...
```

При `streak_message=""` (no fallback) → `🌟 +0 очков  ·    ·  ...` — два разделителя без content.

### Гипотезы для diagnosis

1. **payload['streak'] = 0 или missing** — пользователь tid 786301802 не имеет active streak. Логировал давно. `current_streak` в `users` table может быть 0 если он не логировался вчера.
   - Check: `SELECT current_streak FROM users WHERE telegram_id=786301802`
   - Если 0 → fallback корректно не активируется (мы НЕ показываем "Серия: 0 дн.").

2. **n8n payload не передаёт `streak` field** — проверь `Build Python Payload` node в n8n workflow. Сейчас payload включает `streak_message`, но НЕ `streak` integer. Этого не хватает для fallback.
   ```python
   # В tools/_n8n_03_ai_engine_modify.py:130 строка отсутствует:
   "streak": $('RPC Log Meal').item.json.streak || 0,
   ```
   **СКОРЕЕ ВСЕГО ЭТО И ЕСТЬ BUG**. RPC возвращает `streak` integer, но n8n не прокидывает его в payload.

3. **Template renders {streak_message} как пустую строку** — even если fallback engaged, possible regression в template substitution.

### Recommended fix

**Add `streak` field в Build Python Payload n8n node:**

В `tools/_n8n_03_ai_engine_modify.py:130` (или примерно):
```python
"  streak: $('RPC Log Meal').item.json.streak || 0,\n"
"  streak_message: $('RPC Log Meal').item.json.streak_message || '',\n"
```

Затем re-run script, PUT workflow.

После — verify в exec_data что `Build Python Payload` output содержит `streak: 18` (или другое actual value), и handler корректно composes streak block.

---

## Issue #3: Trailing `·` artifact

Даже если streak fallback fixed, остаётся **edge case**: premium user (hide_mana_block=true) видит template `_no_mana`:
```
🌟 +<b>{xp_gained}</b> {tr:gamification.points_label}  ·  {streak_message}
```

Если `streak_message` пуст (юзер без streak) → trailing `·`. Это **rendering issue** в template.

**Recommended:** post-render trailing `·` strip в Python handler.
```python
# В render_food_log_confirmation, после _resolve_text:
text = re.sub(r'\s+·\s*$', '', text, flags=re.MULTILINE)
text = re.sub(r'·\s*·', '·', text)  # collapse adjacent separators
```

ИЛИ четыре template variants (with_mana + with_streak / no_mana + with_streak / with_mana + no_streak / no_mana + no_streak). Overkill.

**Pragmatic:** Python regex post-process (~5 LOC). Не нарушает Dumb Renderer (это data → string cleanup, не business logic).

---

## TODO остатки (из original плана)

### High priority (UX-critical, нужно next session)

1. **Sage dynamic `noms_comment`** — LLM call (flash model, $≤0.01/req) с контекстом:
   - Состав текущего блюда
   - Остаток калорий на день
   - Текущее время суток
   - Optional: weight trend, current league, recent macro balance
   - Constraint: ≤150 символов, "Дерзкий Мудрец" tone, anti-shame.
   - Add field в n8n Build Python Payload: `noms_comment: <LLM response>`.
   - Add separate LLM node перед Build Python Payload OR call internal Python endpoint that wraps OpenAI flash.

2. **Level-up event с GIF/sticker** — отдельное сообщение когда `leveled_up=true`:
   - Sticker channel (см. [[concepts/sticker-architecture-adr]])
   - Picture: радостный Номстер + фейерверк
   - Caption: "УРОВЕНЬ {N} ДОСТИГНУТ! 🚀 Твой метаболический питомец стал ещё сильнее."
   - Triggered в Python handler ПОСЛЕ food log message (`asyncio.create_task` send sticker).
   - Хранить в `bot_stickers` table (как mig 198/201).

3. **XP consolidation 70+50→120** — Python composes single `xp_total` from `xp_breakdown`:
   ```python
   breakdown = payload.get('xp_breakdown', {})
   total_xp = sum(breakdown.values()) or payload.get('xp_gained', 0)
   ```
   Plus extend Sage comment template когда есть bonuses: `"+120 очков (включая стартовый бонус)"`.

4. **Mana onboarding в 3 касания** — контекстная Sage шутка при first log:
   - Touch 1: visual `🔋 1/2` (already in template).
   - Touch 2: при first log Sage explains: "Кстати, чтобы мои нейроны распознавали еду, мне нужна энергия (Мана). У тебя есть 2 бесплатных заряда в день."
   - Touch 3: при mana=0 → `error_no_mana` screen (already exists per [[concepts/no-mana-python-precheck]]).
   - Track в `users.mana_onboarding_shown jsonb` (similar to `stickers_shown`).

### Medium priority

5. **Phase 4 n8n cleanup** — после 7+ дней stable (~2026-05-27):
   - Удалить legacy `Build Gamification Reply` Code node
   - Удалить `Is Python Renderer?` Switch
   - Wire `Check RPC Result main[0]` direct в `Build Python Payload` (безусловный Python path)
   - Удалить legacy `Send Telegram` Telegram node (POST Food Log Render заменил)

6. **Tech debt: extract hardcoded emojis в `app_constants`** (mig'у можно):
   - 💪 → `icon_protein` (новая константа)
   - 🌾 → `icon_carbs` (уже есть как `icon_carbs='🌾'`)
   - 📊 → `icon_total`
   - 🎯 → `icon_target`
   - 🌟 → `icon_reward`
   - Затем templates use `{tr:...}` + `{icon_protein}` substitution.

### Low priority

7. **Edit/Delete callback handling** — кнопки уже работают (callback_data `food_log:edit:{meal_id}` / `food_log:delete:{meal_id}`), но как они роутятся? Скорее всего в menu_v3. Не trogал — out of scope этого session.

8. **End-to-end E2E test** добавить в `tests/live/e2e_crawler.py` — Telethon owner-only:
   - Send text food → assert reply contains new format (💪 / Б / Записано: / 🎯).
   - Premium account → assert no mana block.
   - 5-item input → assert blockquote wrapped.

---

## Runtime state (для disaster recovery)

⚠️ NOT in git. Из `daily/2026-05-20.md` секция PR D:

- **VPS `.env`** (двух мест) содержит `FOOD_LOG_RENDER_TOKEN=<64-char hex>`:
  - `/home/taskbot/noms/.env` (для noms-webhooks)
  - `/home/noms/n8n/compose/.env` (для n8n container env interpolation)
- **`/home/noms/n8n/compose/docker-compose.yml`** содержит `- FOOD_LOG_RENDER_TOKEN=${FOOD_LOG_RENDER_TOKEN}` в environment блоке n8n service.
- **`/etc/systemd/system/noms-webhooks.service.d/override.conf`** binds uvicorn на `0.0.0.0:8443`. Main unit `--host 127.0.0.1` остаётся (deploy.sh может revert через rsync — backups в `.bak.*`). Override persistent.
- **External port 8443** blocked by Hetzner Cloud Firewall.
- **n8n workflow ID `kjw4kkKMD0IqNALg`** (03_AI_Engine) — last modified via Safe PUT. Reproduce: `python3 tools/_n8n_03_ai_engine_modify.py` (idempotent).
- **Flag `handler_food_log_use_python='true'`** в app_constants. Rollback: SQL UPDATE='false'.

---

## Что я **не** сделал и почему

- **Не проверял execution data live тестов 19:11/19:14** — owner попросил закрыть session. Diagnosis оставлен next agent'у.
- **Не патчил n8n payload** на добавление `streak` field — это новая PUT и потенциальные новые iterations. Out of scope этой сессии.
- **Не реализовал Sage dynamic LLM** — требует отдельной сессии с promt engineering + LLM cost budgeting + integration.
- **Не реализовал level-up event** — требует sticker creation pipeline ([[concepts/telegram-sticker-pipeline]]) + Veo prompt + handler integration.

---

## Ключевые KB & files для next agent

### Read first
- `/Users/vladislav/.claude/plans/sharded-swinging-parnas.md` — original 3-PR plan + полное ТЗ.
- `claude-memory-compiler/daily/2026-05-20.md` — chronology всех PR'ов и iterations за сегодня.
- `claude-memory-compiler/handover/2026-05-20_streak_renderer_contract_for_03_AI_Engine_migration.md` — streak contract от mig 285 agent.

### Code references
- `handlers/food_log.py` — entry point `render_food_log_confirmation(payload)`. Streak fallback в lines ~141-148. blockquote logic в `_format_items_block`.
- `webhook_server.py:1288` — `POST /internal/food_log/render` endpoint.
- `tools/_n8n_03_ai_engine_modify.py` — reproducible n8n surgery script (v5). **PYTHON_ENDPOINT_URL = `172.18.0.1:8443`** (Docker bridge gateway, не container loopback).
- `tests/handlers/test_food_log.py` — 25 cases, fixture pattern.

### Concepts
- [[concepts/python-vs-n8n-template-grammar]] — template substitution (`{tr:...}`, `{icon_...}`, `{var}`).
- [[concepts/save-bot-message-contract]] — one-menu pattern, `last_bot_message_id`.
- [[concepts/n8n-data-flow-patterns]] — Safe PUT recipe для workflows >50 KB.
- [[concepts/architecture-registry]] — нужно добавить food log Python path + first n8n→Python callback pattern.
- [[concepts/no-mana-python-precheck]] — Strangler Fig pattern (precedent для food log split).

---

## Спасибо

Это была интересная сессия — 4 PR за день, 5 iterations runtime debug, 3 migration collisions с параллельными агентами. Pre-push hook + sanity audit реально работают.

Удачи! 🚀
