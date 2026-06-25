"""UAE Setup Wizard step — public entry point.

``run_uae_setup(company_name)`` is the UAE equivalent of the Armenia
setup wizard. Idempotent. Safe to call multiple times.

Behaviour:
1. Load the Company.
2. If UAE-jurisdiction (country in {UAE, AE, United Arab Emirates} or
   default_currency==AED):
     a. Ensure the UAE custom fields exist on the Account DocType
        (``account_name_ar``).
     b. Run ``seed_uae_coa(company)`` to insert the COA. Skips any
        account name that already exists.
     c. Create or update the AE Setup Wizard Log row.
3. If not UAE-jurisdiction: write a Skipped log row, return.

Returns a dict with the same shape as run_armenian_setup().
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import frappe

from frappe_uae.coa import seed_uae_coa
from frappe_uae.custom_fields import ensure_custom_fields
from frappe_uae.setup_wizard.log import (
    DOCTYPE,
    STATUS_COMPLETED,
    STATUS_SKIPPED,
    STATUS_STARTED,
    create_log_row,
    get_log_for_company,
    update_log_status,
)


_UAE_COUNTRIES = ("UAE", "AE", "United Arab Emirates")
_UAE_CURRENCY = "AED"


def _eq(a, b):
    return (a or "").strip().lower() == b.lower()


def is_uae_company(company_doc) -> bool:
    country = getattr(company_doc, "country", None)
    currency = getattr(company_doc, "default_currency", None)
    if currency and currency.upper() == _UAE_CURRENCY:
        return True
    if country and any(_eq(country, c) for c in _UAE_COUNTRIES):
        return True
    return False


def _load_company(company_name: str):
    if not frappe.db.exists("Company", company_name):
        raise ValueError(f"Company {company_name!r} does not exist")
    return frappe.get_doc("Company", company_name)


def _now():
    return datetime.now()


def run_uae_setup(company_name: str) -> dict[str, Any]:
    """Idempotent UAE setup for an existing Company.

    Raises ValueError if the Company doesn't exist.
    """
    company_doc = _load_company(company_name)
    country = getattr(company_doc, "country", None)
    currency = getattr(company_doc, "default_currency", None)

    base_result: dict[str, Any] = {
        "company": company_name,
        "ran": False,
        "status": None,
        "accounts_seeded": 0,
        "custom_fields_registered": False,
    }

    if not is_uae_company(company_doc):
        create_log_row(
            company=company_name,
            country=country,
            default_currency=currency,
            status=STATUS_SKIPPED,
        )
        update_log_status(
            company_name,
            country=country or "",
            default_currency=currency or "",
            completed_at=_now(),
        )
        base_result["status"] = STATUS_SKIPPED
        return base_result

    # UAE company: do the work.
    existing_log = get_log_for_company(company_name)
    if existing_log:
        existing_status = frappe.db.get_value(DOCTYPE, existing_log, "status")
        if existing_status == STATUS_COMPLETED:
            row = frappe.get_doc(DOCTYPE, existing_log)
            return {
                "company": company_name,
                "ran": False,
                "status": STATUS_COMPLETED,
                "accounts_seeded": int(row.get("accounts_seeded") or 0),
                "custom_fields_registered": bool(row.get("custom_fields_registered")),
            }

    # Mark Started so we can audit partial runs.
    create_log_row(
        company=company_name,
        country=country,
        default_currency=currency,
        status=STATUS_STARTED,
    )
    update_log_status(
        company_name,
        status=STATUS_STARTED,
        started_at=_now(),
    )

    custom_fields_registered = False
    try:
        ensure_custom_fields()
        custom_fields_registered = True
    except Exception:
        frappe.log_error(
            title="frappe_uae.setup_wizard.ensure_custom_fields failed",
            message=frappe.get_traceback(),
        )

    # Seed the COA.
    seed_result = seed_uae_coa(company_name)
    seeded = seed_result.get("inserted", 0) if isinstance(seed_result, dict) else int(seed_result or 0)

    # Mark Completed.
    update_log_status(
        company_name,
        status=STATUS_COMPLETED,
        completed_at=_now(),
        accounts_seeded=seeded,
        custom_fields_registered=custom_fields_registered,
        country=country or "",
        default_currency=currency or "",
    )

    return {
        "company": company_name,
        "ran": True,
        "status": STATUS_COMPLETED,
        "accounts_seeded": int(seeded if not isinstance(seeded, dict) else seeded.get("inserted", 0)),
        "custom_fields_registered": custom_fields_registered,
    }
