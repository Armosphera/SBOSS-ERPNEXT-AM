"""Tests for UAE sales VAT validation on Sales Invoice submit (W2-T12).

Honors UAE Federal Decree-Law No. 8 of 2017 + Cabinet Decision 52/2017
Articles 30-46. Default VAT rate 5% per FTA. Implements:
  - Standard-rate supplies (5% VAT)
  - Zero-rated supplies (exports, 0% per Art. 30)
  - Exempt supplies (no VAT, Art. 34)
  - Reverse-charge on buyer (rare for sales, but supported per Art. 32)

Pattern mirrors frappe_armenia.vat W1-T12 (sales) + W1-T14 (purchase)
hooks so the two apps look symmetric and easy to extend.
"""
from __future__ import annotations

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_uae.custom_fields import ensure_custom_fields
from frappe_uae.vat import (
    AE_VAT_FIELD_EXEMPT,
    AE_VAT_FIELD_REVERSE,
    AE_VAT_FIELD_STANDARD,
    expected_item_vat_uae,
    get_ae_vat_settings,
)


_TEST_COMPANY = "_Test UAE Co W2T12"
_TEST_ITEM = "_Test UAE Item W2T12"
_TEST_CUSTOMER = "_Test Customer UAE W2T12"


def _make_company(name=_TEST_COMPANY):
    if frappe.db.exists("Company", name):
        return
    frappe.get_doc({
        "doctype": "Company",
        "company_name": name,
        "abbr": "UAE12",
        "default_currency": "AED",
        "country": "United Arab Emirates",
    }).insert(ignore_permissions=True)
    frappe.db.commit()
    # Ensure UAE company is linked to active Fiscal Year (ERPNext date validators).
    fy = frappe.db.get_value(
        "Fiscal Year",
        {"disabled": 0},
        "name",
        order_by="year_start_date desc",
    )
    if fy and not frappe.db.exists(
        "Fiscal Year Company", {"parent": fy, "company": name}
    ):
        frappe.get_doc({
            "doctype": "Fiscal Year Company",
            "parent": fy,
            "parenttype": "Fiscal Year",
            "parentfield": "companies",
            "company": name,
        }).insert(ignore_permissions=True)
        frappe.db.commit()


def _make_customer(name=_TEST_CUSTOMER):
    if frappe.db.exists("Customer", name):
        return
    if not frappe.db.exists("Customer Group", "All Customer Groups"):
        frappe.get_doc({
            "doctype": "Customer Group",
            "customer_group_name": "All Customer Groups",
            "is_group": 0,
        }).insert(ignore_permissions=True)
        frappe.db.commit()
    try:
        frappe.get_doc({
            "doctype": "Customer",
            "customer_name": name,
            "customer_group": "All Customer Groups",
        }).insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        pass


def _make_item_group():
    if not frappe.db.exists("Item Group", "All Item Groups"):
        frappe.sql(
            "INSERT INTO `tabItem Group` "
            "(name, creation, modified, modified_by, owner, docstatus, "
            " item_group_name, parent_item_group, is_group, lft, rgt) "
            "VALUES (%s, NOW(), NOW(), %s, %s, 0, %s, '', 1, 1, 2)",
            ("All Item Groups", "Administrator", "Administrator", "All Item Groups"),
        )
        frappe.db.commit()


def _wipe_items():
    for n in frappe.get_all("Item", filters={"item_code": _TEST_ITEM}, pluck="name"):
        frappe.delete_doc("Item", n, force=True)
    frappe.db.commit()


def _wipe_invoices():
    for n in frappe.get_all(
        "Sales Invoice", filters={"company": _TEST_COMPANY}, pluck="name"
    ):
        try:
            frappe.delete_doc("Sales Invoice", n, force=True)
        except Exception:
            pass
    frappe.db.commit()


def _make_item(item_vat=None):
    fields = {
        "doctype": "Item",
        "item_code": _TEST_ITEM,
        "item_name": _TEST_ITEM,
        "item_group": "All Item Groups",
        "stock_uom": "Unit",
        "is_stock_item": 0,
        "standard_rate": 100,
    }
    if item_vat:
        fields.update(item_vat)
        # Mirror UAE rates into Armenia's parallel Item fields so Armenia's
        # Sales Invoice hook (also registered globally on on_submit) also
        # passes. We're testing the UAE hook here, not Armenia's logic; if
        # Armenia's per-item check fires first on a rate mismatch, it
        # shadows the UAE validation we want to exercise.
        # Also mirror to am_vat_export_rate AND ae_vat_export_rate: both
        # Armenia's and UAE's expected_item_vat prefer the *_export_rate
        # field when present in the dict (even at 0), so leaving it unset
        # would short-circuit the standard-rate fallback and silently
        # treat every item as a 0% export.
        if AE_VAT_FIELD_STANDARD in item_vat:
            fields.setdefault("am_vat_standard_rate", item_vat[AE_VAT_FIELD_STANDARD])
            fields.setdefault("am_vat_export_rate", item_vat[AE_VAT_FIELD_STANDARD])
            fields.setdefault("ae_vat_export_rate", item_vat[AE_VAT_FIELD_STANDARD])
        if AE_VAT_FIELD_EXEMPT in item_vat:
            fields.setdefault("am_vat_exempt", item_vat[AE_VAT_FIELD_EXEMPT])
        if AE_VAT_FIELD_REVERSE in item_vat:
            fields.setdefault("am_vat_reverse_charge", item_vat[AE_VAT_FIELD_REVERSE])
    doc = frappe.get_doc(fields)
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.name


