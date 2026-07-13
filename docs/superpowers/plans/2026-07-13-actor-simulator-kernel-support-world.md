# Actor Simulator Kernel + Support World Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic SimPy-backed discrete-event kernel and an explicit-actor support scenario (customers, tickets, workers, queues, service, SLA and abandonment) that produces a causal, replayable journal without changing the currently-proven FastAPI/Durable integration.

**Architecture:** New `model.py`, `runtime.py`, `projection.py` and `packs/support.py` files coexist beside the aggregate spike. `SimulationRuntime` owns SimPy logical time, seeded randomness and the event journal; `SupportScenario` owns typed actors and SimPy processes; projections are derived from actors, never primary state. Plan 2 will migrate the live bridge after this kernel passes its deterministic and scale proof.

**Tech Stack:** Python 3.13, SimPy 4.1.x, stdlib dataclasses/random/json/pathlib, pytest, uv.

**Design spec:** [`docs/superpowers/specs/2026-07-13-observable-actor-simulator-design.md`](../specs/2026-07-13-observable-actor-simulator-design.md)

---

## File structure

| File | Responsibility |
|---|---|
| `api/server/world/model.py` | Generic immutable `SimulationEvent` / `SimulationCommand` records. |
| `api/server/world/runtime.py` | SimPy environment, seeded random source, logical stepping, journal and NDJSON export. No support-domain nouns. |
| `api/server/world/packs/support.py` | Support-specific actor records and processes: arrivals, queueing, assignment, service, SLA, abandonment, demand surge. |
| `api/server/world/projection.py` | Pure derived support metrics and sensor measurements. |
| `tools/support_actor_sim_proof.py` | One-command deterministic actor-simulation proof and journal export. |

Existing `contract.py`, `engine.py`, `packs/toy.py`, `world_bridge.py` and FastAPI wiring remain untouched in Plan 1.

Tests live in `tests/api/world/actor/`.

---

### Task 1: SimPy dependency + event/command records

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `api/server/world/model.py`
- Create: `tests/api/world/actor/__init__.py`
- Create: `tests/api/world/actor/test_model.py`

- [ ] **Step 1: Add SimPy through the repository package manager**

Run:

```bash
uv add --python 3.13 "simpy>=4.1,<5"
```

Expected:

- `pyproject.toml` contains `"simpy>=4.1,<5"`
- `uv.lock` contains a `name = "simpy"` package
- `.venv` contains SimPy

Verify:

```bash
uv run --frozen --no-sync python -c "import simpy; print(simpy.__version__)"
```

Expected: a `4.1.x` version.

- [ ] **Step 2: Write the failing model tests**

Create empty `tests/api/world/actor/__init__.py`.

Create `tests/api/world/actor/test_model.py`:

```python
from dataclasses import FrozenInstanceError

import pytest

from api.server.world.model import SimulationCommand, SimulationEvent


def test_event_serialises_all_causal_fields():
    event = SimulationEvent(
        seq=7,
        event_id="evt-00000007",
        sim_time=12.5,
        type="ticket.queued",
        actor_id="TKT-1",
        target_id="queue:support",
        cause_event_id="evt-00000006",
        trace_id="ticket-TKT-1",
        payload={"severity": "high"},
    )
    assert event.to_dict() == {
        "seq": 7,
        "event_id": "evt-00000007",
        "sim_time": 12.5,
        "type": "ticket.queued",
        "actor_id": "TKT-1",
        "target_id": "queue:support",
        "cause_event_id": "evt-00000006",
        "trace_id": "ticket-TKT-1",
        "payload": {"severity": "high"},
    }


def test_event_and_command_are_frozen():
    event = SimulationEvent(
        seq=1, event_id="evt-00000001", sim_time=0.0, type="simulation.started",
        actor_id=None, target_id=None, cause_event_id=None,
        trace_id="evt-00000001", payload={},
    )
    command = SimulationCommand(
        command_id="cmd-1", trace_id="trace-1", issued_by="staffing",
        type="reallocate_workers", payload={"worker_ids": ["WRK-1"]},
    )
    with pytest.raises(FrozenInstanceError):
        event.type = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        command.type = "changed"  # type: ignore[misc]


def test_command_serialises_to_wire_shape():
    command = SimulationCommand(
        command_id="cmd-1",
        trace_id="trace-1",
        issued_by="surge_staffing",
        type="reallocate_workers",
        payload={"worker_ids": ["WRK-1"], "duration_minutes": 30},
    )
    assert command.to_dict()["type"] == "reallocate_workers"
    assert command.to_dict()["payload"]["duration_minutes"] == 30
```

- [ ] **Step 3: Run tests and verify they fail**

Run:

```bash
uv run --frozen --no-sync pytest tests/api/world/actor/test_model.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'api.server.world.model'`.

- [ ] **Step 4: Implement the model records**

Create `api/server/world/model.py`:

