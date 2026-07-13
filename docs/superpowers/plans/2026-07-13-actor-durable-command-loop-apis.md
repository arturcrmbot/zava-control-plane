# Actor Durable Command Loop + World APIs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the explicit support actor simulation inside FastAPI, turn actor-backed pressure events into a real Durable staffing decision, validate/apply a typed command that moves actual reserve workers, and expose snapshot/events/SSE/control APIs.

**Architecture:** `ActorWorldService` is the single live actor-world authority for `ZAVA_WORLD=support`; it paces the reviewed SimPy runtime, publishes journal events to the existing EventBus and SSE subscribers, and provides observations/commands. `WorldBridge` remains outside `api/server/world/`, schedules the real Durable responder, and returns its typed command to the service. `ZAVA_WORLD=toy` retains the aggregate spike for regression only.

**Tech Stack:** Python 3.13, SimPy 4.1.2, FastAPI, sse-starlette, Azure Durable Functions, httpx, pytest.

**Design spec:** [`docs/superpowers/specs/2026-07-13-observable-actor-simulator-design.md`](../specs/2026-07-13-observable-actor-simulator-design.md)

---

## File structure

| File | Responsibility |
|---|---|
| `api/server/world/packs/support.py` | Reserve-team actors and typed command validation/application. |
| `api/server/world/service.py` | Live runtime pacing, EventBus/SSE publication, snapshot, observation, controls. |
| `api/functions/workflows/surge_staffing_activities.py` | Deterministic actor-level staffing decision returning `SimulationCommand` wire data. |
| `api/functions/workflows/surge_staffing.py` | Durable orchestration returning command + reasoning. |
| `api/server/services/world_bridge.py` | Sensor → Durable → command application; responder lifecycle journal events. |
| `api/server/routes/world.py` | Snapshot, catch-up events, SSE, control and injection. |
| `api/server/main.py` | Select one authority: actor support service or aggregate toy spike. |
| `tools/actor_world_e2e_proof.py` | Drives/asserts the live proof against already-running services. |
| `tools/actor_world_e2e_proof.sh` | Boots Azurite + Functions + FastAPI, runs driver, tears down. |

---

### Task 1: Typed worker-reallocation commands

**Files:**
- Modify: `api/server/world/packs/support.py`
- Create: `tests/api/world/actor/test_commands.py`

Required model changes:

- Add `reserve_worker_count: int = 0` to `SupportConfig`.
- Add `TEAM-RESERVE`; the last `reserve_worker_count` workers begin there with `status="reserve"`.
- Only support-team workers start queue-consumer processes.
- Keep `worker_processes: dict[str, simpy.Process]` and `applied_commands: dict[str, SimulationEvent]`.
- `apply_command(SimulationCommand) -> SimulationEvent`:
  - duplicate command ID returns the original accepted/rejected event and emits nothing
  - only `reallocate_workers` is accepted
  - validate all workers/from/to/duration before mutating anything
  - accepted command emits `command.accepted`, then one `worker.reallocated` per actual worker
  - reallocated reserve workers join support and start real worker loops
  - after duration, each waits until idle, stops its blocked worker process safely, returns to reserve and emits `worker.returned`
  - rejected commands emit `command.rejected`; state unchanged

Tests in `tests/api/world/actor/test_commands.py` must prove:

