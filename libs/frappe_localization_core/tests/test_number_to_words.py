"""Tests for frappe_localization_core.number_to_words.

Contract C (frozen): number_to_words(value: Decimal, lang: str) -> str
Supports lang in {"en", "hy", "ar", "ru"}; raises ValueError otherwise.
"""
import unittest
from decimal import Decimal

from frappe_localization_core.number_to_words import number_to_words


class TestNumberToWords(unittest.TestCase):
    def test_en_integer(self):
        self.assertEqual(number_to_words(Decimal("0"), "en"), "zero")
        self.assertEqual(number_to_words(Decimal("1"), "en"), "one")
        self.assertEqual(number_to_words(Decimal("42"), "en"), "forty-two")
        self.assertEqual(number_to_words(Decimal("1000000"), "en"), "one million")

    def test_en_fractional(self):
        # "12.34" -> "twelve point three four"  (currencies use the local
        # 2-decimal form elsewhere)
        self.assertEqual(
            number_to_words(Decimal("12.34"), "en"),
            "twelve point three four",
        )

    def test_hy_basic(self):
        # Armenian uses its own script
        result = number_to_words(Decimal("42"), "hy")
        self.assertIn("քառասուն", result)  # "forty" in Armenian
        self.assertIn("երկու", result)        # "two" in Armenian

    def test_ar_basic(self):
        # Arabic-Indic numerals may be used in formal print; this returns words
        result = number_to_words(Decimal("42"), "ar")
        # 42 in Arabic: "اثنان وأربعون"
        self.assertTrue(
            "أربعون" in result or "اربعون" in result,
            f"expected 'أربعون' or 'اربعون' in {result!r}",
        )

    def test_ru_basic(self):
        result = number_to_words(Decimal("42"), "ru")
        self.assertIn("сорок", result)
        self.assertIn("два", result)

    def test_negative(self):
        self.assertEqual(number_to_words(Decimal("-5"), "en"), "minus five")
        self.assertIn("մինուս", number_to_words(Decimal("-5"), "hy"))

    def test_unknown_lang_raises(self):
        with self.assertRaises(ValueError):
            number_to_words(Decimal("1"), "klingon")

    def test_decimal_value(self):
        self.assertEqual(
            number_to_words(Decimal("1234567890.12"), "en"),
            "one billion, two hundred thirty-four million, "
            "five hundred sixty-seven thousand, "
            "eight hundred ninety point one two",
        )


if __name__ == "__main__":
    unittest.main()
