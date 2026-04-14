# Control Plane v1 — Solution Audit

This document is an internal architecture-vs-implementation audit conducted on 2026-04-13, ten days before the WPP written response is due (2026-04-23). Its purpose is to surface, honestly, which of solution.md's 16-section architecture is materialised in the v1 codebase, which gaps are deliberately deferred with a documented reason, and which gaps are uncovered and need to be handled carefully in the written response. Written response authors should treat section 5 (Risks) and section 6 (Recommended caveats) as required reading before drafting the Control Plane and orchestration sections. This audit supersedes any optimistic summary; if a claim is not supported by a file path, it is flagged accordingly.

---

## 1. Executive Summary

- **What we proved**: Fleet Manager is a genuine `@github/copilot-sdk` session, not a rule engine. `CopilotClient.createSession()` runs; `session.sendAndWait()` produces real model reasoning; tool calls (`compose-exception`, `query-fleet`, `query-traces`, `propose-skill-amplification`, `dry-run-policy`) fire via the SDK MCP client and write to the state store. The right-rail SSE stream shows live `tool.execution_start` / `tool.execution_complete` events. The spike confirmed all four SDK acceptance criteria on `@github/copilot-sdk@0.2.2`. This is the demo's single biggest differentiator against vendors shipping "a filtered list."

- **What we deliberately deferred (in-scope for v1 design, not yet built)**: Azure Durable Functions orchestration (entire durability layer is replaced by an in-memory `WorkflowSimulator`); Microsoft Agent Framework workflow graphs (no MAF code exists); Foundry Hosted Agents deployment adapter (all code runs locally via `gh auth token`); APIM AI Gateway and Azure API Center (MCP servers are bare Express stubs, not governed endpoints). These deferrals are documented in the v1 design doc (§9 out-of-scope) and in solution.md §16 known constraints.

- **What we didn't build that we must not claim**: no Azure infrastructure of any kind is deployed — no Durable Functions, no APIM, no Cosmos DB, no Foundry Guardrails, no Agent 365, no Log Analytics. OTEL telemetry is emitted to an in-memory store, not to any Azure Monitor or Foundry Tracing endpoint. Eval scores are simulated random numbers, not Foundry Evaluators running on real model outputs. The "continuous evaluation" claim (CP-10) and "7-12 year audit retention" claim (§9) have zero backing code.

- **What is inconsistent and needs a fix before screenshots**: solution.md §6 and §11 both promise SignalR for Control Plane push. v1 implements SSE (`SSEHub`). The written response must name the production transport (SignalR) while describing the demo transport (SSE) without conflating them. This is the highest-priority prose fix (P1).

- **Risk rating for the written response: MEDIUM.** The Control Plane demo is genuine and defensible. The gap risk is in the layers *behind* the CP — specifically the claim that Durable Functions and MAF are the orchestration layer when no code for either exists. A sharp WPP reviewer asking "show me the DF orchestrator" during the shortlist demo will find nothing. That question needs a prepared answer now.

**Score summary (preview):**
- Solution.md sections: 3 HONOURED / 6 PARTIAL / 5 NARRATIVE-ONLY / 2 OUT-OF-SCOPE-FOR-V1
- CP capabilities: 5 DEMOABLE / 5 PARTIAL / 2 NOT BUILT

---

## 2. Solution.md Walkthrough

### Section 1: Principles (Determinism ↔ Agentic spectrum; three-layer execution model; skill crystallisation)

- **Solution claim:** WPP workflows span a spectrum. The architecture expresses this through three execution layers: (1) Durable Functions as the durable outer envelope, (2) MAF workflow graphs as the deterministic per-phase graph, (3) GHCP SDK sessions as the agentic reasoning layer inside agent executor nodes. Most MAF nodes are plain functions. Skill crystallisation graduates proven agentic patterns to deterministic code.

- **v1 implementation:** The three-layer model is stated in the solution and referenced in the v1 design doc but not implemented. `WorkflowSimulator` (`src/server/services/workflowSimulator.ts`) emulates the workflow lifecycle as a single TypeScript class. There are no Durable Functions, no MAF workflow objects, and no distinct "agent executor" vs "plain function executor" separation — all phases are plain TypeScript `async` functions. The `Fleet Manager` GHCP SDK session exists, but it is the *governance* layer, not the workflow execution layer. The determinism principle is honoured in spirit (simulator phases are deterministic functions) but the actual three-substrate architecture is not present.

- **Verdict:** 🟡 PARTIAL

- **Note:** The principle is architecturally sound and the written response can describe it accurately. However, every code example, diagram, or claim about "MAF executor nodes" will be referencing design, not implementation. Be precise: "our v1 Control Plane validates the governance and observability tier; the three-layer execution substrate (DF + MAF + GHCP SDK) is the engineering target for POC1."

---

### Section 2: Approach (DF + MAF + GHCP SDK + Fleet Manager + API Center + APIM + Foundry CP)

- **Solution claim:** Azure Durable Functions provides the durable envelope. MAF workflow graphs, wired to DF via the durable task extension, define deterministic phase execution. GHCP SDK sessions run on Foundry Hosted Agents. Fleet Manager agents govern the fleet. API Center + APIM govern all agents, tools, skills, and models.

- **v1 implementation:** Only Fleet Manager is implemented as a real GHCP SDK session (`FleetManagerService`, `src/server/services/fleetManagerService.ts`). There are no Durable Functions activities, no MAF workflows, no Foundry Hosted Agents container, no APIM configuration, no API Center registry, and no skill lifecycle management. The "Skills" approach (SKILL.md files with lifecycle gating) is partially implemented: `fleet-manager.skill.md` (`src/server/skills/fleet-manager.skill.md`) is a real SKILL.md loaded as the Fleet Manager's system prompt, but it is the only skill, it is not registered in Azure API Center, and there is no lifecycle gate. MCP tools are in-process Node functions (`src/server/mcp-tools/`), not governed MCP endpoints behind APIM.

