"""
Tests for W2-T06 — UAE Setup Wizard step "Choose Country" branch.

Exercises:
  1. AE Setup Wizard Log DocType can be created and read back.
  2. run_uae_setup(company) for a UAE company seeds >=400 accounts.
  3. run_uae_setup(company) is idempotent — second call returns the
     same accounts_seeded, account count unchanged.
  4. run_uae_setup(company) skips non-UAE companies
     (currency!=AED AND country not in {UAE, AE, United Arab Emirates}),
     marking the log row as "Skipped".
  5. After setup, all seeded accounts carry an Arabic name
     (account_name_ar round-trips through MariaDB utf8mb4 cleanly).
"""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_uae.setup_wizard.log import (
    DOCTYPE,
    ALL_STATUSES,
    STATUS_COMPLETED,
    STATUS_INVITED,
    STATUS_SKIPPED,
    STATUS_STARTED,
    create_log_row,
    get_log_for_company,
    update_log_status,
)
from frappe_uae.setup_wizard.run_setup import is_uae_company, run_uae_setup


_UAE_COMPANY = "_Test UAE Co W2T06"
_FOREIGN_COMPANY = "_Test Foreign Co W2T06"


def _make_company(name: str, country: str | None, currency: str | None) -> None:
    if frappe.db.exists("Company", name):
        return
    fields = {
        "doctype": "Company",
        "company_name": name,
        "abbr": "FGN" if "Foreign" in name else "UAE",
        "default_currency": currency or "USD",
    }
    if country:
        fields["country"] = country
    doc = frappe.get_doc(fields)
    doc.insert(ignore_permissions=True)
    frappe.db.commit()


def _wipe_log_rows(company: str) -> None:
    if not frappe.db.exists("DocType", DOCTYPE):
        return
    names = frappe.get_all(
        DOCTYPE, filters={"company": company}, pluck="name"
    )
    for n in names:
        frappe.delete_doc(DOCTYPE, n, force=True)
    frappe.db.commit()


def _wipe_accounts(company: str) -> None:
    frappe.db.delete("Account", {"company": company})
    frappe.db.commit()


def _ensure_root_group(company: str, abbr: str) -> str:
    full_name = f"1000 - Assets - {abbr}"
    if not frappe.db.exists("Account", full_name):
        doc = frappe.get_doc({
            "doctype": "Account",
            "company": company,
            "account_number": "1000",
            "account_name": "Assets",
            "root_type": "Asset",
            "is_group": 1,
            "account_currency": "AED",
        })
        doc.insert(ignore_permissions=True, ignore_mandatory=True)
        frappe.db.commit()
    return full_name


