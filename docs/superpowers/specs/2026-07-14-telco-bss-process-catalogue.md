# Telco BSS Process Catalogue

**Date:** 2026-07-14
**Status:** Source catalogue for future telco world/process design
**Purpose:** Preserve the candidate BSS processes that complement the OSS
catalogue. This is an input backlog, not a commitment to implement one Zava
domain per row.

## Relationship to the simulator

This catalogue builds on:

- [`2026-07-13-observable-actor-simulator-design.md`](2026-07-13-observable-actor-simulator-design.md)
- [`2026-07-14-autonomous-systemic-simulator-design.md`](2026-07-14-autonomous-systemic-simulator-design.md)
- [`2026-07-10-organisational-world-simulator-design.md`](2026-07-10-organisational-world-simulator-design.md)
- [`2026-07-14-telco-oss-process-catalogue.md`](2026-07-14-telco-oss-process-catalogue.md)

The OSS catalogue focuses on the network and operational control loop. These
BSS processes add customers, accounts, products, orders, bills, payments,
offers, communications and commercial policies to the simulated world. Many
of the strongest scenarios will couple the two catalogues through shared
network-to-customer and service-to-resource maps.

The processes below should therefore be treated as candidate **coupled
vertical slices**. Selection should favour processes that add distinct world
actors, resources, signals, objectives and commands. Closely related rows can
share one scenario model and one responder family rather than becoming
duplicated workflows.

## Common process grammar

Most rows reduce to the same reusable control loop:

```text
trigger
  -> ingest customer, commercial and operational context
  -> detect, predict or interpret the current state
  -> reason about impact, policy, risk and next-best action
  -> pass through a policy/HITL gate where required
  -> execute a bounded account, order, billing or communication action
  -> observe the result and verify the customer or business outcome
```

That shared grammar is deliberate. The differentiation lies primarily in the
world model, decision policy, authority boundary and available commands.

## Working consolidation lens

This grouping is a starting hypothesis, not the final domain architecture.

| Candidate process family | Source rows | Distinctive simulation concern |
|---|---|---|
| Assisted and autonomous customer care | BSS-01, BSS-02, BSS-08, BSS-13 | Intent, confidence, customer vulnerability, resolution and escalation |
| Proactive experience, retention and growth | BSS-03, BSS-04, BSS-05, BSS-14 | Network impact, churn propensity, offer policy, margin and conversion |
| Order, activation and number fulfilment | BSS-06, BSS-07, BSS-16 | Catalogue decomposition, feasibility, scarce resources, fallout and industry SLAs |
| Revenue assurance and collections | BSS-09, BSS-10 | Usage-to-cash reconciliation, financial controls, payment risk and fair treatment |
| Identity, onboarding and fraud prevention | BSS-11, BSS-12 | Identity evidence, behavioural risk, false positives and regulated decisions |
| Roaming experience and steering | BSS-15 | Partner quality, commercial agreements, steering and customer experience |
| Customer experience modelling | BSS-17 | Journey simulation, network experience, behavioural response and change impact |

## Source catalogue

### BSS-01 - Contact-centre agent assist (copilot)

- **Sub-domain:** Customer Care.
- **Business outcome:** Provide a real-time agent copilot that surfaces network
  context, knowledge-base answers and next-best actions.
- **Trigger:** Customer interaction.
- **Twin layer:** Process twin with network context.
- **Key inputs and telemetry:** Call transcript, customer profile, network
  status from the twin and knowledge-base content.
- **Source systems:** CCaaS, CRM, knowledge base and network assurance.
- **Core process:** Understand intent -> pull network and account context ->
  suggest a resolution or next-best action -> draft a response -> log the
  interaction.
- **Decision points:** Resolution path and whether to escalate.
- **HITL gate:** The contact-centre agent stays in control; the workflow is a
  copilot.
- **Outputs and systems of action:** Suggested responses, automatic notes and
  account actions.
- **Agent pattern:** Copilot plus RAG.
- **Target autonomy:** ITU L2 (assist).
- **KPIs:** Average-handle-time reduction, first-contact-resolution
  improvement and CSAT.
- **Data, compliance and risk:** Accuracy and privacy.
- **Automation potential:** High.
- **Twin dependencies:** CRM, knowledge base and network-to-customer map.

