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
