# POC 1 Inventory — what's built, graded against the brief

> **Snapshot at the pivot moment (2026-04-27).** This inventory was the
> input to the pivot decision; the codebase has since been migrated to
> expense compliance per the pivot plans. **Do not read the R/A/D
> grades as current state** — for that, see [poc1-status.md](poc1-status.md).
>
> **Question this answers:** for every artifact in the repo as of
> 2026-04-27, can it be reused as-is for the *expense compliance* POC1
> the brief asks for, does it need adapting, or is it invoice-specific
> dead weight?
> **Source:** code at `c:\dev\ghcp sdk stuff` as of 2026-04-27. Brief: [poc1-brief.md](poc1-brief.md). Submitted PRD: [poc1-prd-submitted.md](poc1-prd-submitted.md).

## Grading legend

- **R — Reuse as-is.** Domain-agnostic plumbing. No code change needed for expense compliance.
- **A — Adapt.** Same shape, swap domain guts (rename, replace prompts, add fields, new mock endpoints).
- **D — Discard.** Invoice-specific with no expense-compliance analogue. Don't carry forward.

The brief is **expense compliance**, not invoice P2P. The PRD we submitted to Zava is also written as expense compliance (despite the title saying "Procure-to-Pay"). The code we built is **invoice P2P**. That mismatch is the central finding here.

---

## 1. Orchestration layer (Durable Functions)

| Artifact | What it does | Grade | Note |
|---|---|---|---|
| [api/functions/workflows/invoice_p2p.py](../api/functions/workflows/invoice_p2p.py) | Durable orchestrator: 6 phases (Intake → Validation → Routing → Approval → Payment → Reconciliation), HITL via `wait_for_external_event`, 72-hour timer, lifecycle checkpoints | **A** | Generator pattern + HITL wait + reject/timeout branches transplant directly. Phase list and the rejected-path semantics need to be re-shaped to the expense brief (Intake/Normalise → Classify → Validate Receipt → Notify → Arbitrate → Escalate → Audit). The HITL-on-Approval pattern becomes HITL-on-Amber. |
| [api/functions/workflows/activities.py](../api/functions/workflows/activities.py) | Activity-trigger registrations bridging the orchestrator to per-phase MAF graphs | **A** | One activity per phase; rename + repoint to new graphs. |
| [function_app.py](../function_app.py) (root) | Durable Functions Python entrypoint | **R** | Untouched. |
| [host.json](../host.json), [local.settings.json](../local.settings.json) | Functions host config | **R** | Untouched. |

**Takeaway.** The Durable Functions runtime, HITL-via-external-event pattern, timer-with-task_any race, and lifecycle event emission (`workflow.started`, `suspended`, `resumed`, `workflow.completed`, `workflow.rejected`) is all directly reusable. Zava §4.3 (HITL without restart) and §4.11 (region-down recovery, no data loss) ride on this layer.

## 2. MAF Pregel graphs (per-phase)

| Artifact | What it does | Grade | Note |
|---|---|---|---|
| [api/functions/graphs/_common.py](../api/functions/graphs/_common.py) | `call_mcp` wrapper emitting `mcp.call` events | **R** | Pure plumbing. |
| [api/functions/graphs/_tracked_executor.py](../api/functions/graphs/_tracked_executor.py) | TrackedExecutor base + TerminalExecutor — emits step/executor lifecycle events | **R** | Pure plumbing. |
| [api/functions/graphs/intake.py](../api/functions/graphs/intake.py) | Intake graph: `doc_intelligence_extract → agent_field_extractor → agent_line_item_extractor → validate_required_fields` | **A** | Replace OCR target (invoice → receipt) and extracted fields (PO/vendor/lines → claim/category/amount/receipt). |
| [api/functions/graphs/validation.py](../api/functions/graphs/validation.py) | Validation graph (three-way match etc.) | **D** | Three-way match is PO/Receipt/Invoice match — invoice-only. Replace with policy classification graph. |
| [api/functions/graphs/routing.py](../api/functions/graphs/routing.py) | Routing graph: GL coding + cost-centre assignment + threshold authority validation | **D** | Wholly invoice — GL/cost-centre routing has no expense-compliance analogue. Becomes "notification + arbitration routing" instead. |
| [api/functions/graphs/approval.py](../api/functions/graphs/approval.py) | Approval graph (HITL gating) | **A** | HITL-gating pattern reusable; signal becomes Amber/Red verdict, not invoice value threshold. |
| [api/functions/graphs/payment.py](../api/functions/graphs/payment.py) | Payment graph: payment file generation + submit | **D** | No payment in expense compliance — claims either approve, reject, or require justification. |
| [api/functions/graphs/reconciliation.py](../api/functions/graphs/reconciliation.py) | Reconciliation: bank statement match | **D** | No bank reconciliation in expense compliance. |

