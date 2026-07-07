# Visual Domain Composer — Phase 2 (The Real Agent) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the Phase-1 pipe into a real composer: swap the fake agent for `copilot --acp`, stand up the **compose-bridge MCP** (`report_stage` / `ask_operator` / `present_brief` / `composition_complete`) so the agent's questions + brief review flow through structured tools, add document→text intake (PDF/docx), the `.poc-safety` + `COMPOSE_PERMISSION_POLICY` safety gate, and the committed `compose-domain-live` micro-skill.

**Architecture:** A shared in-process `registry` holds compose sessions + the single active one (v1 is one-run-at-a-time). A FastMCP streamable-HTTP app (mounted at `/api/compose/mcp`) exposes four tools that read/emit through the active `ComposeSession`; `ask_operator`/`present_brief` block on an asyncio Future resolved by new REST endpoints (`/answer`, `/brief`). The agent is spawned with `mcpServers` pointed back at our own app and told (via the `compose-domain-live` micro-skill) to call those tools at the seams of `add-domain`.

**Tech Stack:** Python 3.13, FastAPI/Starlette, `mcp` 1.27 (FastMCP), `pypdf` + `python-docx` (new deps), asyncio, pytest.

**Depends on:** Phase 1 (`2026-07-07-visual-domain-composer-phase-1-bridge.md`). **Design source of truth:** [`../specs/2026-07-07-visual-domain-composer-design.md`](../specs/2026-07-07-visual-domain-composer-design.md) §4.1, §4.5, §4.6, §6.

---

## File Structure

| File | Responsibility |
|---|---|
| `api/server/services/compose/registry.py` | Shared session registry: `sessions` dict + `active` pointer + helpers. (Phase-1 `_SESSIONS` moves here.) |
| `api/server/services/compose/intake.py` | `extract_text(filename, raw) -> str` for pdf/docx/md/txt/paste. |
| `api/server/services/compose/mcp_server.py` | FastMCP app + the four bridge tools, operating on the active session. |
| `api/server/services/compose/session.py` | Modify: add `pending` Futures + `resolve()` for HITL. |
| `api/server/services/compose/bridge.py` | Modify: attach `mcpServers`, choose model, real prompt referencing the micro-skill, permission policy. |
| `api/server/routes/compose.py` | Modify: use registry; add `/answer`, `/brief`; `.poc-safety` gate; pdf/docx intake. |
| `api/server/main.py` | Modify: mount the FastMCP app + run its session-manager lifespan. |
| `api/shared/compose_config.py` | `permission_policy()` + `poc_safety_ok()` + `repo_root()` helpers. |
| `.github/skills/compose-domain-live/SKILL.md` | The committed micro-skill wrapping `add-domain` with the bridge tools. |
| `tests/api/compose/test_intake.py` | intake dispatch + passthrough. |
| `tests/api/compose/test_mcp_tools.py` | the four tools emit/block/resolve correctly. |
| `tests/api/compose/test_hitl_endpoints.py` | `/answer` + `/brief` resolve pending futures. |
| `tests/api/compose/test_safety.py` | `.poc-safety` gate + permission policy. |
| `tests/api/compose/test_integration_real.py` | opt-in real compose (env-gated, not CI). |

---

## Task 1: Session registry (refactor Phase-1 storage)

**Files:**
- Create: `api/server/services/compose/registry.py`
- Modify: `api/server/routes/compose.py`
- Test: `tests/api/compose/test_registry.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/compose/test_registry.py`:

```python
from api.server.services.compose import registry
from api.server.services.compose.session import ComposeSession


def test_register_sets_active_and_lookup():
    registry.reset()
    s = ComposeSession("cid1")
    registry.register(s)
    assert registry.get("cid1") is s
    assert registry.active() is s


def test_register_second_replaces_active():
    registry.reset()
    a, b = ComposeSession("a"), ComposeSession("b")
    registry.register(a)
    registry.register(b)
    assert registry.active() is b
    assert registry.get("a") is a
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/api/compose/test_registry.py -v`
Expected: FAIL — `ModuleNotFoundError: ...registry`.

