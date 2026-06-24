app_name = "frappe_armenia"
app_title = "Armosphera Armenia Localization"
app_publisher = "Armosphera"
app_description = "ERPNext localization for Armenia: COA, VAT, payroll, e-invoice, banking"
app_email = "dev@armosphera.com"
app_license = "Armosphera Proprietary"
required_apps = ["frappe", "erpnext", "hrms"]

# Custom fields registered on site install / bench migrate.
# Maps DocType name -> list of custom_field dicts. Frappe reads this
# from hooks.py and calls create_custom_fields() for us. The shape is
# the same as in apps/frappe_armenia/frappe_armenia/custom_fields.py.
custom_fields = {
    "Account": [
        {
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
    ],
}
