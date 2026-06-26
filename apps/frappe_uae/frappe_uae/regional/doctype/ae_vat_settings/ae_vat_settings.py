"""AE VAT Settings - UAE VAT settings for a company.

Contract A: DocType name is ``AE VAT Settings``.
Upstream-survivability: this is a custom DocType in the frappe_uae
app, fully owned by us; no upstream ERPNext files are touched.
"""
import frappe
from frappe.model.document import Document


class AEVATSettings(Document):
    """Controller for the AE VAT Settings DocType."""
    pass
