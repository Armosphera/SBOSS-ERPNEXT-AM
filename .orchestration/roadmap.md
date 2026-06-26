# SBOSS ERPNEXT AM — Build Roadmap

> This file is auto-generated from the master plan. Do not edit by hand.
> Source: `.hermes/plans/2026-06-24_142129-erpnext-armenia-uae-localization.md`
> Regenerate with: `python tools/swarm/codegen-task.py --roadmap`

## Phase 0 — Foundation (Month 1)

**Goal:** monorepo boots, bench up, tests green, swarm tooling functional.

| W0-T | Title | Est |
|---|---|---|
| W0-T01 | Create monorepo SBOSS-ERPNEXT-AM on GitHub (AGPL-3.0 LICENSE) | 0.5h |
| W0-T02 | AGENTS.md at repo root | 1h |
| W0-T03 | .orchestration/roadmap.md (generated) | 1h |
| W0-T04 | .orchestration/state.json schema | 0.5h |
| W0-T05 | expected-repos.json + check-portfolio-drift.js | 0.5h |
| W0-T06 | infra/docker/dev.Dockerfile | 2h |
| W0-T07 | infra/compose/dev.yml | 1.5h |
| W0-T08 | bench new-site + install erpnext v15.x | 1h |
| W0-T09 | install frappe/hrms v15.x | 0.5h |
| W0-T10 | scaffold frappe_armenia | 1h |
| W0-T11 | scaffold frappe_uae | 1h |
| W0-T12 | scaffold frappe_ai_local | 1h |
| W0-T13 | pyproject.toml for frappe_localization_core | 1h |
| W0-T14 | pyproject.toml for frappe_payroll_engine | 1h |
| W0-T15 | ci/github-actions/unit-tests.yml | 2h |
| W0-T16 | ci/github-actions/lint.yml | 1h |
| W0-T17 | ci/pre-commit-config.yaml | 0.5h |
| W0-T18 | docs/architecture.md (frozen contracts) | 3h |
| W0-T19 | ci/github-actions/upstream-sync.yml | 1.5h |
| W0-T20 | infra/scripts/sync-upstream.sh | 3h |
| W0-T21 | tools/swarm/run-task.sh | 3h |
| W0-T22 | tools/swarm/verify-isolation.py | 1.5h |
| W0-T23 | state.json schema validator | 0.5h |
| W0-T24 | first green CI on main | 1h |
| W0-T25 | tag v0.0.1-foundation | 0.25h |

**Exit criteria:** `docker compose -f infra/compose/dev.yml up` brings a working bench; all 3 apps install; CI green; swarm CLI functional.

## Phase 1 — Armenia MVP (Months 2–4)

**Goal:** `frappe_armenia v0.1.0` shipped; first pilot customer in Yerevan.

| Workstream | Tasks | Hours |
|---|---|---|
| W1.a Setup wizard + COA | W1-T01..T07 | 16h |
| W1.b VAT | W1-T10..T17 | 20h |
| W1.c E-invoice | W1-T20..T27 | 30h |
| W1.d Payroll | W1-T30..T36 | 22h |
| W1.e Banking | W1-T40..T45 | 16h |
| W1.f Bilingual print formats | W1-T50..T55 | 8h |

## Phase 2 — UAE MVP (Months 5–7)

**Goal:** `frappe_uae v0.1.0` shipped; first UAE pilot.

| Workstream | Tasks | Hours |
|---|---|---|
| W2.a Setup + COA | W2.a-T01..T07 | 16h |
| W2.b VAT | W2.b-T10..T17 | 20h |
| W2.c Corporate tax | W2.c-T20..T27 | 20h |
| W2.d E-invoicing (Peppol) | W2.d-T30..T37 | 60h |
| W2.e Payroll + EOSB | W2.e-T40..T47 | 40h |
| W2.f Banking | W2.f-T50..T55 | 30h |
| W2.g Arabic print formats | W2.g-T60..T66 | 15h |
| W2.h FTA VAT return export | W2.h-T70..T73 | 10h |

## Phase 3 — High-Value Modules (Months 8–13)

**Goal:** E-invoice live in both countries; AI agent MVP; upstream sync.

| Workstream | Tasks |
|---|---|
| W3.a AI infra (Ollama + Gemma 2 2B) | W3-T01..T07 |
| W3.b Agent tools (8+ Frappe tools) | W3-T10..T20 |
| W3.c RAG (ChromaDB + multilingual embeddings) | W3-T30..T35 |
| W3.d Chat widget | W3-T40..T46 |
| W3.e Bilingual prompts | W3-T50..T55 |
| W6 Upstream sync | W6-T01..T08 |

## Phase 4 — Market Leadership (Months 14–18)

**Goal:** Two paying customers per country; partner channel; AI chatbot GA.

- Industry packs (Manufacturing, Agriculture, Holding)
- SaaS hosting
- Partner directory listing
- Frappe partner program progression (Bronze → Silver → Gold)
