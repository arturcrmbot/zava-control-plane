# WPP RFP Response — Master Document Population Design

**Status:** Draft for review
**Date:** 2026-04-15
**Author:** Artur Zielinski (with Claude)
**Deadline context:** Written response due 2026-04-23 (8 days from spec date)

## 1. Context

WPP's Enterprise Agent Capability Framework RFP is a 3–5 year strategic partnership decision. Microsoft's response has two parts:

- **Part A — Framework Assessment:** long-form written proposal + questionnaire response
- **Part B — POC Design:** solution architectures for POC1 (Finance P2P) and POC2 (HR Talent)

The master response document is `WPP-RFP-Response-Master.docx` in the MSFT_Response OneDrive folder. It provides the outline and narrative guidance for the written proposal. The separate assessment questionnaire (157 rows, 5 original columns, Appendix A of WPP's brief) is submitted as an xlsx workbook, **not embedded in the Word document**.

Three raw-material sources need to be consolidated into a cohesive, evaluator-ready response:
- `response/response-technical-sections.md` — technical narrative, structured to match RFP §§4–13, 16–17
- `solution/solution.md` — internal solution architecture, with POC technical detail
- `response/questionnaire answers/` — 29 CSVs holding Microsoft's answers to all 157 questionnaire items

The raw material was authored iteratively for different purposes. Dropping it straight into the master will produce a document that reads like four voices. This spec defines both a **content plan** (what each master section actually says, drawing from the sources) and a **tool plan** (how we mechanically render that content into the docx and rebuild the questionnaire xlsx).

## 2. Scope

Two deliverables:

**Deliverable 1 — Docx populator.** Python tool that reads `WPP-RFP-Response-Master.docx`, matches target headings by text, and injects authored content into stub sections and inline placeholders using `python-docx`. Output: a new docx alongside the master; master is never overwritten. Injection is prose-and-bullet only — no new images, no new complex tables. Existing master tables get empty placeholder cells filled in where specified.

**Deliverable 2 — Questionnaire xlsx builder.** Python tool that reads the 29 answer CSVs and the original WPP questionnaire template (`wppetai-agentic-framework-assessment-questionnaire.xlsx` in the Originals folder), joins them into a single submission-ready xlsx, preserves the original `Instructions` sheet, and writes the `Questionnaire` sheet with Microsoft's answers added as five additional columns after WPP's original five.

**Out of scope** (for this spec):
- Appendix C — Architecture Diagrams. The master stubs reference diagrams that need to be produced (Enterprise Architecture Diagram, C4 Context/Container/Component, Control Plane fleet dashboard wireframe, agentic loop state diagram). Handled separately from this tool; parked per the brainstorming discussion.
- Control Plane Diagrams PDF referenced in WPP's Q&A (hyperlink target) — we are recipients, not authors.
- Commercial & Partnership (§12) — already written by the account team; left untouched.
- Executive Letter (§0) — already written; left untouched.

## 3. Narrative strategy (the winning argument)

Before defining per-section content, the spec fixes the **overall argument shape**. Every populated section must serve this argument. Deviations are flagged.

### The argument WPP's evaluators must reach by the end of the document

1. **Agents are digital workers** — not software. Microsoft is the only vendor treating them that way (opening narrative, §§0–2).
2. **WPP already has the governance substrate for digital workers** — Entra, Purview, Defender, M365, Power Platform, APIM. Microsoft's framework *extends* it rather than building a parallel universe (§3 Reading WPP's Ambition).
3. **The agentic architecture is layered, honest, and built for change** — three execution layers (Durable Functions + MAF + GHCP SDK), deterministic by default, agentic by exception, skill-crystallisation as the maturity path. GA foundation; replaceable runtime (§4 Reference Architecture).
4. **The Control Plane is the product** — not a dashboard. A purpose-built fleet operator experience that achieves 1:20–50 human-to-workflow ratios, with exception-only surfacing, bulk HITL, autonomy dials, and Fleet Manager agents doing the cognitive work (§5 Control Plane). *This is the single highest-weighted section.*
5. **Multi-agent orchestration is durable, inspectable, interruptible** — MAF workflow graphs inside Durable Functions envelopes; zero-compute HITL; Pregel BSP; stable coordination patterns (§6).
6. **Governance is structural, not policy-on-top** — five enforcement layers (MAF validators, Foundry Guardrails, APIM, Agent 365/Entra, runtime isolation). The LLM cannot bypass any of them (§7).
7. **The platform integrates where WPP already lives** — Workday, D365, Greenhouse, LinkedIn, ServiceNow via MCP; M365, Teams, Power Apps, D365, SharePoint, voice, email as surfaces. One agent definition, many surfaces (§8).
8. **Every builder persona is served without divergent runtimes** — pro-code (GHCP SDK + MAF), low-code (Copilot Studio), Threadlight for SME capture, 60-minute build, runtime agent assembly — all producing Git-committable artefacts on one APIOps pipeline (§9).
9. **Execution is proven by the POCs** — POC1 Finance beats the 97.6% accuracy benchmark; POC2 HR demonstrates 22 advanced capabilities end-to-end across five humans in four timezones (§10).
10. **NFRs are met by the underlying Azure SLAs, verified at POC** (§11).
11. **Portability is structural** — MCP, A2A, OTEL, open skill format, MIT SDK; exit path is documented (§13).
12. **Commercial terms signal skin-in-the-game** — co-investment POC pricing, modular scaling, MACC alignment, three-year partnership trajectory (§12 — already written).

### Three rules for per-section drafting

**Rule 1: Lead with the WPP quote or requirement.** Every populated section opens by referencing the WPP brief requirement(s) it answers. Evaluators with a scoring rubric in front of them can instantly see "this section addresses §3.4 Control Plane fleet management".

**Rule 2: Every technical claim traces to a source.** If `response-technical-sections.md` says it, the master must say the same thing in the same way. If the CSVs commit us to it, the master must not soften it. If the two sources disagree, §5 of this spec resolves them.

**Rule 3: No invented facts.** If a claim appears only in the master docx outline but not in any source (e.g. the five-layer Apex model), flag it for human decision before writing. The master has at least three places where existing prose asserts things the sources don't back (§5.3 of this spec lists them).

## 4. Source-of-truth precedence

When sources disagree:

**0. Topic-specific authored v-PDFs in `MSFT_Response/`** — the account team has authored stand-alone submission-grade documents (e.g. `WPP-Control-Plane-Integration-Architecture-v7.pdf`, dated 2026-04-15). Where one of these exists for a section, it is the highest authority and outranks the MD sources. **Known v-PDFs as of 2026-04-16:**
   - `WPP-Control-Plane-Integration-Architecture-v7.pdf` — §4.3.2 Control Plane Integration Architecture (primary source for master §5 Control Plane)

   **Backlog — not in scope for this iteration, but required before final submission:** inventory pass over the entire `MSFT_Response/` folder (and related Account Team OneDrive folders) to catalogue all authored v-PDFs. Each v-PDF discovered must be added to this precedence list and the corresponding master section updated to match. Without this pass, we risk shipping a response that contradicts content the Account Team has already written and circulated. Tracked as **open deliverable B-1**.

**1. Questionnaire CSVs** — these are the most recent, most commitment-bearing artefacts. If we told WPP in writing that we "can do X today," the main-document narrative must not soften to "we will be able to do X."

**2. Solution.md** — detailed architecture of record. Wins on implementation detail when the narrative MD is thinner.

**3. Response-technical-sections.md** — narrative of record. Wins on framing and argumentation when the solution MD is too internal or too technical for an evaluator audience.

**Conflicts are flagged for human decision**, not silently resolved, when the disagreement is material (different product names, different roadmap dates, different scope claims).

## 5. Content plan — section by section

Section numbers below match the master docx (as extracted into `scratch/wpp-master-extract.md`). For each section: WPP requirements served; narrative purpose; content outline; source attribution; gaps or conflicts to flag.

### §0. Executive Letter

**Status:** Already written. Leave untouched.

### §1. Response Navigator

**§1 body (summary sentence).** Already written.

**§1.1 "Mapping WPP's Vision to Our Response" table.** The right-hand column ("Our Section(s)") is empty. Fill with exactly these references:

| Evaluation Domain | Weight | Our Section(s) |
|---|---|---|
| Control Plane & Human Supercharger | 20% | §5 (Control Plane), §9 (Development Experience), §10.1/10.2 (POC Control Plane demos), §14.3 Appendix C (Fleet Dashboard wireframe) |
| Multi-agent orchestration & durability | 20% | §6 (Multi-Agent Orchestration), §4.1 (agentic loop), §10 (POC orchestration evidence) |
| Governance, security & compliance | 20% | §7 (Governance), §4.2 (Governance layer), §11 (NFRs on compliance) |
| System integration & protocol support | 15% | §8 (System Integration & Protocols), §4.2 (Integration layer) |
| Advanced capabilities (POC 2 scope) | 15% | §10.2 (POC 2 HR), §14.2 Appendix B (POC 2 technical design) |
| Vendor partnership & commercial model | 10% | §12 (Commercial & Partnership), §12.5 (Talent & Enablement), §12.6 (Becoming Frontier) |

