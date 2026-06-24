"""
Tests for W2-T05 — bilingual account_name_ar custom field on Account.

Spec:
- A Custom Field `account_name_ar` exists on the standard Account DocType.
  Properties:
    fieldname      = account_name_ar
    fieldtype      = Data
    label          = "Account Name (Arabic / اسم الحساب)"
    insert_after   = account_name
    depends_on     = eval:doc.company
    read_only      = 0
    hidden         = 0

- setting account_name_ar on a real Account doc persists and reads back.
- the helper set_ar_account_name(account_name, account_name_ar) updates both
  fields atomically.
- Arabic text round-trips correctly (no encoding corruption).

The test uses the live bench at erpnext.localhost per AGENTS.md.
"""
from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import (
    create_custom_fields as frappe_create_custom_fields,
)
from frappe.tests.utils import FrappeTestCase

from frappe_uae.coa.install_coa import set_ar_account_name
from frappe_uae.custom_fields import (
    ACCOUNT_NAME_AR_FIELD,
    CUSTOM_FIELDS,
    ensure_custom_fields,
)

# A representative Arabic string we use across several tests.
# Includes diacritics-free letters, a tatweel, and a question mark-free zone.
AR_SAMPLE = "الأصول غير المتداولة"
AR_SAMPLE_2 = "ذمم مدينة - مخصص الديون المشكوك في تحصيلها"


def _ensure_test_company() -> str:
    """Create _Test UAE Co (AED, UAE) if missing. Returns the company name."""
    TEST_COMPANY = "_Test UAE Co W2T05"
    if not frappe.db.exists("Warehouse Type", "Transit"):
        wt = frappe.get_doc({"doctype": "Warehouse Type", "name": "Transit"})
        wt.insert(ignore_permissions=True)
    if not frappe.db.exists("Fiscal Year", {"name": "2026"}):
        try:
            fy = frappe.get_doc({
                "doctype": "Fiscal Year",
                "year": "2026",
                "year_start_date": "2026-01-01",
                "year_end_date": "2026-12-31",
            })
            fy.insert(ignore_permissions=True)
        except Exception:
            pass
    if not frappe.db.exists("Company", TEST_COMPANY):
        co = frappe.get_doc({
            "doctype": "Company",
            "company_name": TEST_COMPANY,
            "abbr": "TU2T05",
            "country": "United Arab Emirates",
            "default_currency": "AED",
            "create_chart_of_accounts_based_on": None,
        })
        co.insert(ignore_permissions=True)
    return TEST_COMPANY


def _ensure_root_group(company: str, abbr: str) -> str:
    """Ensure a root group account exists for the test company.

    ERPNext's `Account.validate_root_details()` throws if a non-group
    account has no parent_account. The simplest way to create a leaf
    account is to create a group parent first, then attach leaves to it.
    """
    group_name = f"_Test Root Group - {abbr}"
    if frappe.db.exists("Account", group_name):
        return group_name
    grp = frappe.get_doc({
        "doctype": "Account",
        "company": company,
        "account_name": "_Test Root Group",
        # account_type must be empty so ERPNext treats it as a generic group
        "account_type": "",
        "root_type": "Asset",
        "is_group": 1,
        "account_currency": "AED",
    })
    # Root groups have no parent — bypass the mandatory parent_account check
    grp.flags.ignore_permissions = True
    grp.flags.ignore_mandatory = True
    grp.insert()
    return grp.name


