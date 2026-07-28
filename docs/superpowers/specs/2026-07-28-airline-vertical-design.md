# Airline Operating-Company Vertical Design

**Date:** 2026-07-28  
**Status:** Approved Phase Design  
**Target:** Reusable synthetic network-airline operating-company vertical  
**Build state:** Not asserted by this document; Phase Build is a separate gate

## 1. Decision

Design an `airline` vertical for a network airline that operates aircraft,
crew, slots, and a hub schedule under its own operating authority. The vertical
is inspired by operating realities described in public airline, regulator, and
industry sources, including public disclosures associated with British Airways
and International Airlines Group. It does not reproduce either organisation.

The approved hero portfolio is:

1. **Integrated Hub Disruption Recovery** as the golden flagship.
2. **AOG Engineering and Spares Recovery** as hero 2.
3. **Pre-emptive Schedule Resilience** as hero 3.

The golden story starts with a delayed inbound aircraft and a constrained hub
stand. Those events create a visible cascade across an aircraft rotation, crew
duty margin, departure slots, stands, and passenger-connection cohorts.
Operations Control receives feasible recovery options, a human approves the
material intervention, typed actions mutate the synthetic world, and the
evaluation shows the operational outcome and counterfactual.

The vertical is intentionally an airline operating-company design, not a
travel retailer, tour operator, airport, alliance, air-navigation provider, or
maintenance vendor.

## 2. Evidence and synthetic-data boundary

### 2.1 What public sources may establish

Public sources may establish broad operating realities and regulatory
obligations, including:

- network airlines coordinate schedules, aircraft, crew, airports, ground
  handlers, and air-traffic constraints during disruption;
- realistic, deliverable schedules and cross-industry resilience planning are
  expected;
- safety and security cannot be traded away to recover punctuality;
- disrupted passengers have information, care, rerouting, refund, assistance,
  and, in qualifying cases, compensation rights;
- airport collaborative decision making uses shared operational milestones;
- fleet availability depends on maintenance capacity, approved repair routes,
  spares lead times, traceability, and supply-chain visibility;
- large airline groups publicly discuss operational performance,
  transformation, fleet investment, customer outcomes, and resilience.

These facts justify the vertical's entity families, causal relationships,
decision boundaries, and KPI categories. They do not justify copying a named
airline's internal workflow, system configuration, policy threshold, authority
limit, schedule, fleet record, customer record, or recovery algorithm.

### 2.2 What must always be synthetic

Every operating record and scenario is synthetic and visibly labelled as such.
This includes:

- airline identity, callsigns, flight numbers, routes, hubs, stations, slots,
  stands, aircraft registrations, fleet mix, and schedules;
- employees, roles below public archetype level, crew qualifications, rosters,
  pairings, duties, legality margins, and reserve availability;
- customers, passenger counts, connection cohorts, accessibility needs,
  bookings, entitlements, and communications;
- defects, maintenance findings, engineering work, spares, suppliers, costs,
  repair durations, and return-to-service evidence;
- disruption events, weather, airport constraints, air-traffic restrictions,
  recovery plans, approvals, commands, outcomes, and KPI values;
- authority limits, escalation paths, automation thresholds, policy wording,
  and decision reasons.

Synthetic records use unmistakable identifiers such as `SYN-HUB`,
`SYN-TAIL-001`, `SYN-SECTOR-001`, and `SYN-DUTY-001`. UI labels and evidence
bundles state that the world is synthetic. No synthetic value is presented as a
benchmark, policy, or performance claim about a real airline.

### 2.3 Prohibited source use

The vertical must not ingest, infer, reconstruct, or imitate:

- confidential or leaked airline manuals, disruption playbooks, operational
  control procedures, authority matrices, crew records, maintenance records,
  passenger records, or supplier terms;
- proprietary airline schedules, optimization models, recovery heuristics,
  system prompts, internal system names, or non-public performance data;
- logos, liveries, trademarks, named-airline branding, or a look-and-feel that
  could imply endorsement;
- real incidents presented as replayable synthetic scenarios without explicit
  abstraction and removal of identifying facts.

## 3. Airline-versus-Travel boundary

The existing `travel` vertical models a tour operator and package-holiday
retailer. The airline vertical must remain materially different.

