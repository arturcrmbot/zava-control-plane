# WPP Enterprise Agent Framework — Solution Architecture

## 1. Principles

### The determinism ↔ agentic spectrum

WPP's processes span a spectrum. Some phases are rule-driven and must be deterministic (three-way PO match, jurisdiction routing, payment file generation, IT provisioning tickets). Others require reasoning over unstructured input and judgement (CV triage, voice screening, compliance narrative review). A 12-week hiring process is not one mode or the other — it is a **sequence of deterministic scaffolding gates with agentic reasoning inside specific steps**.

Our architecture expresses this spectrum explicitly through three execution layers. Each has a different substrate, a different failure model, and a different cost profile. Mixing them is the point — not a compromise.

### Three-layer execution model

| Layer | Substrate | Role | Determinism |
|-------|-----------|------|-------------|
| **1. Durable execution envelope** | [Azure Durable Functions](https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-functions-overview) (GA) | One orchestration instance per workflow. Owns phase boundaries, HITL waits at zero compute (days or weeks), timer escalation, checkpoint/replay, geo-replicated state. | Fully deterministic — code-defined, event-sourced replay. |
| **2. Workflow graph** | [Microsoft Agent Framework (MAF) workflows](https://learn.microsoft.com/en-us/agent-framework/workflows/) with the [durable task extension](https://learn.microsoft.com/en-us/agent-framework/integrations/azure-functions) for Azure Durable Functions | Defines each phase (or the whole process) as a graph of typed executors with fan-out/fan-in, conditional routing, and HITL hooks. Validator executors sit between agent executors. | **Deterministic by default, agentic by exception** — most nodes are plain functions. |
| **3. Agent executor contents** | [GHCP SDK](https://github.com/github/copilot-sdk) sessions running on [Foundry Hosted Agents](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents) | Invoked from MAF agent executor nodes only. Load [skills](https://github.com/github/copilot-sdk/blob/main/docs/features/skills.md) and [MCP tools](https://github.com/github/copilot-sdk/blob/main/docs/features/mcp.md), reason, call tools through [hooks](https://github.com/github/copilot-sdk/blob/main/docs/features/hooks.md), emit [OTEL](https://github.com/github/copilot-sdk/blob/main/docs/observability/opentelemetry.md), exit. | Probabilistic LLM reasoning sandboxed inside a single executor, wrapped by deterministic pre/post hooks. |

A WPP workflow is therefore a **Durable Functions orchestration** that coordinates **MAF workflow graphs** whose agent nodes invoke **GHCP SDK sessions**. Each layer earns its place: DF for long-running durability that MAF does not itself provide at zero compute; MAF for the deterministic graph shape of a phase with HITL and typed data flow; GHCP SDK for the LLM runtime with hooks, MCP, skills, and OTEL.

### Deterministic by default, agentic by exception

Most executors in a MAF workflow are plain Python/C# functions — they fetch data, validate, route, emit events. Agent executors are used only where LLM reasoning is genuinely required. Between agent executors, **validator executors** assert structural and policy constraints before output propagates — this is the "judge catches executioner" pattern made explicit in the graph, not delegated to the model.

The consequence for governance: the majority of the workflow graph is literally code. The LLM is contained inside specific executors, wrapped in GHCP SDK hooks (pre/post tool-use), with Foundry Guardrails intercepting at four points, with external validators between nodes, and with APIM AI Gateway governing every model and tool call. Probabilism is bounded.

### Skill crystallisation — the migration path

Proven patterns move left along the spectrum. A phase that starts as an agent executor producing structured output, validated by a downstream executor, and found stable over N completed workflows can be **crystallised** — promoted from LLM-generated to deterministic code, versioned as a skill in [Azure API Center](https://learn.microsoft.com/en-us/azure/api-center/key-concepts), and swapped into the MAF graph as a plain function executor. The agent executor remains available as a fallback for exceptions. This is how the system gets cheaper, faster, and more predictable as it matures — without re-architecting anything.

### Why GHCP SDK for agent executors

The agentic loop pattern is well understood. The hard part is the runtime around it: session management, skill resolution, MCP client lifecycle, hook interception, OTEL instrumentation, model failover, structured outputs, sub-agent delegation, prompt caching. Building this from scratch is a multi-quarter engineering effort, and what you end up with is what GitHub already runs in production behind GitHub Copilot — serving millions of developers daily.

**[GHCP SDK](https://github.com/github/copilot-sdk) is that runtime, extracted and open-sourced (MIT, Python/TypeScript/Go/.NET).** Inside a MAF agent executor, adopting it means:

- **Scaled, not DIY** — the loop, hooks, skills, and MCP client implementations are battle-tested at GitHub Copilot scale, not bespoke code we maintain
- **Composable governance** — [hooks](https://github.com/github/copilot-sdk/blob/main/docs/features/hooks.md) intercept tool calls deterministically; non-revocable actions route to humans without LLM intervention in the send path
- **Open standards native** — [MCP](https://github.com/github/copilot-sdk/blob/main/docs/features/mcp.md) (tools), A2A (agent-to-agent), [OTEL](https://github.com/github/copilot-sdk/blob/main/docs/observability/opentelemetry.md) (observability) are first-class, not bolted on
- **Portable** — same SDK code runs on Foundry Hosted Agents, Container Apps, AKS, or local dev. No lock-in to a specific hosting fabric
- **Specialisation via skills, not via separate agents** — one domain-scoped Hosted Agent (with one Entra Agent ID, one tool allow-list, one audit identity) runs many phase-specific executors by loading different [SKILL.md](https://github.com/github/copilot-sdk/blob/main/docs/features/skills.md) files. Avoids the "300 agents to manage" anti-pattern

Everything else in this document (Foundry, APIM, MAF workflows, DF, Fleet Managers, Control Plane, IQ products) is the **enterprise envelope** around these three layers.

---

## 2. Approach

**Azure Durable Functions** provides the long-running durable envelope around each workflow. Inside each phase, a **Microsoft Agent Framework (MAF) workflow** graph — wired to DF via the MAF [durable task extension](https://learn.microsoft.com/en-us/agent-framework/integrations/azure-functions) — defines the deterministic execution path, with most nodes as plain functions and agent nodes invoking **GHCP SDK** sessions on Azure AI Foundry Hosted Agents. The entire stack is governed by Fleet Manager agents, grounded by **Foundry IQ / Fabric IQ / Work IQ**, centrally managed through **Azure API Center + APIM AI Gateway**, and surfaced through Foundry Control Plane.

> **Refs**: [GHCP SDK](https://github.com/github/copilot-sdk) (MIT, Python/TypeScript/Go/.NET) · [Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/overview/) (v1.0, Python/.NET) · [MAF Durable Functions integration](https://learn.microsoft.com/en-us/agent-framework/integrations/azure-functions) · [Durable Agent Orchestration tutorial](https://learn.microsoft.com/en-us/agent-framework/tutorials/agents/orchestrate-durable-agents)

**Skills**: [SKILL.md files](https://github.com/github/copilot-sdk/blob/main/docs/features/skills.md) define capabilities declaratively. New capability = new skill file. Skills are the specialisation mechanism — instead of separate agents for screening, sourcing, compliance, etc., a single domain-scoped Hosted Agent loads different skills per MAF agent executor. Each skill defines its own role, allowed tools, model assignment, and governance rules. Skills are also crystallisation artefacts — proven agentic patterns graduate from LLM-generated to deterministic code, versioned as skills, and can be swapped into the MAF graph as plain-function executors (agent executor kept as exception fallback). Skills are registered in Azure API Center with lifecycle management (Design → Preview → Production → Deprecated) and governed via APIM AI Gateway.

> **Ref**: [Azure API Center lifecycle](https://learn.microsoft.com/en-us/azure/api-center/key-concepts)

**MCP tools**: enterprise system integrations (Workday, Greenhouse, LinkedIn, ServiceNow, Graph, Dataverse) exposed as [MCP servers](https://github.com/github/copilot-sdk/blob/main/docs/features/mcp.md), governed through APIM AI Gateway with auth, rate limiting, and content safety policies. APIM provides a [REST-to-MCP gateway](https://learn.microsoft.com/en-us/azure/api-management/export-rest-mcp-server) that auto-generates MCP tool definitions from OpenAPI specs.

**Hooks**: GHCP SDK session hooks ([`onPreToolUse`](https://github.com/github/copilot-sdk/blob/main/docs/hooks/pre-tool-use.md), [`onPostToolUse`](https://github.com/github/copilot-sdk/blob/main/docs/hooks/post-tool-use.md)) provide operational governance inside each agent executor's session. Non-revocable actions (send email, submit background check, extend offer, execute payment) are intercepted by hooks, blocked from immediate execution, and routed to the human's PA for approval. After approval, execution is deterministic — no LLM in the send path. Hooks also handle audit logging (every tool call logged with workflow context) and tool allow-listing per skill set. Hooks complement MAF validator executors: hooks operate inside the session; validators operate on its typed output.

**Structured outputs**: agent executors produce type-safe, schema-validated results. GHCP SDK skills declare output schemas; MAF workflow executors are typed; APIM validates every response against the declared schema before it propagates to the next executor. Schema violations are rejected at the gateway and surfaced to Fleet Manager. Structured outputs are a first-class property of the pipeline, not a post-hoc parse. (Addresses §6.1 "Structured outputs: Type-safe, schema-validated agent responses".)

**AG-UI protocol**: dynamic, agent-rendered UI components are emitted by MAF agent executors as [AG-UI](https://learn.microsoft.com/en-us/agent-framework/user-interface/ag-ui/overview) events (SSE stream) and consumed by the custom Control Plane UI. An agent can render a per-workflow approval form, a contextual chart, or a multi-step decision wizard without hardcoded UI for each workflow type. AG-UI streams are APIM-mediated (auth, rate limit, audit). (Addresses §5.3 "AG-UI or equivalent: Must support: for dynamic, agent-rendered UI components within the Control Plane".)

**Human interaction**: humans interact with their personal agent (PA) through M365 Copilot (Teams, Outlook) via the [M365 Agents SDK](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/publish), and through the custom Control Plane UI for fleet management. There is always an agentic layer between humans and the system.

---

## 3. Architecture

### Layers

| Layer | Component | Role |
|-------|-----------|------|
| **Fleet Manager** | Always-on GHCP SDK Hosted Agent | Consumes telemetry from all workflows. Reasons about fleet health, SLA risk, anomalies. Composes the exception queue for the Control Plane. Monitors compliance enforcement events. |
| **Durable envelope** | [Azure Durable Functions](https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-functions-overview) (GA) | One orchestration instance per workflow. HITL waits at zero compute for days or weeks, timer escalation, checkpoint/replay, geo-replicated state. Coordinates phase boundaries and escalations. |
| **Workflow graph** | [MAF workflow](https://learn.microsoft.com/en-us/agent-framework/workflows/) via [durable task extension](https://learn.microsoft.com/en-us/agent-framework/integrations/azure-functions) | Deterministic graph of typed executors for each phase. Plain function executors for data mapping, validation, routing. Agent executors where reasoning is required. Validator executors between agent executors (judge/executor separation). Pregel BSP execution, fan-out/fan-in, conditional routing, HITL hooks. |
| **Agent executor contents** | Ephemeral GHCP SDK sessions | Invoked only from agent executor nodes. Load skills + MCP tools. Reason about the task. Write state. Emit [OTEL telemetry](https://github.com/github/copilot-sdk/blob/main/docs/observability/opentelemetry.md). Exit. |

### Identity & Access

The Entra Agent ID lives on the **Hosted Agent container**, not on individual sessions. The GHCP SDK session invoked from a MAF agent executor is a unit of work inside a persistent container — it uses the container's identity when calling tools.

**Hosted Agent topology** (design decision for POC):

| Hosted Agent | Entra Agent ID | Tool Access | Hosts Agent Executors For |
|-------------|---------------|-------------|---------------|
| Hiring Agent | `hiring-agent@wpp` | Greenhouse, LinkedIn, Workday (hiring), Graph, ACS | All hiring workflow agent executors (screening, sourcing, compliance, offer, onboarding) |
| Finance Agent | `finance-agent@wpp` | Workday (finance), D365 F&O, Maconomy | All P2P workflow agent executors (intake, validation, routing, payment, reconciliation) |
| Fleet Manager | `fleet-manager@wpp` | Read-only: Foundry Tracing, Event Grid, workflow state store. No tool invocation on downstream systems. | Fleet monitoring, exception composition, compliance oversight |

Each Hosted Agent is domain-scoped — it has only the tool access its domain requires. All GHCP SDK sessions invoked from MAF agent executors inside it inherit that scope.

**OBO vs app-only**: when a MAF workflow is triggered by a human action (Finance BP approves), the GHCP SDK session inside an agent executor can act [on-behalf-of](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/agent-on-behalf-of-oauth-flow) that human — audit trail attributes the decision to them, downstream access uses their delegated permissions. For autonomous phases (screening 200 CVs), the session uses the Hosted Agent's app-only identity.

**Skill and policy governance**: skill promotion (Design → Production) goes through Azure API Center lifecycle gates. API Center integrates with GitHub Actions workflows for syncing SKILL.md files from repositories. Autonomy threshold changes are audit-logged with operator identity. Governance policy changes require PR review in Git, deployed via [APIOps CI/CD](https://learn.microsoft.com/en-us/azure/api-management/devops-api-development-templates).

**Per-skill tool allow-list (APIM-enforced)**: each SKILL.md declares its allowed tools in frontmatter. On skill promotion, the allow-list is compiled into an APIM policy fragment. APIM rejects any tool call from a session loading `skill.X` to tool `tool.Y` if the allow-list does not permit it — enforcement sits in the gateway, outside the agent runtime, and cannot be bypassed by the LLM.

### Authorisation & Non-Revocable Actions

Authorisation is layered: identity (who is acting) is resolved by Entra; capability (what tools the session may call) is constrained by skill allow-lists at APIM; reversibility (whether the action can be undone) is classified per tool in a version-controlled catalogue.

**Non-revocable operations catalogue**: each MCP tool declares `revocable: true|false`. Non-revocable invocations route through a hook-enforced HITL gate regardless of which skill or workflow invokes them. The catalogue is Git-committed and PR-reviewed.

| Operation | Domain | Enforcement |
|-----------|--------|-------------|
| Send email to external recipient | Hiring, Finance, Onboarding | GHCP SDK hook blocks send; HITL approval via PA required |
| Extend offer letter | Hiring | Hook + MAF validator + dual-control |
| Submit payment / release funds (amount > threshold) | Finance | Hook + MAF validator + dual-control |
| Create ServiceNow JML ticket | IT Ops | Hook + HITL approval |
| Post outbound A2A message to external agent | Multi-domain | Hook + validator; allow-listed destinations only |
| Write to Workday / D365 F&O master data | HR, Finance | Hook + dual-control + audit link to operator |
| Commit compliance attestation | Compliance | Dual-control mandatory |
| Publish content to external channels | Marketing (future) | Hook + HITL |

Revocability is a property of the tool, not of the skill — the same tool is non-revocable regardless of which skill invokes it.

**Dual-control**: high-risk operations require two operator approvals from two distinct Entra identities in two distinct operator groups. Enforced by Durable Functions — the orchestration does not advance until two distinct `raise_event` calls arrive from two distinct operators. Group membership is checked via an APIM policy against Entra group claims; the second approver cannot be the first. All four-eyes approvals are audit-logged with both identities.

**Prompt-injection hardening**: tool calls that originate from an agent executor carry the skill context (skill ID, skill version, workflow phase, jurisdiction) as JWT claims issued by the Hosted Agent's managed identity. APIM validates these claims against the skill's declared allow-list and destination. A prompt-injected attempt to call a tool not in the current skill's allow-list is rejected at the gateway — the LLM cannot elevate its own capability.

### Network & Data Boundaries

**Principle**: APIM is the only public edge. Everything behind it — Foundry Hosted Agents, Durable Functions, MAF workflow executors, MCP servers, Cosmos DB, Key Vault, AI Search, Log Analytics, Event Grid — is reachable only over Private Endpoints or VNet-integrated paths. Agents have no direct internet access; outbound calls to third-party SaaS traverse Azure Firewall with an FQDN allow-list. **All roads go through APIM — privately.**

**Network perimeter**

| Boundary | Control | Notes |
|----------|---------|-------|
| **Public ingress** | [Azure Front Door Premium](https://learn.microsoft.com/en-us/azure/frontdoor/private-link) (WAF, DDoS) → [APIM Private Endpoint](https://learn.microsoft.com/en-us/azure/api-management/private-endpoint) | Single external entry point (candidate portal, partner A2A agents). WAF blocks OWASP Top-10. Front Door reaches APIM over Private Link — the APIM gateway has no public IP. |
| **East/west (agent ↔ model/tool)** | APIM AI Gateway as the only addressable endpoint; backends reached via Private Endpoint | Hosted Agents, DF workers, and MAF executors resolve APIM via Private DNS. [Foundry model endpoints](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/configure-private-link), [Cosmos DB](https://learn.microsoft.com/en-us/azure/cosmos-db/how-to-configure-private-endpoints), [Key Vault](https://learn.microsoft.com/en-us/azure/key-vault/general/private-link-service), [AI Search](https://learn.microsoft.com/en-us/azure/search/service-create-private-endpoint), [Log Analytics](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/private-link-security), and Event Grid all sit on private endpoints. |
| **Egress (agent → SaaS)** | Azure Firewall Premium with FQDN allow-list | Named destinations only: Workday, LinkedIn, Greenhouse, HeyGen, Dynamics 365 SaaS, Okta, Maconomy. Everything else blocked. TLS inspection optional. Egress logs flow to Log Analytics. |
| **Compute isolation** | Azure Functions VNet integration; Foundry Hosted Agents deployed into dedicated subnets; no public IPs on compute | DF workers and MAF workflow executors communicate with APIM and data-plane dependencies over Private DNS only. Subnet NSGs enforce least-privilege flow. |
| **Cross-region** | Region-pinned deployments per jurisdiction | EU workflows never resolve US-region endpoints. Log Analytics workspaces, Cosmos DB accounts, and Foundry Hosted Agent pools are regional. Cross-region replication is opt-in per workload for DR only. |
| **Residency CI gate** | APIOps pipeline validation | PRs that register a non-EU backend against a DE-tagged skill or model fail CI before deployment. Jurisdiction becomes an enforced boundary, not a runtime hope. |

**Data classification and boundaries**

Data is classified into four categories, each with distinct retention, residency, and redaction policy:

| Class | Where it lives | Retention | Redaction | Residency |
|-------|---------------|-----------|-----------|-----------|
| **Workflow state** (phase state, action ledger, approval records, candidate/invoice data) | [Cosmos DB](https://learn.microsoft.com/en-us/azure/cosmos-db/introduction) (hot) → Azure Storage immutable export (cold) | Workflow lifetime + 90 days hot; archive thereafter | Encrypted at rest with Customer-Managed Keys via Key Vault; per-field sensitivity labels via Purview | Region-pinned to jurisdiction |
| **Model context** (prompts, tool calls, reasoning chain within a GHCP SDK session) | In-memory during the session; never persisted by default | Ephemeral — discarded at session end | [Foundry Guardrails](https://learn.microsoft.com/en-us/azure/foundry/guardrails/guardrails-overview) redact PII at input, output, tool-call, and tool-response intervention points before egress | Never crosses region — session runs in the jurisdiction's Hosted Agent |
| **Audit ledger** (every tool call, model call, enforcement decision, human interaction) | [Log Analytics](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/data-retention-archive) → Azure Storage immutable export | 7–12 years, immutable via Azure Storage [immutability policies](https://learn.microsoft.com/en-us/azure/storage/blobs/immutable-policy-configure-version-scope) | Prompt/response bodies stored with Guardrails PII redaction applied; reasoning chain stored separately from the action ledger | Regional Log Analytics workspace per jurisdiction |
| **Telemetry** (OTEL spans, metrics, cost attribution) | Application Insights | 90 days (configurable to 2 years) | Span attributes carry workflow/phase/jurisdiction/model/token counts — **no prompt or response bodies** | Regional App Insights instance |

**Explicit separation**: the reasoning chain is never co-located with the action ledger. A non-revocable action's audit record carries the span ID that produced it, not the model's reasoning tokens. Auditors can trace cause and effect without the reasoning chain itself becoming the audit artefact.

**Prompt retention**: prompt and response bodies are never stored in App Insights. They land in Log Analytics only, after Guardrails redaction, and are accessible only to compliance operators via Sentinel with access logging.

### Human Interaction Model

Every human has a **personal agent (PA)** — a GHCP SDK agent surfaced in M365 Copilot via the [M365 Agents SDK](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/publish). The PA is a capability **layered on** M365 Copilot, not a replacement for it — where Copilot 365 entitles the user, the PA is available inside that existing Copilot experience. No new agent surface, no additional per-user licence beyond WPP's existing Copilot 365 entitlement. The PA knows the human's role, permissions, and context. It surfaces information, recommends actions, drafts outputs, and triggers workflows on behalf of the human. Humans make all decisions. The PA prepares and executes.

| Surface | How | Who |
|---------|-----|-----|
| **M365 Copilot (Teams)** | Each user's PA agent. Understands role context, surfaces relevant information proactively, triggers workflows OBO the user when instructed. | All WPP users |
| **Email (Adaptive Cards)** | PA composes Adaptive Card with context and recommendation. Human reviews and decides. Response routes back through PA. | Finance BP, approvers |
| **Control Plane UI** | A richer surface the PA uses when the situation requires more than a Teams message — fleet view, bulk approvals, drill-downs. The HR BP's PA IS the Fleet Manager. | HR BP, Fleet operators |
| **ServiceNow** | PA writes provisioning tasks via ServiceNow MCP. | IT Ops |
| **Web portal** | Custom web surface for external participants. | Candidates |
| **Voice** | GPT-Realtime as speech-to-speech front end. Tool calls to GHCP SDK backend for reasoning. | Candidates (screening) |

### Flow (Hiring Workflow)

1. **Hiring Manager's PA** surfaces a headcount gap based on Workday/Dataverse data: "There's an open Senior Data Engineer role. I've prepared a draft requisition — want me to kick off the hiring workflow?"
2. **Hiring Manager** reviews and approves. PA triggers the Durable Functions orchestration, acting OBO the manager.
3. **Durable Functions** starts the Budget & Job Design phase by invoking the corresponding MAF workflow as a durable activity. The MAF graph runs: a deterministic `fetch_headcount_context` executor pulls Workday/Dataverse data, an `agent_job_design` executor (GHCP SDK session with job-design skill) drafts the JD, a `validate_jd_schema` executor asserts structure, a `compute_budget_envelope` function finalises numbers. State is emitted back to DF.
4. **Durable Functions**: budget needs Finance BP approval → `wait_for_external_event` (zero compute, preserved across MAF workflow checkpoints via the durable task extension)
5. **Finance BP's PA** receives the approval request, presents it in Teams or via Adaptive Card with context and recommendation. Finance BP reviews and approves.
6. **PA** processes the decision, writes to state → `raise_event` → Durable Functions resumes and invokes the next-phase MAF workflow
7. **HR BP's PA** (Fleet Manager) monitors all workflows, proactively surfaces: "2 of your 20 workflows need attention. Workflow-456 has a compliance flag — here's what happened and my recommendation."
8. **HR BP** acts on the recommendation via Control Plane UI or directly in Teams. The other 18 workflows run autonomously.

---

## 4. API Centre & AI Gateway

[Azure API Center](https://learn.microsoft.com/en-us/azure/api-center/key-concepts) and [APIM AI Gateway](https://learn.microsoft.com/en-us/azure/api-management/genai-gateway-capabilities) together form a **single, cohesive control plane for everything addressable by an agent** — models, MCP tools, A2A agents, skills, and APIs. One pane, one policy engine, one audit trail.

### What flows through this layer

| Asset class | API Center role | APIM AI Gateway role |
|-------------|----------------|---------------------|
| **LLM endpoints** (Foundry models, third-party) | Model registry, version metadata, jurisdiction tags | [Load balancing & failover](https://learn.microsoft.com/en-us/azure/api-management/backends), spillover to alt regions, [token rate limits](https://learn.microsoft.com/en-us/azure/api-management/llm-token-limit-policy), [semantic caching](https://learn.microsoft.com/en-us/azure/api-management/azure-openai-semantic-cache-lookup-policy), [cost emission](https://learn.microsoft.com/en-us/azure/api-management/llm-emit-token-metric-policy), per-team/per-workflow budget control |
| **MCP tools** | Tool catalogue with metadata, lifecycle, allowed-skill matrix | Auth injection, rate limiting, [content safety](https://learn.microsoft.com/en-us/azure/api-management/llm-content-safety-policy), [discovery](https://learn.microsoft.com/en-us/azure/api-management/mcp-server-overview), [REST→MCP auto-generation](https://learn.microsoft.com/en-us/azure/api-management/export-rest-mcp-server) |
| **A2A agents** | Agent card registration, capability discovery | [JSON-RPC mediation, policy enforcement, SSE/gRPC transport](https://learn.microsoft.com/en-us/azure/api-management/agent-to-agent-api) (preview) |
| **Skills** | SKILL.md lifecycle (Design → Preview → Production → Deprecated), GitHub Actions sync, allowed-tools governance | Per-skill tool allow-list enforcement at runtime |
| **APIs** (REST, OpenAPI) | OpenAPI registry, cross-cloud discovery (Azure / GCP / AWS / on-prem) | Standard APIM governance: auth, throttling, transformation |
| **Foundry IQ knowledge bases** | Registered as discoverable retrieval endpoints | Uniform auth + audit for grounding calls |
| **[AG-UI](https://learn.microsoft.com/en-us/agent-framework/user-interface/ag-ui/overview) event streams** | Registered as agent surface streams with component schema | APIM mediates the SSE stream, enforces auth and rate limits, audits connection lifecycle |
| **Structured output schemas** | Registered alongside skills — each skill declares its output JSON Schema | APIM validates responses against the declared schema before forwarding; schema violations are logged and surfaced to Fleet Manager |

### Why this matters for WPP

- **Cost control at scale**: 500 concurrent workflows × 30 markets means token spend is operational risk. APIM's per-model/per-team/per-workflow token metrics + budget enforcement is the only sane way to cap this. (Refs 26.1, 26.4)
- **Cross-cloud discovery**: API Center registers MCP servers, skills, and APIs hosted **anywhere** — Azure-hosted Foundry models, GCP-hosted Vertex agents, AWS-hosted internal APIs, on-prem SAP. Single registry, single discovery endpoint for agents. (Refs 8.13, 22.4, 33.3)
- **Jurisdiction routing**: APIM routes a German workflow to an EU-only model endpoint without the agent needing to know the model topology. Policy lives in the gateway, not the agent code. (Ref 32.1)
- **DR & spillover**: model-level load balancing across regions, automatic failover when a region degrades, no agent restarts needed.
- **One auditable record** of every model call, tool call, A2A handoff, and skill invocation — feeds Log Analytics for the 7-12 year retention requirement. (Ref 10.5, 32.3)
- **Policy-as-code**: APIM policies version-controlled via [APIOps CI/CD](https://learn.microsoft.com/en-us/azure/api-management/devops-api-development-templates). Skill and tool registrations in API Center synced from Git. Governance changes go through PR review. (Ref 21.4)

This addresses **Refs 8.13, 8.16, 22.1-22.6, 26.1-26.4, 32.1-32.3** in one architectural primitive.

---

## 5. Intelligence Layer

Agents need three kinds of grounding: **enterprise documents** (policy, law, SOPs), **business semantics** (what entities exist, how they relate, what rules apply), and **work context** (who collaborates with whom, what's currently in flight). Microsoft now has a purpose-built product for each, and all three are MCP-addressable — meaning they sit behind APIM AI Gateway alongside any other tool, governed identically.

| Product | Role | Status | Skills/Agents that consume it |
|---------|------|--------|-------------------------------|
| **[Foundry IQ](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/what-is-foundry-iq)** | Unified agentic retrieval over enterprise corpora. Self-reflective query planner with configurable "retrieval reasoning effort". Federates SharePoint, Fabric, OneLake, Blob, AI Search, web, and MCP behind one endpoint. Permission-aware. Built on Azure AI Search. | Public preview | **Compliance Agent** (right-to-work, EU AI Act, GDPR), **Job Design** (comp benchmarking, role profiles), **Skill Amplification** (Fleet Manager surfacing precedents and policy to operator), **Onboarding** (Day-1 plan templates) |
| **[Fabric IQ](https://learn.microsoft.com/en-us/fabric/iq/overview)** | Semantic intelligence layer over WPP's Fabric / OneLake estate: business **ontology** (entities + relationships + rules), **semantic model** (BI definitions extended to AI), **graph engine** for multi-hop reasoning, **data agents** and **operations agents**. | Public preview | **Budget Agent** (headcount, cost-centre, agency hierarchy), **ROI reporting**, **Process Evolution** (detect inefficiencies after N workflows), **cross-entity reasoning** (matrix navigation: role in Media, budget from WPP Corp) |
| **[Work IQ](https://learn.microsoft.com/en-us/microsoft-copilot-studio/use-work-iq) (MCP)** | M365 work graph + memory layer behind Copilot. Three layers: data (M365, D365, Power Platform), context/memory (collaboration patterns, expertise, work velocity), skills & tools. Exposed to custom agents via MCP servers. | Preview | **Personal Agents** (every PA's grounding for "who is this person, what do they care about"), **Interview Coordinator** (timezone, availability, calendar patterns), **Org Topology / Escalation** (who has authority, who's reachable, who's the SME) |

### How agents use them

- A loop loads a skill (e.g. `compliance.right-to-work-DE`)
- The skill declares an MCP tool dependency on `foundry-iq:de-employment-law` (a knowledge base registered in Foundry IQ)
- The loop's tool call goes through APIM AI Gateway, which authenticates via the Hosted Agent's Entra Agent ID, applies content safety, logs to App Insights, and forwards to Foundry IQ
- Foundry IQ plans a multi-source retrieval (BetrVG corpus + GDPR consent guidance + WPP DE handbook), synthesises with citations, returns
- The loop reasons over the result and acts

The **substrate** for Foundry IQ is Azure AI Search, but agents address Foundry IQ, not raw AI Search — the agentic retrieval planner is the value-add.

### Bridging WPP's existing data estate (Databricks, Snowflake)

WPP's data estate runs on Databricks and Snowflake (§5.1 of the RFP). Our intelligence layer integrates with both **without requiring migration**. Three patterns, in order of preference:

**1. Fabric IQ federation via OneLake shortcuts**. [OneLake shortcuts](https://learn.microsoft.com/en-us/fabric/onelake/onelake-shortcuts) provide zero-copy, zero-movement access to Databricks Unity Catalog tables and Snowflake external tables. Fabric IQ's semantic layer reasons over this data in-place — no ETL, no duplication, no lineage fracture. Budget Agent, ROI Agent, and analytics workflows query WPP's Databricks / Snowflake estate through Fabric IQ as if it were native. [Unity Catalog](https://learn.microsoft.com/en-us/fabric/onelake/onelake-shortcuts-unity-catalog)'s fine-grained access control is preserved through the shortcut — a user who cannot read a Unity Catalog table cannot read it via Fabric either.

**2. Direct MCP servers for operational SQL access**. For workloads that need direct query access (ad-hoc analytics, custom data pipelines, exploratory reasoning), purpose-built MCP servers for [Databricks SQL Warehouse](https://learn.microsoft.com/en-us/azure/databricks/sql/) and Snowflake are exposed via APIM. Agent executors query structured and unstructured data in Databricks / Snowflake directly, governed identically to all other MCP tools — auth injection, rate limiting, content safety, audit.

**3. Fine-tuneable analytics models in-place**. Analytics models fine-tuned on WPP's data stay where the data lives. Models deployed on Databricks (via [MLflow](https://learn.microsoft.com/en-us/azure/databricks/mlflow/) + Model Serving) or Snowflake ([Snowpark Container Services](https://docs.snowflake.com/en/developer-guide/snowpark-container-services/overview) / [Cortex](https://docs.snowflake.com/en/guides-overview-ai-features)) are callable as MCP tools through APIM. This addresses the §6.3 Advanced requirement for "Fine-tuneable analytics models to run Analytics agents on structured and unstructured data (Databricks, Snowflake, file stores)" without forcing model relocation.

**4. Inference-side federation (optional)**. Where WPP's data teams require agent inference to stay *inside* their data platform, [Databricks Mosaic AI Gateway](https://www.databricks.com/product/ai-gateway) and [Snowflake Cortex](https://docs.snowflake.com/en/guides-overview-ai-features) are callable as MCP tools through APIM. The APIM policy layer, audit trail, and governance model are identical — a Databricks-hosted model call is governed the same as a Foundry model call.

**Positioning**: Fabric IQ is the semantic / ontology layer *over* WPP's existing data estate, not a replacement for it. Databricks and Snowflake remain the systems of record; Fabric IQ provides the business ontology, semantic model, and graph engine that agents need to reason across them.

### Mapping to WPP requirements

| Ref | Requirement | Covered by |
|-----|------------|-----------|
| 6.3 | Learning from past interactions and human feedback | Work IQ memory + Fabric IQ ontology updates |
| 16.1 | Tiered memory | Work IQ (working/episodic) + Foundry IQ (semantic/factual) + Fabric IQ (procedural/business rules) |
| 16.4 | Grounding in knowledge bases, document stores, databases, APIs | Foundry IQ (one endpoint, all sources) |
| 23.1 | Process mining from email, docs, system interactions, meetings | Work IQ |
| 25.1-25.3 | Org topology, escalation, cross-entity navigation | Work IQ + Fabric IQ graph engine |
| 28.1, 28.3 | Document comprehension + quantitative reasoning | Foundry IQ + Fabric IQ |

---

## 6. Fleet Manager Agents

Domain-scoped GHCP SDK Hosted Agents that govern other agents. WPP cannot manage fleet-scale agentic operations relying on human eyes alone — agentic governance is required.

**Multiple instances by domain**: hiring fleet manager, finance fleet manager, compliance fleet manager. Each scoped to its domain's telemetry and workflows. If one degrades, its domain falls back to unfiltered view while others continue.

**Inputs**: telemetry events from DF orchestrations, MAF workflow executors, and GHCP SDK sessions via Event Grid. Enforcement events from Foundry Guardrails, MAF validators, and APIM.

**Outputs**: fleet health assessment, prioritised exception queue, contextual recommendations, compliance alerts — pushed to Control Plane UI via SignalR.

**What the operator sees**: Fleet Manager's assessment. Exception-only view — only flagged workflows are visible. For each: what happened, why it stopped, recommended action, options. Bulk approval queue for batched low-risk decisions. Autonomy dials for per-workflow thresholds.

Delivers WPP's Refs 31.1-31.5: exception-only surfacing, situational awareness, skill amplification, AI-driven prioritisation.

---

## 7. Workflow Durability & Execution

Three cooperating substrates, connected by Microsoft's [**Durable Agent Orchestration**](https://learn.microsoft.com/en-us/agent-framework/tutorials/agents/orchestrate-durable-agents) pattern (Feb 2026): Durable Functions + MAF + SignalR. This is the Microsoft-productised approach for long-running agent workflows with HITL waits.

**Azure Durable Functions — the outer envelope**: event routing across phases, HITL waits (zero compute, days/weeks), timer escalation, parallel coordination, checkpoint/replay, geo-replicated state. Durable Functions does **not** execute reasoning, tool calls, or skills — it coordinates.

**MAF workflow — the per-phase graph**: each phase is a MAF workflow graph of typed executors. The [MAF durable task extension for Azure Functions](https://learn.microsoft.com/en-us/agent-framework/integrations/azure-functions) lets a DF orchestrator invoke a MAF workflow as a durable activity. MAF's own checkpointing is preserved across DF replay — conversation context and workflow state persist automatically. Most executors are plain Python/C# functions (deterministic). Agent executors delegate to GHCP SDK sessions. Validator executors enforce structural and policy constraints between nodes.

**GHCP SDK sessions — inside agent executors**: ephemeral sessions that load skills and MCP tools, reason, call tools through hooks, emit OTEL, and return a typed result to the MAF executor.

**Why both Durable Functions *and* Foundry Hosted Agents (they are not alternatives)**. This is a common question. Hosted Agents is the agent *runtime* — a container hosting the GHCP SDK session, exposing the Responses API, giving Foundry a uniform surface for evaluation, guardrails, tracing, and scaling. Durable Functions is the business-process *envelope* — it owns the multi-week lifecycle, the zero-compute HITL waits, the compensating actions, the timer escalation, and the geo-replicated state. Hosted Agents cannot wait eight weeks at zero compute for a Finance BP approval, because a hosted agent session is ephemeral. Durable Functions can, because it is event-sourced and replay-based. Microsoft's own [Durable Agent Orchestration](https://learn.microsoft.com/en-us/agent-framework/tutorials/agents/orchestrate-durable-agents) pattern composes both — DF as the envelope, Hosted Agents (or local GHCP SDK sessions) as the runtime inside MAF agent executors. WPP's 12-week hiring process and 8-week P2P workflows require this composition; neither layer alone is sufficient.

**Workflow state store** ([Cosmos DB](https://learn.microsoft.com/en-us/azure/cosmos-db/introduction) / Dataverse): phase state, context, candidate data, approval records, append-only action ledger (revocable/non-revocable tracking), OTEL span summaries. Cosmos DB provides [multi-region writes with automatic failover](https://learn.microsoft.com/en-us/azure/cosmos-db/multi-region-writes) and [continuous backup with point-in-time restore](https://learn.microsoft.com/en-us/azure/cosmos-db/continuous-backup-restore-introduction).

**HITL pattern**: a MAF workflow executor detects human input is needed → composes contextual message/Adaptive Card → routes it to the appropriate human via their preferred surface → signals DF to suspend. DF issues `wait_for_external_event` at zero compute. Human responds → response triggers `raise_event` → DF resumes, invokes the resumption MAF workflow to process the decision → next phase begins. Bulk approval raises events on multiple DF instances simultaneously. MAF workflows also support their own native pause/resume for shorter-lived HITL within a phase ([MAF human-in-the-loop](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/building-human-in-the-loop-ai-workflows-with-microsoft-agent-framework/4460342)).

**Execution model**: MAF workflows use a Pregel-based Bulk Synchronous Parallel (BSP) execution model — supersteps collect pending messages, route to target executors per edge definitions, run all target executors concurrently, wait for completion before advancing. This makes parallel phases and fan-out/fan-in deterministic and inspectable. Combined with MAF's stable [orchestration patterns](https://learn.microsoft.com/en-us/agent-framework/workflows/) (sequential, concurrent, handoff, group chat, Magentic-One), this covers the multi-agent topologies WPP requires without bespoke coordination code.

---

## 8. Observability

| Layer | Source | Purpose |
|-------|--------|---------|
| **[Foundry Tracing](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/trace-agent-setup) (OTEL)** | Every GHCP SDK session (inside MAF agent executors) emits via [GHCP SDK OTEL](https://github.com/github/copilot-sdk/blob/main/docs/observability/opentelemetry.md) TracerProvider. MAF workflow execution spans are emitted natively. | Raw telemetry: executor lifecycle, model calls, tool calls, tokens, latency, cost. Drill-down for situational awareness. [Foundry Agent Monitoring Dashboard](https://learn.microsoft.com/en-us/azure/foundry/control-plane/monitoring-across-fleet) out-of-box. |
| **APIM AI Gateway metrics** | [Token usage](https://learn.microsoft.com/en-us/azure/api-management/llm-emit-token-metric-policy), latency, errors per model/tool/agent | Central cost tracking and rate limit monitoring across all AI assets. |
| **Fleet Manager assessment** | Event-driven reasoning over telemetry | Intelligent layer: fleet health, anomaly detection, SLA risk, exception prioritisation. Default Control Plane view. |

OTEL spans carry workflow ID, phase, jurisdiction, model, token count. Cost attribution per workflow, phase, model, and consumer visible in Control Plane and Foundry dashboards.

---

## 9. Compliance & Governance — Five Enforcement Layers

Compliance is enforced externally and structurally. The LLM cannot bypass these.

| Layer | Technology | Status | Enforcement |
|-------|-----------|--------|-------------|
| **MAF workflow validators** | Validator executors in the [MAF workflow graph](https://learn.microsoft.com/en-us/agent-framework/workflows/) between agent executors | GA (MAF v1.0) | Structural and policy enforcement inside the graph. A validator executor downstream of an agent executor asserts schema, checks against policy tables, runs deterministic rule engines, and routes to a rejection branch if violated. Judge/executor context separation is expressed as two nodes and an edge — the judge does not share the executioner's context. |
| **[Foundry Guardrails](https://learn.microsoft.com/en-us/azure/foundry/guardrails/guardrails-overview)** | Tool call/response interception, PII detection, [Task Adherence](https://learn.microsoft.com/en-us/azure/foundry/guardrails/how-to-task-adherence) | Preview | Intercepts tool calls before execution. Blocks PII in outputs. Detects policy drift from system message. [Four intervention points](https://learn.microsoft.com/en-us/azure/foundry/guardrails/intervention-points): input, output, tool-call (preview), tool-response (preview). Complements MAF validators: Guardrails operate inside the agent executor's GHCP SDK session; MAF validators operate outside, on the typed result. |
| **APIM AI Gateway** | Model routing, content safety, token limits | GA | Jurisdiction-based model routing (DE workflow → EU endpoint only). `llm-content-safety` policy. Token rate limiting. Semantic caching. All MCP tool calls governed (auth, rate limits, content filtering). |
| **[Agent 365](https://learn.microsoft.com/en-us/security/security-for-ai/agent-365-security) + [Entra](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/what-is-agent-id)** | Identity, access control, DLP, threat detection | GA May 2026 | Per-agent tool access via RBAC on downstream resources. [Conditional Access policies on agent identities](https://learn.microsoft.com/en-us/entra/identity/conditional-access/agent-id). [Purview DLP on agent interactions](https://learn.microsoft.com/en-us/purview/ai-agent-365). [Defender for threat detection](https://learn.microsoft.com/en-us/azure/defender-for-cloud/ai-threat-protection). |
| **Runtime isolation** | [Azure Private Endpoints](https://learn.microsoft.com/en-us/azure/private-link/private-endpoint-overview) + VNet integration + [Azure Firewall](https://learn.microsoft.com/en-us/azure/firewall/overview) egress allow-list + APIM as sole public edge | GA | All east/west traffic over Private Link; outbound to third-party SaaS restricted to named FQDNs; no direct internet from Hosted Agents or DF workers. Residency enforced by APIOps CI gate rejecting cross-region backends. See §3 "Network & Data Boundaries". |

**Policy-as-code**: APIM policies version-controlled via APIOps CI/CD. Foundry Guardrails configured per agent. Jurisdiction-specific skills define compliance rules declaratively.

**Jurisdiction switching**: workflow state carries `jurisdiction`. APIM routes to region-appropriate model endpoint. Foundry Guardrails enforce PII and content safety universally. Jurisdiction-specific skills (right-to-work, works council, GDPR consent) load automatically based on workflow context. Task Adherence guardrail catches drift from jurisdiction policy in the system message.

**Audit**: [Azure Log Analytics](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/data-retention-archive) with archive tier (7-12yr retention; immutability enforced via Azure Storage export with immutability policies). Every tool call, model call, enforcement decision, and human interaction logged. Queryable via Log Analytics and [Microsoft Sentinel](https://learn.microsoft.com/en-us/azure/sentinel/quickstart-onboard).

**Platform certifications**: the Azure services in this architecture inherit [SOC 1 / SOC 2 Type II / SOC 3](https://learn.microsoft.com/en-us/compliance/regulatory/offering-soc), [ISO/IEC 27001](https://learn.microsoft.com/en-us/compliance/regulatory/offering-iso-27001), [ISO/IEC 27017](https://learn.microsoft.com/en-us/compliance/regulatory/offering-iso-27017), [ISO/IEC 27018](https://learn.microsoft.com/en-us/compliance/regulatory/offering-iso-27018), [ISO/IEC 27701](https://learn.microsoft.com/en-us/compliance/regulatory/offering-iso-27701), [HIPAA](https://learn.microsoft.com/en-us/compliance/regulatory/offering-hipaa-hitech), [PCI DSS Level 1](https://learn.microsoft.com/en-us/compliance/regulatory/offering-pci-dss), [FedRAMP High](https://learn.microsoft.com/en-us/compliance/regulatory/offering-fedramp), [GDPR](https://learn.microsoft.com/en-us/compliance/regulatory/gdpr), and the [BSI C5](https://learn.microsoft.com/en-us/compliance/regulatory/offering-c5-germany) attestation used in Germany. EU AI Act alignment is maintained through Microsoft's [Responsible AI Standard](https://www.microsoft.com/en-us/ai/principles-and-approach), Foundry Guardrails' classifier coverage of high-risk categories, and built-in evaluators for bias and safety. The authoritative compliance matrix sits in the [Microsoft Trust Center](https://www.microsoft.com/en-us/trust-center). WPP's SOC 2 readiness and GDPR evidence inherit from these attestations — no bespoke security certification is required at the WPP application layer.

**Encryption**: TLS 1.2+ enforced on all ingress and east/west traffic; TLS 1.3 where supported. At-rest encryption defaults to Microsoft-managed keys, with [Customer-Managed Keys (CMK) via Azure Key Vault](https://learn.microsoft.com/en-us/azure/key-vault/keys/customer-managed-keys) available for Cosmos DB, Log Analytics, AI Search, Storage, and Foundry — recommended for regulated jurisdictions. Azure Storage supports [double encryption](https://learn.microsoft.com/en-us/azure/storage/common/infrastructure-encryption-enable) (service + infrastructure layer) for the immutable audit export. Key rotation is automated via Key Vault; credentials are never seen by agent code — APIM injects them at request time from Key Vault references.

**Multi-factor authentication**: enforced by [Entra Conditional Access](https://learn.microsoft.com/en-us/entra/identity/conditional-access/overview) on every human-triggered path — operators accessing the Control Plane UI, business partners approving via their PA, and platform engineers making governance changes. Phishing-resistant methods ([FIDO2 security keys, Windows Hello, Microsoft Authenticator with number matching](https://learn.microsoft.com/en-us/entra/identity/authentication/concept-authentication-strengths)) are required; SMS and voice MFA are explicitly blocked via Authentication Strengths policy. Agent-triggered actions use managed identities, not interactive credentials — there is no shared secret an attacker could phish.

---

## 10. Builder Experience

All agent artefacts — pro-code, low-code, Threadlight-generated, runtime-spawned — are declarative, Git-committable, and flow through the same APIOps governance pipeline. This is how we meet §6.5 "Low-code artefacts must serialise to the same code/config format as pro-code artefacts": every path produces versioned, reviewable artefacts that register in Azure API Center, are governed by APIM, and carry Entra Agent IDs — regardless of which surface built them.

| Requirement | Approach |
|-------------|---------|
| Pro-code SDK (Must) | [GHCP SDK](https://github.com/github/copilot-sdk) Python (primary) + TypeScript / .NET / Go for [skills](https://github.com/github/copilot-sdk/blob/main/docs/features/skills.md) and [MCP servers](https://github.com/github/copilot-sdk/blob/main/docs/features/mcp.md). MAF for workflow graphs in Python or .NET. |
| **Low-code visual builder (Must)** | **[Microsoft Copilot Studio](https://learn.microsoft.com/en-us/microsoft-copilot-studio/)**: Microsoft's flagship low-code agent builder. Visual drag-and-drop designer for conversational and workflow agents — conditional branching, tool bindings (Power Platform connectors + MCP), HITL touchpoints, knowledge grounding. Suitable for citizen developers and domain experts. Agents are exported as declarative YAML / JSON within Power Platform solutions, Git-committable via [Power Platform ALM](https://learn.microsoft.com/en-us/power-platform/alm/overview-alm), versioned through environments (Dev → Test → Prod), and deployed through the same governance pipeline as pro-code agents. Copilot Studio agents register in Agent 365 with first-class Entra Agent ID, are governed by APIM, Purview, and Defender, and appear alongside GHCP SDK agents in the Control Plane. This is how Copilot Studio meets §6.5 parity: declarative serialisation + Git-committable + same governance pathway. For complex autonomous multi-step workflows that need deterministic graph primitives, pro-code (GHCP SDK + MAF) remains the recommended path; Copilot Studio excels at the breadth of citizen-developer scenarios. |
| Low-code MCP servers | **[Azure Logic Apps](https://learn.microsoft.com/en-us/azure/logic-apps/logic-apps-overview)** exposed as MCP tools via APIM's [REST→MCP gateway](https://learn.microsoft.com/en-us/azure/api-management/export-rest-mcp-server). Gives WPP IT teams a no-code path to add new tools (SharePoint → email, Outlook trigger → Dataverse write, 1,400+ prebuilt connectors) without touching Python. Logic Apps is **not** an orchestrator here — DF owns workflow state — Logic Apps is a tool/integration primitive sitting at the same layer as hand-written MCP servers behind APIM. |
| Low-code configuration (Must) | Custom Control Plane UI: skill library (browse, fork, customise skills backed by Azure API Center), tool catalogue (APIM), governance editor, autonomy dials, template fork-and-customise. For operational configuration (threshold tuning, template deployment, fleet management) by process owners — not agent construction itself. All changes written back to Git through APIOps. |
| **60-minute build benchmark (§6.4)** | Copilot Studio hits this benchmark natively: citizen developer picks a template, adds 3 MCP tool connectors from the APIM-governed catalogue (pre-wired auth, rate limits, content safety), adds 3 knowledge sources from Foundry IQ, publishes to Agent 365. End-to-end build time: **<30 minutes** for a junior developer or seasoned UI user. The Control Plane UI template forge provides a parallel path for operators wanting to consume pre-wired pro-code templates. Scripted as an observable task for POC evaluation. |
| **Agentic builder (§9 / §6.2 design-time)** | A MAF agent executor generates new SKILL.md files from natural-language specifications. Output is a typed skill definition with declared tools, model assignment, and governance rules. Registered in API Center in Design state. Human reviews and approves to promote to Production. **Built and demonstrated.** |
| **Runtime agent assembly (§6.2 runtime)** | MAF supports dynamic executor creation at runtime — a supervising agent executor can spawn a sub-workflow or a persistent sub-agent within a domain's Hosted Agent scope. For persistent spawned agents, a governance-gate callback auto-registers the new agent in [Entra Agent ID](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/what-is-agent-id) and [API Center](https://learn.microsoft.com/en-us/azure/api-center/key-concepts) (skill in Design state), and writes the spawning decision to the audit ledger. The agent runs in the ephemeral (Design) state until a human operator promotes it to Production — enforcing the RFP's requirement that "persistent agents must be elevated into the same Data Plane storage schema as human-built agents, along the governance pathway." No runtime escape from governance. |
| Template library (Should) | Pre-built skill sets and workflow templates in Git. API Center integrates with GitHub Actions for syncing `skill.md` files from repos. Forkable and customisable. Initial library covers the POC1 / POC2 skills and ~20 common enterprise patterns. |
| **Knowledge extraction (Could) — Threadlight** | **Threadlight** is a Microsoft delivery accelerator, built and demonstrated. It is an interview-capture agent that runs alongside an SME, transcribes and structures the conversation, and produces executable artefacts: SKILL.md files, MAF workflow graphs, and MCP tool stubs with declared schemas. Output enters the same governance pathway as hand-written skills — API Center Design state, human review, promotion to Production. The accelerator closes the gap between "the SME knows how to do it" and "the system can do it" without writing code. Not a black-box service: the artefacts are SKILL.md / Python / YAML, fully inspectable and Git-committable. |

Skills registered in Azure API Center have lifecycle management (Design → Preview → Production → Deprecated), declared allowed tools, and GitHub Actions integration for `skill.md` files. Every artefact — pro-code, low-code UI, Threadlight-generated, runtime-spawned — lands in the same Git repository and flows through the same APIOps pipeline. **One truth for how an agent is defined, regardless of who built it.**

---

## 11. Control Plane — Two Layers

### Foundry Control Plane (platform governance)

Foundry Control Plane provides the platform-level management layer. It is an existing product, not custom build:

- Fleet health dashboards: active agents, run completion rates, compliance posture, cost efficiency, prohibited behaviours
- Agent inventory across all platforms (Foundry-native, custom, external) with lifecycle operations
- Model registry with quota management
- Tool registry with APIM governance
- Continuous evaluation and monitoring with deep links for debugging
- Compliance enforcement (guardrails configuration)
- Integration with Defender (threat detection) and Purview (DLP)

This covers WPP's requirements for agent registry (8.5), model registry (8.1), observability (8.14), agent lifecycle (22.3), and compliance posture monitoring.

### Custom Control Plane UI (operator experience)

Foundry Control Plane monitors the platform. WPP's requirements go further — they need an operator experience where 1 human governs 20-50 concurrent workflows with intelligent exception surfacing. This requires a custom React application powered by the Fleet Manager agent:

| Capability | Why custom | WPP Refs |
|-----------|-----------|----------|
| Fleet Dashboard (Fleet Manager's assessment) | Foundry shows platform health. WPP needs workflow-level status, SLA tracking, agency/market/jurisdiction filtering. Fleet Manager reasons about what to show. | 31.1 |
| Exception-Only Queue | Foundry does not filter to "the 2% needing attention." Fleet Manager composes this intelligently based on business impact, confidence, SLA urgency. | 31.2 |
| Instant Situational Awareness | Click any workflow → what agents did, what stopped progress, recommendations, options. Requires OTEL drill-down + Fleet Manager's contextual reasoning. <5 seconds. | 31.3 |
| Bulk HITL | Batch similar decisions (e.g., 8 interview schedules), approve in one action. Raises events on all waiting Durable Functions instances. | 31.4 |
| Autonomy Dials | Per-workflow threshold sliders (auto-shortlist %, HITL gates). Writes to config store, effective immediately. | 21.1 |
| Skill Amplification | Fleet Manager proactively surfaces relevant policy, precedents, recommended approach when operator is uncertain. Powered by Foundry IQ retrieval over WPP corpora. | 31.5 |
| Role-Based Operator Views | HR BP sees hiring workflows. Finance BP sees budget gates. IT Ops sees provisioning. RBAC-filtered. | 10.1 |
| Cost Dashboard | Per-workflow cost attribution from OTEL + APIM token metrics. | 26.4 |
| AG-UI dynamic components | The UI consumes [AG-UI](https://learn.microsoft.com/en-us/agent-framework/user-interface/ag-ui/overview) SSE streams from Fleet Manager and agent executors, rendering dynamic components (approval forms, charts, wizards) specific to each workflow type. No hardcoded UI per workflow. APIM mediates the stream. | 5.3 |

The custom UI consumes data from: **Application Insights APIs** (agent run traces, token usage, cost, error rates), **Foundry REST APIs** (agent inventory, model deployments), **APIM metrics** (token consumption, rate limit status per model/tool), **workflow state store** (Cosmos DB / Dataverse — phase status, approvals, action ledger), and **Fleet Manager agent assessments** (pushed via SignalR).

---

## 12. Voice, Video, Avatar

These are MCP tools and skills invoked from MAF agent executors when a phase needs them.

| Capability | Approach |
|-----------|---------|
| Voice screening | [GPT-Realtime](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/realtime-audio) as speech-to-speech front end. [ACS Call Automation](https://learn.microsoft.com/en-us/azure/communication-services/concepts/call-automation/call-automation) for telephony. [MAI-Transcribe-1](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/mai-transcribe) for transcription. [MAI-Voice-1](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/mai-voices) for TTS (preview). Tool calls to GHCP SDK backend for reasoning and scoring. |
| Video meeting notes | Teams bot joins meeting (Bot Framework, GA). Post-meeting transcript via Graph API MCP. A MAF agent executor processes the transcript into structured notes and scores via a downstream validator. Real-time in-meeting speaking achievable via ACS integration but primary value is intelligent note-taking. |
| Avatar onboarding | An agent executor drafts the personalised script; a downstream deterministic executor invokes the HeyGen API MCP to produce a branded video. Avatars configurable (appearance, voice, branding) and persistent across sessions. |

---

## 13. Component Summary

| Component | Technology | Role |
|-----------|-----------|------|
| Agent Runtime | [GHCP SDK](https://github.com/github/copilot-sdk) (MIT, Python/TypeScript) | Autonomous reasoning inside MAF agent executors: [skills](https://github.com/github/copilot-sdk/blob/main/docs/features/skills.md), [MCP tools](https://github.com/github/copilot-sdk/blob/main/docs/features/mcp.md), [hooks](https://github.com/github/copilot-sdk/blob/main/docs/features/hooks.md) |
| Hosting | [Foundry Hosted Agents](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents) | Containerised deployment, scaling. GHCP SDK wrapped in container exposing Responses API (custom adapter). |
| Workflow Graph | [Microsoft Agent Framework workflows](https://learn.microsoft.com/en-us/agent-framework/workflows/) (v1.0 GA, Python/.NET) | Per-phase deterministic graph of typed executors. Plain-function nodes, agent nodes, validator nodes. Pregel BSP execution, fan-out/fan-in, HITL hooks, pause/resume. |
| Durable Envelope | [Azure Durable Functions](https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-functions-overview) (GA) | Long-running orchestration: event routing, HITL waits at zero compute (days/weeks), timer escalation, checkpoint/replay, geo-replicated state. |
| DF ↔ MAF glue | [MAF Durable Task extension](https://learn.microsoft.com/en-us/agent-framework/integrations/azure-functions) | Productised pattern wiring MAF workflows as DF activities. Preserves MAF checkpoint state across DF replay. |
| Fleet Governance | Fleet Manager Agent (GHCP SDK) | Agentic monitoring, exception composition |
| API & AI Gateway | [APIM AI Gateway](https://learn.microsoft.com/en-us/azure/api-management/genai-gateway-capabilities) (GA) + [Azure API Center](https://learn.microsoft.com/en-us/azure/api-center/key-concepts) | Unified entry point for models, MCP tools, A2A agents, skills, APIs. Cross-cloud discovery. |
| **Knowledge & Grounding** | **[Foundry IQ](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/what-is-foundry-iq)** + **[Fabric IQ](https://learn.microsoft.com/en-us/fabric/iq/overview)** + **[Work IQ MCP](https://learn.microsoft.com/en-us/microsoft-copilot-studio/use-work-iq)** | Agentic retrieval, business semantic ontology, M365 work graph |
| Low-code MCP | [Azure Logic Apps](https://learn.microsoft.com/en-us/azure/logic-apps/logic-apps-overview) | Citizen-dev integrations exposed as MCP tools via APIM REST→MCP |
| Control Plane | Foundry Control Plane (GA) | Agent fleet management, evaluation, compliance |
| Agent Lifecycle | [Agent 365](https://learn.microsoft.com/en-us/microsoft-agent-365/overview) + [Entra Agent ID](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/what-is-agent-id) | Identity, RBAC. GA May 2026 — integration with Hosted Agents needs POC validation. Supports Copilot Studio agents natively. |
| Control Plane UI | Custom React | Fleet dashboard, HITL queue, autonomy dials |
| Observability | [Foundry Tracing](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/trace-agent-setup) (OTEL) + [GHCP SDK OTEL](https://github.com/github/copilot-sdk/blob/main/docs/observability/opentelemetry.md) | Telemetry, cost attribution |
| Evaluation | [Foundry Evaluators](https://learn.microsoft.com/en-us/azure/foundry/concepts/built-in-evaluators) | Task adherence, quality, safety, [continuous evaluation](https://learn.microsoft.com/en-us/azure/foundry/concepts/observability) |
| Compliance Layer 1 | Foundry Guardrails | Tool call/output interception, PII, task adherence |
| Compliance Layer 2 | APIM AI Gateway | Model routing, content safety, token limits |
| Compliance Layer 3 | Agent 365 + Entra | Identity, access control, DLP, threat detection |
| Human Surfaces | M365 Agents SDK + Custom UI | Copilot (Teams), Email (Adaptive Cards), Control Plane, Web, Voice |
| Integration | MCP Servers (via APIM) | Workday, Greenhouse, LinkedIn, ServiceNow, Graph, Dataverse, ACS, HeyGen |
| Skills | [SKILL.md](https://github.com/github/copilot-sdk/blob/main/docs/features/skills.md) + [Azure API Center](https://learn.microsoft.com/en-us/azure/api-center/key-concepts) | Declarative, composable, lifecycle-managed, GitHub Actions integration |
| Voice | GPT-Realtime + ACS | Speech-to-speech with agentic backend |
| Audit | [Azure Log Analytics](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/data-retention-archive) | 7-12yr retention (immutability via Azure Storage export) |
| Knowledge Extraction | **Threadlight** accelerator (Microsoft delivery) | Interview-based knowledge capture into SKILL.md + MAF workflow artefacts |
| **Dynamic UI protocol** | [AG-UI](https://learn.microsoft.com/en-us/agent-framework/user-interface/ag-ui/overview) over SSE, APIM-mediated | Agent-rendered components in the Control Plane — forms, charts, wizards composed at runtime |
| **Networking** | [Private Endpoints](https://learn.microsoft.com/en-us/azure/private-link/private-endpoint-overview) + VNet integration + [Azure Firewall](https://learn.microsoft.com/en-us/azure/firewall/overview) (egress) + [Front Door Premium](https://learn.microsoft.com/en-us/azure/frontdoor/private-link) (WAF ingress) | Runtime isolation: APIM is the sole public edge; east/west over Private Link; outbound to SaaS via FQDN allow-list |
| **Data Platform Bridge** | [OneLake shortcuts](https://learn.microsoft.com/en-us/fabric/onelake/onelake-shortcuts) to Unity Catalog / Snowflake; Databricks + Snowflake MCP servers; [Mosaic AI Gateway](https://www.databricks.com/product/ai-gateway) / [Snowflake Cortex](https://docs.snowflake.com/en/guides-overview-ai-features) as MCP | Federates WPP's existing Databricks + Snowflake estate without migration; fine-tuned analytics models stay in-place |

---

## 14. POC 1: Finance Procure-to-Pay

**Scope**: 30-50 concurrent invoice workflows managed by a Finance Controller via the Control Plane.

**Execution shape**: Durable Functions orchestration coordinates phase boundaries and HITL waits. Each phase is a MAF workflow graph. Most executors are plain functions; agent executors are used only where reasoning is required.

**Phases and executor types**:

| Phase | MAF executor type | Notes |
|-------|-------------------|-------|
| Intake / OCR | **Hybrid** | Azure Document Intelligence as a deterministic executor; `agent_field_extractor` (GHCP SDK) only for low-confidence fields. Validator executor asserts schema before forward. |
| Three-way match | **Deterministic** | Plain function: PO / GRN / invoice matching against tolerance rules. No LLM. |
| GL coding & cost centre | **Hybrid** | `agent_gl_coder` reasons over vendor, description, agency context; downstream validator confirms GL exists and cost centre is active. |
| Routing & approval gate | **Deterministic** | Threshold-based routing logic. HITL event raised to DF; zero-compute wait. |
| Payment file generation | **Deterministic** | Format-driven code. No LLM. Non-revocable action → GHCP SDK hook gates execution until human confirms. |
| Reconciliation | **Hybrid** | Deterministic bank statement match; `agent_exception_classifier` only for unmatched items. |

**MCP integrations**: Workday, Dynamics 365 F&O, Maconomy — all governed through APIM AI Gateway.

**Grounding**: Fabric IQ for cost-centre / agency hierarchy / budget semantics; Foundry IQ for vendor master data, purchasing policy, and tax-rule corpora.

**Demonstrates**: deterministic-by-default MAF workflow graph, HITL approval gates (Finance BP interacts via Adaptive Card in Outlook, routed through PA), bulk approval for batched low-risk items, rollback/compensating actions, Fleet Manager monitoring 30-50 concurrent workflows, exception-only Control Plane view, OTEL cost attribution per invoice, Foundry Guardrails inside agent executors, MAF validator executors between agent and non-revocable executors, DF replay across restart.

---

## 15. POC 2: HR Talent Lifecycle

**Scope**: 15-20 concurrent hiring workflows managed by an HR Business Partner via the Control Plane. Five human participants across four timezones.

**Execution shape**: the 12-week hiring process is a Durable Functions orchestration with ~10 phases. Each phase is a MAF workflow graph — mostly deterministic executors, agent executors where reasoning is genuinely required, validator executors between them. DF owns the long waits between phases; MAF owns the graph shape within a phase.

**Phases and executor types**:

| Phase | MAF executor type | Notes |
|-------|-------------------|-------|
| Budget & approvals | **Deterministic** | Threshold routing, Fabric IQ lookups. HITL gate to Finance BP via DF `wait_for_external_event`. |
| Job design | **Hybrid** | `agent_jd_drafter` (GHCP SDK + Foundry IQ for comp benchmarking); `validate_jd_completeness` asserts structure. |
| Sourcing | **Deterministic** | Greenhouse + LinkedIn MCP queries by criteria. No LLM required. |
| CV triage / screening | **Agentic with validator** | `agent_cv_scorer` reasons over CV; `validate_bias_markers` downstream executor runs deterministic bias checks and flags to Fleet Manager. **Crystallisation target**: after N workflows, promote to a deterministic classifier + agent fallback for low-confidence cases. |
| Voice screening | **Agentic** | GPT-Realtime + ACS as the executor; structured scoring validator downstream. |
| Interview coordination | **Deterministic** | Work IQ for timezone/calendar; plain scheduling logic. |
| Compliance (jurisdiction-aware) | **Hybrid** | `agent_compliance_narrative` for right-to-work / works council interpretation; deterministic rule executors (GDPR consent checklist, EU AI Act classifier); Task Adherence guardrail detects drift from jurisdiction policy. |
| Offer letter | **Hybrid** | Template-based deterministic generation; `agent_personaliser` for narrative sections only. Non-revocable send gated by GHCP SDK hook → human approval. |
| JML onboarding | **Deterministic** | ServiceNow ticket creation via MCP. Plain executor. |
| Avatar welcome video | **Hybrid** | Agent drafts script; HeyGen MCP deterministic generation. |

**MCP integrations**: Greenhouse ATS, LinkedIn Recruiter, Workday (hiring), Microsoft Graph (calendar/email), ServiceNow (IT provisioning), Azure Communication Services (voice), HeyGen (avatar) — all governed through APIM AI Gateway.

**Grounding**: Foundry IQ for jurisdiction-specific employment law (US vs DE corpora), GDPR consent guidance, WPP people handbooks; Fabric IQ for headcount, comp bands, agency hierarchy, levelling history (episodic memory of past hires); Work IQ for calendar/timezone/availability and org topology (escalation routing).

**Human surfaces**: Hiring Manager via M365 Copilot in Teams (agent surfaced via M365 Agents SDK), Finance BP via email Adaptive Cards, candidate via web portal + voice, IT Ops via ServiceNow, HR BP via Control Plane.

**Demonstrates**: all POC 1 capabilities plus — voice screening with structured scoring, CV parsing with crystallisation pipeline (agent executor → deterministic classifier in API Center), episodic memory from workflow state store + Fabric IQ (recall past hires levelled too low), A2A interop with external candidate agent (governed via APIM), jurisdiction-aware compliance (USA vs Germany enforcement switching via APIM routing + jurisdiction-specific skills + Foundry IQ corpora + Foundry Guardrails), MAF validator executors separating agent judgement from downstream action, autonomy dials (configurable auto-shortlist thresholds), skill amplification (Fleet Manager surfaces policy + precedents via Foundry IQ), process evolution (Fleet Manager proposes crystallisation candidates after completed workflows), synthetic CV evaluation (500 CVs via Foundry Evaluators), avatar onboarding video, **Threadlight** knowledge extraction demo (interview HR SME, produce executable skills).

---

## 16. Known Constraints

The stack separates a **GA foundation** from a **replaceable agent runtime layer**. The foundation — Azure Durable Functions, APIM AI Gateway, Azure API Center, Cosmos DB, Azure AI Foundry runtime, Microsoft Agent Framework v1.0, Entra, Log Analytics, Application Insights — is GA and production-proven. The agent runtime layer is GHCP SDK today; because skills are SKILL.md files and tools are MCP servers (both open standards), the agent runtime is **replaceable without redesigning the stack**. If GHCP SDK ever stalls or WPP wants a different runtime, swap the runtime — the skills, tools, workflow graphs, governance, and data layer all remain. This is the honest framing of the preview-dependency question.

| Constraint | Impact | Mitigation |
|-----------|--------|-----------|
| GHCP SDK in tech preview | API surface may change | Core patterns ([skills](https://github.com/github/copilot-sdk/blob/main/docs/features/skills.md), [MCP](https://github.com/github/copilot-sdk/blob/main/docs/features/mcp.md), [hooks](https://github.com/github/copilot-sdk/blob/main/docs/features/hooks.md)) are GA inside GitHub Copilot's production runtime serving millions of developers daily. SDK is the same code, MIT-licensed. Replaceable: if needed, skills (SKILL.md) and MCP tools port to any MCP-native runtime without redesign. |
| [Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/overview/) v1.0 released Oct 2025 | Framework is young | MAF v1.0 is GA for the core runtime and workflows. [Durable task extension](https://learn.microsoft.com/en-us/agent-framework/integrations/azure-functions) for Azure Functions is productised by Microsoft as the [Durable Agent Orchestration](https://learn.microsoft.com/en-us/agent-framework/tutorials/agents/orchestrate-durable-agents) pattern. Orchestration patterns (sequential, concurrent, handoff, group chat, Magentic-One) are stable. Fallback: the GHCP SDK + Durable Functions combination works without MAF — MAF adds the deterministic graph primitive. |
| Foundry Hosted Agents: max 5 replicas per deployment (preview) | Scaling ceiling | Multiple deployments, or Azure Container Apps with Foundry telemetry. Preview limit expected to increase at GA. |
| [Foundry Guardrails](https://learn.microsoft.com/en-us/azure/foundry/guardrails/guardrails-overview) tool call interception (preview) | May not be GA for POC | GHCP SDK session hooks provide equivalent enforcement at code level. Guardrails are additive. |
| [APIM A2A agent governance](https://learn.microsoft.com/en-us/azure/api-management/agent-to-agent-api) (preview) | A2A features still maturing. A2A is not required for core architecture — only for POC2 external candidate agent demo. | HTTP gateway primitives work today. Purpose-built A2A policies emerging. |
| Skills in [Azure API Center](https://learn.microsoft.com/en-us/azure/api-center/key-concepts) (preview) | Skill registry is new. API Center does not have native Git sync — uses GitHub Actions workflows. | Core skill execution is GHCP SDK native. API Center adds governance layer. |
| GHCP SDK + Foundry Hosted Agents integration not documented | Hosting adapter needs custom work | Hosted Agents accept any container image that exposes the Responses API protocol. The adapter must translate between Responses API and GHCP SDK session management. This is the primary integration engineering task for the POC. |
| [Agent 365](https://learn.microsoft.com/en-us/microsoft-agent-365/overview) GA: May 2026 | Not yet GA. Integration with Foundry Hosted Agents unclear. | In preview. Whether Hosted Agents auto-register in Agent 365 or require manual onboarding needs validation. [Entra Agent ID](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/what-is-agent-id) (the identity layer) is usable independently of Agent 365. Agent 365 natively supports Copilot Studio agents; our Control Plane will also support them. |
| [Foundry IQ](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/what-is-foundry-iq) / [Fabric IQ](https://learn.microsoft.com/en-us/fabric/iq/overview) / [Work IQ](https://learn.microsoft.com/en-us/microsoft-copilot-studio/use-work-iq) in public preview | Intelligence layer products are new. APIs evolving. | All three are MCP-addressable — we can fall back to direct Azure AI Search + Fabric SQL + Graph API queries if needed. The IQ products are an upgrade path, not a single point of failure. |
| MAI-Voice-1 | In public preview, not GA. No SLA. | Screening calls use GPT-Realtime (GA) as primary. MAI-Voice-1 is additive for TTS quality. |
| Copilot Studio on Foundry Hosted Agents | Copilot Studio is not supported on Foundry Hosted Agents. | Copilot Studio agents supported via Agent 365. Custom Control Plane UI natively supports both Copilot Studio and GHCP SDK agents. |

---

## 17. Architectural Choice — Skills, Not Separate Agents

POC 2 calls for "9+ specialist agents" in the hiring lifecycle: Budget, Job Design, Sourcing, Triage, Screening, Interview Coordinator, Compliance, Offer, Onboarding, Voice Screening. The brief's mental model is that each specialist role is an independent agent process with its own identity, its own tool set, and an inter-agent protocol connecting them.

We implement the same *capabilities* with a different *topology*: one domain-scoped Hosted Agent per domain (Hiring, Finance, Compliance) running ephemeral GHCP SDK sessions from MAF agent executors. Each session loads a different **skill** (SKILL.md file) per phase — screening skill, sourcing skill, compliance skill, and so on. Each skill declares its own role, its own tool allow-list, its own model assignment, its own governance rules. The specialisation WPP asks for — heterogeneous expertise, distinct authority, per-role model choice — is **preserved**. What changes is the coordination substrate: a MAF workflow graph with typed edges and validator nodes, not an A2A protocol between separate agent processes.

**Side-by-side trade-offs**:

| Dimension | 9 separate specialist agents | Skills-based (our approach) |
|---|---|---|
| **Specialisation** | 1 agent per role, distinct identity per role | 1 skill per role, loaded on demand per MAF agent executor; distinct role definition, tool allow-list, model per skill |
| **Coordination substrate** | A2A protocol between agents (JSON-RPC / SSE) on every handoff | MAF workflow graph edges — in-process, typed, deterministic |
| **Identity surface** | 9 Entra Agent IDs per domain, 9 Conditional Access policies, 9 audit identities | 1 domain Entra Agent ID; policy and audit segmentation at the skill layer via APIM |
| **Context sharing** | Each agent re-grounds or serialises context across the A2A boundary | Shared workflow state in the MAF graph; no re-grounding, no serialisation of working context |
| **Latency** | N × retrieval + N × inference + N × network hops | 1 × retrieval (where shared) + N × inference; zero inter-agent network hops within the graph |
| **Cost** | N × working-memory tokens; every A2A handoff re-establishes context | Amortised working memory; context flows down MAF edges without re-establishment |
| **Failure modes** | Network partition between agents; protocol version drift; handoff races | In-process graph execution; Pregel BSP guarantees deterministic fan-in |
| **Debuggability** | N separate OTEL traces per workflow; stitching via correlation IDs | Single MAF workflow trace per phase; natural parent-child span hierarchy |
| **Governance surface** | Per-agent governance — 9 APIM policy sets to keep aligned | Per-skill governance with one shared domain identity; policy at the skill layer; fewer drift points |
| **Operationalisation at fleet scale** | 9 × N workflows of agent instances to monitor, scale, restart | N workflows × one domain pool of Hosted Agents; skills load in ~ms from a content store |
| **Matches "specialist team" mental model** | Yes | Yes — skills are the specialists; the graph is the team |

**Where A2A still applies**. We are not against agent-to-agent protocols. A2A is the right choice when an agent is genuinely **off-platform** — a partner's candidate agent, an external supplier's pricing agent, a jurisdictional authority's compliance agent owned by a different organisation. These cross-boundary interactions go through [APIM A2A governance](https://learn.microsoft.com/en-us/azure/api-management/agent-to-agent-api) (JSON-RPC, AgentCards, SSE). What we avoid is **fragmenting a single domain's internal specialisation** across N network-separated processes when a typed workflow graph achieves the same specialisation with better operational characteristics.

**What WPP gets either way**:

- Heterogeneous expertise per phase — yes, as skills with distinct models and tools
- Role-based authority and tool access — yes, as skill-declared allow-lists enforced at APIM
- Auditability per role — yes, as skill-tagged OTEL spans and audit ledger entries
- Independent evolution per role — yes, as skill-versioned artefacts in API Center

**What WPP avoids**:

- 9× identity/governance/operational overhead per domain
- Inter-agent protocol failure modes
- Latency and cost of re-grounding across every handoff
- Debugging a correlation-ID graph instead of a workflow trace

This is not an argument against multi-agent systems. It is an argument for applying agent-process separation at the **organisational boundary** where it creates value, and skill-based specialisation at the **domain boundary** where it reduces cost and complexity without giving up any capability. If WPP evaluators prefer the separate-agent topology after seeing the trade-offs, both approaches are supported by MAF — we can compose a hybrid: skills inside a domain, A2A across domains.

