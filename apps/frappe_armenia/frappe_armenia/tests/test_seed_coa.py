"""
Integration test for `seed_armenian_coa(company)` (W1-T04).

This test exercises the real DB insertion path against the live
erpnext.localhost site. It:

1. Creates a fresh test company.
2. Calls `seed_armenian_coa(company)` -- first time creates accounts.
3. Re-runs the seed -- second time must be a no-op (idempotent).
4. Verifies the on-disk account distribution matches the spec.
5. Cleans up: removes the test company and all accounts we created.

The test is gated on a `_Test Company` being safe to create; if the
company cannot be created (e.g. on a CI site that disallows new
companies), the test skips rather than fails.
"""
import os
import unittest

import frappe
from frappe.tests.utils import FrappeTestCase


# Load install_coa without the frappe-requiring side effect.
import importlib.util as _ilu
_HERE = os.path.dirname(__file__)
_SPEC = _ilu.spec_from_file_location(
    "frappe_armenia.coa.install_coa",
    os.path.join(_HERE, "..", "coa", "install_coa.py"),
)
_mod = _ilu.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_mod)
seed_armenian_coa = _mod.seed_armenian_coa
build_coa_tree = _mod.build_coa_tree
count_by_root_type = _mod.count_by_root_type


_TEST_COMPANY = "_Test AM Co W1T04"


def _make_test_company():
    """Create the test company if it doesn't exist. Returns the name."""
    if frappe.db.exists("Company", _TEST_COMPANY):
        return _TEST_COMPANY
    co = frappe.get_doc({
        "doctype": "Company",
        "company_name": _TEST_COMPANY,
        "default_currency": "AMD",
        "country": "Armenia",
    })
    co.insert(ignore_permissions=True)
    frappe.db.commit()
    return _TEST_COMPANY


def _wipe_company_accounts(company: str) -> None:
    """Delete every account belonging to the test company."""
    names = frappe.get_all("Account", filters={"company": company}, pluck="name")
    # Delete leaves first, then parents, to avoid lft/rgt issues
    for name in list(names):
        try:
            frappe.delete_doc("Account", name, force=True, ignore_permissions=True)
        except Exception:
            # Some leaves may have GL entries; ignore and continue
            pass
    frappe.db.commit()


def _wipe_test_company():
    """Tear down the test company and any accounts still attached."""
    if not frappe.db.exists("Company", _TEST_COMPANY):
        return
    _wipe_company_accounts(_TEST_COMPANY)
    try:
        frappe.delete_doc(
            "Company", _TEST_COMPANY, force=True, ignore_permissions=True
        )
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()


class TestSeedArmenianCOA(FrappeTestCase):
    """Integration tests for the live seeding path."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._cleanup_done = False
        try:
            _make_test_company()
        except Exception as e:
            cls._skip_reason = f"cannot create test company: {e}"
        else:
            cls._skip_reason = None
        # Always start from a clean slate
        _wipe_company_accounts(_TEST_COMPANY)

    @classmethod
    def tearDownClass(cls):
        _wipe_test_company()
        super().tearDownClass()

    def setUp(self):
        if self._skip_reason:
            self.skipTest(self._skip_reason)
        # Reset between tests
        _wipe_company_accounts(_TEST_COMPANY)

    def test_seed_inserts_full_coa(self):
        """First run creates every account in the tree."""
        expected = len(build_coa_tree())
        created = seed_armenian_coa(_TEST_COMPANY)
        self.assertEqual(created, expected,
                         f"expected {expected} new accounts, got {created}")

        # Verify all accounts are present in the DB
        present = frappe.get_all(
            "Account", filters={"company": _TEST_COMPANY}, pluck="name"
        )
        self.assertGreaterEqual(
            len(present), expected,
            f"DB has only {len(present)} accounts; expected >= {expected}",
        )

    def test_seed_is_idempotent(self):
        """Second run is a no-op (no duplicates, no errors)."""
        seed_armenian_coa(_TEST_COMPANY)
        before = frappe.get_all(
            "Account", filters={"company": _TEST_COMPANY}, pluck="name"
        )
        # Re-run: should create zero new accounts
        created_second = seed_armenian_coa(_TEST_COMPANY)
        self.assertEqual(created_second, 0,
                         f"idempotent re-run created {created_second} accounts")
        after = frappe.get_all(
            "Account", filters={"company": _TEST_COMPANY}, pluck="name"
        )
        self.assertEqual(len(before), len(after),
                         f"account count changed: {len(before)} -> {len(after)}")

    def test_seeded_root_type_distribution(self):
        """The seeded DB has the required minimum count per root_type."""
        seed_armenian_coa(_TEST_COMPANY)
        tree = build_coa_tree()
        expected = count_by_root_type(tree)

        for root in ("Asset", "Liability", "Equity", "Income", "Expense"):
            with self.subTest(root=root):
                n = frappe.db.count(
                    "Account",
                    filters={"company": _TEST_COMPANY, "root_type": root},
                )
                self.assertGreaterEqual(
                    n, expected[root],
                    f"root_type={root} expected >= {expected[root]}, got {n}",
                )

    def test_seeded_account_numbers_in_range(self):
        """Account numbers 1xxx -> Asset, 3xxx -> Equity, etc."""
        seed_armenian_coa(_TEST_COMPANY)
        # Spot-check: every account with number 1xxx must be Asset
        bad = frappe.db.sql(
            """
            SELECT account_number, root_type
            FROM `tabAccount`
            WHERE company = %(c)s
              AND CAST(account_number AS UNSIGNED) BETWEEN 1000 AND 1999
              AND root_type != 'Asset'
            """,
            {"c": _TEST_COMPANY},
        )
        self.assertEqual(list(bad), [], f"1xxx non-Asset accounts: {bad}")

        bad = frappe.db.sql(
            """
            SELECT account_number, root_type
            FROM `tabAccount`
            WHERE company = %(c)s
              AND CAST(account_number AS UNSIGNED) BETWEEN 4000 AND 5999
              AND root_type != 'Liability'
            """,
            {"c": _TEST_COMPANY},
        )
        self.assertEqual(list(bad), [], f"4xxx/5xxx non-Liability accounts: {bad}")

    def test_seeded_company_must_exist(self):
        """Seeding against a non-existent company raises ValueError."""
        with self.assertRaises(ValueError):
            seed_armenian_coa("__definitely_not_a_company_xyz__")


if __name__ == "__main__":
    unittest.main()
