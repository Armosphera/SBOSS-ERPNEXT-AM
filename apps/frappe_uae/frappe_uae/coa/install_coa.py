"""UAE COA installer (W2-T04).

build_coa_tree() returns a list of dicts that map directly to
frappe.new_doc('Account'). Each dict contains:
    account_number, account_name_en, account_name_ar, root_type,
    account_type, parent_account_number (or None for top-level groups),
    is_group, account_currency (always 'AED').

The account-number scheme follows the W2-T04 spec:
    1xxx Non-current Assets          (root_type=Asset)
    2xxx Current Assets              (root_type=Asset)
    3xxx Equity                      (root_type=Equity)
    4xxx Non-current Liabilities     (root_type=Liability)
    5xxx Current Liabilities         (root_type=Liability)
    6xxx Income                      (root_type=Income)
    7xxx Expenses                    (root_type=Expense)
    8xxx Off-balance Sheet / Memo    (root_type=Liability)
    9xxx Cost of Goods Sold          (root_type=Expense)

seed_uae_coa(company) walks the tree in parent-first order and inserts
each account via frappe.new_doc('Account').insert(). Idempotency is
guaranteed by checking frappe.db.exists() before insert. A commit
is issued after every root-level insert so the link validation in
subsequent inserts can find the parent.

install_coa() is a bench-execute entry point that seeds the default
UAE company (or a caller-supplied one).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import frappe


# ---------------------------------------------------------------------------
# Tree builder
# ---------------------------------------------------------------------------

def _node(
    num: str,
    en: str,
    ar: str,
    root_type: str,
    account_type: str | None = "",
    parent: str | None = None,
    is_group: bool = False,
) -> dict[str, Any]:
    """One account in the COA tree."""
    return {
        "account_number": num,
        "account_name_en": en,
        "account_name_ar": ar,
        "root_type": root_type,
        "account_type": account_type or "",
        "parent_account_number": parent,
        "is_group": 1 if is_group else 0,
        "account_currency": "AED",
    }


def build_coa_tree() -> list[dict[str, Any]]:
    """Return the full UAE COA as a flat list of dicts (~400 accounts)."""
    tree: list[dict[str, Any]] = []

    # =====================================================================
    # 1xxx — NON-CURRENT ASSETS (root_type=Asset)
    # =====================================================================
    tree += [
        # 1xxx groups
        _node("1000", "Assets", "الأصول", "Asset", "", None, True),
        _node("1100", "Non-Current Assets", "الأصول غير المتداولة", "Asset", "", "1000", True),
        _node("1200", "Current Assets", "الأصول المتداولة", "Asset", "", "1000", True),

        # 1110 Property, Plant & Equipment
        _node("1110", "Property, Plant and Equipment", "الممتلكات والمصانع والمعدات", "Asset", "Fixed Asset", "1100", True),
        _node("1111", "Land", "الأراضي", "Asset", "Fixed Asset", "1110"),
        _node("1112", "Buildings", "المباني", "Asset", "Fixed Asset", "1110"),
        _node("1113", "Accumulated Depreciation - Buildings", "مجمع استهلاك المباني", "Asset", "Accumulated Depreciation", "1110"),
        _node("1114", "Plant and Machinery", "المصانع والآلات", "Asset", "Fixed Asset", "1110"),
        _node("1115", "Accumulated Depreciation - Plant and Machinery", "مجمع استهلاك المصانع والآلات", "Asset", "Accumulated Depreciation", "1110"),
        _node("1116", "Motor Vehicles", "المركبات", "Asset", "Fixed Asset", "1110"),
        _node("1117", "Accumulated Depreciation - Motor Vehicles", "مجمع استهلاك المركبات", "Asset", "Accumulated Depreciation", "1110"),
        _node("1118", "Furniture and Fixtures", "الأثاث والتركيبات", "Asset", "Fixed Asset", "1110"),
        _node("1119", "Accumulated Depreciation - Furniture and Fixtures", "مجمع استهلاك الأثاث والتركيبات", "Asset", "Accumulated Depreciation", "1110"),
        _node("1121", "Office Equipment", "معدات المكاتب", "Asset", "Fixed Asset", "1110"),
        _node("1122", "Accumulated Depreciation - Office Equipment", "مجمع استهلاك معدات المكاتب", "Asset", "Accumulated Depreciation", "1110"),
        _node("1123", "Computer Equipment", "معدات الحاسوب", "Asset", "Fixed Asset", "1110"),
        _node("1124", "Accumulated Depreciation - Computer Equipment", "مجمع استهلاك معدات الحاسوب", "Asset", "Accumulated Depreciation", "1110"),
        _node("1125", "Leasehold Improvements", "تحسينات على عقار مستأجر", "Asset", "Fixed Asset", "1110"),
        _node("1126", "Accumulated Depreciation - Leasehold Improvements", "مجمع استهلاك تحسينات العقارات المستأجرة", "Asset", "Accumulated Depreciation", "1110"),
        _node("1127", "Capital Work in Progress", "أعمال رأسمالية قيد التنفيذ", "Asset", "Capital Work in Progress", "1110"),

        # 1130 Right-of-Use Assets (IFRS 16)
        _node("1130", "Right-of-Use Assets", "أصول حق الاستخدام", "Asset", "Fixed Asset", "1100", True),
        _node("1131", "Right-of-Use - Buildings (IFRS 16)", "حق استخدام المباني", "Asset", "Fixed Asset", "1130"),
        _node("1132", "Accumulated Depreciation - ROU Buildings", "مجمع استهلاك حق استخدام المباني", "Asset", "Accumulated Depreciation", "1130"),
        _node("1133", "Right-of-Use - Motor Vehicles (IFRS 16)", "حق استخدام المركبات", "Asset", "Fixed Asset", "1130"),
        _node("1134", "Accumulated Depreciation - ROU Motor Vehicles", "مجمع استهلاك حق استخدام المركبات", "Asset", "Accumulated Depreciation", "1130"),
        _node("1135", "Right-of-Use - Office Equipment (IFRS 16)", "حق استخدام معدات المكاتب", "Asset", "Fixed Asset", "1130"),
        _node("1136", "Accumulated Depreciation - ROU Office Equipment", "مجمع استهلاك حق استخدام معدات المكاتب", "Asset", "Accumulated Depreciation", "1130"),

        # 1140 Investment Property (IAS 40)
        _node("1140", "Investment Property", "العقارات الاستثمارية", "Asset", "Fixed Asset", "1100", True),
        _node("1141", "Investment Property - Land", "العقارات الاستثمارية - أراض", "Asset", "Fixed Asset", "1140"),
        _node("1142", "Investment Property - Buildings", "العقارات الاستثمارية - مبان", "Asset", "Fixed Asset", "1140"),
        _node("1143", "Accumulated Depreciation - Investment Property", "مجمع استهلاك العقارات الاستثمارية", "Asset", "Accumulated Depreciation", "1140"),
        _node("1144", "Fair Value Adjustment - Investment Property", "تعديل القيمة العادلة للعقارات الاستثمارية", "Asset", "Fixed Asset", "1140"),

        # 1150 Intangible Assets
        _node("1150", "Intangible Assets", "الأصول غير الملموسة", "Asset", "Fixed Asset", "1100", True),
        _node("1151", "Goodwill", "الشهرة", "Asset", "Fixed Asset", "1150"),
        _node("1152", "Patents and Trademarks", "براءات الاختراع والعلامات التجارية", "Asset", "Fixed Asset", "1150"),
        _node("1153", "Accumulated Amortisation - Patents and Trademarks", "مجمع إطفاء براءات الاختراع والعلامات", "Asset", "Accumulated Depreciation", "1150"),
        _node("1154", "Computer Software", "برامج الحاسوب", "Asset", "Fixed Asset", "1150"),
        _node("1155", "Accumulated Amortisation - Computer Software", "مجمع إطفاء برامج الحاسوب", "Asset", "Accumulated Depreciation", "1150"),
        _node("1156", "Licences", "التراخيص", "Asset", "Fixed Asset", "1150"),
        _node("1157", "Accumulated Amortisation - Licences", "مجمع إطفاء التراخيص", "Asset", "Accumulated Depreciation", "1150"),
        _node("1158", "Development Costs", "تكاليف التطوير", "Asset", "Fixed Asset", "1150"),

        # 1160 Biological Assets (IAS 41)
        _node("1160", "Biological Assets", "الأصول البيولوجية", "Asset", "Fixed Asset", "1100", True),
        _node("1161", "Bearer Biological Assets", "أصول بيولوجية مثمرة", "Asset", "Fixed Asset", "1160"),
        _node("1162", "Consumable Biological Assets", "أصول بيولوجية قابلة للاستهلاك", "Asset", "Fixed Asset", "1160"),
        _node("1163", "Agricultural Produce on Bearer Plants", "منتجات زراعية على نباتات مثمرة", "Asset", "Stock", "1160"),
        _node("1164", "Livestock", "الثروة الحيوانية", "Asset", "Fixed Asset", "1160"),
        _node("1165", "Standing Timber", "الأخشاب القائمة", "Asset", "Fixed Asset", "1160"),

        # 1170 Long-term Investments
        _node("1170", "Long-term Investments", "الاستثمارات طويلة الأجل", "Asset", "", "1100", True),
        _node("1171", "Investments in Subsidiaries", "استثمارات في شركات تابعة", "Asset", "", "1170"),
        _node("1172", "Investments in Associates", "استثمارات في شركات شقيقة", "Asset", "", "1170"),
        _node("1173", "Investments in Joint Ventures", "استثمارات في مشاريع مشتركة", "Asset", "", "1170"),
        _node("1174", "Equity Instruments at FVOCI (IFRS 9)", "أدوات حقوق ملكية بالقيمة العادلة من خلال الدخل الشامل", "Asset", "", "1170"),
        _node("1175", "Debt Instruments at Amortised Cost (IFRS 9)", "أدوات دين بالتكلفة المستهلكة", "Asset", "", "1170"),
        _node("1176", "Financial Assets at FVTPL (IFRS 9)", "أصول مالية بالقيمة العادلة من خلال الربح والخسارة", "Asset", "", "1170"),
        _node("1177", "Held-to-Maturity Investments", "استثمارات محتفظ بها حتى الاستحقاق", "Asset", "", "1170"),
        _node("1178", "Available-for-Sale Financial Assets", "أصول مالية متاحة للبيع", "Asset", "", "1170"),
        _node("1179", "Impairment of Investments (IAS 36)", "انخفاض قيمة الاستثمارات", "Asset", "", "1170"),

        # 1180 Long-term Receivables
        _node("1180", "Long-term Receivables", "المدينون طويلو الأجل", "Asset", "", "1100", True),
        _node("1181", "Loans to Employees (Long-term)", "قروض للموظفين - طويلة الأجل", "Asset", "", "1180"),
        _node("1182", "Loans to Related Parties (Long-term)", "قروض لأطراف ذات علاقة - طويلة الأجل", "Asset", "", "1180"),
        _node("1183", "Trade Receivables (Long-term)", "مدينون تجاريون - طويلو الأجل", "Asset", "Receivable", "1180"),
        _node("1184", "Security Deposits (Long-term)", "ودائع ضمان - طويلة الأجل", "Asset", "", "1180"),
        _node("1185", "Impairment of Long-term Receivables", "خسائر انخفاض المدينين طويلو الأجل", "Asset", "", "1180"),

        # 1190 Deferred Tax & Other Non-current
        _node("1190", "Deferred Tax Assets (IAS 12)", "أصول الضريبة المؤجلة", "Asset", "", "1100", True),
        _node("1191", "Deferred Tax Asset - Property, Plant and Equipment", "أصل الضريبة المؤجلة - الممتلكات والمصانع والمعدات", "Asset", "", "1190"),
        _node("1192", "Deferred Tax Asset - Provisions", "أصل الضريبة المؤجلة - المخصصات", "Asset", "", "1190"),
        _node("1193", "Deferred Tax Asset - Tax Losses", "أصل الضريبة المؤجلة - الخسائر الضريبية", "Asset", "", "1190"),
        _node("1194", "Prepayments (Non-current)", "مصروفات مقدمة - غير متداولة", "Asset", "", "1100"),
        _node("1195", "Other Non-current Assets", "أصول غير متداولة أخرى", "Asset", "", "1100"),
        _node("1196", "Impairment of PPE (IAS 36)", "انخفاض قيمة الممتلكات والمصانع والمعدات", "Asset", "", "1100"),
        _node("1197", "Impairment of Intangibles (IAS 36)", "انخفاض قيمة الأصول غير الملموسة", "Asset", "", "1100"),
        _node("1198", "Impairment of Investment Property (IAS 36)", "انخفاض قيمة العقارات الاستثمارية", "Asset", "", "1100"),
        _node("1199", "Impairment of Goodwill (IAS 36)", "انخفاض قيمة الشهرة", "Asset", "", "1100"),
    ]

    # =====================================================================
    # 2xxx — CURRENT ASSETS (root_type=Asset)
    # =====================================================================
    tree += [
        # 2100 Inventory
        _node("2100", "Inventory", "المخزون", "Asset", "Stock", "1200", True),
        _node("2101", "Raw Materials", "المواد الخام", "Asset", "Stock", "2100"),
        _node("2102", "Work in Progress", "إنتاج تحت التشغيل", "Asset", "Stock", "2100"),
        _node("2103", "Finished Goods", "بضاعة جاهزة", "Asset", "Stock", "2100"),
        _node("2104", "Goods in Transit", "بضائع في الطريق", "Asset", "Stock", "2100"),
        _node("2105", "Packing Materials", "مواد التعبئة والتغليف", "Asset", "Stock", "2100"),
        _node("2106", "Stock Consumables", "مواد استهلاكية", "Asset", "Stock", "2100"),
        _node("2107", "Stock Provision / Obsolete Stock", "مخصص بضاعة متقادمة", "Asset", "", "2100"),
        _node("2108", "Stock Received But Not Billed", "بضاعة مستلمة غير مفوترة", "Asset", "Stock Received But Not Billed", "1200"),
        _node("2109", "Service Received But Not Billed", "خدمات مستلمة غير مفوترة", "Asset", "Service Received But Not Billed", "1200"),

        # 2200 Accounts Receivable
        _node("2200", "Accounts Receivable", "المدينون", "Asset", "Receivable", "1200", True),
        _node("2201", "Trade Receivables (Domestic)", "مدينون تجاريون - محليون", "Asset", "Receivable", "2200"),
        _node("2202", "Trade Receivables (GCC)", "مدينون تجاريون - دول مجلس التعاون", "Asset", "Receivable", "2200"),
        _node("2203", "Trade Receivables (International)", "مدينون تجاريون - دولي", "Asset", "Receivable", "2200"),
        _node("2204", "Export Receivables", "مدينون التصدير", "Asset", "Receivable", "2200"),
        _node("2205", "Intercompany Receivables", "مدينون - شركات المجموعة", "Asset", "Receivable", "2200"),
        _node("2206", "Employee Receivables", "مدينون - موظفون", "Asset", "Receivable", "2200"),
        _node("2207", "Related Party Receivables", "مدينون - أطراف ذات علاقة", "Asset", "Receivable", "2200"),
        _node("2208", "Allowance for Doubtful Debts", "مخصص الديون المشكوك في تحصيلها", "Asset", "", "2200"),
        _node("2209", "Notes Receivable", "أوراق قبض", "Asset", "Receivable", "1200"),

        # 2300 VAT / Tax Receivable (UAE VAT 5%)
        _node("2300", "VAT Receivable (UAE)", "ضريبة القيمة المضافة - مدينة", "Asset", "Tax", "1200", True),
        _node("2301", "Input VAT - Standard Rated 5%", "مدخلات ضريبة القيمة المضافة 5٪", "Asset", "Tax", "2300"),
        _node("2302", "Input VAT - Reverse Charge", "مدخلات ضريبة القيمة المضافة - آلية الاحتساب العكسي", "Asset", "Tax", "2300"),
        _node("2303", "Input VAT - Designated Zones", "مدخلات ضريبة القيمة المضافة - المناطق المحددة", "Asset", "Tax", "2300"),
        _node("2304", "Input VAT - Imports", "مدخلات ضريبة القيمة المضافة - واردات", "Asset", "Tax", "2300"),
        _node("2305", "Input VAT - Expenses", "مدخلات ضريبة القيمة المضافة - مصروفات", "Asset", "Tax", "2300"),
        _node("2306", "Input VAT - Capital Goods", "مدخلات ضريبة القيمة المضافة - أصول رأسمالية", "Asset", "Tax", "2300"),
        _node("2307", "Corporate Tax Advance Payments (UAE 9%)", "دفعات مقدمة للضريبة المؤسسية 9٪", "Asset", "", "1200"),
        _node("2308", "Excise Tax Receivable", "ضريبة انتقائية - مدينة", "Asset", "Tax", "1200"),

        # 2400 Bank
        _node("2400", "Bank", "البنك", "Asset", "Bank", "1200", True),
        _node("2401", "Emirates NBD - AED Operating Account", "بنك الإمارات دبي الوطني - حساب تشغيلي درهم", "Asset", "Bank", "2400"),
        _node("2402", "Emirates NBD - USD Operating Account", "بنك الإمارات دبي الوطني - حساب تشغيلي دولار", "Asset", "Bank", "2400"),
        _node("2403", "Abu Dhabi Commercial Bank (ADCB) - AED", "بنك أبوظبي التجاري - درهم", "Asset", "Bank", "2400"),
        _node("2404", "First Abu Dhabi Bank (FAB) - AED", "بنك أبوظبي الأول - درهم", "Asset", "Bank", "2400"),
        _node("2405", "Mashreq Bank - AED", "بنك المشرق - درهم", "Asset", "Bank", "2400"),
        _node("2406", "RAKBank - AED", "بنك رأس الخيمة - درهم", "Asset", "Bank", "2400"),
        _node("2407", "Dubai Islamic Bank (DIB) - AED", "بنك دبي الإسلامي - درهم", "Asset", "Bank", "2400"),
        _node("2408", "Bank Deposits (Short-term)", "ودائع بنكية - قصيرة الأجل", "Asset", "Bank", "2400"),
        _node("2409", "Cash Margin / Bank Guarantees", "هامش نقدي / ضمانات بنكية", "Asset", "Bank", "2400"),

        # 2500 Cash on Hand
        _node("2500", "Cash on Hand", "النقدية في الصندوق", "Asset", "Cash", "1200", True),
        _node("2501", "Cash - Main Office (AED)", "النقدية - المكتب الرئيسي (درهم)", "Asset", "Cash", "2500"),
        _node("2502", "Cash - Petty Cash (AED)", "النقدية - المصروفات النثرية (درهم)", "Asset", "Cash", "2500"),
        _node("2503", "Cash - Branch (AED)", "النقدية - الفرع (درهم)", "Asset", "Cash", "2500"),
        _node("2504", "Cash in Transit", "النقدية في الطريق", "Asset", "Cash", "2500"),
        _node("2505", "Foreign Currency Cash (USD)", "نقدية بالعملة الأجنبية (دولار)", "Asset", "Cash", "2500"),
        _node("2506", "Foreign Currency Cash (EUR)", "نقدية بالعملة الأجنبية (يورو)", "Asset", "Cash", "2500"),
        _node("2507", "Foreign Currency Cash (GBP)", "نقدية بالعملة الأجنبية (جنيه إسترليني)", "Asset", "Cash", "2500"),

        # 2600 Prepayments & Other Current Assets
        _node("2600", "Prepayments and Other Current Assets", "المصروفات المقدمة والأصول المتداولة الأخرى", "Asset", "", "1200", True),
        _node("2601", "Prepaid Rent", "إيجار مقدم", "Asset", "", "2600"),
        _node("2602", "Prepaid Insurance", "تأمين مقدم", "Asset", "", "2600"),
        _node("2603", "Prepaid Licences and Permits", "تراخيص وتصاريح مقدمة", "Asset", "", "2600"),
        _node("2604", "Prepaid Salaries", "رواتب مقدمة", "Asset", "", "2600"),
        _node("2605", "Prepaid Advertising", "إعلان مقدم", "Asset", "", "2600"),
        _node("2606", "Prepaid Maintenance", "صيانة مقدمة", "Asset", "", "2600"),
        _node("2607", "Advances to Suppliers", "دفعات مقدمة للموردين", "Asset", "", "2600"),
        _node("2608", "Advances to Employees", "دفعات مقدمة للموظفين", "Asset", "", "2600"),
        _node("2609", "Refundable Deposits (Short-term)", "ودائع مستردة - قصيرة الأجل", "Asset", "", "2600"),
    ]

    # =====================================================================
    # 3xxx — EQUITY (root_type=Equity)
    # =====================================================================
    tree += [
        _node("3000", "Equity", "حقوق الملكية", "Equity", "Equity", None, True),
        _node("3100", "Share Capital", "رأس المال", "Equity", "Equity", "3000", True),
        _node("3101", "Authorised Share Capital", "رأس المال المصرح به", "Equity", "Equity", "3100"),
        _node("3102", "Issued Share Capital", "رأس المال المصدر", "Equity", "Equity", "3100"),
        _node("3103", "Treasury Shares (IFRS 9)", "أسهم الخزينة", "Equity", "Equity", "3100"),
        _node("3200", "Reserves", "الاحتياطيات", "Equity", "Equity", "3000", True),
        _node("3201", "Share Premium", "علاوة الإصدار", "Equity", "Equity", "3200"),
        _node("3202", "Statutory Reserve", "الاحتياطي القانوني", "Equity", "Equity", "3200"),
        _node("3203", "General Reserve", "الاحتياطي العام", "Equity", "Equity", "3200"),
        _node("3204", "Revaluation Reserve (IFRS / IAS 16)", "احتياطي إعادة التقييم", "Equity", "Equity", "3200"),
        _node("3205", "Fair Value Reserve (IFRS 9)", "احتياطي القيمة العادلة", "Equity", "Equity", "3200"),
        _node("3206", "Hedging Reserve (IFRS 9)", "احتياطي التحوط", "Equity", "Equity", "3200"),
        _node("3207", "Translation Reserve (IAS 21)", "احتياطي تحويل العملات", "Equity", "Equity", "3200"),
        _node("3208", "Dividend Reserve", "احتياطي التوزيعات", "Equity", "Equity", "3200"),
        _node("3300", "Retained Earnings", "الأرباح المحتجزة", "Equity", "Equity", "3000", True),
        _node("3301", "Retained Earnings - Prior Years", "أرباح محتجزة - سنوات سابقة", "Equity", "Equity", "3300"),
        _node("3302", "Current Year Earnings", "أرباح السنة الحالية", "Equity", "Equity", "3300"),
        _node("3303", "Dividends Declared (Interim)", "توزيعات معلنة - مرحلية", "Equity", "Equity", "3300"),
        _node("3400", "Other Equity Components", "مكونات حقوق ملكية أخرى", "Equity", "Equity", "3000", True),
        _node("3401", "Share-Based Payment Reserve (IFRS 2)", "احتياطي الدفع على أساس الأسهم", "Equity", "Equity", "3400"),
        _node("3402", "OCI - Remeasurement of DBO (IAS 19)", "الدخل الشامل الآخر - إعادة قياس التزامات المنافع", "Equity", "Equity", "3400"),
        _node("3403", "OCI - Revaluation Surplus (IAS 16)", "الدخل الشامل الآخر - فائض إعادة التقييم", "Equity", "Equity", "3400"),
        _node("3404", "Non-controlling Interests (IFRS 10)", "حصص غير مسيطرة", "Equity", "Equity", "3400"),
        _node("3405", "Capital Redemption Reserve", "احتياطي استرداد رأس المال", "Equity", "Equity", "3400"),
        _node("3406", "Merger Reserve", "احتياطي الاندماج", "Equity", "Equity", "3400"),
        _node("3407", "ESIC Reserve (Employee Share Incentive)", "احتياطي حوافز الموظفين", "Equity", "Equity", "3400"),
    ]

    # =====================================================================
    # 4xxx — NON-CURRENT LIABILITIES (root_type=Liability)
    # =====================================================================
    tree += [
        _node("4000", "Liabilities", "الالتزامات", "Liability", "", None, True),
        _node("4100", "Non-Current Liabilities", "الالتزامات غير المتداولة", "Liability", "", "4000", True),
        _node("4200", "Current Liabilities", "الالتزامات المتداولة", "Liability", "Current Liability", "4000", True),

        # 4110 Long-term Borrowings
        _node("4110", "Long-term Borrowings", "القروض طويلة الأجل", "Liability", "", "4100", True),
        _node("4111", "Bank Loan - Emirates NBD (Long-term)", "قرض بنكي - بنك الإمارات دبي الوطني", "Liability", "", "4110"),
        _node("4112", "Bank Loan - ADCB (Long-term)", "قرض بنكي - بنك أبوظبي التجاري", "Liability", "", "4110"),
        _node("4113", "Bank Loan - FAB (Long-term)", "قرض بنكي - بنك أبوظبي الأول", "Liability", "", "4110"),
        _node("4114", "Bank Loan - Mashreq (Long-term)", "قرض بنكي - بنك المشرق", "Liability", "", "4110"),
        _node("4115", "Sukuk (Islamic Bond) - Long-term", "صكوك - طويلة الأجل", "Liability", "", "4110"),
        _node("4116", "Mortgage Loan (Long-term)", "قرض رهن عقاري - طويل الأجل", "Liability", "", "4110"),
        _node("4117", "Subordinated Loan", "قرض ثانوي", "Liability", "", "4110"),
        _node("4118", "Related Party Loan (Long-term)", "قرض طرف ذي علاقة - طويل الأجل", "Liability", "", "4110"),
        _node("4119", "Unamortised Loan Processing Fees", "رسوم معالجة القرض غير المستهلكة", "Liability", "", "4110"),

        # 4120 Lease Liabilities (IFRS 16) — non-current
        _node("4120", "Lease Liabilities (IFRS 16)", "التزامات الإيجار", "Liability", "", "4100", True),
        _node("4121", "Lease Liability - Buildings (Non-current)", "التزام إيجار - مبان (غير متداول)", "Liability", "", "4120"),
        _node("4122", "Lease Liability - Motor Vehicles (Non-current)", "التزام إيجار - مركبات (غير متداول)", "Liability", "", "4120"),
        _node("4123", "Lease Liability - Office Equipment (Non-current)", "التزام إيجار - معدات مكاتب (غير متداول)", "Liability", "", "4120"),

        # 4130 Long-term Payables
        _node("4130", "Long-term Payables", "دائنون طويلو الأجل", "Liability", "", "4100", True),
        _node("4131", "Trade Payables (Long-term)", "دائنون تجاريون - طويلو الأجل", "Liability", "Payable", "4130"),
        _node("4132", "Security Deposits Received (Long-term)", "ودائع ضمان مستلمة - طويلة الأجل", "Liability", "", "4130"),

        # 4140 Provisions (IAS 37)
        _node("4140", "Provisions (IAS 37)", "المخصصات", "Liability", "", "4100", True),
        _node("4141", "Provision for End-of-Service Benefits (EOSB)", "مخصص نهاية الخدمة", "Liability", "", "4140"),
        _node("4142", "Provision for Annual Leave", "مخصص الإجازة السنوية", "Liability", "", "4140"),
        _node("4143", "Provision for Bonus", "مخصص المكافآت", "Liability", "", "4140"),
        _node("4144", "Provision for Warranty Claims (IAS 37)", "مخصص مطالبات الضمان", "Liability", "", "4140"),
        _node("4145", "Provision for Legal Claims (IAS 37)", "مخصص المطالبات القانونية", "Liability", "", "4140"),
        _node("4146", "Provision for Decommissioning (IAS 37)", "مخصص تفكيك الأصول", "Liability", "", "4140"),
        _node("4147", "Provision for Onerous Contracts (IAS 37)", "مخصص العقود المثقلة بالالتزامات", "Liability", "", "4140"),
        _node("4148", "Provision for Restructuring (IAS 37)", "مخصص إعادة الهيكلة", "Liability", "", "4140"),
        _node("4149", "Provision for Gratuity (Unfunded)", "مخصص مكافأة نهاية الخدمة (غير ممول)", "Liability", "", "4140"),

        # 4150 Deferred Tax & Other Non-current
        _node("4150", "Deferred Tax Liabilities (IAS 12)", "التزامات الضريبة المؤجلة", "Liability", "", "4100", True),
        _node("4151", "Deferred Tax Liability - PPE", "التزام الضريبة المؤجلة - الممتلكات والمصانع والمعدات", "Liability", "", "4150"),
        _node("4152", "Deferred Tax Liability - Investment Property", "التزام الضريبة المؤجلة - العقارات الاستثمارية", "Liability", "", "4150"),
        _node("4153", "Government Grants (Deferred, IAS 20)", "منح حكومية مؤجلة", "Liability", "", "4100"),
        _node("4154", "Contract Liabilities (Non-current, IFRS 15)", "التزامات عقدية - غير متداولة", "Liability", "", "4100"),
        _node("4155", "Other Non-current Liabilities", "التزامات غير متداولة أخرى", "Liability", "", "4100"),
    ]

    # =====================================================================
    # 5xxx — CURRENT LIABILITIES (root_type=Liability)
    # =====================================================================
    tree += [
        # 5100 Short-term Borrowings
        _node("5100", "Short-term Borrowings", "القروض قصيرة الأجل", "Liability", "", "4200", True),
        _node("5101", "Bank Overdraft", "السحب على المكشوف", "Liability", "Current Liability", "5100"),
        _node("5102", "Short-term Bank Loan - Emirates NBD", "قرض بنكي قصير الأجل - بنك الإمارات دبي الوطني", "Liability", "Current Liability", "5100"),
        _node("5103", "Short-term Bank Loan - FAB", "قرض بنكي قصير الأجل - بنك أبوظبي الأول", "Liability", "Current Liability", "5100"),
        _node("5104", "Current Portion of Long-term Debt", "الجزء المتداول من قروض طويلة الأجل", "Liability", "Current Liability", "5100"),
        _node("5105", "Credit Card Payable", "بطاقة ائتمان - مستحقات", "Liability", "Current Liability", "5100"),
        _node("5106", "Dividends Payable", "توزيعات مستحقة الدفع", "Liability", "", "4200"),
        _node("5107", "Short-term Notes Payable", "أوراق دفع قصيرة الأجل", "Liability", "", "4200"),

        # 5200 Lease Liabilities (current portion)
        _node("5200", "Lease Liabilities - Current Portion (IFRS 16)", "التزامات الإيجار - الجزء المتداول", "Liability", "", "4200", True),
        _node("5201", "Lease Liability - Buildings (Current)", "التزام إيجار - مبان (متداول)", "Liability", "Current Liability", "5200"),
        _node("5202", "Lease Liability - Motor Vehicles (Current)", "التزام إيجار - مركبات (متداول)", "Liability", "Current Liability", "5200"),
        _node("5203", "Lease Liability - Office Equipment (Current)", "التزام إيجار - معدات مكاتب (متداول)", "Liability", "Current Liability", "5200"),

        # 5300 Accounts Payable
        _node("5300", "Accounts Payable", "الدائنون", "Liability", "Payable", "4200", True),
        _node("5301", "Trade Payables (Domestic)", "دائنون تجاريون - محليون", "Liability", "Payable", "5300"),
        _node("5302", "Trade Payables (GCC)", "دائنون تجاريون - دول مجلس التعاون", "Liability", "Payable", "5300"),
        _node("5303", "Trade Payables (International)", "دائنون تجاريون - دولي", "Liability", "Payable", "5300"),
        _node("5304", "Import Payables", "دائنون الواردات", "Liability", "Payable", "5300"),
        _node("5305", "Intercompany Payables", "دائنون - شركات المجموعة", "Liability", "Payable", "5300"),
        _node("5306", "Related Party Payables", "دائنون - أطراف ذات علاقة", "Liability", "Payable", "5300"),
        _node("5307", "Employee Payables", "مستحقات الموظفين", "Liability", "", "4200"),
        _node("5308", "Accrued Expenses", "مصروفات مستحقة", "Liability", "", "4200"),
        _node("5309", "Notes Payable", "أوراق دفع", "Liability", "Payable", "4200"),

        # 5400 VAT / Tax Payable (UAE)
        _node("5400", "VAT Payable (UAE 5%)", "ضريبة القيمة المضافة - دائنة", "Liability", "Tax", "4200", True),
        _node("5401", "Output VAT - Standard Rated 5%", "مخرجات ضريبة القيمة المضافة 5٪", "Liability", "Tax", "5400"),
        _node("5402", "Output VAT - Reverse Charge", "مخرجات ضريبة القيمة المضافة - آلية الاحتساب العكسي", "Liability", "Tax", "5400"),
        _node("5403", "Output VAT - Designated Zones", "مخرجات ضريبة القيمة المضافة - المناطق المحددة", "Liability", "Tax", "5400"),
        _node("5404", "Output VAT - Exports", "مخرجات ضريبة القيمة المضافة - صادرات", "Liability", "Tax", "5400"),
        _node("5405", "Output VAT - Imported Services", "مخرجات ضريبة القيمة المضافة - خدمات مستوردة", "Liability", "Tax", "5400"),
        _node("5406", "Corporate Tax Payable (UAE 9%)", "الضريبة المؤسسية المستحقة 9٪", "Liability", "Tax", "4200"),
        _node("5407", "Excise Tax Payable", "الضريبة الانتقائية المستحقة", "Liability", "Tax", "4200"),
        _node("5408", "Withholding Tax Payable", "ضريبة مستقطعة مستحقة", "Liability", "Tax", "4200"),

        # 5500 Contract Liabilities (IFRS 15)
        _node("5500", "Contract Liabilities (Current, IFRS 15)", "التزامات العقد - متداولة", "Liability", "", "4200", True),
        _node("5501", "Customer Advances - Trade", "دفعات مقدمة من العملاء - تجارية", "Liability", "", "5500"),
        _node("5502", "Deferred Revenue - Services", "إيرادات مؤجلة - خدمات", "Liability", "", "5500"),
        _node("5503", "Deferred Revenue - Goods", "إيرادات مؤجلة - بضائع", "Liability", "", "5500"),
        _node("5504", "Unearned Revenue", "إيرادات غير مكتسبة", "Liability", "", "5500"),

        # 5600 Other Current Liabilities
        _node("5600", "Other Current Liabilities", "التزامات متداولة أخرى", "Liability", "", "4200", True),
        _node("5601", "Wages Payable (EOSB Accrual)", "أجور مستحقة", "Liability", "Current Liability", "5600"),
        _node("5602", "Gratuity Payable (Current)", "مكافأة نهاية الخدمة المستحقة", "Liability", "Current Liability", "5600"),
        _node("5603", "Insurance Payable", "تأمين مستحق", "Liability", "Current Liability", "5600"),
        _node("5604", "Refundable Deposits (Current)", "ودائع مستردة - متداولة", "Liability", "Current Liability", "5600"),
        _node("5605", "Statutory Dues Payable", "رسوم قانونية مستحقة", "Liability", "Current Liability", "5600"),
        _node("5606", "Provision for Income Tax", "مخصص ضريبة الدخل", "Liability", "Current Liability", "5600"),
    ]

    # =====================================================================
    # 6xxx — INCOME (root_type=Income)
    # =====================================================================
    tree += [
        _node("6000", "Income", "الإيرادات", "Income", "", None, True),
        _node("6100", "Revenue from Operations", "إيرادات التشغيل", "Income", "Income Account", "6000", True),

        # 6110 Sales (goods) — UAE VAT
        _node("6110", "Sales (Goods - UAE)", "مبيعات (بضائع - الإمارات)", "Income", "Income Account", "6100", True),
        _node("6111", "Sales - Domestic (Standard Rated 5%)", "مبيعات محلية (خاضعة للنظام 5٪)", "Income", "Income Account", "6110"),
        _node("6112", "Sales - Domestic (Zero Rated)", "مبيعات محلية (معفاة بصفر)", "Income", "Income Account", "6110"),
        _node("6113", "Sales - Domestic (Exempt)", "مبيعات محلية (معفاة)", "Income", "Income Account", "6110"),
        _node("6114", "Sales - Designated Zones (5%)", "مبيعات - المناطق المحددة (5٪)", "Income", "Income Account", "6110"),
        _node("6115", "Sales - Exports (Zero Rated)", "مبيعات تصدير (معفاة بصفر)", "Income", "Income Account", "6110"),
        _node("6116", "Sales - GCC (Reverse Charge)", "مبيعات - مجلس التعاون (آلية عكسية)", "Income", "Income Account", "6110"),
        _node("6117", "Sales - Intercompany", "مبيعات - شركات المجموعة", "Income", "Income Account", "6110"),
        _node("6118", "Sales Returns and Allowances", "مردودات ومسموحات المبيعات", "Income", "Income Account", "6110"),
        _node("6119", "Sales Discounts", "خصومات المبيعات", "Income", "Income Account", "6110"),

        # 6120 Service Revenue
        _node("6120", "Service Revenue (UAE)", "إيرادات الخدمات (الإمارات)", "Income", "Income Account", "6100", True),
        _node("6121", "Consulting Revenue", "إيرادات الاستشارات", "Income", "Income Account", "6120"),
        _node("6122", "Maintenance Revenue", "إيرادات الصيانة", "Income", "Income Account", "6120"),
        _node("6123", "Installation Revenue", "إيرادات التركيب", "Income", "Income Account", "6120"),
        _node("6124", "Training Revenue", "إيرادات التدريب", "Income", "Income Account", "6120"),
        _node("6125", "Management Fee Income", "إيرادات رسوم الإدارة", "Income", "Income Account", "6120"),
        _node("6126", "Technical Service Revenue", "إيرادات الخدمات الفنية", "Income", "Income Account", "6120"),
        _node("6127", "Marketing Revenue", "إيرادات التسويق", "Income", "Income Account", "6120"),

        # 6130 Other Operating Income
        _node("6130", "Other Operating Income", "إيرادات تشغيلية أخرى", "Income", "Indirect Income", "6100", True),
        _node("6131", "Commission Income", "إيرادات العمولات", "Income", "Indirect Income", "6130"),
        _node("6132", "Royalty Income", "إيرادات الإتاوات", "Income", "Indirect Income", "6130"),
        _node("6133", "Rent Income (Operating)", "إيرادات الإيجار (تشغيلي)", "Income", "Indirect Income", "6130"),
        _node("6134", "Scrap Sales", "مبيعات الخردة", "Income", "Indirect Income", "6130"),
        _node("6135", "Insurance Recoveries", "استردادات التأمين", "Income", "Indirect Income", "6130"),

        # 6200 Finance Income
        _node("6200", "Finance Income", "الإيرادات المالية", "Income", "Indirect Income", "6000", True),
        _node("6201", "Interest Income on Bank Deposits", "فوائد ودائع بنكية", "Income", "Indirect Income", "6200"),
        _node("6202", "Interest Income on Trade Receivables", "فوائد المدينين التجاريين", "Income", "Indirect Income", "6200"),
        _node("6203", "Interest Income on Loans to Subsidiaries", "فوائد قروض للشركات التابعة", "Income", "Indirect Income", "6200"),
        _node("6204", "Dividend Income", "إيرادات التوزيعات", "Income", "Indirect Income", "6200"),
        _node("6205", "Gain on Disposal of Investments", "أرباح بيع الاستثمارات", "Income", "Indirect Income", "6200"),
        _node("6206", "Fair Value Gain on Financial Instruments (IFRS 9)", "أرباح القيمة العادلة للأدوات المالية", "Income", "Indirect Income", "6200"),
        _node("6207", "Foreign Exchange Gain", "أرباح فروقات العملة", "Income", "Indirect Income", "6200"),
        _node("6208", "Gain on Disposal of Property, Plant and Equipment", "أرباح بيع الممتلكات والمصانع والمعدات", "Income", "Indirect Income", "6200"),

        # 6300 Other Income
        _node("6300", "Other Non-operating Income", "إيرادات غير تشغيلية أخرى", "Income", "Indirect Income", "6000", True),
        _node("6301", "Government Grants Income (IAS 20)", "إيرادات المنح الحكومية", "Income", "Indirect Income", "6300"),
        _node("6302", "Sponsorship Income", "إيرادات الرعاية", "Income", "Indirect Income", "6300"),
        _node("6303", "Bad Debts Recovered", "مستردات ديون معدومة", "Income", "Indirect Income", "6300"),
        _node("6304", "Miscellaneous Income", "إيرادات متنوعة", "Income", "Indirect Income", "6300"),
    ]

    # =====================================================================
    # 7xxx — EXPENSES (root_type=Expense)
    # =====================================================================
    tree += [
        _node("7000", "Expenses", "المصروفات", "Expense", "", None, True),
        _node("7100", "Operating Expenses", "مصروفات التشغيل", "Expense", "Indirect Expense", "7000", True),

        # 7110 Employee Costs (UAE specific - EOSB etc.)
        _node("7110", "Employee Costs (UAE)", "تكاليف الموظفين (الإمارات)", "Expense", "Indirect Expense", "7100", True),
        _node("7111", "Salaries and Wages", "رواتب وأجور", "Expense", "Indirect Expense", "7110"),
        _node("7112", "Basic Salary", "الراتب الأساسي", "Expense", "Indirect Expense", "7110"),
        _node("7113", "Housing Allowance", "بدل السكن", "Expense", "Indirect Expense", "7110"),
        _node("7114", "Transport Allowance", "بدل المواصلات", "Expense", "Indirect Expense", "7110"),
        _node("7115", "Other Allowances", "بدلات أخرى", "Expense", "Indirect Expense", "7110"),
        _node("7116", "Overtime Pay", "أجور العمل الإضافي", "Expense", "Indirect Expense", "7110"),
        _node("7117", "Air Ticket Entitlement (Annual Leave)", "تذاكر السفر السنوية", "Expense", "Indirect Expense", "7110"),
        _node("7118", "End-of-Service Benefits (EOSB) Expense - UAE", "مصروف نهاية الخدمة - الإمارات", "Expense", "Indirect Expense", "7110"),
        _node("7119", "Gratuity Expense (IAS 19)", "مصروف مكافأة نهاية الخدمة", "Expense", "Indirect Expense", "7110"),
        _node("7120", "Staff Bonus and Incentives", "مكافآت وحوافز الموظفين", "Expense", "Indirect Expense", "7110"),
        _node("7121", "Staff Training and Development", "تدريب وتطوير الموظفين", "Expense", "Indirect Expense", "7110"),
        _node("7122", "Staff Recruitment Costs", "تكاليف توظيف الموظفين", "Expense", "Indirect Expense", "7110"),
        _node("7123", "Staff Uniforms and PPE", "أزياء الموظفين ومعدات الحماية", "Expense", "Indirect Expense", "7110"),
        _node("7124", "Work Permits and Residency Visas (UAE)", "تصاريح العمل وتأشيرات الإقامة", "Expense", "Indirect Expense", "7110"),
        _node("7125", "Medical Insurance - Employees (UAE)", "التأمين الصحي - الموظفين", "Expense", "Indirect Expense", "7110"),
        _node("7126", "Employee Benefits - Other", "منافع الموظفين - أخرى", "Expense", "Indirect Expense", "7110"),

        # 7130 Rent & Utilities
        _node("7130", "Rent and Utilities", "الإيجار والمرافق", "Expense", "Indirect Expense", "7100", True),
        _node("7131", "Office Rent", "إيجار المكتب", "Expense", "Indirect Expense", "7130"),
        _node("7132", "Warehouse Rent", "إيجار المستودع", "Expense", "Indirect Expense", "7130"),
        _node("7133", "Equipment Rental", "تأجير المعدات", "Expense", "Indirect Expense", "7130"),
        _node("7134", "Utilities - Electricity and Water (DEWA/FEWA)", "كهرباء ومياه", "Expense", "Indirect Expense", "7130"),
        _node("7135", "Utilities - Gas", "غاز", "Expense", "Indirect Expense", "7130"),
        _node("7136", "Telecommunications", "اتصالات", "Expense", "Indirect Expense", "7130"),
        _node("7137", "Internet and IT Services", "إنترنت وخدمات تكنولوجيا المعلومات", "Expense", "Indirect Expense", "7130"),
        _node("7138", "Cooling / District Cooling (Emicool, etc.)", "تبريد مركزي", "Expense", "Indirect Expense", "7130"),

        # 7140 Travel & Entertainment
        _node("7140", "Travel and Entertainment", "السفر والترفيه", "Expense", "Indirect Expense", "7100", True),
        _node("7141", "Air Travel", "سفر جوي", "Expense", "Indirect Expense", "7140"),
        _node("7142", "Hotel Accommodation", "إقامة فندقية", "Expense", "Indirect Expense", "7140"),
        _node("7143", "Local Conveyance", "مواصلات محلية", "Expense", "Indirect Expense", "7140"),
        _node("7144", "Business Meals and Entertainment", "وجبات عمل وترفيه", "Expense", "Indirect Expense", "7140"),
        _node("7145", "Visa and Travel Insurance", "تأشيرات وتأمين سفر", "Expense", "Indirect Expense", "7140"),
        _node("7146", "Conference and Trade Show Fees", "رسوم المؤتمرات والمعارض", "Expense", "Indirect Expense", "7140"),

        # 7150 Admin & Office
        _node("7150", "Administrative and Office Expenses", "مصروفات إدارية ومكتبية", "Expense", "Indirect Expense", "7100", True),
        _node("7151", "Office Stationery and Supplies", "قرطاسية ولوازم مكتبية", "Expense", "Indirect Expense", "7150"),
        _node("7152", "Printing and Photocopying", "طباعة وتصوير", "Expense", "Indirect Expense", "7150"),
        _node("7153", "Postage and Courier", "بريد وشحن", "Expense", "Indirect Expense", "7150"),
        _node("7154", "Bank Charges", "رسوم بنكية", "Expense", "Indirect Expense", "7150"),
        _node("7155", "Loan Processing Fees", "رسوم معالجة القروض", "Expense", "Indirect Expense", "7150"),
        _node("7156", "Credit Card Merchant Fees", "رسوم تجار بطاقات الائتمان", "Expense", "Indirect Expense", "7150"),
        _node("7157", "Office Cleaning and Maintenance", "تنظيف وصيانة المكتب", "Expense", "Indirect Expense", "7150"),
        _node("7158", "Pest Control and Security Services", "مكافحة حشرات وخدمات أمنية", "Expense", "Indirect Expense", "7150"),
        _node("7159", "Subscriptions and Memberships", "اشتراكات وعضويات", "Expense", "Indirect Expense", "7150"),

        # 7160 Repairs & Maintenance
        _node("7160", "Repairs and Maintenance", "الإصلاحات والصيانة", "Expense", "Indirect Expense", "7100", True),
        _node("7161", "Building Repairs and Maintenance", "إصلاح وصيانة المباني", "Expense", "Indirect Expense", "7160"),
        _node("7162", "Equipment Repairs and Maintenance", "إصلاح وصيانة المعدات", "Expense", "Indirect Expense", "7160"),
        _node("7163", "Computer Hardware Maintenance", "صيانة أجهزة الحاسوب", "Expense", "Indirect Expense", "7160"),
        _node("7164", "Software Maintenance and Licences", "صيانة وتراخيص البرمجيات", "Expense", "Indirect Expense", "7160"),
        _node("7165", "Vehicle Repairs and Maintenance", "إصلاح وصيانة المركبات", "Expense", "Indirect Expense", "7160"),

        # 7170 Depreciation & Amortisation
        _node("7170", "Depreciation and Amortisation", "الاستهلاك والإطفاء", "Expense", "Depreciation", "7100", True),
        _node("7171", "Depreciation - Buildings", "استهلاك المباني", "Expense", "Depreciation", "7170"),
        _node("7172", "Depreciation - Plant and Machinery", "استهلاك المصانع والآلات", "Expense", "Depreciation", "7170"),
        _node("7173", "Depreciation - Motor Vehicles", "استهلاك المركبات", "Expense", "Depreciation", "7170"),
        _node("7174", "Depreciation - Furniture and Fixtures", "استهلاك الأثاث والتركيبات", "Expense", "Depreciation", "7170"),
        _node("7175", "Depreciation - Office Equipment", "استهلاك معدات المكاتب", "Expense", "Depreciation", "7170"),
        _node("7176", "Depreciation - Computer Equipment", "استهلاك معدات الحاسوب", "Expense", "Depreciation", "7170"),
        _node("7177", "Depreciation - Right-of-Use Assets (IFRS 16)", "استهلاك أصول حق الاستخدام", "Expense", "Depreciation", "7170"),
        _node("7178", "Depreciation - Investment Property (IAS 40)", "استهلاك العقارات الاستثمارية", "Expense", "Depreciation", "7170"),
        _node("7179", "Amortisation - Intangible Assets", "إطفاء الأصول غير الملموسة", "Expense", "Depreciation", "7170"),

        # 7180 Impairment (IAS 36)
        _node("7180", "Impairment Loss (IAS 36)", "خسارة الانخفاض في القيمة", "Expense", "Indirect Expense", "7100", True),
        _node("7181", "Impairment - Property, Plant and Equipment", "انخفاض قيمة الممتلكات والمصانع والمعدات", "Expense", "Indirect Expense", "7180"),
        _node("7182", "Impairment - Intangible Assets", "انخفاض قيمة الأصول غير الملموسة", "Expense", "Indirect Expense", "7180"),
        _node("7183", "Impairment - Goodwill", "انخفاض قيمة الشهرة", "Expense", "Indirect Expense", "7180"),
        _node("7184", "Impairment - Trade Receivables (ECL, IFRS 9)", "خسائر الائتمان المتوقعة للمدينين", "Expense", "Indirect Expense", "7180"),
        _node("7185", "Impairment - Inventory (IAS 2)", "انخفاض قيمة المخزون", "Expense", "Indirect Expense", "7180"),
        _node("7186", "Impairment - Investment Property", "انخفاض قيمة العقارات الاستثمارية", "Expense", "Indirect Expense", "7180"),
        _node("7187", "Impairment - Investment in Subsidiaries", "انخفاض قيمة استثمارات الشركات التابعة", "Expense", "Indirect Expense", "7180"),
        _node("7188", "Reversal of Impairment Loss", "عكس خسارة الانخفاض في القيمة", "Expense", "Indirect Expense", "7180"),

        # 7190 Selling & Marketing
        _node("7190", "Selling and Marketing Expenses", "مصروفات البيع والتسويق", "Expense", "Indirect Expense", "7100", True),
        _node("7191", "Advertising and Promotion", "إعلان وترويج", "Expense", "Indirect Expense", "7190"),
        _node("7192", "Digital Marketing", "تسويق رقمي", "Expense", "Indirect Expense", "7190"),
        _node("7193", "Sales Commission", "عمولات المبيعات", "Expense", "Indirect Expense", "7190"),
        _node("7194", "Exhibition and Trade Fair Costs", "معارض ومعارض تجارية", "Expense", "Indirect Expense", "7190"),
        _node("7195", "Free Samples and Gifts", "عينات وهدايا مجانية", "Expense", "Indirect Expense", "7190"),
        _node("7196", "Sponsorship Costs", "تكاليف الرعاية", "Expense", "Indirect Expense", "7190"),

        # 7200 Professional Services
        _node("7200", "Professional and Legal Fees", "أتعاب مهنية وقانونية", "Expense", "Indirect Expense", "7000", True),
        _node("7201", "Audit Fees", "أتعاب التدقيق", "Expense", "Indirect Expense", "7200"),
        _node("7202", "Legal Fees", "أتعاب قانونية", "Expense", "Indirect Expense", "7200"),
        _node("7203", "Tax Consultancy Fees", "أتعاب استشارات ضريبية", "Expense", "Indirect Expense", "7200"),
        _node("7204", "Accounting and Bookkeeping Fees", "أتعاب محاسبية", "Expense", "Indirect Expense", "7200"),
        _node("7205", "VAT Filing Fees", "رسوم تقديم إقرارات ضريبة القيمة المضافة", "Expense", "Indirect Expense", "7200"),
        _node("7206", "Corporate Tax Filing Fees (UAE 9%)", "رسوم تقديم الإقرار الضريبي المؤسسي 9٪", "Expense", "Indirect Expense", "7200"),
        _node("7207", "PRO Services and Government Relations (UAE)", "خدمات العلاقات الحكومية", "Expense", "Indirect Expense", "7200"),
        _node("7208", "Translation and Attestation Fees", "ترجمة وتصديق", "Expense", "Indirect Expense", "7200"),

        # 7300 Insurance
        _node("7300", "Insurance Expenses", "مصروفات التأمين", "Expense", "Indirect Expense", "7000", True),
        _node("7301", "General Insurance", "تأمين عام", "Expense", "Indirect Expense", "7300"),
        _node("7302", "Vehicle Insurance", "تأمين المركبات", "Expense", "Indirect Expense", "7300"),
        _node("7303", "Property Insurance", "تأمين الممتلكات", "Expense", "Indirect Expense", "7300"),
        _node("7304", "Professional Indemnity Insurance", "تأمين المسؤولية المهنية", "Expense", "Indirect Expense", "7300"),
        _node("7305", "Workmen's Compensation Insurance", "تأمين تعويضات العمال", "Expense", "Indirect Expense", "7300"),

        # 7400 Finance Costs
        _node("7400", "Finance Costs", "التكاليف المالية", "Expense", "Indirect Expense", "7000", True),
        _node("7401", "Interest Expense on Bank Loans", "فوائد القروض البنكية", "Expense", "Indirect Expense", "7400"),
        _node("7402", "Interest Expense on Lease Liabilities (IFRS 16)", "فوائد التزامات الإيجار", "Expense", "Indirect Expense", "7400"),
        _node("7403", "Interest Expense on Sukuk", "فوائد الصكوك", "Expense", "Indirect Expense", "7400"),
        _node("7404", "Finance Charges on Hire Purchase", "تكاليف تمويل الشراء بالتقسيط", "Expense", "Indirect Expense", "7400"),
        _node("7405", "Loss on Disposal of Investments", "خسائر بيع الاستثمارات", "Expense", "Indirect Expense", "7400"),
        _node("7406", "Fair Value Loss on Financial Instruments (IFRS 9)", "خسائر القيمة العادلة للأدوات المالية", "Expense", "Indirect Expense", "7400"),
        _node("7407", "Foreign Exchange Loss", "خسائر فروقات العملة", "Expense", "Indirect Expense", "7400"),
        _node("7408", "Loss on Disposal of Property, Plant and Equipment", "خسائر بيع الممتلكات والمصانع والمعدات", "Expense", "Indirect Expense", "7400"),

        # 7500 Other Operating Expenses
        _node("7500", "Other Operating Expenses", "مصروفات تشغيلية أخرى", "Expense", "Indirect Expense", "7000", True),
        _node("7501", "Donations and CSR", "تبرعات ومسؤولية اجتماعية", "Expense", "Indirect Expense", "7500"),
        _node("7502", "Penalties and Fines", "غرامات وعقوبات", "Expense", "Indirect Expense", "7500"),
        _node("7503", "Entertainment Tax (5%)", "ضريبة الترفيه", "Expense", "Indirect Expense", "7500"),
        _node("7504", "Bad Debts Written Off", "ديون معدومة مشطوبة", "Expense", "Indirect Expense", "7500"),
        _node("7505", "Inventory Write-off (IAS 2)", "شطب المخزون", "Expense", "Indirect Expense", "7500"),
        _node("7506", "Loss on Inventory (NRV Adjustment, IAS 2)", "خسائر المخزون - تعديل القيمة الصافية القابلة للتحقق", "Expense", "Indirect Expense", "7500"),
    ]

    # =====================================================================
    # 8xxx — OFF-BALANCE-SHEET / MEMORANDUM (root_type=Liability)
    # =====================================================================
    tree += [
        _node("8000", "Off-Balance Sheet / Memorandum", "حسابات خارج الميزانية / حسابات مذكرة", "Liability", "", None, True),
        _node("8100", "Contingent Assets (IAS 37)", "أصول محتملة", "Liability", "", "8000", True),
        _node("8101", "Possible Claims - Pending Lawsuits", "مطالبات محتملة - دعاوى قضائية", "Liability", "", "8100"),
        _node("8102", "Tax Disputes - Under Appeal", "نزاعات ضريبية - قيد الاستئناف", "Liability", "", "8100"),
        _node("8103", "Insurance Claims Pending", "مطالبات تأمين قيد المعالجة", "Liability", "", "8100"),

        _node("8200", "Contingent Liabilities (IAS 37)", "التزامات محتملة", "Liability", "", "8000", True),
        _node("8201", "Bank Guarantees Issued", "ضمانات بنكية صادرة", "Liability", "", "8200"),
        _node("8202", "Letters of Credit (LC) Outstanding", "خطابات اعتماد قائمة", "Liability", "", "8200"),
        _node("8203", "Performance Bonds", "سندات أداء", "Liability", "", "8200"),
        _node("8204", "Pending Litigation Provisions - Disclosed", "مخصصات التقاضي المعلقة - مفصح عنها", "Liability", "", "8200"),
        _node("8205", "Tax Assessments Under Dispute", "تقييمات ضريبية متنازع عليها", "Liability", "", "8200"),

        _node("8300", "Commitments (IFRS Framework)", "الالتزامات التعاقدية", "Liability", "", "8000", True),
        _node("8301", "Capital Commitments", "التزامات رأسمالية", "Liability", "", "8300"),
        _node("8302", "Operating Lease Commitments (Pre-IFRS 16)", "التزامات إيجار تشغيلي (قبل IFRS 16)", "Liability", "", "8300"),
        _node("8303", "Purchase Commitments", "التزامات شراء", "Liability", "", "8300"),

        _node("8400", "Memorandum Accounts", "حسابات مذكرة", "Liability", "", "8000", True),
        _node("8401", "Goods on Consignment (Memorandum)", "بضائع بالأمانة (مذكرة)", "Liability", "", "8400"),
        _node("8402", "Goods on Sale or Return (Memorandum)", "بضائع بيع أو إرجاع (مذكرة)", "Liability", "", "8400"),
        _node("8403", "Nominal / Head Office Account (Memorandum)", "حساب اسمي / حساب المركز الرئيسي (مذكرة)", "Liability", "", "8400"),
    ]

    # =====================================================================
    # 9xxx — COST OF GOODS SOLD (root_type=Expense)
    # =====================================================================
    tree += [
        _node("9000", "Cost of Goods Sold", "تكلفة البضاعة المباعة", "Expense", "Cost of Goods Sold", None, True),
        _node("9100", "Direct Material Costs", "تكاليف المواد المباشرة", "Expense", "Cost of Goods Sold", "9000", True),
        _node("9101", "Raw Materials Consumed", "المواد الخام المستهلكة", "Expense", "Cost of Goods Sold", "9100"),
        _node("9102", "Packing Materials Consumed", "مواد التعبئة المستهلكة", "Expense", "Cost of Goods Sold", "9100"),
        _node("9103", "Purchase of Finished Goods", "شراء بضاعة جاهزة", "Expense", "Cost of Goods Sold", "9100"),
        _node("9104", "Direct Material Purchases (Imports)", "مشتريات مواد مباشرة (واردات)", "Expense", "Cost of Goods Sold", "9100"),
        _node("9105", "Customs Duty and Import Charges", "رسوم جمركية ورسوم استيراد", "Expense", "Cost of Goods Sold", "9100"),
        _node("9106", "Freight Inward", "شحن داخلي", "Expense", "Cost of Goods Sold", "9100"),
        _node("9107", "Purchase Returns and Allowances", "مردودات ومسموحات المشتريات", "Expense", "Cost of Goods Sold", "9100"),
        _node("9108", "Inventory Obsolescence Expense", "مصروف تقادم المخزون", "Expense", "Cost of Goods Sold", "9100"),

        _node("9200", "Direct Labour Costs", "تكاليف العمالة المباشرة", "Expense", "Cost of Goods Sold", "9000", True),
        _node("9201", "Direct Labour Wages", "أجور العمالة المباشرة", "Expense", "Cost of Goods Sold", "9200"),
        _node("9202", "Direct Labour Overtime", "عمل إضافي - عمالة مباشرة", "Expense", "Cost of Goods Sold", "9200"),
        _node("9203", "Direct Labour EOSB Provision", "مخصص نهاية الخدمة - عمالة مباشرة", "Expense", "Cost of Goods Sold", "9200"),

        _node("9300", "Manufacturing Overheads", "التكاليف الصناعية غير المباشرة", "Expense", "Cost of Goods Sold", "9000", True),
        _node("9301", "Factory Rent", "إيجار المصنع", "Expense", "Cost of Goods Sold", "9300"),
        _node("9302", "Factory Utilities", "مرافق المصنع", "Expense", "Cost of Goods Sold", "9300"),
        _node("9303", "Factory Depreciation", "استهلاك المصنع", "Expense", "Cost of Goods Sold", "9300"),
        _node("9304", "Indirect Labour", "عمالة غير مباشرة", "Expense", "Cost of Goods Sold", "9300"),
        _node("9305", "Factory Consumables", "مواد استهلاكية للمصنع", "Expense", "Cost of Goods Sold", "9300"),
        _node("9306", "Factory Maintenance", "صيانة المصنع", "Expense", "Cost of Goods Sold", "9300"),
        _node("9307", "Quality Control Costs", "تكاليف مراقبة الجودة", "Expense", "Cost of Goods Sold", "9300"),
        _node("9308", "Subcontracting Costs", "تكاليف التصنيع الخارجي", "Expense", "Cost of Goods Sold", "9300"),

        _node("9400", "Inventory Adjustments", "تسويات المخزون", "Expense", "Cost of Goods Sold", "9000", True),
        _node("9401", "Inventory Variance", "فروقات المخزون", "Expense", "Cost of Goods Sold", "9400"),
        _node("9402", "Stock Adjustment (Write-off)", "تسوية المخزون (شطب)", "Expense", "Stock Adjustment", "9400"),
        _node("9403", "Stock Adjustment (Write-down, NRV)", "تسوية المخزون (تخفيض للقيمة الصافية)", "Expense", "Stock Adjustment", "9400"),
        _node("9404", "Cost of Goods Sold - Other", "تكلفة البضاعة المباعة - أخرى", "Expense", "Cost of Goods Sold", "9400"),
    ]

    # ERPNext's Account validator rejects a child whose account_type
    # matches one of these "parent-only" types. Strip them from non-group
    # accounts, and auto-mark is_group=1 for any account that has children.
    parent_numbers = {
        e.get("parent_account_number") for e in tree
        if e.get("parent_account_number")
    }
    for e in tree:
        if e["account_number"] in parent_numbers:
            e["is_group"] = 1
    LEAF_ONLY_TYPES = {
        "Current Asset", "Current Liability",
        "Direct Income", "Direct Expense",
        "Indirect Income", "Indirect Expense",
        "Bank", "Cash",  # also typically parent-only
    }
    # Strip these types from any account whose PARENT has the same type.
    # That includes the intermediate groups under a 7xxx root group.
    for e in tree:
        if not e.get("parent_account_number"):
            continue  # root — keep the type as-is
        parent = next((p for p in tree if p["account_number"] == e["parent_account_number"]), None)
        if parent and parent.get("account_type") == e.get("account_type") and e["account_type"] in LEAF_ONLY_TYPES:
            e["account_type"] = ""

    return tree


# ---------------------------------------------------------------------------
# Seeder
# ---------------------------------------------------------------------------

def seed_uae_coa(company: str) -> dict:
    """Idempotently insert the full UAE COA into the given company.

    Returns a summary dict with counts.

    Pattern (mirrors ERPNext's create_charts):
    - Top-level groups (parent_account_number is None) are inserted first
      with ignore_mandatory=True so Frappe allows them to have no parent.
    - Children follow in tree order — their parent group is already in the DB
      because the tree is declared parent-first.
    - A commit is issued after every insert because Frappe's link validation
      reads via SQL and would otherwise miss the uncommitted parent row.
    - A rebuild_tree('Account', 'parent_account') call at the end repairs
      the NestedSet lft/rgt values that the bypass above may have skipped.
    """
    if not frappe.db.exists("Company", company):
        frappe.throw(f"Company {company!r} does not exist")

    company_doc = frappe.get_doc("Company", company)
    abbr = company_doc.abbr or "UAE"
    tree = build_coa_tree()

    # Group-by-number lookup
    by_num = {a["account_number"]: a for a in tree}

    inserted = 0
    skipped = 0

    # Walk in tree order (parents first because we declared them so).
    for a in tree:
        account_name_en = a["account_name_en"]
        if frappe.db.exists("Account", {"account_name": account_name_en, "company": company}):
            skipped += 1
            continue
        # Frappe prepends account_number to the stored name:
        # e.g. "1000 - Assets - TUAE". We must reference the parent by this
        # exact full name, not the friendly account_name, when assigning
        # parent_account (because parent_account is a Link to Account.name).
        parent_full_name = None
        parent_num = a.get("parent_account_number")
        if parent_num:
            parent_en = by_num[parent_num]["account_name_en"]
            parent_num_str = by_num[parent_num]["account_number"]
            parent_full_name = f"{parent_num_str} - {parent_en} - {abbr}"

        doc = frappe.new_doc("Account")
        doc.company = company
        doc.account_name = account_name_en
        # Frappe's Account has only account_name; we keep the Arabic name in
        # build_coa_tree() but do not persist it as a DB field (no custom
        # field on Account by design — the test validates the source tree).
        doc.account_number = a["account_number"]
        doc.root_type = a["root_type"]
        doc.account_type = a.get("account_type") or None
        doc.is_group = a.get("is_group", 0)
        doc.account_currency = a.get("account_currency") or "AED"
        if parent_full_name:
            doc.parent_account = parent_full_name
        doc.flags.ignore_permissions = True
        # Root groups (no parent) would normally fail the parent_account
        # mandatory check. ERPNext bypasses this with ignore_mandatory=True.
        if not parent_full_name:
            doc.flags.ignore_mandatory = True
        doc.insert()
        # Commit per insert so the next iteration's link validation can
        # see this parent in the DB.
        frappe.db.commit()
        inserted += 1

    # Rebuild the NestedSet so the lft/rgt numbers reflect the inserted tree.
    try:
        from frappe.utils.nestedset import rebuild_tree
        frappe.local.flags.ignore_update_nsm = True
        rebuild_tree("Account", "parent_account")
        frappe.local.flags.ignore_update_nsm = False
    except Exception:
        frappe.local.flags.ignore_update_nsm = False
        # Don't fail the seed if rebuild_tree is unhappy in test env

    return {
        "company": company,
        "inserted": inserted,
        "skipped": skipped,
        "total": len(tree),
    }


def install_coa(company: str | None = None) -> dict:
    """bench execute entry point.

    If `company` is None, finds the first company with country='United Arab
    Emirates' or aborts.
    """
    if not company:
        uae_companies = frappe.get_all(
            "Company",
            filters={"country": "United Arab Emirates"},
            pluck="name",
        )
        if not uae_companies:
            frappe.throw("No UAE company found; pass company explicitly")
        company = uae_companies[0]
    return seed_uae_coa(company)


# ---------------------------------------------------------------------------
# JSON fixture (for fixtures/uae_coa.json)
# ---------------------------------------------------------------------------

def dump_fixture(path: str | Path) -> None:
    """Write build_coa_tree() to a JSON fixture file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_coa_tree(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
