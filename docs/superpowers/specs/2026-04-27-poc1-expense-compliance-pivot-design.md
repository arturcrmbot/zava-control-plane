# POC1 Expense Compliance Pivot — Design Spec

> **Topic:** Pivot the existing invoice-P2P implementation to the expense-compliance scenario WPP's POC1 brief actually asks for, hitting all 13 acceptance criteria in ≈3 weeks.
> **Date:** 2026-04-27
> **Status:** Design — awaiting implementation plan
> **Source brief:** [docs/poc1-brief.md](../../poc1-brief.md)
> **Submitted PRD:** [docs/poc1-prd-submitted.md](../../poc1-prd-submitted.md)
> **Inventory of current code:** [docs/poc1-inventory.md](../../poc1-inventory.md)

---

## 1. Context

The WPP POC1 brief (Tom Kelshaw, 31 Mar 2026) asks for an **expense compliance** scenario: agents process employee expense claims across 15+ EMSs (Workday, Concur, Chrome River …), classify each line Red/Amber/Green against a T&E policy, run a closed-loop notify→arbitrate→escalate behaviour-change pipeline, and surface everything through a Control Plane the Finance Controller governs without ever logging into the EMSs themselves.

The PRD we submitted to WPP (`07a-poc1-prd.md`) is content-correct expense compliance — same scenario, same agent team, same R/A/G mechanism, same VML NA 97.6% benchmark — but is mis-titled "Procure-to-Pay" and has propagated that title into our local memory.

The code in this repo is **invoice procure-to-pay**: vendor invoices, three-way match, GL coding, payment file generation, bank reconciliation. None of that maps to expense compliance.

The internal Microsoft team estimates 8 weeks to build POC1. This spec is a counter-position: the platform we already shipped (Durable Functions + MAF Pregel graphs + Fleet Manager + APIM-fronted MCP tools + Apex Control Plane UI) is the load-bearing 75% of POC1. The remaining 25% is domain layer — skills, two mocks, one route, the synthetic data — and lands in ≈3 weeks of vibe-coding.

## 2. Goal

Ship a working expense-compliance POC1 demo that:

1. Hits **all 13 acceptance criteria** from brief §7 with a real demo path (live where possible, recorded fallback for region failover).
2. Demonstrates ≥95% R/A/G classification accuracy on a 300-claim synthetic dataset, with policy-driven (not hard-coded) classification logic.
3. Shows two EMSs (Workday + Concur) with a system-agnostic Control Plane.
4. Gives the operator a Finance Controller view (Control Plane) and an SSC Reviewer view (queue) — both purpose-built per brief §3 and §3.1.
5. Runs end-to-end in ≤3 weeks of focused work — proving the platform is mostly already there, not "we need 8 weeks".

Non-goals: production hardening; full 3,430-claim benchmark (we use 300); WPP's real T&E policy (we synthesise); WPP's real EMS sandbox credentials (mocks); the Advanced Regional Sovereignty Exercise from POC2 Appendix B.

## 3. Approach

**In-place rewrite on `main`.** The platform layer (Durable orchestration + MAF graphs + Fleet Manager + Control Plane shell + validators-as-guardrails edge pattern) stays untouched. Invoice-specific phase graphs, executors, agents, skills and mocks are deleted. Expense equivalents replace them.

Considered and rejected:
- **Feature-branch pivot** with invoice on `main` as fallback. Adds maintenance overhead with no benefit — invoice is not a deliverable.
- **Dual-domain coexistence** (UI domain switch). Doubles maintenance, muddies demo narrative, and isn't what the brief asks for.

The historical invoice POC will be preserved as a git tag (`v0.5-invoice-poc`) before the rewrite begins.

## 4. Architecture

### 4.1 Orchestrator phase shape

The current 6-phase invoice orchestrator becomes a **7-phase expense orchestrator**. Same Durable Functions generator pattern, same `wait_for_external_event` HITL gating, same lifecycle event vocabulary (`workflow.started`, `suspended`, `resumed`, `workflow.completed`, `workflow.rejected`), same TrackedExecutor / validator-as-guardrail edge pattern.

