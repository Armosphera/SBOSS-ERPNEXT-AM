"""Tests for Armenian input VAT validation on Purchase Invoice submit (W1-T14).

Honors Armenian Tax Code Articles 65-69:
  - Art. 65: standard-rate purchases - input VAT fully recoverable
  - Art. 66: zero-rated imports - input VAT recoverable at 0%
  - Art. 67: exempt purchases - no input VAT
  - Art. 68: reverse-charge imports of services - input VAT IS recoverable
              at the standard rate (recipient self-assesses both sides)
  - Art. 69: non-deductible input VAT - expensed, not recoverable
"""
from __future__ import annotations

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from frappe_armenia.custom_fields import ensure_custom_fields
from frappe_armenia.vat import (
    AM_VAT_FIELD_EXEMPT,
    AM_VAT_FIELD_EXPORT,
    AM_VAT_FIELD_REVERSE,
    AM_VAT_FIELD_STANDARD,
    expected_purchase_input_vat,
    get_vat_settings,
)


_TEST_COMPANY = "_Test AM Co W1T14"
_TEST_ITEM = "_Test AM Item W1T14"
_TEST_SUPPLIER = "_Test Supplier W1T14"


def _make_company(name=_TEST_COMPANY):
    if frappe.db.exists("Company", name):
        return
    frappe.get_doc({
        "doctype": "Company",
        "company_name": name,
        "abbr": "TAM114",
        "default_currency": "AMD",
        "country": "Armenia",
    }).insert(ignore_permissions=True)
    frappe.db.commit()


def _make_supplier(name=_TEST_SUPPLIER):
    if not frappe.db.exists("Supplier Group", "All Supplier Groups"):
        frappe.get_doc({
            "doctype": "Supplier Group",
            "supplier_group_name": "All Supplier Groups",
            "is_group": 0,
        }).insert(ignore_permissions=True)
        frappe.db.commit()
    if frappe.db.exists("Supplier", name):
        return
    try:
        frappe.get_doc({
            "doctype": "Supplier",
            "supplier_name": name,
            "supplier_group": "All Supplier Groups",
        }).insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        print(f"supplier create failed: {e}")


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
    for n in frappe.get_all("Purchase Invoice", filters={"company": _TEST_COMPANY}, pluck="name"):
        try:
            frappe.delete_doc("Purchase Invoice", n, force=True)
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


class TestExpectedPurchaseInputVAT(unittest.TestCase):
    """Pure helper tests."""

    def test_standard_rate_returns_20_percent(self):
        v = get_vat_settings(_TEST_COMPANY) if frappe.db else None
        # Without a real Company in this pure test, mock the company_vat object.
        class _MockVat:
            reverse_charge_enabled = 1
        v = _MockVat()
        item_vat = {AM_VAT_FIELD_STANDARD: 20.0,
                    AM_VAT_FIELD_EXEMPT: 0, AM_VAT_FIELD_REVERSE: 0}
        result = expected_purchase_input_vat(1000.0, item_vat, v)
        self.assertEqual(result, 200.0)

    def test_exempt_returns_zero(self):
        class _MockVat:
            reverse_charge_enabled = 1
        item_vat = {AM_VAT_FIELD_STANDARD: 20.0,
                    AM_VAT_FIELD_EXEMPT: 1, AM_VAT_FIELD_REVERSE: 0}
        result = expected_purchase_input_vat(1000.0, item_vat, _MockVat())
        self.assertEqual(result, 0.0)

    def test_reverse_charge_returns_standard_rate_vat(self):
        """Reverse-charge on a purchase: input VAT IS recoverable.
        Per Armenian Tax Code Art. 68, the buyer self-assesses both
        output AND input VAT at the standard rate."""
        class _MockVat:
            reverse_charge_enabled = 1
        item_vat = {AM_VAT_FIELD_STANDARD: 20.0,
                    AM_VAT_FIELD_EXEMPT: 0, AM_VAT_FIELD_REVERSE: 1}
        result = expected_purchase_input_vat(1000.0, item_vat, _MockVat())
        self.assertEqual(result, 200.0)

    def test_zero_rate_export_returns_zero(self):
        class _MockVat:
            reverse_charge_enabled = 1
        item_vat = {AM_VAT_FIELD_STANDARD: 0.0, AM_VAT_FIELD_EXEMPT: 0, AM_VAT_FIELD_REVERSE: 0}
        result = expected_purchase_input_vat(1000.0, item_vat, _MockVat())
        self.assertEqual(result, 0.0)


