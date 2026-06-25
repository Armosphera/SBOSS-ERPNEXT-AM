app_name = "frappe_uae"
app_title = "Armosphera UAE Localization"
app_publisher = "Armosphera"
app_description = "ERPNext localization for UAE: COA, VAT 5%, corporate tax 9%, payroll+EOSB, e-invoicing, banking, Arabic prints."
app_email = "dev@armosphera.com"
app_license = "Armosphera Proprietary"

required_apps = ["frappe", "erpnext", "hrms"]

# Custom fields registered on site install / bench migrate.
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
            "translatable": 0,
            "description": "Bilingual Arabic name for the account. Set by the UAE COA seeder.",
        }
    ],
}

# Document-event hooks (W2-T06).
doc_events = {
    "Company": {
        "after_insert": "frappe_uae.setup_wizard.on_company_created.on_company_created",
    },
}
