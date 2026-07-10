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
