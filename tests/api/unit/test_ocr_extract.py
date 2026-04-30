"""Tests for ocr_extract MCP tool."""
from __future__ import annotations
from unittest.mock import MagicMock

import pytest

from api.server.mcp_tools import ocr_extract
from api.server.mcp_tools.ocr_extract import get_ocr, _OcrExtractParams, ocr_extract_tool


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
