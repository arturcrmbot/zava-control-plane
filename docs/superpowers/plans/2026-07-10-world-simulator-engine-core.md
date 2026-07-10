# World Simulator — Engine Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the generic, industry-agnostic world-simulator engine (milestones 1–3 of the spec) — a tick-driven stock-and-flow loop with perturbations, sensors, and actuators — proven end-to-end over the real EventBus with a neutral toy pack, and wired into the FastAPI lifespan behind a `ZAVA_WORLD` flag.

**Architecture:** A new `api/server/world/` package. `contract.py` declares seven frozen-dataclass primitives (Stock, Flow, Signal, Resource, Perturbation, Sensor, Actuator) grouped into a `WorldPack`. A `WorldEngine` holds runtime `WorldState`, integrates flows each tick, recomputes signals, evaluates sensors (emitting bus events), and lets actuators (bus subscribers) feed responder outcomes back into state. All pack-authored math runs in a persona-grade sandbox (restricted builtins + AST guard). The engine couples to the rest of Zava only through the existing `EventBus`. It is off by default; setting `ZAVA_WORLD=<pack>` starts it in the lifespan.

**Tech Stack:** Python 3.13 (FastAPI process), pytest (`uv run pytest`, asyncio_mode=auto), Pydantic v2 `FleetEvent`, stdlib `ast`/`compile`/`eval`, `random`, `math`, `importlib`. No new dependencies.

**Spec:** [`docs/superpowers/specs/2026-07-10-organisational-world-simulator-design.md`](../specs/2026-07-10-organisational-world-simulator-design.md) (milestones 1–3, §11).

**Note on commits:** Every commit command below appends the repo's Co-authored-by trailer via a second `-m`. Keep it.

---

## File Structure

New package `api/server/world/` — each file one responsibility:

| File | Responsibility |
|---|---|
| `api/server/world/__init__.py` | Package marker + `maybe_start_world(bus)` lifespan helper. |
| `api/server/world/contract.py` | The seven primitive dataclasses + `WorldPack` container. Declarations only, no behaviour. |
| `api/server/world/sandbox.py` | Compile + AST-guard + restricted-builtins evaluator for pack expressions. |
| `api/server/world/state.py` | `WorldState` — runtime mutable stocks/resources/inputs/constants/signals + `namespace()` + `add()`. |
| `api/server/world/integrator.py` | Pure `integrate(state, flows, codes, dt)` — apply flows to stocks. |
| `api/server/world/signals.py` | Pure `evaluate_signals(state, signals, codes)` — recompute derived readouts. |
| `api/server/world/perturbations.py` | `PerturbationScheduler` — seeded poisson/manual exogenous kicks onto `inputs`. |
| `api/server/world/sensors.py` | `SensorRuntime` — rising-edge + cooldown condition→event emission. |
| `api/server/world/actuators.py` | `ActuatorRuntime` — subscribe responder-completion events, apply feedback deltas. |
| `api/server/world/engine.py` | `WorldEngine` — owns state + runtimes; `tick()` and async `run()`. |
| `api/server/world/loader.py` | `world_enabled()`, `active_world_name()`, `load_pack(name)`. |
| `api/server/world/packs/__init__.py` | Packs namespace marker. |
| `api/server/world/packs/toy/__init__.py` | Toy pack marker. |
| `api/server/world/packs/toy/pack.py` | Neutral support-queue pack exposing `PACK: WorldPack`. |
| `api/server/main.py` (modify) | Start/stop the engine in the lifespan behind the flag. |

Tests under `tests/api/world/` (one file per unit + one end-to-end + one wiring).

---

## Task 1: Package + the seven primitives (`contract.py`)

**Files:**
- Create: `api/server/world/__init__.py`
- Create: `api/server/world/contract.py`
- Test: `tests/api/world/__init__.py`, `tests/api/world/test_contract.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/world/__init__.py` (empty file), then `tests/api/world/test_contract.py`:

```python
from api.server.world.contract import (
    Stock, Flow, Signal, Resource, Perturbation, Sensor, Actuator, WorldPack,
)


def test_primitives_construct_with_expected_fields():
    assert Stock("backlog", initial=5.0).min == 0.0
    assert Flow(into="backlog", rate="arrival").out_of is None
    assert Signal("sla", "backlog / 10").formula == "backlog / 10"
    assert Resource("agents", capacity=20.0).capacity == 20.0
    p = Perturbation("surge", target="arrival", magnitude=60.0, schedule="manual")
    assert p.duration_ticks == 1
    assert Sensor("hot", when="sla > 0.5", emit="ops.x").cooldown_ticks == 0
    assert Actuator("hire", on="x.done", target="agents", effect="1").target == "agents"


def test_worldpack_groups_declarations_and_is_frozen():
    pack = WorldPack(
        name="t",
        stocks=(Stock("backlog"),),
        inputs={"arrival": 30.0},
        constants={"HANDLE": 2.0},
    )
    assert pack.name == "t"
    assert pack.stocks[0].name == "backlog"
    assert pack.inputs["arrival"] == 30.0
    assert pack.flows == ()  # default empty
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/world/test_contract.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.server.world'`.

- [ ] **Step 3: Write minimal implementation**

Create `api/server/world/__init__.py`:

```python
"""Generic organisational world-simulator engine (spec 2026-07-10).

Industry-agnostic: all nouns come from a WorldPack. See contract.py.
"""
```

Create `api/server/world/contract.py`:

```python
"""The narrow waist: seven primitive types every world pack conforms to.

Declarations only — no behaviour. Expression-bearing fields (Flow.rate,
Signal.formula, Perturbation is numeric, Sensor.when, Actuator.effect) are
sandboxed strings evaluated by api.server.world.sandbox.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Stock:
    """A level that fills/drains. `min`/`max` clamp it (None = unbounded)."""
    name: str
    initial: float = 0.0
    min: float | None = 0.0
    max: float | None = None


@dataclass(frozen=True)
class Flow:
    """Moves `rate` units/tick into stock `into` (drains `out_of` if set).

    `rate` is a sandboxed expression -> float. Negative rates drain `into`.
    """
    into: str
    rate: str
    out_of: str | None = None


@dataclass(frozen=True)
class Signal:
    """A derived readout. `formula` is a sandboxed expression -> float."""
    name: str
    formula: str


@dataclass(frozen=True)
class Resource:
    """A finite pool functions contend for."""
    name: str
    capacity: float


@dataclass(frozen=True)
class Perturbation:
    """An exogenous kick: while active, adds `magnitude` to inputs[target].

    `schedule` is "poisson:<rate_per_hour>" or "manual".
    """
    name: str
    target: str
    magnitude: float
    schedule: str
    duration_ticks: int = 1


@dataclass(frozen=True)
class Sensor:
    """when <sandboxed bool expr> then emit <event type>, with cooldown."""
    name: str
    when: str
    emit: str
    cooldown_ticks: int = 0


@dataclass(frozen=True)
class Actuator:
    """On bus event `on`, add sandboxed `effect` (-> float) to `target`.

    `effect` is evaluated with the event payload injected as `event` (dict).
    """
    name: str
    on: str
    target: str
    effect: str


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
git commit -m "feat(world): contract — seven world-pack primitives + WorldPack" -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 2: Sandboxed expression evaluator (`sandbox.py`)

Mirrors the persona sandbox in `api/server/services/persona_responder.py` (`_DECISION_BUILTINS` + `_validate_persona_source`) but standalone so the engine core carries no heavy imports.

**Files:**
- Create: `api/server/world/sandbox.py`
- Test: `tests/api/world/test_sandbox.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/world/test_sandbox.py`:

```python
import pytest
from api.server.world.sandbox import compile_expr, eval_expr


def test_evaluates_arithmetic_over_namespace():
    code = compile_expr("min(backlog, agents * HANDLE)", "flow:x")
    val = eval_expr(code, {"backlog": 100.0, "agents": 20.0, "HANDLE": 2.0})
    assert val == 40.0


def test_allows_non_dunder_attribute_call():
    code = compile_expr("event.get('hired', 0)", "actuator:hire")
    assert eval_expr(code, {"event": {"hired": 5}}) == 5


def test_rejects_dunder_attribute_access():
    with pytest.raises(ValueError, match="dunder"):
        compile_expr("().__class__", "sensor:evil")


def test_rejects_import_like_names_have_no_builtins():
    code = compile_expr("open", "flow:x")
    with pytest.raises(NameError):
        eval_expr(code, {})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/world/test_sandbox.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.server.world.sandbox'`.

- [ ] **Step 3: Write minimal implementation**

Create `api/server/world/sandbox.py`:

```python
"""Locked-down evaluator for pack-authored expressions.

Same posture as the persona decision-policy sandbox: __builtins__ replaced
with a tiny whitelist, plus an AST guard that rejects dunder attribute
access (the reflection escape path). Expressions are eval-mode only.
"""
from __future__ import annotations

import ast
from typing import Any

_WORLD_BUILTINS: dict[str, Any] = {
    "len": len, "min": min, "max": max, "abs": abs, "round": round,
    "float": float, "int": int, "bool": bool, "sum": sum,
    "any": any, "all": all,
    "True": True, "False": False, "None": None,
}


def _validate(source: str, tag: str) -> None:
    try:
        tree = ast.parse(source, mode="eval")
    except SyntaxError as ex:
        raise ValueError(f"world expr {tag!r} fails to parse: {ex}") from ex
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("__") and node.attr.endswith("__"):
                raise ValueError(
                    f"world expr {tag!r}: forbidden dunder attribute "
                    f"'.{node.attr}' at line {node.lineno}"
                )


def compile_expr(source: str, tag: str):
    """Validate + compile an expression string into a code object."""
    _validate(source, tag)
    return compile(source, f"<world:{tag}>", "eval")


def eval_expr(code, namespace: dict[str, Any]) -> Any:
    """Evaluate a compiled expression against `namespace` (locals)."""
    return eval(code, {"__builtins__": _WORLD_BUILTINS}, namespace)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/world/test_sandbox.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add api/server/world/sandbox.py tests/api/world/test_sandbox.py
git commit -m "feat(world): sandboxed expression evaluator (builtins whitelist + AST guard)" -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 3: Runtime state (`state.py`)

**Files:**
- Create: `api/server/world/state.py`
- Test: `tests/api/world/test_state.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/world/test_state.py`:

```python
import pytest
from api.server.world.contract import Stock, Resource, WorldPack
from api.server.world.state import WorldState


def _pack():
    return WorldPack(
        name="t",
        stocks=(Stock("backlog", initial=5.0, min=0.0, max=100.0),),
        resources=(Resource("agents", capacity=20.0),),
        inputs={"arrival": 30.0},
        constants={"HANDLE": 2.0},
    )


def test_initialises_from_pack():
    s = WorldState(_pack())
    assert s.stocks["backlog"] == 5.0
    assert s.resources["agents"] == 20.0
    assert s.inputs["arrival"] == 30.0


def test_namespace_flattens_all_categories():
    s = WorldState(_pack())
    ns = s.namespace({"event": {"x": 1}})
    assert ns["backlog"] == 5.0 and ns["agents"] == 20.0
    assert ns["arrival"] == 30.0 and ns["HANDLE"] == 2.0
    assert ns["event"] == {"x": 1}