| Concern | Airline operating-company vertical | Existing Travel vertical |
|---|---|---|
| Primary responsibility | Operate a safe, legal, resilient flying programme | Sell and fulfil package holidays |
| Core assets | Aircraft, rotations, crew duties, slots, stands, maintenance status | Packages, hotel allotments, transfers, supplier inventory |
| Operational centre | Airline Operations Control and engineering control | Tour-operator operations and destination operations |
| Disruption decision | Recover the flying programme under aircraft, crew, airport, and airspace constraints | Reaccommodate package customers across travel suppliers |
| Revenue/capacity scope | Flight schedule and network resilience | Package yield and hotel capacity |
| Customer scope | Passenger-impact cohorts and statutory care/rerouting consequences | Individual package bookings, hotels, transfers, refunds, and payments |
| Typed actions | Re-time or cancel sectors, swap eligible tails, activate reserve crew, reassign stands, create engineering/spares actions | Rebook travellers, move hotel allotments, dispatch resort transfers, refund package bookings |
| Explicit exclusions | Hotel contracting, resort transfers, package sales, package payment exceptions | Aircraft technical control, crew legality, airworthiness, slot and rotation control |

Passenger consequences belong in the airline world because operational choices
affect connections, care, rerouting, and accessibility. They remain downstream
operational impacts, not a package-holiday fulfilment model.

## 4. Goals

1. Show how a network airline detects, explains, governs, and resolves a
   multi-constraint operational disruption.
2. Make the causal relationship between aircraft, crew, slots, stands,
   engineering, and passenger impact visible in one actor world.
3. Demonstrate bounded autonomy: AI may analyse and rank evidence, while
   deterministic controls and authorised people own safety, legality, and
   consequential decisions.
4. Present three distinct, credible hero stories with separate triggers,
   commands, world mutations, and proof evidence.
5. Support a seller journey that starts from a healthy synthetic operation,
   introduces a named event, shows the cascade, obtains an approval, applies a
   command, and measures the result.
6. Preserve deterministic reset and replay so the same source state and
   decisions produce the same evidence.
7. Satisfy the current vertical proof contract without inflating machine proof
   into seller approval.

## 5. Explicit non-goals

- Reproduce British Airways, IAG, or any other named airline.
- Model an airline group holding company, alliance governance, joint-business
  economics, loyalty programme, or corporate finance consolidation.
- Replace certified dispatch, crew-control, maintenance-control, flight
  planning, safety-management, or airworthiness systems.
- Let AI release an aircraft, defer a defect, certify maintenance, waive crew
  legality, override a slot or airport restriction, or compromise safety.
- Build a complete passenger-service, ticketing, pricing, revenue-management,
  loyalty, cargo, catering, fuel-hedging, or airport-operations platform.
- Implement exact UK261 eligibility or compensation calculations as legal
  advice. The vertical may surface deterministic synthetic entitlement
  indicators and route uncertain cases to a human.
- Copy the Travel vertical's package booking, hotel, transfer, refund, or
  payment processes under airline terminology.
- Claim optimized or globally optimal recovery. The design requires feasible,
  explainable options and measurable outcomes.
- Create process breadth before each declared hero can be proved independently.

## 6. Operating model and actor world

### 6.1 Organisational boundary

The model contains one synthetic network airline operating company with:

- a primary synthetic hub and a small set of outstations;
- an Airline Operations Control centre;
- a Maintenance Control Centre and continuing-airworthiness function;
- network and schedule-planning teams;
- crew control and reserve-crew coordination;
- airport and ground-handling counterparties;
- customer operations responsible for disruption impact and care;
- external air-traffic, airport-capacity, weather, and supplier signals.

Airport, ground-handler, air-traffic, regulator, MRO, OEM, and parts-supplier
actors are external counterparties. They publish constraints or fulfil approved
requests; they are not controlled by the airline.

### 6.2 Human actors

