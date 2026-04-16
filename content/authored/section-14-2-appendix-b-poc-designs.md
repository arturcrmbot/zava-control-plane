# Appendix B — Detailed POC Technical Designs

This appendix elaborates the foundations referenced in sections 10.1 (POC 1) and 10.2 (POC 2), restating the architectural principles, identity and network boundaries, and known constraints that govern both POCs.

## B.1 Principles

### B.1.1 The determinism to agentic spectrum

WPP's processes span a spectrum. Some phases are rule-driven and must be deterministic (three-way PO match, jurisdiction routing, payment file generation, IT provisioning tickets); others require reasoning and judgement over unstructured input (CV triage, voice screening, compliance narrative review). A 12-week hiring process is a sequence of deterministic scaffolding gates with agentic reasoning inside specific steps. The architecture expresses this through three execution layers, each with a different substrate, failure model and cost profile.

### B.1.2 Three-layer execution model

| Layer | Substrate | Role | Determinism |
|-------|-----------|------|-------------|
| 1. Durable envelope | Azure Durable Functions (GA) | One orchestration per workflow. Phase boundaries, HITL waits at zero compute (days/weeks), timer escalation, checkpoint/replay, geo-replicated state. | Fully deterministic, event-sourced replay. |
| 2. Workflow graph | MAF workflows + durable task extension | Each phase as a graph of typed executors with fan-out/fan-in, conditional routing, HITL hooks. Validator executors between agent executors. | Deterministic by default, agentic by exception. |
| 3. Agent executor | GHCP SDK sessions on Foundry Hosted Agents | Invoked from MAF agent nodes. Load skills and MCP tools, reason, call tools through hooks, emit OTEL, exit. | Probabilistic LLM reasoning wrapped by deterministic pre/post hooks. |

A WPP workflow is therefore a Durable Functions orchestration coordinating MAF workflow graphs whose agent nodes invoke GHCP SDK sessions. Durable Functions provides zero-compute long-running durability (the Azure-native equivalent of Temporal for event-sourced state); MAF provides the deterministic graph shape of a phase with HITL and typed data flow; GHCP SDK provides the LLM runtime with hooks, MCP, skills and OTEL.

### B.1.3 Deterministic by default, agentic by exception

Most executors in a MAF workflow are plain Python or C# functions that fetch data, validate, route and emit events. Agent executors are used only where LLM reasoning is genuinely required. Between agent executors, validator executors assert structural and policy constraints before output propagates — the "judge catches executioner" pattern made explicit in the graph rather than delegated to the model. The consequence for governance is that the majority of the graph is literally code. The LLM is contained inside specific executors, wrapped in GHCP SDK hooks (pre/post tool-use), with Foundry Guardrails intercepting at four points, external validators between nodes, and APIM AI Gateway governing every model and tool call. Probabilism is bounded.

### B.1.4 Skill crystallisation — the migration path

Proven patterns move left along the spectrum. A phase that starts as an agent executor producing structured output, validated by a downstream executor and found stable over N completed workflows can be crystallised — promoted from LLM-generated to deterministic code, versioned as a skill in Azure API Center, and swapped into the MAF graph as a plain function executor. The agent executor remains available as an exception fallback. This is how the system becomes cheaper, faster and more predictable as it matures, without re-architecting anything.

### B.1.5 Why GHCP SDK for agent executors

The agentic loop pattern is well understood; the hard part is the runtime around it — session management, skill resolution, MCP client lifecycle, hook interception, OTEL instrumentation, model failover, structured outputs, sub-agent delegation, prompt caching. GHCP SDK is that runtime, MIT-licensed (Python, TypeScript, Go, .NET), battle-tested behind GitHub Copilot at scale. Adopting it inside a MAF agent executor means:

- Scaled, not DIY. The loop, hooks, skills and MCP client are battle-tested at GitHub Copilot scale, not bespoke code WPP maintains.
- Composable governance. Hooks intercept tool calls deterministically; non-revocable actions route to humans without LLM intervention in the send path.
- Open standards native. MCP, A2A and OTEL are first-class, not bolted on.
- Portable. The same SDK code runs on Foundry Hosted Agents, Container Apps, AKS, or local dev. No lock-in.
- Specialisation via skills, not via separate agents. One domain-scoped Hosted Agent (one Entra Agent ID, one tool allow-list, one audit identity) runs many phase-specific executors by loading different SKILL.md files, avoiding the "300 agents to manage" anti-pattern.

Everything else (Foundry, APIM, MAF workflows, Durable Functions, Fleet Managers, Control Plane, IQ products) is the enterprise envelope around these three layers.

---

## B.2 Approach

Azure Durable Functions provides the long-running durable envelope around each workflow. Inside each phase, a MAF workflow graph — wired to Durable Functions via the MAF durable task extension — defines the deterministic execution path, with most nodes as plain functions and agent nodes invoking GHCP SDK sessions on Foundry Hosted Agents. The stack is governed by Fleet Manager agents, grounded by Foundry IQ, Fabric IQ and Work IQ, centrally managed through API Center and APIM AI Gateway, and surfaced through Foundry Control Plane.

### B.2.1 Skills

SKILL.md files define capabilities declaratively; a new capability is a new skill file. Skills are the specialisation mechanism — instead of separate agents for screening, sourcing, compliance and so on, a single domain-scoped Hosted Agent loads different skills per MAF agent executor. Each skill defines its own role, allowed tools, model assignment and governance rules. Skills are also crystallisation artefacts: proven agentic patterns graduate to deterministic code, versioned as skills, and are swapped into the MAF graph as plain-function executors (agent executor kept as exception fallback). Skills are registered in Azure API Center with lifecycle management (Design, Preview, Production, Deprecated) and governed via APIM AI Gateway.

### B.2.2 MCP tools

Enterprise system integrations (Workday, Greenhouse, LinkedIn, ServiceNow, Microsoft Graph, Dataverse) are exposed as MCP servers, governed through APIM AI Gateway with auth, rate limiting and content safety policies. APIM provides a REST-to-MCP gateway that auto-generates MCP tool definitions from OpenAPI specifications, giving WPP IT teams a supported path to expose existing REST APIs without bespoke server work.

### B.2.3 Hooks

GHCP SDK session hooks (onPreToolUse, onPostToolUse) provide operational governance inside each agent session. Non-revocable actions (send email, submit background check, extend offer, execute payment) are intercepted, blocked from immediate execution and routed to the human's PA for approval. After approval, execution is deterministic — no LLM in the send path. Hooks also handle audit logging and per-skill tool allow-listing. They complement MAF validator executors: hooks operate inside the session; validators operate on its typed output.

### B.2.4 Structured outputs

Agent executors produce type-safe, schema-validated results. GHCP SDK skills declare output schemas; MAF executors are typed; APIM validates every response against the declared schema before propagation. Schema violations are rejected at the gateway and surfaced to Fleet Manager.

### B.2.5 AG-UI protocol

Dynamic, agent-rendered UI components are emitted by MAF agent executors as AG-UI events (SSE) and consumed by the custom Control Plane UI. An agent can render a per-workflow approval form, a contextual chart or a multi-step decision wizard without hardcoded UI per workflow type. AG-UI streams are APIM-mediated for auth, rate-limiting and audit.

### B.2.6 Human interaction

Humans interact with their personal agent (PA) through M365 Copilot (Teams, Outlook) via the M365 Agents SDK, and through the Control Plane UI for fleet management. There is always an agentic layer between humans and the system.

---

## B.3 Architecture

### B.3.1 Layers

| Layer | Component | Role |
|-------|-----------|------|
| Fleet Manager | Always-on GHCP SDK Hosted Agent | Consumes telemetry from all workflows. Reasons about fleet health, SLA risk, anomalies. Composes the exception queue and monitors compliance enforcement events. |
| Durable envelope | Azure Durable Functions (GA) | One orchestration per workflow. HITL waits at zero compute for days or weeks, timer escalation, checkpoint/replay, geo-replicated state. |
| Workflow graph | MAF workflow via durable task extension | Deterministic graph of typed executors per phase. Plain functions for data mapping, validation and routing; agent executors where reasoning is required; validator executors between agent executors. Pregel BSP execution, fan-out/fan-in, conditional routing, HITL hooks. |
| Agent executor contents | Ephemeral GHCP SDK sessions | Invoked only from agent executor nodes. Load skills and MCP tools, reason, write state, emit OTEL, exit. |