def test_add_clamps_stock_to_bounds():
    s = WorldState(_pack())
    s.add("backlog", -100.0)
    assert s.stocks["backlog"] == 0.0        # clamped at min
    s.add("backlog", 1000.0)
    assert s.stocks["backlog"] == 100.0      # clamped at max


def test_add_to_resource_is_unbounded():
    s = WorldState(_pack())
    s.add("agents", 40.0)
    assert s.resources["agents"] == 60.0


def test_add_unknown_name_raises():
    s = WorldState(_pack())
    with pytest.raises(KeyError):
        s.add("nope", 1.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/world/test_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.server.world.state'`.

- [ ] **Step 3: Write minimal implementation**

Create `api/server/world/state.py`:

```python
"""Runtime mutable world state (stocks/resources/inputs/constants/signals)."""
from __future__ import annotations

from typing import Any

from api.server.world.contract import WorldPack


class WorldState:
    def __init__(self, pack: WorldPack) -> None:
        self.stocks: dict[str, float] = {s.name: float(s.initial) for s in pack.stocks}
        self.resources: dict[str, float] = {r.name: float(r.capacity) for r in pack.resources}
        self.inputs: dict[str, float] = dict(pack.inputs)
        self.constants: dict[str, float] = dict(pack.constants)
        self.signals: dict[str, float] = {}
        self._bounds: dict[str, tuple[float | None, float | None]] = {
            s.name: (s.min, s.max) for s in pack.stocks
        }

    def namespace(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        ns: dict[str, Any] = {}
        ns.update(self.constants)
        ns.update(self.inputs)
        ns.update(self.stocks)
        ns.update(self.resources)
        ns.update(self.signals)
        if extra:
            ns.update(extra)
        return ns

    def add(self, name: str, delta: float) -> None:
        if name in self.stocks:
            value = self.stocks[name] + delta
            lo, hi = self._bounds[name]
            if lo is not None:
                value = max(lo, value)
            if hi is not None:
                value = min(hi, value)
            self.stocks[name] = value
        elif name in self.resources:
            self.resources[name] = self.resources[name] + delta
        else:
            raise KeyError(f"unknown stock/resource {name!r}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/world/test_state.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add api/server/world/state.py tests/api/world/test_state.py
git commit -m "feat(world): WorldState runtime holder (namespace + clamped add)" -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 4: Flow integrator (`integrator.py`)

**Files:**
- Create: `api/server/world/integrator.py`
- Test: `tests/api/world/test_integrator.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/world/test_integrator.py`:

```python
from api.server.world.contract import Stock, Flow, WorldPack
from api.server.world.state import WorldState
from api.server.world.sandbox import compile_expr
from api.server.world.integrator import integrate


def _setup():
    pack = WorldPack(
        name="t",
        stocks=(Stock("a", initial=10.0, min=None), Stock("b", initial=0.0, min=None)),
        flows=(Flow(into="b", rate="2.0", out_of="a"),),
    )
    state = WorldState(pack)
    codes = [compile_expr(f.rate, f"flow:{f.into}") for f in pack.flows]
    return pack, state, codes


def test_transfer_flow_matches_hand_computed_trajectory():
    pack, state, codes = _setup()
    integrate(state, pack.flows, codes, dt=1.0)
    assert state.stocks["a"] == 8.0 and state.stocks["b"] == 2.0
    integrate(state, pack.flows, codes, dt=1.0)
    assert state.stocks["a"] == 6.0 and state.stocks["b"] == 4.0


def test_drain_clamps_at_min_zero():
    pack = WorldPack(
        name="t",
        stocks=(Stock("q", initial=1.0, min=0.0),),
        flows=(Flow(into="q", rate="-10.0"),),
    )
    state = WorldState(pack)
    codes = [compile_expr(f.rate, "flow:q") for f in pack.flows]
    integrate(state, pack.flows, codes, dt=1.0)
    assert state.stocks["q"] == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/world/test_integrator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.server.world.integrator'`.

- [ ] **Step 3: Write minimal implementation**

Create `api/server/world/integrator.py`:

```python
"""Explicit-Euler flow integrator. Pure over WorldState + compiled rates."""
from __future__ import annotations

from api.server.world.sandbox import eval_expr
from api.server.world.state import WorldState


def integrate(state: WorldState, flows, compiled_rates, dt: float) -> None:
    """Evaluate every flow rate against the pre-tick namespace, then apply.

    Computing all deltas before applying makes the tick order-independent.
    """
    namespace = state.namespace()
    deltas: dict[str, float] = {}
    for flow, code in zip(flows, compiled_rates):
        rate = float(eval_expr(code, namespace))
        deltas[flow.into] = deltas.get(flow.into, 0.0) + rate * dt
        if flow.out_of:
            deltas[flow.out_of] = deltas.get(flow.out_of, 0.0) - rate * dt
    for name, delta in deltas.items():
        state.add(name, delta)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/world/test_integrator.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add api/server/world/integrator.py tests/api/world/test_integrator.py
git commit -m "feat(world): explicit-Euler flow integrator" -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 5: Signal evaluator (`signals.py`)

**Files:**
- Create: `api/server/world/signals.py`
- Test: `tests/api/world/test_signals.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/world/test_signals.py`:

```python
from api.server.world.contract import Stock, Resource, Signal, WorldPack
from api.server.world.state import WorldState
from api.server.world.sandbox import compile_expr
from api.server.world.signals import evaluate_signals


def _codes(pack):
    return [compile_expr(s.formula, f"signal:{s.name}") for s in pack.signals]


def test_computes_signal_from_stocks_and_resources():
    pack = WorldPack(
        name="t",
        stocks=(Stock("backlog", initial=60.0),),
        resources=(Resource("agents", capacity=20.0),),
        constants={"HANDLE": 2.0},
        signals=(Signal("breach", "backlog / max(backlog + agents * HANDLE, 1)"),),
    )
    state = WorldState(pack)
    out = evaluate_signals(state, pack.signals, _codes(pack))
    assert round(out["breach"], 3) == 0.6  # 60 / (60 + 40)


def test_bad_formula_is_isolated():
    pack = WorldPack(
        name="t",
        stocks=(Stock("x", initial=1.0),),
        signals=(Signal("bad", "x / missing_name"), Signal("good", "x + 1")),
    )
    state = WorldState(pack)
    out = evaluate_signals(state, pack.signals, _codes(pack))
    assert "bad" not in out
    assert out["good"] == 2.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/world/test_signals.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.server.world.signals'`.

- [ ] **Step 3: Write minimal implementation**

Create `api/server/world/signals.py`:

```python
"""Derived-signal evaluator. Pure; a broken formula disables only itself."""
from __future__ import annotations

from api.server.world.sandbox import eval_expr
from api.server.world.state import WorldState


def evaluate_signals(state: WorldState, signals, compiled) -> dict[str, float]:
    out: dict[str, float] = {}
    for sig, code in zip(signals, compiled):
        namespace = state.namespace()
        namespace.update(out)  # later signals may read earlier ones
        try:
            out[sig.name] = float(eval_expr(code, namespace))
        except Exception:
            continue
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/world/test_signals.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add api/server/world/signals.py tests/api/world/test_signals.py
git commit -m "feat(world): derived-signal evaluator with per-signal isolation" -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 6: Perturbation scheduler (`perturbations.py`)

**Files:**
- Create: `api/server/world/perturbations.py`
- Test: `tests/api/world/test_perturbations.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/world/test_perturbations.py`:

```python
from api.server.world.contract import Stock, Perturbation, WorldPack
from api.server.world.state import WorldState
from api.server.world.perturbations import PerturbationScheduler


def _state():
    pack = WorldPack(name="t", stocks=(Stock("q"),), inputs={"arrival": 30.0})
    return WorldState(pack)


def test_manual_injection_fires_and_offsets_input_for_duration():
    perts = (Perturbation("surge", target="arrival", magnitude=60.0,
                          schedule="manual", duration_ticks=2),)
    sched = PerturbationScheduler(perts, seed=0)
    state = _state()

    # tick 1: no injection yet -> baseline restored, no offset
    state.inputs = {"arrival": 30.0}
    sched.step(state, dt_hours=1.0)
    assert state.inputs["arrival"] == 30.0

    # inject, then two active ticks add magnitude, third is baseline again
    sched.inject("surge")
    state.inputs = {"arrival": 30.0}
    sched.step(state, dt_hours=1.0)
    assert state.inputs["arrival"] == 90.0
    state.inputs = {"arrival": 30.0}
    sched.step(state, dt_hours=1.0)
    assert state.inputs["arrival"] == 90.0
    state.inputs = {"arrival": 30.0}
    sched.step(state, dt_hours=1.0)
    assert state.inputs["arrival"] == 30.0  # expired


def test_poisson_is_reproducible_for_a_fixed_seed():
    perts = (Perturbation("spike", target="arrival", magnitude=10.0,
                          schedule="poisson:5", duration_ticks=1),)

    def run():
        sched = PerturbationScheduler(perts, seed=42)
        state = _state()
        history = []
        for _ in range(30):
            state.inputs = {"arrival": 30.0}
            sched.step(state, dt_hours=1.0)
            history.append(state.inputs["arrival"] > 30.0)
        return history

    assert run() == run()          # deterministic
    assert any(run())              # and it actually fires sometimes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/world/test_perturbations.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.server.world.perturbations'`.

- [ ] **Step 3: Write minimal implementation**

Create `api/server/world/perturbations.py`:

```python
"""Exogenous perturbation scheduler.

The engine resets state.inputs to the pack baseline each tick; this
scheduler then adds each active perturbation's magnitude on top, so an
expired perturbation naturally leaves no trace. Poisson uses a seeded RNG
for reproducibility (the replay guarantee).
"""
from __future__ import annotations

import math
import random

from api.server.world.state import WorldState


class PerturbationScheduler:
    def __init__(self, perturbations, seed: int = 0) -> None:
        self._perts = tuple(perturbations)
        self._rng = random.Random(seed)
        self._active: dict[str, int] = {}      # name -> remaining ticks
        self._manual: list[str] = []           # queued manual injections

    def inject(self, name: str) -> None:
        self._manual.append(name)

    def step(self, state: WorldState, dt_hours: float) -> None:
        # 1) maybe start perturbations not already active
        for pert in self._perts:
            if pert.name in self._active:
                continue
            if pert.schedule.startswith("poisson:"):
                rate = float(pert.schedule.split(":", 1)[1])       # events/hour
                if self._rng.random() < 1.0 - math.exp(-rate * dt_hours):
                    self._active[pert.name] = pert.duration_ticks
            elif pert.schedule == "manual":
                if pert.name in self._manual:
                    self._manual.remove(pert.name)
                    self._active[pert.name] = pert.duration_ticks
        # 2) apply active offsets and decrement
        for pert in self._perts:
            remaining = self._active.get(pert.name)
            if remaining is None:
                continue
            state.inputs[pert.target] = state.inputs.get(pert.target, 0.0) + pert.magnitude
            remaining -= 1
            if remaining <= 0:
                del self._active[pert.name]
            else:
                self._active[pert.name] = remaining
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/world/test_perturbations.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add api/server/world/perturbations.py tests/api/world/test_perturbations.py
git commit -m "feat(world): seeded perturbation scheduler (poisson + manual)" -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 7: Sensor runtime (`sensors.py`)

**Files:**
- Create: `api/server/world/sensors.py`
- Test: `tests/api/world/test_sensors.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/world/test_sensors.py`:

```python
from api.server.world.contract import Stock, Sensor, WorldPack
from api.server.world.state import WorldState
from api.server.world.sandbox import compile_expr
from api.server.world.sensors import SensorRuntime


def _runtime(sensor):
    codes = [compile_expr(sensor.when, f"sensor:{sensor.name}")]
    return SensorRuntime((sensor,), codes)


def _state(backlog):
    pack = WorldPack(name="t", stocks=(Stock("backlog", initial=backlog, max=None),))
    return WorldState(pack)


def test_fires_on_rising_edge_only():
    sensor = Sensor("hot", when="backlog > 50", emit="ops.hot", cooldown_ticks=0)
    rt = _runtime(sensor)

    events = rt.evaluate(_state(10.0))
    assert events == []                       # below threshold

    events = rt.evaluate(_state(80.0))
    assert len(events) == 1 and events[0].type == "ops.hot"

    events = rt.evaluate(_state(90.0))
    assert events == []                       # still high -> latched, no refire


def test_refires_after_dropping_and_rising_again():
    sensor = Sensor("hot", when="backlog > 50", emit="ops.hot")
    rt = _runtime(sensor)
    assert len(rt.evaluate(_state(80.0))) == 1
    assert rt.evaluate(_state(10.0)) == []    # drops -> unlatches
    assert len(rt.evaluate(_state(80.0))) == 1


def test_cooldown_suppresses_refire():
    sensor = Sensor("hot", when="backlog > 50", emit="ops.hot", cooldown_ticks=3)
    rt = _runtime(sensor)
    assert len(rt.evaluate(_state(80.0))) == 1   # fires, cooldown=3
    rt.evaluate(_state(10.0))                     # unlatch, cooldown 3->2
    assert rt.evaluate(_state(80.0)) == []        # rising but cooling (2->1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/world/test_sensors.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.server.world.sensors'`.

- [ ] **Step 3: Write minimal implementation**

Create `api/server/world/sensors.py`:

```python
"""Sensor runtime: rising-edge + cooldown condition -> bus event."""
from __future__ import annotations

from api.shared.events import FleetEvent
from api.server.world.sandbox import eval_expr
from api.server.world.state import WorldState


class SensorRuntime:
    def __init__(self, sensors, compiled_conditions) -> None:
        self._sensors = tuple(sensors)
        self._codes = list(compiled_conditions)
        self._latched: dict[str, bool] = {s.name: False for s in self._sensors}
        self._cooldown: dict[str, int] = {s.name: 0 for s in self._sensors}

    def evaluate(self, state: WorldState) -> list[FleetEvent]:
        events: list[FleetEvent] = []
        namespace = state.namespace()
        for sensor, code in zip(self._sensors, self._codes):
            if self._cooldown[sensor.name] > 0:
                self._cooldown[sensor.name] -= 1
            try:
                condition = bool(eval_expr(code, namespace))
            except Exception:
                condition = False
            if condition and not self._latched[sensor.name] and self._cooldown[sensor.name] == 0:
                events.append(FleetEvent(type=sensor.emit, sensor=sensor.name))
                self._latched[sensor.name] = True
                self._cooldown[sensor.name] = sensor.cooldown_ticks
            if not condition:
                self._latched[sensor.name] = False
        return events
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/world/test_sensors.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add api/server/world/sensors.py tests/api/world/test_sensors.py
git commit -m "feat(world): sensor runtime (rising-edge + cooldown -> FleetEvent)" -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 8: Actuator runtime (`actuators.py`)

**Files:**
- Create: `api/server/world/actuators.py`
- Test: `tests/api/world/test_actuators.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/world/test_actuators.py`:

```python
from api.server.services.event_bus import EventBus
from api.shared.events import FleetEvent
from api.server.world.contract import Resource, Actuator, WorldPack
from api.server.world.state import WorldState
from api.server.world.sandbox import compile_expr
from api.server.world.actuators import ActuatorRuntime


def _setup():
    pack = WorldPack(name="t", resources=(Resource("agents", capacity=20.0),))
    state = WorldState(pack)
    act = Actuator("hire", on="surge-staffing.completed", target="agents",
                   effect="event.get('hired', 0)")
    codes = [compile_expr(act.effect, "actuator:hire")]
    runtime = ActuatorRuntime((act,), codes, state)
    return state, runtime


def test_completion_event_applies_delta_from_payload():
    state, runtime = _setup()
    bus = EventBus()
    runtime.attach(bus)
    bus.emit(FleetEvent(type="surge-staffing.completed", hired=15))
    assert state.resources["agents"] == 35.0


def test_unrelated_event_is_ignored():
    state, runtime = _setup()
    bus = EventBus()
    runtime.attach(bus)
    bus.emit(FleetEvent(type="something.else", hired=15))
    assert state.resources["agents"] == 20.0


def test_malformed_effect_is_isolated():
    pack = WorldPack(name="t", resources=(Resource("agents", capacity=20.0),))
    state = WorldState(pack)
    act = Actuator("bad", on="x.done", target="agents", effect="event.get('missing')")
    codes = [compile_expr(act.effect, "actuator:bad")]
    runtime = ActuatorRuntime((act,), codes, state)
    bus = EventBus()
    runtime.attach(bus)
    bus.emit(FleetEvent(type="x.done"))          # effect -> None -> float(None) raises
    assert state.resources["agents"] == 20.0     # swallowed, no crash
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/world/test_actuators.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.server.world.actuators'`.

- [ ] **Step 3: Write minimal implementation**

Create `api/server/world/actuators.py`:

```python
"""Actuator runtime: responder-completion events feed back into state."""
from __future__ import annotations

from api.shared.events import FleetEvent
from api.server.world.sandbox import eval_expr
from api.server.world.state import WorldState


class ActuatorRuntime:
    def __init__(self, actuators, compiled_effects, state: WorldState) -> None:
        self._state = state
        self._by_event: dict[str, list] = {}
        for actuator, code in zip(actuators, compiled_effects):
            self._by_event.setdefault(actuator.on, []).append((actuator, code))

    def attach(self, bus) -> None:
        for event_type in self._by_event:
            bus.on(event_type, self._handle)

    def _handle(self, event: FleetEvent) -> None:
        payload = event.model_dump()
        for actuator, code in self._by_event.get(event.type, []):
            try:
                delta = float(eval_expr(code, self._state.namespace({"event": payload})))
                self._state.add(actuator.target, delta)
            except Exception:
                continue
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/world/test_actuators.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add api/server/world/actuators.py tests/api/world/test_actuators.py
git commit -m "feat(world): actuator runtime (bus completion -> feedback delta)" -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 9: The engine — single tick (`engine.py`)

**Files:**
- Create: `api/server/world/engine.py`
- Test: `tests/api/world/test_engine_tick.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/world/test_engine_tick.py`:

```python
from api.server.services.event_bus import EventBus
from api.server.world.contract import Stock, Resource, Flow, Signal, WorldPack
from api.server.world.engine import WorldEngine


def _pack():
    return WorldPack(
        name="t",
        stocks=(Stock("backlog", initial=0.0, min=0.0, max=None),),
        resources=(Resource("agents", capacity=20.0),),
        inputs={"arrival": 30.0},
        constants={"HANDLE": 2.0},
        flows=(
            Flow(into="backlog", rate="arrival"),
        ),
        signals=(Signal("breach", "backlog / max(backlog + agents * HANDLE, 1)"),),
    )


def test_tick_integrates_stocks_and_recomputes_signals():
    engine = WorldEngine(_pack(), EventBus())
    engine.tick(dt_hours=1.0)
    # inflow-only: backlog 0 + arrival(30) * dt(1) = 30
    assert engine.state.stocks["backlog"] == 30.0
    assert "breach" in engine.state.signals


def test_tick_publishes_world_tick_event():
    bus = EventBus()
    seen = []
    bus.on("world.tick", lambda e: seen.append(e))
    engine = WorldEngine(_pack(), bus)
    engine.tick(dt_hours=1.0)
    assert len(seen) == 1
    assert seen[0].world == "t"
    assert seen[0].stocks["backlog"] == 30.0
    assert "breach" in seen[0].signals
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/world/test_engine_tick.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.server.world.engine'`.

- [ ] **Step 3: Write minimal implementation**

Create `api/server/world/engine.py`:

```python
"""WorldEngine: owns state + runtimes; advances the world one tick.

Order per tick: reset inputs to baseline -> apply perturbations -> integrate
flows -> recompute signals -> evaluate sensors (emit) -> publish world.tick.
Actuators are bus subscribers (attached in attach()/run()), not on the tick
path — feedback is event-driven.
"""
from __future__ import annotations

import asyncio

from api.shared.events import FleetEvent
from api.server.world.contract import WorldPack
from api.server.world.state import WorldState
from api.server.world.sandbox import compile_expr
from api.server.world.integrator import integrate
from api.server.world.signals import evaluate_signals
from api.server.world.perturbations import PerturbationScheduler
from api.server.world.sensors import SensorRuntime
from api.server.world.actuators import ActuatorRuntime


class WorldEngine:
    def __init__(self, pack: WorldPack, bus, *, seed: int = 0) -> None:
        self.pack = pack
        self.bus = bus
        self.state = WorldState(pack)
        self._rate_codes = [compile_expr(f.rate, f"flow:{f.into}") for f in pack.flows]
        self._sig_codes = [compile_expr(s.formula, f"signal:{s.name}") for s in pack.signals]
        self._sensor_codes = [compile_expr(s.when, f"sensor:{s.name}") for s in pack.sensors]
        self._act_codes = [compile_expr(a.effect, f"actuator:{a.name}") for a in pack.actuators]
        self.scheduler = PerturbationScheduler(pack.perturbations, seed=seed)
        self.sensors = SensorRuntime(pack.sensors, self._sensor_codes)
        self.actuators = ActuatorRuntime(pack.actuators, self._act_codes, self.state)
        self._attached = False
        self._running = False

    def attach(self) -> None:
        if not self._attached:
            self.actuators.attach(self.bus)
            self._attached = True

    def tick(self, dt_hours: float) -> None:
        self.state.inputs = dict(self.pack.inputs)
        self.scheduler.step(self.state, dt_hours)
        integrate(self.state, self.pack.flows, self._rate_codes, dt_hours)
        self.state.signals = evaluate_signals(self.state, self.pack.signals, self._sig_codes)
        for event in self.sensors.evaluate(self.state):
            self.bus.emit(event)
        self.bus.emit(FleetEvent(
            type="world.tick",
            world=self.pack.name,
            signals=dict(self.state.signals),
            stocks=dict(self.state.stocks),
        ))

    async def run(self, *, tick_seconds: float = 1.0, dt_hours: float = 1.0,
                  max_ticks: int | None = None) -> None:
        self.attach()
        self._running = True
        count = 0
        while self._running and (max_ticks is None or count < max_ticks):
            self.tick(dt_hours)
            count += 1
            await asyncio.sleep(tick_seconds)

    def stop(self) -> None:
        self._running = False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/world/test_engine_tick.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add api/server/world/engine.py tests/api/world/test_engine_tick.py
git commit -m "feat(world): WorldEngine.tick — integrate, signal, sense, publish" -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 10: Toy pack + loader (`packs/toy/pack.py`, `loader.py`)

**Files:**
- Create: `api/server/world/packs/__init__.py`
- Create: `api/server/world/packs/toy/__init__.py`
- Create: `api/server/world/packs/toy/pack.py`
- Create: `api/server/world/loader.py`
- Test: `tests/api/world/test_loader.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/world/test_loader.py`:

```python
import pytest
from api.server.world.loader import world_enabled, active_world_name, load_pack


def test_flag_helpers_read_env(monkeypatch):
    monkeypatch.delenv("ZAVA_WORLD", raising=False)
    assert world_enabled() is False
    assert active_world_name() is None
    monkeypatch.setenv("ZAVA_WORLD", "toy")
    assert world_enabled() is True
    assert active_world_name() == "toy"


def test_loads_toy_pack_by_name():
    pack = load_pack("toy")
    assert pack.name == "toy"
    names = {s.name for s in pack.stocks}
    assert "support_backlog" in names
    assert any(sensor.emit == "ops.surge_staffing.requested" for sensor in pack.sensors)


def test_unknown_pack_raises():
    with pytest.raises(Exception):
        load_pack("does_not_exist")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/world/test_loader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.server.world.loader'`.

- [ ] **Step 3: Write minimal implementation**

Create `api/server/world/packs/__init__.py`:

```python
"""World packs — one sub-package per pluggable industry world."""
```

Create `api/server/world/packs/toy/__init__.py`:

```python
"""Neutral toy pack — the engine's permanent industry-independent guard."""
```

Create `api/server/world/packs/toy/pack.py`:

```python
"""Support-queue toy world: the minimal neutral pack exercising every primitive.

Baseline arrival (30/h) < capacity (20 agents * 2/h = 40/h) so the backlog
drains. A manual `demand_surge` (+60/h for 3 ticks) pushes arrival past
capacity, backlog climbs, the breach signal crosses 0.5, the sensor emits
`ops.surge_staffing.requested`; a responder completing `surge-staffing.completed`
with `hired` feeds the actuator, raising agent capacity.
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
        Flow(into="support_backlog", rate="ticket_arrival_rate"),
        Flow(into="support_backlog", rate="-(agents * HANDLE)"),
    ),
    signals=(
        Signal("sla_breach_pct",
               "support_backlog / max(support_backlog + agents * HANDLE, 1)"),
    ),
    perturbations=(
        Perturbation("demand_surge", target="ticket_arrival_rate",
                     magnitude=60.0, schedule="manual", duration_ticks=3),
    ),
    sensors=(
        Sensor("backlog_high", when="sla_breach_pct > 0.5",
               emit="ops.surge_staffing.requested", cooldown_ticks=5),
    ),
    actuators=(
        Actuator("hire", on="surge-staffing.completed",
                 target="agents", effect="event.get('hired', 0)"),
    ),
)
```

Create `api/server/world/loader.py`:

```python
"""Pack discovery + the ZAVA_WORLD flag."""
from __future__ import annotations

import importlib
import os

from api.server.world.contract import WorldPack


def active_world_name() -> str | None:
    return os.getenv("ZAVA_WORLD") or None


def world_enabled() -> bool:
    return active_world_name() is not None


def load_pack(name: str) -> WorldPack:
    module = importlib.import_module(f"api.server.world.packs.{name}.pack")
    pack = getattr(module, "PACK", None)
    if not isinstance(pack, WorldPack):
        raise RuntimeError(f"world pack {name!r} does not expose a PACK: WorldPack")
    return pack
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/world/test_loader.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add api/server/world/packs api/server/world/loader.py tests/api/world/test_loader.py
git commit -m "feat(world): neutral toy pack + ZAVA_WORLD pack loader" -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 11: Full closed-loop end-to-end (over the real bus)

Proves the whole spec loop with zero `app_state` dependency: perturbation → stock change → signal crosses → sensor emits → stub responder completes → actuator restores capacity → backlog drains.

**Files:**
- Test: `tests/api/world/test_engine_loop_e2e.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/world/test_engine_loop_e2e.py`:

```python
from api.server.services.event_bus import EventBus
from api.shared.events import FleetEvent
from api.server.world.engine import WorldEngine
from api.server.world.loader import load_pack


def test_closed_loop_surge_triggers_hiring_then_backlog_recovers():
    bus = EventBus()
    fired = []
    bus.on("ops.surge_staffing.requested", lambda e: fired.append(e))

    # Stub responder: on a surge request, "hire" 60 more agent-capacity.
    bus.on("ops.surge_staffing.requested",
           lambda e: bus.emit(FleetEvent(type="surge-staffing.completed", hired=60)))

    engine = WorldEngine(load_pack("toy"), bus)
    engine.attach()

    # Baseline: arrival(30) < capacity(40); backlog stays ~0.
    for _ in range(3):
        engine.tick(dt_hours=1.0)
    assert engine.state.stocks["support_backlog"] == 0.0
    assert fired == []

    # Inject the surge: arrival jumps to 90/h for 3 ticks -> backlog climbs.
    engine.scheduler.inject("demand_surge")
    for _ in range(4):
        engine.tick(dt_hours=1.0)

    # The sensor fired and the actuator raised capacity above the original 20.
    assert len(fired) >= 1
    assert engine.state.resources["agents"] >= 80.0  # 20 + 60 hired

    # With extra capacity, the backlog drains back down.
    for _ in range(10):
        engine.tick(dt_hours=1.0)
    assert engine.state.stocks["support_backlog"] == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/world/test_engine_loop_e2e.py -v`
Expected: FAIL initially only if earlier tasks are incomplete; with Tasks 1–10 done it should PASS. If it FAILS, read the assertion and fix the responsible module (do not weaken the test). Treat a genuine failure here as a real defect in the loop.

- [ ] **Step 3: (No new implementation)**

This task is an integration guard over existing modules. If Step 2 passed, proceed. If it failed, diagnose against Tasks 6–10.

- [ ] **Step 4: Run the whole world suite**

Run: `uv run pytest tests/api/world -v`
Expected: PASS (all world tests green).

- [ ] **Step 5: Commit**

```bash
git add tests/api/world/test_engine_loop_e2e.py
git commit -m "test(world): closed-loop e2e — surge -> sensor -> hire -> recovery" -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 12: Lifespan wiring behind `ZAVA_WORLD`

Adds `maybe_start_world(bus)` and calls it from the FastAPI lifespan so the engine starts only when the flag is set, and is cancelled cleanly on shutdown.

**Files:**
- Modify: `api/server/world/__init__.py`
- Modify: `api/server/main.py` (lifespan startup near the `ramp_task` creation ~line 175; shutdown cancel loop ~line 360)
- Test: `tests/api/world/test_wiring.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/world/test_wiring.py`:

```python
import asyncio
import pytest
from api.server.services.event_bus import EventBus
from api.server.world import maybe_start_world


@pytest.mark.asyncio
async def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ZAVA_WORLD", raising=False)
    task = maybe_start_world(EventBus())
    assert task is None


@pytest.mark.asyncio
async def test_starts_engine_when_flag_set(monkeypatch):
    monkeypatch.setenv("ZAVA_WORLD", "toy")
    bus = EventBus()
    ticks = []
    bus.on("world.tick", lambda e: ticks.append(e))
    task = maybe_start_world(bus, tick_seconds=0.0, dt_hours=1.0, max_ticks=2)
    assert task is not None
    await task                      # runs 2 ticks then completes
    assert len(ticks) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/world/test_wiring.py -v`
Expected: FAIL — `ImportError: cannot import name 'maybe_start_world'`.

- [ ] **Step 3: Write minimal implementation**

Replace the contents of `api/server/world/__init__.py` with:

```python
"""Generic organisational world-simulator engine (spec 2026-07-10).

Industry-agnostic: all nouns come from a WorldPack. See contract.py.
`maybe_start_world` is the single lifespan entry point.
"""
from __future__ import annotations

import asyncio

from api.server.world.loader import world_enabled, active_world_name, load_pack
from api.server.world.engine import WorldEngine


def maybe_start_world(bus, **run_kwargs) -> "asyncio.Task | None":
    """Start the world engine iff ZAVA_WORLD is set; else return None.

    `run_kwargs` are forwarded to WorldEngine.run (tick_seconds, dt_hours,
    max_ticks) — tests pass max_ticks to make the loop finite.
    """
    if not world_enabled():
        return None
    engine = WorldEngine(load_pack(active_world_name()), bus)
    return asyncio.create_task(engine.run(**run_kwargs))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/world/test_wiring.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Wire it into the FastAPI lifespan**

In `api/server/main.py`, find the ramp-loop startup (around line 175):

```python
    ramp_task = asyncio.create_task(simulator_orchestrator.ramp_loop())
```

Add immediately after it:

```python
    # World simulator engine — off unless ZAVA_WORLD is set (spec 2026-07-10).
    from api.server.world import maybe_start_world
    world_task = maybe_start_world(app_state.bus)
    if world_task is not None:
        print(f"[server] world engine ON (ZAVA_WORLD={os.getenv('ZAVA_WORLD')})")
```

Then find the shutdown cancel loop (around line 360):

```python
        for t in (ramp_task, seed_task, dream_cadence_task):
```

Change it to include `world_task`:

```python
        for t in (ramp_task, seed_task, dream_cadence_task, world_task):
```

- [ ] **Step 6: Verify the app still imports and the flag-off default holds**

Run: `uv run python -c "import api.server.main"`
Expected: no error (module imports; with `ZAVA_WORLD` unset the engine does not start).

Run: `uv run pytest tests/api/world -q`
Expected: PASS (entire world suite green).

- [ ] **Step 7: Commit**

```bash
git add api/server/world/__init__.py api/server/main.py tests/api/world/test_wiring.py
git commit -m "feat(world): start engine in FastAPI lifespan behind ZAVA_WORLD flag" -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

## Final verification

- [ ] **Run the full world suite**

Run: `uv run pytest tests/api/world -v`
Expected: all tests pass.

- [ ] **Run the broader suite to confirm no regressions**

Run: `uv run pytest -q`
Expected: no new failures attributable to `api/server/world` or the `main.py` edit (the engine is off by default, so existing behaviour is unchanged).

- [ ] **Lint the new package**

Run: `uv run ruff check api/server/world`
Expected: clean (or only pre-existing repo-wide advisories).

---

## What this plan deliberately does NOT cover (follow-on plans)

- **M4 — the minimal telco slice** (`world/packs/telco/`): its stocks/signals/sensors/actuators plus the response-half domains/personae/projections authored via `compose-domain`. Gets its own plan once this engine API is real (spec §11.1).
- **M5 — the cosmic-lens `world.tick` signals stream**: the SSE channel + lens rendering. Separate plan.
- **Cron-scheduled perturbations, time-series history store, and the two-tier (reaction vs Durable) work router** — spec §12 open questions; deferred until a pack needs them.