| Actor | Responsibility | May decide | Must not delegate to AI |
|---|---|---|---|
| Hub Operations Officer | Monitor the live hub bank and prepare bounded recovery options | Routine reversible operational actions within synthetic authority | Safety, legality, material cancellation, or exceptional spend |
| Duty Operations Manager | Own the integrated operational recovery decision | Material tail, sector, stand, reserve-crew, and passenger-impact plan | Final accountability for the approved recovery plan |
| Crew Controller | Validate duty, qualification, positioning, and reserve-crew feasibility | Crew assignments within deterministic legality and authority | Waiver of legality, qualification, or fitness constraints |
| Engineering Controller | Coordinate technical status, work, and spares options | Approved maintenance coordination within role authority | Airworthiness release or defect deferral outside certified process |
| Engineering Duty Manager | Approve material engineering and spares recovery | Work package, approved-provider, spares, ferry or substitution decisions within policy | Airworthiness certification or unsupported technical judgement |
| Network Planning Manager | Prepare resilience interventions before the day of operation | Bounded schedule buffers and capacity moves | Material publication changes or slot surrender beyond authority |
| Network Operations Director | Own consequential schedule-resilience decisions | Material retiming, cancellation, slot, capacity, and cost choices | Safety or legality overrides |
| Customer Operations Lead | Assess passenger cohorts, accessibility, care, and communication consequences | Care and communication action within synthetic policy | Suppression of rights or vulnerable-passenger protections |

### 6.3 Entities and relationships

The actor world contains:

- `Airline`, `Station`, `Hub`, `Route`, `Sector`, `Rotation`;
- `Aircraft`, `AircraftConfiguration`, `TechnicalStatus`;
- `CrewMember`, `CrewDuty`, `Pairing`, `Qualification`, `ReserveCrew`;
- `Slot`, `Stand`, `Gate`, `Turnaround`, `GroundHandler`;
- `MaintenanceTask`, `EngineeringWorkOrder`, `Spare`, `SpareMovement`,
  `ApprovedProvider`;
- `PassengerCohort`, `Connection`, `AccessibilityNeed`, `CareObligation`;
- `Disruption`, `Constraint`, `RecoveryOption`, `Decision`, `TypedCommand`,
  `Evaluation`.

Required relationships include:

- a sector uses one eligible aircraft and one legal crew duty;
- sectors form a rotation, and delay propagates through that rotation;
- a sector holds a slot and requires a compatible stand and turnaround;
- a crew duty covers sectors subject to qualification and remaining duty margin;
- passenger cohorts connect between sectors and inherit disruption impact;
- an aircraft technical status constrains eligibility for future sectors;
- maintenance work consumes approved capability, time, and traceable spares;
- recovery options cite the exact evidence versions used to establish
  feasibility;
- a decision authorises one bounded command family;
- an evaluation compares the resulting world with the pre-action baseline.

### 6.4 Synthetic demo scale

The deterministic demo world uses:

- 1 synthetic hub and 4 synthetic outstations;
- 5 synthetic aircraft, including one operational reserve;
- 8 sectors across 4 rotations in one morning bank;
- 5 active crew duties and one reserve crew;
- 8 coordinated slots, 5 stands, and associated turnaround milestones;
- 2 connection cohorts, including one cohort requiring additional assistance;
- a compact engineering inventory with one locally available spare and one
  repositionable spare;
- fixed-seed event timing and costs.

These numbers are demo-shaping assumptions, not claims about a real carrier.
The scale is large enough to show a cascade but small enough for a seller to
explain every decision.

### 6.5 World invariants

The world fails closed when a proposed action would:

- assign an ineligible or technically unavailable aircraft;
- create overlapping aircraft use;
- assign a crew without required qualification or legal duty margin;
- use an unavailable slot, stand, or turnaround capacity;
- consume an unavailable or untraceable spare;
- exceed the approving persona's action or value authority;
- act on stale evidence or an already resolved disruption;
- reuse an idempotency key for a different payload;
- claim a world mutation while the world is unavailable.

Reset returns the same canonical source state, event sequence, scenario IDs, and
synthetic values for a given scale and seed.

## 7. Process portfolio

### 7.1 Hero workflows

