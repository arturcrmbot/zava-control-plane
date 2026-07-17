# Telco OSS Process Catalogue

**Date:** 2026-07-14
**Status:** Source catalogue for future telco world/process design
**Purpose:** Preserve the candidate OSS processes that the simulator has been
building toward. This is an input backlog, not a commitment to implement one
Zava domain per row.

## Relationship to the simulator

This catalogue builds on:

- [`2026-07-13-observable-actor-simulator-design.md`](2026-07-13-observable-actor-simulator-design.md)
- [`2026-07-14-autonomous-systemic-simulator-design.md`](2026-07-14-autonomous-systemic-simulator-design.md)
- [`2026-07-10-organisational-world-simulator-design.md`](2026-07-10-organisational-world-simulator-design.md)

The simulator now has a causal telco network loop: explicit cell sites,
subscribers and sessions can produce a network anomaly; a real Durable
responder can issue a typed reroute command; and the resulting site/session
recovery is written back into the simulated world.

The processes below should therefore be treated as candidate **coupled
vertical slices**. Selection should favour processes that add distinct world
actors, resources, signals, objectives and commands. Closely related rows can
share one scenario model and one responder family rather than becoming
duplicated workflows.

## Common process grammar

Most rows reduce to the same reusable control loop:

```text
trigger
  -> ingest telemetry and operational context
  -> detect, predict or simulate in a twin
  -> reason about impact, risk and alternatives
  -> pass through a policy/HITL gate where required
  -> execute a bounded action
  -> observe the result and verify recovery or improvement
```

That shared grammar is deliberate. The differentiation lies primarily in the
world model, decision policy, authority boundary and available commands.

## Working consolidation lens

This grouping is a starting hypothesis, not the final domain architecture.

| Candidate process family | Source rows | Distinctive simulation concern |
|---|---|---|
| Network fault detection, diagnosis and recovery | OSS-02, OSS-13, OSS-15 | Alarm/event cascades, root cause, remediation and verification |
| Predictive asset maintenance and field fulfilment | OSS-01, OSS-09, OSS-10, OSS-11 | Physical degradation, technicians, spares, travel and repair |
| Capacity, rollout and topology planning | OSS-03, OSS-06 | Demand growth, geography, capital allocation and build sequencing |
| Closed-loop network optimisation | OSS-04, OSS-08, OSS-12, OSS-17 | Continuous KPI trade-offs under coverage, energy, latency and spectrum constraints |
| Change and release safety | OSS-05, OSS-16 | Twin validation, canaries, approval, rollout and rollback |
| Slice and SLA orchestration | OSS-07 | Intent translation, resource isolation and adaptive allocation |
| Customer-impact prevention and communication | OSS-14, OSS-20 | Network-to-customer mapping, proactive mitigation and communications |
| Network security response | OSS-18 | Adversarial traffic, false positives and bounded mitigation |
| Experience benchmarking | OSS-19 | Measurement campaigns, representativeness and optimisation feedback |

## Zava executable process map

Every source row has an independently triggerable workflow. Hero workflows keep
bespoke simulation/UI; standard workflows run through the shared profile
substrate and generic process-case view.

