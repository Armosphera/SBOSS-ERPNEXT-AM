"""
Tests for UAE COA (IFRS-style chart) — W2-T04.

The build_coa_tree() function must return a list of dicts shaped for
frappe.new_doc('Account').insert(). It must:
- total ~400 accounts
- cover all 5 root_types: Asset, Liability, Equity, Income, Expense
- cover the 9 top-level groups (1xxx..9xxx)
- have 100+ Asset accounts, 60+ Liability, 15+ Equity, 25+ Income, 80+ Expense
- every account has account_name_ar (Arabic) and account_name_en (English)
- include IFRS-specific accounts: right-of-use, contract liabilities,
  impairment, provisions, investment property, biological assets

The seed_uae_coa(company) function must be idempotent (second call is a no-op).

These tests use the live bench at erpnext.localhost per AGENTS.md.
The test site has a default currency of INR, so we explicitly set AED on the
test company we create here.
"""
import os
import re
import unittest

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_uae.coa import build_coa_tree, seed_uae_coa


TEST_COMPANY = "_Test UAE Co"
TEST_COUNTRY = "United Arab Emirates"
TEST_CURRENCY = "AED"


def _ensure_test_company():
    """Create _Test UAE Co (AED, UAE) if missing. Returns the company name.

    ERPNext's on_update hook calls create_default_warehouses(), which
    inserts a Warehouse of type 'Transit'. If the Warehouse Type 'Transit'
    does not exist, we create it first. We also seed a Fiscal Year so the
    company passes all the validations ERPNext's Company controller runs.
    """
    if not frappe.db.exists("Warehouse Type", "Transit"):
        wt = frappe.get_doc({"doctype": "Warehouse Type", "name": "Transit"})
        wt.insert(ignore_permissions=True)
    if not frappe.db.exists("Warehouse Type", "Stores"):
        wt = frappe.get_doc({"doctype": "Warehouse Type", "name": "Stores"})
        wt.insert(ignore_permissions=True)
    if not frappe.db.exists("Fiscal Year", {"name": "2026"}):
        # Best-effort — Company insert doesn't strictly need it but it
        # silences follow-up validations
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
            "abbr": "TUAE",
            "country": TEST_COUNTRY,
            "default_currency": TEST_CURRENCY,
            "create_chart_of_accounts_based_on": None,
        })
        co.insert(ignore_permissions=True)
    # Make sure the default currency sticks (Frappe may default to INR)
    doc = frappe.get_doc("Company", TEST_COMPANY)
    if doc.default_currency != TEST_CURRENCY:
        doc.default_currency = TEST_CURRENCY
        doc.save(ignore_permissions=True)
    return TEST_COMPANY


