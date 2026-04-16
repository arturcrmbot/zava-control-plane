## 10.1 POC 1 — Finance: Intelligent Procure-to-Pay

WPP manages employee expense claims across **15+ expense management systems** (Workday, SAP Concur, Chrome River, and local tools), governed by **100+ local policies** spanning markets and agencies, and reviewed by **~130 FTEs** conducting manual checks. Non-compliant spend is significant and detection is reactive. The August 2025 VML North America pilot established the internal benchmark: **3,430 claims and USD 839K of spend processed through Workday with 97.6% classification accuracy** using a Red/Amber/Green policy model. That benchmark was single-EMS. POC 1 must reproduce the capability **across multiple underlying systems** behind a **system-agnostic** operator experience.

The core architectural principle is stated in WPP's brief and is preserved in our design:

> *"Agents operate the expense systems; humans operate the Control Plane. The Finance Controller never logs into Workday or Concur. They govern the agent fleet."*

Every design choice below follows from that principle.

## Duration, operator, concurrency

Eight-week sprint. A single **Finance Controller (London)** operates the Control Plane across **30–50 concurrent invoice and expense workflows** spanning multiple EMS platforms. The Controller sees policies, violations, trends, and exceptions — not the EMS from which a claim originated.

## Architecture

A domain-scoped Hosted Agent, **`finance-agent@wpp`**, anchors the solution. It is registered in Entra Agent ID (GA today) as the workload identity; Agent 365 platform-level primitives are adopted when GA in May 2026. The hosting component is an Azure AI Foundry Hosted Agent where available; until that service is generally available, Azure Container Apps provides the equivalent runtime without changing the agent contract.

**Skills:**

- Intake/OCR — Azure Document Intelligence
- Validation — three-way match, duplicate detection
- Routing — GL coding, cost-centre allocation
- Approval — threshold-based routing with HITL gates
- Payment — payment file generation
- Reconciliation — statement matching, exception identification

## Execution shape

Each invoice is a **Durable Functions orchestration**. Each phase (intake, validation, routing, approval, payment, reconciliation) is a **MAF workflow graph** invoked as a durable activity. Most executors are plain functions. **Agent executors** are used only where genuine reasoning is needed — low-confidence OCR extraction, GL coding, exception classification. A **validator executor** sits between any agent output and any downstream non-revocable action. Deterministic logic is deterministic; probabilistic logic is bounded and gated.

## MCP integrations

Workday, Dynamics 365 F&O, and Deltek Maconomy are integrated via MCP servers. All MCP traffic is brokered by APIM AI Gateway. Sandbox and mock APIs for the POC are provided by WPP. EMS endpoints are reached over Azure Private Endpoints; outbound SaaS egress goes via Azure Firewall with an FQDN allow-list; APIM is the sole public edge.

## What the POC demonstrates

Each capability below maps to a WPP POC 1 acceptance criterion or evaluation dimension.

- **Fleet Manager monitoring 30–50 concurrent workflows** — single Finance Controller view (acceptance #1).
- **Exception-only Control Plane view** — routine Green claims hidden from the default view; live demo runs 20 workflows with 3 exceptions surfaced (acceptance #2).
- **Bulk approval of batched low-risk items** — 10+ items approved in a single action with per-item audit (acceptance #3).
- **≥95% classification accuracy with per-line policy reasoning** — policy-driven R/A/G model; updating the policy document changes classification behaviour without redeployment (acceptance #4; covers the 40% accuracy scoring weight — see Success metric below).
- **Receipt cross-validation** — receipt image compared to structured data for mismatch, missing-receipt, and anomaly detection (acceptance #5).
- **Progressive enforcement** — warning, escalation, major-violation flow for repeat offenders across time windows (acceptance #6).
- **Autonomous learning** — Arbitration skill observes SSC Reviewer decisions and recommends autonomy changes; live demo shows the initial (all-to-human) to steady-state (agent recommends, human spot-checks) curve. Changes are proposed as governance change-requests requiring Finance Controller sign-off; they do not auto-apply (acceptance #7).
- **SSC Reviewer operational interface** — a purpose-built queue view for the Manila reviewer, sorted by severity, value, and SLA urgency, with status feeding back to the Control Plane in real time (acceptance #8).
- **System-agnostic Control Plane** — claims from Workday and at least one additional EMS appear identically; the default view gives no indication of source system (acceptance #9; see System-agnostic proof below).
- **Integration extensibility** — a new EMS is added by registering its MCP server in APIM and declaring it as a skill tool; no agent logic or Control Plane changes (acceptance #10; see Integration extensibility below).
- **Workflow recovery after simulated region failure** — mid-workflow platform restart with Durable Functions replay and MAF workflow checkpoint resume; zero data loss, resume from last checkpoint within RTO (acceptance #11).
- **Immutable audit trail** — every agent action (agent, system, decision, data, policy applied, approver) logged; queryable for compliance reporting during the demo (acceptance #12).
- **OTEL cost-per-task report** — cost attribution per invoice across all three execution layers (Durable Functions, MAF, agent); weekly report generated by the Orchestrator on the Control Plane (acceptance #13).
- **HITL approval gates** — the Finance BP interacts via an Adaptive Card in Outlook, routed through the Personal Assistant; Durable Functions `wait_for_external_event` holds the workflow at zero compute cost until the human responds.
- **Deterministic-by-default MAF graphs** — three-way match, payment file generation, and routing are plain functions with no LLM in the path.
- **Rollback and compensating transactions** — non-revocable actions gated by GHCP SDK hooks inside agent executors and by MAF validator executors.
- **Foundry Guardrails inside agent executors** — PII detection and content safety applied to every LLM invocation.
- **Private network posture** — MCPs over Private Endpoints; egress via Azure Firewall FQDN allow-list; APIM sole public edge.
- **Non-revocable operations demo** — payment file generation gated by an explicit dual-control requirement (Finance Controller plus Finance BP, distinct Entra identities in distinct groups); the non-revocable-operations catalogue is visible in the Control Plane.
- **60-minute build close-out** — scripted demo in which a junior developer builds, tests, and deploys a new agent with three MCPs and three knowledge sources via Copilot Studio in under 30 minutes (WPP §6.4 benchmark). Copilot Studio is used here only as the rapid-build surface; production authoring uses the GHCP SDK.

## Success metric

POC 1 scoring allocates **40% to accuracy and policy reasoning**. The primary success metric is to match or exceed the **97.6% VML NA classification benchmark** on the synthetic 3,430-line dataset WPP provides. Output is reported with per-line policy-based reasoning per R/A/G verdict, confidence scores on ambiguous Amber cases, and competing interpretations where present. The policy document is treated as a first-class artefact — when it is updated, classification behaviour changes without code changes.

## System-agnostic Control Plane proof

Claims from Workday and at least one additional EMS are loaded concurrently. In the Finance Controller's default view they are indistinguishable: identical fields, identical affordances, identical bulk actions. The source system is available only on drill-down for forensic audit purposes.

## Integration extensibility

Adding a third EMS — Maconomy, Rippling, or an agency-local tool — requires three steps: register the EMS MCP server in the APIM AI Gateway registry; declare the new tool in the relevant skill manifest; publish. No agent logic changes. No Control Plane changes. This is walked through on-screen during the architecture segment of the demonstration.
