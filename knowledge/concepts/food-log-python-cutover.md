---
title: "Food Log Python Cutover (Stage 7a) — confirmation rendering migration"
aliases: [food-log-cutover, stage-7a, food-log-python, pr-abc-food-log, food-log-render-endpoint]
tags: [python-cutover, food-log, n8n-migration, architecture, stage-7a]
sources:
  - "daily/2026-05-20.md"
created: 2026-05-20
updated: 2026-05-20
---

# Food Log Python Cutover (Stage 7a)

Миграция рендеринга food-log confirmation screen из n8n `03_AI_Engine` → Python `handlers/food_log.py`. Первый **callback endpoint n8n→Python** в кодовой базе NOMS. 4-PR phased cutover + 5 runtime iterations при live debug.

## Key Points

- **3-PR plan + 1 follow-up PR** (PR A #129 SQL, PR B #130 Python handler, PR C #131 n8n wiring + flag flip, PR D #138/#141 polish). Phased cutover по образцу Stage 6 (payment).
- **Первый internal callback endpoint:** `POST /internal/food_log/render` — n8n вызывает Python для рендеринга, не наоборот. Security: token-protected (`FOOD_LOG_RENDER_TOKEN`), 503 без токена.
- **Dumb Renderer pattern:** Python выбирает template по boolean `hide_mana_block` из RPC, подставляет готовый `streak_message` из SQL, маршаллит items — никакой бизнес-логики в renderer'е.
- **5 n8n runtime iterations** после flag flip (Switch false-routing, ECONNREFUSED Docker, wrong field refs, sticker не удаляется, title colon missing). Каждая — surgical n8n PUT + verify.
- **Feature flag:** `app_constants.handler_food_log_use_python` (DB-backed, hot-reload 60s). n8n `Is Python Renderer?` IF-node reads from trigger payload constants (не SQL hit per request).

## Details

### Архитектура

```
Food photo/text/voice → n8n 03_AI_Engine → GPT-4o parse → RPC log_meal_transaction
    ↓ (RPC returns: calories, macros, streak, mana, items)
    ↓
Is Python Renderer? (IF: constants.handler_food_log_use_python == 'true')
    ├─ TRUE → Build Python Payload (Set) → POST /internal/food_log/render (HTTP)
    │         ↓ Python handler:
    │         1. Select template (with_mana / no_mana)
    │         2. Format items list
    │         3. Build inline keyboard (cmd_edit_last / cmd_delete_last)
    │         4. Delete thinking sticker
    │         5. Send via _send_and_persist (one-menu pattern)
    └─ FALSE → Build Gamification Reply (legacy JS) → Send Telegram (legacy)
```

### PR A — SQL foundation (mig 287)

- 2 confirmation templates × 13 langs: `food_log.confirmation_text_{with,no}_mana`
- Bilingual macro markers: P/F/C → Б/Ж/У (RU), Б/Ж/В (UK), B/T/W (PL), E/F/K (DE), etc.
- Icon changes: 🥩→💪 (inclusive proteins), 🥖→🌾 (inclusive carbs), 🧪→🔋 (mana intuitive)
- `log_meal_transaction` extended: +5 fields (`mana_max`, `subscription_status`, `hide_mana_block`, `language_code`, `input_source`)
- New daily line: `🎯 Daily left: N kcal` (uses existing `remaining_daily_calories`)

### PR B — Python handler + endpoint

- `handlers/food_log.py` (287 LOC): render function, NOT standard `handle_xxx(update, ctx, decision)` — entry point is HTTP endpoint from n8n callback
- `webhook_server.py:1288`: `POST /internal/food_log/render` with `X-Food-Log-Render-Token` header check
- 19 test cases: template selection, input-icon mapping, items formatting, HTML-escape, streak passthrough

### PR C — n8n wiring + cutover

- `tools/_n8n_03_ai_engine_modify.py` (273 LOC): reproducible JSON surgery script, idempotent
- 4 new n8n nodes: `Fetch Food Log Flag` (removed v2) → `Is Python Renderer?` → `Build Python Payload` → `POST Food Log Render`
- VPS deploy: `FOOD_LOG_RENDER_TOKEN` in both `.env` files (FastAPI + Docker n8n), `docker compose up -d --force-recreate`
- **Flag flip: 2026-05-20 15:34:44 MSK** — cutover live

### PR D — 5 runtime iterations

| iter | Bug | Root cause | Fix |
|---|---|---|---|
| v1 | Switch always FALSE | Supabase REST GET for flag returned wrong value | Read from `constants.*` in trigger payload instead |
| v2 | ECONNREFUSED | `127.0.0.1:8443` = container loopback, not host | URL → `172.18.0.1:8443` (Docker bridge gateway) + systemd drop-in override bind `0.0.0.0` |
| v3 | Empty items / 0 calories | Field refs `total_kcal`/`items_for_display` wrong (guessed) | Verified live exec: real fields `total.calories`, `items` |
| v4 | Thinking sticker stays | `POST Food Log Render` was terminal in n8n | Python owns delete: payload includes `thinking_sticker_message_id`, handler deletes before send |
| v5 | Title without `:` | Single-item `count_suffix` empty, no colon | Mig 293: append `:` after `{count_suffix}` × 13 langs |

### Architectural decisions

**Why callback endpoint, not forward-to-handler:**
- `03_AI_Engine` stays in n8n (GPT-4o Vision pipeline — Stage 7 full migration is separate)
- Only **confirmation rendering** moves to Python (dumb-renderer pattern)
- n8n does business logic (AI parse + log_meal_transaction), Python does presentation

**Why `constants.*` from payload, not SQL hit:**
- Тимлид-замечание #2: «Python должен прокидывать флаг через payload, n8n не должен лезть в БД»
- Pragmatic compromise: food log goes through legacy `forward_to_n8n` (raw body), not enriched payload — `01_Dispatcher` Prepare Data 03 already injects 305 constants including the flag
- n8n reads flag from trigger payload, zero additional SQL

**Sticker delete ownership:**
- n8n `$('Send Thinking Sticker').first()` doesn't resolve from Python branch (cross-branch scope rules)
- Python handler receives `thinking_sticker_message_id` in payload → fire-and-forget `deleteMessage` before send

### Legacy callback routing (PR D)

Initial keyboard used `food_log:edit:{meal_id}` / `food_log:delete:{meal_id}` callbacks — these had no routing rule in `dispatcher/router.py`, fell through to AI Engine → `errors.ai_failed` response. Fixed by switching to legacy `cmd_edit_last` / `cmd_delete_last` (wired through `_global_floating_actions` virtual screen in mig 209/211).

Tradeoff: meal_id precision lost (RPC hits «last meal today»). Acceptable for 99.9% use case — кнопки появляются сразу под залогенным meal'ом.

### n8n cross-branch scope rule (lesson)

`$('Node').first()` в n8n is **branch-scoped** — cross-branch references silently return empty/undefined, not error. Symptom: downstream node doesn't fire or fires with garbage data. Workaround: pass needed fields through Build Payload Set node.

### Gotchas

- **Docker bridge networking:** `127.0.0.1` inside container = container's own loopback. Use bridge gateway IP `172.18.0.1`. External port blocked by Hetzner Cloud Firewall → `0.0.0.0` bind safe. See [[concepts/docker-bridge-networking-pattern]].
- **systemd drop-in override:** main unit file can revert after deploy. `/etc/systemd/system/X.service.d/override.conf` survives. See [[concepts/systemd-dropin-override-pattern]].
- **3 migration collisions in one day:** mig 290→292, mig 292→293. pre-push hook + sanity audit caught both.

## Deployment checklist (reusable for future n8n→Python callbacks)

1. `RENDER_TOKEN` в обоих `.env` (FastAPI + Docker compose)
2. Docker recreate (`docker compose up -d --force-recreate`)
3. `systemctl restart noms-webhooks noms-cron` (оба)
4. Endpoint smoke: 403 (no token), 403 (wrong), 400 (valid + `{}`)
5. n8n PUT: add IF switch + Build Payload + HTTP Request nodes
6. Flag flip в `app_constants` → monitor journalctl 5 min
7. Rollback: `UPDATE app_constants SET value='false'` (hot-reload 60s)

## Open follow-ups (после 7+ дней stable)

- Sage dynamic `noms_comment` (LLM flash $≤0.01/req)
- Level-up event с GIF/sticker
- XP consolidation (70+50→120)
- Phase 4 n8n cleanup: remove legacy `Build Gamification Reply` chain
- Extract 💪/🌾/📊/🎯/🌟 в `app_constants`

## Related Concepts

- [[concepts/architecture-registry]] — food_log rendering теперь Python authoritative
- [[concepts/phase2-python-menu-v3]] — аналогичный cutover pattern для menu_v3
- [[concepts/docker-bridge-networking-pattern]] — container→host loopback gotcha (v2 fix)
- [[concepts/systemd-dropin-override-pattern]] — persistent bind change (v2 fix)
- [[concepts/claim-vs-check-idempotency-anti-pattern]] — related idempotency lesson
- [[concepts/variant-b-cutover]] — общий паттерн n8n→Python staged rollout
- [[concepts/save-bot-message-contract]] — one-menu pattern preserved через `_send_and_persist`
- [[concepts/headless-button-creation-gotchas]] — gotcha 4 (meta copy) при переиспользовании `cmd_edit_last`

## Sources

- [[daily/2026-05-20.md]] — PR A (#129 mig 287): translations + RPC extend. PR B (#130): Python handler + endpoint. PR C (#131): n8n wiring + flag flip 15:34:44 MSK. PR D (#138/#141): 5 runtime iterations (Switch false-routing, ECONNREFUSED Docker, wrong fields, sticker delete, title colon). Cutover trilogy + polish = 4 PRs merged, 25 tests, 678 suite green.
