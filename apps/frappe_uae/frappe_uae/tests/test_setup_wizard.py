"""
Tests for W2-T06 — UAE Setup Wizard step "Choose Country" branch.

Goal of this task: a `AE Setup Wizard Log` DocType tracks which companies
the UAE setup has been run for; a `frappe_uae.setup_wizard.run_uae_setup(company_name)`
helper is the public entry point used by the wizard's UAE branch (and by the
`on_company_created` hook). It must:

  1. Be idempotent — a second call is a no-op (no duplicate Account rows).
  2. Ensure the `account_name_ar` custom field on Account exists.
  3. Seed the UAE IFRS COA (>=400 accounts).
  4. Skip companies whose country/currency does not look UAE — we only fire
     when `default_currency == "AED"` AND `country in {"UAE", "AE",
     "United Arab Emirates"}`.
  5. Write / update an `AE Setup Wizard Log` row (Invited → Completed).
  6. The seeded accounts must all carry an Arabic name (`account_name_ar`).

We also want a round-trip test that stores a representative Arabic string,
reloads it from MariaDB (utf8mb4), and asserts byte-for-byte equality — this
is the same shape as the W2-T05 round-trip test but for the Setup Wizard
log row's `notes` / `wizard_state` fields.

Tests use the live bench at erpnext.localhost per AGENTS.md.

Run with:
    docker exec -w / compose-bench-1 bash -c \
      "cd /workspace/frappe-bench && bench --site erpnext.localhost run-tests \
       --app frappe_uae --module frappe_uae.tests.test_setup_wizard"
"""
from __future__ import annotations

import os
import re
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_COMPANY_UAE = "_Test UAE Co W2T06"
TEST_COMPANY_OTHER = "_Test Other Co W2T06"
TEST_COMPANY_BAD_CCY = "_Test BadCcy Co W2T06"
TEST_COMPANY_BAD_CTRY = "_Test BadCtry Co W2T06"

LOG_DOCTYPE = "AE Setup Wizard Log"
WIZARD_STATE_INVITED = "Invited"
WIZARD_STATE_COMPLETED = "Completed"
WIZARD_STATE_SKIPPED = "Skipped"

AR_SAMPLE = "تم إعداد الشركة لدولة الإمارات العربية المتحدة"


def _ensure_warehouse_type(name: str) -> None:
    if not frappe.db.exists("Warehouse Type", name):
        try:
            wt = frappe.get_doc({"doctype": "Warehouse Type", "name": name})
            wt.insert(ignore_permissions=True)
        except Exception:
            pass


def _ensure_fiscal_year_2026() -> None:
    if not frappe.db.exists("Fiscal Year", {"year": "2026"}):
        try:
            fy = frappe.get_doc(
                {
                    "doctype": "Fiscal Year",
                    "year": "2026",
                    "year_start_date": "2026-01-01",
                    "year_end_date": "2026-12-31",
                }
            )
            fy.insert(ignore_permissions=True)
        except Exception:
            pass


def _ensure_company(name: str, abbr: str, country: str, currency: str) -> None:
    if frappe.db.exists("Company", name):
        return
    co = frappe.get_doc(
        {
            "doctype": "Company",
            "company_name": name,
            "abbr": abbr,
            "country": country,
            "default_currency": currency,
            "create_chart_of_accounts_based_on": None,
        }
    )
    co.insert(ignore_permissions=True)


def _ensure_test_companies() -> None:
    """Seed four test companies used by the cases below."""
    _ensure_warehouse_type("Transit")
    _ensure_warehouse_type("Stores")
    _ensure_fiscal_year_2026()
    _ensure_company(TEST_COMPANY_UAE, "TU2T06", "United Arab Emirates", "AED")
    _ensure_company(TEST_COMPANY_OTHER, "OT2T06", "United States", "USD")
    _ensure_company(TEST_COMPANY_BAD_CCY, "BC2T06", "United Arab Emirates", "USD")
    _ensure_company(TEST_COMPANY_BAD_CTRY, "BR2T06", "India", "AED")


