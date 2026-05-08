# POC 1 PRD — Finance: Intelligent Procure-to-Pay

> **ARCHIVED 2026-04-27.** This is the PRD as submitted to Zava on 2026-04-16,
> framed around invoice procure-to-pay. POC1 was subsequently re-scoped to
> **expense compliance** (the brief that followed). Kept as audit artefact.
>
> **Canonical current truth:** [poc1-brief.md](poc1-brief.md) (the addendum
> that drove the pivot) and [poc1-status.md](poc1-status.md) (build state).
> Pivot rationale: [superpowers/specs/2026-04-27-poc1-expense-compliance-pivot-design.md](superpowers/specs/2026-04-27-poc1-expense-compliance-pivot-design.md).

**Owner:** Microsoft (delivery); Zava AI CoE (acceptance)
**Status:** Submitted to Zava (superseded by expense-compliance pivot)
**Date:** 2026-04-16
**Timeline:** 8-week sprint from kick-off

## 1. Problem statement

Zava manages employee expense claims across **15+ expense management systems** — Workday, SAP Concur, Chrome River and local tools — governed by **100+ local policies** across markets and agencies, and reviewed by **~130 FTEs** conducting manual checks. Non-compliant spend is significant; detection is reactive; there is no proactive compliance culture.

The **August 2025 VML North America pilot** established the internal benchmark: **3,430 claims and USD 839K of spend processed through Workday with 97.6% classification accuracy** using a Red/Amber/Green policy model. That benchmark was single-EMS. POC 1 must reproduce the capability across multiple underlying systems behind a system-agnostic operator experience.

The core architectural principle is taken verbatim from Zava's POC 1 brief and preserved in our design:

> *"Agents operate the expense systems; humans operate the Control Plane. The Finance Controller never logs into Workday or Concur. They govern the agent fleet."*

Every requirement, success criterion and design decision in this PRD follows from that principle. Sources: Zava POC 1 brief §"Business problem" and §"Target operating model"; our response §10.1.

## 2. Goals

- **Primary.** Match or exceed the 97.6% R/A/G classification accuracy benchmark on Zava's synthetic 3,430-line dataset, with per-line policy-based reasoning per verdict. Sources: Zava POC 1 §4.5, acceptance #4; our §10.1 Success metric.
- **Secondary.** Demonstrate a system-agnostic Control Plane across at least two EMS (Workday plus one other — Concur, Chrome River or Maconomy). Sources: Zava §4.2, acceptance #9; our §10.1 "System-agnostic Control Plane proof".
- **Secondary.** Demonstrate a single Finance Controller supervising 30–50 concurrent expense workflows with exception-only surfacing. Sources: Zava §"Target operating model", acceptance #1, #2; our §10.1 "Duration, operator, concurrency".
- **Secondary.** Demonstrate zero-compute HITL waits, bulk approval of 10+ Amber items, and rollback/compensating actions for failed phases. Sources: Zava §4.3, acceptance #3; our §10.1; our §14.2 Appendix B.4.
- **Secondary.** Demonstrate infrastructure resilience: mid-workflow region failure recovery with zero data loss. Sources: Zava §4.11, acceptance #11; questionnaire row 29.
- **Secondary.** Produce a cost-per-task report on the Control Plane summarising agent compute cost, claims processed, breach rate and FTE equivalent. Sources: Zava §4.9, acceptance #13.

## 3. Non-goals

- Replacing existing EMS or Workday workflows. Agents operate them; Zava retains its EMS estate.
- Zava-wide rollout within the POC. Scope is demo-scale (30–50 concurrent workflows).
- Operator training and change management. Enablement is a separate programme.
- Building the full 85,000-seat production platform. This is a POC, not the partnership delivery.
- The Advanced Regional Sovereignty Exercise. Zava has flagged this as a shortlist-only tie-breaker for POC 2 (brief Appendix B) and it is out of scope for POC 1.

## 4. Users and personas

From the Zava POC 1 brief §"Human cast":