```python
"""Generic wire records shared by simulation scenarios, APIs and replay."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SimulationEvent:
    seq: int
    event_id: str
    sim_time: float
    type: str
    actor_id: str | None
    target_id: str | None
    cause_event_id: str | None
    trace_id: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SimulationCommand:
    command_id: str
    trace_id: str
    issued_by: str
    type: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
```

- [ ] **Step 5: Run tests and verify they pass**

Run:

```bash
uv run --frozen --no-sync pytest tests/api/world/actor/test_model.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock api/server/world/model.py tests/api/world/actor
git commit -m "feat(world): add SimPy and causal simulation records" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>" \
  -m "Copilot-Session: 9c29044c-2d33-401f-8e7c-a453079cf45e"
```

---

### Task 2: Generic deterministic simulation runtime

**Files:**
- Create: `api/server/world/runtime.py`
- Create: `tests/api/world/actor/test_runtime.py`

- [ ] **Step 1: Write the failing runtime tests**

Create `tests/api/world/actor/test_runtime.py`:

```python
import json

from api.server.world.runtime import SimulationRuntime


def _install_clock(runtime: SimulationRuntime) -> None:
    def clock():
        first = runtime.emit("clock.started", actor_id="clock-1", payload={"n": 1})
        yield runtime.env.timeout(5)
        runtime.emit(
            "clock.rang",
            actor_id="clock-1",
            cause_event_id=first.event_id,
            trace_id=first.trace_id,
            payload={"n": 2},
        )

    runtime.process(clock())


def test_step_advances_to_next_event_and_returns_new_journal_entries():
    runtime = SimulationRuntime(seed=7)
    _install_clock(runtime)
    events = runtime.step()
    assert runtime.now == 0.0
    assert [e.type for e in events] == ["clock.started"]
    assert runtime.status == "paused"


def test_run_until_processes_events_in_logical_time_order():
    runtime = SimulationRuntime(seed=7)
    _install_clock(runtime)
    runtime.run_until(5)
    assert [e.type for e in runtime.journal] == ["clock.started", "clock.rang"]
    assert runtime.journal[1].cause_event_id == runtime.journal[0].event_id
    assert runtime.journal[1].sim_time == 5.0


def test_event_ids_and_default_trace_ids_are_deterministic():
    left = SimulationRuntime(seed=1)
    right = SimulationRuntime(seed=1)
    for runtime in (left, right):
        runtime.emit("a")
        runtime.emit("b")
    assert left.canonical_journal() == right.canonical_journal()
    assert left.journal[0].event_id == "evt-00000001"
    assert left.journal[0].trace_id == "evt-00000001"


def test_export_ndjson_round_trips(tmp_path):
    runtime = SimulationRuntime(seed=3)
    runtime.emit("simulation.started", payload={"seed": 3})
    path = runtime.export_ndjson(tmp_path / "journal.ndjson")
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert rows == runtime.canonical_journal()
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run --frozen --no-sync pytest tests/api/world/actor/test_runtime.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'api.server.world.runtime'`.

- [ ] **Step 3: Implement the runtime**

Create `api/server/world/runtime.py`:

```python
"""Generic deterministic SimPy runtime and append-only causal journal."""
from __future__ import annotations

import json
import random
from collections.abc import Generator
from pathlib import Path
from typing import Any

import simpy

from api.server.world.model import SimulationEvent


class SimulationRuntime:
    def __init__(self, seed: int) -> None:
        self.seed = seed
        self.env = simpy.Environment()
        self.rng = random.Random(seed)
        self.journal: list[SimulationEvent] = []
        self.status = "paused"
        self._seq = 0

    @property
    def now(self) -> float:
        return float(self.env.now)

    def process(self, generator: Generator):
        return self.env.process(generator)

    def emit(
        self,
        event_type: str,
        *,
        actor_id: str | None = None,
        target_id: str | None = None,
        cause_event_id: str | None = None,
        trace_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> SimulationEvent:
        self._seq += 1
        event_id = f"evt-{self._seq:08d}"
        event = SimulationEvent(
            seq=self._seq,
            event_id=event_id,
            sim_time=self.now,
            type=event_type,
            actor_id=actor_id,
            target_id=target_id,
            cause_event_id=cause_event_id,
            trace_id=trace_id or event_id,
            payload=dict(payload or {}),
        )
        self.journal.append(event)
        return event

    def step(self) -> list[SimulationEvent]:
        if self.env.peek() == float("inf"):
            self.status = "completed"
            return []
        before = len(self.journal)
        self.status = "running"
        self.env.step()
        if self.env.peek() == float("inf"):
            self.status = "completed"
        else:
            self.status = "paused"
        return self.journal[before:]

    def run_until(self, until: float) -> list[SimulationEvent]:
        if until < self.now:
            raise ValueError(f"cannot run backwards from {self.now} to {until}")
        before = len(self.journal)
        self.status = "running"
        while self.env.peek() <= until:
            self.env.step()
        self.status = "completed" if self.env.peek() == float("inf") else "paused"
        return self.journal[before:]

    def run_events(self, count: int) -> list[SimulationEvent]:
        before = len(self.journal)
        for _ in range(count):
            if self.env.peek() == float("inf"):
                self.status = "completed"
                break
            self.step()
        return self.journal[before:]

    def pause(self) -> None:
        self.status = "paused"

    def canonical_journal(self) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self.journal]

    def export_ndjson(self, path: str | Path) -> Path:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in self.canonical_journal()),
            encoding="utf-8",
        )
        return output
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```bash
uv run --frozen --no-sync pytest tests/api/world/actor/test_runtime.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add api/server/world/runtime.py tests/api/world/actor/test_runtime.py
git commit -m "feat(world): deterministic SimPy runtime and causal journal" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>" \
  -m "Copilot-Session: 9c29044c-2d33-401f-8e7c-a453079cf45e"
