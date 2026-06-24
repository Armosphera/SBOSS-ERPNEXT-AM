"""frappe_localization_core — country-agnostic localization helpers.

Public API (Contract C — frozen):
    number_to_words(value: Decimal, lang: str) -> str
"""
from frappe_localization_core.number_to_words import (
    SUPPORTED,
    number_to_words,
)

__version__ = "0.1.1"
__all__ = ["SUPPORTED", "number_to_words"]
