---
title: "E2E Telethon DFS Crawler — headless UI smoke testing"
aliases: [e2e-crawler, telethon-crawler, headless-ui-test, dfs-crawler]
tags: [testing, e2e, telethon, headless, tooling]
sources:
  - "daily/2026-05-04.md"
created: 2026-05-04
updated: 2026-05-04
---

# E2E Telethon DFS Crawler

DFS-обход inline-клавиатур Telegram-бота через Telethon User API. Owner-only (tid=417002669). Находит dead buttons (timeout), routing-error'ы (NewMessage без inline keyboard = вылет из headless UI в legacy AI-fallback) и замеряет per-click latency. Покрывает все headless UI экраны через reply-keyboard root'ы (`icon_myday/progress/profile`).

## Key Points

- **DFS по inline-кнопкам:** script заходит с reply-keyboard root → кликает каждую inline-кнопку → рекурсивно обходит дочерние экраны → `cmd_back` возвращает наверх
- **Без хардкода строк:** все `errors.*` строки тянутся из `ui_translations` по `users.language_code`, `icon_*` — из `app_constants`. Ноль русских/английских фраз в коде для матчинга
- **Safety gates:** `--allow-purchases` (default OFF, skip `cmd_buy_*/pay_*/premium_*`), `--include-destructive` (default OFF, skip delete-account flow), `cmd_confirm_payout` жёстко заблокирован всегда
- **Cycle protection:** SHA1 от `(normalized_text, sorted(callback_data))` + глобальный `MAX_CLICKS=400`
- **Output:** JSON-граф + Markdown summary c p50/p95/max latency и списками dead/routing/skipped кнопок

## Details

### Архитектура

```
tests/live/e2e_crawler.py
    ├── DB connection (psycopg2) → ui_translations + app_constants (для dynamic matching)
    ├── Telethon UserClient → session из TELETHON_STRING_SESSION env
    ├── DFS engine:
    │   ├── send reply-text (icon_myday / icon_progress / icon_profile)
    │   ├── wait MessageEdited or NewMessage (timeout 5s)
    │   ├── extract inline_keyboard buttons
    │   ├── for each button not in visited/blocked:
    │   │     ├── click → wait response → record latency
    │   │     ├── classify: dead (timeout) / routing-error (NewMessage w/o KB) / ok
    │   │     ├── recurse into new keyboard
    │   │     └── cmd_back to restore parent screen
    │   └── return to root via reply-keyboard
    └── Report generation (JSON + Markdown)
```

### Классификация ответов

| Ответ | Классификация | Что значит |
|---|---|---|
| `MessageEdited` с inline keyboard | ✅ OK (headless editMessageText) | Нормальный headless-переход |
| `NewMessage` с inline keyboard | ⚠️ OK (send_new стратегия) | delete_and_send_new или send_new — допустимо |
| `NewMessage` **без** inline keyboard | 🔴 Routing error | Вылет из headless UI в legacy AI-fallback |
| Timeout 5s | 🔴 Dead button | Бот не ответил — callback уходит в void |
| Error text matching `errors.*` | 🟡 Error response | Бот ответил ошибкой (может быть expected) |

### Safety design

**Purchase protection** — кнопки с prefixes `cmd_buy_`, `cmd_pay_`, `cmd_recharge_`, `cmd_premium_`, `cmd_confirm_buy_` логируются как `[skipped: purchase]` по умолчанию. Разблокируются через `--allow-purchases`.

**Destructive protection** — цепочка `cmd_delete_account → cmd_confirm_delete → cmd_restore_account` запускается **только в самом конце** после JSON-snapshot `users` + `food_logs[2000]` в `tests/live/snapshots/`. Разблокируется через `--include-destructive`.

**Hard blocklist** — `cmd_confirm_payout` заблокирован безусловно (real money transfer).

### Изоляция зависимостей

`telethon` + `psycopg2-binary` в отдельном `tests/live/requirements.txt` — runtime бота их не использует. Не раздуваем prod-deps и не ломаем CI на отсутствии Telethon.

### Запуск

```bash
pip install -r tests/live/requirements.txt

# Первый прогон — напечатает StringSession для .env
python tests/live/e2e_crawler.py --dry-run

# Полный прогон (без покупок и удалений)
python tests/live/e2e_crawler.py

# С destructive flow (snapshot сохранится автоматически)
python tests/live/e2e_crawler.py --include-destructive --yes
```

### Output

`tests/live/reports/e2e_<UTC-iso>.json` — полный граф (screen → buttons → responses → children).

`tests/live/reports/e2e_<UTC-iso>.md` — human-readable summary:
```
## Summary
- Total clicks: 87
- Dead buttons: 2 (cmd_edit_phenotype, cmd_notifications)
- Routing errors: 0
- Skipped (purchase): 12
- p50 latency: 340ms
- p95 latency: 1200ms
- Max latency: 2100ms (cmd_friends_info)
```

## Watchlist для агентов

При добавлении **новых reply-keyboard root icon_keys** в `dispatcher/router.py:436-464` → обновить `REPLY_ROOT_ICON_KEYS` в `e2e_crawler.py:54`.

При появлении **новых деструктивных callback'ов** (типа `cmd_factory_reset`) → добавить в `DESTRUCTIVE_CALLBACKS` в `e2e_crawler.py`.

При изменении **формата ответов** (например, кнопка стала URL-кнопкой вместо callback) → crawler классифицирует как dead (нет callback_data). Обработка URL-кнопок не реализована (они не дают callback_query).

## Discoveries (первый прогон 04.05)

- `cmd_edit_phenotype` — **dead button** (dangling, нет screen в `ui_screens`). См. [[concepts/ui-screens-map]] §7 anomaly #2.
- `{👑} Премиум-планы` — **routing error с артефактом** `{{icon_premium}}`. Literal `{icon_premium}` в тексте Telegram-сообщения = `cmd_select_plan_*` проваливался в menu_v3 Python вместо legacy 10_Payment. Фикс: мигр. 177 (flatten `{{icon_*}}` → `{icon_*}`) + `PAYMENT_PREFIXES` exclusion guard в router.py. См. [[concepts/router-prefix-collision]].

## Related Concepts

- [[concepts/headless-architecture]] — целевая архитектура для всех UI экранов (crawler тестирует её E2E)
- [[concepts/ui-screens-map]] — навигационное дерево (source of truth для ожидаемых переходов)
- [[concepts/router-prefix-collision]] — найденный краулером `{👑}` routing-leak привёл к фиксу
- [[concepts/test-user-reset-recipe]] — рецепт обнуления тестового юзера перед прогоном краулера

## Sources

- [[daily/2026-05-04.md]] — E2E Telethon-краулер для headless UI: DFS-обход, safety gates, cycle protection, output format, первый прогон с обнаружением dead buttons и routing errors. Branch `claude/e2e-crawler` → PR #10 → merged.
