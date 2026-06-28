---
name: doctype-authoring
description: Use when adding or modifying a Frappe DocType in any of the SBOSS apps (frappe_armenia, frappe_uae, frappe_ai_local). Covers the namespace contract (AM / AE / AIL prefix), naming, fixtures, tests, and bilingual strings.
version: 1.0.0
author: SBOSS Agentic OS
license: MIT
metadata:
  hermes:
    tags: [meta, frappe, doctype, contract-a]
    related_skills: [history-scan, upstream-sync]
---

# DocType Authoring

## Overview

Every DocType in SBOSS must follow **Contract A** from `docs/architecture.md`:
the name is prefixed `AM ` (Armenia), `AE ` (UAE), or `AIL ` (AI layer) with a
**required space** between prefix and the rest of the name. This skill enforces
the prefix, the tests, the bilingual strings, and the swarm claim/release flow.

## When to Use

- User says: "add a DocType", "create a new AM / AE / AIL DocType", "model X as a DocType"
- You are about to create a file under `apps/*/frappe_*/doctype/<name>/`
- You need to validate that an existing DocType conforms to the contract

**Do not use for:** modifying upstream ERPNext DocTypes (forbidden — file a W6 issue instead).

## The contract (verbatim from docs/architecture.md#contract-a)

| Prefix | Country | Example |
|---|---|---|
| `AM ` | Armenia | `AM VAT Register Entry`, `AM E-Invoice Provider`, `AM Salary Component` |
| `AE ` | UAE | `AE VAT 201`, `AE Corporate Tax Dashboard`, `AE EOSB Accrual` |
| `AIL ` | AI layer | `AI Provider`, `AI Chat Session`, `AI Chat Message`, `AI Knowledge Source` |

The space after the prefix is **required** (matches Frappe's display-name convention).

## Procedure

### Step 1 — Pick the right scope

```
Armenia tax / payroll / banking / Armenian law   → AM
UAE tax / e-invoice / EOSB / Arabic              → AE
Ollama / RAG / agent / chat                      → AIL
```

If it crosses all three (e.g. a tax assistant that knows both), pick the
**primary country** prefix and put the cross-cutting logic in `libs/`.

### Step 2 — Claim the swarm task (if one exists)

```bash
python tools/swarm/claim-task.py W3-T05
cat .orchestration/tasks/W3-T05.md
```

If the task file specifies `globs:`, the PR is restricted to those paths.

### Step 3 — Scaffold the DocType

```bash
cd frappe-bench
bench --site test.localhost new-doctype "<Name>"
```

Manual edit `apps/<app>/<app>/doctype/<name>/<name>.json`:

- `name`: must start with `AM ` / `AE ` / `AIL ` exactly
- `module`: usually `Armosphera <Country>` or `Armosphera AI`
- `naming_rule`: usually `"field:title_field"` or `"autoincrement"`
- `fields`: declare all fields with types; never use `frappe.db.sql`
- For bilingual labels, use the Frappe translation system (`.csv` per locale)

### Step 4 — Add the failing test (TDD)

```python
# apps/<app>/<app>/tests/test_<doctype>.py
import frappe
from frappe.tests.utils import FrappeTestCase

class TestAMVatRegisterEntry(FrappeTestCase):
    def test_prefix_is_am_space(self):
        meta = frappe.get_meta("AM VAT Register Entry")
        self.assertTrue(meta.name.startswith("AM "))

    def test_required_fields_present(self):
        meta = frappe.get_meta("AM VAT Register Entry")
        self.assertIn("company", meta.get("fields", {"fieldname": "company"}))
```

Run it, watch it fail:

```bash
bench --site test.localhost run-tests --app <app> --module tests.test_<doctype>
```

### Step 5 — Implement the minimum to pass

Only after the test fails, write the DocType + any hooks needed.

### Step 6 — Add bilingual strings

In `apps/<app>/<app>/translations/en.csv`, `hy.csv`, `ar.csv`:

```
"AM VAT Register Entry","AM VAT Register Entry","ԱԱՀ ռեեստրի գրառում","سجل ضريبة القيمة المضافة"
```

### Step 7 — Commit, push, PR

```bash
git add apps/<app>/<app>/doctype/<name>/
git commit -m 'feat(am): add AM VAT Register Entry DocType (W3-T05)'
# Single-quote if message contains backticks — see .github/COMMIT_PITFALLS.md
git push -u origin HEAD
gh pr create --title "feat(am): AM VAT Register Entry DocType (W3-T05)" --body-file .github/PULL_REQUEST_TEMPLATE.md
```

## Common Pitfalls

1. **Forgetting the space** — `AMVAT` violates the contract; must be `AM VAT`.
2. **Hardcoding English labels** — always use `__("…")` with `.csv` translations.
3. **Skipping the failing test** — TDD is mandatory, see AGENTS.md rule 4.
4. **Touching upstream files** — `apps/frappe_armenia/erpnext/...` is read-only.
5. **Cross-app imports** — use `libs/` for shared logic, never `frappe_armenia` from `frappe_uae`.

## Verification Checklist

- [ ] DocType name starts with the right prefix **and a space**
- [ ] `module` set to `Armosphera <Country>` or `Armosphera AI`
- [ ] At least one failing test was written and confirmed to fail before implementation
- [ ] Bilingual strings exist in `en.csv`, `hy.csv` (Armenia), `ar.csv` (UAE)
- [ ] `python tools/swarm/verify-isolation.py W*-T*` exits 0
- [ ] PR opened, CI green, merged, `state.json` updated
