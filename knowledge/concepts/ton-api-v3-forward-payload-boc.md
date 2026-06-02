# TON API v3 forward_payload — base64 BoC parsing + tx hash normalization

> **Live incident 2026-05-21:** TonPaymentChecker cron crash + USDT 5.49 не зачислился из-за изменения shape API. Lesson зафиксирован в mig 300.
> **Follow-up incident 2026-05-22:** каскадное дублирование подписок из-за tx hash encoding mismatch (base64 в API vs hex в backfill). Fix: mig 302-303.

## Симптом

`AttributeError: 'str' object has no attribute 'get'` в cron `TonPaymentChecker` на строке (legacy):
```python
fp = tx.get("forward_payload") or {}
comment = tx.get("comment", "") or fp.get("value", "")  # ← краш
```

Cron уходит в exception → BaseCron шлёт админ-алерт → payment **НЕ зачисляется**.

## Корень

TonCenter API v3 (`https://toncenter.com/api/v3/jetton/transfers`) изменил shape ответа vs v2:

| Поле | v2 (legacy) | v3 (2026-05+) |
|---|---|---|
| `comment` | strings или NULL | **всегда `None`** |
| `forward_payload` | dict `{"value": "<memo>"}` или `None` | **сырая base64 BoC string** |

Старый guard `or {}` защищает только от `None` (None → falsy → `or {}`). Но string is truthy → `fp.get()` падает на str.

## Анатомия BoC text-comment payload

Bag-of-Cells (BoC) формат для text-comment:
```
<BoC magic 4 bytes>  + <cell header bytes>  + \x00\x00\x00\x00  + <UTF-8 memo>  + <CRC trailing>
```

`\x00\x00\x00\x00` — op-code для «text comment» (32-bit zero).

Пример из incident (tid=786301802):
```
forward_payload = "te6cckEBAQEADwAAGgAAAAA3ODYzMDE4MDJEiUVq"
base64-decoded:
b'\xb5\xee\x9cr\x41\x01\x01\x01\x00\x0f\x00\x00\x1a\x00\x00\x00\x00786301802DEj\x55\x76'
                                          ^^^^^^^^^^^^^^^^                       ^^^^^^^^^^^
                                          op-code     memo (UTF-8)              CRC trailing
```

Здесь "DEj" после "786301802" — это часть CRC (case-insensitive printable), не часть memo.

## Канонический fix (mig 300)

```python
import base64
import re

@staticmethod
def _extract_memo(tx: dict) -> str:
    # Path 1: top-level comment (legacy / некоторые endpoints)
    comment = tx.get("comment")
    if comment and isinstance(comment, str):
        return comment.strip()

    fp = tx.get("forward_payload")

    # Path 2: dict shape (legacy)
    if isinstance(fp, dict):
        v = fp.get("value") or fp.get("comment")
        if v and isinstance(v, str):
            return v.strip()

    # Path 3 (mig 300): raw base64 BoC string (v3)
    if isinstance(fp, str) and fp:
        try:
            raw = base64.b64decode(fp, validate=False)
            # Для NOMS memo всегда telegram_id (digits only). Digit-only regex
            # игнорирует CRC trailing junk (которое в base64-decoded BoC может
            # быть printable ASCII).
            m = re.search(rb"\x00\x00\x00\x00(\d{1,32})", raw)
            if m:
                return m.group(1).decode("ascii", errors="ignore").strip()
        except Exception:
            pass

    return ""
```

## Регрессионный тест

```python
def test_ton_memo_extract_from_boc_string():
    # Real fixture from incident 2026-05-21 21:18
    tx = {
        "comment": None,
        "forward_payload": "te6cckEBAQEADwAAGgAAAAA3ODYzMDE4MDJEiUVq",
        "amount": "5490000",
        "transaction_hash": "Ugw638Ce3pEKoe/78I0Kz1ZeVrW7D2jTUkxg1I7puZ8=",
    }
    assert TonPaymentCheckerCron._extract_memo(tx) == "786301802"
```

## Generalisation

Если в будущем memo сможет быть НЕ просто цифры (e.g. префикс типа `ref_NNN`):

```python
# Match ASCII printable run (но не high bytes 0x80+ — обычно начало CRC):
m = re.search(rb"\x00\x00\x00\x00([\x20-\x7e]{1,256})", raw)
if m:
    candidate = m.group(1).decode("ascii", errors="ignore")
    # Strip trailing CRC-like junk: take leading valid memo chars.
    # For NOMS this would be a custom rule.
```

Для proper parsing — использовать `pytoniq-core` или `tonsdk` библиотеки которые знают BoC cell-length encoding. Но для memo как digits — regex достаточно.

