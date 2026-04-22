# WPP Control Plane v1 — As-Built Architecture

This document describes the implementation as it was built for POC1 (Finance Procure-to-Pay). It is an engineer-facing companion to the code, not a restatement of the solution design. For install/run instructions see [`README.md`](../README.md). For the aspirational production architecture see `c:/dev/ghcp sdk stuff/solution/solution.md`.

---

## 1. The thesis in one paragraph

Finance P2P at WPP runs 30–50 concurrent invoice workflows. Each workflow calls multiple enterprise systems (Workday, Dynamics 365, Maconomy, a payment gateway), emits structured telemetry, and can hit exceptions — duplicate invoices, PO mismatches, sanctions flags — that need a Finance Controller's eyes. The Control Plane's job is to ensure a human only sees exceptions that actually need them, composed with enough context to decide quickly. The load-bearing element is the **Fleet Manager**: a persistent `@github/copilot-sdk` session that subscribes to every event on the fleet, debounces bursts, calls read tools to gather context, and writes composed exceptions to a queue via a non-revocable hook-gated tool. What makes this "not a chat wrapper" is the architecture around the agent: the event bus, triage classifier, debounce queue, action ledger, audit log, and policy dry-run capability exist independently of the LLM — the Fleet Manager is a reasoning layer inside a deterministic control structure, not a free-running agent.

---

## 2. Tech stack at a glance

| Layer | Technology | Notes |
|-------|-----------|-------|
| Agent runtime | `@github/copilot-sdk` v0.2.2 | Single `CopilotClient` + `CopilotSession`; auth via `gh auth token` |
| Agent model | `gpt-4.1` (default) | Configurable via `FLEET_MANAGER_MODEL` env var |
| API server | Express 5 + TypeScript (ESM) | Port 3001 |
| UI | React 18 + Vite + Tailwind CSS | Port 5173 |
| Event transport (server-internal) | Node.js `EventEmitter` (`EventBus`) | In-process; no network hop |
| Event transport (server → UI) | Server-Sent Events (`SSEHub`) | Two topics: `fleet`, `fleet-manager` |
| State | In-memory `Map`s (`StateStore`) | Lost on restart |
| Mock MCP services | 4 Express servers | Ports 4101–4104 |
| Tool definition | `defineTool` + Zod v4 | All 5 Fleet Manager tools use this shape |
| Build | `tsc` + `vite` | See `package.json` |

See [`README.md`](../README.md) for the `npm run dev` quickstart.

---

## 3. System map

```
                         ┌─────────────────────────────────────────┐
                         │           Express API  :3001             │
                         │                                          │
  ┌──────────────┐  HTTP │  ┌─────────────┐    ┌────────────────┐  │
  │ WorkflowSim  │──────►│  │  StateStore │    │   SSEHub       │  │
  │ (Orchestrator│       │  │  (in-memory)│    │  topic:fleet   │  │
  │  30–50 conc) │       │  └──────┬──────┘    │  topic:fleet-  │  │
  └──────┬───────┘       │         │            │    manager     │  │
         │ callMcp()     │  ┌──────▼──────┐    └───────┬────────┘  │
         │               │  │  EventBus   │            │           │
  ┌──────▼──────┐        │  │ (EventEmit- │◄───────────┤           │
  │ Mock MCPs   │        │  │   ter)      │            │           │
  │ :4101 wd    │        │  └──────┬──────┘     onLive()           │
  │ :4102 d365  │        │         │broadcast   ┌───────┴────────┐  │
  │ :4103 mac   │        │         │            │ FleetManager   │  │
  │ :4104 pay   │        │  ┌──────▼──────┐    │ Service        │  │
  └─────────────┘        │  │   Triage    │    │ (GHCP SDK      │  │
                         │  │  + Queue    │───►│  session)      │  │
                         │  │ debounce    │    │  ┌──────────┐  │  │
                         │  │   2000ms    │    │  │ MCP Tools│  │  │
                         │  └─────────────┘    │  │ query-   │  │  │
                         │                     │  │ fleet    │  │  │
                         │  ┌──────────────┐   │  │ query-   │  │  │
                         │  │ AuditLogger  │   │  │ traces   │  │  │
                         │  └──────────────┘   │  │ compose- │  │  │
                         │                     │  │ exception│  │  │
                         └─────────────────────┘  └──────────┘  │  │
                                                  └─────────────┘  │
                                                                    │
  ┌─────────────────────────────────────────────────────────────────┘
  │   React UI  :5173
  │   ┌────────────────────────────┐  ┌──────────────────┐
  │   │  Main area (5 routes)      │  │ Right rail       │
  │   │  FleetDashboard            │  │ FleetManagerRail │
  │   │  ExceptionQueue            │  │ SSE: fleet-mgr   │
  │   │  WorkflowDetail            │  │ max 50 events    │
  │   │  PolicyAndAutonomy         │  └──────────────────┘
  │   │  Analytics / Evaluations   │
  │   └────────────────────────────┘
  └─────────────────────────────────────────────────────────────────
```

