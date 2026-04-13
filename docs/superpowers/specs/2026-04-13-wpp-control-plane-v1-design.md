# WPP Control Plane v1 — Design

**Status:** Draft for approval
**Date:** 2026-04-13
**Author:** brainstorm session
**Target milestone:** evidence (screenshots + video) embedded in the WPP RFP written response due 2026-04-23
**Build window:** 2 days, solo engineer
**Working directory:** `c:\dev\ghcp sdk stuff\control-plane\`

---

## 1. Context and goal

WPP's RFP (see [spec.md](../../../spec.md) §2) makes the Control Plane the single highest-scored deliverable: "A vendor who demonstrates 22 of 23 capabilities brilliantly but fails to propose a Control Plane solution will struggle to pass this POC." Everything else is secondary.

This document specifies a 2-day build of a working Control Plane v1 — not a production system, but a genuine working software artefact whose screenshots and video become evidence in the written response. The CP is driven by a real GitHub Copilot SDK Fleet Manager agent consuming real telemetry from a simulated POC1 (Finance Procure-to-Pay) workload. Nothing on screen is hand-crafted JSON; every pixel traces back to an event emitted by the simulator, a span stored by the state store, or a reasoning output produced by the Fleet Manager agent.

### Goals

- Validate the three-tier architecture (Fleet Manager ↔ orchestration ↔ agentic loops) from [solution/solution.md](../../../solution/solution.md) end-to-end.
- Produce six hero screenshots + one short demo video suitable for inline inclusion in the written response.
- Deliver a codebase we can continue extending toward a live POC demo post-shortlist, not a throwaway.

### Non-goals

- Production readiness (auth, persistence, multi-tenant, HA).
- POC2 (HR Talent Lifecycle) surfaces. Architecture supports a role-switch, but no POC2 data.
- Cloud deployment. Runs locally via `npm run dev`.
- Full CP-capability coverage if time runs short. See §9 cut list.

---

## 2. Scope summary (from brainstorm decisions)

- **Milestone:** internal PoC to validate architecture + generate evidence for 23 April response. (Not the live shortlist demo.)
- **CP capability cut:** full v1 (CP-1 through CP-11, plus skill amplification). CP-12 analytics optional.
- **PoC mocked:** POC1 Finance Procure-to-Pay only.
- **Starting point:** fresh repo, port specific patterns from [scratch/ghcp-ui/](../../../scratch/ghcp-ui/).
- **Fleet Manager shape:** Approach 1 — event-driven, always-on GHCP SDK session with pre-filter/debounce/coalesce scaling mechanics.
- **Phase execution in simulator:** deterministic functions emitting SDK-identical event shapes (not real sub-sessions) for predictable demo and bounded token burn.
- **Mock MCP servers:** four — workday, d365, maconomy, payment.
- **Autonomy configuration:** no live sliders. Read-first, change-with-ceremony Policy & Autonomy screen. Governance-as-code framing.

---

## 3. System architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    React CP (Vite, Tailwind)                │
│   Fleet Dashboard · Exception Queue · Drill-down · HITL     │
│   Policy & Autonomy · Skill Amplification · What-If         │
└──────────────────────▲──────────────────────────────────────┘
                       │ SSE (live)  + REST (actions)
┌──────────────────────┴──────────────────────────────────────┐
│               Express API + SSE hub (Node/TS)               │
│  /api/workflows · /api/exceptions · /api/policy             │
│  /api/policy/dry-run · /api/fleet-manager/stream (SSE)      │
└───────▲───────────────────────────────────▲─────────────────┘
        │                                   │
        │  subscribe                        │  reasoning output
┌───────┴──────────┐                 ┌──────┴──────────────────┐
│  EventBus        │◄────emit────────│  FleetManagerService    │
│  (EventEmitter)  │                 │  GHCP SDK session       │
└───────▲──────────┘                 │  + SKILL.md             │
        │                            │  + MCP tools:           │
   events (pre-filtered)             │   · query-fleet         │
        │                            │   · query-traces        │
┌───────┴──────────────┐             │   · compose-exception   │
│ WorkflowSimulator    │             │   · propose-skill-amp   │
│ (30–50 in-flight     │             │   · dry-run-policy      │
│  invoice workflows)  │             └─────────────────────────┘
└───────▲──────────────┘                       │
        │                                      │ MCP calls
        │ MCP calls                            ▼
        ▼                      ┌────────────────────────────┐
┌─────────────────────┐        │  StateStore (in-memory     │
│ Mock MCP servers    │        │  Maps + JSON fixtures)     │
│ · workday-mcp       │        │  · workflows, spans,       │
│ · d365-mcp          │        │    exceptions, ledger      │
│ · maconomy-mcp      │        └────────────────────────────┘
│ · payment-mcp       │
└─────────────────────┘
```

