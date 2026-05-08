---
title: "n8n Performance Optimization"
aliases: [performance, inlining, app-constants-cache, typing-action, answerCallbackQuery, latency]
tags: [n8n, performance, supabase, ux, patterns]
sources:
  - "daily/2026-04-10.md"
  - "daily/2026-04-15.md"
created: 2026-04-10
updated: 2026-04-21
---

# n8n Performance Optimization

Techniques applied to reduce reply-button latency from ~400-800ms to under 300ms, and eliminate the perception of lag via immediate user feedback.

## Key Points

- **`app_constants_cache` table (migration 054):** single-row JSONB cache with a trigger that refreshes on any `app_constants` change; `v_user_context` joins it via `CROSS JOIN` instead of `jsonb_object_agg` subquery — saves ~30-50ms per request
- **Sub-workflow inlining:** moving nodes from separate workflows into `04_Menu` eliminates Execute Workflow hop overhead (~30-50ms each); Progress, Quests, League, Friends, Shop all inlined
- **Typing action as parallel branch:** `sendChatAction('typing')` fires as a parallel fire-and-forget branch from Menu Router before any RPC — user sees "печатает..." within ~50ms of tapping
- **`answerCallbackQuery` as parallel branch:** fires immediately from Command Classifier for all inline callbacks — removes the 3-second spinner from buttons
- **`cleanText()` centralized in Dispatcher (Phase 3):** `\\n → \n` normalization done once in Dispatcher, removed from 5 sub-workflows
- **Quick Status Check параллельно (2026-04-15):** QSC запускается параллельно с Get User Context вместо последовательно — экономия ~300ms для reply-кнопок
- **`idx_ui_translations_lang_code` (migration 061):** индекс на `ui_translations(lang_code)` ускоряет JOIN в `v_user_context` в ~10x
- **Early Typing Action (2026-04-15):** HTTP Request fire-and-forget от Telegram Trigger в Dispatcher — пользователь видит typing через ~50ms вместо ~1с

## Details

### Bottleneck profile (before optimization)

| Bottleneck | Cost | Fix applied |
|-----------|------|-------------|
| `jsonb_object_agg` on 60+ app_constants rows | ~30-50ms | `app_constants_cache` with trigger |
| cleanText() in 5 sub-workflows | ~5-10ms each | Centralized in Dispatcher |
| Execute Workflow hop (Progress) | ~30-50ms | Inlined into 04_Menu |
| Execute Workflow hop × 4 (Quests/League/Friends/Shop) | ~120-200ms total | All inlined into 04_Menu |
| No typing feedback | Felt slow regardless of actual latency | Typing actions + answerCallbackQuery |

### app_constants_cache (migration 054)

```sql
-- Cache table: single row, refreshed by trigger
CREATE TABLE app_constants_cache (
  id BOOLEAN DEFAULT TRUE PRIMARY KEY,
  data JSONB NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Auto-refresh trigger on app_constants mutations
CREATE TRIGGER trg_refresh_constants_cache
  AFTER INSERT OR UPDATE OR DELETE ON app_constants
  FOR EACH STATEMENT EXECUTE FUNCTION refresh_constants_cache();
```

`v_user_context` was recreated using `CROSS JOIN app_constants_cache` — a single row join — instead of the subquery `(SELECT jsonb_object_agg(key, value) FROM app_constants)` which scanned the entire table on every query. Result: 185 constants keys available in the view, ~30-50ms saved per request.

### Inlining sub-workflows into 04_Menu

04_Menu grew from 56 nodes to 80 nodes (after Progress inline) and then 80 to 95 nodes (after all 4 sub-workflows inlined). Each inlined workflow eliminates one n8n Execute Workflow node, which carries ~30-50ms overhead for spawning a sub-execution context.

The original sub-workflows (08_Progress, 08.1_Quests, 08.2_League, 08.3_Friends, 08.4_Shop) remain active for backward compatibility and are not deleted.

### Typing action pattern

Every reply-keyboard button handler (Stats, Profile, Progress, Quests, League, Shop, Friends) has a `Typing Action` node as a **parallel dead-end branch** from the Menu Router:

```
Menu Router[n] ─┬→ RPC / Build node (main flow)
                └→ Typing Action: sendChatAction(typing) [dead-end]
```

This fires the `POST /sendChatAction` request in parallel with the RPC call. Telegram shows "печатает..." within ~100ms. The branch has no outgoing connections — if it fails, the main flow is unaffected.

### answerCallbackQuery pattern

