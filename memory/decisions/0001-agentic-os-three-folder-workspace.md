# ADR 0001: Adopt the "Agentic OS" three-folder workspace

- Status: Accepted
- Date: 2026-06-28
- Deciders: Sam Step + Hermes

## Context

Claude Code is being used across this repo but skills, agents, and persistent memory are scattered — every task re-explains the same context. We watched Ethan Nelson's "Agentic OS" video which proposes a 4-level stack: skills + agents + memory + (optional) interface + distribution. The repo already has `AGENTS.md` for project rules and `.orchestration/tasks/` for the swarm. What's missing is the **codified knowledge layer** that makes Claude faster turn-over-turn.

## Decision

Add three top-level folders + a `CLAUDE.md` entry point:

| Folder | Holds | Append-only? |
|---|---|---|
| `skills/<scope>/<name>/SKILL.md` | Codified knowledge (how-tos) | No — versioned with code |
| `agents/<scope>/<name>/AGENT.md` | Autonomous agent specs | No — versioned with code |
| `memory/{decisions,runbooks,learnings,sources}/` | Persistent state | `learnings/` is append-only |

`CLAUDE.md` becomes the table of contents that Claude reads at the start of every session; `AGENTS.md` remains the source of truth for project rules.

## Consequences

- **Pro:** New collaborators (human or AI) onboard in one read of `CLAUDE.md` + the matching `SKILL.md`
- **Pro:** The history-scan skill can audit the gap between "what the user keeps doing" and "what is codified"
- **Pro:** `memory/learnings/skills-audit.md` becomes a measurable signal — re-run weekly, watch counts drop as skills get built
- **Con:** Adds 3 directories to remember; mitigated by the `INDEX.md` in each
- **Con:** Risk of duplication with `~/.hermes/skills/`; mitigated by `skills/_meta/` living in the repo (Hermes loads repo skills first if they shadow user-local)

## Alternatives considered

- **Put everything in `~/.claude/skills/`** — rejected, not version-controlled with the code
- **Use a single `AGENTS.md` for everything** — rejected, would be >30k chars; the three-folder split mirrors the playbook
- **Adopt LangGraph / CrewAI conventions** — rejected, the swarm already has its own agent model; we just needed a place to put *specs* for it

## Supersedes

None.
