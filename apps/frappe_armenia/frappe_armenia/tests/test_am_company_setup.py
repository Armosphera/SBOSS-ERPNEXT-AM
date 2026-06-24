"""
Tests for AM Company Setup DocType (W1-T01).

Imports the controller from the regional.doctype.am_company_setup submodule.
The submodule name is the same as the actual directory name (16 chars),
NOT a sanitized placeholder. Path is dynamic in case the install
script ever renames the dir.
"""
import os
import unittest

import frappe
from frappe.tests.utils import FrappeTestCase

# Build the import path at runtime from the actual directory layout
_REGION_DIR = os.path.join(
    os.path.dirname(__file__),
    "..", "regional", "doctype",
)
_REGION_DIR = os.path.abspath(_REGION_DIR)
_DOCTYPE_DIR = None
for n in os.listdir(_REGION_DIR):
    full = os.path.join(_REGION_DIR, n)
    if os.path.isdir(full) and n != "__pycache__":
        _DOCTYPE_DIR = full
        break
assert _DOCTYPE_DIR is not None, f"No DocType dir found in {_REGION_DIR!r}"

# Use importlib so we don't hardcode a sanitized path in the source
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location(
    "am_company_setup_controller",
    os.path.join(_DOCTYPE_DIR, n + ".py"),
)
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

validate_tin = _mod.validate_tin
AMCompanySetup = _mod.AMCompanySetup


class TestAMCompanySetup(FrappeTestCase):
    def test_doctype_exists(self):
        meta = frappe.get_meta("AM Company Setup")
        self.assertTrue(meta.custom)
        # The DocType module is the app name (set during bootstrap)
        self.assertEqual(meta.module, "frappe_armenia")

    def test_required_fields(self):
        meta = frappe.get_meta("AM Company Setup")
        field_names = {f.fieldname for f in meta.fields}
        for required in (
            "company",
            "taxpayer_identification_number",
            "registration_number",
            "legal_form",
            "vat_treatment",
        ):
            self.assertIn(required, field_names, f"missing field {required}")

    def test_tin_validation_accepts_valid(self):
        self.assertTrue(validate_tin("01234567"))
        self.assertTrue(validate_tin("99999999"))
        self.assertTrue(validate_tin("00000000"))

    def test_tin_validation_rejects_invalid(self):
        self.assertFalse(validate_tin("1234567"))  # too short
        self.assertFalse(validate_tin("012345678"))  # too long
        self.assertFalse(validate_tin("abcdefgh"))  # not digits
        self.assertFalse(validate_tin(""))  # empty
        self.assertFalse(validate_tin(None))  # None
        self.assertFalse(validate_tin("0123-567"))  # dash

    def test_insert_and_read_round_trip(self):
        test_company = "_Test Company"
        if not frappe.db.exists("Company", test_company):
            self.skipTest(f"Test company {test_company!r} not present in this site")
        existing = frappe.db.exists("AM Company Setup", {"company": test_company})
        if existing:
            frappe.delete_doc("AM Company Setup", existing, force=True)

        doc = frappe.get_doc({
            "doctype": "AM Company Setup",
            "company": test_company,
            "taxpayer_identification_number": "01234567",
            "registration_number": "12345678",
            "legal_form": "LLC",
            "vat_treatment": "Standard",
        })
        doc.insert(ignore_permissions=True)
        loaded = frappe.get_doc("AM Company Setup", doc.name)
        self.assertEqual(loaded.taxpayer_identification_number, "01234567")
        self.assertEqual(loaded.legal_form, "LLC")
        self.assertEqual(loaded.vat_treatment, "Standard")

    def test_single_row_per_company_enforced(self):
        test_company = "_Test Company"
        if not frappe.db.exists("Company", test_company):
            self.skipTest(f"Test company {test_company!r} not present in this site")
        existing = frappe.db.exists("AM Company Setup", {"company": test_company})
        if existing:
            frappe.delete_doc("AM Company Setup", existing, force=True)

        first = frappe.get_doc({
            "doctype": "AM Company Setup",
            "company": test_company,
            "taxpayer_identification_number": "01234567",
            "registration_number": "12345678",
            "legal_form": "LLC",
            "vat_treatment": "Standard",
        })
        first.insert(ignore_permissions=True)

        with self.assertRaises(frappe.DuplicateEntryError):
            frappe.get_doc({
                "doctype": "AM Company Setup",
                "company": test_company,
                "taxpayer_identification_number": "99999999",
                "registration_number": "88888888",
                "legal_form": "JSC",
                "vat_treatment": "Exempt",
            }).insert(ignore_permissions=True)

    def test_invalid_tin_rejected_on_save(self):
        test_company = "_Test Company 2"
        if not frappe.db.exists("Company", test_company):
            self.skipTest(f"Test company {test_company!r} not present in this site")
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc({
                "doctype": "AM Company Setup",
                "company": test_company,
                "taxpayer_identification_number": "BAD-TIN!",
                "registration_number": "12345678",
                "legal_form": "LLC",
                "vat_treatment": "Standard",
            }).insert(ignore_permissions=True)
