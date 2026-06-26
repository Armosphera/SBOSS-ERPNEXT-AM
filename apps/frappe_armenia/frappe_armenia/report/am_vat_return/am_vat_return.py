"""AM VAT Return — Armenian VAT return report (W1-T15).

Aggregates OUTPUT VAT (from submitted Sales Invoices) and INPUT VAT
(from submitted Purchase Invoices) within a date range, and computes
the net VAT payable (or refundable) for the period.

The pure helper :func:`compute_vat_return` is exposed for unit testing.
The Frappe-facing :class:`VATReturnReport` wraps it as a Script Report.
"""
from __future__ import annotations

from typing import Any

import frappe


def compute_vat_return(
    company: str,
    from_date: str,
    to_date: str,
) -> dict[str, Any]:
    """Return OUTPUT VAT, INPUT VAT, NET VAT and invoice counts for the period.

    Parameters
    ----------
    company : str
        Company name (must match ``Sales Invoice.company``).
    from_date, to_date : str
        Inclusive posting-date bounds (``YYYY-MM-DD``).

    Returns
    -------
    dict
        ``output_vat``, ``input_vat``, ``net_vat`` (all floats in AMD),
        plus ``output_invoice_count`` and ``input_invoice_count`` (ints).

    Notes
    -----
    - Only submitted invoices (``docstatus = 1``) are included.
    - Tax amounts come from each invoice's
      ``total_taxes_and_charges`` column — same source the
      ``validate_invoice_vat`` hook checks against.
    - Defensive: an unknown company / no rows yields all zeros
      (does not raise).
    """
    output_vat, output_count = _aggregate_vat("Sales Invoice", company, from_date, to_date)
    input_vat, input_count = _aggregate_vat("Purchase Invoice", company, from_date, to_date)

    return {
        "company": company,
        "from_date": from_date,
        "to_date": to_date,
        "output_vat": round(output_vat, 2),
        "input_vat": round(input_vat, 2),
        "net_vat": round(output_vat - input_vat, 2),
        "output_invoice_count": output_count,
        "input_invoice_count": input_count,
    }


def _aggregate_vat(doctype: str, company: str, from_date: str, to_date: str) -> tuple[float, int]:
    """Sum total_taxes_and_charges and count rows for the given DocType + period.

    Uses raw SQL with ``COALESCE(SUM(...), 0)`` so the result is always a
    row even when no invoices match. Returns (vat_sum, count).
    """
    # Whitelist-safe: only DocType name interpolated, all values as params.
    sql = (
        f"SELECT COALESCE(SUM(`total_taxes_and_charges`), 0) AS vat_sum, "
        f"COUNT(*) AS inv_count "
        f"FROM `tab{doctype}` "
        f"WHERE `company` = %(company)s "
        f"AND `posting_date` BETWEEN %(from_date)s AND %(to_date)s "
        f"AND `docstatus` = 1"
    )
    row = frappe.db.sql(
        sql,
        values={"company": company, "from_date": from_date, "to_date": to_date},
        as_dict=True,
    )[0]
    # Dict-style access so this works with both frappe._dict and plain dicts
    # (the latter being what unit-test mocks typically return).
    return float(row["vat_sum"] or 0.0), int(row["inv_count"] or 0)


# Frappe Script Report boilerplate ----------------------------------------


def execute(filters: dict | None = None):
    """Frappe Script Report entrypoint."""
    filters = filters or {}
    company = filters.get("company")
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")

    if not (company and from_date and to_date):
        return (
            ["Section", "Amount (AMD)"],
            [{"section": "Please set Company, From Date and To Date.", "amount": None}],
            None,
            None,
            None,
        )

    summary = compute_vat_return(company, from_date, to_date)

    columns = [
        {"label": "Section", "fieldname": "section", "fieldtype": "Data", "width": 280},
        {"label": "Amount (AMD)", "fieldname": "amount", "fieldtype": "Currency", "width": 180},
    ]

    data = [
        {"section": "Period", "amount": f"{from_date} → {to_date}"},
        {"section": "Company", "amount": company},
        {"section": "Output VAT (Sales Invoices)", "amount": summary["output_vat"]},
        {"section": "Input VAT (Purchase Invoices)", "amount": summary["input_vat"]},
        {"section": "Net VAT Payable / (Refundable)", "amount": summary["net_vat"]},
        {"section": "Sales invoices in period", "amount": summary["output_invoice_count"]},
        {"section": "Purchase invoices in period", "amount": summary["input_invoice_count"]},
    ]

    report_summary = [
        {"label": "Output VAT", "value": summary["output_vat"], "datatype": "Currency"},
        {"label": "Input VAT", "value": summary["input_vat"], "datatype": "Currency"},
        {"label": "Net VAT", "value": summary["net_vat"], "datatype": "Currency"},
    ]

    return columns, data, None, None, report_summary