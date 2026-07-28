# Anonymous Hospitality Operations Vertical Design

**Date:** 2026-07-28
**Status:** Approved for autonomous execution
**Target:** Anonymous multi-country, hotel-led hospitality operator

## 1. Decision

Build `hospitality` as an automatically discovered, self-contained Zava
vertical pack. It is informed by public research into a large, vertically
integrated budget-hotel owner-operator, but every committed asset is anonymous:
no customer or brand names, logos, slogans, colours, executives, exact estate
figures, property names, proprietary policies, or inferred confidential
processes.

The hero workflow is **Hotel Operations Recovery**. A near-capacity hotel loses
a block of rooms shortly before a large arrival wave because a critical
building asset fails. The workflow coordinates maintenance, room readiness,
cross-property capacity, guest protection, workforce allocation, and governed
recovery spend. It ends with typed world mutations and measured operational and
commercial outcomes.

The first release contains the hero plus seven executable supporting workflows.
All eight are backed by synthetic deterministic cases, pack-owned skills and
tools, typed commands, projections, and distinct proof evidence. There are no
stubs.

## 2. Research and anonymity boundary

The private research input establishes only public operating-model anchors:

- a predominantly hotel-led business with integrated on-site food and beverage;
- a large directly operated estate across the UK/Ireland and Germany;
- mixed owned and leased property;
- operational consistency, guest experience, cost discipline, room growth, and
  digital hotel operations as strategic themes;
- modern booking, property, integration, finance, and digital guest platforms.

Those anchors do not establish room-out-of-order thresholds, maintenance SLAs,
relocation policies, compensation bands, workforce rules, system schemas, or
approval limits. The vertical therefore labels all such values as synthetic
demo assumptions.

The committed design and runtime use:

- the generic display name **Hospitality**;
- fictional properties, people, guests, suppliers, and incidents;
- rounded synthetic scale rather than a copied estate;
- generic system roles rather than undocumented vendor interfaces;
- a boundary test that rejects customer-identifying terms in pack-owned assets.

## 3. Goals

1. Give hotel-operations leaders a credible control-room story spanning one
   property incident and its network-wide consequences.
2. Demonstrate bounded autonomy: automate safe, reversible coordination and
   require named authority for material guest, room, labour, and spend actions.
3. Use one causal actor world so maintenance, housekeeping, bookings, guests,
   workforce, food and beverage, energy, and KPIs cannot drift into unrelated
   fixtures.
4. Make every recommendation explainable through typed evidence and observed
   agent/tool execution.
5. Show measured recovery: protected arrivals, rooms restored, revenue at risk,
   guest disruption, recovery cost, and readiness SLA.
6. Keep all business behavior under `verticals/hospitality/` and preserve
   cross-pack isolation.
7. Produce repeatable live and replay proof and a stable seller-review demo
   command.

## 4. Non-goals

- Recreate a named company, hotel brand, proprietary policy, or internal system.
- Build a hotel booking website, consumer app, full property-management system,
  or real maintenance integration.
- Perform autonomous dynamic pricing or cancel guest bookings without governed
  authority.
- Model every hotel room, employee, or guest in the seller-facing scene.
- Present synthetic policy thresholds as industry or customer facts.
- Reuse the Travel pack's tour-operator hotel-allotment behavior. This vertical
  operates hotels; it does not procure hotel inventory from suppliers.
- Create a universal hospitality DSL or refactor unrelated shared substrate.

## 5. Approach decision

Three implementation approaches were considered:

| Approach | Strength | Risk | Decision |
|---|---|---|---|
| Fully generated shared engine | Fastest path to eight registered workflows | Risks a cosmetic Travel relabel and weak hero semantics | Rejected |
| Bespoke implementation for all eight workflows | Maximum fidelity per process | Duplicates orchestration and proof plumbing; slower and harder to maintain | Rejected |
| Bespoke hero plus a pack-owned profiled engine | Distinct causal hero with economical supporting breadth | Requires a clear generated/bespoke ownership boundary | **Selected** |