- **Finance Controller (London)** — Control Plane operator. Oversees all expense workflows, sets policy, approves threshold and autonomy changes.
- **SSC Expense Reviewer (Manila)** — reviews AI-classified claims; overrides verdicts; sets corrective actions for breaches.
- **Line Manager (various)** — receives breach notifications; approves high-value claims above their delegated authority.
- **Employee / Claimant (various)** — submits claims, receives compliance feedback, provides justification where a claim is flagged.

In our implementation each human has a personal agent surfaced in M365 Copilot via the M365 Agents SDK. The Finance Controller's primary surface is the bespoke Control Plane UI; approvers interact via Adaptive Cards in Outlook or Teams routed through their personal agent. Source: our §14.2 B.3.5 "Human Interaction Model".

## 5. User journeys and use cases

- **Happy-path claim (Green).** Employee submits a claim in Workday or Concur. The Intake skill normalises it, the Classification skill verifies policy fit and the Validation skill confirms the receipt. The claim is auto-approved, payment file generated via a deterministic MAF executor, reconciled and closed. The Finance Controller never sees it; it does not surface in the exception queue. Source: our §14.2 B.4 phase table.
- **Amber-path claim.** Claim scores Amber — a competing interpretation exists, or a confidence threshold is not met. It enters the SSC Reviewer queue sorted by severity, value and SLA urgency. The reviewer approves, overrides or escalates. The decision feeds the Arbitration skill's learning loop. Sources: Zava §4.5, §4.6; our §10.1 acceptance #8.
- **Red-path claim.** Claim scores Red against a named policy. The Notification skill contacts the claimant via Teams or email requesting justification. The Arbitration skill captures the response and routes to the Line Manager or SSC Reviewer according to the delegated authority matrix. Source: Zava §"Agent team".
- **Bulk approval.** Finance Controller reviews 12 low-risk Amber items grouped by policy reason, spot-checks two, applies a single bulk-approve action. Durable Functions raises `raise_event` on each orchestration in parallel; every item carries its own audit entry. Sources: Zava §4.3, acceptance #3; our §10.1.
- **Exception — missing receipt.** Intake flags a missing receipt. The agent queries the claimant via Teams. If no response within the SLA window, the workflow is flagged to the SSC Reviewer queue. Source: Zava §4.4 scenario.
- **Failure recovery.** A platform restart occurs mid-workflow. Durable Functions event-sourced replay resumes orchestrations from the last checkpoint; MAF graph state is preserved via the durable task extension. No in-flight claim is lost. Sources: Zava §4.11, acceptance #11; our §14.2 B.1.2, B.6.

## 6. Functional requirements

Mapped to Zava POC 1 brief §4.1 through §4.11. Status values are **Can do today** (GA stack), **Preview** (dependency on preview service) and **Needs POC validation** (demonstrable scope we will prove during the sprint).