```python
from api.server.world.model import SimulationCommand
from api.server.world.packs.support import SupportConfig, SupportScenario
from api.server.world.runtime import SimulationRuntime


def scenario_with_reserve() -> SupportScenario:
    runtime = SimulationRuntime(seed=31)
    scenario = SupportScenario(
        runtime,
        SupportConfig(
            customer_count=50,
            worker_count=12,
            reserve_worker_count=3,
            arrival_rate_per_hour=0.1,
            simulation_minutes=180,
            sensor_backlog_threshold=10_000,
            sensor_recovery_threshold=5_000,
        ),
    )
    scenario.install()
    runtime.run_until(0)
    return scenario


def command(worker_ids=("WRK-0010", "WRK-0011"), command_id="cmd-1"):
    return SimulationCommand(
        command_id=command_id,
        trace_id="trace-1",
        issued_by="surge_staffing",
        type="reallocate_workers",
        payload={
            "worker_ids": list(worker_ids),
            "from_team_id": "TEAM-RESERVE",
            "to_team_id": "TEAM-SUPPORT",
            "duration_minutes": 30,
        },
    )


def test_valid_command_moves_actual_workers_and_journals_each_move():
    scenario = scenario_with_reserve()
    result = scenario.apply_command(command())
    assert result.type == "command.accepted"
    assert scenario.workers["WRK-0010"].team_id == "TEAM-SUPPORT"
    assert scenario.workers["WRK-0010"].status == "idle"
    moved = [e.actor_id for e in scenario.runtime.journal if e.type == "worker.reallocated"]
    assert moved == ["WRK-0010", "WRK-0011"]


def test_invalid_command_is_all_or_nothing():
    scenario = scenario_with_reserve()
    result = scenario.apply_command(command(("WRK-0010", "MISSING")))
    assert result.type == "command.rejected"
    assert scenario.workers["WRK-0010"].team_id == "TEAM-RESERVE"
    assert not any(e.type == "worker.reallocated" for e in scenario.runtime.journal)


def test_duplicate_command_is_idempotent():
    scenario = scenario_with_reserve()
    first = scenario.apply_command(command())
    count = len(scenario.runtime.journal)
    second = scenario.apply_command(command())
    assert second.event_id == first.event_id
    assert len(scenario.runtime.journal) == count


def test_workers_return_to_reserve_after_duration():
    scenario = scenario_with_reserve()
    accepted = scenario.apply_command(command(("WRK-0010",)))
    scenario.runtime.run_until(31)
    worker = scenario.workers["WRK-0010"]
    assert worker.team_id == "TEAM-RESERVE"
    assert worker.status == "reserve"
    returned = next(e for e in scenario.runtime.journal if e.type == "worker.returned")
    assert returned.cause_event_id in {
        e.event_id for e in scenario.runtime.journal if e.type == "worker.reallocated"
    }
    assert accepted.trace_id == returned.trace_id
```

Implementation must keep existing Plan 1 journals unchanged when
`reserve_worker_count=0`.

Run:

```bash
uv run --frozen --no-sync pytest tests/api/world/actor/test_commands.py -v
uv run --frozen --no-sync pytest tests/api/world/actor -q
uv run --frozen --no-sync ruff check api/server/world/packs/support.py tests/api/world/actor/test_commands.py
```

Commit:

```bash
git add api/server/world/packs/support.py tests/api/world/actor/test_commands.py
git commit -m "feat(world): apply typed commands to real workers" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>" \
  -m "Copilot-Session: 9c29044c-2d33-401f-8e7c-a453079cf45e"
```

---

### Task 2: Live actor-world service

**Files:**
- Create: `api/server/world/service.py`
- Create: `tests/api/world/actor/test_service.py`

`ActorWorldService` owns one `SimulationRuntime` + `SupportScenario` and:

- installs the scenario with a support config
- paces one SimPy event at a time in an asyncio task
- `minutes_per_second` changes wall pacing only
- `pause`, `resume`, `step_once`, `stop`
- `inject_demand_surge(multiplier, duration_minutes)` at current logical time
- `events_after(seq)` catch-up
- bounded subscriber queues for live events
- publishes each event to subscribers and `EventBus` as
  `FleetEvent(type=f"world.{event.type}", simulation_event=event.to_dict())`
- `snapshot()` returns logical status, sequence, projection, customers, tickets,
  workers and teams (dataclass wire dictionaries)
- `build_observation(sensor_event)` returns queued ticket details, support and
  reserve worker details, projection, allowed command vocabulary and trace ID
- `apply_command(command)` applies scenario command and immediately publishes
  every newly journalled event
- `record_external(...)` journals/publishes responder lifecycle events

Factory defaults for the live support proof:

```python
SupportConfig(
    customer_count=1_000,
    worker_count=40,
    reserve_worker_count=10,
    arrival_rate_per_hour=90,
    simulation_minutes=480,
    sla_minutes=30,
    sensor_backlog_threshold=25,
    sensor_recovery_threshold=10,
)
```

Tests must prove:

