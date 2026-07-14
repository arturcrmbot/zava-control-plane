# Autonomy Kernel Through Existing Worlds Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace scenario/responder branches with small registries and introduce a deterministic objective/command lifecycle while preserving the proven support and telco behavior.

**Architecture:** A static world-pack registry builds scenarios; sensors open deduplicated objectives; a responder registry selects the Durable orchestrator; a command gateway enforces objective command scope before delegating mutation to the scenario. Existing responder and world events remain for UI/proof compatibility.

**Tech Stack:** Python 3.13, SimPy, FastAPI EventBus, Azure Durable Functions, pytest.

**Status:** ✅ Implemented (all tasks). Commits: Task 1 `59abcfc1`, Task 2
`232c4d20`, Task 3 `341a90a7`, Task 4 `2604509d`, Task 5 `3aea3c7e`, proof
lifecycle assertions `013caf47`, docs this commit. Plan B (measured verdict +
governance integration) intentionally deferred — see "Deliberate deferrals".

---

## Task 1: Scenario pack registry

**Status:** ✅ Done (`59abcfc1`).

**Files:**
- Create: `api/server/world/registry.py`
- Modify: `api/server/world/service.py`
- Modify: `api/server/main.py`
- Test: `tests/api/world/actor/test_world_registry.py`

Add immutable `WorldPackRegistration`:

```python
@dataclass(frozen=True, slots=True)
class WorldPackRegistration:
    name: str
    build_scenario: Callable[[SimulationRuntime], Any]
    default_minutes_per_second: float
    objective_type: str
    allowed_command_types: frozenset[str]
```

Registry contains only:

```text
support → support_capacity → reallocate_workers
telco   → network_service_recovery → reroute_sessions
```

`ActorWorldService.for_world(name, seed, bus, speed=None)` resolves the
registration. Existing `.support()` / `.telco()` remain thin compatibility
wrappers. `main.py` uses `for_world` for support/telco; aggregate `toy` remains
the only legacy branch.

Tests prove unknown world rejects, support/telco configs/actors unchanged, and
both real browser proof scripts still pass after the complete plan.

---

## Task 2: Objective records and deterministic manager

**Status:** ✅ Done (`232c4d20`).

**Files:**
- Modify: `api/server/world/model.py`
- Create: `api/server/world/objectives.py`
- Test: `tests/api/world/actor/test_objectives.py`

Add frozen `Objective`:

```python
Objective(
    id, type, trace_id, owner_function, priority, status,
    created_at, deadline, evidence_event_ids, allowed_command_types,
    claimed_by=None,
)
```

Statuses:

```text
open, claimed, acting, evaluating, resolved, failed, superseded
```

`ObjectiveManager`:

- deterministic ID `obj-{sensor_event_id}`
- dedupe active objectives by `(type, target_id)`
- create from a real sensor event and registration
- transition with explicit allowed-state table
- each transition writes `objective.<status>` into the simulation journal
- expose active/all objectives for snapshot
- no background task, priority queue or agent logic

Tests cover dedupe, invalid transition, causal/trace links and deterministic IDs.

---

## Task 3: Responder registry + objective-driven bridge

**Status:** ✅ Done (`341a90a7`).

**Files:**
- Create: `api/server/services/world_responders.py`
- Modify: `api/server/services/world_bridge.py`
- Modify: `api/server/world/service.py`
- Test: `tests/api/server/services/test_world_bridge_objectives.py`

Static `ResponderRegistration` maps objective type to orchestrator/workflow
type/prefix/owner function/timeout.

Sensor handling:

```text
sensor.tripped
  → objective.opened
  → objective.claimed
  → responder.requested
  → Durable
  → objective.acting
```

Bridge no longer selects responder by scenario branch. It asks the service to
open the scenario registration's objective, resolves the responder by
objective type, and preserves existing responder events.

Duplicate sensor episodes return the existing active objective and schedule no
second Durable orchestration.

---

## Task 4: Command gateway + evaluation foundation

**Status:** ✅ Done (`2604509d`). Gateway is the foundation; measured verdict and
governance integration deferred to Plan B (would require speculative APIs).

**Files:**
- Create: `api/server/world/commands.py`
- Modify: `api/server/world/service.py`
- Modify: `api/server/services/world_bridge.py`
- Modify: `api/server/world/model.py`
- Test: `tests/api/world/actor/test_command_gateway.py`

`CommandGateway.apply(objective, command)`:

- objective status must be `acting`
- command trace must equal objective trace
- command type must be in objective allowed commands
- issuer must equal claimed responder
- rejection emits `command.rejected` and fails objective
- acceptance delegates to scenario `apply_command`
- accepted result transitions objective to `evaluating`

Add frozen `Evaluation` record and `evaluation.started` journal event containing
baseline measurements from the original sensor. Do not claim effectiveness or
change policy yet; completed evaluation waits for the coupled systemic slice.

No duplicate command validation is moved out of scenarios.

---

## Task 5: Snapshot/view compatibility + real proof

**Status:** ✅ Done (view/snapshot `3aea3c7e`; proof lifecycle assertions
`013caf47`; docs this commit).

**Files:**
- Modify: `api/server/world/service.py`
- Modify: `web/client/hooks/useWorldSimulation.ts`
- Modify: `web/client/routes/World.tsx`
- Modify: `web/client/routes/TelcoWorld.tsx`
- Test: existing Python/Vitest/Playwright suites
- Modify: `docs/ARCHITECTURE.md`

Snapshot adds:

```text
objectives: [...]
evaluations: [...]
```

World views show a compact objective state/priority/owner alongside the
existing real responder causal strip. No new page, chart or control.

Verification:

```bash
pytest actor/world/bridge/objective/gateway suites
vitest support/telco world views
vite build
bash tools/actor_world_viewer_proof.sh
bash tools/telco_world_e2e_proof.sh
```

Both proofs must preserve actor IDs, Durable outputs and existing causal chains,
while adding:

```text
objective.opened → objective.claimed → objective.acting → objective.evaluating
```

Update architecture documentation with the objective/command lifecycle.

---

## Deliberate deferrals

- no dynamic plugin discovery
- no self-generated top-level goals
- no priority scheduler beyond deterministic objective fields
- no completed effectiveness verdict
- no learning/policy mutation
- no checkpoints/forks

Those require the coupled network/care/field scenario in Plan B.

