"""frappe_armenia.setup_wizard -- Armenia-specific setup wizard step.

Public API
----------
- ``on_company_created(doc, method)``: hook called by Frappe when a
  Company is inserted. Writes an Invited log row.
- ``run_armenian_setup(company_name)``: idempotent top-level helper
  that seeds the Armenian COA + registers custom fields + updates the
  log row to Completed.
- ``is_armenian_company(company_doc_or_dict)``: pure branch-detection
  function (country == "Armenia" OR default_currency == "AMD").

Invocation
----------
Either:

    bench execute frappe_armenia.setup_wizard.run_armenian_setup --kwargs "{'company_name': 'My Co'}"

Or via the Frappe document hook ``on_company_created`` (registered in
``hooks.py``). The first form is what users run manually after the
Setup Wizard finishes; the second is the automatic entry point.
"""
from __future__ import annotations

from .log import create_log_row, get_log_for_company, update_log_status
from .on_company_created import on_company_created
from .run_setup import is_armenian_company, run_armenian_setup

__all__ = [
    "create_log_row",
    "get_log_for_company",
    "is_armenian_company",
    "on_company_created",
    "run_armenian_setup",
    "update_log_status",
]