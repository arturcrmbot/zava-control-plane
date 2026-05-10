---
goal: Expand the org simulator from a workflow-launch surface into a full demo-driver for the Org Building visualisation. Add affordances that exercise the not-yet-visible substrate primitives — cross-function entity reuse, meta-workflows, decisions, ambient agents, cadences, persona inboxes, failure modes — independently of organic activity, so a 5-minute demo lights up every primitive the [Org Building spec](2026-05-09-org-building-design.md) calls for.
version: 1.0
date_created: 2026-05-10
last_updated: 2026-05-10
owner: Zava Control Plane — substrate
status: 'Draft'
tags: [feature, backend, simulator, observatory, agentic-org, demo]
---

# Org-simulation expansion — design spec

![Status: Draft](https://img.shields.io/badge/status-Draft-lightgrey)

## Problem

The simulator surface today
([`api/server/routes/simulator.py`](../../../api/server/routes/simulator.py),
~38 endpoints) is **workflow-launch-centric**: every endpoint kicks
off one workflow type. The Org Building forward design
([2026-05-09-org-building-design.md](2026-05-09-org-building-design.md))
makes *cross-function entity reuse*, *decisions*, *ambient agents*,
*cadences*, *meta-workflows*, and *failure modes* the headline
primitives — but the simulator can't drive any of them independently
of a workflow. That means:

- The cross-function light-beam elevator (REQ-005, the spec's headline
  visual) only appears when the same vendor happens to be touched by
  ≥ 2 functions organically. Within a 5-minute demo, this is unlikely.
- Sub-spawn filaments (REQ-006) only fire when a meta-workflow happens
  to fan out. Same problem.
- The cadence clock (REQ-008) only ticks at wall-clock 09:00 / month-end
  / quarter-end. Not demoable in a meeting.
- Right-rail audit-eligible failure entries (REQ-009) only appear when
  something fails. The simulator only has one failure injection
  (`simulate_region_failure`).
- Ambient sensor flashes (TASK-021) only happen when KPI thresholds
  cross organically.

Operators presenting the substrate need a deterministic, scriptable way
to make every primitive visible on demand. This spec proposes the
expansions, ordered by demo leverage.

## What we're building

A staged expansion of the simulator with three tiers:

1. **Tier 1 — directly amplify the Org Building demo** (~2 weeks): five
   targeted endpoints that each light up one Org Building primitive.
2. **Tier 2 — operator scenarios** (~3 weeks): scripted multi-step
   demos, replay, synthetic operator load, broader failure injection.
3. **Tier 3 — long-term org realism** (~4-6 weeks): persona inboxes,
   cross-function KPI feedback loops, what-if mode, multi-tenant.

Tier 1 is broken into TASKs at the bottom of this spec (the same shape
as the Org Building spec). Tier 2 + Tier 3 are roadmap-level for now;
each will get its own TASK breakdown when promoted from roadmap to
plan.

## 1. Requirements & Constraints

- **REQ-001:** Each Tier-1 endpoint must produce a deterministic,
  observable visualisation effect within 30 seconds. Not "eventually"
  via probabilistic bus traffic.
- **REQ-002:** No new substrate event types. The expansion must use
  existing event types only (`entity.upserted`, `decision.recorded`,
  `ambient.decided`, `cadence.tick`, `workflow.sub_spawned`,
  `entity.write.failed`, `governance.find_entities.denied`). Widening
  the event vocabulary is a substrate-level decision and is out of
  scope here.
- **REQ-003:** Each Tier-1 endpoint must be POST-only, JSON in / JSON
  out, and live under `/api/simulator/`. Naming follows the existing
  convention (`/api/simulator/<noun-or-verb>`).
- **REQ-004:** Endpoints must be safe to call in any environment that
  already accepts simulator traffic. They must not bypass governance
  policy: ambient kicks still flow through
  [`ambient_dispatcher.py`](../../../api/server/services/ambient_dispatcher.py),
  decisions still hit the audit ledger, entity upserts still go
  through the projections.
- **REQ-005:** Failure injection (`simulator/entity-write-fail`,
  `simulator/governance-deny`, `simulator/hitl-timeout`) must produce
  the *same* event shapes that organic failures produce — no synthetic
  shapes that drift from production behaviour.
- **REQ-006:** A scripted scenario (Tier 2) must be re-runnable from a
  cold start (`make reset` + `make up`) and produce a recognisable
  visual sequence within ~5 minutes.
- **SEC-001:** All new endpoints respect the existing audit + AGT
  governance contract. Tier-1 endpoints record an `audit.summary.composed`
  entry with the operator action so the simulator's footprint is
  auditable.
- **SEC-002:** The `simulator/governance-deny` endpoint must drive the
  governance kernel through its real deny path, not synthesise the
  `governance.find_entities.denied` event from a stub. Faking the event
  would create a false-positive audit entry.
- **CON-001:** No new external dependencies. Reuse the existing
  `simulator_orchestrator.py`, `audit_logger.py`, `event_bus.py`,
  `ambient_dispatcher.py`, `cadence_loader.py`, `kpi_store.py`.
- **CON-002:** Cadence fast-forward (TASK-104) is a virtual clock
  injection in `cadence_loader.py`, not a real `time.time()` mock. The
  rest of the substrate must continue to read wall-clock time
  unchanged.
- **CON-003:** Replay (Tier 2) reads from JSONL and re-emits onto the
  in-process bus. It does **not** rewind durable state; the
  visualisation receives a recording, the orchestrator does not.
- **CON-004:** Multi-tenant partitioning (Tier 3) is gated on a
  substrate-level decision about SSE topic partitioning. This spec
  flags it but does not implement it.
- **GUD-001:** Each new endpoint should produce a single recognisable
  visual signature. If an endpoint amplifies two primitives, split it.
- **GUD-002:** Endpoints must be idempotent-safe (calling twice in a
  row does not corrupt state) but may be non-idempotent (calling twice
  produces twice the events).
- **PAT-001:** Endpoints should be thin glue over existing service
  layers. The pattern is: `routes/simulator.py` parses the request,
  calls a function in `services/simulator_orchestrator.py` (or a new
  sibling module), which composes existing primitives.
- **PAT-002:** All new endpoints have a smoke test under
  `tests/api/server/routes/test_simulator_*.py` asserting the produced
  audit-ledger entries match the expected shape.

## 2. Tier 1 — Implementation Steps

### Implementation Phase 1 — Cross-function entity reuse generator

- GOAL-101: One endpoint that creates a single `Organisation` entity
  and triggers three workflows against it across three different
  function floors over ~30 seconds. Lights up the cross-function
  light-beam elevator (Org Building REQ-005, TASK-025, TASK-027).

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-101 | Add `POST /api/simulator/cross-function-vendor` to [`api/server/routes/simulator.py`](../../../api/server/routes/simulator.py). Body: `{vendor_name?: str, delay_s?: int}` (defaults: synthetic name, 10 s between launches). | | |
| TASK-102 | In [`api/server/services/simulator_orchestrator.py`](../../../api/server/services/simulator_orchestrator.py), add `async def spawn_cross_function_vendor(vendor_name, delay_s)` that: (a) upserts an `Organisation` entity via the existing entity reflector, (b) launches `fleet-vendor-kyc`, (c) waits `delay_s`, (d) launches `fleet-purchase-order` referencing the same vendor, (e) waits `delay_s`, (f) launches `fleet-ap-invoice` referencing the same vendor. Return `{vendor_id, workflow_ids: [...]}`. | | |
| TASK-103 | Smoke test: `tests/api/server/routes/test_simulator_cross_function_vendor.py` — POST the endpoint, assert one `entity.upserted` for the vendor, three `workflow.started`, three `entity.upserted` events linking the vendor as a `source_workflow` of each launched workflow. | | |

### Implementation Phase 2 — Meta-workflow burst

- GOAL-102: One endpoint that fires a parent workflow that spawns 3-5
  children spanning ≥ 2 floors. Lights up the bright-filament
  sub-spawn primitive (Org Building REQ-006, TASK-024).

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-104 | Add `POST /api/simulator/meta-spawn-burst`. Body: `{parent_type?: str, child_count?: int}`. Defaults: `creative-campaign` parent, 4 children spread across `marketing` + `tech` + `data` floors. | | |
| TASK-105 | In `simulator_orchestrator.py`, add `async def spawn_meta_burst(parent_type, child_count)` that launches the parent workflow then explicitly emits `workflow.sub_spawned` for each child via the existing meta-workflow reflector path (i.e. through the orchestrator, not synthesised — see SEC-002 reasoning). | | |
| TASK-106 | Smoke test: assert one parent `workflow.started`, `child_count` `workflow.sub_spawned` events with the expected `parent_workflow_id` and child `workflow_type`s spread across ≥ 2 floors. | | |

### Implementation Phase 3 — Decision storm

- GOAL-103: One endpoint that backfills 20-30 `decision.recorded`
  events in ~60 seconds, distributed across multiple persona desks.
  Lights up the decision-spark + lobby Decision-vault tick (TASK-020).

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-107 | Add `POST /api/simulator/decision-storm`. Body: `{count?: int, duration_s?: int}`. Defaults: 25 decisions across 60 s. | | |
| TASK-108 | In `simulator_orchestrator.py`, add `async def spawn_decision_storm(count, duration_s)` that drives existing in-flight workflows toward `decision.recorded` via the persona auto-responder, OR (if there are no in-flight workflows) seeds synthetic decisions through the existing `seed_decisions` path. Spread across 3-5 persona roles. | | |
| TASK-109 | Smoke test: assert exactly `count` `decision.recorded` events emitted within `duration_s + 5` seconds, spread across at least 3 distinct `persona_role` values. | | |

### Implementation Phase 4 — Cadence fast-forward

- GOAL-104: One endpoint that virtually advances the cadence clock by
  N seconds, firing morning-sweep / period-close / quarterly-okr on
  demand (TASK-022, REQ-008). Wall-clock unchanged everywhere else.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-110 | In [`api/server/services/cadence_loader.py`](../../../api/server/services/cadence_loader.py), add an injected `_virtual_offset_s: int = 0`. The cadence runner reads `time.time() + _virtual_offset_s` when computing `next_run_at`. Wall-clock for the rest of the substrate is unaffected. | | |
| TASK-111 | Add `POST /api/simulator/cadences/fast-forward`. Body: `{seconds: int}`. Increments `_virtual_offset_s` and immediately wakes the cadence runner so any cadences that are now in the past fire on the next tick. | | |
| TASK-112 | Add `POST /api/simulator/cadences/reset` to clear `_virtual_offset_s` back to 0 — required for clean test teardown and demo resets. | | |
| TASK-113 | Smoke test: fast-forward 24 h, assert at least one `cadence.tick` for the daily morning-sweep within 5 s; fast-forward 30 days, assert period-close fires; reset, assert next normal tick is at the natural wall-clock interval. | | |

### Implementation Phase 5 — Ambient-agent kick

- GOAL-105: One endpoint that synthesises the trigger condition for a
  named ambient agent and lets the dispatcher run end-to-end. Lights
  up the sensor flash on the floor's ambient indicator (TASK-021).

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-114 | Add `POST /api/simulator/ambient/{agent_name}/kick`. Body: `{payload?: dict}` — optional override for the trigger payload. Defaults vary per agent (the dispatcher knows what shape each ambient agent expects). | | |
| TASK-115 | In `ambient_dispatcher.py`, add `async def kick(agent_name, payload)` that invokes the agent's reasoning skill with the supplied payload, runs through the existing decide path, and emits `ambient.decided` (or `ambient.declined`) — the *real* dispatcher path, not a synthesised event. | | |
| TASK-116 | Smoke test: kick each registered ambient agent in turn, assert one `ambient.decided` per kick with the expected `agent` field. | | |

### Implementation Phase 6 — Tier-1 wrap-up

- GOAL-106: Tier 1 is end-to-end demoable. Documentation + the
  visualisation reference are updated.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-117 | Update [`docs/visualisation.md` §3](../../visualisation.md#3-event--visual-mapping) — once the SSE allow-list is widened (Org Building TASK-002), move the relevant rows from "Emitted but not yet visualised" up to the active table. The 5 Tier-1 endpoints become the demo recipes. | | |
| TASK-118 | Update [`docs/visualisation-contributor-guide.md` "Local-dev recipes"](../../visualisation-contributor-guide.md#local-dev-recipes) — append the 5 new endpoints with one-line curl recipes. | | |
| TASK-119 | End-to-end smoke: `make up` + cold start + run all 5 Tier-1 endpoints in sequence + open `?view=constellation`. Capture a 60-90 s screen recording showing each primitive lighting up exactly once. Save to `docs/superpowers/specs/2026-05-10-simulator-expansion.smoke.mp4` (or .webm). | | |

## 3. Tier 2 — Operator scenarios (roadmap)

Each item below will get its own TASK breakdown when promoted to a
plan. Listed in priority order.

### Scenario scripts

A new `api/server/services/simulator_scripts/` directory with named
multi-step YAML scripts. Each script is a sequence of inject + delay +
decision-storm + cadence-tick + ambient-kick steps. Surface as
`POST /api/simulator/scripts/{name}/run`.

Initial scripts:
- `vendor-onboarding-end-to-end` — composes Tier-1 cross-function-vendor
  + ambient-kick + decision-storm into a recognisable 90 s sequence.
- `quarter-close` — fast-forwards cadences to the next quarter end,
  fires period-close ambient, drives 3 finance workflows through HITL.
- `incident-rolls-through-org` — failure injection on one floor,
  watches the ripple to other floors via cross-function beams.
- `new-employee-day-1` — `fleet-employee-onboarding` end-to-end with
  HR + IT-access + finance touchpoints.

Drives the "30-second understanding" acceptance criterion (Org
Building "Done means").

### Time-controlled replay

- `POST /api/simulator/record/start|stop` — captures an SSE tail to
  `data/simulator-recordings/<name>.jsonl`.
- `POST /api/simulator/replay` — re-emits a recording onto the bus at
  configurable speed (`speed_multiplier: float`, default `1.0`).
- Notes: replay does NOT rewind durable state (CON-003). The
  visualisation receives a faithful re-emission; the orchestrator
  observes nothing. Use for screenshot / video capture.

### Synthetic operator load

- `POST /api/simulator/persona/{role}/auto-respond` — drives the
  existing
  [`persona_responder.py`](../../../api/server/services/persona_responder.py)
  in stochastic mode for `duration_s` seconds with a configurable
  `accept_rate`. Useful for backpressure tests on persona inboxes
  (Tier 3).

### Broader failure injection

Today only `simulate_region_failure` exists. Add:

- `POST /api/simulator/entity-write-fail` — drives the entity reflector
  through its existing kill-switch path so `entity.write.failed` events
  fire with realistic shapes.
- `POST /api/simulator/governance-deny` — submits a governance request
  designed to be denied by the kernel, producing a real
  `governance.find_entities.denied` audit entry (SEC-002).
- `POST /api/simulator/hitl-timeout` — accelerates a pending HITL
  gate's SLA so it breaches and fires
  `workflow.sla.breach_imminent` + `workflow.hitl.escalated`.

These light up the right-rail audit-eligible failure feed (Org
Building REQ-009).

## 4. Tier 3 — Long-term org realism (roadmap)

Each item is its own design spec when promoted.

### Persona inboxes & SLAs

Today personas are stateless responders. Add a queue per persona with
an SLA timer; HITL gates accumulate. The Org Building can then
colour-code "persona is overloaded" at zoom-1 (extends TASK-040).
Backed by [`pending_gates.py`](../../../api/server/services/pending_gates.py)
already existing.

### Cross-function KPI feedback loops

Wire one function's KPI threshold to another's ambient agent (e.g.
high `dso` on Finance triggers Customer-Success outreach). Makes the
cross-function beams *causally meaningful*, not just statistical
co-occurrence. Spec mentions this implicitly via REQ-005 but the
substrate today doesn't have cross-function ambient triggers.

### Org-clone "what-if" mode

Let the operator clone the running org's state into a sandbox and run
the simulator against the clone (different cadence schedules, more
aggressive HITL auto-close). Plays naturally into
[`OrgClonePage.tsx`](../../../web/blueprint/src/pages/OrgClonePage.tsx)'s
thesis. Long-tail; will be its own spec.

### Multi-tenant org partitioning

Run two simulated orgs side-by-side in the building view (left wing =
Org A, right wing = Org B) so the visual primitive scales beyond one
tenant. Requires SSE topic partitioning — a substrate-level change
(CON-004).

## 5. Mapping — endpoint → primitive it activates

| Simulator addition | Tier | Primitive it activates | Org Building spec ref |
|---|---|---|---|
| `cross-function-vendor` | 1 | Inter-floor light-beam elevators | REQ-005, TASK-025, TASK-027 |
| `meta-spawn-burst` | 1 | Bright-filament sub-spawn | REQ-006, TASK-024 |
| `decision-storm` | 1 | Decision spark + lobby vault tick | TASK-020 |
| `cadences/fast-forward` | 1 | Cadence clock pulse + ambient flash | TASK-022, REQ-008 |
| `ambient/{agent}/kick` | 1 | Sensor flash on facade | TASK-021 |
| `scripts/{name}/run` | 2 | All-of-the-above choreographed | "Done means" |
| `record/replay` | 2 | Reproducible screen captures | TASK-027, TASK-055 |
| `entity-write-fail` / `governance-deny` / `hitl-timeout` | 2 | Right-rail audit-eligible entries | REQ-009, SEC-001 |
| `persona/{role}/auto-respond` | 2 | Persona-desk overload colour | TASK-040 |
| Persona inboxes & SLAs | 3 | Zoom-1 persona-desk overload | extends TASK-040 |
| Cross-function KPI → ambient | 3 | Causal cross-function beams | extends REQ-005 |
| Org-clone what-if | 3 | OrgClonePage drill | n/a |
| Multi-tenant partitioning | 3 | Wing-per-tenant | n/a |

## 6. Done means

> A new operator runs `make up` + the 5 Tier-1 endpoints in sequence
> over ~3 minutes, opens `?view=constellation`, and observes: (a) one
> cross-function light-beam elevator appearing as the vendor walks
> three floors, (b) a meta-workflow filament fanning out to ≥ 2
> floors, (c) ~25 decision sparks across multiple persona desks, (d)
> the cadence clock advancing and firing morning-sweep / period-close,
> (e) ambient sensors flashing on the kicked agents' floors. Every
> primitive the Org Building spec calls headline-worthy is now
> demoable on demand.

Smoke commands once Tier 1 ships:

```bash
make up   # full stack

# 1. Cross-function vendor walks 3 floors over ~30 s
curl -X POST http://localhost:3001/api/simulator/cross-function-vendor \
     -H 'Content-Type: application/json' -d '{}'

# 2. Meta-workflow burst — parent + 4 children across 2+ floors
curl -X POST http://localhost:3001/api/simulator/meta-spawn-burst \
     -H 'Content-Type: application/json' -d '{}'

# 3. Decision storm — 25 decisions in 60 s
curl -X POST http://localhost:3001/api/simulator/decision-storm \
     -H 'Content-Type: application/json' -d '{}'

# 4. Fast-forward 24 h — morning-sweep fires
curl -X POST http://localhost:3001/api/simulator/cadences/fast-forward \
     -H 'Content-Type: application/json' -d '{"seconds": 86400}'

# 5. Kick a named ambient agent
curl -X POST http://localhost:3001/api/simulator/ambient/finance-anomaly-watch/kick \
     -H 'Content-Type: application/json' -d '{}'

open 'http://localhost:5175/?view=constellation'
```

Acceptance, mapped to TASKs:
- Cross-function entity reuse generator → TASK-101..-103
- Meta-workflow burst → TASK-104..-106
- Decision storm → TASK-107..-109
- Cadence fast-forward → TASK-110..-113
- Ambient-agent kick → TASK-114..-116
- Tier-1 wrap-up + screen recording → TASK-117..-119

## 7. Cross-references

- **Visualisation reference (what's wired today)** → [../../visualisation.md](../../visualisation.md)
- **Visualisation contributor guide** → [../../visualisation-contributor-guide.md](../../visualisation-contributor-guide.md)
- **Org Building forward design (the customer of this spec)** → [2026-05-09-org-building-design.md](2026-05-09-org-building-design.md)
- **Substrate event vocabulary** → [2026-05-03-substrate-fix-design.md](2026-05-03-substrate-fix-design.md)
- **Existing simulator** → [`api/server/routes/simulator.py`](../../../api/server/routes/simulator.py), [`api/server/services/simulator_orchestrator.py`](../../../api/server/services/simulator_orchestrator.py)

## 8. Open questions

1. **Cadence fast-forward scope** — should `_virtual_offset_s` apply
   only to cadences, or to anything that reads "now"? Recommend:
   cadences only (cadence_loader-local), to avoid pulling KPI snapshot
   timestamps and audit-ledger timestamps off wall-clock. Decision
   deferred to TASK-110 implementation.
2. **Decision-storm provenance** — should synthesised decisions carry
   a `simulator: true` marker so they can be filtered out of accuracy
   evals? Recommend yes; add to TASK-108. Existing `seed_decisions`
   already does similar.
3. **Replay event ordering** — replay re-emits events in recorded
   order, but the orchestrator that produced them is not running.
   Some events reference workflow_ids that don't exist in the live
   state. Decision: replay events use a `replay: true` envelope key
   so consumers (notably the entity reflector) can decline to mutate
   real state. Defer to Tier 2 design.
4. **Persona auto-respond accept-rate semantics** — "accept" vs
   "decline" vs "escalate" — three-way verdict per existing
   `decision_policy` shape. Defer to Tier 2 design.
5. **Multi-tenant partition key** — a tenant-id header? An env-var on
   spawn? Substrate decision; spec only flags it.
