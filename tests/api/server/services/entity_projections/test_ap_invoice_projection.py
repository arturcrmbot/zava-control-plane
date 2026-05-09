"""Test the AP-invoice projection (TASK-015)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite, RelWrite
from api.server.services.entity_projections.ap_invoice import project, WORKFLOW_TYPE

from ._helpers import fixture_payload, make_workflow


def test_ap_invoice_projection_emits_core_entities():
    payload = fixture_payload("ap-invoice", "invoices.json")
    wf = make_workflow("API-T1", WORKFLOW_TYPE, payload)

    ops = project(wf)
    entities = [o for o in ops if isinstance(o, EntityWrite)]
    rels = [o for o in ops if isinstance(o, RelWrite)]
    kinds = {e.kind for e in entities}

    assert "Organisation" in kinds
    assert "Asset" in kinds
    assert "Money" in kinds

    money = next(e for e in entities if e.kind == "Money")
    assert money.id == f"MONEY-INV-{payload['invoice_id']}"
    assert money.attrs["amount"] == float(payload["amount_gbp"])
    assert money.attrs["currency"] == payload["currency"]

    rel_kinds = {(r.src_id.split("-")[0], r.rel) for r in rels}
    assert ("MONEY", "TRANSACTS") in rel_kinds
    assert ("MONEY", "OWNS") in rel_kinds
