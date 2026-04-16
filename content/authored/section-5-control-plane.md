## 5.1 Why the Control Plane is the product

WPP's brief is explicit: *"Vendors who demonstrate only single-agent, single-session surfaces (Teams chat, Copilot Studio bots, email approval flows) will score 0 on Control Plane criteria. These channels are trigger and response mechanisms, not Control Planes. We require a demonstrated fleet management interface."* The Control Plane is the operator experience where WPP's Business Partners supervise digital labour at the stated 1:20–50 human-to-agent ratio. It is not a chat client, an Adaptive Card in an email, or a notification channel.

WPP's own Apex diagram pack makes the same point in architectural form. Apex Diagram 1 (*"3 Humans x 1 Agent: Chat Surface"*) is drawn as the anti-pattern. Its stated **LIMITATIONS OF CURRENT MODEL** block enumerates:

- No fleet-wide view
- No bulk approval
- No cross-workflow context
- No autonomy adjust at runtime
- Sub-agents must be hand-coded in Studio
- Each human must poll for updates
- Single human cannot govern 20+ concurrent workflows
- It is a notification and point-interaction channel only — not a Control Plane

Apex Diagrams 2, 3, and 4 describe the positive operating model: a Fleet Dashboard with Exception Queue, Autonomy Engine, and Bulk HITL sitting above an orchestration layer; a shared Fleet Dashboard with role-filtered views for multi-operator governance; and aggregated oversight of N parallel instances of a single agent type with per-instance autonomy and per-agency auth scope. Our architecture answers these three diagrams directly. The Control Plane described below is the product, and the operator experience is its primary surface.

## 5.2 Two-layer architecture

The Control Plane has two layers that cover different requirements and are delivered by different components.

**Foundry Control Plane** (existing Microsoft product, GA). Platform-level management: fleet health dashboards, agent inventory, model registry, Guardrails configuration, continuous evaluation, Microsoft Defender for AI Services and Purview integration. This covers WPP Refs 8.1 (model registry), 8.5 (agent registry), 8.14 (observability), and 22.3 (agent lifecycle). It is consumed; it is not custom built.

**Custom Control Plane UI** (React single-page application powered by Fleet Manager agents). The operator experience where WPP's 1:20–50 fleet management requirement is met. Exception-only queue, bulk HITL, autonomy dials, skill amplification, role-based views, cost dashboard, AG-UI dynamic components. This covers WPP Refs 31.1–31.5, 21.1, 10.1, 26.4, and 5.3. No vendor ships this as a product. It is custom build, delivered as a co-creation partnership (see §5.15).

## 5.3 Fleet Manager agents

The Fleet Manager is the intelligence layer between raw telemetry and the operator surface. It is not a pass-through dashboard feed. It is an always-on GHCP SDK Hosted Agent on Azure AI Foundry, domain-scoped (Hiring, Finance, Compliance), that consumes telemetry via Azure Event Grid and reasons over fleet state.

On each incoming signal the Fleet Manager evaluates SLA risk, anomaly patterns, business impact, and cross-workflow context. It composes the exception queue, pre-composes situational summaries for each flagged workflow, and surfaces crystallisation candidates. Its assessments are pushed to the Custom CP UI via Azure SignalR as AG-UI-shaped JSON payloads.

This is agentic governance. Human-eye governance does not scale to a 1:20–50 ratio — an operator cannot manually scan 50 concurrent workflow telemetry streams and identify the three that need intervention. The Fleet Manager performs that triage continuously.

## 5.4 Capability table

