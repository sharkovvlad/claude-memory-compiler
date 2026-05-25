# Sticker Architecture (4 Channels, Single Source of Truth)

> Полное архитектурное решение: ADR `docs/adr/0001-sticker-architecture.md` в репо NOMS. Этот документ — operational guide для агентов, добавляющих/правящих стикеры.

## TL;DR

Все стикеры в NOMS хранятся в **единой таблице `bot_stickers`** (single source of truth, никаких file_id в коде). Отправка идёт по **одному из 4 каналов** в зависимости от семантики стикера:

| Канал | Семантика | Триггер | Способ отправки | Удаление |
|---|---|---|---|---|
| **A** UI Content | Часть экрана (welcome, success, level_up) | SQL FSM-переход в screen_id с `meta.show_sticker=true` | Headless: `render_screen` → `telegram_ui.sticker_category` → `template_engine` → `OutboundItem(send_sticker)` → `telegram_send` через `await` | Нет (Trophy) |
| **B** Event side-channel | Реакция на action (food_recognized, water_logged) | Явный Python вызов `await stickers.send_event(...)` (TBD — Stage 2+) | Прямой POST через cache | Опционально через `meta.auto_delete_after_ms` |
| **C** Push (cron) | Push-нотификация со стикером | Cron job | Sequential `await` (sticker → text) | Нет |
| **D** Transient indicator | Thinking/analyzing ожидание | Любое входящее в `active` статусе | Fire-and-forget из `telegram_proxy.py` | Да, после AI-ответа (`users.indicator_message_id`) |

**Принцип:** SQL решает WHAT (категория, когда показать), Python — HOW (резолв file_id из кэша, HTTP-вызов).

## Семантический раздел: thinking-стикер (D) vs UI-стикер (A)

| Свойство | Channel D (thinking) | Channel A (UI content) |
|---|---|---|
| Назначение | Индикатор ожидания долгой операции | Часть приветственного / поздравительного экрана |
| Триггер | Любое входящее в `active` статусе | FSM-переход в конкретный screen_id |
| Где живёт правило показа | Python `telegram_proxy.maybe_send_indicator` | SQL `ui_screens.meta.show_sticker` |
| Способ отправки | `asyncio.create_task(_tg_send_sticker())` | `OutboundItem(send_sticker)` через envelope, **строго через `await`** |
| Порядок в чате | Не критичен (transient) | **Критичен** — должен предшествовать тексту |
| Удаление | Да, после AI-ответа | Нет, Trophy |

**Race-condition guard для Channel A:** `asyncio.create_task` ЗАПРЕЩЁН. Параллельная отправка стикера и текста инвертирует порядок на балансировщиках Telegram — текст может прийти раньше стикера. Поэтому в `services/telegram_send.py` `send_sticker` всегда через `await`. Подробности — ADR 0001.

## Контракт SQL ↔ Python (Channel A)

Это симметрично mig 157 `attach_reply_kb`: «декларативное поле в `telegram_ui` → OutboundItem в envelope».

| Источник | Поле в `telegram_ui` | Что Python добавляет | Позиция в envelope |
|---|---|---|---|
| `ui_screens.meta.reply_kb_entry=true` (mig 157) | `reply_keyboard = {...}` | `OutboundItem(attach_reply_kb)` | В КОНЕЦ |
| `ui_screens.meta.show_sticker=true` (mig 198) | `sticker_category = '<text>'` | `OutboundItem(send_sticker)` | ПОСЛЕ ACQ, ПЕРЕД основным item |

### Цепочка вызовов Channel A

