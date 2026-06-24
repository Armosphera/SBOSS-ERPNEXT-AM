"""Tests for frappe_localization_core.iban_validator.

Contract C (frozen):
    iban_validator(iban: str, country: str) -> bool

Supports ``country`` in ``{"AM", "AE"}`` only. Raises :class:`ValueError` on
unsupported countries. Performs the standard ISO 13616 / ECBS TR201
mod-97 check-digit validation.

Test vectors:
    AM (Armenia, 31 chars):
        AM96103000112345678901234567890
        — 27-digit BBAN = bank 103 (Ardshinbank) + branch 0001
          + a 20-digit account serial. Check digits computed via the
          ISO 13616 algorithm.
    AE (UAE, 23 chars):
        AE070331234567890123456
        — 19-digit BBAN = bank 033 (Emirates NBD) + a 16-digit
          account serial. Check digits computed via the ISO 13616
          algorithm.
"""
import unittest

from frappe_localization_core.iban_validator import SUPPORTED_COUNTRIES, iban_validator


class TestIbanValidator(unittest.TestCase):
    # --- 1: a known-valid Armenian IBAN must validate ----------------------
    def test_valid_am_iban(self):
        # Realistic Armenian structure: bank 103 (Ardshinbank), branch 0001.
        iban = "AM96103000112345678901234567890"
        self.assertTrue(iban_validator(iban, "AM"))

    # --- 2: a known-valid UAE IBAN must validate ---------------------------
    def test_valid_ae_iban(self):
        iban = "AE070331234567890123456"
        self.assertTrue(iban_validator(iban, "AE"))

    # --- 3: wrong check digits must be rejected ----------------------------
    def test_invalid_iban_wrong_check_digit(self):
        # Take the valid AM IBAN and tamper with one check digit.
        bad = "AM00103000112345678901234567890"  # check was 96, now 00
        self.assertFalse(iban_validator(bad, "AM"))
        # Same for AE.
        bad_ae = "AE990331234567890123456"  # check was 07, now 99
        self.assertFalse(iban_validator(bad_ae, "AE"))

    # --- 4: wrong country-specific length must be rejected -----------------
    def test_wrong_country_length(self):
        # AM IBANs must be exactly 31 chars. 30 must fail.
        too_short = "AM9610300011234567890123456789"  # 30 chars
        self.assertEqual(len(too_short), 30)
        self.assertFalse(iban_validator(too_short, "AM"))
        # AE IBANs must be exactly 23 chars. 24 must fail.
        too_long_ae = "AE0703312345678901234567"  # 24 chars
        self.assertEqual(len(too_long_ae), 24)
        self.assertFalse(iban_validator(too_long_ae, "AE"))

    # --- 5: spaces, dashes, lowercase must not be accepted ----------------
    def test_invalid_characters(self):
        # AM IBAN with spaces (a common human-readable form).
        with_spaces = "AM96 1030 0011 2345 6789 0123 4567 890"
        self.assertFalse(iban_validator(with_spaces, "AM"))
        # AE IBAN with dashes.
        with_dashes = "AE07-0331-2345-6789-0123-456"
        self.assertFalse(iban_validator(with_dashes, "AE"))
        # Lowercase letters in the country code are technically allowed by
        # the algorithm (the function uppercases internally) — but spaces
        # and dashes are NOT part of the canonical IBAN character set
        # and must be rejected.  This test is specifically about non-
        # alphanumeric characters, so we expect False here.
        with_punct = "AE07.0331.2345.6789.0123.456"
        self.assertFalse(iban_validator(with_punct, "AE"))

    # --- 6: unsupported country must raise ValueError ----------------------
    def test_unsupported_country(self):
        # DE is a real IBAN country but out of scope; must raise.
        with self.assertRaises(ValueError):
            iban_validator("DE89370400440532013000", "DE")
        # Junk country code likewise.
        with self.assertRaises(ValueError):
            iban_validator("XX000000000000000000000000", "XX")

    # --- bonus: SUPPORTED_COUNTRIES public constant exists and is correct --
    def test_supported_countries_constant(self):
        self.assertIn("AM", SUPPORTED_COUNTRIES)
        self.assertIn("AE", SUPPORTED_COUNTRIES)
        self.assertEqual(SUPPORTED_COUNTRIES, ("AM", "AE"))


if __name__ == "__main__":
    unittest.main()