Event flow direction: `WorkflowSimulator` → `EventBus` → fan-out to `SSEHub("fleet")` and `FleetManagerService.triage` → `FleetManagerQueue` → `session.sendAndWait` → MCP tool calls → `StateStore` upserts → SSEHub("fleet-manager") → right rail.

---

## 4. The three tiers

### 4.1 Fleet Manager

The Fleet Manager is a persistent `CopilotSession` created at server startup in [`fleetManagerService.ts`](../src/server/services/fleetManagerService.ts). It is the only part of the system that uses `@github/copilot-sdk`.

**Auth.** At boot, [`index.ts`](../src/server/index.ts) runs `execSync("gh auth token")` and passes the result as `githubToken` to `new CopilotClient(...)`. If the token fetch fails, the Fleet Manager is skipped entirely — the rest of the system boots and runs normally (see §11).

**Session creation.** `FleetManagerService.start()` calls `client.createSession(...)` with:
- `model`: defaults to `"gpt-4.1"`, overridable via env.
- `maxTokens`: defaults to 2000.
- `onPermissionRequest: approveAll` — all tool executions are auto-approved; there is no interactive confirmation step.
- `tools`: the 5 Fleet Manager MCP tools (see §9).
- `systemMessage`: the contents of [`fleet-manager.skill.md`](../src/server/skills/fleet-manager.skill.md) appended to the system prompt.
- `infiniteSessions: { enabled: false }` — disables context compaction for predictability in the demo.

**Wake-up.** The Fleet Manager subscribes to the `EventBus` via `bus.onAny(...)`. On each event it calls `triage.observe(event)` and `triage.detectAnomaly()`. If the event type is in `WAKE_TYPES` (defined in [`events.ts`](../src/shared/events.ts)) and carries a `workflowId`, the entry is pushed into the `FleetManagerQueue`. The queue batches entries with a **2-second debounce** (`debounceMs: 2000`) before flushing — so rapid bursts from the same workflow coalesce into a single agent invocation.

**Fleet tick.** A `setInterval` fires every **30 seconds** and emits `fleet.tick` onto the bus. This wakes the Fleet Manager on the regular cadence described in the skill: produce a fleet-health summary only if anomalies exist, otherwise exit silently.

**Agent invocation.** `processBatch(batch)` assembles a plain-text prompt listing all triggering workflow IDs and reasons, then calls `session.sendAndWait(prompt, 60_000)`. The session handles tool-call/response turns internally; the server receives the final assistant message when all tool calls are complete (or the 60s timeout expires).

**Overload guard.** If the queue depth exceeds 20 entries at flush time, the service emits `fleet.overload` onto the bus. This is informational only in v1 — no shedding occurs.

**Live events.** The `onLive` callback passed to `FleetManagerService` is wired in `index.ts` to `hub.broadcast("fleet-manager", ev)`. This pushes every `FleetManagerLiveEvent` (kind: `idle | wakeup | reasoning_start | tool_call | reasoning_done | error`) to SSE clients on the `fleet-manager` topic.

**Tool-call observation.** `session.on("tool.execution_start", ...)` and `session.on("tool.execution_complete", ...)` are registered before any messages are sent, and forward events through `onLive` to the right rail.

**Compose-exception hook gate.** `compose-exception` is the only tool that writes to `StateStore` and is described in its `defineTool` description as "Non-revocable action — audited before and after write." It logs two `AuditLogger` entries (pre and post) around the `store.upsertException(exc)` call. All other tools are read-only.

**Key files:** [`fleetManagerService.ts`](../src/server/services/fleetManagerService.ts), [`fleetManagerQueue.ts`](../src/server/services/fleetManagerQueue.ts), [`triage.ts`](../src/server/services/triage.ts), [`fleet-manager.skill.md`](../src/server/skills/fleet-manager.skill.md), [`mcp-tools/index.ts`](../src/server/mcp-tools/index.ts).

---

### 4.2 Workflow orchestration

The simulator is a deterministic async state machine, not an LLM. It exists to drive realistic-looking fleet activity at demo time.

**Orchestrator.** [`simulatorOrchestrator.ts`](../src/server/services/simulatorOrchestrator.ts) ramps up to a target number of concurrent workflows (default 40, configurable via `SIMULATOR_TARGET_WORKFLOWS`) over 3 minutes (`rampMs: 180_000`), then spawns additional workflows every 3–8 seconds indefinitely.

**Lifecycle.** Each workflow runs a 6-phase pipeline: `Intake → Validation → Routing → Approval → Payment → Reconciliation`. The phase sequence is defined in `PHASE_ORDER` in [`types.ts`](../src/shared/types.ts). Each phase is a dedicated async function in [`workflowSimulator.ts`](../src/server/services/workflowSimulator.ts) that:
1. Appends a `Phase` record with status `in_progress`.
2. Emits `workflow.phase.started`.
3. Calls mock MCP tools via `callMcp()` and traces each call as an `OtelSpan`.
4. On success: updates phase to `completed`, emits an `otel.span.emitted` for the phase, emits `workflow.phase.completed`.
5. On exception scenario: emits `workflow.exception.detected` and sets the workflow to `awaiting_hitl`.