| Capability | What it does | WPP Ref |
|---|---|---|
| Fleet Dashboard | Fleet Manager composes workflow-level status, SLA tracking, agency/market/jurisdiction filtering. Fleet Manager assessment, not raw telemetry. | 31.1 |
| Exception-Only Queue | Of N active workflows, the operator sees only the 2–3% needing attention. Prioritised by business impact x confidence x SLA urgency. | 31.2 |
| Instant Situational Awareness | Click any workflow: what happened, why it stopped, what was tried, what the Fleet Manager recommends, available options. Pre-composed. <5 second comprehension target. | 31.3 |
| Bulk HITL | Batch similar decisions (e.g. eight interview schedules, all low-risk). Single approval raises events on all waiting Durable Functions instances simultaneously. | 31.4 |
| Autonomy Dials | Per-workflow, per-phase, per-agent-type threshold adjustment. Writes to Cosmos DB config store. Effect on next phase boundary. Audit-logged. See §5.5 on production hardening. | 21.1 |
| Skill Amplification | Fleet Manager proactively surfaces policy, precedents, recommended approach when operator is uncertain. Grounded via Foundry IQ over WPP corpora. | 31.5 |
| Role-Based Views | HR BP sees hiring. Finance BP sees budget gates. IT Ops sees provisioning. Entra RBAC-filtered. | 10.1 |
| Cost Dashboard | Per-workflow, per-phase, per-model, per-consumer cost attribution. Sourced from OTEL spans and APIM token metrics. | 26.4 |
| AG-UI Dynamic Components | UI consumes AG-UI event streams over SSE emitted by MAF agent executors and Fleet Manager. Dynamic approval forms, charts, wizards per workflow type, no hardcoded UI. APIM-mediated. | 5.3 |

## 5.5 Autonomy dials — the runtime-adjustability question

WPP's brief requires autonomy dials *"adjustable at runtime without redeployment"*. We meet that requirement. Autonomy thresholds are stored in Cosmos DB config documents, scoped per-agent-type, per-workflow, and per-phase. An operator adjusts a dial in the Custom CP UI; the UI writes the new value to Cosmos DB; the next MAF phase reads the new threshold at its conditional-routing node and takes effect at the next phase boundary with no redeployment. Every change is audit-logged with operator identity, timestamp, previous value, and new value.

**We explicitly recommend that runtime adjustment is not enabled on production systems, or is enabled only under tightened governance.** This is sound governance advice that flows from the audit and dual-control principles emphasised elsewhere in the response — not pushback on the requirement. Three options, ordered by preference:

1. **Disable runtime adjustment in production; use change-request workflow.** Threshold changes land via PR into the config repository, promoted through Design -> Preview -> Production via APIOps, with approvals and full Git history. Runtime dials remain fully functional in Development and Staging for operator training and exception tuning.
2. **Runtime adjustment in production with dual-control.** Threshold changes in the production tenant require a second operator's approval recorded in the action ledger before the Cosmos DB write is committed. Pair with tight Conditional Access scoping.
3. **Runtime adjustment in production with PR-gated promotion between environments.** Operator changes a threshold in Staging; an APIOps pipeline raises a PR that, on approval, promotes the config value into Production.

The mechanism is in the platform. The governance posture is a deployment decision per tenant and per workflow.

## 5.6 AG-UI

MAF agent executors and the Fleet Manager emit AG-UI events over Server-Sent Events. The Custom CP UI consumes and renders them as interactive Adaptive Card-style React components: per-workflow approval forms, workflow visualisations, autonomy dial states, charts, and wizards. APIM mediates the SSE stream for authentication, rate limiting, and audit. There is no hardcoded UI per workflow type — the UI is rendered by the agent layer. This addresses WPP §5.3 *"AG-UI or equivalent: Must support"*.

## 5.7 Data sources for the custom UI

The Custom CP UI is a thin render layer over five telemetry and state surfaces:

- **Application Insights REST API** — OTEL spans (traces, token consumption, latency, cost attribution), KQL-based historical dashboards and drill-down.
- **Foundry REST API and Foundry SDK** — agent inventory, model registry, evaluator results (quality, safety, task adherence, tool call accuracy).
- **APIM metrics** — token consumption per model/tool/agent, latency percentiles, error rates, rate limit hits, content safety blocks, cache hit ratio.
- **Cosmos DB REST API** — workflow state store: phase status, action ledger (revocable vs non-revocable entries), approval records, autonomy threshold values, jurisdiction context.
- **Fleet Manager assessments** — AG-UI-shaped payloads pushed over Azure SignalR in real time (SignalR primary, Cosmos DB polling at 30s as fallback).

