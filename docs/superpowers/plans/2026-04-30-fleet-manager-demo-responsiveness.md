# Fleet Manager Demo Responsiveness — Implementation Plan

**Goal:** Make the Fleet Manager rail populate during a normal expense-claim demo run, instead of staying at "0 recent events" until a HITL suspend fires 60+ seconds in.

**Why this is needed:** Investigation 2026-04-30 confirmed the rail can only update when the FM service wakes up. Today wakes only fire on `workflow.exception.detected` (validator-blocked) or `workflow.hitl.requested` (suspended). The expense workflow's hot path does not emit either until Phase 4+, so the rail looks dead during the long agent steps.

**Two root causes:**

1. The 30s `fleet.tick` heartbeat is filtered out of the wake path in [api/server/services/fleet_manager_service.py:163](../../../api/server/services/fleet_manager_service.py#L163) because it has no `workflow_id` and the guard requires one. So even an idle demo gets no rail activity.
2. The classifier's verdict (`green/amber/red`) never reaches the bus — `claim.routed.*` is declared in [api/shared/events.py:33-35](../../../api/shared/events.py#L33-L35) but no code actually emits it. The deterministic router [api/functions/graphs/executors/deterministic/apply_verdict_routing.py](../../../api/functions/graphs/executors/deterministic/apply_verdict_routing.py) just returns a dict.

**Out of scope:** Changing what the FM reasons about, redesigning the queue, anything in the orchestration tab.

## Steps

- [ ] **Step 1 — Allow workflow-less wake events to enqueue.**
  - Make `QueueEntry.workflow_id` optional in [api/server/services/fleet_manager_queue.py:8-9](../../../api/server/services/fleet_manager_queue.py#L8-L9): `workflow_id: str | None = None`.
  - Change the keying logic at line 17 / line 22: `dict[str, QueueEntry]` keyed by `workflow_id or f"__fleet__:{entry.reason}"` so tick and anomaly events don't collide with each other or with real workflow ids.
  - Drop the `and event.workflow_id` clause from [api/server/services/fleet_manager_service.py:163](../../../api/server/services/fleet_manager_service.py#L163).
  - Update the prompt builder at line 192 to skip the `workflow=` token when `workflow_id is None` (so the model gets `- reason=fleet.tick` instead of `- workflow=None reason=fleet.tick`).
  - Tests to add under `tests/api/unit/`:
    - `test_fleet_manager_queue_workflowless.py` — enqueue two `QueueEntry(workflow_id=None, reason=...)` with different reasons; assert depth=2 and both flush.
    - Extend `test_fleet_manager_service.py` (or create) — emit a `fleet.tick` on the bus, advance the queue debounce, assert `_on_live` saw a `wakeup` followed by `reasoning_start`.

- [ ] **Step 2 — Emit `claim.routed.{green,amber,red}` from the route phase.**
  - The deterministic executor has no `bus` reference, so emit one tier up — in `api/functions/graphs/route.py` after `apply_verdict_routing` runs, or via the activity wrapper in `api/functions/workflows/activities.py::route_activity`. Pick the activity wrapper: it already has the workflow_id and produces the result dict, and keeps executors pure.
  - Read `result["routed_to"]` / `result["verdict"]` from the route activity output; emit `FleetEvent(type=f"claim.routed.{verdict}", workflow_id=..., routed_to=..., escalation_tier=...)` via `app_state.bus.emit(...)` if the activity has bus access, else surface through the same mechanism that `internal_durable_event` uses (preferred — keeps the orchestrator-vs-server boundary intact; add a new `kind="claim_routed"` branch to that route).
  - Test: `tests/api/integration/test_internal_durable_event_claim_routed.py` — POST a `kind=claim_routed` payload with `verdict=red`, assert one `claim.routed.red` event hits the bus with the right workflow_id.

- [ ] **Step 3 — Wake the FM on red routes.**
  - Add `claim.routed.red` to `WAKE_TYPES` in [api/shared/events.py:54-61](../../../api/shared/events.py#L54-L61). Do **not** add green or amber — green is no-op, amber goes to the reviewer queue and doesn't need fleet attention.
  - Update `tests/api/unit/test_events_fleet_type_week2.py` to assert `claim.routed.red in WAKE_TYPES` and the others are not.

- [ ] **Step 4 — Verify in a live demo run.**
  - Start the stack, spawn one red claim via the simulator. Expected sequence in the FM rail: `idle` (on start) → `wakeup` (from `claim.routed.red`, before HITL) → `reasoning_start` → `tool_call` × N → `reasoning_done`. Then a separate `wakeup` for the eventual `workflow.hitl.requested`.
  - Spawn one green claim. Expected: `idle` only, plus periodic `wakeup` from `fleet.tick` every 30s. Confirms Step 1 works without spamming on green.
  - Run `pytest tests/api -q` and `npm run test`; both green.

## Definition of done

1. `pytest tests/api -q` green; `npm run test` green.
2. Live demo run shows FM rail activity within ~5s of a red-route claim, not 60+s.
3. Idle demo (no claims) still shows a periodic FM heartbeat (`wakeup` every 30s with `reason=fleet.tick`).
4. Green and amber claims do **not** wake the FM (verified by absence of FM rail entries for those `workflow_id`s aside from the global tick).

## Risk notes

- The `__fleet__:<reason>` sentinel keying is the only piece of "design choice" here. Alternative: make the queue collapse all workflow-less events into a single `__fleet__` key (loses information when tick + anomaly arrive together within debounce window). Sentinel-per-reason is safer.
- Adding `claim.routed.red` to WAKE_TYPES will increase FM reasoning frequency in production. Acceptable for the demo; if real volume becomes an issue post-demo, gate via the existing autonomy policy mechanism.
- Step 2's choice of emission point (activity vs internal_durable_event route) should match whatever the rest of the orchestration → bus bridge does for `validator.blocked` and `suspended`. Re-check that pattern before implementing — if those go through `internal_durable_event`, follow suit.