**Scenario injection.** Every `spawn()` call picks a scenario from a weighted distribution: normal (~59%), po-mismatch (15%), duplicate-invoice (10%), threshold-exceeded (8%), sanctions-flag (5%), payment-timeout (2%), compliance (1%). The `POST /api/simulator/inject` endpoint accepts an explicit `scenario` string to bypass the random draw — used in the demo script.

**OTEL emission.** `traceTool()` wraps every MCP call and appends an `OtelSpan` to `StateStore` and emits `otel.span.emitted` regardless of outcome. Spans carry `workflow.id`, `workflow.phase`, and `tool.name` attributes. There is no real OTEL collector — the spans live in memory and are queryable via `GET /api/workflows/:id`.

**Why not real GHCP SDK sub-sessions for phases?** Deterministic phase functions give the demo three things real sub-sessions cannot: predictable timing, zero token cost for orchestration, and the ability to inject specific failure scenarios on demand. The production target (Azure Durable Functions) is documented in §12.

**Key files:** [`workflowSimulator.ts`](../src/server/services/workflowSimulator.ts), [`simulatorOrchestrator.ts`](../src/server/services/simulatorOrchestrator.ts), [`mcpClient.ts`](../src/server/services/mcpClient.ts).

---

### 4.3 Mock MCP integrations

Four small Express services expose a `POST /mcp/call/:tool` endpoint and a `GET /mcp/tools` listing. All are fixture-backed (JSON files in their respective directories).

| Service | Port | Tools | Fixture |
|---------|------|-------|---------|
| workday-mcp | 4101 | `getVendor`, `getCostCentre`, `getApprovalChain` | vendors, cost centres, approval chains |
| d365-mcp | 4102 | `parseInvoice`, `matchPO`, `postGLEntry` | purchase orders, GL accounts |
| maconomy-mcp | 4103 | `lookupProject`, `getTimesheetHours` | projects (timesheet data is randomised) |
| payment-mcp | 4104 | `createPaymentFile`, `submitPayment`, `reconcileStatement` | none (stateless); first-call timeout simulation via in-process `Set` |

The `payment-mcp` implements a stateful first-call timeout: when `simulateTimeout: true` is passed, the first call per `paymentFileId` returns 504 after 50ms; subsequent calls succeed. This drives the `payment-timeout` scenario in the simulator.

**Why not real MCP servers?** The simulator calls these services using plain HTTP (`callMcp` in `mcpClient.ts`) — not the MCP wire protocol. The services satisfy the simulator's tool-call shape (POST body in, JSON out) without needing an MCP SDK. The Fleet Manager's tools (`query-fleet`, `query-traces`, etc.) are registered directly on the GHCP SDK session via `defineTool` — they are not MCP servers either; they are in-process tool handlers that read from `StateStore`.

**Key files:** [`mocks/workday-mcp/server.ts`](../mocks/workday-mcp/server.ts), [`mocks/d365-mcp/server.ts`](../mocks/d365-mcp/server.ts), [`mocks/maconomy-mcp/server.ts`](../mocks/maconomy-mcp/server.ts), [`mocks/payment-mcp/server.ts`](../mocks/payment-mcp/server.ts), [`mcpClient.ts`](../src/server/services/mcpClient.ts).

---

## 5. Event flow walkthrough — life of one workflow

**T+0 — spawn.** `SimulatorOrchestrator` calls `sim.spawn()`. The simulator assigns the next sequential ID (`INV-0042`), picks a scenario (say, `duplicate-invoice`), calls `store.upsertWorkflow(w)`, and emits `workflow.started` on the bus.

**T+0 — bus fan-out.** `EventBus.emit()` fires the event to all typed listeners and the catch-all `"*"` listener. The catch-all wired in `index.ts` (`bus.onAny((e) => hub.broadcast("fleet", e))`) immediately pushes the event as `data: {...}\n\n` to all SSE clients on the `fleet` topic. The `useWorkflows` hook in the UI receives this via SSE and triggers a re-fetch of `GET /api/workflows`. The Fleet Dashboard refreshes.

**T+0 — Fleet Manager triage.** The Fleet Manager's own `bus.onAny` handler fires. `triage.observe(event)` is called — for non-exception events this is a no-op. `triage.shouldWake(event)` returns `false` for `workflow.started` (not in `WAKE_TYPES`), so nothing is enqueued.

**T+0–3s — Intake phase.** `doIntake()` sleeps 1–3 seconds, then calls `callMcp(workdayUrl, "getVendor", ...)` and `callMcp(d365Url, "parseInvoice", ...)`. Each call is wrapped in `traceTool()`, which appends an `OtelSpan` to `StateStore` and emits `otel.span.emitted` — two more events onto the bus, two more SSE pushes to the `fleet` topic.

