"""Bank-statement-to-invoice reconciliation.

Contract C extension (additive, no breakage): reconcile_payments_to_invoices.

Given a parsed bank statement (from parse_camt053 or parse_mt940) and a
list of invoices, returns a structured dict of matched / unmatched
items, plus totals.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any


# Per-currency tolerance for matching amounts (because AMD has 0 decimals
# and rounding errors accumulate, while AED/USD/EUR have 2 decimal digits
# and round-trip more cleanly).
DEFAULT_TOLERANCE = {
    "AMD": Decimal("10"),
    "AED": Decimal("0.05"),
    "USD": Decimal("0.05"),
    "EUR": Decimal("0.05"),
    "GBP": Decimal("0.05"),
}


def _iter_bank_entries(bank_statement: Any) -> list[dict]:
    """Normalize a bank statement into a flat list of entry dicts.

    Supports both CAMT.053 (dict with statement.entries) and MT940
    (list of statement dicts, each with entries).
    """
    entries: list[dict] = []
    if isinstance(bank_statement, list):
        # MT940: list of statements
        for stmt in bank_statement:
            for e in (stmt.get("entries") or []):
                entries.append(e)
    elif isinstance(bank_statement, dict):
        # CAMT.053: single statement
        stmt = bank_statement.get("statement") or {}
        for e in (stmt.get("entries") or []):
            entries.append(e)
    else:
        raise TypeError(f"Unsupported bank_statement type: {type(bank_statement).__name__}")
    return entries


def _normalize_entry(entry: dict) -> dict:
    """Coerce a bank entry into {date, amount, currency, ref}."""
    amount = entry.get("amount")
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount or "0"))
    direction = entry.get("direction") or "C"
    # In payments, C = credit (money in), D = debit (money out). We only
    # match credits against invoice amounts due.
    if direction == "D":
        amount = -amount
    return {
        "date": entry.get("value_date") or entry.get("date"),
        "amount": abs(amount),  # normalize to positive for matching
        "currency": entry.get("currency"),
        "ref": entry.get("ref") or entry.get("info") or "",
    }


def _get_tolerance(currency: str, overrides: dict | None = None) -> Decimal:
    tol = (overrides or {}).get(currency) if overrides else None
    if tol is None:
        tol = DEFAULT_TOLERANCE.get(currency, Decimal("0.05"))
    return Decimal(str(tol))


def reconcile_payments_to_invoices(
    bank_statement: Any,
    invoices: list[dict],
    currency: str,
    locale: str = "en",  # noqa: ARG001 - reserved for future locale-specific parsing
    tolerance_amd: float | Decimal = 10,
    tolerance_aed: float | Decimal = 0.05,
    tolerance_usd: float | Decimal = 0.05,
    tolerance_eur: float | Decimal = 0.05,
    reconciliation_date: str | date | None = None,
) -> dict:
    """Match bank-statement payments against open invoices.

    Parameters
    ----------
    bank_statement : parsed statement (dict from parse_camt053 or list
        from parse_mt940).
    invoices : list of dicts with keys:
        invoice_no, customer, amount_due, amount_paid, currency, due_date.
    currency : the statement currency (e.g. 'AMD', 'AED').
    locale : reserved for future locale-aware parsing.
    tolerance_amd/aed/usd/eur : matching tolerance per currency.
    reconciliation_date : ISO date string or datetime.date. Defaults to today.

    Returns
    -------
    dict with keys: matched, unmatched_payments, unmatched_invoices,
    reconciliation_date, totals.
    """
    overrides = {
        "AMD": tolerance_amd,
        "AED": tolerance_aed,
        "USD": tolerance_usd,
        "EUR": tolerance_eur,
    }
    tol = _get_tolerance(currency, overrides)

    rec_date = reconciliation_date or date.today().isoformat()

    raw_entries = _iter_bank_entries(bank_statement)
    payments = [_normalize_entry(e) for e in raw_entries]

    # Filter payments by currency (we only match statement currency).
    payments = [p for p in payments if p["currency"] == currency]

    matched: list[dict] = []
    unmatched_payments: list[dict] = []
    used_invoices: set[int] = set()

    # Sort payments descending by amount; try to match each to an invoice.
    # Greedy: one payment matches at most one invoice.
    invoice_amounts = []
    for idx, inv in enumerate(invoices):
        amount_paid = Decimal(str(inv.get("amount_paid") or 0))
        amount_due = Decimal(str(inv.get("amount_due") or 0))
        invoice_amounts.append((idx, inv, amount_due, amount_paid))

    for payment in payments:
        payment_amount = payment["amount"]
        matched_idx = None
        for idx, inv, due, paid in invoice_amounts:
            if idx in used_invoices:
                continue
            # The amount we expect is "amount_due - amount_paid" (open balance).
            open_balance = due - paid
            if abs(payment_amount - open_balance) <= tol:
                matched_idx = idx
                break
        if matched_idx is not None:
            idx, inv, due, paid = invoice_amounts[matched_idx]
            matched.append({
                "invoice_no": inv.get("invoice_no"),
                "customer": inv.get("customer"),
                "payment_date": payment["date"],
                "amount": payment_amount,
            })
            used_invoices.add(matched_idx)
        else:
            unmatched_payments.append({
                "date": payment["date"],
                "amount": payment_amount,
                "ref": payment["ref"],
            })

    # Unmatched invoices (no matching payment found)
    unmatched_invoices: list[dict] = []
    today = date.today()
    for idx, inv, due, paid in invoice_amounts:
        if idx in used_invoices:
            continue
        open_balance = due - paid
        if open_balance <= 0:
            continue  # already paid; not outstanding
        due_date_str = inv.get("due_date")
        days_overdue = 0
        if due_date_str:
            try:
                if isinstance(due_date_str, str):
                    due_date_obj = date.fromisoformat(due_date_str)
                else:
                    due_date_obj = due_date_str
                days_overdue = max(0, (today - due_date_obj).days)
            except (ValueError, TypeError):
                pass
        unmatched_invoices.append({
            "invoice_no": inv.get("invoice_no"),
            "customer": inv.get("customer"),
            "amount_due": open_balance,
            "days_overdue": days_overdue,
        })

    # Totals
    # "invoiced" = total amount_due across all invoices (raw)
    invoiced = sum(
        (Decimal(str(inv.get("amount_due") or 0)) for _, inv, _, _ in invoice_amounts),
        Decimal("0"),
    )
    received = sum((p["amount"] for p in payments), Decimal("0"))
    # "outstanding" = invoiced - matched_amounts - already_paid_amounts
    matched_total = sum((m["amount"] for m in matched), Decimal("0"))
    already_paid = sum(
        (
            Decimal(str(inv.get("amount_paid") or 0))
            for _, inv, _, _ in invoice_amounts
        ),
        Decimal("0"),
    )
    outstanding = invoiced - matched_total - already_paid
    if outstanding < 0:
        outstanding = Decimal("0")

    return {
        "matched": matched,
        "unmatched_payments": unmatched_payments,
        "unmatched_invoices": unmatched_invoices,
        "reconciliation_date": rec_date,
        "totals": {
            "invoiced": invoiced,
            "received": received,
            "outstanding": outstanding,
        },
    }


__all__ = ["reconcile_payments_to_invoices", "DEFAULT_TOLERANCE"]