```
1. ui_screens row:
   meta = {'show_sticker': true, 'sticker_category': 'onboarding_welcome'}

2. SQL render_screen (Step 8b + Step 9, mig 198):
   IF v_screen.meta->>'show_sticker' = 'true' THEN
       v_sticker_category := v_screen.meta->>'sticker_category';
   END IF;
   v_telegram_ui = jsonb_build_object(..., 'sticker_category', v_sticker_category, ...);

3. services/template_engine.py render_envelope() — Channel A block:
   sticker_category = telegram_ui.get('sticker_category')
   if isinstance(sticker_category, str) and sticker_category:
       from services import stickers_cache
       sticker_file_id = stickers_cache.lookup(sticker_category)
       if sticker_file_id:
           items.append(OutboundItem(
               strategy='send_sticker',
               chat_id=chat_id,
               sticker_id=sticker_file_id,
           ))
       # else: graceful skip (log info, main message still renders)

4. services/telegram_send.py:225-231:
   if item.strategy == 'send_sticker':
       await client.post('/sendSticker', {chat_id, sticker})
   # await — гарантия порядка
```

### Cache контракт (`services/stickers_cache.py`)

- **TTL 60 секунд** + background refresher (PgBouncer transaction mode не поддерживает LISTEN/NOTIFY, поэтому полл-модель).
- **Fail-open**: network error при refresh → `keep stale` (защита от потери welcome-стикера на pooler blip).
- **Sync lookup** (вызывается из синхронного `render_envelope`); async — только prewarm/invalidate/refresh.
- **DI-friendly**: `StickersCache(query_fn=...)` для тестов без сети.
- **Manual reload**: `POST /internal/stickers/reload` с заголовком `X-Stickers-Reload-Token` (env `STICKERS_RELOAD_TOKEN`). Возвращает 503 если token не настроен.
- **Observability**: `stats()` → `{categories, total_stickers, last_refresh_age_s, last_status: never|ok|empty|error|stale}`.

## Как добавить новый стикер на новый экран (Channel A)

1. **Получить file_id**: переслать стикер боту @RawDataBot (или любому echo-bot), скопировать `message.sticker.file_id` — длинная строка `CAACAg...`. File_id видеостикеров глобально валидны для всех ботов.
2. **Миграция (SQL only)**:
   ```sql
   -- Add sticker row (mig 201: meta.channel='A' маркер для самодокументации)
   INSERT INTO public.bot_stickers
       (sticker_key, category, file_id, file_type, description, sort_order, is_active, meta)
   VALUES
       ('level_up_celebration_1', 'level_up_celebration',
        '<file_id>', 'video_sticker',
        'Celebration sticker shown after level-up.', 0, true,
        '{"channel": "A"}'::jsonb)
   ON CONFLICT (sticker_key) DO UPDATE
      SET file_id = EXCLUDED.file_id, is_active = true,
          meta = EXCLUDED.meta;

   -- Declare on screen. show_sticker_once=true → стикер покажется ровно
   -- ОДИН раз на пользователя (mig 201). Опустите если стикер должен
   -- эмиттиться при каждом рендере (но для Channel A это редкий кейс).
   UPDATE public.ui_screens
      SET meta = meta
                 || jsonb_build_object(
                     'show_sticker',      true,
                     'sticker_category',  'level_up_celebration',
                     'show_sticker_once', true)
    WHERE screen_id = 'level_up_screen';
   ```
3. **Никаких правок в Python**. Reload `POST /internal/stickers/reload` или жди 60s TTL.

### Сбросить one-time флаг для конкретного юзера (e.g. account-restore)

```sql
UPDATE public.users
   SET stickers_shown = stickers_shown - 'level_up_celebration'
 WHERE telegram_id = <tid>;
```
После этого пользователь снова увидит стикер при следующем рендере экрана.

## Активация placeholder-стикера (Channel C, D — cron-driven push / indicator)

Channel A добавляется через миграцию (см. выше). **Channel C и D** обычно имеют placeholder-строку в `bot_stickers` (`file_id LIKE 'TODO_%'`, `is_active=false`), созданную feature-миграцией. Когда владелец сгенерирует и пришлёт реальный file_id — активация одной командой, **без деплоя**:

```sql
UPDATE public.bot_stickers
   SET file_id = '<file_id из Telegram>',
       is_active = true
 WHERE sticker_key = '<sticker_key>';
```

Эффект — через ≤60s (TTL `services/stickers_cache`) или мгновенно через `POST /internal/stickers/reload` (с `X-Stickers-Reload-Token` заголовком).