**Validation — exception detected.** `doValidation()` checks the scenario. For `duplicate-invoice`, it calls `emitException(workflowId, "duplicate-invoice", "high")`. This sets `w.status = "awaiting_hitl"`, calls `store.upsertWorkflow(w)`, and emits `workflow.exception.detected` with `category: "duplicate-invoice"` and `severity: "high"`.

**Fleet Manager wakes.** The Fleet Manager's bus handler fires for `workflow.exception.detected`. `triage.observe(event)` records this in `recentDups`. `triage.detectAnomaly()` checks if 3+ duplicate-invoice exceptions have arrived in the last 60 seconds — if not, no anomaly. `triage.shouldWake(event)` returns `true` (it is in `WAKE_TYPES`). The entry is `queue.enqueue({ workflowId: "INV-0042", reason: "workflow.exception.detected" })`. The right rail receives a `wakeup` live event immediately (before the debounce fires).

**2-second debounce.** `FleetManagerQueue` starts a `setTimeout` for 2000ms. Any additional exception events for `INV-0042` arriving in that window overwrite the same `Map` entry (keyed by `workflowId`) — they do not add duplicate queue entries. After 2 seconds, `flush()` runs.

**Agent invocation.** `processBatch` assembles the prompt and calls `session.sendAndWait(prompt, 60_000)`. A `reasoning_start` live event is broadcast to the right rail. The GHCP SDK sends the prompt to the model.

**Tool calls.** The model calls `query-fleet` first (no args or minimal filters). The handler calls `store.listWorkflows({})` and `store.listExceptions()`, returns aggregate counts and the 5 most recent exceptions. The model then calls `query-traces({ workflowId: "INV-0042" })`, which returns all `OtelSpan` records for this workflow. Each `tool.execution_start` and `tool.execution_complete` event on the session fires the registered listener, which calls `onLive(...)`, which broadcasts to `hub("fleet-manager")`. The right rail receives `tool_call(start)` then `tool_call(complete)` for each tool.

**compose-exception.** The model calls `compose-exception` with a composed summary, recommendation, options array, and `confidence` score. The handler: (1) logs `compose-exception.pre` to `AuditLogger`; (2) constructs an `Exception` object with a `nanoid`-generated ID; (3) calls `store.upsertException(exc)`, which sets `w.activeExceptionId = exc.id`; (4) logs `compose-exception.emitted`. The Fleet Manager does not emit anything to the event bus at this point — the exception simply exists in `StateStore`.

**reasoning_done.** `session.sendAndWait` returns. `processBatch` broadcasts `reasoning_done` with a 200-character preview of the assistant's response. The right rail completes its sequence: `wakeup → reasoning_start → tool_call(start) → tool_call(complete) × N → reasoning_done`.

**UI update.** The `useWorkflows` hook's SSE listener has been receiving `otel.span.emitted` events throughout — each triggers a `GET /api/workflows` re-fetch. The Fleet Dashboard shows `INV-0042` with status `awaiting_hitl`. The operator sees the exception badge and navigates to `ExceptionQueue` or clicks the workflow card to open `WorkflowDetail`. On `WorkflowDetail`, the Overview tab shows the active exception (fetched from `GET /api/workflows/INV-0042` which includes `activeException`).

**Resolution.** The operator selects the exception and clicks "Bulk resolve". `ExceptionQueue` posts to `POST /api/exceptions/bulk-resolve`. The route calls `store.resolveException(id, resolvedBy)`, sets `e.resolvedAt`, clears `w.activeExceptionId`, and appends an `ActionLedgerEntry` (actor: `human`, revocable: `false`) to the workflow.

---

## 6. The five mechanisms that make it scale

The design spec describes a 5-layer escalation architecture. Here is the v1 implementation status of each:

| Mechanism | v1 Status | Implementation |
|-----------|-----------|---------------|
| **Event classification** | Implemented | `WAKE_TYPES` in [`events.ts`](../src/shared/events.ts); 6 wake-worthy types out of 13 total |
| **Triage + anomaly detection** | Implemented | `Triage.observe()` + `detectAnomaly()` in [`triage.ts`](../src/server/services/triage.ts); duplicate-burst pattern (3+ in 60s) triggers `fleet.anomaly.detected` |
| **Debounce queue** | Implemented | `FleetManagerQueue` with 2s debounce + deduplication by `workflowId`; overload signal at depth > 20 |
| **Bounded concurrency** | Partially implemented | `flushing` guard prevents concurrent `processBatch` runs; no formal concurrency cap on agent calls |
| **Tiered models** | Documented only | Single model (`gpt-4.1`) in v1; the spec describes routing high-severity events to more capable models — not implemented |

---

## 7. Data model

All types are defined in [`types.ts`](../src/shared/types.ts). All instances live in [`StateStore`](../src/server/services/stateStore.ts) in-memory Maps.

