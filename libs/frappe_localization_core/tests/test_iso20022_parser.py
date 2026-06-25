"""Tests for frappe_localization_core.iso20022_parser — CAMT.053 statement parser.

Contract C (frozen):
    parse_camt053(xml: bytes | str) -> dict

The returned dict is normalised so the caller does not need to know
about ISO 20022 namespaces or lxml:

    {
        "header": {
            "msg_id":     str,        # GrpHdr/MsgId
            "created_at": str,        # GrpHdr/CreDtTm (ISO 8601 string)
            "fr_dt_to_bk": str,       # GrpHdr/Fr/FIId/FinInstnId/BICFI
                                     # (i.e. the BIC of the sending bank)
        },
        "statement": {
            "id":              str,   # Stmt/Id
            "account_iban":    str,   # Stmt/Acct/Id/IBAN
            "account_currency": str,  # Stmt/Acct/Ccy
            "balance_opening": {
                "amount":   Decimal,
                "currency": str,
                "date":     str,     # ISO 8601 (YYYY-MM-DD)
            },
            "balance_closing": { ... same shape ... },
            "entries": [
                {
                    "value_date":       str,   # YYYY-MM-DD
                    "booking_date":     str,
                    "amount":           Decimal,
                    "currency":         str,
                    "direction":        "C" | "D",  # from CdtDbtInd
                    "counterparty_name": str | None,
                    "counterparty_iban": str | None,
                    "ref":              str | None,  # NtryRef or EndToEndId
                    "info":             str | None,  # AddtlNtryInf / RmtInf/Ustrd
                },
                ...
            ],
        },
    }

Unsupported root elements raise :class:`ValueError`.  Both ``bytes``
and ``str`` input are accepted (the schema declares UTF-8 / ISO 20022
XML, so ``bytes`` are decoded as UTF-8 with surrogate-escape fallback).
"""
from __future__ import annotations

import unittest
from decimal import Decimal

from frappe_localization_core.iso20022_parser import parse_camt053


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

# ISO 20022 namespace for the standard CAMT.053.001.06 schema used by
# Armenian banks (Ameriabank, Ardshinbank, Converse Bank) and by UAE banks
# (ENBD, Mashreq, FAB, ADCB).
CAMT_NS = "urn:iso:std:iso:20022:tech:xsd:camt.053.001.06"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"