## 5.8 Cross-references

See §9 (Builder Experiences) for how Copilot Studio and GHCP SDK agents both appear in the Control Plane through the same telemetry contract; §10 (POC demos) for the live demonstrations of fleet management, bulk HITL, and exception-only queue at scale; and §14.3 Appendix C for Control Plane UI wireframes.

## 5.9 Telemetry ingestion pathways

The Control Plane consumes nine telemetry streams, each originating from a different architectural layer or Azure platform service. Each source is mapped to a specific transport mechanism, data points, delivery latency, and downstream consumer.

| Source | Transport | Data Points | Latency | Consumer |
|---|---|---|---|---|
| GHCP SDK sessions (agent executors) | OTEL TracerProvider -> App Insights | Model calls, tool calls, tokens, latency, cost, reasoning chain, skill loaded, structured output | Near real-time (seconds) | Custom CP UI via App Insights REST API (trace drill-down). Fleet Manager receives context via Event Grid when hooks publish state-change events alongside Cosmos DB writes (see Hook 1). |
| MAF workflow graph (executor lifecycle) | OTEL spans -> App Insights | Executor start/complete/fail, phase transitions, fan-out/fan-in, validator pass/fail, conditional routing decisions | Near real-time | Custom CP UI via App Insights REST API (workflow analytics). Fleet Manager receives MAF context via Event Grid (Hook 2). |
| Durable Functions (orchestration envelope) | Dual-path: (1) Azure Event Grid (push); (2) OTEL spans -> App Insights (query) | Workflow started/completed/failed, HITL wait entered, timer escalation fired, checkpoint written, phase boundary crossed | Sub-second (Event Grid); near real-time (App Insights) | Fleet Manager (Event Grid push for real-time reasoning); Custom CP UI (App Insights REST API for historical dashboards, KQL drill-down, SLA tracking) |
| APIM AI Gateway (model + tool governance) | APIM metrics -> App Insights | Token consumption per model/tool/agent, latency percentiles, error rates, rate limit hits, content safety blocks, cache hit ratio | Near real-time | Custom CP UI (Cost Dashboard, SLA views, token cost via App Insights REST API) |
| Cosmos DB (workflow state store) | REST API (queried by CP UI) | Phase status updates, action ledger entries (revocable/non-revocable), approval records, autonomy threshold values, jurisdiction context | On-demand (query) | Custom CP UI (state queries, action ledger drill-down, approval audit). Fleet Manager receives state-change events via Event Grid and queries Cosmos DB on-demand for context enrichment. |
| Foundry Agent Service (agent + model registry) | Foundry REST API (polled) | Agent inventory (list, status, metadata), model registry (deployed models, versions, lifecycle, capabilities) | Polled | Custom CP UI (inventory views, model deployment dashboards) |
| Foundry Evaluations (quality + safety scoring) | Foundry SDK (project-level API, polled) | Evaluator results: quality (coherence, fluency, groundedness, relevance), safety (violence, hate, self-harm), agent-specific (task adherence, tool call accuracy) | Polled (on evaluation completion) | Custom CP UI (evaluator dashboards, quality gates, drift tracking) |
| Content Safety / Guardrail config | Azure ARM Management API (polled) | RAI policy definitions: content filter categories, severity thresholds (per prompt/completion), blocklists, Prompt Shield configuration | Polled (low frequency) | Custom CP UI (guardrail config views, policy audit) |
| Microsoft Defender for AI Services | Defender for Cloud REST API (ARM, polled or alert-triggered) | Security alerts: prompt injection, jailbreak, data leakage, tool misuse, privilege compromise, identity spoofing | Near real-time (alert-triggered via Defender XDR) | Custom CP UI (security dashboard, alert feed); Defender XDR portal (primary SOC surface) |

**Correlation attributes.** A standard set of attributes is propagated across all telemetry surfaces — OTEL spans, Cosmos DB action ledger entries, and Event Grid event payloads: `workflow_id, phase, jurisdiction, model, agent_identity, skill, token_count`. These are set by the GHCP SDK TracerProvider at session creation and included in Event Grid event payloads and Cosmos DB action ledger entries by the hook layer. The Fleet Manager uses them for domain scoping and fleet-level aggregation; the Custom CP UI uses the same attributes for filtering, drill-down, and cost attribution.