### B.3.2 Identity and Access

The Entra Agent ID lives on the Hosted Agent container, not on individual sessions. A GHCP SDK session invoked from a MAF agent executor is a unit of work inside that container and uses the container's identity when calling tools. Agent 365 (GA May 2026) provides the lifecycle and policy layer over these identities.

Hosted Agent topology for the POCs:

| Hosted Agent | Entra Agent ID | Tool Access | Hosts Agent Executors For |
|-------------|---------------|-------------|---------------|
| Hiring Agent | hiring-agent@wpp | Greenhouse, LinkedIn, Workday (hiring), Graph, ACS | All hiring agent executors (screening, sourcing, compliance, offer, onboarding) |
| Finance Agent | finance-agent@wpp | Workday (finance), D365 F&O, Maconomy | All P2P agent executors (intake, validation, routing, payment, reconciliation) |
| Fleet Manager | fleet-manager@wpp | Read-only: Foundry Tracing, Event Grid, workflow state store. No downstream tool invocation. | Fleet monitoring, exception composition, compliance oversight |

Each Hosted Agent is domain-scoped and has only the tool access its domain requires. Sessions invoked inside it inherit that scope.

OBO versus app-only: when a MAF workflow is triggered by a human action, the GHCP SDK session can act on-behalf-of that human; audit attributes the decision to them and downstream access uses their delegated permissions. For autonomous phases (for example screening 200 CVs), the session uses the Hosted Agent's app-only identity.

Skill and policy governance: skill promotion (Design to Production) goes through Azure API Center lifecycle gates. API Center integrates with GitHub Actions for SKILL.md sync. Governance changes require PR review and deploy via APIOps CI/CD. Autonomy threshold changes are audit-logged with operator identity.

Per-skill tool allow-list (APIM-enforced): each SKILL.md declares its allowed tools in frontmatter. On skill promotion, the allow-list is compiled into an APIM policy fragment. APIM rejects any tool call from a session loading skill.X to tool.Y if the allow-list does not permit it. Enforcement sits in the gateway, outside the runtime, and cannot be bypassed by the LLM.

### B.3.3 Authorisation and Non-Revocable Actions

Authorisation is layered: identity (who is acting) is resolved by Entra; capability (what tools the session may call) is constrained by skill allow-lists at APIM; reversibility is classified per tool in a version-controlled catalogue. Each MCP tool declares `revocable: true|false`. Non-revocable invocations route through a hook-enforced HITL gate regardless of which skill or workflow invokes them. The catalogue is Git-committed and PR-reviewed.

| Operation | Domain | Enforcement |
|-----------|--------|-------------|
| Send email to external recipient | Hiring, Finance, Onboarding | Hook blocks send; HITL approval via PA |
| Extend offer letter | Hiring | Hook + MAF validator + dual-control |
| Submit payment / release funds (above threshold) | Finance | Hook + MAF validator + dual-control |
| Create ServiceNow JML ticket | IT Ops | Hook + HITL approval |
| Post outbound A2A message to external agent | Multi-domain | Hook + validator; allow-listed destinations only |
| Write to Workday / D365 F&O master data | HR, Finance | Hook + dual-control + audit link to operator |
| Commit compliance attestation | Compliance | Dual-control mandatory |
| Publish content to external channels | Marketing (future) | Hook + HITL |

Revocability is a property of the tool, not of the skill: the same tool is non-revocable regardless of which skill invokes it.

Dual-control: high-risk operations require two operator approvals from two distinct Entra identities in two distinct operator groups. Enforced by Durable Functions — the orchestration does not advance until two distinct raise_event calls arrive from two distinct operators. The second approver cannot be the first. All four-eyes approvals are audit-logged with both identities.

