#!/usr/bin/env bash
# Run a single swarm task end-to-end.
# Usage: tools/swarm/run-task.sh W1-T04
#
# Steps:
#   1. Read task file .orchestration/tasks/$TASK.md
#   2. Claim the task (tools/swarm/swarm.py claim-task)
#   3. Verify isolation
#   4. Create branch
#   5. (TDD cycle is performed by the agent in its own context)
#   6. After agent commits, this script pushes & opens the PR

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <TASK-ID> [--push]"
  exit 2
fi

TASK_ID="$1"
shift || true

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TASK_FILE="$REPO_ROOT/.orchestration/tasks/${TASK_ID}.md"
SWARM_CLI="$REPO_ROOT/tools/swarm/swarm.py"

cd "$REPO_ROOT"

if [[ ! -f "$TASK_FILE" ]]; then
  echo "ERROR: task file not found: $TASK_FILE"
  exit 1
fi

echo "==> Claiming task $TASK_ID"
python3 "$SWARM_CLI" claim-task "$TASK_ID" --owner "${USER:-unknown}"

echo "==> Verifying isolation"
python3 "$SWARM_CLI" verify-isolation "$TASK_ID"

# Extract workstream + suggested branch from task file
WORKSTREAM=$(grep -E '^\*\*Workstream:\*\*' "$TASK_FILE" | head -1 | sed 's/.*://' | awk '{print $1}')
SUGGESTED_BRANCH=$(grep -E '^\*\*Branch prefix:\*\*' "$TASK_FILE" | head -1 | sed -E 's/.*\*\*Branch prefix:\*\*[[:space:]]*//' | sed -E 's/`//g' | awk '{print $1}')

BRANCH="${SUGGESTED_BRANCH:-feat/}$(echo "$TASK_ID" | tr '[:upper:]' '[:lower:]')"
echo "==> Creating branch $BRANCH"
git fetch origin 2>/dev/null || true
git checkout -b main 2>/dev/null || git checkout main 2>/dev/null || true
git checkout -b "$BRANCH"

echo
echo "================================================================="
echo "  Task $TASK_ID is claimed, isolation verified, branch created."
echo "  Now perform the TDD cycle described in:"
echo "    $TASK_FILE"
echo
echo "  When tests pass, commit and push:"
echo "    git add <files>"
echo "    git commit -m 'type(scope): subject'   # single-quote if backticks"
echo "    git push -u origin HEAD"
echo
echo "  Then open a PR with:"
echo "    gh pr create --title '<title>' --body-file .github/PULL_REQUEST_TEMPLATE.md"
echo
echo "  Then release:"
echo "    python3 $SWARM_CLI release-task $TASK_ID --pr <PR_NUMBER>"
echo "================================================================="