| Source | Workflow type | Fidelity | Engine | Skills | MCP packs |
|---|---|---|---|---|---|
| OSS-01 | `predictive-site-maintenance` | hero | hero | site failure diagnosis | network, operations |
| OSS-02 | `network-incident` | hero | hero | deterministic remediation | network |
| OSS-03 | `ran-capacity-planning` | standard | FSP | evidence, risk, scenario, action | network, twin |
| OSS-04 | `capacity-optimization` | hero | hero | capacity action planning | network, twin |
| OSS-05 | `network-configuration-validation` | standard | RIG | evidence, risk, scenario, exception | network, operations, twin |
| OSS-06 | `rollout-site-planning` | standard | FSP | scenario, action, resources | twin, operations |
| OSS-07 | `network-slice-assurance` | standard | OFV | risk, scenario, action, resources | network, twin |
| OSS-08 | `energy-optimization` | standard | DDA | evidence, risk, action | network, twin |
| OSS-09 | `field-repair-dispatch` | hero | hero | field resource matching | operations |
| OSS-10 | `spares-inventory-optimization` | standard | FSP | evidence, resources, action | operations, commercial, twin |
| OSS-11 | `site-asset-health-monitoring` | standard | DDA | evidence, risk, action | network, operations |
| OSS-12 | `backhaul-optimization` | standard | DDA | evidence, risk, action | network, twin |
| OSS-13 | `core-network-anomaly-management` | standard | DDA | evidence, risk, exception | network, operations |
| OSS-14 | `proactive-service-assurance` | standard | DDA | evidence, risk, communication | network, commercial |
| OSS-15 | `service-ticket-resolution` | hero | hero | ticket root-cause correlation | operations, commercial, network |
| OSS-16 | `network-change-release` | standard | RIG | risk, scenario, exception | network, operations, twin |
| OSS-17 | `spectrum-interference-management` | standard | DDA | evidence, risk, action | network, twin |
| OSS-18 | `network-security-response` | standard | RIG | evidence, risk, action | network, operations |
| OSS-19 | `experience-benchmarking` | standard | FSP | evidence, scenario, action | network, twin |
| OSS-20 | `outage-risk-management` | hero | hero | outage risk planning | network, operations, twin |

## Source catalogue

### OSS-01 - Predictive RAN equipment failure prevention

- **Sub-domain:** Network Assurance
- **Business outcome:** Predict RRU/BBU/gNB hardware failures before they
  cause outages and raise pre-emptive work orders.
- **Trigger:** Continuous telemetry stream or anomaly-threshold breach.
- **Twin layer:** Network and asset twins.
- **Key inputs and telemetry:** RRU temperature, VSWR, PA current, output
  power, PM counters (3GPP TS 28.552) and FM alarms (TS 28.532).
- **Source systems:** EMS/NMS, OSS assurance, element managers and a
  time-series telemetry store.
- **Core process:** Ingest telemetry -> detect anomaly in the twin -> estimate
  failure probability (for example, with an LSTM) -> classify severity ->
  create a pre-emptive work order -> schedule a field task.
- **Decision points:** Failure probability versus threshold; equipment
  criticality and customer impact; repair versus replace.
- **HITL gate:** Approve high-cost dispatches or major swaps; automate
  low-risk work.
- **Outputs and systems of action:** Predictive FSM work order, spare
  reservation and engineer dispatch.
- **Agent pattern:** Predictive model plus closed-loop agent.
- **Target autonomy:** ITU L3.
- **KPIs:** Unplanned outage reduction, MTBF improvement, avoided truck rolls
  and availability.
- **Data, compliance and risk:** Safety-critical swaps require sign-off;
  monitor model drift.
- **Automation potential:** High.
- **Twin dependencies:** Network twin, telemetry pipeline and failure model.

### OSS-02 - Autonomous fault management and self-healing

- **Sub-domain:** Service Assurance / NOC
- **Business outcome:** Correlate alarms, identify root cause and
  automatically remediate faults to self-heal the network.
- **Trigger:** Alarm storm or fault event.
- **Twin layer:** Network and process twins.
- **Key inputs and telemetry:** FM alarms, topology and CM data, event logs
  and service KPIs.
- **Source systems:** FM/alarm system, NMS, topology database and ITSM
  (ServiceNow).
- **Core process:** Ingest alarms -> correlate events -> find topology-aware
  root cause -> select remediation -> reconfigure, restart or reroute ->
  verify recovery.
- **Decision points:** Root-cause confidence; automate versus escalate;
  expected blast radius.
- **HITL gate:** Human-on-the-loop, with approval for changes above the
  configured risk tier.
- **Outputs and systems of action:** Closed ticket, configuration change,
  traffic reroute and NOC notification.
- **Agent pattern:** Closed-loop sense-reason-act multi-agent system.
- **Target autonomy:** ITU L3-L4.
- **KPIs:** MTTR reduction, auto-resolution rate, ticket-volume reduction and
  SLA adherence.
- **Data, compliance and risk:** Change control, rollback and a complete audit
  trail.
