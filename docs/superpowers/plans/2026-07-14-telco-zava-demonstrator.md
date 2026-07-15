---
goal: Build a demonstrable Telco Zava across simulator, workflows, agents, governance, graph and UI
version: 1.0
date_created: 2026-07-14
last_updated: 2026-07-14
owner: Zava engineering
status: Planned
tags: [feature, telco, simulator, durable-functions, agents, entity-graph, visualisation]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This plan converts the shipped network-incident simulator proof into a Telco
Zava demonstrator. It implements two end-to-end slices:

1. network incident -> recovery -> proactive customer care;
2. service order -> network feasibility -> activation.

Design authority:
[`2026-07-14-telco-zava-demonstrator-design.md`](../specs/2026-07-14-telco-zava-demonstrator-design.md).

> **For agentic workers:** Execute phases in order. Within a phase, tasks may
> run in parallel only when the Dependencies column permits it. Use TDD for
> every code task. Do not begin the next phase until its completion gate passes.

## 1. Requirements & Constraints

- **REQ-001**: Keep `ActorWorldService` and `NetworkScenario` authoritative for
  live telco actor state.
- **REQ-002**: Actor-triggered responders must create normal `Workflow` records
  in `StateStore`.
- **REQ-003**: Actor-triggered responders must emit canonical workflow/Durable
  checkpoints so Feed, history, AG-UI, entity reflection and Constellation
  consume the same lifecycle.
- **REQ-004**: One telco world must route at least three objective types:
  network recovery, proactive customer care and service activation.
- **REQ-005**: Every world mutation must pass `CommandGateway` and
  scenario-level atomic validation.
- **REQ-006**: Every accepted command must reach an evidence-backed terminal
  evaluation and objective state.
- **REQ-007**: Commercial actions above configured limits must use existing
  authority/HITL paths.
- **REQ-008**: Entity graph projections must preserve actor-world authority;
  graph writes are read models only.
- **REQ-009**: `/world` must show network, customer, order and control lenses
  using real snapshot/journal data.
- **REQ-010**: Every telco workflow must be inspectable through existing AG-UI
  per-run SSE.
- **REQ-011**: Telco domains must pulse in existing Blueprint Constellation via
  standard workflow events.
- **REQ-012**: Default non-telco behaviour must remain unchanged when
  `ZAVA_VERTICAL` is unset.
- **REQ-013**: Local live proof must use real Azurite, Azure Functions, FastAPI
  and Playwright.
- **REQ-014**: Public proof must be recorded replay generated from a passing
  live trace; it must not claim live Functions execution.

- **SEC-001**: Keep HMAC verification on `/internal/durable-event`.
- **SEC-002**: Validate full command batches before any actor mutation.
- **SEC-003**: Keep graph writes behind existing governance/kill-switch checks.
- **SEC-004**: Do not expose raw customer PII; synthetic account IDs and
  generated attributes only.

- **CON-001**: `ZAVA_WORLD` selects one actor world per FastAPI process.
- **CON-002**: Current `WorldPackRegistration` supports one objective type.
- **CON-003**: Current network incident path does not create a Workflow record.
- **CON-004**: Current network incident activity is deterministic; do not label
  it as an LLM agent.
- **CON-005**: Current Kuzu graph has generic enterprise kinds; reuse them
  before adding vertical node kinds.
- **CON-006**: Current world UI uses explicit support/telco React components;
  do not introduce a runtime UI DSL.
- **CON-007**: Functions worker must keep `ENTITY_PLANE_ENABLED=0` to avoid the
  Kuzu single-writer lock.

- **PAT-001**: Follow `NetworkScenario.apply_command()` for atomic,
  idempotent mutation.
- **PAT-002**: Follow generated fleet orchestrators for checkpoint, HITL,
  persona and external-event handling.
- **PAT-003**: Follow `EntityReflector` and per-domain projections for graph
  writes.
- **PAT-004**: Follow `WorldObjectiveStrip`, `WorldInterventionStrip` and
  event-backed pulse rules for visual state.
- **PAT-005**: Keep global `DOMAINS` and `FUNCTIONS` as sources of truth;
  vertical profile only filters.

## 2. Implementation Steps

### Implementation Phase 1 - Baseline and Telco profile

- **GOAL-001**: Establish repeatable baseline and a non-invasive Telco vertical
  selector.

