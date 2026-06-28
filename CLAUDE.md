# CLAUDE.md — Claude Code entry point for SBOSS-ERPNEXT-AM

> **READ THIS FIRST** at the start of every Claude Code session.
> This file is the **table of contents** that points Claude at the right skills,
> agents, and memory for the current task. `AGENTS.md` is the source of truth for
> project rules; this file is the source of truth for **how Claude should work**.

## 1. Project at a glance

| Field | Value |
|---|---|
| Project | SBOSS-ERPNEXT-AM (Armosphera ERPNext localization) |
| Stack | Frappe v15.x + ERPNext v15.x + HRMS, 3 custom apps (frappe_armenia, frappe_uae, frappe_ai_local) |
| Country scope | Armenia (AM) + UAE (AE) + AI layer (AIL) |
| Languages | English (en), Armenian (hy), Arabic (ar) |
| Local LLM | Ollama + Gemma 4 E2B / Gemma 2 2B, embedded ChromaDB |
| Architecture | Frozen contracts in `docs/architecture.md` (Contract A/B/C) |
| Workstream model | Wave-based swarm — tasks in `.orchestration/tasks/W*-T*.md` |
| License | Apps = Armosphera Proprietary · Libs = MIT |

## 2. Workspace layout (the Agentic OS)

```
SBOSS-ERPNEXT-AM/
├── AGENTS.md              ← project rules (source of truth, do not edit lightly)
├── CLAUDE.md              ← THIS FILE (Claude's table of contents)
├── docs/architecture.md   ← frozen contracts
├── .orchestration/        ← swarm state + task definitions
│
├── skills/                ← Level 1a: reusable knowledge (SKILL.md per skill)
│   ├── am/                ← Armenia-specific skills (VAT, e-invoice, payroll, COA)
│   ├── ae/                ← UAE-specific skills (VAT 201, CT 9%, Peppol, EOSB)
│   ├── ail/               ← AI layer skills (Ollama client, RAG, agent tools)
│   ├── libs/              ← localization_core / payroll_engine patterns
│   └── _meta/             ← skill index, naming conventions
│
├── agents/                ← Level 1b: autonomous agent specs
│   ├── am/                ← Armenia-focused agents (VAT audit, payroll calc, …)
│   ├── ae/                ← UAE-focused agents (VAT 201 generator, CT calc, …)
│   ├── ail/               ← AI layer agents (doc-summarizer, classifier, …)
│   └── _meta/             ← agent index, handoff protocol
│
├── memory/                ← Level 2: persistent state
│   ├── decisions/         ← ADRs (architecture decision records)
│   ├── runbooks/          ← step-by-step playbooks (deploy, sync-upstream, …)
│   ├── learnings/         ← post-mortems, gotchas, patterns
│   └── sources/           ← raw reference material (tax PDFs, FTA circulars)
│
└── _examples/             ← reference skill/agent SKILL.md templates
```

## 3. How to work a task (Claude-specific flow)

For every request:

1. **Identify the country scope** from the user's words (Armenia → AM, UAE → AE, AI layer → AIL, cross-cutting → libs/).
2. **Read the matching `SKILL.md`** in `skills/<scope>/<name>/SKILL.md` if one exists for this task type. Skills are the source of codified knowledge — load them **before** starting work.
3. **Claim the swarm task** if the request maps to a `.orchestration/tasks/W*-T*.md` file:
   ```bash
   python tools/swarm/claim-task.py W2-T13
   cat .orchestration/tasks/W2-T13.md
   ```
4. **Use the matching agent** in `agents/<scope>/<name>/AGENT.md` as your operating procedure for multi-step autonomous work.
5. **Persist learnings** to `memory/learnings/` after any non-trivial task. Append, never overwrite.
6. **Commit + push + PR** using Conventional Commits; single-quote any commit message containing backticks (see `.github/COMMIT_PITFALLS.md`).

## 4. Hard rules (mirror of AGENTS.md — Claude must enforce)

- **NEVER edit upstream** code under `apps/frappe_armenia/erpnext/`, `apps/frappe_armenia/frappe/`, `apps/frappe_armenia/hrms/` (or equivalents in the other apps). If upstream needs a change, file a W6 upstream-sync issue.
- **NEVER make a PR** that touches files outside the task's claimed `globs` (CI runs `tools/swarm/verify-isolation.py`).
- **ALL DocTypes** are prefixed `AM ` / `AE ` / `AIL ` (Contract A). The space is required.
- **AI tool calls** must be registered in the AIL Tool Whitelist (Contract B). No `frappe.delete_doc`, no `frappe.rename_doc`, no `frappe.db.sql`.
- **Bilingual UI strings** — every user-facing string needs `_en` / `_hy` / `_ar` variants via Frappe translation system.
- **TDD is mandatory** — RED-GREEN-REFACTOR. Write the failing test first, watch it fail, write minimal code to pass.
- **Never commit secrets** — fixtures only, even in tests.

## 5. Quick reference: the skills that always apply

| When you need to… | Load skill at |
|---|---|
| Write or modify a Frappe hook / validation | `skills/am/...` or `skills/ae/...` (country-specific) |
| Add a new DocType | `skills/_meta/doctype-authoring/SKILL.md` |
| Wire up an AI tool to the agent | `skills/ail/tool-whitelist/SKILL.md` |
| Calculate payroll (Armenia or UAE) | `skills/libs/payroll-engine/SKILL.md` |
| Generate tax return (VAT 201, AM VAT register) | `skills/ae/vat-201-return/SKILL.md`, `skills/am/vat-register/SKILL.md` |
| Sync upstream | `skills/_meta/upstream-sync/SKILL.md` |
| Discover new skills from your past work | `skills/_meta/history-scan/SKILL.md` |

> If a skill you need doesn't exist, **first check the audit** in `memory/learnings/skills-audit.md`
> (regenerated by running the history-scan skill). The audit lists every skill that *should* exist
> and which are still missing.

## 6. When you finish a task

Always end the turn with the three-section report the user wants:

```
## Done
- (bullet list with PR numbers, test counts, tag names — evidence, not prose)

## Not Done
- (honest list of blocked / partial / skipped items with the specific blocker)

## Next
- (the single highest-value remaining item, do not list 5)
```

## 7. Related

- `AGENTS.md` — full project rules
- `docs/architecture.md` — frozen contracts
- `.hermes/plans/2026-06-24_142129-erpnext-armenia-uae-localization.md` — the plan
- `.github/COMMIT_PITFALLS.md` — shell quoting gotcha
- Skill index: `skills/_meta/INDEX.md`
- Agent index: `agents/_meta/INDEX.md`
- Memory index: `memory/INDEX.md`
