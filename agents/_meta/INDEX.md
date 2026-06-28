# Agents Index

> Every agent lives at `agents/<scope>/<name>/AGENT.md`.
> An agent = a skill + a goal + an autonomy loop. Agents are *recipes for autonomous work*; skills are *recipes for one task*.

## Existing agents

| Scope | Agent | Wraps | Goal | Status |
|---|---|---|---|---|
| am | vat-auditor | am/vat-register | Audit every submitted Sales/Purchase Invoice for AM VAT compliance | scaffold |
| am | payroll-runner | libs/payroll-engine | Run end-to-end AM payroll for a period | scaffold |
| ae | vat-201-generator | ae/vat-201-return | Generate + submit-ready VAT 201 for a tax period | scaffold |
| ae | corporate-tax-calc | ae/corporate-tax | Compute UAE 9% CT with QFZP / small-business relief | scaffold |
| ail | doc-summarizer | ail/ollama-client | Summarize a Frappe doc into EN/HY/AR | scaffold |
| ail | rag-qa | ail/rag-ingest + ail/ollama-client | Answer questions from the user's Frappe corpus | scaffold |
| _meta | history-scan-runner | _meta/history-scan | Read last 25 sessions and propose skills/agents | scaffold |

## Naming convention

```
agents/<scope>/<kebab-case-name>/AGENT.md
```

- One folder per agent
- `AGENT.md` is the entry point: persona + goal + steps + completion criterion
- Use a loop pattern: `observe → act → reflect → persist` (see `_examples/agent-template/AGENT.md`)
