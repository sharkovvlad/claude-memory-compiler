# Handover: PR B — Python food log handler (post-mig 287)

> **Дата:** 2026-05-20.
> **Создан:** агентом mig 287 (UX redesign Phase 1).
> **Адресат:** агент следующей сессии (либо я-же при возврате), который реализует Phase 2 — `handlers/food_log.py` + `POST /internal/food_log/render` endpoint.
> **Статус Phase 1:** [PR #129](https://github.com/sharkovvlad/noms-bot/pull/129) open, CI green. Ждёт merge перед стартом PR B.
> **План:** `/Users/vladislav/.claude/plans/sharded-swinging-parnas.md` (utvrjon owner'ом).

---

## TL;DR

В БД уже лежит **вся инфраструктура** для Python рендера экрана подтверждения food log:

1. **RPC `log_meal_transaction`** возвращает 5 новых полей (нет необходимости дополнительно вычислять что-либо в Python).
2. **Два полных шаблона** `food_log.confirmation_text_with_mana` / `_no_mana` × 13 langs — для **Dumb Renderer**.
3. **14 ключей** в namespace'ах `food_log.*` / `macros.*` / `gamification.*` готовы.
4. **App constants** обновлены (icon_carbs=🌾, icon_mana=🔋, icon_protein=💪 new).
5. **Cutover flag** `handler_food_log_use_python=false` (default) — UX не activates пока PR C не приземлится.

PR B = только **`handlers/food_log.py`** + **`POST /internal/food_log/render`** endpoint в `webhook_server.py`. Никакой SQL, никакого n8n.

---

## Архитектурное решение (locked by owner)

```
Telegram → n8n 03_AI_Engine (Vision/Transcribe — НЕ трогаем, остаётся в n8n)
            ↓ RPC log_meal_transaction (returns now включает hide_mana_block + ...)
            ↓ Switch node на $json.use_python_renderer (PR C добавит)
            ├─ false (default) → OLD: Build Gamification Reply (JS) → Send Telegram (legacy)
            └─ true → NEW: HTTP Request → POST /internal/food_log/render → Python
                                                                          ↓
                                                                handlers/food_log.py:render()
                                                                  - выбирает text_key по hide_mana_block
                                                                  - подставляет в шаблон
                                                                  - send_message + save_bot_message
```

**Dumb Renderer principle** (тимлид-уровне корректировка): Python НЕ принимает business decisions. Только:
- if/else на boolean `payload['hide_mana_block']` → выбор text_key.
- "\n".join(format_item(i)) — data marshaling для динамического списка items.
- input_icon lookup: `{'text': '⌨️', 'voice': '🎤', 'photo': '📸'}`.
- standard template substitution `{tr:...}`, `{icon_...}`, `{var}` placeholders.

---

## RPC `log_meal_transaction` contract (post-mig 287)

Return JSONB — все поля needed для рендера already there:

```json
{
  "success": true,
  "meal_id": "uuid",
  "items_count": 3,
  "xp_gained": 75,
  "xp_breakdown": {"base": 25, "streak_keep": 50, "day_closed": 0},
  "leveled_up": false,
  "old_level": 23, "new_level": 23, "level": 23,
  "mana_remaining": 1,
  "mana_skipped": false,
  "streak": 18,
  "streak_event": "kept",
  "streak_message": "🏆 Серия: 18 дн.",   // path 1: готовая локализованная строка (recommended for PR B)
  "day_closed": false,
  "meals_today": 3,
  "daily_consumed": 420,
  "daily_target": 2000,
  "remaining_daily_calories": 1580,
  "nomscoins": 200,
  // mig 287 new fields ↓
  "mana_max": 2,
  "subscription_status": "free",
  "hide_mana_block": false,                // ← Python: simple if/else на этот булев
  "language_code": "ru",
  "input_source": "voice"
}
```

**Streak handling:** consume `streak_message` (path 1, готовая строка). Это уже локализовано в RPC через mig 285 (`gamification.streak_kept` lookup + REPLACE `{streak}` placeholder). PR B agent **НЕ** нужно делать lookup самому — RPC сделал. Если `streak_event = 'same_day'` → `streak_message = ''` (skip rendering в pill).

---

## Templates (live in DB, 13 langs)

### `food_log.confirmation_text_with_mana` (free users)

```
{input_icon} <b>{tr:food_log.header_logged_word}{count_suffix}</b>

{items_block}

━━━━━━━━━━━━━━━
📊 <b>{tr:food_log.total_label}:</b> {total_kcal} {tr:food_log.kcal}
{icon_protein} {tr:macros.p_short}: <b>{protein}</b>{tr:food_log.unit_g}  ·  {icon_fat} {tr:macros.f_short}: <b>{fat}</b>{tr:food_log.unit_g}  ·  {icon_carbs} {tr:macros.c_short}: <b>{carbs}</b>{tr:food_log.unit_g}

🎯 {tr:food_log.remaining_label}: <b>{remaining_kcal}</b> {tr:food_log.kcal}

{noms_comment_block}🌟 +<b>{xp_gained}</b> {tr:gamification.points_label}  ·  {streak_message}  ·  {icon_mana} {tr:gamification.mana_label}: <b>{mana_current}/{mana_max}</b>
```

### `food_log.confirmation_text_no_mana` (premium/trial)

Идентичный, но без mana блока в конце:
```
... 🌟 +<b>{xp_gained}</b> {tr:gamification.points_label}  ·  {streak_message}
```

### Placeholders Python должен заполнить:

| Placeholder | Source | Пример |
|---|---|---|
| `{input_icon}` | static lookup по `input_source` | `⌨️` / `🎤` / `📸` |
| `{count_suffix}`| если `items_count > 1` → ` {count} {tr:food_log.header_text_multi_suffix}` иначе пустая строка | См. ниже |
| `{items_block}` | `"\n".join([f"{emoji} {name} ({portion}) — {cal} {tr:kcal}" for ...])` | Multi-line list |
| `{total_kcal}` | `sum(item.calories for item in items)` или `daily_consumed` ⚠ верифицировать какое | `420` |
| `{protein}`, `{fat}`, `{carbs}` | sum of items' macros | `12`, `18`, `42` |
| `{remaining_kcal}` | RPC `remaining_daily_calories` | `1580` |
| `{noms_comment_block}` | если Sage comment есть → `{tr:noms_comment_prefix} "{comment}"\n\n`, иначе пустая | `💬 Noms: "..."` |
| `{xp_gained}` | RPC `xp_gained` | `75` |
| `{streak_message}` | RPC `streak_message` (готовая строка) | `🏆 Серия: 18 дн.` |
| `{mana_current}`, `{mana_max}` | RPC `mana_remaining`, `mana_max` | `1`, `2` |
| `{tr:...}` | resolve через user's `language_code` + nested key path | `Записано` для `food_log.total_label` в ru |
| `{icon_protein/fat/carbs/mana}` | resolve через `app_constants` | `💪`/`🥑`/`🌾`/`🔋` |

⚠️ **`count_suffix` actual implementation:** проверь existing patterns в `handlers/payment.py` или `dispatcher/`. Скорее всего нужно ИЛИ переделать `header_logged_word` template с conditional ИЛИ использовать existing `header_text_single/multi` от mig 287 (он сохранил оба варианта).

⚠️ **Items emoji** для каждого item (☕/🥐/🥣 etc.) — в текущем n8n flow это AI определяет (Vision/Parse AI). PR B нужен этот emoji приходящим через payload от n8n callback. Проверь что n8n включает emoji в каждый item.

---

## Internal endpoint pattern

Скопировать с existing `POST /internal/stickers/reload` (`webhook_server.py:1017`):

```python
@app.post('/internal/food_log/render')
async def food_log_render_endpoint(request: Request):
    expected = os.getenv('FOOD_LOG_RENDER_TOKEN', '').strip()
    if not expected:
        raise HTTPException(status_code=503, detail='endpoint not configured')
    got = request.headers.get('X-Food-Log-Render-Token', '')
    if got != expected:
        raise HTTPException(status_code=403, detail='invalid token')
    payload = await request.json()
    result = await food_log_handler.render(payload)
    return result
```

**Token:** `FOOD_LOG_RENDER_TOKEN` в `/home/taskbot/noms/.env` на VPS (НЕ в git). После добавления — `systemctl restart noms-webhooks noms-cron`. n8n bumps на `http://127.0.0.1:8443/internal/food_log/render` (loopback, не через Caddy).

---

## Template substitution в Python

Project standard pattern — `{tr:...}`, `{icon_...}`, `{var}` placeholders. Look at:
- [[concepts/python-vs-n8n-template-grammar]] — KB для template grammar
- `_resolve_translation_with_variants` helper (упомянут в [[concepts/python-vs-n8n-template-grammar]])
- `dispatcher/` modules — examples how `v_user_context.translations` + `constants` consumed
- `handlers/payment.py:1` — full handler pattern (Stage 6 prior)
- `handlers/menu_v3.py`, `handlers/onboarding.py`, `handlers/location.py` — other Python authoritative handlers

Recommended: вызвать `render_screen` RPC если оно поддерживает custom context, **иначе** делать substitution в Python directly через `v_user_context.translations` + `constants`. **Проверь сначала** — Explore показал что render_screen signature `(p_telegram_id, p_screen_id)` без context. Если нет способа передать payload — Python делает substitution сам.

---

## Items list block — единственный data→string маршаллинг

```python
def format_item(item: dict, kcal_label: str) -> str:
    emoji = item.get('emoji', '🍽️')
    name = item['food_name']
    portion = item.get('portion', '')
    cal = item['calories']
    portion_str = f' ({portion})' if portion else ''
    return f'{emoji} {name}{portion_str} — {cal} {kcal_label}'

items_block = '\n'.join(format_item(i, kcal_label=tr.get('food_log.kcal','kcal')) for i in payload['items'])
```

Это **data → string**, не business logic. OK по Dumb Renderer rules.

---

## save_bot_message contract

После send_message — ОБЯЗАТЕЛЬНО:
- `users.last_bot_message_id = msg_id` (one-menu pattern)
- `save_bot_message` (или RPC equivalent) — для menu_v3 cleanup

Без этого reply-keyboard клик не удалит payment-style меню (см. [[concepts/save-bot-message-contract]]).

---

## Тестирование

### Local unit
- `tests/handlers/test_food_log.py::test_render_free_user_with_streak_kept`
- `tests/handlers/test_food_log.py::test_render_premium_skips_mana_block`
- `tests/handlers/test_food_log.py::test_render_same_day_skips_streak_message`
- Подходящий fixture pattern в `handlers/payment.py` tests.

### E2E (after deploy, flag=false → safe)
- Add endpoint to `tests/live/e2e_crawler.py` if needed.
- Manual test: curl loopback с правильным token → 200.
- Manual test: curl без token → 403.

### Cutover (in PR C session)
- Flag flip в `app_constants.handler_food_log_use_python = 'true'`.
- Watch `journalctl -u noms-webhooks -f | grep -i food_log` за 30 минут.
- При >2 errors / 5 min → flag в false.

---

## Open questions / unresolved

1. **`leveled_up` block** — в плане отложен в TODO (отдельное сообщение с GIF/sticker для дофамин-эффекта). В PR B: **игнорировать `payload['leveled_up']`** — не добавлять "Level X!" в pill. Реализация level-up event — отдельная сессия.

2. **XP consolidation** (70+50→120 единая цифра + Noms объяснит в шутке). В плане TODO — оставить `xp_gained` как есть (RPC уже консолидирует через `v_xp_total`), показать одно число.

3. **`spam_message`** — RPC может возвращать (XP soft cap). В Python нужно обработать или skip — спросить owner'а.

4. **Sage comment** — где сейчас приходит? n8n `Parse AI` нода уже генерирует или это отдельный LLM call? PR B agent должен проверить flow или просто ожидать `noms_comment` в payload и render если есть, skip если нет.

5. **`items` emoji** в payload — обеспечить что n8n callback включает emoji для каждого item (currently hardcoded в Parse AI node JS code).

---

## Owner-policy reminders

- **Snapshots:** per mig 286 owner-policy "snapshots dropped immediately, no backup tables created". PR B = код-only, snapshots не нужны.
- **Деплой:** auto через GitHub Actions при merge. НЕ `./deploy.sh` руками.
- **Rebase перед commit:** обязательно (`git fetch origin main && git rebase origin/main`).
- **Pre-push sanity:** `git diff origin/main..HEAD --stat` — caps diff scope.

---

## Связано

- [[handover/2026-05-20_streak_renderer_contract_for_03_AI_Engine_migration]] — streak contract (mig 285+286 agent)
- [[concepts/python-vs-n8n-template-grammar]] — template grammar (placeholders)
- [[concepts/save-bot-message-contract]] — one-menu pattern
- [[concepts/supabase-db-patterns]] — JSON patterns, mig 287 lesson about jsonb_set nested parents
- [[daily/2026-05-20]] — mig 287 entry (full context)
- `/Users/vladislav/.claude/plans/sharded-swinging-parnas.md` — full 3-PR plan
