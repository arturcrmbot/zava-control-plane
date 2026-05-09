"""Test the contract-renewal projection (TASK-021)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite, RelWrite
from api.server.services.entity_projections.contract_renewal import (
    project, WORKFLOW_TYPE,
)

from ._helpers import fixture_payload, make_workflow


def test_contract_renewal_projection_emits_vendor_contract_and_money():
    payload = fixture_payload("contract-renewal", "contracts.json")
    wf = make_workflow("CRN-T1", WORKFLOW_TYPE, payload)

    ops = project(wf)
    entities = [o for o in ops if isinstance(o, EntityWrite)]
    rels = [o for o in ops if isinstance(o, RelWrite)]

    asset = next(e for e in entities if e.kind == "Asset")
    money = next(e for e in entities if e.kind == "Money")
    assert asset.attrs["status"] == "renewing"
    assert money.attrs["amount"] == float(payload["proposed_annual_value"])
    assert money.attrs["prior_value"] == float(payload["current_annual_value"])

    assert any(r.rel == "TRANSACTS" for r in rels)
    assert any(r.rel == "BELONGS_TO" for r in rels)