| # | Phase | What happens | Key executors |
|---|---|---|---|
| 1 | **Intake & Normalise** | Pull claim from EMS (Workday or Concur); normalise to common schema; OCR receipt | `lookup_claim`, `doc_intelligence_extract`, `agent_field_extractor` (existing, retargeted), `validate_required_fields` (existing) |
| 2 | **Classify (R/A/G)** | Classifier agent grounded on T&E policy; structured output: verdict, policy_clause, confidence, competing_interpretations[] | `agent_rag_classifier`, `validate_classification_schema` |
| 3 | **Validate Receipt** | Multimodal cross-check: receipt image vs structured (amount/date/category/vendor) | `agent_receipt_validator`, `validate_amount_consistency` (existing) |
| 4 | **Route by Verdict** | Green → auto-approve & close; Amber → SSC Reviewer queue; Red → Notify path. Threshold-driven, runtime-adjustable from Policy page. Calls `escalation_advisor` skill in line for repeat-offender tier. | `agent_escalation` (loads `escalation_advisor.skill.md`), `apply_verdict_routing` |
| 5 | **Notify** (Red path only) | Send Adaptive Card to claimant + line manager via Graph; capture justification response | `agent_notification` (hook-gated send), `wait_for_external_event:justification` |
| 6 | **Arbitrate** | Justification routed to SSC Reviewer; reviewer accepts / requires-repayment / warns / escalates; arbitration agent observes and emits autonomy proposals | `agent_arbitration`, `validate_recommendation_authority` (existing), `wait_for_external_event:reviewer_decision` |
| 7 | **Audit** | Append immutable ledger entry; emit `workflow.completed` | `record_decision` (existing) |

Escalate is **not** a per-claim phase. It is cross-workflow state: `escalation_advisor` skill reads `employee.history` (prior breaches in the state store) and emits a tier (warning / escalation / major-violation). The tier influences notification tone and SSC routing on the *current* claim.

### 4.2 Three tiers (unchanged)

| Tier | Scope | Lifetime | Reasoning |
|---|---|---|---|
| **Fleet Manager** | Always-on GHCP SDK Hosted Agent. Reads OTEL/event telemetry, composes exception queue, surfaces autonomy + cost reports. | Process-long | Yes — frontier model on triage-filtered events |
| **Workflow Orchestration** | Azure Durable Functions, one instance per claim. HITL waits at zero compute, timer escalation, parallel coordination, checkpoint/replay. | Days–weeks | No |
| **Agentic Loops** | Ephemeral GHCP SDK sessions, one per phase. Loads skills + MCP tools, emits OTEL, exits. Stateless. | Seconds | Yes — model varies by skill (cheap for OCR/keyword screen; frontier for policy reasoning) |

## 5. Components

Working from [poc1-inventory.md](../../poc1-inventory.md) grading. The platform layer (≈50 files) is untouched. Domain layer is the work.

### 5.1 Delete

- `mocks/d365-mcp/`, `mocks/payment-mcp/`
- Phase graphs: `validation.py` (three-way match), `payment.py`, `reconciliation.py`. (Routing graph reshapes into Phase 4 verdict routing.)
- Deterministic executors: `three_way_match`, `generate_payment_file`, `submit_payment`, `bank_statement_match`, `lookup_active_gls`, `lookup_cost_centre_policy`, `lookup_vendor_context`
- Agents: `agent_invoice_classifier`, `agent_gl_coder`, `agent_cost_centre_assigner`
- Validators: `validate_gl_active`, `validate_threshold_authority` (rebound; see §5.3)
- Skills: `gl_coder.skill.md`, `cost_centre_assigner.skill.md`, `invoice_classifier.skill.md`

### 5.2 Adapt (rename + re-prompt; structure unchanged)

