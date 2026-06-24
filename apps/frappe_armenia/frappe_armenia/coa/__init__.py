"""frappe_armenia.coa — Armenian Chart of Accounts (COA) fixture.

Public API re-exported here for convenience:

    from frappe_armenia.coa import build_coa_tree, count_by_root_type, seed_armenian_coa

See `install_coa.py` for the implementation.
"""

from frappe_armenia.coa.install_coa import (
    build_coa_tree,
    count_by_root_type,
    seed_armenian_coa,
)

__all__ = [
    "build_coa_tree",
    "count_by_root_type",
    "seed_armenian_coa",
]
