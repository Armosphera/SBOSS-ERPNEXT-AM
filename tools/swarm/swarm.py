#!/usr/bin/env python3
"""
Swarm CLI for SBOSS ERPNEXT AM.

Subcommands:
    claim-task.py <T-ID>                  -- atomically claim a task
    release-task.py <T-ID> --pr <N>        -- mark a task done
    verify-isolation.py <T-ID>            -- check no overlapping globs
    validate-state.py                     -- check state.json schema
    codegen-task.py --roadmap              -- regenerate task files from plan
"""
import argparse
import contextlib
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
STATE_PATH = ROOT / ".orchestration" / "state.json"
TASKS_DIR = ROOT / ".orchestration" / "tasks"
PLAN_PATH = ROOT / ".hermes" / "plans" / "2026-06-24_142129-erpnext-armenia-uae-localization.md"

VALID_STATUSES = {"pending", "claimed", "in_progress", "in_review", "done", "blocked", "cancelled"}


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {"version": "0.0.0", "tasks": {}}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    state["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


@contextlib.contextmanager
def atomic_lock(target_path: Path):
    """Context manager that uses O_EXCL lock file for atomic claim."""
    lock_path = target_path.with_suffix(target_path.suffix + ".lock")
    fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    try:
        yield fd
    finally:
        os.close(fd)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def cmd_claim(args: argparse.Namespace) -> int:
    task_id = args.task_id
    owner = args.owner or os.environ.get("USER", "unknown")
    task_file = TASKS_DIR / f"{task_id}.md"
    if not task_file.exists():
        print(f"ERROR: task file {task_file} not found", file=sys.stderr)
        return 2

    state = load_state()
    if task_id in state["tasks"] and state["tasks"][task_id]["status"] in ("claimed", "in_progress", "in_review"):
        print(f"ERROR: task {task_id} already claimed by {state['tasks'][task_id].get('owner')}", file=sys.stderr)
        return 3

    try:
        with atomic_lock(STATE_PATH):
            state = load_state()  # re-read under lock
            state["tasks"][task_id] = {
                "id": task_id,
                "status": "claimed",
                "owner": owner,
                "claimed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "branch": None,
                "pr": None,
                "commit": None,
                "completed_at": None,
            }
            save_state(state)
    except FileExistsError:
        print(f"ERROR: state.json is locked by another agent; retry in 5s", file=sys.stderr)
        return 4

    print(f"OK: claimed {task_id} for {owner}")
    print(f"Next: read {task_file}")
    return 0


def cmd_release(args: argparse.Namespace) -> int:
    task_id = args.task_id
    state = load_state()
    if task_id not in state["tasks"]:
        print(f"ERROR: task {task_id} not in state.json", file=sys.stderr)
        return 2
    task = state["tasks"][task_id]
    task["status"] = "done"
    task["pr"] = args.pr
    task["completed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save_state(state)
    print(f"OK: released {task_id} (PR #{args.pr})")
    return 0


def parse_task_globs(task_file: Path) -> list[str]:
    """Extract file globs from a task file.

    Recognizes the AGENTS.md convention:
        ## Files to create/modify
        - `path/to/file.py` (new)
        - `path/to/other.py` (modify)
    Also accepts:
        **Files:** ...
    """
    globs = []
    in_files = False
    lines = task_file.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        low = stripped.lower()
        # Match headings or bold labels that start a "Files" section
        if (low.startswith("## files") or low.startswith("**files") or
            low.startswith("files:") or low.startswith("**files:")):
            in_files = True
            continue
        if in_files:
            if not stripped:
                # blank line — keep going
                continue
            if stripped.startswith("#"):
                # next heading — stop
                in_files = False
                continue
            if stripped.startswith("- "):
                m = re.search(r"`([^`]+)`", stripped)
                if m:
                    glob = m.group(1).strip()
                    # Drop trailing inline notes like "(new)" or "(modify)"
                    glob = re.sub(r"\s+\([^)]+\)\s*$", "", glob)
                    globs.append(glob)
            elif not stripped.startswith("-"):
                # Non-bullet, non-heading content ends the section
                in_files = False
    return globs


def cmd_verify_isolation(args: argparse.Namespace) -> int:
    task_id = args.task_id
    task_file = TASKS_DIR / f"{task_id}.md"
    if not task_file.exists():
        print(f"ERROR: task file {task_file} not found", file=sys.stderr)
        return 2
    my_globs = parse_task_globs(task_file)
    if not my_globs:
        print(f"OK: {task_id} claims no file globs (no isolation check needed)")
        return 0

    state = load_state()
    active = {tid: t for tid, t in state["tasks"].items()
              if t["status"] in ("claimed", "in_progress", "in_review") and tid != task_id}
    if not active:
        print(f"OK: {task_id} — no other active tasks; isolation verified")
        return 0

    conflicts = []
    for other_id in active:
        other_file = TASKS_DIR / f"{other_id}.md"
        if not other_file.exists():
            continue
        other_globs = parse_task_globs(other_file)
        for g1 in my_globs:
            for g2 in other_globs:
                if glob_overlap(g1, g2):
                    conflicts.append((g1, other_id, g2))
    if conflicts:
        print(f"ERROR: {task_id} has overlapping globs with {len(set(c[1] for c in conflicts))} other task(s):", file=sys.stderr)
        for g1, other_id, g2 in conflicts:
            print(f"  {task_id} ({g1}) overlaps {other_id} ({g2})", file=sys.stderr)
        return 1
    print(f"OK: {task_id} — isolation verified across {len(active)} active task(s)")
    return 0


def glob_overlap(a: str, b: str) -> bool:
    """Check if two file paths overlap. Conservative: literal substring match on the directory."""
    a = a.lstrip("./")
    b = b.lstrip("./")
    if a == b:
        return True
    # If one is a parent of the other (e.g. apps/frappe_armenia/ vs apps/frappe_armenia/coa/file.py)
    if a.endswith("/") and b.startswith(a):
        return True
    if b.endswith("/") and a.startswith(b):
        return True
    # Same directory prefix of depth ≥ 2
    a_parts = a.split("/")
    b_parts = b.split("/")
    if len(a_parts) >= 2 and len(b_parts) >= 2 and a_parts[:2] == b_parts[:2]:
        return True
    return False


def cmd_validate_state(args: argparse.Namespace) -> int:
    try:
        state = load_state()
    except json.JSONDecodeError as e:
        print(f"ERROR: state.json is not valid JSON: {e}", file=sys.stderr)
        return 1
    for tid, t in state.get("tasks", {}).items():
        if tid != t.get("id"):
            print(f"ERROR: task id mismatch: key={tid} but id={t.get('id')}", file=sys.stderr)
            return 1
        if t.get("status") not in VALID_STATUSES:
            print(f"ERROR: task {tid} has invalid status: {t.get('status')}", file=sys.stderr)
            return 1
    print(f"OK: state.json valid ({len(state.get('tasks', {}))} tasks)")
    return 0


def cmd_codegen_roadmap(args: argparse.Namespace) -> int:
    """Stub: in W8-T11 this will scan the plan and regenerate .orchestration/tasks/*.md."""
    print("codegen-task.py: not yet implemented (W8-T11)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="SBOSS ERPNEXT AM swarm CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_claim = sub.add_parser("claim-task", help="atomically claim a task")
    p_claim.add_argument("task_id")
    p_claim.add_argument("--owner", help="owner identifier (default: $USER)")
    p_claim.set_defaults(func=cmd_claim)

    p_rel = sub.add_parser("release-task", help="mark a task done")
    p_rel.add_argument("task_id")
    p_rel.add_argument("--pr", type=int, required=True, help="PR number")
    p_rel.set_defaults(func=cmd_release)

    p_iso = sub.add_parser("verify-isolation", help="check no overlapping globs with other active tasks")
    p_iso.add_argument("task_id")
    p_iso.set_defaults(func=cmd_verify_isolation)

    p_val = sub.add_parser("validate-state", help="validate state.json schema")
    p_val.set_defaults(func=cmd_validate_state)

    p_codegen = sub.add_parser("codegen-roadmap", help="regenerate .orchestration/roadmap.md")
    p_codegen.set_defaults(func=cmd_codegen_roadmap)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
