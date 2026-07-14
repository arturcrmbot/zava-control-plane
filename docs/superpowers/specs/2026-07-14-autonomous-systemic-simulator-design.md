# Autonomous Systemic Simulator — Roadmap Design

**Date:** 2026-07-14  
**Status:** Autonomous design decision; operator unavailable for review  
**Builds on:** [`2026-07-13-observable-actor-simulator-design.md`](2026-07-13-observable-actor-simulator-design.md)

## 0. Current position

The substrate now proves two real closed loops:

1. **Support:** explicit customers/tickets/workers → pressure sensor → real
   Durable staffing responder → typed worker reallocation → later ticket
   outcomes.
2. **Telco network:** explicit cell sites/subscribers/sessions → site failure →
   network anomaly → real Durable incident responder → typed session reroute →
   site and session recovery.

Both loops are deterministic, causal, observable in `/world`, and proven
against real Azurite + Azure Durable Functions + FastAPI + Playwright.

That is a strong reactive simulator. It is not yet an autonomous systemic
organisation because:

- each sensor is directly wired to one responder
- perturbations are mostly operator-injected
- scenarios are selected by branches rather than a pack contract
- organisational objectives are implicit
- loops do not yet contend for shared cross-function resources
- intervention effectiveness is not evaluated as a first-class episode
- completed episodes do not influence future policy

---

## 1. Autonomy boundary

### Decision

Top-level organisational goals remain explicit and governed.

Agents may autonomously:

- observe world state
- detect conditions
- create and prioritise objectives
- decompose objectives into bounded sub-goals
- select registered responders
- issue typed commands within granted authority
- evaluate results
- propose policy or strategic-goal changes

Agents may not autonomously:

- invent new command types
- extend their own authority
- bypass budget, kill switch or command validation
- mutate world physics
- silently adopt a new top-level organisational goal

A proposed strategic goal becomes active only through the existing governance
and policy-decision path.

This is **bounded goal-directed autonomy**, not unrestricted self-direction.

---

## 2. Chosen roadmap approach

### Rejected: engine-first framework

Building a generic autonomy framework before another real vertical would
produce speculative interfaces and no proof that they fit organisational
work.

### Rejected: telco-first hard-coding

Adding more `if scenario == "telco"` branches would create a convincing demo
that cannot become an industry-independent engine.

### Chosen: coupled vertical slices

Each slice must add:

1. one real systemic telco interaction
2. only the reusable engine contract required by that interaction
3. one real Durable agent/command loop
4. deterministic replay and evaluation
5. event-backed visual proof

No abstraction is introduced until two real consumers need it.

---

## 3. Missing reusable engine capabilities

### 3.1 Scenario pack contract and registry

Support and telco currently share one service but still expose
scenario-specific branches. The third scenario/domain interaction justifies a
small pack contract:

```python
class ScenarioPack(Protocol):
    name: str
    runtime: SimulationRuntime

    def render_state(self) -> dict: ...
    def build_observation(self, event: dict, *, now: float) -> dict: ...
    def apply_command(self, command: SimulationCommand) -> SimulationEvent: ...
    def inject(self, name: str, payload: dict) -> str: ...
```

A registry maps `ZAVA_WORLD` to a pack builder. `ActorWorldService` no longer
switches on scenario names.

Do not add package discovery, entry points or dynamic plugins. A Python dict
with two/three builders is sufficient.

### 3.2 Objective manager

Sensors should create `Objective` records rather than name a Durable
orchestrator directly:

```python
Objective(
    id,
    type,
    trace_id,
    owner_function,
    priority,
    status,
    created_at,
    deadline,
    evidence_event_ids,
    allowed_command_types,
)
```

States:

```text
open → claimed → acting → evaluating → resolved | failed | superseded
```

Responsibilities:

- deduplicate objectives for the same episode
- prioritise by severity, deadline and organisational goal
- enforce one owner/responder
- journal every lifecycle transition
- expose objectives through world snapshot/events

The objective manager is in-process and deterministic. It is not another
agent.

### 3.3 Responder registry

A small mapping replaces sensor-specific bridge branching:

```python
RESPONDERS = {
    "support_capacity": SurgeStaffingOrchestrator,
    "network_service_recovery": NetworkIncidentOrchestrator,
    "field_repair": FieldDispatchOrchestrator,
    "customer_harm": CustomerCareOrchestrator,
}
```

Each entry declares:

- objective type
- Durable orchestrator
- observation builder
- allowed command types
- timeout

The bridge operates on objectives, not raw sensor types.

### 3.4 Command gateway

Scenario validation remains local because command semantics are domain
specific.

One shared gateway performs only cross-cutting checks:

- objective permits command type
- issuer owns/claimed objective
- governance/authority allows action
- command ID idempotency
- global budget and kill switch
- outcome journal link to objective/trace

The gateway delegates world mutation to `pack.apply_command()`.

### 3.5 Episode evaluator

Every objective declares success measures and an evaluation horizon:

```python
Evaluation(
    objective_id,
    baseline_measurements,
    final_measurements,
    intended_effect,
    side_effects,
    verdict,
)
```

Examples:

- Did network packet loss recover?
- How many sessions were restored/dropped?
- Did rerouting overload a neighbour?
- Did complaint volume fall?
- What did the intervention cost?

Evaluation closes an episode. It does not change policy by itself.

### 3.6 Autonomous environment

Manual injection remains for demos, but real runs need deterministic
exogenous processes:

- diurnal traffic curves
- stochastic equipment failures
- weather events
- campaign-driven demand
- employee shifts/absence
- customer contact propensity

All randomness stays seeded and journalled.

### 3.7 Checkpoints and branching

The current seed+journal replay is sufficient for reproduction, but systemic
experimentation needs:

