"""Projection: fy-close (pitch-c1).

Emits a Period (the fiscal year) + an Organisation (the entity being
closed) + a DecisionWrite at the ceo_signoff gate.
"""
from __future__ import annotations

from api.server.services.entity_projections import (
    DecisionWrite,
    EntityWrite,
    build_decision,
    slug,
)
from api.shared.types import Workflow

WORKFLOW_TYPE = "fy-close"


def project(workflow: Workflow) -> list[EntityWrite | DecisionWrite]:
    p = workflow.payload or {}
    c = p.get("close") or {}
    fiscal_year = str(c.get("fiscal_year") or p.get("fiscal_year") or "FY-unknown")
    entity = str(c.get("entity") or p.get("entity") or "Zava-Group")

    period_id = f"PERIOD-{fiscal_year}"
    org_id = f"ORG-entity-{slug(entity)}"
    sw = (workflow.id,)

    ops: list[EntityWrite | DecisionWrite] = [
        EntityWrite(
            kind="Period",
            id=period_id,
            attrs={"kind": "fiscal-year", "label": fiscal_year},
        ),
        EntityWrite(
            kind="Organisation",
            id=org_id,
            attrs={"name": entity, "kind": "legal-entity"},
            source_workflows=sw,
        ),
    ]

    d = build_decision(
        workflow,
        gate_phase="ceo_signoff",
        persona_role="controller",
        source_event="workflow.hitl.requested",
        decided_on=(period_id, org_id),
        attributes={"fiscal_year": fiscal_year, "entity": entity},
    )
    if d is not None:
        ops.append(d)

    return ops
