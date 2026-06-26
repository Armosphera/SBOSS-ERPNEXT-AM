"""Tests for Item-level UAE VAT template (W2-T11)."""
from __future__ import annotations

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_uae.custom_fields import ensure_custom_fields
from frappe_uae.vat import (
    DEFAULT_ITEM_VAT,
    ITEM_VAT_FIELDS,
    get_item_vat,
)


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


_TEST_ITEM = "_Test UAE Item W2T11"
_TEST_ITEM_GROUP = "_Test UAE Item Group W2T11"


def _wipe_items():
    for n in frappe.get_all("Item", filters={"item_code": _TEST_ITEM}, pluck="name"):
        frappe.delete_doc("Item", n, force=True)
    frappe.db.commit()


class TestItemVATTemplate(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ensure_custom_fields()
        _make_item_group()
        if not frappe.db.exists("Item Group", _TEST_ITEM_GROUP):
            frappe.get_doc({
                "doctype": "Item Group",
                "item_group_name": _TEST_ITEM_GROUP,
                "parent_item_group": "All Item Groups",
                "is_group": 0,
            }).insert(ignore_permissions=True)
            frappe.db.commit()

    def setUp(self):
        _wipe_items()

    def tearDown(self):
        _wipe_items()

    def _make_item(self, **overrides):
        fields = {
            "doctype": "Item",
            "item_code": _TEST_ITEM,
            "item_name": _TEST_ITEM,
            "item_group": _TEST_ITEM_GROUP,
            "stock_uom": "Unit",
            "is_stock_item": 0,
            "standard_rate": 100,
        }
        fields.update(overrides)
        doc = frappe.get_doc(fields)
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return doc.name

    def test_custom_fields_registered(self):
        cf_names = {
            r.fieldname
            for r in frappe.db.sql(
                "SELECT fieldname FROM `tabCustom Field` WHERE dt = %s",
                "Item", as_dict=True,
            )
        }
        for f in ITEM_VAT_FIELDS:
            self.assertIn(f, cf_names, f"Custom field {f} missing on Item")

    def test_get_item_vat_returns_defaults_for_new_item(self):
        self._make_item()
        v = get_item_vat(_TEST_ITEM)
        self.assertEqual(float(v["ae_vat_standard_rate"]), 5.0,
            "Default AE standard VAT rate is 5% per UAE FTA")
        self.assertEqual(float(v["ae_vat_export_rate"]), 0.0,
            "Default AE export VAT rate is 0%")
        self.assertEqual(int(v["ae_vat_is_exempt"]), 0,
            "Default exempt flag is off")
        self.assertEqual(int(v["ae_vat_reverse_charge"]), 0,
            "Default reverse-charge flag is off")

    def test_get_item_vat_returns_custom_values(self):
        self._make_item(
            **{"ae_vat_standard_rate": 0.0, "ae_vat_export_rate": 5.0, "ae_vat_is_exempt": 1, "ae_vat_reverse_charge": 1}
        )
        v = get_item_vat(_TEST_ITEM)
        self.assertEqual(float(v["ae_vat_standard_rate"]), 0.0)
        self.assertEqual(float(v["ae_vat_export_rate"]), 5.0)
        self.assertEqual(int(v["ae_vat_is_exempt"]), 1)
        self.assertEqual(int(v["ae_vat_reverse_charge"]), 1)

    def test_get_item_vat_handles_missing_item_gracefully(self):
        v = get_item_vat("__definitely_not_an_item_xyz__")
        self.assertEqual(v, DEFAULT_ITEM_VAT)

    def test_exempt_field_default_false(self):
        self._make_item()
        v = get_item_vat(_TEST_ITEM)
        self.assertEqual(int(v["ae_vat_is_exempt"]), 0)

    def test_standard_rate_default_5_percent(self):
        self._make_item()
        v = get_item_vat(_TEST_ITEM)
        self.assertEqual(float(v["ae_vat_standard_rate"]), 5.0)
