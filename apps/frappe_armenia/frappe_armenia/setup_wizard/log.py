"""AM Setup Wizard Log -- persistent record of wizard invocations.

The DocType is intentionally simple: one row per company-wizard
invocation. The lifecycle is ``Invited`` -> ``Started`` -> ``Completed``
or ``Invited`` -> ``Skipped``. We use it for observability (which
companies have been seeded?) and for idempotency (a row in state
``Completed`` means we don't seed again).

This module is the only place that touches the DocType directly. All
higher-level helpers go through ``create_log_row`` / ``get_log_for_company``
/ ``update_log_status`` so the wizard module does not have to know the
field names.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import frappe


DOCTYPE = "AM Setup Wizard Log"


# Status constants -- mirrors the DocType's Select options.
STATUS_INVITED = "Invited"
STATUS_STARTED = "Started"
STATUS_SKIPPED = "Skipped"
STATUS_COMPLETED = "Completed"

ALL_STATUSES = (
    STATUS_INVITED,
    STATUS_STARTED,
    STATUS_SKIPPED,
    STATUS_COMPLETED,
)


def _now() -> datetime:
    """UTC-aware now (Frappe convention)."""
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


def create_log_row(
    company: str,
    country: str | None,
    default_currency: str | None,
    status: str = STATUS_INVITED,
    *,
    started_at: datetime | None = None,
) -> str:
    """Insert a new AM Setup Wizard Log row.

    Returns the document name (== company, since the ``company`` field is
    the natural unique key and we name the doc after it for ergonomics).

    If a row already exists for the company this is *not* an error -- the
    wizard is idempotent and we just return the existing name. Callers that
    want a fresh row should ``frappe.delete_doc(DOCTYPE, name, force=True)``
    first.
    """
    if not frappe.db.exists("DocType", DOCTYPE):
        raise RuntimeError(
            f"DocType '{DOCTYPE}' is not installed on this site; "
            "run `bench migrate` after installing the frappe_armenia app."
        )

    existing = get_log_for_company(company)
    if existing:
        return existing

    doc = frappe.get_doc({
        "doctype": DOCTYPE,
        "company": company,
        "country": country or "",
        "default_currency": default_currency or "",
        "status": status if status in ALL_STATUSES else STATUS_INVITED,
        "started_at": started_at or _now(),
        "accounts_seeded": 0,
        "custom_fields_registered": 0,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.name


def get_log_for_company(company: str) -> str | None:
    """Return the name of the log row for ``company``, or ``None``."""
    if not frappe.db.exists("DocType", DOCTYPE):
        return None
    return frappe.db.get_value(
        DOCTYPE, {"company": company}, "name"
    )


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

    # frappe.db.set_value is the contract-blessed writer for custom-field-like
    # updates (see docs/frappe-gotchas.md lesson set).
    frappe.db.set_value(DOCTYPE, name, updates, update_modified=True)
    frappe.db.commit()
    return name