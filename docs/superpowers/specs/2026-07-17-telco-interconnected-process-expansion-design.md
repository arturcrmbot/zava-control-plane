# Telco Interconnected Process Expansion — Design Spec

**Date:** 2026-07-17
**Status:** Approved
**Scope:** Six new, deeply interconnected Telco workflows on the existing
actor-world, Durable, governance, graph, memory, AG-UI, and operator surfaces.

## 0. Decision

Add six workflows that form one causal operating story:

1. `outage-risk-management`
2. `predictive-site-maintenance`
3. `field-repair-dispatch`
4. `capacity-optimization`
5. `service-ticket-resolution`
6. `retention-orchestration`

Do not add shallow catalogue-only domains. Every workflow must:

- originate from real simulated state or an explicit operator perturbation;
- create a canonical Workflow and objective;
- run through Azure Durable Functions;
- issue a typed, validated command;
- mutate authoritative world actors;
- reach an evidence-backed terminal evaluation;
- project material identities and decisions into graph/memory;
- render from real snapshot/journal state;
- participate in at least two cross-process causal links.

Together with the existing `network-incident`,
`proactive-customer-care`, and `order-to-activate` workflows, the Telco pack
will contain nine live workflow types covering 23 of the 37 saved source rows.

## 1. Catalogue coverage

| Workflow | Source rows | Primary outcome |
|---|---|---|
| Existing: `network-incident` | OSS-02 | Detect, reroute, recover |
| Existing: `proactive-customer-care` | OSS-14, BSS-03 | Identify impacted accounts, notify, credit |
| Existing: `order-to-activate` | BSS-06, BSS-07 | Validate feasibility and activate service |
| `outage-risk-management` | OSS-20 | Predict weather/grid outage risk and pre-stage response |
| `predictive-site-maintenance` | OSS-01, OSS-11 | Detect asset failure risk and create repair/replace work |
| `field-repair-dispatch` | OSS-09, OSS-10 | Allocate technician, route, and spare stock |
| `capacity-optimization` | OSS-03 (partial), OSS-04, OSS-08, OSS-12, OSS-17 | Relieve congestion while balancing QoE and energy |
| `service-ticket-resolution` | OSS-15, BSS-01, BSS-02, BSS-13 | Correlate customer tickets to root cause and resolve |
| `retention-orchestration` | BSS-04, BSS-05, BSS-14 (partial), BSS-17 (partial) | Convert repeated harm into governed retention action |

Covered after expansion:

- OSS: 13 of 20 rows;
- BSS: 10 of 17 rows;
- total: 23 of 37 rows.

Deferred rows remain explicit rather than implied:

- OSS-05, OSS-06, OSS-07, OSS-13, OSS-16, OSS-18, OSS-19;
- BSS-08, BSS-09, BSS-10, BSS-11, BSS-12, BSS-15, BSS-16.

## 2. Demonstration story

### 2.1 Primary cascade: storm to retention

```text
weather/grid risk rises
  → outage-risk-management pre-stages field resources
  → asset health degrades
  → predictive-site-maintenance creates urgent work
  → spare shortage or technician delay
  → field-repair-dispatch schedules late repair
  → site fails
  → existing network-incident reroutes sessions
  → neighbours congest
  → capacity-optimization tunes capacity/energy
  → existing proactive-customer-care notifies and credits
  → service-ticket-resolution correlates ticket storm to incident
  → repeated experience harm raises churn risk
  → retention-orchestration proposes governed offer
```

### 2.2 Order interaction

Existing `order-to-activate` participates in the same world:

- congestion can make an order infeasible;
- `capacity-optimization` can create enough headroom to unblock it;
- a failed activation can create a service ticket;
- delayed activation contributes to experience and churn history.

### 2.3 Alternative outcomes

The world must support both prevention and failure:

- early maintenance avoids the outage entirely;
- no spare stock causes a missed maintenance window;
- field repair restores the failed asset and returns rerouted sessions;
- capacity optimisation can trade energy saving against order backlog;
- tickets can resolve automatically when evidence confirms recovery;
- retention can be declined by policy or a human approver.

## 3. Simulation model

The Telco `NetworkScenario` remains the only writer of actor state.

### 3.1 New actors