```

---

### Task 3: Explicit support actors and processes

**Files:**
- Create: `api/server/world/packs/support.py`
- Create: `tests/api/world/actor/test_support_scenario.py`

- [ ] **Step 1: Write the failing support-scenario tests**

Create `tests/api/world/actor/test_support_scenario.py`:

```python
from api.server.world.packs.support import DemandSurge, SupportConfig, run_support


def _small_config() -> SupportConfig:
    return SupportConfig(
        customer_count=120,
        worker_count=9,
        arrival_rate_per_hour=45,
        simulation_minutes=180,
        sla_minutes=30,
        sensor_backlog_threshold=10_000,  # sensor is Task 4
        sensor_recovery_threshold=5_000,
    )


def test_support_world_contains_real_customers_workers_and_tickets():
    scenario = run_support(seed=11, config=_small_config())
    assert len(scenario.customers) == 120
    assert len(scenario.workers) == 9
    assert len(scenario.tickets) > 0
    assert {e.type for e in scenario.runtime.journal} >= {
        "customer.created", "worker.created", "ticket.arrived", "ticket.queued"
    }


def test_assigned_tickets_match_worker_skills_and_workers_do_not_double_serve():
    scenario = run_support(seed=12, config=_small_config())
    active: dict[str, str] = {}
    for event in scenario.runtime.journal:
        if event.type == "ticket.service_started":
            worker_id = event.payload["worker_id"]
            ticket = scenario.tickets[event.actor_id]
            worker = scenario.workers[worker_id]
            assert ticket.required_skill in worker.skills
            assert worker_id not in active
            active[worker_id] = ticket.id
        elif event.type in {"ticket.resolved", "ticket.abandoned"}:
            worker_id = event.payload.get("worker_id")
            if worker_id:
                active.pop(worker_id, None)


def test_ticket_terminal_states_are_mutually_exclusive():
    scenario = run_support(seed=13, config=_small_config())
    terminal_events: dict[str, list[str]] = {}
    for event in scenario.runtime.journal:
        if event.type in {"ticket.resolved", "ticket.abandoned"}:
            terminal_events.setdefault(event.actor_id, []).append(event.type)
    assert terminal_events
    assert all(len(types) == 1 for types in terminal_events.values())


def test_scheduled_surge_is_a_real_journalled_input():
    surge = DemandSurge(at_minute=30, multiplier=6, duration_minutes=45)
    scenario = run_support(seed=14, config=_small_config(), surges=(surge,))
    events = scenario.runtime.journal
    started = next(e for e in events if e.type == "perturbation.started")
    ended = next(e for e in events if e.type == "perturbation.ended")
    assert started.payload["multiplier"] == 6
    assert ended.cause_event_id == started.event_id
    assert any(
        e.type == "ticket.arrived" and e.payload["arrival_multiplier"] == 6
        for e in events
    )


