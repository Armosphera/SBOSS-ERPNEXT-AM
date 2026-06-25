"""AE Setup Wizard Log — audit trail for the UAE Setup Wizard step.

Contract A: DocType name is ``AE Setup Wizard Log`` (with spaces).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import frappe
from frappe.model.document import Document

from frappe_uae.custom_fields import ensure_custom_fields


DOCTYPE = "AE Setup Wizard Log"

STATUS_INVITED = "Invited"
STATUS_STARTED = "Started"
STATUS_SKIPPED = "Skipped"
STATUS_COMPLETED = "Completed"

ALL_STATUSES = (STATUS_INVITED, STATUS_STARTED, STATUS_SKIPPED, STATUS_COMPLETED)


class AESetupWizardLog(Document):
    """Controller for the AE Setup Wizard Log DocType.

    All writes go through ``create_log_row`` / ``update_log_status``
    helpers so the wizard code is small.
    """
    pass


def create_log_row(
    *,
    company: str,
    country: str | None = None,
    default_currency: str | None = None,
    status: str = STATUS_INVITED,
) -> str | None:
    """Insert a new AE Setup Wizard Log row for ``company``.

    Returns the inserted row name, or None if the DocType isn't installed
    yet (so this is safe to call from on_company_created on a fresh site
    that hasn't migrated).
    """
    if not frappe.db.sql("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s", (frappe.conf.db_name, "tab" + DOCTYPE), as_list=1):
        return None
    if status not in ALL_STATUSES:
        raise ValueError(f"invalid status {status!r}; must be one of {ALL_STATUSES}")
    try:
        doc = frappe.get_doc({
            "doctype": DOCTYPE,
            "company": company,
            "country": country or "",
            "default_currency": default_currency or "",
            "status": status,
            "started_at": datetime.now(),
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return doc.name
    except Exception as exc:
        frappe.log_error(title="AE Setup Wizard: create_log_row failed", message=str(exc))
        return None


def get_log_for_company(company: str) -> str | None:
    """Return the log row name for ``company``, or None if there isn't one."""
    if not frappe.db.sql("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s", (frappe.conf.db_name, "tab" + DOCTYPE), as_list=1):
        return None
    rows = frappe.get_all(
        DOCTYPE,
        filters={"company": company},
        pluck="name",
        limit=1,
    )
    return rows[0] if rows else None


def update_log_status(
    company: str,
    *,
    status: str | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    accounts_seeded: int | None = None,
    custom_fields_registered: bool | None = None,
    country: str | None = None,
    default_currency: str | None = None,
) -> str | None:
    """Patch fields on the log row for ``company``.

    Only the fields that are not ``None`` are written. Returns the row
    name, or ``None`` if no row exists.
    """
    name = get_log_for_company(company)
    if not name:
        return None

    updates: dict[str, Any] = {}
    if status is not None:
        if status not in ALL_STATUSES:
            raise ValueError(
                f"invalid status {status!r}; must be one of {ALL_STATUSES}"
            )
        updates["status"] = status
    if started_at is not None:
        updates["started_at"] = started_at
    if completed_at is not None:
        updates["completed_at"] = completed_at
    if accounts_seeded is not None:
        updates["accounts_seeded"] = int(accounts_seeded)
    if custom_fields_registered is not None:
        updates["custom_fields_registered"] = 1 if custom_fields_registered else 0
    if country is not None:
        updates["country"] = country
    if default_currency is not None:
        updates["default_currency"] = default_currency

    if not updates:
        return name

    frappe.db.set_value(DOCTYPE, name, updates)
    frappe.db.commit()
    return name


__all__ = [
    "DOCTYPE",
    "ALL_STATUSES",
    "STATUS_INVITED",
    "STATUS_STARTED",
    "STATUS_SKIPPED",
    "STATUS_COMPLETED",
    "AESetupWizardLog",
    "create_log_row",
    "get_log_for_company",
    "update_log_status",
    "ensure_custom_fields",
]