- **Automation potential:** High.
- **Twin dependencies:** Network topology twin, alarm correlation and
  executable runbooks.

### OSS-03 - RAN capacity planning and traffic forecasting

- **Sub-domain:** Capacity and Planning
- **Business outcome:** Forecast cell/site congestion and recommend capacity
  augmentation or carrier additions.
- **Trigger:** Weekly schedule plus exceptional demand-signal spikes.
- **Twin layer:** Network simulation twin.
- **Key inputs and telemetry:** PRB utilisation, throughput, subscriber
  growth and events calendar.
- **Source systems:** OSS PM, planning tools and geo/demographic datasets.
- **Core process:** Aggregate utilisation -> forecast demand -> simulate
  scenarios -> rank augmentation options -> feed the capital plan.
- **Decision points:** Congestion threshold; spectrum, carrier, small-cell or
  other augmentation; expected ROI.
- **HITL gate:** Planner approves capital-bearing recommendations.
- **Outputs and systems of action:** Capacity plan, augmentation work orders
  and capital proposal.
- **Agent pattern:** Simulation-in-twin plus recommendation agent.
- **Target autonomy:** ITU L2-L3.
- **KPIs:** Congestion-hours reduction, capital efficiency and QoE.
- **Data, compliance and risk:** Forecast accuracy and capital governance.
- **Automation potential:** Medium-high.
- **Twin dependencies:** Network twin and demand-forecast model.

### OSS-04 - RAN optimisation / SON

- **Sub-domain:** Network Optimisation
- **Business outcome:** Continuously tune RF parameters for coverage,
  capacity and handover performance through twin-validated changes.
- **Trigger:** KPI degradation or a scheduled optimisation cycle.
- **Twin layer:** Network and process twins.
- **Key inputs and telemetry:** MDT/MR reports, service KPIs, drive-test data
  and configuration.
- **Source systems:** SON platform, OSS and EMS.
- **Core process:** Detect degradation -> run twin what-if analysis ->
  optimise parameters -> validate in the twin -> push through NETCONF/O1 ->
  monitor.
- **Decision points:** Expected KPI gain versus risk and rollback criteria.
- **HITL gate:** Human-on-the-loop; automate changes within policy guardrails.
- **Outputs and systems of action:** EMS parameter changes and optimisation
  report.
- **Agent pattern:** Closed-loop optimisation.
- **Target autonomy:** ITU L3-L4.
- **KPIs:** Dropped-call rate, throughput, coverage and handover success.
- **Data, compliance and risk:** Explicit guardrails and automatic rollback.
- **Automation potential:** High.
- **Twin dependencies:** Network twin and SON policies.

### OSS-05 - Network configuration change validation

- **Sub-domain:** Change Management
- **Business outcome:** Simulate configuration and software changes before
  production deployment to reduce change risk.
- **Trigger:** Planned change request.
- **Twin layer:** Network twin.
- **Key inputs and telemetry:** Proposed configuration, current CM, topology
  and traffic model.
- **Source systems:** Change management (ServiceNow), CM database and digital
  twin.
- **Core process:** Import change -> simulate impact -> predict KPI changes
  and failures -> recommend approve/reject -> schedule deployment.
- **Decision points:** Predicted regression and go/no-go outcome.
- **HITL gate:** Change Advisory Board approval remains mandatory.
- **Outputs and systems of action:** Validation report and approved/rejected
  change record.
- **Agent pattern:** Simulation plus agent assistance.
- **Target autonomy:** ITU L2-L3.
- **KPIs:** Change-failure reduction, fewer rollbacks and reduced lab time.
- **Data, compliance and risk:** Twin fidelity and formal sign-off.
- **Automation potential:** Medium-high.
- **Twin dependencies:** High-fidelity network twin.

### OSS-06 - 5G / fibre rollout and site planning

- **Sub-domain:** Network Build / Planning
- **Business outcome:** Optimise site selection, coverage design and rollout
  sequencing.
- **Trigger:** Rollout programme or detected coverage gap.
- **Twin layer:** Geospatial/RF network twin.
- **Key inputs and telemetry:** Geospatial, clutter and terrain data; demand
  heatmaps; existing coverage.
