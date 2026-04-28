"""agent_receipt_validator tests — mocks the SDK session wrapper."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest

from api.functions.graphs.executors.agents import agent_receipt_validator


@pytest.mark.asyncio
async def test_short_circuits_for_missing_receipt(monkeypatch):
    """Zero-byte receipts return a canonical missing-receipt verdict
    without spinning up a session — saves tokens."""
    monkeypatch.setattr(
        agent_receipt_validator, "get_receipt",
        lambda cid: {
            "claim_id": cid, "filename": f"{cid}.png", "size_bytes": 0,
            "flavour": "missing-receipt", "absent": True, "image_b64": None,
        },
    )
    with patch.object(agent_receipt_validator, "run_agent_session", AsyncMock()) as mock_run:
        result = await agent_receipt_validator.execute({"claim_id": "CLM-X"})

    mock_run.assert_not_called()
    v = result["receipt_validation"]
    assert v["verdict"] == "mismatch"
    assert v["flavour"] == "missing-receipt"
    assert "CLM-X" in v["evidence"]
    assert v["confidence"] == 1.0


@pytest.mark.asyncio
async def test_passes_image_attachment_and_tools_for_present_receipt(monkeypatch):
    monkeypatch.setattr(
        agent_receipt_validator, "get_receipt",
        lambda cid: {
            "claim_id": cid, "filename": f"{cid}.png", "size_bytes": 12345,
            "flavour": "correct", "absent": False, "image_b64": "iVBORw0KGgo=FAKE",
        },
    )
    fake = {
        "verdict": "match", "flavour": "correct",
        "evidence": "Receipt totals match.", "confidence": 0.92,
    }
    with patch.object(agent_receipt_validator, "run_agent_session", AsyncMock(return_value=fake)) as mock_run:
        result = await agent_receipt_validator.execute({"claim_id": "CLM-0000"})

    assert result["receipt_validation"] == fake
    mock_run.assert_awaited_once()
    _, kwargs = mock_run.call_args
    assert "CLM-0000" in kwargs["prompt"]
    assert kwargs["skill_label"] == "receipt-validator"
    # The SDK tool list registers exactly claim_get_structured (image is on
    # the multimodal attachment channel, not a tool).
    tool_names = {t.name for t in kwargs["tools"]}
    assert tool_names == {"claim_get_structured"}
    # Image attached to the session, not embedded in the prompt.
    assert kwargs["attachments"] == [
        {"type": "inline", "content_type": "image/png", "data": "iVBORw0KGgo=FAKE"}
    ]


@pytest.mark.asyncio
async def test_passes_through_parse_error(monkeypatch):
    monkeypatch.setattr(
        agent_receipt_validator, "get_receipt",
        lambda cid: {
            "claim_id": cid, "filename": f"{cid}.png", "size_bytes": 1024,
            "flavour": None, "absent": False, "image_b64": "iVBORw=AAAA",
        },
    )
    parse_err = {"raw": "model talked instead of JSON", "parse_error": True}
    with patch.object(agent_receipt_validator, "run_agent_session", AsyncMock(return_value=parse_err)):
        result = await agent_receipt_validator.execute({"claim_id": "CLM-0000"})
    assert result["receipt_validation"]["parse_error"] is True
