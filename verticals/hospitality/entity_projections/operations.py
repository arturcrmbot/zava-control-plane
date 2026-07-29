"""Minimal Hospitality entity projection.

Writes only what the workflow payload genuinely carries: the workflow node,
the real hotel/asset/work-order/booking actors named in the observation, their
relationships to the owning property, and — when an authority decision is
actually recorded — one Decision node. Absent evidence produces no node; this
projection never fabricates an actor.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from api.server.services.entity_graph import (
    DecisionWrite,
    EntityWrite,
    RelWrite,
)
from api.shared.types import Workflow
from verticals.hospitality.domains import HOSPITALITY_DOMAINS
from verticals.hospitality.process_profiles import HOSPITALITY_PROCESS_PROFILES


_ACTOR_KINDS = {
    "HOTEL-": "hotel-property",
    "ASSET-": "critical-asset",
    "WO-": "work-order",
    "BKG-": "booking",
    "GP-": "guest-party",
    "TEAM-": "team-member",
    "SHIFT-": "shift",
    "FSP-": "food-service-plan",
    "EM-": "energy-meter",
    "ROOM-": "room",
}

_OBSERVATION_KEYS = ("hospitality_case", "observation")


def _actor_kind(actor_id: str) -> str:
    return next(
        (kind for prefix, kind in _ACTOR_KINDS.items() if actor_id.startswith(prefix)),
        "hospitality-actor",
    )


def _observation(workflow: Workflow) -> dict:
    payload = workflow.payload or {}
    for key in _OBSERVATION_KEYS:
        candidate = payload.get(key)
        if isinstance(candidate, dict):
            return candidate
    return {}


def _asset(actor_id: str, *, status: str, workflow_id: str) -> EntityWrite:
    return EntityWrite(
        kind="Asset",
        id=actor_id,
        attrs={
            "kind": _actor_kind(actor_id),
            "identifier": actor_id,
            "status": status,
            "attributes": json.dumps({"workflow_id": workflow_id}, sort_keys=True),
        },
        source_workflows=(workflow_id,),
    )


def _decision(workflow: Workflow, actor_ids: tuple[str, ...]) -> DecisionWrite | None:
    profile = HOSPITALITY_PROCESS_PROFILES.get(workflow.type)
    if profile is None:
        return None
    payload = workflow.payload or {}
    entries = payload.get("decisions") or []
    if entries:
        entry = entries[-1]
        decision_id = entry.get("decision_id")
    else:
        decision = payload.get("decision") or {}
        reasoning = decision.get("reasoning")
        authority = reasoning.get("authority") if isinstance(reasoning, dict) else None
        if not isinstance(authority, dict) or not authority.get("decision"):
            return None
        gates = HOSPITALITY_DOMAINS[workflow.type].hitl_gates
        entry = {
            "phase": gates[0].gate_phase if gates else "Approval",
            "persona_role": authority.get("persona"),
            "verdict": authority.get("decision"),
            "reason": reasoning.get("summary") or "Durable authority decision.",
            "decided_at": datetime.fromtimestamp(
                workflow.created_at,
                tz=timezone.utc,
            ).isoformat(),
        }
        decision_id = authority.get("decision_id")
    return DecisionWrite(
        workflow_id=workflow.id,
        phase=str(entry.get("phase") or "Approval"),
        persona_role=str(
            entry.get("persona_role") or profile.hitl_persona or profile.function
        ),
        verdict=str(entry.get("verdict") or "approve"),
        reason=str(entry.get("reason") or ""),
        decided_at=str(entry.get("decided_at") or ""),
        source_event="world.responder.decided",
        attributes={
            "workflow_type": workflow.type,
            "command_type": profile.command_type,
            "decision_id": decision_id,
        },
        decided_on=actor_ids,
    )


def project(workflow: Workflow) -> list[EntityWrite | RelWrite | DecisionWrite]:
    if workflow.type not in HOSPITALITY_PROCESS_PROFILES:
        return []
    observation = _observation(workflow)
    actor_ids = tuple(
        dict.fromkeys(
            str(value) for value in observation.get("actor_ids") or [] if value
        )
    )
    operations: list[EntityWrite | RelWrite | DecisionWrite] = [
        EntityWrite(
            kind="Workflow",
            id=workflow.id,
            attrs={"workflow_type": workflow.type, "status": workflow.status},
            source_workflows=(workflow.id,),
        )
    ]
    if not actor_ids:
        return operations

    hotel_ids = [
        actor_id for actor_id in actor_ids if actor_id.startswith("HOTEL-")
    ]
    for actor_id in actor_ids:
        operations.append(
            _asset(actor_id, status=workflow.status, workflow_id=workflow.id)
        )
    for hotel_id in hotel_ids:
        for actor_id in actor_ids:
            if actor_id == hotel_id or actor_id.startswith("HOTEL-"):
                continue
            operations.append(RelWrite(actor_id, "ASSET_AT_SITE", hotel_id))

    decision = _decision(workflow, actor_ids[:5])
    if decision is not None:
        operations.append(decision)
    return operations