- **Source systems:** Planning/GIS, digital twin and propagation models.
- **Core process:** Model coverage -> simulate site options -> optimise rollout
  sequence -> generate design -> feed the build process.
- **Decision points:** Coverage and capacity versus cost; permit constraints.
- **HITL gate:** Planning approval.
- **Outputs and systems of action:** Site design, rollout plan and build work
  orders.
- **Agent pattern:** Simulation plus optimisation agent.
- **Target autonomy:** ITU L2.
- **KPIs:** Coverage, cost per site and time to live.
- **Data, compliance and risk:** Input-data accuracy and permits.
- **Automation potential:** Medium.
- **Twin dependencies:** Geospatial twin and propagation models.

### OSS-07 - Network slicing design and SLA assurance

- **Sub-domain:** 5G Slicing / Service Orchestration
- **Business outcome:** Design, instantiate and assure network slices against
  their SLAs.
- **Trigger:** Slice order or predicted SLA breach.
- **Twin layer:** Network and process twins.
- **Key inputs and telemetry:** Slice intent, SLA parameters and resource
  telemetry.
- **Source systems:** Slice manager/NSSMF, orchestrator and assurance systems.
- **Core process:** Translate intent -> design slice -> simulate ->
  instantiate -> monitor SLA -> automatically adjust resources.
- **Decision points:** Resource allocation and SLA-breach remediation.
- **HITL gate:** Approve commercial slice terms.
- **Outputs and systems of action:** Slice instance, SLA reports and scaling
  actions.
- **Agent pattern:** Intent-based closed loop.
- **Target autonomy:** ITU L3.
- **KPIs:** SLA adherence, slice-provisioning time and utilisation.
- **Data, compliance and risk:** Isolation, security and SLA penalties.
- **Automation potential:** High.
- **Twin dependencies:** Network twin, orchestrator and intent engine.

### OSS-08 - Energy and sustainability optimisation

- **Sub-domain:** Energy / ESG
- **Business outcome:** Reduce network energy consumption through cell sleep,
  carrier shutdown and cooling optimisation.
- **Trigger:** Low-traffic windows or energy-price signals.
- **Twin layer:** Network and process twins.
- **Key inputs and telemetry:** Traffic load, energy consumption, tariffs and
  weather.
- **Source systems:** Energy management, EMS and digital twin.
- **Core process:** Predict low load -> simulate energy saving versus QoE ->
  apply sleep/shutdown action -> verify no SLA impact.
- **Decision points:** Energy saving versus coverage/QoE trade-off.
- **HITL gate:** Human-on-the-loop with policy guardrails.
- **Outputs and systems of action:** EMS energy actions and ESG savings
  report.
- **Agent pattern:** Closed-loop optimisation.
- **Target autonomy:** ITU L3-L4.
- **KPIs:** kWh saved, operating-cost reduction and CO2 reduction. Industry
  reference points in the source material include Verizon at approximately
  $100M/year and Nokia at approximately 29% operating-cost reduction.
- **Data, compliance and risk:** QoE guardrails.
- **Automation potential:** High.
- **Twin dependencies:** Network twin and energy model.

### OSS-09 - Field service dispatch and work-order optimisation

- **Sub-domain:** Field Operations
- **Business outcome:** Optimise technician scheduling, routing and skills
  matching.
- **Trigger:** Work-order creation or an advancing SLA clock.
- **Twin layer:** Process twin plus asset twin.
- **Key inputs and telemetry:** Work orders, technician location and skills,
  parts availability, SLA, traffic and weather.
- **Source systems:** FSM (Dynamics Field Service or ServiceNow), workforce
  system and inventory.
- **Core process:** Prioritise orders -> match skills -> optimise routes ->
  dispatch -> track -> automatically reschedule when conditions change.
- **Decision points:** Priority, SLA risk, skill match and route.
- **HITL gate:** Dispatcher override.
- **Outputs and systems of action:** Optimised schedule, dispatch and customer
  ETA.
- **Agent pattern:** Optimisation plus orchestration agent.
- **Target autonomy:** ITU L3.
- **KPIs:** First-time-fix rate, SLA attainment, travel-time reduction and
  jobs per day.
