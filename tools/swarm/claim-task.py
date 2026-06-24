#!/usr/bin/env python3
"""Wrapper so `claim-task.py` (the name used in AGENTS.md) works as an alias."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from swarm import cmd_claim, cmd_release, cmd_verify_isolation, cmd_validate_state, cmd_codegen_roadmap
import argparse

if __name__ == "__main__":
    # Allow `python tools/swarm/claim-task.py TASK_ID --owner X`
    # to map to `swarm.py claim-task TASK_ID --owner X`
    if len(sys.argv) > 1 and sys.argv[0].endswith((".py", ".sh")):
        script_name = Path(sys.argv[0]).stem
        sys.argv = [sys.argv[0], script_name.replace("-", "_").replace("claim_task", "claim-task").replace("release_task", "release-task").replace("verify_isolation", "verify-isolation").replace("validate_state", "validate-state").replace("codegen_roadmap", "codegen-roadmap")] + sys.argv[1:]
    # Map the bash-style names to the python subcommand names
    name_map = {
        "claim-task.py": "claim-task",
        "release-task.py": "release-task",
        "verify-isolation.py": "verify-isolation",
        "validate-state.py": "validate-state",
        "codegen-task.py": "codegen-roadmap",
    }
    for fname, subcmd in name_map.items():
        if sys.argv[0].endswith(fname):
            sys.argv[0:1] = ["swarm.py", subcmd]
            break
    from swarm import main
    sys.exit(main())
