"""Test the treasury-fx projection (TASK-025)."""
from __future__ import annotations

from api.server.services.entity_graph import EntityWrite
from api.server.services.entity_projections.treasury_fx import (
    project, WORKFLOW_TYPE,
)

from ._helpers import fixture_payload, make_workflow


def test_treasury_fx_projection_emits_money_node():
    payload = fixture_payload("treasury-fx", "ops.json")
    wf = make_workflow("TFX-T1", WORKFLOW_TYPE, payload)

    ops = project(wf)
    entities = [o for o in ops if isinstance(o, EntityWrite)]
    money = next(e for e in entities if e.kind == "Money")
    assert money.id == f"MONEY-FX-{payload['op_id']}"
    assert money.attrs["amount"] == float(payload["notional_gbp"])
    assert money.attrs["currency_pair"] == payload["currency_pair"]
    assert money.attrs["op_kind"] == payload["op_kind"]
