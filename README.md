# SBOSS ERPNEXT AM — Armosphera ERPNext Localization Platform

[![License: Armosphera Proprietary](https://img.shields.io/badge/license-Armosphera%20Proprietary-red)](./LICENSE-ARMOSPHERA.md)
[![ERPNext](https://img.shields.io/badge/ERPNext-v15.x-blue)](https://github.com/frappe/erpnext)
[![Python](https://img.shields.io/badge/Python-3.11+-green)](https://www.python.org)
[![Gemma 4 4B](https://img.shields.io/badge/LLM-Gemma%204%204B-orange)](https://huggingface.co)

> Three production-grade Frappe custom apps on top of upstream ERPNext v15.x that localize it for **Armenia** and the **UAE**, plus a **local LLM** (Gemma 4 4B via Ollama) AI agent layer that runs **fully offline** in HY/AR/EN.

## Apps

| App | Country | Status | Description |
|---|---|---|---|
| [`apps/frappe_armenia`](apps/frappe_armenia/)  | Armenia 🇦🇲 | planned (Phase 1) | COA, VAT 20%, profit tax 18%, e-invoice, payroll, banking, HY/EN bilingual |
| [`apps/frappe_uae`](apps/frappe_uae/)          | UAE 🇦🇪     | planned (Phase 2) | VAT 5%, corporate tax 9%, e-invoicing (Peppol), EOSB, Arabic RTL, banking |
| [`apps/frappe_ai_local`](apps/frappe_ai_local/) | Both      | planned (Phase 3) | Local-LLM AI agent + chat (Ollama + Gemma 4 4B), offline-capable, HY/AR/EN |

## Shared libraries (MIT)

- [`libs/frappe_localization_core`](libs/frappe_localization_core/) — country-agnostic helpers (number-to-words, IBAN, ISO20022, MT940, currency)
- [`libs/frappe_payroll_engine`](libs/frappe_payroll_engine/) — generic payroll calculation engine

## Quickstart (local dev)

```bash
# 1. Clone
git clone https://github.com/armosphera/SBOSS-ERPNEXT-AM.git
cd SBOSS-ERPNEXT-AM

# 2. Boot the dev stack (bench + MariaDB + Redis + Ollama)
docker compose -f infra/compose/dev.yml up -d

# 3. Inside the bench container
bench new-site erpnext.localhost
bench --site erpnext.localhost install-app erpnext hrms
bench get-app apps/frappe_armenia
bench --site erpnext.localhost install-app frappe_armenia
# ... same for frappe_uae and frappe_ai_local
```

## How to work a task (AI agents)

Read [`AGENTS.md`](AGENTS.md) first. Tasks live in [`.orchestration/tasks/`](.orchestration/tasks/); claim one with:

```bash
bash tools/swarm/run-task.sh W1-T04
```

The claim is atomic, the branch is created, and a TDD template is given to you.

## Status

This repo is in **Phase 0 — Foundation**. We are landing:

- Monorepo skeleton ✅
- Swarm CLI (claim / release / isolation check) ✅
- Architecture with frozen contracts A/B/C ✅
- 3 worked-example task files ✅
- Local LLM plan (Ollama + Gemma 4 4B) ✅
- AI agent integration (Claude Code, Codex) ✅

Coming next: Docker dev stack, CI workflows, the three `bench new-app` scaffolds.

## Roadmap

See [`.orchestration/roadmap.md`](.orchestration/roadmap.md) (4 phases, 18 months).

## License

- `apps/*` — [Armosphera Proprietary License](./LICENSE-ARMOSPHERA.md)
- `libs/*` — MIT
- Upstream (ERPNext, Frappe, HRMS) — their original licenses (AGPL-3.0 / MIT)

We **link** to upstream open-source components; we do not fork or redistribute them.

## Contact

- licensing@armosphera.com — for commercial licensing of the proprietary apps
- dev@armosphera.com — for engineering inquiries

---

**This is a planning milestone. The code that runs in production is shipping per the [master plan](./.hermes/plans/2026-06-24_142129-erpnext-armenia-uae-localization.md).**