### BSS-02 - Autonomous self-service / virtual agent

- **Sub-domain:** Digital Care.
- **Business outcome:** Fully automate resolution for common billing, coverage
  and troubleshooting queries.
- **Trigger:** Customer contact through chat, voice or app.
- **Twin layer:** Process twin with network context.
- **Key inputs and telemetry:** Query, account, network status and device.
- **Source systems:** Digital channels, CRM, network systems and knowledge
  base.
- **Core process:** Understand intent -> diagnose -> resolve through a reset,
  credit or configuration action -> confirm -> hand off if needed.
- **Decision points:** Automatically resolve versus hand off to a human.
- **HITL gate:** Hand off on low confidence, a complaint or a vulnerable
  customer.
- **Outputs and systems of action:** Resolution and account actions.
- **Agent pattern:** Conversational multi-agent system.
- **Target autonomy:** ITU L3.
- **KPIs:** Containment rate, cost-per-contact reduction and CSAT.
- **Data, compliance and risk:** Mis-resolution and vulnerable-customer
  treatment.
- **Automation potential:** High.
- **Twin dependencies:** CRM, network map and knowledge base.

### BSS-03 - Proactive care: network-driven notification and credit

- **Sub-domain:** Proactive CX.
- **Business outcome:** Detect customer-impacting issues, proactively notify
  affected customers and automatically compensate them.
- **Trigger:** Network degradation affecting a customer.
- **Twin layer:** Network and process twins.
- **Key inputs and telemetry:** Network impact from the twin,
  network-to-customer mapping and SLA.
- **Source systems:** Assurance, CRM and billing.
- **Core process:** Identify affected customers -> assess entitlement -> notify
  -> apply credit -> track.
- **Decision points:** Credit eligibility and amount.
- **HITL gate:** Approve credits above the configured threshold.
- **Outputs and systems of action:** Notifications, billing credits and cases.
- **Agent pattern:** Orchestration agent.
- **Target autonomy:** ITU L3.
- **KPIs:** Churn reduction, complaint reduction and NPS.
- **Data, compliance and risk:** Credit governance.
- **Automation potential:** High.
- **Twin dependencies:** Network-to-customer map and billing.

### BSS-04 - Churn prediction and retention orchestration

- **Sub-domain:** Retention.
- **Business outcome:** Predict churn risk and orchestrate personalised
  retention.
- **Trigger:** Risk-score change or contract end.
- **Twin layer:** Process twin with a customer twin.
- **Key inputs and telemetry:** Usage, billing, care, network experience and
  tenure.
- **Source systems:** CRM, billing, experience and campaign platforms.
- **Core process:** Score churn -> identify drivers -> select an offer ->
  execute through a call or digital offer -> track.
- **Decision points:** Offer type, channel and value.
- **HITL gate:** Approve high-value offers.
- **Outputs and systems of action:** Retention offers, campaign actions and
  save actions.
- **Agent pattern:** Predictive plus next-best-action orchestration.
- **Target autonomy:** ITU L3.
- **KPIs:** Churn reduction, save rate and retention ROI.
- **Data, compliance and risk:** Offer margin and fairness.
- **Automation potential:** High.
- **Twin dependencies:** Customer twin and offer engine.

### BSS-05 - Next-best action / personalised offer and upsell

- **Sub-domain:** Marketing / CVM.
- **Business outcome:** Deliver real-time personalised offers and upsell across
  channels.
- **Trigger:** Interaction or lifecycle event.
- **Twin layer:** Process twin.
- **Key inputs and telemetry:** Customer profile, usage, propensity and
  interaction context.
- **Source systems:** CDP/CRM, campaign platform and billing.
- **Core process:** Detect the moment -> score propensity -> select an offer ->
  deliver -> learn.
- **Decision points:** Offer, timing and channel.
- **HITL gate:** Campaign-policy approval.
- **Outputs and systems of action:** Offers and campaign actions.
- **Agent pattern:** Next-best-action multi-agent system.
- **Target autonomy:** ITU L3.
- **KPIs:** ARPU improvement, conversion and uptake.
- **Data, compliance and risk:** Consent and marketing rules.
- **Automation potential:** High.
- **Twin dependencies:** CDP and propensity models.

