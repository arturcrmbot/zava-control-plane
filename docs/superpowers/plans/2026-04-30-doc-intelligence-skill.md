# Document Intelligence Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire real Azure AI Document Intelligence behind the existing `receipt-validator` (POC1) and `cv-crystalliser` (POC2) skills via one new `use-document-intelligence` skill plus one new `ocr_extract` MCP tool, plus 50 hand-crafted CV PDFs for POC2 to operate on.

**Architecture:** One Pydantic-backed MCP tool (`ocr_extract`) wraps `azure-ai-documentintelligence` SDK and is registered on the receipt-validator agent session. One new SKILL.md documents DI usage as a runbook for the model. Two existing skill files gain a "Step 0: extract" pre-step. PDF generator (`weasyprint`) emits 50 hand-crafted CVs from the existing JSON records using 4 templates plus 5 salted edge cases.

**Tech Stack:** Python 3.11, `azure-ai-documentintelligence` v1+ SDK, `weasyprint` (PDF generator), pytest, GHCP SDK (`copilot` package), OpenTelemetry.

**Spec:** [docs/superpowers/specs/2026-04-30-doc-intelligence-skill-design.md](../specs/2026-04-30-doc-intelligence-skill-design.md)

---

## File Structure

**Create:**
- `api/server/mcp_tools/ocr_extract.py` — the MCP tool wrapping DI SDK
- `api/server/skills/use-document-intelligence/SKILL.md` — runbook for the agent
- `data/synthetic/hiring/cvs/templates/classic-serif.html`
- `data/synthetic/hiring/cvs/templates/modern-sans.html`
- `data/synthetic/hiring/cvs/templates/two-column.html`
- `data/synthetic/hiring/cvs/templates/technical.html`
- `data/synthetic/hiring/cvs/generate_pdfs.py` — generator script
- `data/synthetic/hiring/cvs/pdfs/{candidate_id}.pdf` × 50 — generated artifacts
- `tests/api/unit/test_ocr_extract.py` — unit tests for the tool

**Modify:**
- `pyproject.toml` — add `azure-ai-documentintelligence` and `weasyprint` deps
- `requirements.txt` — re-exported by `uv export`
- `.env` — add the two `AZURE_DOCUMENT_INTELLIGENCE_*` vars
- `local.settings.json` — same two vars in `Values`
- `api/server/skills/receipt-validator/SKILL.md` — Step 0, frontmatter, output schema
- `api/server/skills/cv-crystalliser/SKILL.md` — same shape
- `api/functions/graphs/executors/agents/agent_receipt_validator.py` — register `ocr_extract_tool` in `tools=[...]`

---

## Task 1: Add Python dependencies

**Files:**
- Modify: `pyproject.toml`
- Modify: `requirements.txt` (regenerated)
- Modify: `.funcvenv/` (deps installed)

- [ ] **Step 1: Add deps via uv**

```bash
uv add azure-ai-documentintelligence weasyprint
```

Expected: pyproject.toml gains `azure-ai-documentintelligence>=1.0.0` and `weasyprint>=63.0` under `[project.dependencies]`. Lockfile (`uv.lock`) updates.

- [ ] **Step 2: Re-export requirements.txt**

```bash
uv export --no-dev --no-hashes --format requirements-txt -o requirements.txt
```

Expected: `requirements.txt` gains the two new packages plus any transitive deps (e.g. `azure-core`, `pillow`, `pydyf`, `cssselect2`, `pyphen`, `tinycss2`).

- [ ] **Step 3: Install into the func host venv**

```bash
.funcvenv/Scripts/python.exe -m pip install -r requirements.txt --quiet
```

Expected: completes without error. May print one notice about pip upgrade — ignore it.

- [ ] **Step 4: Smoke-test imports**

```bash
.funcvenv/Scripts/python.exe -c "from azure.ai.documentintelligence import DocumentIntelligenceClient; import weasyprint; print('imports ok')"
```

Expected output: `imports ok`. If `weasyprint` errors with a GTK/Cairo missing-DLL message on Windows, install GTK runtime (https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases) and re-run.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock requirements.txt
git commit -m "deps: add azure-ai-documentintelligence + weasyprint"
```

---

## Task 2: Add new env vars (placeholders)

**Files:**
- Modify: `.env`
- Modify: `local.settings.json`

- [ ] **Step 1: Add to `.env`**

Append at the bottom of `c:\dev\ghcp sdk stuff\.env`:

```
# Azure AI Document Intelligence — set both before running OCR-using workflows.
# Leave unset and ocr_extract will fail-fast with a clear error.
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=
AZURE_DOCUMENT_INTELLIGENCE_KEY=
```

- [ ] **Step 2: Add to `local.settings.json` Values block**

Edit `c:\dev\ghcp sdk stuff\local.settings.json`. The `Values` block currently ends with `"FASTAPI_WEBHOOK_URL": "http://localhost:3001/internal/durable-event"`. Append:

```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "PYTHON_ISOLATE_WORKER_DEPENDENCIES": "0",
    "PYTHONPATH": "c:/dev/ghcp sdk stuff",
    "FASTAPI_WEBHOOK_URL": "http://localhost:3001/internal/durable-event",
    "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT": "",
    "AZURE_DOCUMENT_INTELLIGENCE_KEY": ""
  }
}
```

Note: leave the values blank in the committed file. The user will populate them locally with the real provisioned resource values.

- [ ] **Step 3: Commit**

```bash
git add .env local.settings.json
git commit -m "config: add AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT/KEY placeholders"
```

---

## Task 3: `ocr_extract` MCP tool — path resolution + happy path

**Files:**
- Create: `api/server/mcp_tools/ocr_extract.py`
- Create: `tests/api/unit/test_ocr_extract.py`

- [ ] **Step 1: Write the failing test (path resolution + DI call with mock)**

Create `tests/api/unit/test_ocr_extract.py`:

```python
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
    _stub_di_client(monkeypatch, {"documents": [], "tables": [], "pages": [], "model": "prebuilt-layout"})

    record = get_ocr("C-SE-USA-00", "prebuilt-layout")

    assert record["model"] == "prebuilt-layout"
    assert record["cached"] is False
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.funcvenv/Scripts/python.exe -m pytest tests/api/unit/test_ocr_extract.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` for `api.server.mcp_tools.ocr_extract` (file doesn't exist yet).

- [ ] **Step 3: Implement minimal tool (happy path only)**

Create `api/server/mcp_tools/ocr_extract.py`:

```python
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
_PDFS_DIR = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "hiring" / "cvs" / "pdfs"