def _minimal_camt053_xml() -> bytes:
    """A hand-built, minimal-valid CAMT.053.001.06 document with two entries.

    This is the smallest document that exercises every field of the
    normalised dict: header + opening/closing balance + 1 credit entry
    + 1 debit entry.  It is used by ``test_parse_minimal_camt053`` to
    pin the contract shape.
    """
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<Document xmlns="{CAMT_NS}" xmlns:xsi="{XSI_NS}">'
        f'  <BkToCstmrStmt>'
        f'    <GrpHdr>'
        f'      <MsgId>STMT-2026-06-24-001</MsgId>'
        f'      <CreDtTm>2026-06-24T10:00:00</CreDtTm>'
        f'      <Fr>'
        f'        <FIId>'
        f'          <FinInstnId>'
        f'            <BICFI>AMERAM22XXX</BICFI>'
        f'          </FinInstnId>'
        f'        </FIId>'
        f'      </Fr>'
        f'    </GrpHdr>'
        f'    <Stmt>'
        f'      <Id>STMT-2026-06-24-001-STMT</Id>'
        f'      <Acct>'
        f'        <Id>'
        f'          <IBAN>AM96103000112345678901234567890</IBAN>'
        f'        </Id>'
        f'        <Ccy>AMD</Ccy>'
        f'      </Acct>'
        f'      <Bal>'
        f'        <Tp><CdOrPrtry><Cd>OPBD</Cd></CdOrPrtry></Tp>'
        f'        <Amt Ccy="AMD">1500000.00</Amt>'
        f'        <Dt><Dt>2026-06-23</Dt></Dt>'
        f'      </Bal>'
        f'      <Bal>'
        f'        <Tp><CdOrPrtry><Cd>CLBD</Cd></CdOrPrtry></Tp>'
        f'        <Amt Ccy="AMD">1750000.00</Amt>'
        f'        <Dt><Dt>2026-06-24</Dt></Dt>'
        f'      </Bal>'
        # Entry 1: a credit (money received).  Counterparty is the Dbtr.
        f'      <Ntry>'
        f'        <Amt Ccy="AMD">500000.00</Amt>'
        f'        <CdtDbtInd>CRDT</CdtDbtInd>'
        f'        <BookgDt><Dt>2026-06-24</Dt></BookgDt>'
        f'        <ValDt><Dt>2026-06-24</Dt></ValDt>'
        f'        <NtryRef>PAY-1001</NtryRef>'
        f'        <AddtlNtryInf>Salary payment June</AddtlNtryInf>'
        f'        <NtryDtls><TxDtls>'
        f'          <RltdPties>'
        f'            <Dbtr><Nm>ACME LLC</Nm></Dbtr>'
        f'            <DbtrAcct><Id><IBAN>AM22000000000000000000000000</IBAN></Id></DbtrAcct>'
        f'          </RltdPties>'
        f'          <RmtInf><Ustrd>Invoice 2026-001</Ustrd></RmtInf>'
        f'        </TxDtls></NtryDtls>'
        f'      </Ntry>'
        # Entry 2: a debit (money sent).  Counterparty is the Cdtr.
        f'      <Ntry>'
        f'        <Amt Ccy="AMD">250000.00</Amt>'
        f'        <CdtDbtInd>DBIT</CdtDbtInd>'
        f'        <BookgDt><Dt>2026-06-24</Dt></BookgDt>'
        f'        <ValDt><Dt>2026-06-24</Dt></ValDt>'
        f'        <NtryRef>PAY-1002</NtryRef>'
        f'        <AddtlNtryInf>Rent June</AddtlNtryInf>'
        f'        <NtryDtls><TxDtls>'
        f'          <RltdPties>'
        f'            <Cdtr><Nm>Landlord Inc.</Nm></Cdtr>'
        f'            <CdtrAcct><Id><IBAN>AE070331234567890123456</IBAN></Id></CdtrAcct>'
        f'          </RltdPties>'
        f'        </TxDtls></NtryDtls>'
        f'      </Ntry>'
        f'    </Stmt>'
        f'  </BkToCstmrStmt>'
        f'</Document>'
    ).encode("utf-8")


