---
name: upstream-sync
description: Use when running the weekly W6 upstream ERPNext sync, or when a failure suggests upstream has changed. Owns the "upstream-survivability" contract.
version: 1.0.0
author: SBOSS Agentic OS
license: MIT
metadata:
  hermes:
    tags: [meta, upstream, w6, contract]
    related_skills: [doctype-authoring]
---

# Upstream Sync (W6)

## Overview

ERPNext ships updates continuously. SBOSS localization apps must keep working
after every upstream update without operator intervention. The W6 workstream
owns that contract: pull upstream, run the wrapper tests, fix breakages in
`libs/` only, never edit upstream code.

## When to Use

- It's been 7+ days since the last sync
- CI red on the `upstream-compat` job
- An upstream PR landed that mentions a hook we wrap

**Do not use for:** one-off dependency bumps in `pyproject.toml` (just PR them with a `chore(deps)` commit).

## Procedure

```bash
# 1. Inside frappe-bench
cd frappe-bench

# 2. Pull upstream for the apps we link
bench update --pull

# 3. Run the wrapper test suite
bash ../infra/scripts/sync-upstream.sh test

# 4. If failures: file a W6 issue
#    .orchestration/tasks/W6-T<NN>.md with the failing test name + stack
#    Then fix in libs/ (or in the local app), NOT in the upstream folder.
```

## Common Pitfalls

1. **Editing upstream in place** — `apps/frappe_armenia/erpnext/...` is read-only. Always fix the wrapper.
2. **Skipping `bash -n` check** — the sync script catches shell-quoting bugs the test runner doesn't.
3. **Forgetting to commit the upstream-submodule bump** — bench update leaves the repo dirty; the operator must commit.

## Verification Checklist

- [ ] `bench update --pull` ran cleanly
- [ ] `bash infra/scripts/sync-upstream.sh test` exits 0
- [ ] Any breakage is fixed in `libs/` or the local app, not in upstream
- [ ] `state.json` updated if a W6 task was created/closed