### BSS-06 - Order management and orchestration (order-to-activate)

- **Sub-domain:** Order Management.
- **Business outcome:** Orchestrate complex orders end to end with exception
  handling.
- **Trigger:** Order placed.
- **Twin layer:** Process twin.
- **Key inputs and telemetry:** Order, product catalogue, inventory and network
  feasibility.
- **Source systems:** Order management, catalogue and OSS provisioning.
- **Core process:** Validate -> decompose -> check feasibility -> orchestrate
  provisioning -> handle exceptions -> confirm.
- **Decision points:** Feasibility and exception handling.
- **HITL gate:** Complex or enterprise exceptions.
- **Outputs and systems of action:** Provisioned service and order status.
- **Agent pattern:** Workflow plus exception agent.
- **Target autonomy:** ITU L3.
- **KPIs:** Order-cycle-time reduction, fallout reduction and right-first-time
  rate.
- **Data, compliance and risk:** Data integrity.
- **Automation potential:** High.
- **Twin dependencies:** Catalogue and OSS feasibility.

### BSS-07 - Service provisioning and activation

- **Sub-domain:** Fulfilment.
- **Business outcome:** Automate service configuration and activation, including
  fallout resolution.
- **Trigger:** Provisioning request.
- **Twin layer:** Network and process twins.
- **Key inputs and telemetry:** Service specification, network resources and
  configuration.
- **Source systems:** Provisioning/activation, OSS and network systems.
- **Core process:** Design -> reserve resources -> configure -> activate ->
  test -> resolve fallout.
- **Decision points:** Resource selection and fallout fix.
- **HITL gate:** Human-on-the-loop for fallout.
- **Outputs and systems of action:** Active service and activation record.
- **Agent pattern:** Workflow plus closed loop.
- **Target autonomy:** ITU L3-L4.
- **KPIs:** Activation time, fallout rate and right-first-time rate.
- **Data, compliance and risk:** Configuration errors.
- **Automation potential:** High.
- **Twin dependencies:** Network twin and provisioning.

### BSS-08 - Billing dispute detection and resolution

- **Sub-domain:** Billing / Care.
- **Business outcome:** Detect billing errors and disputes, investigate them
  and resolve them.
- **Trigger:** Dispute raised or anomaly detected.
- **Twin layer:** Process twin.
- **Key inputs and telemetry:** Bills, usage/CDRs, tariffs and contracts.
- **Source systems:** Billing, mediation and CRM.
- **Core process:** Analyse bill against usage -> find a discrepancy ->
  determine the resolution -> adjust -> notify.
- **Decision points:** Whether the dispute is valid and the adjustment amount.
- **HITL gate:** Approve adjustments above the configured threshold.
- **Outputs and systems of action:** Adjustments and dispute closure.
- **Agent pattern:** Analytical agent.
- **Target autonomy:** ITU L3.
- **KPIs:** Dispute-resolution-time reduction, accuracy and CSAT.
- **Data, compliance and risk:** Revenue impact and fairness.
- **Automation potential:** High.
- **Twin dependencies:** Billing and usage data.

### BSS-09 - Revenue assurance and leakage detection

- **Sub-domain:** Revenue Assurance.
- **Business outcome:** Detect revenue leakage across the usage-to-cash chain.
- **Trigger:** Scheduled run plus anomaly detection.
- **Twin layer:** Process twin.
- **Key inputs and telemetry:** CDRs, mediation, rating, billing and
  provisioning data.
- **Source systems:** Mediation, billing and revenue-assurance tools.
- **Core process:** Reconcile the chain -> detect leakage -> identify root
  cause -> recommend a fix -> track recovery.
- **Decision points:** Leakage severity and whether to fix or monitor.
- **HITL gate:** Approve corrections.
- **Outputs and systems of action:** Leakage cases and recovery actions.
- **Agent pattern:** Analytical multi-agent system.
- **Target autonomy:** ITU L2-L3.
- **KPIs:** Leakage recovered and revenue-assurance coverage.
- **Data, compliance and risk:** Financial controls.
- **Automation potential:** Medium-high.
- **Twin dependencies:** Usage-to-cash data.

### BSS-10 - Collections and dunning optimisation

- **Sub-domain:** Credit and Collections.
- **Business outcome:** Optimise the collections strategy for each customer's
  risk.
