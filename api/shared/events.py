# src/shared/events.py
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict

FleetEventType = Literal[
    "workflow.started",
    "workflow.phase.started",
    "workflow.phase.completed",
    "workflow.phase.failed",
    "workflow.exception.detected",
    "workflow.hitl.requested",
    "workflow.sla.breach_imminent",
    "workflow.policy.violation",
    "workflow.resolved",
    "otel.span.emitted",
    "fleet.anomaly.detected",
    "fleet.tick",
    "fleet.overload",
    # Durable Workflow events (new in py POC1)
    "durable.workflow.started",
    "durable.step.started",
    "durable.step.completed",
    "durable.executor.invoked",
    "durable.validator.blocked",
    "durable.suspended",
    "durable.resumed",
    "durable.workflow.completed",
    # Accuracy harness events (one-shot evaluation runs; do NOT wake the fleet manager)
    "accuracy.progress",
    "accuracy.complete",
    # Per-agent eval signal — emitted by run_agent_session, observed by online_subscriber.
    # Does NOT wake the fleet manager.
    "agent.completed",
    # Week 2 — expense-claim domain events
    "claim.routed.green",
    "claim.routed.amber",
    "claim.routed.red",
    "receipt.mismatch.detected",
    "escalation.tier.assigned",
    "notification.sent",
    "justification.received",
    "arbitration.recommended",
    "audit.summary.composed",
    "region.failure.simulated",
]


class FleetEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: FleetEventType
    workflow_id: str | None = None
    # All other fields permitted via extra="allow"


WAKE_TYPES: frozenset[FleetEventType] = frozenset({
    "workflow.exception.detected",
    "workflow.hitl.requested",
    "workflow.sla.breach_imminent",
    "workflow.policy.violation",
    "fleet.anomaly.detected",
    "fleet.tick",
    # Red routes warrant FM attention before the HITL gate trips, so the
    # demo rail pulses on the agent's hot path instead of waiting 60s+ for
    # a suspend. Green/amber are routine signal and stay out.
    "claim.routed.red",
})


def wakes_fleet_manager(e: FleetEvent) -> bool:
    return e.type in WAKE_TYPES