Inline-button taps (callback_query events) show a loading spinner on the tapped button until `answerCallbackQuery` is called. Without it, the spinner persists for ~3 seconds (Telegram's timeout). The fix adds `Answer Callback Query` as a parallel dead-end branch from Command Classifier[0]:

```
Command Classifier[0] ─┬→ Menu Router (main flow)
                        └→ Answer Callback Query [dead-end, fire-and-forget]
```

This instantly clears the spinner regardless of how long the actual handler takes.

### Estimated total savings

| Optimization | Estimated saving |
|-------------|-----------------|
| app_constants_cache | ~30-50ms per request |
| cleanText() centralization | ~25-50ms per request |
| Progress inline | ~30-50ms per tap |
| Quests/League/Friends/Shop inline | ~120-200ms total |
| Typing + answerCallbackQuery | Perceived latency improvement (not measured) |

**Total:** ~65-110ms (Phase 1-3) + ~120-200ms (Phase 4) reduction per button tap.

### Quick Status Check параллельно (2026-04-15)

**Проблема:** 2 последовательных запроса: Quick Status Check (~300ms) → Get User Context (~300ms) = ~600ms на каждое нажатие reply-кнопки. QSC нужен ТОЛЬКО для typing indicator перед AI анализом еды — для обычных reply-кнопок (Мой день, Профиль, Прогресс) бесполезен.

**Фикс:** `Is Callback? [FALSE]` (reply-keyboard path) теперь параллельно запускает:
1. `Get User Context` (main flow) → User Exists? → основная обработка
2. `Quick Status Check` → Needs Indicator? → Send Early Indicator [dead-end]

`Send Early Indicator` и `Send Indicator? FALSE` — dead-end ветки, не блокируют main flow.

**Экономия:** ~300ms для reply-кнопок (QSC больше не блокирует GUC).

### Early Typing Action

Нода `Early Typing Action` добавлена в Dispatcher как параллельная dead-end ветка от Telegram Trigger (до всей цепочки IF/Get User Context). Отправляет `sendChatAction(typing)` немедленно при получении любого сообщения.

Результат: пользователь видит "typing..." через ~50ms вместо ~1с (раньше typing action был только в 04_Menu после прохождения всего Dispatcher).

### idx_ui_translations_lang_code (migration 061)

```sql
CREATE INDEX idx_ui_translations_lang_code ON ui_translations(lang_code);
```

`v_user_context` выполняет `JOIN ui_translations ON lang_code = u.language_code`. Без индекса — sequential scan по всей таблице (~2000+ строк × 13 языков) при каждом запросе. С индексом — index scan на нужный lang_code. Экономия в v_user_context JOIN ~10x.

### Обновлённый профиль bottleneck (после 2026-04-15)

| Bottleneck | Cost | Fix |
|-----------|------|-----|
| QSC → GUC последовательно | ~300ms | QSC параллельно с GUC |
| ui_translations sequential scan | неизвестно | `idx_ui_translations_lang_code` (migration 061) |
| Early Typing Action | perceived | dead-end ветка от Telegram Trigger |

### Python Proxy Architecture (2026-04-21)

После исчерпания возможностей оптимизации внутри n8n — реализован Python FastAPI proxy между Telegram и n8n, обеспечивший радикальное снижение latency индикатора.

**Проблема n8n-подхода:** indicator в n8n стоял ПОСЛЕ `Get User Context` (100-300ms) в критическом пути. Параллелизация ломала удаление стикера из-за race condition: `06_Indicator_Clear` читал `last_bot_message_id` до того как Python успевал его сохранить.

**Архитектура Python proxy:**
```
Telegram API → Python FastAPI (6-10ms ack)
    ├── background: send indicator + save state (RPC migration 109)
    └── background: forward to n8n
```

**Что удалено из 01_Dispatcher (Phase 2, 57→53 ноды):**
- `Quick Status Check` — HTTP GET проверка статуса
- `Needs Indicator?` — IF node
- `Send Indicator?` — IF node
- `Send Early Indicator` — executeWorkflow 06_Indicator_Send

**Latency результаты:**

| Метрика | До proxy | После | Улучшение |
|---|---|---|---|
| Ack Telegram | ~1s | 6-10ms | ~99% |
| Indicator delivered | ~1.5-2s | ~400-500ms | ~75-80% |

Совокупная экономия **~85%** vs baseline.

**Pre-warm оптимизация:** на startup proxy загружает sticker file_ids и ui_translations для всех 13 языков (955ms). Первый юзер не платит cold-cache цену.

**Skip-translations для sticker-mode:** если сегодня уже был текстовый indicator — шлём только стикер без загрузки phrases (~450ms экономии).

Полные детали: [[concepts/telegram-proxy-indicator]].

### Self-Hosted n8n (2026-04-26) — Remaining Cold-Start Bottleneck

After Python proxy eliminated indicator latency (~85% improvement), the remaining bottleneck was n8n Cloud cold-start on first user interaction after Cloud scheduler idle: **~1.3-1.5s** on first menu click.

**Root cause:** n8n Cloud puts idle workflows to sleep; first execution after idle warms up the execution engine, adding ~1.3-1.5s that cannot be eliminated via workflow-level optimization.

**Solution:** self-host n8n CE in Docker on the NOMS VPS. Local execution engine stays warm. Expected: first-click latency drops from ~1.3-1.5s to ~100-200ms (n8n execution overhead without cold-start).

Steps 0.1-0.4 completed 2026-04-26 (Docker + container + systemd). Traffic switch pending (steps 0.5-0.10). See [[concepts/n8n-self-hosting]] for full migration plan.

## Related Concepts

- [[concepts/n8n-data-flow-patterns]] — fire-and-forget branch pattern used for all typing/callback nodes
- [[concepts/n8n-stateful-ui]] — answerCallbackQuery is part of the stateful UI contract
- [[concepts/supabase-db-patterns]] — app_constants_cache is a DB-layer optimization
- [[concepts/noms-architecture]] — performance is a first-class concern; P0-P4 priority ladder in CLAUDE.md
- [[concepts/telegram-proxy-indicator]] — Python proxy for instant indicator delivery (~85% latency improvement)
- [[concepts/n8n-self-hosting]] — self-hosted n8n CE to eliminate Cloud cold-start ~1.3-1.5s

## Sources

- [[daily/2026-04-10.md]] — Migration 054 (app_constants_cache + cleanText centralization + Progress inline); sub-workflow inlining (Quests/League/Friends/Shop); typing actions × 7; answerCallbackQuery parallel branch
- [[daily/2026-04-15.md]] — QSC параллельно с GUC (~300ms экономия); Early Typing Action от Telegram Trigger; migration 061 (idx_ui_translations_lang_code ~10x JOIN ускорение)
- [[daily/2026-04-21.md]] — Python FastAPI proxy: 6-10ms ack, ~85% latency improvement; Phase 2 Dispatcher cleanup (57→53 nodes); migration 109 RPCs; pre-warm + skip-translations optimizations
