"""Tests for mt940_parser (W4-T04)."""
from decimal import Decimal
from pathlib import Path

import pytest

from frappe_localization_core.mt940_parser import parse_mt940


REAL_PATH = Path(__file__).parent / "real_world_samples"


def test_parse_minimal_mt940():
    """Hand-built minimal MT940 with one entry."""
    content = (
        ":20:STATEMENT-001\n"
        ":25:DE89370400440532013000\n"
        ":28C:1/1\n"
        ":60F:C230101EUR1000,00\n"
        ":61:2301010102D123,45NTRFNONREF//ABC123\n"
        "Payment for invoice 42\n"
        ":86:Supplier ABC GmbH, Berlin\n"
        ":62F:C230102EUR876,55\n"
        "-\n"
    )
    statements = parse_mt940(content)
    assert len(statements) == 1
    s = statements[0]
    assert s["reference"] == "STATEMENT-001"
    assert s["account"] == "DE89370400440532013000"
    assert s["statement_number"] == "1/1"
    assert s["opening_balance"]["amount"] == Decimal("1000.00")
    assert s["opening_balance"]["currency"] == "EUR"
    assert s["opening_balance"]["date"] == "2023-01-01"
    assert s["closing_balance"]["amount"] == Decimal("876.55")
    assert len(s["entries"]) == 1
    e = s["entries"][0]
    assert e["amount"] == Decimal("-123.45")  # D = debit = negative
    assert e["direction"] == "D"
    assert e["value_date"] == "2023-01-01"
    assert e["entry_date"] == "2023-01-02"
    assert e["info"] == "Supplier ABC GmbH, Berlin"
    # :61:2301010102D123,45NTRFNONREF//ABC123
    # N = transaction type id, TRF = 3-char SWIFT code, NONREF = customer
    # reference, //ABC123 = account-servicer reference.
    assert e["ref"] == "NONREF"
    assert e["type_code"] == "TRF"
    assert e["ref_acc_owner"] == "ABC"
    assert e["ref_acc_number"] == "123"


def test_parse_opening_balance_signed():
    """C vs D balances have opposite signs."""
    content_credit = ":20:X\n:25:A\n:28C:1/1\n:60F:C230101USD500,00\n:62F:C230101USD500,00\n-\n"
    content_debit = ":20:Y\n:25:B\n:28C:1/1\n:60F:D230101USD500,00\n:62F:D230101USD500,00\n-\n"
    s_c = parse_mt940(content_credit)[0]
    s_d = parse_mt940(content_debit)[0]
    assert s_c["opening_balance"]["amount"] == Decimal("500.00")
    assert s_d["opening_balance"]["amount"] == Decimal("-500.00")
    assert s_c["closing_balance"]["amount"] == Decimal("500.00")
    assert s_d["closing_balance"]["amount"] == Decimal("-500.00")


def test_parse_closing_balance_signed():
    """Same as opening test, but specifically for :62F: tag."""
    content = ":20:X\n:25:A\n:28C:1/1\n:60F:C230101USD0,00\n:62F:D230101USD-150,75\n-\n"
    s = parse_mt940(content)[0]
    assert s["closing_balance"]["amount"] == Decimal("-150.75")


def test_parse_entry_direction():
    """D entries are negative, C entries are positive."""
    content_d = ":20:X\n:25:A\n:28C:1/1\n:60F:C230101USD0,00\n:61:2301010102D100,00NTRFREF//X\n:62F:C230101USD-100,00\n-\n"
    content_c = ":20:Y\n:25:B\n:28C:1/1\n:60F:C230101USD0,00\n:61:2301010102C100,00NTRFREF//Y\n:62F:C230101USD100,00\n-\n"
    s_d = parse_mt940(content_d)[0]
    s_c = parse_mt940(content_c)[0]
    assert s_d["entries"][0]["amount"] == Decimal("-100.00")
    assert s_c["entries"][0]["amount"] == Decimal("100.00")


def test_parse_multiple_statements_per_file():
    """One file can contain multiple :20: blocks."""
    content = (
        ":20:FIRST\n:25:A\n:28C:1/1\n:60F:C230101EUR0,00\n:62F:C230101EUR100,00\n-\n"
        ":20:SECOND\n:25:B\n:28C:1/1\n:60F:C230102EUR100,00\n:62F:C230102EUR250,00\n-\n"
    )
    statements = parse_mt940(content)
    assert len(statements) == 2
    assert statements[0]["reference"] == "FIRST"
    assert statements[1]["reference"] == "SECOND"
    assert statements[0]["closing_balance"]["amount"] == Decimal("100.00")
    assert statements[1]["opening_balance"]["amount"] == Decimal("100.00")


def test_euro_decimal_comma_format():
    """European comma-decimal format with thousands separator dots."""
    content = ":20:X\n:25:A\n:28C:1/1\n:60F:C230101EUR1.234.567,89\n:62F:C230101EUR1.234.789,01\n-\n"
    s = parse_mt940(content)[0]
    assert s["opening_balance"]["amount"] == Decimal("1234567.89")
    assert s["closing_balance"]["amount"] == Decimal("1234789.01")


def test_no_comma_amount_treated_as_implicit_decimal():
    """When amount is just digits with no separator, treat as cents implicit."""
    # E.g. "12345" -> 123.45 (last 2 digits = cents).
    content = ":20:X\n:25:A\n:28C:1/1\n:60F:C230101EUR0,00\n:61:2301010102D12345NTRFREF//Z\n:62F:C230101USD-12345\n-\n"
    s = parse_mt940(content)[0]
    # The entry amount has no comma; should be -123.45
    assert s["entries"][0]["amount"] == Decimal("-123.45")


def test_date_y2k_boundary():
    """YY < 50 is 20YY, YY >= 50 is 19YY."""
    content_2024 = ":20:X\n:25:A\n:28C:1/1\n:60F:C241231EUR0,00\n:62F:C241231EUR0,00\n-\n"
    content_1999 = ":20:Y\n:25:B\n:28C:1/1\n:60F:C991231EUR0,00\n:62F:C991231EUR0,00\n-\n"
    assert parse_mt940(content_2024)[0]["opening_balance"]["date"] == "2024-12-31"
    assert parse_mt940(content_1999)[0]["opening_balance"]["date"] == "1999-12-31"