Prompt-injection hardening: tool calls carry skill context (skill ID, version, workflow phase, jurisdiction) as JWT claims issued by the Hosted Agent's managed identity. APIM validates these claims against the skill's declared allow-list and destination. A prompt-injected attempt to call a tool not in the current skill's allow-list is rejected at the gateway — the LLM cannot elevate its own capability.

### B.3.4 Network and Data Boundaries

APIM is the only public edge. Everything behind it — Hosted Agents, Durable Functions, MAF executors, MCP servers, Cosmos DB, Key Vault, AI Search, Log Analytics, Event Grid — is reachable only over Private Endpoints or VNet-integrated paths. Agents have no direct internet access; outbound calls to third-party SaaS traverse Azure Firewall with an FQDN allow-list.

| Boundary | Control | Notes |
|----------|---------|-------|
| Public ingress | Azure Front Door Premium (WAF, DDoS) to APIM Private Endpoint | Single external entry point. WAF blocks OWASP Top-10. Front Door reaches APIM over Private Link; the APIM gateway has no public IP. |
| East/west (agent to model/tool) | APIM AI Gateway as the only addressable endpoint; backends via Private Endpoint | Hosted Agents, Durable Functions workers and MAF executors resolve APIM via Private DNS. Foundry model endpoints, Cosmos DB, Key Vault, AI Search, Log Analytics and Event Grid all sit on private endpoints. |
| Egress (agent to SaaS) | Azure Firewall Premium with FQDN allow-list | Named destinations only: Workday, LinkedIn, Greenhouse, HeyGen, Dynamics 365 SaaS, Okta, Maconomy. Everything else blocked. Egress logs flow to Log Analytics. |
| Compute isolation | Functions VNet integration; Hosted Agents in dedicated subnets; no public IPs on compute | Communication with APIM and data-plane dependencies is over Private DNS only. Subnet NSGs enforce least-privilege flow. |
| Cross-region | Region-pinned deployments per jurisdiction | EU workflows never resolve US-region endpoints. Log Analytics workspaces, Cosmos DB accounts and Hosted Agent pools are regional. Cross-region replication is opt-in per workload for DR only. |
| Residency CI gate | APIOps pipeline validation | PRs registering a non-EU backend against a DE-tagged skill or model fail CI before deployment. Jurisdiction is an enforced boundary, not a runtime hope. |

Data is classified into four categories, each with distinct retention, residency and redaction policy:

| Class | Where it lives | Retention | Residency and redaction |
|-------|---------------|-----------|-----------|
| Workflow state (phase state, action ledger, approvals, candidate/invoice data) | Cosmos DB (hot) to Azure Storage immutable export (cold) | Workflow lifetime + 90 days hot; archive thereafter | Region-pinned; Customer-Managed Keys via Key Vault; per-field sensitivity labels via Purview |
| Model context (prompts, tool calls, reasoning chain in a GHCP SDK session) | In-memory during session; never persisted by default | Ephemeral — discarded at session end | Never crosses region. Foundry Guardrails redact PII at input, output, tool-call and tool-response intervention points before egress |
| Audit ledger (every tool call, model call, enforcement decision, human interaction) | Log Analytics to Azure Storage immutable export | 7 to 12 years, immutable via Storage immutability policies | Regional Log Analytics per jurisdiction. Prompt/response bodies stored with Guardrails PII redaction; reasoning chain stored separately from the action ledger |
| Telemetry (OTEL spans, metrics, cost attribution) | Application Insights | 90 days (configurable to 2 years) | Regional App Insights. Span attributes carry workflow/phase/jurisdiction/model/token counts — no prompt or response bodies |

The reasoning chain is never co-located with the action ledger: a non-revocable action's audit record carries the span ID that produced it, not the model's reasoning tokens. Prompt and response bodies are never stored in Application Insights; they land in Log Analytics only, after Guardrails redaction, and are accessible only to compliance operators via Sentinel with access logging.

### B.3.5 Human Interaction Model

