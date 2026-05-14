"""Projection: creative-awards-submission (pitch-c3).

Emits a Pitch node (the awards submission, in pitch-e1's agency-domain
schema) plus a DecisionWrite at the creative_signoff gate.
"""
from __future__ import annotations

from api.server.services.entity_projections import (
    DecisionWrite,
    EntityWrite,
    build_decision,
    slug,
)
from api.shared.types import Workflow

WORKFLOW_TYPE = "creative-awards-submission"


def project(workflow: Workflow) -> list[EntityWrite | DecisionWrite]:
    p = workflow.payload or {}
    s = p.get("submission") or {}
    award = str(s.get("award") or p.get("award") or "unknown-award")
    campaign = str(s.get("campaign") or p.get("campaign") or workflow.id)

    pitch_id = f"PITCH-awards-{slug(campaign)}"
    sw = (workflow.id,)

    ops: list[EntityWrite | DecisionWrite] = [
        EntityWrite(
            kind="Pitch",
            id=pitch_id,
            attrs={"name": f"{award}: {campaign}", "status": "submitted"},
            source_workflows=sw,
        ),
    ]

    d = build_decision(
        workflow,
        gate_phase="creative_signoff",
        persona_role="creative_director",
        source_event="workflow.hitl.requested",
        decided_on=(pitch_id,),
        attributes={"award": award, "campaign": campaign},
    )
    if d is not None:
        ops.append(d)

    return ops
