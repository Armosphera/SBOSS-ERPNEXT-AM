"""
Tests for tools/swarm/codegen-task.py

Run with: python -m pytest tools/swarm/tests/test_codegen.py -v
Or:       python tools/swarm/tests/run_codegen_tests.py  (no pytest dep)

The codegen tool reads the master plan from
~/.hermes/plans/2026-06-24_142129-erpnext-armenia-uae-localization.md
and writes one .orchestration/tasks/T-ID.md per task row it finds.
"""
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Add tools/swarm/ to path so we can import the module
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # tools/swarm/

import codegen_task as ct  # noqa: E402


SAMPLE_PLAN = """\
# Test plan

Some prose.

### W0: Foundation

| T-ID | Title | Est | Ver | Deps |
|---|---|---|---|---|
| **W0-T01** | Create monorepo | 0.5h | `gh repo view` | — |
| **W0-T02** | Add AGENTS.md | 1h | file exists, 200+ lines | T01 |

### W1: Armenia

#### W1.a — Setup

| T-ID | Title | Est | Ver |
|---|---|---|---|
| **W1-T01** | Custom DocType `AM Company Setup` | 2h | doctype in desk |
"""


class TestParseTaskRow(unittest.TestCase):
    def test_parses_five_column_row(self):
        row = "| **W0-T01** | Create monorepo | 0.5h | `gh repo view` | — |"
        result = ct.parse_task_row(row)
        self.assertIsNotNone(result)
        self.assertEqual(result.id, "W0-T01")
        self.assertEqual(result.title, "Create monorepo")
        self.assertEqual(result.est, "0.5h")
        self.assertEqual(result.ver, "`gh repo view`")
        self.assertEqual(result.deps, "—")

    def test_parses_four_column_row(self):
        row = "| **W1-T01** | Custom DocType `AM Company Setup` | 2h | doctype in desk |"
        result = ct.parse_task_row(row)
        self.assertIsNotNone(result)
        self.assertEqual(result.id, "W1-T01")
        self.assertEqual(result.title, "Custom DocType `AM Company Setup`")
        self.assertEqual(result.est, "2h")
        self.assertEqual(result.ver, "doctype in desk")
        self.assertEqual(result.deps, "")

    def test_ignores_non_task_row(self):
        self.assertIsNone(ct.parse_task_row("| T-ID | Title | Est | Ver |"))
        self.assertIsNone(ct.parse_task_row("|---|---|---|---|"))
        self.assertIsNone(ct.parse_task_row("| **W0** | not a task | 1h | x |"))  # no -T?? suffix

    def test_ignores_bold_marker_in_id(self):
        # `**W0-T01**` should be cleaned to `W0-T01`
        row = "| **W2.a-T05** | Title | 1h | ver |"
        result = ct.parse_task_row(row)
        self.assertEqual(result.id, "W2.a-T05")  # dotted sub-workstream IDs supported


