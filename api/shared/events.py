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
})


def wakes_fleet_manager(e: FleetEvent) -> bool:
    return e.type in WAKE_TYPES
