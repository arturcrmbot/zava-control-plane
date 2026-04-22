# Python POC1 Demo Script

3-5 minute walkthrough showing the real DF + MAF + GHCP SDK three-layer architecture in action.

## Pre-flight

1. All 5 terminals up per README quickstart
2. Wait 60s after FastAPI boots for the simulator ramp to populate workflows (visible on Fleet Dashboard)
3. Fleet Manager right-rail should show a few wakeup -> reasoning -> tool_call -> reasoning_done sequences from the periodic 30s tick

## Shot list (record + screenshot)

### Shot 1 — Fleet Dashboard (CP-1 / CP-7 / CP-8)
- Open http://localhost:5173
- Wide shot showing 30+ workflows, counters at top, filter bar, right rail visible
- Note the right rail has TWO tabs: [Fleet Manager] [Orchestration]

### Shot 2 — Inject the bounded-probabilism case
Run in a side terminal:
```bash
curl -X POST http://localhost:3001/api/simulator/inject \
  -H "Content-Type: application/json" \
  -d '{"scenario":"demo-fail"}'
```
Watch the right rail Orchestration tab — workflow.started -> step.started:Intake -> executor.invoked entries -> step.completed:Intake -> ... -> eventually reaches Routing where validate_gl_active blocks. Right rail Fleet Manager tab then lights up as FM picks up the validator-blocked event and composes an exception.

### Shot 3 — Workflow Detail Orchestration tab (HERO SHOT)
- Click the demo-fail workflow on the Fleet Dashboard
- Workflow Detail opens with 6 tabs: Overview / Phases / Traces / Ledger / Amplification / **Orchestration**
- Click Orchestration tab
- Screenshot: "Durable Workflow: InvoiceP2POrchestrator" header, instance ID, status, 6-step timeline with per-step executor lists. The Routing step shows blocked with the failed `validate_gl_active` validator.

### Shot 4 — Right rail Orchestration feed (HERO SHOT)
- During a busy moment (multiple workflows running), screenshot the right rail's Orchestration tab
- Should show a stream of executor.invoked events from multiple workflows interleaved

### Shot 5 — Exception Queue with Fleet Manager-composed exception
- Click "Exceptions" in left nav
- Find the validator-blocked exception
- Expand it: shows summary, recommendation, related policy refs

### Shot 6 — Workflow Detail Traces tab
- Same workflow, switch to Traces tab
- Shows OTEL spans from Phase 8 graphs (TrackedExecutor emits these)

### Shot 7 — HITL workflow suspended
- Without injecting demo-fail, normal workflows above $5000 hit Approval HITL
- Find one: Workflow Detail -> Orchestration tab -> "Approval" step shows suspended with "awaiting `approval_decision`"
- Screenshot

### Shot 8 — Resume HITL via bulk-resolve
- Go to Exceptions, find the HITL request, click bulk resolve approve
- Right rail shows "resumed" event for the workflow
- Workflow Detail Orchestration tab updates: Approval completed, Payment running

### Shot 9 — Azurite Storage Explorer view
- (Optional) Open Azure Storage Explorer connected to Azurite
- Show the `InvoiceP2PHubInstances` table with persisted orchestration rows
- Proves the durable runtime is real, not in-memory

## Post-recording

- Trim to 3-5 min
- Title card: "WPP Control Plane Python POC1 — MAF Durable Agents on Azure Durable Functions"
- Export to `response/evidence/poc1-py-demo.mp4`
- Copy hero PNGs (shots 3, 4, 7) to `response/evidence/` for embedding in `response-technical-sections.md`
