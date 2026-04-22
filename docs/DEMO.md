# Demo

3–5 minute walkthrough of the Finance P2P pipeline with Durable
Functions orchestration, per-phase MAF Pregel graphs, and a live
Fleet Manager supervising every exception.

## Pre-flight

```bash
make reset          # wipe Azurite state between takes
make up             # boot azurite + mocks + functions + fastapi + vite
# wait for "All services should be up" banner + 30s for simulator warm-up
```

Open http://localhost:5173 — you should see the Fleet Dashboard with
a handful of workflows and the right-rail Fleet Manager idle.

## Scenario catalogue

All scenarios inject via:

```bash
curl -X POST http://localhost:3001/api/simulator/inject \
  -H "Content-Type: application/json" \
  -d '{"scenario":"<name>"}'
```

Passing `{}` runs the happy path.

| Scenario | What happens | UI signal |
|---|---|---|
| *(default `{}`)* | Invoice completes all six phases cleanly | Workflow ticks Intake → Validation → Routing → Approval → Payment → Reconciliation; status `completed` |
| `demo-fail` | `agent_gl_coder` picks GL-9999 (inactive); `validate_gl_active` blocks in Routing | Right-rail Fleet Manager wakes, composes exception; card lands in Exception Queue |
| `duplicate-invoice` | Three injections with the same invoice number in rapid succession | Triage coalesces, Fleet Manager composes a bulk-of-3 exception |
| `sanctions-flag` | Vendor flagged during three-way match | Validation phase halts; exception card with policy-ref citation |
| `po-mismatch` | Invoice total exceeds PO allowance | Three-way-match validator blocks; Fleet Manager recommends PO amendment |
| `threshold-exceeded` | Amount above `auto_threshold` policy | Approval phase suspends via `wait_for_external_event`; awaits HITL |
| `payment-timeout` | Mock Payment MCP first-call timeout | Payment phase retries; if still fails, exception with rollback plan |
| `compliance` | Bundled compliance-flag case (legal-flag vendor) | Multiple validators fire; Fleet Manager produces a summary exception |

The full scenario list lives in the switch block in
[api/server/services/simulator_orchestrator.py](../api/server/services/simulator_orchestrator.py).

## UI tour

Left-nav routes, all visible in the demo:

- **Fleet Dashboard** (`/`) — workflow card grid, counters, agency
  filter, right-rail Fleet Manager + Orchestration feeds.
- **Workflow Detail** (`/workflows/:id`) — per-workflow six-tab
  breakdown (Overview · Phases · Traces · Ledger · Amplification ·
  Orchestration). The Orchestration tab is the durable-runtime view:
  instance ID, step-by-step timeline with executors.
- **Exception Queue** — unresolved exceptions with bulk-resolve and
  policy-reference expansions.
- **Policy** — live policies with dry-run and "propose as change" CTA.
- **Evaluations** — skill-amplification tracker (lightweight view).
- **Analytics** — aggregate counters (lightweight view).

## Shot list (record + screenshots)

1. **Fleet Dashboard wide shot** — counters + grid + right rail.
2. **Inject `demo-fail`** — watch right-rail Orchestration feed scroll
   (workflow.started → step.started:Intake → executor.invoked ×N →
   step.completed:Intake → … → step.started:Routing → validator
   blocked). Fleet Manager tab then wakes and composes exception.
3. **Workflow Detail Orchestration tab (HERO)** — click the demo-fail
   workflow, open Orchestration tab. `InvoiceP2POrchestrator` header,
   instance ID, six-step timeline; Routing is blocked with the failed
   `validate_gl_active` validator.
4. **Right-rail Orchestration feed (HERO)** — during a busy moment,
   screenshot the interleaved executor.invoked stream from multiple
   workflows.
5. **Exception Queue with Fleet-Manager-composed exception** — expand
   to show summary + recommendation + policy refs.
6. **Workflow Detail Traces tab** — OTEL span tree from per-phase
   graphs (TrackedExecutor emits these).
7. **HITL workflow suspended** — Workflow Detail → Orchestration →
   Approval step shows `suspended · awaiting approval_decision`.
8. **Resume HITL via bulk-resolve** — Exception Queue → bulk-approve;
   right rail shows `resumed`; Orchestration tab updates Approval →
   completed, Payment → running.
9. **(Optional) Azurite Storage Explorer** — show
   `InvoiceP2PHubInstances` table with persisted orchestration rows —
   proves the durable runtime is real, not in-memory.

## Between takes

```bash
# Stop
# Ctrl-C the `make up` terminal

make reset    # wipe Azurite
make up       # fresh stack, fresh in-memory state
```