| Task | Description | Dependencies | Completed | Date |
|---|---|---|---|---|
| TASK-001 | Run baseline tests with isolated graph data: `PORTAL_DATA_DIR=/tmp/zava-telco-baseline uv run --frozen --no-sync pytest -q tests/api/world/actor tests/api/server/services/entity_projections/test_network_incident_projection.py tests/api/routes/test_workflow_agui.py`. Save command/result in plan execution notes. | None | | |
| TASK-002 | Create `api/shared/verticals.py` with frozen `VerticalProfile(name, world, workflow_types, ramp_workflow_types)`. Telco declares the three hero workflow types and an empty ramp tuple because all three are event/API-driven. Add `active_vertical()` reading `ZAVA_VERTICAL`; unset returns `None`; unknown value raises `ValueError`. Add `registered_workflow_types()` that intersects the profile with live `DOMAINS`, so predeclared future types never reach runtime consumers before graduation. | None | | |
| TASK-003 | Add `tests/api/shared/test_verticals.py` covering unset, telco and unknown values. | TASK-002 | | |
| TASK-004 | Modify `api/server/main.py` world startup so `ZAVA_VERTICAL=telco` supplies default world `telco` only when `ZAVA_WORLD` is unset. Explicit `ZAVA_WORLD` remains authoritative. | TASK-002 | | |
| TASK-005 | Modify `api/server/services/blueprint_inventory.py::_build_domain_manifest()` to filter live domains by `registered_workflow_types()`. Do not mutate `DOMAINS`. | TASK-002 | | |
| TASK-006 | Modify `api/server/services/simulator_orchestrator.py::ramp_loop()` so an unset `SIMULATOR_RAMP_DOMAINS` uses active profile `ramp_workflow_types`; Telco empty tuple means no timer-spawned hero workflows. Explicit CSV still wins. Preserve `spawn_network_incident_workflow()` only for registry/spawn compatibility. | TASK-002 | | |
| TASK-007 | Add profile tests for composition output and ramp-domain selection. | TASK-004, TASK-005, TASK-006 | | |

**Completion gate:** Default tests retain all existing domains; Telco profile
returns only currently registered Telco workflow types and boots
`ZAVA_WORLD=telco`.

### Implementation Phase 2 - Canonical actor-workflow lifecycle

- **GOAL-002**: Make the live network incident a first-class Zava Workflow.

| Task | Description | Dependencies | Completed | Date |
|---|---|---|---|---|
| TASK-008 | Extract non-HTTP event ingestion from `api/server/routes/internal_durable_event.py` into `api/server/services/workflow_event_ingestor.py::ingest(workflow_id, instance_id, kind, payload, at=None)`. Move history, store, phase, ledger, hub and FleetEvent updates without changing behaviour. Route keeps HMAC/body validation then calls the service. | Phase 1 | | |
| TASK-009 | Add `tests/api/server/services/test_workflow_event_ingestor.py` by moving behavioural assertions from route tests; keep route tests for auth/schema delegation. | TASK-008 | | |
| TASK-010 | Extract the reusable registered-domain Workflow factory from `simulator_orchestrator._build_strategic_workflow()` into `api/server/services/synthetic_data.py::build_registered_workflow()`. Derive initial phase from `DOMAINS[workflow_type].phases[0]`, not hardcoded `"Intake"`. Create `api/server/services/world_workflow_adapter.py`; `start(sensor_event, objective, responder, observation)` must call that factory, upsert the Workflow, return deterministic ID `<prefix>-<sensor_event_id>`, and store `objective_id`, `trace_id` plus observation under the payload key expected by the domain projection (`incident` for `network-incident`). | TASK-008 | | |
| TASK-011 | Add adapter methods `scheduled()`, `decided()`, `resolved()` and `failed()` that call `workflow_event_ingestor.ingest()` and update workflow payload/status. No direct duplicate phase/history logic. | TASK-010 | | |
| TASK-012 | Modify `api/server/services/world_bridge.py` to create the Workflow before scheduling Durable. Delete the current inline `f"{responder.prefix}-{trace_id}"` ID construction; the adapter-returned ID is the single ID used by StateStore, Durable payload, checkpoints, AG-UI and EntityReflector. Include ID/type/objective in orchestration payload; route every terminal path through adapter. | TASK-010, TASK-011 | | |
| TASK-013 | Make the network workflow phases truthful. Split `network_incident_activities.py` into deterministic impact-diagnosis and reroute-planning functions, register both in `function_app.py`, and checkpoint the matching phases in `network_incident.py`. Recovery verification is emitted by world evaluation. Update `api/shared/domains.py` and `network-incident-brief.yaml` so these phases are `deterministic` and `skills=()` unless real runtime skills are implemented. Do not emit terminal completion before world mutation/evaluation. | TASK-008 | | |
| TASK-015 | Add integration test proving one actor-triggered incident creates StateStore workflow, phases, orchestration history, workflow-scoped FleetEvents and AG-UI events. | TASK-012, TASK-013 | | |
| TASK-016 | Add test proving `EntityReflector` receives the live incident Workflow and writes Workflow + site Asset from `entity_projections/network_incident.py`. | TASK-012, TASK-013 | | |