def test_every_causal_reference_points_to_an_earlier_event():
    scenario = run_support(seed=15, config=_small_config())
    positions = {event.event_id: event.seq for event in scenario.runtime.journal}
    for event in scenario.runtime.journal:
        if event.cause_event_id:
            assert positions[event.cause_event_id] < event.seq
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run --frozen --no-sync pytest tests/api/world/actor/test_support_scenario.py -v
```

Expected: FAIL with `ModuleNotFoundError` for `api.server.world.packs.support`.

- [ ] **Step 3: Implement the support scenario**

Create `api/server/world/packs/support.py`:

```python
"""Explicit-actor support-world scenario running on SimulationRuntime."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

import simpy

from api.server.world.runtime import SimulationRuntime

Skill = Literal["billing", "technical", "account"]
TicketStatus = Literal["queued", "in_service", "resolved", "abandoned"]
SKILLS: tuple[Skill, ...] = ("billing", "technical", "account")


@dataclass(slots=True)
class Customer:
    id: str
    segment: str
    value_band: str
    patience_minutes: float
    sentiment: float = 1.0
    churn_risk: float = 0.0
    active_ticket_ids: set[str] = field(default_factory=set)


@dataclass(slots=True)
class Ticket:
    id: str
    customer_id: str
    severity: str
    required_skill: Skill
    created_at: float
    queued_at: float
    sla_deadline: float
    trace_id: str
    status: TicketStatus = "queued"
    assigned_worker_id: str | None = None
    assigned_at: float | None = None
    resolved_at: float | None = None
    abandoned_at: float | None = None
    sla_breached: bool = False
    last_event_id: str | None = None


@dataclass(slots=True)
class Worker:
    id: str
    team_id: str
    skills: tuple[Skill, ...]
    service_rate: float
    status: str = "idle"
    current_ticket_id: str | None = None
    available_at: float = 0.0


@dataclass(slots=True)
class Team:
    id: str
    name: str
    worker_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class DemandSurge:
    at_minute: float
    multiplier: float
    duration_minutes: float


@dataclass(frozen=True, slots=True)
class SupportConfig:
    customer_count: int = 1_000
    worker_count: int = 40
    arrival_rate_per_hour: float = 60.0
    simulation_minutes: float = 480.0
    sla_minutes: float = 30.0
    sensor_backlog_threshold: int = 25
    sensor_recovery_threshold: int = 10


class SupportScenario:
    def __init__(self, runtime: SimulationRuntime, config: SupportConfig) -> None:
        self.runtime = runtime
        self.config = config
        self.customers: dict[str, Customer] = {}
        self.tickets: dict[str, Ticket] = {}
        self.workers: dict[str, Worker] = {}
        self.teams: dict[str, Team] = {}
        self.queue = simpy.FilterStore(runtime.env)
        self.arrival_multiplier = 1.0
        self._ticket_seq = 0
        self._customer_ids: list[str] = []

    def install(self) -> None:
        self.runtime.emit(
            "simulation.started",
            actor_id="scenario:support",
            payload={"seed": self.runtime.seed, "config": asdict(self.config)},
        )
        self._create_customers()
        self._create_workers()
        for worker in self.workers.values():
            self.runtime.process(self._worker_loop(worker))
        self.runtime.process(self._arrival_loop())

    def schedule_surge(self, surge: DemandSurge) -> None:
        self.runtime.process(self._surge_process(surge))

    def _create_customers(self) -> None:
        patience = {"standard": 60.0, "premium": 90.0, "vulnerable": 30.0}
        values = {"standard": "medium", "premium": "high", "vulnerable": "medium"}
        for index in range(1, self.config.customer_count + 1):
            segment = self.runtime.rng.choices(
                ["standard", "premium", "vulnerable"], weights=[70, 20, 10], k=1
            )[0]
            customer = Customer(
                id=f"CUS-{index:05d}",
                segment=segment,
                value_band=values[segment],
                patience_minutes=patience[segment],
            )
            self.customers[customer.id] = customer
            self._customer_ids.append(customer.id)
            self.runtime.emit(
                "customer.created",
                actor_id=customer.id,
                trace_id=f"customer-{customer.id}",
                payload={"segment": segment, "value_band": customer.value_band},
            )

    def _create_workers(self) -> None:
        team = Team(id="TEAM-SUPPORT", name="Customer Support")
        self.teams[team.id] = team
        for index in range(1, self.config.worker_count + 1):
            primary = SKILLS[(index - 1) % len(SKILLS)]
            skills: tuple[Skill, ...]
            if index % 5 == 0:
                skills = SKILLS
            else:
                skills = (primary,)
            worker = Worker(
                id=f"WRK-{index:04d}",
                team_id=team.id,
                skills=skills,
                service_rate=round(self.runtime.rng.uniform(0.85, 1.15), 3),
            )
            self.workers[worker.id] = worker
            team.worker_ids.append(worker.id)
            self.runtime.emit(
                "worker.created",
                actor_id=worker.id,
                target_id=team.id,
                trace_id=f"worker-{worker.id}",
                payload={"skills": list(worker.skills), "service_rate": worker.service_rate},
            )

    def _arrival_loop(self):
        while self.runtime.now < self.config.simulation_minutes:
            per_minute = (self.config.arrival_rate_per_hour * self.arrival_multiplier) / 60.0
            delay = self.runtime.rng.expovariate(per_minute)
            if self.runtime.now + delay > self.config.simulation_minutes:
                return
            yield self.runtime.env.timeout(delay)
            self._create_ticket()

    def _create_ticket(self) -> None:
        self._ticket_seq += 1
        customer = self.customers[self.runtime.rng.choice(self._customer_ids)]
        severity = self.runtime.rng.choices(
            ["low", "medium", "high"], weights=[55, 35, 10], k=1
        )[0]
        required_skill: Skill = self.runtime.rng.choice(SKILLS)
        ticket = Ticket(
            id=f"TKT-{self._ticket_seq:06d}",
            customer_id=customer.id,
            severity=severity,
            required_skill=required_skill,
            created_at=self.runtime.now,
            queued_at=self.runtime.now,
            sla_deadline=self.runtime.now + self.config.sla_minutes,
            trace_id=f"ticket-TKT-{self._ticket_seq:06d}",
        )
        self.tickets[ticket.id] = ticket
        customer.active_ticket_ids.add(ticket.id)
        arrived = self.runtime.emit(
            "ticket.arrived",
            actor_id=ticket.id,
            target_id=customer.id,
            trace_id=ticket.trace_id,
            payload={
                "customer_id": customer.id,
                "severity": severity,
                "required_skill": required_skill,
                "arrival_multiplier": self.arrival_multiplier,
            },
        )
        queued = self.runtime.emit(
            "ticket.queued",
            actor_id=ticket.id,
            target_id="queue:support",
            cause_event_id=arrived.event_id,
            trace_id=ticket.trace_id,
            payload={"required_skill": required_skill},
        )
        ticket.last_event_id = queued.event_id
        self.queue.put(ticket)
        self.runtime.process(self._sla_watch(ticket))
        self.runtime.process(self._abandon_watch(ticket))

    def _worker_loop(self, worker: Worker):
        while True:
            ticket: Ticket = yield self.queue.get(
                lambda item: item.status == "queued" and item.required_skill in worker.skills
            )
            if ticket.status != "queued":
                continue
            worker.status = "busy"
            worker.current_ticket_id = ticket.id
            ticket.status = "in_service"
            ticket.assigned_worker_id = worker.id
            ticket.assigned_at = self.runtime.now
            assigned = self.runtime.emit(
                "ticket.assigned",
                actor_id=ticket.id,
                target_id=worker.id,
                cause_event_id=ticket.last_event_id,
                trace_id=ticket.trace_id,
                payload={"worker_id": worker.id, "required_skill": ticket.required_skill},
            )
            started = self.runtime.emit(
                "ticket.service_started",
                actor_id=ticket.id,
                target_id=worker.id,
                cause_event_id=assigned.event_id,
                trace_id=ticket.trace_id,
                payload={"worker_id": worker.id},
            )
            ticket.last_event_id = started.event_id
            base_minutes = {"low": 10.0, "medium": 20.0, "high": 35.0}[ticket.severity]
            duration = (base_minutes * self.runtime.rng.uniform(0.8, 1.2)) / worker.service_rate
            worker.available_at = self.runtime.now + duration
            yield self.runtime.env.timeout(duration)
            self._resolve(ticket, worker)

    def _resolve(self, ticket: Ticket, worker: Worker) -> None:
        if ticket.status != "in_service":
            return
        ticket.status = "resolved"
        ticket.resolved_at = self.runtime.now
        customer = self.customers[ticket.customer_id]
        customer.active_ticket_ids.discard(ticket.id)
        customer.sentiment = min(1.0, customer.sentiment + 0.02)
        customer.churn_risk = max(0.0, customer.churn_risk - 0.02)
        resolved = self.runtime.emit(
            "ticket.resolved",
            actor_id=ticket.id,
            target_id=customer.id,
            cause_event_id=ticket.last_event_id,
            trace_id=ticket.trace_id,
            payload={"worker_id": worker.id, "customer_id": customer.id},
        )
        ticket.last_event_id = resolved.event_id
        worker.status = "idle"
        worker.current_ticket_id = None
        worker.available_at = self.runtime.now
        self.runtime.emit(
            "worker.available",
            actor_id=worker.id,
            cause_event_id=resolved.event_id,
            trace_id=ticket.trace_id,
            payload={"ticket_id": ticket.id},
        )

    def _sla_watch(self, ticket: Ticket):
        yield self.runtime.env.timeout(self.config.sla_minutes)
        if ticket.status not in {"queued", "in_service"}:
            return
        ticket.sla_breached = True
        customer = self.customers[ticket.customer_id]
        customer.sentiment = max(0.0, customer.sentiment - 0.15)
        customer.churn_risk = min(1.0, customer.churn_risk + 0.10)
        breached = self.runtime.emit(
            "ticket.sla_breached",
            actor_id=ticket.id,
            target_id=customer.id,
            cause_event_id=ticket.last_event_id,
            trace_id=ticket.trace_id,
            payload={"status": ticket.status, "customer_id": customer.id},
        )
        ticket.last_event_id = breached.event_id

    def _abandon_watch(self, ticket: Ticket):
        customer = self.customers[ticket.customer_id]
        yield self.runtime.env.timeout(customer.patience_minutes)
        if ticket.status != "queued":
            return
        yield self.queue.get(lambda item: item.id == ticket.id)
        ticket.status = "abandoned"
        ticket.abandoned_at = self.runtime.now
        customer.active_ticket_ids.discard(ticket.id)
        customer.sentiment = max(0.0, customer.sentiment - 0.40)
        customer.churn_risk = min(1.0, customer.churn_risk + 0.30)
        abandoned = self.runtime.emit(
            "ticket.abandoned",
            actor_id=ticket.id,
            target_id=customer.id,
            cause_event_id=ticket.last_event_id,
            trace_id=ticket.trace_id,
            payload={"customer_id": customer.id},
        )
        ticket.last_event_id = abandoned.event_id

    def _surge_process(self, surge: DemandSurge):
        if surge.at_minute < self.runtime.now:
            raise ValueError("surge cannot start in the past")
        yield self.runtime.env.timeout(surge.at_minute - self.runtime.now)
        started = self.runtime.emit(
            "perturbation.started",
            actor_id="perturbation:demand_surge",
            target_id="queue:support",
            trace_id=f"surge-{int(surge.at_minute)}",
            payload={
                "multiplier": surge.multiplier,
                "duration_minutes": surge.duration_minutes,
            },
        )
        self.arrival_multiplier *= surge.multiplier
        yield self.runtime.env.timeout(surge.duration_minutes)
        self.arrival_multiplier /= surge.multiplier
        self.runtime.emit(
            "perturbation.ended",
            actor_id="perturbation:demand_surge",
            target_id="queue:support",
            cause_event_id=started.event_id,
            trace_id=started.trace_id,
            payload={"multiplier": surge.multiplier},
        )


def run_support(
    *,
    seed: int,
    config: SupportConfig,
    surges: tuple[DemandSurge, ...] = (),
) -> SupportScenario:
    runtime = SimulationRuntime(seed)
    scenario = SupportScenario(runtime, config)
    scenario.install()
    for surge in surges:
        scenario.schedule_surge(surge)
    runtime.run_until(config.simulation_minutes)
    return scenario
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```bash
uv run --frozen --no-sync pytest tests/api/world/actor/test_support_scenario.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add api/server/world/packs/support.py tests/api/world/actor/test_support_scenario.py
git commit -m "feat(world): explicit support actors and SimPy processes" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>" \
  -m "Copilot-Session: 9c29044c-2d33-401f-8e7c-a453079cf45e"
```

---

### Task 4: Derived projections + pressure sensor

**Files:**
- Create: `api/server/world/projection.py`
- Modify: `api/server/world/packs/support.py`
- Create: `tests/api/world/actor/test_projection_sensor.py`

- [ ] **Step 1: Write the failing projection/sensor tests**

Create `tests/api/world/actor/test_projection_sensor.py`:

```python
from api.server.world.packs.support import SupportConfig, run_support
from api.server.world.projection import project_support


def test_projection_is_derived_from_actor_state():
    scenario = run_support(
        seed=21,
        config=SupportConfig(
            customer_count=100,
            worker_count=6,
            arrival_rate_per_hour=80,
            simulation_minutes=120,
            sensor_backlog_threshold=10_000,
            sensor_recovery_threshold=5_000,
        ),
    )
    projection = project_support(scenario)
    assert projection.support_backlog == sum(
        ticket.status == "queued" for ticket in scenario.tickets.values()
    )
    assert projection.workers_busy == sum(
        worker.status == "busy" for worker in scenario.workers.values()
    )
    assert projection.tickets_opened == len(scenario.tickets)
    assert 0.0 <= projection.sla_breach_pct <= 1.0
    assert 0.0 <= projection.customer_sentiment <= 1.0


def test_overloaded_actor_world_trips_sensor_with_real_ticket_ids():
    scenario = run_support(
        seed=22,
        config=SupportConfig(
            customer_count=200,
            worker_count=3,
            arrival_rate_per_hour=180,
            simulation_minutes=90,
            sensor_backlog_threshold=8,
            sensor_recovery_threshold=3,
        ),
    )
    sensor = next(e for e in scenario.runtime.journal if e.type == "sensor.tripped")
    assert sensor.payload["measurements"]["support_backlog"] >= 8
    assert sensor.payload["actor_ids"]
    assert all(actor_id in scenario.tickets for actor_id in sensor.payload["actor_ids"])
    assert sensor.cause_event_id is not None
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run --frozen --no-sync pytest tests/api/world/actor/test_projection_sensor.py -v
```

Expected: FAIL because `api.server.world.projection` does not exist.

- [ ] **Step 3: Implement the pure projection**

Create `api/server/world/projection.py`:

```python
"""Pure projections derived from explicit support actors."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from api.server.world.packs.support import SupportScenario


