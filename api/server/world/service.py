"""ActorWorldService: a focused async adapter over SimulationRuntime/SupportScenario.

Owns one authoritative actor world, paces SimPy one event at a time inside an
asyncio task, and publishes journal events to the EventBus and to bounded
subscriber queues. Provides the read surfaces (snapshot/events_after/
build_observation) and write surfaces (apply_command/record_external) the
world bridge, routes and Durable responder need, plus playback controls
(pause/resume/stop/step_once/set_speed/restart/inject_demand_surge).

Single-threaded asyncio only: every method is synchronous and runs to
completion atomically except `run()`, whose loop is the sole place that
awaits between events; `step_once()` is `async` only so callers have one
consistent single-step awaitable, but it never yields internally. No locks
or threads are needed.
"""
from __future__ import annotations

import asyncio
import math
from dataclasses import asdict
from typing import Any

from api.server.services.event_bus import EventBus
from api.server.world.model import SimulationCommand, SimulationEvent
from api.server.world.packs.support import DemandSurge, SupportConfig, SupportScenario, Worker
from api.server.world.projection import project_support
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
        config: SupportConfig,
        bus: EventBus,
        minutes_per_second: float = 10,
    ) -> None:
        self.config = config
        self.bus = bus
        self.scenario_name = "support"
        self._subscribers: list[asyncio.Queue[dict[str, Any]]] = []
        self._paused = False
        self._stop_requested = False
        self.set_speed(minutes_per_second)
        self.seed = seed
        self.runtime, self.scenario = self._install(seed)

    @classmethod
    def support(
        cls, seed: int, bus: EventBus, minutes_per_second: float = 10
    ) -> ActorWorldService:
        """Build the live support-scenario proof world with its exact config."""
        config = SupportConfig(
            customer_count=1_000,
            worker_count=40,
            reserve_worker_count=10,
            arrival_rate_per_hour=90,
            simulation_minutes=480,
            sla_minutes=30,
            sensor_backlog_threshold=25,
            sensor_recovery_threshold=10,
        )
        return cls(seed=seed, config=config, bus=bus, minutes_per_second=minutes_per_second)

    def _install(self, seed: int) -> tuple[SimulationRuntime, SupportScenario]:
        """Build and install a fresh runtime/scenario; reset the publish cursor.

        Customer/worker installation events land in the journal directly (not
        via SimPy steps) so they are catch-up/snapshot-only: `_published_seq`
        is set past them here, before anything is ever published, so they are
        never blasted onto the EventBus on startup.
        """
        runtime = SimulationRuntime(seed)
        scenario = SupportScenario(runtime, self.config)
        scenario.install()
        self._published_seq = len(runtime.journal)
        return runtime, scenario

    @property
    def status(self) -> str:
        if self.runtime.status == "completed":
            return "completed"
        if self._stop_requested:
            return "stopped"
        if self._paused:
            return "paused"
        return "running"

    # -- playback ------------------------------------------------------------

    async def run(self) -> None:
        """Pace the SimPy env one event at a time until stop() or completion.

        Wall delay between events is the positive logical time delta divided
        by `minutes_per_second`. Same-time events (delta == 0) still yield to
        asyncio so pause()/stop() called from another task are observed
        promptly instead of starving the event loop.
        """
        self._stop_requested = False
        while not self._stop_requested:
            if self._paused:
                await asyncio.sleep(0.05)
                continue
            if self.runtime.status == "completed":
                break
            before = self.runtime.now
            await self.step_once()
            delta = self.runtime.now - before
            if delta > 0:
                await asyncio.sleep(delta / self.minutes_per_second)
            else:
                await asyncio.sleep(0)

    async def step_once(self) -> None:
        """Execute exactly one SimPy env event and publish anything new."""
        self.runtime.step()
        self._publish_new()

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def stop(self) -> None:
        self._stop_requested = True

    def set_speed(self, value: float) -> None:
        self.minutes_per_second = _require_finite_positive(value, label="minutes_per_second")

    def restart(self, seed: int | None = None) -> None:
        """Rebuild runtime/scenario with the same config; only while paused."""
        if not self._paused:
            raise RuntimeError("restart is only allowed while the world is paused")
        self.seed = self.seed if seed is None else seed
        self._stop_requested = False
        self.runtime, self.scenario = self._install(self.seed)

    def inject_demand_surge(self, multiplier: float, duration_minutes: float) -> None:
        multiplier = _require_finite_positive(multiplier, label="multiplier", floor=1.0)
        duration_minutes = _require_finite_positive(duration_minutes, label="duration_minutes")
        surge = DemandSurge(
            at_minute=self.runtime.now,
            multiplier=multiplier,
            duration_minutes=duration_minutes,
        )
        self.scenario.schedule_surge(surge)

    # -- catch-up + live subscription -----------------------------------------

    def events_after(self, seq: int) -> list[dict[str, Any]]:
        start = max(seq, 0)
        return [event.to_dict() for event in self.runtime.journal[start:]]

    def subscribe(self, maxsize: int = 1000) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=maxsize)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)

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
        payload = event.to_dict()
        for queue in self._subscribers:
            self._enqueue(queue, payload)

    @staticmethod
    def _enqueue(queue: asyncio.Queue[dict[str, Any]], payload: dict[str, Any]) -> None:
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            queue.put_nowait(payload)

    # -- read surfaces ---------------------------------------------------------

    @staticmethod
    def _customer_wire(d: dict[str, Any]) -> dict[str, Any]:
        d["active_ticket_ids"] = sorted(d["active_ticket_ids"])
        return d

    @staticmethod
    def _worker_wire(d: dict[str, Any]) -> dict[str, Any]:
        d["skills"] = list(d["skills"])
        return d

    def snapshot(self) -> dict[str, Any]:
        scenario = self.scenario
        return {
            "enabled": True,
            "scenario": self.scenario_name,
            "seed": self.seed,
            "status": self.status,
            "sim_time": self.runtime.now,
            "speed": self.minutes_per_second,
            "latest_seq": len(self.runtime.journal),
            "projection": asdict(project_support(scenario)),
            "customers": [self._customer_wire(asdict(c)) for c in scenario.customers.values()],
            "tickets": [asdict(ticket) for ticket in scenario.tickets.values()],
            "workers": [self._worker_wire(asdict(w)) for w in scenario.workers.values()],
            "teams": [asdict(team) for team in scenario.teams.values()],
        }

    def build_observation(self, sensor_event: dict[str, Any]) -> dict[str, Any]:
        payload = sensor_event.get("payload") or {}
        actor_ids = payload.get("actor_ids") or []
        queued_tickets = []
        for ticket_id in actor_ids:
            ticket = self.scenario.tickets.get(ticket_id)
            if ticket is None:
                continue
            queued_tickets.append(
                {
                    "id": ticket.id,
                    "customer_id": ticket.customer_id,
                    "severity": ticket.severity,
                    "required_skill": ticket.required_skill,
                    "status": ticket.status,
                    "queued_at": ticket.queued_at,
                    "sla_deadline": ticket.sla_deadline,
                    "wait_minutes": self.runtime.now - ticket.queued_at,
                }
            )

        def worker_view(worker: Worker) -> dict[str, Any]:
            return {
                "id": worker.id,
                "skills": list(worker.skills),
                "status": worker.status,
                "team_id": worker.team_id,
                "current_ticket_id": worker.current_ticket_id,
            }

        support_workers = [
            worker_view(worker)
            for worker in self.scenario.workers.values()
            if worker.team_id == "TEAM-SUPPORT"
        ]
        reserve_workers = [
            worker_view(worker)
            for worker in self.scenario.workers.values()
            if worker.team_id == "TEAM-RESERVE"
        ]

        return {
            "trace_id": sensor_event.get("trace_id"),
            "sensor_event_id": sensor_event.get("event_id"),
            "queued_tickets": queued_tickets,
            "support_workers": support_workers,
            "reserve_workers": reserve_workers,
            "projection": asdict(project_support(self.scenario)),
            "allowed_commands": ["reallocate_workers"],
        }

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