```python
import asyncio

import pytest

from api.server.services.event_bus import EventBus
from api.server.world.model import SimulationCommand
from api.server.world.service import ActorWorldService


def service() -> ActorWorldService:
    return ActorWorldService.support(seed=42, bus=EventBus(), minutes_per_second=1000)


def test_snapshot_contains_actual_actor_state_and_projection():
    world = service()
    snapshot = world.snapshot()
    assert snapshot["scenario"] == "support"
    assert len(snapshot["customers"]) == 1_000
    assert len(snapshot["workers"]) == 40
    assert snapshot["projection"]["tickets_opened"] == 0
    assert snapshot["latest_seq"] == len(world.runtime.journal)


def test_events_after_returns_causal_journal_tail():
    world = service()
    tail = world.events_after(1_030)
    assert tail
    assert all(event["seq"] > 1_030 for event in tail)


def test_apply_command_publishes_command_and_worker_events():
    world = service()
    queue = world.subscribe()
    command = SimulationCommand(
        command_id="cmd-test",
        trace_id="trace-test",
        issued_by="test",
        type="reallocate_workers",
        payload={
            "worker_ids": ["WRK-0031"],
            "from_team_id": "TEAM-RESERVE",
            "to_team_id": "TEAM-SUPPORT",
            "duration_minutes": 30,
        },
    )
    result = world.apply_command(command)
    assert result.type == "command.accepted"
    published = [queue.get_nowait(), queue.get_nowait()]
    assert [e["type"] for e in published] == ["command.accepted", "worker.reallocated"]


@pytest.mark.asyncio
async def test_pause_step_resume_control_authoritative_runtime():
    world = service()
    world.pause()
    before = world.runtime.now
    await world.step_once()
    assert world.runtime.now >= before
    world.resume()
    task = asyncio.create_task(world.run())
    await asyncio.sleep(0.02)
    world.stop()
    await task
    assert world.runtime.now > before
```

The service must not publish the installation backlog of
`customer.created`/`worker.created` events to the EventBus on startup; they are
available via snapshot/catch-up. It begins live publication from the journal
sequence after installation.

Run:

```bash
uv run --frozen --no-sync pytest tests/api/world/actor/test_service.py -v
uv run --frozen --no-sync ruff check api/server/world/service.py
```

Commit:

```bash
git add api/server/world/service.py tests/api/world/actor/test_service.py
git commit -m "feat(world): run actor simulation as a live service" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>" \
  -m "Copilot-Session: 9c29044c-2d33-401f-8e7c-a453079cf45e"
```

---

### Task 3: Durable responder returns a typed actor command

**Files:**
- Modify: `api/functions/workflows/surge_staffing_activities.py`
- Modify: `api/functions/workflows/surge_staffing.py`
- Modify: `tests/api/functions/workflows/test_surge_staffing_activity.py`

Replace aggregate hiring output with actor-level command selection.

Input:

```json
{
  "trace_id": "support-pressure-42",
  "observation": {
    "queued_tickets": [{"id":"TKT-1","required_skill":"technical", ...}],
    "support_workers": [...],
    "reserve_workers": [{"id":"WRK-31","skills":["technical"]}, ...],
    "projection": {...},
    "allowed_commands": ["reallocate_workers"]
  }
}
```

Decision algorithm:

1. Count queued tickets by required skill.
2. Score each reserve worker by the sum of queued demand for its skills.
3. Sort by descending score, then worker ID.
4. Select `min(reserve_count, max(1, ceil(backlog / 20)))`.
5. Return:

```python
{
    "command": {
        "command_id": f"cmd-{trace_id}-staff",
        "trace_id": trace_id,
        "issued_by": "surge_staffing",
        "type": "reallocate_workers",
        "payload": {
            "worker_ids": [...],
            "from_team_id": "TEAM-RESERVE",
            "to_team_id": "TEAM-SUPPORT",
            "duration_minutes": 60,
        },
    },
    "reasoning": "...",
}
```

If no queued tickets or no reserve workers, return `command=None` and an
explicit reason.

Tests must cover skill-based ordering, backlog scaling, and safe no-op.
Update orchestration output to include `observation`, `command`, `reasoning`,
`status`, and `instance_id`.

Replace `tests/api/functions/workflows/test_surge_staffing_activity.py` with:

```python
from api.functions.workflows.surge_staffing_activities import (
    surge_staffing_decide_activity,
)


def observation(*, technical=30, billing=10, account=0, reserve=True):
    tickets = [
        {"id": f"TKT-T-{i}", "required_skill": "technical"}
        for i in range(technical)
    ]
    tickets += [
        {"id": f"TKT-B-{i}", "required_skill": "billing"}
        for i in range(billing)
    ]
    tickets += [
        {"id": f"TKT-A-{i}", "required_skill": "account"}
        for i in range(account)
    ]
    workers = (
        [
            {"id": "WRK-0031", "skills": ["billing"]},
            {"id": "WRK-0032", "skills": ["technical"]},
            {"id": "WRK-0033", "skills": ["technical", "account"]},
            {"id": "WRK-0034", "skills": ["account"]},
        ]
        if reserve else []
    )
    return {
        "trace_id": "support-pressure-42",
        "observation": {
            "queued_tickets": tickets,
            "support_workers": [],
            "reserve_workers": workers,
            "projection": {"support_backlog": len(tickets)},
            "allowed_commands": ["reallocate_workers"],
        },
    }


def test_selects_workers_covering_the_highest_skill_pressure():
    out = surge_staffing_decide_activity(observation())
    command = out["command"]
    assert command["payload"]["worker_ids"] == ["WRK-0032", "WRK-0033"]
    assert command["type"] == "reallocate_workers"
    assert command["trace_id"] == "support-pressure-42"


def test_selected_worker_count_scales_with_backlog():
    small = surge_staffing_decide_activity(observation(technical=5, billing=0))
    large = surge_staffing_decide_activity(observation(technical=65, billing=0))
    assert len(small["command"]["payload"]["worker_ids"]) == 1
    assert len(large["command"]["payload"]["worker_ids"]) == 4


def test_no_queue_or_no_reserve_returns_explicit_noop():
    empty = surge_staffing_decide_activity(
        observation(technical=0, billing=0, account=0)
    )
    no_reserve = surge_staffing_decide_activity(observation(reserve=False))
    assert empty["command"] is None
    assert "no queued tickets" in empty["reasoning"]
    assert no_reserve["command"] is None
    assert "no reserve workers" in no_reserve["reasoning"]
```

Implementation core:

```python
def surge_staffing_decide_activity(payload: dict) -> dict:
    import math
    from collections import Counter

    trace_id = str(payload.get("trace_id") or "unknown")
    observation = payload.get("observation") or {}
    queued = observation.get("queued_tickets") or []
    reserve = observation.get("reserve_workers") or []
    if not queued:
        return {"command": None, "reasoning": "no queued tickets"}
    if not reserve:
        return {"command": None, "reasoning": "no reserve workers"}

    pressure = Counter(ticket.get("required_skill") for ticket in queued)
    ranked = sorted(
        reserve,
        key=lambda worker: (
            -sum(pressure.get(skill, 0) for skill in worker.get("skills", [])),
            worker["id"],
        ),
    )
    count = min(len(ranked), max(1, math.ceil(len(queued) / 20)))
    worker_ids = [worker["id"] for worker in ranked[:count]]
    return {
        "command": {
            "command_id": f"cmd-{trace_id}-staff",
            "trace_id": trace_id,
            "issued_by": "surge_staffing",
            "type": "reallocate_workers",
            "payload": {
                "worker_ids": worker_ids,
                "from_team_id": "TEAM-RESERVE",
                "to_team_id": "TEAM-SUPPORT",
                "duration_minutes": 60,
            },
        },
        "reasoning": (
            f"backlog={len(queued)}; selected {len(worker_ids)} reserve workers "
            f"against skill pressure {dict(pressure)}"
        ),
    }
```

Run:

```bash
uv run --frozen --no-sync pytest tests/api/functions/workflows/test_surge_staffing_activity.py -v
uv run --frozen --no-sync python -m py_compile \
  api/functions/workflows/surge_staffing.py \
  api/functions/workflows/surge_staffing_activities.py \
  function_app.py
```

Commit:

```bash
git add api/functions/workflows/surge_staffing.py \
  api/functions/workflows/surge_staffing_activities.py \
  tests/api/functions/workflows/test_surge_staffing_activity.py
git commit -m "feat(world): make Durable responder issue typed worker commands" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>" \
  -m "Copilot-Session: 9c29044c-2d33-401f-8e7c-a453079cf45e"
```

---

### Task 4: Migrate the world bridge to actor observations and commands

**Files:**
- Modify: `api/server/services/world_bridge.py`
- Create: `tests/api/server/services/test_world_bridge_actor.py`

