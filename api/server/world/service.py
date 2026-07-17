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
from pathlib import Path
from typing import Any

from api.server.services.event_bus import EventBus
from api.server.world.commands import CommandGateway
from api.server.world.evaluations import OutcomeEvaluator
from api.server.world.model import Objective, SimulationCommand, SimulationEvent
from api.server.world.objectives import TERMINAL_STATUSES, ObjectiveManager
from api.server.world.registry import resolve_world_pack
from api.server.world.runtime import SimulationRuntime
from api.shared.events import FleetEvent
from api.shared.vertical_loader import active_runtime, build_runtime
from api.shared.vertical_pack import VerticalRuntime
from api.shared.world_contracts import ObjectiveRoute, WorldPackRegistration


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
        vertical_runtime: VerticalRuntime,
        registration: WorldPackRegistration,
        scale_name: str,
        minutes_per_second: float | None = None,
    ) -> None:
        self.bus = bus
        self.vertical_runtime = vertical_runtime
        self.registration = registration
        self.scenario_name = registration.name
        self.scale_name = scale_name
        scale = registration.scales[scale_name]
        self._build_scenario = scale.build_scenario
        self._stop_requested = False
        self.minutes_per_second = _require_finite_positive(
            scale.default_minutes_per_second
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
        runtime = active_runtime()
        return cls.for_runtime(
            runtime,
            seed=seed,
            bus=bus,
            speed=speed,
            world_name=name,
        )

    @classmethod
    def for_runtime(
        cls,
        runtime: VerticalRuntime,
        *,
        seed: int,
        bus: EventBus,
        speed: float | None = None,
        world_name: str | None = None,
    ) -> ActorWorldService:
        name = world_name or runtime.world_name
        if name is None:
            raise ValueError(
                f"vertical {runtime.pack.name!r} has no active world"
            )
        registration = resolve_world_pack(runtime, name)
        scale_name = (
            runtime.world_scale_name or registration.default_scale
        )
        return cls(
            seed=seed,
            bus=bus,
            vertical_runtime=runtime,
            registration=registration,
            scale_name=scale_name,
            minutes_per_second=speed,
        )

    @classmethod
    def support(
        cls, seed: int, bus: EventBus, minutes_per_second: float = 10
    ) -> ActorWorldService:
        """Thin compatibility wrapper: build the live support world."""
        runtime = build_runtime(
            {"ZAVA_WORLD": "support"},
            data_root=Path("."),
        )
        return cls.for_runtime(
            runtime,
            seed=seed,
            bus=bus,
            speed=minutes_per_second,
        )

    @classmethod
    def telco(
        cls, seed: int, bus: EventBus, minutes_per_second: float = 10
    ) -> ActorWorldService:
        """Thin compatibility wrapper: build the live telco world."""
        runtime = build_runtime(
            {"ZAVA_VERTICAL": "telco"},
            data_root=Path("."),
        )
        return cls.for_runtime(
            runtime,
            seed=seed,
            bus=bus,
            speed=minutes_per_second,
        )

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
        self.objectives = ObjectiveManager(runtime)
        self.evaluator = OutcomeEvaluator(runtime, self.objectives)
        self.commands = CommandGateway(
            runtime, self.objectives, scenario.apply_command, self.evaluator
        )
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

    def inject_capacity_pressure(
        self, site_id: str, *, utilization: float = 0.95
    ) -> str:
        """Constrain one healthy Telco site's real capacity for exception proof."""
        inject = getattr(self.scenario, "inject_capacity_pressure", None)
        if inject is None:
            raise ValueError(
                f"scenario {self.scenario_name!r} has no capacity pressure"
            )
        result = inject(site_id, utilization=utilization)
        self._publish_new()
        return result

    def submit_service_order(
        self, *, account_id: str, product: str, requested_site_id: str
    ) -> str:
        submit = getattr(self.scenario, "submit_service_order", None)
        if submit is None:
            raise ValueError(f"scenario {self.scenario_name!r} has no service orders")
        result = submit(
            account_id=account_id,
            product=product,
            requested_site_id=requested_site_id,
        )
        self._publish_new()
        return result

    def _require_scenario_method(self, name: str):
        """Return a scenario method or raise a clear error for unsupported
        worlds (e.g. calling a telco-only injector against the support
        world)."""
        method = getattr(self.scenario, name, None)
        if method is None:
            raise ValueError(f"scenario {self.scenario_name!r} has no {name}")
        return method

    def inject_weather_risk(
        self, region: str, severity: float, duration_minutes: float
    ) -> str:
        """Inject a regional weather risk event (telco scenario). Returns the
        weather event id."""
        inject = self._require_scenario_method("inject_weather_risk")
        result = inject(region, severity, duration_minutes)
        self._publish_new()
        return result

    def inject_spare_shortage(self, region: str, part_kind: str) -> str:
        """Zero out one region's spare stock for a part kind (telco
        scenario). Returns the spare stock id."""
        inject = self._require_scenario_method("inject_spare_shortage")
        result = inject(region, part_kind)
        self._publish_new()
        return result

    def inject_technician_unavailable(self, technician_id: str) -> str:
        """Mark one technician unavailable (telco scenario). Returns the
        technician id."""
        inject = self._require_scenario_method("inject_technician_unavailable")
        result = inject(technician_id)
        self._publish_new()
        return result

    def run_scenario(self, name: str) -> dict[str, Any]:
        run = self._require_scenario_method("run_scenario")
        result = run(name)
        self._publish_new()
        return result

    def run_reference_process(self, workflow_type: str) -> dict[str, Any]:
        run = self._require_scenario_method("run_reference_process")
        result = run(workflow_type)
        self._publish_new()
        return result

    # -- catch-up ---------------------------------------------------------

    def events_after(self, seq: int) -> list[dict[str, Any]]:
        start = max(seq, 0)
        return [event.to_dict() for event in self.runtime.journal[start:]]

    def _publish_new(self) -> None:
        self._publish_since(self._published_seq)

    def _publish_since(self, start: int) -> None:
        index = start
        while index < len(self.runtime.journal):
            event = self.runtime.journal[index]
            self.evaluator.observe((event,))
            self._publish(event)
            index += 1
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
        base["objectives"] = [objective.to_dict() for objective in self.objectives.all()]
        base["evaluations"] = [evaluation.to_dict() for evaluation in self.evaluator.evaluations]
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

    def apply_typed_command(
        self, objective: Objective, command: SimulationCommand
    ) -> SimulationEvent:
        """Apply a typed command through the gateway under its claimed objective."""
        start = len(self.runtime.journal)
        result = self.commands.apply(objective, command)
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

    # -- objective surface -------------------------------------------------

    def open_objective(
        self,
        sensor_event: dict[str, Any],
        route: ObjectiveRoute,
        *,
        owner_function: str,
        priority: int = 0,
        deadline: float | None = None,
    ) -> Objective:
        """Open (or return the existing active) objective for this world's pack."""
        start = len(self.runtime.journal)
        objective = self.objectives.open(
            sensor_event,
            route,
            owner_function=owner_function,
            priority=priority,
            deadline=deadline,
        )
        self._publish_since(start)
        return objective

    def transition_objective(self, objective_id: str, to_status: str, **kwargs: Any) -> Objective:
        """Transition an objective and publish the journalled lifecycle event."""
        start = len(self.runtime.journal)
        objective = self.objectives.transition(objective_id, to_status, **kwargs)
        self._publish_since(start)
        return objective

    def fail_objective(self, objective_id: str, **kwargs: Any) -> Objective | None:
        """Fail an active objective; no-op if it is unknown or already terminal."""
        objective = self.objectives.get(objective_id)
        if objective is None or objective.status in TERMINAL_STATUSES:
            return objective
        return self.transition_objective(objective_id, "failed", **kwargs)
