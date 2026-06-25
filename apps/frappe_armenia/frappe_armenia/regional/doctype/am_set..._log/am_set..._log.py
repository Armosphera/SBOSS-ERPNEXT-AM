"""
AM Setup Wizard Log - audit trail for the Armenia Setup Wizard step.

This DocType stores one row per Company-wizard invocation. The actual
mutation logic lives in ``frappe_armenia.setup_wizard.log`` so the
controller stays small.

Contract A: DocType name is ``AM Setup Wizard Log`` (with spaces).
Upstream-survivability: this is a custom DocType in the frappe_armenia
app, fully owned by us; no upstream ERPNext files are touched.
"""
import frappe
from frappe.model.document import Document


class AMSetupWizardLog(Document):
    """Controller for the AM Setup Wizard Log DocType.

    No business logic in the controller itself -- all writes go through
    the ``frappe_armenia.setup_wizard.log`` helpers so the wizard can
    stay free of DocType-name strings.
    """

    def validate(self) -> None:
        # Single-row-per-company enforcement. The Company Link field is
        # already `unique`, so DB-level constraints back this up. The
        # extra Python check gives a friendlier error message and also
        # protects against bulk-insert paths that skip DB-level uniques
        # during tests.
        if not self.company:
            return
        existing = frappe.db.exists(
            "AM Setup Wizard Log",
            {"company": self.company, "name": ("!=", self.name)},
        )
        if existing:
            frappe.throw(
                f"AM Setup Wizard Log already exists for company {self.company}",
                frappe.DuplicateEntryError,
            )