def _delete_setup_wizard_logs_for(company: str) -> None:
    """Wipe any prior log rows for the given company so each test starts clean."""
    for log_name in frappe.get_all(
        LOG_DOCTYPE, filters={"company": company}, pluck="name"
    ):
        frappe.delete_doc(LOG_DOCTYPE, log_name, force=True, ignore_permissions=True)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAESetupWizard(FrappeTestCase):
    """TDD for W2-T06 — UAE Setup Wizard step + helper."""

    def setUp(self):
        from frappe_uae.setup_wizard.run_setup import run_uae_setup

        self.run_uae_setup = run_uae_setup
        _ensure_test_companies()
        # Clean slate — remove any old log rows + accounts for these companies
        for co in (
            TEST_COMPANY_UAE,
            TEST_COMPANY_OTHER,
            TEST_COMPANY_BAD_CCY,
            TEST_COMPANY_BAD_CTRY,
        ):
            _delete_setup_wizard_logs_for(co)
        # Make sure the custom field is installed
        from frappe_uae.custom_fields import ensure_custom_fields

        ensure_custom_fields()

    def tearDown(self):
        frappe.db.rollback()

    # ------------------------------------------------------------------
    # 1) AE Setup Wizard Log DocType exists & we can write to it
    # ------------------------------------------------------------------

    def test_log_doc_creation(self):
        """The `AE Setup Wizard Log` DocType exists, is custom=1, and we can
        insert a row tagged to a UAE company with a representative state +
        Arabic notes."""
        self.assertTrue(
            frappe.db.exists("DocType", LOG_DOCTYPE),
            f"DocType {LOG_DOCTYPE} must be installed by this app",
        )
        meta = frappe.get_meta(LOG_DOCTYPE)
        self.assertEqual(meta.custom, 1, "AE Setup Wizard Log must be a Custom DocType")
        self.assertEqual(meta.module, "Frappe UAE")

        # Required fields are present
        required = {f.fieldname for f in meta.fields if f.reqd}
        for f in ("company", "wizard_state"):
            self.assertIn(f, required, f"AE Setup Wizard Log.{f} must be required")

        # Insert a real row
        log = frappe.get_doc(
            {
                "doctype": LOG_DOCTYPE,
                "company": TEST_COMPANY_UAE,
                "wizard_state": WIZARD_STATE_INVITED,
                "notes": AR_SAMPLE,
            }
        )
        log.insert(ignore_permissions=True)

        # Read back
        fetched = frappe.get_doc(LOG_DOCTYPE, log.name)
        self.assertEqual(fetched.company, TEST_COMPANY_UAE)
        self.assertEqual(fetched.wizard_state, WIZARD_STATE_INVITED)
        self.assertEqual(fetched.notes, AR_SAMPLE)

    # ------------------------------------------------------------------
    # 2) run_uae_setup() seeds >=400 accounts and calls seed_uae_coa()
    # ------------------------------------------------------------------

    def test_run_uae_setup_creates_accounts(self):
        """run_uae_setup() must seed the full IFRS COA (>=400 accounts)
        by delegating to seed_uae_coa()."""
        # Pre-condition: a fresh UAE company should have few or no accounts
        before = frappe.get_all(
            "Account", filters={"company": TEST_COMPANY_UAE}, pluck="name"
        )

        # Patch seed_uae_coa so we can assert it was called + count it
        with mock.patch(
            "frappe_uae.coa.install_coa.seed_uae_coa",
            wraps=frappe.get_attr("frappe_uae.coa.install_coa.seed_uae_coa"),
        ) as spy:
            result = self.run_uae_setup(TEST_COMPANY_UAE)

        # seed_uae_coa was called at least once with our company name
        self.assertGreaterEqual(spy.call_count, 1)
        for call in spy.call_args_list:
            args, kwargs = call
            self.assertTrue(
                TEST_COMPANY_UAE in (list(args) + list(kwargs.values())),
                f"seed_uae_coa was called with unexpected args: {call}",
            )

        # Accounts were created (>= 400)
        after = frappe.get_all(
            "Account", filters={"company": TEST_COMPANY_UAE}, pluck="name"
        )
        self.assertGreaterEqual(
            len(after),
            400,
            f"expected >=400 accounts after UAE setup, got {len(after)}",
        )
        self.assertGreater(
            len(after),
            len(before),
            "UAE setup must add new accounts",
        )
        # Result dict is informational
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("company"), TEST_COMPANY_UAE)

    # ------------------------------------------------------------------
    # 3) run_uae_setup() is idempotent — second call is a no-op
    # ------------------------------------------------------------------

    def test_run_uae_setup_is_idempotent(self):
        """Calling run_uae_setup() twice must not create duplicates.

        We assert by:
        - counting accounts before / after the second call (must be equal)
        - counting log rows (must not double-insert a new Completed row)
        """
        # First call — does the heavy lifting
        self.run_uae_setup(TEST_COMPANY_UAE)
        accounts_after_first = frappe.get_all(
            "Account", filters={"company": TEST_COMPANY_UAE}, pluck="name"
        )
        logs_after_first = frappe.get_all(
            LOG_DOCTYPE,
            filters={"company": TEST_COMPANY_UAE, "wizard_state": WIZARD_STATE_COMPLETED},
            pluck="name",
        )

        # Second call — should be a no-op
        with mock.patch(
            "frappe_uae.coa.install_coa.seed_uae_coa",
            wraps=frappe.get_attr("frappe_uae.coa.install_coa.seed_uae_coa"),
        ) as spy:
            self.run_uae_setup(TEST_COMPANY_UAE)

        accounts_after_second = frappe.get_all(
            "Account", filters={"company": TEST_COMPANY_UAE}, pluck="name"
        )
        logs_after_second = frappe.get_all(
            LOG_DOCTYPE,
            filters={"company": TEST_COMPANY_UAE, "wizard_state": WIZARD_STATE_COMPLETED},
            pluck="name",
        )

        self.assertEqual(
            len(accounts_after_second),
            len(accounts_after_first),
            "second run_uae_setup must not create new Account rows",
        )
        self.assertEqual(
            len(logs_after_second),
            len(logs_after_first),
            "second run_uae_setup must not insert a second Completed log row",
        )
        # And seed_uae_coa was NOT invoked again (idempotency short-circuits
        # before the COA seed).
        self.assertEqual(
            spy.call_count,
            0,
            "second run_uae_setup must not re-seed the COA",
        )

    # ------------------------------------------------------------------
    # 4) Non-UAE companies are skipped
    # ------------------------------------------------------------------

    def test_skips_non_uae_company(self):
        """run_uae_setup() must NOT seed the COA when the company isn't UAE:
        - default_currency != AED
        - country not in {UAE, AE, United Arab Emirates}
        The result should have wizard_state=Skipped (or similar) and no
        new accounts."""
        for bad_company in (TEST_COMPANY_BAD_CCY, TEST_COMPANY_BAD_CTRY, TEST_COMPANY_OTHER):
            before = frappe.get_all(
                "Account", filters={"company": bad_company}, pluck="name"
            )

            result = self.run_uae_setup(bad_company)

            after = frappe.get_all(
                "Account", filters={"company": bad_company}, pluck="name"
            )

            self.assertEqual(
                len(after),
                len(before),
                f"run_uae_setup({bad_company!r}) must not add accounts",
            )
            # The result must signal skip, not success
            self.assertIn(
                (result.get("wizard_state") or "").lower(),
                ("skipped", "skip", "not_applicable"),
                f"run_uae_setup({bad_company!r}) must return wizard_state=Skipped, got {result!r}",
            )

    # ------------------------------------------------------------------
    # 5) account_name_ar populated for all seeded accounts after setup
    # ------------------------------------------------------------------

    def test_account_name_ar_populated_after_setup(self):
        """After run_uae_setup(), every seeded account for the UAE company
        must have a non-empty account_name_ar custom field."""
        self.run_uae_setup(TEST_COMPANY_UAE)

        # MariaDB-level check: how many accounts are missing account_name_ar?
        rows = frappe.db.sql(
            """
            SELECT name, account_name, account_name_ar
            FROM `tabAccount`
            WHERE company = %s
            ORDER BY account_number
            """,
            (TEST_COMPANY_UAE,),
            as_dict=True,
        )
        self.assertGreaterEqual(
            len(rows),
            400,
            f"expected >=400 accounts, got {len(rows)}",
        )

        missing = [r for r in rows if not (r.get("account_name_ar") or "").strip()]
        self.assertEqual(
            len(missing),
            0,
            f"{len(missing)} accounts missing account_name_ar "
            f"(first few: {[r['name'] for r in missing[:5]]})",
        )

        # Spot-check an Arabic round-trip on the field for a known account
        sample = next(
            r for r in rows if r["account_name"] == "Application of Funds (Funds Out)"
            or r["account_name"] == "Property, Plant and Equipment"
        )
        self.assertRegex(
            sample["account_name_ar"],
            r"[\u0600-\u06FF]",
            f"sample account {sample['name']!r} has no Arabic codepoints in account_name_ar: "
            f"{sample['account_name_ar']!r}",
        )

        # Also test a string-with-digits round-trip via the DB for a representative
        # account. Use one of the seeded accounts.
        target = next(r for r in rows if r["account_name"] == "Trade Payables")
        # Use db_set directly so we don't depend on a controller round-trip
        original = target["account_name_ar"]
        tricky = original + " - 100% - 9٪ - الحساب: 1234-5678"
        frappe.db.set_value(
            "Account",
            target["name"],
            "account_name_ar",
            tricky,
        )
        read_back = frappe.db.get_value("Account", target["name"], "account_name_ar")
        self.assertEqual(read_back, tricky)
        self.assertEqual(read_back.encode("utf-8"), tricky.encode("utf-8"))
