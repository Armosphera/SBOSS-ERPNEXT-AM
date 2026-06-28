# Skills / Agents Audit

> Initial seed — see `skills/_meta/history-scan/scripts/scan.py` for the live generator.
> This file is committed to git; the scan script overwrites it on each run.

## Top workflows by frequency (initial estimate from .orchestration/tasks/)

| # | Workflow | Sessions | Examples | Exists? | Priority | Suggested location |
|---|----------|----------|----------|---------|----------|--------------------|
| 1 | add doctype | many | W0-T12..W0-T18 (namespace contract) | partial | **HIGH** | `skills/_meta/doctype-authoring/SKILL.md` |
| 2 | vat compliance | many | W2-T12, W2-T13 (AE) + W1-T14 (AM) | partial | **HIGH** | `skills/am/vat-register/SKILL.md`, `skills/ae/vat-201-return/SKILL.md` |
| 3 | payroll | several | W3-T01..W3-T08 (engine) | partial | **HIGH** | `skills/libs/payroll-engine/SKILL.md` |
| 4 | tdd discipline | many | every test file in tests/ | scaffold | **HIGH** | `skills/_meta/tdd-discipline/SKILL.md` |
| 5 | git pr workflow | many | every commit | scaffold | **HIGH** | `skills/_meta/git-pr-workflow/SKILL.md` |
| 6 | upstream sync | weekly | W6 workstream | scaffold | MEDIUM | `skills/_meta/upstream-sync/SKILL.md` |
| 7 | ollama client | several | W3-T01 (W3 AI layer) | TODO | MEDIUM | `skills/ail/ollama-client/SKILL.md` |
| 8 | rag ingest | several | W4-T01..W4-T05 | TODO | MEDIUM | `skills/ail/rag-ingest/SKILL.md` |
| 9 | tool whitelist | several | W0-T18, every AIL PR | partial | MEDIUM | `skills/ail/tool-whitelist/SKILL.md` |
| 10 | corporate tax | several | W5-T01..W5-T10 (AE) | TODO | MEDIUM | `skills/ae/corporate-tax/SKILL.md` |
| 11 | eosb accrual | a few | W5-T15+ (AE) | TODO | LOW | `skills/ae/eosb-accrual/SKILL.md` |
| 12 | peppol einv | a few | W4-T20+ (AE) | TODO | LOW | `skills/ae/peppol-einvoicing/SKILL.md` |
| 13 | code review | many | every PR | TODO | MEDIUM | `skills/_meta/code-review/SKILL.md` |
| 14 | debug | occasional | every CI red | TODO | LOW | `skills/_meta/systematic-debug/SKILL.md` |

## Next 3 to build (top of HIGH list)

1. `skills/_meta/git-pr-workflow/SKILL.md` — codify branch naming, conventional commits, single-quote pitfall, PR template
2. `skills/am/vat-register/SKILL.md` — codify the AM VAT validation hook pattern from W1-T14
3. `skills/libs/payroll-engine/SKILL.md` — codify the generic payroll calculator usage from W3

## Uncategorized

None yet — every task in `.orchestration/tasks/` maps to a known workflow above.

## Re-run

```bash
python skills/_meta/history-scan/scripts/scan.py --limit 25
```

This will overwrite the table above with the live counts from the last 25 sessions.