## 5.10 Integration hooks

The framework-to-Control-Plane integration is not ad-hoc. It uses three well-defined hook points, each at a different architectural layer. All three write state to Cosmos DB for persistence and CP UI queries, and publish events to Event Grid for real-time Fleet Manager consumption.

**Hook 1 — GHCP SDK session hooks (agent-executor level).** Every GHCP SDK session emits OTEL spans via its configured TracerProvider. The GHCP SDK hook mechanism additionally intercepts tool calls, model calls, and non-revocable action attempts. On each intercepted event the hook writes an action-ledger entry to Cosmos DB classified as revocable or non-revocable, and emits a corresponding OTEL span. On anomaly — for example, a non-revocable action attempted without validator approval — the hook writes a violation entry to the action ledger and publishes a violation event to Event Grid; the Fleet Manager immediately surfaces it in the exception queue. Non-revocable gating blocks the action until explicit approval via HITL or validator executor. **This is the first enforcement boundary — the agent cannot bypass it.**

**Hook 2 — MAF workflow event callbacks (workflow-graph level).** MAF workflows emit executor lifecycle events as OTEL spans: start, complete, fail, pause, resume for each executor node. Validator rejection events are emitted with the rejection reason, the input that was rejected, and the policy that triggered rejection. Rejections are written to the Cosmos DB action ledger and published as Event Grid events; the Fleet Manager composes them into the exception queue with pre-built context: what was attempted, why it was rejected, what acceptance criteria failed. The CP UI queries App Insights for trend analysis and drill-down. MAF phase-boundary spans feed the Fleet Dashboard's workflow progress view.

**Hook 3 — Durable Functions external events (orchestration level), dual-path.** DF orchestrations emit telemetry via two parallel paths.

- *Path 1 — Event Grid (real-time push).* DF publishes lifecycle events to Azure Event Grid: `workflow_started, phase_boundary, hitl_wait_entered, timer_escalation, workflow_completed, workflow_failed`. The Fleet Manager subscribes via an Event Grid Azure Functions trigger. This is the primary real-time signal for fleet situational awareness — the Fleet Manager knows within sub-seconds when any workflow changes state.
- *Path 2 — OTEL spans to App Insights (query/analytics).* DF emits orchestration spans natively to Application Insights with the same correlation attributes. These power historical SLA tracking, KQL alert rules, trace drill-down, and audit. The Custom CP UI queries App Insights REST API for dashboards and historical views.

**Why both paths.** The Fleet Manager needs sub-second push to reason over live fleet state and compose the exception queue in real time. The Custom CP UI needs queryable, indexed telemetry for dashboards, trend analysis, and audit drill-down. Event Grid delivers the first; App Insights delivers the second.

**Capacity.** At 50 concurrent workflows, Event Grid carries approximately 200–500 events per hour and auto-scales transparently at any volume. App Insights scales in ingestion capacity but requires capacity planning: commitment tier selection, adaptive sampling configuration, and daily cap management.

**Cosmos DB is the persistent state store, not a telemetry transport.** Hooks 1–3 write state to Cosmos DB (action ledger, approvals, phase status) and simultaneously publish events to Event Grid. The Fleet Manager consumes Event Grid for real-time reasoning and queries Cosmos DB on-demand for context enrichment. The CP UI queries Cosmos DB directly for state drill-down and approval history.

## 5.11 Fleet Manager internals

The Fleet Manager is a domain-scoped GHCP SDK Hosted Agent that reasons over incoming signals and produces structured assessments.

**Inputs (Event Grid — single push channel).** The Fleet Manager's primary input channel is Azure Event Grid. It reacts to events pushed to it in real time; it does not poll App Insights or subscribe to change feeds. For context enrichment (composing situational summaries that require accumulated workflow history), it queries Cosmos DB on-demand. This keeps the hot path real-time while allowing full context in the exception queue.

