# World Simulator — Engine Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the generic, industry-agnostic world-simulator engine (spec milestones 1–3) — a tick-driven stock-and-flow loop with manual perturbations, sensors, and actuators — proven end-to-end over the real EventBus with a neutral toy pack, wired into the FastAPI lifespan behind a `ZAVA_WORLD` flag, and off by default.

**Architecture:** A small `api/server/world/` package. `contract.py` holds seven frozen dataclasses (Stock, Flow, Signal, Resource, Perturbation, Sensor, Actuator) grouped into a `WorldPack`; expression fields (rates, formulas, conditions, effects) are **plain Python callables**, because packs are Python modules — no string-eval, no sandbox. One cohesive `engine.py` holds `WorldState` + `WorldEngine`: each tick it resets inputs to baseline, applies active perturbations, integrates flows into stocks, recomputes signals, evaluates sensors (emitting bus events on a rising edge), and publishes a `world.tick`. Actuators are bus subscribers that feed responder-completion outcomes back into state. Couples to the rest of Zava only through the existing `EventBus`.

**Tech Stack:** Python 3.13 (FastAPI process), pytest (`uv run pytest`, asyncio_mode=auto), Pydantic v2 `FleetEvent`, stdlib `asyncio`/`importlib`/`os`. No new dependencies. No `compile`/`eval`.

**Spec:** [`docs/superpowers/specs/2026-07-10-organisational-world-simulator-design.md`](../specs/2026-07-10-organisational-world-simulator-design.md) (milestones 1–3, §11).

**Note on commits:** each commit appends the repo's Co-authored-by trailer via a second `-m`. Keep it.

---

## File Structure

Five Python files (one is a trivial package marker):

| File | Responsibility |
|---|---|
| `api/server/world/contract.py` | Seven primitive dataclasses + `WorldPack`. Data only; expression fields are callables. |
| `api/server/world/engine.py` | `WorldState` (mutable state + `w["name"]` accessor + clamped `add`) and `WorldEngine` (`tick`, perturbations, sensors, actuators, `run`/`stop`). |
| `api/server/world/__init__.py` | `active_world_name()`, `load_pack()`, `maybe_start_world()` — the lifespan entry point. |
| `api/server/world/packs/__init__.py` | Package marker (one line). |
| `api/server/world/packs/toy.py` | Neutral support-queue pack exposing `PACK: WorldPack`. |

Modified: `api/server/main.py` (start/stop the engine in the lifespan behind the flag).
Tests: `tests/api/world/test_engine.py` (units + closed-loop e2e), `tests/api/world/test_wiring.py` (flag + lifespan entry).

**Why one `engine.py` and not a module-per-concern:** the integrator, signal pass, sensor check, and perturbation step are each ~10 lines and share the engine's per-tick state. Splitting them into separate files/classes would be ceremony; the cohesive unit is "advance the world." `contract.py` stays separate because it's the genuinely-reusable data the packs import.

---

## Task 1: The contract — seven primitives (`contract.py`)

**Files:**
- Create: `api/server/world/__init__.py` (temporary stub; finalised in Task 4)
- Create: `api/server/world/contract.py`
- Test: `tests/api/world/__init__.py`, `tests/api/world/test_contract.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/world/__init__.py` (empty). Then `tests/api/world/test_contract.py`:

```python
from api.server.world.contract import (
    Stock, Flow, Signal, Resource, Perturbation, Sensor, Actuator, WorldPack,
)


def test_primitives_construct_with_expected_defaults():
    assert Stock("backlog").min == 0.0 and Stock("backlog").max is None
    assert Flow(into="backlog", rate=lambda w: 1.0).out_of is None
    assert Signal("sla", lambda w: 0.5).formula(None) == 0.5
    assert Resource("agents", capacity=20.0).capacity == 20.0
    assert Perturbation("surge", target="arrival", magnitude=60.0).duration_ticks == 1
    assert Sensor("hot", when=lambda w: True, emit="ops.x").emit == "ops.x"
    assert Actuator("hire", on="x.done", target="agents",
                    effect=lambda ev: ev["hired"]).effect({"hired": 3}) == 3


def test_worldpack_groups_declarations_with_empty_defaults():
    pack = WorldPack(
        name="t",
        stocks=(Stock("backlog"),),
        inputs={"arrival": 30.0},
        constants={"HANDLE": 2.0},
    )
    assert pack.name == "t"
    assert pack.stocks[0].name == "backlog"
    assert pack.inputs["arrival"] == 30.0
    assert pack.flows == () and pack.sensors == ()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/world/test_contract.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.server.world'`.