**Takeaway.** Two of six phase graphs are purely invoice and discard cleanly. The shared infrastructure (TrackedExecutor, _common, validator-as-guardrail edge pattern) is the load-bearing part to keep.

## 3. Executors

### 3a. Deterministic executors

| Artifact | What it does | Grade |
|---|---|---|
| [apply_threshold_routing.py](../api/functions/graphs/executors/deterministic/apply_threshold_routing.py) | Threshold-based routing decision | **A** (rebind to value-of-claim threshold) |
| [bank_statement_match.py](../api/functions/graphs/executors/deterministic/bank_statement_match.py) | Match invoice payment against bank statement | **D** |
| [doc_intelligence_extract.py](../api/functions/graphs/executors/deterministic/doc_intelligence_extract.py) | Azure Document Intelligence OCR for invoice | **A** (retarget at receipts; same Document Intelligence) |
| [generate_payment_file.py](../api/functions/graphs/executors/deterministic/generate_payment_file.py) | Build payment file from approved invoice | **D** |
| [load_authority_policy.py](../api/functions/graphs/executors/deterministic/load_authority_policy.py) | Load delegated authority matrix | **R** (matrix exists in expense brief too — §4.3) |
| [lookup_active_gls.py](../api/functions/graphs/executors/deterministic/lookup_active_gls.py) | GL code lookup against Workday | **D** |
| [lookup_cost_centre_policy.py](../api/functions/graphs/executors/deterministic/lookup_cost_centre_policy.py) | Cost centre policy lookup | **D** |
| [lookup_vendor_context.py](../api/functions/graphs/executors/deterministic/lookup_vendor_context.py) | Vendor lookup (sanctions, credit) | **D** |
| [record_decision.py](../api/functions/graphs/executors/deterministic/record_decision.py) | Append a decision row to the action ledger | **R** |
| [submit_payment.py](../api/functions/graphs/executors/deterministic/submit_payment.py) | Submit payment to payment MCP | **D** |
| [three_way_match.py](../api/functions/graphs/executors/deterministic/three_way_match.py) | PO / Receipt / Invoice three-way match | **D** |

### 3b. Agent executors (LLM-backed)

| Artifact | What it does | Grade |
|---|---|---|
| [agent_anomaly_flagger.py](../api/functions/graphs/executors/agents/agent_anomaly_flagger.py) | Flag anomalous invoice features | **A** (retarget at expense anomalies — duplicate, oversized, off-policy date) |
| [agent_cost_centre_assigner.py](../api/functions/graphs/executors/agents/agent_cost_centre_assigner.py) | Assign cost centre from invoice context | **D** |
| [agent_exception_classifier.py](../api/functions/graphs/executors/agents/agent_exception_classifier.py) | Classify exception type for the queue | **R** (domain-agnostic — categorises queue items) |
| [agent_field_extractor.py](../api/functions/graphs/executors/agents/agent_field_extractor.py) | Extract low-confidence fields after OCR | **A** (same idea, target receipt fields) |
| [agent_gl_coder.py](../api/functions/graphs/executors/agents/agent_gl_coder.py) | Pick a GL code | **D** |
| [agent_invoice_classifier.py](../api/functions/graphs/executors/agents/agent_invoice_classifier.py) | Categorise as media-prod / talent-fees / post-prod / other | **D** |
| [agent_line_item_extractor.py](../api/functions/graphs/executors/agents/agent_line_item_extractor.py) | Extract invoice line items | **A** (target expense lines) |
| [agent_resolution_recommender.py](../api/functions/graphs/executors/agents/agent_resolution_recommender.py) | Recommend exception resolution | **R** (recommendation pattern, surfaces on Control Plane) |
| [agent_root_cause_explainer.py](../api/functions/graphs/executors/agents/agent_root_cause_explainer.py) | Explain why a workflow blocked | **R** |
| [_wrapper.py](../api/functions/graphs/executors/agents/_wrapper.py) | Common GHCP SDK loader for skills | **R** |

