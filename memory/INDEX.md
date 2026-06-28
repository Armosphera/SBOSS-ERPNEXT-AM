# Memory Index

> Persistent knowledge that survives across sessions. Append-only by default.

| Folder | What goes here | How to add |
|---|---|---|
| `decisions/` | Architecture Decision Records (ADR) — one file per decision | Copy `_meta/adr-template.md` |
| `runbooks/` | Step-by-step operational playbooks (deploy, sync, restore) | Copy `_meta/runbook-template.md` |
| `learnings/` | Post-mortems, gotchas, discovered patterns, skills-audit | One file per topic, dated |
| `sources/` | Raw reference material (tax PDFs, FTA circulars, regulator links) | One folder per source |

## The four invariants

1. **Append-only for `learnings/`** — never delete a learning, even if outdated. Mark it `[superseded by ...]` at the top.
2. **ADRs are immutable once `Status: Accepted`** — to reverse, write a new ADR that supersedes the old one.
3. **Runbooks must be tested** — every runbook ends with a verification command. If you change a runbook, run it.
4. **`sources/` is a cache, not the source of truth** — always cite the upstream URL.