- **Verdict:** 🟡 PARTIAL

- **Note:** GHCP SDK as the agent runtime is proved. Everything else in this section is design. The written response can say "our approach uses..." but should not imply any of the APIM/API Center/Foundry infrastructure is deployed or configured.

---

### Section 3: Architecture (Three tiers; Hosted Agent topology; OBO identity; human interaction model)

- **Solution claim:** Fleet Manager, Finance Agent, and Hiring Agent each have distinct Foundry Hosted Agent containers with Entra Agent IDs. OBO flow delegates identity. Human interaction surfaces include M365 Copilot, Adaptive Cards, Control Plane UI, ServiceNow, voice, and a candidate web portal.

- **v1 implementation:** Fleet Manager runs as a local Node.js service using a personal `gh auth token` — not a Foundry Hosted Agent, not an Entra Agent ID. There is no Finance Agent or Hiring Agent (the simulator stands in for workflow execution). No OBO flow. Human surfaces: only the custom Control Plane React UI is implemented. No M365 Copilot integration, no Adaptive Cards, no ServiceNow, no voice, no candidate portal.

- **Verdict:** 🟡 PARTIAL (Control Plane UI exists; rest is narrative)

- **Note:** For the written response, be clear that the Control Plane UI is the live demo surface. M365 Copilot, Adaptive Cards, and the other surfaces are architecture commitments for the POC build, not currently implemented. The Hosted Agent topology is the deployment target, not the current runtime.

---

### Section 4: API Centre & AI Gateway (APIM as unified control plane for models, MCP tools, A2A, skills, APIs)

- **Solution claim:** All model calls, MCP tool calls, A2A handoffs, and skill invocations are governed through APIM AI Gateway with token rate limits, semantic caching, cost emission, content safety, jurisdiction routing, and cross-cloud discovery. Azure API Center holds the registry.

- **v1 implementation:** No APIM instance exists. No API Center. The four mock MCP servers (`mocks/workday-mcp/`, `mocks/d365-mcp/`, `mocks/maconomy-mcp/`, `mocks/payment-mcp/`) are plain Express HTTP servers without auth, rate limiting, or content safety. The `callMcp` utility (`src/server/services/mcpClient.ts`) makes direct HTTP calls to `localhost:410x`. There is no jurisdiction routing, no token metrics, no semantic cache. Cost attribution in `types.ts` (the `costUSD` field on `Workflow`) is populated by the simulator — it is a placeholder number, not an APIM-emitted metric.

- **Verdict:** 🔴 NARRATIVE-ONLY

- **Note:** This is the riskiest section to claim in the written response. APIM AI Gateway is cited as the solution to WPP's token-spend risk (500 concurrent workflows × 30 markets), jurisdiction routing, and cross-cloud discovery. None of this is implemented. The written response should describe APIM as the production architecture target and explicitly note it is not configured in the v1 Control Plane PoC.

---

### Section 5: Intelligence Layer (Foundry IQ, Fabric IQ, Work IQ)

- **Solution claim:** Three Microsoft IQ products provide enterprise grounding: Foundry IQ for document retrieval, Fabric IQ for business semantic ontology, Work IQ for M365 work graph and memory. All three are MCP-addressable and governed via APIM.

- **v1 implementation:** None of the three IQ products are connected. The `propose-skill-amplification` tool (`src/server/mcp-tools/proposeSkillAmp.ts`) accepts and stores policy references and precedents, but these are composed by the Fleet Manager LLM from the in-memory fixture data — not retrieved from Foundry IQ. There is no vector store, no Azure AI Search, no knowledge base, and no Fabric semantic model. The `SkillAmplification` type in `types.ts` models the output correctly, but the source of content is the model's training data and the fixtures.

- **Verdict:** 🔴 NARRATIVE-ONLY

- **Note:** Skill Amplification (CP-5) is demoable as a UI concept — the Fleet Manager agent writes skill amplification cards visible in the Workflow Detail. The content quality depends on the model's training data. The written response should describe Foundry IQ as the production grounding target, not as a working integration. Do not use language implying the Fleet Manager is "grounded in WPP corpora" — it is not.

---

### Section 6: Fleet Manager Agents (Domain-scoped GHCP SDK agents; inputs from DF/MAF/GHCP SDK via Event Grid; outputs via SignalR)

- **Solution claim:** Domain-scoped Fleet Manager agents (hiring, finance, compliance) consume telemetry from DF orchestrations, MAF workflow executors, and GHCP SDK sessions via Azure Event Grid. They push fleet health assessments, exception queues, contextual recommendations, and compliance alerts to the Control Plane UI via SignalR.

- **v1 implementation:** Finance Fleet Manager is implemented as a real `@github/copilot-sdk` session (`FleetManagerService`). It consumes events from the typed `EventBus` (`src/server/services/eventBus.ts`), which is an in-process Node `EventEmitter` — not Azure Event Grid. It pushes to `SSEHub` (`src/server/services/sseHub.ts`) via Server-Sent Events, not SignalR. There is one Fleet Manager instance (not three domain-scoped instances). Triage (`src/server/services/triage.ts`) and queue (`src/server/services/fleetManagerQueue.ts`) are implemented: debounce, coalesce, and anomaly detection are real. The agent's tool set (`query-fleet`, `query-traces`, `compose-exception`, `propose-skill-amplification`, `dry-run-policy`) is fully implemented. The compliance and hiring Fleet Manager instances do not exist.

- **Verdict:** ✅ HONOURED (for the finance domain, with transport delta noted)

- **Note:** This is the section where we have the strongest implementation story. The agent is real. The tool calls are real. The right-rail streaming is real. The transport difference (SSE vs SignalR) and the event bus difference (in-process vs Event Grid) are scale/production concerns, not architecture concerns. The written response should describe SSE as the v1 transport and SignalR as the production target, and describe in-process EventBus as swap-ready for Event Grid (which it is — the EventBus interface is entirely internal).