- [ ] **Step 3: Write minimal implementation**

Create `api/server/world/__init__.py` (temporary stub — Task 4 replaces it):

```python
"""Generic organisational world-simulator engine (spec 2026-07-10)."""
```

Create `api/server/world/contract.py`:

```python
"""The narrow waist: seven primitive types every world pack conforms to.

Data only — no behaviour. Expression-bearing fields (Flow.rate, Signal.formula,
Sensor.when, Actuator.effect) are plain Python callables the pack supplies,
because packs are authored as Python modules (see packs/toy.py). No string
eval, no sandbox: the pack author writes Python either way.

  rate/formula:  (world) -> float     # `world` supports world["name"] lookups
  when:          (world) -> bool
  effect:        (event_payload: dict) -> float
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class Stock:
    """A level that fills/drains. `min`/`max` clamp it (None = unbounded)."""
    name: str
    initial: float = 0.0
    min: float | None = 0.0
    max: float | None = None


@dataclass(frozen=True)
class Flow:
    """Moves `rate(world)` units/hour into `into` (drains `out_of` if set)."""
    into: str
    rate: Callable
    out_of: str | None = None


@dataclass(frozen=True)
class Signal:
    """A derived readout: `formula(world) -> float`."""
    name: str
    formula: Callable


@dataclass(frozen=True)
class Resource:
    """A finite pool functions contend for."""
    name: str
    capacity: float


@dataclass(frozen=True)
class Perturbation:
    """An exogenous kick: while active, adds `magnitude` to inputs[target].

    Manual injection only for the engine core (engine.inject(name)).
    ponytail: poisson/cron schedules land with the telco pack (M4), where
    random faults matter — ~3 lines + a `schedule` field then.
    """
    name: str
    target: str
    magnitude: float
    duration_ticks: int = 1


@dataclass(frozen=True)
class Sensor:
    """when `when(world)` rises true, emit bus event `emit`.

    ponytail: cooldown added with M4 when signals get noisy; the rising-edge
    latch alone suffices for the deterministic core.
    """
    name: str
    when: Callable
    emit: str


@dataclass(frozen=True)
class Actuator:
    """On bus event `on`, add `effect(event_payload)` to stock/resource `target`."""
    name: str
    on: str
    target: str
    effect: Callable


@dataclass(frozen=True)
class WorldPack:
    """A complete world declaration (the 'world half' of an industry pack)."""
    name: str
    stocks: tuple[Stock, ...] = ()
    flows: tuple[Flow, ...] = ()
    signals: tuple[Signal, ...] = ()
    resources: tuple[Resource, ...] = ()
    perturbations: tuple[Perturbation, ...] = ()
    sensors: tuple[Sensor, ...] = ()
    actuators: tuple[Actuator, ...] = ()
    inputs: dict[str, float] = field(default_factory=dict)
    constants: dict[str, float] = field(default_factory=dict)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/world/test_contract.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add api/server/world/__init__.py api/server/world/contract.py tests/api/world/__init__.py tests/api/world/test_contract.py
git commit -m "feat(world): contract — seven world-pack primitives (callable expressions)" -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 2: World state + engine tick (`engine.py`)

The heart of the engine: `WorldState` (mutable dicts + `w["name"]` accessor + clamped `add`) and `WorldEngine.tick` (reset inputs → apply perturbations → integrate flows → recompute signals → fire sensors → publish `world.tick`). Actuators/`run` come in Task 3.

**Files:**
- Create: `api/server/world/engine.py`
- Test: `tests/api/world/test_engine.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/world/test_engine.py`:

```python
from api.server.services.event_bus import EventBus
from api.server.world.contract import (
    Stock, Flow, Signal, Resource, Perturbation, Sensor, WorldPack,
)
from api.server.world.engine import WorldState, WorldEngine