**Completion gate:** Injected site failure appears in `/api/workflows`, has
phase history, emits AG-UI events, projects to Kuzu and produces standard
events accepted by `/api/blueprint/stream`.

### Implementation Phase 3 - Multi-objective routing and terminal evaluation

- **GOAL-003**: Support independent OSS/BSS responses from one causal incident.

| Task | Description | Dependencies | Completed | Date |
|---|---|---|---|---|
| TASK-017 | Add `ObjectiveRoute(sensor_id, objective_type, allowed_command_types, success_event_types, failure_event_types, evaluation_timeout_minutes)` to `api/server/world/registry.py`. Replace single objective fields with `objective_routes`. | Phase 2 | | |
| TASK-018 | Migrate support and telco registrations with current equivalent routes: support pressure -> reallocate workers; network anomaly -> reroute sessions. | TASK-017 | | |
| TASK-019 | Change `ObjectiveManager.open()` and `ActorWorldService.open_objective()` to accept the selected route. Preserve dedupe by `(objective_type, target_id)`. | TASK-017 | | |
| TASK-020 | Change `WorldBridge` in-flight latch from `trace_id` to sensor `event_id`. Resolve route before responder. Unknown route must journal `objective.unroutable`; no fallback. | TASK-017, TASK-019 | | |
| TASK-021 | Extend `Evaluation` in `api/server/world/model.py` with terminal status, final measurements, evidence IDs and completion time. | TASK-017 | | |
| TASK-022 | Create `api/server/world/evaluations.py::OutcomeEvaluator`. Match success/failure events by route + trace; enforce timeout; transition evaluation, objective and Workflow through adapter. Adapter must write the terminal Workflow payload before emitting `workflow.resolved`/`workflow.failed`. | TASK-021, TASK-011 | | |
| TASK-023 | Wire evaluator into `CommandGateway` and `ActorWorldService._publish_since()`. Start evaluation before scenario mutation, or explicitly scan the command journal slice, so immediate success events such as `site.recovered` cannot occur before the evaluator observes them. Publish evaluator-appended events in the same pass. | TASK-022 | | |
| TASK-024 | Preserve root site-failure trace through network anomaly, reroute and recovery in `api/server/world/packs/telco.py`. | TASK-020 | | |
| TASK-025 | Add tests for same-trace sibling objectives, duplicate sensor delivery, unknown sensor, success, failure and timeout. | TASK-020, TASK-023, TASK-024 | | |

**Completion gate:** Network objective reaches `resolved` from
`site.recovered`; same incident trace can concurrently host another objective.

### Implementation Phase 4 - Telco commercial actors and data

- **GOAL-004**: Add coherent BSS state to the existing telco world.

