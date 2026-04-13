# Technical Response Sections [Scott + Artur]

These sections replace §4–§13 and §16–§17 in the vendor response document. They are grounded in the validated solution architecture. Every product claim is referenced.

---

## 4. Framework Architecture

### 4.1 Microsoft Agent Stack Overview

Our architecture has three tiers, a central governance layer, and a custom Control Plane UI.

**Tier 1 — Fleet Managers**: always-on [GHCP SDK](https://github.com/github/copilot-sdk) Hosted Agents on Azure AI Foundry. Domain-scoped (hiring, finance, compliance). Consume telemetry from all workflows via Azure Event Grid. Reason about fleet health, SLA risk, anomalies. Compose the exception queue for the Control Plane. Push assessments via SignalR.

**Tier 2 — Workflow Orchestration**: [Azure Durable Functions](https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-functions-overview) (GA). One orchestration instance per workflow. Routes events to agentic loops. HITL waits at zero compute (days or weeks). Timer escalation. Parallel fan-out/fan-in. Checkpoint/replay with geo-replicated state in Azure Storage.

**Tier 3 — Agentic Loops**: ephemeral GHCP SDK sessions on [Foundry Hosted Agents](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents). Triggered per workflow phase. Each session loads [skills](https://github.com/github/copilot-sdk/blob/main/docs/features/skills.md) and [MCP tools](https://github.com/github/copilot-sdk/blob/main/docs/features/mcp.md) for the task, reasons about it, writes state to Cosmos DB, emits [OTEL telemetry](https://github.com/github/copilot-sdk/blob/main/docs/observability/opentelemetry.md), and exits.

**Central Governance** sits alongside all three tiers:

- **[Azure API Center](https://learn.microsoft.com/en-us/azure/api-center/key-concepts) + [APIM AI Gateway](https://learn.microsoft.com/en-us/azure/api-management/genai-gateway-capabilities)** (GA): one cohesive control point for everything addressable by an agent — models, MCP tools, A2A agents, skills, and APIs. **API Center** is the unified registry: lifecycle management (Design → Preview → Production → Deprecated), GitHub Actions sync, cross-cloud discovery (Azure / GCP / AWS / on-prem). **APIM AI Gateway** is the runtime: model [load balancing, failover, spillover](https://learn.microsoft.com/en-us/azure/api-management/backends), [token rate limits](https://learn.microsoft.com/en-us/azure/api-management/llm-token-limit-policy), per-team / per-workflow budget control, [semantic caching](https://learn.microsoft.com/en-us/azure/api-management/azure-openai-semantic-cache-lookup-policy), jurisdiction-based routing; [MCP tool governance](https://learn.microsoft.com/en-us/azure/api-management/mcp-server-overview) (auth injection, rate limiting, [content safety](https://learn.microsoft.com/en-us/azure/api-management/llm-content-safety-policy)); [A2A governance](https://learn.microsoft.com/en-us/azure/api-management/agent-to-agent-api) (preview); [REST→MCP auto-generation](https://learn.microsoft.com/en-us/azure/api-management/export-rest-mcp-server). One pane, one policy engine, one audit trail.
- **[Foundry Control Plane](https://learn.microsoft.com/en-us/azure/foundry/control-plane/monitoring-across-fleet)** (GA): [agent fleet inventory](https://learn.microsoft.com/en-us/azure/foundry/control-plane/how-to-manage-agents), [model registry](https://learn.microsoft.com/en-us/azure/foundry/concepts/foundry-models-overview) (1900+ models), [guardrails](https://learn.microsoft.com/en-us/azure/foundry/guardrails/guardrails-overview) (PII, [Task Adherence](https://learn.microsoft.com/en-us/azure/foundry/guardrails/how-to-task-adherence)), [built-in evaluators](https://learn.microsoft.com/en-us/azure/foundry/concepts/built-in-evaluators) (quality, safety, drift).
- **[Agent 365 + Entra](https://learn.microsoft.com/en-us/microsoft-agent-365/overview)** (GA May 2026): [Entra Agent ID](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/what-is-agent-id) (first-class agent identity, not service accounts), [agent registry](https://learn.microsoft.com/en-us/microsoft-365/admin/manage/agent-registry), lifecycle management (activate, block, delete), [Conditional Access](https://learn.microsoft.com/en-us/entra/identity/conditional-access/agent-id), [Purview DLP](https://learn.microsoft.com/en-us/purview/ai-agent-365), [Defender](https://learn.microsoft.com/en-us/azure/defender-for-cloud/ai-threat-protection).

**Intelligence Layer** — agents need three kinds of grounding (enterprise documents, business semantics, work context). Microsoft has a purpose-built product for each. All three are MCP-addressable and sit behind APIM AI Gateway alongside any other tool, governed identically:

- **[Foundry IQ](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/what-is-foundry-iq)** (preview): unified agentic retrieval over enterprise corpora. Self-reflective query planner with configurable retrieval reasoning effort. Federates SharePoint, Fabric, OneLake, Blob, AI Search, web, and MCP behind one permission-aware endpoint. Built on Azure AI Search. Used by Compliance Agent (employment law, GDPR, EU AI Act), Job Design (comp benchmarking), Skill Amplification (Fleet Manager surfacing precedents to operator).
- **[Fabric IQ](https://learn.microsoft.com/en-us/fabric/iq/overview)** (preview): semantic intelligence layer over WPP's Fabric / OneLake estate. Business ontology, semantic model, graph engine for multi-hop reasoning. Used by Budget Agent (headcount, cost-centre, agency hierarchy), ROI reporting, cross-entity matrix navigation.
- **[Work IQ MCP](https://learn.microsoft.com/en-us/microsoft-copilot-studio/use-work-iq)** (preview): M365 work graph + memory layer (collaboration patterns, calendar, expertise). Used by Personal Agents, Interview Coordinator (timezone, availability), Org Topology / Escalation routing.

### 4.2 Agent Framework vs Agent Surfaces

| Layer | What It Is | Components |
|-------|-----------|------------|
| **Framework** | The agentic runtime, orchestration engine, state store, governance, tool integration, knowledge grounding, and observability. | GHCP SDK, Foundry Hosted Agents, Durable Functions, APIM AI Gateway + API Center, Foundry IQ + Fabric IQ + Work IQ (Intelligence Layer), Foundry Control Plane, Agent 365 + Entra, Cosmos DB, Application Insights, Log Analytics |
| **Surfaces** | The channels through which humans interact with agents and agent outputs. | M365 Copilot (Teams), Email (Adaptive Cards), Custom Control Plane UI (React), Web Portal, Voice (ACS + GPT-Realtime), ServiceNow |

A single domain agent (e.g. Hiring Agent) is surface-agnostic. The same agentic loop produces outputs that the human's Personal Agent (PA) delivers to whatever surface that human uses. The PA is a GHCP SDK agent surfaced in M365 Copilot via [M365 Agents SDK](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/publish). Every human has one. Humans make all decisions. The PA prepares and executes.

### 4.3 Control Plane Architecture

Two layers.

**Foundry Control Plane** (existing product, not custom build): fleet health dashboards, agent inventory, model registry, guardrails configuration, continuous evaluation, Defender and Purview integration. This covers WPP Refs 8.1, 8.5, 8.14, 22.3.

**Custom Control Plane UI** (React application powered by Fleet Manager agents): this is where WPP's operator-specific requirements are met. No vendor ships what WPP is asking for — a fleet management interface where 1 human governs 20–50 concurrent workflows with intelligent exception surfacing. This is custom build.

| Capability | What it does | WPP Ref |
|-----------|-------------|---------|
| Fleet Dashboard | Fleet Manager composes workflow-level status, SLA tracking, agency/market/jurisdiction filtering. Not raw telemetry — the Fleet Manager's assessment. | 31.1 |
| Exception-Only Queue | Of N active workflows, the operator sees only the 2–3% needing attention. Fleet Manager composes this based on business impact, confidence, SLA urgency. | 31.2 |
| Instant Situational Awareness | Click any workflow → what happened, why it stopped, what was tried, what the Fleet Manager recommends, options. Pre-composed by Fleet Manager. <5 seconds. | 31.3 |
| Bulk HITL | Batch similar decisions (8 interview schedules, all low-risk). Approve in one action. Raises events on all waiting Durable Functions instances simultaneously. | 31.4 |
| Autonomy Dials | Per-workflow threshold sliders. Writes to config store, effective immediately, audit-logged. | 21.1 |
| Skill Amplification | Fleet Manager proactively surfaces policy, precedents, recommended approach when operator is uncertain. | 31.5 |
| Role-Based Views | HR BP sees hiring. Finance BP sees budget gates. Entra RBAC. | 10.1 |
| Cost Dashboard | Per-workflow cost attribution from OTEL + APIM token metrics. | 26.4 |

Data sources for the custom UI: Application Insights APIs (traces, cost), Foundry REST APIs (agent inventory), APIM metrics (token consumption), workflow state store in Cosmos DB (phase status, approvals, action ledger), Fleet Manager assessments (SignalR real-time).

### 4.4 Multi-Agent Orchestration

We do not use separate agent processes for each specialist role. Instead, skills provide specialisation within a single agentic loop per domain.

A domain-scoped Hosted Agent (e.g. Hiring Agent, `hiring-agent@wpp`) runs ephemeral GHCP SDK sessions that load different skills depending on the workflow phase. Each skill defines its own role, allowed tools, model assignment, and governance rules. The outcome — specialised capabilities with distinct roles and model assignments — matches WPP's requirement for heterogeneous teams. The architectural advantages over separate agents: no inter-agent communication overhead, shared workflow context without message passing, simpler governance (one Entra identity per domain), easier operationalisation at fleet scale.

Durable Functions coordinates phase sequencing. Supported topologies: sequential (interview after screening), parallel fan-out/fan-in (sourcing + job design concurrently), conditional (compliance flag triggers additional review), timer escalation, HITL waits at zero compute. The orchestration adapts based on runtime data — not a static DAG.

---

## 5. Core Capability Mapping

### 5.1 Core Framework Capabilities

| Capability | Solution | Status |
|-----------|---------|--------|
| Multi-agent orchestration | Durable Functions + skills-based specialisation within GHCP SDK agentic loops | GA (Durable Functions), Tech Preview (GHCP SDK) |
| Stateful workflow management | Cosmos DB (workflow state, action ledger) + Durable Functions (orchestration state in Azure Storage) | GA |
| Tool/function integration | MCP servers governed through APIM. REST-to-MCP gateway auto-generates tool definitions from OpenAPI specs. | GA (APIM), [MCP preview](https://learn.microsoft.com/en-us/azure/api-management/export-rest-mcp-server) |
| Connectors | MCP servers for Workday, Greenhouse, LinkedIn, D365 F&O, Maconomy, ServiceNow, MS Graph, ACS, HeyGen — all via APIM | Custom build per connector |
| Human-in-the-loop | GHCP SDK hooks intercept non-revocable actions. Durable Functions `wait_for_external_event` at zero compute. PA surfaces decisions to humans. Agent 365 routes to right person. | GA (Durable Functions), custom (HITL flow) |
| Durable execution | Durable Functions checkpoint/replay. Cosmos DB continuous backup with PITR. Geo-replicated state. | GA |
| Memory | Cosmos DB (facts + episodic), skills (procedural), Foundry IQ (semantic retrieval), Fabric IQ (business ontology), Work IQ (M365 episodic), GHCP SDK session (working) | GA (data stores), Preview (IQ products), custom (memory patterns) |
| Model-agnostic | GHCP SDK works with any model from Foundry catalog (1900+). Per-skill model assignment. APIM routes and governs. | GA |
| Control Plane | Foundry Control Plane (platform) + Custom Control Plane UI (operator experience) | GA (Foundry) + custom build |

### 5.2 Desirable Capabilities

| Capability | Solution | Status |
|-----------|---------|--------|
| Rollback / compensating actions | Action ledger tracks revocable vs non-revocable. Hooks block non-revocable before execution. Durable Functions triggers compensating actions on rollback. | Custom build (proven pattern) |
| Self-healing | Durable Functions [retry with backoff](https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-functions-error-handling). APIM [circuit breakers and model failover](https://learn.microsoft.com/en-us/azure/api-management/backends). Fleet Manager routes exceptions to humans. | GA |
| Multi-surface engagement | PA delivers to Teams, Email, Control Plane UI, ServiceNow, Web, Voice — all from the same agentic loop output | GA (M365 Agents SDK) + custom (Control Plane UI, voice) |
| A2A with off-platform agents | [APIM A2A governance](https://learn.microsoft.com/en-us/azure/api-management/agent-to-agent-api): AgentCards, JSON-RPC, SSE | Preview |
| Evaluation framework | [Foundry Evaluators](https://learn.microsoft.com/en-us/azure/foundry/concepts/built-in-evaluators): task adherence, tool call accuracy, safety, groundedness, sensitive data exposure. Continuous evaluation on production traffic. | GA |
| Workflow crystallisation | Skills graduate from generative (LLM-driven) to deterministic (code). API Center lifecycle gates (Design → Production). Exception fallback to generative. | Custom build |

### 5.3 Advanced Capabilities

| Capability | Solution | Status |
|-----------|---------|--------|
| Voice screening | [GPT-Realtime](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/realtime-audio) (speech-to-speech) + [ACS Call Automation](https://learn.microsoft.com/en-us/azure/communication-services/concepts/call-automation/call-automation). [MAI-Voice-1](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/mai-voices) (TTS, preview). | GA (GPT-Realtime, ACS), Preview (MAI-Voice-1) |
| Avatar onboarding video | Agentic loop generates script. HeyGen API MCP produces branded video. | Custom MCP server |
| Fine-tuning | [Azure AI Foundry fine-tuning](https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/fine-tuning-overview). We prioritise skill crystallisation over model fine-tuning. | GA |
| Knowledge extraction | Threadlight accelerator: creates skills from interviews and unstructured data. | Built, demonstrated |

---

## 6. Governance, Security and Compliance

### 6.1 Agent Identity and Governance

Each Hosted Agent has a dedicated [Entra Agent ID](https://learn.microsoft.com/en-us/entra/agent-id/identity-professional/microsoft-entra-agent-identities-for-ai-agents) — a first-class identity in Entra ID, distinct from service accounts. Domain-scoped:

| Hosted Agent | Entra Agent ID | Tool Access |
|-------------|---------------|-------------|
| Hiring Agent | `hiring-agent@wpp` | Greenhouse, LinkedIn, Workday (hiring), Graph, ACS |
| Finance Agent | `finance-agent@wpp` | Workday (finance), D365 F&O, Maconomy |
| Fleet Manager | `fleet-manager@wpp` | Read-only: telemetry, state store. No downstream tool invocation. |

Identity lives on the container, not on individual sessions. When a human triggers an action, the loop acts [on-behalf-of](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/agent-on-behalf-of-oauth-flow) that human. For autonomous phases, the loop uses the Hosted Agent's app-only identity. Every action is attributed to the correct identity in the audit trail.

Agent 365 provides lifecycle management (activate, block, delete), [Conditional Access for agents](https://learn.microsoft.com/en-us/entra/identity/conditional-access/agent-id), and integration with [Purview](https://learn.microsoft.com/en-us/purview/ai-agent-365) (DLP, audit) and [Defender](https://learn.microsoft.com/en-us/azure/defender-for-cloud/ai-threat-protection) (threat detection).

### 6.2 Observability and OpenTelemetry

Three layers of observability:

1. **[Foundry Tracing](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/trace-agent-setup)**: every agentic loop emits OTEL spans via [GHCP SDK OTEL](https://github.com/github/copilot-sdk/blob/main/docs/observability/opentelemetry.md) TracerProvider. Model calls, tool calls, tokens, latency, cost. Spans carry workflow ID, phase, jurisdiction, model, token count.
2. **APIM metrics**: [token usage](https://learn.microsoft.com/en-us/azure/api-management/llm-emit-token-metric-policy), latency, errors per model/tool/agent. Central cost tracking.
3. **Fleet Manager assessment**: event-driven reasoning over telemetry. Fleet health, anomaly detection, SLA risk, exception prioritisation. This is the default Control Plane view.

Cost attribution is per workflow, per phase, per model, per consumer. Visible in both Foundry dashboards and the custom Control Plane UI.

### 6.3 Data Protection and Compliance

Three enforcement layers. The LLM cannot bypass any of them.

**[Foundry Guardrails](https://learn.microsoft.com/en-us/azure/foundry/guardrails/guardrails-overview)** (preview): intercepts at [four intervention points](https://learn.microsoft.com/en-us/azure/foundry/guardrails/intervention-points) — input, output, tool-call, tool-response. PII detection. [Task Adherence](https://learn.microsoft.com/en-us/azure/foundry/guardrails/how-to-task-adherence) detects policy drift.

**APIM AI Gateway** (GA): jurisdiction-based model routing (DE workflow → EU endpoint only). [Content safety](https://learn.microsoft.com/en-us/azure/api-management/llm-content-safety-policy) policy. Token rate limiting. All MCP tool calls governed.

**Agent 365 + Entra** (GA May 2026): per-agent RBAC on downstream resources. Conditional Access. Purview DLP on agent interactions. Defender for threat detection.

**Policy-as-code**: APIM policies via [APIOps CI/CD](https://learn.microsoft.com/en-us/azure/api-management/devops-api-development-templates). Foundry Guardrails per agent. Jurisdiction-specific skills in SKILL.md files. All Git-committed, PR-reviewable, audit-trailed.

**Jurisdiction switching**: workflow state carries `jurisdiction`. APIM routes to region-appropriate model endpoint. Jurisdiction-specific skills (right-to-work, works council, GDPR consent) load automatically based on workflow context. Adding a new jurisdiction = adding new skill files, not modifying agent code.

**Audit**: [Azure Log Analytics](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/data-retention-archive) with 7–12 year retention. Immutability enforced via Azure Storage export with immutability policies. Every tool call, model call, enforcement decision, and human interaction logged. Queryable via KQL and [Microsoft Sentinel](https://learn.microsoft.com/en-us/azure/sentinel/quickstart-onboard).

---

## 7. Protocol Support

| Protocol | Status | Implementation |
|----------|--------|---------------|
| **MCP** | GA | Primary integration pattern. GHCP SDK [natively supports MCP](https://github.com/github/copilot-sdk/blob/main/docs/features/mcp.md). All enterprise systems exposed as MCP servers. APIM provides [REST-to-MCP gateway](https://learn.microsoft.com/en-us/azure/api-management/export-rest-mcp-server) (auto-generates tool definitions from OpenAPI specs). [MCP governance via APIM](https://learn.microsoft.com/en-us/azure/api-management/mcp-server-overview). |
| **A2A** | Preview | [APIM A2A governance](https://learn.microsoft.com/en-us/azure/api-management/agent-to-agent-api): AgentCards, JSON-RPC task lifecycle, SSE streaming. Agents are both A2A clients and servers. A2A is not required for core architecture — used in POC2 for external candidate agent demo. |
| **OpenTelemetry** | GA | Native throughout. [GHCP SDK OTEL](https://github.com/github/copilot-sdk/blob/main/docs/observability/opentelemetry.md) + [Foundry Tracing](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/trace-agent-setup). |

---

## 8. Enterprise Integration

### 8.1 LOB Application Integration

All enterprise systems are integrated via MCP servers governed through APIM AI Gateway. Auth complexity is abstracted at the platform level — agent developers never manage tokens. [Azure Key Vault](https://learn.microsoft.com/en-us/azure/api-management/api-management-howto-properties) stores credentials. APIM injects auth at request time. Automated rotation without agent downtime.

| System | Auth Method | MCP Integration |
|--------|-----------|----------------|
| Workday | SAML-bridged via Okta | MCP server, APIM-governed |
| LinkedIn Recruiter | OAuth 2.0 AuthCode | MCP server, APIM-governed |
| Greenhouse ATS | API App Credentials | MCP server, APIM-governed |
| Microsoft Graph | OBO flow | MCP server, APIM-governed |
| ServiceNow | API key | MCP server, APIM-governed |
| Dynamics 365 F&O | Native | MCP server, APIM-governed |
| Maconomy | REST adapter (APIM REST-to-MCP gateway) | Auto-generated from OpenAPI spec |
| ACS (Voice) | Managed identity | MCP server |
| HeyGen | API key | MCP server |
| Citizen-dev integrations (SharePoint, Outlook, Dataverse, etc.) | Logic App connectors | [Azure Logic Apps](https://learn.microsoft.com/en-us/azure/logic-apps/logic-apps-overview) workflow exposed as MCP tool via APIM REST→MCP gateway. 1,400+ prebuilt connectors. No-code path for new tools. |

Supported OAuth 2.0 grant types: Authorization Code, Client Credentials, SAML-bridged (Okta), PKCE, Device Flow, OBO. All via Entra External ID federation with Okta as primary IdP.

---

## 9. Development Experience

| Mode | Persona | Solution |
|------|---------|---------|
| **Pro-code** | Platform engineers, full-stack developers | [GHCP SDK](https://github.com/github/copilot-sdk) Python (primary) + TypeScript. Full access to [skills](https://github.com/github/copilot-sdk/blob/main/docs/features/skills.md), [MCP](https://github.com/github/copilot-sdk/blob/main/docs/features/mcp.md), [hooks](https://github.com/github/copilot-sdk/blob/main/docs/features/hooks.md), OTEL instrumentation, model selection. MIT open-source. |
| **Low-code agents** | Citizen developers | Copilot Studio visual designer for conversational agents and simpler workflows. Supported via Agent 365 (not Foundry Hosted Agents). Custom Control Plane UI natively supports Copilot Studio agents. Not recommended for complex autonomous workflows. |
| **Low-code MCP tools** | IT teams adding tools without writing Python | [Azure Logic Apps](https://learn.microsoft.com/en-us/azure/logic-apps/logic-apps-overview) visual workflows chaining 1,400+ prebuilt connectors. Logic App exposed as MCP tool via APIM REST→MCP gateway. Governed identically to hand-written MCP servers. |
| **Low-code config** | Operators, process owners | Custom Control Plane UI: skill library (browse, fork, customise), tool catalog, governance rules, autonomy dials, template management. No code required. |
| **Agentic builder** | Domain experts | Agentic loop generates SKILL.md files from natural language specifications. Registered in API Center. Human reviews and approves. Built and demonstrated. |
| **Knowledge extraction** | Transitioning staff, SMEs | Threadlight accelerator: creates skills from interviews and unstructured data. Produces machine-actionable SKILL.md files. |

All agent artefacts are Git-committable: skills as SKILL.md, MCP server code, APIM policies as code, Durable Functions orchestrations, autonomy thresholds. Low-code artefacts (Copilot Studio) register through Agent 365 alongside pro-code artefacts.

---

## 10. Code-as-Truth: Auditability and Transparency

Every artefact is version-controlled and inspectable:

- **Skills**: SKILL.md files in Git. Registered in [Azure API Center](https://learn.microsoft.com/en-us/azure/api-center/key-concepts) with lifecycle management (Design → Preview → Production → Deprecated). GitHub Actions integration for syncing from repositories.
- **APIM policies**: version-controlled via [APIOps CI/CD](https://learn.microsoft.com/en-us/azure/api-management/devops-api-development-templates). PR review gates. Per-environment policy sets.
- **Orchestrations**: Durable Functions code in Git. CI/CD deployment with environment-specific configuration.
- **Governance rules**: autonomy thresholds, compliance rules, jurisdiction skills — all in version-controlled configuration stores with change tracking (who, when, why).
- **Traceability**: every routing decision, model selection, and tool call is fully traceable in OTEL spans and audit logs. Every entry in the action ledger links to the OTEL span that produced it, including the reasoning chain and tool call that triggered it.

A team of 5 developers manages 50 agents across dev, staging, and production using CI/CD pipelines with PR review gates. Non-technical auditors inspect agent authorisations, actions, and rationale via the Foundry Control Plane compliance dashboard and Log Analytics KQL queries.

---

## 11. Non-Functional Requirements Response

| NFR | Target | How |
|-----|--------|-----|
| Availability | 99.9% per region | Azure SLA-backed across all services |
| RTO | <5 minutes | Azure Traffic Manager + Cosmos DB automatic failover + Durable Functions replay |
| RPO | Near-zero | Cosmos DB [continuous backup with PITR](https://learn.microsoft.com/en-us/azure/cosmos-db/continuous-backup-restore-introduction). Durable Functions checkpoints in [geo-redundant Azure Storage](https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-functions-orchestrations). |
| Control Plane latency | <5 seconds | Fleet Manager pre-composes situational context. SignalR push. |
| Concurrent workflows (pilot) | 5,000+ | Durable Functions auto-scaling. Cosmos DB horizontal partitioning. Multiple Hosted Agent deployments. |
| Concurrent workflows (prod) | 50,000+ | Same architecture, scaled. Tiered model usage + crystallisation reduce inference bottleneck. Reference architecture to be provided separately. |
| Audit log retention | 7–12 years | [Azure Log Analytics](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/data-retention-archive) archive tier. Immutability via Azure Storage export. |
| Data residency | Platform-level | APIM routes by jurisdiction. Cosmos DB regional deployment. Log Analytics regional workspaces. Not developer-configured. |
| Workflow state | Survives full restart | Durable Functions replays from checkpoint. Cosmos DB serves from geo-replica. Maximum loss: current in-flight phase replays from start. |

---

## 12. POC 1: Finance Intelligent Procure-to-Pay

**Duration**: 8-week sprint.
**Operator**: Finance Controller via Control Plane.
**Concurrency**: 30–50 concurrent invoice workflows.

**Hosted Agent**: Finance Agent (`finance-agent@wpp`).

**Skills**: Intake/OCR (Azure Document Intelligence), Validation (three-way match, duplicate detection), Routing (GL coding, cost centre allocation), Approval (threshold-based routing with HITL gates), Payment (payment file generation), Reconciliation (statement matching, exception identification).

**MCP integrations**: Workday, Dynamics 365 F&O, Maconomy — all governed through APIM AI Gateway. Sandbox/mock APIs provided by WPP.

**Demonstrates**:
- Multi-phase workflow orchestration via Durable Functions
- HITL approval gates (Finance BP interacts via Adaptive Card in Outlook, routed through PA)
- Bulk approval for batched low-risk items
- Rollback and compensating transactions (non-revocable actions gated by hooks)
- Fleet Manager monitoring 30–50 concurrent workflows
- Exception-only Control Plane view
- OTEL cost attribution per invoice
- Foundry Guardrails (PII detection, content safety)
- Full audit trail from receipt to payment
- Mid-workflow platform restart with resume from checkpoint

---

## 13. POC 2: People Talent Lifecycle Agent Team

**Duration**: 12-week sprint following POC 1.
**Operator**: HR Business Partner (London) via Control Plane.
**Concurrency**: 15–20 concurrent hiring workflows.
**Scenario**: Hire a Senior Data Engineer at a WPP agency in USA.
**Five human participants**: Hiring Manager (LA, Teams), HR BP (London, Control Plane), Finance BP (Mumbai, email), IT Ops (Chennai, ServiceNow), Candidate (external, web + voice).

**Hosted Agent**: Hiring Agent (`hiring-agent@wpp`).

**Skills**: Budget & Approvals, Job Design, Sourcing, Triage, Screening, Interview Coordinator, Compliance (jurisdiction-aware), Offer, Onboarding, Voice Screening.

**MCP integrations**: Greenhouse ATS, LinkedIn Recruiter, Workday (hiring), Microsoft Graph (calendar/email), ServiceNow (IT provisioning), Azure Communication Services (voice), HeyGen (avatar) — all governed through APIM AI Gateway.

**Demonstrates** (all POC 1 capabilities plus):
- Voice screening with structured scoring (GPT-Realtime + ACS)
- CV parsing with crystallisation pipeline (skill promotion from generative to deterministic via API Center)
- Episodic memory (recall past hires levelled too low)
- A2A interop with external candidate agent (APIM-governed)
- Jurisdiction-aware compliance (USA vs Germany enforcement switching via APIM routing + jurisdiction-specific skills + Foundry Guardrails)
- Autonomy dials (configurable auto-shortlist thresholds, adjustable at runtime)
- Skill amplification (Fleet Manager surfaces policy + precedents)
- Process evolution (Fleet Manager proposes improvements after completed workflows)
- Synthetic CV evaluation (500 CVs via Foundry Evaluators for bias/accuracy testing)
- Avatar onboarding video (HeyGen API MCP)
- Threadlight knowledge extraction demo (interview HR SME, produce executable skills)
- 5 humans across 4 timezones interacting simultaneously via different surfaces

---

## 16. Customer References

Microsoft will provide with the full submission:

1. Written testimonials from 3 enterprise customers using Microsoft's agentic stack at comparable scale and complexity to WPP.
2. Reference contacts: 3 customers available for direct calls, each with Engineering Lead, AI/ML Ops Lead, and Head of Transformation (SVP+).

Reference customers to be confirmed upon mutual NDA execution. Sectors: media, financial services, professional services.

---

## 17. Portability and Exit Strategy

Lock-in mitigation at every layer:

| Layer | Portability |
|-------|------------|
| Agent logic | [GHCP SDK](https://github.com/github/copilot-sdk) is open-source (MIT). Skills are SKILL.md markdown files. WPP retains ability to self-host, fork, or migrate. |
| Models | GHCP SDK works with any model from the Foundry catalog (1900+ including OpenAI, Anthropic, Google, Meta, Mistral, open-source). Switching models = configuration change in APIM. |
| Tool layer | [MCP](https://learn.microsoft.com/en-us/azure/api-management/mcp-server-overview) is an open standard. All enterprise integrations are MCP servers, portable to any MCP-compliant platform. |
| Interop | [A2A](https://learn.microsoft.com/en-us/azure/api-management/agent-to-agent-api) is an open standard. Agent definitions using A2A are portable. |
| Telemetry | [OpenTelemetry](https://github.com/github/copilot-sdk/blob/main/docs/observability/opentelemetry.md) is an open standard. Traces portable to any OTEL-compatible backend. |
| State | Workflow state is JSON in Cosmos DB, exportable via standard APIs. Durable Functions state in Azure Storage, extractable. |
| Orchestration | Durable Functions is Azure-specific. The pattern (event-driven workflow orchestration) is reproducible on Temporal, AWS Step Functions, etc. |
| Policies | APIM policies exportable. Governance rules are in version-controlled configuration. |

Exit strategy: export skills (Git), export MCP servers (code), export state (Cosmos DB export), export policies (APIM export). The agentic logic is in portable artefacts.

---

## Appendix: Known Constraints

| Constraint | Impact | Mitigation |
|-----------|--------|-----------|
| GHCP SDK in tech preview | API surface may change | Core patterns (skills, MCP, hooks) proven in production. MIT open-source. |
| Foundry Hosted Agents: max 5 replicas (preview) | Scaling ceiling | Multiple deployments, or Azure Container Apps with Foundry telemetry. |
| Foundry Guardrails tool-call interception (preview) | May not be GA for POC | GHCP SDK session hooks provide equivalent enforcement. Guardrails are additive. |
| APIM A2A governance (preview) | A2A features maturing | Not required for core architecture. HTTP gateway primitives work today. |
| API Center skill registry (preview) | No native Git sync | Uses GitHub Actions workflows. Core skill execution is GHCP SDK native. |
| GHCP SDK + Foundry Hosted Agents integration | Hosting adapter needs custom work | Primary integration engineering task for the POC. |
| Agent 365 GA: May 2026 | Integration with Hosted Agents unclear | Entra Agent ID usable independently. Needs POC validation. |
| Foundry IQ / Fabric IQ / Work IQ in public preview | Intelligence Layer products are new; APIs evolving | All three are MCP-addressable — fall back to direct Azure AI Search + Fabric SQL + Graph API if needed. The IQ products are an upgrade path, not a single point of failure. |
| MAI-Voice-1 (preview) | No SLA | GPT-Realtime (GA) is the primary voice path. MAI-Voice-1 is additive. |
| Copilot Studio on Foundry Hosted Agents | Not supported | Copilot Studio agents supported via Agent 365. Control Plane UI supports both. |

---

## References

| # | Source |
|---|--------|
| 1 | [GHCP SDK repository](https://github.com/github/copilot-sdk) |
| 2 | [GHCP SDK skills](https://github.com/github/copilot-sdk/blob/main/docs/features/skills.md) |
| 3 | [GHCP SDK MCP support](https://github.com/github/copilot-sdk/blob/main/docs/features/mcp.md) |
| 4 | [GHCP SDK hooks](https://github.com/github/copilot-sdk/blob/main/docs/features/hooks.md) |
| 5 | [GHCP SDK OTEL](https://github.com/github/copilot-sdk/blob/main/docs/observability/opentelemetry.md) |
| 6 | [GHCP SDK agent loop](https://github.com/github/copilot-sdk/blob/main/docs/features/agent-loop.md) |
| 7 | [Azure AI Foundry Hosted Agents](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents) |
| 8 | [Foundry Control Plane fleet monitoring](https://learn.microsoft.com/en-us/azure/foundry/control-plane/monitoring-across-fleet) |
| 9 | [Foundry Guardrails](https://learn.microsoft.com/en-us/azure/foundry/guardrails/guardrails-overview) |
| 10 | [Foundry Evaluators](https://learn.microsoft.com/en-us/azure/foundry/concepts/built-in-evaluators) |
| 11 | [Foundry model catalog](https://learn.microsoft.com/en-us/azure/foundry/concepts/foundry-models-overview) |
| 12 | [APIM AI Gateway capabilities](https://learn.microsoft.com/en-us/azure/api-management/genai-gateway-capabilities) |
| 13 | [APIM MCP server support](https://learn.microsoft.com/en-us/azure/api-management/mcp-server-overview) |
| 14 | [APIM REST-to-MCP gateway](https://learn.microsoft.com/en-us/azure/api-management/export-rest-mcp-server) |
| 15 | [APIM A2A governance](https://learn.microsoft.com/en-us/azure/api-management/agent-to-agent-api) |
| 16 | [APIOps CI/CD](https://learn.microsoft.com/en-us/azure/api-management/devops-api-development-templates) |
| 17 | [Agent 365 overview](https://learn.microsoft.com/en-us/microsoft-agent-365/overview) |
| 18 | [Entra Agent ID](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/what-is-agent-id) |
| 19 | [Entra Agent OBO flow](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/agent-on-behalf-of-oauth-flow) |
| 20 | [Conditional Access for agents](https://learn.microsoft.com/en-us/entra/identity/conditional-access/agent-id) |
| 21 | [Purview for Agent 365](https://learn.microsoft.com/en-us/purview/ai-agent-365) |
| 22 | [Defender AI threat protection](https://learn.microsoft.com/en-us/azure/defender-for-cloud/ai-threat-protection) |
| 23 | [Azure Durable Functions](https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-functions-overview) |
| 24 | [Cosmos DB continuous backup](https://learn.microsoft.com/en-us/azure/cosmos-db/continuous-backup-restore-introduction) |
| 25 | [Azure Log Analytics retention](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/data-retention-archive) |
| 26 | [Azure API Center](https://learn.microsoft.com/en-us/azure/api-center/key-concepts) |
| 27 | [M365 Agents SDK](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/publish) |
| 28 | [GPT-Realtime audio](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/realtime-audio) |
| 29 | [ACS Call Automation](https://learn.microsoft.com/en-us/azure/communication-services/concepts/call-automation/call-automation) |
| 30 | [Azure Document Intelligence](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/prebuilt/invoice) |
| 31 | [Foundry IQ overview](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/what-is-foundry-iq) |
| 32 | [Foundry IQ — connect agents](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/foundry-iq-connect) |
| 33 | [Fabric IQ overview](https://learn.microsoft.com/en-us/fabric/iq/overview) |
| 34 | [Work IQ MCP overview](https://learn.microsoft.com/en-us/microsoft-copilot-studio/use-work-iq) |
| 35 | [Azure Logic Apps](https://learn.microsoft.com/en-us/azure/logic-apps/logic-apps-overview) |