The hero owns bespoke incident sensing, recovery planning, governed command
construction, world mutation, evaluation, and projection. Supporting workflows
use one small pack-owned profiled engine only where phase behavior matches.
Every workflow still has a distinct trigger, case, skill, command schema,
projection, and proof record.

## 6. Pack architecture and ownership

```text
verticals/hospitality/
  manifest.py                  # only composition root
  org-brief.yaml               # anonymous approved assumptions, no target identity
  generation-manifest.json     # generated/bespoke ownership ledger
  domains.py                   # eight executable domains
  functions.py                 # organisation functions and KPI ownership
  agents.py                    # machine-agent registry
  personas.py                  # runtime persona registry
  authority.py                 # exact action/value authority
  process_profiles.py          # supporting process behavior and command metadata
  reference_cases.py           # deterministic acceptance cases
  reference_actions.py         # typed expected actions
  actors.py                    # hotel-world entities
  dynamics.py                  # deterministic demand, readiness, and fault dynamics
  sensors.py                   # threshold crossing and deduplication
  world.py                     # actor world, commands, events, evaluation
  worlds.py                    # world registration and objective routes
  lifecycle.py                 # seed/start lifecycle
  durable.py                   # Durable orchestrators and activities
  projections.py               # workflow-facing projections
  entity_projections/          # graph entity/relationship projection
  mcp_tools/                   # typed reads and command preparation
  policies/tools.yaml          # pack-local tool policy
  skills/*/SKILL.md            # reasoning skills
  personae/*/SKILL.md          # decision personas
  ui.json                      # runtime UI manifest
  ui/world-scene.json          # bounded hospitality world scene
  recordings/*.jsonl          # qualifying curated traces
```

`manifest.py` builds one immutable `VerticalPack`. The pack is discovered from
its directory and must not edit global business registries. Shared workflow,
governance, identity, memory, graph, AG-UI, and rendering interfaces remain
substrate-owned.

### Capability classification

**Reuse**

- `VerticalPack`, `Domain`, `Function`, persona, authority, world-registration,
  projection, and recording contracts;
- canonical `run_agent_session`, Durable checkpointing, governance/HITL,
  workflow identity, AG-UI, Memory, Knowledge, and replay interfaces;
- shared world-scene schema and vertical auto-discovery.

**Extend**

- no shared extension is planned initially;
- a shared helper may be extracted only if implementation proves identical need
  in multiple active packs and its tests remain industry-neutral.

**Bespoke**

- hotel entities and causal dynamics;
- operational outage sensor and recovery evaluator;
- every hospitality typed command and mutation;
- hospitality process portfolio, authority, skills, personas, projections, and
  UI scene.

## 7. Organisation and process portfolio

### 7.1 Functions

| Function | Responsibility | Primary KPIs |
|---|---|---|
| `hotel-operations` | Property readiness, room availability, incident command, and network coordination | sellable rooms, protected arrivals, room-readiness SLA, recovery time |
| `engineering-and-estates` | Critical assets, work orders, contractors, and planned maintenance | asset uptime, rooms out of service, first-time fix, maintenance cost |
| `guest-and-commercial` | Booking inventory, guest protection, service recovery, and revenue exposure | arrival fulfilment, relocation rate, guest disruption, revenue at risk |
| `people-and-workforce` | Demand forecasting, shifts, skill coverage, and safe workload | labour coverage, overtime, productivity, unfilled critical shifts |
| `food-and-beverage` | Breakfast and integrated on-site service readiness | service capacity, forecast coverage, waste exposure, guest attach readiness |
| `sustainability-and-utilities` | Energy anomalies and safe efficiency actions | energy intensity, anomaly duration, avoided consumption, comfort exceptions |

### 7.2 Workflows