| Task | Description | Dependencies | Completed | Date |
|---|---|---|---|---|
| TASK-026 | Create `api/server/world/packs/telco_commercial.py` with mutable dataclasses `CustomerAccount`, `ServiceSubscription`, `ServiceOrder`, `Notification`, `CreditAdjustment`. IDs must be deterministic and JSON-viewable. | Phase 3 | | |
| TASK-027 | Extend `NetworkScenario.install()` to generate 2,000 accounts/subscriptions aligned with existing subscribers. Add `account_id` and `subscription_id` to `Subscriber`. | TASK-026 | | |
| TASK-028 | Add deterministic hero records: priority business account, vulnerable consumer, high-credit approval account and infeasible activation order. Assert exact IDs in tests. | TASK-027 | | |
| TASK-029 | Extend `render_state()` with accounts, subscriptions, orders, notifications, credits and derived customer-impact projection. | TASK-027 | | |
| TASK-030 | On session degradation, aggregate affected account/service IDs and emit one `sensor:customer_impact` event on the root incident trace. Event payload carries counts/sample IDs; full records come from `build_observation()`. | TASK-027, TASK-024 | | |
| TASK-031 | Add `apply_customer_remediation` command validation: affected accounts only, unique action/account, non-negative credit, authority marker present, supported channel, full-batch atomicity and command-ID idempotence. | TASK-026 | | |
| TASK-032 | Accepted remediation creates Notification/CreditAdjustment actors, updates account totals and emits `notification.sent`, `credit.applied`, `care.completed`. | TASK-031 | | |
| TASK-033 | Add deterministic-generation, impact-mapping, command-rejection, atomicity and idempotence tests. | TASK-027, TASK-030, TASK-032 | | |

**Completion gate:** One site failure deterministically identifies real impacted
accounts and can atomically apply validated care actions.

### Implementation Phase 5 - Proactive customer-care domain

- **GOAL-005**: Add a real agentic/HITL BSS workflow responding to world impact.

| Task | Description | Dependencies | Completed | Date |
|---|---|---|---|---|
| TASK-034 | Author `docs/superpowers/specs/proactive-customer-care-brief.yaml` with phases Impact Assessment (deterministic), Entitlement Decision (agent), Credit Approval (HITL), Care Execution (agent), Outcome Verification (deterministic). Function: `customer-success`. | Phase 4 | | |
| TASK-035 | Run compose-domain in sandbox and graduate the domain. Apply documented hand-stitches to `function_app.py`, `api/shared/domains.py`, `api/shared/functions.py`, constants, spawner, projection registration and authority surfaces. | TASK-034 | | |
| TASK-036 | Implement agent skill for entitlement decision using impacted account/SLA context. Output structured actions and aggregate credit exposure; no world mutation. | TASK-035 | | |
| TASK-037 | Add customer-care MCP tools for policy lookup, notification preparation and credit preparation. Tool calls must be visible through existing executor/AG-UI events. | TASK-035 | | |
| TASK-038 | Add authority matrix rules and `web/client/components/apex/AuthorityCard.tsx` mapping. Reuse existing `cs_manager` persona and byte-match its `external_event: cs_manager_decision`. Credits below threshold auto-resolve; high aggregate credit reaches `cs_manager` HITL. Run this profile with `AGT_ENFORCE=1` only after authority-resolution tests pass. | TASK-035 | | |
| TASK-039 | Ensure orchestrator output includes typed `apply_customer_remediation` command accepted by `WorldBridge`. Replace the generated pre-command `workflow.completed` checkpoint with a non-terminal decision-ready checkpoint; the adapter emits terminal workflow status only after `care.completed` evaluation. Add responder/objective route registrations and set responder timeout to 300 seconds so deterministic demo HITL can resolve before timeout. | TASK-035, TASK-031 | | |
| TASK-040 | Add end-to-end service test covering low-credit auto path and high-credit HITL path. | TASK-036, TASK-037, TASK-038, TASK-039 | | |

**Completion gate:** Customer-impact sensor creates a normal agentic workflow,
shows tool reasoning in AG-UI, exercises HITL for the hero account and resolves
from `care.completed`.

### Implementation Phase 6 - Entity and decision graph

- **GOAL-006**: Make Telco identities, actions and decisions queryable without
  duplicating live-world authority.

| Task | Description | Dependencies | Completed | Date |
|---|---|---|---|---|
| TASK-041 | Extend `api/server/services/entity_graph.py` with generic relationships `HOLDS_ACCOUNT` (Person->Account), `SUBSCRIBED_TO` (Person->Asset), `HOSTED_ON` (Asset->Asset), and `DECIDED_ACCOUNT` (Decision->Account). Add mapping to `_DECIDED_REL_BY_KIND`. | Phase 5 | | |
| TASK-042 | Enhance `entity_projections/network_incident.py` to project final incident status and autonomous decision from live workflow payload. Keep site as Asset. | TASK-016 | | |
| TASK-043 | Implement proactive-care projection using Person, Account, Asset, Money, Workflow and Decision. Project material credits/notifications only; no session-tick writes. Import the module and add it to `_DOMAIN_MODULES` in `api/server/services/entity_projections/__init__.py`; missing registration is a silent reflector no-op. | TASK-035, TASK-041 | | |
| TASK-044 | Add projection and graph tests for account/service/site/credit relationships, Decision->Account and provenance via `source_workflows`. | TASK-041, TASK-042, TASK-043 | | |
| TASK-045 | Add route-level test proving `/api/entities`, precedents and decision replay expose the telco workflow after live incident execution. | TASK-044 | | |

