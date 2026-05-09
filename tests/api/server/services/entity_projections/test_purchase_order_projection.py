"""Test the purchase-order projection (TASK-016)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite, RelWrite
from api.server.services.entity_projections.purchase_order import project, WORKFLOW_TYPE

from ._helpers import fixture_payload, make_workflow


def test_purchase_order_projection_emits_core_entities():
    payload = fixture_payload("purchase-order", "pos.json")
    wf = make_workflow("POW-T1", WORKFLOW_TYPE, payload)

    ops = project(wf)
    entities = [o for o in ops if isinstance(o, EntityWrite)]
    rels = [o for o in ops if isinstance(o, RelWrite)]
    kinds = {e.kind for e in entities}

    assert {"Organisation", "Asset", "Money", "Period"} <= kinds
    money = next(e for e in entities if e.kind == "Money")
    assert money.attrs["currency"] == "GBP"
    assert money.attrs["kind"] == "budget-line"

    rel_pairs = {(r.src_id.split("-")[0], r.rel) for r in rels}
    assert ("ASSET", "TRANSACTS") in rel_pairs
    assert ("MONEY", "BELONGS_TO") in rel_pairs
