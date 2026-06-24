# frappe_payroll_engine

Generic payroll calculation engine for the Armosphera ERPNext apps. MIT licensed.

## Public API

```python
from frappe_payroll_engine import (
    calculator,             # compute_payslip(employee, period, components) -> Payslip
    eosb,                   # accrual(employee, as_of_date, country) -> Decimal
    social_contrib,         # compute(components, country_rates) -> dict[str, Decimal]
)
```

See `docs/architecture.md` (Contract C) for SemVer guarantees.

## Status

Skeleton only; real implementation in W4-T06..T08.