def _pack():
    return WorldPack(
        name="t",
        stocks=(Stock("backlog", initial=0.0, min=0.0, max=None),),
        resources=(Resource("agents", capacity=20.0),),
        inputs={"arrival": 30.0},
        constants={"HANDLE": 2.0},
        flows=(
            Flow(into="backlog", rate=lambda w: w["arrival"]),
            Flow(into="backlog", rate=lambda w: -(w["agents"] * w["HANDLE"])),
        ),
        signals=(
            Signal("breach", lambda w: w["backlog"] / max(w["backlog"] + w["agents"] * w["HANDLE"], 1)),
        ),
        perturbations=(
            Perturbation("surge", target="arrival", magnitude=60.0, duration_ticks=2),
        ),
        sensors=(
            Sensor("hot", when=lambda w: w["breach"] > 0.5, emit="ops.hot"),
        ),
    )


def test_state_accessor_reads_across_categories_and_clamps_add():
    s = WorldState(_pack())
    assert s["backlog"] == 0.0 and s["agents"] == 20.0
    assert s["arrival"] == 30.0 and s["HANDLE"] == 2.0
    s.add("backlog", -100.0)
    assert s.stocks["backlog"] == 0.0        # clamped at min
    s.add("agents", 40.0)
    assert s.resources["agents"] == 60.0     # resources unbounded


def test_tick_integrates_flows_and_recomputes_signals():
    engine = WorldEngine(_pack(), EventBus())
    engine.tick()
    # inflow 30, outflow 40 -> net -10 -> clamped at 0
    assert engine.state.stocks["backlog"] == 0.0
    assert engine.state.signals["breach"] == 0.0


def test_tick_publishes_world_tick():
    bus = EventBus()
    seen = []
    bus.on("world.tick", lambda e: seen.append(e))
    WorldEngine(_pack(), bus).tick()
    assert len(seen) == 1
    assert seen[0].world == "t" and "breach" in seen[0].signals


def test_manual_perturbation_offsets_input_for_its_duration():
    engine = WorldEngine(_pack(), EventBus())
    engine.inject("surge")
    engine.tick()   # arrival 90, out 40 -> backlog 50
    assert engine.state.stocks["backlog"] == 50.0
    engine.tick()   # surge tick 2: arrival 90, out 40 -> +50 -> 100
    assert engine.state.stocks["backlog"] == 100.0
    engine.tick()   # surge expired: arrival 30, out 40 -> -10 -> 90
    assert engine.state.stocks["backlog"] == 90.0


def test_sensor_fires_once_on_rising_edge():
    bus = EventBus()
    fired = []
    bus.on("ops.hot", lambda e: fired.append(e))
    engine = WorldEngine(_pack(), bus)
    engine.tick()                 # backlog 0, breach 0 -> quiet
    assert fired == []
    engine.inject("surge")
    engine.tick()                 # backlog 50 -> breach 50/90 > 0.5 -> fire
    engine.tick()                 # still hot -> latched, no refire
    assert len(fired) == 1 and fired[0].sensor == "hot"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/world/test_engine.py -v`
Expected: FAIL — `ImportError: cannot import name 'WorldState' from 'api.server.world.engine'` (module doesn't exist yet).

- [ ] **Step 3: Write minimal implementation**

Create `api/server/world/engine.py`:

```python
"""WorldState + WorldEngine — the whole runtime in one cohesive unit.

Tick order: reset inputs to baseline -> apply active perturbations -> integrate
flows into stocks -> recompute signals -> fire sensors (rising edge) -> publish
world.tick. Actuators are bus subscribers (attach()), not on the tick path, so
feedback is event-driven.
"""
from __future__ import annotations

import asyncio

from api.shared.events import FleetEvent
from api.server.world.contract import WorldPack


class WorldState:
    """Mutable world state with a flat `state["name"]` read across categories."""

    def __init__(self, pack: WorldPack) -> None:
        self.stocks: dict[str, float] = {s.name: float(s.initial) for s in pack.stocks}
        self.resources: dict[str, float] = {r.name: float(r.capacity) for r in pack.resources}
        self.inputs: dict[str, float] = dict(pack.inputs)
        self.constants: dict[str, float] = dict(pack.constants)
        self.signals: dict[str, float] = {}
        self._bounds: dict[str, tuple[float | None, float | None]] = {
            s.name: (s.min, s.max) for s in pack.stocks
        }

    def __getitem__(self, name: str) -> float:
        for d in (self.stocks, self.resources, self.inputs, self.constants, self.signals):
            if name in d:
                return d[name]
        raise KeyError(name)

    def add(self, name: str, delta: float) -> None:
        if name in self.stocks:
            lo, hi = self._bounds[name]
            value = self.stocks[name] + delta
            if lo is not None:
                value = max(lo, value)
            if hi is not None:
                value = min(hi, value)
            self.stocks[name] = value
        elif name in self.resources:
            self.resources[name] += delta
        else:
            raise KeyError(f"unknown stock/resource {name!r}")