| Workflow type | Priority | Owning function | Trigger | Terminal operational outcome |
|---|---|---|---|---|
| `integrated-hub-disruption-recovery` | Golden hero | Operations Control | Inbound technical delay plus stand constraint threatens a hub bank | Approved feasible recovery actions applied; rotation, crew, slots, stands, and connection impacts evaluated |
| `aog-engineering-recovery` | Hero 2 | Engineering and Maintenance | Aircraft-on-ground event threatens one or more sectors and a suitable spare or approved repair path is constrained | Approved work, spares, substitution, or schedule actions applied; technical release remains external and human-certified |
| `preemptive-schedule-resilience` | Hero 3 | Network Planning | Forecast airport, airspace, weather, crew, or ground-capacity restriction threatens schedule deliverability | Approved pre-emptive schedule intervention applied before a live cascade; stability and customer impact evaluated |

Each hero requires a distinct sensor, objective, phase sequence, typed command
schema, authority action, named world case, projection, recording, and success
evidence. Sharing infrastructure does not permit sharing proof.

### 7.2 Supporting process breadth

The reviewed process library contains these supporting candidates:

| Process | Function | Purpose | First-release position |
|---|---|---|---|
| Aircraft rotation recovery | Operations Control | Resolve propagated aircraft delay or mispositioning | Sub-process of golden hero |
| Crew legality and reassignment | Operations Control | Find qualified, legal crew or reserve coverage | Sub-process of golden hero |
| Turnaround and stand recovery | Operations Control | Replan compatible stands and ground milestones | Sub-process of golden hero |
| Passenger-impact and rights triage | Customer Operations | Classify connection, care, accessibility, rerouting, and review needs | Supporting workflow after heroes |
| Maintenance work and spares coordination | Engineering and Maintenance | Coordinate approved work, provider capability, parts, and logistics | Core of hero 2 |
| Slot-compliance intervention | Network Planning | Evaluate retiming, cancellation, or slot consequences | Core of hero 3 |
| Operational performance review | Operations leadership | Compare disruption outcomes, repeat causes, and recovery effectiveness | Later deterministic review process |

These processes may share read-only evidence services or deterministic
constraint evaluators. They may not collapse into one generic "airline
exception" workflow.

## 8. Hero 1: Integrated Hub Disruption Recovery

### 8.1 Causal story

The healthy synthetic morning bank has feasible aircraft rotations, legal crew
duties, allocated slots and stands, and protected connection margins. A
technical delay affects an inbound sector while an independent stand constraint
removes its expected arrival position. The combined event:

1. delays the next sector in the aircraft rotation;
2. reduces the assigned crew's remaining duty margin;
3. creates a slot and stand conflict for the outbound wave;
4. threatens passenger-connection cohorts;
5. increases cancellation and care exposure if no action is taken.

The sensor registers one integrated objective rather than launching
uncoordinated aircraft, crew, stand, and customer workflows. The recovery
decision evaluates the whole bank.

### 8.2 Phase truth modes

1. **Detect Hub Disruption** (`deterministic`) validates source events,
   correlates the shared cascade, and snapshots evidence versions.
2. **Assess Network Impact** (`agent`) explains affected rotations, crew,
   slots, stands, and cohorts from typed evidence. It may not change
   feasibility or policy facts.
3. **Synthesize Recovery Options** (`agent`) ranks only options admitted by
   deterministic constraint checks and explains trade-offs and uncertainty.
4. **Approve Recovery Plan** (`hitl`) requires the Duty Operations Manager for
   a material combined intervention.
5. **Commit Recovery Actions** (`deterministic`) validates authority and
   idempotency, then issues the selected typed command.
6. **Verify Recovery Outcome** (`deterministic`) compares pre-action,
   post-action, and no-action counterfactual metrics.

### 8.3 Approved action family

The recovery plan may combine:

- swap an eligible aircraft between synthetic sectors;
- re-time a sector within available operational constraints;
- activate a qualified legal reserve crew;
- reassign a compatible stand;
- cancel a sector when no safe and legal recovery exists;
- initiate passenger-impact and care actions for affected cohorts.

Vulnerable-passenger or disputed-entitlement exceptions are handed to the
Customer Operations Lead's supporting workflow; the Duty Operations Manager's
approval does not absorb that separate authority.

One approved plan carries one bounded synthetic cost and an explicit list of
actions. Partial application fails visibly; it must not produce a success-shaped
evaluation.

### 8.4 Success measures

