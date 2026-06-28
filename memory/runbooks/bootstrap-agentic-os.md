# Runbook: Bootstrap the Agentic OS for a new SBOSS project

> **Use when:** standing up a new SBOSS app / project from scratch and you want the same skill/agent/memory stack.

## Steps

```bash
# 1. Create the three folders
mkdir -p skills/am skills/ae skills/ail skills/libs skills/_meta \
         agents/am agents/ae agents/ail agents/_meta \
         memory/decisions memory/runbooks memory/learnings memory/sources

# 2. Copy the templates from the existing project
cp -r SBOSS-ERPNEXT-AM/skills/_meta/* <new-project>/skills/_meta/
cp -r SBOSS-ERPNEXT-AM/agents/_meta/* <new-project>/agents/_meta/
cp SBOSS-ERPNEXT-AM/CLAUDE.md <new-project>/CLAUDE.md

# 3. Adjust CLAUDE.md to point at the new project's specifics
#    (country scope, app names, license)

# 4. Run the history-scan
python <new-project>/skills/_meta/history-scan/scripts/scan.py \
  --output <new-project>/memory/learnings/skills-audit.md --limit 25

# 5. Pick the top 3 HIGH-priority gaps and build them
```

## Verification

- [ ] `ls skills/_meta/INDEX.md agents/_meta/INDEX.md memory/INDEX.md` all exist
- [ ] `python skills/_meta/history-scan/scripts/scan.py --limit 25` exits 0
- [ ] `memory/learnings/skills-audit.md` has at least 5 rows
