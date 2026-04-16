# Technical Response Sections [Scott + Artur]

These sections replace §4–§13 and §16–§17 in the vendor response document. They are grounded in the validated solution architecture. Every product claim is referenced.

---

## 4. Framework Architecture

### 4.1 Microsoft Agent Stack Overview

Our architecture expresses the **determinism ↔ agentic spectrum** explicitly across three cooperating execution layers, with a Fleet Manager observing from above, a central governance layer, and a custom Control Plane UI.

**Deterministic by default, agentic by exception.** WPP's processes contain both rule-driven steps (three-way match, jurisdiction routing, payment file generation) and reasoning-driven steps (CV triage, voice screening, compliance narrative review). Mixing them cleanly requires a layered substrate:

**Fleet Managers**: always-on [GHCP SDK](https://github.com/github/copilot-sdk) Hosted Agents on Azure AI Foundry. Domain-scoped (hiring, finance, compliance). Consume telemetry from all workflows via Azure Event Grid. Reason about fleet health, SLA risk, anomalies. Compose the exception queue for the Control Plane. Push assessments via SignalR.

**Layer 1 — Durable envelope**: [Azure Durable Functions](https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-functions-overview) (GA). One orchestration instance per workflow. Owns phase boundaries, HITL waits at zero compute (days or weeks), timer escalation, parallel fan-out/fan-in, checkpoint/replay with geo-replicated state in Azure Storage. Fully deterministic — code-defined, event-sourced replay.

**Layer 2 — Workflow graph**: [Microsoft Agent Framework (MAF) workflows](https://learn.microsoft.com/en-us/agent-framework/workflows/) (v1.0 GA) connected to DF via the [durable task extension](https://learn.microsoft.com/en-us/agent-framework/integrations/azure-functions) — Microsoft's [Durable Agent Orchestration](https://learn.microsoft.com/en-us/agent-framework/tutorials/agents/orchestrate-durable-agents) pattern (Feb 2026). Each workflow phase is a graph of typed executors: plain-function executors for deterministic operations, agent executors where LLM reasoning is required, and validator executors between them (judge/executor separation expressed as two nodes and an edge). Pregel BSP execution. MAF's own pause/resume and checkpointing are preserved across DF replay.

**Layer 3 — Agent executor contents**: ephemeral GHCP SDK sessions on [Foundry Hosted Agents](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents). Invoked only from MAF agent executor nodes. Each session loads [skills](https://github.com/github/copilot-sdk/blob/main/docs/features/skills.md) and [MCP tools](https://github.com/github/copilot-sdk/blob/main/docs/features/mcp.md) for the task, reasons about it, calls tools through [hooks](https://github.com/github/copilot-sdk/blob/main/docs/features/hooks.md), writes state to Cosmos DB, emits [OTEL telemetry](https://github.com/github/copilot-sdk/blob/main/docs/observability/opentelemetry.md), and returns a typed result to its MAF executor.

**Skill crystallisation** is the evolution path: proven agent executors graduate from LLM-generated to deterministic code, versioned as skills in API Center, and swapped into the MAF graph as plain-function executors — agent executor preserved as fallback for exceptions.

**Central Governance** sits alongside all three tiers:

- **[Azure API Center](https://learn.microsoft.com/en-us/azure/api-center/key-concepts) + [APIM AI Gateway](https://learn.microsoft.com/en-us/azure/api-management/genai-gateway-capabilities)** (GA): one cohesive control point for everything addressable by an agent — models, MCP tools, A2A agents, skills, and APIs. **API Center** is the unified registry: lifecycle management (Design → Preview → Production → Deprecated), GitHub Actions sync, cross-cloud discovery (Azure / GCP / AWS / on-prem). **APIM AI Gateway** is the runtime: model [load balancing, failover, spillover](https://learn.microsoft.com/en-us/azure/api-management/backends), [token rate limits](https://learn.microsoft.com/en-us/azure/api-management/llm-token-limit-policy), per-team / per-workflow budget control, [semantic caching](https://learn.microsoft.com/en-us/azure/api-management/azure-openai-semantic-cache-lookup-policy), jurisdiction-based routing; [MCP tool governance](https://learn.microsoft.com/en-us/azure/api-management/mcp-server-overview) (auth injection, rate limiting, [content safety](https://learn.microsoft.com/en-us/azure/api-management/llm-content-safety-policy)); [A2A governance](https://learn.microsoft.com/en-us/azure/api-management/agent-to-agent-api) (preview); [REST→MCP auto-generation](https://learn.microsoft.com/en-us/azure/api-management/export-rest-mcp-server). One pane, one policy engine, one audit trail.
- **[Foundry Control Plane](https://learn.microsoft.com/en-us/azure/foundry/control-plane/monitoring-across-fleet)** (GA): [agent fleet inventory](https://learn.microsoft.com/en-us/azure/foundry/control-plane/how-to-manage-agents), [model registry](https://learn.microsoft.com/en-us/azure/foundry/concepts/foundry-models-overview) (1900+ models), [guardrails](https://learn.microsoft.com/en-us/azure/foundry/guardrails/guardrails-overview) (PII, [Task Adherence](https://learn.microsoft.com/en-us/azure/foundry/guardrails/how-to-task-adherence)), [built-in evaluators](https://learn.microsoft.com/en-us/azure/foundry/concepts/built-in-evaluators) (quality, safety, drift).
- **[Agent 365 + Entra](https://learn.microsoft.com/en-us/microsoft-agent-365/overview)** (GA May 2026): [Entra Agent ID](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/what-is-agent-id) (first-class agent identity, not service accounts), [agent registry](https://learn.microsoft.com/en-us/microsoft-365/admin/manage/agent-registry), lifecycle management (activate, block, delete), [Conditional Access](https://learn.microsoft.com/en-us/entra/identity/conditional-access/agent-id), [Purview DLP](https://learn.microsoft.com/en-us/purview/ai-agent-365), [Defender](https://learn.microsoft.com/en-us/azure/defender-for-cloud/ai-threat-protection).

**Intelligence Layer** — agents need three kinds of grounding (enterprise documents, business semantics, work context). Microsoft has a purpose-built product for each. All three are MCP-addressable and sit behind APIM AI Gateway alongside any other tool, governed identically:

- **[Foundry IQ](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/what-is-foundry-iq)** (preview): unified agentic retrieval over enterprise corpora. Self-reflective query planner with configurable retrieval reasoning effort. Federates SharePoint, Fabric, OneLake, Blob, AI Search, web, and MCP behind one permission-aware endpoint. Built on Azure AI Search. Used by Compliance Agent (employment law, GDPR, EU AI Act), Job Design (comp benchmarking), Skill Amplification (Fleet Manager surfacing precedents to operator).
- **[Fabric IQ](https://learn.microsoft.com/en-us/fabric/iq/overview)** (preview): semantic intelligence layer over WPP's Fabric / OneLake estate. Business ontology, semantic model, graph engine for multi-hop reasoning. Used by Budget Agent (headcount, cost-centre, agency hierarchy), ROI reporting, cross-entity matrix navigation.
- **[Work IQ MCP](https://learn.microsoft.com/en-us/microsoft-copilot-studio/use-work-iq)** (preview): M365 work graph + memory layer (collaboration patterns, calendar, expertise). Used by Personal Agents, Interview Coordinator (timezone, availability), Org Topology / Escalation routing.

### 4.1.1 Data Platform Integration: Databricks and Snowflake

WPP's existing data estate on Databricks and Snowflake is integrated without requiring migration. Four patterns, in order of preference:

**Fabric IQ federation via OneLake shortcuts**. [OneLake shortcuts](https://learn.microsoft.com/en-us/fabric/onelake/onelake-shortcuts) provide zero-copy, zero-movement access to Databricks Unity Catalog tables and Snowflake external tables. Fabric IQ's semantic layer reasons over this data in-place — no ETL, no data duplication, no lineage fracture. The Budget Agent, ROI Agent, and analytics workflows query WPP's Databricks / Snowflake estate through Fabric IQ as if it were native. [Unity Catalog](https://learn.microsoft.com/en-us/fabric/onelake/onelake-shortcuts-unity-catalog)'s fine-grained access control is preserved through the shortcut.

**Direct MCP servers**. For workloads that require direct SQL access (ad-hoc analytics, custom data pipelines), purpose-built MCP servers for [Databricks SQL Warehouse](https://learn.microsoft.com/en-us/azure/databricks/sql/) and Snowflake are exposed via APIM. Agent executors query structured and unstructured data in Databricks / Snowflake directly, governed identically to all other MCP tools (auth injection, rate limiting, content safety, audit).

**Fine-tuneable analytics models in-place**. Fine-tuned analytics models deployed on Databricks ([MLflow](https://learn.microsoft.com/en-us/azure/databricks/mlflow/) + Model Serving) or Snowflake ([Snowpark Container Services](https://docs.snowflake.com/en/developer-guide/snowpark-container-services/overview) / [Cortex](https://docs.snowflake.com/en/guides-overview-ai-features)) are callable as MCP tools, enabling Analytics Agents to run predictive models over WPP's data where it already lives. This addresses the §6.3 Advanced requirement for "Fine-tuneable analytics models to run Analytics agents on structured and unstructured data (Databricks, Snowflake, file stores)" without model relocation.

**Inference-side federation (optional)**. Where WPP prefers agent inference to stay inside the data platform, [Databricks Mosaic AI Gateway](https://www.databricks.com/product/ai-gateway) and [Snowflake Cortex](https://docs.snowflake.com/en/guides-overview-ai-features) are callable as MCP tools through APIM — a Databricks-hosted model call is governed identically to a Foundry model call.

**Positioning**: Fabric IQ is the semantic / ontology layer *over* WPP's existing data estate, not a replacement for it. Databricks and Snowflake remain the systems of record; Fabric IQ provides the business ontology, semantic model, and graph engine that agents need to reason across them.

### 4.2 Agent Framework vs Agent Surfaces

| Layer | What It Is | Components |
|-------|-----------|------------|
| **Framework** | The agent runtime, workflow graph engine, durable orchestration envelope, state store, governance, tool integration, knowledge grounding, and observability. | GHCP SDK (agent runtime), Microsoft Agent Framework (workflow graph), Foundry Hosted Agents, Durable Functions (durable envelope), APIM AI Gateway + API Center, Foundry IQ + Fabric IQ + Work IQ (Intelligence Layer), Foundry Control Plane, Agent 365 + Entra, Cosmos DB, Application Insights, Log Analytics |
| **Surfaces** | The channels through which humans interact with agents and agent outputs. | M365 Copilot (Teams), Email (Adaptive Cards), Custom Control Plane UI (React), Web Portal, Voice (ACS + GPT-Realtime), ServiceNow |

A single domain agent (e.g. Hiring Agent) is surface-agnostic. The same agent executors inside its MAF workflows produce outputs that the human's Personal Agent (PA) delivers to whatever surface that human uses. The PA is a GHCP SDK agent surfaced in M365 Copilot via the [M365 Agents SDK](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/publish) — it is a capability **layered on** Copilot 365, not a replacement, and adds no new per-user licence beyond WPP's existing Copilot 365 entitlement. Every human has one. Humans make all decisions. The PA prepares and executes.

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
| AG-UI Dynamic Components | The UI consumes [AG-UI](https://learn.microsoft.com/en-us/agent-framework/user-interface/ag-ui/overview) event streams emitted by MAF agent executors and Fleet Manager — agents render per-workflow approval forms, charts, and wizards without hardcoded UI per workflow type. APIM mediates the stream (auth, rate limit, audit). | 5.3 |

Data sources for the custom UI: Application Insights APIs (traces, cost), Foundry REST APIs (agent inventory), APIM metrics (token consumption), workflow state store in Cosmos DB (phase status, approvals, action ledger), Fleet Manager assessments (SignalR + AG-UI real-time streams).

### 4.4 Multi-Agent Orchestration

We implement WPP's "9+ specialist agents" requirement with skill-based specialisation inside a domain-scoped Hosted Agent, not with N separate agent processes. The specialisation — distinct roles, tool allow-lists, model assignments per phase — is preserved; the coordination substrate changes from inter-agent protocol to MAF workflow graph. See **§18 Architectural Choice — Skills, Not Separate Agents** for the full side-by-side trade-off analysis (specialisation, coordination, latency, cost, governance, debuggability).

A domain-scoped Hosted Agent (e.g. Hiring Agent, `hiring-agent@wpp`) runs ephemeral GHCP SDK sessions from MAF agent executors, each loading different skills depending on the workflow phase. Each skill defines its own role, allowed tools, model assignment, and governance rules. The outcome — specialised capabilities with distinct roles and model assignments — matches WPP's requirement for heterogeneous teams. The architectural advantages over separate agents: no inter-agent communication overhead, shared workflow context without message passing, simpler governance (one Entra identity per domain), easier operationalisation at fleet scale.

**A2A still applies where it genuinely belongs** — cross-organisation interactions with external agents (partner candidate agents, supplier pricing agents, jurisdictional compliance authorities) go through [APIM A2A governance](https://learn.microsoft.com/en-us/azure/api-management/agent-to-agent-api). What we avoid is fragmenting a single domain's internal specialisation across N network-separated processes when a typed workflow graph achieves the same specialisation with better operational characteristics.

**Two coordination substrates, layered**:

- **Within a phase — MAF workflow graph**: Pregel BSP execution, typed edges, fan-out/fan-in, conditional routing, validator executors, pause/resume. Stable MAF orchestration patterns (sequential, concurrent, handoff, group chat, Magentic-One) cover the multi-agent topologies WPP requires.
- **Across phases — Azure Durable Functions**: long-running envelope, HITL waits at zero compute (days/weeks), timer escalation, checkpoint/replay, geo-replicated state. Invokes each phase's MAF workflow as a durable activity via the MAF durable task extension.

Both substrates adapt based on runtime data — not static DAGs. Supported topologies end-to-end: sequential (interview after screening), parallel fan-out/fan-in (sourcing + job design concurrently), conditional (compliance flag triggers additional review branch in the MAF graph), timer escalation, bulk HITL.

---

## 5. Core Capability Mapping

### 5.1 Core Framework Capabilities

| Capability | Solution | Status |
|-----------|---------|--------|
| Multi-agent orchestration | Two-layer: Durable Functions (across phases) + MAF workflows (within phase) + skills-based specialisation in GHCP SDK agent executors | GA (DF, MAF v1.0, MAF Durable Task extension), Tech Preview (GHCP SDK) |
| Stateful workflow management | Cosmos DB (workflow state, action ledger) + Durable Functions (orchestration state in Azure Storage) + MAF workflow checkpointing preserved across DF replay | GA |
| Tool/function integration | MCP servers governed through APIM. REST-to-MCP gateway auto-generates tool definitions from OpenAPI specs. | GA (APIM), [MCP preview](https://learn.microsoft.com/en-us/azure/api-management/export-rest-mcp-server) |
| Connectors | MCP servers for Workday, Greenhouse, LinkedIn, D365 F&O, Maconomy, ServiceNow, MS Graph, ACS, HeyGen — all via APIM | Custom build per connector |
| Human-in-the-loop | GHCP SDK hooks intercept non-revocable actions inside agent executors. MAF validator executors enforce structural/policy checks before non-revocable executors fire. Durable Functions `wait_for_external_event` at zero compute for long waits. PA surfaces decisions to humans. Agent 365 routes to right person. | GA (Durable Functions, MAF), custom (HITL flow) |
| Durable execution | Durable Functions checkpoint/replay envelope + MAF native pause/resume preserved across DF replay (via MAF Durable Task extension). Cosmos DB continuous backup with PITR. Geo-replicated state. | GA |
| Memory | Cosmos DB (facts + episodic), skills (procedural), Foundry IQ (semantic retrieval), Fabric IQ (business ontology), Work IQ (M365 episodic), GHCP SDK session (working) | GA (data stores), Preview (IQ products), custom (memory patterns) |
| Model-agnostic | GHCP SDK works with any model from Foundry catalog (1900+). Per-skill model assignment. APIM routes and governs. | GA |
| Control Plane | Foundry Control Plane (platform) + Custom Control Plane UI (operator experience) | GA (Foundry) + custom build |
| **Structured outputs** | GHCP SDK skills declare output JSON Schemas; MAF workflow executors are typed end-to-end; APIM validates responses against the declared schema before propagation. Schema violations rejected at gateway and surfaced to Fleet Manager. Addresses §6.1 "Type-safe, schema-validated agent responses". | GA (MAF typed executors), GA (GHCP SDK structured outputs), GA (APIM schema validation) |
| **Dynamic UI (AG-UI)** | MAF agent executors emit [AG-UI](https://learn.microsoft.com/en-us/agent-framework/user-interface/ag-ui/overview) events (SSE) consumed by the Control Plane UI — dynamic approval forms, charts, wizards rendered per workflow type with no hardcoded UI. APIM-mediated. Addresses §5.3 "AG-UI or equivalent: Must support". | GA (MAF AG-UI), GA (APIM SSE mediation) |

### 5.2 Desirable Capabilities

| Capability | Solution | Status |
|-----------|---------|--------|
| Rollback / compensating actions | Action ledger tracks revocable vs non-revocable. Hooks block non-revocable before execution. Durable Functions triggers compensating actions on rollback. | Custom build (proven pattern) |
| Self-healing | Durable Functions [retry with backoff](https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-functions-error-handling). MAF workflow conditional routing to recovery branches. APIM [circuit breakers and model failover](https://learn.microsoft.com/en-us/azure/api-management/backends). Fleet Manager routes exceptions to humans. | GA |
| Multi-surface engagement | PA delivers to Teams, Email, Control Plane UI, ServiceNow, Web, Voice — all from the same agent executor output | GA (M365 Agents SDK) + custom (Control Plane UI, voice) |
| A2A with off-platform agents | [APIM A2A governance](https://learn.microsoft.com/en-us/azure/api-management/agent-to-agent-api): AgentCards, JSON-RPC, SSE | Preview |
| Evaluation framework | [Foundry Evaluators](https://learn.microsoft.com/en-us/azure/foundry/concepts/built-in-evaluators): task adherence, tool call accuracy, safety, groundedness, sensitive data exposure. Continuous evaluation on production traffic. | GA |
| Workflow crystallisation | Agent executors in the MAF graph graduate from generative (LLM-driven) to deterministic (plain-function) as patterns mature. Skills versioned through API Center lifecycle gates (Design → Production). Agent executor preserved as exception fallback. | Custom build |

### 5.3 Advanced Capabilities

| Capability | Solution | Status |
|-----------|---------|--------|
| Voice screening | [GPT-Realtime](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/realtime-audio) (speech-to-speech) + [ACS Call Automation](https://learn.microsoft.com/en-us/azure/communication-services/concepts/call-automation/call-automation). [MAI-Voice-1](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/mai-voices) (TTS, preview). | GA (GPT-Realtime, ACS), Preview (MAI-Voice-1) |
| Avatar onboarding video | Agent executor drafts script; downstream deterministic executor calls HeyGen API MCP to produce branded video. | Custom MCP server |
| Fine-tuning (Foundry) | [Azure AI Foundry fine-tuning](https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/fine-tuning-overview) for Foundry-hosted models. We prioritise skill crystallisation over model fine-tuning. | GA |
| **Fine-tuneable analytics models on Databricks / Snowflake** | Models fine-tuned on WPP's data stay in-place. Databricks models ([MLflow](https://learn.microsoft.com/en-us/azure/databricks/mlflow/) + Model Serving) and Snowflake models ([Snowpark](https://docs.snowflake.com/en/developer-guide/snowpark-container-services/overview) / [Cortex](https://docs.snowflake.com/en/guides-overview-ai-features)) are callable as MCP tools through APIM — Analytics Agents run predictive models over structured + unstructured data where it already lives. See §4.1.1. | GA |
| Knowledge extraction | **Threadlight** accelerator — a Microsoft delivery accelerator that captures undocumented procedural knowledge from SMEs via interview, producing executable SKILL.md files, MAF workflow graphs, and MCP tool stubs. Output flows through the same API Center governance pathway as hand-written skills. Not a black-box — all artefacts are Git-inspectable. | Built, demonstrated |

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

**Per-skill tool allow-list (APIM-enforced)**: each SKILL.md declares its allowed tools in frontmatter. On skill promotion (Design → Production), the allow-list is compiled into an APIM policy fragment. APIM rejects any tool call from a session loading `skill.X` to tool `tool.Y` if the allow-list does not permit it — enforcement sits in the gateway, outside the agent runtime, and cannot be bypassed by a prompt-injected tool call. Tool calls that originate from an agent executor carry the skill context (skill ID, skill version, workflow phase, jurisdiction) as JWT claims issued by the Hosted Agent's managed identity; APIM validates these claims against the skill's declared allow-list before forwarding.

**Non-revocable operations catalogue**: each MCP tool declares `revocable: true|false`. Non-revocable invocations route through a hook-enforced HITL gate regardless of which skill or workflow invokes them. The catalogue is Git-committed and PR-reviewed.

| Operation | Domain | Enforcement |
|-----------|--------|-------------|
| Send email to external recipient | Hiring, Finance, Onboarding | GHCP SDK hook blocks send; HITL approval via PA |
| Extend offer letter | Hiring | Hook + MAF validator + dual-control |
| Submit payment / release funds (amount > threshold) | Finance | Hook + MAF validator + dual-control |
| Create ServiceNow JML ticket | IT Ops | Hook + HITL approval |
| Post outbound A2A message to external agent | Multi-domain | Hook + validator; allow-listed destinations only |
| Write to Workday / D365 F&O master data | HR, Finance | Hook + dual-control + audit link to operator |
| Commit compliance attestation | Compliance | Dual-control mandatory |

Revocability is a property of the tool, not of the skill — the same tool is non-revocable regardless of which skill invokes it.

**Dual-control (four-eyes)**: high-risk operations require two operator approvals from two distinct Entra identities in two distinct operator groups. Enforced by Durable Functions — the orchestration does not advance until two distinct `raise_event` calls arrive from two distinct operators. Group membership is validated via an APIM policy against Entra group claims; the second approver cannot be the first. Both identities are audit-logged.

### 6.2 Observability and OpenTelemetry

Three layers of observability:

1. **[Foundry Tracing](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/trace-agent-setup)**: every GHCP SDK session (inside a MAF agent executor) emits OTEL spans via [GHCP SDK OTEL](https://github.com/github/copilot-sdk/blob/main/docs/observability/opentelemetry.md) TracerProvider; MAF workflow execution emits executor-lifecycle spans natively; DF emits orchestration spans. Model calls, tool calls, tokens, latency, cost. Spans carry workflow ID, phase, jurisdiction, model, token count.
2. **APIM metrics**: [token usage](https://learn.microsoft.com/en-us/azure/api-management/llm-emit-token-metric-policy), latency, errors per model/tool/agent. Central cost tracking.
3. **Fleet Manager assessment**: event-driven reasoning over telemetry. Fleet health, anomaly detection, SLA risk, exception prioritisation. This is the default Control Plane view.

Cost attribution is per workflow, per phase, per model, per consumer. Visible in both Foundry dashboards and the custom Control Plane UI.

**Telemetry data classification**: OTEL span attributes carry workflow/phase/jurisdiction/model/token counts — **no prompt or response bodies are stored in App Insights**. Bodies are redacted by Foundry Guardrails and stored in Log Analytics only. Reasoning chain and action ledger are stored in separate tables — a non-revocable action's audit record carries the span ID that produced it, not the model's reasoning tokens. Auditors trace cause and effect without the reasoning chain becoming the audit artefact.

### 6.3 Network and Runtime Isolation

**Principle**: APIM is the only public edge. Everything behind it — Foundry Hosted Agents, Durable Functions, MAF workflow executors, MCP servers, Cosmos DB, Key Vault, AI Search, Log Analytics, Event Grid — is reachable only over Private Endpoints or VNet-integrated paths. Agents have no direct internet access; outbound calls to third-party SaaS traverse Azure Firewall with an FQDN allow-list. **All roads go through APIM — privately.**

| Boundary | Control | Notes |
|----------|---------|-------|
| **Public ingress** | [Azure Front Door Premium](https://learn.microsoft.com/en-us/azure/frontdoor/private-link) (WAF, DDoS) → [APIM Private Endpoint](https://learn.microsoft.com/en-us/azure/api-management/private-endpoint) | Single external entry point. WAF blocks OWASP Top-10. APIM gateway has no public IP; Front Door reaches it over Private Link. |
| **East/west (agent ↔ model/tool)** | APIM AI Gateway as sole addressable endpoint; backends on Private Endpoint | [Foundry model endpoints](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/configure-private-link), [Cosmos DB](https://learn.microsoft.com/en-us/azure/cosmos-db/how-to-configure-private-endpoints), [Key Vault](https://learn.microsoft.com/en-us/azure/key-vault/general/private-link-service), [AI Search](https://learn.microsoft.com/en-us/azure/search/service-create-private-endpoint), [Log Analytics](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/private-link-security), Event Grid — all private endpoints. |
| **Egress (agent → SaaS)** | [Azure Firewall Premium](https://learn.microsoft.com/en-us/azure/firewall/premium-features) with FQDN allow-list | Named destinations only: Workday, LinkedIn, Greenhouse, HeyGen, Dynamics 365 SaaS, Okta, Maconomy. Everything else blocked. TLS inspection optional. |
| **Compute isolation** | Azure Functions VNet integration; Foundry Hosted Agents in dedicated subnets; no public IPs on compute | DF workers and MAF executors resolve APIM and data-plane dependencies over Private DNS only. Subnet NSGs enforce least-privilege. |
| **Cross-region** | Region-pinned deployments per jurisdiction | EU workflows never resolve US-region endpoints. Log Analytics workspaces, Cosmos DB accounts, and Foundry Hosted Agent pools are regional. |
| **Residency CI gate** | APIOps pipeline validation | PRs that register a non-EU backend against a DE-tagged skill or model fail CI before deployment. Jurisdiction is an enforced boundary, not a runtime decision. |

**Data classification and retention** — four categories, each with distinct residency and redaction policy:

| Class | Where it lives | Retention | Redaction | Residency |
|-------|---------------|-----------|-----------|-----------|
| **Workflow state** (phase state, action ledger, approval records, candidate/invoice data) | Cosmos DB → Storage immutable export | Workflow lifetime + 90d hot; archive thereafter | CMK via Key Vault; per-field Purview labels | Region-pinned to jurisdiction |
| **Model context** (prompts, tool calls, reasoning chain within a session) | In-memory during the GHCP SDK session; never persisted by default | Ephemeral — discarded at session end | Foundry Guardrails redact at input/output/tool-call/tool-response | Never crosses region |
| **Audit ledger** (every tool call, model call, enforcement decision, human interaction) | Log Analytics → Azure Storage immutable export | 7–12 years, immutable | Bodies stored with Guardrails PII redaction applied | Regional workspace per jurisdiction |
| **Telemetry** (OTEL spans, metrics, cost attribution) | Application Insights | 90d (configurable to 2y) | IDs, metadata, token counts only — no bodies | Regional instance |

### 6.4 Data Protection and Compliance

Three enforcement layers. The LLM cannot bypass any of them.

**[Foundry Guardrails](https://learn.microsoft.com/en-us/azure/foundry/guardrails/guardrails-overview)** (preview): intercepts at [four intervention points](https://learn.microsoft.com/en-us/azure/foundry/guardrails/intervention-points) — input, output, tool-call, tool-response. PII detection. [Task Adherence](https://learn.microsoft.com/en-us/azure/foundry/guardrails/how-to-task-adherence) detects policy drift.

**APIM AI Gateway** (GA): jurisdiction-based model routing (DE workflow → EU endpoint only). [Content safety](https://learn.microsoft.com/en-us/azure/api-management/llm-content-safety-policy) policy. Token rate limiting. All MCP tool calls governed.

**Agent 365 + Entra** (GA May 2026): per-agent RBAC on downstream resources. Conditional Access. Purview DLP on agent interactions. Defender for threat detection.

**Policy-as-code**: APIM policies via [APIOps CI/CD](https://learn.microsoft.com/en-us/azure/api-management/devops-api-development-templates). Foundry Guardrails per agent. Jurisdiction-specific skills in SKILL.md files. All Git-committed, PR-reviewable, audit-trailed.

**Jurisdiction switching**: workflow state carries `jurisdiction`. APIM routes to region-appropriate model endpoint. Jurisdiction-specific skills (right-to-work, works council, GDPR consent) load automatically based on workflow context. Adding a new jurisdiction = adding new skill files, not modifying agent code.

**Audit**: [Azure Log Analytics](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/data-retention-archive) with 7–12 year retention. Immutability enforced via Azure Storage export with immutability policies. Every tool call, model call, enforcement decision, and human interaction logged. Queryable via KQL and [Microsoft Sentinel](https://learn.microsoft.com/en-us/azure/sentinel/quickstart-onboard).

**Platform certifications**: the Azure services in this architecture inherit [SOC 1 / SOC 2 Type II / SOC 3](https://learn.microsoft.com/en-us/compliance/regulatory/offering-soc), [ISO/IEC 27001](https://learn.microsoft.com/en-us/compliance/regulatory/offering-iso-27001), [ISO/IEC 27017](https://learn.microsoft.com/en-us/compliance/regulatory/offering-iso-27017), [ISO/IEC 27018](https://learn.microsoft.com/en-us/compliance/regulatory/offering-iso-27018), [ISO/IEC 27701](https://learn.microsoft.com/en-us/compliance/regulatory/offering-iso-27701), [HIPAA](https://learn.microsoft.com/en-us/compliance/regulatory/offering-hipaa-hitech), [PCI DSS Level 1](https://learn.microsoft.com/en-us/compliance/regulatory/offering-pci-dss), [FedRAMP High](https://learn.microsoft.com/en-us/compliance/regulatory/offering-fedramp), [GDPR](https://learn.microsoft.com/en-us/compliance/regulatory/gdpr), and [BSI C5](https://learn.microsoft.com/en-us/compliance/regulatory/offering-c5-germany) (used in Germany). EU AI Act alignment is maintained through Microsoft's [Responsible AI Standard](https://www.microsoft.com/en-us/ai/principles-and-approach), Foundry Guardrails' classifier coverage of high-risk categories, and Foundry built-in evaluators for bias and safety. Authoritative compliance matrix at the [Microsoft Trust Center](https://www.microsoft.com/en-us/trust-center). WPP's SOC 2 readiness and GDPR evidence inherit from these attestations — no bespoke security certification is required at the WPP application layer. (Addresses §6.3 Enterprise Non-Negotiable.)

**Encryption**: TLS 1.2+ enforced on all ingress and east/west traffic; TLS 1.3 where supported. At-rest encryption defaults to Microsoft-managed keys, with [Customer-Managed Keys (CMK) via Azure Key Vault](https://learn.microsoft.com/en-us/azure/key-vault/keys/customer-managed-keys) available for Cosmos DB, Log Analytics, AI Search, Storage, and Foundry — recommended for regulated jurisdictions. Azure Storage supports [double encryption](https://learn.microsoft.com/en-us/azure/storage/common/infrastructure-encryption-enable) (service + infrastructure layer) for the immutable audit export. Key rotation is automated via Key Vault; agent code never sees raw credentials — APIM injects them at request time from Key Vault references.

**Multi-factor authentication**: enforced by [Entra Conditional Access](https://learn.microsoft.com/en-us/entra/identity/conditional-access/overview) on every human-triggered path — operators accessing the Control Plane UI, business partners approving via their PA, and platform engineers making governance changes. Phishing-resistant methods ([FIDO2, Windows Hello, Microsoft Authenticator with number matching](https://learn.microsoft.com/en-us/entra/identity/authentication/concept-authentication-strengths)) are required; SMS and voice MFA are explicitly blocked via Authentication Strengths policy. Agent-triggered actions use managed identities, not interactive credentials — no shared secret to phish.

---

## 7. Protocol Support

| Protocol | Status | Implementation |
|----------|--------|---------------|
| **MCP** | GA | Primary integration pattern. GHCP SDK [natively supports MCP](https://github.com/github/copilot-sdk/blob/main/docs/features/mcp.md). All enterprise systems exposed as MCP servers. APIM provides [REST-to-MCP gateway](https://learn.microsoft.com/en-us/azure/api-management/export-rest-mcp-server) (auto-generates tool definitions from OpenAPI specs). [MCP governance via APIM](https://learn.microsoft.com/en-us/azure/api-management/mcp-server-overview). |
| **A2A** | Preview | [APIM A2A governance](https://learn.microsoft.com/en-us/azure/api-management/agent-to-agent-api): AgentCards, JSON-RPC task lifecycle, SSE streaming. Agents are both A2A clients and servers. A2A is not required for core architecture — used in POC2 for external candidate agent demo. |
| **OpenTelemetry** | GA | Native throughout. [GHCP SDK OTEL](https://github.com/github/copilot-sdk/blob/main/docs/observability/opentelemetry.md) + [Foundry Tracing](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/trace-agent-setup). |
| **[AG-UI](https://learn.microsoft.com/en-us/agent-framework/user-interface/ag-ui/overview)** | GA (MAF native) | Dynamic, agent-rendered UI components within the Control Plane. MAF agent executors emit AG-UI events over SSE; the Control Plane UI consumes and renders them. APIM mediates the SSE stream (auth, rate limit, audit). Addresses §5.3 "AG-UI or equivalent: Must support" in the RFP. |
| **Structured Outputs** | GA | Type-safe, schema-validated agent responses. GHCP SDK skills declare output JSON Schemas; MAF workflow executors are typed end-to-end; APIM validates every response against the declared schema before forwarding to the next executor. Addresses §6.1 "Type-safe, schema-validated agent responses". |

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

### 8.2 Surface-Side Integrations (where agents are invoked from)

§8.1 above covers the backend systems agents reach through MCP. This section addresses the surfaces where agents are **invoked from**, per §3.6 of the RFP. The consistent pattern: the user's Personal Agent is the invocation surface; each platform integrates either directly through Copilot or through a thin connector to the PA.

| Platform | MoSCoW | Invocation pattern | Status |
|----------|--------|-------------------|--------|
| **M365 Copilot (Teams / Outlook / Word / Excel)** | Must | PA surfaced via [M365 Agents SDK](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/publish). Primary surface for most WPP users. | GA |
| **Custom Control Plane UI (React)** | Must | First-class surface. AG-UI component rendering, SignalR real-time, REST for fleet queries. | Custom build |
| **Web Portal (Angular / React)** | Nice-to-have | Candidate-facing web portal uses the same GHCP SDK + AG-UI pattern. The Angular / React choice is a UI-kit decision — both consume the same AG-UI SSE streams and REST endpoints via APIM. An [Angular AG-UI client](https://learn.microsoft.com/en-us/agent-framework/user-interface/ag-ui/overview) is a routine SSE consumer; no bespoke protocol work. | Custom build |
| **SharePoint (SPFx web parts)** | Should | A lightweight SPFx web part embeds the PA via the M365 Agents SDK chat surface; the web part can also invoke named skills through a pre-registered APIM endpoint. Agents reach into SharePoint through the Graph MCP. Bidirectional: SharePoint as invocation surface and as knowledge source (Foundry IQ federates SharePoint natively). | GA (SPFx + Graph MCP); custom SPFx web part |
| **Power Apps (connector / PCF)** | Must | Two patterns: (a) a **custom connector** to APIM exposes named agent skills to Power Apps formulas/flows, so a citizen-dev app can trigger a workflow (e.g. "submit timesheet for review"); (b) a **PCF control** embeds the PA chat into model-driven apps. Governed identically — APIM enforces auth, rate limit, content safety. | GA (custom connector + PCF); skill registration custom |
| **Dynamics 365 forms / workflows / plugins** | Must | D365 is both a backend (via MCP for reads/writes to master data) **and** a surface. Surface patterns: D365 form embeds the PA via the [Power Platform embedded Copilot surface](https://learn.microsoft.com/en-us/power-platform/admin/copilot-responsible-ai-faqs); D365 workflow steps invoke named agent skills via a custom connector to APIM; D365 plugins call out to APIM for synchronous agent invocation. | GA (D365 + connector); custom D365 resources per workflow |
| **.NET SDK** | Should | MAF ships with full .NET parity — agent executors, workflow graphs, and durable task integration are available in C#. Teams preferring .NET build against MAF .NET with the same skills, MCPs, and governance; artefacts serialise identically (SKILL.md, MAF workflow definitions). | GA (MAF .NET, DF .NET) |
| **ServiceNow** | Must | ServiceNow invokes the PA via the ServiceNow MCP server, which is governed through APIM. IT Ops works in their existing surface; the PA writes back provisioning tickets. | Custom MCP server |
| **Voice (ACS + GPT-Realtime)** | Must | Speech-to-speech front end; tool calls to GHCP SDK backend for reasoning. ACS handles telephony + PSTN. | GA |
| **Email (Adaptive Cards)** | Must | PA composes Adaptive Cards; responses route back through PA. | GA |

All surface-side patterns share the same invariant: **the agent runtime is invoked through APIM, governed identically regardless of surface.** No surface gets a privileged path around the gateway. No surface bypasses MFA, RBAC, content safety, or audit.

---

## 9. Development Experience

All agent artefacts — pro-code, low-code, Threadlight-generated, runtime-spawned — are declarative, Git-committable, and flow through the same APIOps governance pipeline. This is how we meet §6.5 "Low-code artefacts must serialise to the same code/config format as pro-code artefacts": every path produces versioned, reviewable artefacts that register in Azure API Center, are governed by APIM, and carry Entra Agent IDs — regardless of which surface built them.

| Mode | Persona | Solution |
|------|---------|---------|
| **Pro-code** | Platform engineers, full-stack developers | [GHCP SDK](https://github.com/github/copilot-sdk) Python (primary) + TypeScript / .NET / Go for [skills](https://github.com/github/copilot-sdk/blob/main/docs/features/skills.md), [MCP servers](https://github.com/github/copilot-sdk/blob/main/docs/features/mcp.md), [hooks](https://github.com/github/copilot-sdk/blob/main/docs/features/hooks.md). MAF for workflow graphs in Python or .NET. MIT open-source. Recommended for complex autonomous multi-step workflows. |
| **Low-code visual builder (primary, §6.5)** | Citizen developers, domain experts | **[Microsoft Copilot Studio](https://learn.microsoft.com/en-us/microsoft-copilot-studio/)**: Microsoft's flagship low-code agent builder. Visual drag-and-drop designer for conversational and workflow agents — conditional branching, tool bindings (Power Platform connectors + MCP), HITL touchpoints, knowledge grounding. Agents export as declarative YAML / JSON within Power Platform solutions, Git-committable via [Power Platform ALM](https://learn.microsoft.com/en-us/power-platform/alm/overview-alm), versioned through environments (Dev → Test → Prod), and deployed through the same governance pipeline as pro-code agents. Copilot Studio agents register in Agent 365 with first-class Entra Agent ID, are governed by APIM, Purview, and Defender, and appear alongside GHCP SDK agents in the Control Plane — meeting §6.5 parity via declarative serialisation + Git-committable artefacts + shared governance pathway. |
| **Low-code MCP tools** | IT teams adding integrations without writing Python | [Azure Logic Apps](https://learn.microsoft.com/en-us/azure/logic-apps/logic-apps-overview) visual workflows chaining 1,400+ prebuilt connectors. Logic App exposed as MCP tool via APIM REST→MCP gateway. Governed identically to hand-written MCP servers. |
| **Low-code config** | Operators, process owners | Custom Control Plane UI: skill library (browse, fork, customise templates backed by Azure API Center), tool catalogue view, governance editor, autonomy dials, template fork-and-customise. For operational tuning by process owners, not agent construction. All changes written back to Git through APIOps. |
| **60-minute build (§6.4 benchmark)** | Junior developers, seasoned UI users | Copilot Studio hits this benchmark natively: pick a template, add 3 MCP tool connectors from the APIM-governed catalogue (pre-wired auth, rate limits, content safety), add 3 knowledge sources from Foundry IQ, publish to Agent 365. End-to-end build time: **<30 minutes**. Control Plane UI template forge provides a parallel path for consuming pre-wired pro-code templates. Scripted as an observable task for POC evaluation. |
| **Agentic builder (§6.2 design-time)** | Domain experts | A MAF agent executor generates SKILL.md files from natural-language specifications. Output is a typed skill definition with declared tools, model assignment, and governance rules. Registered in API Center in Design state. Human reviews and approves to promote to Production. **Built and demonstrated.** |
| **Runtime agent assembly (§6.2 runtime)** | Supervising agents spawning sub-agents | MAF supports dynamic executor creation at runtime — a supervising agent executor can spawn a sub-workflow or persistent sub-agent within a domain's Hosted Agent scope. For persistent spawned agents, a governance-gate callback auto-registers the new agent in [Entra Agent ID](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/what-is-agent-id) and [API Center](https://learn.microsoft.com/en-us/azure/api-center/key-concepts) (skill in Design state), and writes the spawning decision to the audit ledger. The agent runs in Design state until a human operator promotes it to Production — enforcing the RFP's "persistent agents must be elevated into the same Data Plane storage schema as human-built agents, along the governance pathway." **No runtime escape from governance.** |
| **Knowledge extraction (Threadlight)** | Transitioning staff, SMEs | **Threadlight** is a Microsoft delivery accelerator, built and demonstrated. Interview-capture agent that runs alongside an SME, transcribes and structures the conversation, and produces executable artefacts: SKILL.md files, MAF workflow graphs, and MCP tool stubs with declared schemas. Output enters the same API Center governance pathway as hand-written skills — Design state, human review, promotion to Production. All artefacts are Git-committable and fully inspectable (SKILL.md / Python / YAML) — not a black box. |

All agent artefacts are Git-committable: skills as SKILL.md, MCP server code, APIM policies as code, MAF workflow definitions (Python/.NET), Durable Functions orchestrations, autonomy thresholds. Every artefact — pro-code, low-code UI, Threadlight-generated, runtime-spawned — lands in the same Git repository and flows through the same APIOps pipeline. **One truth for how an agent is defined, regardless of who built it.**

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

**Execution shape**: a Durable Functions orchestration per invoice. Each phase (intake, validation, routing, approval, payment, reconciliation) is a MAF workflow graph. Most executors are plain functions; agent executors are used only where genuine reasoning is needed; validator executors sit between agent output and any downstream non-revocable action.

**Demonstrates**:
- Deterministic-by-default MAF workflow graph (three-way match, payment file generation, routing are plain functions — no LLM)
- Agent executors limited to low-confidence OCR extraction, GL coding reasoning, exception classification — each followed by a validator executor
- Multi-phase orchestration via Durable Functions, with each phase invoked as a durable activity wrapping a MAF workflow
- HITL approval gates (Finance BP interacts via Adaptive Card in Outlook, routed through PA; DF `wait_for_external_event` at zero compute)
- Bulk approval for batched low-risk items
- Rollback and compensating transactions (non-revocable actions gated by GHCP SDK hooks inside agent executors AND by MAF validator executors)
- Fleet Manager monitoring 30–50 concurrent workflows
- Exception-only Control Plane view
- OTEL cost attribution per invoice across all three layers
- Foundry Guardrails inside agent executors (PII detection, content safety)
- Full audit trail from receipt to payment
- Mid-workflow platform restart with DF replay and MAF workflow checkpoint resume
- **Private network posture**: Workday / D365 F&O / Maconomy MCPs reached over Private Endpoints; egress to SaaS via Azure Firewall FQDN allow-list; APIM sole public edge
- **Non-revocable operations demo**: payment file generation with explicit dual-control gate (Finance Controller + Finance BP, distinct Entra identities); catalogue visible in Control Plane
- **60-minute build close-out**: scripted demo where a junior developer builds, tests, and deploys a new agent (3 MCPs + 3 knowledge sources) via the Control Plane UI template forge in under 30 minutes

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

**Execution shape**: a Durable Functions orchestration per hire. The ~10 phases (budget & approvals, job design, sourcing, CV triage, voice screening, interview coordination, compliance, offer, JML onboarding, avatar welcome) are each MAF workflow graphs. Deterministic executors dominate (sourcing queries, interview scheduling, JML provisioning tickets, offer letter templating, HeyGen video generation). Agent executors are bounded — JD drafting, CV scoring, voice screening, compliance narrative, offer personalisation. Validator executors enforce structural and policy checks between agent output and downstream action.

**Demonstrates** (all POC 1 capabilities plus):
- Layered orchestration: DF envelope across 12 weeks + MAF workflow graphs per phase + GHCP SDK sessions in agent executors
- Deterministic-by-default graphs annotated per phase (see [solution.md §15](../solution/solution.md)) — transparently shows what is code vs what is LLM
- Voice screening with structured scoring (GPT-Realtime + ACS) followed by validator executor
- CV parsing with crystallisation pipeline (agent CV scorer → deterministic classifier in API Center, agent preserved as fallback)
- Episodic memory (recall past hires levelled too low) via workflow state store + Fabric IQ
- A2A interop with external candidate agent (APIM-governed)
- Jurisdiction-aware compliance (USA vs Germany enforcement switching via APIM routing + jurisdiction-specific skills + Foundry Guardrails + MAF validator executors for GDPR consent, EU AI Act classification)
- Autonomy dials (configurable auto-shortlist thresholds, adjustable at runtime — controls whether a phase routes to agent executor or falls back to deterministic baseline)
- Skill amplification (Fleet Manager surfaces policy + precedents)
- Process evolution (Fleet Manager proposes crystallisation candidates after completed workflows)
- Synthetic CV evaluation (500 CVs via Foundry Evaluators for bias/accuracy testing)
- Avatar onboarding video (HeyGen API MCP)
- Threadlight knowledge extraction demo (interview HR SME, produce executable skills in the MAF graph)
- 5 humans across 4 timezones interacting simultaneously via different surfaces
- **AG-UI dynamic components**: HR BP sees bulk-approval forms, interview scorecards, and escalation cards rendered dynamically per workflow type by MAF agent executors — no hardcoded UI per workflow
- **Runtime agent assembly demo**: Threadlight captures a new jurisdiction-specific compliance pattern from an SME interview during the POC, generates a SKILL.md, auto-registers it in Entra Agent ID + API Center (Design state), human operator reviews and promotes to Production — new capability live in the next workflow without a redeploy
- **Databricks / Snowflake federation demo**: Fabric IQ queries levelling-history data residing in Databricks Unity Catalog via OneLake shortcuts — the Hiring Agent's "past hires levelled too low" recall runs against WPP's existing data estate with no migration
- **Private network + residency posture**: German hiring workflow routes only to EU model endpoints and EU Log Analytics workspace; APIOps pipeline rejects a deliberate PR that registers a US backend to the DE skill (live CI gate demo)

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

The stack separates a **GA foundation** from a **replaceable agent runtime layer**. The foundation — Azure Durable Functions, APIM AI Gateway, Azure API Center, Cosmos DB, Azure AI Foundry runtime, Microsoft Agent Framework v1.0, Entra, Log Analytics, Application Insights — is GA and production-proven. The agent runtime layer is GHCP SDK today; because skills are SKILL.md files and tools are MCP servers (both open standards), the agent runtime is **replaceable without redesigning the stack**. If GHCP SDK stalls or WPP prefers a different runtime, the runtime swaps and skills, tools, workflow graphs, governance, data layer, and Control Plane all remain. This is the honest framing of the preview-dependency question: preview-layer risk is confined to the agent runtime, not distributed across the stack.

| Constraint | Impact | Mitigation |
|-----------|--------|-----------|
| GHCP SDK in tech preview | API surface may change | Core patterns (skills, MCP, hooks) proven in production inside GitHub Copilot serving millions of developers daily. MIT open-source. Replaceable: skills (SKILL.md) and MCP tools port to any MCP-native runtime without redesign. |
| Microsoft Agent Framework v1.0 (Oct 2025) | Framework is young | Core runtime and workflows are GA. MAF durable task extension for Azure Functions is productised by Microsoft as the Durable Agent Orchestration pattern. Orchestration patterns stable. Fallback: GHCP SDK + DF combination works without MAF — MAF adds the deterministic graph primitive. |
| Foundry Hosted Agents: max 5 replicas (preview) | Scaling ceiling | Multiple deployments, or Azure Container Apps with Foundry telemetry. |
| Foundry Guardrails tool-call interception (preview) | May not be GA for POC | GHCP SDK session hooks provide equivalent enforcement. Guardrails are additive. |
| APIM A2A governance (preview) | A2A features maturing | Not required for core architecture. HTTP gateway primitives work today. |
| API Center skill registry (preview) | No native Git sync | Uses GitHub Actions workflows. Core skill execution is GHCP SDK native. |
| GHCP SDK + Foundry Hosted Agents integration | Hosting adapter needs custom work | Primary integration engineering task for the POC. |
| Agent 365 GA: May 2026 | Integration with Hosted Agents unclear | Entra Agent ID usable independently. Needs POC validation. |
| Foundry IQ / Fabric IQ / Work IQ in public preview | Intelligence Layer products are new; APIs evolving | All three are MCP-addressable — fall back to direct Azure AI Search + Fabric SQL + Graph API if needed. The IQ products are an upgrade path, not a single point of failure. |
| MAI-Voice-1 (preview) | No SLA | GPT-Realtime (GA) is the primary voice path. MAI-Voice-1 is additive. |
| Copilot Studio on Foundry Hosted Agents | Not supported | Copilot Studio agents supported via Agent 365 with Entra Agent ID and full Purview/Defender governance. Control Plane UI supports both Copilot Studio and GHCP SDK agents. Copilot Studio artefacts (declarative YAML, Power Platform solutions) are Git-committable via Power Platform ALM and meet §6.5 serialisation parity through the shared governance pathway. |

---

## 18. Architectural Choice — Skills, Not Separate Agents

POC 2 calls for "9+ specialist agents" in the hiring lifecycle: Budget, Job Design, Sourcing, Triage, Screening, Interview Coordinator, Compliance, Offer, Onboarding, Voice Screening. The brief's mental model is that each specialist role is an independent agent process with its own identity, its own tool set, and an inter-agent protocol connecting them.

We implement the same *capabilities* with a different *topology*: one domain-scoped Hosted Agent per domain (Hiring, Finance, Compliance) running ephemeral GHCP SDK sessions from MAF agent executors, each loading a different **skill** per phase. Each skill declares its own role, tool allow-list, model assignment, and governance rules. Specialisation is **preserved**; what changes is the coordination substrate — a MAF workflow graph with typed edges and validator nodes, not an A2A protocol between separate agent processes.

**Side-by-side trade-offs**:

| Dimension | 9 separate specialist agents | Skills-based (our approach) |
|---|---|---|
| **Specialisation** | 1 agent per role, distinct identity per role | 1 skill per role, distinct role definition + tool allow-list + model per skill |
| **Coordination substrate** | A2A protocol between agents (JSON-RPC / SSE) on every handoff | MAF workflow graph edges — in-process, typed, deterministic |
| **Identity surface** | 9 Entra Agent IDs per domain, 9 Conditional Access policies, 9 audit identities | 1 domain Entra Agent ID; policy + audit segmentation at the skill layer via APIM |
| **Context sharing** | Each agent re-grounds or serialises context across the A2A boundary | Shared workflow state in the MAF graph; no re-grounding |
| **Latency** | N × retrieval + N × inference + N × network hops | 1 × shared retrieval + N × inference; zero inter-agent network hops within the graph |
| **Cost** | N × working-memory tokens; every A2A handoff re-establishes context | Amortised working memory; context flows down MAF edges |
| **Failure modes** | Network partition between agents; protocol version drift; handoff races | In-process graph execution; Pregel BSP guarantees deterministic fan-in |
| **Debuggability** | N separate OTEL traces per workflow; stitching via correlation IDs | Single MAF workflow trace per phase; natural parent-child span hierarchy |
| **Governance surface** | Per-agent governance — 9 APIM policy sets to keep aligned | Per-skill governance with one shared domain identity; fewer drift points |
| **Operationalisation at fleet scale** | 9 × N workflows of agent instances to monitor, scale, restart | N workflows × one domain pool of Hosted Agents; skills load in ~ms |
| **Matches "specialist team" mental model** | Yes | Yes — skills are the specialists; the graph is the team |

**Where A2A still applies**. We are not against agent-to-agent protocols. A2A is the right choice when an agent is genuinely **off-platform** — a partner's candidate agent, an external supplier's pricing agent, a jurisdictional authority's compliance agent owned by a different organisation. These cross-boundary interactions go through [APIM A2A governance](https://learn.microsoft.com/en-us/azure/api-management/agent-to-agent-api) (JSON-RPC, AgentCards, SSE). What we avoid is **fragmenting a single domain's internal specialisation** across N network-separated processes when a typed workflow graph achieves the same specialisation with better operational characteristics.

**What WPP gets either way**:

- Heterogeneous expertise per phase — as skills with distinct models and tools
- Role-based authority and tool access — as skill-declared allow-lists enforced at APIM
- Auditability per role — as skill-tagged OTEL spans and audit ledger entries
- Independent evolution per role — as skill-versioned artefacts in API Center

**What WPP avoids**:

- 9× identity / governance / operational overhead per domain
- Inter-agent protocol failure modes
- Latency and cost of re-grounding across every handoff
- Debugging a correlation-ID graph instead of a single workflow trace

This is not an argument against multi-agent systems. It is an argument for applying agent-process separation at the **organisational boundary** where it creates value, and skill-based specialisation at the **domain boundary** where it reduces cost and complexity without giving up any capability. If WPP evaluators prefer the separate-agent topology after reviewing the trade-offs, both approaches are supported by MAF — we can compose a hybrid: skills inside a domain, A2A across domains.

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
| 36 | [Microsoft Agent Framework overview](https://learn.microsoft.com/en-us/agent-framework/overview/) |
| 37 | [MAF Workflows](https://learn.microsoft.com/en-us/agent-framework/workflows/) |
| 38 | [MAF Workflow Executors](https://learn.microsoft.com/en-us/agent-framework/workflows/executors) |
| 39 | [MAF Durable Task Extension for Azure Functions](https://learn.microsoft.com/en-us/agent-framework/integrations/azure-functions) |
| 40 | [MAF Durable Agent Orchestration tutorial](https://learn.microsoft.com/en-us/agent-framework/tutorials/agents/orchestrate-durable-agents) |
| 41 | [MAF v1.0 release announcement](https://devblogs.microsoft.com/agent-framework/microsoft-agent-framework-version-1-0/) |
| 42 | [Building Human-in-the-Loop AI Workflows with MAF](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/building-human-in-the-loop-ai-workflows-with-microsoft-agent-framework/4460342) |
