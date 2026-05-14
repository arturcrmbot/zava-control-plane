"""Projection: new-business-pipeline-scrub (pitch-c3).

Emits a Period (the scrub week) + a Pitch (the pipeline stamp) + a
DecisionWrite at the account_director_signoff gate.
"""
from __future__ import annotations

from api.server.services.entity_projections import (
    DecisionWrite,
    EntityWrite,
    build_decision,
)
from api.shared.types import Workflow

WORKFLOW_TYPE = "new-business-pipeline-scrub"


def project(workflow: Workflow) -> list[EntityWrite | DecisionWrite]:
    p = workflow.payload or {}
    s = p.get("scrub") or {}
    week_label = str(s.get("week_label") or p.get("week_label") or workflow.id)
    pipeline_count = int(s.get("pipeline_count") or p.get("pipeline_count") or 0)

    period_id = f"PERIOD-week-{week_label}"
    pitch_id = f"PITCH-pipeline-{week_label}-{workflow.id}"
    sw = (workflow.id,)

    ops: list[EntityWrite | DecisionWrite] = [
        EntityWrite(
            kind="Period",
            id=period_id,
            attrs={"kind": "scrub-week", "label": week_label},
        ),
        EntityWrite(
            kind="Pitch",
            id=pitch_id,
            attrs={"name": f"Pipeline {week_label}", "status": "scrubbed"},
            source_workflows=sw,
        ),
    ]

    d = build_decision(
        workflow,
        gate_phase="account_director_signoff",
        persona_role="account_director",
        source_event="workflow.hitl.requested",
        decided_on=(period_id, pitch_id),
        attributes={"week_label": week_label, "pipeline_count": pipeline_count},
    )
    if d is not None:
        ops.append(d)

    return ops