class TestAccountNameArCustomField(FrappeTestCase):
    """TDD for W2-T05 — Custom Field account_name_ar on Account."""

    def setUp(self):
        # Make sure the custom field exists in the DB before each test.
        ensure_custom_fields()
        self.company = _ensure_test_company()
        # ERPNext requires non-group accounts to have a parent. Create one
        # root group per test to anchor the leaves.
        self.parent_account = _ensure_root_group(self.company, "TU2T05")

    def tearDown(self):
        # Don't leave a stack of test companies around across runs.
        frappe.db.rollback()

    # ------------------------------------------------------------------
    # 1) Custom field exists with correct properties
    # ------------------------------------------------------------------

    def test_custom_field_account_name_ar_exists(self):
        cf = frappe.get_doc(
            "Custom Field",
            {"dt": "Account", "fieldname": "account_name_ar"},
        )
        self.assertEqual(cf.fieldtype, "Data")
        self.assertEqual(cf.label, "Account Name (Arabic / اسم الحساب)")
        self.assertEqual(cf.insert_after, "account_name")
        self.assertEqual(cf.depends_on, "eval:doc.company")
        self.assertEqual(int(cf.read_only or 0), 0)
        self.assertEqual(int(cf.hidden or 0), 0)
        # Sanity: the constant in custom_fields matches what we read back
        self.assertEqual(ACCOUNT_NAME_AR_FIELD["fieldname"], "account_name_ar")
        self.assertEqual(CUSTOM_FIELDS["Account"][0]["fieldname"], "account_name_ar")

    # ------------------------------------------------------------------
    # 2) Setting account_name_ar on a real Account doc persists + reads back
    # ------------------------------------------------------------------

    def test_account_name_ar_persists_on_account_doc(self):
        en_name = f"W2T05 Test Account {frappe.generate_hash(length=6)}"
        ar_name = AR_SAMPLE
        acc = frappe.get_doc({
            "doctype": "Account",
            "company": self.company,
            "account_name": en_name,
            "account_name_ar": ar_name,
            "parent_account": self.parent_account,
            # account_type must be set explicitly to avoid ERPNext's auto-derive
            # picking a parent-only type and failing validation.
            "account_type": "",
            "root_type": "Asset",
            "is_group": 0,
        })
        acc.insert(ignore_permissions=True)
        acc.reload()
        self.assertEqual(acc.account_name, en_name)
        self.assertEqual(acc.account_name_ar, ar_name)

    # ------------------------------------------------------------------
    # 3) set_ar_account_name() helper updates both fields atomically
    # ------------------------------------------------------------------

    def test_set_ar_account_name_helper_updates_both_fields(self):
        en_name = f"W2T05 Helper Test {frappe.generate_hash(length=6)}"
        acc = frappe.get_doc({
            "doctype": "Account",
            "company": self.company,
            "account_name": en_name,
            "parent_account": self.parent_account,
            "account_type": "",
            "root_type": "Asset",
            "is_group": 0,
        })
        acc.insert(ignore_permissions=True)

        new_en = f"W2T05 Helper Test Renamed {frappe.generate_hash(length=6)}"
        new_ar = AR_SAMPLE_2
        result = set_ar_account_name(acc.name, new_en, new_ar)

        # Helper returns the loaded doc; both fields updated in one call.
        self.assertEqual(result.account_name, new_en)
        self.assertEqual(result.account_name_ar, new_ar)

        # Reload from DB to confirm persistence.
        acc.reload()
        self.assertEqual(acc.account_name, new_en)
        self.assertEqual(acc.account_name_ar, new_ar)

    def test_set_ar_account_name_helper_raises_for_missing_doc(self):
        # Calling on a non-existent account name must raise, not silently no-op.
        from frappe.exceptions import DoesNotExistError
        missing = f"DOES-NOT-EXIST-{frappe.generate_hash(length=8)}"
        with self.assertRaises((DoesNotExistError, frappe.DoesNotExistError, Exception)):
            set_ar_account_name(missing, "x", "س")

    # ------------------------------------------------------------------
    # 4) Arabic text round-trips correctly (no encoding corruption)
    # ------------------------------------------------------------------

    def test_arabic_text_round_trips(self):
        # Multi-line Arabic with punctuation, numbers, and mixed content.
        tricky = (
            "ذمم مدينة - مخصص الديون المشكوك في تحصيلها "
            "(مخصص) - 100% - 9٪ - الإمارات - الحساب: 1234-5678"
        )
        en_name = f"W2T05 Round-trip {frappe.generate_hash(length=6)}"
        acc = frappe.get_doc({
            "doctype": "Account",
            "company": self.company,
            "account_name": en_name,
            "account_name_ar": tricky,
            "parent_account": self.parent_account,
            "account_type": "",
            "root_type": "Liability",
            "is_group": 0,
        })
        acc.insert(ignore_permissions=True)

        # Reload — Frappe round-trips the value through MariaDB (utf8mb4).
        acc.reload()
        self.assertEqual(acc.account_name_ar, tricky)
        # Confirm the bytes really survived — encode to UTF-8 and check codepoints.
        self.assertEqual(len(acc.account_name_ar), len(tricky))
        self.assertEqual(
            acc.account_name_ar.encode("utf-8"),
            tricky.encode("utf-8"),
        )
        # Sanity: at least one Arabic codepoint (U+0600..U+06FF) is present.
        self.assertRegex(acc.account_name_ar, r"[\u0600-\u06FF]")
