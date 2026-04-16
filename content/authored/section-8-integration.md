WPP's §5.3 names four protocols as Must-Have and §3.6 enumerates a LOB and surface matrix with MoSCoW priorities. One invariant runs through this section: the agent runtime is invoked through APIM, governed identically regardless of surface, and integrated with LOB systems through MCP with auth abstracted at the platform level. No surface is privileged; no integration bypasses the gateway. (Response §7, §8; Solution §4.)

## 8.1 Protocol support

All four WPP Must-Have protocols plus Structured Outputs are supported. (Response §7.)

| Protocol | Status | Implementation |
|---|---|---|
| MCP | GA | Primary integration pattern. GHCP SDK natively supports MCP. All enterprise systems exposed as MCP servers. APIM provides a REST-to-MCP gateway that auto-generates tool definitions from OpenAPI specs. Governance (auth injection, rate limiting, content safety, audit) sits in APIM. |
| A2A | Preview | APIM A2A governance covers AgentCards, JSON-RPC task lifecycle, and SSE streaming. Agents act as both clients and servers. Used for cross-organisation interactions with external agents. |
| OpenTelemetry | GA | Native throughout. GHCP SDK OTEL, MAF executor-lifecycle spans, and Durable Functions orchestration spans share one trace graph. Application Insights, Log Analytics, and any OTEL-compatible backend are consumers. |
| AG-UI | GA (MAF native) | MAF agent executors emit AG-UI events over SSE. The Control Plane UI renders dynamic approval forms, scorecards, and wizards per workflow type — no hardcoded UI per workflow. APIM mediates the SSE stream (auth, rate limit, audit). |
| Structured Outputs | GA | Type-safe, schema-validated responses. GHCP SDK skills declare output JSON Schemas. MAF workflow executors are typed end-to-end. APIM validates every response against the declared schema before forwarding. Violations are rejected at the gateway and surfaced to the Fleet Manager. |

## 8.2 LOB application integration

Every LOB system is reached through an MCP server governed by APIM. Credentials live in Azure Key Vault. APIM injects auth at request time from Key Vault references. Rotation is automated and does not require agent downtime. Agent developers never handle tokens. (Response §8.1; Solution §4.)

| System | Auth method | MCP integration |
|---|---|---|
| Workday | SAML-bridged via Okta | MCP server, APIM-governed |
| LinkedIn Recruiter | OAuth 2.0 Authorization Code | MCP server, APIM-governed |
| Greenhouse ATS | API app credentials | MCP server, APIM-governed |
| Microsoft Graph | OBO (On-Behalf-Of) flow | MCP server, APIM-governed |
| ServiceNow | API key | MCP server, APIM-governed |
| Dynamics 365 F&O | Native | MCP server, APIM-governed |
| Deltek Maconomy | REST adapter via APIM REST-to-MCP gateway | Auto-generated from OpenAPI spec |
| Azure Communication Services | Managed identity | MCP server, APIM-governed |
| HeyGen | API key | MCP server, APIM-governed |
| Citizen-dev integrations (SharePoint, Outlook, Dataverse, 1,400+) | Logic Apps connectors | Logic App exposed as MCP tool via APIM REST-to-MCP gateway |

Supported OAuth 2.0 grant types: Authorization Code, Client Credentials, SAML-bridged (Okta), PKCE, Device Flow, and On-Behalf-Of. All flows federate through Entra External ID with Okta as the primary IdP — matching WPP's stated identity posture. (Response §8.1.)

## 8.3 Surface-side integrations

§8.2 covers backend systems. This section covers the surfaces from which agents are invoked. The invariant: the agent runtime is invoked through APIM, governed identically regardless of surface. No surface bypasses MFA, RBAC, content safety, or audit. (Response §8.2.)

| Platform | MoSCoW | Invocation pattern | Status |
|---|---|---|---|
| M365 Copilot (Teams, Outlook, Word, Excel) | Must | Personal Agent surfaced via M365 Agents SDK. Primary surface for most WPP users. | GA |
| Custom Control Plane UI (React) | Must | First-class surface. AG-UI over SSE, SignalR for real-time Fleet Manager pushes, REST for fleet queries — all through APIM. | Custom build |
| Web Portal (Angular / React) | Nice-to-have | Candidate-facing portal consumes the same AG-UI SSE streams and REST endpoints via APIM. An Angular AG-UI client is a routine SSE consumer. | Custom build |
| SharePoint (SPFx) | Should | SPFx web part embeds the PA via the M365 Agents SDK chat surface and invokes named skills through a pre-registered APIM endpoint. Bidirectional: SharePoint as invocation surface and as a Foundry IQ knowledge source. | GA (SPFx, Graph MCP); custom SPFx web part |
| Power Apps (connector / PCF) | Must | A custom connector to APIM exposes named agent skills to Power Apps formulas and flows; a PCF control embeds the PA chat into model-driven apps. Copilot Studio is available as the flagship low-code path; for the workflow topology in scope the recommended approach is MAF workflows plus skills (see §9). Governance is identical either way. | GA (connector, PCF); skill registration custom |
| Dynamics 365 (forms, workflows, plugins) | Must | D365 is both backend (via MCP) and surface. Forms embed the PA via the Power Platform embedded Copilot surface; workflow steps invoke named skills via a custom connector to APIM; plugins call APIM for synchronous invocation. | GA (D365, connector); custom D365 resources per workflow |
| .NET SDK | Should | MAF ships with full .NET parity — agent executors, workflow graphs, and durable task integration available in C#. Artefacts serialise identically (SKILL.md, MAF workflow definitions). | GA (MAF .NET, Durable Functions .NET) |
| ServiceNow | Must | ServiceNow invokes the PA via the ServiceNow MCP server, governed through APIM. IT Ops works in its existing surface; the PA writes back provisioning tickets. | Custom MCP server |
| Voice (ACS + GPT-Realtime) | Must | Speech-to-speech front end via GPT-Realtime; tool calls to GHCP SDK sessions for reasoning. ACS handles telephony and PSTN. | GA |
| Email (Adaptive Cards) | Must | The PA composes Adaptive Cards; responses route back through the PA. | GA |

## 8.4 One agent, many surfaces

WPP's §3.6 invariant is explicit: a single agent definition must be deployable to any supported surface via configuration or thin adapter, not by duplicating agent logic. A domain-scoped Hosted Agent (e.g. `hiring-agent@wpp`) contains skills addressable from any surface; the surface contributes only rendering and invocation.

Concrete example. The Hiring Agent's Interview Coordinator skill is invokable from the HR BP's Control Plane UI, from the Hiring Manager's PA in Teams, from a ServiceNow form raised by IT Ops, and from an external candidate agent via A2A. The same MAF workflow executor handles all four. Each surface supplies a thin adapter: AG-UI components for the Control Plane, a Teams card for the PA, a ServiceNow connector call, and a JSON-RPC AgentCard for A2A. Skill code, tool allow-lists, model assignment, governance rules, and audit trail are unchanged across surfaces. (Response §8.2; Solution §4.)

## 8.5 Cross-cloud discovery via API Center

WPP's stated posture is multi-cloud — Azure primary, GCP primary, AWS. Azure API Center registers MCP servers, skills, APIs, and A2A agent cards hosted anywhere: Azure-hosted Foundry models, GCP-hosted Vertex agents, AWS-hosted internal APIs, on-prem SAP. A single registry, a single discovery endpoint. APIM provides uniform governance regardless of backend cloud — no second control plane, no migration. (Solution §4; Response §4.1.)