@dataclass(frozen=True, slots=True)
class SupportProjection:
    support_backlog: int
    tickets_in_service: int
    tickets_resolved: int
    tickets_abandoned: int
    tickets_opened: int
    workers_idle: int
    workers_busy: int
    sla_breach_pct: float
    average_wait_minutes: float
    customer_sentiment: float
    customer_churn_risk: float


def project_support(scenario: "SupportScenario") -> SupportProjection:
    tickets = list(scenario.tickets.values())
    workers = list(scenario.workers.values())
    customers = list(scenario.customers.values())
    assigned = [ticket for ticket in tickets if ticket.assigned_at is not None]
    waits = [ticket.assigned_at - ticket.queued_at for ticket in assigned]
    opened = len(tickets)
    return SupportProjection(
        support_backlog=sum(ticket.status == "queued" for ticket in tickets),
        tickets_in_service=sum(ticket.status == "in_service" for ticket in tickets),
        tickets_resolved=sum(ticket.status == "resolved" for ticket in tickets),
        tickets_abandoned=sum(ticket.status == "abandoned" for ticket in tickets),
        tickets_opened=opened,
        workers_idle=sum(worker.status == "idle" for worker in workers),
        workers_busy=sum(worker.status == "busy" for worker in workers),
        sla_breach_pct=(
            sum(ticket.sla_breached for ticket in tickets) / opened if opened else 0.0
        ),
        average_wait_minutes=(sum(waits) / len(waits) if waits else 0.0),
        customer_sentiment=(
            sum(customer.sentiment for customer in customers) / len(customers)
            if customers else 0.0
        ),
        customer_churn_risk=(
            sum(customer.churn_risk for customer in customers) / len(customers)
            if customers else 0.0
        ),
    )