_DI_MODELS = ("prebuilt-receipt", "prebuilt-layout", "prebuilt-invoice", "prebuilt-document", "prebuilt-idDocument")
_OcrModel = Literal["prebuilt-receipt", "prebuilt-layout", "prebuilt-invoice", "prebuilt-document", "prebuilt-idDocument"]

# In-memory cache, process-scoped. Key: (sha256, model). Value: trimmed dict.
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

    Imports the SDK lazily so tests can monkeypatch the entire helper without
    needing the real package installed at import time."""
    endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")
    if not endpoint or not key:
        missing = "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT" if not endpoint else "AZURE_DOCUMENT_INTELLIGENCE_KEY"
        raise RuntimeError(
            f"{missing} is not configured. Set both AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT "
            f"and AZURE_DOCUMENT_INTELLIGENCE_KEY in .env (FastAPI) and local.settings.json (func host)."
        )
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.core.credentials import AzureKeyCredential
    return DocumentIntelligenceClient(endpoint, AzureKeyCredential(key))


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
    _cache[key] = {**trimmed}  # store with cached=False; copy on hit
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
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
.funcvenv/Scripts/python.exe -m pytest tests/api/unit/test_ocr_extract.py -v
```

Expected: both tests pass.

- [ ] **Step 5: Commit**

```bash
git add api/server/mcp_tools/ocr_extract.py tests/api/unit/test_ocr_extract.py
git commit -m "feat(mcp): ocr_extract tool — Document Intelligence wrapper with path resolution"
```

---

## Task 4: `ocr_extract` — caching by sha256

**Files:**
- Modify: `tests/api/unit/test_ocr_extract.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/api/unit/test_ocr_extract.py`:

```python
def test_caches_by_sha256_and_model(tmp_path, monkeypatch):
    """Second call with same bytes + model returns cached: true and does not hit DI again."""
    receipts_dir = tmp_path / "receipts"
    receipts_dir.mkdir()
    (receipts_dir / "CLM-0042.png").write_bytes(b"\x89PNG\r\n\x1a\nfake-bytes-deterministic")
    monkeypatch.setattr(ocr_extract, "_RECEIPTS_DIR", receipts_dir)
    monkeypatch.setattr(ocr_extract, "_PDFS_DIR", tmp_path / "absent")
    monkeypatch.setattr(ocr_extract, "_cache", {})  # isolate from any prior test
    fake_client = _stub_di_client(monkeypatch, {"documents": [{"fields": {"merchantName": {"value": "Côte", "confidence": 0.99}}}], "tables": [], "pages": [], "keyValuePairs": []})

    first = get_ocr("CLM-0042", "prebuilt-receipt")
    second = get_ocr("CLM-0042", "prebuilt-receipt")

    assert first["cached"] is False
    assert second["cached"] is True
    assert second["documents"] == first["documents"]
    # DI client must have been called exactly once across the two get_ocr calls.
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
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
.funcvenv/Scripts/python.exe -m pytest tests/api/unit/test_ocr_extract.py -v
```

Expected: all 4 tests pass (caching is already implemented in Task 3's code; this task verifies behaviour).

- [ ] **Step 3: Commit**

```bash
git add tests/api/unit/test_ocr_extract.py
git commit -m "test(mcp): ocr_extract — verify sha256+model cache key"
```

---

## Task 5: `ocr_extract` — error paths

**Files:**
- Modify: `tests/api/unit/test_ocr_extract.py`

- [ ] **Step 1: Write failing tests for the three error paths**

Append to `tests/api/unit/test_ocr_extract.py`:

```python
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

    result = ocr_extract_tool(_OcrExtractParams(document_id="CLM-0001", model="prebuilt-receipt"))
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

    result = ocr_extract_tool(_OcrExtractParams(document_id="CLM-0001", model="prebuilt-receipt"))
    assert result.result_type == "failure"
    assert "TimeoutError" in (result.text_result_for_llm or "") or "timeout" in (result.error or "").lower()
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
.funcvenv/Scripts/python.exe -m pytest tests/api/unit/test_ocr_extract.py -v
```

Expected: all 8 tests pass (error handling is already in Task 3's tool wrapper; these verify it).

- [ ] **Step 3: Commit**

```bash
git add tests/api/unit/test_ocr_extract.py
git commit -m "test(mcp): ocr_extract — error paths (unknown id, missing file, no env, DI failure)"
```

---

## Task 6: Author `use-document-intelligence` skill

**Files:**
- Create: `api/server/skills/use-document-intelligence/SKILL.md`

- [ ] **Step 1: Write the SKILL.md**

Create `api/server/skills/use-document-intelligence/SKILL.md`:

```markdown
---
name: use-document-intelligence
description: How to OCR a document via Azure AI Document Intelligence — when to use which prebuilt model, how to call ocr_extract, how to interpret confidence scores, error handling.
allowed-tools: ocr_extract
---

You use Azure AI Document Intelligence (DI) for OCR + structured extraction of any document — receipts, CVs, invoices, IDs. DI runs in the cloud; one call returns structured fields with per-field confidence scores, plus tables, key-value pairs, and full text lines. Always call DI **before** reasoning over a document with vision: the structured output anchors your verdict and the confidence scores carry through to the audit trail.

## Models

| Model | Use for | Returns |
|---|---|---|
| `prebuilt-receipt` | Expense receipt PNGs/JPGs | `documents[].fields.merchantName`, `total`, `transactionDate`, `items[]` |
| `prebuilt-layout` | CVs, generic forms, anything with structure | `tables[]`, `keyValuePairs[]`, `pages[].lines` (reading order) |
| `prebuilt-invoice` | Vendor invoices | `vendorName`, `invoiceTotal`, `lineItems`, customer fields |
| `prebuilt-document` | Unknown structure / fallback | Generic key-value pairs and tables |
| `prebuilt-idDocument` | Passports, visas, driver licences | `firstName`, `lastName`, `dateOfBirth`, `documentNumber`, `expirationDate` |

**Decision tree:**
- Receipt-type document → `prebuilt-receipt`.
- CV / résumé / form-like document → `prebuilt-layout`.
- Vendor invoice → `prebuilt-invoice`.
- Right-to-work proof, passport, visa → `prebuilt-idDocument`.
- Anything else → `prebuilt-document`.

## How to call

```
ocr_extract(document_id="CLM-0042", model="prebuilt-receipt")
→
{
  "model": "prebuilt-receipt",
  "documents": [{"fields": {
      "merchantName": {"value": "Côte Brasserie", "confidence": 0.99},
      "total": {"value": 33.81, "confidence": 0.97},
      "transactionDate": {"value": "2026-04-01", "confidence": 0.95},
      "items": [...]
  }}],
  "tables": [...],
  "keyValuePairs": [...],
  "pages": [{"pageNumber": 1, "lines": ["Côte Brasserie", "Steak frites 22.00", ...]}],
  "cached": false
}
```

`document_id` is a domain identifier — `CLM-*` for expense claims, `C-*` for hiring candidates. The tool resolves to the local file. Don't pass paths.

## Reading the response

- `documents[].fields` is the structured extraction. Each field is `{value, confidence}`. Confidence is 0.0-1.0.
- `tables[]` is rendered tables (rowCount, columnCount, cells with row/column index).
- `keyValuePairs[]` is "Label: Value" extractions (e.g. "Email: alice@x.com").
- `pages[].lines` is the full text in reading order — use as a fallback when structured fields are missing.

**Confidence policy:**
- ≥0.9 → trustworthy, cite directly.
- 0.7-0.9 → cite but flag as uncertain in your evidence.
- <0.7 → escalate (treat as unknown, fall back to vision attachment, or return inconclusive).

## Worked example A — receipt validation

You're given `claim_id="CLM-0042"`. First call:

```
ocr_extract(document_id="CLM-0042", model="prebuilt-receipt")
```

From the response, extract `merchantName.value`, `total.value`, `transactionDate.value`, plus their confidences. Compare against the structured claim record (loaded via `claim_get_structured`). Cite the specific values and confidences in your evidence sentence:

> "Document Intelligence reads merchantName='NOT-Côte Brasserie' (conf 0.94); claim asserts vendor='Côte Brasserie'. Mismatch → flavour=wrong-vendor."

## Worked example B — CV crystallisation

You're given `candidate_id="C-SE-USA-00"`. First call:

```
ocr_extract(document_id="C-SE-USA-00", model="prebuilt-layout")
```

Map the response to the canonical profile schema:
- Work history → look in `tables[]` first (often rendered as a table); fall back to `pages[].lines` if rendered as prose.
- Education → same — usually a table or a "Education" section in `pages[].lines`.
- Skills → typically a comma-separated list under a "Skills" heading in `pages[].lines`, or a `keyValuePairs[]` entry with key `"Skills"`.
- Contact info → `keyValuePairs[]` with keys like `"Email"`, `"Phone"`, `"LinkedIn"`.

## When NOT to use

The tool caches by sha256 of the document bytes plus model id, so repeat calls with the same id+model return cached results for free. But don't loop on the tool — call once at the start of your skill, store the structured fields in your working memory, refer to them throughout.

## Error handling

A `failure` result_type with error `"AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT is not configured"` → environment is broken; you cannot recover. Return your skill's best-effort verdict citing this in evidence.

A `failure` with error containing `"document not found"` → the upstream pipeline failed to put the file in place. For receipts, fall through to the existing `missing-receipt` flavour. For CVs, return your skill's "missing input" output with confidence 0.

A `failure` with another error (timeout, 5xx) → fall back to vision-only validation. The image is also attached to your session; describe what you can see directly and lower your confidence accordingly.

## Cost note

Each call is a real Azure billing event ($0.0015 per receipt, $0.0015 per CV page). Cache cuts repeats. Don't loop.
```

- [ ] **Step 2: Verify file exists and is non-empty**

```bash
ls -la api/server/skills/use-document-intelligence/SKILL.md
```

Expected: file ~5KB.

- [ ] **Step 3: Commit**

```bash
git add api/server/skills/use-document-intelligence/SKILL.md
git commit -m "feat(skill): use-document-intelligence — runbook for OCR via DI"
```

---

## Task 7: Edit `receipt-validator` skill + register tool on agent

**Files:**
- Modify: `api/server/skills/receipt-validator/SKILL.md`
- Modify: `api/functions/graphs/executors/agents/agent_receipt_validator.py`

- [ ] **Step 1: Update receipt-validator SKILL.md**

Edit `api/server/skills/receipt-validator/SKILL.md`. Change the frontmatter `allowed-tools` line:

```markdown
allowed-tools: claim_get_structured, ocr_extract
```

After the existing "## Inputs" section, insert a new "## Step 0: Extract" section (before "## Procedure"):

```markdown
## Step 0: Extract via Document Intelligence

Before inspecting the image, call:

```
ocr_extract(document_id=claim_id, model="prebuilt-receipt")
```

The structured fields it returns (`merchantName`, `total`, `transactionDate`, `items[]`) are your **authoritative read** of the receipt. Use them as primary evidence, with the attached image as a sanity check. Cite the per-field confidence scores in your evidence sentence per the use-document-intelligence skill.

If `ocr_extract` returns a `failure` result, follow the error-handling guidance in use-document-intelligence: fall back to vision-only validation if the failure is transient (timeout, 5xx); short-circuit to `missing-receipt` if the document is genuinely absent.
```

In the existing "## Output" JSON schema, add a `field_confidences` block after `confidence`:

```json
{
  "verdict": "match" | "mismatch",
  "flavour": "correct" | "wrong-amount" | "wrong-date" | "wrong-vendor" | "missing-line-item" | "missing-receipt",
  "evidence": "1-3 sentences. State what the receipt shows and what the claim asserts; identify the mismatch (or confirm match).",
  "confidence": 0.0,
  "field_confidences": {
    "merchantName": 0.0,
    "total": 0.0,
    "transactionDate": 0.0
  }
}
```

Update the existing rules block. Replace:

> - `evidence` quotes specific values from the receipt (`"receipt total reads USD 234.50"`) and the claim (`"claim asserts USD 156.33"`). Never guess fields you can't see.

with:

> - `evidence` quotes specific values from Document Intelligence with their confidences (`"Document Intelligence reads total=USD 234.50 (conf 0.97)"`) and the claim (`"claim asserts USD 156.33"`). Never guess fields you can't see.
> - `field_confidences` carries the DI confidences through to the audit trail. Copy them verbatim from the `documents[].fields.*.confidence` values you read.

- [ ] **Step 2: Wire `ocr_extract_tool` into the agent session**

Edit `api/functions/graphs/executors/agents/agent_receipt_validator.py`. Currently line 16 reads:

```python
from api.server.mcp_tools.claim_get_structured import claim_get_structured_tool
```

Add a new import after it:

```python
from api.server.mcp_tools.claim_get_structured import claim_get_structured_tool
from api.server.mcp_tools.ocr_extract import ocr_extract_tool
```

Find the `tools=[claim_get_structured_tool]` argument inside `run_agent_session(...)` (around line 57). Change to:

```python
tools=[claim_get_structured_tool, ocr_extract_tool],
```

- [ ] **Step 3: Run existing receipt-validator tests to ensure no regression**

```bash
.funcvenv/Scripts/python.exe -m pytest tests/api/unit/test_agent_receipt_validator.py -v
```

Expected: tests pass. They likely mock `run_agent_session`; the new tool import is just registered, not exercised. If a test asserts on the exact `tools=[...]` list, update the assertion to include `ocr_extract_tool`.

- [ ] **Step 4: Commit**

```bash
git add api/server/skills/receipt-validator/SKILL.md api/functions/graphs/executors/agents/agent_receipt_validator.py
git commit -m "feat(skill): receipt-validator calls ocr_extract first; field_confidences in output"
```

---

## Task 8: Edit `cv-crystalliser` skill

**Files:**
- Modify: `api/server/skills/cv-crystalliser/SKILL.md`

- [ ] **Step 1: Update cv-crystalliser SKILL.md**

Edit `api/server/skills/cv-crystalliser/SKILL.md`. Change the frontmatter `allowed-tools` line to:

```markdown
allowed-tools: linkedin_profile_fetch, ocr_extract
```

After "## Inputs", before "## Procedure", insert:

```markdown
## Step 0: Extract via Document Intelligence

Call:

```
ocr_extract(document_id=candidate_id, model="prebuilt-layout")
```

The response's `tables[]`, `keyValuePairs[]`, and `pages[].lines` are your structured read of the CV. Map to the canonical profile per use-document-intelligence skill's worked example B:

- Work history → `tables[]` first (CVs that render work history as a table — common in technical/data-engineering CVs); fall back to sequential `pages[].lines` for prose-style CVs.
- Education → same pattern.
- Skills → `keyValuePairs[]` for "Skills:" entries, or pull from `pages[].lines` under a Skills heading.
- Contact / right-to-work hints → `keyValuePairs[]` for `"Email"`, `"Phone"`, `"Citizenship"`.

If `ocr_extract` returns `failure`, fall back to attaching the PDF to the session and reasoning over it visually. Lower the output `confidence` accordingly.
```

In the existing "## Output" JSON schema, add per-field confidences:

```json
{
  "candidate_id": "C-001",
  "name": "...",
  "current_title": {"value": "...", "confidence": 0.0},
  "tenure_years_total": {"value": 0.0, "confidence": 0.0},
  "education": [{"institution": "...", "degree": "...", "year": 2018}],
  "work_history": [{"employer": "...", "title": "...", "start": "2020-01", "end": "2024-06"}],
  "skills": ["python", "kubernetes"],
  "right_to_work": {"jurisdiction": "USA", "evidence": "us_citizen" | "h1b" | "green_card" | "unknown"},
  "inconsistencies": [{"kind": "date_overlap", "detail": "...", "confidence": 0.0}],
  "confidence": 0.0
}
```

The trailing rules paragraph stays as-is (about not hallucinating dates).

- [ ] **Step 2: Verify file**

```bash
grep -n "ocr_extract\|Step 0" api/server/skills/cv-crystalliser/SKILL.md
```

Expected: `allowed-tools` line + Step 0 heading both appear.

- [ ] **Step 3: Commit**

```bash
git add api/server/skills/cv-crystalliser/SKILL.md
git commit -m "feat(skill): cv-crystalliser calls ocr_extract first; per-field confidences"
```

---

## Task 9: Author 4 CV templates (HTML)

**Files:**
- Create: `data/synthetic/hiring/cvs/templates/classic-serif.html`
- Create: `data/synthetic/hiring/cvs/templates/modern-sans.html`
- Create: `data/synthetic/hiring/cvs/templates/two-column.html`
- Create: `data/synthetic/hiring/cvs/templates/technical.html`

Each template uses Python `string.Template` (`$placeholder`) substitution against a flat dict of fields prepared by the generator (Task 10): `name`, `email`, `phone`, `current_title`, `summary`, `work_history_html`, `education_html`, `skills_html`, `header_section_label` (e.g. "Werdegang" for DE classic-serif), and optional `photo_data_uri`.

- [ ] **Step 1: Create classic-serif template**

Create `data/synthetic/hiring/cvs/templates/classic-serif.html`:

```html
<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
@page { size: A4; margin: 2cm 2.2cm; }
body { font-family: "EB Garamond", "Garamond", serif; font-size: 11pt; line-height: 1.4; color: #111; }
h1 { font-size: 22pt; margin: 0 0 0.2em 0; letter-spacing: 0.3px; font-weight: 600; }
.title { font-size: 12pt; color: #555; font-style: italic; margin: 0 0 1em 0; }
.contact { font-size: 10pt; color: #444; margin-bottom: 1.5em; }
h2 { font-size: 12pt; text-transform: uppercase; letter-spacing: 1.2px; border-bottom: 1px solid #999; padding-bottom: 2pt; margin: 1.4em 0 0.6em 0; }
.entry { margin-bottom: 0.8em; }
.entry .top { display: flex; justify-content: space-between; font-weight: 600; }
.entry .where { color: #555; font-style: italic; }
ul { margin: 0.3em 0 0.3em 1em; padding: 0; }
.skills { font-size: 10.5pt; color: #333; }
</style></head><body>
<h1>$name</h1>
<div class="title">$current_title</div>
<div class="contact">$email · $phone</div>

<h2>Summary</h2>
<p>$summary</p>

<h2>$header_section_label</h2>
$work_history_html

<h2>Education</h2>
$education_html

<h2>Skills</h2>
<p class="skills">$skills_html</p>
</body></html>
```

- [ ] **Step 2: Create modern-sans template**

Create `data/synthetic/hiring/cvs/templates/modern-sans.html`:

```html
<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
@page { size: A4; margin: 2cm; }
body { font-family: "Inter", "Helvetica Neue", sans-serif; font-size: 10.5pt; line-height: 1.5; color: #1f2937; }
h1 { font-size: 26pt; font-weight: 700; margin: 0; color: #111827; letter-spacing: -0.5px; }
.title { font-size: 13pt; color: #4b5563; margin: 0.2em 0 0.4em 0; }
.contact { font-size: 9.5pt; color: #6b7280; margin-bottom: 1.8em; }
h2 { font-size: 11pt; text-transform: uppercase; letter-spacing: 1.5px; color: #2563eb; margin: 1.6em 0 0.5em 0; }
.entry { margin-bottom: 0.9em; }
.entry .top { display: flex; justify-content: space-between; }
.entry .role { font-weight: 600; color: #111827; }
.entry .where { color: #6b7280; font-size: 9.5pt; }
ul { margin: 0.3em 0 0.3em 1.1em; padding: 0; }
.skill-tag { display: inline-block; background: #eff6ff; color: #1e40af; padding: 2pt 6pt; border-radius: 8pt; font-size: 9pt; margin: 1pt 1pt; }
</style></head><body>
<h1>$name</h1>
<div class="title">$current_title</div>
<div class="contact">$email · $phone</div>

<h2>Summary</h2>
<p>$summary</p>

<h2>Experience</h2>
$work_history_html

<h2>Education</h2>
$education_html

<h2>Skills</h2>
<div>$skills_html</div>
</body></html>
```

- [ ] **Step 3: Create two-column template**

Create `data/synthetic/hiring/cvs/templates/two-column.html`:

```html
<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
@page { size: A4; margin: 1.6cm 1.4cm; }
body { font-family: "Inter", "Helvetica Neue", sans-serif; font-size: 10pt; line-height: 1.45; color: #1f2937; }
.header { background: #0f172a; color: #f8fafc; padding: 1.2em 1.4em; margin: -1.6cm -1.4cm 1.2em -1.4cm; }
.header h1 { font-size: 24pt; margin: 0; font-weight: 600; letter-spacing: -0.3px; }
.header .title { font-size: 12pt; color: #cbd5e1; margin-top: 0.2em; }
.header .contact { font-size: 9.5pt; color: #94a3b8; margin-top: 0.6em; }
.cols { display: flex; gap: 1.4em; }
.col-left { width: 33%; }
.col-right { width: 67%; }
h2 { font-size: 10.5pt; text-transform: uppercase; letter-spacing: 1.2px; color: #0f172a; border-bottom: 2px solid #0f172a; padding-bottom: 2pt; margin: 0 0 0.5em 0; }
.col-left h2:not(:first-child) { margin-top: 1.4em; }
.col-right h2:not(:first-child) { margin-top: 1.2em; }
.entry { margin-bottom: 0.8em; }
.entry .role { font-weight: 600; }
.entry .where { color: #475569; font-size: 9.5pt; }
.entry .dates { color: #64748b; font-size: 9pt; font-style: italic; }
ul { margin: 0.3em 0 0.3em 1em; padding: 0; font-size: 9.5pt; }
.skill-line { font-size: 9.5pt; color: #334155; margin: 0.2em 0; }
</style></head><body>
<div class="header">
  <h1>$name</h1>
  <div class="title">$current_title</div>
  <div class="contact">$email · $phone</div>
</div>

<div class="cols">
  <div class="col-left">
    <h2>Skills</h2>
    <div>$skills_html</div>

    <h2>Education</h2>
    $education_html
  </div>
  <div class="col-right">
    <h2>Summary</h2>
    <p>$summary</p>

    <h2>Experience</h2>
    $work_history_html
  </div>
</div>
</body></html>
```

- [ ] **Step 4: Create technical template**

Create `data/synthetic/hiring/cvs/templates/technical.html`:

```html
<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
@page { size: A4; margin: 1.8cm; }
body { font-family: "JetBrains Mono", "Source Code Pro", monospace; font-size: 9.5pt; line-height: 1.5; color: #0f172a; }
h1 { font-family: "Inter", sans-serif; font-size: 22pt; margin: 0; font-weight: 700; }
.title { font-family: "Inter", sans-serif; font-size: 12pt; color: #475569; margin-top: 0.1em; }
.contact { font-size: 9pt; color: #64748b; margin: 0.4em 0 1.4em 0; }
h2 { font-family: "Inter", sans-serif; font-size: 11pt; color: #2563eb; text-transform: uppercase; letter-spacing: 1.5px; margin: 1.4em 0 0.5em 0; border-left: 3px solid #2563eb; padding-left: 0.5em; }
table.work, table.skills-grid { width: 100%; border-collapse: collapse; margin-bottom: 0.6em; }
table.work td { vertical-align: top; padding: 4pt 6pt; border-bottom: 1px solid #e2e8f0; font-family: "Inter", sans-serif; font-size: 9.5pt; }
table.work td.dates { color: #64748b; white-space: nowrap; width: 20%; }
table.work td.role { font-weight: 600; width: 30%; }
table.work td.employer { color: #475569; width: 25%; }
table.work td.impact { width: 25%; font-size: 9pt; color: #334155; }
table.skills-grid td { padding: 3pt 6pt; border: 1px solid #e2e8f0; background: #f8fafc; font-size: 9pt; }
</style></head><body>
<h1>$name</h1>
<div class="title">$current_title</div>
<div class="contact">$email · $phone</div>

<h2>Summary</h2>
<p>$summary</p>

<h2>Experience</h2>
$work_history_html

<h2>Education</h2>
$education_html

<h2>Skills</h2>
$skills_html
</body></html>
```

- [ ] **Step 5: Commit**

```bash
git add data/synthetic/hiring/cvs/templates/
git commit -m "feat(synthetic): hand-craft 4 CV HTML templates for PDF generation"
```

---

## Task 10: Implement `generate_pdfs.py`

**Files:**
- Create: `data/synthetic/hiring/cvs/generate_pdfs.py`
- Create: `tests/api/unit/test_generate_pdfs.py`

- [ ] **Step 1: Write failing smoke test**

Create `tests/api/unit/test_generate_pdfs.py`:

```python
"""Smoke test for the CV PDF generator.

