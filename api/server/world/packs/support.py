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
