"""``on_company_created`` hook for frappe_uae."""
from __future__ import annotations

import frappe

from frappe_uae.setup_wizard.log import (
    STATUS_INVITED,
    create_log_row,
)
from frappe_uae.setup_wizard.run_setup import is_uae_company


def on_company_created(doc, method=None) -> None:
    """Frappe document-event hook. ``doc`` is a Company document.

    Writes an Invited log row when a new Company is created. The
    actual setup work (COA seed, custom fields) is triggered later
    via the wizard UI or bench-execute.
    """
    if not doc or getattr(doc, "doctype", None) != "Company":
        return
    if not frappe.db:
        return
    if not is_uae_company(doc):
        return
    create_log_row(
        company=doc.name,
        country=getattr(doc, "country", None),
        default_currency=getattr(doc, "default_currency", None),
        status=STATUS_INVITED,
    )