### 3c. Validators

| Artifact | What it does | Grade |
|---|---|---|
| [validate_amount_consistency.py](../api/functions/graphs/executors/validators/validate_amount_consistency.py) | Amount sanity check | **A** (same idea, expense amount vs receipt amount) |
| [validate_gl_active.py](../api/functions/graphs/executors/validators/validate_gl_active.py) | Block if GL code inactive | **D** |
| [validate_recommendation_authority.py](../api/functions/graphs/executors/validators/validate_recommendation_authority.py) | Check operator has authority for the resolution they chose | **R** (delegated authority matrix is in expense brief §4.3) |
| [validate_required_fields.py](../api/functions/graphs/executors/validators/validate_required_fields.py) | Block if required fields missing | **R** (rename per-phase) |
| [validate_threshold_authority.py](../api/functions/graphs/executors/validators/validate_threshold_authority.py) | Check approver authority vs invoice value | **A** (rebind to claim value) |

**Takeaway.** The validator-as-guardrail edge pattern (agent picks → validator blocks → exception emits → Fleet Manager wakes) is the strongest design choice in the codebase and ports directly. About half the executors discard; the other half adapt with a prompt rewrite.

## 4. Skills (`.skill.md` files loaded by GHCP SDK)

| Skill | Grade | Note |
|---|---|---|
| [anomaly_flagger.skill.md](../api/server/skills/anomaly_flagger.skill.md) | **A** | Retarget anomalies at duplicates / off-policy dates / repeat amount-just-under-limit. |
| [cost_centre_assigner.skill.md](../api/server/skills/cost_centre_assigner.skill.md) | **D** | |
| [exception_classifier.skill.md](../api/server/skills/exception_classifier.skill.md) | **R** | Domain-agnostic. |
| [field_extractor.skill.md](../api/server/skills/field_extractor.skill.md) | **A** | Re-prompt for expense receipt fields. |
| [fleet-manager.skill.md](../api/server/skills/fleet-manager.skill.md) | **A** | One sentence ("Finance Procure-to-Pay workflow fleet") to retarget; rest is generic Fleet Manager prose. |
| [gl_coder.skill.md](../api/server/skills/gl_coder.skill.md) | **D** | |
| [invoice_classifier.skill.md](../api/server/skills/invoice_classifier.skill.md) | **D** | Categorises as media-prod/talent-fees/post-prod/other. Discard. |
| [line_item_extractor.skill.md](../api/server/skills/line_item_extractor.skill.md) | **A** | |
| [resolution_recommender.skill.md](../api/server/skills/resolution_recommender.skill.md) | **R** | Domain-agnostic. |
| [root_cause_explainer.skill.md](../api/server/skills/root_cause_explainer.skill.md) | **R** | Domain-agnostic. |

## 5. Mock MCP servers

| Mock | Endpoints | Grade | Note |
|---|---|---|---|
| [workday-mcp](../mocks/workday-mcp/) | `getVendor`, `getCostCentre`, `getApprovalChain` | **A** | Workday is in scope (primary EMS for expense claims) but exposed surface is wrong — needs `getExpenseClaim`, `listClaimsForApproval`, `submitJustification`, etc. |
| [d365-mcp](../mocks/d365-mcp/) | D365 F&O finance flows | **D** | D365 not in expense brief. |
| [maconomy-mcp](../mocks/maconomy-mcp/) | Maconomy finance flows | **A** | Brief lists Maconomy as a possible third EMS extension example (§4.2). Could rebind. |
| [payment-mcp](../mocks/payment-mcp/) | Submit payment file, status | **D** | No payment phase in expense compliance. |

