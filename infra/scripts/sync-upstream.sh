#!/usr/bin/env bash
# Sync-upstream.sh — weekly ERPNext/Frappe/HRMS version tracking.
#
# Modes:
#   detect  — check if upstream has new tags; print "true"/"false" for $CHANGES
#   open-pr — open a draft PR to bump the pinned version
#   test    — run the test suite against the new upstream

set -euo pipefail

MODE="${1:-detect}"

# Upstreams we track
REPOS=(
  "frappe/frappe:15.3.0"
  "frappe/erpnext:15.3.0"
  "frappe/hrms:15.0.0"
)

CACHE_DIR="${HOME}/.cache/sboss-upstream-cache"
mkdir -p "$CACHE_DIR"

detect() {
  local changes=false
  for entry in "${REPOS[@]}"; do
    local repo="${entry%%:*}"
    local current_pin="${entry##*:}"
    local cache_file="${CACHE_DIR}/${repo//\//_}.last_seen"
    local latest
    latest=$(gh release list --repo "$repo" --limit 20 --json tagName -q '.[].tagName' \
              | grep -E "^v?15\." | head -1 | tr -d 'v' || echo "")
    if [[ -z "$latest" ]]; then
      echo "WARN: no upstream tag for $repo" >&2
      continue
    fi
    local last_seen=""
    [[ -f "$cache_file" ]] && last_seen=$(cat "$cache_file")
    if [[ "$latest" != "$last_seen" ]]; then
      echo "  $repo: latest=$latest (was=${last_seen:-none}, pinned=$current_pin)"
      changes=true
    fi
  done
  if $changes; then
    echo "CHANGES_DETECTED=true" >> "$GITHUB_OUTPUT"
    echo "true"
  else
    echo "CHANGES_DETECTED=false" >> "$GITHUB_OUTPUT"
    echo "false"
  fi
}

open-pr() {
  local branch="chore/upstream-sync-$(date +%Y%m%d)"
  git checkout -b "$branch"
  # Bump pins in apps/*/pyproject.toml — placeholder; real bump logic comes in W6-T08
  echo "# Upstream sync $(date -u +%Y-%m-%d)" > .orchestration/upstream-sync.md
  git add .orchestration/upstream-sync.md
  git commit -m 'chore: upstream-sync marker (real version bump in W6-T08)'
  git push -u origin "$branch"
  gh pr create --draft --title "chore: upstream sync $(date +%Y-%m-%d)" \
                --body "Automated sync. Real version-pin bump will be in W6-T08."
}

test() {
  echo "TODO: bench container + run-tests in W6-T08"
  exit 0
}

case "$MODE" in
  detect) detect ;;
  open-pr) open-pr ;;
  test) test ;;
  *) echo "Usage: $0 {detect|open-pr|test}" >&2; exit 2 ;;
esac
