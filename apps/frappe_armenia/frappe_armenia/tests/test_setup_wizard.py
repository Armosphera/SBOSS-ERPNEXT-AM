"""
Tests for the Armenia Setup Wizard step (W1-T06).

Exercises:

1. The AM Setup Wizard Log DocType can be created and read back.
2. ``run_armenian_setup(company)`` for an Armenian company seeds accounts
   (i.e. delegates to ``seed_armenian_coa``).
3. ``run_armenian_setup(company)`` is idempotent -- a second call is a
   no-op (zero new accounts, no errors, no second log row).
4. ``run_armenian_setup(company)`` is a no-op for non-Armenian companies
   (country != "Armenia" AND default_currency != "AMD"), marking the log
   row as "Skipped" rather than seeding anything.

The tests run against the live ``erpnext.localhost`` bench site. They
follow the same pattern as ``test_seed_coa.py``: build a throw-away test
company in ``setUp``, tear it down in ``tearDown``.
"""
from __future__ import annotations

import importlib.util as _ilu
import os
import unittest
from datetime import datetime, timedelta

import frappe
from frappe.tests.utils import FrappeTestCase


# ---------------------------------------------------------------------------
# Resolve the new setup_wizard package without hard-coding it
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(__file__)
_APP_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
_SW_DIR = os.path.join(_APP_ROOT, "setup_wizard")

# Make `frappe_armenia.setup_wizard` importable as a normal package.
import sys
if _APP_ROOT not in sys.path:
    sys.path.insert(0, _APP_ROOT)

# Resolve the seed_armenian_coa entry point the same way test_seed_coa does.
_seed_spec = _ilu.spec_from_file_location(
    "frappe_armenia.coa.install_coa",
    os.path.join(_APP_ROOT, "coa", "install_coa.py"),
)
_seed_mod = _ilu.module_from_spec(_seed_spec)
_seed_spec.loader.exec_module(_seed_mod)
seed_armenian_coa = _seed_mod.seed_armenian_coa
build_coa_tree = _seed_mod.build_coa_tree

# Import the new helpers under test
from frappe_armenia.setup_wizard import (  # noqa: E402
    is_armenian_company,
    run_armenian_setup,
)
from frappe_armenia.setup_wizard.log import (  # noqa: E402
    create_log_row,
    get_log_for_company,
    update_log_status,
)


# ---------------------------------------------------------------------------
# Test company helpers
# ---------------------------------------------------------------------------
_ARM_COMPANY = "_Test AM Co W1T06"
_FOREIGN_COMPANY = "_Test NonAM Co W1T06"


def _make_company(name: str, country: str, currency: str) -> None:
    """Create a fresh test company. Idempotent."""
    if frappe.db.exists("Company", name):
        return
    co = frappe.get_doc({
        "doctype": "Company",
        "company_name": name,
        "default_currency": currency,
        "country": country,
    })
    co.insert(ignore_permissions=True)
    frappe.db.commit()


def _wipe_log_rows(company: str) -> None:
    """Remove any AM Setup Wizard Log rows for the test company."""
    if not frappe.db.exists("DocType", "AM Setup Wizard Log"):
        return
    names = frappe.get_all(
        "AM Setup Wizard Log",
        filters={"company": company},
        pluck="name",
    )
    for n in names:
        try:
            frappe.delete_doc(
                "AM Setup Wizard Log", n,
                force=True, ignore_permissions=True,
            )
        except Exception:
            pass
    frappe.db.commit()


def _wipe_accounts(company: str) -> None:
    """Delete every account belonging to the test company."""
    names = frappe.get_all("Account", filters={"company": company}, pluck="name")
    for n in list(names):
        try:
            frappe.delete_doc(
                "Account", n, force=True, ignore_permissions=True,
            )
        except Exception:
            pass
    frappe.db.commit()


def _wipe_company(name: str) -> None:
    """Remove accounts then the company itself."""
    _wipe_accounts(name)
    if frappe.db.exists("Company", name):
        try:
            frappe.delete_doc(
                "Company", name,
                force=True, ignore_permissions=True,
            )
            frappe.db.commit()
        except Exception:
            frappe.db.rollback()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestAMSetupWizardLog(FrappeTestCase):
    """Round-trip and status-machine tests for the AM Setup Wizard Log."""

    def setUp(self):
        if not frappe.db.exists("DocType", "AM Setup Wizard Log"):
            self.skipTest(
                "AM Setup Wizard Log DocType not migrated yet on this site"
            )
        _make_company(_ARM_COMPANY, "Armenia", "AMD")
        _wipe_log_rows(_ARM_COMPANY)
        _wipe_log_rows(_FOREIGN_COMPANY)

    def tearDown(self):
        _wipe_log_rows(_ARM_COMPANY)
        _wipe_log_rows(_FOREIGN_COMPANY)

    def test_log_doc_creation(self):
        """create_log_row + read-back round-trip yields matching fields."""
        row_name = create_log_row(
            company=_ARM_COMPANY,
            country="Armenia",
            default_currency="AMD",
            status="Invited",
        )
        self.assertTrue(row_name, "create_log_row returned empty name")

        doc = frappe.get_doc("AM Setup Wizard Log", row_name)
        self.assertEqual(doc.company, _ARM_COMPANY)
        self.assertEqual(doc.country, "Armenia")
        self.assertEqual(doc.default_currency, "AMD")
        self.assertEqual(doc.status, "Invited")
        self.assertIsInstance(doc.creation, datetime)

        # Read-back via the helper used by run_armenian_setup
        found = get_log_for_company(_ARM_COMPANY)
        self.assertEqual(found, row_name)


