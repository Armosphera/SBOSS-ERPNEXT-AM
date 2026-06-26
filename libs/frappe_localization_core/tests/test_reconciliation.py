"""Tests for reconcile_payments_to_invoices (W4-T07)."""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from frappe_localization_core.reconciliation import reconcile_payments_to_invoices


def _make_statement_entry(date_, amount, currency="AMD", direction="C", ref=""):
    """Helper to build a CAMT.053-style bank entry dict."""
    return {
        "value_date": date_,
        "amount": Decimal(str(amount)),
        "currency": currency,
        "direction": direction,
        "ref": ref,
    }


def _wrap_camt(entries):
    """Wrap entries into a CAMT.053-style statement dict."""
    return {
        "header": {},
        "statement": {"entries": entries},
    }


def test_reconcile_perfect_match():
    """Exact-amount payment matches an open invoice."""
    stmt = _wrap_camt([
        _make_statement_entry("2026-06-01", "100000", "AMD"),
    ])
    invoices = [
        {
            "invoice_no": "INV-001",
            "customer": "ACME",
            "amount_due": "100000",
            "amount_paid": "0",
            "currency": "AMD",
            "due_date": "2026-06-15",
        }
    ]
    out = reconcile_payments_to_invoices(stmt, invoices, "AMD")
    assert len(out["matched"]) == 1
    assert out["matched"][0]["invoice_no"] == "INV-001"
    assert out["matched"][0]["amount"] == Decimal("100000")
    assert out["unmatched_payments"] == []
    assert out["unmatched_invoices"] == []
    assert out["totals"]["outstanding"] == Decimal("0")


def test_reconcile_with_tolerance():
    """AMD payment off by 5 AMD is within tolerance (10 AMD)."""
    stmt = _wrap_camt([
        _make_statement_entry("2026-06-01", "100005", "AMD"),
    ])
    invoices = [
        {
            "invoice_no": "INV-002",
            "customer": "ACME",
            "amount_due": "100000",
            "amount_paid": "0",
            "currency": "AMD",
            "due_date": "2026-06-15",
        }
    ]
    out = reconcile_payments_to_invoices(stmt, invoices, "AMD")
    assert len(out["matched"]) == 1
    assert out["matched"][0]["invoice_no"] == "INV-002"


def test_reconcile_partial_payment():
    """Partial payment leaves the invoice outstanding."""
    stmt = _wrap_camt([
        _make_statement_entry("2026-06-01", "50000", "AMD"),
    ])
    invoices = [
        {
            "invoice_no": "INV-003",
            "customer": "ACME",
            "amount_due": "100000",
            "amount_paid": "0",
            "currency": "AMD",
            "due_date": "2026-06-15",
        }
    ]
    out = reconcile_payments_to_invoices(stmt, invoices, "AMD")
    # The 50K payment won't match a 100K invoice (50K > 10 tolerance).
    assert out["matched"] == []
    assert len(out["unmatched_payments"]) == 1
    assert len(out["unmatched_invoices"]) == 1


def test_reconcile_overpayment_outside_tolerance():
    """A payment significantly larger than any invoice is unmatched."""
    stmt = _wrap_camt([
        _make_statement_entry("2026-06-01", "999999", "AMD"),
    ])
    invoices = [
        {
            "invoice_no": "INV-004",
            "customer": "ACME",
            "amount_due": "100000",
            "amount_paid": "0",
            "currency": "AMD",
            "due_date": "2026-06-15",
        }
    ]
    out = reconcile_payments_to_invoices(stmt, invoices, "AMD")
    assert out["matched"] == []
    assert len(out["unmatched_payments"]) == 1


def test_reconcile_unmatched_payment():
    """A payment with no corresponding invoice stays unmatched."""
    stmt = _wrap_camt([
        _make_statement_entry("2026-06-01", "50000", "AMD"),
    ])
    out = reconcile_payments_to_invoices(stmt, [], "AMD")
    assert out["matched"] == []
    assert len(out["unmatched_payments"]) == 1
    assert out["unmatched_payments"][0]["amount"] == Decimal("50000")
    assert out["totals"]["invoiced"] == Decimal("0")