**Completion gate:** Live incident/care trace is visible as connected
Workflow/Asset/Person/Account/Money/Decision graph data.

### Implementation Phase 7 - Telco operator visualisation

- **GOAL-007**: Present one coherent Telco workspace across existing surfaces.

| Task | Description | Dependencies | Completed | Date |
|---|---|---|---|---|
| TASK-046 | Extend `WorldState` wire types in `web/client/hooks/useWorldSimulation.ts` for accounts, subscriptions, orders, notifications and credits. | Phase 4 | | |
| TASK-047 | Refactor `TelcoWorld.tsx` into local lens components: `NetworkLens`, `CustomerImpactLens`, `OrderLens`, `ControlLens`. Keep scenario routing in `World.tsx`; do not add a UI DSL. | TASK-046 | | |
| TASK-048 | Network lens retains existing site/session proof. Customer lens shows impacted/notified/credited account lanes. Control lens shows objectives/evaluations/workflow links and causal journal. | TASK-047, Phase 5 | | |
| TASK-049 | Add links from objective/workflow IDs to existing Control Plane workflow drawer and Blueprint `?view=run&run_id=` AG-UI route. | TASK-015, TASK-048 | | |
| TASK-050 | Verify Telco profile composition drives Feed chips and Blueprint domain catalogue through existing `useDomainRegistry`; add only missing filter tests. | TASK-005, TASK-035 | | |
| TASK-051 | Add UI tests asserting every rendered account/order/status references snapshot data or a causal event. | TASK-048 | | |
| TASK-052 | Extend Constellation test with live telco standard workflow events; no telco-specific 3D component. | TASK-015, TASK-050 | | |

**Completion gate:** `/world`, Feed, AG-UI run view, Entities and Constellation
all show the same telco incident/care trace using shared IDs.

### Implementation Phase 8 - Order-to-activate proof slice

- **GOAL-008**: Prove business-driven BSS work can mutate OSS world state.

| Task | Description | Dependencies | Completed | Date |
|---|---|---|---|---|
| TASK-053 | Author and graduate `order-to-activate` composed domain with Order Validation, Network Feasibility agent, Exception Approval HITL, Activation and Verification. Function: `revenue`; operations support from `ops`. Replace generated pre-command terminal checkpoint with decision-ready; adapter emits terminal status after activation evidence. | Phase 5 | | |
| TASK-054 | Add `activate_service` scenario command validating account, order status, requested product, target-site capacity and idempotence before creating subscription/session actors. | TASK-026 | | |
| TASK-055 | Add network-feasibility observation/tool returning candidate sites and capacity; agent chooses bounded activation proposal. | TASK-053, TASK-054 | | |
| TASK-056 | Add `POST /api/world/inject/service_order` that creates a real `ServiceOrder` actor and emits `sensor:service_order`. Register an `order_activation` objective route so existing `WorldBridge`, adapter, evaluator and command gateway handle the workflow; do not add a second bridge or direct Functions-to-world mutation path. | TASK-053, TASK-054 | | |
| TASK-057 | Implement order activation graph projection using existing generic kinds and relationships. Import the module and add it to `_DOMAIN_MODULES` in `api/server/services/entity_projections/__init__.py`; add a registry-coverage test. | TASK-041, TASK-053 | | |
| TASK-058 | Populate Order lens and add happy-path plus infeasible-HITL browser tests. | TASK-047, TASK-056 | | |

**Completion gate:** A submitted order becomes a stored Durable workflow,
passes feasibility/governance, creates real service actors and resolves in UI
and graph.

### Implementation Phase 9 - Unmocked proof and replay

- **GOAL-009**: Produce repeatable live and replay evidence for the complete
  Telco demonstrator.

