# Architecture — SBOSS ERPNEXT AM

> This document freezes the **three contracts** that the workstreams depend on.
> Changes to a contract require a signed-off RFC in `.orchestration/rfcs/`.

## System diagram

```
┌────────────────────────────────────────────────────────────────────┐
│                    Upstream (linked, not modified)                  │
│  ┌─────────────┐   ┌─────────────┐   ┌──────────────┐              │
│  │ Frappe      │   │ ERPNext     │   │ HRMS         │              │
│  │ Framework   │   │ v15.x       │   │              │              │
│  │ (MIT)       │   │ (AGPL-3.0)  │   │ (MIT)        │              │
│  └──────┬──────┘   └──────┬──────┘   └──────┬───────┘              │
│         │                 │                 │                       │
│         │     hooks       │   DocTypes      │  Salary Component     │
│         └────────────────┬┴─────────────────┘                       │
│                          │                                          │
│  ┌───────────────────────▼───────────────────────────────────────┐  │
│  │                Armosphera localization apps                  │  │
│  │                                                               │  │
│  │  apps/frappe_armenia ──┐    apps/frappe_uae ──┐               │  │
│  │  (Armosphera           │    (Armosphera       │               │  │
│  │   Proprietary)         │     Proprietary)     │               │  │
│  │                        │                       │               │  │
│  │  apps/frappe_ai_local ─┴──── (Armosphera Proprietary)         │  │
│  │                                                               │  │
│  │  uses:                                                        │  │
│  │  libs/frappe_localization_core (MIT) ─── number-to-words,     │  │
│  │                                          IBAN, ISO20022,       │  │
│  │                                          MT940, currency       │  │
│  │  libs/frappe_payroll_engine (MIT)   ──── generic payroll      │  │
│  │                                          calculator, EOSB,     │  │
│  │                                          social contrib        │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Local LLM layer (apps/frappe_ai_local)                      │  │
│  │  ┌──────────────┐    ┌──────────────────┐   ┌──────────────┐  │  │
│  │  │ Ollama       │───▶│ Gemma 4 E2B QAT       │   │ ChromaDB     │  │  │
│  │  │ (sidecar)    │    │ (GGUF, offline)  │   │ (embedded)   │  │  │
│  │  └──────────────┘    └──────────────────┘   └──────────────┘  │  │
│  │          │                     │                    │         │  │
│  │          └───────── LangGraph agent ────────────────┘         │  │
│  │                      │                                        │  │
│  │                      └─ 8+ Frappe-API tools (whitelisted)     │  │
│  └───────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

## App boundaries

| App | Owns | MUST NOT import from |
|---|---|---|
| `frappe_armenia` | `apps/frappe_armenia/frappe_armenia/**`, all DocTypes prefixed `AM ` | `frappe_uae`, `frappe_ai_local` (use `libs/` for shared) |
| `frappe_uae`     | `apps/frappe_uae/frappe_uae/**`, all DocTypes prefixed `AE ` | `frappe_armenia`, `frappe_ai_local` |
| `frappe_ai_local`| `apps/frappe_ai_local/frappe_ai_local/**`, DocTypes prefixed `AIL ` | `frappe_armenia`, `frappe_uae` (consume via REST API) |
| `frappe_localization_core` | `libs/frappe_localization_core/**` | anything outside `libs/` |
| `frappe_payroll_engine`    | `libs/frappe_payroll_engine/**` | anything outside `libs/` |

## Contract A — DocType names (frozen at W0-T12)

Every DocType we create **must** be prefixed with one of:

| Prefix | Country | Example |
|---|---|---|
| `AM ` | Armenia | `AM VAT Register Entry`, `AM E-Invoice Provider`, `AM Salary Component` |
| `AE ` | UAE | `AE VAT 201`, `AE Corporate Tax Dashboard`, `AE EOSB Accrual` |
| `AIL ` | AI layer | `AI Provider`, `AI Chat Session`, `AI Chat Message`, `AI Knowledge Source` |

The space after the prefix is **required** (matches Frappe's display name convention).

DocType `name` (the internal slug) follows the same prefix but in snake_case with no space:
- `AM VAT Register Entry` → `name = "AM VAT Register Entry"` (Frappe preserves the space)
- This means we never collide with upstream DocTypes.

## Contract B — AI Tool Whitelist (frozen at W0-T18)

The `frappe_ai_local` agent can only call Python functions registered in this whitelist:

```python
# apps/frappe_ai_local/frappe_ai_local/agent/tools.py
TOOL_WHITELIST = {
    # Read-only DocType access
    "frappe.get_doc",
    "frappe.get_all",
    "frappe.get_list",
    "frappe.get_value",
    "frappe.get_single_value",
    "frappe.count",
    "frappe.exists",

    # Country-app-exposed read tools (the 8+ tools in W3.b)
    "frappe_ai_local.api.tools.get_invoice",
    "frappe_ai_local.api.tools.get_customer_balance",
    "frappe_ai_local.api.tools.get_vat_register",
    "frappe_ai_local.api.tools.get_employee_eosb",
    "frappe_ai_local.api.tools.get_profit_and_loss",
    "frappe_ai_local.api.tools.get_outstanding_payables",
    "frappe_ai_local.api.tools.search_documents",

    # Draft creation only (never submit)
    "frappe_ai_local.api.tools.create_draft_invoice",

    # Reporting
    "frappe.desk.query_report.run",
}

# Explicit blacklist — these will NEVER be reachable
TOOL_BLACKLIST = {
    "frappe.delete_doc",
    "frappe.rename_doc",
    "frappe.db.sql",
    "frappe.db.sql_list",
    "frappe.db.sql_ddl",
    "frappe.db.set_value",
    "frappe.db.set_global",
    "frappe.db.commit",
    "os.system",
    "subprocess.run",
    "subprocess.Popen",
    "subprocess.call",
}
```

The agent runtime checks every LLM tool call against this whitelist before
executing. A call to a blacklisted function is rejected with a clear error
that the LLM sees and is told to find an alternative.

## Contract C — Shared library API (versioned, SemVer)

The two `libs/` packages follow [SemVer 2.0](https://semver.org/). Their
public API is what country apps can import.

### `frappe_localization_core` (v0.1.0)

```python
# Public API
from frappe_localization_core import (
    number_to_words,        # number_to_words(value: Decimal, lang: str) -> str
    iban_validator,         # iban_validator(iban: str, country: str) -> bool
    iso20022_parser,        # parse_camt053(xml: str) -> list[BankTransaction]
    mt940_parser,           # parse_mt940(text: str) -> list[BankTransaction]
    currency_format,        # format_currency(value: Decimal, currency: str) -> str
)
```

### `frappe_payroll_engine` (v0.1.0)

```python
# Public API
from frappe_payroll_engine import (
    calculator,             # compute_payslip(employee, period, components) -> Payslip
    eosb,                   # accrual(employee, as_of_date, country) -> Decimal
    social_contrib,         # compute(components, country_rates) -> dict[str, Decimal]
)
```

**Versioning rule:** a change to a public function signature is a BREAKING
change → major version bump → country apps must update and re-test. Adding
a new function or optional kwarg is MINOR.

## Bilingual conventions

- All user-facing strings use Frappe's `__("…")` translation system.
- Translations live in per-locale CSV files:
  - `apps/frappe_armenia/frappe_armenia/translations/hy.csv` (Armenian)
  - `apps/frappe_armenia/frappe_armenia/translations/ru.csv` (Russian, optional)
  - `apps/frappe_uae/frappe_uae/translations/ar.csv` (Arabic)
  - `apps/frappe_uae/frappe_uae/translations/en.csv` (English fallback)
  - `apps/frappe_ai_local/frappe_ai_local/translations/{hy,ar,en}.csv`

## Versioning policy

- We pin against a specific **ERPNext minor version** (e.g. `v15.3.0`).
- W6 upstream-sync runs **weekly**, opens PRs to update the pin.
- We do NOT track `develop` directly — that is unstable.
- A pin bump is a release; we run the full test suite + a 1-day staging
  deployment in the UAE staging tenant before shipping.

## Upstream-survivability contract (operator requirement, 2026-06-24)

**The localization modules MUST keep working after every upstream ERPNext
update.** This is a hard requirement, not a stretch goal. Concretely:

1. **No edits to upstream code.** The localization apps **link** to Frappe /
   ERPNext / HRMS via their public Python API and hooks. They never monkey-
   patch, never `git pull` upstream into our repo, never import private
   internals. If we need a feature that doesn't exist upstream, we **wrap**
   the API in `libs/frappe_localization_core` so the wrapper is the only
   thing we have to update.

2. **W6 weekly sync is mandatory.** Every Monday 04:00 UTC, CI:
   - Detects new `v15.x` tags in `frappe/frappe`, `frappe/erpnext`,
     `frappe/hrms`.
   - Bumps the pin in each app's `pyproject.toml`.
   - Runs the full unit + integration test suite.
   - If green, opens a PR with the new pin. If red, opens a
     `upstream-breakage` issue with the failing test list and tags the
     workstream owner.
   - Posts to Slack/Telegram webhook.

3. **Operator can trigger a sync on demand.** `Actions → Upstream Sync →
   Run workflow` (manual `workflow_dispatch`) is wired. So is the CLI
   equivalent: `bash infra/scripts/sync-upstream.sh open-pr` from a
   maintenance shell.

4. **Backwards-compatibility window.** Localization apps MUST work against
   the **last 3 minor versions** of ERPNext. So a customer on `v15.1.0`
   is supported when we ship against `v15.4.0`. This is enforced by a CI
   matrix in `unit-tests.yml` that runs the suite against multiple ERPNext
   pins.

5. **Rollback is one click.** Because we never modify upstream, rolling
   back to a previous ERPNext version is just `bench update --reset` plus
   pinning the old `pyproject.toml` constraint. We do not ship schema
   migrations that touch upstream tables.

6. **What if an upstream change breaks us anyway?** The W6 sync catches
   it within 7 days. The breakage is fixed in the wrapper layer, not in
   our app logic. A patch release ships within 48h of detection.

## Hosting topology

- **Local dev:** Docker Compose with bench + MariaDB + Redis + Ollama.
- **Armenia customers:** any Frappe Cloud region or self-hosted.
- **UAE customers:** `me-central-1` (AWS UAE) or self-hosted in UAE for
  data-residency compliance.
- **AI inference:** Ollama as a sidecar to the bench container, in the same
  VPC. GPU optional (CPU works for Gemma 4 E2B QAT at ~5–10 tokens/sec).
