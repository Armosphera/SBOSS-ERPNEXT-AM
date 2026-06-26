"""Currency formatting and parsing for AM (Armenia) / AE (UAE) locales.

Contract C (frozen public signature):
    format_currency(value, currency, locale='en') -> str
    parse_currency(formatted: str, currency: str) -> Decimal

The implementation is intentionally explicit (a hand-rolled formatter
driven by a per-currency rule table) rather than relying on
:class:`locale.localeconv` or `babel`. Two reasons:

1. **Stable across environments.**  The ICU data shipped with the
   user's OS or with ``babel`` can produce subtly different output for
   the same locale (e.g. NBSP vs. space, comma vs. dot for the decimal
   separator in Armenian AMD).  The library must produce byte-exact
   output that round-trips with :func:`parse_currency`.
2. **Locale set is small.**  We only need en / ar / hy / ru for AMD,
   AED, EUR and USD.  Hand-rolling those four rules is shorter than
   configuring ``babel`` and gives us deterministic output.

Supported currencies (Contract C frozen list):

| Code | Name                  | Decimals | Symbol  | Default pos  |
|------|-----------------------|----------|---------|--------------|
| AMD  | Armenian dram         | 0        | ֏ U+058F| after (space)|
| AED  | UAE dirham            | 2        | د.إ     | after (space)|
| EUR  | Euro                  | 2        | € U+20AC| before en / after ar |
| USD  | US dollar             | 2        | $       | before (no sep) |

Locale overrides:

* ``EUR`` with ``locale='ar'`` moves the symbol to the right.
* ``USD`` with ``locale='ru'`` uses space-thousands / comma-decimal.
* ``AMD`` / ``AED`` formatting is the same regardless of locale (the
  symbol is always trailing for those currencies).

Unsupported currency codes raise :class:`ValueError` so callers cannot
accidentally rely on a silent pass-through for a typo'd code.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Literal, Union


# Public, frozen list of supported currency codes (Contract C).
SUPPORTED_CURRENCIES: tuple[str, ...] = ("AMD", "AED", "EUR", "USD")


# Decimal rounding mode for fractional-digit truncation/expansion.
# Banker's rounding (ROUND_HALF_EVEN) is statistically nicer but the
# common-accounting convention is ROUND_HALF_UP. ERPNext's `money_in_words`
# helpers also use ROUND_HALF_UP, so we follow suit for consistency.
_ROUNDING = ROUND_HALF_UP


Number = Union[Decimal, float, int, str]


@dataclass(frozen=True)
class _Rule:
    """Per-currency formatting rules.

    Attributes:
        decimals: number of fractional digits to display (and to which
            the value is rounded before formatting).
        thou_sep: character used to separate groups of 3 integer digits.
            For ASCII currencies this is ``,`` (en) or ``" "`` (ru).
        dec_sep: character used to separate the integer from the fractional
            part.
        symbol: the currency symbol to render.
        space_after_symbol: whether to insert a space between the number
            and the symbol (or between the symbol and the number).
        symbol_before: True if the symbol is rendered *before* the number,
            False if it is rendered after.
    """

    decimals: int
    thou_sep: str
    dec_sep: str
    symbol: str
    space_after_symbol: bool
    symbol_before: bool


# Rules per (currency, locale).
# Default rules: locale-agnostic.
_DEFAULT_RULES: dict[str, _Rule] = {
    "AMD": _Rule(
        decimals=0,
        thou_sep=" ",
        dec_sep=".",
        symbol="\u058f",
        space_after_symbol=True,
        symbol_before=False,
    ),
    "AED": _Rule(
        decimals=2,
        thou_sep=",",
        dec_sep=".",
        symbol="\u062f.\u0625",
        space_after_symbol=True,
        symbol_before=False,
    ),
    "EUR": _Rule(
        decimals=2,
        thou_sep=",",
        dec_sep=".",
        symbol="\u20ac",
        space_after_symbol=False,
        symbol_before=True,
    ),
    "USD": _Rule(
        decimals=2,
        thou_sep=",",
        dec_sep=".",
        symbol="$",
        space_after_symbol=False,
        symbol_before=True,
    ),
}

# Per-currency, per-locale overrides.  Only the deltas need to be
# listed here; we look up the default rule first and then patch.
_LOCALE_OVERRIDES: dict[tuple[str, str], _Rule] = {
    # Arabic places the EUR symbol after the number.
    ("EUR", "ar"): _Rule(
        decimals=2,
        thou_sep=",",
        dec_sep=".",
        symbol="\u20ac",
        space_after_symbol=True,
        symbol_before=False,
    ),
    # Russian uses a space-thousands / comma-decimal pattern for USD.
    # The symbol stays before the number but no longer tight against it
    # (Russian typography separates the symbol from the number with a
    # non-breaking thin space in print; here we use a regular space for
    # parseability).
    ("USD", "ru"): _Rule(
        decimals=2,
        thou_sep=" ",
        dec_sep=",",
        symbol="$",
        space_after_symbol=False,
        symbol_before=True,
    ),
}


def _resolve_rule(currency: str, locale: str) -> _Rule:
    """Look up the rule for ``(currency, locale)``."""
    override = _LOCALE_OVERRIDES.get((currency, locale))
    if override is not None:
        return override
    default = _DEFAULT_RULES.get(currency)
    if default is None:
        raise ValueError(
            f"Unsupported currency: {currency!r}. "
            f"Supported: {SUPPORTED_CURRENCIES}"
        )
    return default


def _to_decimal(value: Number) -> Decimal:
    """Coerce ``value`` to :class:`Decimal` without losing precision.

    Strings are parsed as :class:`Decimal` so we don't go through ``float``
    (which would round e.g. ``0.1`` to ``0.1000000000000000055511151231``).
    :class:`int` and :class:`Decimal` are passed through unchanged.
    :class:`float` is converted via :class:`str` to avoid the binary
    representation surprise.
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        # str(value) gives the shortest decimal repr that round-trips
        # back to the same float64, which is the closest possible Decimal.
        return Decimal(str(value))
    if isinstance(value, str):
        try:
            return Decimal(value.strip())
        except InvalidOperation as exc:
            raise ValueError(f"Cannot parse number from string: {value!r}") from exc
    raise TypeError(
        f"Unsupported type for currency value: {type(value).__name__}. "
        f"Expected Decimal, float, int or str."
    )