| Entity | Description |
|--------|-------------|
| `Workflow` | One invoice P2P run: vendor, invoice data, SLA deadline, current phase, status, action ledger, token/cost counters, optional `activeExceptionId` |
| `Phase` | One named phase within a workflow: status, timestamps, `agentId`, tool calls summary, span IDs |
| `OtelSpan` | One traced operation: trace/span IDs, name, start/end timestamps, attributes (`workflow.id`, `workflow.phase`, `tool.name`, LLM metrics), status |
| `Exception` | A Fleet Manager–composed or simulator-injected exception surfaced to the operator: severity, category, summary, recommendation, decision options, policy refs, bulk candidate IDs, confidence score, composer identity |
| `AutonomyPolicy` | A named policy parameter loaded from [`policies.yaml`](../src/shared/policies.yaml): current value, `gitSha`, author, timestamp. Three policies ship: `auto_threshold` (5000), `variance.tolerance_pct` (0.02), `duplicate.window_days` (30) |
| `SkillAmplification` | Fleet Manager–generated context card: policy snippets, precedent decisions, recommended approach — surfaced in `WorkflowDetail` Amplification tab |
| `ActionLedgerEntry` | Append-only record on `Workflow.actionLedger`: actor (agent/human + id), action string, revocable flag, details |

---

## 8. Event taxonomy

Defined in [`events.ts`](../src/shared/events.ts). The `FleetEvent` discriminated union has 13 types:

| Event type | Wakes Fleet Manager | Description |
|------------|--------------------|----|
| `workflow.started` | No | New workflow spawned |
| `workflow.phase.started` | No | Phase began |
| `workflow.phase.completed` | No | Phase finished successfully |
| `workflow.phase.failed` | No | Phase threw an error |
| `workflow.exception.detected` | **Yes** | Simulator detected an exception scenario |
| `workflow.hitl.requested` | **Yes** | Threshold-exceeded: explicit HITL request |
| `workflow.sla.breach_imminent` | **Yes** | SLA deadline approaching (emitted by simulator — not yet wired in v1 simulator; type defined) |
| `workflow.policy.violation` | **Yes** | Policy breach detected (type defined; not currently emitted by simulator) |
| `workflow.resolved` | No | Workflow completed or resolved |
| `otel.span.emitted` | No | A traced tool call or phase completed |
| `fleet.anomaly.detected` | **Yes** | Triage detected a cross-workflow pattern |
| `fleet.tick` | **Yes** | 30-second heartbeat |
| `fleet.overload` | No | Queue depth exceeded 20 |

Note: `workflow.sla.breach_imminent` and `workflow.policy.violation` are in `WAKE_TYPES` and the triage code handles them, but the v1 simulator does not emit them. They would wake the Fleet Manager if emitted by an external system or future simulator extension.

---

## 9. Fleet Manager MCP tools

All five tools are defined using `defineTool` from `@github/copilot-sdk` with Zod v4 parameter schemas. All use `skipPermission: true` (the `approveAll` handler covers this at session level). They are assembled in [`mcp-tools/index.ts`](../src/server/mcp-tools/index.ts) and registered at `createSession` time.

| Tool | File | Hook-gated | Description |
|------|------|-----------|-------------|
| `query-fleet` | [`queryFleet.ts`](../src/server/mcp-tools/queryFleet.ts) | No | Returns workflow counts by phase and status, plus the 5 most recent open exceptions. Accepts optional `phase`, `agency`, `hasException` filters. |
| `query-traces` | [`queryTraces.ts`](../src/server/mcp-tools/queryTraces.ts) | No | Returns all `OtelSpan` records for a given `workflowId`, optionally filtered by phase. Returns span count, durations, tool names, LLM metrics. |
| `compose-exception` | [`composeException.ts`](../src/server/mcp-tools/composeException.ts) | **Yes** — audit pre + post | Constructs and upserts an `Exception` into `StateStore`. Logs `compose-exception.pre` before the write and `compose-exception.emitted` after. The only tool that mutates state. |
| `propose-skill-amplification` | [`proposeSkillAmp.ts`](../src/server/mcp-tools/proposeSkillAmp.ts) | No | Appends a `SkillAmplification` card to `StateStore` for a workflow. Policy context and precedents are supplied by the model. Surfaced in WorkflowDetail UI. |
| `dry-run-policy` | [`dryRunPolicy.ts`](../src/server/mcp-tools/dryRunPolicy.ts) | No | Replays completed workflows against a proposed policy value and returns how many outcomes would have differed. In v1 only `invoice-p2p.approval.auto_threshold` is implemented; defaults to 30-day scope, caps impacted IDs at 20. Also callable directly from the UI via `POST /api/policy/dry-run`. |

`compose-exception` is described in the skill as the action that writes to the operator queue. The skill explicitly instructs the agent: "Never call `compose-exception` twice for the same root cause in the same debounce window."

---

## 10. UI surfaces

The React app at `:5173` is a single-page app with a persistent right rail. All routes are in [`src/client/routes/`](../src/client/routes/).