Components:

- **WorkflowSimulator** — background worker generating and advancing 30–50 concurrent invoice workflows through the POC1 phase lifecycle. Each phase is a deterministic function that calls mock MCP servers and emits OTEL-shaped spans plus lifecycle events onto the EventBus.
- **EventBus** — in-process `EventEmitter`, typed wrapper. Every producer and consumer speaks the fixed event taxonomy (§5). Swap-ready for Azure Event Grid without touching consumers.
- **Triage** — rule-based pre-filter. Runs synchronously on every event. Decides whether to wake Fleet Manager. Most events stop at state-store update.
- **FleetManagerService** — always-on GHCP SDK session with a SKILL.md role definition and five MCP tools. Subscribes to Triage's "should wake" signal. Debounces and coalesces per workflow. Reasons in bounded concurrency. Emits structured outputs (exceptions, skill amplification cards) via its MCP tool calls, which write to the state store and fan out to the UI via SSE.
- **StateStore** — in-memory `Map<id, T>` for Workflows, Phases, OtelSpans, Exceptions, ActionLedgerEntries, Policies. Seeded from JSON fixtures on boot. Loss-on-restart accepted.
- **Mock MCP servers** — four separate processes speaking MCP over HTTP, backed by fixture JSON. Produce real MCP traffic Fleet Manager can drill into.
- **SSE hub** — pushes state changes and Fleet Manager reasoning deltas to the UI. Client subscribes on connect and receives a snapshot + live diff stream.

---

## 4. Fleet Manager design

The Fleet Manager is **the intelligence layer of the Control Plane**. Without a real agent here, the CP is "a filtered list" and scores 0 against WPP's Control Plane criteria (spec §2 anti-requirements).

### 4.1 Shape

- **Always-on GHCP SDK session**, one instance for v1. Started at boot. Persists across the demo.
- Driven by [`fleet-manager.skill.md`](control-plane/src/server/skills/fleet-manager.skill.md) that declares role, tool access, and output contract.
- **Model:** Azure Foundry, GPT-4.1 default; the user will supply a stronger model if available. Same codepath either way.
- **Output:** every significant reasoning step ends with a tool call — either `compose-exception`, `propose-skill-amplification`, or (on tick) a no-op ack. No free-text outputs reach the UI unmediated.

### 4.2 Scaling mechanics (the "50 workflows at once" story)

Five layered mechanisms keep reasoning load proportional to *exceptions per minute*, not *events per minute*:

1. **Event triage** — rule-based classifier on every event. Only six categories wake Fleet Manager: `workflow.exception.detected`, `workflow.hitl.requested`, `workflow.sla.breach_imminent`, `workflow.policy.violation`, `fleet.anomaly.detected`, `fleet.tick` (every 30s). Routine events (phase started/completed, span emitted) stop at state-store update.
2. **Per-workflow debounce + coalesce** — triggering events for a given workflow ID enter a ~2s debounce window. Further events within the window collapse into one reasoning pass.
3. **Batch-aware reasoning** — when multiple workflows trigger in the same window, queue flushes as a batch. Fleet Manager sees "workflows 042, 073, 089 all hit duplicate-invoice" and emits one bulk-HITL exception rather than three.
4. **Bounded reasoning concurrency** — at most 1 reasoning pass in flight in v1 (simple implementation; N>1 is a trivial extension). Queue absorbs spikes. Queue depth over threshold emits a `fleet.overload` UI signal — honest surfacing.
5. **Tiered models (future, documented now)** — not implemented in v1; referenced in written response to answer Ref 26.1 (tiered model usage). v2 can add a cheap classifier model upstream of frontier reasoning.

