"""Projection: employee-onboarding (TASK-018).

Payload keys (``data/synthetic/employee-onboarding/joiners.json``)::

    employee_id, department, buddy_id, start_date, scenario

The laptop :class:`Asset` is omitted when the scenario opts out
(``no-laptop``, ``byod``); otherwise a standard laptop asset is emitted.
"""
from __future__ import annotations

from api.server.services.entity_projections import (
    DecisionWrite,
    EntityWrite,
    RelWrite,
    build_decision,
)
from api.shared.types import Workflow

WORKFLOW_TYPE = "employee-onboarding"


def project(workflow: Workflow) -> list[EntityWrite | RelWrite | DecisionWrite]:
    p = workflow.payload or {}
    employee_id = str(p.get("employee_id") or "unknown")
    department = str(p.get("department") or "")
    buddy_id = str(p.get("buddy_id") or "")
    start_date = str(p.get("start_date") or "")
    scenario = str(p.get("scenario") or "").lower()

    person_id = f"PERSON-{employee_id}"
    sw = (workflow.id,)

    person_attrs: dict = {"department": department}
    if start_date:
        person_attrs["employed_from"] = start_date

    ops: list[EntityWrite | RelWrite | DecisionWrite] = [
        EntityWrite(
            kind="Person",
            id=person_id,
            attrs=person_attrs,
            source_workflows=sw,
        ),
    ]

    if buddy_id:
        buddy_pid = f"PERSON-{buddy_id}"
        ops.append(EntityWrite(kind="Person", id=buddy_pid, attrs={}, source_workflows=sw))
        # Buddy-of edge: Person -> Person; MANAGES is the only Person→Person rel.
        ops.append(RelWrite(src_id=person_id, rel="MANAGES", dst_id=buddy_pid))

    asset_id: str | None = None
    if "no-laptop" not in scenario and "byod" not in scenario:
        asset_id = f"ASSET-laptop-{employee_id}"
        ops.append(
            EntityWrite(
                kind="Asset",
                id=asset_id,
                attrs={"kind": "laptop", "identifier": asset_id},
                source_workflows=sw,
            )
        )
        ops.append(RelWrite(src_id=person_id, rel="OWNS", dst_id=asset_id))

    decided_on: tuple[str, ...] = (person_id,) if asset_id is None else (person_id, asset_id)
    d = build_decision(
        workflow,
        gate_phase="it_admin_approval",
        persona_role="onboarding_it_admin",
        source_event="workflow.hitl.requested",
        decided_on=decided_on,
        attributes={"employee_id": employee_id, "department": department},
    )
    if d is not None:
        ops.append(d)

    return ops
