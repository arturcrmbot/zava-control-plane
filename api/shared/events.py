# src/shared/events.py
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict

# Documentation-only catalogue of canonical event types. Per Phase 4 of
# feature-fleet-domain-substrate-1, FleetEvent.type is plain `str` so
# per-domain wake hints declared in api/shared/domains.py (e.g.
# `vendor.kyc.high_risk`) can flow through the bus without each domain
# editing this file. Triage + WAKE_TYPES still gate which events wake
# the FM.
FleetEventType = Literal[
    "workflow.started",
    "workflow.phase.started",
    "workflow.phase.completed",
    "workflow.phase.failed",
    "workflow.exception.detected",
    "workflow.hitl.requested",
    "workflow.hitl.escalated",
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
    # Week 3 — candidate portal events (POC2 demo-ready scope)
    "candidate.applied",
    "magic_link.issued",
    "offer.decided",
    "voice_transcript.received",
]


class FleetEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    # Was a Literal[FleetEventType] union; widened to str so per-domain
    # wake-hint events declared in api.shared.domains can flow through
    # without editing this file. The FleetEventType literal above stays
    # as the canonical catalogue for documentation + WAKE_TYPES membership.
    type: str
    workflow_id: str | None = None
    # All other fields permitted via extra="allow"


WAKE_TYPES: frozenset[str] = frozenset({
    "workflow.exception.detected",
    "workflow.hitl.requested",
    "workflow.hitl.escalated",
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