| Workflow type | Kind | Function | Trigger | Typed command |
|---|---|---|---|---|
| `hotel-operations-recovery` | Hero, bespoke | hotel-operations | Critical asset fault plus arrival/occupancy pressure | `hotel.recovery.execute` |
| `room-readiness-coordination` | Profiled | hotel-operations | Clean-room readiness falls below arrival demand | `room.readiness-plan.apply` |
| `asset-maintenance-response` | Profiled | engineering-and-estates | Predictive or reactive critical-asset alert | `maintenance.work-order.dispatch` |
| `guest-service-recovery` | Profiled | guest-and-commercial | Material in-stay or arrival service failure | `guest.recovery-action.issue` |
| `occupancy-pressure-response` | Profiled | guest-and-commercial | Sellable inventory no longer covers protected demand | `booking.inventory-plan.apply` |
| `workforce-demand-balancing` | Profiled | people-and-workforce | Forecast workload exceeds safe skill coverage | `workforce.shift-plan.apply` |
| `food-and-beverage-readiness` | Profiled | food-and-beverage | Forecast service demand exceeds prepared capacity | `food-beverage.service-plan.apply` |
| `energy-anomaly-response` | Profiled | sustainability-and-utilities | Consumption anomaly persists outside comfort/safety bands | `energy.control-plan.apply` |

Supporting processes share phase mechanics, not command semantics. Each profile
owns its own event type, case, evidence schema, skill, authority action, typed
payload validator, mutation handler, evaluation, and recording.

## 8. Actor world

### 8.1 Entities and relationships

The deterministic world contains:

- hotels, regions, and room types;
- rooms and aggregate sellable-room inventory;
- bookings, guest parties, arrivals, and protected requirements;
- critical assets, faults, work orders, contractors, and parts;
- housekeeping, front-office, engineering, and food-service teams and shifts;
- breakfast/service capacity and energy meters;
- policy rows, approvals, commands, and evaluations.

Key relationships include:

- a room belongs to one hotel and room type;
- a booking reserves a compatible room requirement at one hotel;
- a guest party has accessibility, family, timing, and channel constraints;
- an asset serves one or more room blocks or services;
- a work order targets an asset and consumes team/contractor capacity;
- a shift provides skills to a hotel during a time window;
- a recovery plan may move a booking only to a compatible sister property;
- every mutation links back to the originating workflow and evidence digest.

### 8.2 Deterministic demo scale

The `demo` seed uses:

- 6 fictional hotels across two countries;
- 240 rooms across standard, family, accessible, and premium room types;
- 180 active synthetic bookings and a four-hour arrival horizon;
- 36 synthetic team members across operational skill groups;
- 18 critical assets, 12 open or planned work orders, and 6 suppliers;
- 6 food-service plans and 12 energy meters.

High-volume guests and rooms remain in world state but project to bounded hotel
and room-block aggregates in the UI. Identical seed, commands, and virtual time
produce identical events and evaluations.

### 8.3 Golden causal scenario

At fictional property `HOTEL-RIVERSIDE-CENTRAL`, occupancy is 96% and 44 guest
parties are due within four hours. A hot-water plant fault makes 18 rooms
unsellable while 7 additional rooms are not yet ready. Protected accessible and
family bookings constrain simple room swaps. Nearby sister properties have
limited compatible capacity.

The sensor emits `hotel.operations-risk.detected` after evaluating:

- rooms affected and estimated restoration time;
- arrival demand by room requirement and promised check-in window;
- ready-room and housekeeping capacity;
- protected accessibility and family constraints;
- compatible sister-property inventory and transfer time;
- contractor and engineering-team availability;
- guest disruption, recovery spend, and revenue-at-risk estimates.

The selected recovery plan:

1. expedites the critical work order;
2. prioritises eight recoverable rooms for engineering and housekeeping;
3. relocates ten compatible bookings to two sister properties;
4. preserves protected room requirements;
5. reallocates two qualified shifts;
6. issues guest communications and bounded recovery actions;
7. records the residual no-room and cost risk.

Cross-property relocation and total recovery value require a regional operations
decision. The post-command evaluation compares the chosen plan with an unchanged
baseline.

## 9. Hero workflow

`hotel-operations-recovery` runs:

1. **Detect Operational Risk** (`deterministic`) validates the sensor event and
   snapshots hotel, booking, room, asset, workforce, and policy versions.
