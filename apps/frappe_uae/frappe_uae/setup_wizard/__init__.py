"""frappe_uae.setup_wizard package.

Exposes:
- run_uae_setup(company_name) — idempotent UAE setup entry point
- on_company_created(doc, method) — Frappe document-event hook
- AE Setup Wizard Log DocType (custom=1, module=frappe_uae)
"""
from .log import (
    ALL_STATUSES,
    DOCTYPE,
    STATUS_COMPLETED,
    STATUS_INVITED,
    STATUS_SKIPPED,
    STATUS_STARTED,
    AESetupWizardLog,
    create_log_row,
    get_log_for_company,
    update_log_status,
)
from .on_company_created import on_company_created
from .run_setup import is_uae_company, run_uae_setup

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
    "is_uae_company",
    "run_uae_setup",
    "on_company_created",
]