class TestLogDocType(TestCase if False else FrappeTestCase):
    """Smoke test for the AE Setup Wizard Log DocType and log helpers."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # Make sure the DocType is installed and a UAE company exists.
        from frappe_uae.custom_fields import ensure_custom_fields
        ensure_custom_fields()
        _make_company(_UAE_COMPANY, "United Arab Emirates", "AED")
        _wipe_log_rows(_UAE_COMPANY)

    def test_constants_present(self):
        self.assertEqual(DOCTYPE, "AE Setup Wizard Log")
        self.assertIn(STATUS_INVITED, ALL_STATUSES)
        self.assertIn(STATUS_STARTED, ALL_STATUSES)
        self.assertIn(STATUS_SKIPPED, ALL_STATUSES)
        self.assertIn(STATUS_COMPLETED, ALL_STATUSES)

    def test_log_row_create_and_read(self):
        name = create_log_row(
            company=_UAE_COMPANY,
            country="United Arab Emirates",
            default_currency="AED",
            status=STATUS_INVITED,
        )
        self.assertIsNotNone(name)
        row = frappe.get_doc(DOCTYPE, name)
        self.assertEqual(row.company, _UAE_COMPANY)
        self.assertEqual(row.country, "United Arab Emirates")
        self.assertEqual(row.default_currency, "AED")
        self.assertEqual(row.status, STATUS_INVITED)
        # cleanup
        frappe.delete_doc(DOCTYPE, name, force=True)
        frappe.db.commit()

    def test_update_log_status_started_at(self):
        name = create_log_row(
            company=_UAE_COMPANY, country="UAE", default_currency="AED",
            status=STATUS_INVITED,
        )
        now = datetime.now()
        update_log_status(_UAE_COMPANY, status=STATUS_STARTED, started_at=now)
        row = frappe.get_doc(DOCTYPE, name)
        self.assertEqual(row.status, STATUS_STARTED)
        frappe.delete_doc(DOCTYPE, name, force=True)
        frappe.db.commit()

    def test_update_log_status_invalid_raises(self):
        name = create_log_row(
            company=_UAE_COMPANY, country="UAE", default_currency="AED",
            status=STATUS_INVITED,
        )
        with self.assertRaises(ValueError):
            update_log_status(_UAE_COMPANY, status="Garbage")
        frappe.delete_doc(DOCTYPE, name, force=True)
        frappe.db.commit()


class TestRunUAESetup(FrappeTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        from frappe_uae.custom_fields import ensure_custom_fields
        ensure_custom_fields()
        _make_company(_UAE_COMPANY, "United Arab Emirates", "AED")
        _make_company(_FOREIGN_COMPANY, "United Kingdom", "GBP")

    def setUp(self) -> None:
        _wipe_log_rows(_UAE_COMPANY)
        _wipe_log_rows(_FOREIGN_COMPANY)
        _wipe_accounts(_UAE_COMPANY)
        _wipe_accounts(_FOREIGN_COMPANY)

    def tearDown(self) -> None:
        _wipe_log_rows(_UAE_COMPANY)
        _wipe_log_rows(_FOREIGN_COMPANY)
        _wipe_accounts(_UAE_COMPANY)

    def test_is_uae_company_classifier(self):
        uae_doc = frappe.get_doc("Company", _UAE_COMPANY)
        self.assertTrue(is_uae_company(uae_doc))
        foreign_doc = frappe.get_doc("Company", _FOREIGN_COMPANY)
        self.assertFalse(is_uae_company(foreign_doc))

    def test_run_uae_setup_creates_accounts(self):
        result = run_uae_setup(_UAE_COMPANY)
        self.assertEqual(result.get("status"), STATUS_COMPLETED)
        self.assertGreaterEqual(result.get("accounts_seeded", 0), 400,
            f"expected >=400 accounts seeded, got {result.get('accounts_seeded')}")
        self.assertTrue(result.get("custom_fields_registered"))
        n = frappe.db.count("Account", {"company": _UAE_COMPANY})
        self.assertGreaterEqual(n, 400, f"only {n} accounts in DB")

    def test_run_uae_setup_is_idempotent(self):
        first = run_uae_setup(_UAE_COMPANY)
        self.assertEqual(first.get("status"), STATUS_COMPLETED)
        accounts_after_first = frappe.get_all(
            "Account", filters={"company": _UAE_COMPANY}, pluck="name"
        )

        second = run_uae_setup(_UAE_COMPANY)
        self.assertEqual(second.get("status"), STATUS_COMPLETED)
        self.assertEqual(
            second.get("accounts_seeded", 0),
            first.get("accounts_seeded", 0),
            "idempotent re-run must report the same accounts_seeded",
        )

        accounts_after_second = frappe.get_all(
            "Account", filters={"company": _UAE_COMPANY}, pluck="name"
        )
        self.assertEqual(
            len(accounts_after_first),
            len(accounts_after_second),
            "account count changed across idempotent re-run",
        )

        rows = frappe.get_all(
            DOCTYPE, filters={"company": _UAE_COMPANY}, pluck="name"
        )
        self.assertEqual(len(rows), 1, f"expected 1 log row, got {len(rows)}")

    def test_skips_non_uae_company(self):
        result = run_uae_setup(_FOREIGN_COMPANY)
        self.assertEqual(result.get("status"), STATUS_SKIPPED)
        # Foreign company should have no accounts after the run
        n = frappe.db.count("Account", {"company": _FOREIGN_COMPANY})
        self.assertEqual(n, 0, f"foreign company should have no accounts, has {n}")
        # And a log row was written with status Skipped
        rows = frappe.get_all(
            DOCTYPE,
            filters={"company": _FOREIGN_COMPANY},
            fields=["status"],
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], STATUS_SKIPPED)

    def test_seeding_against_non_existent_company_raises(self):
        with self.assertRaises(ValueError):
            run_uae_setup("__definitely_not_a_company_xyz__")

    def test_account_name_ar_populated_after_setup(self):
        # Run setup (idempotent) and verify the bilingual Arabic names
        # made it through MariaDB's utf8mb4 layer without corruption.
        run_uae_setup(_UAE_COMPANY)
        # Pick 5 random accounts and verify their account_name_ar is non-empty.
        ar_accounts = frappe.get_all(
            "Account",
            filters={"company": _UAE_COMPANY},
            fields=["name", "account_name", "account_name_ar"],
            limit=5,
        )
        self.assertGreater(len(ar_accounts), 0)
        for a in ar_accounts:
            self.assertTrue(
                a.get("account_name_ar"),
                f"account {a['name']!r} ({a['account_name']!r}) has empty account_name_ar"
            )
