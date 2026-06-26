"""AM VAT Settings - Armenian VAT settings for a company.

Contract A: DocType name is ``AM VAT Settings``.
Upstream-survivability: this is a custom DocType in the frappe_armenia
app, fully owned by us; no upstream ERPNext files are touched.
"""
import frappe
from frappe.model.document import Document


class AMVATSettings(Document):
    """Controller for the AM VAT Settings DocType."""
    pass