- cancellations avoided compared with no action;
- departure-zero and departure-within-fifteen-minute recovery;
- minimum remaining crew-duty margin;
- resolved slot and stand conflicts;
- protected connection cohorts;
- passengers requiring rerouting, care, or human review;
- synthetic recovery cost;
- time from scenario trigger to first visible event and terminal outcome.

## 9. Hero 2: AOG Engineering and Spares Recovery

### 9.1 Causal story

A synthetic defect grounds an aircraft before its next sector. The aircraft
cannot be scheduled while grounded. The event threatens the downstream
rotation, and recovery depends on approved maintenance capability, task
duration, spares availability and traceability, logistics lead time, substitute
aircraft eligibility, crew consequences, and passenger impact.

The workflow may coordinate work and operational recovery. It cannot diagnose
beyond provided technical evidence, approve an unsupported repair, defer a
defect, or release an aircraft to service.

### 9.2 Phase truth modes

1. **Detect AOG Event** (`deterministic`) validates technical-status and
   schedule-impact evidence.
2. **Check Airworthiness Constraints** (`deterministic`) applies declared
   eligibility, provider, task, and parts constraints.
3. **Synthesize Engineering Recovery Options** (`agent`) compares admitted
   work, spares, logistics, substitution, and schedule options.
4. **Approve Engineering Recovery** (`hitl`) requires the Engineering Duty
   Manager for material work, spares, provider, or operational substitution.
5. **Commit Engineering and Operational Actions** (`deterministic`) creates
   approved work, spares movement, and schedule actions.
6. **Verify Recovery State** (`deterministic`) measures operational recovery
   and waits for an external certified return-to-service event when applicable.

### 9.3 Approved action family

- create an engineering work order using declared approved capability;
- reserve or reposition a traceable spare;
- request an approved external provider;
- substitute an eligible serviceable aircraft;
- re-time or cancel affected sectors;
- register the external certified return-to-service event.

The final action is evidence ingestion, not AI certification.

### 9.4 Success measures

- sectors protected or restored;
- AOG elapsed time and projected time reduction;
- spare availability and logistics lead time;
- work-order status and approved-provider coverage;
- passenger cohorts protected or routed to care;
- synthetic engineering and operational recovery cost;
- explicit proof that no AI phase released the aircraft.

## 10. Hero 3: Pre-emptive Schedule Resilience

### 10.1 Causal story

A forecast synthetic restriction reduces expected hub, airspace, crew, or
ground capacity for a future operating window. The published schedule is still
feasible under nominal assumptions but has insufficient resilience under the
forecast restriction. Waiting would create a larger live cascade.

The workflow compares bounded interventions before the day of operation. It
must distinguish evidence-backed risk from uncertainty and preserve a
no-action option.

### 10.2 Phase truth modes

1. **Detect Schedule Risk Signal** (`deterministic`) validates forecast source,
   horizon, confidence, and affected schedule window.
2. **Assess Network Ripple Effects** (`agent`) explains likely propagation and
   identifies evidence gaps.
3. **Synthesize Resilience Options** (`agent`) ranks deterministically feasible
   interventions and includes no action.
4. **Approve Schedule Adjustment** (`hitl`) requires the Network Operations
   Director for material publication, cancellation, slot, or spend decisions.
5. **Commit Schedule Adjustment** (`deterministic`) applies the authorised
   typed schedule command.
6. **Verify Network Stability** (`deterministic`) evaluates deliverability and
   customer impact under the same forecast scenario.

### 10.3 Approved action family

- add bounded schedule buffer;
- re-time sectors within available slots and resources;
- swap eligible aircraft or planned rotations;
- pre-position reserve crew or aircraft;
- cancel a limited sector before the operating day;
- retain the schedule unchanged with an explicit monitored-risk decision.

### 10.4 Success measures

- reduction in predicted delay propagation and cancellations;
- restored aircraft, crew, stand, and slot feasibility;
- passenger cohorts notified or protected before travel;
- schedule capacity retained;
- synthetic intervention cost;
- forecast uncertainty and false-positive exposure;
- comparison with the no-action counterfactual.

## 11. Authority and governance

### 11.1 Synthetic authority model

Authority values are explicit demo assumptions. They are not based on a real
airline's delegation policy.