**Net new mock needed:** SAP Concur (OAuth 2.0 in brief §4.2) — the most natural second EMS for the system-agnostic proof (acceptance #9). Optionally: Microsoft Graph mock for the Teams notification path (§4.6).

## 6. Fleet Manager + control-plane services (FastAPI)

| Service | Grade | Note |
|---|---|---|
| [fleet_manager_service.py](../api/server/services/fleet_manager_service.py) | **R** | Always-on GHCP SDK session, tool allow-list, OTEL spans. Domain-agnostic. |
| [fleet_manager_queue.py](../api/server/services/fleet_manager_queue.py) | **R** | Debounce + coalesce. |
| [triage.py](../api/server/services/triage.py) | **R** | Wake-types filter; retune the WAKE_TYPES set if new event kinds added. |
| [event_bus.py](../api/server/services/event_bus.py) | **R** | |
| [sse_hub.py](../api/server/services/sse_hub.py) | **R** | SSE fan-out to UI. |
| [exception_factory.py](../api/server/services/exception_factory.py) | **A** | Emits "Finance-flavored option sets" — rebind options to expense actions (accept-justification / require-repayment / issue-warning / escalate). |
| [exception_narrative.py](../api/server/services/exception_narrative.py) | **A** | Template-driven narrative; templates are invoice-flavored. |
| [economics.py](../api/server/services/economics.py) | **R** | Per-workflow cost / model calls / tool calls — domain-agnostic. Maps directly to brief §4.9 cost-per-task. |
| [synthetic_data.py](../api/server/services/synthetic_data.py) | **A** | Currently generates invoice fixtures; need expense-claim equivalents. |
| [simulator_orchestrator.py](../api/server/services/simulator_orchestrator.py) | **A** | Scenario injection patterns (`demo-fail`, `duplicate-invoice`, `sanctions-flag` etc.) reusable shape; replace each scenario with expense analogue. |
| [audit_logger.py](../api/server/services/audit_logger.py) | **R** | Immutable ledger. Maps to brief §4.8. |
| [state_store.py](../api/server/services/state_store.py) | **R** | Workflow state + exceptions + MCP calls. |
| [durable_client.py](../api/server/services/durable_client.py) | **R** | Talks to Functions host. |

## 7. MCP tools (Fleet Manager's allow-list)

| Tool | Grade |
|---|---|
| [query_fleet.py](../api/server/mcp_tools/query_fleet.py) | **R** |
| [query_traces.py](../api/server/mcp_tools/query_traces.py) | **R** |
| [compose_exception.py](../api/server/mcp_tools/compose_exception.py) | **R** |
| [propose_skill_amp.py](../api/server/mcp_tools/propose_skill_amp.py) | **R** (becomes the channel for §4.6 autonomy proposals + §4.7 procedural-memory proposals) |
| [dry_run_policy.py](../api/server/mcp_tools/dry_run_policy.py) | **R** (matches brief §4.5 "policy-driven, not hard-coded" + autonomy threshold dry-run) |

## 8. FastAPI routes

| Route | Grade | Note |
|---|---|---|
| [workflows.py](../api/server/routes/workflows.py) | **R** | Workflow detail with economics/narrative/MCP calls — shape stays. |
| [exceptions.py](../api/server/routes/exceptions.py) | **A** | Bulk-resolve actions are invoice-flavored (`reroute-gl`); rename to expense actions. |
| [fleet.py](../api/server/routes/fleet.py) | **R** | `/api/fleet/economics`. |
| [policy.py](../api/server/routes/policy.py) | **R** | Policy + dry-run. Maps to §4.5. |
| [audit.py](../api/server/routes/audit.py) | **R** | |
| [evals.py](../api/server/routes/evals.py) | **R** | Skill-amplification tracker. |
| [orchestration.py](../api/server/routes/orchestration.py) | **R** | |
| [internal_durable_event.py](../api/server/routes/internal_durable_event.py) | **R** | |
| [simulator.py](../api/server/routes/simulator.py) | **A** | Scenario list. |
| [stream.py](../api/server/routes/stream.py) | **R** | SSE. |

## 9. React UI (`web/client/`)

| File | Grade | Note |
|---|---|---|
| [App.tsx](../web/client/App.tsx) | **R** | Apex shell chrome. |
| [styles.css](../web/client/styles.css) | **R** | Light-theme palette. |
| [routes/FleetDashboard.tsx](../web/client/routes/FleetDashboard.tsx) | **R** | Layout reusable; counters/labels rebind. |
| [routes/WorkflowDetail.tsx](../web/client/routes/WorkflowDetail.tsx) | **A** | Phase ribbon labels invoice-specific. |
| [routes/ExceptionQueue.tsx](../web/client/routes/ExceptionQueue.tsx) | **R** | The natural home of the Finance Controller's bulk-approve + spot-check (acceptance #3). |
| [routes/PolicyAndAutonomy.tsx](../web/client/routes/PolicyAndAutonomy.tsx) | **R** | Maps to brief autonomy dial language. |
| [routes/Analytics.tsx](../web/client/routes/Analytics.tsx) | **A** | Counters reframe to claim throughput / breach rate. |
| [routes/Evaluations.tsx](../web/client/routes/Evaluations.tsx) | **R** | |
| [components/apex/](../web/client/components/apex/) | **R** | PhaseRibbon, ExceptionAnalysisCard, InterventionProtocols, EconomicsPanel, FleetAssignment, AuditTrail, ExecutionTimelineTab — domain-agnostic Apex visual language. Phase-ribbon labels rebind. |
| [components/FleetManagerRail.tsx](../web/client/components/FleetManagerRail.tsx) | **R** | Right-rail Fleet Manager reasoning + tool-call deltas. |
| [components/OrchestrationView.tsx](../web/client/components/OrchestrationView.tsx) | **R** | Durable runtime view. |
| [components/OtelSpanTree.tsx](../web/client/components/OtelSpanTree.tsx) | **R** | Trace tree. |
| [components/PhaseTimeline.tsx](../web/client/components/PhaseTimeline.tsx) | **A** | Phase labels invoice-specific. |
| [components/WorkflowCard.tsx](../web/client/components/WorkflowCard.tsx) | **A** | |
| [components/BulkHitlModal.tsx](../web/client/components/BulkHitlModal.tsx) | **R** | Bulk approval modal. Maps acceptance #3 directly. |
| [components/ExceptionItem.tsx](../web/client/components/ExceptionItem.tsx) | **A** | Action labels rebind. |
| [components/SkillAmplificationPanel.tsx](../web/client/components/SkillAmplificationPanel.tsx) | **R** | Maps to brief skill-amplification + proposal queue. |
| [components/WhatIfPanel.tsx](../web/client/components/WhatIfPanel.tsx) | **R** | Policy dry-run. |
| [components/DevPanel.tsx](../web/client/components/DevPanel.tsx) | **R** | |

**Net new UI needed:** an **SSC Reviewer queue route** (`/reviewer-queue`) — the brief explicitly demands a *separate* operational interface (§3.1 + acceptance #8). The Finance Controller view is the existing Fleet Dashboard; the SSC Reviewer view is missing entirely.

## 10. Tests

| Path | Grade |
|---|---|
| [tests/api/](../tests/api/) | **A** (rebind fixture data; test shapes reusable) |
| [tests/web/](../tests/web/) | **A** |
| [tests/e2e/smoke.spec.ts](../tests/e2e/smoke.spec.ts) | **A** (rewrite scenarios) |

---

## Summary scoreboard

By count of source-file artifacts:

- **R (Reuse as-is):** ~50 — runtime, services, MCP tools, routes, UI shell, half the agents, all the validators-as-guardrails plumbing.
- **A (Adapt — same shape, swap guts):** ~25 — phase graphs, half the executors, most skills, mocks, simulator scenarios, several UI components.
- **D (Discard):** ~15 — three-way match, GL coding, payment, reconciliation, vendor lookup, D365, payment-mcp.

**The reusable percentage is high (≈ 75%)** — the platform layer is genuinely domain-agnostic. **The discard set is concentrated in two phases (Routing + Payment + Reconciliation) plus one mock (D365) plus one mock (payment-mcp).** That's the cleanly-removable part.

---

## Net-new (not in repo)

These are demanded by the brief and have **no analogue** in the current code. Net new build cost lands here.

### Scenario domain layer
- **R/A/G classifier skill** with structured output: verdict, policy clause cited, confidence, competing interpretations for Amber.
- **Receipt validator** with multimodal reasoning (image + structured-data cross-validation; missing-receipt detection).
- **Notification skill** with recipient-targeted Adaptive Card path (employee + line manager) — gated by hook so the LLM is not in the send path.
- **Arbitration skill** — captures justifications, surfaces autonomy-change proposals.
- **Escalation skill** — repeat-offender progressive enforcement across time windows (warning → escalation → major violation).
- **Audit reporter skill** — narrative summary over the immutable ledger.
- **Foundry IQ corpus** with the Zava T&E policy document so classification is policy-driven (acceptance: policy update changes behaviour, no code change).
- **Synthetic 3,430-claim dataset** with receipt images and ground-truth R/A/G labels (Zava supplies; we ingest).

### Operator surfaces
- **SSC Reviewer queue UI** — separate route, sorted by severity / value / SLA urgency; processing-time-per-item visible (§3.1 + acceptance #8).
- **System-agnostic claim view** in Fleet Dashboard — drill-down reveals source EMS only on forensic path (acceptance #9).
- **Cost-per-task weekly report** in the brief's exact language — claims processed, EMS breakdown, breach rate, FTE-equivalent (acceptance #13). Economics service has the data; report panel is missing.

### Integrations
- **SAP Concur mock** (OAuth 2.0) as the second EMS — required for system-agnostic proof.
- **Microsoft Graph mock** (or live integration) for Teams notification + Adaptive Card.
- **Workday claim API** added to existing mock — replaces vendor/cost-centre endpoints.

### Demo evidence
- **Accuracy benchmark report** vs Zava labels — ≥ 95% floor, target 97.6%+ (40% of POC1 score).
- **Region-failover dry run** — 500 in-flight claims, recovery within RTO, no data loss (acceptance #11).
- **Learning-curve demo** — initial state (all-Amber-to-reviewer) vs. steady state (agent recommends, human spot-checks) (acceptance #7).

### Architecture artifacts (not code)
- **Integration architecture diagram** — auth abstraction, three-step EMS onboarding walkthrough (acceptance #10).
- **Cost model** — pilot vs. full Zava rollout economics (15% of score).

---

## Open questions for brainstorming

These are the calls that need a human decision before we scope the pivot.

1. **Do we live-pivot the implementation to expense compliance, or do we re-pitch the existing P2P demo as "platform shape, illustrated on invoices"?** Brief evaluation criteria (40% accuracy on R/A/G classification) tilts strongly toward live-pivot.
2. **Which second EMS** for system-agnostic proof — SAP Concur (most natural OAuth example), Chrome River, or rebind the existing Maconomy mock?
3. **Where to draw the line on §4.6 behaviour-change loop** — full closed loop with simulated repeat offenders, or a narrative + skill-amplification proposal stub?
4. **§4.7 memory & learning** — full episodic + procedural memory (Fabric IQ binding) or simulated via state-store snapshots for the demo?
5. **§4.10 process evolution** — feasible to fake convincingly with synthetic 2,000-claim history, or accept "can do with customisation" framing?
6. **§4.11 region failover** — can we run the live demo on Azure with a real region pair, or is this a recorded video?
7. **Autonomy-dial governance.** Brief §3 demands "policy changes take effect across all active workflows immediately, without redeployment". Memory says we have a "no live-tuning autonomy sliders" position. The submitted PRD §17 risks-and-mitigations carries this tension explicitly. **Which path does the live demo show?**
8. **Demo timing.** Brief §9: "vendor presentations: April 2026". Today is 2026-04-27. **What is our actual demo date?** This drives whether option 1 or option 2 from the framing question above is feasible.