---

## TX Hash Normalization (mig 302-303, 2026-05-22)

### Симптом

TON cron каждые 5 минут создавал **новые подписки** для одной и той же транзакции. Pre-check RPC `SELECT EXISTS(WHERE external_charge_id = ...)` возвращал FALSE, потому что сохранённый hash и hash из API были в **разных кодировках**.

### Корень — base64 vs hex

TON API v3 отдаёт `transaction_hash` в **base64**:
```
"Ugw638Ce3pEKoe/78I0Kz1ZeVrW7D2jTUkxg1I7puZ8="
```

При backfill агент использовал tonviewer.com, который показывает **hex**:
```
"520c3adf...c09edece..."
```

Это **одна и та же транзакция**, просто разный encoding одних и тех же байтов. Без нормализации dedup ломается — `base64_string != hex_string` всегда.

### Canonical hash format = lowercase hex

Python cron нормализует любой формат через `_normalize_tx_hash()`:

```python
import base64, re

@staticmethod
def _normalize_tx_hash(raw: str) -> str:
    """Normalize TON tx hash to lowercase hex, regardless of input encoding."""
    if not raw:
        return ""
    raw = raw.strip()
    # If it looks like hex already (only hex chars, even length)
    if re.fullmatch(r'[0-9a-fA-F]+', raw) and len(raw) % 2 == 0:
        return raw.lower()
    # Try base64 decode
    try:
        decoded = base64.b64decode(raw, validate=False)
        return decoded.hex()  # always lowercase
    except Exception:
        return raw.lower()
```

### 3-уровневая dedup защита

| Уровень | Что ловит |
|---|---|
| **L1 — cron normalize** | `_normalize_tx_hash()` перед любым сравнением/INSERT. Приводит base64/hex/mixed-case к canonical lowercase hex |
| **L2 — RPC pre-check** | `process_ton_payment` v0.5: `SELECT EXISTS(WHERE external_charge_id = p_normalized_hash)` ПЕРЕД INSERT subscription |
| **L3 — DB UQ index** | `CREATE UNIQUE INDEX uq_payment_events_external_charge ON payment_events(external_charge_id) WHERE external_charge_id IS NOT NULL` |

Каждый уровень ловит то, что пропустил предыдущий.

### Mig 302 — колонка + index + RPC pre-check

```sql
ALTER TABLE payment_events ADD COLUMN external_charge_id TEXT;
CREATE UNIQUE INDEX uq_payment_events_external_charge
    ON payment_events(external_charge_id)
    WHERE external_charge_id IS NOT NULL;
```

`process_ton_payment` расширен: получает `p_external_charge_id`, проверяет `EXISTS` перед `INSERT INTO payment_events`.

### Mig 303 — очистка non-canonical записей

```sql
-- Set NULL для base64 записей (они будут re-processed с canonical hex)
UPDATE payment_events
SET external_charge_id = NULL
WHERE external_charge_id ~ '[+/=]';  -- base64 chars, not hex
```

### Паттерн для агентов

> **При сохранении идентификаторов из внешних API всегда канонизировать encoding.** TON base64/hex — частный случай общего правила. Аналогичные ситуации: Stripe event_id (всегда string), Telegram charge_id (always int-as-string). Без нормализации dedup ломается на boundary encoding.

### Тесты `_normalize_tx_hash`

```python
def test_normalize_hex():
    assert _normalize_tx_hash("520C3ADF") == "520c3adf"

def test_normalize_base64():
    assert _normalize_tx_hash("Ugw63w==") == "520c3adf"  # same bytes

def test_normalize_empty():
    assert _normalize_tx_hash("") == ""
```

**Gotcha:** значение которое выглядит как hex (только hex-символы, чётная длина) нормализуется lower-case **без** base64 decode. Это правильно — hex→hex = identity, лишний decode мог бы испортить валидный hex.

---

## See also

- `crons/ton_payment_checker.py:_extract_memo` — canonical BoC parsing implementation
- `crons/ton_payment_checker.py:_normalize_tx_hash` — canonical hash normalization
- `tests/test_mig300_payment_p0.py` — pytest fixtures (5 cases)
- daily/2026-05-21.md секция «Payment P0 launch blockers» (Lesson 2)
- daily/2026-05-22.md секция «TON duplicate cascade» (Lesson: base64 vs hex)
- [[concepts/payment-idempotency-pattern]] — общий idempotency framework (Stripe/Stars/TON)
- [[concepts/n8n-data-flow-patterns]] — общий pattern про API contract drift