| Persona | Routine authority | Escalates when |
|---|---|---|
| Hub Operations Officer | Prepare and execute reversible actions up to GBP 15,000 when all deterministic constraints pass | Combined intervention, cancellation, reserve activation, protected-cohort exception, or higher value |
| Duty Operations Manager | Approve integrated recovery up to GBP 150,000 | Wider network intervention, unsupported action, stale evidence, or unresolved safety/legality constraint |
| Engineering Controller | Coordinate approved work and spares actions up to GBP 20,000 | Material provider, logistics, substitution, or schedule consequence |
| Engineering Duty Manager | Approve engineering recovery up to GBP 200,000 | Airworthiness uncertainty, unavailable approved capability, or higher value |
| Network Planning Manager | Prepare bounded resilience moves up to GBP 25,000 | Material publication, cancellation, slot surrender, or higher value |
| Network Operations Director | Approve schedule-resilience action up to GBP 300,000 | Enterprise-level decision or unresolved legal, safety, or regulatory issue |
| Customer Operations Lead | Approve care and communication actions up to GBP 10,000 | Vulnerable passenger exception, disputed entitlement, material rerouting, or higher value |

An approval must match persona, action, category, and value. A persona cannot
approve an action outside its declared authority. Unknown actions, missing
evidence, stale versions, and exceeded values fail closed and record the
reason.

### 11.2 Separation of recommendation and decision

The agent that recommends an option is not the approving identity. HITL records
contain:

- approving persona;
- workflow and phase identity;
- selected option and rejected alternatives;
- evidence versions;
- action, category, and value;
- verdict and reason;
- external event name;
- recovery context needed to resume after a missed event or restart.

## 12. Honest AI, deterministic, and HITL boundaries

### 12.1 Agent work

Agent phases may:

- summarize typed operational evidence;
- connect effects across rotations, crew, slots, stands, engineering, and
  passenger cohorts;
- generate and rank candidates admitted by deterministic validators;
- explain trade-offs, uncertainty, and why an option was rejected;
- draft internal and passenger communication for human or deterministic review.

Agent phases must call the canonical agent-session path and persist observed
reasoning and tool evidence. A canned deterministic result cannot be declared
as agent work.

### 12.2 Deterministic work

Deterministic logic owns:

- identity, version, source, and idempotency validation;
- aircraft availability and declared compatibility;
- crew qualification, overlap, and legality;
- slot, stand, gate, turnaround, and schedule conflict checks;
- maintenance status, approved capability, and spares traceability;
- synthetic passenger-rights and accessibility routing rules;
- authority action/category/value checks;
- typed-command execution and world mutation;
- KPI and counterfactual evaluation.

### 12.3 Human decisions

HITL is mandatory for:

- material cancellation or schedule publication;
- exceptional spend;
- reserve-crew or reserve-aircraft activation beyond routine authority;
- slot surrender or material retiming;
- consequential engineering provider, work, spares, or substitution decisions;
- vulnerable-passenger or disputed-entitlement exceptions;
- any case with unresolved safety, legality, airworthiness, or evidence
  uncertainty.

No human approval may convert an infeasible, unsafe, illegal, or
airworthiness-invalid option into a valid command.

## 13. Systems and capability boundaries

The design uses generic system roles, not claims about a named airline's stack:

| System role | Read boundary | Write boundary |
|---|---|---|
| Operations control | Schedule, rotations, disruptions, recovery state | Approved operational recovery actions |
| Crew management | Duties, qualifications, legality, reserves | Approved reassignment or reserve activation |
| Maintenance and airworthiness | Technical status, tasks, providers, spares | Work and logistics coordination; certified release remains external |
| Airport/ground operations | Stand, gate, turnaround, handling milestones | Approved stand and milestone requests |
| Slot/network operations | Slot windows, restrictions, forecast constraints | Approved retiming, cancellation, or monitored-risk action |
| Passenger service | Connection cohorts, accessibility, care indicators | Approved cohort-level care, rerouting, and communication actions |
| Weather/air-traffic feeds | Forecast and live constraints | Read-only |

The first design does not require public vendor names. A future source-backed
stack override may name a vendor only when the airline or vendor has publicly
disclosed the relationship and the source remains current.

## 14. Typed command and mutation contract

Every hero has a distinct command schema. A command includes:

