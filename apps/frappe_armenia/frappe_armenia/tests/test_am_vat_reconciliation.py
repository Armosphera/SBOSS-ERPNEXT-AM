"""Tests for Armenian VAT Reconciliation report (W1-T16).

The reconciliation report groups OUTPUT VAT (from Sales Invoices) and
INPUT VAT (from Purchase Invoices) into monthly buckets within a date range,
returning net VAT per month + totals. Pure helper is unit-tested by mocking
the SQL aggregation so we don't depend on full invoice fixtures.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe

from frappe_armenia.armenia.report.am_vat_reconciliation.am_vat_reconciliation import (
    _aggregate_vat_for_period,
    compute_vat_reconciliation,
)


_TEST_COMPANY = "_Test AM Co W1T16"
_TEST_FROM = "2026-03-01"
_TEST_TO = "2026-05-31"


class TestComputeVATReconciliationHelpers(unittest.TestCase):
    """Pure-function tests that don't need fixtures."""

    def test_compute_vat_reconciliation_is_importable(self):
        self.assertTrue(callable(compute_vat_reconciliation))

    def test_aggregate_vat_for_period_is_importable(self):
        self.assertTrue(callable(_aggregate_vat_for_period))

    @patch("frappe.db.sql")
    def test_aggregate_vat_for_period_returns_tuple(self, mock_sql):
        mock_sql.return_value = [{"vat_sum": 500.0, "inv_count": 3}]
        vat, count = _aggregate_vat_for_period(
            "Sales Invoice", "X", "2026-03-01", "2026-03-31"
        )
        self.assertAlmostEqual(vat, 500.0)
        self.assertEqual(count, 3)

    @patch("frappe.db.sql")
    def test_compute_vat_reconciliation_with_no_data(self, mock_sql):
        # No invoices in the period -> zero totals, but ALL months in the
        # range are still emitted as zero-filled buckets so the timeline is
        # visible (useful for reconciliation against the GL).
        mock_sql.return_value = [{"vat_sum": 0, "inv_count": 0}]
        result = compute_vat_reconciliation(
            company=_TEST_COMPANY,
            from_date=_TEST_FROM,
            to_date=_TEST_TO,
        )
        self.assertEqual(result["total_output_vat"], 0.0)
        self.assertEqual(result["total_input_vat"], 0.0)
        self.assertEqual(result["total_net_vat"], 0.0)
        self.assertEqual(result["total_output_count"], 0)
        self.assertEqual(result["total_input_count"], 0)
        # Mar + Apr + May = 3 months in the Mar-May range
        self.assertEqual(len(result["buckets"]), 3)
        for b in result["buckets"]:
            self.assertEqual(b["output_vat"], 0.0)
            self.assertEqual(b["input_vat"], 0.0)
            self.assertEqual(b["net_vat"], 0.0)


