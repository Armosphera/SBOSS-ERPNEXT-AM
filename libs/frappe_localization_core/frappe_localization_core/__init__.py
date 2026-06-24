"""frappe_localization_core — country-agnostic localization helpers.

Public API (Contract C — frozen):
    number_to_words(value: Decimal, lang: str) -> str
    iban_validator(iban: str, country: str) -> bool
"""
from frappe_localization_core.iban_validator import (
    SUPPORTED_COUNTRIES,
    iban_validator,
)
from frappe_localization_core.number_to_words import (
    SUPPORTED,
    number_to_words,
)

__version__ = "0.1.2"
__all__ = [
    "SUPPORTED",
    "SUPPORTED_COUNTRIES",
    "iban_validator",
    "number_to_words",
]