- canonical workflow, objective, disruption, and scenario IDs;
- selected option ID and evidence versions;
- authorised persona and governance decision ID;
- action category and synthetic value;
- idempotency key;
- typed action list;
- expected preconditions;
- expected mutation and evaluation type.

The command handler:

1. validates identity, authority, evidence freshness, and idempotency;
2. re-runs deterministic feasibility checks;
3. rejects the whole command if any mandatory action is invalid;
4. writes entity-store and graph mutations with the same workflow identity;
5. emits success or rejection events;
6. invokes the matching deterministic evaluation.

The three commands must not accept one another's payload shape.

## 15. Seed, reset, and scenario contract

The seed produces a healthy, explainable operation before each scenario.
Scenario activation is explicit; ordinary time progression does not silently
inject a hero event during seller setup.

Each scenario has:

- a stable synthetic ID and label;
- deterministic preconditions;
- a visible source event within one second of activation;
- one primary objective and a bounded set of causal effects;
- a reset-safe event sequence;
- a direct diagnostic trigger that preserves the real sensor input;
- a no-action baseline for evaluation.

Reset clears prior workflow, command, decision, and mutation effects, restores
the canonical source state, rewinds the event journal, and allows a mounted
client to detect and recover from the lower cursor without a page refresh.

## 16. Seller journey

The default seller walk uses the golden hero:

1. **Orient:** Open the synthetic airline world and identify the hub bank,
   aircraft rotations, crew duties, slots, stands, and connection cohorts.
2. **Establish health:** Show that the morning bank is initially feasible and
   the operational KPIs are stable.
3. **Trigger:** Activate `synthetic-hub-cascade`.
4. **Observe causality:** Watch the inbound technical delay and stand
   constraint propagate across rotation, crew, slot, stand, and passenger
   impact.
5. **Inspect intelligence:** Open the workflow and distinguish deterministic
   facts from the agent's ranked options and explanations.
6. **Govern:** Show the Duty Operations Manager approval, authority result,
   selected option, rejected alternatives, and reason.
7. **Execute:** Follow the typed command into the world mutation.
8. **Measure:** Compare post-action D0/D15, cancellations avoided, crew margin,
   connection protection, and synthetic cost with the no-action baseline.
9. **Trace:** Confirm the same workflow identity in World, Workflow API,
   drawer, Memory, Knowledge, AG-UI, graph, and Constellation.
10. **Reset:** Restore the healthy bank without restarting the seller journey.

Hero 2 and hero 3 are shorter follow-on walks:

- AOG demonstrates the hard boundary between AI coordination and certified
  airworthiness release.
- Schedule resilience demonstrates acting before a disruption while preserving
  a transparent no-action choice and forecast uncertainty.

## 17. Proof contract

The design adopts `docs/VERTICAL-PROOF.md` contract version `1.0.0` without
relaxation.

### 17.1 Required causal proof

Each hero must prove:

```text
synthetic actor world
  -> distinct sensor
  -> objective
  -> Durable orchestration
  -> declared deterministic/agent/HITL phases
  -> real authority decision
  -> distinct typed command
  -> world and graph mutation
  -> deterministic evaluation
```

Every HITL path must prove the real governance matrix allows the emitted
action/category/value and that the suspended workflow persists complete
`payload.hitl_context`.

### 17.2 Cross-surface identity

The same workflow ID and terminal result must agree across:

- actor-world event log;
- Workflow API;
- workflow drawer and phase ribbon;
- Memory search;
- Knowledge graph;
- AG-UI lifecycle stream;
- graph projection;
- Constellation.

### 17.3 Distinct hero evidence

Each hero requires its own:

- scenario and trigger;
- workflow profile;
- typed command schema;
- authority action;
- world mutation;
- evaluation;
- recording;
- live and replay detail capture.

Evidence from the golden hero cannot satisfy hero 2 or hero 3.

### 17.4 Resilience and browser gates

Proof must include:

- Functions-disabled behavior with no phantom workflow;
- actor-world-disabled direct diagnostic behavior with no claimed world
  mutation;
- zero browser console errors;
- zero dropped or out-of-order workflow events;
- first visible scenario event within one second;
- mounted-client recovery after backend reset or restart;
- HITL auto-close decision, Durable resume, and terminal state within 15
  seconds;
