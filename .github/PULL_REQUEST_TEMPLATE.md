<!--
Pull requests to SBOSS-ERPNEXT-AM.

Every PR must reference a task in `.orchestration/tasks/T-ID.md`.
The swarm CLI enforces isolation; this template helps the agent self-check.
-->

## Task

- **Task ID:** <!-- e.g. W1-T04 -->
- **Workstream:** <!-- e.g. W1.a (Armenia COA) -->
- **Branch:** <!-- e.g. feat/am/coa-fixture -->

## Summary

<!-- 1–3 bullets describing what this PR does. -->

## Type of change

- [ ] New feature (non-breaking change that adds functionality)
- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] Breaking change (fix or feature that would cause existing functionality to change)
- [ ] Documentation update

## TDD checklist

- [ ] I wrote a failing test FIRST
- [ ] I watched the test fail
- [ ] I wrote the minimal implementation
- [ ] I watched the test pass
- [ ] I ran the full test suite (if app exists yet)
- [ ] I ran `python tools/swarm/swarm.py verify-isolation W?-T??` (exits 0)
- [ ] I ran `python tools/swarm/swarm.py validate-state` (exits 0)

## Contracts respected

- [ ] Contract A — DocTypes I created are prefixed `AM ` / `AE ` / `AIL ` (if any)
- [ ] Contract B — AI tools I added are in the whitelist (if any)
- [ ] Contract C — I did not break `frappe_localization_core` or `frappe_payroll_engine` API
- [ ] No edits to upstream ERPNext/Frappe/HRMS files

## Test plan

<!-- What commands to run, what output to expect. -->

```bash
bench --site test.localhost run-tests --app <APP> --module <MODULE>
```

Expected: `Ran N tests in Xms — OK`

## Pitfalls encountered

<!-- Anything you debugged, anything that was non-obvious. Other agents will benefit. -->

## Linked issues

<!-- Closes #N, fixes #M, etc. -->

## Release

- [ ] `python tools/swarm/swarm.py release-task <T-ID> --pr <THIS-PR-NUMBER>` (run after merge)