- **Trigger:** Overdue balance or risk-score change.
- **Twin layer:** Process twin.
- **Key inputs and telemetry:** Payment history, risk, usage and contact data.
- **Source systems:** Billing, credit and CRM.
- **Core process:** Score risk -> select a strategy -> execute reminders,
  offers or restrictions -> track -> escalate.
- **Decision points:** Strategy, channel, timing and restriction.
- **HITL gate:** Approve service restriction or a legal step.
- **Outputs and systems of action:** Dunning actions and payment plans.
- **Agent pattern:** Optimisation plus orchestration.
- **Target autonomy:** ITU L3.
- **KPIs:** DSO reduction, bad-debt reduction and recovery rate.
- **Data, compliance and risk:** Fair treatment and regulation.
- **Automation potential:** High.
- **Twin dependencies:** Credit models and billing.

### BSS-11 - Fraud detection and prevention

- **Sub-domain:** Fraud Management.
- **Business outcome:** Detect subscription, SIM-swap, roaming and IRSF fraud
  in real time.
- **Trigger:** Transaction or usage event.
- **Twin layer:** Process twin.
- **Key inputs and telemetry:** CDRs, provisioning, device, behaviour and
  threat intelligence.
- **Source systems:** Fraud systems, billing and CRM.
- **Core process:** Monitor -> detect an anomaly -> score -> block or hold ->
  investigate -> feed back.
- **Decision points:** Fraud probability and whether to block or review.
- **HITL gate:** Analyst review of borderline cases.
- **Outputs and systems of action:** Blocks, holds, cases and SIM actions.
- **Agent pattern:** Real-time detection plus agent.
- **Target autonomy:** ITU L3-L4.
- **KPIs:** Fraud-loss reduction, detection rate and false-positive reduction.
- **Data, compliance and risk:** Customer friction and false positives.
- **Automation potential:** High.
- **Twin dependencies:** Behaviour models and threat intelligence.

### BSS-12 - Customer onboarding and KYC

- **Sub-domain:** Onboarding.
- **Business outcome:** Automate acquisition onboarding, including identity,
  KYC and credit checks.
- **Trigger:** New customer application.
- **Twin layer:** Process twin.
- **Key inputs and telemetry:** Identity documents, credit data and
  application.
- **Source systems:** CRM, KYC/identity verification and credit bureau.
- **Core process:** Capture -> verify identity -> check credit -> provision ->
  welcome.
- **Decision points:** Approve or decline and assign a risk tier.
- **HITL gate:** Manual review of exceptions.
- **Outputs and systems of action:** Onboarded account and provisioned service.
- **Agent pattern:** Workflow plus verification agent.
- **Target autonomy:** ITU L3.
- **KPIs:** Onboarding-time reduction, fraud reduction and conversion.
- **Data, compliance and risk:** KYC/AML compliance and privacy.
- **Automation potential:** High.
- **Twin dependencies:** Identity and credit services.

### BSS-13 - Complaint and NPS driver analysis (closed loop)

- **Sub-domain:** CX Insight.
- **Business outcome:** Analyse complaint and NPS drivers, route fixes and
  close the loop.
- **Trigger:** Feedback/NPS signal or complaint-volume change.
- **Twin layer:** Process twin.
- **Key inputs and telemetry:** Complaints, NPS, transcripts and network data.
- **Source systems:** CRM, survey, care and assurance.
- **Core process:** Aggregate -> classify drivers -> link to root cause ->
  route a fix -> verify improvement.
- **Decision points:** Driver priority and owner.
- **HITL gate:** Review systemic issues.
- **Outputs and systems of action:** Driver report and improvement tasks.
- **Agent pattern:** Analytical plus routing agent.
- **Target autonomy:** ITU L2.
- **KPIs:** NPS improvement and repeat-complaint reduction.
- **Data, compliance and risk:** Attribution accuracy.
- **Automation potential:** Medium-high.
- **Twin dependencies:** Feedback data and network map.

### BSS-14 - Device lifecycle and upgrade management

- **Sub-domain:** Device / Handset.
- **Business outcome:** Manage the device lifecycle, upgrade eligibility and
  trade-in offers.
