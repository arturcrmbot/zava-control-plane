"""Tests for ocr_extract MCP tool."""
from __future__ import annotations
import asyncio
from unittest.mock import MagicMock

import pytest
from copilot.tools import ToolInvocation

from api.server.mcp_tools import ocr_extract
from api.server.mcp_tools.ocr_extract import get_ocr, _OcrExtractParams, ocr_extract_tool


def _invoke(params: _OcrExtractParams):
    """Tool objects from @define_tool expose an async handler — drive it from sync tests.
    The handler unpacks ToolInvocation.arguments via pydantic, so we pass the dict form."""
    inv = ToolInvocation(arguments=params.model_dump())
    return asyncio.run(ocr_extract_tool.handler(inv))


def _stub_di_client(monkeypatch, payload: dict):
    """Replace _get_di_client with a MagicMock returning a poller whose .result()
    returns a MagicMock with .as_dict() yielding `payload`."""
    fake_result = MagicMock()
    fake_result.as_dict.return_value = payload
    fake_poller = MagicMock()
    fake_poller.result.return_value = fake_result
    fake_client = MagicMock()
    fake_client.begin_analyze_document.return_value = fake_poller
    monkeypatch.setattr(ocr_extract, "_get_di_client", lambda: fake_client)
    return fake_client


def test_resolves_clm_id_to_receipt_path(tmp_path, monkeypatch):
    """A `CLM-*` id resolves to data/synthetic/receipts/{id}.png."""
    receipts_dir = tmp_path / "receipts"
    receipts_dir.mkdir()
    (receipts_dir / "CLM-0001.png").write_bytes(b"\x89PNG\r\n\x1a\nfake-png")
    monkeypatch.setattr(ocr_extract, "_RECEIPTS_DIR", receipts_dir)
    monkeypatch.setattr(ocr_extract, "_PDFS_DIR", tmp_path / "absent")
    monkeypatch.setattr(ocr_extract, "_cache", {})
    fake_client = _stub_di_client(monkeypatch, {"documents": [], "tables": [], "pages": [], "model": "prebuilt-receipt"})

    record = get_ocr("CLM-0001", "prebuilt-receipt")

    assert record["model"] == "prebuilt-receipt"
    assert record["cached"] is False
    fake_client.begin_analyze_document.assert_called_once()
    call_kwargs = fake_client.begin_analyze_document.call_args
    assert call_kwargs.kwargs.get("model_id") == "prebuilt-receipt" or call_kwargs.args[0] == "prebuilt-receipt"


def test_resolves_c_id_to_pdf_path(tmp_path, monkeypatch):
    """A `C-*` id resolves to data/synthetic/hiring/cvs/pdfs/{id}.pdf."""
    pdfs_dir = tmp_path / "pdfs"
    pdfs_dir.mkdir()
    (pdfs_dir / "C-SE-USA-00.pdf").write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(ocr_extract, "_RECEIPTS_DIR", tmp_path / "absent")
    monkeypatch.setattr(ocr_extract, "_PDFS_DIR", pdfs_dir)
    monkeypatch.setattr(ocr_extract, "_cache", {})
    _stub_di_client(monkeypatch, {"documents": [], "tables": [], "pages": [], "model": "prebuilt-layout"})

    record = get_ocr("C-SE-USA-00", "prebuilt-layout")

    assert record["model"] == "prebuilt-layout"
    assert record["cached"] is False


def test_caches_by_sha256_and_model(tmp_path, monkeypatch):
    """Second call with same bytes + model returns cached: true and does not hit DI again."""
    receipts_dir = tmp_path / "receipts"
    receipts_dir.mkdir()
    (receipts_dir / "CLM-0042.png").write_bytes(b"\x89PNG\r\n\x1a\nfake-bytes-deterministic")
    monkeypatch.setattr(ocr_extract, "_RECEIPTS_DIR", receipts_dir)
    monkeypatch.setattr(ocr_extract, "_PDFS_DIR", tmp_path / "absent")
    monkeypatch.setattr(ocr_extract, "_cache", {})
    fake_client = _stub_di_client(monkeypatch, {"documents": [{"fields": {"merchantName": {"value": "Côte", "confidence": 0.99}}}], "tables": [], "pages": [], "keyValuePairs": []})

    first = get_ocr("CLM-0042", "prebuilt-receipt")
    second = get_ocr("CLM-0042", "prebuilt-receipt")

    assert first["cached"] is False
    assert second["cached"] is True
    assert second["documents"] == first["documents"]
    assert fake_client.begin_analyze_document.call_count == 1


