---
title: "JSONB-array Sassy variants — Python consumer blind spot"
aliases: [sassy-variants-array-python, already_premium-array-bug]
tags: [migrations, jsonb, python, sassy, payment, lessons]
sources:
  - "daily/2026-05-31.md"
  - "migrations/306_sassy_payment_screens.sql"
  - "migrations/307_get_subscription_business_data_array_aware.sql"
created: 2026-05-31
updated: 2026-05-31
---

# JSONB-array Sassy variants — Python consumer blind spot

Когда translation key переписывается из single-string в **JSONB-array variants**
(паттерн mig 306 — random pick для Sassy tone), нужно обновить **ВСЕХ
consumer'ов**, не только тех что в SQL RPC.

## Background

Mig 306 (`sassy_payment_screens`) переписал 3 payment translation keys из
plain string в JSONB-array (3 Sassy варианта каждый):
- `payment.already_premium_block_body`
- `payment.cancel_done_stripe_callback`
- `payment.resume_done_callback`

Цель — random pick на каждый показ → Sage не звучит как заевшая пластинка.

Для **SQL RPC** consumer'ов был сделан фикс **mig 307**:
```sql
SELECT CASE jsonb_typeof(content->'payment'->'key')
    WHEN 'array' THEN
        content->'payment'->'key'->>(floor(random() * jsonb_array_length(...))::int)
    ELSE content->'payment'->>'key'
END
```

**Но Python-consumers `payment.already_premium_block_body` остался
не array-aware.** Конкретно — `webhook_server._send_already_premium_redirect()`.

## Symptom (production, 2026-05-31 14:24 UTC)

Admin tid 417002669 (already-premium) тапает «Картой» из планов:
```
ERROR _send_already_premium_redirect failed tid=417002669
Traceback:
  File "webhook_server.py", line 2789, in _send_already_premium_redirect
    text = text.replace("{expires}", str(expires_fmt))
AttributeError: 'list' object has no attribute 'replace'
```

Try/except снаружи проглотил — endpoint всё равно ответил 302 на t.me. Но
юзер видит в чате только `/start` без объясняющего Sassy-сообщения. Disorienting UX.

## Fix (PR #263, mig не нужна — Python-only)

```python
if isinstance(text, list):
    text = random.choice(text) if text else fallback
text = text.replace("{expires}", str(expires_fmt))
```

3 строки + `import random`.

## Key Points

- **mig 306+ Sassy variants** перевели N translation keys в JSONB-array. Список в самой mig 306.
- **mig 307** закрыл SQL-сторону для `get_subscription_business_data` RPC.
- **Python consumers** через grep `.replace("{...}",` в `webhook_server.py`/`handlers/` — могут не быть array-aware → AttributeError при первом popadanii в array-вариант.
- **Try/except в коде сглатывает баг тихо.** Юзер видит частичный UX, а не explicit error. Без production-логов невозможно заметить.

## Recipe — когда переводишь string → JSONB-array

1. **SQL grep всех RPC**, читающих этот key:
   ```bash
   grep -rln "content->'<namespace>'->>'<key>'" migrations/
   ```
   Каждый — переписать через `CASE jsonb_typeof = 'array'` (см. mig 307 как канон).

2. **Python grep ВСЕХ consumer'ов**, читающих этот key через REST:
   ```bash
   grep -rln "'<key>'" handlers/ webhook_server.py crons/ services/
   ```
   В каждом — добавить `isinstance(list)` перед `.replace()`/`.format()`/`.startswith()` и random pick.

3. **Test smoke**: вызвать functionality с new array data → убедиться что строка
   приходит юзеру, а не traceback в логах.

4. **Логи мониторинг 24h**: `journalctl ... | grep AttributeError` — если try/except
   глушит, прод-логи единственный сигнал.

## Related Concepts

- [[concepts/jsonb-shallow-merge-antipattern]] — `content || payload` wipe (другой класс JSONB ошибок)
- [[concepts/sassy-sage-multilingual-glossary]] — Sage tone и variants pattern
- [[concepts/copywriter-playbook]] — как создавать variants
- [[concepts/payment-idempotency-pattern]] — payment system context

## Анти-паттерн для следующего агента

> «Я добавил Sassy variants — обновил mig 307 (RPC). Кажется всё.»

Нет, не всё. **Python тоже потребляет** эти keys через REST → JSONB → `dict.get()` → `.replace()`. Только RPC-сторону закрыть = баг через 2-4 недели когда random pick попадёт на array из 3 элементов вместо string.

---

## Recurrence 2026-06-12 — `payment.activated_body` (mig 500)

**Третий рецидив того же класса.** Mig 500 переписал phantom-key
`payment.activated_body` из `null` сразу в JSONB-array (3 Sage-tone variants × 13
langs). До mig 500 ключ отсутствовал, Python шёл в hardcoded EN fallback. После
mig 500 он получил `list` и упал бы с `TypeError: list.replace` если бы не
сделать **тем же PR'ом** Python-fix.

### Симптом

`crons/ton_payment_checker.py:338`:
```python
activated_text = (pay_t.get("activated_body")
    or "✅ Premium Activated!\n\nPayment: {amount} USDT\nPlan: {plan}\n...")
activated_text = activated_text.replace("{amount}", f"{amount_usdt:.2f}")
```

Phantom-key → ветка `or` → scalar string → `replace` работает. Mig 500 → `raw` стал
list → `replace` упадёт.

### Fix (тот же commit что и mig 500)

```python
raw = pay_t.get("activated_body")
if isinstance(raw, list) and raw:
    activated_text = random.choice(raw)
elif isinstance(raw, str) and raw:
    activated_text = raw
else:
    activated_text = "<scalar EN fallback for defensive>"
```

### Durable rule (reinforced)

**JSONB-array-миграция (scalar → array, OR null → array) = двойной commit
SQL+Python в ОДНОМ PR.** Между ними не должно быть деплоя. Иначе:
- если SQL первая → Python падает с TypeError на следующем cron-tick'е
- если Python первая → defensive `random.choice(raw or [])` тихо отдаёт пустоту,
  юзеры получают пустые/fallback тексты до apply SQL

**Pre-flight check** перед каждой scalar→array миграцией: `grep -rn '<key>'
--include="*.py"` по handlers/ services/ crons/ webhook_server.py main.py. Каждый
consumer переключи на array-aware в том же diff. Не оставляй TODO «починю позже».

### Ссылки

- mig 306/307 — первый кейс (payment.already_premium_block_body).
- mig 416/417 — второй кейс (payment.trial_expired).
- mig 500 (PR #388) — третий кейс (payment.activated_body, отличие — phantom-key
  не было, идёт null→array а не scalar→array).
