"""Phase 1 (Intake) graph for expense claims — drives the workflow with a stub
field-extractor and asserts the four-node order via the final output shape."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest

from api.functions.graphs.intake_expense import build_intake_expense_workflow


CLAIM = {
    "claim_id": "CLM-0007",
    "amount": 142.0,
    "currency": "GBP",
    "category": "meals",
    "market": "UK",
    "attendees": 3,
    "vendor": "Côte Brasserie",
    "ems_source": "workday",
    "receipt_filename": "CLM-0007.png",
}


@pytest.mark.asyncio
async def test_intake_graph_drives_pipeline_to_terminal_on_complete_input():
    fake_extracted = {
        "amount": 142.0,
        "currency": "GBP",
        "category": "meals",
        "market": "UK",
        "attendees": 3,
        "vendor": "Côte Brasserie",
    }
    with patch(
        "api.functions.graphs.executors.agents.agent_field_extractor.execute",
        AsyncMock(return_value={"extracted": fake_extracted}),
    ):
        wf = build_intake_expense_workflow()
        events = await wf.run({
            "workflow_id": "CLM-0007",
            "claim": dict(CLAIM),
        })
    out = events.get_outputs()[0]
    assert out["extracted"]["category"] == "meals"
    # validate_required_fields ran last and passed
    assert out.get("ok") is True
    assert out.get("missing") == []
    # lookup_claim populated the canonical OCR-ish shape
    assert out["structure"]["claim_id"] == "CLM-0007"
    assert "CLAIM CLM-0007" in out["raw_text"]
    # claim_record carried the looked-up claim through
    assert out["claim_record"]["claim_id"] == "CLM-0007"


@pytest.mark.asyncio
async def test_intake_graph_blocks_on_missing_fields():
    bad = {"amount": 0, "currency": "GBP"}  # missing category, market, vendor
    with patch(
        "api.functions.graphs.executors.agents.agent_field_extractor.execute",
        AsyncMock(return_value={"extracted": bad}),
    ):
        wf = build_intake_expense_workflow()
        events = await wf.run({
            "workflow_id": "CLM-bad",
            "claim": {"claim_id": "CLM-bad", "ems_source": "workday"},
        })
    out = events.get_outputs()[0]
    assert out.get("ok") is False
    missing = set(out.get("missing") or [])
    assert {"category", "market", "vendor"} <= missing


@pytest.mark.asyncio
async def test_intake_graph_calls_claim_lookup_when_only_claim_id_given():
    fake_extracted = dict(CLAIM)
    with patch(
        "api.functions.graphs.executors.agents.agent_field_extractor.execute",
        AsyncMock(return_value={"extracted": fake_extracted}),
    ), patch(
        "api.server.mcp_tools.claim_lookup.lookup",
        return_value=dict(CLAIM),
    ) as mock_lookup:
        wf = build_intake_expense_workflow()
        events = await wf.run({
            "workflow_id": "CLM-0007",
            "claim_id": "CLM-0007",
            "ems_source": "workday",
        })
    out = events.get_outputs()[0]
    mock_lookup.assert_called_once_with("CLM-0007", ems_source="workday")
    assert out["claim_record"]["claim_id"] == "CLM-0007"
    assert out.get("ok") is True
