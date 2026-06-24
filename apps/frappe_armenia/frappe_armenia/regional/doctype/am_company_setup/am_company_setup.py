"""
AM Company Setup - Armenian company-specific settings.

Contract A: DocType name is "AM Company Setup" (with space).
Upstream-survivability: this DocType extends the standard Company via a
separate linked single-row DocType. Never modifies the standard Company DocType.
"""
import frappe
from frappe import _
from frappe.model.document import Document


def validate_tin(tin: str) -> bool:
    """Armenian taxpayer identification number (HHID / ՀՎՀՀ): exactly 8 digits.

    Reference: Armenian Tax Code Article 52.
    """
    if not tin or not isinstance(tin, str):
        return False
    return len(tin) == 8 and tin.isdigit()


class AMCompanySetup(Document):
    def validate(self):
        # TIN format check
        if not validate_tin(self.taxpayer_identification_number):
            frappe.throw(
                _("TIN (HHID/ՀՎՀՀ) must be exactly 8 digits. Got: {0}").format(
                    self.taxpayer_identification_number
                ),
                title=_("Invalid TIN"),
            )

        # Single-row-per-company enforcement
        existing = frappe.db.exists(
            "AM Company Setup",
            {"company": self.company, "name": ("!=", self.name)},
        )
        if existing:
            frappe.throw(
                _("AM Company Setup already exists for company {0}").format(self.company),
                frappe.DuplicateEntryError,
            )