Source: authored from this spec; no MD source.

### §2. The Paradigm Shift: Agents as Digital Labour

**Status:** Already written (§§2.1, 2.2, 2.3). Leave untouched. This is the opening argument; the account team has crafted it carefully.

### §3. Reading WPP's Ambition: Our Understanding of Project Apex

**Status:** Largely already written. Three things to resolve:

**§3 inline placeholder 1** — `<<Add something about governance in the "legacy" platform – i.e. how do we position Entra, Purview etc, APIM etc>>`

**Content to inject (authored, ~150 words):**
> The existing Microsoft governance stack that WPP already operates — Entra ID, Purview, Defender, APIM — was designed for humans and extended for agents without a parallel control system. Entra provides first-class agent identity (Entra Agent ID) with the same Conditional Access, RBAC, and audit semantics WPP uses for its 85,000+ employees. Purview extends DLP, sensitivity labels, retention, and eDiscovery to agent interactions. Defender provides threat detection across agent activity. APIM AI Gateway governs every model call, tool call, and A2A handoff with policy-as-code via APIOps. Governance changes are PR-reviewed, audit-trailed, and environment-scoped — the same engineering discipline WPP applies to any production system. There is no "agent shadow governance" to build; there is only the existing estate, extended.

**§3 inline placeholder 2** — `<<Add some details>>` under "Enterprise Applications":

**Content to inject (authored, ~100 words):**
> WPP's enterprise estate includes M365 (7 tenants, 95%+ employee coverage), Dynamics 365 (CRM and F&O), Workday HCM as staff identity source-of-truth, ServiceNow for ITSM, SAP BFC and Deltek Maconomy for finance, and the Power Platform (Dataverse, Power Apps, Cloud Flows, Power Automate Desktop, Copilot Studio) for low-code application and agent development. Okta is the federated identity broker. The agent framework integrates into all of these via MCP servers governed through APIM AI Gateway — no agent has a privileged path around the gateway, regardless of which surface invoked it.

**§3 inline placeholder 3** — `<<Add something about the strategy benefiting from the combination of Power Automate and Agentic Workflows – simplified integration>>`

**Content to inject (authored, ~120 words):**
> The combination of Power Automate (deterministic, rule-driven) and agentic workflows (probabilistic, reasoning-driven) is not a choice between tools — it is a layered composition. Power Automate workflows execute explicit, predefined steps where the same input must always produce the same outcome; they are ideal for finance operations and regulated processes. Agentic workflows handle cases that require reasoning over unstructured input, judgment, or dynamic tool selection. In Microsoft's framework both coexist: a Power Automate flow can be exposed as an MCP tool callable from an agent executor, and an agentic workflow can invoke a Power Automate flow when a deterministic sub-step is required. The integration surface is APIM, so governance, audit, and cost attribution are uniform across both.

**§3 "L4: Control Plane" subsection — inline placeholder** — `Cut and paste below from Artur's document…`

**Action:** Remove this placeholder text. Replace with the full content from `response-technical-sections.md` §4.3 (Control Plane Architecture — ~40 lines including the 8-row capability table). The two-paragraph existing content below the placeholder (Foundry Control Plane + Custom Control Plane UI) already matches — do not duplicate. Only the preamble sentence needs replacement with nothing; the existing content stands.

**Conflict to resolve:** §3 references a "Five-Layer Enterprise AI Stack" (L0 UX, L1 Intelligence, L3 Agent Framework, L4 Control Plane, L5 Governance). This does not appear in the vendor brief .docx. WPP's Q&A provides a hyperlink to an Appendix B PDF ("Control Plane Diagrams") that likely contains this model. **Decision needed from user:** (a) confirm the five-layer model exists in that PDF before presenting it as authoritative, or (b) reframe our own architecture around WPP's actual stated structure (Data Plane / Control Plane + Agent Framework / Agent Surface). The response currently adopts the five-layer model as if authoritative — high-risk claim if WPP's evaluators don't recognise it.

**L2 section** is referenced by name ("L2") but no L2 heading exists in the current master. Check with user: was L2 deliberately omitted, or is it a gap?

### §4. Reference Architecture: The Frontier AI Agent Platform

**§4.1 Design Philosophy** — already written (three principles + three sub-principles). Leave untouched.

**§4.2 Architecture Layers table** — already populated in the extract. Verify it matches the final "five-layer vs Apex" decision from §3 above. If we reframe to 2-plane + 2-layer, this table needs restructuring.

**§4 body after table** — **gap**. The master guidance says "This is the heavyweight section." Currently ends with the §4.2 table. Need substantive architecture narrative here.

**Content to inject (authored, drawn from `response-technical-sections.md` §4.1 and `solution.md` §§1–3, ~800 words):**
- The determinism ↔ agentic spectrum as the architectural frame
- Three-layer execution model (Durable Functions + MAF + GHCP SDK sessions) — one paragraph each, with the table from `response-technical-sections.md` §4.1 adapted
- Skill crystallisation as the maturity path
- Central governance sitting alongside (API Center + APIM, Foundry Control Plane, Agent 365 + Entra)
- Intelligence Layer (Foundry IQ + Fabric IQ + Work IQ) — one paragraph
- The "GA foundation / replaceable runtime" framing

Source priority: `response-technical-sections.md` §4.1 for narrative; `solution.md` §1 for the determinism-spectrum framing that grounds it.

### §5. Control Plane – Controlling agent fleets

**The single highest-weighted section (20%) and the #1 scoring determinant across all three briefs.** Must not be underweight in the response.

**Master status:** Empty body after the lead-in sentence.

**Primary source: `WPP-Control-Plane-Integration-Architecture-v7.pdf`** (11 pages, authored 2026-04-15, positioned as §4.3.2 Control Plane Integration Architecture). Per source-precedence rule #0, this PDF's content outranks `response-technical-sections.md` §4.3 and `solution.md` §11 for the Control Plane section. The MDs are now supporting source material, not primary. The PDF's structure defines §5.x subsection numbering below.

**Numbering note:** the PDF labels itself §4.3.2, which implies an outline where Control Plane is §4.3 (inside Reference Architecture §4). The current master docx places Control Plane at §5 (top-level). The populator must adopt the master's numbering — inject at master §5, re-label PDF subsection headings from §4.3.2.* to §5.*. Flag to the account team so the PDF-as-attachment (if it also ships standalone) and the master-document numbering reconcile before submission.

**Content to inject (authored, ~2500 words — larger than original estimate because the v7 PDF has substantially more detail; structured as):**

**5.1 Why the Control Plane is the product.** Open by quoting the WPP anti-requirement verbatim: vendors showing only Teams chat / Copilot Studio bots / email approval flows score **zero** on Control Plane criteria. State our thesis: the Control Plane is where WPP's managers supervise digital labour at 1:20–50 ratios. It is not a dashboard. It is not Copilot Studio. It is a purpose-built operator experience powered by Fleet Manager agents.

**5.2 Two-layer architecture.**
- **Foundry Control Plane** (platform governance, existing product): fleet health, agent inventory, model registry, guardrails config, continuous evaluation, Defender/Purview integration. Covers WPP Refs 8.1, 8.5, 8.14, 22.3.
- **Custom Control Plane UI** (operator experience, custom React + Fleet Manager): exception-only queue, bulk HITL, autonomy dials, skill amplification, role-based views, cost dashboard, AG-UI dynamic components. Covers WPP Refs 31.1–31.5, 21.1, 10.1, 26.4, 5.3.

**5.3 Fleet Manager agents.** Always-on GHCP SDK Hosted Agents on Foundry, domain-scoped (Hiring, Finance, Compliance). Consume telemetry via Event Grid. Reason about fleet health, SLA risk, anomalies. Compose the exception queue. Push assessments via SignalR. This is agentic governance, not human-eyes governance — essential for WPP's scale.

**5.4 Capability table.** Port directly from `response-technical-sections.md` §4.3 (the 8-row table: Fleet Dashboard, Exception-Only Queue, Instant Situational Awareness, Bulk HITL, Autonomy Dials, Skill Amplification, Role-Based Views, Cost Dashboard, AG-UI) with WPP Ref column preserved.

**5.5 Autonomy dials — the runtime-adjustability question.** The brief demands runtime-adjustable dials; governance discipline demands audit-trailed change management. Our answer: **both.** Dials are adjustable in the Control Plane UI in real time, effective immediately on active workflows, and every change is audit-logged with operator identity, timestamp, rationale, and effective scope. For high-risk threshold changes (e.g. lowering HITL gate thresholds), dual-control is required — two operators from two distinct Entra groups. Runtime speed without runtime chaos.

**5.6 AG-UI.** Dynamic agent-rendered components over SSE, APIM-mediated. MAF agent executors emit AG-UI events; the Control Plane UI renders them. No hardcoded UI per workflow type. Addresses §5.3 "AG-UI or equivalent: Must support".

