"""
Tests for the Armenian account_name_hy custom field and the
set_hy_account_name helper (W1-T05).

TDD: written first, run against the live erpnext.localhost site.
"""
from __future__ import annotations

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_armenia.custom_fields import (
    ACCOUNT_NAME_HY_FIELD,
    CUSTOM_FIELDS,
    get_account_custom_fields,
)
from frappe_armenia.coa.install_coa import set_hy_account_name


_TEST_COMPANY = "_Test AM W1T05"


def _make_test_company() -> None:
    if frappe.db.exists("Company", _TEST_COMPANY):
        return
    doc = frappe.get_doc({
        "doctype": "Company",
        "company_name": _TEST_COMPANY,
        "abbr": "_TAM1T05",
        "default_currency": "AMD",
        "country": "Armenia",
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()


def _wipe_company_accounts() -> None:
    frappe.db.delete("Account", {"company": _TEST_COMPANY})
    frappe.db.commit()


def _ensure_root_group() -> str:
    """Create one root group for the test to anchor any leaf accounts.

    Returns the full stored Account name (Frappe prepends account_number
    and appends company abbr).
    """
    full_name = f"1000 - Root Group - _TAM1T05"
    if not frappe.db.exists("Account", full_name):
        doc = frappe.get_doc({
            "doctype": "Account",
            "company": _TEST_COMPANY,
            "account_number": "1000",
            "account_name": "Root Group",
            "root_type": "Asset",
            "is_group": 1,
            "account_currency": "AMD",
        })
        doc.insert(ignore_permissions=True, ignore_mandatory=True)
        frappe.db.commit()
    return full_name


class TestAccountNameHY(FrappeTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # Ensure the custom fields exist (idempotent)
        from frappe_armenia.custom_fields import ensure_custom_fields
        ensure_custom_fields()
        _make_test_company()
        _wipe_company_accounts()
        _ensure_root_group()

    @classmethod
    def tearDownClass(cls) -> None:
        _wipe_company_accounts()
        super().tearDownClass()

    def test_custom_field_registered(self):
        # The custom field is in the database; verify via direct SQL and meta.
        custom_field_names = {
            r.fieldname
            for r in frappe.db.sql(
                "SELECT fieldname FROM `tabCustom Field` WHERE dt = %s",
                "Account",
                as_dict=True,
            )
        }
        self.assertIn("account_name_hy", custom_field_names)

        # And it shows up in the meta's custom field list.
        meta = frappe.get_meta("Account")
        custom_fields = {f.fieldname: f for f in (meta.get_custom_fields() or [])}
        self.assertIn("account_name_hy", custom_fields)
        cf = custom_fields["account_name_hy"]
        self.assertEqual(cf.fieldtype, "Data")
        self.assertEqual(cf.insert_after, "account_name")
        self.assertEqual(cf.read_only, 0)
        self.assertEqual(cf.hidden, 0)
        # Depends on company being set (custom_fields visibility)
        self.assertIn("doc.company", cf.depends_on or "")

    def test_get_account_custom_fields_shape(self):
        fields = get_account_custom_fields()
        self.assertIn("Account", fields)
        names = [f["fieldname"] for f in fields["Account"]]
        self.assertIn("account_name_hy", names)
        # And it should match the module-level constant
        self.assertEqual(ACCOUNT_NAME_HY_FIELD["fieldname"], "account_name_hy")
        # CUSTOM_FIELDS should be the same object as what get_account_custom_fields returns
        self.assertIs(CUSTOM_FIELDS, fields)

    def test_set_hy_account_name_persists(self):
        root = f"1000 - Root Group - _TAM1T05"
        # Create a leaf account under the root
        leaf = frappe.get_doc({
            "doctype": "Account",
            "company": _TEST_COMPANY,
            "account_number": "1100",
            "account_name": "Cash on Hand",
            "root_type": "Asset",
            "account_type": "Cash",
            "is_group": 0,
            "account_currency": "AMD",
            "parent_account": root,
        })
        leaf.insert(ignore_permissions=True)
        frappe.db.commit()

        # Set Armenian name via the helper
        set_hy_account_name(leaf.name, "Ձեռքի դրամ")
        frappe.db.commit()

        # Re-read and verify
        reloaded = frappe.get_doc("Account", leaf.name)
        self.assertEqual(reloaded.account_name, "Cash on Hand")
        self.assertEqual(reloaded.account_name_hy, "Ձեռքի դրամ")

    def test_set_hy_account_name_armenian_text_round_trip(self):
        """Tricky Armenian text: includes ձ, ու, mixed case, digits, punctuation."""
        root = f"1000 - Root Group - _TAM1T05"
        leaf = frappe.get_doc({
            "doctype": "Account",
            "company": _TEST_COMPANY,
            "account_number": "1200",
            "account_name": "Bank Account (Test)",
            "root_type": "Asset",
            "account_type": "Bank",
            "is_group": 0,
            "account_currency": "AMD",
            "parent_account": root,
        })
        leaf.insert(ignore_permissions=True)
        frappe.db.commit()

        tricky = "Բանկային հաշիվ (թեստ) - № 12345"
        set_hy_account_name(leaf.name, tricky)
        frappe.db.commit()

        reloaded = frappe.get_doc("Account", leaf.name)
        self.assertEqual(reloaded.account_name_hy, tricky)