Существующие placeholder'ы (на момент 2026-05-12) — серия `streak_milestone_7/14/30/100`, `streak_healed` (Channel C, mig 205), `freeze_used` (Channel C, mig 191).

**Полный pipeline-recipe для генерации source → активация:** KB [[concepts/telegram-sticker-pipeline]] секции 6.5 (активация в БД) и 6.6 (canonical Negative-блок для Veo промптов — обязательно содержать в каждом, иначе risk розовых splash-артефактов в финальном стикере).

## Что НЕЛЬЗЯ делать

1. **Не клади логику Channel A в `handlers/*.py`** — нарушение headless. Только через `ui_screens.meta`.
2. **Не используй `asyncio.create_task` для Channel A** — race condition инвертирует порядок «стикер → текст».
3. **Не дублируй thinking-кэш для UI-контент** — у Channel A свой кэш (`services/stickers_cache.py`).
4. **Не хардкодь file_id в коде/конфигах/`.env`** — single source of truth = `bot_stickers`.
5. **Не используй n8n-маршрут** — миграция onboarding в Python завершена (mig 161+165+182).

## Migration roadmap

- **Stage 1 (mig 198, 2026-05-11):** Channel A работает. Channels C/D всё ещё используют свои локальные кэши в `telegram_proxy.py` / `crons/*.py`.
- **Stage 2 (planned, отдельный PR):** `telegram_proxy._get_stickers` / `_get_freeze_sticker_id` мигрируют на общий `services/stickers_cache`. Channel D `processing_*` и Channel C `freeze` живут под единой инфрой.
- **Stage 3 (по потребности):** Channel B facade `services/stickers.py:send_event(chat_id, category)` — когда AI-Engine мигрирует из n8n в Python (Roadmap).

## История

