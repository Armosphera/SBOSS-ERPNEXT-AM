# AGENTS.md — Instructions for AI Coding Agents

> Read this file first. It is the single source of truth for how an AI coding
> agent (Claude Code, Codex, OpenCode, or any other) should work in this repo.

## Project

**SBOSS ERPNEXT AM** — the Armosphera ERPNext localization platform. Three
production-grade Frappe custom apps on top of upstream ERPNext v15.x:

| App | Country | Purpose |
|---|---|---|
| `apps/frappe_armenia` | Armenia | COA, VAT 20%, profit tax 18%, e-invoice, payroll, banking, HY/EN bilingual |
| `apps/frappe_uae`     | UAE     | VAT 5%, corporate tax 9%, e-invoicing (Peppol), EOSB, Arabic RTL, banking |
| `apps/frappe_ai_local` | Both  | Local-LLM AI agent + chat (Ollama + Gemma 4 E2B QAT), offline-capable, HY/AR/EN |

Two shared libraries under `libs/` (MIT):
- `frappe_localization_core` — country-agnostic helpers (number-to-words, IBAN, ISO20022, MT940, currency)
- `frappe_payroll_engine`    — generic payroll calculation engine

## Ground rules (READ THESE — VIOLATIONS BREAK THE BUILD)

0. **Upstream-survivability is a hard requirement.** ERPNext ships updates
   continuously. Our localization apps must keep working after every upstream
   update without operator intervention. The mechanism is: link to upstream's
   public API only, run the W6 weekly sync, fix breakages in wrapper layers
   (`libs/`), never edit upstream code. See `docs/architecture.md` → "Upstream-
   survivability contract". An operator can trigger `bench update && bash
   infra/scripts/sync-upstream.sh test` at any time and expect tests to pass.

1. **NEVER modify anything under `apps/frappe_armenia/erpnext/`, `apps/frappe_armenia/frappe/`, `apps/frappe_armenia/hrms/`, or the equivalent paths in `frappe_uae` / `frappe_ai_local`.** These are upstream references. If you think upstream needs a change, file an issue in the W6 upstream-sync workstream — do not edit.

2. **NEVER make a PR that touches files outside your claimed task's `globs`.** The CI runs `tools/swarm/verify-isolation.py` and will fail the build.

3. **Licensing.** `apps/*` are Armosphera Proprietary. `libs/*` are MIT. Do not mix them. The `LICENSE-ARMOSPHERA.md` file must be preserved in every `apps/*/`.

4. **TDD is mandatory.** Every task is RED-GREEN-REFACTOR. Write the failing test FIRST, run it, watch it fail, then write the minimal code to pass. No exceptions.

5. **Frequent commits.** Commit after every green test. Use Conventional Commits. **Use single-quotes for any commit message containing backticks** (shell pitfall, see `.github/COMMIT_PITFALLS.md`).

6. **Never commit secrets.** No API keys, no client certs, no TINs, no payroll data. Even in tests, use fixtures.

7. **All ERPNext DocTypes you create must be prefixed `AM ` (Armenia) or `AE ` (UAE) or `AIL ` (AI layer).** This is the namespace contract — see `docs/architecture.md#contract-a`.

8. **All AI tools registered with the agent must be added to the `AIL Tool Whitelist`** — see `docs/architecture.md#contract-b`. The agent CANNOT call `frappe.delete_doc`, `frappe.rename_doc`, or any `frappe.db.sql` directly.

9. **Bilingual UI strings:** every user-facing string has `_en`, `_hy` (Armenian), and `_ar` (Arabic) variants. Use Frappe's translation system (`__("…")` with `.csv` files per locale), do not hardcode in JS.

## How to work a task

Every task in this repo is defined by a file in `.orchestration/tasks/T-ID.md`.
The pattern is:

```bash
# 1. Claim the task (atomic file lock + state.json update)
python tools/swarm/claim-task.py W1-T04

# 2. Read the task file
cat .orchestration/tasks/W1-T04.md

# 3. Create the branch
git checkout -b feat/am/coa-fixture

# 4. RED: write the failing test
# (paste code from the task file)

# 5. Run tests, see them fail
bench --site test.localhost run-tests --app frappe_armenia --module tests.test_coa

# 6. GREEN: write the minimal implementation

# 7. Run tests, see them pass

# 8. REFACTOR

# 9. Commit (single-quoted if backticks)
git add apps/frappe_armenia/
git commit -m 'feat(am): seed Armenian chart of accounts (350 accounts)'

# 10. Push and open PR
git push -u origin HEAD
gh pr create --title "feat(am): seed Armenian chart of accounts (350 accounts)" --body-file .github/PULL_REQUEST_TEMPLATE.md

# 11. Release the task
python tools/swarm/release-task.py W1-T04 --pr <PR_NUMBER>
```

## Verifying isolation before PR

```bash
python tools/swarm/verify-isolation.py W1-T04
# Exits 0 if no other active task claims an overlapping glob
# Exits 1 with a clear error otherwise
```

## Available skills

This repo is designed to be worked by AI agents. The skills you should load
before starting are:

- `plan` — for sub-planning a large task
- `test-driven-development` — for TDD discipline
- `github-pr-workflow` — for branch/PR/merge mechanics
- `requesting-code-review` — before merging a milestone PR
- `systematic-debugging` — when tests fail unexpectedly

## Conventions

| Item | Convention |
|---|---|
| Branch prefixes | `feat/am/`, `feat/uae/`, `feat/ai/`, `feat/libs/`, `chore/`, `ci/`, `docs/` |
| Commit format | Conventional Commits (`type(scope): subject`) |
| Python style | `ruff` (enforced in CI) |
| JS style | `prettier` (enforced in CI) |
| Test framework | `unittest` + `FrappeTestCase` |
| DocType prefix | `AM ` / `AE ` / `AIL ` |
| File encoding | UTF-8 everywhere, including HY/AR strings |
| Time zone | UTC for all timestamps; display in user's locale |

## Anti-patterns to avoid

- ❌ Editing upstream ERPNext files in place (file a W6 issue instead)
- ❌ Cross-app imports (`frappe_armenia` importing from `frappe_uae` — use `libs/` instead)
- ❌ Hardcoded English in user-facing strings (always `__("…")`)
- ❌ `frappe.db.sql` in app code (use Query Builder or `frappe.get_all`)
- ❌ `os.system` / `subprocess` calls (use Frappe's shell utilities)
- ❌ Modifying `state.json` by hand (always use the swarm CLI)
- ❌ Opening a PR that includes `package-lock.json` or `yarn.lock` for `node_modules/` inside an app (Frappe apps bundle their own assets)

## Where to get help

- The plan: `.hermes/plans/2026-06-24_142129-erpnext-armenia-uae-localization.md`
- Architecture: `docs/architecture.md`
- Frozen contracts: `docs/architecture.md#contract-a-b-c`
- Task list: `.orchestration/tasks/`
- Tax references: `docs/tax-references/`
- Frappe docs: https://docs.frappe.io/framework
- ERPNext docs: https://docs.frappe.io/erpnext
