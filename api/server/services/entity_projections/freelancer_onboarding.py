"""Projection: freelancer-onboarding (pitch-c3).

Emits a Person (the freelancer) + a DecisionWrite at the hr_signoff gate.
"""
from __future__ import annotations

from api.server.services.entity_projections import (
    DecisionWrite,
    EntityWrite,
    build_decision,
)
from api.shared.types import Workflow

WORKFLOW_TYPE = "freelancer-onboarding"


def project(workflow: Workflow) -> list[EntityWrite | DecisionWrite]:
    p = workflow.payload or {}
    f = p.get("freelancer") or {}
    freelancer_id = str(f.get("freelancer_id") or p.get("freelancer_id") or workflow.id)
    discipline = str(f.get("discipline") or "creative")

    person_id = f"PERSON-freelancer-{freelancer_id}"
    sw = (workflow.id,)

    ops: list[EntityWrite | DecisionWrite] = [
        EntityWrite(
            kind="Person",
            id=person_id,
            attrs={"role": f"freelancer-{discipline}"},
            source_workflows=sw,
        ),
    ]

    d = build_decision(
        workflow,
        gate_phase="hr_signoff",
        persona_role="hr_bp",
        source_event="workflow.hitl.requested",
        decided_on=(person_id,),
        attributes={"freelancer_id": freelancer_id, "discipline": discipline},
    )
    if d is not None:
        ops.append(d)

    return ops