class TestComputeVATReconciliationAggregation(unittest.TestCase):
    """Aggregation logic: per-month buckets + totals."""

    @patch("frappe.db.sql")
    def test_three_month_period_with_data(self, mock_sql):
        # 3 months of data, each with different VAT and counts.
        # Side effects are sequential SQL calls in this order:
        #   1. Mar Sales (output)
        #   2. Mar Purchase (input)
        #   3. Apr Sales (output)
        #   4. Apr Purchase (input)
        #   5. May Sales (output)
        #   6. May Purchase (input)
        mock_sql.side_effect = [
            [{"vat_sum": 600.0, "inv_count": 2}],   # Mar Sales
            [{"vat_sum": 100.0, "inv_count": 1}],   # Mar Purchase
            [{"vat_sum": 1200.0, "inv_count": 3}],  # Apr Sales
            [{"vat_sum": 400.0, "inv_count": 2}],   # Apr Purchase
            [{"vat_sum": 800.0, "inv_count": 2}],   # May Sales
            [{"vat_sum": 0.0, "inv_count": 0}],     # May Purchase
        ]
        result = compute_vat_reconciliation(
            company=_TEST_COMPANY,
            from_date="2026-03-01",
            to_date="2026-05-31",
        )

        # 3 buckets expected
        self.assertEqual(len(result["buckets"]), 3)

        # March: output 600, input 100, net 500
        mar = result["buckets"][0]
        self.assertEqual(mar["month"], "2026-03-01")
        self.assertAlmostEqual(mar["output_vat"], 600.0, places=2)
        self.assertAlmostEqual(mar["input_vat"], 100.0, places=2)
        self.assertAlmostEqual(mar["net_vat"], 500.0, places=2)
        self.assertEqual(mar["output_count"], 2)
        self.assertEqual(mar["input_count"], 1)

        # April: output 1200, input 400, net 800
        apr = result["buckets"][1]
        self.assertEqual(apr["month"], "2026-04-01")
        self.assertAlmostEqual(apr["net_vat"], 800.0, places=2)

        # May: output 800, input 0, net 800
        may = result["buckets"][2]
        self.assertEqual(may["month"], "2026-05-01")
        self.assertAlmostEqual(may["net_vat"], 800.0, places=2)
        self.assertEqual(may["input_count"], 0)

        # Totals
        self.assertAlmostEqual(result["total_output_vat"], 2600.0, places=2)
        self.assertAlmostEqual(result["total_input_vat"], 500.0, places=2)
        self.assertAlmostEqual(result["total_net_vat"], 2100.0, places=2)
        self.assertEqual(result["total_output_count"], 7)
        self.assertEqual(result["total_input_count"], 3)

    @patch("frappe.db.sql")
    def test_negative_net_vat_when_input_exceeds_output(self, mock_sql):
        # Refund scenario: input > output in all months
        mock_sql.side_effect = [
            [{"vat_sum": 50.0, "inv_count": 1}],    # Mar Sales
            [{"vat_sum": 200.0, "inv_count": 2}],   # Mar Purchase
            [{"vat_sum": 100.0, "inv_count": 1}],   # Apr Sales
            [{"vat_sum": 300.0, "inv_count": 3}],   # Apr Purchase
        ]
        result = compute_vat_reconciliation(
            company=_TEST_COMPANY,
            from_date="2026-03-01",
            to_date="2026-04-30",
        )

        # Totals: 150 out, 500 in, -350 net
        self.assertAlmostEqual(result["total_output_vat"], 150.0, places=2)
        self.assertAlmostEqual(result["total_input_vat"], 500.0, places=2)
        self.assertAlmostEqual(result["total_net_vat"], -350.0, places=2)

    @patch("frappe.db.sql")
    def test_monthly_bucket_labels_are_first_of_month(self, mock_sql):
        # Verify the bucket labels are first-of-month dates (YYYY-MM-01).
        mock_sql.side_effect = [
            [{"vat_sum": 100.0, "inv_count": 1}],   # Mar
            [{"vat_sum": 0.0, "inv_count": 0}],
            [{"vat_sum": 200.0, "inv_count": 2}],   # Apr
            [{"vat_sum": 0.0, "inv_count": 0}],
        ]
        result = compute_vat_reconciliation(
            company=_TEST_COMPANY,
            from_date="2026-03-15",  # mid-month start
            to_date="2026-04-15",
        )
        self.assertEqual(result["buckets"][0]["month"], "2026-03-01")
        self.assertEqual(result["buckets"][1]["month"], "2026-04-01")

    @patch("frappe.db.sql")
    def test_sql_filter_uses_company_and_period(self, mock_sql):
        """Each SQL call must filter by company + posting_date BETWEEN bounds."""
        mock_sql.return_value = [{"vat_sum": 0, "inv_count": 0}]
        compute_vat_reconciliation(
            company="ACME LLC",
            from_date="2026-06-01",
            to_date="2026-06-30",
        )
        # 2 months x 2 doctypes = 4 calls minimum
        self.assertGreaterEqual(mock_sql.call_count, 2)
        for call in mock_sql.call_args_list:
            args, kwargs = call
            self.assertIn("values", kwargs)
            self.assertEqual(kwargs["values"]["company"], "ACME LLC")
            self.assertEqual(kwargs["values"]["from_date"], "2026-06-01")
            self.assertEqual(kwargs["values"]["to_date"], "2026-06-30")

    @patch("frappe.db.sql")
    def test_only_docstatus_1_in_sql(self, mock_sql):
        """Only submitted invoices should be counted (docstatus=1)."""
        mock_sql.return_value = [{"vat_sum": 0, "inv_count": 0}]
        compute_vat_reconciliation(
            company=_TEST_COMPANY,
            from_date="2026-03-01",
            to_date="2026-03-31",
        )
        # Inspect first SQL string
        first_sql = mock_sql.call_args_list[0][0][0]
        self.assertIn("docstatus", first_sql)
        self.assertIn("= 1", first_sql)

    @patch("frappe.db.sql")
    def test_filters_by_posting_date_in_sql(self, mock_sql):
        mock_sql.return_value = [{"vat_sum": 0, "inv_count": 0}]
        compute_vat_reconciliation(
            company=_TEST_COMPANY,
            from_date="2026-03-01",
            to_date="2026-03-31",
        )
        first_sql = mock_sql.call_args_list[0][0][0]
        self.assertIn("posting_date", first_sql)
        self.assertIn("BETWEEN", first_sql.upper())