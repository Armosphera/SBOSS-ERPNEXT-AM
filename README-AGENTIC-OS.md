# Agentic OS for SBOSS-ERPNEXT-AM

> This repo now has an **Agentic OS** layer on top of `AGENTS.md`.
> See [CLAUDE.md](./CLAUDE.md) for the Claude Code entry point.

## The three folders

| Folder | Holds | Owner of content |
|---|---|---|
| [`skills/`](./skills/) | Codified knowledge — one `SKILL.md` per how-to | Codified once, evolved rarely |
| [`agents/`](./agents/) | Autonomous agent specs — one `AGENT.md` per agent | Wraps skills with a goal + loop |
| [`memory/`](./memory/) | Persistent state — decisions, runbooks, learnings, sources | Append-only for `learnings/` |

## Why

Ethan Nelson's "Agentic OS" playbook: most of Claude Code's value is in the
**engine** (skills + agents + memory), not the interface. The interface is 10%.
The repo already had `AGENTS.md` (project rules) and `.orchestration/`
(swarm state) — it was missing the codified-knowledge layer that makes
Claude faster turn-over-turn.

## How to use it

1. **Read `CLAUDE.md`** at the start of every Claude Code session.
2. **Look up the matching skill** in `skills/_meta/INDEX.md` before starting a task.
3. **Run the history-scan** weekly to find new skills to build:
   ```bash
   python skills/_meta/history-scan/scripts/scan.py --limit 25
   ```
4. **Persist learnings** to `memory/learnings/` after any non-trivial task.

## Status (2026-06-28)

- ✅ Three-folder scaffold + `CLAUDE.md` + `AGENTS.md` cross-link
- ✅ `skills/_meta/history-scan` (skill + Python script)
- ✅ `skills/_meta/doctype-authoring`
- ✅ `skills/_meta/upstream-sync`
- ✅ `agents/_meta/history-scan-runner`
- ✅ Initial `memory/learnings/skills-audit.md` (seeded from task list)
- ✅ ADR 0001 recording the decision
- ⏳ Per-country skills (`am/vat-register`, `ae/vat-201-return`, …) — scaffold only, to be built from the audit
- ⏳ Per-country agents — same

See [memory/learnings/skills-audit.md](./memory/learnings/skills-audit.md) for the priority list.