Every human has a personal agent (PA) — a GHCP SDK agent surfaced in M365 Copilot via the M365 Agents SDK. The PA is a capability layered on M365 Copilot, not a replacement: where Copilot 365 entitles the user, the PA is available inside that Copilot experience. No new agent surface, no additional per-user licence beyond WPP's existing Copilot 365 entitlement. The PA knows the human's role, permissions and context; it surfaces information, recommends actions, drafts outputs and triggers workflows on behalf of the human. Humans decide; the PA prepares and executes.

| Surface | How | Who |
|---------|-----|-----|
| M365 Copilot (Teams) | Each user's PA. Understands role context, surfaces information proactively, triggers workflows OBO the user when instructed. | All WPP users |
| Email (Adaptive Cards) | PA composes Adaptive Card with context and recommendation; response routes back through PA. | Finance BP, approvers |
| Control Plane UI | Richer surface for fleet view, bulk approvals and drill-downs. The HR BP's PA is the Fleet Manager. | HR BP, Fleet operators |
| ServiceNow | PA writes provisioning tasks via ServiceNow MCP. | IT Ops |
| Web portal | Custom web surface for external participants. | Candidates |
| Voice | GPT-Realtime as speech-to-speech front end; tool calls to GHCP SDK backend for reasoning. | Candidates (screening) |

### B.3.6 Flow (Hiring Workflow)

The walkthrough below illustrates how the layers compose for a hiring workflow and is the canonical flow referenced from POC 2.

1. The Hiring Manager's PA surfaces a headcount gap from Workday/Dataverse data and offers to kick off the hiring workflow.
2. The Hiring Manager approves. The PA triggers the Durable Functions orchestration, acting OBO the manager.
3. Durable Functions starts the Budget and Job Design phase by invoking the corresponding MAF workflow as a durable activity. The MAF graph runs: a deterministic `fetch_headcount_context` executor pulls Workday/Dataverse data; an `agent_job_design` executor (GHCP SDK with job-design skill) drafts the JD; `validate_jd_schema` asserts structure; `compute_budget_envelope` finalises the numbers. State is emitted back to Durable Functions.
4. Durable Functions detects the budget needs Finance BP approval and issues `wait_for_external_event` (zero compute, preserved across MAF checkpoints via the durable task extension).
5. The Finance BP's PA presents the request in Teams or Adaptive Card with context and recommendation. The Finance BP approves.
6. The PA writes the decision to state and calls `raise_event`. Durable Functions resumes and invokes the next-phase MAF workflow.
7. The HR BP's PA (Fleet Manager) monitors all workflows and proactively surfaces exceptions — for example "2 of your 20 workflows need attention; Workflow-456 has a compliance flag — here's my recommendation."
8. The HR BP acts via Control Plane UI or directly in Teams. The other 18 workflows run autonomously.

---

## B.4 POC 1 Technical Design — Finance Procure-to-Pay

Scope: 30-50 concurrent invoice workflows managed by a Finance Controller via the Control Plane. A Durable Functions orchestration coordinates phase boundaries and HITL waits. Each phase is a MAF workflow graph; most executors are plain functions, with agent executors used only where reasoning is required.

Phases and executor types:

| Phase | Type | Notes |
|-------|------|-------|
| Intake / OCR | Hybrid | Azure Document Intelligence as deterministic executor; `agent_field_extractor` only for low-confidence fields. Validator asserts schema before forwarding. |
| Three-way match | Deterministic | PO, GRN and invoice matching against tolerance rules. No LLM. |
| GL coding and cost centre | Hybrid | `agent_gl_coder` reasons over vendor, description, agency context; validator confirms GL exists and cost centre is active. |
| Routing and approval gate | Deterministic | Threshold-based routing. HITL event raised to Durable Functions; zero-compute wait. |
| Payment file generation | Deterministic | Format-driven code. Non-revocable action: GHCP SDK hook gates execution until a human confirms. |
| Reconciliation | Hybrid | Deterministic bank statement match; `agent_exception_classifier` only for unmatched items. |

MCP integrations: Workday, Dynamics 365 F&O, Maconomy, all governed through APIM AI Gateway.