class TestParsePlan(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.plan_path = Path(self.tmpdir.name) / "plan.md"
        self.plan_path.write_text(SAMPLE_PLAN, encoding="utf-8")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_finds_all_task_rows(self):
        tasks = ct.parse_plan(self.plan_path)
        ids = [t.id for t in tasks]
        self.assertIn("W0-T01", ids)
        self.assertIn("W0-T02", ids)
        self.assertIn("W1-T01", ids)
        self.assertEqual(len(tasks), 3)

    def test_workstream_inferred_from_id(self):
        tasks = ct.parse_plan(self.plan_path)
        by_id = {t.id: t for t in tasks}
        self.assertEqual(by_id["W0-T01"].workstream, "W0")
        self.assertEqual(by_id["W0-T02"].workstream, "W0")
        self.assertEqual(by_id["W1-T01"].workstream, "W1.a")  # dotted form

    def test_title_preserves_inner_backticks(self):
        # Inner backticks are markdown code formatting and should be preserved
        # so the rendered task file shows `AM Company Setup` in code style.
        tasks = ct.parse_plan(self.plan_path)
        by_id = {t.id: t for t in tasks}
        self.assertEqual(by_id["W1-T01"].title, "Custom DocType `AM Company Setup`")

    def test_deps_split_on_comma(self):
        tasks = ct.parse_plan(self.plan_path)
        by_id = {t.id: t for t in tasks}
        # W0-T02 has deps "T01" — single dep
        self.assertEqual(by_id["W0-T02"].deps_list, ["T01"])


class TestRenderTaskFile(unittest.TestCase):
    def test_renders_well_formed_markdown(self):
        task = ct.Task(
            id="W1-T01",
            workstream="W1.a",
            title="Custom DocType AM Company Setup",
            est="2h",
            ver="doctype in desk",
            deps="W0-T10",
        )
        md = ct.render_task_file(task)
        # Required sections
        for header in ("# W1-T01:", "**Workstream:**", "**Branch prefix:**",
                       "**Estimated effort:**", "**Depends on:**",
                       "## Goal", "## Files to create/modify",
                       "## TDD cycle", "## Verification",
                       "## Pitfalls", "## References"):
            self.assertIn(header, md, f"missing section: {header}")
        # Branch prefix
        self.assertIn("`feat/am/`", md)  # W1.a maps to feat/am/


class TestBranchPrefixMapping(unittest.TestCase):
    def test_w1_uses_feat_am(self):
        self.assertEqual(ct.branch_prefix_for("W1"), "feat/am/")

    def test_w2_uses_feat_uae(self):
        self.assertEqual(ct.branch_prefix_for("W2"), "feat/uae/")

    def test_w3_uses_feat_ai(self):
        self.assertEqual(ct.branch_prefix_for("W3"), "feat/ai/")

    def test_w4_uses_feat_libs(self):
        self.assertEqual(ct.branch_prefix_for("W4"), "feat/libs/")

    def test_w5_uses_ci(self):
        self.assertEqual(ct.branch_prefix_for("W5"), "ci/")

    def test_w6_uses_chore(self):
        self.assertEqual(ct.branch_prefix_for("W6"), "chore/")

    def test_w7_uses_docs(self):
        self.assertEqual(ct.branch_prefix_for("W7"), "docs/")

    def test_w8_uses_chore(self):
        self.assertEqual(ct.branch_prefix_for("W8"), "chore/")

    def test_w0_uses_chore(self):
        self.assertEqual(ct.branch_prefix_for("W0"), "chore/")


class TestCodegenEndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.plan_path = Path(self.tmpdir.name) / "plan.md"
        self.plan_path.write_text(SAMPLE_PLAN, encoding="utf-8")
        self.tasks_dir = Path(self.tmpdir.name) / "tasks"
        self.tasks_dir.mkdir()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_codegen_writes_files(self):
        written = ct.codegen(self.plan_path, self.tasks_dir, force=True)
        self.assertEqual(len(written), 3)
        self.assertTrue((self.tasks_dir / "W0-T01.md").exists())
        self.assertTrue((self.tasks_dir / "W0-T02.md").exists())
        self.assertTrue((self.tasks_dir / "W1-T01.md").exists())

    def test_codegen_idempotent(self):
        """Running twice produces the same files (no drift)."""
        ct.codegen(self.plan_path, self.tasks_dir, force=True)
        first = {p.name: p.read_text(encoding="utf-8")
                 for p in self.tasks_dir.glob("*.md")}
        ct.codegen(self.plan_path, self.tasks_dir, force=True)
        second = {p.name: p.read_text(encoding="utf-8")
                  for p in self.tasks_dir.glob("*.md")}
        self.assertEqual(first, second)

    def test_codegen_skips_existing_without_force(self):
        ct.codegen(self.plan_path, self.tasks_dir, force=True)
        # Modify one file to mark it
        target = self.tasks_dir / "W0-T01.md"
        target.write_text("HUMAN EDITED\n", encoding="utf-8")
        # Run again without --force: file should be preserved
        ct.codegen(self.plan_path, self.tasks_dir, force=False)
        self.assertEqual(target.read_text(encoding="utf-8"), "HUMAN EDITED\n")

    def test_codegen_force_overwrites(self):
        ct.codegen(self.plan_path, self.tasks_dir, force=True)
        target = self.tasks_dir / "W0-T01.md"
        target.write_text("HUMAN EDITED\n", encoding="utf-8")
        ct.codegen(self.plan_path, self.tasks_dir, force=True)
        self.assertNotEqual(target.read_text(encoding="utf-8"), "HUMAN EDITED\n")
        self.assertIn("# W0-T01:", target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
