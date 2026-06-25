"""
Tests for tools/swarm/verify-isolation.py

Run with: python tools/swarm/tests/run_verify_isolation_tests.py

The wrapper script `tools/swarm/verify-isolation.py` is a thin dispatch layer
on top of `swarm.py` (which owns the real logic — `glob_overlap` and
`parse_task_globs`). These tests target the underlying logic so that any
future refactor of `swarm.py` keeps the public contract intact.

What we test:
- `glob_overlap(a, b)` — pairwise file-glob overlap detection.
- `parse_task_globs(path)` — extracts the "## Files to create/modify" list
  from a task markdown file, dropping trailing "(new)" / "(modify)" notes.
- End-to-end: invoking the wrapper as a subprocess must exit 0 when there
  are no conflicts and non-zero with a clear message when there are.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

# Add tools/swarm/ to sys.path so `import swarm` resolves.
HERE = Path(__file__).resolve().parent
SWARM_DIR = HERE.parent
sys.path.insert(0, str(SWARM_DIR))

import swarm  # noqa: E402


class TestGlobOverlap(unittest.TestCase):
    """Pure-function tests for `glob_overlap`."""

    def test_identical_paths_overlap(self):
        self.assertTrue(swarm.glob_overlap("apps/frappe_armenia/coa.py",
                                           "apps/frappe_armenia/coa.py"))

    def test_parent_directory_overlaps_child_file(self):
        self.assertTrue(swarm.glob_overlap("apps/frappe_armenia/",
                                           "apps/frappe_armenia/coa/foo.py"))

    def test_child_file_overlaps_parent_directory(self):
        self.assertTrue(swarm.glob_overlap("apps/frappe_armenia/coa/foo.py",
                                           "apps/frappe_armenia/"))

    def test_same_two_level_prefix_overlaps(self):
        # Conservative heuristic: any two paths sharing the first 2 segments
        # count as overlapping (would otherwise let two agents silently
        # collide inside apps/frappe_armenia/*).
        self.assertTrue(swarm.glob_overlap("apps/frappe_armenia/coa.py",
                                           "apps/frappe_armenia/setup_wizard.py"))

    def test_disjoint_top_level_paths_do_not_overlap(self):
        self.assertFalse(swarm.glob_overlap("tools/swarm/foo.py",
                                            "apps/frappe_armenia/foo.py"))

    def test_sibling_subdirs_under_shared_root_do_not_overlap(self):
        # apps/frappe_armenia vs apps/frappe_uae share "apps/" (1 segment)
        # but NOT the first two segments, so they don't collide.
        self.assertFalse(swarm.glob_overlap("apps/frappe_armenia/",
                                            "apps/frappe_uae/"))

    def test_leading_dot_slash_stripped(self):
        self.assertTrue(swarm.glob_overlap("./tools/swarm/foo.py",
                                           "tools/swarm/foo.py"))


class TestParseTaskGlobs(unittest.TestCase):
    """Tests for `parse_task_globs` — extracts the Files section of a task file."""

    def _write_task(self, body: str) -> Path:
        # Write into a tempdir that mirrors .orchestration/tasks/<T-ID>.md
        tmp = Path(tempfile.mkdtemp())
        task_file = tmp / "W-TEST.md"
        task_file.write_text(textwrap.dedent(body), encoding="utf-8")
        return task_file

    def test_extracts_single_file_under_files_heading(self):
        task_file = self._write_task("""\
            # W-TEST

            ## Files to create/modify
            - `tools/swarm/verify-isolation.py` (new)

            ## Verification
            `python tools/swarm/verify-isolation.py` exits 0
        """)
        globs = swarm.parse_task_globs(task_file)
        self.assertEqual(globs, ["tools/swarm/verify-isolation.py"])

    def test_extracts_multiple_files_and_drops_trailing_notes(self):
        task_file = self._write_task("""\
            ## Files to create/modify
            - `tools/swarm/verify-isolation.py` (new)
            - `tools/swarm/tests/test_verify_isolation.py` (new)

            ## Verification
        """)
        globs = swarm.parse_task_globs(task_file)
        self.assertEqual(
            globs,
            [
                "tools/swarm/verify-isolation.py",
                "tools/swarm/tests/test_verify_isolation.py",
            ],
        )

    def test_returns_empty_when_no_files_section(self):
        task_file = self._write_task("""\
            # W-TEST
            Goal: do a thing.
        """)
        self.assertEqual(swarm.parse_task_globs(task_file), [])

    def test_returns_empty_when_files_section_has_no_bullets(self):
        task_file = self._write_task("""\
            ## Files to create/modify
            TBD by agent.

            ## Verification
        """)
        self.assertEqual(swarm.parse_task_globs(task_file), [])

    def test_stops_at_next_heading(self):
        task_file = self._write_task("""\
            ## Files to create/modify
            - `tools/swarm/verify-isolation.py` (new)

            ## Verification
            - `python tools/swarm/verify-isolation.py` exits 0
        """)
        globs = swarm.parse_task_globs(task_file)
        self.assertEqual(globs, ["tools/swarm/verify-isolation.py"])

    def test_accepts_bold_files_label_variant(self):
        task_file = self._write_task("""\
            **Files:**
            - `tools/swarm/foo.py` (new)
        """)
        self.assertEqual(swarm.parse_task_globs(task_file), ["tools/swarm/foo.py"])


class TestWrapperEndToEnd(unittest.TestCase):
    """
    Run `tools/swarm/verify-isolation.py` as a subprocess against an
    isolated, synthetic state.json + tasks dir. This validates that the
    wrapper exists, is executable, and correctly delegates to swarm.py.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        # Build a minimal repo layout:
        #   <tmp>/tools/swarm/swarm.py  (importable as `swarm`)
        #   <tmp>/tools/swarm/verify-isolation.py  (the wrapper)
        #   <tmp>/.orchestration/state.json
        #   <tmp>/.orchestration/tasks/<T-ID>.md
        self.tools_dir = self.tmp / "tools" / "swarm"
        self.tools_dir.mkdir(parents=True)
        # Re-use the real swarm.py so we're testing the wrapper, not duplicating logic.
        real_swarm = SWARM_DIR / "swarm.py"
        (self.tools_dir / "swarm.py").write_bytes(real_swarm.read_bytes())
        # Copy the wrapper (or skip if not present — test still validates the rest).
        real_wrapper = SWARM_DIR / "verify-isolation.py"
        if real_wrapper.exists():
            (self.tools_dir / "verify-isolation.py").write_bytes(real_wrapper.read_bytes())

        self.orch = self.tmp / ".orchestration"
        self.orch.mkdir()
        self.tasks_dir = self.orch / "tasks"
        self.tasks_dir.mkdir()

    def _write_state(self, tasks: dict) -> None:
        (self.orch / "state.json").write_text(
            json.dumps({"tasks": tasks}, indent=2), encoding="utf-8"
        )

    def _write_task(self, task_id: str, body: str) -> Path:
        p = self.tasks_dir / f"{task_id}.md"
        p.write_text(textwrap.dedent(body), encoding="utf-8")
        return p

    def _run_wrapper(self, task_id: str) -> subprocess.CompletedProcess:
        wrapper = self.tools_dir / "verify-isolation.py"
        if not wrapper.exists():
            self.skipTest("verify-isolation.py not yet created (wrapper is the deliverable)")
        return subprocess.run(
            [sys.executable, str(wrapper), task_id],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
        )

    def test_wrapper_exits_zero_when_no_other_active_tasks(self):
        # First the wrapper needs to exist; this guards the RED phase.
        self._write_task("W-X", """\
            ## Files to create/modify
            - `tools/swarm/verify-isolation.py` (new)
        """)
        self._write_state({
            "W-X": {"id": "W-X", "status": "claimed", "owner": "agent-W0a"},
        })
        result = self._run_wrapper("W-X")
        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_wrapper_exits_nonzero_on_glob_overlap(self):
        self._write_task("W-A", """\
            ## Files to create/modify
            - `tools/swarm/verify-isolation.py` (new)
        """)
        self._write_task("W-B", """\
            ## Files to create/modify
            - `tools/swarm/verify-isolation.py` (new)
        """)
        self._write_state({
            "W-A": {"id": "W-A", "status": "claimed", "owner": "agent-A"},
            "W-B": {"id": "W-B", "status": "claimed", "owner": "agent-B"},
        })
        result = self._run_wrapper("W-A")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("W-B", result.stderr)
        self.assertIn("overlap", result.stderr.lower())

    def test_wrapper_exits_zero_for_disjoint_globs(self):
        self._write_task("W-A", """\
            ## Files to create/modify
            - `apps/frappe_armenia/coa.py` (new)
        """)
        self._write_task("W-B", """\
            ## Files to create/modify
            - `apps/frappe_uae/coa.py` (new)
        """)
        self._write_state({
            "W-A": {"id": "W-A", "status": "claimed", "owner": "agent-A"},
            "W-B": {"id": "W-B", "status": "claimed", "owner": "agent-B"},
        })
        result = self._run_wrapper("W-A")
        self.assertEqual(result.returncode, 0, msg=result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
