---
title: "Cron Silent Failure Pattern + Centralized BaseCron Alerting"
aliases: [silent-cron-failure, basecron-alerting, admin-alert-cron, cron-failure-detection]
tags: [cron, ops, alerting, anti-pattern, architecture, python]
sources:
  - "daily/2026-05-04.md"
  - "daily/2026-05-17.md"
created: 2026-05-04
updated: 2026-05-17
---

# Cron Silent Failure Pattern + Centralized BaseCron Alerting

APScheduler'ные крон-задачи NOMS могут «тихо» падать в проде: scheduler лог показывает «executed successfully» (потому что Python wrapper-функция не пробросила исключение), но RPC внутри возвращает HTTP 400, side-effect не произведён, юзер не уведомлён. Без специальных мер это остаётся незамеченным сутки и дольше.

## Key Points

- **Silent failure pattern:** apscheduler считает job "executed successfully" если Python-обёртка `async def run(self)` не выбрасывает исключение. Внутри `supabase.rpc(...)` может вернуть 400 (RPC syntax error, ambiguity, permission denied) — scheduler этого НЕ видит.
- **Инцидент 04.05:** `cron_check_streak_breaks` падал каждый час с PG 42702 ambiguity (root cause: stale-base regression мигр. 042→166→167). Обнаружено только при ручной проверке VPS логов — через ~сутки.
- **Решение — централизованный `BaseCron._alert_admin`:** общий для всех 11 крон-задач механизм в `crons/base.py`. Per-cron cooldown 6 часов. При исключении или `result is None` — шлёт HTML-уведомление в admin Telegram-чат (`417002669`).
- **NoneType guard pattern:** `dict.get("key", default)` возвращает default только если ключа **НЕТ**. Если ключ = `None` — возвращается `None`, и `.get(...)` на нём падает. Фикс: `fp = tx.get("key") or {}`.
- **Smoke-test RPC:** `EXPLAIN SELECT public.<fn>()` не ловит runtime ошибки (ambiguity, column reference). Использовать `SELECT public.<fn>()` для реального вызова даже при ожидаемых 0-row results.

## Details

### Анатомия silent failure

```python
# crons/streak_checker.py (до фикса)
class StreakCheckerCron(BaseCron):
    async def run(self):
        result = await self.rpc('cron_check_streak_breaks')
        # result = None при HTTP 400 (supabase_client обрабатывает как None, не exception)
        frozen = result.get('frozen', [])  # AttributeError: NoneType has no .get
        # ↑ НО: streak_checker имел try/except вокруг → логировал ERROR и return
        # apscheduler видел: job completed without exception → "executed successfully"
```

Юзеры: streaks не замораживаются, не ломаются, уведомления не уходят. Никаких алертов. Обнаружение — только через `journalctl -u noms-cron | grep ERROR` вручную.

### Централизованный _alert_admin (crons/base.py)

```python
class BaseCron:
    _ADMIN_ALERT_COOLDOWN_SEC = 6 * 3600  # 6 часов между алертами одного крона
    _last_admin_alert_at: ClassVar[dict[str, float]] = {}

    async def run(self):
        try:
            await self._execute()  # конкретная логика крона
        except Exception as exc:
            logger.exception(f"[{self.name}] FAILED")
            await self._alert_admin(f"{type(exc).__name__}: {exc}")

    async def _alert_admin(self, reason: str):
        now = time.time()
        last = self._last_admin_alert_at.get(self.name, 0)
        if now - last < self._ADMIN_ALERT_COOLDOWN_SEC:
            return  # cooldown active
        self._last_admin_alert_at[self.name] = now
        try:
            await telegram.send_message(
                chat_id=config.ADMIN_CHAT_ID,
                text=f"⚠️ {self.name} cron failed\n\n{reason}",
                parse_mode="HTML",
            )
        except Exception:
            pass  # если Telegram API недоступен — cron не ломается
```

Все 11 крон-задач наследуют поведение **без правок их кода** (TON, mana, streak, league weekly/midweek/fomo, reminders, escrow, subscription, retention, webhook health).

### Per-cron cooldown — почему ClassVar dict, не per-instance

- `ClassVar[dict[str, float]]` = shared state между всеми экземплярами одного класса.
- Ключ = `self.name` (уникальное имя крона).
- In-memory — рестарт `noms-cron` обнуляет все cooldown'ы. Это **intentional**: первая ошибка после рестарта всегда проходит, чтобы админ знал о проблеме.
- Альтернатива (Redis/DB cooldown) — overengineering для 11 задач.

### NoneType guard pattern

```python
# ❌ WRONG: dict.get("key", {}) не защищает от ключа со значением None
fp = tx.get("forward_payload", {})  # key exists, value = None → returns None
comment = fp.get("value", "")       # AttributeError: 'NoneType' has no attribute 'get'

# ✅ RIGHT: fallback через `or`
fp = tx.get("forward_payload") or {}
comment = tx.get("comment", "") or fp.get("value", "")
```

Реальный кейс: TON API `forward_payload: null` для multi-hop transfers. `dict.get("key", default)` возвращает `default` только при **отсутствии** ключа, не при `None`-значении.

### Smoke-test RPC — EXPLAIN vs SELECT

