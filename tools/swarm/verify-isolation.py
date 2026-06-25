#!/usr/bin/env python3
"""
Wrapper so `verify-isolation.py` (the name used in AGENTS.md) works as an alias.

Usage:
    python3 tools/swarm/verify-isolation.py <T-ID>

The real implementation lives in `swarm.py` (cmd_verify_isolation), which reads
`.orchestration/state.json`, walks active tasks, parses each task file's
"## Files to create/modify" section, and reports any overlapping globs.

Exit codes (delegated from swarm.py):
    0  — no isolation conflicts, or this task declares no globs
    1  — overlapping globs with another active task (error printed to stderr)
    2  — task file not found (the task ID does not exist)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from swarm import main  # noqa: E402

if __name__ == "__main__":
    # Rewrite argv so swarm.main()'s argparse sees the right subcommand.
    # sys.argv[0] is replaced with a bare program name to avoid argparse
    # trying to interpret this wrapper's path.
    sys.argv = ["swarm.py", "verify-isolation"] + sys.argv[1:]
    sys.exit(main())
