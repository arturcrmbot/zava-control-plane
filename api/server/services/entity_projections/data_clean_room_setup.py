"""Projection: data-clean-room-setup (pitch-c3).

Emits an Organisation (the data partner) + an Asset (the clean room
itself) + a DecisionWrite at the data_signoff gate.
"""
from __future__ import annotations

from api.server.services.entity_projections import (
    DecisionWrite,
    EntityWrite,
    build_decision,
    slug,
)
from api.shared.types import Workflow

WORKFLOW_TYPE = "data-clean-room-setup"


def project(workflow: Workflow) -> list[EntityWrite | DecisionWrite]:
    p = workflow.payload or {}
    c = p.get("clean_room") or {}
    partner = str(c.get("partner_org") or p.get("partner_org") or "unknown")
    data_classes = c.get("data_classes") or p.get("data_classes") or []

    partner_id = f"ORG-partner-{slug(partner)}"
    asset_id = f"ASSET-clean-room-{workflow.id}"
    sw = (workflow.id,)

    ops: list[EntityWrite | DecisionWrite] = [
        EntityWrite(
            kind="Organisation",
            id=partner_id,
            attrs={"name": partner, "kind": "data-partner"},
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Asset",
            id=asset_id,
            attrs={"kind": "clean-room", "label": f"Clean room: {partner}"},
            source_workflows=sw,
        ),
    ]

    d = build_decision(
        workflow,
        gate_phase="data_signoff",
        persona_role="chief_data_officer",
        source_event="workflow.hitl.requested",
        decided_on=(partner_id, asset_id),
        attributes={"partner_org": partner, "data_classes": list(data_classes)},
    )
    if d is not None:
        ops.append(d)

    return ops