def test_cache_is_keyed_on_model_too(tmp_path, monkeypatch):
    """Same bytes with different model => DI is called twice."""
    receipts_dir = tmp_path / "receipts"
    receipts_dir.mkdir()
    (receipts_dir / "CLM-0099.png").write_bytes(b"\x89PNG\r\n\x1a\nbytes-v2")
    monkeypatch.setattr(ocr_extract, "_RECEIPTS_DIR", receipts_dir)
    monkeypatch.setattr(ocr_extract, "_PDFS_DIR", tmp_path / "absent")
    monkeypatch.setattr(ocr_extract, "_cache", {})
    fake_client = _stub_di_client(monkeypatch, {"documents": [], "tables": [], "pages": [], "keyValuePairs": []})

    get_ocr("CLM-0099", "prebuilt-receipt")
    get_ocr("CLM-0099", "prebuilt-document")

    assert fake_client.begin_analyze_document.call_count == 2


def test_unknown_id_prefix_raises_valueerror():
    """An id like 'INV-001' is rejected — only CLM-* and C-* are valid."""
    with pytest.raises(ValueError, match="recognised prefix"):
        ocr_extract._resolve_path("INV-001")


def test_missing_file_raises_filenotfounderror(tmp_path, monkeypatch):
    """Resolved path doesn't exist on disk → FileNotFoundError."""
    monkeypatch.setattr(ocr_extract, "_RECEIPTS_DIR", tmp_path)
    monkeypatch.setattr(ocr_extract, "_PDFS_DIR", tmp_path)
    monkeypatch.setattr(ocr_extract, "_cache", {})
    with pytest.raises(FileNotFoundError):
        get_ocr("CLM-9999", "prebuilt-receipt")


def test_missing_env_var_raises_runtimeerror_via_tool(tmp_path, monkeypatch):
    """Tool wrapper catches the RuntimeError and returns failure ToolResult."""
    receipts_dir = tmp_path / "receipts"
    receipts_dir.mkdir()
    (receipts_dir / "CLM-0001.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
    monkeypatch.setattr(ocr_extract, "_RECEIPTS_DIR", receipts_dir)
    monkeypatch.setattr(ocr_extract, "_PDFS_DIR", tmp_path / "absent")
    monkeypatch.setattr(ocr_extract, "_cache", {})
    monkeypatch.delenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", raising=False)

    result = _invoke(_OcrExtractParams(document_id="CLM-0001", model="prebuilt-receipt"))
    assert result.result_type == "failure"
    assert "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT" in (result.error or "")


def test_di_call_failure_returns_failure_toolresult(tmp_path, monkeypatch):
    """A DI SDK exception (e.g. timeout) becomes a failure ToolResult, not a crash."""
    receipts_dir = tmp_path / "receipts"
    receipts_dir.mkdir()
    (receipts_dir / "CLM-0001.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
    monkeypatch.setattr(ocr_extract, "_RECEIPTS_DIR", receipts_dir)
    monkeypatch.setattr(ocr_extract, "_PDFS_DIR", tmp_path / "absent")
    monkeypatch.setattr(ocr_extract, "_cache", {})

    def _boom():
        raise TimeoutError("simulated DI timeout")
    monkeypatch.setattr(ocr_extract, "_get_di_client", _boom)

    result = _invoke(_OcrExtractParams(document_id="CLM-0001", model="prebuilt-receipt"))
    assert result.result_type == "failure"
    assert "TimeoutError" in (result.text_result_for_llm or "") or "timeout" in (result.error or "").lower()
