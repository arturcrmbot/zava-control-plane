"""ActorWorldService: a focused async adapter over SimulationRuntime scenarios.

Owns one authoritative actor world (support *or* telco), paces SimPy one event
at a time inside an asyncio task, and publishes journal events to the EventBus.
Provides the read surfaces (snapshot/events_after/build_observation) and write
surfaces (apply_command/record_external) the world bridge, routes and Durable
responder need, plus the scenario perturbation injectors.

The service is scenario-agnostic: it holds a :class:`WorldPackRegistration`
(``build_scenario`` factory, ``scenario_name``, objective/command vocabulary)
and delegates every scenario-specific projection to the scenario object
(``render_state`` / ``build_observation``). The registration is resolved from
the static world-pack registry via ``for_world`` (``.support()`` / ``.telco()``
are thin wrappers). Exactly one scenario is live per process, selected in
``main.py`` via ``ZAVA_WORLD``.

Single-threaded asyncio only: every method is synchronous and runs to
completion atomically except `run()`, which is the sole place that awaits
between events. No locks or threads are needed.
"""
from __future__ import annotations

import asyncio
import math
from typing import Any

from api.server.services.event_bus import EventBus
from api.server.world.model import SimulationCommand, SimulationEvent
from api.server.world.registry import WorldPackRegistration, resolve_world_pack
from api.server.world.runtime import SimulationRuntime
from api.shared.events import FleetEvent


def _require_finite_positive(value: Any, *, label: str, floor: float = 0.0) -> float:
    """Validate a numeric control input; returns the float on success."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    if not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    if value <= floor:
        raise ValueError(f"{label} must be greater than {floor}")
    return float(value)


class ActorWorldService:
    """Live pacing + publication authority for one actor world."""

    def __init__(
        self,
        *,
        seed: int,
        bus: EventBus,
        registration: WorldPackRegistration,
        minutes_per_second: float | None = None,
    ) -> None:
        self.bus = bus
        self.registration = registration
        self.scenario_name = registration.name
        self._build_scenario = registration.build_scenario
        self._stop_requested = False
        self.minutes_per_second = _require_finite_positive(
            registration.default_minutes_per_second
            if minutes_per_second is None
            else minutes_per_second,
            label="minutes_per_second",
        )
        self.seed = seed
        self.runtime, self.scenario = self._install(seed)

    @classmethod
    def for_world(
        cls,
        name: str,
        seed: int,
        bus: EventBus,
        speed: float | None = None,
    ) -> ActorWorldService:
        """Build the live world registered under ``name`` (``support``/``telco``).

        ``speed`` overrides the registration's ``default_minutes_per_second``;
        ``None`` keeps the registered default. Unknown names raise ``ValueError``.
        """
        return cls(
            seed=seed,
            bus=bus,
            registration=resolve_world_pack(name),
            minutes_per_second=speed,
        )

    @classmethod
    def support(
        cls, seed: int, bus: EventBus, minutes_per_second: float = 10
    ) -> ActorWorldService:
        """Thin compatibility wrapper: build the live support world."""
        return cls.for_world("support", seed, bus, speed=minutes_per_second)

    @classmethod
    def telco(
        cls, seed: int, bus: EventBus, minutes_per_second: float = 10
    ) -> ActorWorldService:
        """Thin compatibility wrapper: build the live telco world."""
        return cls.for_world("telco", seed, bus, speed=minutes_per_second)

    def _install(self, seed: int) -> tuple[SimulationRuntime, Any]:
        """Build and install a fresh runtime/scenario; reset the publish cursor.

        Installation events (actor creation) land in the journal directly (not
        via SimPy steps) so they are catch-up/snapshot-only: `_published_seq`
        is set past them here, before anything is ever published, so they are
        never blasted onto the EventBus on startup.
        """
        runtime = SimulationRuntime(seed)
        scenario = self._build_scenario(runtime)
        scenario.install()
        self._published_seq = len(runtime.journal)
        return runtime, scenario

    @property
    def status(self) -> str:
        if self.runtime.status == "completed":
            return "completed"
        if self._stop_requested:
            return "stopped"
        return "running"

    # -- playback ------------------------------------------------------------

    async def run(self) -> None:
        """Pace the SimPy env one event at a time until stop() or completion.

        Wall delay between events is the positive logical time delta divided
        by `minutes_per_second`. Same-time events (delta == 0) still yield to
        asyncio so stop() called from another task is observed promptly
        instead of starving the event loop.
        """
        self._stop_requested = False
        while not self._stop_requested:
            if self.runtime.status == "completed":
                break
            before = self.runtime.now
            self._step_once()
            delta = self.runtime.now - before
            await asyncio.sleep(max(0, delta / self.minutes_per_second))

    def _step_once(self) -> None:
        """Execute exactly one SimPy env event and publish anything new."""
        self.runtime.step()
        self._publish_new()

    def stop(self) -> None:
        self._stop_requested = True

    def inject_demand_surge(self, multiplier: float, duration_minutes: float) -> None:
        multiplier = _require_finite_positive(multiplier, label="multiplier", floor=1.0)
        duration_minutes = _require_finite_positive(duration_minutes, label="duration_minutes")
        from api.server.world.packs.support import DemandSurge

        surge = DemandSurge(
            at_minute=self.runtime.now,
            multiplier=multiplier,
            duration_minutes=duration_minutes,
        )
        self.scenario.schedule_surge(surge)

    def inject_site_failure(self, site_id: str | None = None) -> str:
        """Fail one real cell site (telco scenario). Returns the resolved ID."""
        inject = getattr(self.scenario, "inject_site_failure", None)
        if inject is None:
            raise ValueError(f"scenario {self.scenario_name!r} has no site_failure")
        return inject(site_id)

    # -- catch-up ---------------------------------------------------------

    def events_after(self, seq: int) -> list[dict[str, Any]]:
        start = max(seq, 0)
        return [event.to_dict() for event in self.runtime.journal[start:]]

    def _publish_new(self) -> None:
        self._publish_since(self._published_seq)

    def _publish_since(self, start: int) -> None:
        for event in self.runtime.journal[start:]:
            self._publish(event)
        self._published_seq = len(self.runtime.journal)

    def _publish(self, event: SimulationEvent) -> None:
        self.bus.emit(
            FleetEvent(
                type=f"world.{event.type}",
                simulation_event=event.to_dict(),
                trace_id=event.trace_id,
            )
        )

    # -- read surfaces ---------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        base = {
            "enabled": True,
            "scenario": self.scenario_name,
            "seed": self.seed,
            "status": self.status,
            "sim_time": self.runtime.now,
            "speed": self.minutes_per_second,
            "latest_seq": len(self.runtime.journal),
        }
        base.update(self.scenario.render_state())
        return base

    def build_observation(self, sensor_event: dict[str, Any]) -> dict[str, Any]:
        return self.scenario.build_observation(sensor_event, now=self.runtime.now)

    # -- write surfaces ----------------------------------------------------

    def apply_command(self, command: SimulationCommand) -> SimulationEvent:
        start = len(self.runtime.journal)
        result = self.scenario.apply_command(command)
        self._publish_since(start)
        return result

    def record_external(
        self,
        event_type: str,
        *,
        trace_id: str,
        cause_event_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> SimulationEvent:
        start = len(self.runtime.journal)
        event = self.runtime.emit(
            event_type,
            cause_event_id=cause_event_id,
            trace_id=trace_id,
            payload=payload,
        )
        self._publish_since(start)
        return event