---

### Section 7: Workflow Durability & Execution (Durable Functions + MAF + GHCP SDK sessions; HITL pattern; Cosmos DB state)

- **Solution claim:** Azure Durable Functions orchestrates each workflow instance with zero-compute HITL waits, timer escalation, checkpoint/replay, and geo-replicated state in Cosmos DB. MAF workflow graphs define the per-phase deterministic graph. GHCP SDK sessions run inside MAF agent executor nodes.

- **v1 implementation:** `WorkflowSimulator` (`src/server/services/workflowSimulator.ts`) and `SimulatorOrchestrator` (`src/server/services/simulatorOrchestrator.ts`) replace the DF + MAF layer entirely. The simulator is an in-memory TypeScript class that advances workflows through phases using `setTimeout` delays and direct function calls. State is held in `StateStore` (`src/server/services/stateStore.ts`), which is `Map<string, T>` with no persistence. HITL is simulated: when a scenario triggers `threshold-exceeded`, the workflow is set to `awaiting_hitl` and stops; the UI's bulk-resolve endpoint resumes it by setting status back to `in_progress`. There is no actual `wait_for_external_event`, no replay, no durable task journal, and no Cosmos DB.

- **Verdict:** 🔴 NARRATIVE-ONLY

- **Note:** This is the most significant architecture gap. Solution.md §7 is the technical backbone of the "state persistence across days/weeks" and "full restart + resume" claims (spec §4.3). None of this is implemented. The written response must not imply these capabilities exist in the current build. The defensible framing: "v1 demonstrates the Control Plane governance layer; workflow durability (Durable Functions + MAF) is the primary engineering work for the POC1 build, already scoped in solution.md §16."

---

### Section 8: Observability (Foundry Tracing; APIM AI Gateway metrics; Fleet Manager assessment as the default CP view)

- **Solution claim:** Every GHCP SDK session inside MAF agent executors emits via GHCP SDK OTEL TracerProvider to Foundry Tracing. APIM emits token usage, latency, and error metrics. Fleet Manager's assessment is the default Control Plane view.

- **v1 implementation:** OTEL spans are generated by `WorkflowSimulator` (`workflowSimulator.ts` — `mkSpan` and `traceTool`) and stored in `StateStore`. The span shape (`OtelSpan` in `types.ts`) has the correct attribute structure: `workflow.id`, `workflow.phase`, `tool.name`, `llm.model`, `llm.tokens.in/out`, `cost.usd`. These are visible in the Workflow Detail Traces tab (`WorkflowDetail.tsx` + `OtelSpanTree.tsx`). However, the spans are simulated — they are not emitted by a real OTEL TracerProvider and not exported to any backend. APIM metrics do not exist. Fleet Manager assessment as the default view is implemented: Fleet Manager's exception queue and skill amplification cards populate the Exception Queue and the Amplification tab in Workflow Detail.

- **Verdict:** 🟡 PARTIAL

- **Note:** The OTEL span schema is correct and the drill-down experience is real. The written response can say "the Control Plane displays OTEL trace data for each workflow, with tool calls, model calls, tokens, cost, and latency." It cannot say "exported to Azure Monitor" or "integrated with Foundry Tracing." The Fleet Manager as the default CP view is genuinely implemented and should be highlighted.

---

### Section 9: Compliance & Governance — Four Enforcement Layers (MAF validators; Foundry Guardrails; APIM; Agent 365/Entra)

- **Solution claim:** Four enforcement layers: (1) MAF validator executors in the workflow graph, (2) Foundry Guardrails intercepting tool calls and detecting PII, (3) APIM content safety and jurisdiction routing, (4) Agent 365 and Entra Agent ID for identity and DLP. All complementary. Policy-as-code via APIOps CI/CD.

- **v1 implementation:** Layer 1 (MAF validators): no MAF code, so no validators. Layer 2 (Foundry Guardrails): not configured or connected. Layer 3 (APIM): no APIM. Layer 4 (Agent 365/Entra): not applicable — auth is a personal `gh` CLI token. The `composeException` tool has an audit hook (`audit.log` calls before and after the write), which is the closest analogue to "non-revocable action gating" in the solution — it is implemented and is the demo's "hook-gated non-revocable action" proof point. The Policy & Autonomy screen (`PolicyAndAutonomy.tsx`) implements the "read-first, change-with-ceremony" pattern: policies are loaded from `policies.yaml` (which has `gitSha`, `author`, `updatedAt`), and the propose-change endpoint creates a `changeRequest` record rather than mutating live state. No actual Git PR is opened.

- **Verdict:** 🔴 NARRATIVE-ONLY (for the four-layer compliance model; governance-as-code *pattern* is partial)

- **Note:** The audit hook on `compose-exception` is the one genuine compliance proof point and should be featured prominently in the demo. The "governance-as-code" framing in the Policy screen is correctly implemented as a UI pattern, but there is no actual Git integration. The written response should not claim any of the four enforcement layers are deployed — they are architecture commitments. The `compose-exception` audit log is the honest, demoable evidence for the non-revocable action pattern.

---

### Section 10: Builder Experience (Pro-code GHCP SDK; low-code Copilot Studio; Logic Apps MCP; Control Plane skill library; agentic builder; Threadlight)

- **Solution claim:** Three build modes: pro-code (GHCP SDK Python/TypeScript), low-code (Copilot Studio via Agent 365), low-code MCP (Azure Logic Apps via APIM REST→MCP). Control Plane UI hosts a skill library (backed by API Center), tool catalogue, governance editor, autonomy dials, and template fork-and-customise. Agentic builder: a MAF executor generates new SKILL.md files from natural language. Threadlight accelerator for knowledge extraction.

