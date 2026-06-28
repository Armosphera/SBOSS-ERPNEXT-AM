#!/usr/bin/env python3
"""
history-scan/scripts/scan.py
=============================

Read the user's last N sessions from the best available source and emit a
skills/agents audit markdown file.

Usage:
    python scan.py --output memory/learnings/skills-audit.md --limit 25
    python scan.py --output /tmp/audit.md --limit 50 --source ~/.hermes/sessions.db
    python scan.py --output /tmp/audit.md --limit 25 --source claude-code-export.json

Sources (first existing wins, or pass --source):
    1. ~/.hermes/sessions.db          (Hermes Agent SQLite, FTS5)
    2. ~/.claude/sessions/*.jsonl     (Claude Code native)
    3. claude-code-export.json        (Claude Code official export)

Output columns: Workflow | Sessions | Examples | Exists? | Priority
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import glob
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# ---- Workflow vocabulary (verb + noun) ---------------------------------------

# Common patterns we look for in user messages. Each tuple is
# (regex, "verb noun", scope)
WORKFLOW_PATTERNS = [
    # Armenia
    (r"\b(add|create|new)\b.*\b(doctype|doc\s*type)\b",  "add doctype",     "am"),
    (r"\b(vat|еш\u0561\u0574|ավելացման արժեք)\b",      "vat compliance",  "am"),
    (r"\b(profit tax|շահութահարկ)\b",                     "profit tax",      "am"),
    (r"\b(e-?invoice|է-?հաշիվ)\b",                       "e-invoice",       "am"),
    (r"\b(payroll|աշխատավարձ)\b",                        "payroll",         "am"),

    # UAE
    (r"\b(vat\s*201|vat return|fta return)\b",          "vat 201 return",  "ae"),
    (r"\b(corporate tax|ct 9%|qfzp)\b",                  "corporate tax",   "ae"),
    (r"\b(peppol|uae e-?invoice)\b",                     "peppol einv",     "ae"),
    (r"\b(eosb|end.of.service)\b",                       "eosb accrual",    "ae"),

    # AI layer
    (r"\b(ollama|llm|local model)\b",                    "ollama client",   "ail"),
    (r"\b(rag|embedding|chroma|vector)\b",               "rag ingest",      "ail"),
    (r"\b(whitelist|tool registration|allowlist)\b",     "tool whitelist",  "ail"),
    (r"\b(agent|harness|loop)\b",                        "agent harness",   "ail"),

    # Cross-cutting
    (r"\b(upstream|sync|weekly)\b",                      "upstream sync",   "_meta"),
    (r"\b(commit|pr|push|merge)\b",                      "git pr workflow", "github"),
    (r"\b(test|failing test|red green|tdd)\b",           "tdd discipline",  "software-development"),
    (r"\b(review|code review|simplify)\b",               "code review",     "software-development"),
    (r"\b(debug|traceback|root cause|why is)\b",         "debug",           "software-development"),
]


# ---- Source loaders ---------------------------------------------------------

def load_hermes(db_path: str, limit: int):
    """Read the most recent user messages from a Hermes SQLite session DB."""
    if not os.path.exists(db_path):
        return None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        # Hermes schema: messages(role, content, created_at, session_id)
        rows = cur.execute(
            "SELECT session_id, role, content, created_at "
            "FROM messages "
            "WHERE role = 'user' "
            "ORDER BY created_at DESC "
            "LIMIT ?",
            (limit * 3,),  # grab extra; some will be short
        ).fetchall()
        conn.close()
        return [(r["session_id"], r["content"], r["created_at"]) for r in rows]
    except Exception as e:
        print(f"[warn] Hermes DB read failed: {e}", file=sys.stderr)
        return None


def load_claude_jsonl(sessions_dir: str, limit: int):
    if not os.path.isdir(sessions_dir):
        return None
    files = sorted(glob.glob(os.path.join(sessions_dir, "*.jsonl")),
                   key=os.path.getmtime, reverse=True)
    out = []
    for fp in files:
        with open(fp) as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    if rec.get("role") == "user":
                        out.append((os.path.basename(fp),
                                    rec.get("content", ""),
                                    rec.get("timestamp", "")))
                except json.JSONDecodeError:
                    continue
                if len(out) >= limit * 3:
                    return out
    return out


def load_claude_export(path: str, limit: int):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        data = json.load(f)
    # Expecting {"conversations": [{"id":..., "messages":[{role,content}]}]}
    out = []
    for convo in data.get("conversations", []):
        for msg in convo.get("messages", []):
            if msg.get("role") == "user":
                out.append((convo.get("id", "?"), msg.get("content", ""), ""))
        if len(out) >= limit * 3:
            break
    return out


# ---- Workflow clustering ----------------------------------------------------

def cluster_messages(messages, limit):
    """Group messages by matched workflow, keep top `limit` user messages."""
    # Take the most recent `limit` first
    messages = messages[:limit]
    buckets = defaultdict(list)
    matched_any = 0
    for session_id, content, ts in messages:
        content_low = content.lower()
        matched = False
        for pat, name, scope in WORKFLOW_PATTERNS:
            if re.search(pat, content_low, re.IGNORECASE):
                buckets[(name, scope)].append((session_id, content[:140], ts))
                matched = True
                matched_any += 1
        if not matched:
            buckets[("uncategorized", "_meta")].append((session_id, content[:140], ts))
    return buckets, matched_any, len(messages)


# ---- Skill index cross-reference -------------------------------------------

def load_skill_index():
    """Return set of (workflow_name_lower) that already have a SKILL.md."""
    index_path = Path("skills/_meta/INDEX.md")
    if not index_path.exists():
        return set()
    text = index_path.read_text().lower()
    # Crude: any line in the table whose first cell is a known workflow
    existing = set()
    for line in text.splitlines():
        if "|" not in line:
            continue
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if cells and cells[0] not in ("scope", "---", ""):
            existing.add(cells[0])
    return existing


# ---- Output ----------------------------------------------------------------

def render_audit(buckets, matched, total, existing_skills, out_path):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    lines = []
    lines.append(f"# Skills / Agents Audit")
    lines.append(f"")
    lines.append(f"Generated: {today}  ·  Source: sessions DB  ·  Messages scanned: {total}  ·  Matched: {matched}")
    lines.append(f"")
    lines.append(f"This audit is the output of the `history-scan` skill. Run it again after")
    lines.append(f"building new skills to measure whether occurrences of those workflows drop.")
    lines.append(f"")
    lines.append(f"## Top workflows by frequency")
    lines.append(f"")
    lines.append(f"| # | Workflow | Sessions | Examples | Exists? | Priority | Suggested location |")
    lines.append(f"|---|----------|----------|----------|---------|----------|--------------------|")

    # Sort by count desc
    ranked = sorted(buckets.items(), key=lambda kv: -len(kv[1]))
    for i, ((name, scope), entries) in enumerate(ranked, 1):
        count = len(entries)
        examples = ", ".join(f"`{e[0]}`" for e in entries[:2])
        exists = "[x]" if name in existing_skills or name == "uncategorized" else "[ ]"
        if count >= 5:
            prio = "**HIGH**"
        elif count >= 2:
            prio = "MEDIUM"
        else:
            prio = "LOW"
        location = f"`skills/{scope}/{name}/SKILL.md`" if scope != "_meta" else f"`skills/{scope}/{name}/SKILL.md`"
        lines.append(f"| {i} | {name} | {count} | {examples} | {exists} | {prio} | {location} |")

    lines.append(f"")
    lines.append(f"## Uncategorized messages (no workflow match)")
    lines.append(f"")
    unc = buckets.get(("uncategorized", "_meta"), [])
    if unc:
        for sid, content, ts in unc[:10]:
            lines.append(f"- `{sid}`: {content}")
    else:
        lines.append(f"_None — every message matched a known workflow._")
    lines.append(f"")
    lines.append(f"## How to use this audit")
    lines.append(f"")
    lines.append(f"1. Pick the top 3 HIGH-priority workflows that do not yet have a skill.")
    lines.append("2. For each, read the example sessions to understand the user's \"what good looks like\".")
    lines.append(f"3. Use the `hermes-agent-skill-authoring` skill to scaffold a new `SKILL.md`.")
    lines.append(f"4. Re-run the scan next week — the count for that workflow should drop as Claude starts using the new skill.")
    lines.append(f"")

    out = "\n".join(lines)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(out)
    return out


# ---- Main ------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="memory/learnings/skills-audit.md")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--source", default=None,
                    help="Path to sessions source. Auto-detects if omitted.")
    args = ap.parse_args()

    msgs = None
    if args.source:
        if args.source.endswith(".db"):
            msgs = load_hermes(args.source, args.limit)
        elif args.source.endswith(".jsonl") or os.path.isdir(args.source):
            if os.path.isdir(args.source):
                msgs = load_claude_jsonl(args.source, args.limit)
            else:
                msgs = load_claude_jsonl(os.path.dirname(args.source), args.limit)
        elif args.source.endswith(".json"):
            msgs = load_claude_export(args.source, args.limit)
    else:
        # Auto-detect
        for path in [
            os.path.expanduser("~/.hermes/sessions.db"),
            os.path.expanduser("~/.claude/sessions"),
        ]:
            if os.path.isdir(path):
                msgs = load_claude_jsonl(path, args.limit)
                if msgs:
                    break
            elif os.path.exists(path):
                if path.endswith(".db"):
                    msgs = load_hermes(path, args.limit)
                else:
                    msgs = load_claude_export(path, args.limit)
                if msgs:
                    break

    if not msgs:
        print("ERROR: No session source found. Pass --source <path> explicitly.", file=sys.stderr)
        sys.exit(2)

    buckets, matched, total = cluster_messages(msgs, args.limit)
    existing = load_skill_index()
    audit = render_audit(buckets, matched, total, existing, args.output)
    print(audit)


if __name__ == "__main__":
    main()