- [ ] **Step 3: Implement `registry.py`**

Create `api/server/services/compose/registry.py`:

```python
"""Process-wide compose session registry.

v1 is one-run-at-a-time, so an `active` pointer is enough for the MCP tools to
find the session a tool call belongs to. Multi-session would key MCP calls by a
header/URL instead (see design §4.5).
"""
from __future__ import annotations

from .session import ComposeSession

_sessions: dict[str, ComposeSession] = {}
_active: str | None = None


def register(session: ComposeSession) -> None:
    global _active
    _sessions[session.id] = session
    _active = session.id


def get(cid: str) -> ComposeSession | None:
    return _sessions.get(cid)


def active() -> ComposeSession | None:
    return _sessions.get(_active) if _active else None


def reset() -> None:
    """Test helper."""
    global _active
    _sessions.clear()
    _active = None
```

- [ ] **Step 4: Point the router at the registry**

In `api/server/routes/compose.py`, delete the module-level `_SESSIONS: dict[...] = {}` line and `import` the registry:

```python
from api.server.services.compose import registry
```
Replace `_SESSIONS[cid] = session` with `registry.register(session)`, and every `_SESSIONS.get(cid)` with `registry.get(cid)`.

- [ ] **Step 5: Run to verify pass (registry + existing routes still green)**

Run: `uv run pytest tests/api/compose/test_registry.py tests/api/compose/test_routes_compose.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add api/server/services/compose/registry.py api/server/routes/compose.py tests/api/compose/test_registry.py
git commit -m "refactor(compose): shared session registry with active pointer (phase 2)"
```

---

## Task 2: HITL futures on ComposeSession

**Files:**
- Modify: `api/server/services/compose/session.py`
- Test: `tests/api/compose/test_session.py` (add cases)

- [ ] **Step 1: Add failing tests**

Append to `tests/api/compose/test_session.py`:

```python
@pytest.mark.asyncio
async def test_pending_future_resolves():
    s = ComposeSession("cid")
    fut = s.new_pending("req1")
    assert not fut.done()
    s.resolve("req1", {"answer": "CFO"})
    assert await asyncio.wait_for(fut, timeout=1) == {"answer": "CFO"}


def test_resolve_unknown_request_is_noop():
    s = ComposeSession("cid")
    s.resolve("nope", {"x": 1})  # must not raise
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/api/compose/test_session.py -k pending_future -v`
Expected: FAIL — `AttributeError: 'ComposeSession' object has no attribute 'new_pending'`.

- [ ] **Step 3: Implement on `session.py`**

Add to `ComposeSession.__init__`: `self.pending: dict[str, asyncio.Future] = {}`. Add methods:

```python
    def new_pending(self, request_id: str) -> asyncio.Future:
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self.pending[request_id] = fut
        return fut

    def resolve(self, request_id: str, value) -> bool:
        fut = self.pending.pop(request_id, None)
        if fut and not fut.done():
            fut.set_result(value)
            return True
        return False
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/api/compose/test_session.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/server/services/compose/session.py tests/api/compose/test_session.py
git commit -m "feat(compose): HITL pending-future support on ComposeSession (phase 2)"
```

---

## Task 3: Document intake (pdf/docx/text)

**Files:**
- Create: `api/server/services/compose/intake.py`
- Test: `tests/api/compose/test_intake.py`
- Modify: `pyproject.toml` (+`pypdf`, `python-docx`)

- [ ] **Step 1: Add deps**

Run: `uv add pypdf python-docx`

- [ ] **Step 2: Write the failing tests**

Create `tests/api/compose/test_intake.py`:

```python
from api.server.services.compose import intake


def test_plaintext_passthrough():
    assert intake.extract_text("note.txt", b"hello world") == "hello world"


def test_markdown_passthrough():
    assert intake.extract_text("spec.md", b"# Title\nbody") == "# Title\nbody"


def test_unknown_extension_decodes_utf8():
    assert intake.extract_text("blob", b"raw text") == "raw text"


def test_pdf_dispatches_to_pdf_extractor(monkeypatch):
    monkeypatch.setattr(intake, "_extract_pdf", lambda raw: "PDF TEXT")
    assert intake.extract_text("doc.PDF", b"%PDF-1.4...") == "PDF TEXT"


def test_docx_dispatches_to_docx_extractor(monkeypatch):
    monkeypatch.setattr(intake, "_extract_docx", lambda raw: "DOCX TEXT")
    assert intake.extract_text("doc.docx", b"PK...") == "DOCX TEXT"


def test_extractor_failure_falls_back_to_decode(monkeypatch):
    def boom(raw):
        raise ValueError("bad pdf")
    monkeypatch.setattr(intake, "_extract_pdf", boom)
    assert intake.extract_text("doc.pdf", b"fallbacktext") == "fallbacktext"
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/api/compose/test_intake.py -v`
Expected: FAIL — `ModuleNotFoundError: ...intake`.

- [ ] **Step 4: Implement `intake.py`**

Create `api/server/services/compose/intake.py`:

```python
"""Normalize an uploaded document (or pasted text) into plain text for the
composition prompt. Fail soft: on any extractor error, fall back to a utf-8
decode so the agent still receives *something* to read.
"""
from __future__ import annotations

import io


def _extract_pdf(raw: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(raw))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _extract_docx(raw: bytes) -> str:
    import docx  # python-docx
    document = docx.Document(io.BytesIO(raw))
    return "\n".join(p.text for p in document.paragraphs)


def extract_text(filename: str, raw: bytes) -> str:
    ext = ""
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
    try:
        if ext == "pdf":
            return _extract_pdf(raw)
        if ext == "docx":
            return _extract_docx(raw)
    except Exception:
        pass  # fall through to decode
    return raw.decode("utf-8", "ignore")
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/api/compose/test_intake.py -v`
Expected: PASS (6 tests).

- [ ] **Step 6: Commit**

```bash
git add api/server/services/compose/intake.py tests/api/compose/test_intake.py pyproject.toml uv.lock
git commit -m "feat(compose): document intake pdf/docx/text extraction (phase 2)"
```

---

## Task 4: Safety config (`.poc-safety` gate + permission policy)

**Files:**
- Create: `api/shared/compose_config.py`
- Test: `tests/api/compose/test_safety.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/api/compose/test_safety.py`:

```python
from api.shared import compose_config as cfg


def test_permission_policy_defaults_autopilot(monkeypatch):
    monkeypatch.delenv("COMPOSE_PERMISSION_POLICY", raising=False)
    assert cfg.permission_policy() == "autopilot"


def test_permission_policy_in_repo_only(monkeypatch):
    monkeypatch.setenv("COMPOSE_PERMISSION_POLICY", "in_repo_only")
    assert cfg.permission_policy() == "in_repo_only"


def test_poc_safety_ok_true_when_marker_present(tmp_path, monkeypatch):
    (tmp_path / ".poc-safety").write_text("POC_UNSAFE_FOR_PUBLIC_DEPLOY=1\n")
    monkeypatch.setenv("ZAVA_REPO_ROOT", str(tmp_path))
    assert cfg.poc_safety_ok() is True


def test_poc_safety_ok_false_when_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("ZAVA_REPO_ROOT", str(tmp_path))
    assert cfg.poc_safety_ok() is False


def test_in_repo_path_classification(tmp_path, monkeypatch):
    monkeypatch.setenv("ZAVA_REPO_ROOT", str(tmp_path))
    inside = str(tmp_path / "api" / "x.py")
    assert cfg.is_in_repo(inside) is True
    assert cfg.is_in_repo("/etc/passwd") is False
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/api/compose/test_safety.py -v`
Expected: FAIL — `ModuleNotFoundError: api.shared.compose_config`.

- [ ] **Step 3: Implement `compose_config.py`**

Create `api/shared/compose_config.py`:

```python
"""Config + safety helpers for the Visual Domain Composer (localhost-only)."""
from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    return Path(os.getenv("ZAVA_REPO_ROOT", os.getcwd())).resolve()


def poc_safety_ok() -> bool:
    marker = repo_root() / ".poc-safety"
    return marker.exists() and "POC_UNSAFE_FOR_PUBLIC_DEPLOY=1" in marker.read_text()


def permission_policy() -> str:
    """`autopilot` (v1 default, --allow-all) or `in_repo_only` (stricter)."""
    val = os.getenv("COMPOSE_PERMISSION_POLICY", "autopilot").strip()
    return val if val in ("autopilot", "in_repo_only") else "autopilot"


def is_in_repo(path: str) -> bool:
    try:
        Path(path).resolve().relative_to(repo_root())
        return True
    except (ValueError, OSError):
        return False
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/api/compose/test_safety.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add api/shared/compose_config.py tests/api/compose/test_safety.py
git commit -m "feat(compose): .poc-safety gate + permission-policy config (phase 2)"
```

---

## Task 5: compose-bridge MCP server (the four tools)

**Files:**
- Create: `api/server/services/compose/mcp_server.py`
- Test: `tests/api/compose/test_mcp_tools.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/api/compose/test_mcp_tools.py` (tests call the tool *implementations* directly against a live session — the FastMCP wrapper is exercised via the integration test in Task 9):

```python
import asyncio
import pytest
from api.server.services.compose import registry, mcp_server
from api.server.services.compose.session import ComposeSession


def _fresh_session():
    registry.reset()
    s = ComposeSession("cid")
    registry.register(s)
    return s


def test_report_stage_emits_stage_event():
    s = _fresh_session()
    q = s.subscribe()
    mcp_server._report_stage_impl("composing", "Composing")
    assert q.get_nowait() == {"type": "stage", "stage": "composing", "label": "Composing"}
    assert s.stage == "composing"


def test_composition_complete_emits_done():
    s = _fresh_session()
    q = s.subscribe()
    mcp_server._composition_complete_impl("capex-approval", "Capex Approval")
    assert q.get_nowait() == {
        "type": "done", "workflow_type": "capex-approval", "display_name": "Capex Approval"}


@pytest.mark.asyncio
async def test_ask_operator_blocks_until_answer():
    s = _fresh_session()
    q = s.subscribe()
    task = asyncio.create_task(mcp_server._ask_operator_impl("CFO or committee?", ["CFO", "committee"]))
    await asyncio.sleep(0.05)
    event = q.get_nowait()
    assert event["type"] == "question" and event["options"] == ["CFO", "committee"]
    s.resolve(event["request_id"], "CFO")
    assert await asyncio.wait_for(task, timeout=1) == "CFO"


@pytest.mark.asyncio
async def test_present_brief_blocks_until_review():
    s = _fresh_session()
    q = s.subscribe()
    task = asyncio.create_task(mcp_server._present_brief_impl("domain: x"))
    await asyncio.sleep(0.05)
    event = q.get_nowait()
    assert event["type"] == "brief" and event["yaml"] == "domain: x"
    s.resolve(event["request_id"], {"approved": True, "yaml": "domain: x-edited"})
    assert await asyncio.wait_for(task, timeout=1) == {"approved": True, "yaml": "domain: x-edited"}
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/api/compose/test_mcp_tools.py -v`
Expected: FAIL — `ModuleNotFoundError: ...mcp_server`.

- [ ] **Step 3: Implement `mcp_server.py`**

Create `api/server/services/compose/mcp_server.py`:

```python
"""compose-bridge MCP server: the structured HITL + progress channel the
compose agent calls. Mounted at /api/compose/mcp (streamable HTTP). v1 resolves
the target session via the registry's `active` pointer (one run at a time).

The `_impl` functions hold the logic and are unit-tested directly; the FastMCP
`@mcp.tool()` wrappers just delegate to them.
"""
from __future__ import annotations

import uuid

from mcp.server.fastmcp import FastMCP

from . import registry

mcp = FastMCP("compose-bridge")


def _emit(event: dict) -> None:
    session = registry.active()
    if session is not None:
        session.emit(event)


def _report_stage_impl(stage: str, label: str) -> str:
    _emit({"type": "stage", "stage": stage, "label": label})
    return "ok"


def _composition_complete_impl(workflow_type: str, display_name: str) -> str:
    _emit({"type": "done", "workflow_type": workflow_type, "display_name": display_name})
    return "ok"


async def _ask_operator_impl(question: str, options: list[str] | None = None) -> str:
    session = registry.active()
    if session is None:
        return ""
    request_id = uuid.uuid4().hex
    fut = session.new_pending(request_id)
    session.emit({"type": "question", "request_id": request_id,
                  "text": question, "options": options or []})
    return await fut


async def _present_brief_impl(yaml: str) -> dict:
    session = registry.active()
    if session is None:
        return {"approved": True, "yaml": yaml}
    request_id = uuid.uuid4().hex
    fut = session.new_pending(request_id)
    session.emit({"type": "brief", "request_id": request_id, "yaml": yaml})
    return await fut


@mcp.tool()
def report_stage(stage: str, label: str) -> str:
    """Report the current composition stage (intake|understanding|brief|composing|graduating|verifying|ready)."""
    return _report_stage_impl(stage, label)


@mcp.tool()
async def ask_operator(question: str, options: list[str] | None = None) -> str:
    """Ask the operator a clarifying question and wait for the answer. Use ONLY when the document is genuinely ambiguous."""
    return await _ask_operator_impl(question, options)


@mcp.tool()
async def present_brief(yaml: str) -> dict:
    """Present the drafted domain brief for operator review; returns {approved, yaml} (yaml may be operator-edited). Call before composing."""
    return await _present_brief_impl(yaml)


@mcp.tool()
def composition_complete(workflow_type: str, display_name: str) -> str:
    """Signal that the domain is graduated and verified; reveals the Ignite control."""
    return _composition_complete_impl(workflow_type, display_name)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/api/compose/test_mcp_tools.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add api/server/services/compose/mcp_server.py tests/api/compose/test_mcp_tools.py
git commit -m "feat(compose): compose-bridge MCP tools (stage/ask/brief/complete) (phase 2)"
```

---

## Task 6: HITL REST resolvers (`/answer`, `/brief`) + `.poc-safety` gate + real intake

**Files:**
- Modify: `api/server/routes/compose.py`
- Test: `tests/api/compose/test_hitl_endpoints.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/api/compose/test_hitl_endpoints.py`:

```python
import asyncio
import pytest
from api.server.services.compose import registry
from api.server.services.compose.session import ComposeSession
from api.server.routes.compose import resolve_answer, resolve_brief


@pytest.mark.asyncio
async def test_resolve_answer_sets_future():
    registry.reset()
    s = ComposeSession("cid"); registry.register(s)
    fut = s.new_pending("r1")
    await resolve_answer("cid", {"request_id": "r1", "answer": "CFO"})
    assert await asyncio.wait_for(fut, timeout=1) == "CFO"


@pytest.mark.asyncio
async def test_resolve_brief_sets_future_with_edit():
    registry.reset()
    s = ComposeSession("cid"); registry.register(s)
    fut = s.new_pending("r2")
    await resolve_brief("cid", {"request_id": "r2", "approved": True, "yaml": "edited"})
    assert await asyncio.wait_for(fut, timeout=1) == {"approved": True, "yaml": "edited"}
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/api/compose/test_hitl_endpoints.py -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_answer'`.

- [ ] **Step 3: Extend `routes/compose.py`**

Add the intake import + `.poc-safety` gate + resolvers. At the top add:

```python
from api.server.services.compose import intake
from api.shared import compose_config
```

Replace the file-read branch in `create_session` so uploads go through intake:

```python
    if file is not None:
        raw = await file.read()
        document_text = intake.extract_text(file.filename or "", raw)
```

Tighten the guard (localhost **and** `.poc-safety`):

```python
def _guard(request: Request) -> bool:
    return _is_loopback(request) and compose_config.poc_safety_ok()
```
and call `_guard(request)` in `create_session` instead of `_is_loopback(request)`.

