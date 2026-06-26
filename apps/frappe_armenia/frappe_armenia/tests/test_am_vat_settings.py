"""
Tests for the AM VAT Settings DocType and get_vat_settings helper (W1-T10).
"""
from __future__ import annotations

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_armenia.vat import DOCTYPE, get_vat_settings


_TEST_COMPANY = "_Test AM Co W1T10"


def _make_company(name: str = _TEST_COMPANY) -> None:
    if frappe.db.exists("Company", name):
        return
    doc = frappe.get_doc({
        "doctype": "Company",
        "company_name": name,
        "abbr": "TAM1T10",
        "default_currency": "AMD",
        "country": "Armenia",
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()


def _wipe_vat_rows(company: str) -> None:
    if not frappe.db.exists("DocType", DOCTYPE):
        return
    rows = frappe.get_all(DOCTYPE, filters={"company": company}, pluck="name")
    for n in rows:
        frappe.delete_doc(DOCTYPE, n, force=True)
    frappe.db.commit()


class TestAMVATSettings(FrappeTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        _make_company()

    def setUp(self) -> None:
        _wipe_vat_rows(_TEST_COMPANY)

    def test_get_vat_settings_creates_with_defaults(self):
        v = get_vat_settings(_TEST_COMPANY)
        self.assertIsNotNone(v)
        self.assertEqual(v.company, _TEST_COMPANY)
        self.assertEqual(float(v.default_vat_rate), 20.0,
            "Armenian standard VAT rate must default to 20%")
        self.assertEqual(float(v.export_vat_rate), 0.0,
            "Export VAT must default to 0%")
        self.assertEqual(int(v.reverse_charge_enabled), 1,
            "Reverse charge must be enabled by default")
        self.assertEqual(v.vat_period, "Monthly",
            "Armenia defaults to monthly VAT filing")
        self.assertEqual(v.vat_authority, "State Revenue Committee of Armenia")
        self.assertEqual(v.e_invoice_provider, "TaxNet-Armenia")

    def test_get_vat_settings_idempotent(self):
        first = get_vat_settings(_TEST_COMPANY)
        second = get_vat_settings(_TEST_COMPANY)
        self.assertEqual(first.name, second.name,
            "Second call must return the same row, not create a duplicate")

    def test_default_vat_rate_is_20_percent(self):
        v = get_vat_settings(_TEST_COMPANY)
        self.assertEqual(float(v.default_vat_rate), 20.0)

    def test_reverse_charge_default_enabled(self):
        v = get_vat_settings(_TEST_COMPANY)
        self.assertEqual(int(v.reverse_charge_enabled), 1)

    def test_exempt_categories_persisted(self):
        v = get_vat_settings(_TEST_COMPANY)
        v.exempt_categories = "Medical services\nEducation\nFinancial services"
        v.save(ignore_permissions=True)
        frappe.db.commit()
        reloaded = frappe.get_doc(DOCTYPE, v.name)
        self.assertEqual(
            reloaded.exempt_categories,
            "Medical services\nEducation\nFinancial services",
        )

    def test_e_invoice_threshold(self):
        v = get_vat_settings(_TEST_COMPANY)
        self.assertEqual(float(v.mandatory_e_invoicing_threshold_amd), 10000000.0)

    def test_vat_for_non_armenian_company_still_creates(self):
        """get_vat_settings creates the row regardless of country."""
        other = "_Test Other Co W1T10"
        if not frappe.db.exists("Company", other):
            frappe.get_doc({
                "doctype": "Company",
                "company_name": other,
                "abbr": "OTH1T10",
                "default_currency": "USD",
                "country": "United States",
            }).insert(ignore_permissions=True)
            frappe.db.commit()
        _wipe_vat_rows(other)
        v = get_vat_settings(other)
        self.assertIsNotNone(v)
        self.assertEqual(v.company, other)
        # cleanup
        _wipe_vat_rows(other)
        frappe.delete_doc("Company", other, force=True)
