# Plan Archive

Shipped / completed plans kept for audit and historical context. **Do not read as current state** — the codebase has moved on since these landed.

| File | Status | Summary |
|---|---|---|
| [feature-agentic-org-phase-1-entity-graph.md](feature-agentic-org-phase-1-entity-graph.md) | Shipped | EntityGraph foundation, EntityReflector + projection registry, 12 per-domain projections, AppState wiring, `/api/entities` read API, blueprint observatory `/entities` page. |
| [feature-agentic-org-phase-2-compose-v4.md](feature-agentic-org-phase-2-compose-v4.md) | Shipped | compose-domain v4 — schema-aligned projections + sub-orchestrator phase generator. |
| [feature-agentic-org-phase-3-function-fms.md](feature-agentic-org-phase-3-function-fms.md) | Shipped | FUNCTIONS registry, AmbientAgent primitive + dispatcher, in-process MCP tools, FunctionFleetManager runtime, three concrete ambient agents, `/api/functions` route + observatory. |
| [feature-agentic-org-phase-4-ceo-fm.md](feature-agentic-org-phase-4-ceo-fm.md) | Shipped | Cadence loader + cron loop, `KpiStore`, precedent_query, three meta-workflows (`hire-to-productive` / `vendor-risk-to-pay` / `lead-to-cash`), CEO-FM, `/admin/org-clone`. |
| [feature-agent-governance-toolkit-1.md](feature-agent-governance-toolkit-1.md) | Completed (8/8 phases) | AGT v3.4 — 10/10 OWASP Agentic AI Top 10 coverage, in-process governance kernel, audit chain verification, evidence panel. |
| [feature-authority-and-personae-1.md](feature-authority-and-personae-1.md) | Completed | Authority matrix + persona registry — 32 personae across 14+5 domains. |
| [feature-fleet-domain-substrate-1.md](feature-fleet-domain-substrate-1.md) | Completed | Brought all six fleet-* domains to first-class FM substrate parity. |
| [refactor-rebrand-zava-1.md](refactor-rebrand-zava-1.md) | Completed | Legacy-brand → Zava rebrand (2026-05-08). |
| [feature-humanize-cosmic-lens-1.md](feature-humanize-cosmic-lens-1.md) | Shipped | Cosmic-lens humanization — every interactive surface reads as plain English via `web/shared/humanize.ts`. Shipped 2026-05-11 as Track F (`f1`–`f8`) of `refactor-repo-coherence-remediation-1.md`. |

## Why these were archived

Each carries a `status: Shipped` (or `Completed`) header, an `Update YYYY-MM-DD` line listing the implementation commits, and a "test count baseline → final" delta. The actual implementation is now part of the live substrate; the plan is no longer guidance — it is history.

## Cross-references

If you arrive here from a still-current doc that linked into `plan/`, that link was rewritten when the plan moved. Repo-relative paths inside these archived plans use `../../` (e.g. `../../api/server/state.py`). Sibling-plan refs use `name.md` for plans also in the archive and `../name.md` for plans still active in `plan/`.
