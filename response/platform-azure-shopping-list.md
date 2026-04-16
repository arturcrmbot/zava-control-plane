# Platform & Control Plane — Azure Shopping List

Covers the remainder of the stack not attributed to POC1 or POC2. This is the **cross-cutting platform** that supports both POCs and any future domain (compliance, procurement, media ops, etc.): the custom Control Plane UI, the shared observability + audit spine, and the delivery infrastructure.

**Timing note**: the Custom Control Plane UI is needed **Day 1 of POC1** — operators access POC1 through it. Its build cost is tracked here (separate from POC1) because it's a platform asset that serves both POCs and any future domain.

Azure-only consumption. M365 / identity / DLP / threat-detection licences (Agent 365, Purview, Defender for Cloud AI) are out of scope for this list per direction.

---

## Shopping list

| # | Resource | Tier / config | Purpose |
|---|---|---|---|
| 1 | **Azure Static Web Apps** (or App Service) | Standard tier | Hosts the Custom Control Plane UI (React app): fleet dashboard, exception queue, situational-awareness drill-down, bulk HITL, autonomy dials, skill-amplification surface, cost dashboard. |
| 2 | **Azure SignalR Service** | Standard tier, 1 unit | Real-time push from Fleet Manager agents to the Control Plane UI — fleet assessments, exception prioritisation, workflow state changes. |
| 3 | **Azure Front Door** (or Application Gateway with WAF) | Standard tier | CDN + WAF + TLS termination in front of the Control Plane UI. Entra Conditional Access enforced at this edge for role-based operator views (HR BP, Finance BP, IT Ops). |
| 4 | **Microsoft Foundry Control Plane** | GA, platform product | Fleet inventory across all agent platforms, model registry (1900+ models), guardrails configuration, built-in evaluators, continuous evaluation on production traffic, Defender + Purview integration. No additional charge — included with Foundry. |
| 5 | **Azure API Center** (shared tenant) | Preview (free) | Single registry across POCs and future domains — models, MCP tools, A2A agents, skills, APIs. Cross-cloud discovery (Azure / GCP / AWS / on-prem). GitHub Actions sync for SKILL.md files. |
| 6 | **Azure Monitor — Log Analytics workspace (shared)** | PAYG Analytics + long-retention | Single workspace aggregating OTEL from both POCs, APIM, MCP servers, Control Plane UI. Queryable via KQL. |
| 7 | **Microsoft Sentinel** | PAYG over Log Analytics | SIEM for security + compliance monitoring. Detects anomalous agent behaviour, policy drift, identity misuse. Required for WPP's enforcement-event monitoring across the fleet. |
| 8 | **Azure Storage — archive tier (immutable)** | Standard GPv2 + immutability policy | Long-retention audit archive — **7-12 year retention** required for compliance (every tool call, model call, enforcement decision, human interaction). Immutability policy enforced at the Storage account. |
| 9 | **Azure Container Registry** | Standard tier | Hosts custom container images: GHCP SDK ↔ Foundry Responses API adapter, MCP server images for both POCs, Threadlight accelerator artefacts. |
| 10 | **Azure Key Vault** (platform-level) | Standard | Shared platform secrets distinct from per-POC credentials — APIOps signing keys, SignalR access keys, Sentinel workspace keys, platform service principals. |
| 11 | **Azure DevOps** or **GitHub Actions self-hosted runners on Azure** | PAYG | APIOps CI/CD pipeline — APIM policies, API Center registrations, SKILL.md promotion (Design → Preview → Production → Deprecated), Foundry Guardrails config, infrastructure-as-code deployment. |
| 12 | **Azure Policy + Azure Blueprints** | Included | Governance guardrails for subscription-level enforcement (tagging, region pinning, SKU allow-lists) across POC and future environments. |

---

## Assumptions