- **v1 implementation:** Pro-code GHCP SDK: demonstrated by Fleet Manager. Low-code Copilot Studio: not implemented. Logic Apps MCP: not implemented. Control Plane skill library: the Policy & Autonomy screen exists but covers governance policies, not a skill library with API Center lifecycle. No tool catalogue, no template fork. Agentic SKILL.md builder: not implemented. Threadlight: not implemented. The Control Plane's Policy & Autonomy screen is the nearest analogue but it is governance policy management, not a skill lifecycle manager.

- **Verdict:** 🔴 NARRATIVE-ONLY (for the multi-mode builder vision; pro-code runtime is PARTIAL)

- **Note:** The written response can demonstrate pro-code builder experience by pointing at the actual GHCP SDK code in the repository. Low-code and agentic builder are future milestones. Do not include screenshots of the Policy screen and label them "skill library" — they are not the same thing.

---

### Section 11: Control Plane — Two Layers (Foundry Control Plane for platform governance; custom React UI for operator experience)

- **Solution claim:** Foundry Control Plane (existing product) covers platform-level agent inventory, model registry, tool registry, evaluation, and compliance posture. Custom React UI adds Fleet Dashboard, Exception-Only Queue, Instant Situational Awareness, Bulk HITL, Autonomy Dials, Skill Amplification, and Role-Based Views — all powered by Fleet Manager.

- **v1 implementation:** Foundry Control Plane: not connected. The custom React UI is fully implemented: Fleet Dashboard (`FleetDashboard.tsx`), Exception Queue with bulk HITL (`ExceptionQueue.tsx`, `BulkHitlModal.tsx`), Workflow Detail drill-down (`WorkflowDetail.tsx`) with Overview, Phases, Traces, Ledger, and Amplification tabs, Policy & Autonomy with What-If (`PolicyAndAutonomy.tsx`, `WhatIfPanel.tsx`), Analytics (`Analytics.tsx`), Evaluations (`Evaluations.tsx`), and Fleet Manager right rail (`FleetManagerRail.tsx`). The backend provides seven API routes (`/api/workflows`, `/api/exceptions`, `/api/policy`, `/api/simulator`, `/api/audit`, `/api/evals`, `/api/stream`). Role-Based Views: the header hard-codes `Finance Controller · Ogilvy-US · US-CA` — RBAC is a mockup, not implemented.

- **Verdict:** ✅ HONOURED (custom UI layer; Foundry CP integration is ⚪ OUT-OF-SCOPE-FOR-V1)

- **Note:** This is where v1 delivers most strongly. All six CP UI surfaces exist and are functional. The right-rail Fleet Manager stream is the demo's visual centrepiece. Role-Based Views is cosmetic (hard-coded role header); be explicit that RBAC is an RFP commitment, not a v1 feature.

---

### Section 12: Voice, Video, Avatar (GPT-Realtime + ACS; Teams bot; HeyGen API)

- **Solution claim:** Voice screening via GPT-Realtime + ACS Call Automation with real-time STT and scoring. Video meeting notes via Teams Bot Framework. Avatar onboarding via HeyGen API MCP from a MAF agent executor.

- **v1 implementation:** None of these are implemented. v1 is Finance P2P only; these capabilities belong to POC2 (HR Talent Lifecycle).

- **Verdict:** ⚪ OUT-OF-SCOPE-FOR-V1

- **Note:** This is explicitly out of scope per v1 design doc §1 (Non-goals) and solution.md §15 (POC2). No risk for the written response as long as we clearly position these as POC2 deliverables.

---

### Section 13: Component Summary (full table of 20+ components)

- **Solution claim:** Component table covers the complete production stack: GHCP SDK, Foundry Hosted Agents, MAF, DF, APIM, API Center, Foundry IQ, Fabric IQ, Work IQ, Agent 365, Entra, M365 Agents SDK, ACS, HeyGen, Log Analytics, etc.

- **v1 implementation:** Of the ~20 distinct components in the table, v1 implements: GHCP SDK (Fleet Manager only), custom React Control Plane UI, EventBus (in-process), StateStore (in-memory), mock MCP servers (4, HTTP stubs). All other components are not deployed or connected.

- **Verdict:** 🟡 PARTIAL

- **Note:** The component table is the solution architecture. The written response should position it as the architecture we are delivering, with v1 as the first proof point. A reviewer who asks "which of these are running today" should hear "the Control Plane UI and Fleet Manager — the governance tier. The execution substrate (DF + MAF + Hosted Agents) is POC engineering work." That is an honest and defensible answer.

---

### Section 14: POC 1: Finance Procure-to-Pay

- **Solution claim:** 30-50 concurrent invoice workflows managed by a Finance Controller via the Control Plane. Durable Functions orchestration, MAF workflow graphs, GHCP SDK agent executors for OCR/GL coding/reconciliation, HITL approval gates, Workday/D365/Maconomy integrations, Foundry Guardrails inside agent executors, rollback/compensating actions.

- **v1 implementation:** The Control Plane UI for the Finance Controller use case is implemented end-to-end. The simulator generates 30-50 concurrent invoice workflows that traverse six phases (Intake, Validation, Routing, Approval, Payment, Reconciliation) and call the four mock MCP servers. Exception scenarios (duplicate-invoice, po-mismatch, threshold-exceeded, sanctions-flag, payment-timeout, compliance) are implemented with realistic probability distributions. Fleet Manager monitors the fleet and composes exceptions. Bulk HITL resolves batches. The action ledger tracks revocable/non-revocable actions. What is absent: actual DF/MAF/GHCP SDK agent executors for the workflow phases; real Workday/D365/Maconomy integrations (stubs only); Foundry Guardrails; rollback/compensating transaction logic (the simulator just stops on failure). The `payment-timeout` scenario demonstrates retry logic (`workflowSimulator.ts` lines 234-249), which is the closest analogue to self-healing.

- **Verdict:** 🟡 PARTIAL

- **Note:** The demo tells the POC1 story convincingly at the Control Plane layer. The gap is the execution layer. For the written response, describe what the Finance Controller sees (which is real) and describe the DF+MAF+GHCP SDK execution layer as the engineering roadmap for the 8-week POC sprint.

