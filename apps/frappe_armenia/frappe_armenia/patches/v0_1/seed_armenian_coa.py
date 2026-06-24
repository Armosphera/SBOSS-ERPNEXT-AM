"""frappe_armenia.patches.v0_1.seed_armenian_coa

Patch: seed the Armenian Chart of Accounts for any company that
exists in the current site and does not yet have the COA installed.

This patch is idempotent: it calls `seed_armenian_coa(company)` which
skips accounts that already exist (checked by `(company, account_number)`).
"""
import frappe

from frappe_armenia.coa.install_coa import seed_armenian_coa


def execute():
    """Run the seed patch for every existing company on this site."""
    companies = frappe.get_all("Company", pluck="name")
    for company in companies:
        # Skip the bench's bootstrap company (no real chart of accounts yet)
        if company in ("Administrator",):
            continue
        # Idempotent: returns 0 if the COA is already seeded
        try:
            created = seed_armenian_coa(company)
            if created:
                frappe.logger("frappe_armenia").info(
                    f"[W1-T04 patch] seeded {created} Armenian COA accounts for {company!r}"
                )
        except Exception as e:  # pragma: no cover - logging-only
            frappe.log_error(
                f"Failed to seed Armenian COA for {company!r}: {e}",
                "frappe_armenia.patches.v0_1.seed_armenian_coa",
            )
