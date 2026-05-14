"""Projection: client-renewal (pitch-c3 + pitch-h6 entanglement).

Per pitch-c3 brief: a client-renewal workflow naturally yields a Pitch
(the renewal pitch) + a Campaign (the next-cycle campaign), so we emit
both pitch-e1 agency-domain kinds plus the client Organisation.

pitch-h6 (entanglement) extends the projection to also emit three child
Workflow nodes + SUB_WORKFLOW_OF rels so a single client-renewal rocket
visibly spawns the MSA renewal (contract-renewal), the privacy-dpia
compliance check, and the monthly-client-pnl portfolio review. The
MetaWorkflowReflector also mirrors the same SUB_WORKFLOW_OF edges from
``workflow.sub_spawned`` bus events; both writers MERGE on
(parent, child) so a double write is idempotent.
"""
from __future__ import annotations

from api.server.services.entity_projections import (
    DecisionWrite,
    EntityWrite,
    RelWrite,
    build_decision,
    slug,
)
from api.shared.types import Workflow

WORKFLOW_TYPE = "client-renewal"

CHILD_WORKFLOW_TYPES: tuple[str, ...] = (
    "contract-renewal",
    "privacy-dpia",
    "monthly-client-pnl",
)


def _child_id(child_type: str, parent_id: str) -> str:
    return f"WF-{child_type}-{parent_id}"


def project(workflow: Workflow) -> list[EntityWrite | RelWrite | DecisionWrite]:
    p = workflow.payload or {}
    r = p.get("renewal") or {}
    client_name = str(r.get("client_name") or p.get("client_name") or "unknown")
    annual_value = float(r.get("annual_value_gbp") or p.get("annual_value_gbp") or 0)
    brand_name = str(r.get("brand_name") or p.get("brand_name") or client_name)

    client_id = f"ORG-client-{slug(client_name)}"
    pitch_id = f"PITCH-renewal-{slug(client_name)}-{workflow.id}"
    campaign_id = f"CAMPAIGN-renewal-{slug(client_name)}-{workflow.id}"
    sw = (workflow.id,)

    ops: list[EntityWrite | RelWrite | DecisionWrite] = [
        EntityWrite(
            kind="Organisation",
            id=client_id,
            attrs={"name": client_name, "kind": "client"},
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Pitch",
            id=pitch_id,
            attrs={"name": f"Renewal: {brand_name}", "status": "in-progress",
                   "value_gbp": annual_value},
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Campaign",
            id=campaign_id,
            attrs={"name": f"Renewal: {brand_name}", "status": "planned"},
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Workflow",
            id=workflow.id,
            attrs={"workflow_type": WORKFLOW_TYPE, "status": workflow.status},
            source_workflows=sw,
        ),
    ]
    for child_type in CHILD_WORKFLOW_TYPES:
        cid = _child_id(child_type, workflow.id)
        ops.append(EntityWrite(
            kind="Workflow",
            id=cid,
            attrs={"workflow_type": child_type, "status": "spawned"},
            source_workflows=(cid,),
        ))
        ops.append(RelWrite(
            src_id=workflow.id,
            rel="SUB_WORKFLOW_OF",
            dst_id=cid,
        ))

    d = build_decision(
        workflow,
        gate_phase="account_director_signoff",
        persona_role="account_director",
        source_event="workflow.hitl.requested",
        decided_on=(client_id, pitch_id, campaign_id),
        attributes={"client_name": client_name, "annual_value_gbp": annual_value},
    )
    if d is not None:
        ops.append(d)

    return ops
