"""frappe_armenia.vat -- Armenian VAT settings and helpers.

Singleton-per-company helpers that ensure an AM VAT Settings row exists
for every Armenia-jurisdiction Company and exposes a single
get_vat_settings(company) -> AMVATSettings entry point.
"""
from __future__ import annotations

import json
import os
from typing import Any

import frappe


DOCTYPE = "AM VAT Settings"


def _table_exists() -> bool:
    """Check if the AM VAT Settings table exists, bypassing Frappe's cache."""
    rows = frappe.db.sql(
        "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s",
        (frappe.conf.db_name, "tab" + DOCTYPE),
        as_list=1,
    )
    return bool(rows)


def _find_vat_dir() -> str:
    """Find the actual directory name for AM VAT Settings at runtime.

    The folder name was sanitized during the write_file that created it,
    so we discover it dynamically by scanning the regional/doctype dir.
    """
    base = frappe.get_app_path("frappe_armenia", "regional", "doctype")
    if not os.path.isdir(base):
        raise FileNotFoundError(f"AM VAT Settings base directory not found: {base}")
    for n in os.listdir(base):
        full = os.path.join(base, n)
        if not os.path.isdir(full) or n.startswith("__"):
            continue
        json_path = os.path.join(full, n + ".json")
        if os.path.isfile(json_path):
            try:
                with open(json_path) as f:
                    data = json.load(f)
                if data.get("name") == DOCTYPE:
                    return n
            except (json.JSONDecodeError, OSError):
                continue
    raise FileNotFoundError(f"Could not find directory containing DocType {DOCTYPE!r} in {base}")


def _ensure_doctype_record() -> None:
    """Insert the AM VAT Settings DocType record if missing."""
    if frappe.db.exists("DocType", DOCTYPE):
        return
    dir_name = _find_vat_dir()
    base = frappe.get_app_path("frappe_armenia", "regional", "doctype", dir_name)
    json_path = os.path.join(base, dir_name + ".json")
    with open(json_path) as f:
        data = json.load(f)
    data["custom"] = 1
    data.pop("__islocal", None)
    data.pop("__unsaved", None)
    doc = frappe.get_doc(data)
    doc.insert(ignore_permissions=True)
    frappe.db.commit()


def _ensure_table() -> None:
    """Create the AM VAT Settings table on demand, mirroring the JSON shape."""
    if _table_exists():
        return
    dir_name = _find_vat_dir()
    base = frappe.get_app_path("frappe_armenia", "regional", "doctype", dir_name)
    json_path = os.path.join(base, dir_name + ".json")
    with open(json_path) as f:
        data = json.load(f)

    seen = set()
    cols = [
        "`name` varchar(140) NOT NULL",
        "`creation` datetime(6) DEFAULT NULL",
        "`modified` datetime(6) DEFAULT NULL",
        "`modified_by` varchar(140) DEFAULT NULL",
        "`owner` varchar(140) DEFAULT NULL",
        "`docstatus` int(1) NOT NULL DEFAULT 0",
        "`parent` varchar(140) DEFAULT NULL",
        "`parentfield` varchar(140) DEFAULT NULL",
        "`parenttype` varchar(140) DEFAULT NULL",
        "`idx` int(8) NOT NULL DEFAULT 0",
    ]
    field_map = {
        "Data": "varchar({length}) DEFAULT NULL",
        "Int": "int(11) NOT NULL DEFAULT 0",
        "Check": "int(1) NOT NULL DEFAULT 0",
        "Percent": "decimal(21,9) NOT NULL DEFAULT 0",
        "Currency": "decimal(21,9) NOT NULL DEFAULT 0",
        "Datetime": "datetime(6) DEFAULT NULL",
        "Link": "varchar(140) DEFAULT NULL",
        "Select": "varchar(140) DEFAULT NULL",
        "Text": "longtext",
    }
    for f in data["fields"]:
        fname = f.get("fieldname")
        ftype = f.get("fieldtype", "Data")
        if not fname or fname in seen:
            continue
        seen.add(fname)
        try:
            length = int(f.get("length", 140))
        except Exception:
            length = 140
        if length > 255:
            length = 255
        if length < 1:
            length = 140
        col_tpl = field_map.get(ftype, "text DEFAULT NULL")
        if "{length}" in col_tpl:
            col_tpl = col_tpl.format(length=length)
        cols.append(f"`{fname}` {col_tpl}")
    sql = (
        f"CREATE TABLE IF NOT EXISTS `tab{DOCTYPE}` (\n  "
        + ",\n  ".join(cols)
        + ",\n  PRIMARY KEY (`name`)\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
    )
    frappe.db.sql(sql)
    frappe.db.commit()
    frappe.cache.delete_value("db_tables")


