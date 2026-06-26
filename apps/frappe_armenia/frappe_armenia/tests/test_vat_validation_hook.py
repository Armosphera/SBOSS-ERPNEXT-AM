"""Tests for Armenian VAT validation hook (W1-T12)."""
from __future__ import annotations

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_armenia.custom_fields import ensure_custom_fields
from frappe_armenia.vat import (
    AM_VAT_FIELD_EXEMPT,
    AM_VAT_FIELD_EXPORT,
    AM_VAT_FIELD_REVERSE,
    AM_VAT_FIELD_STANDARD,
    DEFAULT_ITEM_VAT,
    expected_item_vat,
    get_vat_settings,
)


_TEST_COMPANY = "_Test AM Co W1T12"
_TEST_ITEM = "_Test AM Item W1T12"
_TEST_CUSTOMER = "_Test Customer W1T12"


def _make_company(name=_TEST_COMPANY):
    if frappe.db.exists("Company", name):
        return
    frappe.get_doc({
        "doctype": "Company",
        "company_name": name,
        "abbr": "TAM112",
        "default_currency": "AMD",
        "country": "Armenia",
    }).insert(ignore_permissions=True)
    frappe.db.commit()


def _make_customer(name=_TEST_CUSTOMER):
    """Create a customer. ERPNext's set_missing_values looks up
    customer.payment_terms; if it's None, validation errors. So we
    create a Customer Group + a no-payment-terms customer."""
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
    except Exception as e:
        print(f"customer create failed: {e}")


def _make_item_group():
    if not frappe.db.exists("Item Group", "All Item Groups"):
        frappe.db.sql(
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
    for n in frappe.get_all("Sales Invoice", filters={"company": _TEST_COMPANY}, pluck="name"):
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
    doc = frappe.get_doc(fields)
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.name


class TestExpectedItemVAT(unittest.TestCase):
    """The pure helper functions can be called independently."""

    def test_helpers_can_be_called_independently(self):
        v = expected_item_vat(1000.0, {AM_VAT_FIELD_STANDARD: 20.0, AM_VAT_FIELD_EXEMPT: 0, AM_VAT_FIELD_REVERSE: 0})
        self.assertEqual(v, 200.0)

    def test_exempt_returns_zero(self):
        v = expected_item_vat(1000.0, {AM_VAT_FIELD_STANDARD: 20.0, AM_VAT_FIELD_EXEMPT: 1, AM_VAT_FIELD_REVERSE: 0})
        self.assertEqual(v, 0.0)

    def test_reverse_charge_returns_zero(self):
        v = expected_item_vat(1000.0, {AM_VAT_FIELD_STANDARD: 20.0, AM_VAT_FIELD_EXEMPT: 0, AM_VAT_FIELD_REVERSE: 1})
        self.assertEqual(v, 0.0)

    def test_export_rate_is_zero(self):
        # Export-only item: standard=20 but export=0, so result is 0
        v = expected_item_vat(1000.0, {AM_VAT_FIELD_STANDARD: 20.0, AM_VAT_FIELD_EXEMPT: 0, AM_VAT_FIELD_REVERSE: 0, AM_VAT_FIELD_EXPORT: 0.0})
        # Export rate is 0, which means we treat this as an export
        # and return 0 VAT.
        self.assertEqual(v, 0.0)


class TestValidateInvoiceVAT(FrappeTestCase):
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

    def _make_invoice(self, item_vat=None):
        if item_vat:
            _make_item(item_vat=item_vat)
        else:
            _make_item()
        return frappe.get_doc({
            "doctype": "Sales Invoice",
            "company": _TEST_COMPANY,
            "customer": _TEST_CUSTOMER,
            "currency": "AMD",
            "items": [{
                "item_code": _TEST_ITEM,
                "qty": 1,
                "rate": 1000.0,
            }],
        })

    def test_standard_rate_20_percent_correct_accepted(self):
        get_vat_settings(_TEST_COMPANY)
        invoice = self._make_invoice(item_vat={
            AM_VAT_FIELD_STANDARD: 20.0,
            AM_VAT_FIELD_EXPORT: 0.0,
            AM_VAT_FIELD_EXEMPT: 0,
            AM_VAT_FIELD_REVERSE: 0,
        })
        invoice.insert(ignore_permissions=True)
        invoice.submit()
        self.assertEqual(invoice.docstatus, 1)

    def test_zero_rate_export_correct_accepted(self):
        # An export-only item has export_rate == 0 so expected_vat is 0.
        get_vat_settings(_TEST_COMPANY)
        invoice = self._make_invoice(item_vat={
            AM_VAT_FIELD_STANDARD: 0.0,
            AM_VAT_FIELD_EXPORT: 0.0,
            AM_VAT_FIELD_EXEMPT: 0,
            AM_VAT_FIELD_REVERSE: 0,
        })
        invoice.insert(ignore_permissions=True)
        invoice.submit()
        self.assertEqual(invoice.docstatus, 1)

    def test_exempt_accepted_with_zero_tax(self):
        get_vat_settings(_TEST_COMPANY)
        invoice = self._make_invoice(item_vat={
            AM_VAT_FIELD_STANDARD: 20.0,
            AM_VAT_FIELD_EXPORT: 0.0,
            AM_VAT_FIELD_EXEMPT: 1,
            AM_VAT_FIELD_REVERSE: 0,
        })
        invoice.insert(ignore_permissions=True)
        invoice.submit()
        self.assertEqual(invoice.docstatus, 1)

    def test_wrong_vat_rate_rejected(self):
        get_vat_settings(_TEST_COMPANY)
        invoice = self._make_invoice(item_vat={
            AM_VAT_FIELD_STANDARD: 20.0,
            AM_VAT_FIELD_EXPORT: 0.0,
            AM_VAT_FIELD_EXEMPT: 0,
            AM_VAT_FIELD_REVERSE: 0,
        })
        invoice.insert(ignore_permissions=True)
        invoice.items[0].tax_amount = 50.0
        invoice.db_update()
        with self.assertRaises(frappe.ValidationError) as ctx:
            invoice.submit()
        self.assertIn("expected VAT", str(ctx.exception))

    def test_reverse_charge_when_disabled_rejected(self):
        # Disable reverse-charge at the company level
        v = get_vat_settings(_TEST_COMPANY)
        v.reverse_charge_enabled = 0
        v.save(ignore_permissions=True)
        frappe.db.commit()

        invoice = self._make_invoice(item_vat={
            AM_VAT_FIELD_STANDARD: 20.0,
            AM_VAT_FIELD_EXPORT: 0.0,
            AM_VAT_FIELD_EXEMPT: 0,
            AM_VAT_FIELD_REVERSE: 1,
        })
        invoice.insert(ignore_permissions=True)
        with self.assertRaises(frappe.ValidationError) as ctx:
            invoice.submit()
        self.assertIn("reverse-charge", str(ctx.exception).lower())

        # Re-enable for next test
        v.reverse_charge_enabled = 1
        v.save(ignore_permissions=True)
        frappe.db.commit()