- `api/functions/workflows/invoice_p2p.py` → `expense_claim.py` — generator pattern + HITL waits + reject/timeout branches transplant directly; phase list is the only change.
- Phase graphs `intake.py`, `routing.py`, `approval.py` → reshape per §4.1.
- Executors `agent_anomaly_flagger`, `agent_field_extractor`, `agent_line_item_extractor`, `agent_resolution_recommender`, `agent_root_cause_explainer`, `agent_exception_classifier` — keep, retarget at expense.
- Skills `anomaly_flagger.skill.md`, `field_extractor.skill.md`, `line_item_extractor.skill.md`, `resolution_recommender.skill.md`, `root_cause_explainer.skill.md`, `exception_classifier.skill.md`, `fleet-manager.skill.md` — one-line retarget plus prompt body where domain-specific.
- `mocks/workday-mcp/` — extend with claim endpoints (`getExpenseClaim`, `listClaimsForApproval`, `submitJustification`, `listEmployeeClaimHistory`); existing vendor/CC endpoints removed.
- `mocks/maconomy-mcp/` — rebind to expense, used as the "third EMS extensibility" example narrated in acceptance #10.
- `api/server/services/exception_factory.py` — new option set (accept-justification, require-repayment, issue-warning, escalate).
- `api/server/services/exception_narrative.py` — re-skin templates.
- `api/server/services/synthetic_data.py` — bridge to new `data/synthetic/` artifacts.
- `api/server/services/simulator_orchestrator.py` — new scenarios (`receipt-mismatch-amount`, `receipt-missing`, `repeat-offender`, `breach-justification-cycle`, `simulate-region-failure`, etc.).
- React UI label rebinds: `WorkflowDetail`, `WorkflowCard`, `ExceptionItem`, `Analytics`, `FleetDashboard`, `PhaseTimeline`. Existing components are otherwise unchanged.

### 5.3 Reuse untouched

Durable Functions runtime, `_common.py`, `_tracked_executor.py`, Fleet Manager service + queue + triage, event bus, SSE hub, state store, audit logger, economics service, durable client, all existing MCP tools (`query_fleet`, `query_traces`, `compose_exception`, `propose_skill_amp`, `dry_run_policy`), routes (`workflows.py`, `fleet.py`, `policy.py`, `audit.py`, `evals.py`, `orchestration.py`, `internal_durable_event.py`, `stream.py`), Apex UI shell, FleetManagerRail, OrchestrationView, OtelSpanTree, BulkHitlModal, SkillAmplificationPanel, WhatIfPanel, ExceptionQueue route, Policy route, Evaluations route, Analytics route. `validate_required_fields`, `validate_recommendation_authority`, `validate_amount_consistency`, `record_decision`, `load_authority_policy`, `apply_threshold_routing` — keep.

### 5.4 New — skills-first

**Skills** (`.skill.md` files; the *behaviour* lives here, not in Python services):

| Skill | Purpose | `allowed-tools` |
|---|---|---|
| `rag_classifier.skill.md` | R/A/G verdict + policy clause + confidence + competing_interpretations[] | `policy.search`, `claim.getStructured` |
| `receipt_validator.skill.md` | Multimodal cross-check of image vs structured fields | `claim.getReceipt`, `claim.getStructured` |
| `escalation_advisor.skill.md` | Given employee history + current claim → tier + reasoning | `employee.history` |
| `arbitration.skill.md` | Given justification text + policy clause → recommended SSC reviewer options | `policy.search`, `precedents.search` |
| `notification_composer.skill.md` | Compose Adaptive Card / email body from breach + policy citation | `claim.summary`, `policy.cite` |
| `audit_summariser.skill.md` | Narrative compliance report from ledger query results | `audit.query` |

**Fleet Manager skill (existing) — extend**, not replace. Add one prompt paragraph for behaviour-change loop on `fleet.tick`, and one paragraph for cost-per-task report on `report.cost_per_task`. New `allowed-tools` entries: `query_reviewer_decisions`, `query_economics`. No new service; the existing FleetManagerService runs both behaviours.