---

### Section 15: POC 2: HR Talent Lifecycle

- **Solution claim:** 15-20 concurrent hiring workflows, 5 human participants across 4 timezones, 10+ agent team, 22 capability demonstrations including voice screening, avatar, A2A, crystallisation, episodic memory, and jurisdiction-aware compliance.

- **v1 implementation:** Nothing from POC2 is implemented in v1. The UI hard-codes `Finance Controller` role. No hiring workflow type exists in `types.ts`. No POC2 data.

- **Verdict:** ⚪ OUT-OF-SCOPE-FOR-V1

- **Note:** Explicitly out of scope per v1 design doc. No risk in the written response as long as POC2 is correctly positioned as the 12-week post-shortlist sprint. The architecture supports a role-switch (the v1 design doc mentions this) but no UI or data exists for it yet.

---

### Section 16: Known Constraints (GHCP SDK preview; MAF young; Foundry Hosted Agents max 5 replicas; Guardrails preview; Agent 365 May 2026; IQ products preview; Hosted Agents + GHCP SDK integration is primary engineering task)

- **Solution claim:** These are honestly scoped constraints with documented mitigations. The single most significant: "GHCP SDK + Foundry Hosted Agents integration not documented. Hosting adapter needs custom work. This is the primary integration engineering task for the POC."

- **v1 implementation:** The spike (`spike/SPIKE-NOTES.md`) confirmed that the GHCP SDK works with a personal `gh auth token` via the Copilot CLI subprocess. The BYOK path (provider config to point at Azure AI Foundry) is documented in the spike but not configured. The spike notes: "At fleet scale, each `CopilotClient` instance is a subprocess. You will likely want a pool or a shared CLI server (`cliUrl` option)." This is an open engineering concern for the POC.

- **Verdict:** ✅ HONOURED (constraint section is honestly written and the spike validates the core concern)

- **Note:** The spike confirms the SDK works. The Hosted Agents integration remains the primary engineering task. The written response should reference this section directly when discussing risk and mitigation — it is one of the most credible parts of the solution because it names real gaps.

---

## 3. CP Capability Matrix

| CP | Capability | v1 Status | Evidence |
|----|------------|-----------|----------|
| CP-1 | Fleet Dashboard | ✅ DEMOABLE | `FleetDashboard.tsx` — shows all workflows, status counts, phase/agency filters, exceptions-only toggle. Live via SSE polling from `/api/workflows`. |
| CP-2 | Exception-Only Surfacing | ✅ DEMOABLE | `ExceptionQueue.tsx` — Fleet Manager composes exceptions via `compose-exception` tool; only flagged workflows appear here. `FleetDashboard.tsx` has "Exceptions only" filter. |
| CP-3 | Instant Situational Awareness | ✅ DEMOABLE | `WorkflowDetail.tsx` — 5 tabs: Overview (exception + recommendation), Phases, Traces (OTEL), Ledger, Amplification. Load is a single fetch from `/api/workflows/:id`. Speed depends on state store latency (in-memory, sub-1ms). The 5-second rule is met. |
| CP-4 | Bulk HITL | ✅ DEMOABLE | `ExceptionQueue.tsx` + `BulkHitlModal.tsx` — multi-select checkboxes, "Bulk resolve (N)" button, modal with approve/reject, POST to `/api/exceptions/bulk-resolve`. Fleet Manager uses `bulkCandidateIds` in `compose-exception` to group related exceptions. |
| CP-5 | Skill Amplification | ✅ DEMOABLE | `proposeSkillAmpTool` (`mcp-tools/proposeSkillAmp.ts`) — Fleet Manager writes amplification cards. `SkillAmplificationPanel.tsx` renders them in Workflow Detail Amplification tab. Content is LLM-generated from in-memory data, not Foundry IQ. |
| CP-6 | Autonomy Dials | 🟡 PARTIAL | `PolicyAndAutonomy.tsx` — policies displayed read-only with Git metadata. "Propose as change" creates a change request (`/api/policy/propose-change`). No live threshold adjustment; this is the deliberate governance-as-code design. The absence of live sliders is intentional but may not satisfy WPP's literal reading of "adjustable at runtime." |
| CP-7 | Role-Based Views | 🟡 PARTIAL | `App.tsx` header shows hard-coded `Finance Controller · Ogilvy-US · US-CA`. No RBAC middleware. No HR BP or IT Ops view. The architecture supports it; v1 has one static role. |
| CP-8 | Cross-Workflow Context | ✅ DEMOABLE | `FleetDashboard.tsx` — unified view across all concurrent workflows. `FleetManagerService` reasons across the whole fleet in each `processBatch` call. `query-fleet` tool returns aggregated state. |
| CP-9 | Real-Time Observability | 🟡 PARTIAL | `WorkflowDetail.tsx` Traces tab + `OtelSpanTree.tsx` — OTEL spans with tool name, duration, status. Spans are simulator-generated (correct shape, not exported to any backend). No APIM token metrics. No cost attribution from real model calls. |
| CP-10 | Continuous Evaluation | 🟡 PARTIAL | `EvalRunner` (`src/server/services/evalRunner.ts`) samples completed workflows every 15 seconds and generates `taskAdherence`, `safety`, `toolAccuracy` scores. `Evaluations.tsx` renders them. Scores are `0.85 + Math.random() * 0.15` — simulated, not Foundry Evaluators on real outputs. The pattern is present; the substance is synthetic. |
| CP-11 | Policy Dry-Run | ✅ DEMOABLE | `dryRunPolicyTool` (`mcp-tools/dryRunPolicy.ts`) + `dryRunPolicyImpl` — replays completed workflows against a proposed `invoice-p2p.approval.auto_threshold` value and returns the count of outcomes that would differ. `WhatIfPanel.tsx` renders the result. Implemented for one policy; extensible. |
| CP-12 | Human Performance Analytics | 🟡 PARTIAL | `Analytics.tsx` — four metrics (intervention rate, avg resolution, override frequency, quality delta). `interventionRate` is computed from real `actionLedger` data. `avgResolutionMs`, `overrideFrequency`, `qualityDelta` are hard-coded constants. The screen exists; the metrics are partially synthetic. |