- **Data, compliance and risk:** Labour/union rules and safety.
- **Automation potential:** High.
- **Twin dependencies:** Asset twin and FSM data.

### OSS-10 - Spares and inventory optimisation

- **Sub-domain:** Supply / Logistics (Network)
- **Business outcome:** Forecast spare demand and optimise stock levels and
  positioning.
- **Trigger:** Failure predictions or stock-threshold breach.
- **Twin layer:** Network and process twins.
- **Key inputs and telemetry:** Failure forecasts, consumption, lead times
  and stock levels.
- **Source systems:** Inventory/ERP, FSM and digital twin.
- **Core process:** Forecast demand -> optimise stock -> automatically
  replenish -> position inventory near predicted hotspots.
- **Decision points:** Reorder point, positioning and asset criticality.
- **HITL gate:** Approve large purchase orders.
- **Outputs and systems of action:** ERP replenishment orders and stock moves.
- **Agent pattern:** Forecast plus action agent.
- **Target autonomy:** ITU L3.
- **KPIs:** Stockout reduction, carrying-cost reduction and availability.
- **Data, compliance and risk:** Supplier constraints.
- **Automation potential:** High.
- **Twin dependencies:** Failure model and inventory data.

### OSS-11 - Tower / site asset health monitoring

- **Sub-domain:** Passive Infrastructure / TowerCo
- **Business outcome:** Monitor structural health, power and environment at
  sites and perform predictive maintenance through an asset twin.
- **Trigger:** Sensor anomaly or inspection schedule.
- **Twin layer:** Physical asset twin.
- **Key inputs and telemetry:** Structural sensors, power/energy,
  environmental readings and drone/LiDAR scans.
- **Source systems:** IoT/SCADA, asset database and GIS.
- **Core process:** Ingest sensor data -> run structural/load analysis in the
  twin -> detect risk -> conduct virtual site survey -> schedule maintenance.
- **Decision points:** Structural risk, safety and maintenance priority.
- **HITL gate:** Safety engineer sign-off.
- **Outputs and systems of action:** Maintenance orders, virtual site survey
  and safety alerts.
- **Agent pattern:** Asset twin plus predictive agent.
- **Target autonomy:** ITU L2-L3.
- **KPIs:** Downtime reduction, avoided site visits and fewer safety
  incidents.
- **Data, compliance and risk:** Structural safety and regulation.
- **Automation potential:** Medium-high.
- **Twin dependencies:** 2D/3D asset twin and IoT telemetry.

### OSS-12 - Transport / backhaul optimisation

- **Sub-domain:** Transport Network
- **Business outcome:** Optimise path, capacity and latency across backhaul
  and transport.
- **Trigger:** Congestion or latency breach.
- **Twin layer:** Network twin.
- **Key inputs and telemetry:** Link utilisation, latency and topology.
- **Source systems:** Transport NMS and digital twin.
- **Core process:** Monitor -> detect congestion -> simulate reroute -> apply
  path change -> verify.
- **Decision points:** Reroute versus augment and latency SLA.
- **HITL gate:** Human-on-the-loop.
- **Outputs and systems of action:** Path changes and capacity plan.
- **Agent pattern:** Closed loop.
- **Target autonomy:** ITU L3.
- **KPIs:** Latency, utilisation and packet loss.
- **Data, compliance and risk:** Service impact.
- **Automation potential:** High.
- **Twin dependencies:** Transport twin.

### OSS-13 - Core network performance and anomaly detection

- **Sub-domain:** Core (5GC/EPC)
- **Business outcome:** Detect anomalies or degradation in core network
  functions and automatically remediate them.
- **Trigger:** KPI anomaly.
- **Twin layer:** Network and process twins.
- **Key inputs and telemetry:** Core KPIs, signalling and logs.
- **Source systems:** Core EMS, observability platform and digital twin.
- **Core process:** Ingest -> detect anomaly -> determine root cause -> scale
  or heal -> verify.
