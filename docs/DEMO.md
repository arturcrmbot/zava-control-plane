# Demo

Walkthrough of the POC1 expense compliance pipeline with Durable
Functions orchestration, per-phase MAF Pregel graphs, and a live
Fleet Manager supervising every exception.

> **Canonical state of the demo, including which acceptance criteria
> are live, partial, or to-build, lives in
> [poc1-status.md](poc1-status.md).** This doc is the operational
> "how to run it" companion.

## Pre-flight

```bash
make reset          # wipe Azurite state between takes
make up             # boot azurite + mocks + functions + fastapi + vite
# wait for "All services should be up" banner + 30s for simulator warm-up
```

Open http://localhost:5173 — Fleet Dashboard with a fleet of expense
workflows ramping in, right-rail Fleet Manager idle.

## Injection

```bash
curl -X POST http://localhost:3001/api/simulator/inject \
  -H "Content-Type: application/json" \
  -d '{"scenario":"<name>"}'
```

Passing `{}` or omitting the body runs the default ramp claim.

The full scenario list and routing logic lives in
[api/server/services/simulator_orchestrator.py](../api/server/services/simulator_orchestrator.py).
Receipt-mismatch flavours (`receipt-mismatch-amount`,
`receipt-mismatch-date`, `receipt-mismatch-vendor`,
`receipt-missing-line`, `receipt-missing`) deterministically pick a
claim from the synthetic corpus stamped with that flavour, so the
Phase 3 receipt validator has known content to classify. The Day 9
repeat-offender ramp (`spawn_repeat_offender_ramp`) walks one
employee's claims through warning → escalation → major-violation tiers.

## UI tour

Left-nav routes:

- **Fleet Dashboard** (`/`) — workflow card grid, counters, agency
  filter, right-rail Fleet Manager + Orchestration feeds.
- **Workflow Detail** (`/workflows/:id`) — per-workflow tabbed
  breakdown (Overview · Phases · Traces · Ledger · Amplification ·
  Orchestration). The Orchestration tab is the durable-runtime view:
  instance ID, step-by-step timeline with executors.
- **Exception Queue** — unresolved exceptions with bulk-resolve and
  policy-reference expansions (acceptance #3).
- **Policy** — live policies with dry-run and "propose as change" CTA.
- **Evaluations** — skill-amplification tracker.
- **Analytics** — aggregate counters.

## What's demoable today

For the AC #1–13 status table — what's live, partial, or to-build —
see [poc1-status.md §1](poc1-status.md#1-acceptance-criteria--status).
That table is the single source; do not re-state it here.

## Between takes

```bash
# Stop
# Ctrl-C the `make up` terminal

make reset    # wipe Azurite
make up       # fresh stack, fresh in-memory state
```