```

- [ ] **Step 4: Add the pressure sensor process**

In `SupportScenario.__init__`, add:

```python
        self._sensor_latched = False
```

At the end of `SupportScenario.install`, add:

```python
        self.runtime.process(self._sensor_loop())
```

Add this method to `SupportScenario` before `_surge_process`:

```python
    def _sensor_loop(self):
        from api.server.world.projection import project_support

        while self.runtime.now < self.config.simulation_minutes:
            yield self.runtime.env.timeout(1)
            projection = project_support(self)
            if (
                projection.support_backlog >= self.config.sensor_backlog_threshold
                and not self._sensor_latched
            ):
                queued_ids = [
                    ticket.id
                    for ticket in self.tickets.values()
                    if ticket.status == "queued"
                ][:20]
                cause = next(
                    (
                        event.event_id
                        for event in reversed(self.runtime.journal)
                        if event.type == "ticket.queued"
                    ),
                    None,
                )
                self.runtime.emit(
                    "sensor.tripped",
                    actor_id="sensor:support_pressure",
                    target_id="queue:support",
                    cause_event_id=cause,
                    trace_id=f"support-pressure-{int(self.runtime.now)}",
                    payload={
                        "actor_ids": queued_ids,
                        "measurements": {
                            "support_backlog": projection.support_backlog,
                            "sla_breach_pct": projection.sla_breach_pct,
                            "average_wait_minutes": projection.average_wait_minutes,
                        },
                    },
                )
                self._sensor_latched = True
            elif (
                projection.support_backlog <= self.config.sensor_recovery_threshold
                and self._sensor_latched
            ):
                self.runtime.emit(
                    "sensor.recovered",
                    actor_id="sensor:support_pressure",
                    target_id="queue:support",
                    trace_id=f"support-pressure-recovery-{int(self.runtime.now)}",
                    payload={"support_backlog": projection.support_backlog},
                )
                self._sensor_latched = False
