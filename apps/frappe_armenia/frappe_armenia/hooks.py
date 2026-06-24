"""
frappe_armenia hooks.

All hooks are registered to Frappe via the standard hooks mechanism
(https://docs.frappe.io/framework/user/en/python-api/hooks).

Keep this file thin — heavy lifting lives in frappe_armenia.* submodules.
"""
app_name = "frappe_armenia"
app_title = "Armosphera Armenia Localization"
app_publisher = "Armosphera"
app_description = "ERPNext localization for Armenia."
app_email = "dev@armosphera.com"
app_license = "Armosphera Proprietary"

# Required upstream apps
required_apps = ["frappe", "erpnext", "hrms"]

# DocEvent hooks (filled in by W1-T01..T45 tasks)
# doc_events = {
#     "Sales Invoice": {
#         "on_submit": "frappe_armenia.regional.vat.on_submit",
#     },
#     "Company": {
#         "on_update": "frappe_armenia.coa.install_coa.seed_armenian_coa_for_new_company",
#     },
# }