Validates that running the generator on a small fixture set produces the
expected number of non-empty PDFs with deterministic content (re-runs are
byte-identical)."""
from __future__ import annotations
import json
import importlib.util
import sys
from pathlib import Path

import pytest


def _load_generator():
    """Import generate_pdfs.py without making it importable as a package."""
    path = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "hiring" / "cvs" / "generate_pdfs.py"
    spec = importlib.util.spec_from_file_location("generate_pdfs", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["generate_pdfs"] = module
    spec.loader.exec_module(module)
    return module


def test_generator_produces_pdf_per_input_json(tmp_path):
    pytest.importorskip("weasyprint", reason="weasyprint required to run generator")
    gen = _load_generator()

    cvs_dir = tmp_path / "cvs"
    cvs_dir.mkdir()
    out_dir = tmp_path / "pdfs"
    templates_dir = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "hiring" / "cvs" / "templates"

    record = {
        "candidate_id": "C-SE-USA-00",
        "name": "Test Candidate",
        "email": "test@x.com",
        "phone": "+1 555 0100",
        "current_title": "Senior Data Engineer",
        "summary": "Test summary line.",
        "education": [{"institution": "MIT", "degree": "BSc CS", "year": 2018}],
        "work_history": [{"employer": "Acme", "title": "Engineer", "start": "2020-01", "end": "2024-01", "impact": "Built things"}],
        "skills": ["python", "kubernetes"],
        "right_to_work": {"jurisdiction": "USA", "evidence": "us_citizen"},
    }
    (cvs_dir / "C-SE-USA-00.json").write_text(json.dumps(record), encoding="utf-8")

    gen.generate_all(cvs_dir=cvs_dir, out_dir=out_dir, templates_dir=templates_dir)

    pdf = out_dir / "C-SE-USA-00.pdf"
    assert pdf.exists()
    assert pdf.stat().st_size > 1000  # rough sanity: a real PDF, not an empty file
    head = pdf.read_bytes()[:5]
    assert head == b"%PDF-"


def test_generator_is_deterministic(tmp_path):
    """Re-running generate_all on the same input produces a byte-identical PDF."""
    pytest.importorskip("weasyprint", reason="weasyprint required to run generator")
    gen = _load_generator()

    cvs_dir = tmp_path / "cvs"
    cvs_dir.mkdir()
    out_dir = tmp_path / "pdfs"
    templates_dir = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "hiring" / "cvs" / "templates"

    record = {
        "candidate_id": "C-FR-USA-01",
        "name": "Deterministic Test",
        "email": "d@x.com",
        "phone": "+1 555 0101",
        "current_title": "Frontend Engineer",
        "summary": "Summary.",
        "education": [],
        "work_history": [],
        "skills": ["js"],
        "right_to_work": {"jurisdiction": "USA", "evidence": "h1b"},
    }
    (cvs_dir / "C-FR-USA-01.json").write_text(json.dumps(record), encoding="utf-8")

    gen.generate_all(cvs_dir=cvs_dir, out_dir=out_dir, templates_dir=templates_dir)
    first_bytes = (out_dir / "C-FR-USA-01.pdf").read_bytes()

    # Re-run
    gen.generate_all(cvs_dir=cvs_dir, out_dir=out_dir, templates_dir=templates_dir)
    second_bytes = (out_dir / "C-FR-USA-01.pdf").read_bytes()

    # PDF metadata embeds creation timestamp by default — generate_all must
    # set a fixed timestamp / disable metadata so re-runs are stable.
    assert first_bytes == second_bytes
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.funcvenv/Scripts/python.exe -m pytest tests/api/unit/test_generate_pdfs.py -v
```

Expected: failure on `gen.generate_all(...)` call (module doesn't exist or function not defined).

- [ ] **Step 3: Implement the generator**

Create `data/synthetic/hiring/cvs/generate_pdfs.py`:

```python
"""Generate hand-crafted CV PDFs from existing JSON candidate records.