```

- [ ] **Step 5: Run tests and verify they pass**

Run:

```bash
uv run --frozen --no-sync pytest tests/api/world/actor/test_projection_sensor.py -v
```

Expected: 2 passed.

Run the complete actor suite:

```bash
uv run --frozen --no-sync pytest tests/api/world/actor -q
```

Expected: 14 passed.

- [ ] **Step 6: Commit**

```bash
git add api/server/world/projection.py api/server/world/packs/support.py tests/api/world/actor/test_projection_sensor.py
git commit -m "feat(world): derive support metrics and trip actor-backed sensor" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>" \
  -m "Copilot-Session: 9c29044c-2d33-401f-8e7c-a453079cf45e"
```

---

### Task 5: Deterministic scale proof + journal artifact

**Files:**
- Create: `tests/api/world/actor/test_determinism_scale.py`
- Create: `tools/support_actor_sim_proof.py`

- [ ] **Step 1: Write the failing deterministic/scale tests**

Create `tests/api/world/actor/test_determinism_scale.py`:

```python
import json

from api.server.world.packs.support import DemandSurge, SupportConfig, run_support


CONFIG = SupportConfig(
    customer_count=1_000,
    worker_count=40,
    arrival_rate_per_hour=90,
    simulation_minutes=480,
    sla_minutes=30,
    sensor_backlog_threshold=25,
    sensor_recovery_threshold=10,
)
SURGES = (DemandSurge(at_minute=120, multiplier=4, duration_minutes=90),)


def test_same_seed_and_inputs_produce_identical_journal():
    left = run_support(seed=42, config=CONFIG, surges=SURGES)
    right = run_support(seed=42, config=CONFIG, surges=SURGES)
    assert left.runtime.canonical_journal() == right.runtime.canonical_journal()


