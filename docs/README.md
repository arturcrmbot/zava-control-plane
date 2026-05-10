# Docs Index

What every file in this directory is for, and where the canonical truth
lives for any topic. Read top-down: each section answers "what's the one
place to look for X?".

## Quick links

| If you want… | Go to |
|---|---|
| The pitch this whole substrate carries | [blueprint.md](blueprint.md) |
| A walking tour of the codebase | [CODEBASE-TOUR.md](CODEBASE-TOUR.md) |
| Lab build vs engagement POC — what we ship locally vs what the bid commits to | [SCOPE-DELTA.md](SCOPE-DELTA.md) |
| POC1 acceptance-criteria status + remaining work | [poc1-status.md](poc1-status.md) |
| POC2 capability matrix + status | [poc2-status.md](poc2-status.md) |
| Code-anchored architecture reference | [ARCHITECTURE.md](ARCHITECTURE.md) |
| To run the stack | Root [README.md](../README.md) Quickstart (`make up`) |
| To run the POC2 demo | [poc2-quick-demo.md](poc2-quick-demo.md) (5–8 min) |
| To make a new domain show up on the blueprint page | [blueprint-microsite-contributor-guide.md](blueprint-microsite-contributor-guide.md) |
| How the visualisation surfaces work | [visualisation.md](visualisation.md) |
| To add a new visualisation layer (event, function, kind, cadence pip) | [visualisation-contributor-guide.md](visualisation-contributor-guide.md) |
| Where the observatory is going (4-zoom Org Building) | [superpowers/specs/2026-05-09-org-building-design.md](superpowers/specs/2026-05-09-org-building-design.md) |
| To compose a new domain end-to-end | [superpowers/skills/compose-domain/SKILL.md](superpowers/skills/compose-domain/SKILL.md) |
| Local dev setup | [DEVELOPMENT.md](DEVELOPMENT.md) |
| Verbatim Zava brief | [poc1-brief.md](poc1-brief.md) |
| Where the agentic-org direction is going (Plane 1 entity graph design) | [agentic-org-design.md](agentic-org-design.md) |

## Doc taxonomy

Docs fall into four buckets. Each topic has **one canonical home**;
everything else points at it.

### 1. Source documents (immutable inputs)

Never edited. Referenced as authoritative ground truth.

| File | Purpose |
|---|---|
| [poc1-brief.md](poc1-brief.md) | The Zava POC1 brief, verbatim. The 13 acceptance criteria live here. |

### 2. Living truth (canonical state of the build)

The single source for "what's true today". When facts change, edit here.

| File | Purpose | Owns |
|---|---|---|
| [poc1-status.md](poc1-status.md) | POC1 build state | The AC #1–13 table, per-claim 7-phase flow, remaining-work plan |
| [poc2-status.md](poc2-status.md) | POC2 build state | The 22-capability matrix, six work tracks, 12-week shape, current demo-ready state |
| [SCOPE-DELTA.md](SCOPE-DELTA.md) | Lab build vs engagement POC | What's identical, what swaps at engagement-POC time, what landed at the substrate level since the bid was written |
| [blueprint.md](blueprint.md) | The pitch (manuscript → press; case of type) | The argument the substrate is making to the audience; copy + reasoning |
| [agentic-org-design.md](agentic-org-design.md) | Forward design — first-slice Plane 1 (entity graph) on top of the existing 18-domain substrate | Five-plane decomposition; the next thing this substrate becomes |
| [visualisation.md](visualisation.md) | Canonical visualisation reference | Surface inventory (`?view=constellation` / `entities` / `functions` / `org-clone`); visual vocabulary; SSE event → visual mapping; performance budget |

### 3. Reference (how the codebase works)

These describe HOW, not WHAT-IS-DONE. Stable as long as the design holds.

