"""AE Setup Wizard Log — audit trail for the UAE Setup Wizard step.

This DocType stores one row per Company-wizard invocation. The actual
mutation logic lives in ``frappe_uae.setup_wizard.log`` so the
controller stays small.

Contract A: DocType name is ``AE Setup Wizard Log`` (with spaces).
Upstream-survivability: this is a custom DocType in the frappe_uae
app, fully owned by us; no upstream ERPNext files are touched.
"""
from __future__ import annotations

import frappe
from frappe.model.document import Document


class AESetupWizardLog(Document):
    """Controller for the AE Setup Wizard Log DocType.

    All writes go through the ``frappe_uae.setup_wizard.log`` helpers.
    """
    pass