| Task | Description | Dependencies | Completed | Date |
|---|---|---|---|---|
| TASK-059 | Create `tools/telco_zava_e2e_proof.sh` by reusing `tools/lib/actor_world_proof_stack.sh`; boot Azurite, Functions, FastAPI with `ZAVA_VERTICAL=telco` and `AGT_ENFORCE=1`, Control Plane Vite, and Blueprint Vite. Use separate strict ports and exact-PID teardown. | Phases 1-8 | | |
| TASK-060 | Create Playwright driver spanning both frontends: Control Plane `/world`/Feed and Blueprint Constellation/Entities/AG-UI run page. Assert network incident, proactive care, HITL resolution, terminal evaluations, graph records, AG-UI events and DOM/world/command identity equality. | TASK-059 | | |
| TASK-061 | Extend driver with order-to-activate happy and exception paths. | TASK-060 | | |
| TASK-062 | Add machine-readable evidence under `tmp/telco-zava-e2e-proof/`: summary JSON, event journal, Durable outputs, graph query output, screenshots and video. | TASK-060 | | |
| TASK-063 | Record passing live traces using existing blueprint recorder; add replay fixtures under `data/blueprint-recordings/`. | TASK-060, TASK-061 | | |
| TASK-064 | Verify public blueprint replay renders recorded telco domains without Functions host. Update contributor/runbook documentation with exact live versus replay claims. | TASK-063 | | |

**Completion gate:** One command exits zero only after cross-checking Durable
outputs, world actors, workflow records, graph projections, AG-UI and browser
DOM. Replay is generated from that passing evidence.

## 3. Alternatives

- **ALT-001**: Implement one simulator per OSS/BSS process. Rejected: duplicates
  world state and cannot produce cross-process causality.
- **ALT-002**: Build a generic schema-driven UI/agent-generated layout first.
  Rejected: current code proves explicit scenario views plus shared primitives;
  a UI DSL adds risk before a second industry needs it.
- **ALT-003**: Push every world event into Kuzu. Rejected: duplicates
  high-volume authority and creates unnecessary graph write load.
- **ALT-004**: Convert network reroute into an LLM agent immediately. Rejected:
  deterministic bounded planning is safer; agent value is demonstrated in
  diagnosis, entitlement and feasibility.
- **ALT-005**: Keep actor responders outside StateStore and build separate telco
  pages. Rejected: bypasses Zava's strongest existing surfaces.
- **ALT-006**: Run separate OSS and BSS world services. Rejected:
  `ZAVA_WORLD` is single-world and shared identity is the purpose of the telco
  pack.

## 4. Dependencies

- **DEP-001**: Existing `NetworkScenario`, `ActorWorldService`,
  `WorldBridge`, `ObjectiveManager`, `CommandGateway`.
- **DEP-002**: Azure Functions Core Tools + Azurite for live proof.
- **DEP-003**: Existing compose-domain pipeline for agentic business domains.
- **DEP-004**: Existing `api.server.services.persona_responder` module,
  authority matrix, governance kernel
  and `AuthorityCard`.
- **DEP-005**: Existing EntityReflector, Kuzu graph and projection registry.
- **DEP-006**: Existing AG-UI workflow route and reducers.
- **DEP-007**: Existing Control Plane `/world`, Feed and Blueprint
  Constellation.
- **DEP-008**: Existing actor-world proof stack and blueprint recorder.

## 5. Files

- **FILE-001**: `api/shared/verticals.py` - Telco profile filter.
- **FILE-002**: `api/server/services/workflow_event_ingestor.py` - shared
  checkpoint ingestion.
- **FILE-003**: `api/server/services/world_workflow_adapter.py` - objective to
  canonical Workflow lifecycle.
- **FILE-004**: `api/server/services/world_bridge.py` - route/schedule/apply
  coordination.
- **FILE-005**: `api/server/world/registry.py` - objective routes.
- **FILE-006**: `api/server/world/evaluations.py` - terminal outcome evaluator.
- **FILE-007**: `api/server/world/packs/telco.py` - existing network world
  integration.
- **FILE-008**: `api/server/world/packs/telco_commercial.py` - commercial
  actors and views.
- **FILE-009**: `api/functions/workflows/network_incident.py` - standard
  checkpoints.
- **FILE-010**: `api/shared/domains.py`, `api/shared/functions.py`,
  `function_app.py` - new Telco domains and Durable registration.