- *DF lifecycle events:* workflow started, phase boundary, HITL wait entered, timer escalation, workflow completed, workflow failed. Published natively by Durable Functions.
- *Hook state-change events:* action-ledger entries (attempted actions, violations, rejection reasons), approval records, validator rejections, phase status updates. Published by GHCP SDK hooks and MAF callbacks at the point of Cosmos DB write.
- *Operator config-change events:* autonomy threshold changes, agent block/unblock. Published by the CP UI when it writes enforcement actions to Cosmos DB or APIM.

**Outputs.**

- *Fleet health assessment:* aggregated workflow status, SLA tracking per domain/jurisdiction/agency. *"47 of 50 hiring workflows on track. 3 require attention."*
- *Exception queue:* prioritised by business impact x confidence x SLA urgency. Of N active workflows, the operator sees only the 2–3% needing intervention.
- *Situational context per workflow:* pre-composed for <5 second operator comprehension — what happened, why it stopped, what was tried, what the Fleet Manager recommends, available options. Includes links to OTEL trace spans and action ledger entries.
- *Crystallisation candidates:* patterns across completed workflows suitable for deterministic graduation. *"The CV triage skill has been consistent for 50 workflows — recommend crystallisation to deterministic classifier."*

**Delivery (SignalR push).** Azure SignalR delivers structured JSON payloads to the Custom CP UI in real time. Channels are scoped by domain (hiring, finance, compliance) and role (HR BP, Finance Controller, IT Ops) — operators receive only signals relevant to their scope. Payloads follow the AG-UI pattern (exception cards, approval forms, workflow visualisations, autonomy dial states) and are rendered as interactive components. If the SignalR connection drops, the Custom CP UI falls back to polling the Fleet Manager's assessment store in Cosmos DB at a 30-second interval; no data is lost because assessments are persisted before push.

## 5.12 Enforcement pathways

The Control Plane is a control surface, not a monitoring dashboard. Operator actions flow back into the runtime through defined enforcement channels. Each has a specific mechanism, target, and observable effect.

| Operator Action | Mechanism | Target | Effect |
|---|---|---|---|
| Approve / reject HITL decision | CP UI -> DF `raise_external_event` | DF orchestration instance (by `workflow_id`) | Waiting DF instance resumes from zero-compute state. Approved: next phase fires. Rejected: DF triggers compensating action sequence via action ledger. |
| Bulk approve batch | CP UI -> DF `raise_external_event` (batch) | Multiple DF instances | All waiting instances in the batch resume. Single API call raises events on N instances via Azure Storage queue fan-out. |
| Adjust autonomy dial | CP UI -> Cosmos DB config write | Workflow config store (per-agent-type, per-workflow, or per-phase) | Threshold written. Next MAF phase evaluates the new threshold at its conditional-routing node. Takes effect on next phase boundary — no redeployment. Change audit-logged. |
| Trigger rollback | CP UI -> DF `raise_external_event` (rollback) | DF orchestration instance | DF reads action ledger from Cosmos DB. Identifies revocable steps. Fires compensating actions (reverse API calls) in reverse order. Non-revocable steps flagged for manual resolution. |
| Override model / tool | CP UI -> APIM policy update (via APIOps) | APIM AI Gateway policy | Routing rule updated. Next agent executor invocation uses overridden model/tool. Audit-logged. Requires operator confirmation. |
| Block / unblock agent | CP UI -> Agent 365 API (or API Center) | Agent registry | Agent status set to blocked/active. Blocked agents cannot start new workflows. In-flight workflows routed to exception queue. |

**Bidirectional data-flow summary.** Telemetry flows IN — read-only, high-volume, real-time — via OTEL spans to App Insights and Event Grid events to Fleet Manager. Enforcement flows OUT — write, low-volume, operator-initiated, audit-logged — via DF `raise_external_event`, Cosmos DB writes, and APIM policy updates. The two paths are architecturally separated: the telemetry pipeline cannot be affected by enforcement actions, and enforcement actions produce their own Event Grid events for audit.

## 5.13 Infrastructure topology