| Ref | Requirement | Our approach | Status |
|---|---|---|---|
| 4.1 | Multi-agent orchestration: dynamic routing fast-track Green vs full-review Red; tiered models (cheap for OCR/keyword, frontier for nuanced policy); concurrent batches across EMS on one Control Plane | Durable Functions orchestration per claim; MAF workflow graph per phase with conditional routing; tiered model assignment via skill frontmatter and APIM AI Gateway; Fleet Manager composes the cross-agency view. Sources: our §10.1, §14.2 B.1.2, B.4; questionnaire row 07 | Can do today |
| 4.2 | System integration and auth: Workday (SAML-bridged via Okta), SAP Concur (OAuth 2.0), Microsoft Graph (OBO); platform-level auth abstraction; auto token refresh; credential vault; access audit; path to add a third EMS without modifying agent logic | APIM AI Gateway governs every MCP call; credentials in Azure Key Vault; Entra Agent ID for agent identity; OBO for human-triggered workflows, app-only for autonomous phases. Adding an EMS is register MCP server in APIM + declare in skill manifest + publish. Sources: our §10.1 "Integration extensibility", §14.2 B.3.2; questionnaire rows 02, 18, 20 | Can do today |
| 4.3 | HITL approval gates: threshold change without workflow restart; bulk approval of 12 Amber items with 2-item spot-check; <5 second click-to-context | Durable Functions `wait_for_external_event` holds at zero compute; threshold is a governance artefact read at event resume, not baked into the orchestration; Control Plane AG-UI composes bulk-approve action; OTEL telemetry enables sub-5-second situational awareness. Sources: our §10.1, §14.2 B.1.2, B.2.5; questionnaire rows 03, 06 | Can do today |
| 4.4 | Exception handling and self-healing: missing receipt (agent queries employee, SSC flag if unresolved); EMS timeout (exponential backoff retry); duplicate claim (auto-reject with audit entry) | MAF validator executors catch structural issues; GHCP SDK hooks and Durable Functions retry policies handle transient faults; duplicate detection is a deterministic executor. Sources: our §14.2 B.1.3, B.4; questionnaire row 09 | Can do today |
| 4.5 | Expense classification and policy reasoning: ≥95% accuracy vs 97.6% benchmark; policy-driven (policy document update changes behaviour without code changes); Amber cases include competing interpretations plus confidence score | Policy document is a first-class grounding artefact via Foundry IQ; classification skill emits structured output with per-line reasoning, confidence and competing interpretations; MAF validator asserts schema. Sources: our §10.1, §14.2 B.4; questionnaire row 12 | Needs POC validation |
| 4.6 | Behaviour change and progressive enforcement: closed-loop Detect → Notify → Arbitrate → Autonomous learning; initial-to-steady-state learning curve visible | Arbitration skill observes reviewer decisions and proposes autonomy changes as governance change-requests requiring Finance Controller sign-off (not auto-applied). Escalation skill tracks repeat offenders across time windows. Sources: our §10.1 acceptance #7; questionnaire row 17, and the position recorded in our memory that governance changes go through PR / change-request rather than instant-apply sliders | Needs POC validation |
| 4.7 | Memory and learning: procedural memory (e.g. London meal > GBP 75 with 4+ attendees consistently accepted → auto-accept proposal); episodic memory (category consistently Amber-but-accepted → reclass proposal) | Workflow state store plus Fabric IQ hold episodic memory; procedural memory surfaced as Fleet Manager proposals on the Control Plane awaiting operator approval. Sources: our §14.2 B.3, B.5; questionnaire row 12 | Needs POC validation |
| 4.8 | Audit trail and compliance reporting: every agent action logged (agent, system, decision, data, policy applied, approver); immutable, versioned, queryable; system-agnostic compliance view | Log Analytics plus Azure Storage immutable export with 7–12 year retention; reasoning chain stored separately from action ledger; compliance view composed over normalised action ledger. Sources: our §14.2 B.3.4 data-class table; questionnaire rows 05, 25 | Can do today |
| 4.9 | Cost-per-task awareness: weekly Control Plane report showing agent compute cost, claims processed, EMS breakdown, breach rate, FTE equivalent | OTEL spans carry cost attribution per phase and per model; Fleet Manager composes weekly report; AG-UI renders on Control Plane. Sources: our §10.1 acceptance #13, §14.2 B.3.4 telemetry row; questionnaire rows 13, 22 | Can do today |
| 4.10 | Process evolution: proven patterns crystallise from agent executor to deterministic code | Skill crystallisation pipeline: agent executor produces validated output over N workflows → promote to deterministic skill in Azure API Center → swap into MAF graph as plain function with agent executor retained as exception fallback. Sources: our §14.2 B.1.4, B.2.1; questionnaire rows 11, 23 | Preview |
| 4.11 | Infrastructure resilience: region-down recovery with 500 in-flight claims; no data loss; resume from last checkpoint in secondary region within RTO | Durable Functions event-sourced replay, geo-replicated state in Cosmos DB, region-pinned Hosted Agent pools, cross-region failover opt-in per workload. Sources: our §14.2 B.1.2, B.3.4, B.6; questionnaire row 29 | Can do today |

