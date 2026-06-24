"""
codegen-task.py — generate `.orchestration/tasks/T-ID.md` files from the
master plan at ~/.hermes/plans/2026-06-24_142129-erpnext-armenia-uae-localization.md.

This is W8-T11 in the swarm plan.

Subcommands:
    codegen [--plan PATH] [--out DIR] [--force]   Generate task files
    sync-state [--state PATH] [--tasks-dir DIR]   Add new task entries to state.json
    diff [--plan PATH] [--tasks-dir DIR]          Show what would change
    validate                                       Verify all task files are valid
    stats                                          Print counts

Idempotency:
    By default, files that exist are preserved (assume a human edited them).
    Pass --force to overwrite.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable

# Plan location: conventionally ~/.hermes/plans/<timestamp>-<slug>.md
# Allow override via --plan
DEFAULT_PLAN = Path.home() / ".hermes" / "plans" / "2026-06-24_142129-erpnext-armenia-uae-localization.md"
DEFAULT_TASKS_DIR = Path(".orchestration") / "tasks"
DEFAULT_STATE = Path(".orchestration") / "state.json"

# Branch prefix mapping: workstream -> branch prefix
# (matches the workstream ownership declared in docs/architecture.md)
BRANCH_PREFIXES = {
    "W0": "chore/",
    "W1": "feat/am/",
    "W2": "feat/uae/",
    "W3": "feat/ai/",
    "W4": "feat/libs/",
    "W5": "ci/",
    "W6": "chore/",
    "W7": "docs/",
    "W8": "chore/",
}

# Display name for each workstream
WORKSTREAM_NAMES = {
    "W0": "Foundation",
    "W1": "Armenia Localization",
    "W2": "UAE Localization",
    "W3": "AI / Local LLM",
    "W4": "Shared Libraries",
    "W5": "CI / Infrastructure",
    "W6": "Upstream Sync",
    "W7": "Documentation",
    "W8": "Swarm / AI Agent Integration",
}

# ID pattern: W?, optionally W?.letter, then -T??
TASK_ID_RE = re.compile(r"\*?\*?(W\d+(?:\.[a-z])?-T\d+)\*?\*?")
TABLE_HEADER_RE = re.compile(r"\|\s*T-ID\s*\|", re.IGNORECASE)
TABLE_SEPARATOR_RE = re.compile(r"^\|[\s\-:|]+\|\s*$")


@dataclass
class Task:
    id: str
    workstream: str
    title: str
    est: str
    ver: str
    deps: str = ""
    section: str = ""  # "### W1.a — Setup Wizard & COA" etc.

    @property
    def deps_list(self) -> list[str]:
        if not self.deps or self.deps == "—":
            return []
        # Split on comma, strip "T" prefix redundancy, trim
        return [d.strip() for d in self.deps.split(",") if d.strip()]

    def to_dict(self) -> dict:
        return asdict(self)


# ---------- Plan parser ----------

def _strip_md(s: str) -> str:
    """Strip leading/trailing **bold** markers; preserve all backticks.

    Inner backticks are markdown code formatting and must be preserved so
    the rendered task file shows `code` in code style.
    `**Title**` -> "Title"
    `**Title with \`code\`` -> "Title with \`code\`"
    """
    s = s.strip()
    # Strip leading ** or * (bold markers)
    while s.startswith("**") or s.startswith("*"):
        s = s[1:].lstrip()
    # Strip trailing ** or *
    while s.endswith("**") or s.endswith("*"):
        s = s[:-1].rstrip()
    return s


def parse_task_row(line: str, current_section: str = "") -> Task | None:
    """Parse a single markdown table row into a Task, or return None if it
    is not a task row.
    """
    # Must start with `|` and have a task-id in the first cell
    cells = [c.strip() for c in line.split("|")]
    # split("|") on a row like `| a | b | c |` gives ['', 'a', 'b', 'c', '']
    if len(cells) < 4:
        return None
    if not cells[0] and len(cells) >= 2:
        cells = cells[1:]
    # First non-empty cell is the id
    first = cells[0] if cells else ""
    m = TASK_ID_RE.search(first)
    if not m:
        return None
    task_id = m.group(1)

    # Extract remaining cells (4 or 5 expected)
    rest = [c for c in cells[1:] if c != ""]
    if len(rest) < 3:
        return None
    title = _strip_md(rest[0])
    est = _strip_md(rest[1]) if len(rest) > 1 else ""
    ver = _strip_md(rest[2]) if len(rest) > 2 else ""
    deps = _strip_md(rest[3]) if len(rest) > 3 else ""

    # Infer workstream:
    #   If section is a W?.x subsection (e.g. "W1.a — Setup Wizard & COA"), use that.
    #   Otherwise fall back to the workstream implied by the task ID.
    section_match = re.match(r"(W\d+\.[a-z])\b", current_section)
    if section_match:
        workstream = section_match.group(1)
    else:
        ws_match = re.match(r"(W\d+)-T\d+", task_id)
        workstream = ws_match.group(1) if ws_match else "W?"

    return Task(
        id=task_id,
        workstream=workstream,
        title=title,
        est=est,
        ver=ver,
        deps=deps,
    )


def parse_plan(plan_path: Path) -> list[Task]:
    """Parse the plan and return all Task objects in document order."""
    if not plan_path.exists():
        raise FileNotFoundError(f"Plan not found: {plan_path}")
    content = plan_path.read_text(encoding="utf-8")

    tasks: list[Task] = []
    current_section = ""
    in_table = False
    in_header = False

    for line in content.splitlines():
        stripped = line.strip()

        # Track current section heading (### W1.a — ... or #### W1.b — ...)
        if stripped.startswith("#"):
            current_section = stripped.lstrip("#").strip()
            in_table = False
            in_header = False
            continue

        # Detect table start
        if TABLE_HEADER_RE.search(stripped):
            in_table = True
            in_header = True
            continue
        if in_header and TABLE_SEPARATOR_RE.match(stripped):
            in_header = False
            continue
        if not stripped.startswith("|"):
            in_table = False
            in_header = False
            continue

        # We're in a data row of a task table
        if in_table and not in_header:
            task = parse_task_row(stripped, current_section=current_section)
            if task is not None:
                task.section = current_section
                tasks.append(task)

    return tasks


# ---------- Branch prefix mapping ----------

def branch_prefix_for(workstream: str) -> str:
    """Return the git branch prefix for a given workstream."""
    top = re.match(r"(W\d+)", workstream)
    key = top.group(1) if top else workstream
    return BRANCH_PREFIXES.get(key, "feat/")


def workstream_name(workstream: str) -> str:
    """Return a human-readable workstream name."""
    top = re.match(r"(W\d+)", workstream)
    key = top.group(1) if top else workstream
    return WORKSTREAM_NAMES.get(key, workstream)


# ---------- Template ----------

TEMPLATE = """\
# {task_id}: {title}

