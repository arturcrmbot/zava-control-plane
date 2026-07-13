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
