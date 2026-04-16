# Section 7 — Governance, Security and Compliance

This section addresses WPP's §5.2 governance requirements and the §6.3 Enterprise Non-Negotiables. Governance is enforced externally and structurally; the LLM cannot bypass the layers below.

## 7.1 Agent identity and governance

WPP requires every agent to carry a first-class enterprise identity, distinct from service accounts, with RBAC-enforced access to downstream tools. Each Hosted Agent has a dedicated Entra Agent ID — domain-scoped and attached to the container, not to individual sessions.

| Hosted Agent | Entra Agent ID | Tool Access |
|--------------|----------------|-------------|
| Hiring Agent | hiring-agent@wpp | Greenhouse, LinkedIn, Workday (hiring), Microsoft Graph, Azure Communication Services |
| Finance Agent | finance-agent@wpp | Workday (finance), D365 F&O, Maconomy |
| Fleet Manager | fleet-manager@wpp | Read-only: telemetry, state store. No downstream tool invocation. |

When a human triggers an action the loop acts on-behalf-of that human via OAuth OBO; autonomous phases use the Hosted Agent's app-only identity. Every action is attributed to the correct identity in the audit trail.

Entra Agent ID is usable in preview today. The Agent 365 umbrella — admin-centre lifecycle management (activate, block, delete), cross-service Conditional Access for agents, Purview DLP on agent interactions, and Defender threat detection — reaches general availability in May 2026. The identity primitive is present today; Agent 365 layers on governance flows at GA without re-platforming.

## 7.2 Per-skill tool allow-list (APIM-enforced)

Each SKILL.md declares its allowed tools in frontmatter. On promotion from Design to Production, the allow-list is compiled into an APIM policy fragment. Tool calls from an agent executor carry skill context — skill ID, version, workflow phase, jurisdiction — as JWT claims issued by the Hosted Agent's managed identity; APIM validates these claims against the declared allow-list before forwarding. Enforcement sits in the gateway, outside the agent runtime, and cannot be bypassed by a prompt-injected tool call.

## 7.3 Non-revocable operations catalogue

Each MCP tool declares `revocable: true|false`. Non-revocable invocations route through a hook-enforced HITL gate regardless of skill or workflow. The catalogue is Git-committed and PR-reviewed. Revocability is a property of the tool, not of the skill.

| Operation | Domain | Enforcement |
|-----------|--------|-------------|
| Send email to external recipient | Hiring, Finance, Onboarding | GHCP SDK hook blocks send; HITL approval via Power Automate |
| Extend offer letter | Hiring | Hook + MAF validator + dual-control |
| Submit payment / release funds (amount above threshold) | Finance | Hook + MAF validator + dual-control |
| Create ServiceNow JML ticket | IT Ops | Hook + HITL approval |
| Post outbound A2A message to external agent | Multi-domain | Hook + validator; allow-listed destinations only |
| Write to Workday / D365 F&O master data | HR, Finance | Hook + dual-control + audit link to operator |
| Commit compliance attestation | Compliance | Dual-control mandatory |
| Publish external content | Marketing, Comms | Hook + HITL approval; allow-listed channels |

## 7.4 Dual-control (four-eyes)

High-risk operations require two approvals from two distinct Entra identities in two distinct operator groups. Durable Functions enforces the gate: the orchestration does not advance until two `raise_event` calls arrive from two distinct operators. APIM validates group claims against Entra groups; the second approver cannot be the first. Both identities are audit-logged against the orchestration instance.

## 7.5 Five enforcement layers

Compliance is enforced across five layers. The LLM cannot bypass any of them.

| Layer | Technology | Status | Enforcement |
|-------|------------|--------|-------------|
| MAF workflow validators | Validator executors in the MAF workflow graph | GA (MAF v1.0) | Structural and policy enforcement inside the graph. A validator asserts schema, checks policy tables, runs rule engines, and routes to a rejection branch if violated. Judge/executor separation as two nodes and an edge. |
| Foundry Guardrails | Tool-call/response interception, PII detection, Task Adherence | Preview | Four intervention points — input, output, tool-call (preview), tool-response (preview). PII redaction. Task Adherence detects drift from system-message policy. Complements MAF validators (inside vs. outside the executor). |
| APIM AI Gateway | Model routing, content safety, token limits | GA | Jurisdiction-based model routing (a DE workflow reaches EU endpoints only). `llm-content-safety` policy. Token rate limiting. Semantic caching. All MCP tool calls governed. |
| Agent 365 + Entra | Identity, access control, Purview DLP, Defender | GA May 2026 (Entra Agent ID in preview today) | Per-agent RBAC on downstream resources. Conditional Access on agent identities. Purview DLP on interactions. Defender threat detection. |
| Runtime isolation | Private Endpoints + VNet + Firewall Premium egress allow-list + APIM sole public edge | GA | East/west traffic over Private Link; SaaS egress restricted to named FQDNs; no direct internet from Hosted Agents or DF workers. Residency enforced by APIOps CI gate. |

## 7.6 Observability and OpenTelemetry

Three layers:

1. Foundry Tracing. Every GHCP SDK session (inside a MAF agent executor) emits OTEL spans via the GHCP SDK OTEL TracerProvider; MAF emits executor-lifecycle spans natively; Durable Functions emits orchestration spans. Model calls, tool calls, tokens, latency, and cost are captured. Spans carry workflow ID, phase, jurisdiction, model, and token count.
2. APIM metrics. Token usage, latency, and errors per model, tool, and agent. Central cost tracking.
3. Fleet Manager assessment. Event-driven reasoning over telemetry: fleet health, anomaly detection, SLA risk, exception prioritisation. This is the default Control Plane view.

Cost attribution is per workflow, per phase, per model, per consumer.