The Control Plane infrastructure is a set of stable Azure PaaS resources, provisioned per WPP tenant, that scale independently of agent runtime workloads.

| Component | Role in Control Plane | Provisioning |
|---|---|---|
| Azure SignalR Service | Real-time push channel from Fleet Manager to Custom CP UI. Supports 100K+ concurrent connections. WebSocket-based. | Shared instance, auto-scaled. Domain-scoped channels (hiring, finance, compliance). |
| Azure Event Grid (namespace) | Single event transport to Fleet Manager. Carries DF lifecycle events, GHCP SDK hook events, MAF callback events, operator config-change events. Push-based, sub-second delivery. | Shared namespace with topic-per-domain. Auto-scales transparently with event volume. |
| Fleet Manager Hosted Agents | Always-on GHCP SDK agents that consume telemetry and produce structured assessments. One per domain. | One Foundry Hosted Agent deployment per domain (hiring, finance, compliance). Multiple replicas. **Azure Container Apps is available as GA-today fallback** where Hosted Agent preview constraints apply; functional parity, same MAF + GHCP SDK composition. |
| Application Insights workspace | OTEL span storage. KQL query engine for cost/trace analysis. Alert rules for validator rejections and SLA breaches. | Shared workspace. Role-based access. Requires capacity planning at scale: commitment tier selection, adaptive sampling, daily cap configuration. 90-day hot, 2-year warm, 7–12 year archive tier. |
| Cosmos DB (config + state) | Persistent state store: workflow state, action ledger, autonomy config, approval records. Queried by CP UI for drill-down and audit. Not a telemetry transport — hooks publish to Event Grid separately. | Regional deployment per data residency. Auto-scaled RU throughput. Continuous backup with PITR. |
| Azure Functions (triggers) | Lightweight functions routing Event Grid events to Fleet Manager. | Consumption plan. Zero cost at idle. Scales automatically with event volume. |
| Custom CP UI (React SPA) | Operator-facing fleet management dashboard. Consumes SignalR (Fleet Manager assessments), App Insights REST API (OTEL traces, cost), Cosmos DB REST API (state queries), Foundry REST API (agent inventory), Foundry SDK (evaluator results), ARM API (guardrail config, Defender alerts). | Azure Static Web Apps. CDN-fronted. Regional deployment. |
| Foundry resource + projects | Agent inventory (list, status), model deployments (versions, lifecycle, capabilities), quality and safety scoring (coherence, fluency, groundedness, relevance, violence, hate, task adherence). | Foundry resource (`Microsoft.CognitiveServices/account`, kind `AIServices`) provisioned per WPP tenant/region. Projects as child resources. Model deployments at resource level (PTU or pay-as-you-go). Hosted Agent deployments within projects. Evaluations run as managed compute within projects. |
| Azure AI Content Safety | Content filter policies (RAI policies), blocklists, Prompt Shield configuration. Consumed via ARM Management API. | Configured per Foundry resource. Polled by Custom CP UI for config audit. |
| Microsoft Defender for AI Services | Runtime security alerts: prompt injection, jailbreak, data leakage, tool misuse. GA for Foundry agents. | Enabled at subscription level via Defender for Cloud. Alerts surfaced in Defender XDR and polled by Custom CP UI via ARM Security API. |

**Scaling independence.** Adding concurrent workflows scales the runtime layer (more DF instances, more Hosted Agent replicas, more APIM throughput). It does not change the Control Plane infrastructure topology. Event Grid and SignalR auto-scale transparently. Cosmos DB auto-scales RU throughput. App Insights scales in capacity but requires operational attention as volume grows: commitment tier upgrades, adaptive sampling tuning, daily cap adjustments to balance cost against telemetry completeness. The infrastructure footprint is the same from 50 to 50,000 concurrent workflows — though App Insights configuration must be right-sized for the volume.

## 5.14 Platform plug-in model — framework-agnostic onboarding

When WPP adds a new domain agent (e.g. Legal, Marketing) or integrates a third-party framework (e.g. Copilot Studio bots via Agent 365, WPP Open agents via A2A), the new agent type must fulfil a minimum telemetry contract to appear in the Control Plane. Any agent type that meets three requirements is visible and governable:

1. **OTEL spans** with standard correlation attributes (`workflow_id, phase, agent_identity, model, skill, token_count`) to the shared Application Insights workspace.
2. **Event Grid lifecycle events** (`workflow_started, phase_boundary, workflow_completed`) to the shared Event Grid namespace.
3. **Cosmos DB state writes** using the standard schema (phase status, action ledger entries) to the shared container.

Integration effort by agent type:

| Agent Type | Contract Fulfilment | Integration Effort |
|---|---|---|
| Foundry Hosted Agent (GHCP SDK) | Automatic. GHCP SDK emits OTEL via TracerProvider. DF publishes to Event Grid natively. Cosmos DB writes are part of the standard workflow pattern. | Zero additional work. Deploy and it appears in the Control Plane. |
| Copilot Studio agent (via Agent 365) | Partial automatic. Agent 365 registration makes the agent visible in Foundry Control Plane inventory. For deeper integration (HITL, exception queue), a thin adapter publishes lifecycle events to Event Grid and writes state to Cosmos DB. | Thin Azure Functions adapter per agent type. Standard pattern, reusable template provided. |
| External agent (A2A via APIM) | APIM logs all A2A interactions as OTEL spans automatically. AgentCard registered in API Center for discovery. APIM-generated telemetry provides minimum data points for fleet-level visibility. | AgentCard registration + optional Event Grid webhook for deeper integration. |
| Custom / third-party runtime | Must implement the telemetry contract explicitly: emit OTEL spans, publish Event Grid events, write to Cosmos DB state store. | SDK-agnostic. Any runtime that can emit OTEL and call REST APIs can integrate. Reference adapter provided. |

The Control Plane infrastructure is framework-agnostic. It consumes telemetry via open standards (OTEL, Event Grid, Cosmos DB) and does not require agents to use a specific SDK or runtime. The GHCP SDK path is zero-effort; any agent fulfilling the contract is visible and governable.

## 5.15 Co-creation partnership

*"WPP's Control Plane requirements exceed any out-of-the-box product available today. The 1:20–50 human-to-agent ratio, fleet-level exception surfacing, and intelligent autonomy management represent frontier capabilities that no vendor ships as a product. This is not a product procurement. It is a co-creation partnership."*

| Dimension | What Microsoft Provides | What WPP Provides | Outcome |
|---|---|---|---|
| Platform infrastructure | Event Grid, SignalR, App Insights, Cosmos DB, Foundry Control Plane, APIM — GA, SLA-backed Azure services | Azure tenancy, subscription, data residency requirements | Stable, scalable foundation. Not custom. |
| Custom Control Plane UI | Microsoft Services (CSU/MCS) engineering for React UI, Fleet Manager agent logic, SignalR integration | Domain expertise: what "exception" means in hiring vs finance, operator workflow requirements, UX feedback | Purpose-built fleet management surface co-designed with operators |
| Fleet Manager agents | GHCP SDK agent development, OTEL integration patterns, Event Grid subscription design | Business rules: SLA definitions, escalation policies, exception classification criteria | Domain-scoped intelligence layer encoding WPP's operational knowledge |
| Codebase ownership | Initial build + knowledge transfer | Long-term maintenance, CI/CD, feature evolution | **WPP owns the code. Standard React + Azure PaaS. No proprietary lock-in.** |
| Productisation | Evaluates proven patterns for Foundry Control Plane roadmap (**H2 2027 candidates: exception-only queuing, bulk HITL, autonomy dials**) | Production validation at enterprise scale | WPP gets early access when the platform absorbs the custom build. Microsoft gets pattern validation. |

WPP gets a Control Plane purpose-built for its operating model today, with a clear path to platform-supported capabilities as the market matures. Microsoft gets production validation of frontier fleet management patterns at enterprise scale. See §12 (Commercial & Partnership) for engagement model and §13 (Portability) for exit strategy detailing WPP's ownership of the codebase and substitutability of each Azure PaaS component.