def _realistic_ameriabank_camt053_xml() -> bytes:
    """A realistic 4-entry CAMT.053.001.06 statement modelled on what
    Armenian banks (Ameriabank / Ardshinbank) actually emit in production.

    Includes:
        * AMD account (Ardshinbank, BIC = ASHBAM22)
        * 1 incoming wire (CRDT, foreign counterparty)
        * 1 outgoing utility payment (DBIT)
        * 1 incoming POS / card settlement (CRDT)
        * 1 outgoing tax payment to the State Revenue Committee (DBIT,
          AM tax-collector IBAN)
        * opening + closing balance
    """
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<Document xmlns="{CAMT_NS}" xmlns:xsi="{XSI_NS}">'
        f'  <BkToCstmrStmt>'
        f'    <GrpHdr>'
        f'      <MsgId>ASHB-2026-06-24-AMSTMT-9921</MsgId>'
        f'      <CreDtTm>2026-06-24T23:59:00+04:00</CreDtTm>'
        f'      <Fr>'
        f'        <FIId>'
        f'          <FinInstnId>'
        f'            <BICFI>ASHBAM22</BICFI>'
        f'            <Nm>Ardshinbank OJSC</Nm>'
        f'          </FinInstnId>'
        f'        </FIId>'
        f'      </Fr>'
        f'      <MsgRcpt><FIId><FinInstnId><BICFI>CUSTAM22</BICFI></FinInstnId></FIId></MsgRcpt>'
        f'    </GrpHdr>'
        f'    <Stmt>'
        f'      <Id>ASHB-2026-06-24-AMSTMT-9921-STMT</Id>'
        f'      <CreDtTm>2026-06-24T23:59:00+04:00</CreDtTm>'
        f'      <Acct>'
        f'        <Id>'
        f'          <IBAN>AM96103000112345678901234567890</IBAN>'
        f'        </Id>'
        f'        <Ccy>AMD</Ccy>'
        f'        <Nm>ACME LLC operating account</Nm>'
        f'      </Acct>'
        f'      <Bal>'
        f'        <Tp><CdOrPrtry><Cd>OPBD</Cd></CdOrPrtry></Tp>'
        f'        <Amt Ccy="AMD">12500000.00</Amt>'
        f'        <Dt><Dt>2026-06-23</Dt></Dt>'
        f'      </Bal>'
        f'      <Bal>'
        f'        <Tp><CdOrPrtry><Cd>CLBD</Cd></CdOrPrtry></Tp>'
        f'        <Amt Ccy="AMD">11235400.50</Amt>'
        f'        <Dt><Dt>2026-06-24</Dt></Dt>'
        f'      </Bal>'
        # 1: incoming SWIFT wire (USD, later converted by bank into AMD).
        f'      <Ntry>'
        f'        <Amt Ccy="AMD">3500000.00</Amt>'
        f'        <CdtDbtInd>CRDT</CdtDbtInd>'
        f'        <BookgDt><Dt>2026-06-24</Dt></BookgDt>'
        f'        <ValDt><Dt>2026-06-24</Dt></ValDt>'
        f'        <NtryRef>SWIFT20260624XYZ001</NtryRef>'
        f'        <AddtlNtryInf>SWIFT incoming wire from overseas client</AddtlNtryInf>'
        f'        <NtryDtls><TxDtls>'
        f'          <Refs><EndToEndId>INV-2026-EU-777</EndToEndId></Refs>'
        f'          <RltdPties>'
        f'            <Dbtr><Nm>Müller GmbH</Nm></Dbtr>'
        f'            <DbtrAcct><Id><IBAN>DE89370400440532013000</IBAN></Id></DbtrAcct>'
        f'          </RltdPties>'
        f'          <RmtInf><Ustrd>Invoice EU-2026-777 goods delivery</Ustrd></RmtInf>'
        f'        </TxDtls></NtryDtls>'
        f'      </Ntry>'
        # 2: outgoing utility payment (Electric Networks of Armenia).
        f'      <Ntry>'
        f'        <Amt Ccy="AMD">185400.00</Amt>'
        f'        <CdtDbtInd>DBIT</CdtDbtInd>'
        f'        <BookgDt><Dt>2026-06-24</Dt></BookgDt>'
        f'        <ValDt><Dt>2026-06-24</Dt></ValDt>'
        f'        <NtryRef>UTIL-2026-06-24-001</NtryRef>'
        f'        <AddtlNtryInf>Electric Networks of Armenia — June bill</AddtlNtryInf>'
        f'        <NtryDtls><TxDtls>'
        f'          <RltdPties>'
        f'            <Cdtr><Nm>Electric Networks of Armenia CJSC</Nm></Cdtr>'
        f'            <CdtrAcct><Id><IBAN>AM00ENA00000000000000000000</IBAN></Id></CdtrAcct>'
        f'          </RltdPties>'
        f'        </TxDtls></NtryDtls>'
        f'      </Ntry>'
        # 3: incoming POS / card settlement (Ardshinbank's acquiring).
        f'      <Ntry>'
        f'        <Amt Ccy="AMD">520800.50</Amt>'
        f'        <CdtDbtInd>CRDT</CdtDbtInd>'
        f'        <BookgDt><Dt>2026-06-24</Dt></BookgDt>'
        f'        <ValDt><Dt>2026-06-24</Dt></ValDt>'
        f'        <NtryRef>POS-2026-06-24-7733</NtryRef>'
        f'        <AddtlNtryInf>Card settlement batch 2026-06-24</AddtlNtryInf>'
        f'        <NtryDtls><TxDtls>'
        f'          <RltdPties>'
        f'            <Dbtr><Nm>Ardshinbank Acquiring</Nm></Dbtr>'
        f'          </RltdPties>'
        f'        </TxDtls></NtryDtls>'
        f'      </Ntry>'
        # 4: outgoing tax payment to the Armenian State Revenue Committee.
        f'      <Ntry>'
        f'        <Amt Ccy="AMD">5000000.00</Amt>'
        f'        <CdtDbtInd>DBIT</CdtDbtInd>'
        f'        <BookgDt><Dt>2026-06-24</Dt></BookgDt>'
        f'        <ValDt><Dt>2026-06-24</Dt></ValDt>'
        f'        <NtryRef>TAX-2026-Q2-PAY-001</NtryRef>'
        f'        <AddtlNtryInf>Profit tax Q2 2026</AddtlNtryInf>'
        f'        <NtryDtls><TxDtls>'
        f'          <RltdPties>'
        f'            <Cdtr><Nm>State Revenue Committee of RA</Nm></Cdtr>'
        f'            <CdtrAcct><Id><IBAN>AM00SRC00000000000000000000</IBAN></Id></CdtrAcct>'
        f'          </RltdPties>'
        f'          <RmtInf><Ustrd>Profit tax Q2 2026 TIN 01234567</Ustrd></RmtInf>'
        f'        </TxDtls></NtryDtls>'
        f'      </Ntry>'
        f'    </Stmt>'
        f'  </BkToCstmrStmt>'
        f'</Document>'
    ).encode("utf-8")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestParseCamt053(unittest.TestCase):
    """Contract C pin: the normalised dict shape produced by parse_camt053."""

    # (1) Hand-built minimal document -> expected dict shape ----------------
    def test_parse_minimal_camt053(self):
        out = parse_camt053(_minimal_camt053_xml())

        # Header
        self.assertEqual(out["header"]["msg_id"], "STMT-2026-06-24-001")
        self.assertEqual(out["header"]["created_at"], "2026-06-24T10:00:00")
        self.assertEqual(out["header"]["fr_dt_to_bk"], "AMERAM22XXX")

        # Statement identity + account
        self.assertEqual(out["statement"]["id"], "STMT-2026-06-24-001-STMT")
        self.assertEqual(
            out["statement"]["account_iban"], "AM96103000112345678901234567890"
        )
        self.assertEqual(out["statement"]["account_currency"], "AMD")

        # Balances (Decimal, NOT str / float)
        op = out["statement"]["balance_opening"]
        cl = out["statement"]["balance_closing"]
        self.assertIsInstance(op["amount"], Decimal)
        self.assertEqual(op["amount"], Decimal("1500000.00"))
        self.assertEqual(op["currency"], "AMD")
        self.assertEqual(op["date"], "2026-06-23")

        self.assertIsInstance(cl["amount"], Decimal)
        self.assertEqual(cl["amount"], Decimal("1750000.00"))
        self.assertEqual(cl["currency"], "AMD")
        self.assertEqual(cl["date"], "2026-06-24")

        # Two entries
        entries = out["statement"]["entries"]
        self.assertEqual(len(entries), 2)

        # Entry 1: credit, counterparty = Dbtr
        e1 = entries[0]
        self.assertIsInstance(e1["amount"], Decimal)
        self.assertEqual(e1["amount"], Decimal("500000.00"))
        self.assertEqual(e1["currency"], "AMD")
        self.assertEqual(e1["direction"], "C")
        self.assertEqual(e1["counterparty_name"], "ACME LLC")
        self.assertEqual(e1["counterparty_iban"], "AM22000000000000000000000000")
        self.assertEqual(e1["ref"], "PAY-1001")
        # info concatenates <AddtlNtryInf> ("Salary payment June") with
        # <RmtInf><Ustrd> ("Invoice 2026-001") when both are present —
        # the latter usually carries the invoice/remittance reference
        # the former omits.
        self.assertEqual(e1["info"], "Salary payment June Invoice 2026-001")
        self.assertEqual(e1["value_date"], "2026-06-24")
        self.assertEqual(e1["booking_date"], "2026-06-24")

        # Entry 2: debit, counterparty = Cdtr
        e2 = entries[1]
        self.assertEqual(e2["amount"], Decimal("250000.00"))
        self.assertEqual(e2["direction"], "D")
        self.assertEqual(e2["counterparty_name"], "Landlord Inc.")
        self.assertEqual(e2["counterparty_iban"], "AE070331234567890123456")
        self.assertEqual(e2["ref"], "PAY-1002")

    # (2) Real-world Ardshinbank-shaped sample ---------------------------------
    def test_parse_real_ardshinbank_sample(self):
        out = parse_camt053(_realistic_ameriabank_camt053_xml())

        # Header / statement identity
        self.assertEqual(out["header"]["msg_id"], "ASHB-2026-06-24-AMSTMT-9921")
        self.assertEqual(out["header"]["created_at"], "2026-06-24T23:59:00+04:00")
        self.assertEqual(out["header"]["fr_dt_to_bk"], "ASHBAM22")
        self.assertEqual(out["statement"]["id"], "ASHB-2026-06-24-AMSTMT-9921-STMT")
        self.assertEqual(out["statement"]["account_currency"], "AMD")

        # Opening / closing balance
        self.assertEqual(
            out["statement"]["balance_opening"]["amount"], Decimal("12500000.00")
        )
        self.assertEqual(
            out["statement"]["balance_closing"]["amount"], Decimal("11235400.50")
        )

        # 4 entries (2 credits, 2 debits)
        entries = out["statement"]["entries"]
        self.assertEqual(len(entries), 4)
        directions = [e["direction"] for e in entries]
        self.assertEqual(directions, ["C", "D", "C", "D"])

        # Credit entry has a foreign (DE) counterparty IBAN.
        credit_wire = entries[0]
        self.assertEqual(credit_wire["counterparty_name"], "Müller GmbH")
        self.assertEqual(credit_wire["counterparty_iban"], "DE89370400440532013000")
        self.assertEqual(credit_wire["amount"], Decimal("3500000.00"))

        # Debit entry (utility) has Armenian counterparty.
        utility = entries[1]
        self.assertEqual(utility["counterparty_name"], "Electric Networks of Armenia CJSC")
        self.assertEqual(utility["amount"], Decimal("185400.00"))

        # Card settlement — incoming, no counterparty IBAN.
        pos = entries[2]
        self.assertEqual(pos["direction"], "C")
        self.assertEqual(pos["counterparty_name"], "Ardshinbank Acquiring")
        self.assertIsNone(pos["counterparty_iban"])

        # Tax payment — outgoing, TIN reference in info.
        tax = entries[3]
        self.assertEqual(tax["direction"], "D")
        self.assertEqual(tax["counterparty_name"], "State Revenue Committee of RA")
        self.assertIn("TIN 01234567", tax["info"])

    # (3) IBAN extraction from <Acct><Id><IBAN> ---------------------------------
    def test_parse_account_iban_extracted(self):
        out = parse_camt053(_minimal_camt053_xml())
        self.assertEqual(
            out["statement"]["account_iban"], "AM96103000112345678901234567890"
        )

    # (4) Opening / closing balance Decimal extraction -------------------------
    def test_parse_opening_and_closing_balances(self):
        out = parse_camt053(_minimal_camt053_xml())
        op = out["statement"]["balance_opening"]
        cl = out["statement"]["balance_closing"]

        # Decimal — not str, not float.
        self.assertIsInstance(op["amount"], Decimal)
        self.assertIsInstance(cl["amount"], Decimal)

        # No float-inherited repr errors: must preserve the 2-dp form
        # and not collapse it to a float.
        self.assertEqual(op["amount"], Decimal("1500000.00"))
        self.assertEqual(cl["amount"], Decimal("1750000.00"))
        self.assertEqual(op["currency"], "AMD")
        self.assertEqual(cl["currency"], "AMD")
        self.assertEqual(op["date"], "2026-06-23")
        self.assertEqual(cl["date"], "2026-06-24")

    # (5) Direction C/D from CdtDbtInd ----------------------------------------
    def test_parse_entry_direction(self):
        out = parse_camt053(_minimal_camt053_xml())
        e1, e2 = out["statement"]["entries"]

        # CRDT -> 'C' (credit on the customer's account)
        self.assertEqual(e1["direction"], "C")
        # DBIT -> 'D' (debit on the customer's account)
        self.assertEqual(e2["direction"], "D")

        # Robustness: lowercase and whitespace must be normalised.
        out2 = parse_camt053(
            _minimal_camt053_xml().replace(b"<CRDT>", b"<crdt>").replace(b"<DBIT>", b"<dbit>")
        )
        self.assertEqual(out2["statement"]["entries"][0]["direction"], "C")
        self.assertEqual(out2["statement"]["entries"][1]["direction"], "D")

    # (6) Unknown root element must raise ValueError --------------------------
    def test_invalid_root_raises_valueerror(self):
        # Wrong schema family — pain.001 (customer credit transfer init).
        pain_xml = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.09">'
            b'  <CstmrCdtTrfInitn>'
            b'    <GrpHdr><MsgId>X</MsgId></GrpHdr>'
            b'  </CstmrCdtTrfInitn>'
            b'</Document>'
        )
        with self.assertRaises(ValueError):
            parse_camt053(pain_xml)

        # Arbitrary XML — definitely not CAMT.
        random_xml = b'<?xml version="1.0"?><Root><NotCamt/></Root>'
        with self.assertRaises(ValueError):
            parse_camt053(random_xml)


if __name__ == "__main__":
    unittest.main()