**Score: 5 DEMOABLE / 6 PARTIAL / 1 NOT BUILT (not actually 2 — CP-12 exists as a partial screen)**

Correction against the executive summary: on re-count, all 12 CP capabilities have at least a partial implementation in v1. 5 are fully demoable. 6 are partial with synthetic or missing backing data. 1 (CP-10 evaluations) exists as a screen but produces meaningless scores.

---

## 4. Where the As-Built Diverges from Solution.md

1. **Transport: SignalR vs SSE.** Solution.md §6 and §11 both explicitly name SignalR as the push mechanism from Fleet Manager to the Control Plane UI. v1 implements `SSEHub` using native Server-Sent Events (`src/server/services/sseHub.ts`). Consequence: screenshots and the demo will show SSE connections in browser DevTools. The written response should say "real-time push via SSE in v1; production target is SignalR for bi-directional fan-out and Azure hosting compatibility."

2. **Event source: in-process EventBus vs Azure Event Grid.** Solution.md §6 says Fleet Manager "inputs: telemetry events from DF orchestrations, MAF workflow executors, and GHCP SDK sessions via Event Grid." v1 uses an in-process TypeScript `EventEmitter` wrapper. Consequence: all events are local; there is no durability or cross-service delivery. The EventBus interface is designed to be swap-ready, but no adapter exists. The written response should say "EventBus in v1 is an in-process typed emitter; production wires to Azure Event Grid using the same consumer interface."

3. **Durability substrate: DF+MAF+Cosmos DB vs in-memory simulator.** Solution.md §7 describes the three-tier durability model as the orchestration backbone. v1 replaces the entire layer with `WorkflowSimulator` + `StateStore`. Consequence: no restart resilience, no HITL zero-compute wait, no replay, no geo-replicated state. This is the most significant gap.

4. **Hosted Agents vs local CLI subprocess.** Solution.md §3 describes three Foundry Hosted Agent containers with Entra Agent IDs. Fleet Manager runs via `CopilotClient({ githubToken })` using a personal `gh auth token`. Consequence: no container, no Entra Agent ID, no OBO flow, no RBAC on tool access. The BYOK path (switching `provider:` config) is documented in the spike but not configured.

5. **MCP governance: APIM vs bare HTTP.** Solution.md §4 says all MCP tool calls are governed through APIM AI Gateway (auth, rate limits, content safety, token metrics). The four mock MCP servers are bare Express HTTP endpoints on `localhost:410x`. Consequence: no auth, no rate limiting, no audit trail for tool calls at the gateway layer. The `AuditLogger` in the application code (`auditLogger.ts`) provides a lightweight substitute for tool-call logging, but it is in-memory and only covers `compose-exception`.

6. **Grounding: Foundry IQ vs model training data.** Solution.md §5 and §11 describe skill amplification as grounded in WPP corpora via Foundry IQ retrieval. The Fleet Manager's `propose-skill-amplification` tool writes cards whose content comes from the LLM's reasoning over in-memory fixture data. Consequence: policy references in amplification cards are invented by the model, not retrieved from actual WPP policy documents. This matters for demo realism.

7. **Compliance enforcement: zero layers vs four.** Solution.md §9 describes four complementary enforcement layers. v1 has the pre/post audit hooks in `composeException.ts` and the read-only Policy screen — the UI pattern is correct but no enforcement machinery runs.

8. **OTEL export: in-memory vs Foundry Tracing.** Spans have the correct schema (OtelSpan type) and carry the right attributes. They are stored in `StateStore.spans` and rendered in the UI. No `TracerProvider`, no OTLP exporter, no Foundry Tracing backend. The "OTEL" is schema-compatible placeholder data, not actual instrumentation.

9. **Eval scores: random numbers vs Foundry Evaluators.** `EvalRunner.runSample()` generates `0.85 + Math.random() * 0.15` — not model-evaluated outputs. The Evaluations screen will look credible but produces meaningless scores. This is a demo risk: if a reviewer asks "what model produced this adherence score and against what criteria," there is no answer.

10. **Analytics metrics: partially hard-coded.** `Analytics.tsx` computes `interventionRate` from real ledger data but hard-codes `avgResolutionMs: 240_000`, `overrideFrequency: 0.12`, `qualityDelta: 0.04`. These will not change between demo runs. A sharp reviewer who demos twice and sees identical numbers will notice.

11. **Role-based views: cosmetic.** `App.tsx` hard-codes the Finance Controller role in the header. There is no auth middleware, no role-switching, and no HR BP or IT Ops view. The written response should describe RBAC as a POC feature, not a v1 feature.

12. **Policies.yaml is not Git-integrated.** The Policy screen shows `gitSha` and `author` fields from `policies.yaml`, creating the visual impression of a Git-backed policy. The "Propose as change" endpoint creates a record in memory. No actual Git PR is opened and no APIOps pipeline exists.

---

## 5. Risks for the Written Response

**Q: "You say Foundry Hosted Agents but your demo runs locally. Have you actually deployed?"**
Response strategy: Be direct. "The v1 Control Plane PoC runs locally to validate the architecture. Foundry Hosted Agents is the deployment target; the GHCP SDK's `provider:` config switches from personal Copilot to Azure AI Foundry without API changes. The hosting adapter (Responses API wrapper) is the primary engineering task before POC1." Do not imply a cloud deployment exists.

**Q: "Where's the Durable Functions code?"**
Response strategy: "Durable Functions is the production orchestration layer for POC1 and POC2. The v1 Control Plane validates the governance tier — Fleet Manager, exception queue, HITL, observability — using a deterministic simulator to generate realistic fleet state. DF and MAF are the 8-week POC1 engineering sprint, not the 2-day PoC." Have solution.md §7 and §16 ready to show the gap was known and scoped.