| File | Purpose |
|---|---|
| [CODEBASE-TOUR.md](CODEBASE-TOUR.md) | Narrative walkthrough — three tiers, multi-domain pattern, what does what, talking points for visitors |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Code-anchored architecture: tier diagrams, file paths, MCP-tool list, runtime ports, identities, known limitations |
| [poc2-quick-demo.md](poc2-quick-demo.md) | 5–8 min POC2 hiring walkthrough — apply → triage → screen → interview → offer |
| [blueprint-microsite-contributor-guide.md](blueprint-microsite-contributor-guide.md) | The contract for making new skills/MCPs/domains appear on the blueprint page; also documents the Azure Container Apps deploy |
| [visualisation-contributor-guide.md](visualisation-contributor-guide.md) | How to add a new event, function, entity kind, or cadence pip to the visualisation surfaces. Companion to [visualisation.md](visualisation.md). |
| [blueprint-script.md](blueprint-script.md) | Designer brief / one-pager prompt for the printed version of the blueprint |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Local dev: prereqs, terminals, hot reload, test commands, debugging |
| [poc1-accuracy-runbook.md](poc1-accuracy-runbook.md) | Step-by-step for running the 300-claim ≥95% accuracy gate (AC #4) |
| [governance-poc3-adoption-guide.md](governance-poc3-adoption-guide.md) | How to land the AGT governance core into the POC3 worktree per CON-007 of `plan/feature-agent-governance-toolkit-1.md` |
| [../README.md](../README.md) | Repo-root entry point |

### 4. Archived

Historical docs kept for audit trail, all under [archive/](archive/).
**Do not read as current state.** See [archive/README.md](archive/README.md)
for the inventory.

### 5. Active plans + skills (`superpowers/`)

Generated by the writing-plans skill. One spec per major decision, one
plan per executable track. The `skills/` subdirectory holds the
authoring meta-skills the substrate uses to add new capability.

#### Author/compose meta-skills (`superpowers/skills/`)

These are the skills agents use to extend the substrate itself. Read
them before adding a new domain, skill, MCP tool, or persona.

| Skill | Purpose |
|---|---|
| [compose-domain](superpowers/skills/compose-domain/SKILL.md) | The end-to-end "compose a new business domain" meta-skill (now at v3). First proven by `fleet-travel-preapproval`. |
| [author-durable-domain](superpowers/skills/author-durable-domain/SKILL.md) | How to wire a new Durable orchestrator + activities + graphs |
| [author-runtime-skill](superpowers/skills/author-runtime-skill/SKILL.md) | How to add a `SKILL.md` (frontmatter, tool allow-list, prompt) |
| [author-mcp-tool](superpowers/skills/author-mcp-tool/SKILL.md) | How to add a new `@define_tool` under `api/server/mcp_tools/` |
| [author-persona](superpowers/skills/author-persona/SKILL.md) | How to add a persona (`api/server/personae/<name>/SKILL.md`) for the autonomous responder |
| [compose-persona](superpowers/skills/compose-persona/SKILL.md) | Higher-level persona composition |

#### Specs (`superpowers/specs/`) — design decisions

Most recent first.

| Spec | Subject |
|---|---|
| [2026-05-10-simulator-expansion-design.md](superpowers/specs/2026-05-10-simulator-expansion-design.md) | Org-simulation expansion — Tier 1-3 endpoints that drive the Org Building primitives on demand |
| [2026-05-09-org-building-design.md](superpowers/specs/2026-05-09-org-building-design.md) | "The Org Building" — 4-zoom 3D visualisation replacing the Constellation page |
| [2026-05-03-substrate-fix-design.md](superpowers/specs/2026-05-03-substrate-fix-design.md) | Substrate event vocabulary + personae + autonomous run loop |
| [2026-05-03-compose-domain-v3-design.md](superpowers/specs/2026-05-03-compose-domain-v3-design.md) | `compose-domain` v3 — encodes the substrate-fix contract |
| [2026-05-03-blueprint-microsite-design.md](superpowers/specs/2026-05-03-blueprint-microsite-design.md) | Editorial microsite + live observatory + interactive architecture |
| [2026-05-03-compose-domain-meta-skill-design.md](superpowers/specs/2026-05-03-compose-domain-meta-skill-design.md) | First version of the compose-domain meta-skill |
| [2026-05-01-recruiter-hitl-design.md](superpowers/specs/2026-05-01-recruiter-hitl-design.md) | Hiring Phase 7 three-wait HITL sequence |
| [2026-04-30-poc1-poc2-demo-ready-design.md](superpowers/specs/2026-04-30-poc1-poc2-demo-ready-design.md) | Demo-readiness pass |
| [2026-04-30-foundry-eval-integration-design.md](superpowers/specs/2026-04-30-foundry-eval-integration-design.md) | Foundry-backed accuracy harness |
| [2026-04-30-doc-intelligence-skill-design.md](superpowers/specs/2026-04-30-doc-intelligence-skill-design.md) | OCR + Document Intelligence skill |
| [2026-04-28-poc2-talent-lifecycle-design.md](superpowers/specs/2026-04-28-poc2-talent-lifecycle-design.md) | POC2 design spec |
| [2026-04-27-poc1-expense-compliance-pivot-design.md](superpowers/specs/2026-04-27-poc1-expense-compliance-pivot-design.md) | POC1 pivot decision spec |
| `fleet-*-brief.yaml` (6 files) | Domain briefs that fed `compose-domain`. All six graduated to `main` 2026-05-03 and brought to substrate parity 2026-05-04. |
| `controller-persona-brief.yaml` | Persona brief used by `compose-persona` |

#### Plans (`superpowers/plans/` and `plan/`)

Top-level feature plans live in [`../plan/`](../plan/); per-track
execution plans live here under `superpowers/plans/`. Most recent first.

| Plan | Status |
|---|---|
| [`../plan/refactor-rebrand-zava-1.md`](../plan/refactor-rebrand-zava-1.md) | Executed — legacy-brand → Zava rebrand (2026-05-08) |
| [`../plan/feature-fleet-domain-substrate-1.md`](../plan/feature-fleet-domain-substrate-1.md) | Executed — brought all six fleet-* domains to first-class FM substrate parity |
| [`../plan/feature-foundry-credibility-friday-1.md`](../plan/feature-foundry-credibility-friday-1.md) | Executed — Foundry tracing + real cost telemetry + immutable audit blob |
| [`../plan/feature-agent-governance-toolkit-1.md`](../plan/feature-agent-governance-toolkit-1.md) | Executed — AGT v3.4 (10/10 OWASP ASI coverage) |
| [2026-05-01-recruiter-hitl-gates.md](superpowers/plans/2026-05-01-recruiter-hitl-gates.md) | Executed |
| [2026-04-30-candidate-portal-plan.md](superpowers/plans/2026-04-30-candidate-portal-plan.md) | Executed |
| [2026-04-30-voice-real-plan.md](superpowers/plans/2026-04-30-voice-real-plan.md) | Executed |
| [2026-04-30-avatar-real-plan.md](superpowers/plans/2026-04-30-avatar-real-plan.md) | Executed |
| [2026-04-30-ag-ui-render-plan.md](superpowers/plans/2026-04-30-ag-ui-render-plan.md) | Executed |
| [2026-04-30-foundry-eval-integration.md](superpowers/plans/2026-04-30-foundry-eval-integration.md) | Executed |
| [2026-04-30-poc1-foundry-corpus-run-plan.md](superpowers/plans/2026-04-30-poc1-foundry-corpus-run-plan.md) | Executed |
| [2026-04-30-doc-intelligence-skill.md](superpowers/plans/2026-04-30-doc-intelligence-skill.md) | Executed |
| [2026-04-30-fleet-manager-demo-responsiveness.md](superpowers/plans/2026-04-30-fleet-manager-demo-responsiveness.md) | Executed |
| [2026-04-30-demo-ready-index.md](superpowers/plans/2026-04-30-demo-ready-index.md) | Index of demo-ready batches |
| [2026-04-29-poc1-remaining.md](superpowers/plans/2026-04-29-poc1-remaining.md) | Reference — POC1 remaining-work plan |
| [2026-04-28-poc2-track-a1-walking-skeleton.md](superpowers/plans/2026-04-28-poc2-track-a1-walking-skeleton.md) | Executed — POC2 spine |
| [2026-04-28-poc1-...-week2-domain-workflow.md](superpowers/plans/2026-04-28-poc1-expense-compliance-pivot-week2-domain-workflow.md) | Executed |
| [2026-04-27-poc1-...-week1-accuracy-spine.md](superpowers/plans/2026-04-27-poc1-expense-compliance-pivot-week1-accuracy-spine.md) | Executed |

## Where each topic has its single home

| Topic | Canonical home | Where it must NOT be re-stated |
|---|---|---|
| AC #1–13 status table | [poc1-status.md §1](poc1-status.md#1-acceptance-criteria--status) | Anywhere else (ARCHITECTURE.md only points at it) |
| POC2 22-capability matrix | [poc2-status.md §1](poc2-status.md#1-capability-matrix--starting-state) | — |
| Per-claim 7-phase flow chart (POC1) | [poc1-status.md §2](poc1-status.md#2-architecture) | Other docs reference, don't redraw |
| 10-phase hiring flow (POC2) | [poc2-status.md §2](poc2-status.md#2-architecture) | Same |
| Three-tier diagram | [CODEBASE-TOUR.md](CODEBASE-TOUR.md) (ASCII) + [ARCHITECTURE.md](ARCHITECTURE.md) (ASCII) — same shape, different audience | Don't add a third copy elsewhere |
| Skill list | Walked from `api/server/skills/*/SKILL.md` at runtime; surfaced live by [`/api/blueprint/composition`](../api/server/routes/blueprint.py) | No hand-maintained list anywhere |
| MCP tool list | Walked from `api/server/mcp_tools/*.py` at runtime; surfaced live by [`/api/blueprint/composition`](../api/server/routes/blueprint.py) | No hand-maintained list anywhere |
| Persona list | [`api/server/personae/*/SKILL.md`](../api/server/personae/) | Reference by directory |
| Domain registry (the single source of truth for every per-domain integration fact) | [`api/shared/domains.py`](../api/shared/domains.py) | Other docs link, don't restate |
| Lab build vs engagement POC delta | [SCOPE-DELTA.md](SCOPE-DELTA.md) | Other docs link, don't restate |
| Substrate-parity work for the six fleet-* domains | [`../plan/feature-fleet-domain-substrate-1.md`](../plan/feature-fleet-domain-substrate-1.md) | Other docs link |
| Blueprint deploy procedure | [blueprint-microsite-contributor-guide.md §Deploying to Azure](blueprint-microsite-contributor-guide.md#deploying-to-azure) | Other docs link, don't re-document |
| Compose-domain procedure | [superpowers/skills/compose-domain/SKILL.md](superpowers/skills/compose-domain/SKILL.md) | Same |
| Port table | [README.md](../README.md) (canonical) + [CODEBASE-TOUR.md](CODEBASE-TOUR.md) + [ARCHITECTURE.md](ARCHITECTURE.md) — duplicated by intent (different entry points) | — |
| Mock MCP list | Many places — fine, mocks come up everywhere | — |
| Rebrand known issues (binary pixel-leaks from legacy-brand → Zava) | [archive/rebrand-known-issues.md](archive/rebrand-known-issues.md) | — |
| Governance core (AGT v3.4) for POC3 adoption | [governance-poc3-adoption-guide.md](governance-poc3-adoption-guide.md) | — |
| Visualisation surfaces + visual vocabulary + SSE event → visual mapping | [visualisation.md](visualisation.md) | Other docs link, don't restate |
| Adding a new visualisation layer | [visualisation-contributor-guide.md](visualisation-contributor-guide.md) | Other docs link, don't re-document |