**5.7 Data sources for the custom UI.** App Insights APIs (traces, cost), Foundry REST APIs (agent inventory), APIM metrics (token consumption), workflow state store in Cosmos DB (phase status, approvals, action ledger), Fleet Manager assessments (SignalR + AG-UI real-time streams).

**5.8 Cross-references.** Points to §9 (builder experiences) for how Copilot Studio agents and GHCP SDK agents both appear in the Control Plane; to §10 for live demo evidence; to Appendix C for wireframes.

**5.9 Telemetry ingestion pathways** (from v7 PDF §1). Port the 9-row source × transport × data points × latency × consumer table verbatim (GHCP SDK sessions, MAF workflow graph, Durable Functions with dual-path Event Grid + App Insights, APIM AI Gateway, Cosmos DB, Foundry Agent Service, Foundry Evaluations, Content Safety / Guardrail config, Microsoft Defender for AI Services). Include the **standard correlation attributes** block verbatim: `workflow_id, phase, jurisdiction, model, agent_identity, skill, token_count` propagated across OTEL spans, Cosmos DB action ledger entries, and Event Grid event payloads.

**5.10 Integration hooks** (from v7 PDF §2). Three hooks with the **dual-path pattern** explicit: all hooks write state to Cosmos DB for persistence and publish events to Event Grid for real-time Fleet Manager consumption.
- **Hook 1 — GHCP SDK session hooks** (agent-executor level): intercept tool calls, model calls, non-revocable action attempts; write action-ledger entries classifying revocable vs non-revocable; detect violations (non-revocable without validator approval) and publish to Event Grid → Fleet Manager exception queue; **first enforcement boundary — agent cannot bypass it.**
- **Hook 2 — MAF workflow event callbacks** (workflow-graph level): executor lifecycle events (start/complete/fail/pause/resume); validator rejection events with reason + input + triggering policy; phase transition spans. Validator rejections become pre-built Fleet Manager exception-queue items.
- **Hook 3 — Durable Functions external events** (orchestration level): dual-path. Path 1 = Event Grid push (sub-second) for Fleet Manager real-time situational awareness. Path 2 = OTEL → App Insights for queryable analytics, SLA tracking, audit. Explicitly address "why both paths": Fleet Manager needs sub-second push; CP UI needs queryable indexed telemetry.

Capacity note: at 50 concurrent workflows, Event Grid carries ~200–500 events/hour; Event Grid auto-scales transparently; App Insights requires capacity planning (commitment tier, adaptive sampling, daily cap).

**5.11 Fleet Manager internals** (from v7 PDF §3). Not a pass-through — a domain-scoped GHCP SDK Hosted Agent that reasons over incoming signals and produces structured assessments.
- **Inputs** (Event Grid single push channel): DF lifecycle events, hook state-change events, operator config-change events. No polling of App Insights; Cosmos DB queried on-demand for context enrichment.
- **Outputs**: fleet health assessment; exception queue (prioritised by business impact × confidence × SLA urgency); situational context per workflow (pre-composed for <5s operator comprehension); crystallisation candidates (patterns suitable for deterministic graduation).
- **Delivery** (SignalR push): domain-and-role-scoped channels; AG-UI-shaped JSON payloads; Cosmos DB polling fallback if SignalR drops (30s interval, no data loss because assessments persist before push).

**5.12 Enforcement pathways** (from v7 PDF §4). The Control Plane is a control surface, not a monitoring dashboard. Operator actions flow back into the runtime through defined channels. Port the 6-row operator-action × mechanism × target × effect table verbatim (approve/reject HITL via DF `raise_external_event`; bulk approve via batch `raise_external_event`; adjust autonomy dial via Cosmos DB config write; trigger rollback via action-ledger-driven compensating actions; override model/tool via APIM policy update through APIOps; block/unblock agent via Agent 365 / API Center).

**Bidirectional data-flow summary:** telemetry flows IN (read-only, high-volume, real-time — OTEL to App Insights + Event Grid events to Fleet Manager). Enforcement flows OUT (write, low-volume, operator-initiated, audit-logged — DF events, Cosmos DB writes, APIM policy updates). Architecturally separated — telemetry pipeline cannot be affected by enforcement actions; enforcement actions produce their own Event Grid events for audit.

**5.13 Infrastructure topology** (from v7 PDF §5). Stable Azure PaaS resources per WPP tenant, scaling independently of runtime workloads. Port the 10-row component table (Azure SignalR, Event Grid namespace, Fleet Manager Hosted Agents, Application Insights workspace with 90d hot / 2y warm / 7–12yr archive tiering, Cosmos DB, Azure Functions Event Grid triggers, Custom CP UI as Azure Static Web Apps, Foundry resource + projects, Azure AI Content Safety, Microsoft Defender for AI Services — **GA for Foundry agents**). **Scaling independence** paragraph: adding concurrent workflows scales runtime (more DF instances, Hosted Agent replicas, APIM throughput) but does not change Control Plane infrastructure topology. Event Grid + SignalR + Cosmos DB auto-scale transparently. App Insights needs operational attention at scale (commitment tier upgrades, adaptive sampling, daily cap). **Infrastructure footprint is the same from 50 to 50,000 concurrent workflows.**

**5.14 Platform plug-in model — framework-agnostic onboarding** (from v7 PDF §6). A major differentiator.

> Any agent type that fulfils three requirements is visible and governable in the Control Plane: (1) OTEL spans with standard correlation attributes to App Insights, (2) Event Grid lifecycle events to the shared namespace, (3) Cosmos DB state writes using the standard schema.

Port the integration-effort-by-agent-type table (Foundry Hosted Agent: zero effort; Copilot Studio via Agent 365: thin Azure Functions adapter, reusable template; External agent via A2A + APIM: AgentCard + optional webhook; Custom third-party runtime: implement contract explicitly, SDK-agnostic, reference adapter provided). **Conclusion:** Control Plane infrastructure is framework-agnostic, consumes telemetry via open standards, does not require agents to use a specific SDK.

**5.15 Co-creation partnership framing** (from v7 PDF §7). The key strategic framing.

> *"WPP's Control Plane requirements exceed any out-of-the-box product available today. The 1:20–50 human-to-agent ratio, fleet-level exception surfacing, and intelligent autonomy management represent frontier capabilities that no vendor ships as a product. **This is not a product procurement. It is a co-creation partnership.**"*

Port the 5-row dimension × Microsoft provides × WPP provides × outcome table (platform infrastructure, custom CP UI, Fleet Manager agents, codebase ownership — **WPP owns the code, standard React + Azure PaaS, no proprietary lock-in** — and productisation — **Microsoft evaluates proven patterns for Foundry Control Plane roadmap H2 2027 candidates: exception-only queuing, bulk HITL, autonomy dials**).

This section cross-links to §12 Commercial & Partnership and to §13 Portability. **Flag to account team:** the commitments in the co-creation partnership table (WPP owns code, H2 2027 productisation roadmap, MCS engineering resources) are specific and contractually meaningful. Confirm endorsement before shipping — these claims must match §12 (Commercial & Partnership) and must not contradict anything in the Commercial Proposal the account team owns.

Source priority: **v7 PDF is primary.** `response-technical-sections.md` §4.3 and `solution.md` §11 supplement where the PDF is silent (e.g. the broad narrative framing in §§5.1–5.3 above). Conflict: the questionnaire-index agent flagged `§06 9.1` and `§15 19.2` as naming Copilot Studio as the "primary" low-code builder, while `§01 2.1` names "Control Plane UI skill library + template forge". **Resolution before docx populate:** We keep **Copilot Studio as the primary low-code builder for agent construction** (§9) and **the Control Plane UI skill library as the primary operator-facing tool for operational configuration** (§5). These are different personas, different tools. Update `response/questionnaire answers/01-platform-vendor.csv` to align (remove the "primary low-code builder surface" framing from the Control Plane skill library description).

### §6. Multi-Agent Orchestration and Durable Execution

**Master status:** Empty body after lead-in sentence.

**Content to inject (authored, ~900 words):**

**6.1 Two coordination substrates, layered.**
- **Within a phase — MAF workflow graph.** Pregel BSP execution, typed edges, fan-out/fan-in, conditional routing, validator executors, pause/resume. Stable orchestration patterns (sequential, concurrent, handoff, group chat, Magentic-One).
- **Across phases — Azure Durable Functions.** Long-running envelope, HITL waits at zero compute (days/weeks), timer escalation, checkpoint/replay, geo-replicated state. Invokes each phase's MAF workflow as a durable activity via MAF Durable Task extension.

