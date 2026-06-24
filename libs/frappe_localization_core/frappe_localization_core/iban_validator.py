"""IBAN check-digit validator for AM (Armenia) and AE (UAE).

Contract C (frozen public signature):
    iban_validator(iban: str, country: str) -> bool

Algorithm (ISO 13616 / ECBS TR201):
    1. Move the first 4 characters (country code + 2 check digits) to the end.
    2. Replace every letter A..Z with its 2-digit numeric value (A=10..Z=35).
    3. Compute the resulting integer modulo 97.
    4. The IBAN is valid iff the result is exactly 1.

The function only accepts the canonical, compact form of the IBAN
(uppercase letters + digits, no spaces or punctuation).  Whitespace,
dashes, dots and lowercase are rejected as invalid because callers
should normalise before invoking this function (or get a ``False``).

Unsupported countries raise :class:`ValueError` so callers cannot
accidentally rely on a permissive ``False`` return for a typo'd
country code.
"""
from __future__ import annotations

# Public, frozen list of supported country codes (Contract C).
SUPPORTED_COUNTRIES: tuple[str, ...] = ("AM", "AE")

# Official IBAN registry lengths for the supported countries.
_IBAN_LENGTH = {"AM": 31, "AE": 23}

# Precomputed A=10..Z=35 lookup table for fast letter→number conversion.
_LETTER_VALUE = {chr(ord("A") + i): str(i + 10) for i in range(26)}


def _to_numeric(iban: str) -> str:
    """Expand an IBAN to its pure-numeric form per ISO 13616.

    Replaces each letter A..Z with its 2-digit value (A=10..Z=35)
    and concatenates the digits of every numeric character.
    """
    out: list[str] = []
    for ch in iban:
        if "0" <= ch <= "9":
            out.append(ch)
        else:
            v = _LETTER_VALUE.get(ch)
            if v is None:
                raise ValueError(f"invalid IBAN character: {ch!r}")
            out.append(v)
    return "".join(out)


def _mod97(iban: str) -> int:
    """Compute the integer formed by the IBAN modulo 97, per ISO 13616.

    The first 4 characters of an IBAN (country code + 2 check digits)
    are moved to the end before the reduction; only then are letters
    expanded to their 2-digit numeric values (A=10..Z=35).  The result
    of the reduction mod 97 must be exactly 1 for the IBAN to be valid.

    The reduction is done chunk-by-chunk so intermediate values stay
    small (under ~10**9).  This is the canonical reference algorithm
    from ECBS TR201.
    """
    # Step 1: rearrange — move first 4 chars to end.
    rearranged = iban[4:] + iban[:4]
    # Step 2: expand letters to digits.
    numeric = _to_numeric(rearranged)
    # Step 3: reduce chunk by chunk.
    rem = 0
    for i in range(0, len(numeric), 9):
        chunk = numeric[i : i + 9]
        rem = (rem * 10 ** len(chunk) + int(chunk)) % 97
    return rem


def iban_validator(iban: str, country: str) -> bool:
    """Return True iff ``iban`` is a syntactically valid IBAN for ``country``.

    Args:
        iban: the IBAN string in canonical compact form (uppercase letters
            and digits only — no spaces, dashes, or other punctuation).
        country: ISO 3166-1 alpha-2 country code. Must be one of
            ``"AM"`` (Armenia, 31 chars) or ``"AE"`` (UAE, 23 chars).

    Returns:
        True iff the IBAN has the correct length for ``country``, the
        country prefix matches, all characters are alphanumeric ASCII,
        and the mod-97 check digit is 1.

    Raises:
        ValueError: if ``country`` is not in ``SUPPORTED_COUNTRIES``.

    Examples:
        >>> iban_validator("AE070331234567890123456", "AE")
        True
        >>> iban_validator("AM96103000112345678901234567890", "AM")
        True
        >>> iban_validator("AM00103000112345678901234567890", "AM")  # bad check
        False
    """
    if country not in SUPPORTED_COUNTRIES:
        raise ValueError(
            f"Unsupported country: {country!r}. "
            f"Supported: {SUPPORTED_COUNTRIES}"
        )
    if not isinstance(iban, str):
        return False
    expected_len = _IBAN_LENGTH[country]
    if len(iban) != expected_len:
        return False
    # Country prefix must match the explicit ``country`` argument.
    if iban[:2] != country:
        return False
    # All chars must be uppercase ASCII alnum (A-Z + 0-9).
    if not iban.isascii() or not iban.isalnum() or not iban.isupper():
        return False
    # ISO 13616 mod-97 check digit.
    return _mod97(iban) == 1


__all__ = ["SUPPORTED_COUNTRIES", "iban_validator"]