Required behavior:

- Listen to `world.sensor.tripped`.
- Extract the nested `simulation_event`.
- Ask `app_state.world_service.build_observation(...)`.
- Journal/publish `responder.requested` before scheduling.
- Schedule `SurgeStaffingOrchestrator` with trace ID + observation.
- On completion, journal/publish `responder.decided`.
- Parse `SimulationCommand(**output["command"])`.
- Apply through `world_service.apply_command`.
- Store `world_last_response` with Durable instance, observation, output,
  command and result event.
- No command: journal `responder.deferred`; state unchanged.
- failure/timeout: journal `responder.failed`; simulation continues.
- Guard one in-flight response per sensor trace (not one global boolean).

Tests use a fake world service and monkeypatched Durable scheduler/status:

- sensor creates actor observation and scheduling payload
- returned command is applied exactly once
- no-command response defers without mutation
- failure records responder.failed
- duplicate same trace does not schedule twice

Create `tests/api/server/services/test_world_bridge_actor.py`:

```python
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from api.server.services.event_bus import EventBus
from api.server.services.world_bridge import WorldBridge
from api.shared.events import FleetEvent


class FakeWorld:
    def __init__(self):
        self.applied = []
        self.recorded = []

    def build_observation(self, event):
        return {
            "trace_id": event["trace_id"],
            "queued_tickets": [{"id": "TKT-1", "required_skill": "technical"}],
            "reserve_workers": [{"id": "WRK-31", "skills": ["technical"]}],
        }

    def record_external(self, event_type, **kwargs):
        event = SimpleNamespace(
            event_id=f"evt-{len(self.recorded)+1}",
            trace_id=kwargs["trace_id"],
            type=event_type,
        )
        self.recorded.append((event_type, kwargs))
        return event

    def apply_command(self, command):
        self.applied.append(command)
        return SimpleNamespace(event_id="evt-command", type="command.accepted")


def app_state():
    return SimpleNamespace(
        bus=EventBus(), world_service=FakeWorld(), world_last_response=None
    )


def sensor(trace="trace-1"):
    return FleetEvent(
        type="world.sensor.tripped",
        simulation_event={
            "event_id": "evt-sensor",
            "trace_id": trace,
            "type": "sensor.tripped",
            "payload": {"actor_ids": ["TKT-1"]},
        },
    )


@pytest.mark.asyncio
async def test_sensor_schedules_actor_observation_and_applies_typed_command(monkeypatch):
    state = app_state()
    bridge = WorldBridge(state)
    schedule = AsyncMock(
        return_value={"id": "durable-1", "statusQueryGetUri": "status://1"}
    )
    monkeypatch.setattr(
        "api.server.services.world_bridge.schedule_new_orchestration", schedule
    )
    bridge._await_output = AsyncMock(return_value={
        "command": {
            "command_id": "cmd-1",
            "trace_id": "trace-1",
            "issued_by": "surge_staffing",
            "type": "reallocate_workers",
            "payload": {
                "worker_ids": ["WRK-31"],
                "from_team_id": "TEAM-RESERVE",
                "to_team_id": "TEAM-SUPPORT",
                "duration_minutes": 60,
            },
        },
        "reasoning": "move technical worker",
    })
    bridge.start()
    state.bus.emit(sensor())
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert schedule.await_count == 1
    assert schedule.await_args.args[0]["observation"]["queued_tickets"][0]["id"] == "TKT-1"
    assert state.world_service.applied[0].command_id == "cmd-1"
    assert [kind for kind, _ in state.world_service.recorded] == [
        "responder.requested", "responder.decided"
    ]


@pytest.mark.asyncio
async def test_no_command_records_deferred_without_mutation(monkeypatch):
    state = app_state()
    bridge = WorldBridge(state)
    monkeypatch.setattr(
        "api.server.services.world_bridge.schedule_new_orchestration",
        AsyncMock(return_value={"id": "durable-1", "statusQueryGetUri": "status://1"}),
    )
    bridge._await_output = AsyncMock(
        return_value={"command": None, "reasoning": "no reserve workers"}
    )
    bridge.start()
    state.bus.emit(sensor())
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert state.world_service.applied == []
    assert state.world_service.recorded[-1][0] == "responder.deferred"


@pytest.mark.asyncio
async def test_duplicate_trace_is_scheduled_once_while_in_flight(monkeypatch):
    state = app_state()
    bridge = WorldBridge(state)
    gate = asyncio.Event()

    async def schedule(*args):
        await gate.wait()
        return {"id": "durable-1", "statusQueryGetUri": "status://1"}

    scheduled = AsyncMock(side_effect=schedule)
    monkeypatch.setattr(
        "api.server.services.world_bridge.schedule_new_orchestration", scheduled
    )
    bridge.start()
    state.bus.emit(sensor())
    state.bus.emit(sensor())
    await asyncio.sleep(0)
    assert scheduled.await_count == 1
    gate.set()
```