- periodic actor-state checkpoints
- fork from checkpoint with alternate command/policy
- compare episode evaluations
- recorded external Durable/LLM outputs during replay

SQLite or compressed JSON checkpoints are sufficient initially. No distributed
state store.

---

## 4. Full telco systemic world

The next telco world is one coupled organisation, not independent demos.

### 4.1 Network operations — shipped foundation

Actors:

- cell sites
- subscribers
- voice/data/video sessions

Processes:

- traffic/load
- site failure
- session degradation
- anomaly detection
- autonomous reroute

Domain:

- `network-incident`

### 4.2 Customer care

Actors:

- customer contact
- care case
- care advisor
- care queue/team

World coupling:

- degraded/dropped sessions raise contact probability
- premium/vulnerable customers have different patience and escalation
- queue delay reduces sentiment and raises churn risk
- proactive notification can suppress inbound contacts

Domain:

- `customer-care-surge`

Commands:

- `reallocate_advisors`
- `send_proactive_notification`
- `prioritise_cases`

### 4.3 Field operations

Actors:

- field engineer
- depot
- van
- repair job
- site spare part

World coupling:

- failed site creates repair objective
- engineer skills, shift, travel time and parts constrain dispatch
- engineers are shared across incidents
- repair restores site capacity; rerouted sessions may return later

Domain:

- `field-repair-dispatch`

Commands:

- `dispatch_engineer`
- `reserve_part`
- `change_job_priority`

### 4.4 Customer/commercial consequences

Actors/state:

- customer sentiment
- churn propensity
- plan/value segment
- retention offer

World coupling:

- repeated service harm accumulates
- care handling can recover sentiment
- retention intervention costs margin
- network/care actions alter churn trajectory

Domain:

- `proactive-retention`

This is the second telco slice, after network+care+field works.

### 4.5 Finance/regulatory consequences

Derived effects:

- SLA credits
- engineer/overtime cost
- retention cost
- outage duration/severity
- regulatory-reporting threshold

Domains:

- `service-credit-assessment`
- `major-outage-reporting` only after the core cascade is proven

---

## 5. First systemic telco slice

### Story

```text
weather/transport fault
  → SITE-03 fails
  → sessions degrade and reroute pressure spreads
  → network-recovery objective opens
  → customers begin contacting care
  → care queue grows
  → customer-harm objective opens
  → field-repair objective competes for scarce engineers
  → network agent applies safe temporary reroute
  → field agent dispatches qualified engineer with required part
  → care agent sends proactive notification / prioritises vulnerable cases
  → repair restores site
  → traffic normalises, complaint rate falls
  → evaluators measure restoration, neighbour overload, customer harm and cost
```

### Shared resources

- reserve network capacity
- field engineers
- spare parts
- care advisors
- intervention budget

Contention must be real. A command that consumes a resource changes what other
objectives can do.

### New domains in this slice

1. `field-repair-dispatch`
2. `customer-care-surge`

`network-incident` remains the initiating/recovery domain.

---

## 6. Visualisation

The `/world` route becomes a systemic operations view:

- network sites/sessions remain visible
- care contacts/cases queue from actual service-harm events
- field engineers/jobs move through dispatch/travel/repair states
- objectives appear with priority/status/owner
- shared resources show actual reservations
- causal traces connect one site failure across network, care and field events
- episode evaluation shows intended and side effects

No aggregate dashboard replaces actors. Aggregates remain secondary
instrumentation.

The viewer stays scenario-specific where the actor semantics differ. Share
only causal/intervention primitives already used twice.

---

## 7. Safety and governance

- reversible operational commands may auto-execute inside configured limits
- irreversible/high-cost commands require authority/policy approval
- every objective declares allowed commands
- every command is typed, validated and idempotent
- command budget and global kill switch apply before mutation
- responder timeout/failure leaves world running and objective failed/open
- objective storms are deduplicated and rate limited

---

## 8. Determinism and learning

World behavior remains deterministic from:

```text
scenario version + seed + inputs + recorded external commands
```

LLM/Durable outputs are recorded and replayed, not regenerated.

Learning is deliberately deferred until evaluators exist. The first learning
feature may propose a policy change from repeated episodes, but activation
flows through existing policy governance.

---

## 9. Implementation roadmap

### Plan A — autonomy kernel through existing scenarios

- scenario registry/contract
- objective model/manager
- responder registry
- command gateway
- episode evaluator foundation
- migrate support and network-incident without changing behavior

Proof: existing support/telco browser proofs remain identical, with objective
and evaluation events added.

### Plan B — coupled network + field + care

- field actors/processes/resources
- care actors/processes/resources
- automatic service-harm → contacts/cases
- `field-repair-dispatch` Durable domain
- `customer-care-surge` Durable domain
- shared-resource contention
- systemic viewer

Proof: one real site failure closes all three objectives with actor-level and
Durable evidence.

### Plan C — autonomous environment + experiments

- diurnal traffic and deterministic fault generator
- checkpoints/forks
- episode comparison
- replay with recorded responder outputs

### Plan D — commercial/finance consequences

- churn/retention
- SLA credits/cost
- governed policy proposals

---

## 10. Success criteria

The engine is “autonomous systemic” when:

1. A run proceeds without operator injection.
2. One world event produces multiple competing objectives.
3. Several Durable agents act through typed commands.
4. Commands contend for finite shared resources.
5. Actions create second-order effects in other functions.
6. Every episode has causal provenance and an effectiveness evaluation.
7. Replay reproduces the run without recalling external agents.
8. The UI shows actual actors/objectives/resources changing.
9. Governance can block, cap or stop autonomy.
10. A third industry can implement the scenario contract without modifying
    the engine service.