**Workstream:** {workstream} ({ws_name})
**Branch prefix:** `{branch_prefix}`
**Estimated effort:** {est}
**Depends on:** {deps_display}
**Owner role:** TBD
**Difficulty:** TBD

## Goal
{title}.

## Files to create/modify
- TBD by agent (derived from goal above; agent should add concrete paths in a child commit)

## Contracts to respect
- **Contract A** (DocType prefix): any DocType created MUST be prefixed `AM ` (Armenia), `AE ` (UAE), or `AIL ` (AI layer).
- **Contract B** (AI tool whitelist): any AI tool registered MUST be in the `AIL Tool Whitelist` (see `docs/architecture.md#contract-b`).
- **Contract C** (shared lib API): use `frappe_localization_core` and `frappe_payroll_engine` public APIs; do not import private internals.
- **Upstream-survivability**: never edit upstream ERPNext/Frappe/HRMS files. Link via public API.

## TDD cycle

### Step 1 — Write failing test(s)
Write the test in the appropriate `tests/` directory of the app. Use `FrappeTestCase` for app tests, plain `unittest` for lib tests.

### Step 2 — Run test, see it fail
```bash
bench --site test.localhost run-tests --app <APP> --module <MODULE>
```
Expected: failure with the specific reason described in the task.

### Step 3 — Implement minimal code
Write the smallest change that makes the test pass.