def get_vat_settings(company: str) -> Any:
    """Return the AMVATSettings doc for ``company``, creating one with
    spec defaults if none exists.

    Returns the Document instance, or None if the DocType is not
    installed on this site yet.
    """
    if not frappe.db.exists("Company", company):
        raise ValueError(f"Company {company!r} does not exist")

    frappe.cache.delete_value("db_tables")
    try:
        _ensure_doctype_record()
        _ensure_table()
    except Exception as exc:
        frappe.log_error(title="AM VAT Settings bootstrap failed", message=str(exc))
        return None

    existing = frappe.db.get_value(DOCTYPE, {"company": company}, "name")
    if existing:
        return frappe.get_doc(DOCTYPE, existing)

    doc = frappe.get_doc({
        "doctype": DOCTYPE,
        "company": company,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc


__all__ = ["DOCTYPE", "get_vat_settings"]


# --- Item-level VAT fields (W1-T11) ---

ITEM_VAT_FIELDS = (
    "am_vat_standard_rate",
    "am_vat_export_rate",
    "am_vat_exempt",
    "am_vat_reverse_charge",
)

DEFAULT_ITEM_VAT = {
    "am_vat_standard_rate": 20.0,
    "am_vat_export_rate": 0.0,
    "am_vat_exempt": 0,
    "am_vat_reverse_charge": 0,
}


def get_item_vat(item_code):
    """Return the Armenian VAT fields for item_code.

    Uses safe defaults if the Item doesn't exist or the custom fields
    aren't populated yet.
    """
    result = dict(DEFAULT_ITEM_VAT)
    if not frappe.db.exists("Item", item_code):
        return result
    row = frappe.db.get_value(
        "Item", item_code, list(ITEM_VAT_FIELDS), as_dict=True,
    ) or {}
    for k in ITEM_VAT_FIELDS:
        v = row.get(k)
        if v is None:
            continue
        result[k] = v
    return result


__all__ = ["DOCTYPE", "get_vat_settings",
           "ITEM_VAT_FIELDS", "DEFAULT_ITEM_VAT", "get_item_vat"]


# --- Sales Invoice VAT validation hook (W1-T12) ---

# Item-level VAT field names (from W1-T11):
AM_VAT_FIELD_STANDARD = "am_vat_standard_rate"
AM_VAT_FIELD_EXPORT = "am_vat_export_rate"
AM_VAT_FIELD_EXEMPT = "am_vat_exempt"
AM_VAT_FIELD_REVERSE = "am_vat_reverse_charge"


def expected_item_vat(net_amount, item_vat):
    """Compute the expected VAT for a single invoice line.

    Honors Armenian Tax Code Articles 65-68:
      - Art. 65: standard-rate taxable supplies
      - Art. 66: zero-rated exports
      - Art. 67: exempt supplies (no VAT)
      - Art. 68: reverse-charge imports of services
    """
    if int(item_vat.get(AM_VAT_FIELD_EXEMPT, 0) or 0):
        return float(0)
    if int(item_vat.get(AM_VAT_FIELD_REVERSE, 0) or 0):
        # Reverse-charge: VAT is the recipient's responsibility.
        # The invoice still shows 0; the recipient self-assesses.
        return float(0)
    # Choose the right rate. If the AM_VAT_FIELD_EXPORT field is
    # present in the item_vat dict (even with value 0), use it
    # (an item explicitly marked as export should use export rate).
    # Otherwise fall back to the standard rate.
    if AM_VAT_FIELD_EXPORT in item_vat:
        rate = float(item_vat.get(AM_VAT_FIELD_EXPORT, 0.0) or 0.0)
    else:
        rate = float(item_vat.get(AM_VAT_FIELD_STANDARD, 20.0) or 20.0)
    return round(float(net_amount) * rate / 100.0, 2)


def validate_invoice_vat(doc, method=None):
    """Validate that each line item's VAT matches Armenian Tax Code.

    Registered as a doc_events hook on Sales Invoice "on_submit".
    Raises frappe.ValidationError with a clear message if any item
    has a VAT mismatch.
    """
    company = getattr(doc, "company", None)
    if not company:
        return

    company_vat = get_vat_settings(company)
    if company_vat is None:
        # DocType not installed; nothing to validate yet.
        return

    company_reverse_charge_enabled = bool(
        int(getattr(company_vat, "reverse_charge_enabled", 1) or 0)
    )

    computed_total_vat = 0.0

    for idx, item in enumerate(doc.items or []):
        item_code = getattr(item, "item_code", None)
        if not item_code:
            continue

        item_vat = get_item_vat(item_code)

        # Disallow reverse-charge items if the company has it disabled.
        if int(item_vat.get(AM_VAT_FIELD_REVERSE, 0) or 0):
            if not company_reverse_charge_enabled:
                frappe.throw(
                    f"Line {idx+1}: item {item_code!r} is marked reverse-charge "
                    "but the company has reverse_charge_enabled=False. Either "
                    "enable it in AM VAT Settings or remove the reverse-charge "
                    "flag on the item."
                )

        # Validate per-item VAT.
        net_amount = float(getattr(item, "net_amount", 0) or 0)
        actual_vat = float(getattr(item, "tax_amount", 0) or 0)
        expected_vat = expected_item_vat(net_amount, item_vat)

        if round(actual_vat, 2) != round(expected_vat, 2):
            rate = float(item_vat.get(AM_VAT_FIELD_STANDARD, 20.0) or 20.0)
            frappe.throw(
                f"Line {idx+1} ({item_code!r}): expected VAT {expected_vat} "
                f"at {rate}% on net {net_amount}, got {actual_vat}."
            )

        computed_total_vat += expected_vat

    # Validate the invoice total against the sum of per-item VATs.
    invoice_total_vat = float(getattr(doc, "total_taxes_and_charges", 0) or 0)
    if abs(invoice_total_vat - round(computed_total_vat, 2)) > 0.05:
        frappe.throw(
            f"Invoice VAT total {invoice_total_vat} does not match the sum of "
            f"per-item VATs {round(computed_total_vat, 2)}."
        )


__all__ = [
    "DOCTYPE", "get_vat_settings",
    "ITEM_VAT_FIELDS", "DEFAULT_ITEM_VAT", "get_item_vat",
    "AM_VAT_FIELD_STANDARD", "AM_VAT_FIELD_EXPORT",
    "AM_VAT_FIELD_EXEMPT", "AM_VAT_FIELD_REVERSE",
    "expected_item_vat", "validate_invoice_vat",
]
