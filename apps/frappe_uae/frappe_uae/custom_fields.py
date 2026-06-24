"""Custom Field definitions for frappe_uae.

The UAE COA is bilingual (English + Arabic). We don't modify the standard
Account DocType — instead we add the Arabic account name as a Custom Field
on the Account DocType via Frappe's Custom Field mechanism.

Why a Custom Field rather than a property setter or a new DocType?
- Property setters can't add *new* fields with their own storage column.
- A child DocType would force every Account to carry a duplicate `name`,
  breaking every existing report / form view.
- A Custom Field adds the new column to `tabAccount` and shows it on the
  standard form, exactly like a built-in field. ERPNext v15 supports this
  idiom and many upstream apps use it.

`CUSTOM_FIELDS` is the standard shape consumed by Frappe's
`frappe.custom.doctype.custom_field.custom_field.create_custom_fields()`
helper, which is also what `fixtures/custom_field.json` and
`hooks.py:fixtures` produce.

`ensure_custom_fields()` is the idempotent entry point. It calls
`create_custom_fields(update=True)` which:
- inserts a new Custom Field doc if none exists for (dt, fieldname)
- updates the existing Custom Field doc if `update=True`

This means the helper is safe to call from site install, on every bench
restart, and from tests.
"""
from __future__ import annotations

from typing import Any

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


# ---------------------------------------------------------------------------
# Field definitions
# ---------------------------------------------------------------------------

ACCOUNT_NAME_AR_FIELD: dict[str, Any] = {
    "fieldname": "account_name_ar",
    "label": "Account Name (Arabic / اسم الحساب)",
    "fieldtype": "Data",
    "insert_after": "account_name",
    "depends_on": "eval:doc.company",
    "read_only": 0,
    "hidden": 0,
    # translatable=0 because the *value* itself is Arabic text the user
    # enters; Frappe shouldn't translate the field label into other locales
    # since the Arabic text is already in the label.
    "translatable": 0,
    # Allow the field to be edited from the standard Account form without
    # extra permission setup.
    "allow_on_submit": 0,
    "no_copy": 0,
    "print_hide": 0,
    "report_hide": 0,
    "search_index": 0,
    "bold": 0,
    "italic": 0,
    "unique": 0,
}


# Top-level map: DocType -> list of field-defs.
# Shape matches what `create_custom_fields()` expects.
CUSTOM_FIELDS: dict[str, list[dict[str, Any]]] = {
    "Account": [ACCOUNT_NAME_AR_FIELD],
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def ensure_custom_fields() -> None:
    """Idempotently create / update all frappe_uae Custom Fields.

    Safe to call:
    - On site install (from hooks.py or a patch)
    - On every bench start
    - From tests (setUp)
    """
    # update=True makes this an upsert: existing Custom Fields get their
    # properties refreshed, missing ones get created.
    create_custom_fields(CUSTOM_FIELDS, update=True, ignore_validate=False)