def _make_invoice(item_vat=None, rate=1000.0):
    if item_vat:
        _make_item(item_vat=item_vat)
    else:
        _make_item()
    return frappe.get_doc({
        "doctype": "Sales Invoice",
        "company": _TEST_COMPANY,
        "customer": _TEST_CUSTOMER,
        "currency": "AED",
        "items": [{
            "item_code": _TEST_ITEM,
            "qty": 1,
            "rate": float(rate),
        }],
    })


class TestExpectedItemVATUAE(unittest.TestCase):
    """Pure helper tests for expected_item_vat_uae()."""

    def test_helpers_can_be_called_independently(self):
        v = expected_item_vat_uae(
            1000.0,
            {AE_VAT_FIELD_STANDARD: 5.0,
             AE_VAT_FIELD_EXEMPT: 0,
             AE_VAT_FIELD_REVERSE: 0},
        )
        self.assertEqual(v, 50.0)

    def test_standard_rate_5_percent(self):
        v = expected_item_vat_uae(
            1000.0,
            {AE_VAT_FIELD_STANDARD: 5.0,
             AE_VAT_FIELD_EXEMPT: 0,
             AE_VAT_FIELD_REVERSE: 0},
        )
        self.assertEqual(v, 50.0)

    def test_exempt_returns_zero(self):
        v = expected_item_vat_uae(
            1000.0,
            {AE_VAT_FIELD_STANDARD: 5.0,
             AE_VAT_FIELD_EXEMPT: 1,
             AE_VAT_FIELD_REVERSE: 0},
        )
        self.assertEqual(v, 0.0)

    def test_reverse_charge_returns_zero(self):
        # On sales, reverse-charge means recipient self-assesses output,
        # but the supplier's invoice shows 0 VAT.
        v = expected_item_vat_uae(
            1000.0,
            {AE_VAT_FIELD_STANDARD: 5.0,
             AE_VAT_FIELD_EXEMPT: 0,
             AE_VAT_FIELD_REVERSE: 1},
        )
        self.assertEqual(v, 0.0)

    def test_zero_rate_returns_zero(self):
        v = expected_item_vat_uae(
            1000.0,
            {AE_VAT_FIELD_STANDARD: 0.0,
             AE_VAT_FIELD_EXEMPT: 0,
             AE_VAT_FIELD_REVERSE: 0},
        )
        self.assertEqual(v, 0.0)


class TestValidateSalesInvoiceVATUAE(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ensure_custom_fields()
        _make_company()
        _make_customer()
        _make_item_group()

    def setUp(self):
        _wipe_items()
        _wipe_invoices()

    def tearDown(self):
        _wipe_items()
        _wipe_invoices()

    def test_standard_5_percent_correct_accepted(self):
        get_ae_vat_settings(_TEST_COMPANY)
        invoice = _make_invoice(item_vat={
            AE_VAT_FIELD_STANDARD: 5.0,
            AE_VAT_FIELD_EXEMPT: 0,
            AE_VAT_FIELD_REVERSE: 0,
        })
        invoice.items[0].tax_amount = 50.0
        invoice.insert(ignore_permissions=True)
        invoice.submit()
        self.assertEqual(invoice.docstatus, 1)

    def test_zero_rate_export_correct_accepted(self):
        get_ae_vat_settings(_TEST_COMPANY)
        invoice = _make_invoice(item_vat={
            AE_VAT_FIELD_STANDARD: 0.0,
            AE_VAT_FIELD_EXEMPT: 0,
            AE_VAT_FIELD_REVERSE: 0,
        })
        invoice.items[0].tax_amount = 0.0
        invoice.insert(ignore_permissions=True)
        invoice.submit()
        self.assertEqual(invoice.docstatus, 1)

    def test_exempt_accepted_with_zero_tax(self):
        get_ae_vat_settings(_TEST_COMPANY)
        invoice = _make_invoice(item_vat={
            AE_VAT_FIELD_STANDARD: 5.0,
            AE_VAT_FIELD_EXEMPT: 1,
            AE_VAT_FIELD_REVERSE: 0,
        })
        invoice.items[0].tax_amount = 0.0
        invoice.insert(ignore_permissions=True)
        invoice.submit()
        self.assertEqual(invoice.docstatus, 1)

    def test_wrong_vat_rejected(self):
        get_ae_vat_settings(_TEST_COMPANY)
        invoice = _make_invoice(item_vat={
            AE_VAT_FIELD_STANDARD: 5.0,
            AE_VAT_FIELD_EXEMPT: 0,
            AE_VAT_FIELD_REVERSE: 0,
        })
        invoice.items[0].tax_amount = 25.0  # Wrong: should be 50
        invoice.insert(ignore_permissions=True)
        with self.assertRaises(frappe.ValidationError) as ctx:
            invoice.submit()
        self.assertIn("expected VAT", str(ctx.exception))