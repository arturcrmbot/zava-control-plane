"""Tests for claim_get_receipt MCP tool."""
from __future__ import annotations
import base64
import json

import pytest

from api.server.mcp_tools import claim_get_receipt
from api.server.mcp_tools.claim_get_receipt import claim_get_receipt_tool, get_receipt


def test_returns_image_b64_for_existing_claim():
    record = get_receipt("CLM-0000")
    assert record["claim_id"] == "CLM-0000"
    assert record["absent"] is False
    assert record["size_bytes"] > 0
    assert record["image_b64"]
    # Round-trip: decoding base64 should give us bytes that match size_bytes.
    decoded = base64.b64decode(record["image_b64"])
    assert len(decoded) == record["size_bytes"]


def test_reports_absent_for_missing_receipt_flavour(tmp_path, monkeypatch):
    """Zero-byte PNGs (missing-receipt flavour) report absent=True."""
    # Stub get_structured to return a missing-receipt claim and redirect the
    # receipts dir to tmp_path with a zero-byte file.
    fake_dir = tmp_path / "receipts"
    fake_dir.mkdir()
    (fake_dir / "CLM-X.png").write_bytes(b"")
    monkeypatch.setattr(claim_get_receipt, "_RECEIPTS_DIR", fake_dir)
    monkeypatch.setattr(
        claim_get_receipt,
        "get_structured",
        lambda cid, include_gold=False: {
            "claim_id": cid,
            "receipt_filename": "CLM-X.png",
            "receipt_mismatch_flavour": "missing-receipt",
        },
    )

    record = get_receipt("CLM-X")
    assert record["absent"] is True
    assert record["size_bytes"] == 0
    assert record["image_b64"] is None
    assert record["flavour"] == "missing-receipt"


def test_raises_when_receipt_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(claim_get_receipt, "_RECEIPTS_DIR", tmp_path)
    monkeypatch.setattr(
        claim_get_receipt,
        "get_structured",
        lambda cid, include_gold=False: {
            "claim_id": cid,
            "receipt_filename": f"{cid}.png",
            "receipt_mismatch_flavour": "correct",
        },
    )
    with pytest.raises(FileNotFoundError):
        get_receipt("CLM-9999")


def test_tool_returns_structured_summary_without_b64():
    """The SDK tool wrapper strips image_b64 from the LLM-visible payload."""
    result = claim_get_receipt_tool.handler.__wrapped__ if hasattr(
        claim_get_receipt_tool.handler, "__wrapped__"
    ) else None  # cosmetic; main path tested via direct invocation below

    # Invoke the tool's wrapped handler synchronously by calling .handler
    # through ToolInvocation construction.
    from copilot.tools import ToolInvocation
    import asyncio

    inv = ToolInvocation(
        session_id="t", tool_call_id="t", tool_name="claim_get_receipt",
        arguments={"claim_id": "CLM-0000"},
    )
    result = asyncio.run(claim_get_receipt_tool.handler(inv))

    assert result.result_type == "success"
    payload = json.loads(result.text_result_for_llm)
    assert payload["claim_id"] == "CLM-0000"
    assert payload["absent"] is False
    assert "image_b64" not in payload  # stripped


def test_tool_reports_failure_for_unknown_claim_id():
    from copilot.tools import ToolInvocation
    import asyncio

    inv = ToolInvocation(
        session_id="t", tool_call_id="t", tool_name="claim_get_receipt",
        arguments={"claim_id": "CLM-9999"},
    )
    result = asyncio.run(claim_get_receipt_tool.handler(inv))
    assert result.result_type == "failure"