`EXPLAIN SELECT public.<fn>()` проверяет синтаксис и plan, но **НЕ** ловит:
- Column ambiguity (PG 42702) — определяется только при execution.
- Runtime type mismatches, NULL-derefs в PL/pgSQL.
- Conditional branches (IF/CASE) которые не exercised при пустом вводе.

**Правило:** для mutating или complex RPCs всегда `SELECT public.<fn>(...)` с реальным или тестовым аргументом + `SAVEPOINT/ROLLBACK` для безопасности.

## Инциденты

### Streak checker (04.05, ~сутки без обнаружения)

| Факт | Значение |
|---|---|
| RPC | `cron_check_streak_breaks` |
| Ошибка | PG 42702 `column reference "streak_freezes" is ambiguous` |
| Root cause | Stale-base regression через 3 миграции (036→042→166) |
| Обнаружение | Ручной grep VPS логов |
| Fix | Мигр. 167 + centralized alerting |

### TON payment checker (04.05, непрерывный)

| Факт | Значение |
|---|---|
| RPC | `_process_transaction` в TON cron |
| Ошибка | `AttributeError: 'NoneType' has no attribute 'get'` |
| Root cause | TON API v3 `forward_payload: null` (key present, value None) |
| Обнаружение | `[TonPaymentChecker] FAILED 0.53s` в логах — но apscheduler считал job success |
| Fix | `or {}` guard + centralized alerting |

### Mana regeneration NULL-skip (17.05, mig 237)

| Факт | Значение |
|---|---|
| RPC | `cron_regenerate_mana` |
| Ошибка | WHERE `(now() - mana_last_recharge_at) >= '12 hours'` — при `mana_last_recharge_at IS NULL` выражение возвращает NULL → NOT TRUE → юзер пропускается **навсегда** |
| Root cause | Юзер 786301802 создан до того как bootstrap заполнял `mana_last_recharge_at`. Одиночный affected — 1 из 11 real users |
| Обнаружение | Live-тест no-mana pre-check (mig 236, 17.05) — юзер сообщил «мана не регенерируется 12+ часов» |
| Fix | (1) Backfill `mana_last_recharge_at = NOW()` для NULL юзеров. (2) CREATE OR REPLACE `cron_regenerate_mana` — `OR mana_last_recharge_at IS NULL` в WHERE |

**Паттерн «NULL arithmetic даёт NULL → false → row скипается навсегда»:**

```sql
-- ❌ WRONG: NULL - interval = NULL, NULL >= '12 hours' = NULL → NOT TRUE → skip
WHERE (now() - mana_last_recharge_at) >= interval '12 hours'

-- ✅ RIGHT: explicit NULL handling
WHERE mana_last_recharge_at IS NULL
   OR (now() - mana_last_recharge_at) >= interval '12 hours'
```

Этот паттерн шире чем `dict.get()` NoneType guard (секция выше): PostgreSQL NULL arithmetic тоже может «молча проглотить» строки. Для всех cron WHERE-клаузул на datetime/interval колонках — проверить что NULL допустим (для юзеров созданных до миграции, добавившей колонку).

## Anti-patterns

❌ **Per-cron file-local `_alert_admin`** — дублирование cooldown state, N файлов для поддержки.

❌ **`apscheduler.events.EVENT_JOB_ERROR` listener** — ловит только Python exceptions. HTTP 400 от Supabase = не exception, если клиент возвращает `None`.

❌ **Cooldown в DB** — overengineering. In-memory dict достаточно для 11 задач. Restart = reset cooldown = первый alert после рестарта всегда проходит (feature, не bug).

❌ **Без cooldown вообще** — при persistenten ошибке (например ambiguity в SQL) cron падает каждый час = 24 алерта в день = алерт-усталость.

## Чек-лист для нового крона

1. [ ] Наследовать `BaseCron` (не писать standalone async function).
2. [ ] RPC-ответ `None` = обработать явно (`if result is None: raise RuntimeError(...)` или `await self._alert_admin(...)`).
3. [ ] dict-поля с возможным `None` значением — `or {}` / `or ""` guard.
4. [ ] После deploy — дождаться одного цикла крона (`journalctl -u noms-cron --since "5 min ago"`) и убедиться в `Completed in Xs`, не `FAILED`.
5. [ ] Smoke через `SELECT public.<rpc>(...)` с тестовыми аргументами, не через `EXPLAIN`.

## Related Concepts

- [[concepts/safe-create-or-replace-recipe]] — stale-base regression (root cause для streak ambiguity)
- [[concepts/architecture-registry]] — cron jobs отдельный слой, не через Dispatcher
- [[concepts/release-protocol]] — deploy discipline (systemctl restart noms-cron после env-правок)
- [[concepts/supabase-db-patterns]] — мигр. 166/167, WHERE deleted_at IS NULL паттерн

## Sources

- [[daily/2026-05-04.md]] — TON NoneType fix + централизация admin alerts в BaseCron; мигр. 167 ambiguity fix; streak checker silent failure инцидент (~сутки); EXPLAIN vs SELECT smoke lesson
- [[daily/2026-05-17.md]] — Mig 237: `cron_regenerate_mana` NULL-skip (NULL arithmetic → row silently skipped forever). Паттерн «OR col IS NULL» guard для datetime WHERE-клаузул
