# TON API v3 forward_payload — base64 BoC parsing

> **Live incident 2026-05-21:** TonPaymentChecker cron crash + USDT 5.49 не зачислился из-за изменения shape API. Lesson зафиксирован в mig 300.

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

## See also

- `crons/ton_payment_checker.py:_extract_memo` — canonical implementation
- `tests/test_mig300_payment_p0.py` — pytest fixtures (5 cases)
- daily/2026-05-21.md секция «Payment P0 launch blockers» (Lesson 2)
- [[concepts/n8n-data-flow-patterns]] — общий pattern про API contract drift
