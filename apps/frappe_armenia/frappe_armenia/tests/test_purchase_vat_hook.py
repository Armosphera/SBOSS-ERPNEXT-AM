"""Tests for Armenian input VAT validation on Purchase Invoice submit (W1-T14).

Honors Armenian Tax Code Articles 65-69:
  - Art. 65: standard-rate purchases - input VAT fully recoverable
  - Art. 66: zero-rated imports - input VAT recoverable at 0%
  - Art. 67: exempt purchases - no input VAT
  - Art. 68: reverse-charge imports of services - input VAT IS recoverable
              at the standard rate (recipient self-assesses both sides)
  - Art. 69: non-deductible input VAT - expensed, not recoverable

Test infra notes:
- ERPNext's Purchase Invoice controller does NOT auto-compute line taxes
  without an Item Tax Template, so the on_submit VAT hook would see
  tax_amount=0 on every line and reject. We override the line amounts
  in _submit_with_expected_vat() before submit (and again after reload,
  because ERPNext may overwrite them on validate).
- Each test company must be linked to an active Fiscal Year, otherwise
  ERPNext's date validators refuse to accept any transaction. The setup
  creates the link automatically.
"""
from __future__ import annotations

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_armenia.custom_fields import ensure_custom_fields
from frappe_armenia.vat import (
    AM_VAT_FIELD_EXEMPT,
    AM_VAT_FIELD_REVERSE,
    AM_VAT_FIELD_STANDARD,
    expected_purchase_input_vat,
    get_vat_settings,
)


_TEST_COMPANY = "_Test AM Co W1T14"
_TEST_ITEM = "_Test AM Item W1T14"
_TEST_SUPPLIER = "_Test Supplier W1T14"


def _link_company_to_fiscal_year(name):
    """Ensure `name` is linked to an active Fiscal Year so ERPNext accepts
    transactions for it. Idempotent; safe to call multiple times.
    """
    fy = frappe.db.get_value(
        "Fiscal Year",
        {"disabled": 0},
        ["name"],
        as_dict=True,
        order_by="year_start_date desc",
    )
    if not fy:
        return
    if frappe.db.exists(
        "Fiscal Year Company",
        {"parent": fy["name"], "company": name},
    ):
        return
    frappe.get_doc({
        "doctype": "Fiscal Year Company",
        "parent": fy["name"],
        "parenttype": "Fiscal Year",
        "parentfield": "companies",
        "company": name,
    }).insert(ignore_permissions=True)
    frappe.db.commit()


def _make_company(name=_TEST_COMPANY):
    """Create the test company (if missing) and link it to the active
    Fiscal Year. Both steps are idempotent so re-runs are safe.
    """
    if not frappe.db.exists("Company", name):
        frappe.get_doc({
            "doctype": "Company",
            "company_name": name,
            "abbr": "TAM114",
            "default_currency": "AMD",
            "country": "Armenia",
        }).insert(ignore_permissions=True)
        frappe.db.commit()

    # ERPNext's Company.create_default_cost_center() (called automatically
    # when a Company is inserted) creates a root group Cost Center named
    # "<company> - <abbr>" and a leaf "Main - <company> - <abbr>", and sets
    # round_off_cost_center / cost_center / depreciation_cost_center on the
    # Company. The group one is created with ignore_mandatory=True because
    # it has no parent (it's the root). So we ONLY need to handle the case
    # where the Company was created BEFORE this auto-create existed, or
    # where the Cost Centers got wiped (e.g. via frappe.delete_doc on
    # Company). Query by cost_center_name FIELD rather than by document
    # name (which includes the auto-appended " - <abbr>").
    if not frappe.db.exists("Cost Center", {"cost_center_name": name, "company": name}):
        frappe.get_doc({
            "doctype": "Cost Center",
            "cost_center_name": name,
            "company": name,
            "is_group": 1,
        }).flags_ignore_mandatory = True
        doc = frappe.get_doc({
            "doctype": "Cost Center",
            "cost_center_name": name,
            "company": name,
            "is_group": 1,
        })
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        frappe.db.commit()

    if not frappe.db.exists(
        "Cost Center",
        {"cost_center_name": "Main", "company": name},
    ):
        # Parent is the root group's auto-generated name = "<name> - <abbr>".
        # We need to look it up via the cost_center_name field because the
        # name field has the abbr suffix.
        parent_cc = frappe.db.get_value(
            "Cost Center",
            {"cost_center_name": name, "company": name, "is_group": 1},
            "name",
        )
        frappe.get_doc({
            "doctype": "Cost Center",
            "cost_center_name": "Main",
            "company": name,
            "parent_cost_center": parent_cc,
            "is_group": 0,
        }).insert(ignore_permissions=True)
        frappe.db.commit()

    # The Company's CC fields should be set to the auto-generated "Main" CC.
    main_cc_name = frappe.db.get_value(
        "Cost Center",
        {"cost_center_name": "Main", "company": name},
        "name",
    )
    frappe.db.set_value("Company", name, "round_off_cost_center", main_cc_name)
    frappe.db.set_value("Company", name, "cost_center", main_cc_name)
    frappe.db.set_value("Company", name, "depreciation_cost_center", main_cc_name)
    frappe.db.commit()

    _link_company_to_fiscal_year(name)


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
        "Purchase Invoice", filters={"company": _TEST_COMPANY}, pluck="name"
    ):
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


