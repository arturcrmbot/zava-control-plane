"""Projection: employee-onboarding (TASK-018).

Payload keys (``data/synthetic/employee-onboarding/joiners.json``)::

    employee_id, department, buddy_id, start_date, scenario

The laptop :class:`Asset` is omitted when the scenario opts out
(``no-laptop``, ``byod``); otherwise a standard laptop asset is emitted.

Org link: every employee is linked Person→[EMPLOYED_BY]→Organisation
(``ORG-zava``) so the graph carries the canonical employer relationship
the EMPLOYED_BY rel table was added for.
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

WORKFLOW_TYPE = "employee-onboarding"

# Canonical "Zava itself" Organisation node. Every employee EMPLOYED_BY
# this org. Idempotently upserted on every onboarding so the node exists
# even from a clean DB.
ZAVA_ORG_ID = "ORG-zava"


def _to_date(value: str) -> date | None:
    """Coerce an ISO-8601 date string to ``datetime.date``.

    Kuzu 0.6.1 has no implicit STRING→DATE cast, so passing a raw ISO
    string into a DATE-typed column raises a Binder exception and the
    whole upsert fails (the entity_reflector audit-logs but swallows the
    error). Coerce here so the upsert lands cleanly.

    Returns ``None`` if the string can't be parsed; caller should drop
    the field rather than send junk to Kuzu.
    """
    if not value:
        return None
    try:
        # Accept both pure dates ("2026-05-11") and timestamps
        # ("2026-05-11T07:38:18").
        if "T" in value:
            return datetime.fromisoformat(value).date()
        return date.fromisoformat(value)
    except ValueError:
        return None


def project(workflow: Workflow) -> list[EntityWrite | RelWrite | DecisionWrite]:
    p = workflow.payload or {}
    j = p.get("joiner") or {}
    employee_id = str(j.get("employee_id") or p.get("employee_id") or "unknown")
    department = str(j.get("department") or p.get("department") or "")
    buddy_id = str(j.get("buddy_id") or p.get("buddy_id") or "")
    start_date_raw = str(j.get("start_date") or p.get("start_date") or "")
    scenario = str(p.get("scenario") or j.get("scenario") or "").lower()

    person_id = f"PERSON-{employee_id}"
    sw = (workflow.id,)

    person_attrs: dict = {"department": department}
    start_date = _to_date(start_date_raw)
    if start_date is not None:
        person_attrs["employed_from"] = start_date

    ops: list[EntityWrite | RelWrite | DecisionWrite] = [
        # Canonical employer org — idempotent; landing on every onboarding
        # is safe because EntityWrite is MERGE-on-id.
        EntityWrite(
            kind="Organisation",
            id=ZAVA_ORG_ID,
            attrs={"name": "Zava", "kind": "employer"},
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Person",
            id=person_id,
            attrs=person_attrs,
            source_workflows=sw,
        ),
        # Person→EMPLOYED_BY→Org. Pass `since` as a date so the rel
        # property matches the DATE-typed column.
        RelWrite(
            src_id=person_id, rel="EMPLOYED_BY", dst_id=ZAVA_ORG_ID,
            attrs={"since": start_date} if start_date is not None else {},
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
