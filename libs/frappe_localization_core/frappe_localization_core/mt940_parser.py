"""MT940 SWIFT statement parser.

Contract C (frozen): parse_mt940(content: str) -> list[dict]

MT940 is the SWIFT Customer Statement Message. Returns one dict per :20:
statement block, each shaped:
    {
        "reference":         str,           # :20:
        "account":           str,           # :25:
        "statement_number":  str,           # :28C:
        "opening_balance":    {amount Decimal, currency, date},
        "closing_balance":    {amount Decimal, currency, date},
        "entries": [
            {
                "value_date":       str,    # YYYY-MM-DD
                "entry_date":       str,    # YYYY-MM-DD or empty
                "amount":           Decimal, # negative for D
                "direction":        "C" | "D",
                "currency":         str,    # from the enclosing balance tag
                "ref":              str,
                "info":             str,    # from :86: tag
                "type_code":        str,    # 3-char SWIFT code (e.g. NTR, TRF)
                "ref_acc_owner":    str,
                "ref_acc_number":   str,
                "transaction_type": str,
            }
        ]
    }

Format summary (SWIFT MT940 v8+):
    :20:    statement reference (4!c, 16x)
    :25:    account identification (35x)
    :28C:   statement number (5n/5n or 5n[5n])
    :60F:   opening balance (D|C 6!n 3!a 15d) — F = first, M = intermediate
    :61:    statement line:
            YYMMDD [MMDD] [D|C] [RC|RD] amount [N] type_code ref [//supplement]
    :86:    info to account owner
    :62F:   closing balance (D|C 6!n 3!a 15d) — F = first, M = intermediate

Amount format:
    comma is decimal separator (e.g. "1.234,56" = 1234.56 EUR).
    Some banks omit decimals (e.g. "12345" -> 123.45 — implicit cents).
    Some banks put sign as trailing "-" or "{".
"""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Any


_TAG_RE = re.compile(r"^:(\d{2,3}[A-Z]?):")
_DATE_RE = re.compile(r"^(\d{6})?(\d{4})?$")  # captures YYMMDD and optional MMDD


def _to_decimal(amount_str: str) -> Decimal:
    """Parse a SWIFT amount string.

    Examples:
        "1.234,56"     -> 1234.56
        "1234,56"      -> 1234.56
        "0,00"         -> 0
        "12345"        -> 123.45   (implicit cents)
        "-1234,56"     -> -1234.56
        "1234,56-"     -> -1234.56
        "1234,56{"     -> -1234.56
        "USD-1234,56"  -> -1234.56 (sign embedded in the middle)
    """
    s = amount_str.strip()
    sign = 1
    # Remove currency prefix letters if present (USD, EUR, AMD, AED, etc.)
    while s and s[0].isalpha():
        s = s[1:]
    if s.startswith("-"):
        sign = -1
        s = s[1:]
    elif s.endswith(("-", "{")):
        sign = -1
        s = s[:-1]
    # Some banks put the sign mid-string after the currency: "USD-1234,56"
    # We already stripped the currency prefix, so if a leading "-" remains
    # after stripping letters, handle it.
    if s.startswith("-"):
        sign *= -1
        s = s[1:]
    if "," in s:
        # Comma is decimal separator. Dot is thousands.
        s = s.replace(".", "").replace(",", ".")
    elif "." not in s and len(s) >= 3 and s.isdigit():
        # No separator, all digits — implicit decimal point.
        s = s[:-2] + "." + s[-2:]
    return Decimal(s or "0") * sign


def _parse_yymmdd(date_str: str) -> str:
    """YYMMDD -> YYYY-MM-DD (YY < 50 -> 20YY, else 19YY)."""
    if len(date_str) != 6 or not date_str.isdigit():
        return date_str
    yy, mm, dd = int(date_str[:2]), int(date_str[2:4]), int(date_str[4:6])
    year = 2000 + yy if yy < 50 else 1900 + yy
    try:
        return datetime(year, mm, dd).strftime("%Y-%m-%d")
    except ValueError:
        return date_str


def _parse_balance_line(line: str) -> dict[str, Any]:
    """Parse a :60F: or :62F: line.

    Format: [D|C]YYMMDD[AUD][amount]
    Examples:
        "C230101EUR1000,00"     -> +1000.00 EUR
        "D230615USD-150,75"     -> -150.75 USD (sign in the middle)
        "D230101USD150,75"      -> -150.75 USD (sign from D only)
    """
    if line.startswith(":"):
        line = line.split(":", 2)[-1].strip()
    if not line or line[0] not in "DC":
        raise ValueError(f"balance must start with D or C: {line!r}")
    direction = line[0]
    date = _parse_yymmdd(line[1:7])
    currency = line[7:10]
    amount_str = line[10:]
    # Peek for sign: if the amount_str already starts with "-",
    # the value is already negative. Otherwise, the D/C direction decides.
    if amount_str.lstrip().startswith("-"):
        amount = _to_decimal(amount_str)
    else:
        amount = _to_decimal(amount_str)
        if direction == "D":
            amount = -amount
    return {"amount": amount, "currency": currency, "date": date}