class WorldEngine:
    def __init__(self, pack: WorldPack, bus) -> None:
        self.pack = pack
        self.bus = bus
        self.state = WorldState(pack)
        self._pending: list[str] = []              # queued manual injections
        self._active: dict[str, int] = {}          # perturbation -> remaining ticks
        self._latched: dict[str, bool] = {s.name: False for s in pack.sensors}
        self._attached = False
        self._running = False

    def inject(self, name: str) -> None:
        self._pending.append(name)

    def tick(self, dt_hours: float = 1.0) -> None:
        st = self.state
        st.inputs = dict(self.pack.inputs)
        self._apply_perturbations()

        deltas: dict[str, float] = {}
        for flow in self.pack.flows:
            rate = float(flow.rate(st)) * dt_hours
            deltas[flow.into] = deltas.get(flow.into, 0.0) + rate
            if flow.out_of:
                deltas[flow.out_of] = deltas.get(flow.out_of, 0.0) - rate
        for name, delta in deltas.items():
            st.add(name, delta)

        st.signals = {}
        for sig in self.pack.signals:
            try:
                st.signals[sig.name] = float(sig.formula(st))
            except Exception:
                continue

        for sensor in self.pack.sensors:
            try:
                hot = bool(sensor.when(st))
            except Exception:
                hot = False
            if hot and not self._latched[sensor.name]:
                self.bus.emit(FleetEvent(type=sensor.emit, sensor=sensor.name))
                self._latched[sensor.name] = True
            elif not hot:
                self._latched[sensor.name] = False

        self.bus.emit(FleetEvent(
            type="world.tick",
            world=self.pack.name,
            signals=dict(st.signals),
            stocks=dict(st.stocks),
        ))

    def _apply_perturbations(self) -> None:
        for pert in self.pack.perturbations:
            if pert.name in self._pending:
                self._pending.remove(pert.name)
                self._active[pert.name] = pert.duration_ticks
        for pert in self.pack.perturbations:
            remaining = self._active.get(pert.name)
            if remaining is None:
                continue
            self.state.inputs[pert.target] = self.state.inputs.get(pert.target, 0.0) + pert.magnitude
            if remaining <= 1:
                del self._active[pert.name]
            else:
                self._active[pert.name] = remaining - 1
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/world/test_engine.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add api/server/world/engine.py tests/api/world/test_engine.py
git commit -m "feat(world): WorldState + WorldEngine.tick (integrate, signals, sensors)" -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 3: Actuators + run loop + closed-loop e2e (`engine.py`)

Adds the feedback half: actuators subscribe to responder-completion events and mutate state; `run`/`stop` drive the tick loop. Then a full closed-loop test over the real bus.

**Files:**
- Modify: `api/server/world/engine.py` (add `attach`, `_make_actuator`, `run`, `stop` to `WorldEngine`)
- Test: `tests/api/world/test_engine.py` (append actuator + e2e tests)

- [ ] **Step 1: Write the failing test**

Append to `tests/api/world/test_engine.py`:

```python
import asyncio
import contextlib
import pytest
from api.shared.events import FleetEvent
from api.server.world.contract import Actuator, WorldPack, Stock, Resource


def _feedback_pack():
    return WorldPack(
        name="fb",
        resources=(Resource("agents", capacity=20.0),),
        actuators=(
            Actuator("hire", on="surge-staffing.completed", target="agents",
                     effect=lambda ev: ev.get("hired", 0)),
        ),
    )


def test_actuator_applies_delta_from_completion_event():
    engine = WorldEngine(_feedback_pack(), EventBus())
    engine.attach()
    engine.bus.emit(FleetEvent(type="surge-staffing.completed", hired=15))
    assert engine.state.resources["agents"] == 35.0


def test_actuator_ignores_unrelated_and_malformed_events():
    engine = WorldEngine(_feedback_pack(), EventBus())
    engine.attach()
    engine.bus.emit(FleetEvent(type="something.else", hired=15))     # not subscribed
    engine.bus.emit(FleetEvent(type="surge-staffing.completed"))     # no 'hired' -> 0
    assert engine.state.resources["agents"] == 20.0


@pytest.mark.asyncio
async def test_run_loop_ticks_until_stopped():
    engine = WorldEngine(_pack(), EventBus())
    ticks = []
    engine.bus.on("world.tick", lambda e: ticks.append(e))
    task = asyncio.create_task(engine.run(tick_seconds=0.0))
    await asyncio.sleep(0.02)
    engine.stop()
    with contextlib.suppress(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=1.0)
    assert len(ticks) >= 1


def test_closed_loop_surge_triggers_hiring_then_recovers():
    # Toy-shaped pack with the full loop: surge -> sensor -> (stub responder) -> actuator -> drain.
    pack = WorldPack(
        name="loop",
        stocks=(Stock("backlog", initial=0.0, min=0.0, max=None),),
        resources=(Resource("agents", capacity=20.0),),
        inputs={"arrival": 30.0},
        constants={"HANDLE": 2.0},
        flows=(
            Flow(into="backlog", rate=lambda w: w["arrival"]),
            Flow(into="backlog", rate=lambda w: -(w["agents"] * w["HANDLE"])),
        ),
        signals=(Signal("breach", lambda w: w["backlog"] / max(w["backlog"] + w["agents"] * w["HANDLE"], 1)),),
        perturbations=(Perturbation("surge", target="arrival", magnitude=60.0, duration_ticks=3),),
        sensors=(Sensor("hot", when=lambda w: w["breach"] > 0.5, emit="ops.surge_staffing.requested"),),
        actuators=(Actuator("hire", on="surge-staffing.completed", target="agents",
                            effect=lambda ev: ev.get("hired", 0)),),
    )
    bus = EventBus()
    fired = []
    bus.on("ops.surge_staffing.requested", lambda e: fired.append(e))
    # Stub responder: a surge request "hires" 60 agent-capacity.
    bus.on("ops.surge_staffing.requested",
           lambda e: bus.emit(FleetEvent(type="surge-staffing.completed", hired=60)))

    engine = WorldEngine(pack, bus)
    engine.attach()
    for _ in range(3):
        engine.tick()
    assert engine.state.stocks["backlog"] == 0.0 and fired == []

    engine.inject("surge")
    for _ in range(4):
        engine.tick()
    assert len(fired) >= 1
    assert engine.state.resources["agents"] >= 80.0     # 20 + 60 hired

    for _ in range(10):
        engine.tick()
    assert engine.state.stocks["backlog"] == 0.0        # extra capacity drained it
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/world/test_engine.py -v`
Expected: FAIL — `AttributeError: 'WorldEngine' object has no attribute 'attach'`.

- [ ] **Step 3: Write minimal implementation**

Add these methods to `WorldEngine` in `api/server/world/engine.py` (after `_apply_perturbations`):

```python
    def attach(self) -> None:
        if self._attached:
            return
        for actuator in self.pack.actuators:
            self.bus.on(actuator.on, self._make_actuator(actuator))
        self._attached = True

    def _make_actuator(self, actuator):
        def handle(event: FleetEvent) -> None:
            try:
                delta = float(actuator.effect(event.model_dump()))
                self.state.add(actuator.target, delta)
            except Exception:
                pass
        return handle

    async def run(self, tick_seconds: float = 1.0, dt_hours: float = 1.0) -> None:
        self.attach()
        self._running = True
        while self._running:
            self.tick(dt_hours)
            await asyncio.sleep(tick_seconds)

    def stop(self) -> None:
        self._running = False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/world/test_engine.py -v`
Expected: PASS (9 passed).

- [ ] **Step 5: Commit**

```bash
git add api/server/world/engine.py tests/api/world/test_engine.py
git commit -m "feat(world): actuator feedback + run loop + closed-loop e2e" -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 4: Toy pack + loader + lifespan entry (`packs/toy.py`, `__init__.py`)

**Files:**
- Create: `api/server/world/packs/__init__.py`
- Create: `api/server/world/packs/toy.py`
- Modify: `api/server/world/__init__.py` (replace the stub with the loader + starter)
- Test: `tests/api/world/test_wiring.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/world/test_wiring.py`:

```python
import asyncio
import contextlib
import pytest
from api.server.services.event_bus import EventBus
from api.server.world import active_world_name, load_pack, maybe_start_world