| Screen | Route | File | What it shows |
|--------|-------|------|---------------|
| Fleet Dashboard | `/fleet` | [`FleetDashboard.tsx`](../src/client/routes/FleetDashboard.tsx) | Summary counters (total, in-flight, awaiting HITL, completed, exceptions); workflow cards filterable by phase, agency, exceptions-only. Refreshes on SSE `fleet` events. |
| Exception Queue | `/exceptions` | [`ExceptionQueue.tsx`](../src/client/routes/ExceptionQueue.tsx) | List of open exceptions. Multi-select + bulk resolve via `POST /api/exceptions/bulk-resolve`. |
| Workflow Detail | `/workflows/:id` | [`WorkflowDetail.tsx`](../src/client/routes/WorkflowDetail.tsx) | 5 tabs: Overview (status + active exception), Phases (timeline), Traces (OTEL span tree), Ledger (action history with revocable flag), Amplification (skill-amp cards). |
| Policy & Autonomy | `/policy` | [`PolicyAndAutonomy.tsx`](../src/client/routes/PolicyAndAutonomy.tsx) | Reads policies from `GET /api/policy`. Read-only current values with git SHA and author. Right panel: `WhatIfPanel` calls `POST /api/policy/dry-run`. Change proposals submit to `POST /api/policy/propose-change` (stored in memory, no persistence). |
| Analytics | `/analytics` | [`Analytics.tsx`](../src/client/routes/Analytics.tsx) | 4 static-ish metrics: intervention rate (computed from action ledger), avg resolution (hardcoded 240s), override frequency (hardcoded 12%), quality delta (hardcoded +4%). Lightweight placeholder. |
| Evaluations | `/evals` | [`Evaluations.tsx`](../src/client/routes/Evaluations.tsx) | Polls `GET /api/evals` every 5 seconds. Displays last 50 eval records with task adherence, safety, and tool accuracy scores. Scores are synthetic (see `EvalRunner` §6). |
| Fleet Manager Rail | (persistent aside) | [`FleetManagerRail.tsx`](../src/client/components/FleetManagerRail.tsx) | SSE stream from `/api/stream/fleet-manager`. Buffers the last **50 events** (`max = 50`). Displays `kind`, truncated JSON data (160 chars), and timestamp for each live event. |

The `useWorkflows` hook subscribes to `/api/stream/fleet` and re-fetches `GET /api/workflows` on any `workflow.*` or `otel.span.emitted` event. The `useFleetManagerStream` hook subscribes to `/api/stream/fleet-manager` and prepends each incoming event, capping at 50.

---

## 11. Auth model

The only credential in the system is the GitHub personal access token obtained at server boot:

```
githubToken = execSync("gh auth token", { encoding: "utf-8" }).trim()
```

This is passed directly to `new CopilotClient({ githubToken })`. The SDK passes it to the Copilot CLI subprocess internally. Token scopes required: `repo` + `read:org` (standard `gh auth login` scopes). A personal Copilot license is sufficient — no Azure Foundry or Entra credentials are needed.

**Graceful degradation if `gh auth token` fails.** The `try/catch` in [`index.ts`](../src/server/index.ts) logs a warning and continues. `githubToken` remains an empty string. The `if (githubToken)` guard prevents `fm.start()` from being called. The server starts, the simulator runs, all REST routes respond, SSE topics broadcast fleet events — only the `fleet-manager` SSE topic remains silent and the Exception Queue is never populated by the agent. Simulator-injected exceptions (`composedBy: "simulator-injected"`) are not currently implemented in v1, so the exception queue stays empty. This mode is useful for testing the UI and simulator without a Copilot license.

There is no session auth on the API — all endpoints are open. No multi-user identity; the implicit operator identity is `finance-controller@wpp` (hardcoded in the UI header and in `bulk-resolve` calls).

---

## 12. What's REAL vs what's SIMULATED

| Concern | v1 Implementation | Production target |
|---------|-------------------|-------------------|
| Fleet Manager agent | Real `@github/copilot-sdk` v0.2.2 session, real LLM calls, real tool execution | Foundry-hosted agent with Entra Agent ID; BYOK Azure OpenAI provider |
| Agent auth | Personal GitHub Copilot license via `gh auth token` | Managed identity / service principal; no CLI dependency |
| Workflow orchestration | In-memory async + deterministic phase functions; synthetic timing (sleep ranges) | Azure Durable Functions; real ERP system calls |
| MCP integrations | 4 Express HTTP stubs backed by JSON fixtures | Real MCP servers talking to Workday, Dynamics 365, Maconomy, payment rails |
| Event bus | In-process Node.js `EventEmitter` | Azure Event Grid or Service Bus |
| State store | In-memory Maps (lost on restart) | Cosmos DB |
| Audit log | In-memory array in `AuditLogger` | Immutable append-only log (Cosmos or Log Analytics) |
| SSE transport | Direct Express SSE | Azure SignalR or Event Grid webhooks |
| OTEL spans | Synthetic spans stored in memory | Real OTel SDK → Azure Monitor / Application Insights |
| Eval scores | Synthetic random scores in `EvalRunner` (`taskAdherence: 0.85–1.0`, `safety: 0.95–1.0`, `toolAccuracy: 0.88–1.0`) | LLM-as-judge eval harness against real traces |
| Policy store | Static `policies.yaml` loaded at boot; change-requests in-memory | Git-backed policy repo; PR/change-request workflow |
| Concurrency | Single Node.js process; no horizontal scaling | Fleet Manager pool; multiple Durable Function workers |
| Multi-tenancy | Single implicit operator; single agency context in UI | Per-agency RBAC; Entra-backed multi-tenant |

