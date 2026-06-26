"""Tests for Armenian VAT Return report (W1-T15).

The report aggregates OUTPUT VAT (from Sales Invoices) and INPUT VAT
(from Purchase Invoices) within a period, and computes the net VAT
payable/refundable. We test the pure helper :func:`compute_vat_return`
and (by mocking the SQL aggregation) its date-window filter logic.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_armenia.custom_fields import ensure_custom_fields
from frappe_armenia.report.am_vat_return.am_vat_return import (
    _aggregate_vat,
    compute_vat_return,
)


_TEST_COMPANY = "_Test AM Co W1T15"
_TEST_FROM = "2026-03-01"
_TEST_TO = "2026-03-31"


class TestComputeVATReturnHelpers(unittest.TestCase):
    """Pure-function tests that don't need fixtures."""

    def test_compute_vat_return_is_importable(self):
        # Smoke: function exists and is callable.
        self.assertTrue(callable(compute_vat_return))

    def test_aggregate_vat_is_importable(self):
        self.assertTrue(callable(_aggregate_vat))

    @patch("frappe.db.sql")
    def test_aggregate_vat_returns_tuple_of_floats_and_int(self, mock_sql):
        mock_sql.return_value = [{"vat_sum": 1234.56, "inv_count": 7}]
        vat, count = _aggregate_vat("Sales Invoice", "X", "2026-01-01", "2026-01-31")
        self.assertAlmostEqual(vat, 1234.56)
        self.assertEqual(count, 7)

    @patch("frappe.db.sql")
    def test_aggregate_vat_handles_zero_rows(self, mock_sql):
        # COALESCE(SUM(...), 0) yields a row with 0 / 0.
        mock_sql.return_value = [{"vat_sum": 0, "inv_count": 0}]
        vat, count = _aggregate_vat("Sales Invoice", "X", "2026-01-01", "2026-01-31")
        self.assertEqual(vat, 0.0)
        self.assertEqual(count, 0)

    @patch("frappe.db.sql")
    def test_compute_vat_return_with_no_invoices_returns_zero(self, mock_sql):
        mock_sql.return_value = [{"vat_sum": 0, "inv_count": 0}]
        result = compute_vat_return(
            company="_No Such Co_",
            from_date=_TEST_FROM,
            to_date=_TEST_TO,
        )
        self.assertEqual(result["output_vat"], 0.0)
        self.assertEqual(result["input_vat"], 0.0)
        self.assertEqual(result["net_vat"], 0.0)
        self.assertEqual(result["output_invoice_count"], 0)
        self.assertEqual(result["input_invoice_count"], 0)


class TestComputeVATReturnAggregation(unittest.TestCase):
    """Aggregation logic: input/output/net math."""

    @patch("frappe.db.sql")
    def test_aggregates_output_and_input_vat_within_period(self, mock_sql):
        # Sales Invoice: 600.0 VAT, 2 invoices. Purchase Invoice: 100.0 VAT, 1 invoice.
        mock_sql.side_effect = [
            [{"vat_sum": 600.0, "inv_count": 2}],   # Sales Invoice call
            [{"vat_sum": 100.0, "inv_count": 1}],   # Purchase Invoice call
        ]
        result = compute_vat_return(
            company=_TEST_COMPANY,
            from_date=_TEST_FROM,
            to_date=_TEST_TO,
        )

        self.assertAlmostEqual(result["output_vat"], 600.0, places=2)
        self.assertAlmostEqual(result["input_vat"], 100.0, places=2)
        self.assertAlmostEqual(result["net_vat"], 500.0, places=2)
        self.assertEqual(result["output_invoice_count"], 2)
        self.assertEqual(result["input_invoice_count"], 1)

    @patch("frappe.db.sql")
    def test_net_vat_negative_when_input_exceeds_output(self, mock_sql):
        # Refund scenario: input > output
        mock_sql.side_effect = [
            [{"vat_sum": 50.0, "inv_count": 1}],    # Sales Invoice
            [{"vat_sum": 300.0, "inv_count": 4}],   # Purchase Invoice
        ]
        result = compute_vat_return(
            company=_TEST_COMPANY,
            from_date=_TEST_FROM,
            to_date=_TEST_TO,
        )

        self.assertAlmostEqual(result["net_vat"], -250.0, places=2)

    @patch("frappe.db.sql")
    def test_period_bounds_passed_to_sql(self, mock_sql):
        """The function must filter by posting_date BETWEEN from AND to."""
        mock_sql.return_value = [{"vat_sum": 0, "inv_count": 0}]
        compute_vat_return(
            company=_TEST_COMPANY,
            from_date="2026-05-01",
            to_date="2026-05-31",
        )
        # Two SQL calls (Sales + Purchase), both should carry the bounds.
        self.assertEqual(mock_sql.call_count, 2)
        for call in mock_sql.call_args_list:
            args, kwargs = call
            self.assertIn("values", kwargs)
            self.assertEqual(kwargs["values"]["company"], _TEST_COMPANY)
            self.assertEqual(kwargs["values"]["from_date"], "2026-05-01")
            self.assertEqual(kwargs["values"]["to_date"], "2026-05-31")

    @patch("frappe.db.sql")
    def test_docstatus_one_filter_in_sql(self, mock_sql):
        """Only submitted invoices (docstatus=1) should be counted."""
        mock_sql.return_value = [{"vat_sum": 0, "inv_count": 0}]
        compute_vat_return(
            company=_TEST_COMPANY,
            from_date=_TEST_FROM,
            to_date=_TEST_TO,
        )
        # Inspect the SQL string passed to frappe.db.sql.
        first_call_sql = mock_sql.call_args_list[0][0][0]
        self.assertIn("docstatus", first_call_sql)
        self.assertIn("= 1", first_call_sql)