def test_active_world_name_reads_env(monkeypatch):
    monkeypatch.delenv("ZAVA_WORLD", raising=False)
    assert active_world_name() is None
    monkeypatch.setenv("ZAVA_WORLD", "toy")
    assert active_world_name() == "toy"


def test_load_toy_pack():
    pack = load_pack("toy")
    assert pack.name == "toy"
    assert any(s.name == "support_backlog" for s in pack.stocks)
    assert any(sen.emit == "ops.surge_staffing.requested" for sen in pack.sensors)


def test_load_unknown_pack_raises():
    with pytest.raises(Exception):
        load_pack("does_not_exist")


@pytest.mark.asyncio
async def test_maybe_start_world_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ZAVA_WORLD", raising=False)
    assert maybe_start_world(EventBus()) is None


@pytest.mark.asyncio
async def test_maybe_start_world_starts_and_ticks(monkeypatch):
    monkeypatch.setenv("ZAVA_WORLD", "toy")
    bus = EventBus()
    ticks = []
    bus.on("world.tick", lambda e: ticks.append(e))
    task = maybe_start_world(bus, tick_seconds=0.0)
    assert task is not None
    await asyncio.sleep(0.02)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    assert len(ticks) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/world/test_wiring.py -v`
Expected: FAIL — `ImportError: cannot import name 'active_world_name' from 'api.server.world'`.

- [ ] **Step 3: Write minimal implementation**

Create `api/server/world/packs/__init__.py`:

```python
"""World packs — one module per pluggable industry world."""
```

Create `api/server/world/packs/toy.py`:

```python
"""Neutral support-queue toy world — the engine's permanent industry guard.

Baseline arrival (30/h) < service capacity (20 agents * 2/h = 40/h) so the
backlog stays drained. A manual `demand_surge` (+60/h for 3 ticks) pushes
arrival to 90/h; backlog climbs, `sla_breach_pct` crosses 0.5, the sensor
emits `ops.surge_staffing.requested`. A responder completing
`surge-staffing.completed` with `hired` feeds the actuator, raising capacity
until the backlog drains again.
"""
from api.server.world.contract import (
    Stock, Flow, Signal, Resource, Perturbation, Sensor, Actuator, WorldPack,
)

PACK = WorldPack(
    name="toy",
    stocks=(Stock("support_backlog", initial=0.0, min=0.0, max=None),),
    resources=(Resource("agents", capacity=20.0),),
    inputs={"ticket_arrival_rate": 30.0},
    constants={"HANDLE": 2.0},
    flows=(
        Flow(into="support_backlog", rate=lambda w: w["ticket_arrival_rate"]),
        Flow(into="support_backlog", rate=lambda w: -(w["agents"] * w["HANDLE"])),
    ),
    signals=(
        Signal("sla_breach_pct",
               lambda w: w["support_backlog"] / max(w["support_backlog"] + w["agents"] * w["HANDLE"], 1)),
    ),
    perturbations=(
        Perturbation("demand_surge", target="ticket_arrival_rate", magnitude=60.0, duration_ticks=3),
    ),
    sensors=(
        Sensor("backlog_high", when=lambda w: w["sla_breach_pct"] > 0.5,
               emit="ops.surge_staffing.requested"),
    ),
    actuators=(
        Actuator("hire", on="surge-staffing.completed", target="agents",
                 effect=lambda ev: ev.get("hired", 0)),
    ),
)
```

Replace the contents of `api/server/world/__init__.py`:

```python
"""Generic organisational world-simulator engine (spec 2026-07-10).

Industry-agnostic: all nouns come from a WorldPack (see contract.py). Off
unless ZAVA_WORLD names a pack. `maybe_start_world` is the lifespan entry.
"""
from __future__ import annotations

import asyncio
import importlib
import os

from api.server.world.contract import WorldPack
from api.server.world.engine import WorldEngine


def active_world_name() -> str | None:
    return os.getenv("ZAVA_WORLD") or None


def load_pack(name: str) -> WorldPack:
    module = importlib.import_module(f"api.server.world.packs.{name}")
    pack = getattr(module, "PACK", None)
    if not isinstance(pack, WorldPack):
        raise RuntimeError(f"world pack {name!r} does not expose PACK: WorldPack")
    return pack


