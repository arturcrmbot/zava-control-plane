"""ocr_extract MCP tool — Azure AI Document Intelligence wrapper.

See `api/server/skills/use-document-intelligence/SKILL.md` for the runbook
the model follows when calling this tool.

Resolves a domain identifier (claim id `CLM-*` or candidate id `C-*`) to a
local file under data/synthetic/, runs DI's begin_analyze_document on the
bytes, trims the response to the keys agents care about, and caches by
sha256(bytes) + model_id so repeated demo runs don't re-bill.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
from typing import Literal

from copilot.tools import ToolResult, define_tool
from pydantic import BaseModel, Field

from ._otel import traced_tool

_RECEIPTS_DIR = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "receipts"
_PDFS_DIR = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "hiring" / "cv-pdfs"

_OcrModel = Literal[
    "prebuilt-receipt",
    "prebuilt-layout",
    "prebuilt-invoice",
    "prebuilt-document",
    "prebuilt-idDocument",
]

_cache: dict[tuple[str, str], dict] = {}


def _resolve_path(document_id: str) -> Path:
    """Map domain id → local path. CLM-* → receipts dir; C-* → CV pdfs dir."""
    if document_id.startswith("CLM-"):
        return _RECEIPTS_DIR / f"{document_id}.png"
    if document_id.startswith("C-"):
        return _PDFS_DIR / f"{document_id}.pdf"
    raise ValueError(
        f"document_id {document_id!r} has no recognised prefix "
        f"(expected CLM-* for receipts or C-* for CVs)"
    )


def _get_di_client():
    """Return a configured DocumentIntelligenceClient or raise RuntimeError.

    Auth via Entra ID (DefaultAzureCredential) — the local-auth (key) path is
    disabled by tenant policy in this subscription. The signed-in identity (or
    the func host's managed identity in cloud) needs the "Cognitive Services
    User" role on the DI resource.
    """
    endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    if not endpoint:
        raise RuntimeError(
            "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT is not configured. Set it in "
            ".env (FastAPI) and local.settings.json (func host)."
        )
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.identity import DefaultAzureCredential
    return DocumentIntelligenceClient(endpoint, DefaultAzureCredential())


def _trim_di_result(payload: dict, model: str) -> dict:
    """Keep the keys agents need; drop bounding-box pixel coords + diagnostic noise."""
    return {
        "model": model,
        "documents": payload.get("documents", []),
        "tables": payload.get("tables", []),
        "keyValuePairs": payload.get("keyValuePairs", []),
        "pages": [
            {"pageNumber": p.get("pageNumber"), "lines": p.get("lines", [])}
            for p in payload.get("pages", [])
        ],
        "cached": False,
    }


def get_ocr(document_id: str, model: str) -> dict:
    """Plain Python entry point (no MCP wrapping). Used by tests + agent helpers."""
    path = _resolve_path(document_id)
    if not path.exists():
        raise FileNotFoundError(f"document {document_id} not found at {path}")
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    key = (sha, model)
    if key in _cache:
        return {**_cache[key], "cached": True}
    client = _get_di_client()
    poller = client.begin_analyze_document(model_id=model, body=raw)
    result = poller.result()
    payload = result.as_dict() if hasattr(result, "as_dict") else dict(result)
    trimmed = _trim_di_result(payload, model)
    _cache[key] = {**trimmed}
    return trimmed


class _OcrExtractParams(BaseModel):
    document_id: str = Field(description="Claim id (CLM-*) or candidate id (C-*)")
    model: _OcrModel = Field(default="prebuilt-receipt", description="DI prebuilt model to invoke")


@define_tool(
    name="ocr_extract",
    description=(
        "Run Azure AI Document Intelligence on a local document (receipt PNG or CV PDF). "
        "Returns structured fields, tables, key-value pairs, and full text lines. "
        "See use-document-intelligence skill for model selection + response interpretation."
    ),
)
@traced_tool("ocr.extract")
def ocr_extract_tool(params: _OcrExtractParams) -> ToolResult:
    try:
        record = get_ocr(params.document_id, params.model)
    except FileNotFoundError as e:
        return ToolResult(
            text_result_for_llm=f"document not found: {params.document_id}",
            result_type="failure",
            error=str(e),
        )
    except RuntimeError as e:
        return ToolResult(
            text_result_for_llm="document intelligence not configured",
            result_type="failure",
            error=str(e),
        )
    except Exception as e:
        return ToolResult(
            text_result_for_llm=f"document intelligence call failed: {type(e).__name__}",
            result_type="failure",
            error=str(e),
        )
    return ToolResult(text_result_for_llm=json.dumps(record, ensure_ascii=False))