2. **Assess Guest and Operational Impact** (`agent`) calls the canonical agent
   wrapper with typed read tools and returns evidence, constraints, and ranked
   impact.
3. **Plan Network Recovery** (`agent`) returns ranked candidate actions and a
   typed proposed plan; it cannot mutate world state.
4. **Evaluate Policy and Authority** (`deterministic`) computes whether the plan
   is reversible and inside synthetic thresholds.
5. **Approve Recovery Exception** (`hitl`) is required for cross-property
   relocation, protected-requirement exceptions, or recovery value above the
   regional threshold.
6. **Execute Recovery Plan** (`deterministic`) validates versions, authority,
   idempotency, and payload shape before issuing `hotel.recovery.execute`.
7. **Verify Recovery Outcome** (`deterministic`) records KPI deltas and residual
   constraints.

The default synthetic policy allows routine room/team coordination without HITL
only when it relocates no bookings, changes no protected requirement, commits at
most GBP 2,500, and preserves minimum engineering and housekeeping coverage.
Cross-property relocation always requires a decision. These are demo
assumptions, not customer or industry policy.

## 10. Personas and authority

Primary authority roles are:

- `hotel_general_manager`: routine property actions up to GBP 2,500;
- `regional_operations_manager`: cross-property plans and recovery value up to
  GBP 15,000;
- `hotel_operations_director`: exceptional hotel/network recovery up to
  GBP 150,000;
- `maintenance_manager`: work orders up to GBP 10,000;
- `estates_director`: major asset action up to GBP 250,000;
- `guest_recovery_manager`: guest actions up to GBP 2,000 aggregate;
- `commercial_director`: protected inventory and material revenue decisions;
- `workforce_planning_manager`: routine cross-property shift movement;
- `people_operations_director`: overtime or coverage exceptions;
- `food_beverage_operations_manager`: service-plan changes up to GBP 5,000;
- `sustainability_operations_manager`: reversible utility controls;
- `sustainability_director`: comfort/safety exceptions.

Authority rows name exact command families and bounds. A recommendation-producing
persona cannot approve its own proposal. Unknown actions, missing evidence,
stale versions, expired decisions, and namespace mismatches fail closed.

## 11. Skills, tools, and systems

### 11.1 Runtime skills

- `hotel-impact-assessor`
- `hotel-network-recovery-planner`
- `room-readiness-coordinator`
- `maintenance-response-planner`
- `guest-recovery-advisor`
- `occupancy-pressure-advisor`
- `workforce-balancing-advisor`
- `food-service-readiness-advisor`
- `energy-anomaly-advisor`

Each skill consumes typed evidence and returns a validated recommendation. No
skill writes world state.

### 11.2 MCP boundary

Read tools expose bounded views of:

- hotel and room readiness;
- bookings and protected requirements;
- asset faults and work orders;
- team skills and shift capacity;
- sister-property compatibility;
- service capacity, energy state, and synthetic policy.

Command tools prepare or execute only the workflow-specific typed command. Every
mutation includes command ID, workflow ID, expected entity versions, authority
reference where applicable, reason code, and evidence digest.

The pack declares no external capability in the first release. Generic PMS,
CMMS, workforce, guest-messaging, F&B, and energy roles are represented by
in-process adapters; the demo does not claim undocumented production-system
access.

## 12. Data flow

```text
hotel world virtual-time tick
  -> critical asset fault and arrival pressure
  -> hospitality sensor
  -> hotel.operations-risk.detected
  -> objective route
  -> HotelOperationsRecoveryOrchestrator
  -> versioned evidence snapshot
  -> impact assessor and network recovery planner
  -> deterministic policy evaluation
  -> governed persona decision
  -> typed hotel.recovery.execute command
  -> idempotent hotel-world mutation
  -> supporting workflow cascades where thresholds cross
  -> workflow, graph, memory, AG-UI, and UI projections
  -> baseline-versus-result evaluation
```

One workflow identity and terminal outcome remain consistent across every proof
surface. Cascades are deduplicated by source event and workflow type.

