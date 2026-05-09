"""Test the contract-review projection (TASK-022)."""
from __future__ import annotations

import json

from api.server.services.entity_graph import EntityWrite, RelWrite
from api.server.services.entity_projections.contract_review import (
    project, WORKFLOW_TYPE,
)

from ._helpers import fixture_payload, make_workflow


def test_contract_review_projection_emits_vendor_and_contract_asset():
    payload = fixture_payload("contract-review", "contracts.json")
    wf = make_workflow("CRW-T1", WORKFLOW_TYPE, payload)

    ops = project(wf)
    entities = [o for o in ops if isinstance(o, EntityWrite)]
    rels = [o for o in ops if isinstance(o, RelWrite)]

    asset = next(e for e in entities if e.kind == "Asset")
    assert asset.attrs["kind"] == "contract"

    # contract_type / deviates_from_template are not Asset schema columns;
    # they live in the ``attributes`` JSON blob (Phase 1 hardening).
    asset_extra = json.loads(asset.attrs["attributes"])
    assert asset_extra["contract_type"] == payload["contract_type"]
    assert asset_extra["deviates_from_template"] == payload["deviates_from_template"]

    # Asset->TRANSACTS->Org dropped — it was schema-invalid.
    assert rels == []