Run:

```bash
uv run --frozen --no-sync pytest tests/api/server/services/test_world_bridge_actor.py -v
uv run --frozen --no-sync ruff check api/server/services/world_bridge.py
```

Commit:

```bash
git add api/server/services/world_bridge.py tests/api/server/services/test_world_bridge_actor.py
git commit -m "feat(world): bridge actor sensors to Durable commands" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>" \
  -m "Copilot-Session: 9c29044c-2d33-401f-8e7c-a453079cf45e"
```

---

### Task 5: Actor world APIs + lifecycle migration

**Files:**
- Modify: `api/server/routes/world.py`
- Modify: `api/server/main.py`
- Create: `tests/api/routes/test_world_actor_routes.py`

API contract:

```text
GET  /api/world/state
GET  /api/world/events?after=<seq>
GET  /api/world/stream?after=<seq>       SSE, event id = journal seq
POST /api/world/control                 {action: pause|resume|step|speed|restart, value?}
POST /api/world/inject/demand_surge     {multiplier: 4, duration_minutes: 90}
```

Routes operate on `app_state.world_service` when present. `state` may retain
the old aggregate fallback for `ZAVA_WORLD=toy`.

SSE:

- first yields catch-up events after `after`
- then subscribes to service queue
- `{"event":"world","id":str(seq),"data":json.dumps(event)}`
- heartbeat every 15 seconds
- unsubscribe on disconnect

Lifecycle:

```python
if ZAVA_WORLD == "support":
    service = ActorWorldService.support(
        seed=int(os.getenv("WORLD_SEED", "42")),
        bus=app_state.bus,
        minutes_per_second=float(os.getenv("WORLD_MINUTES_PER_SECOND", "10")),
    )
    app_state.world_service = service
    world_task = asyncio.create_task(service.run())
elif ZAVA_WORLD:
    # existing aggregate maybe_start_world path, for toy only
```

Arm `WorldBridge` only for the support service. Stop bridge and cancel task on
shutdown. Never start both actor and aggregate authorities.

Route tests with fake service must cover snapshot, events, pause/step/speed,
surge injection and disabled state. SSE framing gets a focused generator test.

Create `tests/api/routes/test_world_actor_routes.py` with a small FastAPI app
including only `world.router`. Its fake service must implement
`snapshot/events_after/pause/resume/step_once/set_speed/restart/
inject_demand_surge/subscribe/unsubscribe`.

Required assertions:

```python
def test_state_and_event_catchup(monkeypatch):
    fake = FakeWorldService()
    monkeypatch.setattr(app_state, "world_service", fake, raising=False)
    assert client.get("/api/world/state").json()["scenario"] == "support"
    body = client.get("/api/world/events?after=7").json()
    assert body["events"][0]["seq"] == 8
    assert fake.after == 7


def test_controls_call_authoritative_service(monkeypatch):
    fake = FakeWorldService()
    monkeypatch.setattr(app_state, "world_service", fake, raising=False)
    assert client.post("/api/world/control", json={"action": "pause"}).status_code == 200
    assert client.post("/api/world/control", json={"action": "step"}).status_code == 200
    assert client.post(
        "/api/world/control", json={"action": "speed", "value": 25}
    ).status_code == 200
    assert fake.calls == [("pause", None), ("step", None), ("speed", 25)]


def test_demand_surge_injection_is_typed(monkeypatch):
    fake = FakeWorldService()
    monkeypatch.setattr(app_state, "world_service", fake, raising=False)
    response = client.post(
        "/api/world/inject/demand_surge",
        json={"multiplier": 4, "duration_minutes": 90},
    )
    assert response.status_code == 200
    assert fake.calls[-1] == ("inject", (4, 90))


@pytest.mark.asyncio
async def test_stream_generator_frames_catchup_with_sequence_id():
    fake = FakeWorldService()
    request = FakeDisconnectingRequest()
    generator = _stream_events(fake, request, after=7)
    item = await anext(generator)
    assert item == {
        "event": "world",
        "id": "8",
        "data": json.dumps(fake.events[0]),
    }
```

