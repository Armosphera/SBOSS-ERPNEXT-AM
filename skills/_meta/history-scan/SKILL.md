---
name: history-scan
description: Use when the user wants to discover what skills/agents to build from their past Claude Code sessions, or when bootstrapping a new Agentic OS workspace. Reads the last 25 (or N) sessions and proposes a concrete skills/agents inventory.
version: 1.0.0
author: SBOSS Agentic OS
license: MIT
metadata:
  hermes:
    tags: [meta, bootstrap, agentic-os, history-scan, ethans-playbook]
    related_skills: [doctype-authoring, upstream-sync]
---

# History Scan — propose skills/agents from past sessions

## Overview

Ethan Nelson's "Agentic OS" playbook identifies **history scan** as the fastest way to bootstrap
a skills/agents library: read your last 25 conversations with Claude, identify recurring
workflows you keep re-explaining, and turn each one into a codified `SKILL.md`.

This skill does that, but **concretely and reproducibly** — it does not just prompt you to
"go look at your history", it reads a structured export, clusters conversations by
workflow, and emits a `skills-audit.md` with three columns: **Exists** / **Should exist** / **Priority**.

## When to Use

- User says: "scan my sessions", "what skills should I build", "bootstrap my agentic OS"
- First time setting up a new project's `skills/`, `agents/`, `memory/` workspace
- Every ~2 weeks as a maintenance scan to catch new recurring patterns
- After onboarding a new collaborator to a project

**Do not use for:**
- Reading a single past session (use `session_search` directly)
- Generating a skill from a one-off task (use the `hermes-agent-skill-authoring` skill directly)

## Inputs

The script reads from one of three sources, in order of preference:

| Source | Format | When to use |
|---|---|---|
| `claude-code-export.json` | Claude Code session export | You have an official export |
| `~/.claude/sessions/*.jsonl` | JSONL one-per-session | Default for live Claude Code installs |
| `~/.hermes/sessions.db` | SQLite FTS5 | When using Hermes Agent (this repo uses it) |

The first source that exists is used. Override with `--source <path>`.

## Procedure

### Step 1 — Locate the session source

```bash
ls -la claude-code-export.json ~/.claude/sessions/ ~/.hermes/sessions.db 2>&1 | head
```

If none exist, ask the user to export or to point you at the right path.

### Step 2 — Run the scan

```bash
python skills/_meta/history-scan/scripts/scan.py \
  --output memory/learnings/skills-audit.md \
  --limit 25
```

The script:

1. Pulls the last 25 user messages (and their assistant replies) from the source
2. Clusters them by **first verb + first noun** (e.g. "add"+"doctype" → AM DocType authoring)
3. For each cluster, counts occurrences and lists 1-2 representative session IDs
4. Cross-references against `skills/_meta/INDEX.md` to mark which skills already exist
5. Emits a markdown table sorted by occurrence count

### Step 3 — Review the audit

Open `memory/learnings/skills-audit.md`. The output table has columns:

| Column | Meaning |
|---|---|
| Workflow | The recurring pattern (verb + noun) |
| Sessions | How many of the last 25 hit this pattern |
| Examples | First 2 session IDs (or excerpts) |
| Exists? | ✓ / ✗ / partial — cross-ref against `skills/_meta/INDEX.md` |
| Priority | HIGH if ≥5 sessions, MEDIUM if 2-4, LOW if 1 |

### Step 4 — Pick the top 3 and build

Don't try to build all 25 at once. Pick the top 3 by `Priority = HIGH` and:

1. Read the example sessions to understand the user's "what good looks like" for that workflow
2. Use the `hermes-agent-skill-authoring` skill to scaffold a new `SKILL.md`
3. Run the scan again next week to measure if occurrences dropped (i.e. did Claude start using the new skill?)

## Output

The skill writes one file:

- `memory/learnings/skills-audit.md` — the audit table (committed to git)
- A summary table printed to stdout (so the user can see it in chat)

## Common Pitfalls

1. **Scanning too few sessions.** 5 sessions will under-count recurring work. 25 is the sweet spot; 50+ dilutes recency.
2. **Building a skill from a single session.** If it only happened once, it's a one-off, not a skill. Wait for it to repeat.
3. **Forgetting to commit the audit.** The audit is a learning; it lives in `memory/learnings/`, version-controlled, never deleted.
4. **Confusing workflow with task.** "Add DocType X" is a task. "Add a Frappe DocType" is a workflow (the skill captures the latter).

## Verification Checklist

- [ ] `memory/learnings/skills-audit.md` exists, dated, has the priority table
- [ ] Top 3 HIGH-priority workflows either have a skill in `skills/` or are scheduled for build
- [ ] `skills/_meta/INDEX.md` is updated with the new skills (mark "scaffold" → "v1")
- [ ] Audit file is committed (`git add memory/learnings/skills-audit.md && git commit`)

## One-Shot Recipe

```bash
# Full bootstrap for a new project
mkdir -p skills/am skills/ae skills/ail skills/libs skills/_meta \
         agents/am agents/ae agents/ail agents/_meta \
         memory/decisions memory/runbooks memory/learnings memory/sources

# Copy this SKILL.md into the new project
cp skills/_meta/history-scan/SKILL.md <new-project>/skills/_meta/history-scan/SKILL.md

# Run the scan
python skills/_meta/history-scan/scripts/scan.py --limit 25
```

## Related

- `skills/_meta/doctype-authoring/` — the skill you will most often build from a scan hit
- `memory/learnings/skills-audit.md` — the audit output
- `agents/_meta/history-scan-runner/` — the autonomous wrapper around this skill
