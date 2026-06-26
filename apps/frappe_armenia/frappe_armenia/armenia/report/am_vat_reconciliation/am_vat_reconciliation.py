"""AM VAT Reconciliation — Armenian VAT input/output reconciliation report (W1-T16).

For a date range, groups OUTPUT VAT (from submitted Sales Invoices) and
INPUT VAT (from submitted Purchase Invoices) into monthly buckets and
returns per-month + total net VAT. Useful for filing-period reconciliation
against the GL and for spotting period-end mismatches.

The pure helper :func:`compute_vat_reconciliation` is exposed for unit
testing. The Frappe-facing :class:`VATReconciliationReport` wraps it as
a Script Report.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from typing import Any

import frappe


def _month_start(d: date) -> date:
    """Return the first day of the month containing d."""
    return d.replace(day=1)


def _month_end(d: date) -> date:
    """Return the last day of the month containing d."""
    last_day = monthrange(d.year, d.month)[1]
    return d.replace(day=last_day)


def _month_buckets(from_date: date, to_date: date) -> list[tuple[date, date, str, date]]:
    """Yield (bucket_start, bucket_end, label, first_of_month) for each month.

    ``bucket_start`` is the actual start date of the bucket (may be a
    mid-month date if the period starts mid-month). ``label`` and
    ``first_of_month`` are always the first day of that month.
    """
    buckets = []
    first_of_month = _month_start(from_date)
    cursor = _month_start(from_date)
    while cursor <= to_date:
        end = _month_end(cursor)
        if end > to_date:
            end = to_date
        bucket_start = cursor if cursor >= from_date else from_date
        label = first_of_month.isoformat()  # YYYY-MM-DD, always first-of-month
        buckets.append((bucket_start, end, label, first_of_month))
        # advance to next month
        if cursor.month == 12:
            cursor = cursor.replace(year=cursor.year + 1, month=1)
            first_of_month = cursor
        else:
            cursor = cursor.replace(month=cursor.month + 1)
            first_of_month = cursor
    return buckets


def _aggregate_vat_for_period(
    doctype: str, company: str, from_date: str, to_date: str
) -> tuple[float, int]:
    """Sum total_taxes_and_charges and count rows for the given DocType + period.

    Uses raw SQL with ``COALESCE(SUM(...), 0)`` so the result is always a
    row even when no invoices match. Returns (vat_sum, count).
    """
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


def compute_vat_reconciliation(
    company: str, from_date: str, to_date: str
) -> dict[str, Any]:
    """Return per-month output/input/net VAT plus totals for the period.

    Parameters
    ----------
    company : str
        Company name (must match ``Sales Invoice.company`` and
        ``Purchase Invoice.company``).
    from_date, to_date : str
        Inclusive posting-date bounds (``YYYY-MM-DD``).

    Returns
    -------
    dict
        - ``company``, ``from_date``, ``to_date`` — echo of inputs
        - ``buckets``: list of {month, from_date, to_date, output_vat,
          input_vat, net_vat, output_count, input_count}
        - ``total_output_vat``, ``total_input_vat``, ``total_net_vat`` —
          sums across all buckets (floats, AMD)
        - ``total_output_count``, ``total_input_count`` — invoice counts

    Notes
    -----
    - Only submitted invoices (``docstatus = 1``) are included.
    - Tax amounts come from each invoice's
      ``total_taxes_and_charges`` column — same source the
      ``validate_invoice_vat`` hook checks against.
    - Defensive: an unknown company / no rows yields zero buckets and
      zero totals (does not raise).
    """
    from_d = date.fromisoformat(from_date)
    to_d = date.fromisoformat(to_date)

    buckets = []
    total_output = 0.0
    total_input = 0.0
    total_output_count = 0
    total_input_count = 0

    for bucket_from, bucket_to, label, _first in _month_buckets(from_d, to_d):
        out_vat, out_count = _aggregate_vat_for_period(
            "Sales Invoice", company, bucket_from.isoformat(), bucket_to.isoformat()
        )
        in_vat, in_count = _aggregate_vat_for_period(
            "Purchase Invoice", company, bucket_from.isoformat(), bucket_to.isoformat()
        )
        net = round(out_vat - in_vat, 2)
        buckets.append({
            "month": label,
            "from_date": bucket_from.isoformat(),
            "to_date": bucket_to.isoformat(),
            "output_vat": round(out_vat, 2),
            "input_vat": round(in_vat, 2),
            "net_vat": net,
            "output_count": out_count,
            "input_count": in_count,
        })
        total_output += out_vat
        total_input += in_vat
        total_output_count += out_count
        total_input_count += in_count

    return {
        "company": company,
        "from_date": from_date,
        "to_date": to_date,
        "buckets": buckets,
        "total_output_vat": round(total_output, 2),
        "total_input_vat": round(total_input, 2),
        "total_net_vat": round(total_output - total_input, 2),
        "total_output_count": total_output_count,
        "total_input_count": total_input_count,
    }


# Frappe Script Report boilerplate ----------------------------------------


def execute(filters: dict | None = None):
    """Frappe Script Report entrypoint."""
    filters = filters or {}
    company = filters.get("company")
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")

    if not (company and from_date and to_date):
        return (
            ["Month", "Output VAT (AMD)", "Input VAT (AMD)", "Net VAT (AMD)",
             "Output Invoices", "Input Invoices"],
            [{"month": "Please set Company, From Date and To Date.",
              "output_vat_(amd)": None, "input_vat_(amd)": None,
              "net_vat_(amd)": None, "output_invoices": None,
              "input_invoices": None}],
            None,
            None,
            None,
        )

    summary = compute_vat_reconciliation(company, from_date, to_date)

    columns = [
        {"label": "Month", "fieldname": "month", "fieldtype": "Data", "width": 100},
        {"label": "Period", "fieldname": "period", "fieldtype": "Data", "width": 200},
        {"label": "Output VAT (AMD)", "fieldname": "output_vat",
         "fieldtype": "Currency", "width": 160},
        {"label": "Input VAT (AMD)", "fieldname": "input_vat",
         "fieldtype": "Currency", "width": 160},
        {"label": "Net VAT (AMD)", "fieldname": "net_vat",
         "fieldtype": "Currency", "width": 160},
        {"label": "Output Invoices", "fieldname": "output_invoices",
         "fieldtype": "Int", "width": 110},
        {"label": "Input Invoices", "fieldname": "input_invoices",
         "fieldtype": "Int", "width": 110},
    ]

    data = []
    for b in summary["buckets"]:
        data.append({
            "month": b["month"],
            "period": f"{b['from_date']} → {b['to_date']}",
            "output_vat": b["output_vat"],
            "input_vat": b["input_vat"],
            "net_vat": b["net_vat"],
            "output_invoices": b["output_count"],
            "input_invoices": b["input_count"],
        })
    # Totals row
    data.append({
        "month": "TOTAL",
        "period": f"{from_date} → {to_date}",
        "output_vat": summary["total_output_vat"],
        "input_vat": summary["total_input_vat"],
        "net_vat": summary["total_net_vat"],
        "output_invoices": summary["total_output_count"],
        "input_invoices": summary["total_input_count"],
    })

    report_summary = [
        {"label": "Output VAT", "value": summary["total_output_vat"], "datatype": "Currency"},
        {"label": "Input VAT", "value": summary["total_input_vat"], "datatype": "Currency"},
        {"label": "Net VAT", "value": summary["total_net_vat"], "datatype": "Currency"},
        {"label": "Output Invoices", "value": summary["total_output_count"], "datatype": "Int"},
        {"label": "Input Invoices", "value": summary["total_input_count"], "datatype": "Int"},
    ]

    return columns, data, None, None, report_summary