**MCP tools** (small Python modules under `api/server/mcp_tools/`, each ~20–30 lines wrapping the state store / synthetic data / audit ledger):

`policy.search`, `claim.lookup`, `claim.getReceipt`, `claim.getStructured`, `claim.summary`, `policy.cite`, `employee.history`, `precedents.search`, `audit.query`, `query_reviewer_decisions`, `query_economics`.

**MAF Workflow** (one new):

- `accuracy_harness_workflow` — Pregel graph with parallel fan-out: `claim_splitter → [N × rag_classifier_executor] → confusion_matrix_aggregator`. Streams progress via existing event bus → SSE. **Replaces what would have been a Python `accuracy_harness.py` for-loop.**

**Mocks**:

- `mocks/concur-mcp/` (NEW) — Node, OAuth-flavoured endpoints: `listExpenseReports`, `getExpenseLine`, `getReceipt`, `submitJustification`.
- `mocks/workday-mcp/` (extension — see §5.2).

**UI** — minimum new surface:

- `/reviewer-queue` route — composes existing `ExceptionItem`, `BulkHitlModal`, receipt thumbnail with role-filtered queue, severity/value/SLA sort, processing-time-per-item visible. ~150 lines, no new components.
- `AccuracyReport` panel under `/evaluations` — renders confusion matrix from `accuracy_harness_workflow` output (preferably as a skill-rendered AG-UI block, otherwise a small bespoke component).

**Synthetic data** (genuinely new Python — one-shot, not services):

