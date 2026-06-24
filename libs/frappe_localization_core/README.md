# frappe_localization_core

Country-agnostic localization helpers for the Armosphera ERPNext apps. MIT licensed.

## Public API

```python
from frappe_localization_core import (
    number_to_words,        # number_to_words(value, lang) -> str
    iban_validator,         # iban_validator(iban, country) -> bool
    iso20022_parser,        # parse_camt053(xml) -> list[BankTransaction]
    mt940_parser,           # parse_mt940(text) -> list[BankTransaction]
    currency_format,        # format_currency(value, currency) -> str
)
```

See `docs/architecture.md` (Contract C) for SemVer guarantees.

## Status

Skeleton only; real implementation in W4-T01..T10.
