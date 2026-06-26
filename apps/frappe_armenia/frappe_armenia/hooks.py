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

# Document-event hooks (W1-T06).
# On Company creation, write an Invited row to the AM Setup Wizard Log.
# The user-driven wizard UI (or bench execute) then triggers
# ``frappe_armenia.setup_wizard.run_armenian_setup`` which does the
# actual COA seeding and custom-field registration.
doc_events = {
    "Company": {
        "after_insert": "frappe_armenia.setup_wizard.on_company_created.on_company_created",
    },
}


# Document-event hooks (W1-T12 + W1-T14).
# On Sales Invoice submit, validate each line item's VAT against the
# Armenian Tax Code Articles 65-68.
# On Purchase Invoice submit, validate each line item's INPUT VAT
# against Articles 65-69.
doc_events = {
    "Sales Invoice": {
        "on_submit": "frappe_armenia.vat.validate_invoice_vat",
    },
    "Purchase Invoice": {
        "on_submit": "frappe_armenia.vat.validate_purchase_invoice_vat",
    },
}