- **Trigger:** Eligibility or device event.
- **Twin layer:** Process twin.
- **Key inputs and telemetry:** Device inventory, contract, usage and trade-in
  value.
- **Source systems:** CRM, device catalogue and billing.
- **Core process:** Detect eligibility -> personalise an upgrade -> offer ->
  process trade-in -> provision.
- **Decision points:** Offer and trade-in value.
- **HITL gate:** Policy approval.
- **Outputs and systems of action:** Upgrade offers and orders.
- **Agent pattern:** Next-best action plus workflow.
- **Target autonomy:** ITU L2-L3.
- **KPIs:** Upgrade rate, ARPU and retention.
- **Data, compliance and risk:** Margin.
- **Automation potential:** Medium-high.
- **Twin dependencies:** Device catalogue and propensity models.

### BSS-15 - Roaming experience and steering

- **Sub-domain:** Roaming.
- **Business outcome:** Manage roaming quality, partner steering and cost.
- **Trigger:** Roaming session or cost/quality signal.
- **Twin layer:** Network and process twins.
- **Key inputs and telemetry:** Roaming CDRs, partner QoS and agreements.
- **Source systems:** Roaming platform, billing and partner systems.
- **Core process:** Monitor -> steer to the best partner -> optimise cost ->
  assure QoE -> notify the customer.
- **Decision points:** Partner steering and the cost-versus-quality trade-off.
- **HITL gate:** Commercial policy.
- **Outputs and systems of action:** Steering configuration and cost
  optimisation.
- **Agent pattern:** Closed loop plus optimisation.
- **Target autonomy:** ITU L3.
- **KPIs:** Roaming-cost reduction, QoE and revenue.
- **Data, compliance and risk:** Partner agreements.
- **Automation potential:** Medium-high.
- **Twin dependencies:** Partner QoS and agreements.

### BSS-16 - Number / SIM management and porting

- **Sub-domain:** Number Management.
- **Business outcome:** Automate mobile number porting and number/SIM
  provisioning.
- **Trigger:** Port request or SIM order.
- **Twin layer:** Process twin.
- **Key inputs and telemetry:** Port request, number inventory and validation
  data.
- **Source systems:** Number management, provisioning and industry porting.
- **Core process:** Validate -> coordinate the port -> provision -> activate ->
  confirm.
- **Decision points:** Validation and exceptions.
- **HITL gate:** Exception handling.
- **Outputs and systems of action:** Ported and active number.
- **Agent pattern:** Workflow agent.
- **Target autonomy:** ITU L3.
- **KPIs:** Port-time reduction and failure reduction.
- **Data, compliance and risk:** Industry SLAs and errors.
- **Automation potential:** High.
- **Twin dependencies:** Number inventory.

### BSS-17 - Customer experience twin / CX simulation

- **Sub-domain:** CX Modelling.
- **Business outcome:** Model individual or segment experience and simulate the
  CX impact of changes.
- **Trigger:** Planning activity or change proposal.
- **Twin layer:** Customer and network twins.
- **Key inputs and telemetry:** Journey data, network experience and behaviour.
- **Source systems:** CDP, assurance and digital twin.
- **Core process:** Build the experience twin -> simulate change impact ->
  predict CX and churn -> recommend.
- **Decision points:** Whether the change is worthwhile and which segment to
  target.
- **HITL gate:** Strategy review.
- **Outputs and systems of action:** CX impact analysis and recommendations.
- **Agent pattern:** Simulation plus analytics.
- **Target autonomy:** ITU L2.
- **KPIs:** NPS, predicted churn and decision quality.
- **Data, compliance and risk:** Model validity and privacy.
- **Automation potential:** Medium.
- **Twin dependencies:** Customer twin and network twin.

## Selection questions for later design

Before promoting any family into a simulator pack or live workflow, establish:

1. What new actors, finite resources and causal events does it add?
2. Which existing customer, commercial and network signals can trigger it
   without direct sensor-to-orchestrator wiring?
3. Is it a distinct organisational objective or merely another command
   available to an existing responder?
4. What typed commands can the responder issue, and which authority limits
   constrain them?
5. What observable customer, account or business-state change proves that the
   intervention worked?
6. Which source rows can share the same scenario physics, objective type and
   responder without losing a meaningful decision boundary?
