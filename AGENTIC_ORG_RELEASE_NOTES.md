# Agentic Org Blueprint — Phases 1-4 Shipped

> **Branch:** `feature/agentic-org-phase-1-entity-graph`
> **Spec:** [`docs/agentic-org-blueprint.md`](docs/agentic-org-blueprint.md) (v3, locked 2026-05-08)
> **Plans:**
> - [`plan/feature-agentic-org-phase-1-entity-graph.md`](plan/feature-agentic-org-phase-1-entity-graph.md) — Plane 1 (entity graph)
> - [`plan/feature-agentic-org-phase-2-compose-v4.md`](plan/feature-agentic-org-phase-2-compose-v4.md) — `compose-domain` v4 (sequential enrichment pipeline)
> - [`plan/feature-agentic-org-phase-3-function-fms.md`](plan/feature-agentic-org-phase-3-function-fms.md) — Plane 2 (Function FMs)
> - [`plan/feature-agentic-org-phase-4-ceo-fm.md`](plan/feature-agentic-org-phase-4-ceo-fm.md) — Plane 4 (CEO-FM, cadences, meta-workflows, observatory)

## Headline numbers

| Metric | Value |
|---|---|
| Commits on the branch | 31 |
| Files added/modified | 200 (+16,397 lines, -36 lines) |
| Test count delta | 154 baseline → **1,018 passing** (+864 tests) |
| Pre-existing failures (unrelated) | 5 failed + 12 errored — all in `accuracy_route`, `concur_claim`, `workday_claim`, `evals_route`, `audit_chain` (verified pre-existing on `e1177fa7` baseline before any of this work) |
| Frontend build | ✅ Vite + TypeScript clean (3 new observatory pages: `EntitiesPage`, `FunctionsPage`, `OrgClonePage`) |
| Plan status | All 4 plans → `Shipped` |

## What landed

### Phase 1 — Plane 1: Entity Graph (sub-phases 1-7)

