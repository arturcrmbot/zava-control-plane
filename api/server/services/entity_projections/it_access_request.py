"""Projection: it-access-request (TASK-019).

Payload keys (``data/synthetic/it-access-request/requests.json``)::

    employee_id, department, requested_role_templates, business_justification, scenario
"""
from __future__ import annotations

import json

from api.server.services.entity_projections import (
    DecisionWrite,
    EntityWrite,
    RelWrite,
    build_decision,
)
from api.shared.types import Workflow

WORKFLOW_TYPE = "it-access-request"


def project(workflow: Workflow) -> list[EntityWrite | RelWrite | DecisionWrite]:
    p = workflow.payload or {}
    employee_id = str(p.get("employee_id") or "unknown")
    department = str(p.get("department") or "")
    templates = list(p.get("requested_role_templates") or [])
    justification = str(p.get("business_justification") or "")

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

    for gate_phase, persona in (
        ("line_manager_approval", "it_access_line_manager"),
        ("it_admin_approval", "it_access_it_admin"),
    ):
        d = build_decision(
            workflow,
            gate_phase=gate_phase,
            persona_role=persona,
            source_event="workflow.hitl.requested",
            decided_on=(person_id, asset_id),
            attributes={"employee_id": employee_id, "templates": templates},
        )
        if d is not None:
            ops.append(d)

    return ops
