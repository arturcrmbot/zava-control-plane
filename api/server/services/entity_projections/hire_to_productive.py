"""Projection: hire-to-productive (pitch-c1).

Emits a Person (the joiner) + a Period (the onboarding window) so the
domain shows up alongside hiring in the cosmic-lens entity graph.
"""
from __future__ import annotations

from api.server.services.entity_projections import (
    DecisionWrite,
    EntityWrite,
    build_decision,
)
from api.shared.types import Workflow

WORKFLOW_TYPE = "hire-to-productive"


def project(workflow: Workflow) -> list[EntityWrite | DecisionWrite]:
    p = workflow.payload or {}
    j = p.get("joiner") or {}
    joiner_id = str(j.get("joiner_id") or p.get("joiner_id") or workflow.id)
    role_family = str(j.get("role_family") or "unspecified")

    person_id = f"PERSON-{joiner_id}"
    period_id = f"PERIOD-onboarding-{joiner_id}"
    sw = (workflow.id,)

    ops: list[EntityWrite | DecisionWrite] = [
        EntityWrite(
            kind="Person",
            id=person_id,
            attrs={"role": role_family},
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Period",
            id=period_id,
            attrs={"kind": "onboarding-window", "label": joiner_id},
        ),
    ]

    d = build_decision(
        workflow,
        gate_phase="manager_signoff",
        persona_role="hr_bp",
        source_event="workflow.hitl.requested",
        decided_on=(person_id, period_id),
        attributes={"joiner_id": joiner_id, "role_family": role_family},
    )
    if d is not None:
        ops.append(d)

    return ops
