# POC 1 Brief — Expense Compliance (verbatim, with anchors)

> Source: [WPPET-POC1-Finance-Expense-Compliance-260331.docx](../WPPET-POC1-Finance-Expense-Compliance-260331.docx)
> Author: Tom Kelshaw · 31 Mar 2026 · Classification: Confidential, Vendor Distribution
> Extracted via python-docx; section anchors added so this file can be cited as `docs/poc1-brief.md#sec-4-5` etc.

---

<a id="sec-1"></a>
## 1. Purpose

This addendum details the requirements for POC 1: Expense Management. It demonstrates multi-agent orchestration, enterprise system integration, HITL governance, and the Control Plane applied to a high-volume, compliance-sensitive finance process.

Read this alongside the parent brief. Section references below map to the Advanced Capability Assessment Criteria v0.4 unless otherwise noted.

<a id="sec-2"></a>
## 2. The Scenario: Expense Compliance & Behaviour Change

WPP manages employee expense claims across **15+ expense management systems** (Workday, SAP Concur, Chrome River, local tools) with **100+ local policies** across markets and agencies. Approximately **130 FTEs** currently review claims manually. Non-compliant spend across WPP is estimated to be significant. Detection is reactive; there is no proactive compliance culture.

The core architectural principle: **agents operate the expense systems; humans operate the Control Plane.** The Finance Controller never logs into Workday or Concur. They govern the agent fleet that audits, classifies, notifies, and escalates across all underlying systems.

<a id="sec-2-1"></a>
### 2.1 Internal Benchmark

An August 2025 pilot at VML North America processed **3,430 expense claims ($839K total spend)** through Workday with **97.6% correct classification accuracy** using a Red/Amber/Green model against policy rules. This pilot used a single EMS. The POC must demonstrate the same capability across multiple underlying systems; with the human experience remaining system-agnostic.

<a id="sec-2-2"></a>
### 2.2 What We Want to See

Agents handling expense compliance auditing across multiple EMSs. A Finance Controller operating a Control Plane across **30–50 concurrent expense workflows** simultaneously. The controller sees policies, violations, trends, and exceptions. They don't need to see which EMS sourced a given claim; that is the agent's concern.

<a id="sec-2-3"></a>
### 2.3 The Cast

**Human participants:**

- **Finance Controller (London):** operates the Control Plane; oversees all active expense workflows; sets policy; approves threshold and autonomy changes.
- **SSC Expense Reviewer (shared services, Manila):** reviews AI-classified expense claims; overrides when needed; sets corrective actions for breaches.
- **Line Manager (various locations):** receives breach notifications for their reports; approves high-value claims above delegated limit.
- **Employee / Claimant (various locations):** submits expense claims (in EMS e.g. Concur, Maconomy); receives compliance feedback from Agent; provides justifications for flagged items.

**Agent team** (vendors must define composition; this is just illustrative):

- **Orchestrator System:** receives expense batch triggers from multiple EMS sources, decomposes into classification workflows.
- **Intake & Normalisation Pipeline:** connects to each EMS (Workday, Concur, Chrome River, etc.) via its native API; extracts and normalises claim data into a common schema regardless of source system.
- **Expense Classification Agent:** audits each normalised expense line against the applicable policy document; produces Red/Amber/Green classification with policy-based reasoning.
- **Receipt Validation Agent:** analyses receipt images alongside structured data (amount, category, date, vendor) for cross-validation; detects mismatches, missing receipts, and anomalies.
- **Notification Agent:** contacts employee and line manager for material breaches; requests business justification via Teams or email; applies threshold logic.
- **Arbitration Agent:** captures justifications; presents to SSC Expense Reviewer for human review; learns from human decisions to recommend autonomous actions over time.
- **Escalation Agent:** tracks repeat offenders with progressive enforcement across time windows.
- **Audit Agent:** confirms immutable audit trail (in database of your definition); generates compliance reports on demand.

Additional agents can be proposed. Sub-agent architecture is encouraged. Discuss. (§1.3).

<a id="sec-3"></a>
## 3. The Control Plane — Primary Deliverable

This is the most important thing to get right. **A sophisticated agent backend with a Teams notification is not acceptable.**

The Finance Controller does not review expenses. They do not log into Workday, Concur, or any EMS. They govern the agent fleet that operates those systems.

Demonstrate a Control Plane surface where:

- A single Finance Controller monitors 30–50 active expense workflows in real time.
- The default view shows only workflows requiring attention: material violations, stalled arbitrations, SLA breaches, escalation triggers.
- Routine workflows (Green classifications, auto-processed claims) are invisible unless the controller drills in.
- Exception workflows surface with full context: what the agent classified, which policy was applied, what the agent recommends, what the options are.
- The controller can approve, reject, redirect, or override; individually or in bulk.
- Policy changes (e.g. adjust Red/Amber/Green thresholds, change notification triggers, modify escalation windows) take effect across all active workflows immediately, without redeployment.
- The controller view is system-agnostic. Claims from Workday, Concur, and Maconomy appear identically. The underlying EMS is immaterial to the controller.

<a id="sec-3-1"></a>
### 3.1 SSC Reviewer Interface

The Control Plane "Monitor View" serves the Finance Controller. The SSC Expense Reviewer needs a separate, purpose-built interface for their operational work.

Demonstrate an operational reviewer interface where:

- The SSC Reviewer sees AI-classified expense claims with Red/Amber/Green verdicts, policy reasoning, and receipt images; can override classifications, approve justifications, or escalate.
- Claims are sorted by severity, value, and SLA urgency.
- Processing time per item is visible (speed vs. manual baseline).
- The reviewer interface is also system-agnostic: the reviewer does not need to know or care which EMS originated a given claim.
- Status feeds back to the Control Plane in real time; the Finance Controller sees aggregate throughput, breach rates, and reviewer performance without managing individual items.

> **Anti-requirement:** A Copilot Studio bot answering "what's the status of expense #1234?" is not a Control Plane. Neither is an Adaptive Card in an email. These are point interactions; we need fleet management for the Controller and efficient queue management for operational reviewers to HITL at scale and speed.

<a id="sec-4"></a>
## 4. Capabilities to Demonstrate

<a id="sec-4-1"></a>
### 4.1 Multi-Agent Orchestration (§1)

- Show the Orchestrator processing an expense batch: intake from multiple EMS sources, normalisation, classification, notification, arbitration, escalation running as parallel workflow streams.
- Demonstrate dynamic routing: the orchestrator fast-tracks low-value Green claims; routes high-value or Red claims through the full review path.
- Demonstrate tiered model usage: cheap model for initial keyword screening and receipt OCR; frontier model for nuanced policy interpretation and ambiguous Amber cases.
- Show concurrent batch processing: two agencies submit expense batches from different EMS platforms simultaneously; both process through the same agent fleet and surface on the same Control Plane.

<a id="sec-4-2"></a>
### 4.2 System Integration & Auth (§12)

The agents interact with multiple expense management systems. The POC must demonstrate connectivity to **at least two**, e.g.:

- **Workday** (SAML-bridged via Okta): expense claim data, cost centre ownership, delegated authority matrix.
- **SAP Concur** (OAuth 2.0): expense reports, receipt images, approval chains.
- **Microsoft Graph** (on-behalf-of flow): Teams notifications, expense breach communications, calendar for meeting scheduling (escalation).

Demonstrate:

- Platform-level auth abstraction: agent developers do not manage tokens.
- Automatic token refresh across all grant types.
- Credential vault with per-system auth configuration.
- Audit trail of which agent accessed which system, when, with what credentials.
- Integration extensibility: describe how a third EMS (e.g. Maconomy, Rippling, local tools) would be added without modifying the agent logic or Control Plane.

<a id="sec-4-3"></a>
### 4.3 HITL Approval Gates (§3, §21)

- Configurable thresholds: auto-process Green classifications below value threshold; route Amber to SSC Reviewer; route Red above value threshold to Finance Controller.
- Show threshold change taking effect without workflow restart.
- Show bulk approval on the Control Plane: Finance Controller approves 12 Amber classifications in a single action with a 2-item spot-check.
- Show instant situational awareness: controller clicks a flagged workflow and within 5 seconds sees full context — classification, policy reasoning, receipt image, employee history.

<a id="sec-4-4"></a>
### 4.4 Exception Handling & Self-Healing (§3.3)

- Expense claim arrives with missing receipt: agent checks EMS for digital receipt, queries employee via Teams for upload, flags for SSC Reviewer if unresolved within SLA.
- EMS API times out mid-batch: agent retries with exponential backoff, processes remaining claims, flags incomplete items for controller awareness without blocking the queue.
- Duplicate claim detected across two submissions: agent auto-rejects with audit entry, notifies employee, updates workflow state.

<a id="sec-4-5"></a>
### 4.5 Expense Classification & Policy Reasoning (§NEW)

