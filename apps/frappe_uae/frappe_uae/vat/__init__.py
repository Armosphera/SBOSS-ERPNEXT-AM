"""frappe_uae.vat -- UAE VAT settings and helpers.

Singleton-per-company helpers that ensure an AE VAT Settings row exists
for every UAE-jurisdiction Company and exposes a single
get_vat_settings(company) -> AEVATSettings entry point.
"""
from __future__ import annotations

import json
import os
from typing import Any

import frappe


DOCTYPE = "AE VAT Settings"


def _table_exists() -> bool:
    """Check if the AE VAT Settings table exists, bypassing Frappe's cache."""
    rows = frappe.db.sql(
        "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s",
        (frappe.conf.db_name, "tab" + DOCTYPE),
        as_list=1,
    )
    return bool(rows)


def _find_vat_dir() -> str:
    """Find the actual directory name for AE VAT Settings at runtime.

    The folder name was sanitized during the write_file that created it,
    so we discover it dynamically by scanning the regional/doctype dir.
    """
    base = frappe.get_app_path("frappe_uae", "regional", "doctype")
    if not os.path.isdir(base):
        raise FileNotFoundError(f"AE VAT Settings base directory not found: {base}")
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
    """Insert the AE VAT Settings DocType record if missing."""
    if frappe.db.exists("DocType", DOCTYPE):
        return
    dir_name = _find_vat_dir()
    base = frappe.get_app_path("frappe_uae", "regional", "doctype", dir_name)
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
    """Create the AE VAT Settings table on demand, mirroring the JSON shape.

    NOTE: 'Settings' is a reserved keyword in MariaDB, so the table
    name must always be quoted with backticks.
    """
    if _table_exists():
        return
    dir_name = _find_vat_dir()
    base = frappe.get_app_path("frappe_uae", "regional", "doctype", dir_name)
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
        "Date": "date DEFAULT NULL",
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
    """Return the AEVATSettings doc for ``company``, creating one with
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
        frappe.log_error(title="AE VAT Settings bootstrap failed", message=str(exc))
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
