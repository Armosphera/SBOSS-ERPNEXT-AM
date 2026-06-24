"""UAE Chart of Accounts (IFRS) for Armosphera.

Exposes:
- build_coa_tree(): list of dicts representing the seed tree
- seed_uae_coa(company): idempotently insert accounts into a company
- install_coa(): bench-execute wrapper
"""

from .install_coa import build_coa_tree, install_coa, seed_uae_coa

__all__ = ["build_coa_tree", "install_coa", "seed_uae_coa"]