Grounding: Fabric IQ for cost-centre, agency hierarchy and budget semantics; Foundry IQ for vendor master data, purchasing policy and tax-rule corpora.

The POC demonstrates a deterministic-by-default MAF workflow graph with HITL approval gates; the Finance BP interacting via Adaptive Card in Outlook routed through their PA; bulk approval for batched low-risk items raising events on multiple Durable Functions instances simultaneously; rollback and compensating actions for failed phases; Fleet Manager monitoring 30-50 concurrent workflows with an exception-only Control Plane view; OTEL cost attribution per invoice; Foundry Guardrails inside agent executors and MAF validator executors between agent and non-revocable executors; and Durable Functions replay across restart.

---

## B.5 POC 2 Technical Design — HR Talent Lifecycle

Scope: 15-20 concurrent hiring workflows managed by an HR Business Partner via the Control Plane. Five human participants across four timezones.

Execution shape: the 12-week hiring process is a Durable Functions orchestration with approximately 10 phases. Each phase is a MAF workflow graph — mostly deterministic executors, agent executors where reasoning is genuinely required, validator executors between them. Durable Functions owns the long waits between phases; MAF owns the graph shape within a phase.

Phases and executor types:

| Phase | Type | Notes |
|-------|------|-------|
| Budget and approvals | Deterministic | Threshold routing, Fabric IQ lookups. HITL gate to Finance BP via `wait_for_external_event`. |
| Job design | Hybrid | `agent_jd_drafter` (GHCP SDK + Foundry IQ for comp benchmarking); `validate_jd_completeness` asserts structure. |
| Sourcing | Deterministic | Greenhouse and LinkedIn MCP queries by criteria. No LLM required. |
| CV triage / screening | Agentic with validator | `agent_cv_scorer` reasons over CV; `validate_bias_markers` runs deterministic bias checks and flags to Fleet Manager. Crystallisation target: after N workflows, promote to a deterministic classifier with agent fallback for low-confidence cases. |
| Voice screening | Agentic | GPT-Realtime plus ACS as the executor; structured scoring validator downstream. |
| Interview coordination | Deterministic | Work IQ for timezone/calendar; plain scheduling logic. |
| Compliance (jurisdiction-aware) | Hybrid | `agent_compliance_narrative` for right-to-work and works council interpretation; deterministic rule executors (GDPR consent checklist, EU AI Act classifier); Task Adherence guardrail detects drift from jurisdiction policy. |
| Offer letter | Hybrid | Template-based generation; `agent_personaliser` for narrative sections only. Non-revocable send gated by GHCP SDK hook pending human approval. |
| JML onboarding | Deterministic | ServiceNow ticket creation via MCP. |
| Avatar welcome video | Hybrid | Agent drafts script; HeyGen MCP handles deterministic generation. |

MCP integrations: Greenhouse ATS, LinkedIn Recruiter, Workday (hiring), Microsoft Graph (calendar/email), ServiceNow (IT provisioning), Azure Communication Services (voice), HeyGen (avatar), all governed through APIM AI Gateway.

Grounding: Foundry IQ for jurisdiction-specific employment law (US and DE corpora), GDPR consent guidance, WPP people handbooks; Fabric IQ for headcount, comp bands, agency hierarchy, levelling history (episodic memory of past hires); Work IQ for calendar, timezone, availability and org topology (escalation routing).

Human surfaces: Hiring Manager via M365 Copilot in Teams; Finance BP via email Adaptive Cards; candidate via web portal and voice; IT Ops via ServiceNow; HR BP via Control Plane.

The POC demonstrates all POC 1 capabilities plus: voice screening with structured scoring; CV parsing with the crystallisation pipeline (agent executor to deterministic classifier in API Center); episodic memory from the workflow state store and Fabric IQ (for example recall of past hires levelled too low); A2A interoperability with an external candidate agent governed via APIM; jurisdiction-aware compliance (USA versus Germany enforcement switching via APIM routing, jurisdiction-specific skills, Foundry IQ corpora and Foundry Guardrails); MAF validator executors separating agent judgement from downstream action; autonomy dials (configurable auto-shortlist thresholds); skill amplification (Fleet Manager surfaces policy and precedents via Foundry IQ); process evolution (Fleet Manager proposes crystallisation candidates after completed workflows); synthetic CV evaluation (500 CVs via Foundry Evaluators); avatar onboarding video; and Threadlight knowledge extraction (interview HR SME, produce executable skills).