## 7. Agent team

Zava's POC 1 brief lists eight suggested agents. Our implementation consolidates them into a single domain-scoped Hosted Agent, **`finance-agent@zava`**, registered in Entra Agent ID, with a tool allow-list covering Workday (finance), D365 F&O and Maconomy. Specialisation is via SKILL.md files loaded per MAF agent executor — one identity, one audit surface, one allow-list, many capabilities. This avoids the "300 agents to manage" anti-pattern. The Fleet Manager (`fleet-manager@zava`) is a separate always-on agent with read-only telemetry access. Sources: our §10.1 "Architecture", §14.2 B.3.2.

| Zava-suggested agent | Responsibility | Our implementation (skill on `finance-agent@zava`) | Executor type |
|---|---|---|---|
| Orchestrator System | Receives expense batch triggers from each EMS; decomposes into classification workflows | Durable Functions orchestration + MAF workflow graph. No LLM at this layer | Plain (Durable Functions + MAF) |
| Intake and Normalisation Pipeline | Connects to each EMS via native API; normalises to common schema | `intake_normaliser` skill. OCR via Azure Document Intelligence as deterministic executor; `agent_field_extractor` only for low-confidence fields | Hybrid |
| Expense Classification Agent | Audits each line against applicable policy; produces R/A/G with reasoning | `expense_classifier` skill grounded by Foundry IQ policy corpus; structured output with confidence and competing interpretations | Agent (with validator) |
| Receipt Validation Agent | Analyses receipt image alongside structured data; detects mismatches, missing receipts, anomalies | `receipt_validator` skill; multimodal reasoning plus deterministic mismatch rules | Hybrid |
| Notification Agent | Contacts employee and line manager for material breaches; requests justification; applies threshold logic | `notification` skill; send actions gated by GHCP SDK hook and routed through the recipient's personal agent (Adaptive Card) | Agent (with hook-gated send) |
| Arbitration Agent | Captures justifications; presents to SSC Reviewer; learns from human decisions to recommend autonomy changes | `arbitration` skill; proposals surface on Control Plane as governance change-requests | Agent (with validator) |
| Escalation Agent | Tracks repeat offenders with progressive enforcement across time windows | `escalation` skill over workflow state store + Fabric IQ episodic memory | Hybrid |
| Audit Agent | Confirms immutable audit trail; generates compliance reports on demand | `audit_reporter` skill over Log Analytics + immutable Storage; report composition is deterministic | Plain (with agent for narrative summary) |

Source for column 3: our §10.1 "Skills", our §14.2 B.3.2 Hosted Agent topology, our §14.2 B.4 phase table.

## 8. Integration requirements

Platform-level auth abstraction is a stated Zava requirement (§4.2): developers do not manage tokens; the platform does. APIM AI Gateway brokers every call; credentials live in Azure Key Vault; identity is Entra Agent ID with OBO for human-triggered flows and app-only for autonomous phases. Sources: our §14.2 B.3.2, B.3.3; questionnaire rows 02, 18, 20.

