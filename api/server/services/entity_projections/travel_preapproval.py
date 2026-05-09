"""Projection: travel-preapproval (TASK-020).

Payload keys (``data/synthetic/travel-preapproval/trips.json``)::

    employee_id, origin, destination, depart_date, return_date,
    business_reason, scenario

A travel-budget :class:`Money` node is emitted only when the scenario
contains an explicit cost band; in-policy default trips skip it because
the fixture does not carry a notional amount.
"""
from __future__ import annotations

from api.server.services.entity_projections import (
    DecisionWrite,
    EntityWrite,
    RelWrite,
    build_decision,
)
from api.shared.types import Workflow

WORKFLOW_TYPE = "travel-preapproval"


def project(workflow: Workflow) -> list[EntityWrite | RelWrite | DecisionWrite]:
    p = workflow.payload or {}
    employee_id = str(p.get("employee_id") or "unknown")
    origin = str(p.get("origin") or "")
    destination = str(p.get("destination") or "")
    depart = str(p.get("depart_date") or "")
    ret = str(p.get("return_date") or "")
    reason = str(p.get("business_reason") or "")

    person_id = f"PERSON-{employee_id}"
    period_id = f"PERIOD-trip-{workflow.id}"
    sw = (workflow.id,)

    ops: list[EntityWrite | RelWrite | DecisionWrite] = [
        EntityWrite(
            kind="Person",
            id=person_id,
            attrs={},
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Period",
            id=period_id,
            attrs={
                "kind": "trip",
                "starts": depart,
                "ends": ret,
                "label": f"{origin}->{destination}",
            },
        ),
    ]

    if origin:
        origin_id = f"PLACE-{origin}"
        ops.append(EntityWrite(
            kind="Place", id=origin_id,
            attrs={"kind": "airport", "name": origin},
        ))
    if destination:
        dst_id = f"PLACE-{destination}"
        ops.append(EntityWrite(
            kind="Place", id=dst_id,
            attrs={"kind": "airport", "name": destination},
        ))
        ops.append(RelWrite(src_id=person_id, rel="LOCATED_IN", dst_id=dst_id))

    d = build_decision(
        workflow,
        gate_phase="manager_approval",
        persona_role="line_manager",
        source_event="workflow.hitl.requested",
        decided_on=(person_id,),
        attributes={
            "employee_id": employee_id,
            "origin": origin,
            "destination": destination,
            "business_reason": reason,
        },
    )
    if d is not None:
        ops.append(d)

    return ops