Reads each `C-*.json` from data/synthetic/hiring/cvs/, picks a template +
edge-case salt deterministically by hash of candidate_id, renders to
data/synthetic/hiring/cvs/pdfs/{candidate_id}.pdf via weasyprint.

Re-runs are byte-identical: PDF metadata creation date is fixed and we use a
deterministic embedded-image silhouette for the photo edge case.

Usage:
  python data/synthetic/hiring/cvs/generate_pdfs.py
"""
from __future__ import annotations
import argparse
import base64
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
from string import Template
from typing import Any

# 1×1 transparent PNG, base64 — placeholder photo for the salted edge case.
_PHOTO_PLACEHOLDER_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

# Fixed timestamp embedded in PDF metadata so re-runs are byte-identical.
_FIXED_DT = dt.datetime(2026, 4, 30, 0, 0, 0, tzinfo=dt.timezone.utc)


def _pick_template(candidate_id: str, current_title: str) -> str:
    title = (current_title or "").lower()
    if "data engineer" in title:
        return "technical"
    if "creative director" in title:
        return "two-column"
    if "frontend" in title:
        return "two-column"
    if "media strategist" in title:
        return "modern-sans"
    if "werkstudent" in title:
        return "modern-sans"
    return "classic-serif"


def _is_de_jurisdiction(record: dict) -> bool:
    rtw = record.get("right_to_work", {}) or {}
    return rtw.get("jurisdiction") == "DE" or "-DE-" in record.get("candidate_id", "")


def _salt_kind(candidate_id: str) -> str | None:
    """Five candidates get edge-case salting, deterministically by hash."""
    h = int(hashlib.sha256(candidate_id.encode()).hexdigest(), 16)
    salts = ["photo", "scanned", "multi-page", "heavy-tables", "passport-page"]
    if h % 10 == 0:  # ~5/50 candidates
        return salts[(h // 10) % len(salts)]
    return None


def _work_history_html(record: dict, template: str) -> str:
    items = record.get("work_history") or []
    if not items:
        return "<p><em>No prior employment listed.</em></p>"
    if template == "technical":
        rows = []
        for w in items:
            dates = f"{w.get('start','')}–{w.get('end','present') or 'present'}"
            rows.append(
                f"<tr><td class='dates'>{dates}</td>"
                f"<td class='role'>{w.get('title','')}</td>"
                f"<td class='employer'>{w.get('employer','')}</td>"
                f"<td class='impact'>{w.get('impact','')}</td></tr>"
            )
        return "<table class='work'>" + "".join(rows) + "</table>"
    parts = []
    for w in items:
        dates = f"{w.get('start','')} – {w.get('end','present') or 'present'}"
        parts.append(
            f"<div class='entry'>"
            f"<div class='top'><span class='role'>{w.get('title','')}</span>"
            f"<span class='where'>{w.get('employer','')}</span></div>"
            f"<div class='dates'>{dates}</div>"
            f"{f'<ul><li>{w.get(chr(34)+chr(34)).strip() or w.get(\"impact\",\"\")}</li></ul>' if w.get('impact') else ''}"
            f"</div>"
        )
    return "".join(parts)


def _education_html(record: dict) -> str:
    items = record.get("education") or []
    if not items:
        return "<p><em>—</em></p>"
    parts = []
    for e in items:
        parts.append(
            f"<div class='entry'>"
            f"<div class='top'><span class='role'>{e.get('degree','')}</span>"
            f"<span class='where'>{e.get('institution','')}</span></div>"
            f"<div class='dates'>{e.get('year','')}</div>"
            f"</div>"
        )
    return "".join(parts)


def _skills_html(record: dict, template: str) -> str:
    items = record.get("skills") or []
    if template == "modern-sans":
        return " ".join(f"<span class='skill-tag'>{s}</span>" for s in items)
    if template == "two-column":
        return "<br>".join(f"<span class='skill-line'>· {s}</span>" for s in items)
    if template == "technical":
        cells = "".join(f"<td>{s}</td>" for s in items)
        return f"<table class='skills-grid'><tr>{cells}</tr></table>"
    return ", ".join(items)


def _build_fields(record: dict, template: str) -> dict[str, Any]:
    de = _is_de_jurisdiction(record)
    section_label = "Werdegang" if de and template == "classic-serif" else "Experience"
    return {
        "name": record.get("name", record.get("candidate_id", "")),
        "email": record.get("email", "candidate@example.com"),
        "phone": record.get("phone", "+1 555 0100"),
        "current_title": record.get("current_title", ""),
        "summary": record.get("summary", "Experienced practitioner."),
        "header_section_label": section_label,
        "work_history_html": _work_history_html(record, template),
        "education_html": _education_html(record),
        "skills_html": _skills_html(record, template),
    }


def _render_html(template_name: str, fields: dict, templates_dir: Path) -> str:
    tpl_path = templates_dir / f"{template_name}.html"
    raw = tpl_path.read_text(encoding="utf-8")
    return Template(raw).safe_substitute(fields)


def _apply_salt(html: str, salt: str | None, record: dict) -> str:
    if salt is None:
        return html
    if salt == "photo":
        photo_tag = (
            f"<img src='data:image/png;base64,{_PHOTO_PLACEHOLDER_B64}' "
            f"style='width:80px;height:80px;float:right;border-radius:50%;background:#cbd5e1;' />"
        )
        return html.replace("<body>", f"<body>{photo_tag}", 1)
    if salt == "multi-page":
        # Append a "Selected projects" page so total runs to 3 pages of dense work.
        extra = ""
        for i in range(8):
            extra += (
                f"<div class='entry'><div class='top'><span class='role'>Project P-{i+1}</span>"
                f"<span class='where'>Client engagement</span></div>"
                f"<p>Lengthy paragraph describing project P-{i+1} for {record.get('name','')}, "
                f"detailing scope, technologies, outcomes, and stakeholder alignment activities. "
                f"This block exists to push the document onto a third page.</p></div>"
            )
        section = f"<h2 style='page-break-before:always;'>Selected Projects</h2>{extra}"
        return html.replace("</body>", f"{section}</body>", 1)
    if salt == "heavy-tables":
        # Force every section into table form (in addition to whatever the template did).
        certs = "<table class='work'><tr><td>Cert A (2023)</td><td>Cert B (2024)</td><td>Cert C (2025)</td></tr></table>"
        return html.replace("</body>", f"<h2>Certifications</h2>{certs}</body>", 1)
    if salt == "passport-page":
        passport = (
            "<div style='page-break-before:always;'><h2>Right to Work — Document Scan</h2>"
            "<p style='border:1px solid #94a3b8;padding:1em;background:#f8fafc;'>"
            "[Synthetic passport image placeholder · Surname: " + record.get("name","").split(" ")[-1] + " · "
            "Given name: " + record.get("name","").split(" ")[0] + " · "
            "Document No.: P" + record.get("candidate_id","").replace("-","") + " · Expires: 2030-12-31"
            "]</p></div>"
        )
        return html.replace("</body>", f"{passport}</body>", 1)
    if salt == "scanned":
        # Visual-only effect: rotate the body slightly + add a yellowed background.
        style = "<style>body{background:#fefce8;transform:rotate(-1.2deg);}</style>"
        return html.replace("</head>", f"{style}</head>", 1)
    return html


def generate_one(record: dict, templates_dir: Path, out_dir: Path) -> Path:
    from weasyprint import HTML  # imported here so callers can monkeypatch
    candidate_id = record["candidate_id"]
    template = _pick_template(candidate_id, record.get("current_title", ""))
    fields = _build_fields(record, template)
    html = _render_html(template, fields, templates_dir)
    html = _apply_salt(html, _salt_kind(candidate_id), record)
    out_path = out_dir / f"{candidate_id}.pdf"
    out_dir.mkdir(parents=True, exist_ok=True)
    # weasyprint embeds creation timestamp by default — pin to fixed datetime.
    pdf_bytes = HTML(string=html).write_pdf(presentational_hints=True, pdf_version="1.7")
    out_path.write_bytes(_strip_pdf_metadata_dates(pdf_bytes))
    return out_path


def _strip_pdf_metadata_dates(pdf_bytes: bytes) -> bytes:
    """Replace embedded /CreationDate and /ModDate so re-runs are byte-identical.

    weasyprint embeds these as `(D:YYYYMMDDHHMMSS+ZZ'00')` literal strings
    inside the PDF's Info dictionary. We scrub them to a fixed value.
    """
    fixed_marker = b"(D:20260430000000Z)"
    out = pdf_bytes
    for key in (b"/CreationDate ", b"/ModDate "):
        idx = 0
        while True:
            pos = out.find(key, idx)
            if pos < 0:
                break
            paren_open = out.find(b"(", pos)
            paren_close = out.find(b")", paren_open) + 1
            out = out[:paren_open] + fixed_marker + out[paren_close:]
            idx = paren_open + len(fixed_marker)
    return out


def generate_all(cvs_dir: Path, out_dir: Path, templates_dir: Path) -> list[Path]:
    out_paths: list[Path] = []
    for json_path in sorted(cvs_dir.glob("C-*.json")):
        record = json.loads(json_path.read_text(encoding="utf-8"))
        record.setdefault("candidate_id", json_path.stem)
        out_paths.append(generate_one(record, templates_dir, out_dir))
    return out_paths


def _main() -> None:
    parser = argparse.ArgumentParser()
    here = Path(__file__).resolve().parent
    parser.add_argument("--cvs-dir", type=Path, default=here)
    parser.add_argument("--out-dir", type=Path, default=here / "pdfs")
    parser.add_argument("--templates-dir", type=Path, default=here / "templates")
    args = parser.parse_args()
    paths = generate_all(args.cvs_dir, args.out_dir, args.templates_dir)
    print(f"Generated {len(paths)} PDFs into {args.out_dir}")


if __name__ == "__main__":
    _main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.funcvenv/Scripts/python.exe -m pytest tests/api/unit/test_generate_pdfs.py -v
```

Expected: both tests pass. If `weasyprint` import fails, the test will skip — fix the env first per Task 1 step 4.

- [ ] **Step 5: Commit**

```bash
git add data/synthetic/hiring/cvs/generate_pdfs.py tests/api/unit/test_generate_pdfs.py
git commit -m "feat(synthetic): generate_pdfs.py — render hand-crafted CVs with salts"
```

---

## Task 11: Generate the 50 PDFs and commit

**Files:**
- Create: `data/synthetic/hiring/cvs/pdfs/{candidate_id}.pdf` × 50

- [ ] **Step 1: Verify all 50 input JSONs exist**

```bash
ls data/synthetic/hiring/cvs/C-*.json | wc -l
```

Expected: `50`.

- [ ] **Step 2: Run the generator**

```bash
.funcvenv/Scripts/python.exe data/synthetic/hiring/cvs/generate_pdfs.py
```

Expected output: `Generated 50 PDFs into c:\dev\ghcp sdk stuff\data\synthetic\hiring\cvs\pdfs`. Time: ~15-30s.

- [ ] **Step 3: Verify count + sanity-spot-check**

```bash
ls data/synthetic/hiring/cvs/pdfs/*.pdf | wc -l
```

Expected: `50`.

```bash
.funcvenv/Scripts/python.exe -c "from pathlib import Path; sizes = sorted(p.stat().st_size for p in Path('data/synthetic/hiring/cvs/pdfs').glob('*.pdf')); print(f'min={sizes[0]} median={sizes[len(sizes)//2]} max={sizes[-1]}')"
```

Expected: min ≥ 5 KB, max ≤ 200 KB. The "multi-page" salted CVs will be the largest (~80-150 KB).

- [ ] **Step 4: Open one PDF visually**

Open `data/synthetic/hiring/cvs/pdfs/C-SE-USA-00.pdf` (any PDF viewer). Verify: name, title, work history, skills are all present and rendered cleanly. If a section looks broken, fix the template (Task 9) and re-run the generator.

- [ ] **Step 5: Commit the PDFs**

```bash
git add data/synthetic/hiring/cvs/pdfs/
git commit -m "data(synthetic): 50 hand-crafted CV PDFs — 4 templates + 5 salted edge cases"
```

Expected: `git status` clean afterwards. Re-running the generator and `git status` again should show no changes (deterministic output).

---

## Task 12: Manual integration smoke test

**Files:** none (verification only).

- [ ] **Step 1: Confirm env vars are populated**

```bash
grep "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT" .env local.settings.json
```

Expected: both files have non-empty values for the endpoint and key. If empty, populate from the provisioned Azure resource before continuing.

- [ ] **Step 2: Boot the stack**

In the order from [docs/superpowers/specs/2026-04-30-doc-intelligence-skill-design.md](../specs/2026-04-30-doc-intelligence-skill-design.md):

```bash
azurite --silent --location azurite-data --blobHost 0.0.0.0 --queueHost 0.0.0.0 --tableHost 0.0.0.0 &
# wait until http://localhost:10000/devstoreaccount1 returns 400

source .funcvenv/Scripts/activate
PATH="$(pwd)/node_modules/.bin:$PATH" PYTHONPATH="$(pwd)" func start --port 7071 &
# wait for "Functions:" line in output

.funcvenv/Scripts/python.exe -m uvicorn api.server.main:app --port 3001 --host 0.0.0.0 &

npm run demo:mcp &
npm run demo:ui &
```

- [ ] **Step 3: Spawn one expense workflow and watch DI fire**

```bash
curl -s -X POST http://localhost:3001/api/simulator/inject -H "content-type: application/json" -d '{}'
```

Wait ~30-60 seconds for the workflow to advance to Phase 3 (Validate Receipt).

- [ ] **Step 4: Inspect the audit trail for the OCR span**

```bash
curl -sL "http://localhost:3001/api/workflows/" | python -c "
import json,sys
ws = json.load(sys.stdin)
exp = next((w for w in ws if w['type'] == 'expense-claim'), None)
print('found:', exp['id'] if exp else None, 'phase:', exp['currentPhase'] if exp else None)
"
```

Then for the workflow id reported:

```bash
curl -sL "http://localhost:3001/api/workflows/EXP-0001" | python -c "
import json,sys
d = json.load(sys.stdin)
ledger = d.get('workflow',{}).get('actionLedger', [])
for e in ledger:
    if 'ocr' in e.get('action','').lower() or 'document_intelligence' in e.get('action','').lower():
        print(e)
"
```

Expected: at least one `ocr.extract` entry in the action ledger with attributes `zava.ocr.model='prebuilt-receipt'` and a numeric `zava.ocr.confidence_min`.

- [ ] **Step 5: Verify field_confidences in receipt validation output**

```bash
curl -sL "http://localhost:3001/api/workflows/EXP-0001" | python -c "
import json,sys
d = json.load(sys.stdin)
print(json.dumps(d.get('narrative'), indent=2))
"
```

Expected: the receipt-validation narrative includes phrases like "Document Intelligence reads merchantName=…(conf 0.99)" and the underlying skill output (visible via traces or the workflow's metadata) carries a `field_confidences` block.

- [ ] **Step 6: Cleanup**

Kill all background processes when done:

```bash
# In another shell, by PID — or just close terminals
```

Per memory feedback: don't leave dev processes running across sessions.

- [ ] **Step 7: Final commit (if no further fixes needed)**

If anything failed in steps 4-5, fix the relevant skill or executor file and commit those fixes separately. No blanket "smoke-test fixes" commit — keep history granular.

---

## Self-Review

After writing this plan, I checked:

1. **Spec coverage:**
   - Spec §1 architecture — Tasks 3, 6, 7, 8 cover the receipt-validator pipeline; Task 8 covers cv-crystalliser skill (executor wiring is explicitly OUT OF SCOPE per spec §8 + §1, so no task for it — call this out in the handoff).
   - Spec §2 ocr_extract spec — Tasks 3, 4, 5 cover params, behaviour, caching, error paths, OTEL.
   - Spec §3 use-document-intelligence content — Task 6.
   - Spec §4 skill edits — Tasks 7 (receipt-validator), 8 (cv-crystalliser).
   - Spec §5 PDF generation — Tasks 9 (templates), 10 (generator + tests), 11 (artifact generation + commit).
   - Spec §6 configuration — Tasks 1 (deps), 2 (env vars).
   - Spec §7 cost — covered as design context, no task needed.
   - Spec §8 out of scope — explicit; no task for cv-crystalliser triage wiring.
   - Spec §9 risks — manual smoke test in Task 12 catches DI cold start, weasyprint install issues, and skill priming.

2. **Placeholder scan:** No "TBD" / "fill in details" / "similar to Task N" patterns. All code blocks contain real code.

3. **Type consistency:** `ocr_extract` signature — `_OcrExtractParams.document_id: str`, `model: _OcrModel` literal — referenced consistently in Tasks 3, 4, 5, 6 (skill body), 7 (skill edit), 8 (skill edit). `get_ocr(document_id, model)` plain function used in tests with same param names. No drift.

---