```python
NetworkAsset(
    id,
    site_id,
    kind,                 # radio-unit | power | cooling | backhaul
    health,               # 0.0–1.0
    temperature_c,
    load,
    failure_probability,
    status,               # healthy | degraded | failed | maintenance
)

WeatherEvent(
    id,
    region,
    severity,
    power_risk,
    cooling_risk,
    starts_at,
    ends_at,
)

WorkOrder(
    id,
    site_id,
    asset_id,
    kind,                 # inspect | repair | replace | augment
    priority,
    required_skill,
    required_spare,
    status,               # open | planned | dispatched | active | completed | failed
    due_at,
)

Technician(
    id,
    region,
    skills,
    status,               # available | travelling | working | unavailable
    assigned_work_order_id,
)

SpareStock(
    id,
    region,
    part_kind,
    quantity,
    reorder_point,
)

CareTicket(
    id,
    account_id,
    subscription_id,
    incident_trace_id,
    category,
    severity,
    status,               # open | correlated | resolving | resolved | escalated
    root_cause,
)

ExperienceEpisode(
    id,
    account_id,
    source_trace_id,
    kind,                 # outage | congestion | failed-activation | ticket | credit
    impact_score,
    occurred_at,
)

RetentionOffer(
    id,
    account_id,
    reason,
    value_gbp,
    offer_kind,
    status,               # proposed | awaiting-approval | issued | accepted | declined
)
```

### 3.2 Initial deterministic scale

- 12 existing sites;
- 4 assets per site: 48 `NetworkAsset` actors;
- 2,000 existing accounts/subscriptions/subscribers;
- 2,200 existing sessions;
- 20 technicians across four regions;
- regional spare stock for radio, power, cooling, and backhaul parts;
- ticket and experience actors created only by world events;
- one seeded high-value business account and one vulnerable consumer;
- one seeded spare shortage and one technician unavailability case.

Same seed plus same perturbations must produce the same actor state and
deterministic simulation events. LLM recommendations are not assumed
byte-identical; exact public replay comes from recorded accepted outcomes.

### 3.3 Dynamics

Every simulation interval:

1. asset health decays by age, load, temperature, and active weather;
2. failure probability is derived from health and telemetry;
3. high utilisation increases temperature and energy draw;
4. weather affects power/cooling assets by region;
5. technician travel and work advance;
6. spare reservations decrement regional stock;
7. completed work changes asset/site state;
8. customer experience and churn projections update from material events;
9. sensors evaluate rising-edge conditions with per-target dedupe.

No independent random KPI generator is allowed. Signals are projections over
actor state and causal events.

## 4. Objective routes and commands

| Sensor | Objective | Command | Success evidence |
|---|---|---|---|
| `sensor:outage_risk` | `outage_prevention` | `prestage_field_resources` | `resources.prestaged` |
| `sensor:asset_failure_risk` | `site_maintenance` | `create_maintenance_work_order` | `work_order.created` |
| `sensor:work_order_ready` | `field_repair` | `dispatch_field_repair` | `asset.repaired` or `asset.replaced` |
| `sensor:site_congestion` | `capacity_recovery` | `apply_capacity_action` | `site.capacity.stable` |
| `sensor:ticket_pressure` | `ticket_resolution` | `resolve_ticket_batch` | `ticket_batch.resolved` |
| `sensor:churn_risk` | `customer_retention` | `apply_retention_offer` | `retention_offer.issued` |

All commands must:

- be scoped by claimed objective and trace;
- use deterministic command IDs;
- validate the complete batch before mutation;
- reject unknown or already-terminal actors;
- enforce finite resources and authority evidence;
- be idempotent;
- emit command/result events on the objective trace.

## 5. Workflow designs

### 5.1 `outage-risk-management`

| Phase | Kind | Purpose |
|---|---|---|
| External Signal Correlation | deterministic | Join weather/grid risk to regions/sites |
| Exposure Assessment | agent | Rank sites, customers, orders, and assets at risk |
| Pre-stage Plan | agent | Select technicians, spares, and safe capacity |
| High-cost Approval | HITL | `delivery_lead` approves exceptional mobilisation |
| Pre-stage Execution | deterministic | Apply bounded resource reservations |
| Risk Verification | deterministic | Confirm exposure reduction |

### 5.2 `predictive-site-maintenance`

| Phase | Kind | Purpose |
|---|---|---|
| Telemetry Correlation | deterministic | Gather health, temperature, load, alarms |
| Failure Diagnosis | agent | Explain likely failing component and confidence |
| Repair-or-Replace Decision | agent | Select work type and required part |
| Replacement Approval | HITL | `delivery_lead` approves expensive swaps |
| Work Order Creation | deterministic | Create real `WorkOrder` actor |
| Maintenance Verification | deterministic | Confirm work exists and risk is controlled |

### 5.3 `field-repair-dispatch`

| Phase | Kind | Purpose |
|---|---|---|
| Work Intake | deterministic | Load work order, SLA, region, skill, part |
| Resource Matching | agent | Rank technician/spare combinations |
| Dispatch Plan | deterministic | Calculate bounded assignment and route |
| Exception Approval | HITL | Handle overtime, cross-region, or no-spare exception |
| Repair Execution | deterministic | Advance travel/work and mutate asset |
| Repair Verification | deterministic | Confirm telemetry/site recovery |

### 5.4 `capacity-optimization`