| EMS / system | Auth pattern | Integration pattern |
|---|---|---|
| Workday (primary) | SAML-bridged via Okta | MCP server fronted by APIM; sandbox credentials supplied by Zava |
| SAP Concur | OAuth 2.0 | MCP server fronted by APIM; token refresh and vaulting handled by platform |
| Microsoft Graph | On-behalf-of (OBO) | Native OBO flow; surfaced through the personal-agent pattern for Teams and Outlook Adaptive Cards |
| Second POC EMS (Concur, Chrome River, Maconomy — TBC with Zava) | Per EMS | MCP server fronted by APIM; confirms system-agnostic Control Plane (acceptance #9) |

**Extensibility.** Adding a third EMS — Maconomy, Rippling or an agency-local tool — is three steps: register the EMS MCP server in the APIM AI Gateway registry; declare the new tool in the relevant skill manifest; publish. No agent logic changes. No Control Plane changes. This walkthrough is on-screen during the architecture segment of the demonstration, matching Zava acceptance #10. Source: our §10.1 "Integration extensibility".

APIM additionally provides a REST-to-MCP gateway that auto-generates MCP tool definitions from OpenAPI specifications — a supported path for Zava IT teams to expose their existing REST APIs without bespoke MCP server work. Source: our §14.2 B.2.2.

## 9. Control Plane requirements

The Control Plane is the POC 1 primary deliverable. Zava's anti-requirement is explicit and we quote it:

> *"A Copilot Studio bot answering 'what's the status of expense #1234?' is not a Control Plane. Neither is an Adaptive Card in an email."*

Our Control Plane is a bespoke React application consuming Fleet Manager telemetry via AG-UI over SSE, APIM-mediated for auth, rate-limiting and audit. It provides:

- **Fleet dashboard.** All 30–50 active workflows, filterable by policy, agency, market, risk, SLA, exception state, division and client.
- **Exception-only default view.** Routine Green workflows are hidden unless drilled into. Live demo will run 20 workflows with 3 exceptions surfaced (acceptance #2).
- **Sub-5-second situational awareness.** Click-in to any workflow returns full context — classification, policy applied, recommendation, options — within five seconds. OTEL-backed, Application Insights metric. Source: Zava vendor brief §5.4 NFR table.
- **Bulk HITL.** Approve, reject or redirect batches in a single action; each item retains its own audit entry (acceptance #3).
- **System-agnostic surface.** Claims from Workday, Concur or Maconomy appear identically; source system is only visible on drill-down for forensic audit (acceptance #9).
- **Autonomy dials.** Per-workflow and per-skill thresholds. The brief requires these be runtime-adjustable without redeployment. Our production-hardening recommendation (carried over from our response §5.5) is that in production, threshold changes flow as PR / change-request via APIOps CI/CD with dual-control approval, delivering the stated outcome (no redeployment impact to running workflows) with stronger governance. The POC demonstrates both the runtime-adjustable and the PR-gated paths; Zava can choose per deployment.
- **Skill amplification.** When the operator is uncertain, the Fleet Manager proactively surfaces the applicable policy clause, prior adjudication precedents and a recommended action — without being asked. Source: Zava vendor brief §6.2 Skill amplification; questionnaire row 27.
- **Role-based operator views.** SSC Reviewer has a purpose-built queue sorted by severity, value and SLA urgency; Finance Controller sees the aggregate fleet. Source: our §10.1 acceptance #8.
- **Cost dashboard.** Weekly cost-per-task report rendered via AG-UI components (acceptance #13).
- **AG-UI components.** Agent-rendered forms, charts and decision wizards composed at runtime with no hardcoded UI per workflow type. Source: our §14.2 B.2.5.

## 10. Non-functional requirements

Targets align with Zava's vendor-brief §5.4 NFR table and the POC 1 brief. Source column references our §14.2 B.3.4 network/data boundaries and B.6 known constraints.

| NFR | Target (POC) | Source / mitigation |
|---|---|---|
| Availability | 99.9% per region | Zava §5.4. Delivered by Azure Durable Functions (GA), APIM (GA), Cosmos DB (GA) and Front Door Premium (GA) |
| Cross-region failover RTO | < 5 minutes | Zava §5.4. Region-pinned deployments; Cosmos DB geo-replication; Durable Functions replay from last checkpoint |
| Cross-region failover RPO | Near-zero for in-flight workflow state | Zava §5.4. Event-sourced Durable Functions state; Cosmos DB multi-region writes where configured |
| Control Plane dashboard latency | < 5 seconds for fleet status refresh | Zava §5.4. AG-UI over SSE, APIM-mediated; Fleet Manager telemetry composed from OTEL streams |
| Concurrent workflows (POC scale) | 30–50 | POC 1 brief §"Target operating model" |
| Scale test (POC) | 5,500 EOQ concurrent workflows across 10 markets and multiple EMS | Zava §4.11 |
| Audit log retention | 7 years minimum for POC; 7–12 years target for production | Zava §5.4 and our §14.2 B.3.4 audit-ledger row |
| Data residency | Platform-enforced per jurisdiction; not developer-configured | Zava §5.4. Region-pinned Hosted Agent pools; APIOps CI gate rejects PRs binding non-EU backends to DE-tagged skills. Source: our §14.2 B.3.4 residency CI gate row |
| Classification accuracy | ≥ 95% floor (Zava acceptance); target 97.6%+ (VML NA benchmark) | Zava §4.5 and acceptance #4; our §10.1 Success metric |
| Workflow state persistence | Survives full platform restart; resumes from last checkpoint | Zava §5.4; Durable Functions event-sourced replay |

## 11. Acceptance criteria

All 13 items from the Zava POC 1 brief §"Acceptance criteria" are live-demoed. Sources: our §10.1 bullets each reference the same acceptance numbers.

| # | Zava criterion | Evaluation method | Our demo plan |
|---|---|---|---|
| 1 | Single Finance Controller view across 30+ concurrent workflows | Live demo | Control Plane shows 30+ active workflows loaded from the synthetic dataset; Finance Controller filters by agency and market |
| 2 | Exception-only surfacing; routine Green hidden | Live demo (20 workflows, 3 exceptions) | Default view shows 3 exceptions; toggle reveals all 20 including hidden Green |
| 3 | Bulk approval of 10+ items in one action | Live demo | 12 Amber items grouped by policy reason; Controller spot-checks 2, applies single bulk-approve; each item retains its own audit entry |
| 4 | ≥95% classification accuracy with per-line policy reasoning | Accuracy report vs benchmark | Full 3,430-line run on synthetic dataset; report compares against Zava ground-truth labels; per-line reasoning surfaced alongside verdict |
| 5 | Receipt cross-validation — image vs structured data mismatch detection | Live demo with synthetic mismatches | Synthetic mismatches injected (wrong amount, wrong date, missing receipt); Receipt Validation skill flags each correctly |
| 6 | Progressive enforcement — warning, escalation, major-violation flow | Live demo with synthetic repeat offenders | Synthetic repeat-offender profile across three months; warning → escalation → major violation flow surfaces on Control Plane |
| 7 | Autonomous learning — initial-to-steady-state learning curve | Live demo | Initial run: all Amber items to SSC Reviewer. Arbitration skill observes 50+ decisions and proposes autonomy changes; Finance Controller approves; steady-state run shows agent recommends with human spot-check only |
| 8 | SSC Reviewer operational interface with queue management | Live demo | Manila-view mock showing queue sorted by severity, value and SLA urgency; reviewer approves, overrides and escalates; processing time per item visible |
| 9 | System-agnostic Control Plane — claims from 2+ EMS appear identically | Live demo: Workday + one other | Claims loaded from Workday and a second EMS concurrently; default view gives no indication of source system; drill-down shows source only on forensic path |
| 10 | Integration extensibility — adding a new EMS without modifying agent logic | Architecture walkthrough | On-screen walkthrough of the three-step EMS onboarding path (register MCP in APIM; declare tool in skill manifest; publish) |
| 11 | Workflow recovery after simulated region failure with no data loss | Live demo | Mid-run region-failure simulation with 500 in-flight claims; Durable Functions replay from last checkpoint in secondary region; no data loss; recovery within RTO |
| 12 | Immutable audit trail queryable for compliance reporting | Live query + report generation | Live Log Analytics query over the action ledger; compliance report generated on demand via Audit skill |
| 13 | Cost-per-task report generated by Orchestrator | Live output | Weekly report rendered on Control Plane: agent compute cost, claims processed, EMS breakdown, breach rate, FTE equivalent |

## 12. Evaluation criteria

Zava POC 1 brief §"Evaluation criteria" assigns the following weights. Demo design is biased to the 40% accuracy weight and the 25% integration strength weight.

| Weight | Domain | What is evaluated |
|---|---|---|
| 40% | Accuracy and policy reasoning | R/A/G classification accuracy vs 97.6% benchmark; clarity of policy-based reasoning per verdict |
| 20% | UX, workflow and arbitration | Workflow design, speed, arbitration quality, adoption. SSC Reviewer interface quality. Processing speed vs manual baseline |
| 25% | Integration strength | EMS API connectivity across heterogeneous systems; auth abstraction; scalability; extensibility for new EMS without agent logic changes |
| 15% | Total cost of ownership | Transparent, predictable, scalable pricing; VML NA pilot vs full Zava rollout economics |

## 13. What Zava provides

From the Zava POC 1 brief §"What Zava will provide", verbatim scope:

- **Synthetic expense dataset** — 3,430 lines mirroring the VML NA pilot; structured claim data sourced from Workday plus receipt images per line.
- **T&E policy document** — Travel and Expense Policy with R/A/G definitions.
- **Benchmark classifications** — Zava-labelled R/A/G ground-truth per line.
- **Delegated authority matrix** — approval limits per role, cost centre and legal entity.
- **System access** — sandbox Workday credentials plus API documentation for additional EMS targets.

Delivery expected at kick-off (Week 0). Timing of sandbox credentials is an open question, see §19.

## 14. What Microsoft provides

- **Vendor-hosted Azure environment** — subscription, resource groups, networking, Key Vault, Private Endpoints and Azure Firewall per our §14.2 B.3.4.
- **Runtime stack** — GHCP SDK (agent runtime) plus Microsoft Agent Framework workflows (graph layer) plus Azure Durable Functions (durable envelope) plus APIM AI Gateway (tool and model governance). All GA except GHCP SDK (preview) and MAF durable task extension (preview via the Durable Agent Orchestration pattern).
- **Agent hosting** — Azure AI Foundry Hosted Agents where GA; Azure Container Apps (GA today) as the named fallback per Phase 0 decision carried in our §14.2 B.6.
- **Control Plane UI** — bespoke React application consuming AG-UI telemetry, plus the Fleet Manager agent (`fleet-manager@zava`).
- **Engineering team** — one Solution Architect plus two to three engineers across GHCP SDK, Foundry, APIM and Control Plane UI.
- **Microsoft Services co-investment** — CSU / MCS co-investment for POC delivery per the partnership commercial track.

## 15. Timeline

Eight-week sprint from kick-off, followed by a half-day demo for Zava evaluators.

| Week | Milestone | Deliverable |
|---|---|---|
| 1 | Environment setup | Vendor-hosted Azure environment provisioned; APIM AI Gateway configured; MCP server skeletons for Workday and the second EMS; Entra Agent ID registered for `finance-agent@zava` and `fleet-manager@zava`; CI/CD pipeline with APIOps for skill and policy promotion |
| 2 | Intake and Classification on synthetic data | Intake/OCR phase end-to-end on a 100-row sample; Expense Classification skill producing structured output with confidence and policy citation; Foundry IQ loaded with the Zava T&E policy corpus |
| 3 | Validation and HITL gates | Three-way match deterministic executor; Receipt Validation skill with multimodal reasoning; Durable Functions `wait_for_external_event` HITL waits wired end-to-end; Adaptive Card approval path working |
| 4 | Arbitration, escalation, Control Plane MVP | Arbitration and Escalation skills wired into the MAF graph; Control Plane MVP with fleet view, exception-only default, <5s click-to-context, and bulk approval |
| 5 | Behaviour-change learning loop | Arbitration skill observes reviewer decisions and emits autonomy-change proposals; progressive enforcement window and repeat-offender tracking; governance change-request path operational |
| 6 | Audit trail and compliance reporting; cost-per-task | Log Analytics action ledger populated with 7-year immutability; compliance report query + generator; OTEL cost attribution and weekly cost-per-task Control Plane report |
| 7 | Infrastructure resilience and scale testing | Region-down recovery test with 500 in-flight claims; scale test at 5,500 EOQ concurrent workflows across multiple EMS |
| 8 | Accuracy benchmarking and demo dry runs | Full 3,430-line accuracy run vs Zava ground-truth; two demo dry runs with Zava observer; acceptance-criteria checklist validated |
| Demo | Half-day live demo | All 13 acceptance criteria exercised in front of Zava evaluators |

## 16. Dependencies

- Zava delivery of the synthetic 3,430-line dataset, receipt images, T&E policy document, benchmark R/A/G labels and delegated authority matrix at Week 0.
- Zava delivery of Workday sandbox credentials by Week 1, and API documentation plus credentials for the second EMS by Week 2.
- Confirmed Zava decision on the second EMS for system-agnostic proof (see §19).
- MCP server custom build or REST-to-MCP auto-generation for each EMS.
- GHCP SDK and Foundry Hosted Agents integration adapter — the primary custom engineering task per our §14.2 B.6.
- Azure subscription and network topology signed off with Zava CloudHub, or confirmed vendor-hosted environment.

## 17. Risks and mitigations

Source: our §14.2 B.6 known constraints, plus POC-specific risks.

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Foundry Hosted Agents preview scaling ceiling (5 replicas per deployment) | Medium | Medium | Phase 0 decision: fall back to Azure Container Apps (GA) running the same GHCP SDK image, with Foundry telemetry retained |
| Classification accuracy below 95% acceptance floor | Medium | High (40% of score) | Iterative evaluation using Foundry Evaluators each week; policy-corpus tuning; crystallisation of proven patterns; Week 8 benchmarking run preceded by a Week 7 dry run |
| EMS sandbox delays from Zava | Medium | High | Build against OpenAPI specs and mock early; swap to sandbox when available. REST-to-MCP gateway reduces sandbox ramp-up |
| GHCP SDK preview API churn | Low | Low | Core patterns (skills, MCP, hooks) are production-GA inside GitHub Copilot's runtime. SKILL.md files and MCP tools are portable to any MCP-native runtime |
| Agent 365 not GA by demo date (targeted May 2026) | Medium | Low | Entra Agent ID is usable independently today and is the identity primitive we rely on. Agent 365 adds lifecycle and policy layering when GA |
| Autonomy-dial governance tension (brief says runtime-adjustable; we recommend PR-gated in production) | Low | Low | Demonstrate both paths. Runtime-adjustable is shown working; PR-gated is presented as the production-hardening recommendation with dual-control approval. Zava chooses per deployment |
| Copilot Studio misinterpreted as the core agent fleet | Low | Medium | Copilot Studio is positioned as an available low-code surface (60-minute build demo) but explicitly not recommended for the core agent fleet. Core authoring is GHCP SDK |

## 18. Success criteria

POC 1 sign-off requires all of:

- All 13 Zava acceptance criteria met in the live demo.
- Classification accuracy ≥ 95% on the 3,430-line dataset; target ≥ 97.6%.
- 30+ concurrent workflows supervised by a single Finance Controller on one Control Plane.
- Zero data loss in the region-down recovery test; recovery within the stated RTO.
- Immutable audit ledger produces a compliance report on demand during the demo.
- Cost-per-task report rendered live on the Control Plane.

## 19. Open questions

Items requiring Zava input before or at kick-off:

- **Second EMS selection.** Which system alongside Workday for the system-agnostic proof (SAP Concur, Chrome River, Maconomy, other)?
- **Sandbox credentials timing.** Confirmed delivery dates for Workday sandbox (Week 1) and the second EMS (Week 2)?
- **Region pairing for DR test.** Which Azure region pair should the resilience demo use?
- **Operator identities for the dual-control demo.** Which two Entra groups should be seeded for the two distinct approvers required on non-revocable actions?
- **Demo audience and day.** Who attends the half-day demo, and on which day at the end of Week 8?
- **Autonomy-dial policy.** Does Zava prefer the runtime-adjustable path or the PR-gated change-request path for the production-leaning demo segment?