def _parse_entry_line(line: str, currency: str = "") -> dict[str, Any]:
    """Parse a :61: line.

    Format per SWIFT spec:
        YYMMDD      value date (mandatory)
        [MMDD]      entry/booking date (optional)
        [1!a]       funds code (often N in practice)
        [D|C|RC|RD] debit/credit marker (mandatory)
        [15d]       amount with comma decimal separator
        [N]         transaction type id
        [3!c]       transaction type code
        [16x]       customer reference
        [//[32x]]   account servicer reference
        [supplement] optional data
    """
    if line.startswith(":"):
        line = line.split(":", 2)[-1].strip()
    pos = 0

    # Value date: 6 digits
    value_date = ""
    value_year = 2000
    if pos + 6 <= len(line) and line[pos:pos + 6].isdigit():
        value_date = _parse_yymmdd(line[pos:pos + 6])
        value_year = 2000 + int(line[pos:pos + 2]) if int(line[pos:pos + 2]) < 50 else 1900 + int(line[pos:pos + 2])
        pos += 6

    # Entry date (optional): next 4 digits if they're all digits and represent a valid month
    entry_date = ""
    if pos + 4 <= len(line) and line[pos:pos + 4].isdigit():
        candidate = line[pos:pos + 4]
        mm, dd = int(candidate[:2]), int(candidate[2:4])
        if 1 <= mm <= 12 and 1 <= dd <= 31:
            entry_date = datetime(value_year, mm, dd).strftime("%Y-%m-%d")
            pos += 4

    # Funds code (optional, 1 char, often N or empty)
    if pos < len(line) and line[pos].isalpha() and line[pos] not in "DC":
        pos += 1

    # Debit/Credit marker (mandatory): D, C, RC, or RD
    direction = "C"
    # First, check for 2-char RC/RD
    if pos + 1 <= len(line) and line[pos:pos + 2] in ("RC", "RD"):
        direction = "D" if line[pos:pos + 2] == "RD" else "C"
        pos += 2
    elif pos < len(line) and line[pos] in "DC":
        direction = "C" if line[pos] == "C" else "D"
        pos += 1

    # Amount: scan up to 15 chars consisting of digits, comma, dot
    amount_start = pos
    while pos < len(line) and pos < amount_start + 15:
        c = line[pos]
        if c.isdigit() or c in ",.":
            pos += 1
        else:
            break
    amount_str = line[amount_start:pos]
    amount = _to_decimal(amount_str)
    if direction == "D":
        amount = -amount

    # Transaction type id: N (single digit, optional)
    if pos < len(line) and line[pos] == "N":
        pos += 1

    # Transaction type code (3 chars, optional but typical)
    type_code = ""
    if pos + 3 <= len(line):
        # If next chars look like a SWIFT code (letters/digits, no spaces)
        candidate = line[pos:pos + 3]
        if candidate.isalnum():
            type_code = candidate
            pos += 3

    # Reference: until // or end
    ref = ""
    if "//" in line[pos:]:
        ref_part, after = line[pos:].split("//", 1)
        ref = ref_part
        # After //: optional ref_acc_owner (4!a) ref_acc_number (1!a/28x)
        rest = after.strip()
        ref_acc_owner = ""
        ref_acc_number = ""
        # Pattern: owner is 4!a (exactly 4 alphabetic chars) + account_number
        # Some banks emit ABC123 with only ABC as owner + 123 as account
        if len(rest) >= 4 and rest[:4].isalpha():
            ref_acc_owner = rest[:4]
            ref_acc_number = rest[4:].strip()
        elif len(rest) >= 3 and rest[:3].isalpha():
            ref_acc_owner = rest[:3]
            ref_acc_number = rest[3:].strip()
        elif rest:
            ref_acc_number = rest.strip()
        pos = len(line)
    else:
        ref = line[pos:].strip()

    return {
        "value_date": value_date,
        "entry_date": entry_date,
        "amount": amount,
        "currency": currency,
        "direction": direction,
        "ref": ref,
        "info": "",
        "type_code": type_code,
        "ref_acc_owner": ref_acc_owner,
        "ref_acc_number": ref_acc_number,
        "transaction_type": "",
    }


def parse_mt940(content: str) -> list[dict[str, Any]]:
    """Parse an MT940 SWIFT customer statement.

    Returns a list of statement dicts (one per :20: block).
    """
    content = content.replace("\r\n", "\n")
    statements: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    last_currency: str = ""

    for raw_line in content.split("\n"):
        line = raw_line.rstrip()
        if line == "-" or line.startswith("-"):
            # End of statement
            if cur is not None:
                statements.append(cur)
                cur = None
            continue
        m = _TAG_RE.match(line)
        if not m:
            continue
        tag = m.group(1)
        value_part = line[m.end():].strip()

        if tag == "20":
            if cur is not None:
                statements.append(cur)
            cur = {"reference": value_part, "entries": []}
        elif cur is None:
            continue
        elif tag == "25":
            cur["account"] = value_part
        elif tag == "28C":
            cur["statement_number"] = value_part
        elif tag in ("60F", "60M"):
            try:
                bal = _parse_balance_line(line)
                cur["opening_balance"] = bal
                last_currency = bal.get("currency", last_currency)
            except (ValueError, IndexError):
                pass
        elif tag == "61":
            try:
                entry = _parse_entry_line(line, currency=last_currency)
                cur["entries"].append(entry)
            except (ValueError, IndexError):
                pass
        elif tag == "86":
            # Info to account owner — attached to the last entry
            if cur["entries"]:
                cur["entries"][-1]["info"] = value_part
            else:
                cur.setdefault("_orphan_info", []).append(value_part)
        elif tag in ("62F", "62M"):
            try:
                bal = _parse_balance_line(line)
                cur["closing_balance"] = bal
                last_currency = bal.get("currency", last_currency)
            except (ValueError, IndexError):
                pass

    if cur is not None:
        statements.append(cur)
    return statements


SUPPORTED_MESSAGES = ("MT940", "CAMT053")


__all__ = ["parse_mt940", "SUPPORTED_MESSAGES"]
