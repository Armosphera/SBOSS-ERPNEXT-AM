"""
Tests for the AE VAT Settings DocType and get_vat_settings helper (W2-T10).

TDD: written first, then implemented, then re-asserted green.
"""
from __future__ import annotations

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_uae.vat import DOCTYPE, get_vat_settings


_TEST_COMPANY = "_Test UAE Co W2T10"


def _make_company(name: str = _TEST_COMPANY) -> None:
    if frappe.db.exists("Company", name):
        return
    doc = frappe.get_doc({
        "doctype": "Company",
        "company_name": name,
        "abbr": "UAE2T10",
        "default_currency": "AED",
        "country": "United Arab Emirates",
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


class TestAEVATSettings(FrappeTestCase):
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
        self.assertEqual(float(v.default_vat_rate), 5.0,
            "UAE standard VAT rate must default to 5%")
        self.assertEqual(v.vat_period, "Quarterly",
            "UAE defaults to quarterly VAT filing")
        self.assertEqual(v.vat_authority, "Federal Tax Authority")
        self.assertEqual(int(v.reverse_charge_enabled), 1,
            "Reverse charge must be enabled by default")
        self.assertEqual(int(v.voluntary_disclosure_period_months), 5,
            "Voluntary disclosure period is 5 months per Cabinet Decision 52/2017")
        self.assertEqual(int(v.e_invoicing_enabled), 0,
            "E-invoicing is opt-in for UAE")
        self.assertEqual(v.e_invoicing_provider, "Datapel")

    def test_get_vat_settings_idempotent(self):
        first = get_vat_settings(_TEST_COMPANY)
        second = get_vat_settings(_TEST_COMPANY)
        self.assertEqual(first.name, second.name,
            "Second call must return the same row, not create a duplicate")

    def test_default_vat_rate_is_5_percent(self):
        v = get_vat_settings(_TEST_COMPANY)
        self.assertEqual(float(v.default_vat_rate), 5.0)

    def test_default_period_is_quarterly(self):
        v = get_vat_settings(_TEST_COMPANY)
        self.assertEqual(v.vat_period, "Quarterly")

    def test_voluntary_disclosure_default_5_months(self):
        v = get_vat_settings(_TEST_COMPANY)
        self.assertEqual(int(v.voluntary_disclosure_period_months), 5)

    def test_exempt_categories_persisted_arabic(self):
        v = get_vat_settings(_TEST_COMPANY)
        # Arabic text round-trip test (similar to W2-T05)
        tricky = "الخدمات المالية\nالتعليم\nالرعاية الصحية"
        v.exempt_categories = tricky
        v.save(ignore_permissions=True)
        frappe.db.commit()
        reloaded = frappe.get_doc(DOCTYPE, v.name)
        self.assertEqual(reloaded.exempt_categories, tricky)

    def test_get_vat_settings_rejects_unknown_company(self):
        with self.assertRaises(ValueError):
            get_vat_settings("__definitely_not_a_company_xyz__")

    def test_e_invoicing_phase_default_is_none(self):
        v = get_vat_settings(_TEST_COMPANY)
        self.assertEqual(v.e_invoicing_phase, "None")
