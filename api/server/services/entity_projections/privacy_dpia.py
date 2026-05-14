"""Projection: privacy-dpia (TASK-024).

Rels emitted: none. Asset->LOCATED_IN->Place is schema-invalid
(LOCATED_IN is Person→Place); the Place node remains as provenance.

Payload keys (``data/synthetic/privacy-dpia/dpias.json``)::

    dpia_id, system_name, risk_tier, geography, scenario

The CPO sign-off DecisionWrite is only emitted on high-risk DPIAs
(``risk_tier == "high"`` or ``"high_risk"``); the DPO review gate is
unconditional.

Note: today's ``api.shared.domains`` registry collapses both gates into a
single ``approver_signoff`` HITL gate keyed by the resolved persona. This
projection nonetheless looks for ``privacy_dpo_review`` and
``privacy_cpo_signoff`` payload entries to keep the per-persona schema open
for the upcoming Authority-Resolve unwind.
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

WORKFLOW_TYPE = "privacy-dpia"


def _is_high_risk(risk_tier: str) -> bool:
    return risk_tier.lower().replace("-", "_") in {"high", "high_risk"}


def project(workflow: Workflow) -> list[EntityWrite | RelWrite | DecisionWrite]:
    p = workflow.payload or {}
    d = p.get("dpia") or {}
    dpia_id = str(d.get("dpia_id") or p.get("dpia_id") or workflow.id)
    system_name = str(d.get("system_name") or p.get("system_name") or "")
    risk_tier = str(d.get("risk_tier") or p.get("risk_tier") or "")
    geography = str(d.get("geography") or p.get("geography") or "")

    asset_id = f"ASSET-dpia-{dpia_id}"
    place_id = f"PLACE-{geography}" if geography else None
    sw = (workflow.id,)

    asset_extra = {
        "system_name": system_name,
        "risk_tier": risk_tier,
        "geography": geography,
    }

    ops: list[EntityWrite | RelWrite | DecisionWrite] = [
        EntityWrite(
            kind="Asset",
            id=asset_id,
            attrs={
                "kind": "dpia",
                "identifier": dpia_id,
                "attributes": json.dumps(asset_extra, sort_keys=True, default=str),
            },
            source_workflows=sw,
        ),
    ]

    if place_id is not None:
        ops.append(EntityWrite(
            kind="Place",
            id=place_id,
            attrs={"kind": "region", "name": geography},
        ))
        # Schema's LOCATED_IN is FROM Person TO Place; emitting an
        # Asset->Place rel here would be rejected at write-time. The Place
        # node is left as provenance and the geography is also stashed in
        # the Asset's ``attributes`` blob.

    gates: list[tuple[str, str]] = [("privacy_dpo_review", "privacy_dpo")]
    if _is_high_risk(risk_tier):
        gates.append(("privacy_cpo_signoff", "privacy_cpo"))

    for gate_phase, persona in gates:
        d = build_decision(
            workflow,
            gate_phase=gate_phase,
            persona_role=persona,
            source_event="workflow.hitl.requested",
            decided_on=(asset_id,),
            attributes={"dpia_id": dpia_id, "risk_tier": risk_tier},
        )
        if d is not None:
            ops.append(d)

    return ops
