"""``on_company_created`` hook -- write an Invited log row when a new Company is saved.

Frappe calls this hook with ``(doc, method)`` after a Company is inserted.
We do the cheap thing here: read country/currency off the doc, classify
the company, and write a single Invited log row. We deliberately do NOT
seed the COA or register custom fields here -- those are heavier and
could surprise the user mid-Onboarding. The wizard UI (or a manual
``bench execute`` call) drives the actual ``run_armenian_setup``.

Contract A is honoured by the log DocType name (``AM Setup Wizard Log``).
"""
from __future__ import annotations

import frappe

from frappe_armenia.setup_wizard.log import (
    STATUS_INVITED,
    create_log_row,
)
from frappe_armenia.setup_wizard.run_setup import is_armenian_company


def on_company_created(doc, method=None) -> None:
    """Frappe document-event hook. ``doc`` is a Company document.

    Safe to call from any site install / migration. We only WRITE a row
    when (a) the doc is a Company and (b) frappe has a DB connection
    (i.e. we're not in a migration context with no site).
    """
    if not doc or getattr(doc, "doctype", None) != "Company":
        return
    if not frappe.db:
        return

    company_name = doc.name
    country = getattr(doc, "country", None)
    currency = getattr(doc, "default_currency", None)

    if not is_armenian_company({"country": country, "default_currency": currency}):
        # Non-Armenian companies get no log row from this hook.
        return

    try:
        create_log_row(
            company=company_name,
            country=country,
            default_currency=currency,
            status=STATUS_INVITED,
        )
    except Exception:
        # The hook must never break Company creation. Swallow + log so
        # the operator sees a message in the bench log without the
        # transaction failing.
        frappe.log_error(
            title="frappe_armenia.setup_wizard.on_company_created failed",
            message=frappe.get_traceback(),
        )