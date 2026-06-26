"""frappe_payroll_engine.calculator — generic payroll math helpers.

Contract C (frozen, per W4-T06):
    proration_factor(start_date, end_date, period_start, period_end) -> Decimal
    gross_to_net(gross, tax_rate, social_rate, deductions=None) -> dict
    accrue_leave(annual_entitlement, used, accrual_period='monthly',
                 months_elapsed=12) -> Decimal
    thirteen_month(jan_to_dec_gross, contract_months=12) -> Decimal

All amounts use Decimal to avoid floating-point error in payroll math.
Public surface is intentionally minimal — every helper is a pure function
with no external state.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

__all__ = [
    "accrue_leave",
    "gross_to_net",
    "proration_factor",
    "thirteen_month",
]

_ZERO = Decimal("0")
_ONE = Decimal("1")
_TWELVE = Decimal("12")


def proration_factor(
    start_date: date,
    end_date: date,
    period_start: date,
    period_end: date,
) -> Decimal:
    """Return the fraction of ``period_start..period_end`` covered by
    ``start_date..end_date`` (inclusive on both ends), clamped to the period.

    Edge cases:
        * Zero-length period (``period_start > period_end``)            → 0
        * Zero-length employment (``start_date > end_date``)           → 0
        * Employment entirely outside the period                       → 0
        * Employment fully covering the period                         → 1.0

    Otherwise the result is ``overlap_days / period_days`` where
    ``overlap_days`` is the number of inclusive days in the intersection
    of the two ranges.
    """
    if period_start > period_end:
        return _ZERO
    if start_date > end_date:
        return _ZERO

    # Clamp the employment window to the period.
    lo = max(start_date, period_start)
    hi = min(end_date, period_end)

    if lo > hi:
        return _ZERO

    overlap_days = (hi - lo).days + 1  # inclusive on both ends
    period_days = (period_end - period_start).days + 1

    if period_days <= 0:
        return _ZERO

    return Decimal(overlap_days) / Decimal(period_days)


def gross_to_net(
    gross: Decimal,
    tax_rate: Decimal,
    social_rate: Decimal,
    deductions: Optional[Decimal] = None,
) -> dict:
    """Compute a single pay-period payslip from gross pay.

    Tax and social-security contributions are computed on gross. Any other
    flat-amount deductions (union dues, garnishments, loans) are passed in
    via ``deductions`` and subtracted after statutory withholdings.

    Returns a dict with keys: ``gross``, ``tax``, ``social_security``,
    ``other_deductions``, ``net``.
    """
    gross = Decimal(gross)
    tax_rate = Decimal(tax_rate)
    social_rate = Decimal(social_rate)
    other = Decimal(deductions) if deductions is not None else _ZERO

    tax = (gross * tax_rate).quantize(Decimal("0.01"))
    social = (gross * social_rate).quantize(Decimal("0.01"))
    net = gross - tax - social - other

    return {
        "gross": gross,
        "tax": tax,
        "social_security": social,
        "other_deductions": other,
        "net": net,
    }


def accrue_leave(
    annual_entitlement: Decimal,
    used: Decimal,
    accrual_period: str = "monthly",
    months_elapsed: int = 12,
) -> Decimal:
    """Return the leave balance as of ``months_elapsed`` into the year.

    ``accrual_period`` controls the cadence:
        * ``"monthly"``   — 1/12 of the annual entitlement accrues each month.
        * ``"pro_rated"`` — same as monthly, but the result is rounded down
                            to whole days (typical for part-year employees).

    Used days are subtracted from the accrued balance. The result is never
    negative — over-used leave is reported as ``Decimal('0')``.
    """
    annual = Decimal(annual_entitlement)
    used = Decimal(used)
    months = int(months_elapsed)

    if annual <= _ZERO or months <= 0:
        return _ZERO

    accrued = annual * Decimal(months) / _TWELVE

    if accrual_period == "pro_rated":
        accrued = accrued.quantize(Decimal("1"), rounding="ROUND_FLOOR")

    balance = accrued - used
    return balance if balance > _ZERO else _ZERO


def thirteen_month(
    jan_to_dec_gross: Decimal,
    contract_months: int = 12,
) -> Decimal:
    """Compute the 13th-month pay (common in the Philippines and several
    other jurisdictions as a year-end bonus).

    Formula: ``(jan_to_dec_gross / 12) * (contract_months / 12)`` — i.e.
    one-twelfth of the year's gross, pro-rated by the fraction of the year
    the employee was actually under contract.

    Examples:
        >>> thirteen_month(Decimal('12000'), 12)
        Decimal('1000.00')
        >>> thirteen_month(Decimal('6000'), 6)
        Decimal('250.00')
    """
    gross = Decimal(jan_to_dec_gross)
    months = int(contract_months)

    if gross <= _ZERO or months <= 0:
        return _ZERO

    bonus = gross / _TWELVE * Decimal(months) / _TWELVE
    return bonus.quantize(Decimal("0.01"))