def test_different_seed_changes_the_world():
    left = run_support(seed=42, config=CONFIG, surges=SURGES)
    right = run_support(seed=43, config=CONFIG, surges=SURGES)
    assert left.runtime.canonical_journal() != right.runtime.canonical_journal()


def test_scale_run_contains_explicit_actors_and_bounded_journal():
    scenario = run_support(seed=42, config=CONFIG, surges=SURGES)
    assert len(scenario.customers) == 1_000
    assert len(scenario.workers) == 40
    assert len(scenario.tickets) >= 500
    assert len(scenario.runtime.journal) < 100_000
    assert any(e.type == "sensor.tripped" for e in scenario.runtime.journal)


def test_exported_journal_matches_canonical_run(tmp_path):
    scenario = run_support(seed=42, config=CONFIG, surges=SURGES)
    path = scenario.runtime.export_ndjson(tmp_path / "support.ndjson")
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert rows == scenario.runtime.canonical_journal()
```

- [ ] **Step 2: Run tests and inspect any real invariant failure**

Run:

```bash
uv run --frozen --no-sync pytest tests/api/world/actor/test_determinism_scale.py -v
```

Expected: 4 passed. If an assertion fails, fix the scenario/runtime invariant;
do not weaken deterministic equality or causal correctness.

- [ ] **Step 3: Add the one-command proof tool**

Create `tools/support_actor_sim_proof.py`:

```python
"""Run and prove the explicit-actor support simulation without FastAPI/Durable."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from api.server.world.packs.support import DemandSurge, SupportConfig, run_support
from api.server.world.projection import project_support


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=Path("tmp/support-actor-proof"))
    args = parser.parse_args()

    config = SupportConfig(
        customer_count=1_000,
        worker_count=40,
        arrival_rate_per_hour=90,
        simulation_minutes=480,
        sla_minutes=30,
        sensor_backlog_threshold=25,
        sensor_recovery_threshold=10,
    )
    surges = (DemandSurge(at_minute=120, multiplier=4, duration_minutes=90),)
    first = run_support(seed=args.seed, config=config, surges=surges)
    replay = run_support(seed=args.seed, config=config, surges=surges)
    deterministic = first.runtime.canonical_journal() == replay.runtime.canonical_journal()
    if not deterministic:
        raise SystemExit("FAIL: identical seed/input produced a different journal")

    args.output.mkdir(parents=True, exist_ok=True)
    journal_path = first.runtime.export_ndjson(args.output / "journal.ndjson")
    projection = project_support(first)
    summary = {
        "seed": args.seed,
        "deterministic_replay": deterministic,
        "customers": len(first.customers),
        "workers": len(first.workers),
        "tickets": len(first.tickets),
        "events": len(first.runtime.journal),
        "sensor_episodes": sum(
            event.type == "sensor.tripped" for event in first.runtime.journal
        ),
        "projection": {
            field: getattr(projection, field)
            for field in projection.__dataclass_fields__
        },
        "journal": str(journal_path),
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the proof**

Run:

```bash
uv run --frozen --no-sync python tools/support_actor_sim_proof.py
```

Expected:

- exit code 0
- JSON includes:
  - `"deterministic_replay": true`
  - `"customers": 1000`
  - `"workers": 40`
  - `"tickets"` greater than 500
  - at least one sensor episode
- `tmp/support-actor-proof/journal.ndjson` exists
- `tmp/support-actor-proof/summary.json` exists

- [ ] **Step 5: Run all Plan 1 verification**

```bash
uv run --frozen --no-sync pytest tests/api/world/actor tests/api/world -q
uv run --frozen --no-sync ruff check \
  api/server/world/model.py \
  api/server/world/runtime.py \
  api/server/world/projection.py \
  api/server/world/packs/support.py \
  tools/support_actor_sim_proof.py
```

Expected:

- actor tests pass
- existing aggregate-spike world tests still pass
- Ruff reports `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add tests/api/world/actor/test_determinism_scale.py tools/support_actor_sim_proof.py
git commit -m "test(world): deterministic 1k-actor support simulation proof" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>" \
  -m "Copilot-Session: 9c29044c-2d33-401f-8e7c-a453079cf45e"
```

---

## Final Plan 1 proof

Plan 1 is complete only when:

1. `uv run --frozen --no-sync pytest tests/api/world/actor tests/api/world -q` passes.
2. The existing FastAPI/Durable spike imports and tests unchanged.
3. `tools/support_actor_sim_proof.py` creates a journal with 1,000 customers,
   40 workers and hundreds of actual tickets.
4. Running the same seed/input twice produces byte-equivalent canonical
   journals.
5. Every `cause_event_id` points to an earlier event.
6. The support metrics are derived from actor state.
7. At least one actor-backed `sensor.tripped` episode occurs.

Do not start Plan 2 until all seven conditions pass.

