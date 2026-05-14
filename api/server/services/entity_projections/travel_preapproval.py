"""Projection: travel-preapproval (TASK-020).

Payload keys (``data/synthetic/travel-preapproval/trips.json``)::

    employee_id, origin, destination, depart_date, return_date,
    business_reason, scenario

A travel-budget :class:`Money` node is emitted only when the scenario
contains an explicit cost band; in-policy default trips skip it because
the fixture does not carry a notional amount.

The manager-approval decision lists the destination Place and the trip
Period in ``decided_on`` (in addition to the traveller Person), so the
``Decision-[:DECIDED_PLACE]->Place`` and ``Decision-[:DECIDED_PERIOD]
->Period`` shards carry visible end-to-end linkage from a travel
decision to where and when the trip happens.
"""
from __future__ import annotations

from datetime import date, datetime

from api.server.services.entity_projections import (
    DecisionWrite,
    EntityWrite,
    RelWrite,
    build_decision,
)
from api.shared.types import Workflow

WORKFLOW_TYPE = "travel-preapproval"


def _to_ts(value: str) -> datetime | None:
    """Coerce an ISO date/datetime string to ``datetime`` for TIMESTAMP cols.

    Period.starts / Period.ends are TIMESTAMP. Kuzu 0.6.1 doesn't
    auto-cast strings; passing a raw string raises a Binder exception
    and the upsert fails silently in the reflector.
    """
    if not value:
        return None
    try:
        if "T" in value:
            return datetime.fromisoformat(value)
        d = date.fromisoformat(value)
        return datetime(d.year, d.month, d.day)
    except ValueError:
        return None


def project(workflow: Workflow) -> list[EntityWrite | RelWrite | DecisionWrite]:
    p = workflow.payload or {}
    t = p.get("trip") or {}
    employee_id = str(t.get("employee_id") or p.get("employee_id") or "unknown")
    origin = str(t.get("origin") or p.get("origin") or "")
    destination = str(t.get("destination") or p.get("destination") or "")
    depart = str(t.get("depart_date") or p.get("depart_date") or "")
    ret = str(t.get("return_date") or p.get("return_date") or "")
    reason = str(t.get("business_reason") or p.get("business_reason") or "")

    person_id = f"PERSON-{employee_id}"
    period_id = f"PERIOD-trip-{workflow.id}"
    sw = (workflow.id,)

    period_attrs: dict = {
        "kind": "trip",
        "label": f"{origin}->{destination}" if (origin or destination) else "trip",
    }
    starts_ts = _to_ts(depart)
    ends_ts = _to_ts(ret)
    if starts_ts is not None:
        period_attrs["starts"] = starts_ts
    if ends_ts is not None:
        period_attrs["ends"] = ends_ts

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
            attrs=period_attrs,
        ),
    ]

    decided_on: list[str] = [person_id, period_id]

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
        decided_on.append(dst_id)

    d = build_decision(
        workflow,
        gate_phase="manager_approval",
        persona_role="line_manager",
        source_event="workflow.hitl.requested",
        decided_on=tuple(decided_on),
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
