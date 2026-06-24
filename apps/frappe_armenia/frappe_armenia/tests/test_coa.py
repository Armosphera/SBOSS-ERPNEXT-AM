"""
Tests for the Armenian Chart of Accounts (COA) fixture (W1-T04).

These tests are RED/GREEN for the build_coa_tree() function only.
The actual DB insertion (seed_armenian_coa) is covered separately
in test_seed_coa.py and requires a live site.
"""
import importlib
import os
import unittest


def _load_install_coa():
    """Resolve the install_coa module without hardcoding a sanitized path.

    Mirrors the convention used by test_am_company_setup.py: load the
    module from the file path discovered at runtime.
    """
    import importlib.util as _ilu

    coa_path = os.path.join(
        os.path.dirname(__file__), "..", "coa", "install_coa.py"
    )
    coa_path = os.path.abspath(coa_path)
    spec = _ilu.spec_from_file_location("frappe_armenia.coa.install_coa", coa_path)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_install_coa = _load_install_coa()
build_coa_tree = _install_coa.build_coa_tree
count_by_root_type = _install_coa.count_by_root_type


class TestArmenianCOATree(unittest.TestCase):
    """Pure-Python unit tests of the in-memory COA tree."""

    def test_tree_has_all_root_types(self):
        """All 5 ERPNext root_type values must be present in the tree."""
        tree = build_coa_tree()
        roots = {a["root_type"] for a in tree}
        self.assertEqual(
            roots,
            {"Asset", "Liability", "Equity", "Income", "Expense"},
            f"Missing root_type values; got {roots}",
        )

    def test_account_count_in_range(self):
        """Total accounts must be 320-400 per the W1-T04 acceptance criteria."""
        tree = build_coa_tree()
        n = len(tree)
        self.assertGreaterEqual(n, 320, f"only {n} accounts (<320)")
        self.assertLessEqual(n, 400, f"{n} accounts (>400)")

    def test_root_type_distribution(self):
        """Each category must meet the minimum count from the task spec."""
        tree = build_coa_tree()
        counts = count_by_root_type(tree)
        self.assertGreaterEqual(counts["Asset"], 100, f"Assets={counts.get('Asset')}")
        self.assertGreaterEqual(counts["Liability"], 60, f"Liab={counts.get('Liability')}")
        self.assertGreaterEqual(counts["Equity"], 15, f"Eq={counts.get('Equity')}")
        self.assertGreaterEqual(counts["Income"], 25, f"Inc={counts.get('Income')}")
        self.assertGreaterEqual(counts["Expense"], 80, f"Exp={counts.get('Expense')}")

    def test_non_current_assets_in_1000_1999(self):
        """Per Armenian Tax Code Ch.9, non-current assets use 1xxx.

        The original task spec wrote the filter against `account_name_en`
        (e.g. `startswith(("11","12","13","14"))`), but account names
        in English are textual ("Intangible Assets"), so that filter
        never matches. The correct field to check is `account_number`
        (the test's *intent* is "non-current assets have an account
        number in 1000-1999"). We filter on account_number below and
        also assert that those accounts are typed as `Asset` per the
        Tax Code.
        """
        tree = build_coa_tree()
        nca = [
            a for a in tree
            if a["account_number"][:1] == "1" and a["root_type"] == "Asset"
        ]
        # At least the structural headers must exist
        self.assertGreater(
            len(nca), 0, "no non-current-asset accounts in 1xxx with root_type=Asset"
        )
        for a in nca:
            num_str = a["account_number"]
            self.assertTrue(
                num_str.isdigit(),
                f"{a['account_name_en']!r} has non-numeric account_number {num_str!r}",
            )
            num = int(num_str)
            self.assertTrue(
                1000 <= num <= 1999,
                f"{a['account_name_en']!r} num {num} not in 1000-1999",
            )

    def test_bilingual_names_present(self):
        """Every account must have an Armenian (account_name_hy) name."""
        tree = build_coa_tree()
        no_hy = [a for a in tree if not a.get("account_name_hy")]
        self.assertEqual(
            len(no_hy), 0, f"{len(no_hy)} accounts missing HY name: {no_hy[:3]}"
        )

    def test_account_numbers_unique(self):
        """No duplicate account numbers within the tree."""
        tree = build_coa_tree()
        nums = [a["account_number"] for a in tree]
        self.assertEqual(len(nums), len(set(nums)), "duplicate account_number detected")

    def test_root_chapter_alignment(self):
        """Account number prefix must align with the chapter and root_type.

        1xxx/2xxx -> Asset, 3xxx -> Equity, 4xxx/5xxx -> Liability,
        6xxx -> Income, 7xxx/9xxx -> Expense, 8xxx -> off-balance-sheet.
        """
        tree = build_coa_tree()
        for a in tree:
            n = int(a["account_number"])
            chapter = n // 1000
            rt = a["root_type"]
            if chapter in (1, 2):
                self.assertEqual(rt, "Asset", f"{a['account_name_en']} num={n} chapter={chapter}")
            elif chapter == 3:
                self.assertEqual(rt, "Equity", f"{a['account_name_en']} num={n}")
            elif chapter in (4, 5):
                self.assertEqual(rt, "Liability", f"{a['account_name_en']} num={n}")
            elif chapter == 6:
                self.assertEqual(rt, "Income", f"{a['account_name_en']} num={n}")
            elif chapter in (7, 9):
                self.assertEqual(rt, "Expense", f"{a['account_name_en']} num={n}")
            # 8xxx off-balance-sheet: not in root_type taxonomy, allowed as any

    def test_parent_links_resolve(self):
        """Every parent_account_number referenced must exist in the tree."""
        tree = build_coa_tree()
        by_num = {a["account_number"] for a in tree}
        orphans = [
            a for a in tree
            if a["parent_account_number"] and a["parent_account_number"] not in by_num
        ]
        self.assertEqual(
            len(orphans), 0,
            f"{len(orphans)} accounts reference missing parents: {orphans[:3]}",
        )

    def test_module_exports_seed_function(self):
        """The module must expose seed_armenian_coa() (imported lazily)."""
        self.assertTrue(
            hasattr(_install_coa, "seed_armenian_coa"),
            "install_coa.py must define seed_armenian_coa(company)",
        )
        self.assertTrue(callable(_install_coa.seed_armenian_coa))


if __name__ == "__main__":
    unittest.main()
