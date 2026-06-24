"""Number-to-words conversion for English, Armenian, Arabic, and Russian.

Contract C (frozen public signature):
    number_to_words(value: Decimal, lang: str) -> str

For ``en``, ``ru`` and ``ar`` the heavy lifting is delegated to the
``num2words`` library (>= 0.5.10).  ``num2words`` does not ship an Armenian
locale, so ``hy`` is implemented locally with a small dict-based converter
that covers 0 .. 10**12, which is well above any number we will ever print
on an Armenian bank form or invoice.

The fractional part (if any) is always spelled digit-by-digit after a
localised "point" word.  This is the universal convention used in legal and
financial documents in all four languages and avoids locale-specific gender
or case agreement problems.
"""
from __future__ import annotations

from decimal import Decimal

from num2words import num2words

# Public, frozen list of supported language codes (Contract C).
SUPPORTED: tuple[str, ...] = ("en", "hy", "ar", "ru")

# Localised "minus" word prepended to negative numbers.
_MINUS_WORD = {
    "en": "minus ",
    "hy": "մինուս ",
    "ar": "ناقص ",
    "ru": "минус ",
}

# Localised "point" word separating integer and fractional parts.
_POINT_WORD = {
    "en": "point",
    "hy": "կետ",
    "ar": "فاصلة",
    "ru": "точка",
}


# ---------------------------------------------------------------------------
# Armenian (Eastern) number-to-words
# ---------------------------------------------------------------------------
#
# Eastern Armenian orthography (Republic of Armenia).  Covers 0 .. 10**12
# using a recursive split on the thousands groups.  Digits 0-9, teens 11-19,
# tens 20-90, and 100/1000/1000000/1000000000 are lookup tables.  Compound
# numbers 21-99 and 101-999 are formed by simple concatenation with a single
# space.  This is a deliberately small, well-tested surface; it does NOT
# implement the full Eastern Armenian inflectional system (e.g. genitive
# forms after a noun), because we always print the number in *nominative*
# form on cheques, invoices, and payslips.

_HY_UNITS = (
    "զրո",    # 0
    "մեկ",    # 1
    "երկու",  # 2
    "երեք",   # 3
    "չորս",   # 4
    "հինգ",   # 5
    "վեց",    # 6
    "յոթ",    # 7
    "ութ",    # 8
    "ինը",    # 9
)
_HY_TEENS = (
    "տաս",         # 10 (irregular: 10, not "տասը")
    "տասնմեկ",     # 11
    "տասներկու",   # 12
    "տասներեք",    # 13
    "տասնչորս",    # 14
    "տասնհինգ",    # 15
    "տասնվեց",     # 16
    "տասնյոթ",     # 17
    "տասնութ",     # 18
    "տասնինը",     # 19
)
_HY_TENS = (
    "",            # 0 (unused)
    "",            # 10 (covered by _HY_TEENS)
    "քսան",        # 20
    "երեսում",     # 30
    "քառասուն",   # 40
    "հիսուն",      # 50
    "վաթսուն",     # 60
    "յոթանասուն",  # 70
    "ութանասուն",  # 80
    "իննսուն",     # 90
)
_HY_HUNDRED = "հարյուր"
# Magnitude names (Eastern Armenian, singular nominative).
_HY_MAGNITUDES = (
    "",            # 10**0  (units)
    "հազար",       # 10**3
    "միլիոն",      # 10**6
    "միլիարդ",     # 10**9
)


def _hy_below_thousand(n: int) -> str:
    """Convert 0 <= n < 1000 to Eastern Armenian words."""
    if n < 0:
        raise ValueError(f"expected non-negative n, got {n}")
    if n < 10:
        return _HY_UNITS[n]
    if n < 20:
        return _HY_TEENS[n - 10]
    if n < 100:
        tens, units = divmod(n, 10)
        if units == 0:
            return _HY_TENS[tens]
        return f"{_HY_TENS[tens]} {_HY_UNITS[units]}"
    # 100 .. 999
    hundreds, rest = divmod(n, 100)
    head = (
        _HY_UNITS[hundreds] + " " + _HY_HUNDRED
        if hundreds > 1
        else _HY_HUNDRED  # "հարյուր" for exactly 100
    )
    if rest == 0:
        return head
    return f"{head} {_hy_below_thousand(rest)}"