**Foundation** (sub-phase 1): KuzuDB-backed `EntityGraph` with 8 node tables (Person/Organisation/Asset/Money/Decision/Place/Period/Workflow) + 10 rel tables (incl. forward-compatible `SUB_WORKFLOW_OF` for Phase 4's meta-workflow tree). Self-rolled monotonic ULID; per-`(workflow_id, phase)` dedupe lock for `record_decision`; Cypher passthrough (`query`/`query_one`/`find_by_pattern`); 8 entity API methods (`upsert`/`link`/`get`/`by_type`/`linked`/`touched_by`/`record_decision`/`bootstrap_from_fixtures`); defense-in-depth (kind whitelist + rel whitelist + attr-key regex + Decision-aware metadata filter); thread-safe ULID + connection lock; close()/context-manager.

**Reflector + projections** (sub-phases 2-3): `EntityReflector` subscribes to `EventBus.on_any`; per-op exception isolation; PROJECTIONS registry auto-populates from per-domain modules; 12 per-domain projection modules (`ap_invoice`, `purchase_order`, `vendor_kyc`, `treasury_fx`, `contract_renewal`, `employee_onboarding`, `perf_review`, `travel_preapproval`, `it_access_request`, `contract_review`, `privacy_dpia`, `creative_campaign`); schema-aligned attrs (extras → `attributes` JSON blob); schema-incompatible rels dropped (Money→OWNS→Asset etc.).

**Wiring + API + observatory** (sub-phases 4-7): `AppState.__init__` wires governance kernel + entity graph + bootstrap + reflector in correct order (race-free); `reflector.entity_reflector` registered as system actor in `AGENTS` + `tools.yaml`; `/api/entities` HTTP API (5 endpoints: list/detail/linked/touched-by/_stats); blueprint observatory `EntitiesPage` polling `/api/entities/_stats` every 5s; in-process smoke test as CI proxy for live profile-autonomous run.

### Phase 2 — `compose-domain` v4 (design-time)

Sequential enrichment pipeline (5 sub-skills): `author-domain-skeleton` → `author-entity-projection` (+codegen for `entity_projections/<wt>.py`) → `author-decision-mapping` (+Cypher codegen for `precedent_queries/<wt>_<phase>.cypher`) → `author-function-membership` (+`graduate.sh` patcher with guarded skip) → `author-ambient-trigger` (+codegen for `ambient_agents/<function>.py`). Brief schema v4 (`brief.schema.yaml`); 12 v4 brief backfills + a fresh `fleet-purchase-card` brief proving substrate-by-construction.

### Phase 3 — Plane 2: Function FMs

**Registry + primitive + dispatch loop** (IP1-3): `FUNCTIONS` registry with 11 keys (10 non-legacy + ceo); `Domain.function` derived back-ref + boot orphan validator; kill-switch trailing-wildcard matcher (`ambient.*`, `cadence.*`, `reflector.*`); `AmbientAgent` primitive with `BusTrigger`/`CypherTrigger`/`CadenceTrigger` discriminated union; `AmbientDispatcher` with bus subscription + cypher sweep + `dispatch()` public entrypoint (used by Phase 4's cadence loop).

**MCP tools + FunctionFleetManager** (IP4-5): 5 in-process MCP tools (`query_fleet_state`, `query_kpi`, `query_recent_decisions`, `query_entity`, `find_entities` with Cypher write-verb deny-list); `FunctionFleetManager = FleetManagerService` alias; per-function FM session per non-legacy function (9 FMs total); per-function SSE topics (`fleet-manager.<name>`).

**Concrete agents + observatory** (IP6-7): 3 concrete ambient agents (BudgetVarianceWatcher, VendorRiskWatcher, AccessAnomalyWatcher) + 3 cadence-trigger agents added in Phase 4 (MorningSweep, PeriodClose, QuarterlyOkr); `/api/functions` HTTP API + per-function SSE proxy; blueprint observatory `FunctionsPage` (9-tile grid + drill-down).

### Phase 4 — Plane 4: CEO-FM, cadences, meta-workflows, observatory

**Cadence + KPI + precedent** (IP1-3): YAML cadence loader (`croniter`-backed) + async loop in `AppState`; 3 cadence YAMLs (morning-sweep, period-close, quarterly-okr); `KpiStore` (sqlite, schema-versioned per snapshot); `FunctionFleetManager.publish_kpi`; `query_precedents` MCP tool registered with persona responder.

**Meta-workflows + CEO-FM** (IP4-6): compose-v4 sub-orchestrator phase generator (`kind: sub_orchestrator` + `target_workflow_type` + `payload_from` + `parallel_group` → emits `context.call_sub_orchestrator` + `task_all` patterns + `workflow.sub_spawned` audit instrumentation); 3 meta-workflow briefs (`hire-to-productive`, `vendor-risk-to-pay`, `lead-to-cash`); CEO-FM (function `ceo`) graduated; `query_function_fm` MCP tool; `fy-close` + `board-prep` strategic CEO-FM domains.

**Tree + observatory + governance + smoke** (IP7-9): `MetaWorkflowReflector` writes `SUB_WORKFLOW_OF` rels on `workflow.sub_spawned` events; `/api/workflows/{id}/tree` recursive tree endpoint; `/api/functions/{name}/ambient` (last-trigger + last-spawn-outcome ring buffer); `/api/cadences` schedule view; blueprint `OrgClonePage` (5-panel observatory: entity counts + meta-workflow trees + ambient agents per function + KPI snapshots + cadence schedule); `?view=org-clone` routing; audit event registry doc (`AUDIT_EVENT_REGISTRY` enumerating `workflow.sub_spawned`, `cadence.tick`, `decision.recorded`, `entity.write.failed`, `ambient.decided`, `governance.find_entities*`); `economics.record_ambient_cost` for ambient `reasoning_skill` LLM calls (DEC-OQ4); end-to-end org-clone smoke test.

## §12 open questions resolved (Phase 4)

| OQ | Decision | Where |
|---|---|---|
| OQ1 — precedent retrieval shape | Tool call (`query_precedents`) registered with persona responder | `api/server/mcp_tools/query_precedents.py` |
| OQ2 — CEO-FM operator surface | Same shape as function FM, distinct page | `?view=org-clone` page |
| OQ3 — KPI schema versioning | Per-snapshot `schema_version` | `api/server/services/kpi_store.py` |
| OQ4 — ambient `reasoning_skill` economics | Existing economics ledger via `cost_kind="ambient_reasoning"` + `actor=f"ambient.{agent_name}"` | `api/server/services/economics.py` |
| OQ5 — meta-workflow visualisation | `/api/workflows/{id}/tree` recursive endpoint + tree widget on the org-clone page | `api/server/routes/workflows.py` |

## Locked decisions (blueprint §10) — verification

| # | Decision | Status |
|---|---|---|
| 1 | KuzuDB embedded property graph | ✅ `kuzu==0.6.1` pinned + `_NODE_TABLES`/`_REL_TABLES` schema |
| 2 | FUNCTIONS owns; Domain.function derived back-ref | ✅ `_wire_function_back_refs()` at import |
| 3 | No tenancy | ✅ Zero `TenantState` references; no per-tenant paths |
| 4 | ULID Decision id with `(workflow_id, phase, persona_role)` dedupe | ✅ `_ulid()` + per-key threading.Lock |
| 5 | Trigger discriminated union (bus/cypher/cadence) | ✅ `BusTrigger`/`CypherTrigger`/`CadenceTrigger` |
| 6 | Per-fork catalogue | ✅ Briefs in `docs/superpowers/specs/` (Zava is canonical) |
| 7 | PersonaTree on FUNCTIONS | ✅ `Function.persona_hierarchy: PersonaTree` |
| 8 | POC1/POC2 deprioritised; `function="legacy"` placeholder | ✅ `expense-claim`/`hiring` → legacy; no projections |
| 9 | Hybrid FM context (static identity + 5 tools) | ✅ `_function_identity_section` + 5 in-process MCP tools |

## Known follow-ups (deferred — not blocking)

- **Schema rel-direction widening (Phase 2 future work):** Phase 1 dropped 5 rel-direction-incompatible rels (Money→OWNS→Asset, Money→TRANSACTS→Org, Org→TRANSACTS→Org, Asset→TRANSACTS→Org, Asset→LOCATED_IN→Place). Cross-cutting semantic links are preserved via entity attributes + `source_workflows` arrays. If FM queries need richer rel directions, widen the Kuzu schema.
- **3 forward-declared workflow_types:** `variance-investigation`, `access-review`, `vendor-kyc-rescreen` are referenced by ambient agents' `spawnable_workflow_types` but don't have orchestrators yet. The dispatcher logs + skips on unknown wt. Land via compose-v4 graduation when needed.
- **Stub `query_function_fm`:** today returns a stub `{function, response: "<stub>", kpi_snapshot}` — a real LLM-backed FM session call would land when the CEO-FM is exercised in the live profile-autonomous run.
- **Real `profile-autonomous.sh` smoke (TASK-039):** the in-process integration test covers the same contract; running the live script is operator-side validation.
- **Pre-existing failures + errors:** 5 failed + 12 errored in `accuracy_route`, `concur_claim`, `workday_claim`, `evals_route`, `audit_chain` — all confirmed pre-existing on the `e1177fa7` baseline. Untouched by this work.
