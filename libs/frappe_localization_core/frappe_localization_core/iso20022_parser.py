"""CAMT.053.001.06 bank-statement parser.

Contract C (frozen):
    parse_camt053(xml: bytes | str) -> dict

CAMT.053 is the ISO 20022 "BankToCustomerStatement" message family.  The
``.001.06`` variant (XML namespace
``urn:iso:std:iso:20022:tech:xsd:camt.053.001.06``) is the one used by
Armenian banks (Ameriabank, Ardshinbank, Converse Bank) and by UAE banks
(Emirates NBD, Mashreq, FAB, ADCB).

The returned dict is normalised so the caller does not need to know
about ISO 20022 namespaces or lxml::

    {
        "header": {
            "msg_id":     str,        # GrpHdr/MsgId
            "created_at": str,        # GrpHdr/CreDtTm
            "fr_dt_to_bk": str,       # GrpHdr/Fr/FIId/FinInstnId/BICFI
        },
        "statement": {
            "id":               str,
            "account_iban":     str,
            "account_currency": str,
            "balance_opening":  {"amount": Decimal, "currency": str, "date": str},
            "balance_closing":  {"amount": Decimal, "currency": str, "date": str},
            "entries": [
                {
                    "value_date":        str,
                    "booking_date":      str,
                    "amount":            Decimal,
                    "currency":          str,
                    "direction":         "C" | "D",
                    "counterparty_name": str | None,
                    "counterparty_iban": str | None,
                    "ref":               str | None,
                    "info":              str | None,
                },
                ...
            ],
        },
    }

Unsupported root elements raise :class:`ValueError`.  Both ``bytes``
and ``str`` input are accepted (``bytes`` are decoded as UTF-8 with
``surrogateescape`` fallback for the rare case a bank sends a
Latin-1-encoded comment or similar).
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from lxml import etree


# CAMT.053.001.06 canonical namespace.  Banks occasionally emit a
# different xsd version (e.g. .001.02 for older Oracle FLEXCUBE
# implementations), but for Armenia/UAE the .001.06 namespace is
# dominant and we validate by *root local-name* (``Document`` +
# ``BkToCstmrStmt``), not by exact namespace URI.
_CAMT_ROOT_LOCAL = "Document"
_CAMT_MSG_LOCAL = "BkToCstmrStmt"

# Whitelist of balance-type codes we recognise as opening / closing.
# We deliberately do NOT interpret "PRCD" (previously closed) or
# "ITBD" (interim booked) here — those land on the closing balance
# only as a fallback.
_OPENING_CODES = {"OPBD"}
_CLOSING_CODES = {"CLBD", "PRCD", "ITBD"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def parse_camt053(xml: bytes | str) -> dict[str, Any]:
    """Parse a CAMT.053.001.06 statement into a normalised dict.

    Args:
        xml: the CAMT.053 document as ``bytes`` (UTF-8 / ISO 8859-1)
            or ``str``.  ``bytes`` are decoded as UTF-8 first; if that
            fails we fall back to ``latin-1``.

    Returns:
        A normalised dict (see module docstring for the exact shape).

    Raises:
        ValueError: if the XML does not have ``<Document><BkToCstmrStmt>``
            as its root path (i.e. it is not a CAMT.053 statement).
        etree.XMLSyntaxError: if the input is not well-formed XML.
    """
    root = _parse_root(xml)

    if _local_name(root) != _CAMT_ROOT_LOCAL:
        raise ValueError(
            f"unsupported root element <{_local_name(root)}>; "
            f"expected <{_CAMT_ROOT_LOCAL}> for CAMT.053"
        )

    msg = _find_first(root, _CAMT_MSG_LOCAL)
    if msg is None:
        raise ValueError(
            f"missing <{_CAMT_MSG_LOCAL}> child in CAMT.053 root"
        )

    grp = _find_first(msg, "GrpHdr")
    stmt = _find_first(msg, "Stmt")
    if stmt is None:
        raise ValueError("CAMT.053 message contains no <Stmt>")

    return {
        "header": _parse_header(grp),
        "statement": _parse_statement(stmt),
    }


# ---------------------------------------------------------------------------
# Internal helpers — header & statement
# ---------------------------------------------------------------------------
def _parse_header(grp: etree._Element | None) -> dict[str, str]:
    return {
        "msg_id": _text(grp, "MsgId") if grp is not None else "",
        "created_at": _text(grp, "CreDtTm") if grp is not None else "",
        "fr_dt_to_bk": (
            _text(grp, "Fr/FIId/FinInstnId/BICFI") if grp is not None else ""
        ),
    }


def _parse_statement(stmt: etree._Element) -> dict[str, Any]:
    opening: dict[str, Any] | None = None
    closing: dict[str, Any] | None = None
    for bal in _find_all(stmt, "Bal"):
        code = (_text(bal, "Tp/CdOrPrtry/Cd") or "").strip().upper()
        parsed = _parse_balance(bal)
        if parsed is None:
            continue
        if code in _OPENING_CODES and opening is None:
            opening = parsed
        elif code in _CLOSING_CODES and closing is None:
            closing = parsed

    return {
        "id": _text(stmt, "Id") or "",
        "account_iban": _text(stmt, "Acct/Id/IBAN") or "",
        "account_currency": _text(stmt, "Acct/Ccy") or "",
        "balance_opening": opening or _empty_balance(),
        "balance_closing": closing or _empty_balance(),
        "entries": [_parse_entry(e) for e in _find_all(stmt, "Ntry")],
    }


# ---------------------------------------------------------------------------
# Internal helpers — balance, entry, counterparty
# ---------------------------------------------------------------------------
def _empty_balance() -> dict[str, Any]:
    return {"amount": Decimal("0"), "currency": "", "date": ""}


def _parse_balance(bal: etree._Element) -> dict[str, Any] | None:
    amt_el = _find_first(bal, "Amt")
    if amt_el is None or not (amt_el.text or "").strip():
        return None
    try:
        amount = Decimal(amt_el.text.strip())
    except InvalidOperation:
        return None
    return {
        "amount": amount,
        "currency": (amt_el.get("Ccy") or "").strip(),
        "date": _text(bal, "Dt/Dt") or "",
    }


def _parse_entry(ntry: etree._Element) -> dict[str, Any]:
    amt_el = _find_first(ntry, "Amt")
    amount = _to_decimal(amt_el.text if amt_el is not None else None)
    currency = (amt_el.get("Ccy") or "") if amt_el is not None else ""

    direction_raw = (_text(ntry, "CdtDbtInd") or "").strip().upper()
    if direction_raw == "CRDT":
        direction = "C"
    elif direction_raw == "DBIT":
        direction = "D"
    else:
        # Unknown / missing CdtDbtInd — default to debit (safer for
        # double-entry bookkeeping on the customer's books).
        direction = "D"

    # Counterparty: for a credit, the counterparty is the Dbtr
    # (the party that paid us).  For a debit, the counterparty is the
    # Cdtr (the party we paid).
    side = "Dbtr" if direction == "C" else "Cdtr"
    counterparty_name = _text(
        ntry, f"NtryDtls/TxDtls/RltdPties/{side}/Nm"
    )
    counterparty_iban = _text(
        ntry, f"NtryDtls/TxDtls/RltdPties/{side}Acct/Id/IBAN"
    )

    # ``ref`` is the bank's per-entry reference (NtryRef / AcctSvcrRef),
    # falling back to the EndToEndId / TxId in the underlying TxDtls.
    ref = (
        _text(ntry, "NtryRef")
        or _text(ntry, "AcctSvcrRef")
        or _text(ntry, "NtryDtls/TxDtls/Refs/EndToEndId")
        or _text(ntry, "NtryDtls/TxDtls/Refs/TxId")
    )

    # ``info`` is the free-text human-readable description.  Banks
    # often split it across <AddtlNtryInf> (entry level, e.g. "Salary
    # payment June") and <RmtInf><Ustrd> (txn level, e.g. "Invoice
    # 2026-001") — and American Bank of Armenia's connector only fills
    # one or the other.  We concatenate whichever pieces are present
    # with a single space so downstream search / ledger-narration code
    # sees the full description.
    info_parts: list[str] = []
    addtl = _text(ntry, "AddtlNtryInf")
    if addtl:
        info_parts.append(addtl)
    rmt = _text(ntry, "NtryDtls/TxDtls/RmtInf/Ustrd")
    if rmt and rmt not in info_parts:
        info_parts.append(rmt)
    info = " ".join(info_parts) if info_parts else None

    return {
        "value_date": _text(ntry, "ValDt/Dt") or "",
        "booking_date": _text(ntry, "BookgDt/Dt") or "",
        "amount": amount if amount is not None else Decimal("0"),
        "currency": currency,
        "direction": direction,
        "counterparty_name": counterparty_name,
        "counterparty_iban": counterparty_iban,
        "ref": ref,
        "info": info,
    }


# ---------------------------------------------------------------------------
# Low-level lxml utilities
# ---------------------------------------------------------------------------
def _parse_root(xml: bytes | str) -> etree._Element:
    """Decode ``xml`` (bytes or str) and parse it as an lxml Element.

    ``bytes`` are decoded as UTF-8 first; if that fails we fall back
    to ``latin-1``.  We do NOT try to validate against the CAMT.053
    XSD — banks in the wild vary slightly on optional elements, and
    lxml schema validation is out of scope for an on-the-fly parser.
    We do, however, validate the *root* path in
    :func:`parse_camt053` itself.
    """
    if isinstance(xml, bytes):
        try:
            text = xml.decode("utf-8")
        except UnicodeDecodeError:
            text = xml.decode("latin-1")
    else:
        text = xml
    parser = etree.XMLParser(
        recover=False,
        resolve_entities=False,
        no_network=True,
        huge_tree=False,
    )
    if isinstance(text, str):
        text = text.encode("utf-8")
    return etree.fromstring(text, parser=parser)


def _xpath(*local_names: str) -> str:
    """Build a namespace-agnostic, element-relative XPath that matches
    a path of local element names.

    Using ``local-name()`` lets us tolerate ANY namespace URI as long
    as the local element name matches — Ameriabank's connector emits
    a slightly different xsi namespace prefix from ENBD's, and banks
    occasionally upgrade their XSD version (e.g. .001.02 on older
    Oracle FLEXCUBE).  We pin the contract on the element *names*,
    not on the URI.

    The path is **relative** (``./*[local-name()='X']/...``) because
    :meth:`lxml.etree._Element.xpath` evaluates an absolute path
    (``/...``) against the **document root**, not against the calling
    element — so we always anchor at the element we were called on.
    """
    return "." + "/" + "/".join(f"*[local-name()='{n}']" for n in local_names)


def _find_first(el: etree._Element | None, *local_names: str) -> etree._Element | None:
    """Find the first descendant matching ``local_names`` (or ``None``)."""
    if el is None:
        return None
    res = el.xpath(_xpath(*local_names))
    return res[0] if res else None


def _find_all(el: etree._Element, *local_names: str) -> list[etree._Element]:
    """Find all descendants matching ``local_names``."""
    return el.xpath(_xpath(*local_names))


def _local_name(el: etree._Element) -> str:
    """Return the Clark-notation-free local name of an element."""
    tag = el.tag
    if isinstance(tag, str) and tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def _text(el: etree._Element | None, path: "str | tuple[str, ...]") -> str | None:
    """Return the text of the first descendant matching ``path``.

    ``path`` may be either a single ``str`` using ``/`` as a separator
    (e.g. ``"Fr/FIId/FinInstnId/BICFI"``) or a tuple of local element
    names (e.g. ``("Fr", "FIId", "FinInstnId", "BICFI")``).  Returns
    ``None`` if no such descendant exists or if the text is empty.
    """
    if el is None:
        return None
    if isinstance(path, str):
        parts: tuple[str, ...] = tuple(p for p in path.split("/") if p)
    else:
        parts = tuple(path)
    if not parts:
        return None
    target = _find_first(el, *parts)
    if target is None:
        return None
    txt = (target.text or "").strip()
    return txt or None


def _to_decimal(s: str | None) -> Decimal | None:
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


__all__ = ["parse_camt053"]