---

## B.6 Known Constraints

The stack separates a GA foundation from a replaceable agent runtime. The foundation — Azure Durable Functions, APIM AI Gateway, Azure API Center, Cosmos DB, Foundry runtime, MAF v1.0, Entra, Log Analytics, Application Insights — is GA and production-proven. The runtime layer is GHCP SDK today; because skills are SKILL.md files and tools are MCP servers (open standards), the runtime is replaceable without redesigning the stack. If GHCP SDK stalls or WPP later prefers a different runtime, the runtime can be swapped while skills, tools, workflow graphs, governance and data layers remain in place. This is the honest framing of the preview-dependency question.

| Constraint | Impact | Mitigation |
|-----------|--------|-----------|
| GHCP SDK in tech preview | API surface may change. | Core patterns (skills, MCP, hooks) are GA inside GitHub Copilot's production runtime. The SDK is the same code, MIT-licensed. Skills and MCP tools port to any MCP-native runtime without redesign. |
| MAF v1.0 released Oct 2025 | Framework is young. | MAF v1.0 is GA for core runtime and workflows. The durable task extension is productised as the Durable Agent Orchestration pattern. Orchestration patterns (sequential, concurrent, handoff, group chat, Magentic-One) are stable. Fallback: GHCP SDK plus Durable Functions works without MAF. |
| Foundry Hosted Agents: max 5 replicas per deployment (preview); not yet GA | Scaling ceiling and GA timing risk. | Multiple deployments, or fall back to Azure Container Apps (GA) with Foundry telemetry. Container Apps GA is the Phase 0 decision-#4 fallback and runs the same GHCP SDK image. Replica limit expected to increase at Hosted Agents GA. |
| Foundry Guardrails tool call interception (preview) | May not be GA for POC. | GHCP SDK session hooks provide equivalent enforcement at code level. Guardrails are additive. |
| APIM A2A agent governance (preview) | A2A features still maturing. Only required for the POC 2 external candidate agent demo. | HTTP gateway primitives work today. Purpose-built A2A policies are emerging. |
| Skills in Azure API Center (preview) | Skill registry is new; no native Git sync (uses GitHub Actions). | Core skill execution is GHCP SDK native. API Center adds a governance layer. |
| GHCP SDK and Foundry Hosted Agents integration not documented | Hosting adapter needs custom work. | Hosted Agents accept any container image exposing the Responses API protocol. The adapter translates between Responses API and GHCP SDK session management — the primary integration task for the POC. |
| Agent 365 GA: May 2026 | Not yet GA; integration with Foundry Hosted Agents unclear. | Preview. Whether Hosted Agents auto-register or require manual onboarding requires validation. Entra Agent ID (identity layer) is usable independently of Agent 365. Agent 365 natively supports Copilot Studio agents; the Control Plane supports both. |
| Foundry IQ, Fabric IQ, Work IQ in public preview | APIs evolving. | All three are MCP-addressable — direct Azure AI Search, Fabric SQL and Graph API queries remain as fallback. Upgrade path, not a single point of failure. |
| MAI-Voice-1 preview, East US only | No SLA; region-restricted. | Screening calls use GPT-Realtime (GA) as primary. MAI-Voice-1 is additive for TTS quality. |
| MAI-Transcribe-1 | Preview today, GA targeted Q4 2026 (Phase 0.10 verification). | Screening pipelines consume transcription output behind a validator; any regression at GA is absorbed by the MAF validator layer. |
| Copilot Studio on Foundry Hosted Agents | Not supported. | Copilot Studio agents are supported via Agent 365. For this engagement MAF plus skills is recommended; Copilot Studio remains available as the low-code answer if WPP insists, for citizen-developer scenarios. The Control Plane UI supports both Copilot Studio and GHCP SDK agents. |