- The Classification Agent audits each expense line against the provided policy (document or codified extract or embedding).
- Each line receives a Red/Amber/Green classification with clear, traceable policy-based reasoning: which rule was applied, why the verdict was reached, what evidence supports it.
- Receipt images are analysed alongside structured data (amount, category, date, vendor) for cross-validation.
- **Target accuracy: ≥ 95%** correct classification against the provided benchmark dataset (WPP internal pilot achieved 97.6%).
- Ambiguous cases (Amber) must include the competing interpretations and a confidence score.
- Classification logic is policy-driven; not hard-coded. When the policy document is updated, classification behaviour changes without code changes.

<a id="sec-4-6"></a>
### 4.6 Behaviour Change & Progressive Enforcement (§NEW)

This is the closed-loop system that encourages culture change.

**Detect & Notify:**

- For material breaches (Red classifications above a configurable value threshold), the Notification Agent contacts the employee and their line manager via Teams or email.
- Notifications include: the specific policy violation, the amount, the evidence, and a request for business justification.
- Threshold logic determines which breaches trigger notification (not every Amber; configurable).

**Arbitrate:**

- Justifications from employees (returned via email or Teams) are captured and presented to the SSC Expense Reviewer via the reviewer interface.
- The reviewer sets the corrective action: accept justification, require repayment, issue warning, escalate.
- **Autonomous learning:** The Arbitration Agent observes human review decisions over time. After sufficient training data, it recommends autonomous actions for similar future cases. Recommendations surface on the Control Plane for the Finance Controller to approve before the agent acts autonomously.
- Show the learning curve: initial state (all to human review) vs. steady state (agent recommends, human spot-checks).

<a id="sec-4-7"></a>
### 4.7 Memory & Learning (§6)

- The Arbitration Agent builds procedural memory from human review decisions: "when a meal expense in London exceeds GBP 75 but includes 4+ attendees, reviewers consistently accept the justification" becomes an auto-accept rule proposal.
- The Classification Agent learns episodic patterns: "this expense category in this market is consistently flagged Amber but always accepted"; proposes reclassifying as Green with documentation requirement.
- Show post-batch review (§6.5): after a week's batch, the Orchestrator reviews which violation types were most frequent, which took longest, what the agent recommends changing.
- Proposals surface on the Control Plane; the Finance Controller approves or rejects memory and process changes.

<a id="sec-4-8"></a>
### 4.8 Audit Trail & Compliance Reporting (§11.4, §14.3)

- Every agent action is logged: which agent, which system, what decision, what data, what policy governed it, who (human or agent) approved it.
- Audit log is immutable, versioned, and queryable.
- Expense compliance report: "show me all Red-classified expenses in Q1, grouped by violation type, cost centre, and repeat-offender status."
- Legal accountability artefact: "who approved this expense classification override?"; traceable to: delegating human, governing policy version, agent identity, approval event.
- Reports are system-agnostic: data from all EMS sources appears in a single compliance view.

<a id="sec-4-9"></a>
### 4.9 Cost-Per-Task Awareness (§16)

- Model selection: receipt OCR and keyword screening use a fast, cheap model (volume: thousands per day); nuanced policy interpretation and ambiguous case reasoning use a frontier model (volume: tens per day).
- At end of week, the Orchestrator generates: *"Expense auditing cost GBP X in agent compute this week. Processed Y claims across Z EMS sources. W flagged (V% breach rate). Estimated FTE equivalent: N."*
- This report is surfaced on the Control Plane and exportable.

<a id="sec-4-10"></a>
### 4.10 Process Evolution (§17)

- After processing 2,000 expense claims, show pattern detection: the agent identifies that a specific expense category (e.g. client entertainment in a particular market) is consistently flagged Amber but always accepted after justification; proposes reclassifying as Green with documentation requirement.
- After processing across multiple agencies, show cross-agency comparison: breach rates, common violation types, policy interpretation differences.
- Proposals are routed to Finance Controller on the Control Plane for approval; not auto-implemented.

<a id="sec-4-11"></a>
### 4.11 Infrastructure Resilience (§23)

- Describe architecture for **5,500 end-of-quarter concurrent expense workflows** across 10 markets and multiple EMS.
- Show recovery: the hosting region goes down with 500 expense claims in-flight. **No data loss.** Workflows resume from last checkpoint in the secondary region within RTO.
- Show observability: traces, costs, and performance per workflow, attributable by agency, market, EMS source, and agent type; visible on the Control Plane.

<a id="sec-5"></a>
## 5. Response Format

For each section (4.1 through 4.11), provide:

- **Can do today:** GA capability; include a live demonstration.
- **Can do with customisation:** bespoke development required; estimated effort in days/sprints.
- **On roadmap:** planned capability; expected availability date.
- **Cannot do:** not supported, not planned; propose an alternative.
- **Score:** 0–5 per the Assessment Criteria scale.

