"""Test the creative-campaign projection (TASK-026)."""
from __future__ import annotations

import json

from api.server.services.entity_graph import EntityWrite, RelWrite
from api.server.services.entity_projections.creative_campaign import (
    project, WORKFLOW_TYPE,
)

from ._helpers import fixture_payload, make_workflow


def test_creative_campaign_projection_emits_customer_agency_and_campaign_asset():
    payload = fixture_payload("creative-campaign", "briefs.json")
    wf = make_workflow("CMP-T1", WORKFLOW_TYPE, payload, nest_under='brief')

    ops = project(wf)
    entities = [o for o in ops if isinstance(o, EntityWrite)]
    rels = [o for o in ops if isinstance(o, RelWrite)]

    org_kinds = sorted(e.attrs.get("kind") for e in entities if e.kind == "Organisation")
    assert org_kinds == ["agency", "customer"]

    asset = next(e for e in entities if e.kind == "Asset")
    assert asset.attrs["kind"] == "campaign"
    assert asset.id == f"ASSET-campaign-{wf.id}"

    # Non-schema fields routed into Asset.attributes JSON blob.
    asset_extra = json.loads(asset.attrs["attributes"])
    assert asset_extra["category"] == payload["category"]
    assert asset_extra["audience"] == payload["audience"]
    assert asset_extra["channels"] == list(payload["channels"])

    places = [e for e in entities if e.kind == "Place"]
    assert {p.id for p in places} == {f"PLACE-{j}" for j in payload["jurisdictions"]}

    # Asset->TRANSACTS->Org dropped — they were schema-invalid.
    # Campaign->CAMPAIGN_FOR->Brand and Campaign->EXECUTED_BY->Subsidiary
    # are emitted as first-class rels.
    rel_kinds = sorted(r.rel for r in rels)
    assert rel_kinds == ["CAMPAIGN_FOR", "EXECUTED_BY"]


def test_creative_campaign_emits_first_class_campaign():
    wf = make_workflow(
        "CMP-0001", "creative-campaign",
        {"client_brand": "Aurora", "agency": "Zava-Creative", "category": "fmcg",
         "channels": ["tv", "social"], "jurisdictions": ["UK", "US"]},
        nest_under="brief",
    )
    ops = project(wf)
    kinds = [op.kind for op in ops if isinstance(op, EntityWrite)]
    assert "Campaign" in kinds
    assert "MediaPlan" in kinds
