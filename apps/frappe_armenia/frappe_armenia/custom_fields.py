"""
Custom field definitions for frappe_armenia.

Armenian-language extras on standard ERPNext DocTypes.
"""
from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


# Armenian-language account name (data field, shown next to the EN name).
ACCOUNT_NAME_HY_FIELD = {
    "fieldname": "account_name_hy",
    "label": "Account Name (Armenian / Հաշվային անուն)",
    "fieldtype": "Data",
    "insert_after": "account_name",
    "depends_on": "eval:doc.company",
    "read_only": 0,
    "hidden": 0,
    "translatable": 0,
    "description": "Bilingual Armenian name for the account. Set by the Armenia COA seeder.",
}


# Registry: {DocType: [custom_field_dict, ...]}
CUSTOM_FIELDS: dict[str, list[dict]] = {
    "Account": [ACCOUNT_NAME_HY_FIELD],
    # Armenian VAT fields on the standard Item DocType (W1-T11).
    # Inserted after the existing Item.taxes table to keep the form clean.
    "Item": [
        {
            "fieldname": "am_vat_standard_rate",
            "label": "AM Standard VAT Rate",
            "fieldtype": "Percent",
            "insert_after": "taxes",
            "default": "20",
            "description": "Standard VAT rate for this item (Armenian Tax Code: 20%).",
            "depends_on": "",
            "read_only": 0,
            "hidden": 0,
        },
        {
            "fieldname": "am_vat_export_rate",
            "label": "AM Export VAT Rate",
            "fieldtype": "Percent",
            "insert_after": "am_vat_standard_rate",
            "default": "0",
            "description": "VAT rate applied to exports of this item (typically 0%).",
            "depends_on": "",
            "read_only": 0,
            "hidden": 0,
        },
        {
            "fieldname": "am_vat_exempt",
            "label": "AM VAT Exempt",
            "fieldtype": "Check",
            "insert_after": "am_vat_export_rate",
            "default": "0",
            "description": "Whether this item is exempt from VAT under Armenian Tax Code Art. 56.",
            "depends_on": "",
            "read_only": 0,
            "hidden": 0,
        },
        {
            "fieldname": "am_vat_reverse_charge",
            "label": "AM VAT Reverse Charge",
            "fieldtype": "Check",
            "insert_after": "am_vat_exempt",
            "default": "0",
            "description": "Whether reverse-charge VAT applies to this item per Armenian Tax Code Art. 59.",
            "depends_on": "",
            "read_only": 0,
            "hidden": 0,
        },
    ],
}


def get_account_custom_fields() -> dict[str, list[dict]]:
    """Return the CUSTOM_FIELDS dict in the shape Frappe expects.

    Used by `hooks.py` via the `custom_fields` hook, AND called directly
    by `ensure_custom_fields()` for idempotent test setup.
    """
    return CUSTOM_FIELDS


def ensure_custom_fields() -> None:
    """Create / update the custom fields idempotently.

    Safe to call on every site install and from test setUp. Wraps
    `frappe.custom.doctype.custom_field.create_custom_fields` which is
    already idempotent via its `update=True` flag.
    """
    if not frappe.db:
        return
    create_custom_fields(get_account_custom_fields(), update=True)
