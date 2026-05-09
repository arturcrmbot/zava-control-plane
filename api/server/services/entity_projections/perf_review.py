"""Projection: perf-review (TASK-023).

Payload keys (``data/synthetic/perf-review/reviewees.json``)::

    employee_id, cycle, prior_rating, scenario

Both HITL gates (``hr_calibration``, ``line_manager_delivery``) emit a
:class:`DecisionWrite` when the payload carries a matching decision entry.
The ``precedent_of`` linkage to the prior cycle's calibration is intentionally
not derived here — that's a Phase 2 enhancement.
"""
from __future__ import annotations

from api.server.services.entity_projections import (
    DecisionWrite,
    EntityWrite,
    build_decision,
)
from api.shared.types import Workflow

WORKFLOW_TYPE = "perf-review"


def project(workflow: Workflow) -> list[EntityWrite | DecisionWrite]:
    p = workflow.payload or {}
    employee_id = str(p.get("employee_id") or "unknown")
    cycle = str(p.get("cycle") or "")
    prior_rating = str(p.get("prior_rating") or "")

    person_id = f"PERSON-{employee_id}"
    period_id = f"PERIOD-{cycle}" if cycle else f"PERIOD-cycle-{workflow.id}"
    sw = (workflow.id,)

    ops: list[EntityWrite | DecisionWrite] = [
        EntityWrite(
            kind="Person",
            id=person_id,
            attrs={},
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Period",
            id=period_id,
            attrs={"kind": "review-cycle", "label": cycle or workflow.id},
        ),
    ]

    for gate_phase, persona in (
        ("hr_calibration", "perf_review_hr_bp"),
        ("line_manager_delivery", "perf_review_line_manager"),
    ):
        d = build_decision(
            workflow,
            gate_phase=gate_phase,
            persona_role=persona,
            source_event="workflow.hitl.requested",
            decided_on=(person_id,),
            attributes={"cycle": cycle, "prior_rating": prior_rating},
        )
        if d is not None:
            ops.append(d)

    return ops