**Telemetry data classification.** OTEL span attributes carry workflow ID, phase, jurisdiction, model, and token counts — no prompt or response bodies in Application Insights. Bodies are redacted by Foundry Guardrails and held in Log Analytics only. Reasoning chain and action ledger sit in separate tables; a non-revocable action's audit record carries the span ID that produced it, not the reasoning tokens.

## 7.7 Network and runtime isolation

**Principle: APIM is the only public edge.** Everything behind it — Foundry Hosted Agents, Durable Functions, MAF executors, MCP servers, Cosmos DB, Key Vault, AI Search, Log Analytics, Event Grid — is reachable only over Private Endpoints or VNet-integrated paths. Agents have no direct internet access; SaaS egress traverses Azure Firewall Premium with an FQDN allow-list.

| Boundary | Control | Notes |
|----------|---------|-------|
| Public ingress | Azure Front Door Premium (WAF, DDoS) → APIM Private Endpoint | Single external entry. WAF blocks OWASP Top-10. APIM gateway has no public IP; Front Door reaches it over Private Link. |
| East/west (agent ↔ model/tool) | APIM AI Gateway sole addressable endpoint; backends on Private Endpoint | Foundry model endpoints, Cosmos DB, Key Vault, AI Search, Log Analytics, Event Grid — all private endpoints. |
| Egress (agent → SaaS) | Azure Firewall Premium with FQDN allow-list | Named destinations only: Workday, LinkedIn, Greenhouse, HeyGen, Dynamics 365 SaaS, Okta, Maconomy. Everything else blocked. |
| Compute isolation | Functions VNet integration; Hosted Agents in dedicated subnets; no public IPs on compute | DF workers and MAF executors resolve APIM and data-plane dependencies via Private DNS only. Subnet NSGs enforce least-privilege. |
| Cross-region | Region-pinned deployments per jurisdiction | EU workflows never resolve US-region endpoints. Log Analytics, Cosmos DB, and Hosted Agent pools are regional. |
| Residency CI gate | APIOps pipeline validation | PRs registering a non-EU backend against a DE-tagged skill fail CI. Jurisdiction is an enforced boundary, not a runtime decision. |

Four data classes, each with distinct residency and redaction policy:

| Class | Where it lives | Retention | Residency |
|-------|----------------|-----------|-----------|
| Workflow state (phase state, action ledger, approvals, business data) | Cosmos DB → Storage immutable export | Workflow lifetime + 90 days hot; archive thereafter | Region-pinned to jurisdiction |
| Model context (prompts, tool calls, reasoning chain within a session) | In-memory during the GHCP SDK session | Ephemeral — discarded at session end | Never crosses region |
| Audit ledger (every tool call, model call, enforcement decision, human interaction) | Log Analytics → Azure Storage immutable export | 7–12 years, immutable | Regional workspace per jurisdiction |
| Telemetry (OTEL spans, metrics, cost attribution) | Application Insights | 90 days (configurable to 2 years); IDs only, no bodies | Regional instance |

## 7.8 Data protection and compliance

Three enforcement layers apply continuously: Foundry Guardrails (input, output, tool-call, tool-response; PII; Task Adherence); APIM AI Gateway (jurisdiction-based model routing, content-safety filtering, token rate limiting); Agent 365 and Entra (per-agent RBAC, Conditional Access, Purview DLP, Defender threat detection).

Policy-as-code via APIOps: APIM policies, Foundry Guardrails configurations, and jurisdiction-specific skills are Git-committed and PR-reviewable.

Jurisdiction switching is declarative. Workflow state carries `jurisdiction`; APIM routes to the region-appropriate model endpoint; jurisdiction-specific skills (right-to-work, works council, GDPR consent) load automatically from workflow context. Adding a jurisdiction means adding skill files — not modifying agent code.

**Audit.** Azure Log Analytics with 7–12 year retention; immutability via Azure Storage export with immutability policies. Every tool call, model call, enforcement decision, and human interaction is logged. Queryable via KQL and Microsoft Sentinel.

**Platform certifications.** The Azure services in this architecture inherit SOC 1 / SOC 2 Type II / SOC 3, ISO/IEC 27001, ISO/IEC 27017, ISO/IEC 27018, ISO/IEC 27701, HIPAA, PCI DSS Level 1, FedRAMP High, GDPR, and BSI C5 (Germany). EU AI Act alignment is maintained through Microsoft's Responsible AI Standard, Foundry Guardrails' classifier coverage of high-risk categories, and Foundry built-in evaluators for bias and safety. The authoritative matrix sits in the Microsoft Trust Center. WPP's SOC 2 readiness and GDPR evidence inherit from these attestations — no bespoke security certification is required at the WPP application layer.

## 7.9 Encryption, MFA, and secret management

**Encryption.** TLS 1.2+ on all ingress and east/west traffic; TLS 1.3 where supported. At-rest encryption defaults to Microsoft-managed keys; Customer-Managed Keys via Azure Key Vault are available for Cosmos DB, Log Analytics, AI Search, Storage, and Foundry — recommended for regulated jurisdictions. Azure Storage supports double encryption (service plus infrastructure layer) for the immutable audit export. Key rotation is automated via Key Vault; agent code never sees raw credentials — APIM injects them at request time from Key Vault references.

**Multi-factor authentication.** Enforced by Entra Conditional Access on every human path — operators accessing the Control Plane UI, business partners approving via Power Automate, and platform engineers making governance changes. Phishing-resistant methods (FIDO2, Windows Hello, Microsoft Authenticator with number matching) are required; SMS and voice MFA are blocked via Authentication Strengths policy. Agent actions use managed identities, not interactive credentials — no shared secret to phish.