Additionally provide:

- **Control Plane design:** Live demo of the fleet management surface (Finance Controller view).
- **Reviewer interface design:** Wireframe or live demo of the SSC Expense Reviewer operational interface.
- **Integration architecture:** How your platform connects to Workday, Concur, and additional EMS; auth patterns, data flows, error handling, extensibility for new EMS.
- **Acceptance criteria response:** For each demonstration item, describe what "done" looks like and how you will evidence it.
- **Cost model:** Transparent pricing covering consumption vs. subscription models; breakdown for pilot scale vs. full WPP rollout; include model inference costs, platform fees, and storage.

<a id="sec-6"></a>
## 6. Evaluation Criteria (Weighted)

Responses will be scored against the criteria below. MoSCoW classifications from the Assessment Criteria v0.4 apply per capability.

| Domain | Weight | What we are evaluating |
|---|---|---|
| **Accuracy & policy reasoning** | **40%** | Red/Amber/Green classification accuracy vs. 97.6% benchmark. Clarity of policy-based reasoning per verdict. |
| UX, workflow & arbitration | 20% | Workflow design, speed, arbitration capability, adoption potential. SSC Reviewer interface quality. Processing speed vs. manual baseline. |
| Integration strength | 25% | EMS API connectivity across heterogeneous systems. Auth abstraction. Scalability architecture. Extensibility for new EMS without agent logic changes. |
| Total cost of ownership | 15% | Transparent, predictable, scalable pricing. VML NA pilot vs. full WPP rollout economics. |

Beyond scoring, qualitative evaluation:

- **Demonstrated over stated:** live POC demo is required; slides do not constitute evidence.
- **Honesty about gaps:** "we cannot do this" scores higher than vague roadmap commitments.
- **Architecture coherence:** does the platform hold together as a system?
- **System-agnostic human experience:** does the Control Plane abstract the underlying EMS complexity from human operators?

<a id="sec-7"></a>
## 7. Acceptance Criteria

A successful POC 1 demonstration should satisfy:

| # | Criterion | Evidence required |
|---|---|---|
| 1 | Single Finance Controller view across 30+ concurrent expense workflows | Live demo of Control Plane dashboard |
| 2 | Exception-only surfacing: routine (Green) workflows hidden by default | Live demo with at least 20 workflows, 3 exceptions |
| 3 | Bulk approval of 10+ items in a single Control Plane action | Live demo |
| 4 | Expense classification accuracy ≥ 95% with policy-based reasoning per line | Accuracy report against benchmark dataset |
| 5 | Receipt cross-validation: image vs. structured data mismatch detection | Live demo with synthetic mismatched receipts |
| 6 | Progressive enforcement: warning, escalation, major violation flow demonstrated | Live demo with synthetic repeat-offender data |
| 7 | Autonomous learning: agent recommends action based on prior human decisions | Live demo showing learning curve from initial to steady state |
| 8 | SSC Reviewer operational interface with queue management | Live demo of reviewer UX |
| 9 | System-agnostic Control Plane: claims from 2+ EMS appear identically | Live demo with data from Workday and at least one other EMS |
| 10 | Integration extensibility: describe adding a new EMS without modifying agent logic | Architecture walkthrough |
| 11 | Workflow recovery after simulated region failure with no data loss | Demonstrated failover with in-flight workflows |
| 12 | Immutable audit trail queryable for compliance reporting | Live query + report generation |
| 13 | Cost-per-task report generated by Orchestrator | Live output |

<a id="sec-8"></a>
## 8. What WPP Will Provide

| Asset | Description |
|---|---|
| Synthetic expense dataset | 3,430 expense lines (mirroring VML NA pilot): structured claim data from Workday plus receipt images per line |
| Policy document | Travel & Expense Policy with Red/Amber/Green classification definitions |
| Benchmark classifications | WPP-labelled Red/Amber/Green classifications for the expense dataset (ground truth for evals) |
| Delegated authority matrix | Approval limits per role, cost centre, and entity |
| System access | Sandbox credentials for Workday; API documentation for additional EMS targets |

<a id="sec-9"></a>
## 9. Logistics

- **Environment:** Vendor-hosted; WPP provides all synthetic data and sandbox/dummy API credentials listed in §8.
- **Demonstration format:** Live demo; no slides for capability claims.
- **POC timeline:** TBC weeks from asset delivery (target vendor presentations: April 2026).

---

*This document is confidential and intended solely for the named recipient vendors. Any reproduction or distribution without explicit permission from WPP is prohibited.*