| Assumption | Value | Rationale |
|---|---|---|
| Control Plane UI users at POC scale | 5-15 concurrent operators | HR BP + Finance BP + IT Ops + executives + dev/demo accounts. SignalR Standard unit handles ~1k concurrent comfortably — massively over-provisioned for POC, right-sized for early production. |
| Log Analytics retention | Short-term 90 days hot + long-term 7-12 years archive | Compliance (Ref 10.5) requires 7-12 year retention. Hot kept short; archive tier for cold. |
| Audit archive volume at POC | Low (GB-scale) | Both POCs combined produce modest audit volume. Archive tier storage is cheap regardless. |
| Sentinel ingestion scope | All OTEL + APIM + Agent 365 / Entra logs | Required for fleet-wide anomaly detection and compliance enforcement-event monitoring. |
| API Center tenant | One shared instance across dev / staging / POC environments | Lifecycle gates differentiate environments, not separate API Center instances. |
| Container Registry images | ~10-15 images across GHCP SDK adapter, MCP servers, Threadlight | Small footprint; Standard tier sufficient. |
| CI/CD environment | Existing Azure DevOps or GitHub Enterprise | No greenfield CI/CD infrastructure; rides on existing WPP delivery platform. |
| Identity / RBAC | Built on existing Entra P2 tenancy | Agent IDs registered per domain; Conditional Access policies author via platform team. |

---

## Out of scope (deliberately excluded)

| Excluded | Reason |
|---|---|
| POC1-specific Azure resources (APIM, Functions, Cosmos, AI Search Basic, Document Intelligence, etc.) | Covered in [POC1 shopping list](poc1-azure-shopping-list.md). |
| POC2-specific Azure resources (voice stack, Fabric, AI Search S1, 6 MCP servers, etc.) | Covered in [POC2 shopping list](poc2-azure-shopping-list.md). |
| M365 Copilot / M365 Agents SDK / Teams surface infrastructure | Existing WPP M365 tenancy. |
| Third-party SaaS (Workday, Greenhouse, LinkedIn, ServiceNow, Okta IDP) | WPP-provided / existing enterprise estate. |
| HeyGen and any external SaaS | User excluded external parties. |
| Private Endpoints / VNet / NAT gateway / ExpressRoute | Add if compliance posture mandates network isolation. |
| Secondary region / multi-region DR | Not in POC scope. |
| Cost management / FinOps tooling beyond Azure Cost Management | Existing WPP FinOps tooling. |
| Threadlight accelerator build cost | Already built and demonstrated by the solution team. Runtime rides on existing MAF + GHCP SDK + API Center infrastructure. |

---

## How the three shopping lists compose

| Layer | Owned by |
|---|---|
| Domain-specific compute, MCP servers, grounding data, domain-scoped Hosted Agents | POC1 list (Finance) / POC2 list (Hiring) |
| Shared governance control plane (APIM, API Center, Foundry Control Plane) | Each POC lists what it consumes; physical deployment is one shared instance per environment |
| Custom operator experience (Control Plane UI, SignalR, Front Door) | This platform list |
| Cross-cutting observability + audit (Log Analytics, Sentinel, archive storage) | This platform list |
| Delivery infrastructure (Container Registry, APIOps CI/CD, Azure Policy) | This platform list |

In a deployed system the governance control plane (item 5 in both POC lists, APIM / API Center) would be **one instance shared** — not duplicated per POC. The per-POC lists reflect what each POC consumes; the physical topology consolidates.

---

## What the platform adds beyond either POC

1. **The operator experience.** Both POCs reach their Control Plane requirements only through the custom React UI + SignalR + Fleet Manager composition. No vendor ships this out-of-the-box. Required from Day 1 of POC1.
2. **The compliance spine.** 7-12 year immutable audit and Sentinel anomaly detection operate across every POC and every future domain.
3. **The delivery fabric.** APIOps CI/CD, Container Registry, Azure Policy, API Center lifecycle gates — how skills, tools, and agents get promoted from design to production safely.
