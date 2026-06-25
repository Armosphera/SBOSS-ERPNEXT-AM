"""``run_armenian_setup`` -- the user-visible Armenia-setup entry point.

Behaviour summary
-----------------
``run_armenian_setup(company_name)``:

1. Loads the Company document.
2. If the company is Armenian (country=="Armenia" or
   default_currency=="AMD"):
     a. Ensures the Armenia custom fields exist on the Account DocType
        (``account_name_hy``). Idempotent via
        ``frappe_armenia.custom_fields.ensure_custom_fields``.
     b. Runs ``seed_armenian_coa(company)`` to insert the COA. Skips
        any account number that already exists.
     c. Creates or updates the AM Setup Wizard Log row for the company
        with status=Completed, accounts_seeded=<count>,
        custom_fields_registered=1, completed_at=now.
3. If the company is NOT Armenian:
     a. Writes a log row with status=Skipped.
     b. Returns immediately. No custom fields, no COA.

Idempotency
-----------
The function is safe to call multiple times:

- The custom-fields helper is idempotent (uses
  ``create_custom_fields(..., update=True)``).
- ``seed_armenian_coa`` skips existing accounts.
- A Completed log row short-circuits the second call to zero work.

Return value
------------
A dict shaped like::

    {
        "company": str,
        "ran": bool,
        "status": "Completed" | "Skipped",
        "accounts_seeded": int,
        "custom_fields_registered": bool,
    }
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import frappe

from frappe_armenia.coa import seed_armenian_coa
from frappe_armenia.custom_fields import ensure_custom_fields
from frappe_armenia.setup_wizard.log import (
    DOCTYPE,
    STATUS_COMPLETED,
    STATUS_SKIPPED,
    STATUS_STARTED,
    create_log_row,
    get_log_for_company,
    update_log_status,
)


_ARMENIA_COUNTRY = "Armenia"
_ARMENIA_CURRENCY = "AMD"


def _now() -> datetime:
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


def is_armenian_company(company_or_dict: Any) -> bool:
    """Pure branch-detection: ``country == 'Armenia'`` or ``default_currency == 'AMD'``.

    Accepts a Company document, a dict, or any object with ``.country`` and
    ``.default_currency`` attributes.
    """
    country = None
    currency = None
    if isinstance(company_or_dict, dict):
        country = company_or_dict.get("country")
        currency = company_or_dict.get("default_currency")
    else:
        country = getattr(company_or_dict, "country", None)
        currency = getattr(company_or_dict, "default_currency", None)

    def _eq(a, b):
        return (a or "").strip().lower() == b.lower()

    return _eq(country, _ARMENIA_COUNTRY) or _eq(currency, _ARMENIA_CURRENCY)


def _load_company(company_name: str) -> Any:
    if not frappe.db.exists("Company", company_name):
        raise ValueError(f"Company {company_name!r} does not exist")
    return frappe.get_doc("Company", company_name)


def run_armenian_setup(company_name: str) -> dict[str, Any]:
    """Idempotent Armenia setup for an existing Company.

    Raises ``ValueError`` if the Company doesn't exist.
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

    if not is_armenian_company(company_doc):
        # Foreign company -- record a Skipped row and bail.
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

    # Armenian company: do the work.

    # Idempotency: if a Completed log row already exists, no-op.
    existing_log = get_log_for_company(company_name)
    if existing_log:
        existing_status = frappe.db.get_value(DOCTYPE, existing_log, "status")
        if existing_status == STATUS_COMPLETED:
            # Re-fetch the row to report accurate counts.
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

    # 1. Custom fields (idempotent).
    custom_fields_registered = False
    try:
        ensure_custom_fields()
        custom_fields_registered = True
    except Exception:
        frappe.log_error(
            title="frappe_armenia.setup_wizard.ensure_custom_fields failed",
            message=frappe.get_traceback(),
        )

    # 2. Seed the COA.
    seeded = seed_armenian_coa(company_name)

    # 3. Mark Completed.
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
        "accounts_seeded": int(seeded),
        "custom_fields_registered": custom_fields_registered,
    }