### 4.3 MCP tools

Fleet Manager calls these and only these. All are in-process Node functions registered as MCP tools, called via the SDK's MCP client.

| Tool | Purpose |
|------|---------|
| `query-fleet(filters)` | Aggregated state over the full fleet — counts by phase/severity/agency, recent exceptions, SLA risk summary |
| `query-traces(workflowId, phase?)` | OTEL spans for situational awareness drill-down |
| `compose-exception(workflowId, severity, category, summary, recommendation, options, relatedPolicyRefs, bulkCandidateIds?)` | Writes an exception queue item. **Non-revocable action** — gated by `onPreToolUse` hook for audit logging |
| `propose-skill-amplification(workflowId, policyContext, precedents, recommendedApproach)` | Writes a "coach card" linked to a workflow for operator skill amplification |
| `dry-run-policy(policyId, proposedValue, scopeDays)` | Replays past workflows with the proposed policy value. Returns delta: which workflows would have decided differently, net HITL-time impact |

### 4.4 SKILL.md role

```markdown
---
name: fleet-manager
description: Monitors the fleet of concurrent invoice workflows. Composes the
  exception queue surfaced to the Finance Controller via the Control Plane.
  Amplifies operator skill by proposing relevant policy and precedents.
allowed-tools: query-fleet, query-traces, compose-exception,
  propose-skill-amplification, dry-run-policy
---

You are the Fleet Manager for WPP's Finance Procure-to-Pay workflow fleet.

On each trigger event:
1. Call `query-fleet` for current context and `query-traces` for any specific
   workflows named in the trigger.
2. Assess whether a Finance Controller needs to see this. If routine, exit
   silently — do not call any output tool.
3. If surfacing is warranted, call `compose-exception` with a clear summary,
   your recommendation, and the option set. Use `bulkCandidateIds` when you
   detect related workflows.
4. When an exception involves ambiguity the operator would benefit from context
   on, call `propose-skill-amplification` with the most relevant policy
   snippets and the 2–3 most instructive precedent decisions.
5. On `fleet.tick`, produce a fleet-health summary only if anomalies are
   detected. Otherwise exit silently.

Never call `compose-exception` twice for the same root cause in the same
debounce window. Prefer bulk-candidate grouping.

Your output is visible to the operator in near-real-time. Be concise.
Recommendations go in `recommendation`, not in prose.
```

### 4.5 Hook-gated non-revocable action

`compose-exception` is gated by an `onPreToolUse` hook that writes an audit log entry before execution. This is the CP's own demonstration of the hooks pattern from [solution.md §2](../../../solution/solution.md). Every exception that reaches an operator has a traceable agentic origin.

---

## 5. Workflow simulator and data model

### 5.1 Simulator behaviour

- **Seed:** 30–50 concurrent workflows. Ramp: one new workflow every 3–8s for first 3 minutes, then steady-state churn.
- **Phase lifecycle:** Intake → Validation → Routing → Approval → Payment → Reconciliation.
- **Phase duration jitter:** Intake 1–3s, Validation 3–8s, Routing 2–5s, Approval minutes if HITL required else 2–5s, Payment 1–2s, Reconciliation 1–4s.
- **Each phase** calls 2–4 mock MCP tools, writes spans, emits lifecycle events.

### 5.2 Injected scenarios (rates apply to steady-state population)