class TestRunArmenianSetup(FrappeTestCase):
    """Behavioural tests for run_armenian_setup(company)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_done = False
        try:
            _make_company(_ARM_COMPANY, "Armenia", "AMD")
            _make_company(_FOREIGN_COMPANY, "United States", "USD")
            cls._setup_done = True
        except Exception as e:
            cls._skip_reason = f"cannot create test companies: {e}"
        else:
            cls._skip_reason = None

    @classmethod
    def tearDownClass(cls):
        _wipe_company(_ARM_COMPANY)
        _wipe_company(_FOREIGN_COMPANY)
        super().tearDownClass()

    def setUp(self):
        if not self._setup_done:
            self.skipTest(self._skip_reason)
        # Clean slate
        _wipe_accounts(_ARM_COMPANY)
        _wipe_accounts(_FOREIGN_COMPANY)
        _wipe_log_rows(_ARM_COMPANY)
        _wipe_log_rows(_FOREIGN_COMPANY)

    def test_is_armenian_company_detection(self):
        """Pure-function branch detection (no DB writes)."""
        self.assertTrue(is_armenian_company({"country": "Armenia", "default_currency": "AMD"}))
        self.assertTrue(is_armenian_company({"country": "Armenia", "default_currency": "USD"}))
        self.assertTrue(is_armenian_company({"country": "Georgia", "default_currency": "AMD"}))
        self.assertFalse(is_armenian_company({"country": "United States", "default_currency": "USD"}))
        self.assertFalse(is_armenian_company({"country": "France", "default_currency": "EUR"}))
        self.assertFalse(is_armenian_company({"country": None, "default_currency": None}))

    def test_run_armenian_setup_creates_accounts(self):
        """First call seeds the Armenian COA and marks the log row Completed."""
        expected = len(build_coa_tree())

        result = run_armenian_setup(_ARM_COMPANY)
        self.assertTrue(result.get("ran"), f"expected ran=True, got {result!r}")
        self.assertEqual(result.get("status"), "Completed")
        self.assertGreaterEqual(
            result.get("accounts_seeded", 0),
            expected,
            f"expected >={expected} accounts seeded, got {result.get('accounts_seeded')}",
        )

        # The accounts are actually in the DB
        present = frappe.get_all(
            "Account", filters={"company": _ARM_COMPANY}, pluck="name"
        )
        self.assertGreaterEqual(len(present), expected)

        # Log row was written and reached Completed
        log_name = get_log_for_company(_ARM_COMPANY)
        self.assertTrue(log_name, "no AM Setup Wizard Log row for the company")
        log = frappe.get_doc("AM Setup Wizard Log", log_name)
        self.assertEqual(log.status, "Completed")
        self.assertEqual(log.company, _ARM_COMPANY)
        self.assertEqual(log.country, "Armenia")
        self.assertEqual(log.default_currency, "AMD")
        self.assertGreaterEqual(log.accounts_seeded, expected)
        self.assertTrue(bool(log.custom_fields_registered))
        self.assertIsNotNone(log.completed_at)

    def test_run_armenian_setup_is_idempotent(self):
        """Second call is a no-op -- zero new accounts, single log row, Completed."""
        first = run_armenian_setup(_ARM_COMPANY)
        self.assertEqual(first.get("status"), "Completed")
        accounts_after_first = frappe.get_all(
            "Account", filters={"company": _ARM_COMPANY}, pluck="name"
        )

        second = run_armenian_setup(_ARM_COMPANY)
        # The second call should be idempotent: account count unchanged.
        # The implementation reports the same accounts_seeded from the
        # first call (the log row's stored value), not zero, because the
        # log row records what was done, not what's left to do.
        self.assertEqual(second.get("status"), "Completed")
        self.assertEqual(
            second.get("accounts_seeded", 0),
            first.get("accounts_seeded", 0),
            "idempotent re-run must report the same accounts_seeded",
        )

        accounts_after_second = frappe.get_all(
            "Account", filters={"company": _ARM_COMPANY}, pluck="name"
        )
        self.assertEqual(
            len(accounts_after_first),
            len(accounts_after_second),
            "account count changed across idempotent re-run",
        )

        # Only one log row exists for this company
        rows = frappe.get_all(
            "AM Setup Wizard Log", filters={"company": _ARM_COMPANY}, pluck="name"
        )
        self.assertEqual(len(rows), 1, f"expected 1 log row, got {len(rows)}")

    def test_skips_non_armenian_company(self):
        """Foreign country + non-AMD currency => skipped, log row marked Skipped."""
        if not frappe.db.exists("Company", _FOREIGN_COMPANY):
            self.skipTest("foreign test company not present")

        result = run_armenian_setup(_FOREIGN_COMPANY)
        self.assertEqual(result.get("status"), "Skipped")
        self.assertFalse(result.get("ran"))
        self.assertEqual(result.get("accounts_seeded", 0), 0)
        self.assertFalse(result.get("custom_fields_registered", False))

        # No accounts were created for the foreign company
        present = frappe.get_all(
            "Account", filters={"company": _FOREIGN_COMPANY}, pluck="name"
        )
        self.assertEqual(present, [])

        # A log row was still written, but with status=Skipped
        log_name = get_log_for_company(_FOREIGN_COMPANY)
        self.assertTrue(log_name, "no AM Setup Wizard Log row for foreign company")
        log = frappe.get_doc("AM Setup Wizard Log", log_name)
        self.assertEqual(log.status, "Skipped")
        self.assertEqual(log.country, "United States")
        self.assertEqual(log.default_currency, "USD")


if __name__ == "__main__":
    unittest.main()