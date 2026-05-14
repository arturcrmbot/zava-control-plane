"""Projection: board-prep (pitch-c1).

Emits a Period (the meeting period) + a Person (the CFO who signs the
pack) + a DecisionWrite at the board_signoff gate.
"""
from __future__ import annotations

from api.server.services.entity_projections import (
    DecisionWrite,
    EntityWrite,
    build_decision,
)
from api.shared.types import Workflow

WORKFLOW_TYPE = "board-prep"


def project(workflow: Workflow) -> list[EntityWrite | DecisionWrite]:
    p = workflow.payload or {}
    b = p.get("board_pack") or {}
    meeting_date = str(b.get("meeting_date") or p.get("meeting_date") or "unknown")
    agenda = str(b.get("agenda") or p.get("agenda") or "general")

    period_id = f"PERIOD-board-{meeting_date}"
    person_id = "PERSON-cfo"
    sw = (workflow.id,)

    ops: list[EntityWrite | DecisionWrite] = [
        EntityWrite(
            kind="Period",
            id=period_id,
            attrs={"kind": "board-meeting", "label": meeting_date},
        ),
        EntityWrite(
            kind="Person",
            id=person_id,
            attrs={"role": "cfo"},
            source_workflows=sw,
        ),
    ]

    d = build_decision(
        workflow,
        gate_phase="board_signoff",
        persona_role="cfo",
        source_event="workflow.hitl.requested",
        decided_on=(period_id, person_id),
        attributes={"meeting_date": meeting_date, "agenda": agenda},
    )
    if d is not None:
        ops.append(d)

    return ops
