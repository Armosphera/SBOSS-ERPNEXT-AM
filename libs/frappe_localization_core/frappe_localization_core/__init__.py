"""frappe_localization_core — country-agnostic localization helpers.

Public API (Contract C — frozen):
    number_to_words(value: Decimal, lang: str) -> str
    iban_validator(iban: str, country: str) -> bool
    parse_camt053(xml: bytes | str) -> dict

Supported ISO 20022 message families are listed in ``SUPPORTED_MESSAGES``;
adding a new family (e.g. ``pain.001`` for outbound payments) requires
a corresponding parser module and an entry in this tuple.
"""
from frappe_localization_core.iso20022_parser import parse_camt053
from frappe_localization_core.iban_validator import (
    SUPPORTED_COUNTRIES,
    iban_validator,
)
from frappe_localization_core.number_to_words import (
    SUPPORTED,
    number_to_words,
)

__version__ = "0.1.3"

# Public, frozen list of supported ISO 20022 message families.
# Adding a new family requires a sibling ``parse_<message>`` function
# and a contract update (Contract C freeze review).
SUPPORTED_MESSAGES: tuple[str, ...] = ("CAMT053",)

__all__ = [
    "SUPPORTED",
    "SUPPORTED_COUNTRIES",
    "SUPPORTED_MESSAGES",
    "iban_validator",
    "number_to_words",
    "parse_camt053",
]