---

## 13. Extension points

**Replace the simulator with real workflows.** The `EventBus` and `StateStore` interfaces are the only contracts the Fleet Manager depends on. A real workflow engine emitting `FleetEvent`s onto the bus would work without any changes to `FleetManagerService`, `Triage`, or the MCP tools.

**Replace in-memory store with Cosmos DB.** `StateStore` has a clean CRUD interface. Replacing the backing `Map`s with Cosmos SDK calls requires changes only inside [`stateStore.ts`](../src/server/services/stateStore.ts).

**Replace in-process EventBus with Event Grid.** Subscribe `FleetManagerService.busUnsub` to an Event Grid topic instead of the local `EventEmitter`. The `FleetEvent` union and `WAKE_TYPES` set are the contract — no changes to triage or queue logic needed.

**Add a second agent type.** `buildFleetManagerTools(store, bus, audit)` returns a plain array. A second `CopilotSession` with different tools and a different skill file can be created from the same `CopilotClient`. The `SSEHub` already supports arbitrary topic strings.

**Replace `gh auth token` with BYOK Azure OpenAI.** Per [`SPIKE-NOTES.md`](../spike/SPIKE-NOTES.md) §6, swapping auth is one `provider:` object in `createSession`. The rest of the Fleet Manager code does not change.

**Add persistence across restarts.** The simulator assigns sequential IDs from `this.seq = 0`. In a persistent deployment, seed `seq` from the last stored workflow ID. The `StateStore` interface supports incremental upserts — Cosmos `upsert` semantics map directly.

---

## 14. Constraints inherited from the build

| Constraint | Detail |
|-----------|--------|
| SDK preview | `@github/copilot-sdk` v0.2.2 is a preview release. The API surface is not stable. See [`SPIKE-NOTES.md`](../spike/SPIKE-NOTES.md) for the confirmed working patterns. |
| Single CLI subprocess | `CopilotClient` spawns one Copilot CLI subprocess (confirmed by the spike). Running multiple concurrent `CopilotClient` instances means multiple subprocesses. The v1 design uses one session — adequate for a demo but not fleet-scale production. |
| In-memory state | All `StateStore` data is lost on server restart. `npm run dev` starts fresh every time. |
| Local only | No HTTPS, no ingress, no load balancer. All ports are localhost. |
| No real HITL loop-back | When the operator resolves an exception, the workflow status is set back to `in_progress` but the simulator has already exited the lifecycle — the workflow does not resume the remaining phases. |
| Synthetic eval scores | `EvalRunner` generates random scores every 15 seconds. There is no actual quality measurement against real agent behaviour. |
| Anomaly detection is single-pattern | `Triage.detectAnomaly()` only detects `duplicate-burst` (3+ duplicates in 60s). Other anomaly patterns are not implemented. |
| No SSE reconnection logic | The `useSSE` hook does not implement exponential backoff or reconnection on connection drop. A browser tab that loses the server connection will not re-subscribe automatically. |

---

## 15. File map