- **Mig 161** (2026-04-30): положила декларацию `meta.show_sticker` для `onboarding_welcome` + placeholder в `bot_stickers`, но цепочку не дошила (мёртвая декларация ~10 дней).
- **Mig 191** (2026-05-09): Smart Freeze добавил `bot_stickers` row `freeze_used` (Channel C placeholder, file_id=TODO, is_active=false).
- **Mig 198** (2026-05-11): дошила Channel A — `render_screen` подмешивает `sticker_category`, `template_engine` добавляет `send_sticker` item. Заполнила реальные file_id для welcome + success. `bot_stickers` расширена (`meta jsonb`, `updated_at`, partial index, `trg_set_updated_at`).
- **Mig 201** (2026-05-11, originally numbered 200; renamed after parallel-agent collision): one-time semantics — `users.stickers_shown jsonb`, флаг `ui_screens.meta.show_sticker_once`, `render_screen` Step 8b атомарно проверяет+помечает. Backfill для существующих юзеров. `bot_stickers.meta.channel` (A/C/D) маркер для самодокументации. Триггер — наблюдение что welcome выпадал повторно при `cmd_select_lang`.
- **Mig 205** (2026-05-12, PR #53): seed `bot_stickers` Channel C series — `streak_milestone_3/7/14/30/100` + `streak_healed`. Только `streak_milestone_3` is_active=true с реальным file_id (Veo source), остальные placeholders `TODO_*` с `is_active=false`. Активация placeholder — см. секцию «Активация placeholder-стикера» выше.
- **Mig 206** (2026-05-12, PR #54): дошила Channel C cron-side для streak milestones. Cron `crons/streak_checker.py` ушёл на пороги 3/7/14/30/100 (старые 25/50/75 deprecated). Per-streak idempotency через `users.stickers_shown[streak_milestone_<N>]` (вместо `coin_transactions`); очистка ключей в `cron_check_streak_breaks` при `current_streak → 0` — Duolingo-style: каждый новый стрик пере-стреляет серию. Добавлен RPC `mark_sticker_shown(tid, key)` — атомарный insert-if-absent, заменяет client-side merge. Coin reward + sticker push идут синхронно через `services/stickers_cache.lookup(category)` + `telegram.send_batch(sticker_file_id=...)` (sticker → text sequential). Placeholder TODO_* → text-only graceful skip (тот же guard что в `freeze_notification_pusher`). 78 переводов (6 ключей × 13 langs) добавлены в `cron_notifications.streak_milestone_*`.

## Связанные KB

- [headless-architecture.md](headless-architecture.md) — общий принцип SQL=WHAT, Python=HOW
- [telegram-proxy-indicator.md](telegram-proxy-indicator.md) — thinking-стикер (Channel D) pattern
- [phase4-onboarding-migration.md](phase4-onboarding-migration.md) — где жил placeholder `onboarding_welcome_1`
- [one-time-attach-pattern.md](one-time-attach-pattern.md) — родственный паттерн `attach_reply_kb` (mig 157)

---

## ADR rationale (исторический контекст)

> Перенесено из [[sticker-architecture-adr]] 2026-05-25 при KB consolidation. Decision date: 2026-05-11.
> Status: Accepted (Stage 1 + 1.1 live; Stage 2 in review; Stage 3 backlog).
> Migrations: `198_stickers_unified_foundation.sql` + `201_sticker_one_time_semantics.sql` (initially numbered 200, renamed to 201 after collision with parallel phenotype-quiz mig 200).
> Stages:
> - 1.0 (mig 198, PR #45 merged) — Channel A headless infrastructure
> - 1.1 (mig 201, PR #47) — one-time-per-user semantics for UI stickers
> - 2.0 (PR #46 in review) — Channel C/D code consolidation onto common cache
> - 3.0 (backlog) — Channel B event facade for AI-Engine reactions

### Context

NOMS (`@nomsaibot`) currently has **three disconnected ways** of sending Telegram stickers, planted as quick tactical solutions over Q1–Q2 2026:

1. **Thinking/processing indicator** — direct `httpx.post('/sendSticker')` fire-and-forget from `telegram_proxy.py`; local in-memory cache (`_stickers_cache`, TTL 3600s) of `bot_stickers WHERE category='processing'`; rotation via `users.last_indicator_index`; deletion after AI response via `users.indicator_message_id` (mig 165).

2. **Smart Freeze push** (mig 191) — direct `httpx.post` from `crons/freeze_notification_pusher.py`; local cache `_freeze_sticker_cache` of `bot_stickers WHERE category='freeze'`.

3. **Onboarding UI stickers** (mig 161, placeholder) — declared in `ui_screens.meta = {show_sticker:true, sticker_category:'…'}`, but `render_screen` did not read the flag and `template_engine` did not resolve `file_id`. Dead declaration for ~10 days — sticker never reached users.

Product plans ~30–40 stickers across 5+ semantic classes (onboarding, achievement, league, push, AI reactions, Sage mood). Without a unified foundation each new sticker becomes another tactical hack, parallel agents create regressions in each other's caches, and the headless-architecture invariant (mig 161 Phase 4) erodes.

PgBouncer in transaction mode (Supabase pooler `:6543`) rules out `LISTEN/NOTIFY` cache invalidation — we need a polling model.

### Decision Rationale (shared infrastructure)

- **Table `bot_stickers`** with extensions in mig 198:
  - new `meta jsonb` (future per-sticker options like `auto_delete_after_ms`)
  - new `updated_at timestamptz` + `trg_set_updated_at` trigger
  - partial index `(category, sort_order) WHERE is_active`
  - explicitly **rejected** columns: `language_code`, `send_count`, `deprecated_at` (YAGNI / hot-row risk).
- **`services/stickers_cache.py`**:
  - In-memory dict `category → [(sort_order, file_id)]`
  - `prewarm()` on FastAPI startup with 3× exponential-backoff retry, fail-open
  - Background refresher every **60 seconds** (rejected: 15-minute TTL — too slow for active development of 20+ stickers; rejected: LISTEN/NOTIFY — incompatible with PgBouncer transaction mode)
  - **Keep-stale** on transient network error (welcome sticker must survive pooler blips)
  - Synchronous `lookup()` to be callable from synchronous `render_envelope`
  - DI: `query_fn` injection point for tests
  - Manual reload via `POST /internal/stickers/reload` with `X-Stickers-Reload-Token` header (env var; endpoint returns 503 if token absent).

### Headless contract (Channel A)

This is **symmetric to `attach_reply_kb`** (mig 157): declarative field in `telegram_ui` maps to an `OutboundItem` in the envelope. Business rule ("which screen should show a sticker?") lives in `ui_screens.meta`, not in `handlers/`.

```
ui_screens.meta.show_sticker=true
    ↓
SQL render_screen Step 8b + Step 9
    ↓
telegram_ui.sticker_category = '<text>' | null
    ↓
template_engine.render_envelope() Channel A block
    ↓
items[ACQ?, send_sticker?, main_item, attach_reply_kb?]
    ↓
telegram_send sequential await
```

### Consequences

**Positive:**
- **Single source of truth** (`bot_stickers`). New sticker = 2 SQL INSERTs / UPDATEs (one row, one `ui_screens.meta` update). Zero Python changes for adding a sticker to an existing screen pattern.
- **Headless preserved.** `ui_screens.meta.show_sticker` lives next to other Phase 4 declarations (`no_back`, `canonical`, `reply_kb_entry`). Sticker policy is reviewable as a SQL diff.
- **No race conditions in Channel A.** Strict `await` chain in `telegram_send`. Order "sticker above text" is guaranteed by TCP/HTTP request initiation order plus Telegram processing each message atomically.
- **Fail-open cache.** Pooler blips do not break visible UX — stale cache continues serving. Hard-failure (cache empty AND can't refresh) is observable via `stats().last_status='error'`.
- **Hot-reload during development.** `POST /internal/stickers/reload` instantly refreshes; 60s TTL bounds passive lag.
- **Testability.** `StickersCache(query_fn=...)` DI removes Supabase dependency from unit tests.

**Negative / Trade-offs:**
- **Cache latency vs SQL lookup.** SQL emits `category` (text), not `file_id` — keeps `render_screen` p95 at ~70ms (vs. +3–8ms had we JOIN'd `bot_stickers`). Trade-off: cache miss is now a "graceful skip" rather than a SQL error, but `lookup()` returns `None` only if either the category is unknown or the cache failed completely; either case is correctly logged and rendered without the sticker.
- **TTL of 60s.** Updated `file_id` becomes visible up to 60s after `UPDATE bot_stickers`. Manual reload endpoint mitigates for ops; for product changes 60s is acceptable.
- **Lazy import in `template_engine`.** `from services import stickers_cache` happens inside `render_envelope` to avoid circular imports at module load. Cost is one dict lookup per render; acceptable.
- **Channels C/D not yet consolidated.** Stage 1 leaves `telegram_proxy.py:_stickers_cache` / `_freeze_sticker_cache` parallel to the new cache. Stage 2 will collapse them. Coexistence is intentional — protects thinking indicator during Channel A rollout.

**Risks:**
- **Cold-start window.** Between FastAPI startup and `prewarm` completion (~150ms typical), `lookup()` returns `None` for all categories. Channel A handles this as graceful skip; first user might miss a welcome sticker if traffic arrives in this window. Acceptable: shutdown→startup is a deliberate operation.
- **Force-push to `bot_stickers.file_id`.** A malformed update (bad string, deleted sticker pack) propagates to user-facing failure within 60s. Mitigations: `Telegram API` returns 400 on invalid `file_id` → `telegram_send` logs warning, main message still goes out (sticker is optional). No bot crash.

### Alternatives Considered

**Alt 1 — "Just dot the i" (tactical fix only).** Fill `file_id` for `onboarding_welcome_1`, add `onboarding_success_1`, write 7 lines in `template_engine` to read `sticker_file_id` (not category). Skip the cache / 4-channel model.

*Rejected because:* every subsequent sticker (18+ planned) requires a similar one-off code path. Within 2–3 sprints we'd have a fragmented graveyard mirroring today's situation. The fundamental decision (cache layer, channel taxonomy, single source of truth) was the same effort regardless of whether 2 or 20 stickers were live at the time.

**Alt 2 — SQL emits `file_id` directly, no Python cache.** `render_screen` LEFT JOINs `bot_stickers` per render call.

*Rejected because:* adds +3–8ms p95 per screen render. With 1000+ active users and 25 msg/sec peak, that's wasted RTT under load. The cache write-path is trivial (60s polling); the read-path benefit (~0ms in-memory dict) is meaningful.

**Alt 3 — Telegram-proxy fire-and-forget for all stickers (extend Channel D).** Use `asyncio.create_task` everywhere, including Channel A welcome/success.

*Rejected because:* Telegram balancers do not guarantee request ordering. `sendSticker` and `sendMessage` issued in parallel can be received in reverse order, putting the celebration sticker **below** the "Готово!" text. For thinking-indicator (Channel D) this is fine (the sticker is transient and removed after the AI response anyway). For UI-content (Channel A) order is part of the contract — Trophy-mode means whatever lands stays in the chat forever.

**Alt 4 — `LISTEN/NOTIFY` for cache invalidation.** Postgres trigger on `bot_stickers` UPDATE fires `NOTIFY stickers_cache_invalidate`; Python `LISTEN` thread invalidates immediately.

*Rejected because:* Supabase pooler in **transaction mode** does not support session-level features like `LISTEN/NOTIFY`. Switching to session mode for one feature is disproportionate; a 60s TTL plus manual reload endpoint achieves equivalent operational hygiene.

**Alt 5 — `language_code` column on `bot_stickers`.** Allow per-language sticker variants (Russian celebration sticker ≠ English celebration sticker).

*Rejected (YAGNI):* product decision is that stickers are universal (no text on the image; localized text follows as a separate message). Can be added later without a destructive migration.

**Alt 6 — `send_count` increment on every show.** Track popularity in `bot_stickers.send_count` via SQL.

*Rejected:* hot-row UPDATEs on a frequently-rendered row create lock contention. Aggregate analytics belong in structured logs (Datadog/Grafana), not in the source-of-truth table.

### Open Questions / Stage 2+ Backlog

1. **Channel B facade** (`services/stickers.py:send_event`) — postponed until AI-Engine migrates from n8n to Python.
2. **Channel D consolidation** — `telegram_proxy._stickers_cache` → `services/stickers_cache` migration. Will require parallel coexistence for safe rollout.
3. **Per-screen sticker rotation** — currently `lookup(rotation_index=0)` always picks `sort_order=0`. If product wants random rotation for Sage mood, expose a `random_rotation` flag in `ui_screens.meta`.
4. **Multilingual stickers** — re-evaluate `language_code` if product changes mind.

### Stage 1.1 Amendment — One-Time Semantics for UI Stickers

- **Status:** Accepted (mig 201, PR #47)
- **Date:** 2026-05-11
- **Trigger:** Live observation on test account 267703 — welcome sticker fired multiple times because `cmd_select_lang` in `status='new'` re-renders `onboarding_welcome` without advancing FSM.

**Context (amendment).** Stage 1.0 assumed FSM-state transitions naturally guarantee one-time sticker emission: «после первого нажатия статус сменится с new». This was **incorrect**: language selection (and any other in-status callback) re-renders the same screen at the same status → SQL emits `sticker_category` again → another `OutboundItem(send_sticker)`. For Trophy-mode stickers (Channel A: persistent UI content) any re-emission is a visible UX bug — the chat history accumulates redundant celebration stickers.

**Decision (amendment).** Introduce **per-user per-category tracking** via `users.stickers_shown jsonb` and opt-in flag `ui_screens.meta.show_sticker_once = true`. Inside `render_screen` Step 8b:

1. If `meta.show_sticker_once = true` AND `users.stickers_shown ? sticker_category` → emit `NULL` (graceful skip; template_engine renders without the sticker).
2. Otherwise → emit `sticker_category` AND atomically `UPDATE users.stickers_shown = stickers_shown || {sticker_category: now()}` in the same transaction.

The atomic UPDATE inside what looks like a read-shaped function is a deliberate trade-off — see Consequences below.

**Self-documenting Channel marker.** `bot_stickers.meta.channel` (`A` / `C` / `D`; `B` reserved) is set for every existing row. This lets future agents and KB searches see at a glance which channel each row belongs to, without grepping calling code. The marker is descriptive, not functional — Python and SQL ignore it.

**Backfill.** Existing users who already finished onboarding must not see the stickers again at next /start. Mig 201 backfills:
- `onboarding_welcome` → all users where `status != 'new'`
- `onboarding_success` → all users where `status = 'registered'`

**Consequences (amendment) — Positive:**
- **No more redundant stickers** during onboarding language-switch / status-stay callbacks.
- **Generalizable** — any new Channel A sticker gets `show_sticker_once: true` in its `ui_screens.meta` declaration, zero Python changes needed.
- **Atomic** — read-and-mark inside one transaction precludes a race where two concurrent renders both see "not shown" and emit twice.
- **Reset-friendly** — if product wants a user to see a sticker again (e.g. account-restore flow), one SQL: `UPDATE users SET stickers_shown = stickers_shown - 'sticker_category' WHERE telegram_id = X`.

**Consequences (amendment) — Negative:**
- **Side-effect inside read-shaped RPC.** `render_screen` now mutates `users.stickers_shown`. This violates the convention that RPCs whose names start with `render_` are pure reads. Mitigation: the function is `SECURITY DEFINER` and runs in a single Postgres transaction; mutation is bounded to one row and one jsonb key. Diagnostic SELECT calls (without sticker meta) are unaffected — UPDATE only fires when `show_sticker_once = true` AND `sticker_category` would be emitted.
- **Bypass for non-render path.** If code paths invoke `process_user_input` / `dispatch_with_render` and then **separately** call `render_screen` for a side-rendered screen (e.g. `handlers/onboarding_v3.py:681` for `onboarding_success_menu`), each call marks its own categories. This is the correct behavior: each rendered screen is its own one-time event. No additional bookkeeping needed.

**Alternatives Considered (amendment):**

*Alt 1 — Mark on Python side (after template_engine emits).* Have `template_engine.render_envelope` (or `telegram_send`) write back to `users.stickers_shown` after the sticker item is dispatched. **Rejected:** leaks business state into the dumb renderer. Phase 4 invariant (`SQL = WHAT, Python = HOW`) explicitly puts "should this sticker be shown?" in SQL. Cross-transaction marking would also introduce a small window where the same render path concurrently emits two stickers before the mark lands.

*Alt 2 — Use `users.previous_status` to detect "first render".* Only emit when transitioning to the screen for the first time. **Rejected:** `previous_status` overwrites on every transition. `cmd_select_lang` does not change status, so `previous_status` is irrelevant for in-status re-renders. Doesn't solve the bug.

*Alt 3 — Add a separate `users.welcome_sticker_seen_at` column per sticker.* **Rejected:** doesn't scale to 20+ planned stickers. One `jsonb` map is structurally cleaner and works for unbounded categories.

### References

- KB: `claude-memory-compiler/knowledge/concepts/headless-architecture.md`
- KB: `claude-memory-compiler/knowledge/concepts/telegram-proxy-indicator.md` (Channel D pattern)
- Migration: `migrations/198_stickers_unified_foundation.sql`
- Migration: `migrations/201_sticker_one_time_semantics.sql`
- Baseline: `migrations/_baseline_render_screen_2026-05-11.sql`
- Baseline: `migrations/_baseline_render_screen_2026-05-11_post_mig198.sql`
- Code: `services/stickers_cache.py`, `services/template_engine.py` (Channel A block), `webhook_server.py` (prewarm + reload endpoint)
- PR: #47 (`claude/sticker-one-time-fix`)
- Live evidence: test account 267703, `/start` + `cmd_select_lang` on 2026-05-11