**6.1a DF as the Azure-native equivalent of Temporal.** WPP's Apex diagrams reference Temporal as the expected workflow state store ("e.g. Temporal · Durable · Checkpointed"). Azure Durable Functions provides the same fundamental model: event-sourced execution history, deterministic replay-based recovery, checkpointed state in geo-replicated Azure Storage, zero-compute waits, timer-driven escalation, and compensating-action patterns for sagas. The differences are cloud-native integration (first-class in Azure Functions, co-deployed with APIM/Event Grid/SignalR without additional infrastructure) and licensing (GA, bundled with Azure Functions consumption plan, no separate Temporal Cloud or self-hosted Temporal cluster required). For WPP's Temporal mental-model, DF is a drop-in conceptual equivalent running natively on the Azure surface WPP has already standardised on.

**6.2 The Durable Agent Orchestration pattern.** Microsoft's productised Feb 2026 pattern composing DF + MAF + SignalR for long-running agent workflows with HITL. This is the architectural backbone — reference the Microsoft Learn tutorial.

**6.3 Agent executors and GHCP SDK sessions.** Invoked only from MAF agent executor nodes. Ephemeral. Load skills and MCP tools. Reason, call tools through hooks, emit OTEL, return typed result. Identity from the Hosted Agent container, on-behalf-of for human-triggered phases, app-only for autonomous phases.

**6.4 Skills, not separate agents — the architectural choice.** Port the full §18 analysis from `response-technical-sections.md` (the 11-row side-by-side trade-off table for 9-separate-agents vs skills-based). This directly addresses WPP's "9+ specialist agents" mental model from POC 2. We preserve specialisation; we change the coordination substrate. Critical honesty: if WPP evaluators prefer the separate-agent topology after review, both are supported; we can compose a hybrid (skills inside a domain, A2A across domains).

**6.5 A2A where it belongs.** Cross-organisation interactions with external agents (partner candidate agents, supplier pricing agents, jurisdictional compliance authorities) go through APIM A2A governance. Not for fragmenting a single domain's internal specialisation.

**6.6 HITL pattern in detail.** MAF executor detects human input needed → composes message/Adaptive Card → routes via human's preferred surface → signals DF to suspend → DF issues `wait_for_external_event` at zero compute → human responds → `raise_event` → DF resumes → next phase. Bulk approval raises events on multiple DF instances simultaneously. MAF also supports native pause/resume for shorter-lived HITL within a phase.

**6.7 Supported topologies end-to-end.** Sequential, parallel fan-out/fan-in, conditional, timer escalation, bulk HITL. Adaptive based on runtime data, not static DAGs.

Source priority: `response-technical-sections.md` §§4.4, 18; `solution.md` §7.

### §7. Governance as a First-Class Capability

**Master status:** Existing body has the bullets around L5 Human and Agent Governance + Entra/Purview/Defender, written as single-sentence headings (`#### paragraph`). Needs proper section structure.

**Rewrite strategy:** Preserve the narrative thrust of the existing prose but restructure as clean subsections. Keep the "treats agents as governed digital workers" conclusion. Add the five-enforcement-layer detail from `response-technical-sections.md` §6.

**Content to inject (authored, ~1500 words):**

**7.1 Agent identity and governance.** Entra Agent ID as first-class identity, domain-scoped. Table of Hosted Agent → Entra Agent ID → Tool Access (Hiring Agent, Finance Agent, Fleet Manager). Identity lives on the container, not the session. On-behalf-of vs app-only semantics. Agent 365 lifecycle management (activate, block, delete), Conditional Access for agents, Purview DLP integration, Defender threat detection. *Flag: Agent 365 GA date is May 2026 (today is 2026-04-15) — explicitly name this as "GA May 2026, actively in customer preview today," reconciling the questionnaire-index conflict where Agent 365 appears as both "GA May 2026 (roadmap)" and "Can do today" across different CSVs.*

**7.2 Per-skill tool allow-list (APIM-enforced).** Each SKILL.md declares allowed tools in frontmatter. On skill promotion (Design → Production), allow-list compiled into APIM policy fragment. Gateway-enforced, outside the agent runtime, cannot be bypassed by prompt injection. JWT claims carry skill ID / version / phase / jurisdiction.

**7.3 Non-revocable operations catalogue.** Each MCP tool declares `revocable: true|false`. Non-revocable invocations route through hook-enforced HITL gate regardless of skill or workflow. Catalogue is Git-committed and PR-reviewed. Port the 8-row table (send email, extend offer, submit payment, create JML ticket, post A2A, write master data, commit attestation, publish external) from `response-technical-sections.md` §6.1.

**7.4 Dual-control (four-eyes).** High-risk operations require two approvals from two distinct Entra identities in two distinct operator groups. Durable Functions enforces — orchestration does not advance until two distinct `raise_event` calls. APIM validates group claims. Second approver cannot be first. Both identities audit-logged.

**7.5 Five enforcement layers.** Port the 5-row table from `solution.md` §9 (MAF validators, Foundry Guardrails, APIM, Agent 365/Entra, Runtime Isolation). The LLM cannot bypass any of them.

**7.6 Observability and OTEL.** Three layers: Foundry Tracing (session-level OTEL), APIM metrics (token/latency/errors per model/tool/agent), Fleet Manager assessment (event-driven reasoning over telemetry). Cost attribution per workflow/phase/model/consumer. **Telemetry data classification:** spans carry IDs and counts only — no prompt or response bodies in App Insights. Bodies are redacted by Foundry Guardrails and stored in Log Analytics only. Reasoning chain stored separately from action ledger.

**7.7 Network and runtime isolation.** APIM is the only public edge. Private Endpoints for all backends. Azure Firewall Premium with FQDN allow-list for egress. Compute has no public IPs. Region-pinned per jurisdiction. **APIOps residency CI gate** rejects PRs registering cross-region backends. Port the 6-row boundary table and the 4-row data classification table from `response-technical-sections.md` §6.3 and `solution.md` §3.

**7.8 Data protection and compliance.** Three enforcement layers (Guardrails, APIM, Agent 365+Entra) summarised. Policy-as-code via APIOps. Jurisdiction switching (state carries `jurisdiction`, APIM routes, jurisdiction-specific skills load automatically). Audit retention 7–12 years, immutable via Azure Storage. Platform certifications (SOC 1/2/3, ISO 27001/17/18/27701, HIPAA, PCI, FedRAMP, GDPR, BSI C5). EU AI Act alignment through Responsible AI Standard + Guardrails + evaluators. Authoritative compliance matrix at Trust Center.

**7.9 Encryption, MFA, and secret management.** TLS 1.2+ everywhere, TLS 1.3 where supported. At-rest with MS-managed keys, CMK via Key Vault for regulated workloads. Double encryption for immutable audit export. Key rotation automated. MFA via Entra Conditional Access on every human path; phishing-resistant methods (FIDO2, Windows Hello, Authenticator with number matching); SMS/voice blocked. Agent actions use managed identities — no shared secrets.

Source priority: `response-technical-sections.md` §6, `solution.md` §§3, 9.

### §8. System Integration and Protocols Support

**Master status:** Empty body after lead-in.

**Content to inject (authored, ~900 words):**

**8.1 Protocol support.** Port the 5-row table from `response-technical-sections.md` §7 (MCP, A2A, OpenTelemetry, AG-UI, Structured Outputs) with status (GA / preview) and implementation notes.

**8.2 LOB application integration.** All enterprise systems as MCP servers governed through APIM. Auth abstracted at platform level — agent developers never manage tokens. Key Vault stores credentials; APIM injects at request time. Automated rotation without agent downtime. Port the system × auth × MCP table from `response-technical-sections.md` §8.1 (Workday, LinkedIn, Greenhouse, Graph, ServiceNow, D365, Maconomy, ACS, HeyGen, citizen-dev via Logic Apps). Supported OAuth grants: Auth Code, Client Credentials, SAML-bridged, PKCE, Device Flow, OBO.

**8.3 Surface-side integrations.** WPP §3.6 MoSCoW matrix answered line-by-line. The invariant: agent runtime invoked through APIM, governed identically regardless of surface. Port the 10-row surface table from `response-technical-sections.md` §8.2 (M365 Copilot, Control Plane UI, Web Portal, SharePoint SPFx, Power Apps, D365, .NET SDK, ServiceNow, Voice, Email).

**8.4 One agent, many surfaces.** Restate the WPP-required invariant: a single agent definition is deployable to any supported surface via configuration or thin adapter; not by duplicating agent logic. Concrete example: the Hiring Agent's Interview Coordinator skill is invokable from the HR BP's Control Plane UI, from the Hiring Manager's PA in Teams, from a ServiceNow form, and from an external candidate agent via A2A — the same MAF workflow executor handles all four.

**8.5 Cross-cloud discovery via API Center.** API Center registers MCP servers, skills, and APIs hosted anywhere — Azure-hosted Foundry models, GCP-hosted Vertex agents, AWS-hosted internal APIs, on-prem SAP. Single registry. Matches WPP's multi-cloud stated posture (Azure primary, GCP primary, AWS).

Source priority: `response-technical-sections.md` §§7, 8; `solution.md` §4.

### §9. Development Experience (All Builder Personas)

**Master status:** Empty body after lead-in.

**Content to inject (authored, ~1000 words):**