def _group_integer(integer_part: str, thou_sep: str) -> str:
    """Insert ``thou_sep`` every 3 digits, counting from the right.

    For example, ``"1234567"`` with ``thou_sep=" "`` becomes
    ``"1 234 567"``.  Negative signs and any leading/trailing whitespace
    must be stripped before calling this function.
    """
    if len(integer_part) <= 3:
        return integer_part
    # Walk from the right in 3-digit groups.
    groups: list[str] = []
    i = len(integer_part)
    while i > 0:
        groups.append(integer_part[max(0, i - 3) : i])
        i -= 3
    groups.reverse()
    return thou_sep.join(groups)


def _render(value: Number, rule: _Rule) -> str:
    """Render ``value`` according to ``rule`` (number only, no symbol)."""
    d = _to_decimal(value)
    quant = Decimal(10) ** -rule.decimals
    rounded = d.quantize(quant, rounding=_ROUNDING)
    # ``normalized()`` strips trailing zeros; we DO want trailing zeros
    # for the fractional part because AMD-style "round to N decimals"
    # requires padding out to N places.  quantize() already does that.
    sign, digits, exponent = rounded.as_tuple()
    sign_str = "-" if sign else ""
    # Pad / truncate to the exact number of fractional digits.
    if rule.decimals == 0:
        frac_str = ""
        int_str = "".join(str(d) for d in digits)
    else:
        # exponent is negative: e.g. -2 for "1234.56".
        int_digits = -exponent
        digits_str = "".join(str(d) for d in digits)
        # Pad on the left if needed (e.g. "5" with int_digits=2 -> "05").
        if len(digits_str) <= int_digits:
            digits_str = digits_str.zfill(int_digits + 1)
        int_part = digits_str[:-int_digits] or "0"
        frac_part = digits_str[-int_digits:]
        int_str = int_part
        frac_str = frac_part

    grouped_int = _group_integer(int_str, rule.thou_sep)
    number_str = grouped_int if not frac_str else f"{grouped_int}{rule.dec_sep}{frac_str}"
    return f"{sign_str}{number_str}"


def format_currency(value: Number, currency: str, locale: str = "en") -> str:
    """Format ``value`` as a currency string for ``currency`` / ``locale``.

    Args:
        value: the numeric amount.  Accepted types: :class:`Decimal`,
            :class:`int`, :class:`float` and :class:`str`.  Floats are
            converted via their shortest round-trippable repr; strings
            are parsed as :class:`Decimal` so precision is preserved.
        currency: ISO 4217 currency code. Must be one of
            ``"AMD"``, ``"AED"``, ``"EUR"`` or ``"USD"``.
        locale: one of ``"en"``, ``"ar"``, ``"hy"`` or ``"ru"``. Only the
            ``"ar"`` locale for ``EUR`` and the ``"ru"`` locale for
            ``USD`` override the defaults; other combinations fall back
            to the currency's default rule.

    Returns:
        The formatted currency string.

    Raises:
        ValueError: if ``currency`` is not in :data:`SUPPORTED_CURRENCIES`
            or if a string ``value`` cannot be parsed as a number.
        TypeError: if ``value`` is not one of the accepted types.

    Examples:
        >>> format_currency(1234567, "AMD")
        '1 234 567 \u058f'
        >>> format_currency(1234.56, "AED")
        '1,234.56 \u062f.\u0625'
        >>> format_currency(1234.56, "EUR", locale="en")
        '\u20ac1,234.56'
        >>> format_currency(1234.56, "EUR", locale="ar")
        '1,234.56 \u20ac'
        >>> format_currency(1234567.89, "USD")
        '$1,234,567.89'
    """
    rule = _resolve_rule(currency, locale)
    number_str = _render(value, rule)
    # Split off any leading sign so we can place it before the symbol
    # (the conventional rendering is "-$1,234.56" not "$-1,234.56").
    sign = ""
    body = number_str
    if body.startswith("-"):
        sign = "-"
        body = body[1:]
    elif body.startswith("+"):
        sign = "+"
        body = body[1:]
    if rule.symbol_before:
        sep = " " if rule.space_after_symbol else ""
        return f"{sign}{rule.symbol}{sep}{body}"
    sep = " " if rule.space_after_symbol else ""
    return f"{sign}{body}{sep}{rule.symbol}"


