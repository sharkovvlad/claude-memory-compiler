---
title: "No-Mana Python Pre-check — Strangler Fig pattern"
aliases: [no-mana-precheck, mana-strangler-fig, voice-photo-mana-intercept]
tags: [architecture, python-cutover, mana, n8n-decommission, headless, strangler-fig]
sources:
  - "daily/2026-05-17.md"
  - "migrations/236_no_mana_python_precheck.sql"
  - "concepts/architecture-registry.md"
created: 2026-05-17
updated: 2026-05-17
---

# No-Mana Python Pre-check (Strangler Fig)

## TL;DR

Перехватываем case **voice/photo от registered юзера с mana_current=0** в Python `webhook_server.py:_try_authoritative_path` **ДО** forward в n8n `03_AI_Engine`. Рендерим headless экран `no_mana_exhausted` через `render_screen` RPC. Тяжёлая GPT-4o часть AI Engine остаётся в n8n для юзеров с mana > 0.

**Mig 236 (2026-05-17).** PR [#87](https://github.com/sharkovvlad/noms-bot/pull/87).

## Зачем

До mig 236 voice/photo с mana=0 уходил в n8n `03_AI_Engine.Send No Mana`:

1. **EN-литерал у не-EN юзера**: `gamification.no_mana` отсутствовал в БД во всех 13 языках → n8n expression `translations?.gamification?.no_mana || '⚡ No mana left today'` фолбэкал на хардкод.
2. **Литерал `{icon_premium}` на кнопке**: `payment.go_premium_button` во всех 13 языках содержит литерал `{icon_premium} Premium/Премиум`. n8n Telegram-нода НЕ интерполирует Python-style `{var}` — выводит as-is.

Оба бага одновременно ловил tid=786301802 16/5 18:51 (см. `daily/2026-05-17.md`).

## Архитектурный паттерн — Strangler Fig

Не мигрируем `03_AI_Engine` целиком — там сложная GPT-4o vision/voice логика. Вместо этого:

1. **Pre-check в Python** — самый узкий happy path (registered + mana=0) уходит в Python.
2. **n8n остаётся** для всех остальных кейсов (mana > 0 → AI распознавание; unregistered + mana=0 → Send No Mana CTA с `complete_profile_prompt`).
3. **Dead-код n8n не удаляем сразу** — после Python hook трафик туда перестаёт приходить, удаление отдельной сессией (Phase 6.4 cleanup).

Это безопаснее чем сразу деактивировать n8n ноды (riskier PUT, может сломать другие ветки).

## Реализация

### Pre-check в `webhook_server.py:_try_authoritative_path`

После всех существующих target-веток (`menu_v3`, `onboarding`, `location`, `restore_*`, `TARGET_TO_PATH`), ПЕРЕД fallthrough на legacy:

```python
if (
    target == "ai"
    and decision.reason == "food_media"
    and (ctx.status or "") == "registered"
    and (ctx.mana_current or 0) <= 0
):
    try:
        envelope = await _render_no_mana_envelope(ctx)
    except Exception:
        logger.exception(
            "AUTHORITATIVE no_mana render failed tid=%s — fall through to legacy",
            chat_id,
        )
        return False
    asyncio.create_task(_send_and_persist(envelope, chat_id))
    logger.info("AUTHORITATIVE_NO_MANA update_id=%s tid=%s mana=%s ...", ...)
    return True
```

### Helper

```python
async def _render_no_mana_envelope(ctx):
    from supabase_client import supabase
    from services.template_engine import render_envelope
    result = await supabase.rpc("render_screen", {
        "p_telegram_id": ctx.telegram_id,
        "p_screen_id": "no_mana_exhausted",
    })
    # parse list/dict, extract telegram_ui...
    return render_envelope(telegram_ui, ctx, screen_id="no_mana_exhausted")
```

### Headless экран `no_mana_exhausted`

- `render_strategy='delete_and_send_new'` — удаляет indicator-стикер, шлёт ответ.
- `text_key='gamification.no_mana'` — заполнен mig 236 для 13 языков Sassy-quality.
- 2 кнопки:
  - `buttons.recharge_mana` (текст уже содержит `⚡` — `icon_const_key=NULL`, без двойной иконки).
  - `buttons.go_pro_unlimited` (`icon_const_key='icon_stars'` → `⭐`). Паттерн mig 144.

**НЕ используем** `payment.go_premium_button` — содержит литерал `{icon_premium}` во всех 13 языках (системный баг, отдельная задача).

## Критичный design choice — нулевые лишние DB-запросы

`mana_current` уже в `ctx` (загружен из `v_user_context` на старте update'а). Pre-check — это **ровно одна** проверка в памяти. RPC `render_screen` вызывается **только** при срабатывании условия (cold path при mana=0), на горячем пути юзер с маной > 0 не платит ничего.

## Verification recipe

После mig 236:

```sql
-- Все 13 языков заполнены, нет литералов {icon_*}
SELECT lang_code, content #>> '{gamification,no_mana}'
  FROM ui_translations ORDER BY lang_code;

-- Smoke render
SELECT public.render_screen(786301802, 'no_mana_exhausted');
```

Через Python (см. `daily/2026-05-17.md` под секцией Session No-Mana):

```python
from dispatcher.context import UserCtx
from services.template_engine import render_envelope
ctx = UserCtx.from_row(row_from_v_user_context)
env = render_envelope(telegram_ui_from_render_screen, ctx, screen_id='no_mana_exhausted')
# Assert: text не содержит '{', buttons text не содержит '{icon_'
```

## Gotchas

- **Strategy `delete_and_send_new` требует `last_bot_message_id`.** Если NULL (например, юзер до этого не получал сообщений от бота) — `template_engine` degrade'ит на send-only, не падает. Документировано в `services/template_engine.py:render_envelope`.
- **Sticker как last_bot_message_id**. Indicator-стикер (думающий Номс) пишется в `users.last_bot_message_id` через `save_bot_message(p_message_type='sticker')`. `delete_and_send_new` его удалит — это желаемое поведение (стикер уже устарел к моменту no_mana ответа).
- **n8n не трогать.** После Python hook трафик в `Send No Mana` / `Send No Mana CTA` прекращается. PUT с удалением нод откладывается на Phase 6.4. Преждевременный PUT рискует сломать parallel ветки (Build Step Reminder + Is Registered (No Mana)).
- **Unregistered ветка**: остаётся в n8n (Send No Mana CTA с `messages.complete_profile_prompt`). Мig 236 НЕ покрывает unregistered — это сознательное сужение scope.

### Followup fix'ы (mig 237 + 238, 17.05 вечер)

**Mig 237 — NULL-safe mana regeneration.** `cron_regenerate_mana` WHERE содержал `(now() - mana_last_recharge_at) >= '12 hours'`. Для юзеров с `mana_last_recharge_at IS NULL` (созданных до bootstrap'а) выражение давало NULL → строка пропускалась навсегда. Fix: backfill NULL → NOW() + добавление `OR mana_last_recharge_at IS NULL` в WHERE. 1 affected юзер (tid=786301802). Паттерн: [[concepts/cron-silent-failure-alerting]] секция «Mana regeneration NULL-skip».

**Mig 238 — No-mana screen UX polish** (3 проблемы обнаружены после merge PR #87):
1. **Indicator-стикер race:** `maybe_send_indicator` fire-and-forget шлёт стикер **после** Python hook → `save_indicator_state` записывает mid ПОСЛЕ `render_screen` → `delete_and_send_new` бьёт по `last_bot_message_id` (предыдущее меню), а свежий стикер остаётся. Fix: early-return в `telegram_proxy.maybe_send_indicator` при `status='registered' AND mana_current<=0`. Устраняет race **в принципе** + улучшает UX (моментальный ответ без стикера).
2. **Recharge кнопка → INSUFFICIENT_COINS dead-end:** юзер с 70 nomscoins (cost=300) видел unhelpful error. Fix: `visible_condition` на кнопке через `(SELECT value::int FROM app_constants WHERE key='mana_recharge_cost_coins') <= u.nomscoins`. Safe default 999999 если конфиг сломан → кнопка скрыта.
3. **Layout:** кнопки 0/0 + 0/1 (один ряд) → 0/0 + 1/0 (вертикально, лучше читаемость).

`get_indicator_context` DROP+CREATE — добавлены `mana_current` и `subscription_status` в RETURNS TABLE (CREATE OR REPLACE не меняет shape). GRANT восстановлен.

**Lesson — fire-and-forget side-effects ломают delete-and-send-new:** если параллельно идёт fire-and-forget save (`save_indicator_state`), к моменту render `last_bot_message_id` устарел. Решения: (1) skip indicator для no-mana path (наш выбор); (2) explicit deleteMessage по indicator_message_id после render; (3) sync wait (теряет latency).

## Где это пригодится снова

Шаблон применим для **любого** pre-check'а, который должен перехватить вход юзера ДО forward в legacy n8n:

- Subscription expiry (mana=0 + subscription_status='expired') — отдельный экран с CTA.
- Quest gate (попытка логнуть еду до завершения квеста).
- Anti-spam (если за минуту >N логов — показать предупреждение перед AI вызовом).

Каждый раз:
1. Headless экран в `ui_screens` + кнопки в `ui_screen_buttons` (паттерн mig 144).
2. Helper `_render_<screen>_envelope(ctx)` в `webhook_server.py`.
3. Hook в `_try_authoritative_path` с условием по `ctx.<field>` (без новых DB-запросов).
4. n8n не трогать в той же сессии — пусть dead-код отлежится перед удалением.

## См. также

- `concepts/architecture-registry.md` — карта target → handler.
- `concepts/headless-architecture.md` — `render_screen` контракт.
- `concepts/checkmark-prefix-pattern.md` — рендер кнопок через icon_const_key.
- `daily/2026-05-17.md` секция «Session (No-Mana Python pre-check)».
