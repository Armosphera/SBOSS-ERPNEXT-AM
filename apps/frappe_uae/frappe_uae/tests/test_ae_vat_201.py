"""Tests for AE VAT 201 return form (W2-T13).

The AE VAT 201 is the FTA-mandated VAT return form (Federal Tax
Authority, UAE). It aggregates OUTPUT VAT (from submitted Sales
Invoices) and INPUT VAT (from submitted Purchase Invoices) within
a date range, and computes the net VAT payable (or refundable).

Mirrors ``frappe_armenia.armenia.report.am_vat_return`` (W1-T15) so
the two apps look symmetric and easy to extend.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from frappe_uae.uae.report.ae_vat_201.ae_vat_201 import compute_ae_vat_return


def _row(vat_sum: float, inv_count: int) -> dict:
    """Build a mock frappe.db.sql row (frappe._dict-like)."""
    return {"vat_sum": float(vat_sum), "inv_count": int(inv_count)}


class TestComputeAEBVATReturn(unittest.TestCase):
    """Pure helper tests for compute_ae_vat_return() with mocked DB."""

    def _run(
        self,
        sales_row=None,
        purchase_row=None,
        company="_Test UAE Co W2T13",
        from_date="2026-01-01",
        to_date="2026-03-31",
    ):
        """Run compute_ae_vat_return while mocking frappe.db.sql.

        Returns the result dict. The mock fires twice (once for Sales
        Invoice, once for Purchase Invoice); we use side_effect to
        return the appropriate row per doctype.
        """
        if sales_row is None:
            sales_row = _row(0.0, 0)
        if purchase_row is None:
            purchase_row = _row(0.0, 0)
        with patch(
            "frappe_uae.uae.report.ae_vat_201.ae_vat_201.frappe.db.sql",
            side_effect=lambda *a, **kw: [sales_row] if "Sales" in a[0] else [purchase_row],
        ) as _:
            return compute_ae_vat_return(company, from_date, to_date)

    def test_empty_period_returns_zeros(self):
        r = self._run(sales_row=_row(0.0, 0), purchase_row=_row(0.0, 0))
        self.assertEqual(r["output_vat"], 0.0)
        self.assertEqual(r["input_vat"], 0.0)
        self.assertEqual(r["net_vat"], 0.0)
        self.assertEqual(r["output_invoice_count"], 0)
        self.assertEqual(r["input_invoice_count"], 0)
        # Period + company echoed back
        self.assertEqual(r["company"], "_Test UAE Co W2T13")
        self.assertEqual(r["from_date"], "2026-01-01")
        self.assertEqual(r["to_date"], "2026-03-31")

    def test_only_sales_invoices_in_period(self):
        r = self._run(
            sales_row=_row(250.0, 5),  # 5 sales invoices, 250 AED total VAT
            purchase_row=_row(0.0, 0),
        )
        self.assertEqual(r["output_vat"], 250.0)
        self.assertEqual(r["input_vat"], 0.0)
        self.assertEqual(r["net_vat"], 250.0)
        self.assertEqual(r["output_invoice_count"], 5)
        self.assertEqual(r["input_invoice_count"], 0)

    def test_only_purchase_invoices_in_period(self):
        r = self._run(
            sales_row=_row(0.0, 0),
            purchase_row=_row(75.5, 3),  # 3 purchase invoices, 75.50 AED input VAT
        )
        self.assertEqual(r["output_vat"], 0.0)
        self.assertEqual(r["input_vat"], 75.5)
        self.assertEqual(r["net_vat"], -75.5)  # refundable
        self.assertEqual(r["output_invoice_count"], 0)
        self.assertEqual(r["input_invoice_count"], 3)

    def test_mixed_output_and_input(self):
        r = self._run(
            sales_row=_row(1000.0, 20),
            purchase_row=_row(400.0, 12),
        )
        self.assertEqual(r["output_vat"], 1000.0)
        self.assertEqual(r["input_vat"], 400.0)
        self.assertEqual(r["net_vat"], 600.0)  # payable
        self.assertEqual(r["output_invoice_count"], 20)
        self.assertEqual(r["input_invoice_count"], 12)

    def test_refundable_when_input_exceeds_output(self):
        r = self._run(
            sales_row=_row(150.0, 4),
            purchase_row=_row(900.0, 18),
        )
        self.assertEqual(r["net_vat"], -750.0)  # refundable

    def test_rounding_to_two_decimals(self):
        # 33.333 + 33.334 = 66.667 → rounded to 66.67
        r = self._run(
            sales_row=_row(33.333, 1),
            purchase_row=_row(33.334, 1),
        )
        self.assertEqual(r["output_vat"], 33.33)
        self.assertEqual(r["input_vat"], 33.33)
        self.assertEqual(r["net_vat"], 0.0)

    def test_zero_vat_with_invoices_still_net_zero(self):
        # Zero-rated exports and exempt supplies → 0 VAT but invoices still counted
        r = self._run(
            sales_row=_row(0.0, 7),
            purchase_row=_row(0.0, 2),
        )
        self.assertEqual(r["net_vat"], 0.0)
        self.assertEqual(r["output_invoice_count"], 7)
        self.assertEqual(r["input_invoice_count"], 2)

    def test_company_passed_through_unchanged(self):
        r = self._run(company="_Different Co", from_date="2026-04-01", to_date="2026-06-30")
        self.assertEqual(r["company"], "_Different Co")
        self.assertEqual(r["from_date"], "2026-04-01")
        self.assertEqual(r["to_date"], "2026-06-30")


class TestComputeAEBVATReturnSqlShape(unittest.TestCase):
    """Verify the SQL we send to frappe.db.sql has the right shape."""

    def test_sql_uses_docstatus_1(self):
        """Only submitted invoices should be aggregated."""
        captured = []
        def fake_sql(sql, values=None, **kw):
            captured.append(sql)
            return [_row(0.0, 0)]
        with patch(
            "frappe_uae.uae.report.ae_vat_201.ae_vat_201.frappe.db.sql",
            side_effect=fake_sql,
        ):
            compute_ae_vat_return("C", "2026-01-01", "2026-12-31")
        self.assertEqual(len(captured), 2)
        for sql in captured:
            self.assertIn("docstatus", sql)  # column reference (with backticks)
            self.assertIn("= 1", sql)  # equality check (note: space around =)
            self.assertIn("BETWEEN", sql)  # date range
            self.assertIn("%(company)s", sql)
            self.assertIn("%(from_date)s", sql)
            self.assertIn("%(to_date)s", sql)

    def test_sql_targets_sales_and_purchase_invoice(self):
        captured = []
        def fake_sql(sql, values=None, **kw):
            captured.append(sql)
            return [_row(0.0, 0)]
        with patch(
            "frappe_uae.uae.report.ae_vat_201.ae_vat_201.frappe.db.sql",
            side_effect=fake_sql,
        ):
            compute_ae_vat_return("C", "2026-01-01", "2026-12-31")
        doctypes_targeted = sorted(
            "Sales Invoice" if "Sales Invoice" in sql else "Purchase Invoice"
            for sql in captured
        )
        self.assertEqual(doctypes_targeted, ["Purchase Invoice", "Sales Invoice"])


if __name__ == "__main__":
    unittest.main()