```
control-plane/
│
├── src/
│   ├── shared/
│   │   ├── types.ts            ← Domain model (Workflow, Phase, Exception, etc.)
│   │   ├── events.ts           ← FleetEvent union, WAKE_TYPES, wakesFleetManager()
│   │   └── policies.yaml       ← 3 declarative policy parameters (loaded at boot)
│   │
│   ├── server/
│   │   ├── index.ts            ← Wiring: constructs all services, mounts routes, boots server
│   │   │
│   │   ├── services/
│   │   │   ├── eventBus.ts         ← Typed EventEmitter wrapper; onAny() for catch-all
│   │   │   ├── stateStore.ts       ← In-memory Maps for all 7 entity types
│   │   │   ├── triage.ts           ← shouldWake() + observe() + detectAnomaly()
│   │   │   ├── fleetManagerQueue.ts← Debounce queue (2s); dedup by workflowId
│   │   │   ├── fleetManagerService.ts ← CopilotClient + CopilotSession; all agent wiring
│   │   │   ├── workflowSimulator.ts← 6-phase deterministic state machine; scenario injection
│   │   │   ├── simulatorOrchestrator.ts ← Ramp to target + steady-state spawning
│   │   │   ├── mcpClient.ts        ← callMcp(): POST /mcp/call/:tool
│   │   │   ├── sseHub.ts           ← SSE broadcaster; topics: fleet, fleet-manager
│   │   │   ├── auditLogger.ts      ← In-memory append-only audit log
│   │   │   └── evalRunner.ts       ← Synthetic eval sampling every 15s; last 50 results
│   │   │
│   │   ├── mcp-tools/
│   │   │   ├── index.ts            ← buildFleetManagerTools(): assembles all 5 tools
│   │   │   ├── queryFleet.ts       ← query-fleet: fleet aggregate + recent exceptions
│   │   │   ├── queryTraces.ts      ← query-traces: OtelSpans by workflow + phase
│   │   │   ├── composeException.ts ← compose-exception: hook-gated, audited write
│   │   │   ├── proposeSkillAmp.ts  ← propose-skill-amplification: context card write
│   │   │   └── dryRunPolicy.ts     ← dry-run-policy: replay completed workflows
│   │   │
│   │   ├── routes/
│   │   │   ├── workflows.ts    ← GET /api/workflows, GET /api/workflows/:id
│   │   │   ├── exceptions.ts   ← GET /api/exceptions, POST /api/exceptions/bulk-resolve
│   │   │   ├── policy.ts       ← GET /api/policy, POST /api/policy/dry-run, propose-change
│   │   │   ├── simulator.ts    ← POST /api/simulator/inject
│   │   │   ├── audit.ts        ← GET /api/audit
│   │   │   ├── evals.ts        ← GET /api/evals
│   │   │   └── stream.ts       ← GET /api/stream/fleet, GET /api/stream/fleet-manager
│   │   │
│   │   ├── skills/
│   │   │   └── fleet-manager.skill.md  ← System prompt for Fleet Manager session
│   │   │
│   │   └── fixtures/
│   │       ├── vendors.json        ← Vendor master (id, name, country, sanctioned)
│   │       ├── purchase-orders.json← PO master (id, vendorId, amount, currency)
│   │       ├── agencies.json       ← Agency list (id, market, region)
│   │       └── policy-refs.json    ← Policy reference library
│   │
│   └── client/
│       ├── App.tsx                 ← Shell: nav, main, FleetManagerRail aside
│       ├── routes/
│       │   ├── FleetDashboard.tsx  ← Workflow grid + counters
│       │   ├── ExceptionQueue.tsx  ← Exception list + bulk resolve
│       │   ├── WorkflowDetail.tsx  ← 5-tab detail view
│       │   ├── PolicyAndAutonomy.tsx ← Policy read + what-if
│       │   ├── Analytics.tsx       ← Static metric cards
│       │   └── Evaluations.tsx     ← Eval score stream
│       ├── components/
│       │   ├── FleetManagerRail.tsx← Right rail; 50-event buffer
│       │   ├── WorkflowCard.tsx    ← Card in fleet grid
│       │   ├── ExceptionItem.tsx   ← Exception row with checkbox
│       │   ├── BulkHitlModal.tsx   ← Confirm modal for bulk resolve
│       │   ├── PhaseTimeline.tsx   ← Phase status display
│       │   ├── OtelSpanTree.tsx    ← Span list/tree
│       │   ├── SkillAmplificationPanel.tsx ← Amplification cards
│       │   └── WhatIfPanel.tsx     ← dry-run-policy UI
│       └── hooks/
│           ├── useSSE.ts           ← EventSource wrapper
│           ├── useWorkflows.ts     ← Poll + SSE-triggered refresh
│           ├── useExceptions.ts    ← Fetch exceptions
│           └── useFleetManagerStream.ts ← SSE buffer (max 50)
│
├── mocks/
│   ├── workday-mcp/server.ts   ← getVendor, getCostCentre, getApprovalChain; port 4101
│   ├── d365-mcp/server.ts      ← parseInvoice, matchPO, postGLEntry; port 4102
│   ├── maconomy-mcp/server.ts  ← lookupProject, getTimesheetHours; port 4103
│   └── payment-mcp/server.ts   ← createPaymentFile, submitPayment, reconcileStatement; port 4104
│
├── spike/
│   └── SPIKE-NOTES.md          ← @github/copilot-sdk v0.2.2 API surface findings
│
├── tests/unit/                 ← Vitest unit tests (20 tests)
│
└── docs/
    ├── ARCHITECTURE.md         ← This file
    └── demo-script.md          ← Step-by-step demo walkthrough
```

---

## See also

- [`README.md`](../README.md) — Quickstart, ports, demo inject commands
- [`docs/demo-script.md`](./demo-script.md) — Step-by-step demo walkthrough
- [`spike/SPIKE-NOTES.md`](../spike/SPIKE-NOTES.md) — GHCP SDK v0.2.2 API surface findings; auth patterns; gotchas
- `c:/dev/ghcp sdk stuff/solution/solution.md` — Production architecture (Foundry, Durable Functions, Fleet Manager v2)
- `c:/dev/ghcp sdk stuff/docs/superpowers/specs/2026-04-13-wpp-control-plane-v1-design.md` — Design spec this build implements