| Phase | Kind | Purpose |
|---|---|---|
| Congestion Correlation | deterministic | Gather site/neighbour/session/order load |
| Optimisation Plan | agent | Compare reroute, carrier, power, and augmentation |
| Guardrail Evaluation | deterministic | Validate capacity, QoE, energy, blast radius |
| Capital Approval | HITL | Approve permanent augmentation only |
| Optimisation Execution | deterministic | Apply reversible capacity action |
| Stability Verification | deterministic | Confirm congestion/order feasibility outcome |

### 5.5 `service-ticket-resolution`

| Phase | Kind | Purpose |
|---|---|---|
| Ticket Intake | deterministic | Group tickets by account, service, symptom |
| Root-cause Correlation | agent | Link tickets to incident, congestion, or activation |
| Resolution Plan | agent | Select auto-resolution, care, or escalation |
| Vulnerable Customer Review | HITL | `cs_manager` reviews protected cases |
| Resolution Execution | deterministic | Update real ticket actors |
| Customer Verification | deterministic | Confirm service state and ticket closure |

### 5.6 `retention-orchestration`

| Phase | Kind | Purpose |
|---|---|---|
| Experience Aggregation | deterministic | Aggregate episodes, credits, tickets, tenure |
| Churn Driver Analysis | agent | Explain risk and attributable drivers |
| Offer Selection | agent | Select action within margin/fairness policy |
| High-value Offer Approval | HITL | `cs_manager` approves exceptional value |
| Offer Execution | deterministic | Create and issue real `RetentionOffer` |
| Outcome Tracking | deterministic | Record accepted/declined result and churn delta |

## 6. Authority and personae

Reuse existing Telco personae where possible:

- `delivery_lead`: field, maintenance, capacity, and mobilisation exceptions;
- `cs_manager`: vulnerable-customer and high-value retention decisions.

Add one operations escalation persona:

- `network_ops_director`: approves replacements, permanent augmentation, or
  mobilisation above the `delivery_lead` £10k band.

The network-operations hierarchy becomes
`network_ops_director -> delivery_lead`; the authority delegate chain must
resolve entirely inside the Telco pack.

Authority rules must distinguish:

- reversible low-risk actions: automatic;
- overtime/cross-region dispatch: bounded approval;
- replacement or permanent capacity cost: delivery-lead approval;
- vulnerable-customer treatment: mandatory customer-success review;
- retention value above policy band: customer-success approval.

Agent output never authorises itself. Authority evidence is validated before a
command mutates world state.

## 7. Inter-process event contract

Each objective owns a distinct trace derived from its triggering sensor event.
Cross-process causality is carried by:

- `cause_event_id` pointing to the earlier material event;
- `parent_trace_id` naming the immediate upstream workflow;
- `contributing_trace_ids` for later aggregate decisions such as retention.

This is mandatory because `OutcomeEvaluator` matches evidence by trace. Sharing
one storm trace across concurrent objectives could let one command rejection
fail unrelated evaluations.

```text
weather.risk.detected
asset.risk.changed
work_order.created
work_order.dispatched
technician.arrived
asset.repaired
site.failed
session.degraded
site.congestion.detected
site.capacity.stable
ticket.created
ticket.correlated
ticket.resolved
experience.recorded
churn.risk.changed
retention_offer.issued
```

Required cross-links:

- outage risk creates maintenance or pre-stage objectives;
- maintenance creates work ready for field dispatch;
- missing spares raise dispatch exception and site-failure likelihood;
- site failure drives existing incident and proactive care;
- reroute load drives capacity optimisation;
- capacity outcome changes pending order feasibility;
- `site.capacity.stable` re-emits `sensor:service_order` for pending or
  infeasible orders at that site, creating a new activation objective/trace;
- session degradation and failed activation create tickets/experience episodes;
- care credit and ticket outcome change churn risk;
- retention decision references all contributing traces.

## 8. Graph and memory

Use existing generic graph kinds:

| Concept | Graph representation |
|---|---|
| Site, network asset, spare, subscription | `Asset` with `kind` |
| Technician, customer | `Person` |
| Work order, ticket, retention offer | `Asset` with `kind` |
| Process run | `Workflow` |
| Cost, credit, offer value | `Money` |
| Region | `Place` |
| Agent/HITL verdict | `Decision` |

Add the following generic, typed relationships to the shared graph schema:

```text
ASSET_AT_SITE       Asset -> Asset
WORK_FOR_ASSET      Asset -> Asset
ASSIGNED_TO         Asset -> Person
REQUIRES_SPARE      Asset -> Asset
TICKET_FOR_SERVICE  Asset -> Asset
OFFER_FOR_ACCOUNT   Asset -> Account
```

Trace IDs remain node attributes and decision evidence; traces are not graph
nodes, so no `CAUSED_BY_TRACE` relationship is introduced.