def maybe_start_world(bus, **run_kwargs) -> "asyncio.Task | None":
    """Start the engine iff ZAVA_WORLD is set; else return None."""
    name = active_world_name()
    if not name:
        return None
    engine = WorldEngine(load_pack(name), bus)
    return asyncio.create_task(engine.run(**run_kwargs))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/world/test_wiring.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Run the full world suite**

Run: `uv run pytest tests/api/world -v`
Expected: PASS (all world tests green).

- [ ] **Step 6: Commit**

```bash
git add api/server/world/__init__.py api/server/world/packs tests/api/world/test_wiring.py
git commit -m "feat(world): neutral toy pack + ZAVA_WORLD loader + lifespan entry" -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 5: Wire the engine into the FastAPI lifespan (`main.py`)

**Files:**
- Modify: `api/server/main.py` (startup near the `ramp_task` creation ~line 175; shutdown cancel loop ~line 360)

- [ ] **Step 1: Add engine startup after the ramp loop**

In `api/server/main.py`, find (around line 175):

```python
    ramp_task = asyncio.create_task(simulator_orchestrator.ramp_loop())
```

Add immediately after it:

```python
    # World simulator engine — off unless ZAVA_WORLD names a pack (spec 2026-07-10).
    from api.server.world import maybe_start_world
    world_task = maybe_start_world(app_state.bus)
    if world_task is not None:
        print(f"[server] world engine ON (ZAVA_WORLD={os.getenv('ZAVA_WORLD')})")
```

- [ ] **Step 2: Cancel `world_task` on shutdown**

The shutdown block cancels tasks and then awaits them. The engine's `run()` loops until cancelled, so it needs an explicit `.cancel()` (adding it only to the await loop would hang). Find (around line 354):

```python
        if dream_cadence_task is not None:
            dream_cadence_task.cancel()
```

Add immediately after it:

```python
        if world_task is not None:
            world_task.cancel()
```

Then find (around line 360):

```python
        for t in (ramp_task, seed_task, dream_cadence_task):
```

Change it to:

```python
        for t in (ramp_task, seed_task, dream_cadence_task, world_task):
```

- [ ] **Step 3: Verify the app imports and the flag-off default holds**

Run: `uv run python -c "import api.server.main"`
Expected: no error (module imports; with `ZAVA_WORLD` unset the engine never starts).

- [ ] **Step 4: Verify flag-on boot creates the task (no server needed)**

Run:
```bash
uv run python -c "
import asyncio, os
os.environ['ZAVA_WORLD'] = 'toy'
from api.server.services.event_bus import EventBus
from api.server.world import maybe_start_world
async def main():
    t = maybe_start_world(EventBus(), tick_seconds=0.0)
    assert t is not None
    await asyncio.sleep(0.02); t.cancel()
    print('world task started OK')
asyncio.run(main())
"
```
Expected: prints `world task started OK`.

- [ ] **Step 5: Commit**

```bash
git add api/server/main.py
git commit -m "feat(world): start engine in FastAPI lifespan behind ZAVA_WORLD flag" -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

## Final verification

- [ ] **Full world suite**

Run: `uv run pytest tests/api/world -v`
Expected: all pass.

- [ ] **No regressions** (engine is off by default, so existing behaviour is unchanged)

Run: `uv run pytest -q`
Expected: no new failures attributable to `api/server/world` or the `main.py` edit.

- [ ] **Lint**

Run: `uv run ruff check api/server/world`
Expected: clean (or only pre-existing repo-wide advisories).

---

## What this plan deliberately does NOT cover (follow-on plans)

- **M4 — the minimal telco slice** (`world/packs/telco.py` + response-half domains/personae/projections via `compose-domain`). Also brings in **poisson perturbation schedules** and **sensor cooldown** (both dropped from the core as YAGNI — see the `ponytail:` notes in `contract.py`). Its own plan once this engine API is real (spec §11.1).
- **M5 — the cosmic-lens `world.tick` signals stream**: SSE channel + lens rendering. Separate plan.
- **Data-authored (YAML) pack format + its scoped sandbox, time-series history store, two-tier (reaction vs Durable) work router** — spec §12 open questions; deferred until a pack needs them.