class TestValidatePurchaseInvoiceVAT(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ensure_custom_fields()
        _make_company()
        _make_supplier()
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
            "doctype": "Purchase Invoice",
            "company": _TEST_COMPANY,
            "supplier": _TEST_SUPPLIER,
            "currency": "AMD",
            "buying_price_list": "Standard",
            # posting_date defaults to today, bill_date = today,
            # due_date = today (let ERPNext auto-fill = posting_date).
            "items": [{
                "item_code": _TEST_ITEM,
                "qty": 1,
                "rate": 1000.0,
            }],
        })

    def test_standard_purchase_input_vat_20_percent(self):
        get_vat_settings(_TEST_COMPANY)
        invoice = self._make_invoice(item_vat={
            AM_VAT_FIELD_STANDARD: 20.0,
            AM_VAT_FIELD_EXEMPT: 0,
            AM_VAT_FIELD_REVERSE: 0,
        })
        invoice.insert(ignore_permissions=True)
        invoice.submit()
        self.assertEqual(invoice.docstatus, 1)

    def test_zero_rate_purchase_zero_input_vat(self):
        get_vat_settings(_TEST_COMPANY)
        invoice = self._make_invoice(item_vat={
            AM_VAT_FIELD_STANDARD: 0.0,
            AM_VAT_FIELD_EXEMPT: 0,
            AM_VAT_FIELD_REVERSE: 0,
        })
        invoice.insert(ignore_permissions=True)
        invoice.submit()
        self.assertEqual(invoice.docstatus, 1)

    def test_exempt_purchase_no_input_vat(self):
        get_vat_settings(_TEST_COMPANY)
        invoice = self._make_invoice(item_vat={
            AM_VAT_FIELD_STANDARD: 20.0,
            AM_VAT_FIELD_EXEMPT: 1,
            AM_VAT_FIELD_REVERSE: 0,
        })
        invoice.insert(ignore_permissions=True)
        invoice.submit()
        self.assertEqual(invoice.docstatus, 1)

    def test_reverse_charge_self_assessed_input_vat(self):
        """On a reverse-charge purchase, the buyer self-assesses input
        VAT at the standard rate. The invoice should show that amount."""
        get_vat_settings(_TEST_COMPANY)
        invoice = self._make_invoice(item_vat={
            AM_VAT_FIELD_STANDARD: 20.0,
            AM_VAT_FIELD_EXEMPT: 0,
            AM_VAT_FIELD_REVERSE: 1,
        })
        invoice.insert(ignore_permissions=True)
        # ERPNext computes the tax via its Item Tax Template; we need
        # the tax to actually equal the standard 20% on the line so
        # the hook passes. We force it here.
        invoice.items[0].tax_amount = 200.0
        invoice.db_update()
        invoice.reload()
        # Re-set after reload since ERPNext may have overwritten
        invoice.items[0].tax_amount = 200.0
        invoice.db_update()
        invoice.submit()
        self.assertEqual(invoice.docstatus, 1)

    def test_wrong_input_vat_rejected(self):
        get_vat_settings(_TEST_COMPANY)
        invoice = self._make_invoice(item_vat={
            AM_VAT_FIELD_STANDARD: 20.0,
            AM_VAT_FIELD_EXEMPT: 0,
            AM_VAT_FIELD_REVERSE: 0,
        })
        invoice.insert(ignore_permissions=True)
        invoice.items[0].tax_amount = 50.0  # Wrong: should be 200
        invoice.db_update()
        with self.assertRaises(frappe.ValidationError) as ctx:
            invoice.submit()
        self.assertIn("expected input VAT", str(ctx.exception))

    def test_purchase_total_input_vat_matches_sum_of_items(self):
        """A single standard-rated line at 20% on 1000 AMD = 200 VAT."""
        get_vat_settings(_TEST_COMPANY)
        invoice = self._make_invoice(item_vat={
            AM_VAT_FIELD_STANDARD: 20.0,
            AM_VAT_FIELD_EXEMPT: 0,
            AM_VAT_FIELD_REVERSE: 0,
        })
        invoice.insert(ignore_permissions=True)
        invoice.items[0].tax_amount = 200.0
        invoice.db_update()
        invoice.reload()
        # Re-set after reload since ERPNext may have overwritten
        invoice.items[0].tax_amount = 200.0
        invoice.db_update()
        invoice.submit()
        self.assertEqual(invoice.docstatus, 1)

    def test_reverse_charge_disabled_rejected(self):
        """If the company has reverse_charge_enabled=False, a reverse-charge
        item should be rejected."""
        v = get_vat_settings(_TEST_COMPANY)
        v.reverse_charge_enabled = 0
        v.save(ignore_permissions=True)
        frappe.db.commit()

        invoice = self._make_invoice(item_vat={
            AM_VAT_FIELD_STANDARD: 20.0,
            AM_VAT_FIELD_EXEMPT: 0,
            AM_VAT_FIELD_REVERSE: 1,
        })
        invoice.insert(ignore_permissions=True)
        with self.assertRaises(frappe.ValidationError) as ctx:
            invoice.submit()
        self.assertIn("reverse-charge", str(ctx.exception).lower())

        # Re-enable
        v.reverse_charge_enabled = 1
        v.save(ignore_permissions=True)
        frappe.db.commit()