Add the two resolver endpoints (kept as standalone async funcs so they're unit-testable without the HTTP layer):

```python
from fastapi import Body


async def resolve_answer(cid: str, payload: dict) -> dict:
    session = registry.get(cid)
    if session is None:
        return {"ok": False, "error": "not found"}
    ok = session.resolve(payload["request_id"], payload.get("answer", ""))
    return {"ok": ok}


async def resolve_brief(cid: str, payload: dict) -> dict:
    session = registry.get(cid)
    if session is None:
        return {"ok": False, "error": "not found"}
    ok = session.resolve(payload["request_id"],
                         {"approved": bool(payload.get("approved", True)),
                          "yaml": payload.get("yaml", "")})
    return {"ok": ok}


@router.post("/api/compose/{cid}/answer")
async def answer(cid: str, payload: dict = Body(...)):
    return await resolve_answer(cid, payload)


@router.post("/api/compose/{cid}/brief")
async def brief(cid: str, payload: dict = Body(...)):
    return await resolve_brief(cid, payload)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/api/compose/test_hitl_endpoints.py tests/api/compose/test_routes_compose.py -v`
Expected: PASS. (Note: `test_routes_compose.py`'s create test now needs `.poc-safety`; it exists in the repo root so `poc_safety_ok()` is true under the default `ZAVA_REPO_ROOT=cwd`. If tests run elsewhere, set `ZAVA_REPO_ROOT` in a fixture.)

- [ ] **Step 5: Commit**

```bash
git add api/server/routes/compose.py tests/api/compose/test_hitl_endpoints.py
git commit -m "feat(compose): /answer + /brief resolvers, .poc-safety gate, real intake (phase 2)"
```

---

## Task 7: Mount the MCP app + wire it into the bridge

**Files:**
- Modify: `api/server/main.py`
- Modify: `api/server/services/compose/bridge.py`
- Test: `tests/api/compose/test_bridge.py` (add mcpServers assertion)

- [ ] **Step 1: Mount the FastMCP app + lifespan in `main.py`**

Add near the other imports:

```python
from api.server.services.compose.mcp_server import mcp as compose_mcp
```

Mount the streamable-HTTP sub-app (once):

```python
app.mount("/api/compose/mcp", compose_mcp.streamable_http_app())
```

FastMCP's streamable HTTP needs its session manager running. In the existing `lifespan` async contextmanager in `main.py`, wrap the yield so the compose MCP manager runs alongside the rest:

```python
    async with compose_mcp.session_manager.run():
        yield
```
(If `lifespan` already has a single `yield`, replace that `yield` with the `async with ... : yield` block. Keep all existing startup/teardown around it.)

- [ ] **Step 2: Verify the app boots with the mount**

Run: `uv run python -c "from api.server.main import app; print(any(getattr(r,'path','')=='/api/compose/mcp' for r in app.routes) or any('/api/compose/mcp' in str(getattr(r,'path','')) for r in app.routes))"`
Expected: prints `True`.

- [ ] **Step 3: Add mcpServers + model + micro-skill prompt to the bridge**

In `bridge.py`, change `session/new` to attach the compose-bridge MCP and pick a model, and update the prompt. Add a constant + edit `start()`:

```python
COMPOSE_MCP_URL = os.getenv(
    "COMPOSE_MCP_URL", "http://127.0.0.1:3101/api/compose/mcp")
COMPOSE_MODEL = os.getenv("COMPOSE_MODEL", "claude-sonnet-4.6")
```

Replace the `session/new` request in `start()`:

```python
        res = await self.client.request("session/new", {
            "cwd": self.repo_root,
            "mcpServers": [{
                "name": "compose-bridge",
                "type": "http",
                "url": COMPOSE_MCP_URL,
            }],
        })
```

Replace `_build_prompt()`:

```python
    def _build_prompt(self) -> str:
        return (
            "Use the `compose-domain-live` skill to compose a new Zava domain "
            "from the process document below. Route ALL progress through the "
            "compose-bridge MCP tools: call `report_stage` at each phase, "
            "`ask_operator` only when the document is genuinely ambiguous, "
            "always `present_brief` before composing, and `composition_complete` "
            "after graduate.sh + verification pass.\n\n"
            "--- DOCUMENT ---\n" + self.document_text + "\n--- END DOCUMENT ---"
        )
```

- [ ] **Step 4: Update the bridge test for the new session/new shape**

The Phase-1 `test_bridge.py` fake agent ignores `mcpServers`, so it still passes. Add one assertion by capturing the request — simplest: keep the existing end-to-end assertions (they still hold). Run:

Run: `uv run pytest tests/api/compose/test_bridge.py -v`
Expected: PASS (fake agent unaffected by the extra params).

- [ ] **Step 5: Commit**

```bash
git add api/server/main.py api/server/services/compose/bridge.py
git commit -m "feat(compose): mount compose-bridge MCP + wire mcpServers/model/prompt (phase 2)"
```

---

## Task 8: The `compose-domain-live` micro-skill

**Files:**
- Create: `.github/skills/compose-domain-live/SKILL.md`

- [ ] **Step 1: Write the micro-skill**

Create `.github/skills/compose-domain-live/SKILL.md`:

```markdown
---
name: compose-domain-live
description: Compose a new Zava domain from a process document while streaming progress + HITL to the Visual Domain Composer UI via the compose-bridge MCP tools. Wraps add-domain. Invoked only by the ComposeBridge (localhost-only).
---

# compose-domain-live

You are composing a new Zava domain from a process document, driven by the
Visual Domain Composer UI. You MUST route every interaction through the
**compose-bridge** MCP tools so the operator sees your progress and can answer
you. Otherwise, follow the real [`add-domain`](../add-domain/SKILL.md) recipe
exactly — this skill only governs *how you communicate*, not *what you build*.

## Contract

1. Call `report_stage("understanding", "Reading the document")` first.
2. Read the document. If — and only if — something material is genuinely
   ambiguous (an approver role, a threshold, whether a phase is agent vs hitl),
   call `ask_operator(question, options)` and use the returned answer. Do NOT
   ask about things the document already answers. Do NOT ask more than a couple
   of questions.
3. `report_stage("brief", "Drafting the brief")`, author the v4 brief per
   add-domain Phase 2, then **always** call `present_brief(yaml)`. Honour the
   returned `{approved, yaml}` — if the operator edited the YAML, use their
   version; if `approved` is false, revise and present again.
4. `report_stage("composing", ...)` then run compose-domain (add-domain Phase 3)
   into the sandbox.
5. `report_stage("graduating", ...)` then run graduate.sh + the Phase-4b/4c
   hand-stitches (domains.py, entity_projections/__init__.py, AGT matrix, etc.).
6. `report_stage("verifying", ...)` then run add-domain Phase 4d verification.
   If a check fails, fix it and re-verify — narrate what you're doing.
7. On success call
   `composition_complete(workflow_type, display_name)`. Do not restart the
   server yourself — the UI's Ignite control handles the restart.

Narrate briefly as you go (your normal assistant messages appear in the UI as
the agent's "voice"). Think out loud — your reasoning is shown as the thought
stream.
```

- [ ] **Step 2: Verify the agent can see the skill**

Run: `ls .github/skills/compose-domain-live/SKILL.md && grep -c "compose-bridge" .github/skills/compose-domain-live/SKILL.md`
Expected: path listed, count ≥ 1.

- [ ] **Step 3: Commit**

```bash
git add .github/skills/compose-domain-live/SKILL.md
git commit -m "feat(compose): compose-domain-live micro-skill wrapping add-domain (phase 2)"
```

---

## Task 9: Opt-in real end-to-end integration test

**Files:**
- Create: `tests/api/compose/test_integration_real.py`

- [ ] **Step 1: Write the env-gated integration test**

Create `tests/api/compose/test_integration_real.py`:

```python
"""Real compose smoke test. NOT run in CI — spawns a real `copilot` agent and
mutates the tree. Enable with COMPOSE_E2E=1 on a throwaway checkout.

Run: COMPOSE_E2E=1 uv run pytest tests/api/compose/test_integration_real.py -v -s
"""
import os
import asyncio
import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("COMPOSE_E2E") != "1", reason="set COMPOSE_E2E=1 to run real agent")


@pytest.mark.asyncio
async def test_real_compose_reaches_brief_stage():
    from api.server.services.compose import registry
    from api.server.services.compose.session import ComposeSession
    from api.server.services.compose.bridge import ComposeBridge

    registry.reset()
    session = ComposeSession("e2e")
    registry.register(session)
    doc = ("Capital expenditure approval: staff raise a capex request; finance "
           "checks budget; senior leaders approve above a threshold; assets are "
           "recorded. Approvers above 50k are ambiguous.")
    bridge = ComposeBridge(session, document_text=doc)  # real copilot bin
    await bridge.start()

    q = session.subscribe()
    saw_brief = False
    for _ in range(400):
        ev = await asyncio.wait_for(q.get(), timeout=900)
        if ev.get("type") == "question":
            session.resolve(ev["request_id"], "Create a new capex_committee persona")
        if ev.get("type") == "brief":
            saw_brief = True
            session.resolve(ev["request_id"], {"approved": True, "yaml": ev["yaml"]})
        if ev.get("type") == "done" or (ev.get("type") == "stage" and ev.get("stage") in ("ready", "error")):
            break
    assert saw_brief, "agent never presented a brief"
```

- [ ] **Step 2: (Manual, optional) run it on a throwaway checkout**

Run: `COMPOSE_E2E=1 uv run pytest tests/api/compose/test_integration_real.py -v -s`
Expected (manual): the agent asks the capex-committee question, presents a brief, and reaches `done`/`ready`. **Do not run in CI.**

- [ ] **Step 3: Confirm it's skipped by default**

Run: `uv run pytest tests/api/compose/test_integration_real.py -v`
Expected: SKIPPED.

- [ ] **Step 4: Commit**

```bash
git add tests/api/compose/test_integration_real.py
git commit -m "test(compose): opt-in real end-to-end compose smoke (phase 2)"
```

---

## Task 10: Phase-2 exit check

- [ ] **Step 1: Full sweep (hermetic only)**

Run: `uv run pytest tests/api/compose/ -q`
Expected: all green (the real E2E is skipped).

- [ ] **Step 2: Lint**

Run: `uv run ruff check api/server/services/compose api/server/routes/compose.py api/shared/compose_config.py`
Expected: clean.

- [ ] **Step 3: Confirm Phase-2 done-criteria**

  - Uploading a PDF/docx/text produces a composition prompt (intake).
  - The MCP tools emit `stage`/`question`/`brief`/`done` and block on HITL until `/answer` + `/brief`.
  - `create_session` refuses unless loopback **and** `.poc-safety` present.
  - The bridge attaches the compose-bridge MCP + references the `compose-domain-live` skill.
  - (Manual, throwaway machine) a real compose reaches the brief and completes.

---

## Self-Review (against the spec)

- **Coverage:** MCP tools §4.5 ✓ T5; HITL loop §4.6 ✓ T2/T5/T6; document intake §4.3 ✓ T3; safety gate + policy §6 ✓ T4/T6; micro-skill §4.5/§9 ✓ T8; real-agent wiring §4.2 ✓ T7. Ignite (§4.7) + `/permission` surfacing are Phase 3 / deferred (autopilot means permission prompts don't fire in v1).
- **Placeholder scan:** none — runnable code/commands throughout.
- **Type consistency:** `registry.active()/get()/register()/reset()` used identically across mcp_server, routes, tests; `session.new_pending()/resolve()` consistent; MCP `_impl` names match their `@mcp.tool()` wrappers; event `type`s (`stage`/`question`/`brief`/`done`) match spec §4.4 and the Phase-3 reducer.

---

## Next

Phase 3 (`2026-07-07-visual-domain-composer-phase-3-cockpit-ignite.md`): the `?view=compose` React cockpit (thought-stream + tool/diff timeline + plan + question/brief cards) against this SSE stream, plus `compose-ignite.sh` supervised restart + the cosmic-lens handoff.
