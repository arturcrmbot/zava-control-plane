"""Projection: network-incident (telco actor-world domain).

Focused, schema-additive projection using only existing node kinds. Emits:

  * a ``Workflow`` stamp node, and
  * one ``Asset`` node (kind ``cell-site``) for the incident site, carrying
    the region/status and (when present) the rerouted-session count, and
  * an optional autonomous ``Decision`` when the payload records the
    ``reroute_execution`` outcome — the domain has no HITL gate, so the
    decision is agent-authored, not persona-gated.

No new graph schema; no relationships beyond the decision target. The live
authority for the incident lifecycle is the actor-world journal — this
projection only surfaces the workflow in the entity graph for registry
parity + dashboards.
"""
from __future__ import annotations

import json

from api.server.services.entity_projections import (
    DecisionWrite,
    EntityWrite,
    build_decision,
    slug,
)
from api.shared.types import Workflow

WORKFLOW_TYPE = "network-incident"


def _incident_site(payload: dict) -> dict:
    incident = payload.get("incident") or {}
    # Replay tapes may retain the producer's legacy double nesting.
    if "incident_site" not in incident and isinstance(incident.get("incident"), dict):
        incident = incident["incident"]
    site = incident.get("incident_site")
    return site if isinstance(site, dict) else {}


def project(workflow: Workflow) -> list[EntityWrite | DecisionWrite]:
    payload = workflow.payload or {}
    site = _incident_site(payload)
    site_id = str(site.get("id") or workflow.id)
    asset_id = f"ASSET-site-{slug(site_id)}"
    sw = (workflow.id,)

    asset_attrs = {
        "kind": "cell-site",
        "identifier": site_id,
        "attributes": json.dumps(
            {
                "region": site.get("region"),
                "status": site.get("status"),
                "capacity_mbps": site.get("capacity_mbps"),
            },
            sort_keys=True,
            default=str,
        ),
    }

    ops: list[EntityWrite | DecisionWrite] = [
        EntityWrite(
            kind="Workflow",
            id=workflow.id,
            attrs={"workflow_type": WORKFLOW_TYPE, "status": workflow.status},
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Asset",
            id=asset_id,
            attrs=asset_attrs,
            source_workflows=sw,
        ),
    ]

    # Autonomous, reversible mitigation — no HITL gate. A DecisionWrite is
    # still emitted when the payload records the reroute outcome so the
    # agent's action is auditable in the entity graph.
    d = build_decision(
        workflow,
        gate_phase="reroute_execution",
        persona_role="network_incident",
        source_event="world.responder.decided",
        decided_on=(asset_id,),
        attributes={"site_id": site_id},
    )
    if d is not None:
        ops.append(d)

    return ops
