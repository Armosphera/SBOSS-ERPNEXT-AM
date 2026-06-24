# frappe_armenia

ERPNext localization app for Armenia. Armosphera Proprietary.

## What it adds

- Armenian standard chart of accounts (≈350 accounts, HY/EN bilingual names)
- Armenian VAT (20% standard, 0% export, exempt, reverse charge)
- Armenian e-invoice connector (e-SHK format)
- Armenian payroll extensions (income tax, military tax 5%, pension 10%)
- Bank integrations: Ameriabank, Ardshinbank, ACBA (ISO20022 / MT940)
- Bilingual HY/EN print formats

## Install

```bash
bench get-app apps/frappe_armenia
bench --site YOUR.SITE install-app frappe_armenia
```

## License

Armosphera Proprietary — see [`LICENSE-ARMOSPHERA.md`](../../LICENSE-ARMOSPHERA.md).

## Status

v0.0.1 — placeholder. Real implementation in W1 tasks.
