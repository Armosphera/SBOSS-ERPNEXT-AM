"""Tests for ``frappe_localization_core.currency_format``.

Contract C (frozen public signature):
    format_currency(value, currency, locale='en') -> str
    parse_currency(formatted: str, currency: str) -> Decimal

Supported currency/locale matrix (minimum required for W4-T05):

| Currency | Locale | Symbol | Symbol position | Decimals | Thou. sep | Dec. sep | Grouping |
|----------|--------|--------|-----------------|----------|-----------|----------|----------|
| AMD      | en     | ֏ (U+058F) | after          | 0        | space     | .        | 3        |
| AMD      | hy     | ֏ (U+058F) | after          | 0        | space     | .        | 3        |
| AED      | en     | د.إ        | after          | 2        | comma     | .        | 3        |
| AED      | ar     | د.إ        | after          | 2        | comma     | . (ASCII)| 3        |
| EUR      | en     | € (U+20AC) | before         | 2        | comma     | .        | 3        |
| EUR      | ar     | € (U+20AC) | after          | 2        | comma     | .        | 3        |
| USD      | en     | $         | before         | 2        | comma     | .        | 3        |
| USD      | ru     | $         | before         | 2        | space     | ,        | 3        |

Reference: actual real-world formatting used in ERPNext for AM / AE and
the standard ISO 4217 conventions for the symbol and grouping rules.
The locale argument only matters for the symbol position of EUR
(Arabic places it after the number, Latin scripts place it before) and
for the Russian USD formatting (space-separator thousands, comma
decimal).
"""
from __future__ import annotations

import unittest
from decimal import Decimal

from frappe_localization_core.currency_format import (
    SUPPORTED_CURRENCIES,
    format_currency,
    parse_currency,
)


class TestFormatCurrency(unittest.TestCase):
    # --- 1: Armenian dram (AMD) ---------------------------------------------
    def test_amd_format(self):
        # 1,234,567 -> "1 234 567 ֏" (space thou. sep, no decimals, symbol after)
        self.assertEqual(format_currency(1234567, "AMD"), "1 234 567 \u058f")

    def test_amd_with_decimal_truncates(self):
        # AMD has 0 fractional digits — a Decimal with fractional part must round.
        self.assertEqual(format_currency(Decimal("1234567.89"), "AMD"), "1 234 568 \u058f")

    def test_amd_small_value(self):
        # No thousands separator needed.
        self.assertEqual(format_currency(999, "AMD"), "999 \u058f")

    def test_amd_zero(self):
        self.assertEqual(format_currency(0, "AMD"), "0 \u058f")

    # --- 2: UAE dirham (AED) ------------------------------------------------
    def test_aed_format(self):
        # 1234.56 -> "1,234.56 د.إ" (comma thou. sep, two decimals, symbol after)
        self.assertEqual(format_currency(1234.56, "AED"), "1,234.56 \u062f.\u0625")

    def test_aed_thousands(self):
        self.assertEqual(
            format_currency(Decimal("1234567.5"), "AED"),
            "1,234,567.50 \u062f.\u0625",
        )

    def test_aed_accepts_string_input(self):
        # Strings must be parsed as Decimal so we don't silently lose precision.
        self.assertEqual(format_currency("1234.56", "AED"), "1,234.56 \u062f.\u0625")

    # --- 3: EUR in English --------------------------------------------------
    def test_eur_en(self):
        # 1234.56 -> "€1,234.56" (symbol before for Latin scripts)
        self.assertEqual(format_currency(1234.56, "EUR", locale="en"), "\u20ac1,234.56")

    # --- 4: EUR in Arabic ---------------------------------------------------
    def test_eur_ar(self):
        # 1234.56 -> "1,234.56 €" (symbol after for Arabic)
        self.assertEqual(format_currency(1234.56, "EUR", locale="ar"), "1,234.56 \u20ac")

    # --- 5: USD -------------------------------------------------------------
    def test_usd_format(self):
        # 1234567.89 -> "$1,234,567.89"
        self.assertEqual(
            format_currency(1234567.89, "USD"),
            "$1,234,567.89",
        )

    def test_usd_small(self):
        self.assertEqual(format_currency(0.5, "USD"), "$0.50")

    def test_usd_negative(self):
        # Negative values: keep the minus sign tight against the number.
        self.assertEqual(format_currency(-1234.56, "USD"), "-$1,234.56")

    def test_usd_russian_locale(self):
        # Russian uses a space as a thousands separator and a comma as the
        # decimal separator for USD. Symbol stays before.
        self.assertEqual(format_currency(1234.56, "USD", locale="ru"), "$1 234,56")


class TestParseCurrency(unittest.TestCase):
    # --- 6: round-trip AMD --------------------------------------------------
    def test_round_trip_amd(self):
        formatted = format_currency(1234567, "AMD")
        self.assertEqual(parse_currency(formatted, "AMD"), Decimal("1234567"))

    # --- 7: round-trip AED --------------------------------------------------
    def test_round_trip_aed(self):
        formatted = format_currency(1234.56, "AED")
        self.assertEqual(parse_currency(formatted, "AED"), Decimal("1234.56"))

    # --- 8: parse with currency symbol ------------------------------------
    def test_parse_with_currency_symbol(self):
        # Parsing must tolerate a currency symbol in any of the supported
        # positions (before or after).
        self.assertEqual(parse_currency("$1,234,567.89", "USD"), Decimal("1234567.89"))
        self.assertEqual(parse_currency("1,234.56 \u20ac", "EUR"), Decimal("1234.56"))
        self.assertEqual(parse_currency("\u20ac1,234.56", "EUR"), Decimal("1234.56"))
        self.assertEqual(parse_currency("1 234 567 \u058f", "AMD"), Decimal("1234567"))
        self.assertEqual(parse_currency("1,234.56 \u062f.\u0625", "AED"), Decimal("1234.56"))

    def test_parse_usd_negative(self):
        self.assertEqual(parse_currency("-$1,234.56", "USD"), Decimal("-1234.56"))

    def test_parse_eur_russian_locale(self):
        # Russian thousands separator is a space; decimal separator is a comma.
        self.assertEqual(parse_currency("$1 234,56", "USD"), Decimal("1234.56"))


class TestSupportedCurrencies(unittest.TestCase):
    def test_supported_currencies_constant(self):
        self.assertIn("AMD", SUPPORTED_CURRENCIES)
        self.assertIn("AED", SUPPORTED_CURRENCIES)
        self.assertIn("EUR", SUPPORTED_CURRENCIES)
        self.assertIn("USD", SUPPORTED_CURRENCIES)


if __name__ == "__main__":
    unittest.main()