- **Decision points:** Scale versus heal and incident severity.
- **HITL gate:** Human-on-the-loop.
- **Outputs and systems of action:** Scaling/healing actions and incident
  record.
- **Agent pattern:** Closed loop.
- **Target autonomy:** ITU L3.
- **KPIs:** Availability, latency and error rate.
- **Data, compliance and risk:** Core criticality and change control.
- **Automation potential:** High.
- **Twin dependencies:** Core twin and observability.

### OSS-14 - Proactive service assurance and customer-impact prediction

- **Sub-domain:** Service Assurance / CX
- **Business outcome:** Predict customer-impacting degradation and trigger
  pre-emptive remediation and communications.
- **Trigger:** Degradation trend or predicted customer impact.
- **Twin layer:** Network and process twins.
- **Key inputs and telemetry:** Network KPIs, customer/service mapping and
  experience data.
- **Source systems:** Assurance, CRM and digital twin.
- **Core process:** Predict impact -> identify affected customers -> remediate
  -> notify care teams or customers.
- **Decision points:** Impact severity and whether to notify or fix silently.
- **HITL gate:** Communications approval for major events.
- **Outputs and systems of action:** Remediation, proactive notifications and
  care briefing.
- **Agent pattern:** Predictive plus orchestration agent.
- **Target autonomy:** ITU L3.
- **KPIs:** Avoided complaints, NPS and proactive-resolution rate.
- **Data, compliance and risk:** Communication accuracy.
- **Automation potential:** High.
- **Twin dependencies:** Network-to-customer service map.

### OSS-15 - Trouble-ticket triage and auto-resolution

- **Sub-domain:** NOC / Service Desk
- **Business outcome:** Classify, prioritise, correlate and resolve network
  trouble tickets.
- **Trigger:** Ticket creation.
- **Twin layer:** Process twin plus network context.
- **Key inputs and telemetry:** Ticket text, alarms, topology and history.
- **Source systems:** ITSM (ServiceNow), FM and knowledge base.
- **Core process:** Classify -> deduplicate/correlate -> diagnose with RAG and
  twin context -> resolve or route -> close.
- **Decision points:** Auto-resolve versus escalate and ticket category.
- **HITL gate:** Escalation to L2/L3.
- **Outputs and systems of action:** Resolved ticket, routing and knowledge
  base update.
- **Agent pattern:** Multi-agent plus RAG.
- **Target autonomy:** ITU L3.
- **KPIs:** Auto-resolution rate, MTTR and backlog reduction.
- **Data, compliance and risk:** Misrouting.
- **Automation potential:** High.
- **Twin dependencies:** Knowledge base, network twin and ticketing.

### OSS-16 - Network change and release orchestration

- **Sub-domain:** Change / Release
- **Business outcome:** Safely orchestrate network software upgrades and
  rollouts.
- **Trigger:** Release schedule.
- **Twin layer:** Network and process twins.
- **Key inputs and telemetry:** Release artefacts, configuration and
  dependency map.
- **Source systems:** CI/CD, orchestrator, CMDB and digital twin.
- **Core process:** Plan -> validate in twin -> canary -> monitor -> roll out
  or roll back.
- **Decision points:** Canary health and proceed versus rollback.
- **HITL gate:** Release approval.
- **Outputs and systems of action:** Deployed release and rollout report.
- **Agent pattern:** Workflow plus closed loop.
- **Target autonomy:** ITU L3.
- **KPIs:** Change-failure rate, rollout time and rollback rate.
- **Data, compliance and risk:** Production impact.
- **Automation potential:** Medium-high.
- **Twin dependencies:** Twin validation and CMDB.

### OSS-17 - Spectrum and interference management

- **Sub-domain:** RF / Spectrum
- **Business outcome:** Detect interference, optimise spectrum use and
  mitigate PIM or external interference sources.
- **Trigger:** Detected interference or KPI drop.
- **Twin layer:** Network twin.
- **Key inputs and telemetry:** RF measurements, spectrum data and MDT.
- **Source systems:** Spectrum tools, OSS and digital twin.
- **Core process:** Detect -> localise source -> simulate mitigation -> apply
  -> verify.