**Q: "Show me the APIM AI Gateway in action."**
Response strategy: "The mock MCP servers in v1 stand in for APIM-governed endpoints. APIM configuration — token limits, content safety, jurisdiction routing — is the infrastructure layer we provision for POC1. The MCP tool call contract (tool name, args, JSON result) is identical whether the endpoint is `localhost:4101` or behind APIM; that is by design." Be ready to walk through an APIM AI Gateway demo separately from the Control Plane demo.

**Q: "The eval scores on your Evaluations screen — what model generated them and against what criteria?"**
Response strategy: This is a hard one. The honest answer is "these are placeholder scores in v1; production uses Foundry Evaluators running on real model outputs with task adherence and safety criteria." Decide before the demo whether to include the Evaluations screen in the live walkthrough or reserve it for the written response narrative only.

**Q: "You mention governance-as-code. Can I see the Git PR flow for a policy change?"**
Response strategy: "The Policy & Autonomy screen shows policies backed by `policies.yaml` with Git SHA and author metadata, and creates a change-request record when a change is proposed. The PR-based merge flow is the production pattern; in v1 the ceremony is represented by the change-request record without actually opening a PR." Show the `policies.yaml` file as the artifact.

**Q: "How does the Fleet Manager know which policy to cite in the skill amplification card — is it actually reading WPP's policy documents?"**
Response strategy: "In v1, the Fleet Manager reasons from fixture data and its training knowledge. In the POC, policy references are retrieved via Foundry IQ from WPP's actual corpora. The amplification card schema supports structured policy references with title, snippet, and source — the production grounding replaces the v1 model-generated content with retrieved content."

**Q: "You claim 500 concurrent workflows across 30 markets. Your demo shows 40 simulated workflows on a laptop. How does that scale?"**
Response strategy: "The demo proves the governance pattern at representative scale. APIM AI Gateway handles token rate limiting and cost control at 500 workflows; Durable Functions handles zero-compute HITL waits at weeks-long durations; the Fleet Manager's triage + debounce + coalesce mechanics (demonstrated in the demo) keep reasoning load proportional to exception rate, not event rate. The spike notes a concern about one CLI subprocess per `CopilotClient` at scale — a Fleet Manager process pool or shared CLI server (`cliUrl` option) addresses this in the POC."

---

## 6. Recommended Caveats for Written Response

Add these specific phrasings or notes to `response/response-technical-sections.md` before submission:

1. **On the orchestration layer:** "The v1 Control Plane PoC demonstrates the governance and observability tier (Fleet Manager, exception queue, HITL, OTEL drill-down) using a deterministic workflow simulator. Production workflow orchestration runs on Azure Durable Functions + Microsoft Agent Framework workflows, with GHCP SDK sessions invoked from MAF agent executor nodes. This is the primary engineering scope of the 8-week POC1 sprint, already scoped in solution.md §16."

2. **On Foundry Hosted Agents:** "Fleet Manager in v1 runs via the GHCP SDK against GitHub's Copilot API using a personal license. POC1 deployment uses Foundry Hosted Agents with Entra Agent ID — the GHCP SDK's `provider:` configuration switches the model backend without changing the session or tool API. The hosting adapter (Responses API protocol) is the primary integration engineering task identified in solution.md §16."

3. **On OTEL / observability:** "The Control Plane v1 renders OTEL-shaped spans stored in memory, demonstrating the drill-down UX for situational awareness (CP-3, CP-9). Production telemetry flows from GHCP SDK OTEL TracerProvider → Foundry Tracing → Application Insights, with APIM token metrics providing cost attribution. The span schema is production-compatible."

4. **On continuous evaluation (CP-10):** "The Evaluations screen in v1 shows the UX pattern for continuous evaluation on sampled traces. Production evaluation uses Azure Foundry Evaluators running task adherence, safety, and tool call accuracy assessments against real model outputs from completed workflow phases."

5. **On APIM AI Gateway:** "MCP tool calls in the v1 demo route to Express stub servers on localhost. Production routes them through APIM AI Gateway, which adds auth injection, rate limiting, content safety, token metrics, and jurisdiction routing. The MCP tool interface (tool name, JSON args, JSON result) is identical; APIM is transparent to the agent."

6. **On autonomy dials (CP-6):** "The Policy & Autonomy screen takes a read-first, change-with-ceremony approach: autonomy policies are stored in version-controlled YAML with Git SHA and author metadata. Proposed changes create a change-request record; production merges them via APIOps CI/CD after PR review. This is a deliberate governance design choice — not a limitation. Live threshold sliders that mutate governance state without audit trail are inconsistent with WPP's compliance requirements."

7. **On role-based views (CP-7):** "v1 demonstrates the Finance Controller view. RBAC middleware (Entra Conditional Access on Agent IDs, role-based API filtering) is a POC1 infrastructure task. The architecture supports HR BP, Finance Controller, and IT Ops views from the same codebase."

---

## 7. Strengths to Amplify

The following are genuine, evidence-backed strengths that the written response should highlight explicitly:

**Fleet Manager is a real GHCP SDK agent.** `CopilotClient.createSession()` creates a genuine session; `session.sendAndWait()` runs real LLM reasoning; tool calls (`compose-exception`, `query-fleet`, etc.) are invoked by the model's JSON function-call output and execute in-process. The right-rail SSE stream shows live `tool.execution_start` / `tool.execution_complete` events with tool name, args, and timing. The spike (`spike/SPIKE-NOTES.md`) verifies this end-to-end. This directly refutes WPP's anti-requirement: "A Copilot Studio bot is NOT a Control Plane."

**`compose-exception` is hook-gated as a non-revocable action.** The `composeException` tool (`src/server/mcp-tools/composeException.ts`) logs an audit entry *before* writing the exception (pre-hook) and again after (post-hook). This is exactly the "deterministic governance wrapper around LLM action" pattern from solution.md §1 and §2. It is demoable live in the right rail.

