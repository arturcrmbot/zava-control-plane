"""Projection: creative-campaign (TASK-026).

Rels emitted: none. The Asset->TRANSACTS->Org (customer + agency) edges
were dropped in Phase 1 hardening because TRANSACTS is schema-typed
Person→Money. Customer / agency / jurisdictions are preserved via the
Asset's ``attributes`` blob and via the workflow's ``source_workflows``
arrays on every entity. Phase 2's compose-domain v4 will widen the schema
if richer rel directions are needed for FM queries.

Payload keys (``data/synthetic/creative-campaign/briefs.json``)::

    client_brand, category, audience, mandatory_messages, channels,
    kpis, constraints, jurisdictions, agency, scenario
"""
from __future__ import annotations

import json

from api.server.services.entity_projections import (
    DecisionWrite,
    EntityWrite,
    RelWrite,
    build_decision,
    slug,
)
from api.shared.types import Workflow

WORKFLOW_TYPE = "creative-campaign"


def project(workflow: Workflow) -> list[EntityWrite | RelWrite | DecisionWrite]:
    p = workflow.payload or {}
    client_brand = str(p.get("client_brand") or "unknown")
    agency = str(p.get("agency") or "unknown")
    category = str(p.get("category") or "")
    audience = str(p.get("audience") or "")
    channels = list(p.get("channels") or [])
    kpis = p.get("kpis") or {}
    constraints = list(p.get("constraints") or [])
    jurisdictions = list(p.get("jurisdictions") or [])

    customer_id = f"ORG-customer-{slug(client_brand)}"
    agency_id = f"ORG-agency-{slug(agency)}"
    asset_id = f"ASSET-campaign-{workflow.id}"
    sw = (workflow.id,)

    asset_extra = {
        "category": category,
        "audience": audience,
        "channels": channels,
        "kpis": kpis,
        "constraints": constraints,
        "jurisdictions": jurisdictions,
        "customer_id": customer_id,
        "agency_id": agency_id,
    }

    ops: list[EntityWrite | RelWrite | DecisionWrite] = [
        EntityWrite(
            kind="Organisation", id=customer_id,
            attrs={"name": client_brand, "kind": "customer"},
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Organisation", id=agency_id,
            attrs={"name": agency, "kind": "agency"},
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Asset", id=asset_id,
            attrs={
                "kind": "campaign",
                "attributes": json.dumps(asset_extra, sort_keys=True, default=str),
            },
            source_workflows=sw,
        ),
        # NOTE: Asset->TRANSACTS->Organisation (×2) dropped in Phase 1
        # hardening. TRANSACTS is schema-typed Person→Money.
    ]

    for jur in jurisdictions:
        place_id = f"PLACE-{jur}"
        ops.append(EntityWrite(
            kind="Place", id=place_id,
            attrs={"kind": "market", "name": str(jur)},
        ))
        # Asset->LOCATED_IN->Place is also schema-invalid (LOCATED_IN is
        # Person→Place); leave the Place node as provenance only.

    # The five HITL gates use ``creative_director`` for every persona today;
    # the spec calls out ``creative_strategy_director`` as a future-proof
    # alias when the persona registry splits the role.
    for gate_phase in (
        "brief_capture", "brief_approval", "concept_lock",
        "storyboard_approval", "final_signoff",
    ):
        d = build_decision(
            workflow,
            gate_phase=gate_phase,
            persona_role="creative_director",
            source_event="workflow.hitl.requested",
            decided_on=(asset_id,),
            attributes={"client_brand": client_brand, "agency": agency},
        )
        if d is not None:
            ops.append(d)

    return ops