## 13. UI and seller journey

The default Hospitality scene shows six properties as bounded operational nodes.
Each node exposes aggregate room readiness, active arrivals, critical asset
health, workforce coverage, and service readiness. Animations are driven by real
world events:

- asset fault and rooms becoming unavailable;
- work-order dispatch;
- room blocks progressing to ready;
- guest parties moving between compatible properties;
- qualified shifts moving;
- recovery KPI resolution.

The workflow drawer keeps the approval gate inspectable and labels agent,
deterministic, and HITL work truthfully. The seller journey is:

1. reset the fixed demo seed;
2. open the property network scene;
3. trigger the named outage scenario;
4. inspect the operational impact and agent evidence;
5. review the regional decision;
6. observe typed commands and world mutations;
7. compare protected arrivals, revenue risk, disruption, and cost;
8. open Memory, Knowledge, AG-UI, and Constellation evidence for the same ID.

## 14. Failure handling

- Invalid pack references fail at startup; no fallback pack supplies missing
  Hospitality assets.
- Events and commands use typed validation and explicit rejection reasons.
- Optimistic versions and idempotency prevent duplicate room, booking, shift,
  work-order, guest-action, service, or energy mutations.
- Business rejections are not retried. Transient Durable activities use bounded
  substrate retry behavior.
- A stale or missing authority decision blocks execution and leaves the workflow
  inspectable.
- Agent/model failure remains a visible failure in live-AI mode. The separately
  labelled deterministic-fallback mode never masquerades as live AI.
- A no-action result is valid only with evaluated candidates, binding
  constraints, and baseline comparison.
- Reset and proof teardown preserve pre-existing dirty paths and remove only
  proof-owned runtime state.

## 15. Validation and proof

### 15.1 Automated tests

The implementation adds:

- pack discovery, construction, validation, ownership, and cross-pack isolation;
- customer-boundary scanning for identifying terms;
- domain/function/persona/authority/skill/tool consistency;
- entity, seed, deterministic dynamics, sensor deduplication, and reset tests;
- command schema, version, idempotency, protected-requirement, capacity,
  authority, and rejection tests;
- one orchestration-path test per workflow;
- canonical agent-session and observed-tool evidence tests;
- HITL persistence, resume, recovery, and self-approval tests;
- projection, bounded scene, API manifest, recording, and replay tests;
- proof-runner contract and clean-teardown tests.

### 15.2 Permanent commands

```bash
make prove VERTICAL=hospitality
make demo VERTICAL=hospitality
```

Proof must satisfy `docs/VERTICAL-PROOF.md` for all eight workflows, including:

- live causal chain and measured world mutation;
- cross-surface workflow identity and outcome;
- observed agent/tool execution;
- real authority and persisted HITL recovery context;
- Functions-disabled and world-disabled probes;
- live/replay visible parity;
- zero browser errors and zero dropped workflow events;
- bounded visual scale and first-visible-event latency;
- two consecutive complete qualifying runs from the same source and runtime
  fingerprint;
- clean teardown and repository-safety evidence.

Machine proof may set `build_ready: true`. Seller review remains `PENDING` until
a human reviews reset, pacing, visuals, approvals, and story coherence.

## 16. Completion criteria

The Hospitality vertical is complete only when:

1. `ZAVA_VERTICAL=hospitality` discovers and validates exactly eight non-stub
   workflows.
2. No identifying customer or brand terms appear in committed Hospitality
   assets or UI.
3. Inactive packs contribute no Hospitality assets, and Hospitality contributes
   none when inactive.
4. The hero proves asset fault through governed network recovery and measured
   post-command outcome.
5. Every supporting workflow has a distinct case, skill, command, projection,
   recording, and qualifying proof instance.
6. All phase truth modes match observed execution.
7. `make prove VERTICAL=hospitality` passes the current proof contract twice
   consecutively and emits a source-bound manifest.
8. `make demo VERTICAL=hospitality` creates a stable, inspectable seller state
   without touching user-owned work.
9. The final handoff states build readiness and seller-review status separately.