**9.1 One truth for how an agent is defined.** Lead with the WPP §6.5 anti-requirement: "Low-code artefacts must serialise to the same code/config format as pro-code. No divergent runtimes." Our architectural answer: every path — pro-code, low-code, Threadlight-generated, runtime-spawned — produces declarative, Git-committable artefacts on the same APIOps pipeline, registered in Azure API Center, governed by APIM, carrying Entra Agent IDs.

**9.2 Builder modes.** Port the 8-row table from `response-technical-sections.md` §9 (Pro-code, Low-code visual builder/Copilot Studio, Low-code MCP tools/Logic Apps, Low-code config/Control Plane UI, 60-minute build, Agentic builder, Runtime agent assembly, Threadlight).

**9.3 Copilot Studio as primary low-code.** This is Microsoft's flagship visual builder. Declarative YAML/JSON within Power Platform solutions. Git-committable via Power Platform ALM. Environments (Dev → Test → Prod). Registers in Agent 365 with first-class Entra Agent ID. Governed by APIM, Purview, Defender. Appears alongside GHCP SDK agents in the Control Plane. Meets §6.5 parity via declarative serialisation + Git-committable artefacts + shared governance pathway.

**9.4 60-minute build benchmark (§6.4).** Copilot Studio hits this natively: template → 3 MCP tool connectors (pre-wired auth/rate limits/content safety) → 3 knowledge sources from Foundry IQ → publish to Agent 365. End-to-end **<30 minutes** for a junior developer or seasoned UI user. Scripted as an observable task for POC evaluation.

**9.5 Agentic builder (design-time, §6.2).** A MAF agent executor generates SKILL.md files from natural-language specifications. Typed skill definitions with declared tools, model assignment, governance rules. Registered in API Center in Design state. Human reviews and approves to promote to Production. **Built and demonstrated.**

**9.6 Runtime agent assembly (§6.2).** MAF supports dynamic executor creation — a supervising executor can spawn sub-workflow or persistent sub-agent within a domain's Hosted Agent scope. Persistent spawned agents auto-register in Entra Agent ID + API Center (Design state). The agent runs in Design state until a human operator promotes it to Production — **no runtime escape from governance.**

**9.7 Threadlight accelerator.** Interview-capture agent producing SKILL.md files, MAF workflow graphs, MCP tool stubs. Same API Center pathway as hand-written skills. Not a black box — all artefacts Git-inspectable.

**9.8 Code-as-Truth in practice.** All agent artefacts Git-committable: skills as SKILL.md, MCP server code, APIM policies as code, MAF workflow definitions, Durable Functions orchestrations, autonomy thresholds. Every routing decision, model selection, and tool call fully traceable in OTEL spans and audit logs. Every action ledger entry links to the OTEL span that produced it. **A team of 5 developers manages 50 agents across dev/staging/prod using CI/CD pipelines with PR review gates.** Non-technical auditors inspect authorisations, actions, rationale via the Foundry Control Plane compliance dashboard and Log Analytics KQL.

Source priority: `response-technical-sections.md` §§9, 10; `solution.md` §10. Conflict resolution: **Copilot Studio is the primary low-code builder.** Control Plane UI skill library is for operational configuration, not agent construction. CSVs to correct: `01-platform-vendor.csv` 2.1 (remove "primary low-code builder surface" from Control Plane UI description).

### §10. Bringing It to Life: POC Approach

**Master status:** §10.1 and §10.2 headings exist with empty bodies.

**§10 introductory framing** — already written ("three phases that mirror how WPP thinks about risk"). Leave.

### §10.1 POC 1 — Finance: Intelligent Procure-to-Pay (Foundational)

**Content to inject (authored from `response-technical-sections.md` §12 + POC 1 brief, ~1200 words):**

Open with the WPP business problem: 15+ expense management systems, 100+ local policies, 130 FTEs reviewing manually, **VML NA pilot 97.6% classification accuracy benchmark** (Aug 2025). POC scope: **30–50 concurrent invoice workflows** through a single Finance Controller's Control Plane, spanning multiple EMS platforms, **system-agnostic operator experience**.

Then:

1. **Duration, operator, concurrency.** 8-week sprint. Finance Controller via Control Plane. 30–50 concurrent.
2. **Architecture.** Finance Agent (`finance-agent@wpp`) with domain-scoped skills: Intake/OCR (Document Intelligence), Validation (three-way match, duplicate detection), Routing (GL coding, cost centre), Approval (threshold-based + HITL), Payment (file generation), Reconciliation.
3. **Execution shape.** DF orchestration per invoice. Each phase is a MAF workflow graph. Most executors plain functions. Agent executors only where reasoning required. Validator executors before non-revocable actions.
4. **MCP integrations.** Workday, D365 F&O, Maconomy. All governed through APIM.
5. **What the POC demonstrates** (port the 14-item list from `response-technical-sections.md` §12, re-ordered to match WPP's acceptance criteria §4 in POC 1 brief):
   - Deterministic-by-default MAF graph (three-way match, payment file, routing = plain functions, no LLM)
   - Agent executors limited to low-confidence OCR, GL coding, exception classification — each followed by validator
   - Multi-phase DF orchestration with MAF workflow activities
   - HITL approval gates (Finance BP interacts via Adaptive Card in Outlook routed through PA, DF `wait_for_external_event` zero-compute)
   - Bulk approval for batched low-risk items
   - Rollback/compensating actions (non-revocable gated by hooks + MAF validators)
   - Fleet Manager monitoring 30–50 concurrent
   - Exception-only Control Plane view
   - OTEL cost attribution per invoice across all three layers
   - Foundry Guardrails inside agent executors (PII, content safety)
   - Full audit trail from receipt to payment
   - Mid-workflow platform restart with DF replay and MAF checkpoint resume
   - **Private network posture** (MCPs over Private Endpoints, egress via FQDN allow-list, APIM sole public edge)
   - **Non-revocable demo** (payment file with explicit dual-control gate — Finance Controller + Finance BP, distinct Entra identities; catalogue visible in Control Plane)
   - **60-minute build close-out** (junior developer builds 3-MCP + 3-knowledge-source agent via Copilot Studio in <30 minutes, scripted)
6. **Success metric.** Match or exceed the **97.6% VML NA classification accuracy** benchmark on the synthetic dataset WPP provides (3,430 lines).
7. **System-agnostic Control Plane proof.** Claims from Workday + at least one other EMS appear identically to the Finance Controller.
8. **Integration extensibility.** Describe adding a third EMS (Maconomy, Rippling, local) without modifying agent logic or Control Plane — MCP server added to the APIM registry, skill declares it as a tool, done.

### §10.2 POC 2 — People: Advanced Talent Lifecycle Agent Team (Frontier)

**Content to inject (authored from `response-technical-sections.md` §13 + POC 2 brief, ~1500 words):**

Open with the WPP framing: *"This is not a HR chatbot."* 1 HR BP operating Control Plane across 15–20 concurrent hiring workflows spanning agencies, markets, jurisdictions. Scenario: Senior Data Engineer hire at a US WPP agency. Five humans in four timezones. Compressed from 45–60 days to "days not months".

Then:

1. **Duration, operator, concurrency, cast.** 12-week sprint following POC 1. HR BP (London). 15–20 concurrent. Five humans: Hiring Manager (LA, Teams), HR BP (London, Control Plane), Finance BP (Mumbai, email), IT Ops (Chennai, ServiceNow), Candidate (external, web + voice).
2. **Architecture.** Hiring Agent (`hiring-agent@wpp`). Skills: Budget & Approvals, Job Design, Sourcing, Triage, Screening, Interview Coordinator, Compliance (jurisdiction-aware), Offer, Onboarding, Voice Screening.
3. **MCP integrations.** Greenhouse, LinkedIn, Workday, Graph (calendar/email), ServiceNow, ACS, HeyGen. All via APIM.
4. **Execution shape.** DF orchestration per hire. ~10 phases, each a MAF workflow graph. Deterministic executors dominate (sourcing queries, interview scheduling, JML provisioning, offer templating, HeyGen video generation). Agent executors bounded (JD drafting, CV scoring, voice screening, compliance narrative, offer personalisation). Validator executors between agent output and downstream action.
5. **What the POC demonstrates** (all POC 1 capabilities plus — port the 22-item list from `response-technical-sections.md` §13 mapped to POC 2's §4.1–§4.22 refs):
   - Layered orchestration (DF envelope 12 weeks + MAF graphs per phase + GHCP SDK sessions in agent executors)
   - Deterministic-by-default graphs annotated per phase (what is code vs what is LLM, transparent)
   - Voice screening (GPT-Realtime + ACS) with structured scoring validator
   - CV parsing with crystallisation pipeline (agent scorer → deterministic classifier in API Center, agent preserved as fallback)
   - Episodic memory (recall past hires levelled too low) via workflow state + Fabric IQ
   - A2A interop with external candidate agent (APIM-governed)
   - Jurisdiction-aware compliance (USA vs Germany switching via APIM routing + jurisdiction skills + Guardrails + MAF validators; works council, GDPR, EU AI Act)
   - Autonomy dials (auto-shortlist thresholds, runtime-adjustable, audit-trailed)
   - Skill amplification (Fleet Manager surfaces policy + precedents)
   - Process evolution (Fleet Manager proposes crystallisation candidates)
   - Synthetic CV evaluation (500 CVs via Foundry Evaluators for bias/accuracy)
   - Avatar onboarding video (HeyGen API MCP)
   - **Threadlight demo** (interview HR SME, produce executable skills in MAF graph)
   - 5 humans across 4 timezones on different surfaces simultaneously
   - **AG-UI dynamic components** (bulk-approval forms, interview scorecards, escalation cards rendered per workflow type by MAF executors)
   - **Runtime agent assembly demo** (Threadlight captures new jurisdiction pattern mid-POC, generates SKILL.md, auto-registers in Entra + API Center Design state, human promotes to Production — live in next workflow without redeploy)
   - **Databricks/Snowflake federation demo** (Fabric IQ queries levelling history in Unity Catalog via OneLake shortcuts — no migration)
   - **Private network + residency posture** (German hiring routes only to EU model + EU Log Analytics; APIOps rejects deliberate cross-region PR — live CI gate demo)
6. **On the Regional Sovereignty Exercise (Appendix B of POC 2).** Flagged as tie-breaker, shortlist-only, not required in initial response. Our response should **acknowledge** it (show readiness) but not over-invest in written detail. Brief summary: data residency enforced at runtime (Guardrails + APIM routing + APIOps CI gate); German employment law (Compliance Agent with BetrVG skill + Foundry IQ DE corpus); jurisdiction switching (state-driven, skills-driven); EU AI Act conformity (mandatory human oversight + technical documentation + Foundry Evaluators); runtime compliance monitoring (Fleet Manager + Defender alerts). See §7.8 of this response.

### §11. Non-Functional Requirements

**Master status:** Empty body after lead-in.

**Content to inject (authored from `response-technical-sections.md` §11, ~400 words):**

Port the 9-row NFR table with GA/preview/roadmap tagging (Availability 99.9%/region, RTO <5min, RPO near-zero, Control Plane latency <5s, Concurrent workflows 5k pilot / 50k prod, Audit retention 7–12 years, Data residency platform-level, Workflow state survives full restart).

Add a short narrative:
- **99.9% per region, multi-region DR via Azure Traffic Manager + Cosmos DB automatic failover + DF replay.** Azure financially-backed SLAs.
- **Cost attribution and control at scale** — 500 concurrent × 30 markets × varied model usage means token spend is operational risk. APIM per-model/per-team/per-workflow token metrics + budget enforcement, visible in the Control Plane cost dashboard. Semantic caching reduces redundant inference cost.
- **Region-pinned per jurisdiction — enforced at platform level, not developer-configured.** APIOps residency CI gate rejects cross-region backends before deployment.
- **Reference architecture for 50,000+ concurrent workflows** — provided separately on request; same architecture, scaled via DF auto-scaling, Cosmos DB horizontal partitioning, multiple Hosted Agent deployments, tiered model usage, skill crystallisation to reduce inference bottleneck.

### §13. Portability and Exit Strategies

**Master status:** Empty body after lead-in.

**Content to inject (authored from `response-technical-sections.md` §17, ~400 words):**

Port the 8-row portability table (Agent logic → MIT GHCP SDK + SKILL.md; Models → Foundry catalogue 1900+ or any MCP-accessible; Tool layer → MCP open standard; Interop → A2A open standard; Telemetry → OTEL open standard; State → Cosmos DB JSON exportable; Orchestration → DF Azure-specific but pattern reproducible on Temporal/AWS Step Functions; Policies → APIM exportable).

Explicit exit strategy: export skills (Git), export MCP servers (code), export state (Cosmos DB standard export), export policies (APIM export). The agentic logic sits in portable artefacts.

**The honest framing of preview-dependency** (port from `response-technical-sections.md` Appendix: Known Constraints): separates **GA foundation** (DF, APIM, API Center, Cosmos DB, Foundry runtime, MAF v1.0, Entra, Log Analytics, App Insights) from **replaceable agent runtime layer** (GHCP SDK). Preview-layer risk confined to the runtime, not distributed across the stack. If GHCP SDK stalls or WPP prefers different, the runtime swaps; skills, tools, graphs, governance, data layer, Control Plane all remain.

Port the 12-row Known Constraints table (GHCP SDK tech preview, MAF v1.0 young, Foundry Hosted Agents max 5 replicas preview, Guardrails tool-call interception preview, APIM A2A preview, API Center skill registry preview, GHCP SDK + Foundry integration adapter work, Agent 365 GA May 2026, IQ products preview, MAI-Voice-1 preview, Copilot Studio on Foundry not supported but Copilot Studio via Agent 365 supported). Each with mitigation.

### §14. Appendices

**§14.1 Appendix A: Completed Assessment Questionnaire.** Replace the existing body with a single sentence: *"Submitted separately as `wppetai-agentic-framework-assessment-questionnaire-microsoft-response.xlsx`. Every answer cross-references by Ref ID to the questionnaire and traces to a specific capability or service in §4."* The Deliverable 2 tool produces this xlsx.

**§14.2 Appendix B: Detailed POC Technical Designs.** Inject prose-only extraction from `solution.md` (skip the tables and diagram-references that lose meaning without images; keep the narrative). Subset:
- `solution.md` §1 Principles (the determinism ↔ agentic spectrum, three-layer model, by-default/by-exception, skill crystallisation, why GHCP SDK — narrative prose only)
- `solution.md` §2 Approach (the approach paragraph + skills/MCP/hooks/structured-outputs/AG-UI/human-interaction summaries)
- `solution.md` §3 Architecture — Identity & Access, Authorisation & Non-Revocable, Network & Data Boundaries, Human Interaction Model, Flow (Hiring Workflow narrative walkthrough)
- `solution.md` §14 POC 1 Finance P2P (full section)
- `solution.md` §15 POC 2 HR Talent (full section)
- `solution.md` §16 Known Constraints (the prose paragraph + the 12-row table in text form; if the table is dropped per "no complex tables," render each row as a bullet)

**§14.3 Appendix C: Architecture Diagrams.** **Parked** — diagram production is a separate work item. Populate with a single sentence: *"Architecture diagrams supplied as separate PDF deliverable — see Enterprise Architecture Diagram, C4 Context/Container/Component, Control Plane Fleet Dashboard wireframe, Agentic Loop state diagram."*

**§14.4 Appendix D: Customer Stories & Proof Points.** Already partially written (Industry Benchmarks with Gartner / Forrester / IDC mentions). Preserve; the Account Team is responsible for the Financial/People AI Transformation Reference Points subsection.

## 6. Conflict resolutions (LOCKED 2026-04-16)

All decisions confirmed by user. Each row below gives the decision and the concrete action items that flow from it. These drive Phase 0 CSV edits and Phase 3 content-authoring framing.

| # | Conflict | Decision | Action items |
|---|---|---|---|
| 1 | Primary low-code builder | **Copilot Studio is our low-code answer IF WPP insists, BUT we do not recommend any low-code agents for this design.** Position: MAF + skills + agentic loop is recommended because skills can build more skills and the agentic loop expands itself. Integration from Control Plane to Copilot Studio is explained elsewhere — do not duplicate in master §5 or §9. | (a) Correct `01-platform-vendor.csv` row 2.1 — remove "primary low-code builder surface" from Control Plane UI skill library description. (b) In master §9 (Dev Experience), frame Copilot Studio as the low-code answer but explicitly recommend the pro-code MAF+skills path for this engagement. (c) In master §5 (Control Plane), do not re-explain Copilot Studio integration — reference elsewhere only. |
| 2 | Agent 365 GA timing | **Agent 365 is GA May 2026. NOT "can do today."** | Edit all CSVs claiming Agent 365 capabilities as "Can do today" to "Preview today, GA May 2026" (or equivalent). Target CSVs: §07, §14, §15, §17, §18, §20, §27 (verify scope during Phase 0 CSV pass). Entra Agent ID stays usable independently. |
| 3 | Threadlight readiness | **Threadlight ready for POC (Option A confirmed).** | No CSV changes. Keep current claims in §§01, 06, 15, 19, 23, 27. §9.7 content stands. |
| 4 | Foundry Hosted Agents GA | **Hosted Agents are NOT GA. Backup: GHCP SDK + MAF Workflow on Azure Container Apps (GA). Difference from Hosted Agents is "really negligible."** | (a) In §5.13 infrastructure topology table, add Container Apps as GA-today fallback path alongside Foundry Hosted Agents (preview). (b) In §13 Known Constraints, the Foundry Hosted Agents row must reference Container Apps as mitigation. (c) This strengthens the GA-foundation story — name it in §5.13 and §13. |
| 5 | `response-technical-sections.md` §18 refs | §18 verified to exist. No action. | — |
| 6 | Builder taxonomy | **8-row table from `response-technical-sections.md` §9 is canonical.** | Update §06 CSV 9.1 and §15 CSV 19.2 to match the 8-row taxonomy. Master §9.2 uses this table directly. |
| 7 | Five-layer Apex model alignment | **Master §3's L0–L5 labelling does NOT match WPP's actual Apex L1–L5 (verified via `WPPET-4-Apex-diagrams.pdf`). Decision: leave master §3 AS-IS.** The account team used L0–L5 informally without aligning to the Apex document; user accepts the mismatch; no footnote/disclaimer. | No content edit. **Known residual risk:** evaluators aware of WPP's own Apex framework may notice the mismatch — documented in §11 Risks. |
| 8 | L2 missing in master §3 | **Leave as-is (user decision).** Per #7, master §3 is not being reframed to match Apex. L2 absence stays an editing artefact. | No action. |
| 9 | Autonomy dials framing | **Embrace runtime-adjustable dials (Option A — meets WPP's explicit ask). BUT explicitly recommend dials NOT be enabled on production systems, or at least have a high degree of control when enabled.** | Rewrite master §5.5 to include a "Production recommendation" paragraph — runtime-adjustable capability provided and demonstrated; for production, recommend one or more of: tighter operator-group restrictions, dual-control on threshold changes, PR-gated promotion of threshold changes between environments, or disabling runtime adjustment entirely in production with change-request workflow instead. Phrase as sound-governance advice, not pushback. |
| 10 | MAI-Transcribe-1 / Guardrails / Copilot Studio licensing | **Verify against current MS release notes (Option A).** Claude to run during Phase 0. | Run release-note check (~30 min). Update CSVs and §13 Known Constraints consistently based on findings. |

### v7 PDF gate decisions

| Gate | Decision | Action items |
|---|---|---|
| B-2 | Account team endorses v7 PDF §7 co-creation commitments (WPP owns code; H2 2027 Foundry Control Plane roadmap items; MCS engineering resources). | §5.15 content stands. Keep exact language from v7 PDF when porting. |
| B-3 | Populator handles §4.3.2 → §5 re-labelling automatically when porting. | Implemented in `populate_docx.py` as part of MD rendering. No human gate. |

### Additional framing decisions captured during conflict resolution

- **Temporal / Durable Functions mapping (new framing for master §6 Multi-Agent Orchestration).** WPP's Apex diagrams explicitly name Temporal as the expected workflow state store ("e.g. Temporal · Durable · Checkpointed"). Our architecture uses Azure Durable Functions. §6 must proactively position **DF as the Azure-native equivalent of Temporal** — event-sourced durable execution, identical checkpointing semantics, native Azure Functions integration, same replay-based recovery model. Goal: the evaluator's Temporal mental-model maps cleanly to our answer without friction.

- **WPP's Apex PDF Diagram 1 is an explicit anti-pattern (new framing for master §5 Control Plane).** WPP's own `WPPET-4-Apex-diagrams.pdf` Diagram 1 shows a single Copilot Studio / MS Teams chat surface labelled with a "LIMITATIONS OF CURRENT MODEL" block listing every flaw (no fleet view, no bulk approval, no cross-workflow context, no runtime autonomy adjust, sub-agents hand-coded in Studio, single human can't govern 20+). **Reference this directly in §5**: *"WPP's own Apex Diagram 1 illustrates the chat-surface pattern as the anti-requirement. Our Control Plane answers the positive operating model WPP has drawn in Diagrams 2–4 (1 Human × 25 Agents, 3 Humans × 25 Agents with role-scoped exception queues, 3 Humans × 1 Agent Type × 10 Parallel Instances)."* This turns WPP's own artefact into evidence of alignment.

- **Apex diagrams 2–4 reference for §5.** Diagrams 2, 3, 4 canonicalise WPP's expected Control Plane shape. Our §5 narrative aligns with each: Diagram 2 → single HR BP governing 25 concurrent workflows, fleet dashboard + autonomy engine + exception queue (matches our §5.4 capability table). Diagram 3 → multi-operator with role-filtered views, RBAC, bulk HITL (matches our §5.4 Role-Based Views + Bulk HITL rows). Diagram 4 → jurisdiction-aware agents with per-agency auth scope (matches our §7.8 jurisdiction switching + §5.12 per-workflow cost attribution). §5 should reference the diagram numbers explicitly to signal deep engagement with WPP's own framework.

## 7. Additional deliverables beyond the master docx

WPP's §8 Deliverables list requires more than what the master docx produces. Gaps:

| WPP Deliverable | Status in master | Action |
|---|---|---|
| 1. Completed questionnaire response (Excel) | Appendix A is pointer-only | Deliverable 2 of this spec (questionnaire xlsx builder) |
| 2. Long-form written response | Master docx | Deliverable 1 of this spec |
| 3. Enterprise Architecture Diagram | §14.3 parked | **Separate deliverable — out of scope for this spec** |
| 4. C4 diagrams (Context/Container/Component) | Not present | **Separate deliverable — out of scope for this spec** |
| 5. POC 1 Solution Architecture & Design | §10.1 + §14.2 | In scope (content plan §5) |
| 6. POC 2 Solution Architecture & Design | §10.2 + §14.2 | In scope (content plan §5) |
| 7. PRD per POC | Not present in master | **User decision: add §10.1.1 / §10.2.1 PRD subsections, or separate PRD documents?** |
| 8. NFR response table | §11 | In scope (content plan §5) |
| 9. High-Level Delivery Plan | Not present in master | **User decision: add §12.7 Delivery Plan, or separate doc?** |
| 10. Commercial Proposal | §12 | Already written by account team — untouched |
| 11. Testimonials + 3 references | §14.4 stub | **Account team task — out of scope for this tool, but master has the stub** |

Flagging gaps 3, 4, 7, 9, 11 as work items needing owners. The docx populator cannot invent content for them.

## 8. Tool architecture — Deliverable 1 (docx populator)

### 8.1 Module layout

```
helpers/
├── populate_docx.py                 # Entry point
├── docx_populate/
│   ├── __init__.py
│   ├── content_plan.py              # Authored content blocks keyed by target heading
│   ├── placeholders.py              # <<...>> and "Cut and paste..." resolvers
│   ├── heading_matcher.py           # Walks master, locates block items by heading text
│   ├── md_to_docx.py                # Lightweight MD → python-docx paragraph renderer
│   └── table_cell_filler.py         # Fills empty cells in existing master tables
└── csv_loader.py                    # Shared — reads the 29 CSVs (used by Deliverable 2)
```

### 8.2 Key design choices

- **No external rendering dependency.** Pure python-docx. `md_to_docx.py` is a 100–200 line internal renderer that handles the MD subset we actually use: paragraphs, bullets, numbered lists, bold/italic runs, hyperlinks. No full-markdown parser, no pandoc. Tables in the master are NOT rebuilt from MD source — if a table is in scope, the authored content in `content_plan.py` writes it using python-docx Table API directly.
- **Append-after semantics.** For each stub section, the tool matches the heading, walks to the next same-or-higher-level heading, and appends authored content as the last block(s) under the matched heading. Existing master lead-in prose is preserved.
- **Style mapping.** Injected paragraphs use existing master styles discovered in the extract: `heading 10` / `heading 20` / `heading 30` for headings, `List Paragraph` for bullets, default for body. `md_to_docx.py` sets `paragraph.style` by name.
- **Existing table cell fills** use `table.cell(r,c).text = value` to populate empty `Our Section(s)` column in §1.1.
- **Inline placeholder replacement** walks paragraphs, finds the target paragraph by exact-text match, clears its runs, and inserts a new sequence of paragraphs (via XML-level `.addnext()`) carrying the authored content.
- **Output** `WPP-RFP-Response-Master-populated-YYYY-MM-DD-HHMM.docx` alongside the master in the OneDrive folder. Master never overwritten. Timestamped to avoid accidental collisions.
- **Dry-run mode** prints every intended insertion point + first 80 chars of content before writing the output file. Default behaviour.
- **Diff report** emits a markdown file next to the output docx listing: sections populated, sections skipped (with reason), inline placeholders resolved, inline placeholders left alone (with reason), conflicts detected (e.g. heading missing from master).

### 8.3 Content source: `content_plan.py`

The authored content from spec §5 is stored as Python string constants keyed by target heading. Example shape:

```python
# content_plan.py
CONTENT_BLOCKS = {
    "Control Plane – Controlling agent fleets": {
        "mode": "append_body",
        "source": "authored",
        "content": """
## 5.1 Why the Control Plane is the product
...
""",
    },
    "14.1 Appendix A: Completed Assessment Questionnaire": {
        "mode": "append_body",
        "source": "authored",
        "content": "Submitted separately as `wppetai-agentic-framework-assessment-questionnaire-microsoft-response.xlsx`...",
    },
    # ...
}
```

Where the content is directly ported from an MD source, `source` can be `"md:response-technical-sections.md#section-4.3"` and the tool resolves by MD-heading match. The MD-porting path handles the bulk of §§5–13 content; authored strings handle the inline placeholder fills, §1.1 table, §§14.1 and 14.3 appendix pointers, and the new §5.5 autonomy-dial framing.

### 8.4 Placeholder resolver strategy

Four inline placeholders, defined in `placeholders.py`:

```python
INLINE_PLACEHOLDERS = [
    {
        "match": 'Cut and paste below from Artur\'s document…',
        "resolution": "delete_paragraph",  # the actual content is below this line
    },
    {
        "match": '<<Add something about governance in the "legacy" platform',
        "resolution": "replace_with",
        "content": "..." # authored, from spec §5 §3 placeholder 1
    },
    {
        "match": '<<Add some details>>',
        "resolution": "replace_with",
        "content": "..." # authored, from spec §5 §3 placeholder 2
    },
    {
        "match": '<<Add something about the strategy benefiting from the combination of Power Automate',
        "resolution": "replace_with",
        "content": "..." # authored, from spec §5 §3 placeholder 3
    },
]
```

Match is prefix-based (first N chars) to tolerate minor variation in the placeholder text.

### 8.5 Acceptance criteria (Deliverable 1)

1. Running `python helpers/populate_docx.py --dry-run` prints an injection plan enumerating every target heading and every inline placeholder with first-80-char preview.
2. Running `python helpers/populate_docx.py` produces `WPP-RFP-Response-Master-populated-{timestamp}.docx` in the OneDrive folder, master untouched.
3. The produced docx opens cleanly in Microsoft Word with no corruption warnings.
4. Every target heading in the spec §5 content plan has its content populated.
5. Every inline placeholder listed in §8.4 is resolved (replaced or deleted).
6. The §1.1 Evaluation Domain table has all six "Our Section(s)" cells populated with the content from spec §5 §1.1.
7. All new prose uses Word styles that exist in the master (heading 10/20/30, List Paragraph, Normal).
8. No new tables are created (except where explicitly authorised in the content plan).
9. No images are embedded.
10. The diff report is generated.

## 9. Tool architecture — Deliverable 2 (questionnaire xlsx builder)

### 9.1 Module layout

```
helpers/
├── build_questionnaire_xlsx.py      # Entry point
└── xlsx_build/
    ├── __init__.py
    └── joiner.py                     # Join 29 CSVs in Ref order; produce xlsx from template
```

### 9.2 Key design choices

- **Input:**
  - Template xlsx: `C:\Users\...\RFx Documentation - Originals\wppetai-agentic-framework-assessment-questionnaire.xlsx` (157 rows, 5 columns: Ref, Section, Subsection, Question, MoSCoW)
  - Microsoft answers: all 29 CSVs in `response/questionnaire answers/` — each CSV adds 5 columns (Status, Response, Key Technologies, POC Demo, Reference)
- **Output:** `response/wppetai-agentic-framework-assessment-questionnaire-microsoft-response.xlsx`
- **Sheets:**
  - `Instructions` — copied verbatim from the template
  - `Questionnaire` — 158 rows (1 header + 157 data); 10 columns: WPP's original 5 + Microsoft's 5
- **Join key:** `Ref` column. Verify:
  - Every Ref in the template xlsx appears in exactly one CSV
  - No CSV has a Ref missing from the template
  - No Ref has two answer rows
  - The Question text in the CSV matches the Question text in the template (warn on mismatch — likely indicates WPP updated the questionnaire between export and answer)
- **Column order in output:** Ref, Section, Subsection, Question, MoSCoW, Status, Response, Key Technologies, POC Demo, Reference. Original 5 preserved in original order; ours appended.
- **Cell formatting:** preserve the template's existing formatting for the original 5 columns (use openpyxl `load_workbook` + cell-level copy). For our 5 added columns: text wrap on Response; standard width for Status / Key Technologies / POC Demo / Reference.
- **Reference column handling:** CSV `Reference` field contains pipe-separated URLs. In the xlsx, render as newline-separated text within the cell (Word-style wrapping).
- **Ordering:** sort by Ref in the natural order (1.1, 1.2, 1.3, 2.1, 2.2, 2.3, …, 33.4). Mostly already in order but verify via `packaging.version.parse` or a tuple sort.

### 9.3 Acceptance criteria (Deliverable 2)

1. Running `python helpers/build_questionnaire_xlsx.py` produces the submission xlsx.
2. The xlsx has exactly two sheets: `Instructions` (identical to template) and `Questionnaire` (157 data rows + header).
3. Every Ref from the template appears in the output; no Refs added; no duplicates.
4. The 5 original columns match the template verbatim.
5. All 5 Microsoft answer columns are populated for all 157 rows (no empty cells unless a CSV genuinely leaves a field blank).
6. The xlsx opens cleanly in Excel with no corruption.
7. A validation report prints to stdout listing: row count, any Ref mismatches, any Question-text mismatches between CSV and template.

## 10. Implementation sequence (to be refined by writing-plans)

Rough ordering for the execution phase:

1. **Conflict resolution pass** (§6 of this spec) — user confirms decisions on the 10 listed conflicts before any code runs. Updates to the 29 CSVs happen in this pass.
2. **Authored content block writing** — populate `content_plan.py` with the authored strings from spec §5. This is the single largest writing task and should happen up-front while the CSVs are being corrected in parallel.
3. **Deliverable 2 (xlsx builder) first** — shorter and mechanical. Unblocks the Appendix A separate submission.
4. **Deliverable 1 (docx populator) second** — depends on (1) and (2) being stable.
5. **Produce populated docx.** Dry-run, review diff report, produce real output, open in Word, spot-check.
6. **Architecture diagram deliverables** (out of scope here; parallel track).

## 10a. Open deliverables tracked outside this spec

| ID | Description | Owner | Blocking? |
|---|---|---|---|
| B-1 | Inventory pass over `MSFT_Response/` and related Account Team OneDrive folders to catalogue all authored v-PDFs and other submission-grade documents. Add each to source-precedence rule #0 and update affected master sections. Required before final submission. | User / Account team coordinated | Yes — must complete before final submit, not blocking spec-to-plan handoff today |
| B-2 | Validate with the account team that the v7 PDF's co-creation partnership commitments (WPP owns code; H2 2027 Foundry Control Plane roadmap items; MCS engineering resources) are endorsed and consistent with the Commercial Proposal in §12. | Account team (Scott + commercial lead) | Yes before submit |
| B-3 | Reconcile numbering: v7 PDF labels itself §4.3.2 while master places Control Plane at §5. Populator handles re-labelling automatically. | Tool | Not blocking — handled by populator |

## 11. Risks

- **WPP deadline 2026-04-23** is in 7 days. Scope must be ruthlessly policed.
- **Apex L1–L5 labelling mismatch (accepted residual).** Master §3's L0–L5 does NOT align with WPP's Project Apex L1–L5 definitions (WPP: L1 AI-Ready Data, L2 Workforce Design & Ontology, L3 Framework, L4 Control Plane, L5 Governance). Per §6 conflict #7 the mismatch is accepted as-is — no reframe. Evaluators familiar with the Apex framework may flag this. Mitigation relies on the strength of the content inside each of our layers, not on labelling alignment.
- **Content fidelity risk.** The authored content blocks in spec §5 (especially §§5.5 autonomy framing, §3 inline placeholders, §5.9–5.15 ported from v7 PDF) are drafts based on sources. User must review authored blocks before they ship.
- **python-docx known issues.** Complex hyperlink rendering, bookmark preservation, and paragraph-level XML manipulation can be brittle. Test the populator on a sample section before running full document. Fallback: inject plain paragraphs with master-default style; restyle manually in Word.
- **Architecture diagrams gap.** WPP-required deliverables (Enterprise Architecture Diagram, C4 Context/Container/Component, Control Plane wireframe, POC1 PRD, POC2 PRD, High-Level Delivery Plan, Testimonials & references) are not produced by this tool. Tracked as separate work items outside this spec.
- **Autonomy dials production posture (§6 #9).** We meet WPP's "runtime-adjustable" requirement but recommend against enabling in production. If WPP evaluators read this as pushback against their explicit ask rather than sound governance advice, it may score worse than silent acceptance. Mitigation: frame as "capability provided and demonstrated in POC; production hardening recommendation follows from audit and dual-control principles the rest of the response emphasises."

## 12. Out of scope (explicit)

- Architecture diagrams (Appendix C parked; diagrams are a separate work item).
- Executive Letter, Paradigm Shift, Reading WPP's Ambition (already-written prose) — tool leaves these untouched except for the three §3 inline placeholders.
- Commercial & Partnership §12 — Account team owns.
- Competitive Positioning section at end of master — the outline says "(remove this)" — tool deletes it entirely, or user removes manually.
- Control Plane Diagrams PDF authoring — WPP provides; we consume via hyperlink.
- PR review of CSV corrections — human task.
- Word-level formatting polish (final page breaks, table styles, cover-page art) — human task post-populate.