- clean teardown with no orphan processes;
- full live/replay execution-detail parity.

### 17.5 Readiness claims

- **Build ready:** all applicable machine gates pass.
- **Demo ready:** build-ready evidence plus human seller review of reset,
  pacing, visual quality, and story coherence.
- **Deployed:** a separate approved deployment flow passes preflight and smoke.

The machine proof must leave seller review pending until a human completes it.

## 18. Design acceptance criteria

Phase Design is complete because:

1. the operating-company boundary is explicit and excludes Travel semantics;
2. the public-evidence and synthetic-data boundaries are explicit;
3. the golden flagship and two additional heroes are approved;
4. actor relationships and causal dynamics are defined;
5. process breadth is bounded and prioritised;
6. authority and escalation paths are defined with synthetic values;
7. agent, deterministic, and HITL responsibilities are unambiguous;
8. typed commands and mutation invariants are defined;
9. seed, reset, seller journey, and proof expectations are defined;
10. non-goals prevent scope drift and unsafe automation.

No material business question remains open for Phase Build. Technical
implementation decisions remain subject to the current substrate contracts and
must not weaken this design.

## 19. Public source register

Accessed 2026-07-28.

| ID | Source | Kind | Design use |
|---|---|---|---|
| `iag-ar-2025` | [IAG Annual Report and Accounts 2025](https://www.iairgroup.com/media/ktnlp1jx/iag-annual-report-and-accounts-2025.pdf) | Official annual report | Broad public anchor for group operating performance, transformation, fleet investment, customer outcomes, and risk context |
| `ba-h1-2025` | [British Airways interim management report, six months to June 2025](https://www.iairgroup.com/media/m0wlgjva/british-airways-interim-management-report-for-six-months-to-june-2025.pdf) | Official financial disclosure | Broad public anchor for operating-company performance and resilience themes; no internal process is copied |
| `uk-resilience` | [UK government action to minimise aviation disruption and protect passengers](https://www.gov.uk/guidance/uk-government-action-to-minimise-disruption-in-the-aviation-sector-and-protect-passengers) | Government guidance | Deliverable schedules, collaboration, passenger information and assistance, slot measures, and non-negotiable safety |
| `caa-uk261` | [CAA UK261 compliance programme](https://www.caa.co.uk/air-passengers/travel-problems-and-rights/airline-and-travel-company-problems/enforcement-action/uk261-compliance-programme-into-air-passenger-rights/) | Regulator | Airline obligations during delays, cancellations, denied boarding, and rerouting review |
| `caa-consumer` | [CAA guidance on consumer law for airlines and airports](https://www.caa.co.uk/commercial-industry/airlines/guidance-on-consumer-law-for-airlines-and-airports/) | Regulator | Proactive and flexible disruption response; extraordinary-circumstance decisions remain fact-specific |
| `caa-air-ops` | [CAA Air Operations](https://cbo.caa.co.uk/uk-regulations/aviation-safety/basic-regulation-the-implementing-rules-and-uk-caa-amc-gm-cs/air-operations/) | Regulator | Public regulatory anchor for air-operations and crew boundaries |
| `caa-airworthiness` | [CAA Continuing Airworthiness](https://www.caa.co.uk/uk-regulations/aviation-safety/basic-regulation-the-implementing-rules-and-uk-caa-amc-gm-cs/continuing-airworthiness/) | Regulator | Public regulatory anchor for keeping maintenance and return-to-service outside AI authority |
| `eurocontrol-acdm` | [EUROCONTROL Airport Collaborative Decision Making](https://www.eurocontrol.int/concept/airport-collaborative-decision-making) | Intergovernmental operational source | Shared milestone and airport-collaboration reality |
| `iata-supply-chain` | [IATA Aviation Supply Chain](https://www.iata.org/en/programs/ops-infra/techops/aviation-supply-chain/) | Industry association | MRO capacity, spares lead time, approved alternatives, data visibility, and traceability realities |

## 20. Phase boundary

This document completes compose-org Phase Design only. It authorises the
business semantics for a later Phase Build. It does not scaffold a pack, define
an implementation plan, claim that a workflow exists, or provide proof that the
vertical is build ready, demo ready, or deployed.