- `data/synthetic/policy.md` — hand-written 8–12 page T&E policy. Markets: UK, US, DE, IN. Categories: meals, travel, accommodation, entertainment, miscellaneous. R/A/G rules per category × market. Threshold tables. Per-attendee meal limits. Documentation requirements.
- `data/synthetic/generate.py` — deterministic claim generator. Walks the policy and emits ~300 labelled claims (~70% Green, ~20% Amber, ~10% Red). Each claim carries the policy clause that triggered the label as **gold reasoning**.
- `data/synthetic/claims/*.json` — emitted artifacts, committed to repo.
- `data/synthetic/labels.csv` — committed to repo, swappable with `data/wpp/labels.csv`.
- `data/synthetic/receipts/*.png` — receipt PNG generator emits 300 receipts with controllable mismatch flavours (correct, wrong-amount, wrong-date, wrong-vendor, missing-line). PIL/templated. Run once.
- `data/synthetic/employees.json` — small population including ≥3 repeat-offender profiles with seeded breach histories.
- `data/synthetic/precedents.json` — ~50 historical SSC reviewer decisions for the behaviour-change loop seed (acceptance #7) and the `precedents.search` tool.

The data directory layout enforces a **drop-in WPP swap path**: when WPP supplies their 3,430-claim benchmark + real T&E policy + ground-truth labels, they land in `data/wpp/` with the same internal structure and a `--dataset` flag flips the harness over. No code change.

## 6. Synthetic dataset + accuracy harness (the 40% answer)

Brief §4.5 makes accuracy the dominant scoring criterion (40% weight) and acceptance #4 the dominant evidence hook (≥95% with policy-based reasoning per line). The plan:

1. **Synthetic policy as single source of truth.** The same policy markdown grounds the classifier *and* generates ground-truth labels. This is a tautology only if we make it one — the policy is rich (4 markets × 5 categories × multiple sub-rules), the generator emits genuinely ambiguous Amber cases (boundary thresholds, missing-receipt-with-auto-reclaim, cash-no-receipt-under-limit), and the gold reasoning is the *literal policy clause text*, not a code-level rule expression. The classifier reads the policy markdown via the `policy.search` tool and must produce reasoning that matches the gold clause.

2. **Volume.** 300 claims is enough for a credible confusion matrix. Distribution: ~70% Green / ~20% Amber / ~10% Red. We caveat in the demo as "300-line subset following the structure of WPP's 3,430-line benchmark; same harness runs the full set, longer wall-clock."

3. **Receipt images.** PIL-templated PNG generator produces 300 receipts with controllable mismatches. Six mismatch flavours: correct, wrong-amount, wrong-date, wrong-vendor, missing-line-item, missing-receipt-entirely.

4. **Accuracy harness as MAF Workflow.** Not a Python service. `claim_splitter → [N × rag_classifier_executor] → confusion_matrix_aggregator`, streamed via the existing event bus → SSE → AccuracyReport panel.

5. **Live policy editing.** When the operator edits `policy.md` on the Policy page (existing `WhatIfPanel`) and re-runs the eval, accuracy shifts on relevant categories. **The classifier code never changes — only the policy text.** That is the live demo of acceptance #4's "policy update changes behaviour without code change."

The narrative this supports:

> *"We ran our R/A/G classifier across 300 synthetic expense claims generated against a synthetic T&E policy. 97.4% accuracy. Here's the confusion matrix. Click any cell — there are the model's reasoning and the gold reasoning. Now I'll edit the policy meal threshold from $75 to $50 per attendee. Re-run. Watch accuracy shift on meal-category claims. The classifier never changed; only the policy."*

## 7. Acceptance criteria coverage

All 13 items from brief §7 have a demo path. Carrier types: **skill** (`.skill.md` + maybe one MCP tool), **MAF graph node**, **existing component reused**, **mock**, **synthetic data**.

| # | WPP criterion | Demo / evidence | Carrier |
|---|---|---|---|
| 1 | Single Finance Controller view across 30+ workflows | 30 active claim workflows seeded; FleetDashboard with agency / market / verdict filters | Existing FleetDashboard; synthetic data |
| 2 | Exception-only surfacing; Green hidden | 3 Amber + 2 Red surface; toggle reveals 25 silent Greens | Existing default filter; verdict from `rag_classifier` |
| 3 | Bulk approval of 10+ in one action | 12 Amber items grouped by policy clause; spot-check 2; bulk-approve all 12 | Existing BulkHitlModal + `/api/exceptions/bulk-resolve`; rebound action labels |
| 4 | ≥95% R/A/G accuracy with per-line reasoning | AccuracyReport panel + live policy-edit-and-re-run | `rag_classifier` skill · `accuracy_harness_workflow` · AccuracyReport panel · synthetic policy + claims + labels |
| 5 | Receipt cross-validation | 6 mismatch flavours injected; `receipt_validator` flags each; side-by-side image + structured fields | `receipt_validator` skill · `claim.getReceipt` + `claim.getStructured` tools · receipt-image generator · simulator scenarios |
| 6 | Progressive enforcement (warning → escalation → major) | Three claims from same employee in succession; ramping tier visible | `escalation_advisor` skill · `employee.history` MCP tool · Phase 4 in-line call · synthetic repeat-offender profiles |
| 7 | Autonomous learning curve | Initial: all Amber to SSC. After 50 reviewer decisions, Fleet Manager (on `fleet.tick`) detects cluster and proposes autonomy via `propose_skill_amp` | Fleet Manager skill prompt extension · `query_reviewer_decisions` tool · existing `propose_skill_amp` tool · existing SkillAmplificationPanel |
| 8 | SSC Reviewer operational interface | New `/reviewer-queue` route; severity/value/SLA sort; receipt thumbnail; verdict + reasoning + competing interpretations; arbitration skill recommends pre-selected option | `/reviewer-queue` route (~150 lines composing existing components) · `arbitration` skill · `precedents.search` MCP tool |
| 9 | System-agnostic Control Plane (2+ EMS) | 30 claims 50/50 Workday / Concur; cards show no source-system marker; surfaces only in audit drawer | New `concur-mcp` mock · extended `workday-mcp` · existing FleetDashboard with EMS field hidden |
| 10 | Integration extensibility (new EMS, no agent changes) | Narrated live: Maconomy mock acting as third EMS; show 3-step pattern (register MCP → add to skill manifest → publish); single skill-manifest diff on screen | Existing Maconomy mock (rebound) · existing skill manifest format · narration |
| 11 | Workflow recovery after region failure | Live: 30 claims running, `docker compose stop functions`, 12 paused, restart, Durable replays, ledger continuity. Recorded backup video | Existing Durable runtime · new simulator command `simulate-region-failure` |
| 12 | Immutable audit trail + compliance reporting | Live `audit.query`; `audit_summariser` skill renders narrative summary in Fleet Manager rail | `audit_summariser` skill · `audit.query` MCP tool · existing audit_logger · existing rail |
| 13 | Cost-per-task report | On `report.cost_per_task` trigger, Fleet Manager composes weekly summary; renders in existing rail | Fleet Manager skill prompt extension · new `query_economics` MCP tool · existing economics service · existing rail |

## 8. Phasing (≈3 weeks)

Sequenced **risk-first**: the 40%-weight accuracy story must be working at end of Week 1, leaving two weeks to recover if it lands below 95%.

### Week 1 — Accuracy spine

| Day | Work | AC |
|---|---|---|
| 1 | Tag `v0.5-invoice-poc`. Delete D-bucket code. Rename invoice phase graphs to placeholders. Draft synthetic T&E policy markdown (4 markets, 5 categories, R/A/G rules) | scaffold |
| 2 | `data/synthetic/generate.py` → 300 labelled claims + `labels.csv`. Receipt PNG generator → 300 receipts with mismatch flavours | scaffold |
| 3 | `rag_classifier.skill.md` + MCP tools `policy.search` + `claim.getStructured`. Single-claim end-to-end test on 5 samples | #4 partial |
| 4 | `accuracy_harness_workflow` MAF Workflow (parallel fan-out) + SSE progress streaming | #4 partial |
| 5 | `AccuracyReport` panel under `/evaluations`. **Internal milestone:** confusion matrix ≥95%; cell drill-down; live policy-edit-and-re-run | **#4 ✅** |

### Week 2 — Domain workflow + integrations

| Day | Work | AC |
|---|---|---|
| 6 | Workday mock claim endpoints. Reshape Durable orchestrator to 7 expense phases. Wire Phase 1 (Intake) + Phase 2 (Classify) | #1, #2 |
| 7 | `receipt_validator.skill.md` + Phase 3 graph + simulator scenarios for the 5 mismatch flavours | **#5 ✅** |
| 8 | `mocks/concur-mcp/` Node mock. Inject 30 claims 50/50 Workday/Concur. FleetDashboard hides source field | **#9 ✅** |
| 9 | `escalation_advisor.skill.md` + `employee.history` MCP tool + Phase 4 in-line call. Repeat-offender ramp demo | **#6 ✅** |
| 10 | `notification_composer.skill.md` + Phase 5 (Notify, Red path) + hook-gated send. Breach → notification → justification round-trip simulator | foundation for #7 |

### Week 3 — Operator surfaces + behaviour change + polish

| Day | Work | AC |
|---|---|---|
| 11 | `arbitration.skill.md` + `precedents.search` MCP tool. New `/reviewer-queue` route composing existing components | **#8 ✅** |
| 12 | Fleet Manager skill prompt extension (one paragraph). New `query_reviewer_decisions` MCP tool. Seed 50 historical reviewer decisions; `fleet.tick` → autonomy proposal in SkillAmplificationPanel; approve → steady-state batch | **#7 ✅** |
| 13 | `audit_summariser.skill.md` + `audit.query` MCP tool. Then Fleet Manager extension for `report.cost_per_task` + `query_economics` MCP tool | **#12 ✅** **#13 ✅** |
| 14 | `simulate-region-failure` simulator command. Live failover demo + recorded backup video. EMS extensibility narration practice with Maconomy mock | **#11 ✅** **#10 ✅** |
| 15 | End-to-end demo dry run (30 min, all 13 ACs). Bug fixes. Final demo recording | all 13 ✅ |

**Bulk approval** (#3) and **30+ workflows view** (#1) and **exception-only surfacing** (#2) come for free during Days 6–8 once claims flow.

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `rag_classifier` lands < 95% on synthetic set | Medium | High (40% of score) | Day 5 internal milestone is the early signal. Weekend buffer to iterate prompt + retrieval. Worst case: tighten the synthetic policy so edges are less ambiguous |
| Multimodal receipt validator model availability or cost | Medium | Medium | Day 7. Fallback to deterministic field-comparison + image-presence check; honest "preview" framing |
| MAF Workflow parallel fan-out at 300 claims hits rate limits | Medium | Low | Throttle inside the splitter; streaming progress matters more than wall-clock |
| Fleet Manager prompt regression when extended | Low | Medium | One paragraph at a time; existing exception-composition behaviour gate; smoke tests |
| Region failover demo flakes live | Medium | Low | Recorded backup video on Day 14 |
| Demo narrative incoherence | Medium | Medium | Day 15 dry run with someone playing WPP evaluator |
| Policy-as-tautology charge ("you tested rules against rules") | Low | Medium | Genuine ambiguity in Amber claims; gold reasoning is policy *text* not code; live policy edit demonstrates separation |

## 10. Decisions made during brainstorming

- **In-place rewrite on `main`**, not branch or dual-domain. Tag `v0.5-invoice-poc` before starting.
- **300 claims, not 3,430.** Drop-in path to WPP's full set via `data/wpp/` directory.
- **Synthetic policy + deterministic gold labels**, with genuine ambiguity in Amber cases.
- **Skills-first.** No `accuracy_harness.py`, no `escalation_tracker.py`, no `behaviour_change_loop.py`. The behaviours live in skills + MCP tools + Fleet Manager prompt extensions.
- **Fleet Manager rail renders cost-per-task and audit summaries.** No new dedicated panels for those.
- **`/reviewer-queue` is the only genuinely new UI route.** Composes existing components.
- **Concur is the second EMS.** Maconomy stays as the "third EMS extensibility" narrative example.

## 11. Open questions for kickoff

These don't block design sign-off but should be answered before Day 1:

- **What model do we use for `rag_classifier`?** GPT-4.1 (matches existing Fleet Manager) is the default; cheaper model for screening + frontier for ambiguous Amber is the brief's expressed pattern.
- **What multimodal model for `receipt_validator`?** GPT-4.1 vision or equivalent. Validate availability + per-call cost on Day 6 before Day 7 work.
- **Is Foundry IQ realistic in the POC timeframe**, or does `policy.search` hit an in-memory chunked retriever (sentence-transformers + FAISS) in `c:/dev/ghcp sdk stuff`? Default to in-memory; Foundry IQ swap is a tool implementation detail later.
- **Demo audience and timing.** This spec assumes "internal show-and-tell at end of Week 3 to counter the 8-week narrative". If WPP themselves see this, the polish bar in Week 3 raises.
- **Autonomy-dial governance** (carried over from PRD §17). The brief asks for runtime-adjustable thresholds; our memory carries a "no live-tuning autonomy sliders" position. The POC demo shows the runtime-adjustable path; the PR-gated production hardening is a narrated framing alongside, not a built feature.

## 12. What ships

A repo at end of Week 3 containing:

- 7-phase expense claim Durable orchestrator on `main`.
- 6 new skills + 1 Fleet Manager skill extension; ~10 new MCP tools.
- 1 new MAF Workflow (`accuracy_harness_workflow`).
- 1 new mock (`concur-mcp`); 1 extended mock (`workday-mcp`).
- 1 new UI route (`/reviewer-queue`); 1 new panel (`AccuracyReport`).
- `data/synthetic/` with policy + 300 claims + 300 receipts + 50 precedents + employees.
- All 13 acceptance criteria demoable end-to-end.
- A 30-minute recorded demo + a written narrative tying each demo beat to its brief section.
- A counter-narrative artifact for the internal "we need 8 weeks" position: *"this is what 3 weeks of vibe-coding on the existing platform looked like."*