- **FILE-011**: `api/server/services/entity_graph.py` and
  `entity_projections/` - generic telco relationships/projections.
- **FILE-012**: `web/client/routes/TelcoWorld.tsx`,
  `useWorldSimulation.ts`, and existing `web/blueprint` run/entity/
  Constellation surfaces - Telco operator and drill-in lenses.
- **FILE-013**: `data/synthetic/authority/matrix.json` and
  `AuthorityCard.tsx` - commercial authority.
- **FILE-014**: `tools/telco_zava_e2e_proof.*` - unmocked proof.
- **FILE-015**: `data/blueprint-recordings/` - replay evidence.

## 6. Testing

- **TEST-001**: Unit tests for vertical selection and default compatibility.
- **TEST-002**: Route/ingestor regression tests with HMAC preserved.
- **TEST-003**: Live actor incident creates stored Workflow and standard
  checkpoints.
- **TEST-004**: AG-UI translates live incident workflow events.
- **TEST-005**: EntityReflector projects the live actor workflow.
- **TEST-006**: Multi-objective same-trace and duplicate-delivery tests.
- **TEST-007**: Evaluation success/failure/timeout tests.
- **TEST-008**: Seeded account/subscription determinism and referential
  integrity.
- **TEST-009**: Atomic/idempotent customer-remediation command tests.
- **TEST-010**: Proactive-care auto and HITL paths.
- **TEST-011**: Telco graph relationships and precedents.
- **TEST-012**: Telco lenses render only state/journal-backed data.
- **TEST-013**: Order activation happy, capacity failure and HITL paths.
- **TEST-014**: Existing `actor_world_viewer_proof.sh` and
  `telco_world_e2e_proof.sh` remain green through migration.
- **TEST-015**: New full-stack `telco_zava_e2e_proof.sh` passes.
- **TEST-016**: Recorded replay renders without Functions host.

## 7. Risks & Assumptions

- **RISK-001**: Extracting durable-event ingestion can regress many domains.
  Mitigation: characterization tests before extraction; route contract remains.
- **RISK-002**: High-volume account projections can overload Kuzu. Mitigation:
  project durable identities/material actions only, never ticks.
- **RISK-003**: Same incident opens duplicate objectives. Mitigation:
  event-ID in-flight latch plus objective `(type,target)` dedupe.
- **RISK-004**: Workflow completes before world effect is known. Mitigation:
  adapter owns terminal checkpoint after evidence-backed evaluation.
- **RISK-005**: Generated domain output may not match typed world command.
  Mitigation: explicit command adapter contract and integration test.
- **RISK-006**: `WorldBridge` holds an in-memory async poll while Durable waits
  at HITL; FastAPI restart would orphan that objective. Mitigation: V1 proof
  resolves deterministic hero HITL inside 300 seconds and never restarts
  FastAPI mid-run. Restart-safe recovery is explicitly outside V1.
- **RISK-007**: Profile filtering accidentally hides default domains.
  Mitigation: unset-profile regression tests.
- **RISK-008**: Public replay is mistaken for live production. Mitigation:
  UI/runbook labels and separate proof commands.

- **ASSUMPTION-001**: V1 may model one account/subscription per subscriber.
- **ASSUMPTION-002**: Existing 12-site/2,000-subscriber scale is sufficient for
  the demonstrator.
- **ASSUMPTION-003**: `customer-success`, `revenue` and `ops` remain canonical
  function owners.
- **ASSUMPTION-004**: Deterministic network command planning remains acceptable
  while customer/feasibility phases demonstrate real agent behaviour.

## 8. Related Specifications / Further Reading

- [`Telco Zava demonstrator design`](../specs/2026-07-14-telco-zava-demonstrator-design.md)
- [`Telco OSS catalogue`](../specs/2026-07-14-telco-oss-process-catalogue.md)
- [`Telco BSS catalogue`](../specs/2026-07-14-telco-bss-process-catalogue.md)
- [`Observable actor simulator design`](../specs/2026-07-13-observable-actor-simulator-design.md)
- [`Autonomous systemic simulator design`](../specs/2026-07-14-autonomous-systemic-simulator-design.md)
- [`Architecture`](../../ARCHITECTURE.md)
- [`Visualisation reference`](../../visualisation.md)