def test_reconcile_unmatched_invoice_with_overdue():
    """An unpaid past-due invoice shows up in unmatched_invoices with days_overdue."""
    stmt = _wrap_camt([])
    past = (date.today() - timedelta(days=30)).isoformat()
    invoices = [
        {
            "invoice_no": "INV-OVERDUE",
            "customer": "SlowPay",
            "amount_due": "75000",
            "amount_paid": "0",
            "currency": "AMD",
            "due_date": past,
        }
    ]
    out = reconcile_payments_to_invoices(stmt, invoices, "AMD")
    assert len(out["unmatched_invoices"]) == 1
    overdue = out["unmatched_invoices"][0]
    assert overdue["invoice_no"] == "INV-OVERDUE"
    assert overdue["days_overdue"] >= 30
    assert overdue["amount_due"] == Decimal("75000")


def test_reconcile_multiple_invoices():
    """Multiple invoices, multiple payments, mixed match results."""
    stmt = _wrap_camt([
        _make_statement_entry("2026-06-01", "100000", "AMD"),
        _make_statement_entry("2026-06-02", "50000", "AMD"),
    ])
    invoices = [
        {"invoice_no": "INV-A", "customer": "ACME", "amount_due": "100000",
         "amount_paid": "0", "currency": "AMD", "due_date": "2026-06-30"},
        {"invoice_no": "INV-B", "customer": "ACME", "amount_due": "200000",
         "amount_paid": "0", "currency": "AMD", "due_date": "2026-06-30"},
    ]
    out = reconcile_payments_to_invoices(stmt, invoices, "AMD")
    matched_nos = {m["invoice_no"] for m in out["matched"]}
    # INV-A is fully paid (100K); INV-B remains (200K outstanding).
    assert "INV-A" in matched_nos
    assert "INV-B" not in matched_nos
    assert len(out["unmatched_payments"]) == 1
    assert out["unmatched_payments"][0]["amount"] == Decimal("50000")


def test_days_overdue_zero_for_future_invoice():
    """An invoice due in the future has 0 days overdue."""
    stmt = _wrap_camt([])
    future = (date.today() + timedelta(days=10)).isoformat()
    invoices = [
        {"invoice_no": "INV-FUTURE", "customer": "FreshCo", "amount_due": "50000",
         "amount_paid": "0", "currency": "AMD", "due_date": future},
    ]
    out = reconcile_payments_to_invoices(stmt, invoices, "AMD")
    assert out["unmatched_invoices"][0]["days_overdue"] == 0


def test_currency_filter_excludes_other_currencies():
    """Payments in non-matching currencies are filtered out."""
    stmt = _wrap_camt([
        _make_statement_entry("2026-06-01", "100", "USD"),
    ])
    invoices = [
        {"invoice_no": "INV-AMD", "customer": "X", "amount_due": "50000",
         "amount_paid": "0", "currency": "AMD", "due_date": "2026-06-30"},
    ]
    out = reconcile_payments_to_invoices(stmt, invoices, "AMD")
    # The USD payment is filtered out.
    assert out["matched"] == []
    assert out["unmatched_payments"] == []
    assert len(out["unmatched_invoices"]) == 1


def test_already_paid_invoice_not_outstanding():
    """An invoice with amount_paid == amount_due is not outstanding."""
    stmt = _wrap_camt([])
    invoices = [
        {"invoice_no": "INV-PAID", "customer": "X", "amount_due": "100000",
         "amount_paid": "100000", "currency": "AMD", "due_date": "2026-06-30"},
    ]
    out = reconcile_payments_to_invoices(stmt, invoices, "AMD")
    # Open balance is 0; invoice is not "outstanding".
    assert out["unmatched_invoices"] == []
    assert out["totals"]["outstanding"] == Decimal("0")