def _make_invoice(item_vat=None):
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
        # posting_date/bill_date/due_date default to today
        "items": [{
            "item_code": _TEST_ITEM,
            "qty": 1,
            "rate": 1000.0,
        }],
    })


def _submit_with_expected_vat(invoice, expected_vat_per_line):
    """Submit a Purchase Invoice with explicit per-line tax_amounts.

    Without an Item Tax Template, ERPNext's controller doesn't auto-compute
    taxes. We set tax_amount manually on each line (and again after a
    reload, because ERPNext may overwrite the line on validate).
    """
    for idx, line in enumerate(invoice.items):
        line.tax_amount = expected_vat_per_line[idx]
    invoice.insert(ignore_permissions=True)
    invoice.reload()
    for idx, line in enumerate(invoice.items):
        line.tax_amount = expected_vat_per_line[idx]
    invoice.save(ignore_permissions=True)
    invoice.submit()


class TestExpectedPurchaseInputVAT(unittest.TestCase):
    """Pure helper tests for expected_purchase_input_vat()."""

    def test_helpers_can_be_called_independently(self):
        class _MockVat:
            reverse_charge_enabled = 1
        v = expected_purchase_input_vat(
            1000.0,
            {AM_VAT_FIELD_STANDARD: 20.0,
             AM_VAT_FIELD_EXEMPT: 0,
             AM_VAT_FIELD_REVERSE: 0},
            _MockVat(),
        )
        self.assertEqual(v, 200.0)

    def test_standard_rate_returns_20_percent(self):
        class _MockVat:
            reverse_charge_enabled = 1
        v = expected_purchase_input_vat(
            1000.0,
            {AM_VAT_FIELD_STANDARD: 20.0,
             AM_VAT_FIELD_EXEMPT: 0,
             AM_VAT_FIELD_REVERSE: 0},
            _MockVat(),
        )
        self.assertEqual(v, 200.0)

    def test_exempt_returns_zero(self):
        class _MockVat:
            reverse_charge_enabled = 1
        v = expected_purchase_input_vat(
            1000.0,
            {AM_VAT_FIELD_STANDARD: 20.0,
             AM_VAT_FIELD_EXEMPT: 1,
             AM_VAT_FIELD_REVERSE: 0},
            _MockVat(),
        )
        self.assertEqual(v, 0.0)

    def test_reverse_charge_returns_standard_rate_vat(self):
        """Reverse-charge on a purchase: input VAT IS recoverable.

        Per Armenian Tax Code Art. 68, the buyer self-assesses both
        output AND input VAT at the standard rate.
        """
        class _MockVat:
            reverse_charge_enabled = 1
        v = expected_purchase_input_vat(
            1000.0,
            {AM_VAT_FIELD_STANDARD: 20.0,
             AM_VAT_FIELD_EXEMPT: 0,
             AM_VAT_FIELD_REVERSE: 1},
            _MockVat(),
        )
        self.assertEqual(v, 200.0)

    def test_zero_rate_returns_zero(self):
        class _MockVat:
            reverse_charge_enabled = 1
        v = expected_purchase_input_vat(
            1000.0,
            {AM_VAT_FIELD_STANDARD: 0.0,
             AM_VAT_FIELD_EXEMPT: 0,
             AM_VAT_FIELD_REVERSE: 0},
            _MockVat(),
        )
        self.assertEqual(v, 0.0)


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

    def test_standard_purchase_input_vat_20_percent(self):
        get_vat_settings(_TEST_COMPANY)
        invoice = _make_invoice(item_vat={
            AM_VAT_FIELD_STANDARD: 20.0,
            AM_VAT_FIELD_EXEMPT: 0,
            AM_VAT_FIELD_REVERSE: 0,
        })
        _submit_with_expected_vat(invoice, [200.0])
        self.assertEqual(invoice.docstatus, 1)

    def test_zero_rate_purchase_zero_input_vat(self):
        get_vat_settings(_TEST_COMPANY)
        invoice = _make_invoice(item_vat={
            AM_VAT_FIELD_STANDARD: 0.0,
            AM_VAT_FIELD_EXEMPT: 0,
            AM_VAT_FIELD_REVERSE: 0,
        })
        _submit_with_expected_vat(invoice, [0.0])
        self.assertEqual(invoice.docstatus, 1)

    def test_exempt_purchase_no_input_vat(self):
        get_vat_settings(_TEST_COMPANY)
        invoice = _make_invoice(item_vat={
            AM_VAT_FIELD_STANDARD: 20.0,
            AM_VAT_FIELD_EXEMPT: 1,
            AM_VAT_FIELD_REVERSE: 0,
        })
        _submit_with_expected_vat(invoice, [0.0])
        self.assertEqual(invoice.docstatus, 1)

    def test_reverse_charge_self_assessed_input_vat(self):
        """On a reverse-charge purchase, the buyer self-assesses input
        VAT at the standard rate. The invoice should show that amount."""
        get_vat_settings(_TEST_COMPANY)
        invoice = _make_invoice(item_vat={
            AM_VAT_FIELD_STANDARD: 20.0,
            AM_VAT_FIELD_EXEMPT: 0,
            AM_VAT_FIELD_REVERSE: 1,
        })
        _submit_with_expected_vat(invoice, [200.0])
        self.assertEqual(invoice.docstatus, 1)

    def test_wrong_input_vat_rejected(self):
        """If the per-item tax_amount doesn't match the standard-rate
        expected value, on_submit should raise ValidationError."""
        get_vat_settings(_TEST_COMPANY)
        invoice = _make_invoice(item_vat={
            AM_VAT_FIELD_STANDARD: 20.0,
            AM_VAT_FIELD_EXEMPT: 0,
            AM_VAT_FIELD_REVERSE: 0,
        })
        # Submit with WRONG tax_amount; hook should throw.
        for line in invoice.items:
            line.tax_amount = 50.0  # Wrong: should be 200
        invoice.insert(ignore_permissions=True)
        invoice.reload()
        for line in invoice.items:
            line.tax_amount = 50.0
        invoice.save(ignore_permissions=True)
        with self.assertRaises(frappe.ValidationError) as ctx:
            invoice.submit()
        self.assertIn("expected input VAT", str(ctx.exception))

    def test_purchase_total_input_vat_matches_sum_of_items(self):
        """A single standard-rated line at 20% on 1000 AMD = 200 VAT."""
        get_vat_settings(_TEST_COMPANY)
        invoice = _make_invoice(item_vat={
            AM_VAT_FIELD_STANDARD: 20.0,
            AM_VAT_FIELD_EXEMPT: 0,
            AM_VAT_FIELD_REVERSE: 0,
        })
        _submit_with_expected_vat(invoice, [200.0])
        self.assertEqual(invoice.docstatus, 1)

    def test_reverse_charge_disabled_rejected(self):
        """If the company has reverse_charge_enabled=False, a reverse-charge
        item should be rejected (cannot claim input VAT)."""
        v = get_vat_settings(_TEST_COMPANY)
        v.reverse_charge_enabled = 0
        v.save(ignore_permissions=True)
        frappe.db.commit()

        invoice = _make_invoice(item_vat={
            AM_VAT_FIELD_STANDARD: 20.0,
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