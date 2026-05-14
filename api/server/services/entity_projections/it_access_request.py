"""Projection: it-access-request (TASK-019).

Payload keys (``data/synthetic/it-access-request/requests.json``)::

    employee_id, department, requested_role_templates, business_justification, scenario
"""
from __future__ import annotations

import hashlib
import json

from api.server.services.entity_projections import (
    DecisionWrite,
    EntityWrite,
    RelWrite,
    build_decision,
)
from api.shared.types import Workflow

WORKFLOW_TYPE = "it-access-request"


def _line_manager_oo(workflow_id: str) -> bool:
    """Phase 4 Task 4.1: deterministic manager-OOO simulation.

    1-in-5 line-manager decisions defer because the manager hasn't
    returned a decision in time. We use sha1 (not Python's per-process
    randomised ``hash()``) so reseeds and CI runs yield the same shape.
    """
    return int(hashlib.sha1(workflow_id.encode()).hexdigest(), 16) % 5 == 0


def project(workflow: Workflow) -> list[EntityWrite | RelWrite | DecisionWrite]:
    p = workflow.payload or {}
    r = p.get("request") or {}
    employee_id = str(r.get("employee_id") or p.get("employee_id") or "unknown")
    department = str(r.get("department") or p.get("department") or "")
    templates = list(r.get("requested_role_templates")
                     or p.get("requested_role_templates") or [])
    justification = str(r.get("business_justification")
                        or p.get("business_justification") or "")

    person_id = f"PERSON-{employee_id}"
    asset_id = f"ASSET-access-{workflow.id}"
    sw = (workflow.id,)

    asset_extra = {
        # Kuzu node attr columns are scalar STRING; serialise the
        # template list as JSON so the projection round-trips.
        "requested_role_templates": templates,
        "business_justification": justification,
    }

    ops: list[EntityWrite | RelWrite | DecisionWrite] = [
        EntityWrite(
            kind="Person",
            id=person_id,
            attrs={"department": department},
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Asset",
            id=asset_id,
            attrs={
                "kind": "access-grant",
                "attributes": json.dumps(asset_extra, sort_keys=True, default=str),
            },
            source_workflows=sw,
        ),
        RelWrite(src_id=person_id, rel="OWNS", dst_id=asset_id),
    ]

    line_manager_ooo = _line_manager_oo(workflow.id)
    for gate_phase, persona in (
        ("line_manager_approval", "it_access_line_manager"),
        ("it_admin_approval", "it_access_it_admin"),
    ):
        verdict_override = (
            "defer"
            if gate_phase == "line_manager_approval" and line_manager_ooo
            else None
        )
        d = build_decision(
            workflow,
            gate_phase=gate_phase,
            persona_role=persona,
            source_event="workflow.hitl.requested",
            decided_on=(person_id, asset_id),
            attributes={"employee_id": employee_id, "templates": templates},
            verdict_override=verdict_override,
        )
        if d is not None:
            ops.append(d)

    return ops