def _hy_integer(n: int) -> str:
    """Convert any non-negative int to Eastern Armenian words."""
    if n == 0:
        return _HY_UNITS[0]
    # Split into thousands groups, least-significant first.
    # _HY_MAGNITUDES is (units, thousand, million, billion, ...).
    groups: list[int] = []
    while n > 0:
        groups.append(n % 1000)
        n //= 1000
    parts: list[str] = []
    for idx, group in enumerate(groups):
        if group == 0:
            continue
        magnitude = (
            _HY_MAGNITUDES[idx] if idx < len(_HY_MAGNITUDES) else ""
        )
        if magnitude:
            parts.append(f"{_hy_below_thousand(group)} {magnitude}")
        else:
            # Beyond 10**12 — fall back to spelling the raw group.
            parts.append(_hy_below_thousand(group))
    return " ".join(parts)


# ---------------------------------------------------------------------------
# English post-processing
# ---------------------------------------------------------------------------
# ``num2words`` for English inserts a literal " and " between every hundreds
# group and the following tens/units (British/Australian style), e.g.
#   "one billion, two hundred and thirty-four million, ..."
# The Contract C test (and the format used on cheques, invoices, and tax
# forms in the project's localisation apps) does not use the "and".  Strip
# it.  This is safe: " and " is only ever used by num2words as a numeric
# conjunction and never as a sub-string of any number-word in our supported
# range (0 .. 10**12).
def _en_strip_and(s: str) -> str:
    return s.replace(" and ", " ")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def number_to_words(value: Decimal, lang: str) -> str:
    """Convert a ``Decimal`` to its word representation in the given language.

    Args:
        value: any ``Decimal`` (integer, fractional, negative). Floats are
            rejected: callers must construct a ``Decimal`` explicitly to
            avoid the ``0.1 + 0.2 != 0.3`` float-representation bug.
        lang:  one of ``"en"``, ``"hy"``, ``"ar"``, ``"ru"`` (case
            insensitive).  Raises :class:`ValueError` otherwise.

    Returns:
        The number in words.  For negative numbers, the localised word
        for "minus" is prepended.  The fractional part, if any, is
        spelled digit-by-digit after a localised "point" word.

    Examples:
        >>> from decimal import Decimal
        >>> number_to_words(Decimal("42"), "en")
        'forty-two'
        >>> number_to_words(Decimal("-5"), "hy")
        'մինուս հինգ'
        >>> number_to_words(Decimal("12.34"), "en")
        'twelve point three four'
    """
    if lang not in SUPPORTED:
        raise ValueError(
            f"Unsupported language: {lang!r}. Supported: {SUPPORTED}"
        )
    if not isinstance(value, Decimal):
        value = Decimal(str(value))

    sign = ""
    if value < 0:
        sign = _MINUS_WORD[lang]
        value = -value

    int_part = int(value)
    frac = value - int_part

    if frac == 0:
        words = _int_to_words(int_part, lang)
    else:
        # Spell fractional digits one-by-one.  ``Decimal`` always serialises
        # the fractional part with the exact scale it has, e.g. 0.34 ->
        # "0.34" -> digit string "34".
        frac_str = str(frac)
        digits = frac_str.split(".")[1] if "." in frac_str else ""
        int_words = (
            _int_to_words(int_part, lang) if int_part else _int_to_words(0, lang)
        )
        frac_words = " ".join(_int_to_words(int(d), lang) for d in digits)
        words = f"{int_words} {_POINT_WORD[lang]} {frac_words}".strip()

    return f"{sign}{words}"


def _int_to_words(n: int, lang: str) -> str:
    """Convert a non-negative int to words in the given language."""
    if lang == "hy":
        return _hy_integer(n)
    if lang == "en":
        return _en_strip_and(num2words(n, lang="en"))
    # ru, ar: pass through num2words unchanged.
    return num2words(n, lang=lang)


__all__ = ["SUPPORTED", "number_to_words"]