| Scenario | Rate | Effect |
|----------|------|--------|
| Duplicate invoice detected at Validation | ~10% | Exception, Fleet Manager composes bulk-HITL item |
| PO/invoice variance over threshold | ~15% | Exception, standard HITL |
| Threshold-exceeded approval | ~8% | HITL request to Finance Controller |
| Vendor sanctions flag | ~5% | Non-revocable hard stop, human-required |
| Payment gateway timeout | ~2% | Self-heal: retry, succeeds second time |
| Compliance failure (scripted) | 1 workflow | For hero drill-down screenshot |

A `POST /api/simulator/inject` endpoint force-spawns named scenarios for reliable demo recording.

### 5.3 Data model

```ts
Workflow {
  id: string               // "INV-042"
  type: "invoice-p2p"
  status: "in_progress" | "awaiting_hitl" | "completed" | "failed"
  currentPhase: "Intake" | "Validation" | "Routing" | "Approval" | "Payment" | "Reconciliation"
  createdAt: number
  slaDueAt: number
  vendor: { id, name, country }
  invoice: { number, amount, currency, lineItems[], poRef }
  jurisdiction: string     // "US-CA"
  agency: string           // "Ogilvy-US"
  activeExceptionId?: string
  actionLedger: ActionLedgerEntry[]
  tokensSpent: number
  costUSD: number
}

Phase {
  workflowId: string
  name: Workflow["currentPhase"]
  status: "pending" | "in_progress" | "completed" | "failed"
  startedAt?: number
  completedAt?: number
  agentId: "finance-agent"
  toolCalls: ToolCall[]
  spanIds: string[]
}

OtelSpan {
  traceId: string
  spanId: string
  parentSpanId?: string
  name: string
  startMs: number
  endMs: number
  attributes: {
    "workflow.id": string
    "workflow.phase": string
    "tool.name"?: string
    "llm.model"?: string
    "llm.tokens.in"?: number
    "llm.tokens.out"?: number
    "cost.usd"?: number
  }
  status: "ok" | "error"
}

Exception {
  id: string
  workflowId: string
  composedBy: "fleet-manager" | "guardrail" | "simulator-injected"
  severity: "critical" | "high" | "medium"
  category: "duplicate-invoice" | "po-mismatch" | "threshold-exceeded"
    | "sanctions-flag" | "compliance" | "payment-timeout"
  summary: string
  recommendation: string
  options: Array<{ label: string, action: string, nonRevocable: boolean }>
  relatedPolicyRefs: Array<{ title: string, snippet: string, source: string }>
  bulkCandidateIds?: string[]
  confidence: number       // 0..1
  createdAt: number
  resolvedAt?: number
  resolvedBy?: string
}

AutonomyPolicy {
  id: string               // "invoice-p2p.approval.auto_threshold"
  description: string
  currentValue: number | string | boolean
  gitSha: string
  author: string
  updatedAt: number
}

ActionLedgerEntry {
  workflowId: string
  timestamp: number
  actor: { kind: "agent" | "human", id: string }
  action: string
  revocable: boolean
  details: Record<string, unknown>
}
```

### 5.4 Event taxonomy (bus contract)

Fixed contract — producers, Fleet Manager, and UI SSE all speak exactly these:

| Event | Payload | Wakes Fleet Manager? |
|-------|---------|---------------------|
| `workflow.started` | `{workflowId}` | No |
| `workflow.phase.started` | `{workflowId, phase}` | No |
| `workflow.phase.completed` | `{workflowId, phase, durationMs}` | No |
| `workflow.phase.failed` | `{workflowId, phase, reason}` | No |
| `workflow.exception.detected` | `{workflowId, category, severity}` | **Yes** |
| `workflow.hitl.requested` | `{workflowId, reason}` | **Yes** |
| `workflow.sla.breach_imminent` | `{workflowId, minutesRemaining}` | **Yes** |
| `workflow.policy.violation` | `{workflowId, policyId}` | **Yes** |
| `workflow.resolved` | `{workflowId, resolution}` | No |
| `otel.span.emitted` | `{span}` | No |
| `fleet.anomaly.detected` | `{pattern, workflowIds}` | **Yes** |
| `fleet.tick` | `{timestamp}` (every 30s) | **Yes** |
| `fleet.overload` | `{queueDepth}` | No (UI signal only) |