def parse_currency(formatted: str, currency: str) -> Decimal:
    """Parse a previously-formatted currency string back to a :class:`Decimal`.

    The parser is the exact inverse of :func:`format_currency` for the
    supported currencies.  It strips whitespace and the currency symbol
    and re-applies the same (currency, locale='en') rule.  Callers who
    need to round-trip a Russian-formatted USD value must first
    re-normalise to the default ``locale='en'`` separator (or simply not
    call this on the Russian variant — round-trips work for any locale
    because we infer separators from the currency default).

    Args:
        formatted: the string produced by :func:`format_currency`.
        currency: the ISO 4217 code used to format the string.

    Returns:
        The original :class:`Decimal` value (to the precision supported
        by the currency — 0 fractional digits for ``AMD``, 2 for the rest).

    Raises:
        ValueError: if ``currency`` is not in :data:`SUPPORTED_CURRENCIES`.
    """
    if currency not in SUPPORTED_CURRENCIES:
        raise ValueError(
            f"Unsupported currency: {currency!r}. "
            f"Supported: {SUPPORTED_CURRENCIES}"
        )
    rule = _DEFAULT_RULES[currency]

    # Strip whitespace and the currency symbol (the symbol may appear
    # on either side, depending on the currency, so we just remove it
    # wherever it is).
    cleaned = formatted.strip()
    if rule.symbol and rule.symbol in cleaned:
        cleaned = cleaned.replace(rule.symbol, "")
    # Also strip whitespace inside the number (handles e.g. "1 234 567").
    cleaned = cleaned.strip()
    # AED's symbol is two characters joined by a dot — already handled
    # by the .replace() above because the symbol string is contiguous.

    # Determine the sign.
    negative = cleaned.startswith("-")
    if negative:
        cleaned = cleaned[1:].strip()
    elif cleaned.startswith("+"):
        cleaned = cleaned[1:].strip()

    # Split into integer and fractional parts.  We accept either the
    # rule's declared decimal separator OR the other common one (``.`` vs
    # ``,``).  This makes the parser robust against locale swaps — e.g.
    # ``parse_currency("$1 234,56", "USD")`` should work even though
    # USD's default rule says ``dec_sep="."``.
    for sep_candidate in (rule.dec_sep, "." if rule.dec_sep == "," else ","):
        if sep_candidate in cleaned:
            int_part, _, frac_part = cleaned.partition(sep_candidate)
            break
    else:
        int_part, frac_part = cleaned, ""

    # Strip thousands separators and rebuild the canonical numeric string.
    # We accept both the rule's thousands separator and (for round-trip
    # robustness) any whitespace inside the integer part.  This lets the
    # parser cope with strings produced under a different locale than
    # the default — e.g. a Russian-formatted USD string
    # (``"$1 234,56"``) parses cleanly even when ``locale='en'``.
    int_digits = int_part.replace(rule.thou_sep, "")
    if rule.thou_sep != " ":
        int_digits = int_digits.replace(" ", "")

    if rule.decimals == 0:
        # AMD-style: any fractional digits are dropped, NOT rounded.
        # (format_currency rounds, but parse_currency of a manually
        # typed "1234567.89 ֏" should still yield 1234567.)
        numeric_str = int_digits if int_digits else "0"
    else:
        # Pad / truncate frac_part to exactly ``rule.decimals`` digits.
        frac_part = (frac_part + "0" * rule.decimals)[: rule.decimals]
        numeric_str = f"{int_digits or '0'}.{frac_part}"

    try:
        value = Decimal(numeric_str)
    except InvalidOperation as exc:
        raise ValueError(
            f"Cannot parse currency string: {formatted!r} for {currency!r}"
        ) from exc
    return -value if negative else value


__all__ = ["SUPPORTED_CURRENCIES", "format_currency", "parse_currency"]