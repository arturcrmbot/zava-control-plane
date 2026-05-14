"""Projection: quarterly-creative-awards (pitch-c3).

Emits a Period (the quarter) + a Pitch (the awards shortlist stamp) +
a DecisionWrite at the creative_signoff gate.
"""
from __future__ import annotations

from api.server.services.entity_projections import (
    DecisionWrite,
    EntityWrite,
    build_decision,
)
from api.shared.types import Workflow

WORKFLOW_TYPE = "quarterly-creative-awards"


def project(workflow: Workflow) -> list[EntityWrite | DecisionWrite]:
    p = workflow.payload or {}
    q = p.get("quarterly_awards") or {}
    quarter = str(q.get("quarter") or p.get("quarter") or workflow.id)
    shortlist_size = int(q.get("shortlist_size") or p.get("shortlist_size") or 0)

    period_id = f"PERIOD-{quarter}"
    pitch_id = f"PITCH-quarterly-awards-{quarter}-{workflow.id}"
    sw = (workflow.id,)

    ops: list[EntityWrite | DecisionWrite] = [
        EntityWrite(
            kind="Period",
            id=period_id,
            attrs={"kind": "quarter", "label": quarter},
        ),
        EntityWrite(
            kind="Pitch",
            id=pitch_id,
            attrs={"name": f"Awards shortlist {quarter}", "status": "shortlisted"},
            source_workflows=sw,
        ),
    ]

    d = build_decision(
        workflow,
        gate_phase="creative_signoff",
        persona_role="creative_director",
        source_event="workflow.hitl.requested",
        decided_on=(period_id, pitch_id),
        attributes={"quarter": quarter, "shortlist_size": shortlist_size},
    )
    if d is not None:
        ops.append(d)

    return ops