Operational memory stores:

- diagnosis and repair outcomes by asset kind;
- technician/part effectiveness;
- capacity action effectiveness;
- ticket root-cause and resolution;
- retention offer/result.

Memory records material outcomes, not every simulation tick.

## 9. Operator experience

Retain shared Control Plane shell and add one lens:

1. **Network** — weather overlay, site risk, asset health, congestion.
2. **Field Operations** — work-order lanes, technicians, spares, ETAs.
3. **Customer Impact** — tickets, experience episodes, churn, offers.
4. **Orders** — existing fulfilment and capacity blockers.
5. **Control** — objectives, workflows, HITL, evaluations, causal journal.

Visual rules:

- every card/token references a real actor ID;
- every animation references a journal sequence;
- selecting any actor filters the causal journal;
- one trace can show multiple workflows side by side;
- prevention success is visible even when no outage occurs;
- no generic JSON fallback is treated as a finished UI.

Blueprint Constellation remains domain-driven. Nine Telco workflow clusters
appear from the active pack registry without Telco-specific 3D code.

Function ownership:

- `network-operations`: network incident, order activation, outage risk,
  predictive maintenance, field dispatch, capacity optimisation;
- `customer-success`: proactive care, service ticket resolution, retention.

Every new Domain declares its matching operator surface and is wired through
these two existing functions; no new organisational function is added.

## 10. Demo scenarios

### Scenario A — Storm cascade

Full primary story from outage risk through retention.

### Scenario B — Maintenance saves the outage

Prediction, work order, dispatch, repair; no site failure. Demonstrates value
without forcing every run into failure.

### Scenario C — Capacity squeeze blocks revenue

High neighbour load blocks `order-to-activate`; optimisation frees capacity;
order activates.

### Scenario D — Vulnerable customer escalation

Repeated degradation creates tickets and churn risk; care and retention both
reach `cs_manager`.

Each scenario is deterministic by seed and inject endpoint. One browser proof
must exercise all four without fabricated UI state.

## 11. Failure handling

- Missing technician or spare creates an explicit exception, not a fake dispatch.
- Invalid/partial command batches produce `command.rejected`; no mutation.
- Durable failure marks Workflow/objective/evaluation failed and world continues.
- Agent deferral leaves actors unchanged and exposes reasoning.
- External model failure never fabricates an agent decision: the workflow
  either executes an already-declared deterministic safe action, reaches HITL,
  or fails visibly.
- Duplicate sensor event creates no second active objective for the same target.
- HITL timeout emits terminal failure and releases reservations.
- Resource reservation rolls back when dispatch/approval fails.
- World and graph never silently back-sync into each other.

## 12. Testing and proof

### Unit

- deterministic actor generation and referential integrity;
- each dynamic/sensor rising edge and dedupe;
- command atomicity, idempotence, resource bounds;
- authority thresholds and persona event names;
- projection and memory registration;
- pack/domain/function/orchestrator validation.

### Integration

- each workflow completes against the real actor world with only Durable
  transport mocked;
- cross-process events preserve trace/cause chains;
- prevention path and failure path both terminal;
- capacity action changes real order feasibility;
- repair changes telemetry and network state;
- ticket/credit/retention effects change experience/churn projection.

### Unmocked live proof

Boot isolated:

```text
Azurite → selected Telco Functions → FastAPI Telco world
        → Control Plane → Blueprint
```

Machine-check:

- nine Telco workflow types in active manifest;
- four deterministic scenarios;
- real Durable instance output for every workflow;
- actor command equality with journal and DOM;
- graph/memory records reference same IDs/traces;
- AG-UI shows agents, tools, HITL, terminal state;
- no browser/page/application-network errors;
- replay contains all nine workflow types with Functions unreachable;
- all exact process handles and proof ports released.

The deterministic full-cascade proof validates actor IDs, safe command
envelopes, causality, and terminal outcomes. Separate live-agent smoke checks
validate each reasoning skill. External model failure must remain visible and
must not be rewritten as a successful decision.

## 13. Delivery boundaries

Implementation sequence:

1. shared actors, dynamics, sensors, routes, and UI types;
2. outage + maintenance;
3. field dispatch;
4. capacity optimisation and order coupling;
5. service tickets;
6. retention;
7. graph/memory and operator lenses;
8. cross-process proof and replay.

Each boundary is separately tested and committed. No new substrate
architecture, plugin system, UI DSL, or unrelated Agency refactor is allowed.

## 14. Non-goals

- implementing all remaining 14 catalogue rows;
- full RF propagation or geospatial map fidelity;
- real technician GPS routing;
- real ERP/FSM/CRM integrations;
- learned predictive models in V1;
- self-modifying policies;
- separate simulators per process;
- runtime-generated UI layouts.
