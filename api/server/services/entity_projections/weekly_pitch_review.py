"""Projection: weekly-pitch-review (pitch-c3).

Emits a Period (the review week) + a Pitch (the rolled-up slate stamp)
+ a DecisionWrite at the creative_signoff gate.
"""
from __future__ import annotations

from api.server.services.entity_projections import (
    DecisionWrite,
    EntityWrite,
    build_decision,
)
from api.shared.types import Workflow

WORKFLOW_TYPE = "weekly-pitch-review"


def project(workflow: Workflow) -> list[EntityWrite | DecisionWrite]:
    p = workflow.payload or {}
    r = p.get("review") or {}
    week_label = str(r.get("week_label") or p.get("week_label") or workflow.id)
    pitch_count = int(r.get("pitch_count") or p.get("pitch_count") or 0)

    period_id = f"PERIOD-week-{week_label}"
    pitch_id = f"PITCH-weekly-{week_label}-{workflow.id}"
    sw = (workflow.id,)

    ops: list[EntityWrite | DecisionWrite] = [
        EntityWrite(
            kind="Period",
            id=period_id,
            attrs={"kind": "review-week", "label": week_label},
        ),
        EntityWrite(
            kind="Pitch",
            id=pitch_id,
            attrs={"name": f"Pitch slate {week_label}", "status": "in-review"},
            source_workflows=sw,
        ),
    ]

    d = build_decision(
        workflow,
        gate_phase="creative_signoff",
        persona_role="creative_director",
        source_event="workflow.hitl.requested",
        decided_on=(period_id, pitch_id),
        attributes={"week_label": week_label, "pitch_count": pitch_count},
    )
    if d is not None:
        ops.append(d)

    return ops