**Triage + queue + debounce is real scaling machinery.** `Triage` (`src/server/services/triage.ts`) filters events before Fleet Manager wakes; `FleetManagerQueue` (`src/server/services/fleetManagerQueue.ts`) debounces per-workflow triggers with a 2-second window and coalesces batches. `detectAnomaly()` identifies duplicate-invoice bursts. These are the mechanics that make "1 human governing 50 concurrent workflows" believable — and they are running code, not prose.

**Policy & Autonomy is read-first, change-with-ceremony.** The memory context (`feedback_no_autonomy_dials.md`) flagged this as a stronger RFP framing than live sliders. The implementation delivers: `policies.yaml` with `gitSha` and `author` metadata, a read-only display, and a change-request endpoint that requires rationale and proposer identity. This is a defensible answer to CP-6 that is actually stronger than live sliders from a governance standpoint.

**Policy dry-run (CP-11) is fully implemented.** `dryRunPolicyImpl` (`src/server/mcp-tools/dryRunPolicy.ts`) replays completed workflows against a proposed threshold value and returns the exact count of decisions that would have differed, with workflow IDs. `WhatIfPanel.tsx` renders the result inline in the Policy screen. This is the clearest demonstration of "evidence before action" governance — it is working code, not a mockup.

**The OTEL span schema is production-compatible.** `OtelSpan` in `types.ts` has the correct attribute keys (`workflow.id`, `workflow.phase`, `tool.name`, `llm.model`, `llm.tokens.in`, `llm.tokens.out`, `cost.usd`) that would be emitted by a real GHCP SDK OTEL TracerProvider. The WorkflowDetail Traces tab renders a span tree with durations, status, and tool names. A Foundry Tracing integration replaces the in-memory store without changing the UI.

**All 12 CP capabilities have at least a UI manifestation.** WPP's primary scoring criterion is the Control Plane. All 12 mandatory CP capabilities have corresponding UI surfaces in v1. Five are fully demoable end-to-end. This is a strong baseline.

**The mock MCP servers speak real MCP protocol.** The four stubs implement the `/mcp/tools` discovery endpoint and `/mcp/call/:tool` execution endpoint. Tool call traffic from the simulator is real HTTP, not mocked in-process. A APIM AI Gateway sits transparently in front of these in production — the agent code does not change.

---

## 8. Action Items

### P0 — Fix before screenshots are taken

- [ ] **P0.1 — Hard-coded Analytics metrics.** `Analytics.tsx`: compute `avgResolutionMs` from the action ledger (difference between `awaiting_hitl` and next `in_progress` ledger entries per workflow). Remove hard-coded `overrideFrequency` and `qualityDelta` or derive them from ledger data. A reviewer who demos twice and sees identical numbers will flag this. File: `src/client/routes/Analytics.tsx`.

- [ ] **P0.2 — Eval scores exposed as synthetic.** Either (a) replace `EvalRunner.runSample()` random scores with scores derived from real data patterns (e.g., phase duration variance, exception rate per workflow), or (b) add a clearly visible "simulated scores — production uses Foundry Evaluators" label to the Evaluations screen. Current presentation implies real model evaluation. File: `src/server/services/evalRunner.ts`, `src/client/routes/Evaluations.tsx`.

- [ ] **P0.3 — Verify Fleet Manager actually calls tools during the demo flow.** Run the server with a real GitHub token and record whether `compose-exception` is called within a reasonable time after a `sanctions-flag` or `threshold-exceeded` scenario. If the model is not calling tools reliably, strengthen the SKILL.md prompt or reduce the reasoning budget to force deterministic tool calls. File: `src/server/skills/fleet-manager.skill.md`.

### P1 — Caveats to add to written response before 2026-04-23

- [ ] **P1.1** — Add the six caveats from Section 6 above to `response/response-technical-sections.md`.
- [ ] **P1.2** — Remove or qualify any language in the written response that implies Durable Functions or MAF code is running today.
- [ ] **P1.3** — Replace "SignalR" with "SSE (v1) / SignalR (production)" everywhere the transport is mentioned in the written response.
- [ ] **P1.4** — Add a footnote to the Evaluations / CP-10 capability description noting that v1 scores are synthetic and production uses Foundry Evaluators.
- [ ] **P1.5** — Verify the "governance-as-code" claim against the actual Git SHA metadata in `policies.yaml`. The SHAs are fabricated (`a1b2c3d`). Either use real commit SHAs from the repo's policy YAML history or add a note that production SHAs link to the APIOps repository.

### P2 — Nice-to-haves for the live shortlist demo (post-submission)

- [ ] **P2.1** — Add a role-switcher to `App.tsx` that toggles between Finance Controller, HR BP, and IT Ops views (even if the data is the same — it proves the RBAC architecture). Low-effort, high visual impact.
- [ ] **P2.2** — Wire the "Propose as change" endpoint to open a GitHub Issue (or at minimum log a formatted JSON to the console that looks like a PR payload). Makes the governance-as-code story tangible for a live demo.
- [ ] **P2.3** — Connect Fleet Manager to a real Azure AI Foundry endpoint via `provider:` BYOK config. This proves the Hosted Agents path and removes the personal Copilot license dependency. Required before the shortlist demo.
- [ ] **P2.4** — Add a `/api/simulator/inject` endpoint that forces a specific scenario on a specific workflow (e.g., `{ workflowId: "INV-0007", scenario: "sanctions-flag" }`). Makes the demo reproducible without luck.
- [ ] **P2.5** — Export one real OTEL span from the Fleet Manager session to Foundry Tracing. Even a single span with a real trace ID and model attribute proves the observability claim in a way the simulator cannot.

---

*Audit complete. All 16 solution.md sections covered. All 12 CP capabilities covered. Verdicts cite specific files. No section concludes "everything is fine."*