### Step 4 — Run test, see it pass
Same command as Step 2. Expected: 0 failures.

### Step 5 — Refactor
Clean up while keeping tests green.

### Step 6 — Commit (single-quote if backticks)
```bash
git checkout -b {branch_prefix}{task_id_lower}
git add <files>
git commit -m 'type(scope): subject'
git push -u origin HEAD
gh pr create --title "<title>" --body-file .github/PULL_REQUEST_TEMPLATE.md
python3 tools/swarm/swarm.py release-task {task_id} --pr <PR_NUMBER>
```

## Verification
{ver}

## Pitfalls
- See `AGENTS.md` for the 9 ground rules (TDD, no upstream edits, single-quote backticks, etc.)
- See `docs/architecture.md` for frozen contracts.

## References
- `.hermes/plans/2026-06-24_142129-erpnext-armenia-uae-localization.md` §{section}
- `AGENTS.md`
- `docs/architecture.md`

---

*Auto-generated by `tools/swarm/codegen-task.py` (W8-T11). Human edits are preserved on re-run unless `--force` is passed.*
"""


def render_task_file(task: Task) -> str:
    deps_display = task.deps if task.deps else "—"
    return TEMPLATE.format(
        task_id=task.id,
        task_id_lower=task.id.lower(),
        title=task.title,
        workstream=task.workstream,
        ws_name=workstream_name(task.workstream),
        branch_prefix=branch_prefix_for(task.workstream),
        est=task.est,
        deps_display=deps_display,
        ver=task.ver,
        section=task.section or "(see plan)",
    )


# ---------- Codegen ----------

@dataclass
class CodegenResult:
    written: list[Path] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.written) + len(self.skipped) + len(self.errors)


def codegen(plan_path: Path, tasks_dir: Path, force: bool = False) -> CodegenResult:
    """Generate task files from the plan. Idempotent: existing files are
    skipped unless force=True.
    """
    tasks_dir.mkdir(parents=True, exist_ok=True)
    tasks = parse_plan(plan_path)
    result = CodegenResult()
    seen_ids: set[str] = set()

    for task in tasks:
        if task.id in seen_ids:
            continue   # de-duplicate (plan has rows referenced multiple places)
        seen_ids.add(task.id)

        target = tasks_dir / f"{task.id}.md"
        if target.exists() and not force:
            result.skipped.append(target)
            continue

        try:
            target.write_text(render_task_file(task), encoding="utf-8")
            result.written.append(target)
        except Exception as e:
            result.errors.append(f"{task.id}: {e}")

    return result


# ---------- State sync ----------

def sync_state(tasks_dir: Path, state_path: Path) -> int:
    """Add any new task IDs to state.json with status='pending'. Returns
    the number of new tasks added.
    """
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    else:
        state = {"version": "0.0.0", "tasks": {}}
    if "tasks" not in state:
        state["tasks"] = {}

    added = 0
    for task_file in sorted(tasks_dir.glob("*.md")):
        task_id = task_file.stem
        if task_id not in state["tasks"]:
            state["tasks"][task_id] = {
                "id": task_id,
                "status": "pending",
                "owner": None,
                "claimed_at": None,
                "branch": None,
                "pr": None,
                "commit": None,
                "completed_at": None,
            }
            added += 1

    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return added


# ---------- Validate ----------

def validate(tasks_dir: Path) -> tuple[int, list[str]]:
    """Verify all task files parse correctly. Returns (ok_count, errors)."""
    ok = 0
    errors: list[str] = []
    for task_file in sorted(tasks_dir.glob("*.md")):
        try:
            content = task_file.read_text(encoding="utf-8")
            if not content.startswith(f"# {task_file.stem}:"):
                errors.append(f"{task_file.name}: title does not start with '# {task_file.stem}:'")
                continue
            for required in ("**Workstream:**", "**Branch prefix:**",
                             "**Estimated effort:**", "## Goal",
                             "## Verification"):
                if required not in content:
                    errors.append(f"{task_file.name}: missing section '{required}'")
                    break
            else:
                ok += 1
        except Exception as e:
            errors.append(f"{task_file.name}: {e}")
    return ok, errors


# ---------- Stats ----------

def stats(tasks_dir: Path) -> dict[str, int]:
    """Return task count by workstream."""
    counts: dict[str, int] = {}
    for task_file in sorted(tasks_dir.glob("*.md")):
        m = re.match(r"(W\d+(?:\.[a-z])?)-", task_file.stem)
        ws = m.group(1) if m else "?"
        counts[ws] = counts.get(ws, 0) + 1
    return counts


# ---------- CLI ----------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="codegen-task.py — generate task files from the master plan (W8-T11)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_codegen = sub.add_parser("codegen", help="generate task files")
    p_codegen.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    p_codegen.add_argument("--out", type=Path, default=DEFAULT_TASKS_DIR)
    p_codegen.add_argument("--force", action="store_true",
                           help="overwrite existing files (default: preserve human edits)")
    p_codegen.set_defaults(func=lambda a: _run_codegen(a))

    p_diff = sub.add_parser("diff", help="show what codegen would change")
    p_diff.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    p_diff.add_argument("--out", type=Path, default=DEFAULT_TASKS_DIR)
    p_diff.set_defaults(func=lambda a: _run_diff(a))

    p_sync = sub.add_parser("sync-state", help="add new task IDs to state.json")
    p_sync.add_argument("--tasks-dir", type=Path, default=DEFAULT_TASKS_DIR)
    p_sync.add_argument("--state", type=Path, default=DEFAULT_STATE)
    p_sync.set_defaults(func=lambda a: _run_sync(a))

    p_val = sub.add_parser("validate", help="validate existing task files")
    p_val.add_argument("--tasks-dir", type=Path, default=DEFAULT_TASKS_DIR)
    p_val.set_defaults(func=lambda a: _run_validate(a))

    p_stats = sub.add_parser("stats", help="print task counts by workstream")
    p_stats.add_argument("--tasks-dir", type=Path, default=DEFAULT_TASKS_DIR)
    p_stats.set_defaults(func=lambda a: _run_stats(a))

    args = parser.parse_args()
    return args.func(args)


def _run_codegen(args: argparse.Namespace) -> int:
    if not args.plan.exists():
        print(f"ERROR: plan not found: {args.plan}", file=sys.stderr)
        return 2
    result = codegen(args.plan, args.out, force=args.force)
    print(f"OK: wrote {len(result.written)}, skipped {len(result.skipped)}, errors {len(result.errors)}")
    for p in result.written:
        print(f"  + {p}")
    for p in result.skipped:
        print(f"  = {p} (preserved; pass --force to overwrite)")
    for e in result.errors:
        print(f"  ! {e}", file=sys.stderr)
    return 0 if not result.errors else 1


def _run_diff(args: argparse.Namespace) -> int:
    if not args.plan.exists():
        print(f"ERROR: plan not found: {args.plan}", file=sys.stderr)
        return 2
    result = codegen(args.plan, args.out, force=False)
    print(f"Would write {len(result.written)} new files; preserve {len(result.skipped)} existing")
    for p in result.written:
        print(f"  + {p}")
    return 0


def _run_sync(args: argparse.Namespace) -> int:
    if not args.tasks_dir.exists():
        print(f"ERROR: tasks dir not found: {args.tasks_dir}", file=sys.stderr)
        return 2
    added = sync_state(args.tasks_dir, args.state)
    print(f"OK: added {added} new task(s) to {args.state}")
    return 0


def _run_validate(args: argparse.Namespace) -> int:
    if not args.tasks_dir.exists():
        print(f"ERROR: tasks dir not found: {args.tasks_dir}", file=sys.stderr)
        return 2
    ok, errors = validate(args.tasks_dir)
    print(f"OK: {ok} task file(s) valid")
    for e in errors:
        print(f"  ! {e}", file=sys.stderr)
    return 0 if not errors else 1


def _run_stats(args: argparse.Namespace) -> int:
    if not args.tasks_dir.exists():
        print(f"ERROR: tasks dir not found: {args.tasks_dir}", file=sys.stderr)
        return 2
    counts = stats(args.tasks_dir)
    total = sum(counts.values())
    print(f"Total: {total} task files")
    for ws in sorted(counts):
        print(f"  {ws}: {counts[ws]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
