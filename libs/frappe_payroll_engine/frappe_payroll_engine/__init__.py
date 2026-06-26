"""frappe_payroll_engine — generic payroll calculation engine.

Public API (Contract C — frozen):
    calculator     — pro-rata, gross-to-net, accruals, 13th-month pay
                     (see ``frappe_payroll_engine.calculator``)

Submodules:
    * ``calculator``       — pure-function payroll math (no external deps)

All numeric helpers in this package operate on ``Decimal`` to avoid
binary-floating-point error in payroll totals.
"""
from frappe_payroll_engine import calculator

__version__ = "0.1.0"

__all__ = [
    "calculator",
]