"""Pure projections derived from explicit support actors."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from api.server.world.packs.support import SupportScenario
    from verticals.telco.world import NetworkScenario


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


@dataclass(frozen=True, slots=True)
class NetworkProjection:
    sites_total: int
    sites_healthy: int
    sites_failed: int
    subscribers_total: int
    sessions_total: int
    sessions_active: int
    sessions_degraded: int
    sessions_rerouted: int
    sessions_dropped: int
    total_demand_mbps: float
    average_utilization: float
    max_packet_loss_pct: float


def project_network(scenario: "NetworkScenario") -> NetworkProjection:
    sites = list(scenario.sites.values())
    sessions = list(scenario.sessions.values())
    healthy = [site for site in sites if site.status == "healthy"]
    utilisations = [site.utilization for site in healthy]
    return NetworkProjection(
        sites_total=len(sites),
        sites_healthy=len(healthy),
        sites_failed=sum(site.status == "failed" for site in sites),
        subscribers_total=len(scenario.subscribers),
        sessions_total=len(sessions),
        sessions_active=sum(s.status == "active" for s in sessions),
        sessions_degraded=sum(s.status == "degraded" for s in sessions),
        sessions_rerouted=sum(s.status == "rerouted" for s in sessions),
        sessions_dropped=sum(s.status == "dropped" for s in sessions),
        total_demand_mbps=round(sum(site.traffic_mbps for site in sites), 3),
        average_utilization=round(sum(utilisations) / len(utilisations), 4) if utilisations else 0.0,
        max_packet_loss_pct=round(max((site.packet_loss for site in sites), default=0.0) * 100.0, 3),
    )