### 5.5 Mock MCP servers

| Server | Tools |
|--------|-------|
| `workday-mcp` | `getVendor`, `getCostCentre`, `getApprovalChain` |
| `d365-mcp` | `parseInvoice`, `matchPO`, `postGLEntry` |
| `maconomy-mcp` | `lookupProject`, `getTimesheetHours` |
| `payment-mcp` | `createPaymentFile`, `submitPayment`, `reconcileStatement` |

Each ~60–80 LOC, backed by fixture JSON (vendors, POs, invoices, statements).

---

## 6. UI surface

### 6.1 Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ Top bar: role switcher · filters · global search · alerts badge │
├──────────────┬──────────────────────────────────┬───────────────┤
│              │                                  │               │
│  Left nav    │     Main canvas                  │  Right rail:  │
│  · Fleet     │     (context-dependent)          │  Fleet Mgr    │
│  · Exceptions│                                  │  activity     │
│  · Policy    │                                  │  stream       │
│  · Analytics │                                  │               │
│  · Evals     │                                  │  (SSE)        │
│              │                                  │               │
└──────────────┴──────────────────────────────────┴───────────────┘
```

**Right rail always visible.** It is the single most differentiating visual element — shows Fleet Manager wake-ups, active reasoning, tool calls, and outputs in real time. Screenshotable, video-able, unmistakable.

### 6.2 Screens and CP capability mapping

| Screen | Capabilities covered | Notes |
|--------|---------------------|-------|
| **Fleet Dashboard** (default) | CP-1, CP-7, CP-8 | Workflow card grid, counters, filters, role switcher (Finance Controller active; HR BP shows empty state; Unfiltered admin view) |
| **Exception Queue** | CP-2, CP-4, CP-5 | Fleet Manager-composed items, bulk-candidate grouping, skill-amplification panel inline |
| **Workflow Detail** (drill-down) | CP-3, CP-9 | Tabs: Overview · Phases · Traces (OTEL) · Ledger · Amplification. 5-second load rule. |
| **Policy & Autonomy** | CP-6, CP-11 | Read-first current-state list with Git SHA/author/date. What-If analysis (CP-11 dry-run) below. "Propose as change" CTA opens change-request entry — does not mutate live |
| **Analytics** | CP-12 | Four cards (intervention rate, avg resolution, override frequency, quality delta). Optional; first to cut |
| **Evaluations** | CP-10 | Light: recent evals with deep-link into trace. Background routine samples completed workflows |
| **Right rail — Fleet Manager Activity** | Architecture proof | Live SSE stream of wake-ups, tool calls, outputs |

### 6.3 Hero screenshots for written response

| # | Screenshot | Proves |
|---|------------|--------|
| 1 | Fleet Dashboard with 40 workflows, 3 exceptions, filter bar, right rail showing recent FM activity | CP-1, CP-7, CP-8 |
| 2 | Exception Queue: "3 duplicate invoices" bulk item expanded with recommendation + policy refs | CP-2, CP-4, CP-5 |
| 3 | Workflow Detail Traces tab with OTEL span tree, tokens, model, cost | CP-3, CP-9 |
| 4 | Bulk HITL modal, 3 similar exceptions checked, single "Approve all" | CP-4 |
| 5 | Right rail stopped mid-reasoning, `compose-exception` tool call visible | The "it's real" shot |
| 6 | What-If analysis showing decision delta on last 50 workflows, "Propose as change" CTA | CP-6, CP-11, Ref 21.4 governance-as-code |

### 6.4 Deliberately out of scope for v1

- POC2 / hiring workflows in the UI (role switcher ready, no data).
- Real OTLP export (we emit OTel-shaped spans in memory).
- Persistent state across restarts.
- Auth / Entra ID (local, single implicit operator).
- Mobile layout or accessibility polish.

---

## 7. Tech stack and file layout

### 7.1 Stack

| Layer | Pick | Why |
|-------|------|-----|
| Language | TypeScript (strict) | Single language FE/BE; matches ghcp-ui and SDK ergonomics |
| Frontend | React 19 + Vite 6 + Tailwind 4 | Lifted from ghcp-ui; Tailwind fast for dense dashboards |
| Backend | Node 20 + Express 5 | Same stack as ghcp-ui; SSE first-class |
| Agent runtime | `@github/copilot-sdk` | Real SDK, non-negotiable |
| Model | Azure Foundry, GPT-4.1 default (user will supply stronger if available) | Same codepath regardless |
| MCP | SDK's MCP client + `@modelcontextprotocol/sdk` for stub servers | Real MCP traffic for trace screenshots |
| Event bus | Node `EventEmitter` (typed wrapper) | In-process; swap-ready for Event Grid |
| State store | In-memory `Map<id, T>` + JSON fixtures | No DB ceremony |
| UI transport | SSE | Screenshots well; no WebSocket overkill |
| Styling | Tailwind + lucide-react + recharts | Speed |
| Testing | Playwright for one golden-path e2e | Evidence, not coverage |
| Run | `npm run dev` — vite + ts-node-dev + 4 MCP stubs + simulator concurrently | Demoable in 60s from clone |

**Explicitly not using:** Docker, Bicep, Cosmos emulator, Azure Files, EasyAuth, Next.js, Redux/Zustand, react-query. All demoable-in-prose for the RFP.

### 7.2 File layout

```
c:\dev\ghcp sdk stuff\control-plane\
├── README.md
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.ts
├── .env.example
├── src/
│   ├── shared/
│   │   ├── types.ts
│   │   ├── events.ts
│   │   └── policies.yaml
│   ├── client/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── routes/
│   │   │   ├── FleetDashboard.tsx
│   │   │   ├── ExceptionQueue.tsx
│   │   │   ├── WorkflowDetail.tsx
│   │   │   ├── PolicyAndAutonomy.tsx
│   │   │   ├── Analytics.tsx
│   │   │   └── Evaluations.tsx
│   │   ├── components/
│   │   │   ├── WorkflowCard.tsx
│   │   │   ├── ExceptionItem.tsx
│   │   │   ├── PhaseTimeline.tsx
│   │   │   ├── OtelSpanTree.tsx
│   │   │   ├── BulkHitlModal.tsx
│   │   │   ├── SkillAmplificationPanel.tsx
│   │   │   ├── FleetManagerRail.tsx
│   │   │   └── WhatIfPanel.tsx
│   │   ├── hooks/
│   │   │   ├── useSSE.ts
│   │   │   ├── useWorkflows.ts
│   │   │   ├── useExceptions.ts
│   │   │   └── useFleetManagerStream.ts
│   │   └── styles.css
│   └── server/
│       ├── index.ts
│       ├── routes/
│       │   ├── workflows.ts
│       │   ├── exceptions.ts
│       │   ├── policy.ts
│       │   ├── simulator.ts
│       │   ├── evals.ts
│       │   └── stream.ts
│       ├── services/
│       │   ├── eventBus.ts
│       │   ├── stateStore.ts
│       │   ├── workflowSimulator.ts
│       │   ├── fleetManagerService.ts
│       │   ├── triage.ts
│       │   ├── evalRunner.ts
│       │   └── policyEngine.ts
│       ├── skills/
│       │   └── fleet-manager.skill.md
│       ├── mcp-tools/
│       │   ├── queryFleet.ts
│       │   ├── queryTraces.ts
│       │   ├── composeException.ts
│       │   ├── proposeSkillAmp.ts
│       │   └── dryRunPolicy.ts
│       └── fixtures/
│           ├── vendors.json
│           ├── purchase-orders.json
│           ├── invoices.json
│           └── policy-refs.json
├── mocks/
│   ├── workday-mcp/
│   ├── d365-mcp/
│   ├── maconomy-mcp/
│   └── payment-mcp/
├── tests/e2e/golden-path.spec.ts
└── docs/demo-script.md
```

### 7.3 LOC budget

Rough calibration for a 2-day solo build:
- Shared types + events: ~200
- Server core (bus, store, simulator, Fleet Manager, routes): ~1,500
- MCP tools (5): ~300
- Mock MCP servers (4): ~320
- Client (shell + 6 routes + components): ~2,000
- Fixtures + SKILL.md + policies.yaml: ~500
- E2E test: ~150
- **Total: ~5,000 LOC.** Tight but achievable with discipline.

---

## 8. Risks and mitigations

| # | Risk | Mitigation |
|---|------|-----------|
| 1 | GHCP SDK resists event-triggered programmatic usage (non-chat) | Spike for 1 hour at start of day 1 before anything else. Fallback: Approach 2 (timer sweep) — same SDK, simpler driver. |
| 2 | Azure Foundry access / key not available | Confirm before coding. Fallback: OpenAI direct via same SDK, written-response footnote only. |
| 3 | Token burn — Fleet Manager reasoning over a 5-min demo loop | Estimated $0.50–$2 per demo run at GPT-4.1 prices. Cap max tokens per reasoning pass. User providing stronger models shifts math but not approach. |
| 4 | Visual polish floor — screenshots must read as real product | Build to a reference aesthetic (shadcn-style cards, muted palette, whitespace). Stop at "credible," not "polished." |
| 5 | Simulator realism — canned-feel breaks the illusion | Randomise vendor/amount/timing/jitter; keep injection *policy* deterministic for reliable demo recording. |
| 6 | Scope creep into CP-10 / CP-12 at the cost of hero flows | Protected cut list (§9). |

---

## 9. Cut list if we slip

In order:

1. **CP-12 Analytics screen** — prose in written response covers it.
2. **CP-10 Evaluations screen** — keep a one-line right-rail indicator ("Eval runner: 47 passes today, 93% adherence") so it exists.
3. **Playwright e2e test** — demo is recorded manually.
4. **Policy & Autonomy screen** — painful (loses the governance-as-code story), cut only if day 2 afternoon is in trouble.

**Never cut:**
- Fleet Manager as real GHCP SDK session with real tool calls.
- Right-rail Fleet Manager activity stream.
- Workflow Detail → OTEL trace drill-down (CP-3, CP-9).
- Exception Queue with bulk HITL (CP-2, CP-4).
- Skill Amplification panel (CP-5).

---

## 10. Success criteria

The build is done when:

1. `npm run dev` brings up the CP in a browser in under 60 seconds from a clone.
2. 30–50 concurrent workflows visible on the Fleet Dashboard, advancing through phases in real time.
3. Fleet Manager visibly wakes for a triggering event within ~3 seconds of the event and streams its reasoning + tool calls in the right rail.
4. Exception Queue contains items composed by Fleet Manager (not by rules), including at least one bulk-candidate group.
5. Workflow Detail drill-down loads full context (including OTEL span tree) in under 5 seconds.
6. Bulk HITL modal resolves 3+ similar exceptions in one action.
7. Policy & Autonomy screen shows current policies with Git metadata and a working What-If analysis.
8. All six hero screenshots (§6.3) can be produced reliably by running `/api/simulator/inject` commands.
9. A 3–5 minute video can be recorded walking through the golden demo path without stubs or hand-waving.

---

## 11. Open questions

- **Model:** user will supply a stronger model than GPT-4.1 when available. Any model with GHCP SDK tool-calling support slots in without code changes.
- **Hosting for future phases:** local-only for v1. Post-response, Azure Container Apps is the obvious next step, matching ghcp-ui's pattern.

---

## 12. References

- [spec.md](../../../spec.md) — WPP RFP requirements
- [solution/solution.md](../../../solution/solution.md) — full solution architecture
- [scratch/ghcp-ui/](../../../scratch/ghcp-ui/) — reference repo, patterns to port
