"""Tests for frappe_payroll_engine.calculator.

Contract C (frozen, per W4-T06 spec):
    proration_factor(start_date, end_date, period_start, period_end) -> Decimal
    gross_to_net(gross, tax_rate, social_rate, deductions=None) -> dict
    accrue_leave(annual_entitlement, used, accrual_period='monthly',
                 months_elapsed=12) -> Decimal
    thirteen_month(jan_to_dec_gross, contract_months=12) -> Decimal

All amounts use Decimal to avoid floating-point error in payroll math.
"""
import unittest
from datetime import date
from decimal import Decimal

from frappe_payroll_engine.calculator import (
    accrue_leave,
    gross_to_net,
    proration_factor,
    thirteen_month,
)


class TestProrationFactor(unittest.TestCase):
    def test_proration_full_month(self):
        # Employee present for the full month → factor 1.0
        factor = proration_factor(
            date(2026, 1, 1),
            date(2026, 1, 31),
            date(2026, 1, 1),
            date(2026, 1, 31),
        )
        self.assertEqual(factor, Decimal("1.0"))

    def test_proration_half_month(self):
        # Exactly half a month (15 of 30 days) — April has 30 days
        factor = proration_factor(
            date(2026, 4, 1),
            date(2026, 4, 15),
            date(2026, 4, 1),
            date(2026, 4, 30),
        )
        self.assertEqual(factor, Decimal("0.5"))

    def test_proration_mid_month_join(self):
        # Joined on the 15th of a 30-day month (15, 16, …, 30 = 16 days inclusive)
        factor = proration_factor(
            date(2026, 4, 15),
            date(2026, 4, 30),
            date(2026, 4, 1),
            date(2026, 4, 30),
        )
        self.assertEqual(factor, Decimal("16") / Decimal("30"))

    def test_proration_zero_period(self):
        # Zero-length employment (start > end) inside the period → 0
        factor = proration_factor(
            date(2026, 4, 10),
            date(2026, 4, 5),  # end before start → zero-length window
            date(2026, 4, 1),
            date(2026, 4, 30),
        )
        self.assertEqual(factor, Decimal("0"))

    def test_proration_clamps_to_period(self):
        # Employment starts before the period and ends inside → clamp to period_start
        factor = proration_factor(
            date(2026, 3, 15),  # before period
            date(2026, 4, 10),
            date(2026, 4, 1),
            date(2026, 4, 30),
        )
        # 10 days (April 1..10) out of 30
        self.assertEqual(factor, Decimal("10") / Decimal("30"))


class TestGrossToNet(unittest.TestCase):
    def test_gross_to_net_basic(self):
        result = gross_to_net(Decimal("1000"), Decimal("0.10"), Decimal("0.05"))
        self.assertEqual(result["gross"], Decimal("1000"))
        self.assertEqual(result["tax"], Decimal("100"))
        self.assertEqual(result["social_security"], Decimal("50"))
        self.assertEqual(result["other_deductions"], Decimal("0"))
        self.assertEqual(result["net"], Decimal("850"))

    def test_gross_to_net_with_deductions(self):
        result = gross_to_net(
            Decimal("1000"),
            Decimal("0.10"),
            Decimal("0.05"),
            deductions=Decimal("30"),
        )
        self.assertEqual(result["gross"], Decimal("1000"))
        self.assertEqual(result["tax"], Decimal("100"))
        self.assertEqual(result["social_security"], Decimal("50"))
        self.assertEqual(result["other_deductions"], Decimal("30"))
        # 1000 - 100 - 50 - 30 = 820
        self.assertEqual(result["net"], Decimal("820"))

    def test_gross_to_net_zero_deductions_default(self):
        result = gross_to_net(Decimal("500"), Decimal("0.20"), Decimal("0.10"))
        self.assertEqual(result["other_deductions"], Decimal("0"))
        # 500 - 100 - 50 = 350
        self.assertEqual(result["net"], Decimal("350"))


class TestAccrueLeave(unittest.TestCase):
    def test_accrue_leave_monthly(self):
        # 30 days/year, 1 month elapsed → 2.5 days accrued
        accrued = accrue_leave(
            annual_entitlement=Decimal("30"),
            used=Decimal("0"),
            accrual_period="monthly",
            months_elapsed=1,
        )
        self.assertEqual(accrued, Decimal("2.5"))

    def test_accrue_leave_pro_rated(self):
        # 15 days/year, half a year (6 months) → 7.5 days accrued
        accrued = accrue_leave(
            annual_entitlement=Decimal("15"),
            used=Decimal("0"),
            accrual_period="monthly",
            months_elapsed=6,
        )
        self.assertEqual(accrued, Decimal("7.5"))

    def test_accrue_leave_subtracts_used(self):
        # 30 days/year, 6 months elapsed → 15 accrued, 5 used → 10 remaining
        remaining = accrue_leave(
            annual_entitlement=Decimal("30"),
            used=Decimal("5"),
            accrual_period="monthly",
            months_elapsed=6,
        )
        self.assertEqual(remaining, Decimal("10"))


class TestThirteenMonth(unittest.TestCase):
    def test_thirteen_month_full_year(self):
        # 12000 gross over a full year → 1000 bonus (1/12 of annual)
        bonus = thirteen_month(jan_to_dec_gross=Decimal("12000"), contract_months=12)
        self.assertEqual(bonus, Decimal("1000"))

    def test_thirteen_month_partial_year(self):
        # 6 months of work, earned 6000 total → (6000/12) * (6/12) = 250 bonus
        # (13th-month pay is 1/12 of annual gross, pro-rated by months worked).
        bonus = thirteen_month(jan_to_dec_gross=Decimal("6000"), contract_months=6)
        self.assertEqual(bonus, Decimal("250"))


if __name__ == "__main__":
    unittest.main()