- **Decision points:** Source type and mitigation approach.
- **HITL gate:** Human-on-the-loop.
- **Outputs and systems of action:** Configuration changes or a field task
  when the source is physical.
- **Agent pattern:** Closed-loop diagnostic agent.
- **Target autonomy:** ITU L2-L3.
- **KPIs:** Interference-incident reduction and throughput.
- **Data, compliance and risk:** Regulatory spectrum rules.
- **Automation potential:** Medium-high.
- **Twin dependencies:** RF twin.

### OSS-18 - Network security and threat detection

- **Sub-domain:** Network Security
- **Business outcome:** Detect and mitigate network-layer threats including
  DDoS, SS7/Diameter attacks and signalling storms.
- **Trigger:** Traffic anomaly or threat signature.
- **Twin layer:** Network and process twins.
- **Key inputs and telemetry:** Traffic flows, signalling and threat
  intelligence.
- **Source systems:** Security/SOC systems, network probes and digital twin.
- **Core process:** Detect -> classify -> simulate mitigation -> rate-limit,
  block or reroute -> report.
- **Decision points:** Threat severity and mitigation choice.
- **HITL gate:** SOC approval for major action.
- **Outputs and systems of action:** Mitigation actions and SOC incident.
- **Agent pattern:** Closed loop plus SOC agent.
- **Target autonomy:** ITU L3.
- **KPIs:** Threats blocked, reduced dwell time and availability.
- **Data, compliance and risk:** False positives and lawful requirements.
- **Automation potential:** High.
- **Twin dependencies:** Traffic twin and threat intelligence.

### OSS-19 - Experience benchmarking and drive-test automation

- **Sub-domain:** QoE / Benchmarking
- **Business outcome:** Automate experience benchmarking against competitors
  and internal targets.
- **Trigger:** Schedule or campaign.
- **Twin layer:** Network twin plus crowdsourced observations.
- **Key inputs and telemetry:** Crowdsourced/drive-test data, KPIs and
  competitor data.
- **Source systems:** QoE platforms and digital twin.
- **Core process:** Collect -> model experience -> benchmark -> identify gaps
  -> feed optimisation.
- **Decision points:** Gap priority.
- **HITL gate:** Analyst review.
- **Outputs and systems of action:** Benchmark report and optimisation tasks.
- **Agent pattern:** Analytics agent.
- **Target autonomy:** ITU L2.
- **KPIs:** Experience index and competitive rank.
- **Data, compliance and risk:** Data representativeness.
- **Automation potential:** Medium.
- **Twin dependencies:** Experience twin.

### OSS-20 - Outage prediction and proactive customer communications

- **Sub-domain:** Resilience / CX
- **Business outcome:** Predict outages caused by weather, load or power;
  pre-empt their impact and notify customers.
- **Trigger:** External weather/grid signal or load spike.
- **Twin layer:** Network and process twins.
- **Key inputs and telemetry:** Weather, grid/power, load and topology.
- **Source systems:** External feeds, digital twin and CRM.
- **Core process:** Predict risk -> simulate impact -> pre-stage resources ->
  notify affected customers.
- **Decision points:** Risk level and whether to notify or pre-stage.
- **HITL gate:** Communications approval.
- **Outputs and systems of action:** Resource pre-staging and customer
  notifications.
- **Agent pattern:** Predictive plus orchestration agent.
- **Target autonomy:** ITU L2-L3.
- **KPIs:** Reduced outage impact, fewer complaints and NPS.
- **Data, compliance and risk:** Prediction and communication accuracy.
- **Automation potential:** Medium-high.
- **Twin dependencies:** Network twin and external feeds.

## Selection questions for later design

Before promoting any family into a simulator pack or live workflow, establish:

1. What new actors, finite resources and causal events does it add?
2. Which existing telco world signals can trigger it without direct
   sensor-to-orchestrator wiring?
3. Is it a distinct organisational objective or merely another command
   available to an existing responder?
4. What typed commands can the responder issue, and which authority limits
   constrain them?
5. What observable world-state change proves that the intervention worked?
6. Which source rows can share the same scenario physics, objective type and
   responder without losing a meaningful decision boundary?
