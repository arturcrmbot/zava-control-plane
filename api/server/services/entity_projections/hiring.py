"""Projection: hiring (legacy POC2).

Maps a ``hiring`` workflow's payload to:

* :class:`Person` ``candidate`` — the candidate being hired.
* :class:`Organisation` ``sourcing-channel`` — the agency / channel that
  surfaced the CV (e.g. ``ORG-source-linkedin``). Falls back to the
  workflow's ``agency`` when no channel is in the payload.
* :class:`Asset` ``requisition`` — the role / requisition slot.
* ``Person -[:OWNS]-> Asset`` — the candidate "owns" the requisition
  slot for the duration of the workflow.
* :class:`DecisionWrite` for the ``screening``, ``interview``, ``offer``,
  and ``hire`` HITL gates when the payload's ``decisions`` list carries
  matching entries (else skipped).

Payload keys consumed (mirrors ``spawn_hiring_workflow``)::

    candidate_id, candidate_name, role_family, level_target,
    jurisdiction, sourcing_channel | source, agency, scenario,
    start_date, decisions
"""
from __future__ import annotations

from datetime import date, datetime

from api.server.services.entity_projections import (
    DecisionWrite,
    EntityWrite,
    RelWrite,
    build_decision,
    slug,
)
from api.shared.types import Workflow

WORKFLOW_TYPE = "hiring"


def _to_date(value: str) -> date | None:
    """Coerce an ISO-8601 string to ``datetime.date`` (or ``None``)."""
    if not value:
        return None
    try:
        if "T" in value:
            return datetime.fromisoformat(value).date()
        return date.fromisoformat(value)
    except ValueError:
        return None


def project(workflow: Workflow) -> list[EntityWrite | RelWrite | DecisionWrite]:
    p = workflow.payload or {}
    candidate_id = str(p.get("candidate_id") or "")
    candidate_name = str(p.get("candidate_name") or "")
    role_family = str(p.get("role_family") or "")
    level_target = str(p.get("level_target") or "")
    jurisdiction = str(p.get("jurisdiction") or workflow.jurisdiction or "")
    source_channel = str(
        p.get("sourcing_channel") or p.get("source") or workflow.agency or "unknown"
    )
    start_date_raw = str(p.get("start_date") or "")

    person_id = (
        f"PERSON-{candidate_id}" if candidate_id
        else f"PERSON-CANDIDATE-{workflow.id}"
    )
    agency_org_id = f"ORG-source-{slug(source_channel)}"
    asset_id = f"ASSET-req-{workflow.id}"
    sw = (workflow.id,)

    person_attrs: dict = {}
    if candidate_name:
        person_attrs["name"] = candidate_name
    start_date = _to_date(start_date_raw)
    if start_date is not None:
        person_attrs["employed_from"] = start_date

    asset_attrs: dict = {"kind": "requisition", "identifier": asset_id}
    if role_family:
        asset_attrs["role_family"] = role_family
    if level_target:
        asset_attrs["level_target"] = level_target
    if jurisdiction:
        asset_attrs["jurisdiction"] = jurisdiction

    ops: list[EntityWrite | RelWrite | DecisionWrite] = [
        EntityWrite(
            kind="Person",
            id=person_id,
            attrs=person_attrs,
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Organisation",
            id=agency_org_id,
            attrs={"name": source_channel, "kind": "sourcing-channel"},
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Asset",
            id=asset_id,
            attrs=asset_attrs,
            source_workflows=sw,
        ),
        # Candidate "owns" the requisition slot. Person→OWNS→Asset is the
        # only typed direction in the schema, so this is the canonical
        # candidate↔requisition link.
        RelWrite(src_id=person_id, rel="OWNS", dst_id=asset_id),
    ]

    decided_on = (person_id, asset_id, agency_org_id)
    decision_attrs = {
        "candidate_id": candidate_id,
        "role_family": role_family,
        "level_target": level_target,
        "jurisdiction": jurisdiction,
    }
    for gate_phase, persona in (
        ("screening", "recruiter"),
        ("interview", "hiring_manager"),
        ("offer", "hr_bp"),
        ("hire", "hr_bp"),
    ):
        d = build_decision(
            workflow,
            gate_phase=gate_phase,
            persona_role=persona,
            source_event="workflow.hitl.requested",
            decided_on=decided_on,
            attributes=decision_attrs,
        )
        if d is not None:
            ops.append(d)

    return ops
