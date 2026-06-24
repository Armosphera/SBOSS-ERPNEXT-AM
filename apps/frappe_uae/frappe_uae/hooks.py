app_name = "frappe_uae"
app_title = "Armosphera UAE Localization"
app_publisher = "Armosphera"
app_description = "ERPNext localization for UAE: COA, VAT 5%, corporate tax 9%, payroll+EOSB, e-invoicing, banking, Arabic prints."
app_email = "dev@armosphera.com"
app_license = "Armosphera Proprietary"

required_apps = ["frappe", "erpnext", "hrms"]

# Custom Fields installed by frappe_uae on site install / migrate.
# The standard Frappe convention is to expose a module attribute that
# returns either:
#   - a list of {"dt": ..., "fieldname": ..., ...} dicts, OR
#   - a dict of {doctype: [field-dict, ...]}
# Hook handlers may also be defined under "fixture" hooks; we keep this
# simple by returning a dict from frappe_uae.custom_fields.CUSTOM_FIELDS.
#
# Reference: https://frappeframework.com/docs/v15/user/en/python-api/hooks
# (Search "custom_fields" in the hooks documentation.)
custom_fields = {
    "Account": [
        {
            "fieldname": "account_name_ar",
            "label": "Account Name (Arabic / اسم الحساب)",
            "fieldtype": "Data",
            "insert_after": "account_name",
            "depends_on": "eval:doc.company",
            "read_only": 0,
            "hidden": 0,
        }
    ]
}
