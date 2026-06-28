# Skills Index

> Every skill lives at `skills/<scope>/<name>/SKILL.md`.
> Scope = `am` (Armenia) · `ae` (UAE) · `ail` (AI layer) · `libs` (shared libraries) · `_meta` (cross-cutting).

## How to read this index

A skill is **codified knowledge** — the "how-to" that the user no longer wants to type.
An **agent** (in `agents/`) wraps one or more skills with autonomous execution.

## Existing skills

| Scope | Skill | Purpose | Status |
|---|---|---|---|
| _meta | history-scan | Scan past sessions and propose new skills/agents | scaffold |
| _meta | doctype-authoring | Add a new Frappe DocType correctly (prefix, naming, tests) | scaffold |
| _meta | upstream-sync | Weekly W6 sync with upstream ERPNext | scaffold |
| am | vat-register | AM monthly/quarterly VAT register | TODO |
| am | profit-tax | AM 18% profit tax calculation | TODO |
| am | e-invoice | AM e-invoicing provider integration | TODO |
| ae | vat-201-return | UAE VAT 201 FTA return form | TODO |
| ae | corporate-tax | UAE 9% corporate tax (small business relief, QFZP) | TODO |
| ae | peppol-einvoicing | UAE Peppol e-invoicing | TODO |
| ae | eosb-accrual | UAE End-of-Service Benefits accrual | TODO |
| ail | ollama-client | Ollama HTTP client (model select, stream, health) | TODO |
| ail | rag-ingest | Ingest Frappe DocTypes into ChromaDB | TODO |
| ail | tool-whitelist | Register a function in the AIL Tool Whitelist | TODO |
| libs | payroll-engine | Generic payroll calculation engine usage | TODO |
| libs | iban-validator | IBAN validation + BIC lookup | TODO |
| libs | mt940-parser | SWIFT MT940 bank statement parser | TODO |

> Run `python skills/_meta/history-scan/scripts/scan.py` to regenerate the "needed vs. existing" status from your actual session history.

## Naming convention

```
skills/<scope>/<kebab-case-name>/SKILL.md
```

- One folder per skill, not per category
- `SKILL.md` is the entry point; supplementary files in `references/`, `templates/`, `scripts/`
- See `_examples/skill-template/` for the frontmatter + structure