class TestUAECOA(FrappeTestCase):
    """TDD for W2-T04 — UAE COA fixture."""

    def setUp(self):
        _ensure_test_company()

    # ----- structural properties of build_coa_tree() -----

    def test_build_coa_tree_returns_list(self):
        tree = build_coa_tree()
        self.assertIsInstance(tree, list)
        self.assertGreater(len(tree), 0)

    def test_build_coa_tree_total_count_around_400(self):
        tree = build_coa_tree()
        # Spec says ~400; allow ±10% slack
        self.assertGreaterEqual(len(tree), 360, f"got {len(tree)}")
        self.assertLessEqual(len(tree), 440, f"got {len(tree)}")

    def test_build_coa_tree_all_5_root_types_present(self):
        tree = build_coa_tree()
        root_types = {a["root_type"] for a in tree}
        for rt in ("Asset", "Liability", "Equity", "Income", "Expense"):
            self.assertIn(rt, root_types, f"missing root_type={rt}")

    def test_build_coa_tree_root_type_counts(self):
        tree = build_coa_tree()
        by_rt = {}
        for a in tree:
            by_rt.setdefault(a["root_type"], 0)
            by_rt[a["root_type"]] += 1
        self.assertGreaterEqual(by_rt.get("Asset", 0), 100, f"Assets={by_rt.get('Asset')}")
        self.assertGreaterEqual(by_rt.get("Liability", 0), 60, f"Liab={by_rt.get('Liability')}")
        self.assertGreaterEqual(by_rt.get("Equity", 0), 15, f"Eq={by_rt.get('Equity')}")
        self.assertGreaterEqual(by_rt.get("Income", 0), 25, f"Inc={by_rt.get('Income')}")
        self.assertGreaterEqual(by_rt.get("Expense", 0), 80, f"Exp={by_rt.get('Expense')}")

    def test_build_coa_tree_account_numbers_span_1xxx_to_9xxx(self):
        tree = build_coa_tree()
        prefixes = {str(a["account_number"])[0] for a in tree}
        for p in "123456789":
            self.assertIn(p, prefixes, f"missing account-number prefix {p}xxx")

    def test_build_coa_tree_every_account_has_bilingual_names(self):
        tree = build_coa_tree()
        for a in tree:
            self.assertTrue(a.get("account_name_ar"), f"missing account_name_ar on {a.get('account_number')}")
            self.assertTrue(a.get("account_name_en"), f"missing account_name_en on {a.get('account_number')}")
            # Arabic must contain at least one Arabic Unicode char
            self.assertRegex(a["account_name_ar"], r"[\u0600-\u06FF]",
                             f"account_name_ar not Arabic: {a['account_name_ar']!r}")
            # English must contain at least one Latin char
            self.assertRegex(a["account_name_en"], r"[A-Za-z]",
                             f"account_name_en not English: {a['account_name_en']!r}")

    def test_build_coa_tree_account_numbers_unique(self):
        tree = build_coa_tree()
        nums = [a["account_number"] for a in tree]
        self.assertEqual(len(nums), len(set(nums)), "duplicate account numbers")

    def test_build_coa_tree_groups_come_before_children(self):
        """Each non-group must reference an existing group as parent_account."""
        tree = build_coa_tree()
        by_num = {a["account_number"]: a for a in tree}
        for a in tree:
            parent_num = a.get("parent_account_number")
            if parent_num is None:
                continue
            self.assertIn(parent_num, by_num, f"orphan account {a['account_number']}")
            self.assertTrue(by_num[parent_num].get("is_group"),
                            f"parent {parent_num} is not a group for {a['account_number']}")

    def test_build_coa_tree_account_types_subset_of_allowed(self):
        tree = build_coa_tree()
        allowed = {
            None, "", "Accumulated Depreciation", "Bank", "Cash", "Chargeable",
            "Capital Work in Progress", "Cost of Goods Sold", "Current Asset",
            "Current Liability", "Depreciation", "Direct Expense", "Direct Income",
            "Equity", "Expense Account", "Expenses Included In Asset Valuation",
            "Expenses Included In Valuation", "Fixed Asset", "Income Account",
            "Indirect Expense", "Indirect Income", "Liability", "Payable",
            "Receivable", "Round Off", "Stock", "Stock Adjustment",
            "Stock Received But Not Billed", "Service Received But Not Billed",
            "Tax", "Temporary",
        }
        for a in tree:
            self.assertIn(a.get("account_type"), allowed,
                          f"bad account_type on {a['account_number']}: {a.get('account_type')}")

    # ----- IFRS-specific must-haves -----

    def test_ifrs_right_of_use_assets_present(self):
        tree = build_coa_tree()
        en_names = " ".join(a["account_name_en"].lower() for a in tree)
        self.assertIn("right-of-use", en_names, "no right-of-use assets (IFRS 16)")

    def test_ifrs_contract_liabilities_present(self):
        tree = build_coa_tree()
        en_names = " ".join(a["account_name_en"].lower() for a in tree)
        self.assertIn("contract liabilit", en_names, "no contract liabilities (IFRS 15)")

    def test_ifrs_impairment_present(self):
        tree = build_coa_tree()
        all_text = " ".join(a["account_name_en"].lower() for a in tree)
        self.assertIn("impairment", all_text, "no impairment accounts (IAS 36)")

    def test_ifrs_provisions_present(self):
        tree = build_coa_tree()
        all_text = " ".join(a["account_name_en"].lower() for a in tree)
        self.assertIn("provision", all_text, "no provisions accounts (IAS 37)")

    def test_ifrs_investment_property_present(self):
        tree = build_coa_tree()
        all_text = " ".join(a["account_name_en"].lower() for a in tree)
        self.assertIn("investment property", all_text, "no investment property (IAS 40)")

    def test_ifrs_biological_assets_present(self):
        tree = build_coa_tree()
        all_text = " ".join(a["account_name_en"].lower() for a in tree)
        self.assertIn("biological asset", all_text, "no biological assets (IAS 41)")

    # ----- seed_uae_coa() behaviour -----

    def test_seed_uae_coa_creates_accounts(self):
        # Clean any prior run
        frappe.db.delete("Account", {"company": TEST_COMPANY})
        seed_uae_coa(TEST_COMPANY)
        n = frappe.db.count("Account", {"company": TEST_COMPANY})
        self.assertGreater(n, 300, f"only {n} accounts seeded")

    def test_seed_uae_coa_idempotent(self):
        frappe.db.delete("Account", {"company": TEST_COMPANY})
        seed_uae_coa(TEST_COMPANY)
        first = frappe.db.count("Account", {"company": TEST_COMPANY})
        # Second call must not add more
        seed_uae_coa(TEST_COMPANY)
        second = frappe.db.count("Account", {"company": TEST_COMPANY})
        self.assertEqual(first, second, "second seed_uae_coa call added new accounts")

    def test_seed_uae_coa_critical_accounts_present(self):
        frappe.db.delete("Account", {"company": TEST_COMPANY})
        seed_uae_coa(TEST_COMPANY)
        # Spot-check a handful of IFRS/Arabic-required accounts
        for needle in ("Right-of-Use Assets", "Contract Liabilities",
                       "Investment Property", "Biological Assets"):
            self.assertTrue(
                frappe.db.exists("Account", {"company": TEST_COMPANY,
                                              "account_name": ["like", f"%{needle}%"]}),
                f"missing seeded account: {needle}",
            )