`ControlRequest` and `DemandSurgeRequest` are Pydantic models. Invalid action,
non-positive speed, multiplier ≤ 1, or non-positive duration returns HTTP 422.

Run:

```bash
uv run --frozen --no-sync pytest tests/api/routes/test_world_actor_routes.py -v
uv run --frozen --no-sync pytest tests/api/world tests/api/functions/workflows/test_surge_staffing_activity.py -q
uv run --frozen --no-sync python -c "import api.server.main"
```

Commit:

```bash
git add api/server/routes/world.py api/server/main.py tests/api/routes/test_world_actor_routes.py
git commit -m "feat(world): expose live actor state, events, SSE and controls" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>" \
  -m "Copilot-Session: 9c29044c-2d33-401f-8e7c-a453079cf45e"
```

---

### Task 6: Real actor → Durable → worker command proof

**Files:**
- Create: `tools/actor_world_e2e_proof.py`
- Create: `tools/actor_world_e2e_proof.sh`
- Test: real local stack

Driver behavior:

1. Read baseline `/api/world/state`; capture reserve/support worker IDs.
2. POST demand surge.
3. Poll `/api/world/events` until:
   - `sensor.tripped`
   - `responder.requested`
   - `responder.decided`
   - `command.accepted`
   - one or more `worker.reallocated`
4. Assert reallocated actor IDs were previously reserve workers and now have
   `team_id=TEAM-SUPPORT`.
5. Assert later `ticket.resolved` events are causally after the command.
6. Read `last_response` Durable instance ID and query :7071 directly; require
   `runtimeStatus=Completed`, actor-level observation input and typed command
   output.
7. Save:
   - baseline/final snapshots
   - event journal tail
   - Durable instance JSON
   - summary JSON

`tools/actor_world_e2e_proof.py` must be an executable assertion driver, not a
print-only demo. It exits non-zero unless:

```python
required_types = {
    "sensor.tripped",
    "responder.requested",
    "responder.decided",
    "command.accepted",
    "worker.reallocated",
}
assert required_types <= {event["type"] for event in events}
assert set(reallocated_ids) <= baseline_reserve_ids
assert set(reallocated_ids) <= final_support_ids
assert durable["runtimeStatus"] == "Completed"
assert durable["output"]["command"]["type"] == "reallocate_workers"
assert durable["output"]["command"]["payload"]["worker_ids"] == reallocated_ids
assert any(
    event["type"] == "ticket.resolved"
    and event["seq"] > command_accepted_seq
    for event in events
)
```

Use `httpx.Client`, a bounded polling deadline, and write every evidence file
before printing one JSON summary.

Shell script boots fresh Azurite, Functions host and
`ZAVA_WORLD=support WORLD_MINUTES_PER_SECOND=10` FastAPI, runs the driver and
tears all PIDs down.

Final verification:

```bash
uv run --frozen --no-sync pytest \
  tests/api/world/actor \
  tests/api/world \
  tests/api/functions/workflows/test_surge_staffing_activity.py \
  tests/api/server/services/test_world_bridge_actor.py \
  tests/api/routes/test_world_actor_routes.py -q

uv run --frozen --no-sync ruff check \
  api/server/world \
  api/server/services/world_bridge.py \
  api/server/routes/world.py \
  api/functions/workflows/surge_staffing.py \
  api/functions/workflows/surge_staffing_activities.py \
  tools/actor_world_e2e_proof.py

bash tools/actor_world_e2e_proof.sh
```

Commit:

```bash
git add tools/actor_world_e2e_proof.py tools/actor_world_e2e_proof.sh
git commit -m "test(world): prove actor-level Durable command loop end to end" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>" \
  -m "Copilot-Session: 9c29044c-2d33-401f-8e7c-a453079cf45e"
```

Plan 2 is complete only when the real Durable output moves actual worker IDs,
those actor changes are journalled and visible through the APIs, and later
ticket events show the changed world behavior.
