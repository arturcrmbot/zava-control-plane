"""Explicit-actor support-world scenario running on SimulationRuntime."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

import simpy

from api.server.world.model import SimulationCommand, SimulationEvent
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
    reserve_worker_count: int = 0
    arrival_rate_per_hour: float = 60.0
    simulation_minutes: float = 480.0
    sla_minutes: float = 30.0
    sensor_backlog_threshold: int = 25
    sensor_recovery_threshold: int = 10


class SupportScenario:
    def __init__(self, runtime: SimulationRuntime, config: SupportConfig) -> None:
        if not 0 <= config.reserve_worker_count < config.worker_count:
            raise ValueError(
                "reserve_worker_count must satisfy "
                "0 <= reserve_worker_count < worker_count"
            )
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
        self._sensor_latched = False
        self.queued_ticket_ids: dict[str, None] = {}
        self.worker_processes: dict[str, simpy.Process] = {}
        self.applied_commands: dict[str, SimulationEvent] = {}

    def install(self) -> None:
        self.runtime.emit(
            "simulation.started",
            actor_id="scenario:support",
            payload={"seed": self.runtime.seed, "config": asdict(self.config)},
        )
        self._create_customers()
        self._create_workers()
        for worker in self.workers.values():
            if worker.team_id == "TEAM-SUPPORT":
                self._start_worker(worker)
        self.runtime.process(self._arrival_loop())
        self.runtime.process(self._sensor_loop())

    def schedule_surge(self, surge: DemandSurge) -> None:
        self.runtime.process(self._surge_process(surge))

    def apply_command(self, command: SimulationCommand) -> SimulationEvent:
        existing = self.applied_commands.get(command.command_id)
        if existing is not None:
            return existing
        if command.type != "reallocate_workers":
            return self._reject_command(
                command, f"unsupported command type: {command.type!r}"
            )
        reason = self._validate_reallocate_workers(command.payload)
        if reason is not None:
            return self._reject_command(command, reason)
        return self._accept_reallocate_workers(command)

    def _validate_reallocate_workers(self, payload: dict[str, Any]) -> str | None:
        worker_ids = payload.get("worker_ids")
        if not isinstance(worker_ids, list) or not worker_ids:
            return "worker_ids must be a non-empty list"
        if not all(isinstance(worker_id, str) for worker_id in worker_ids):
            return "worker_ids must contain only string worker IDs"
        if len(set(worker_ids)) != len(worker_ids):
            return "worker_ids must be unique"

        if payload.get("from_team_id") != "TEAM-RESERVE":
            return "from_team_id must be TEAM-RESERVE"
        if payload.get("to_team_id") != "TEAM-SUPPORT":
            return "to_team_id must be TEAM-SUPPORT"

        duration_minutes = payload.get("duration_minutes")
        if isinstance(duration_minutes, bool) or not isinstance(duration_minutes, (int, float)):
            return "duration_minutes must be numeric"
        if not math.isfinite(duration_minutes):
            return "duration_minutes must be finite"
        if duration_minutes <= 0:
            return "duration_minutes must be greater than zero"

        for worker_id in worker_ids:
            worker = self.workers.get(worker_id)
            if worker is None:
                return f"unknown worker_id: {worker_id}"
            if worker.team_id != "TEAM-RESERVE":
                return f"worker {worker_id} is not in TEAM-RESERVE"
            if worker.status != "reserve":
                return f"worker {worker_id} is not reserve status"
        return None

    def _reject_command(self, command: SimulationCommand, reason: str) -> SimulationEvent:
        rejected = self.runtime.emit(
            "command.rejected",
            actor_id=command.issued_by,
            target_id="TEAM-SUPPORT",
            trace_id=command.trace_id,
            payload={"command": command.to_dict(), "reason": reason},
        )
        self.applied_commands[command.command_id] = rejected
        return rejected

    def _accept_reallocate_workers(self, command: SimulationCommand) -> SimulationEvent:
        payload = command.payload
        worker_ids: list[str] = list(payload["worker_ids"])
        from_team_id = payload["from_team_id"]
        to_team_id = payload["to_team_id"]
        duration_minutes = payload["duration_minutes"]

        accepted = self.runtime.emit(
            "command.accepted",
            actor_id=command.issued_by,
            target_id="TEAM-SUPPORT",
            trace_id=command.trace_id,
            payload={"command": command.to_dict()},
        )
        self.applied_commands[command.command_id] = accepted

        from_team = self.teams[from_team_id]
        to_team = self.teams[to_team_id]
        for worker_id in worker_ids:
            worker = self.workers[worker_id]
            if worker_id in from_team.worker_ids:
                from_team.worker_ids.remove(worker_id)
            to_team.worker_ids.append(worker_id)
            worker.team_id = to_team_id
            worker.status = "idle"
            reallocated = self.runtime.emit(
                "worker.reallocated",
                actor_id=worker_id,
                target_id=to_team_id,
                cause_event_id=accepted.event_id,
                trace_id=command.trace_id,
                payload={
                    "command_id": command.command_id,
                    "from_team_id": from_team_id,
                    "to_team_id": to_team_id,
                    "duration_minutes": duration_minutes,
                },
            )
            self._start_worker(worker)
            self.runtime.process(
                self._return_worker_after(worker, duration_minutes, reallocated)
            )
        return accepted

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
        support_team = Team(id="TEAM-SUPPORT", name="Customer Support")
        reserve_team = Team(id="TEAM-RESERVE", name="Reserve")
        self.teams[support_team.id] = support_team
        self.teams[reserve_team.id] = reserve_team
        support_count = self.config.worker_count - self.config.reserve_worker_count
        for index in range(1, self.config.worker_count + 1):
            primary = SKILLS[(index - 1) % len(SKILLS)]
            skills: tuple[Skill, ...]
            if index % 5 == 0:
                skills = SKILLS
            else:
                skills = (primary,)
            is_reserve = index > support_count
            team = reserve_team if is_reserve else support_team
            worker = Worker(
                id=f"WRK-{index:04d}",
                team_id=team.id,
                skills=skills,
                service_rate=round(self.runtime.rng.uniform(0.85, 1.15), 3),
                status="reserve" if is_reserve else "idle",
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

    def _start_worker(self, worker: Worker) -> None:
        process = self.worker_processes.get(worker.id)
        if process is not None and process.is_alive:
            return
        self.worker_processes[worker.id] = self.runtime.process(self._worker_loop(worker))

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
        self.queued_ticket_ids[ticket.id] = None
        self.queue.put(ticket)
        self.runtime.process(self._sla_watch(ticket))
        self.runtime.process(self._abandon_watch(ticket))

    def _worker_loop(self, worker: Worker):
        while True:
            request = self.queue.get(
                lambda item: item.status == "queued" and item.required_skill in worker.skills
            )
            try:
                ticket: Ticket = yield request
            except simpy.Interrupt:
                request.cancel()
                return
            if ticket.status != "queued":
                continue
            self.queued_ticket_ids.pop(ticket.id, None)
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
        self.runtime.emit(
            "ticket.sla_breached",
            actor_id=ticket.id,
            target_id=customer.id,
            cause_event_id=ticket.last_event_id,
            trace_id=ticket.trace_id,
            payload={"status": ticket.status, "customer_id": customer.id},
        )

    def _abandon_watch(self, ticket: Ticket):
        customer = self.customers[ticket.customer_id]
        yield self.runtime.env.timeout(customer.patience_minutes)
        if ticket.status != "queued":
            return
        yield self.queue.get(lambda item: item.id == ticket.id)
        self.queued_ticket_ids.pop(ticket.id, None)
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

    def _sensor_loop(self):
        threshold = self.config.sensor_backlog_threshold
        recovery = self.config.sensor_recovery_threshold
        latched = False
        while self.runtime.now < self.config.simulation_minutes:
            yield self.runtime.env.timeout(1)
            backlog = len(self.queued_ticket_ids)
            if backlog >= threshold and not latched:
                from api.server.world.projection import project_support

                projection = project_support(self)
                queued_ids = list(self.queued_ticket_ids)[:20]
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
                latched = True
                self._sensor_latched = True
            elif backlog <= recovery and latched:
                self.runtime.emit(
                    "sensor.recovered",
                    actor_id="sensor:support_pressure",
                    target_id="queue:support",
                    trace_id=f"support-pressure-recovery-{int(self.runtime.now)}",
                    payload={"support_backlog": backlog},
                )
                latched = False
                self._sensor_latched = False

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

    def _return_worker_after(
        self, worker: Worker, duration_minutes: float, reallocated_event: SimulationEvent
    ):
        yield self.runtime.env.timeout(duration_minutes)
        while worker.status == "busy":
            yield self.runtime.env.timeout(1)

        process = self.worker_processes.get(worker.id)
        if process is not None and process.is_alive:
            process.interrupt()
        yield self.runtime.env.timeout(0)

        support_team = self.teams["TEAM-SUPPORT"]
        reserve_team = self.teams["TEAM-RESERVE"]
        if worker.id in support_team.worker_ids:
            support_team.worker_ids.remove(worker.id)
        if worker.id not in reserve_team.worker_ids:
            reserve_team.worker_ids.append(worker.id)
        worker.team_id = reserve_team.id
        worker.status = "reserve"
        worker.current_ticket_id = None
        worker.available_at = self.runtime.now

        self.runtime.emit(
            "worker.returned",
            actor_id=worker.id,
            target_id=reserve_team.id,
            cause_event_id=reallocated_event.event_id,
            trace_id=reallocated_event.trace_id,
            payload={
                "command_id": reallocated_event.payload["command_id"],
                "from_team_id": reallocated_event.payload["from_team_id"],
                "to_team_id": reallocated_event.payload["to_team_id"],
            },
        )

    # -- scenario read surfaces (consumed by ActorWorldService) -------------

    @staticmethod
    def _customer_wire(d: dict[str, Any]) -> dict[str, Any]:
        d["active_ticket_ids"] = sorted(d["active_ticket_ids"])
        return d

    @staticmethod
    def _worker_wire(d: dict[str, Any]) -> dict[str, Any]:
        d["skills"] = list(d["skills"])
        return d

    def render_state(self) -> dict[str, Any]:
        from api.server.world.projection import project_support

        return {
            "projection": asdict(project_support(self)),
            "customers": [self._customer_wire(asdict(c)) for c in self.customers.values()],
            "tickets": [asdict(ticket) for ticket in self.tickets.values()],
            "workers": [self._worker_wire(asdict(w)) for w in self.workers.values()],
            "teams": [asdict(team) for team in self.teams.values()],
        }

    def build_observation(self, sensor_event: dict[str, Any], *, now: float) -> dict[str, Any]:
        from api.server.world.projection import project_support

        payload = sensor_event.get("payload") or {}
        actor_ids = payload.get("actor_ids") or []
        queued_tickets = []
        for ticket_id in actor_ids:
            ticket = self.tickets.get(ticket_id)
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
                    "wait_minutes": now - ticket.queued_at,
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
            for worker in self.workers.values()
            if worker.team_id == "TEAM-SUPPORT"
        ]
        reserve_workers = [
            worker_view(worker)
            for worker in self.workers.values()
            if worker.team_id == "TEAM-RESERVE"
        ]

        return {
            "trace_id": sensor_event.get("trace_id"),
            "sensor_event_id": sensor_event.get("event_id"),
            "queued_tickets": queued_tickets,
            "support_workers": support_workers,
            "reserve_workers": reserve_workers,
            "projection": asdict(project_support(self)),
            "allowed_commands": ["reallocate_workers"],
        }


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
