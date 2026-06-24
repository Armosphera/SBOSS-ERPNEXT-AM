"""
Patch: seed_uae_coa
Idempotently insert the UAE IFRS Chart of Accounts into all UAE companies.

Runs on `bench migrate` after install.
"""
from __future__ import annotations

import frappe

from frappe_uae.coa import seed_uae_coa


def execute() -> None:
    """Seed the UAE COA for every UAE-jurisdiction company in the site.

    A company is identified as UAE-jurisdiction by:
        - default_currency == "AED", or
        - country == "United Arab Emirates"

    Companies that don't match are skipped (Armenia/India/other apps
    have their own COA seeders).
    """
    companies = frappe.get_all(
        "Company",
        fields=["name", "default_currency", "country"],
    )
    uaes = [
        c
        for c in companies
        if (c.get("default_currency") == "AED")
        or (c.get("country") in ("United Arab Emirates", "UAE", "AE"))
    ]
    if not uaes:
        frappe.logger("frappe_uae").info(
            "seed_uae_coa: no UAE companies on this site; skipping"
        )
        return
    for c in uaes:
        try:
            result = seed_uae_coa(c["name"])
            frappe.logger("frappe_uae").info(
                f"seed_uae_coa: {c['name']}: {result}"
            )
        except Exception as e:
            frappe.log_error(
                title=f"UAE COA seed failed for {c['name']}",
                message=str(e),
            )
