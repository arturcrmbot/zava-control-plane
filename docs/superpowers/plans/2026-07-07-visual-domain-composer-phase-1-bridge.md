# Visual Domain Composer — Phase 1 (The Bridge Speaks) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the backend `ComposeBridge` that drives a `copilot --acp` subprocess over ACP (JSON-RPC/stdio), translates its `session/update` notifications into a normalized SSE event stream, and exposes `POST /api/compose/session` + `GET /api/compose/{id}/stream` — proven end-to-end against a **fake ACP agent** so no real agent or tokens are needed in CI.

**Architecture:** A small `api/server/services/compose/` package: a pure `translate` function (ACP update → normalized event), an async `AcpClient` (newline-delimited JSON-RPC over an asyncio subprocess), an in-memory `ComposeSession` (event buffer + pub/sub SSE hub), and `ComposeBridge` (handshake → prompt → notify→translate→emit). A thin `api/server/routes/compose.py` exposes create + SSE-stream. Phase 1 is hermetic: tests inject a fake `copilot` command that replays a fixture trace.

**Tech Stack:** Python 3.13, FastAPI, asyncio subprocess, pytest (+ `pytest-asyncio` if not already present), `uv` for running.

**Design source of truth:** [`docs/superpowers/specs/2026-07-07-visual-domain-composer-design.md`](../specs/2026-07-07-visual-domain-composer-design.md) — see §3.1 (grounded ACP facts), §4.2 (bridge), §4.4 (normalized SSE event schema).

---

## File Structure

| File | Responsibility |
|---|---|
| `api/server/services/compose/__init__.py` | Package marker + public exports. |
| `api/server/services/compose/translate.py` | Pure: ACP `session/update` params → list of normalized event dicts. |
| `api/server/services/compose/acp_client.py` | Async JSON-RPC 2.0 client over stdio (newline-delimited); request/response correlation; notification + server-request callbacks. |
| `api/server/services/compose/session.py` | `ComposeSession`: in-memory stage + event ring buffer + asyncio pub/sub (SSE hub) with replay-on-subscribe. |
| `api/server/services/compose/bridge.py` | `ComposeBridge`: spawn subprocess, ACP handshake, run prompt, wire notifications → `translate` → `session.emit`; auto-approve permission requests. |
| `api/server/routes/compose.py` | FastAPI router: `POST /api/compose/session`, `GET /api/compose/{id}/stream`, `GET /api/compose/{id}`. |
| `api/server/main.py` | Modify: mount `compose_router` alongside the other routers. |
| `tests/api/compose/fake_acp_agent.py` | Test double: a script that speaks minimal ACP and replays a fixture trace of `session/update`s. |
| `tests/api/compose/fixtures/basic_trace.jsonl` | A realistic sequence of ACP `update` objects (thought → read → edit+diff → completed → message). |
| `tests/api/compose/test_translate.py` | Unit tests for `translate_update`. |
| `tests/api/compose/test_acp_client.py` | `AcpClient` request/response + notification against the fake agent. |
| `tests/api/compose/test_session.py` | `ComposeSession` emit/subscribe/replay. |
| `tests/api/compose/test_bridge.py` | End-to-end bridge run against the fake agent. |
| `tests/api/compose/test_routes_compose.py` | HTTP: create session + consume SSE via FastAPI `TestClient`. |

---

## Task 0: Preflight — confirm test tooling

**Files:** none (inspection only).

- [ ] **Step 1: Confirm pytest + asyncio support**

Run: `uv run pytest --version && uv run python -c "import pytest_asyncio; print(pytest_asyncio.__version__)"`
Expected: pytest prints a version. If the `pytest_asyncio` import fails, add it:

Run: `uv add --dev pytest-asyncio`

- [ ] **Step 2: Confirm async test mode**

Check `pyproject.toml` for a `[tool.pytest.ini_options]` block. If `asyncio_mode` is absent, add:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

Run: `uv run pytest tests/ -q -k "definitely_no_such_test"` (Expected: "no tests ran", exits 0/5 — just proves collection works.)

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore(compose): ensure pytest-asyncio available for phase-1"
```

---

## Task 1: Normalized event translation (pure function)

**Files:**
- Create: `api/server/services/compose/__init__.py`
- Create: `api/server/services/compose/translate.py`
- Test: `tests/api/compose/test_translate.py`

- [ ] **Step 1: Create the package marker**

Create `api/server/services/compose/__init__.py`:

```python
"""Visual Domain Composer bridge (design-time; localhost-only). Phase 1."""
```

- [ ] **Step 2: Write the failing tests**

Create `tests/api/compose/test_translate.py`:

```python
from api.server.services.compose.translate import translate_update


def test_agent_message_chunk_becomes_narration():
    params = {"sessionId": "s", "update": {
        "sessionUpdate": "agent_message_chunk",
        "content": {"type": "text", "text": "Domain composed."}}}
    assert translate_update(params) == [
        {"type": "narration", "text": "Domain composed.", "partial": True}]


def test_agent_thought_chunk_becomes_thought():
    params = {"update": {"sessionUpdate": "agent_thought_chunk",
                         "content": {"type": "text", "text": "Reading the registry."}}}
    assert translate_update(params) == [
        {"type": "thought", "text": "Reading the registry.", "partial": True}]


def test_tool_call_read_maps_kind_and_path():
    params = {"update": {
        "sessionUpdate": "tool_call", "toolCallId": "t1",
        "title": "Reading api/shared/domains.py", "kind": "read", "status": "pending",
        "locations": [{"path": "api/shared/domains.py"}]}}
    assert translate_update(params) == [{
        "type": "tool", "id": "t1", "title": "Reading api/shared/domains.py",
        "kind": "read", "status": "pending", "path": "api/shared/domains.py"}]


def test_tool_call_edit_extracts_diff():
    params = {"update": {
        "sessionUpdate": "tool_call", "toolCallId": "t2",
        "title": "Creating fleet_capex.py", "kind": "edit", "status": "pending",
        "content": [{"type": "diff", "path": "api/functions/workflows/fleet_capex.py",
                     "oldText": "", "newText": "# orchestrator\n"}]}}
    out = translate_update(params)[0]
    assert out["type"] == "tool" and out["kind"] == "edit"
    assert out["diff"] == {"old": "", "new": "# orchestrator\n"}
    assert out["path"] == "api/functions/workflows/fleet_capex.py"


def test_tool_call_update_carries_status_and_output():
    params = {"update": {
        "sessionUpdate": "tool_call_update", "toolCallId": "t1", "status": "completed",
        "rawOutput": {"content": "Created file with 6 characters"}}}
    assert translate_update(params) == [{
        "type": "tool", "id": "t1", "status": "completed",
        "output": "Created file with 6 characters"}]


def test_plan_update_maps_entries():
    params = {"update": {"sessionUpdate": "plan", "entries": [
        {"title": "Author brief", "status": "in_progress"},
        {"title": "Graduate", "status": "pending"}]}}
    assert translate_update(params) == [{"type": "plan", "entries": [
        {"title": "Author brief", "status": "in_progress"},
        {"title": "Graduate", "status": "pending"}]}]


def test_ignored_updates_yield_nothing():
    for kind in ("available_commands_update", "config_option_update", "user_message_chunk"):
        assert translate_update({"update": {"sessionUpdate": kind}}) == []
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/api/compose/test_translate.py -v`
Expected: FAIL — `ModuleNotFoundError: api.server.services.compose.translate`.

- [ ] **Step 4: Implement `translate.py`**

Create `api/server/services/compose/translate.py`:

```python
"""Pure translation: ACP `session/update` params -> normalized event dicts.

The normalized schema is the stable contract between the bridge and the UI
(see design spec §4.4). Keeping this a pure function makes it trivially
testable against recorded ACP traces with no live agent.
"""
from __future__ import annotations

from typing import Any

_KIND_MAP = {
    "edit": "edit", "create": "edit", "write": "edit",
    "read": "read", "search": "search", "execute": "execute",
}


def _text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        return content.get("text", "")
    if isinstance(content, list):
        return "".join(_text(c) for c in content)
    return ""


def _kind(k: Any) -> str:
    return _KIND_MAP.get(k, "other")


def _tool_extras(upd: dict) -> dict:
    extras: dict[str, Any] = {}
    locs = upd.get("locations") or []
    if locs and isinstance(locs[0], dict) and locs[0].get("path"):
        extras["path"] = locs[0]["path"]
    for c in upd.get("content") or []:
        if isinstance(c, dict) and c.get("type") == "diff":
            extras["diff"] = {"old": c.get("oldText", ""), "new": c.get("newText", "")}
            if "path" not in extras and c.get("path"):
                extras["path"] = c["path"]
    raw = upd.get("rawOutput") or {}
    if isinstance(raw, dict) and raw.get("content"):
        extras["output"] = raw["content"]
    return extras


def translate_update(params: dict) -> list[dict]:
    """Translate one ACP `session/update` notification's params into 0+ events."""
    upd = (params or {}).get("update") or {}
    kind = upd.get("sessionUpdate")

    if kind == "agent_message_chunk":
        return [{"type": "narration", "text": _text(upd.get("content")), "partial": True}]
    if kind == "agent_thought_chunk":
        return [{"type": "thought", "text": _text(upd.get("content")), "partial": True}]
    if kind == "tool_call":
        return [{
            "type": "tool", "id": upd.get("toolCallId"), "title": upd.get("title"),
            "kind": _kind(upd.get("kind")), "status": upd.get("status", "pending"),
            **_tool_extras(upd),
        }]
    if kind == "tool_call_update":
        return [{
            "type": "tool", "id": upd.get("toolCallId"),
            "status": upd.get("status"), **_tool_extras(upd),
        }]
    if kind == "plan":
        return [{"type": "plan", "entries": [
            {"title": e.get("title") or e.get("content"), "status": e.get("status")}
            for e in (upd.get("entries") or [])
        ]}]
    return []
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/api/compose/test_translate.py -v`
Expected: PASS (7 tests).

- [ ] **Step 6: Commit**

```bash
git add api/server/services/compose/__init__.py api/server/services/compose/translate.py tests/api/compose/test_translate.py
git commit -m "feat(compose): normalized ACP->UI event translation (phase 1)"
```

---

## Task 2: The fake ACP agent + fixture trace

**Files:**
- Create: `tests/api/compose/__init__.py` (empty, so fixtures import cleanly if needed)
- Create: `tests/api/compose/fixtures/basic_trace.jsonl`
- Create: `tests/api/compose/fake_acp_agent.py`

- [ ] **Step 1: Create the fixture trace**

Create `tests/api/compose/fixtures/basic_trace.jsonl` (each line is one ACP `update` object):

```jsonl
{"sessionUpdate":"agent_thought_chunk","content":{"type":"text","text":"Reading the registry to see existing domains."}}
{"sessionUpdate":"tool_call","toolCallId":"t1","title":"Reading api/shared/domains.py","kind":"read","status":"pending","locations":[{"path":"api/shared/domains.py"}]}
{"sessionUpdate":"tool_call_update","toolCallId":"t1","status":"completed","rawOutput":{"content":"read 1180 lines"}}
{"sessionUpdate":"tool_call","toolCallId":"t2","title":"Creating fleet_capex.py","kind":"edit","status":"pending","content":[{"type":"diff","path":"api/functions/workflows/fleet_capex.py","oldText":"","newText":"# orchestrator\n"}]}
{"sessionUpdate":"agent_message_chunk","content":{"type":"text","text":"Domain composed."}}
```

- [ ] **Step 2: Create the fake ACP agent**

Create `tests/api/compose/fake_acp_agent.py`:

```python
"""Minimal ACP server test double.

Speaks just enough of the Agent Client Protocol over stdio (newline-delimited
JSON-RPC 2.0) to satisfy ComposeBridge: responds to `initialize` and
`session/new`, and on `session/prompt` replays the `update` objects from the
JSONL file named by the FAKE_ACP_TRACE env var, then returns a stop reason.

Extra argv (e.g. --acp -C <dir> --allow-all) is ignored on purpose so the
bridge can build its normal command line with this script as the binary.
"""
import json
import os
import sys


def _send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def main() -> None:
    trace_path = os.environ.get("FAKE_ACP_TRACE", "")
    updates: list[dict] = []
    if trace_path and os.path.exists(trace_path):
        with open(trace_path, encoding="utf-8") as fh:
            updates = [json.loads(ln) for ln in fh if ln.strip()]

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        mid = msg.get("id")
        method = msg.get("method")
        if method == "initialize":
            _send({"jsonrpc": "2.0", "id": mid,
                   "result": {"protocolVersion": 1, "agentCapabilities": {}}})
        elif method == "session/new":
            _send({"jsonrpc": "2.0", "id": mid,
                   "result": {"sessionId": "fake-session",
                              "models": {"availableModels": []}}})
        elif method == "session/prompt":
            for upd in updates:
                _send({"jsonrpc": "2.0", "method": "session/update",
                       "params": {"sessionId": "fake-session", "update": upd}})
            _send({"jsonrpc": "2.0", "id": mid, "result": {"stopReason": "end_turn"}})
        # any other method: ignore


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Manually smoke-test the fake (sanity, no assertion yet)**

Run:
```bash
FAKE_ACP_TRACE=tests/api/compose/fixtures/basic_trace.jsonl \
printf '%s\n%s\n%s\n' \
 '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{}}' \
 '{"jsonrpc":"2.0","id":1,"method":"session/new","params":{}}' \
 '{"jsonrpc":"2.0","id":2,"method":"session/prompt","params":{}}' \
 | FAKE_ACP_TRACE=tests/api/compose/fixtures/basic_trace.jsonl uv run python tests/api/compose/fake_acp_agent.py | head
```
Expected: initialize + session/new responses, then 5 `session/update` lines, then a `stopReason` result.

- [ ] **Step 4: Commit**

```bash
git add tests/api/compose/__init__.py tests/api/compose/fake_acp_agent.py tests/api/compose/fixtures/basic_trace.jsonl
git commit -m "test(compose): fake ACP agent + fixture trace (phase 1)"
```

---

## Task 3: `AcpClient` — JSON-RPC over stdio

**Files:**
- Create: `api/server/services/compose/acp_client.py`
- Test: `tests/api/compose/test_acp_client.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/compose/test_acp_client.py`:

```python
import sys
import pytest
from api.server.services.compose.acp_client import AcpClient

FAKE = ["tests/api/compose/fake_acp_agent.py"]


@pytest.mark.asyncio
async def test_initialize_and_session_new_roundtrip(monkeypatch):
    monkeypatch.setenv("FAKE_ACP_TRACE", "tests/api/compose/fixtures/basic_trace.jsonl")
    notifications = []

    async def on_notify(method, params):
        notifications.append((method, params))

    async def on_request(method, params):
        return {}

    client = AcpClient(on_notify, on_request)
    await client.start([sys.executable, *FAKE, "--acp", "-C", ".", "--allow-all"], cwd=".")

    init = await client.request("initialize", {"protocolVersion": 1})
    assert init["protocolVersion"] == 1

    new = await client.request("session/new", {"cwd": "."})
    assert new["sessionId"] == "fake-session"

    await client.request("session/prompt", {"sessionId": "fake-session", "prompt": []})
    # the fake streamed 5 session/update notifications during the prompt
    assert sum(1 for m, _ in notifications if m == "session/update") == 5

    await client.stop()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/api/compose/test_acp_client.py -v`
Expected: FAIL — `ModuleNotFoundError: ...acp_client`.

- [ ] **Step 3: Implement `acp_client.py`**

Create `api/server/services/compose/acp_client.py`:

```python
"""Async JSON-RPC 2.0 client over a subprocess' stdio (newline-delimited).

Verified against `copilot --acp` (protocolVersion 1): messages are single-line
JSON separated by '\\n'. Correlates request ids to responses; forwards
notifications and server->client requests to caller-supplied async callbacks.
"""
from __future__ import annotations

import asyncio
import json
from typing import Awaitable, Callable

NotifyCB = Callable[[str, dict], Awaitable[None]]
RequestCB = Callable[[str, dict], Awaitable[dict]]


class AcpClient:
    def __init__(self, on_notify: NotifyCB, on_request: RequestCB) -> None:
        self._on_notify = on_notify
        self._on_request = on_request
        self._proc: asyncio.subprocess.Process | None = None
        self._reader: asyncio.Task | None = None
        self._pending: dict[int, asyncio.Future] = {}
        self._next_id = 0

    async def start(self, cmd: list[str], cwd: str) -> None:
        self._proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=cwd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._reader = asyncio.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        assert self._proc and self._proc.stdout
        while True:
            raw = await self._proc.stdout.readline()
            if not raw:
                break
            line = raw.decode("utf-8", "ignore").strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            await self._dispatch(msg)

    async def _dispatch(self, msg: dict) -> None:
        if "id" in msg and ("result" in msg or "error" in msg):
            fut = self._pending.pop(msg["id"], None)
            if fut and not fut.done():
                fut.set_result(msg)
        elif msg.get("method") and "id" in msg:
            result = await self._on_request(msg["method"], msg.get("params") or {})
            await self._write({"jsonrpc": "2.0", "id": msg["id"], "result": result})
        elif msg.get("method"):
            await self._on_notify(msg["method"], msg.get("params") or {})

    async def _write(self, obj: dict) -> None:
        assert self._proc and self._proc.stdin
        self._proc.stdin.write((json.dumps(obj) + "\n").encode("utf-8"))
        await self._proc.stdin.drain()

    async def request(self, method: str, params: dict) -> dict:
        self._next_id += 1
        rid = self._next_id
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[rid] = fut
        await self._write({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        resp = await fut
        if "error" in resp:
            raise RuntimeError(f"ACP error for {method}: {resp['error']}")
        return resp.get("result") or {}

    async def notify(self, method: str, params: dict) -> None:
        await self._write({"jsonrpc": "2.0", "method": method, "params": params})

    async def stop(self) -> None:
        if self._reader:
            self._reader.cancel()
        if self._proc and self._proc.returncode is None:
            try:
                self._proc.terminate()
                await asyncio.wait_for(self._proc.wait(), timeout=5)
            except (ProcessLookupError, asyncio.TimeoutError):
                pass
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/api/compose/test_acp_client.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/server/services/compose/acp_client.py tests/api/compose/test_acp_client.py
git commit -m "feat(compose): async ACP JSON-RPC stdio client (phase 1)"
```

---

## Task 4: `ComposeSession` — event buffer + SSE pub/sub

**Files:**
- Create: `api/server/services/compose/session.py`
- Test: `tests/api/compose/test_session.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/compose/test_session.py`:

```python
import asyncio
import pytest
from api.server.services.compose.session import ComposeSession


@pytest.mark.asyncio
async def test_subscribe_receives_live_events():
    s = ComposeSession("abc")
    q = s.subscribe()
    s.emit({"type": "thought", "text": "hi"})
    assert await asyncio.wait_for(q.get(), timeout=1) == {"type": "thought", "text": "hi"}


@pytest.mark.asyncio
async def test_late_subscriber_replays_buffered_events():
    s = ComposeSession("abc")
    s.emit({"type": "narration", "text": "first"})
    q = s.subscribe()  # subscribed AFTER the emit
    assert await asyncio.wait_for(q.get(), timeout=1) == {"type": "narration", "text": "first"}


def test_stage_event_updates_current_stage():
    s = ComposeSession("abc")
    assert s.stage == "intake"
    s.emit({"type": "stage", "stage": "composing", "label": "Composing"})
    assert s.stage == "composing"


@pytest.mark.asyncio
async def test_unsubscribe_stops_delivery():
    s = ComposeSession("abc")
    q = s.subscribe()
    s.unsubscribe(q)
    s.emit({"type": "thought", "text": "ignored"})
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(q.get(), timeout=0.2)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/api/compose/test_session.py -v`
Expected: FAIL — `ModuleNotFoundError: ...session`.

- [ ] **Step 3: Implement `session.py`**

Create `api/server/services/compose/session.py`:

```python
"""In-memory ComposeSession: current stage, an event ring buffer, and an
asyncio pub/sub hub. New subscribers replay the buffered events so a browser
that connects mid-run still sees the whole story so far.
"""
from __future__ import annotations

import asyncio

_MAX_BUFFER = 2000


class ComposeSession:
    def __init__(self, compose_id: str) -> None:
        self.id = compose_id
        self.stage = "intake"
        self.done = False
        self.events: list[dict] = []
        self._subscribers: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        for e in self.events:
            q.put_nowait(e)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    def emit(self, event: dict) -> None:
        if event.get("type") == "stage" and event.get("stage"):
            self.stage = event["stage"]
        self.events.append(event)
        if len(self.events) > _MAX_BUFFER:
            self.events = self.events[-_MAX_BUFFER:]
        for q in list(self._subscribers):
            q.put_nowait(event)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/api/compose/test_session.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add api/server/services/compose/session.py tests/api/compose/test_session.py
git commit -m "feat(compose): ComposeSession event buffer + SSE pub/sub (phase 1)"
```

---

## Task 5: `ComposeBridge` — handshake, prompt, notify→translate→emit

**Files:**
- Create: `api/server/services/compose/bridge.py`
- Test: `tests/api/compose/test_bridge.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/compose/test_bridge.py`:

```python
import asyncio
import sys
import pytest
from api.server.services.compose.session import ComposeSession
from api.server.services.compose.bridge import ComposeBridge

FAKE = ["tests/api/compose/fake_acp_agent.py"]


@pytest.mark.asyncio
async def test_bridge_streams_translated_events_then_ready(monkeypatch):
    monkeypatch.setenv("FAKE_ACP_TRACE", "tests/api/compose/fixtures/basic_trace.jsonl")
    session = ComposeSession("cid1")
    bridge = ComposeBridge(
        session, document_text="A capex approval process.",
        copilot_cmd=[sys.executable, *FAKE],
    )
    await bridge.start()

    # Collect until we hit the terminal 'ready' stage (bridge sets it after prompt).
    collected: list[dict] = []
    q = session.subscribe()
    for _ in range(50):
        ev = await asyncio.wait_for(q.get(), timeout=5)
        collected.append(ev)
        if ev.get("type") == "stage" and ev.get("stage") == "ready":
            break

    types = [e["type"] for e in collected]
    assert "thought" in types
    assert "tool" in types
    assert "narration" in types
    assert collected[-1] == {"type": "stage", "stage": "ready", "label": "Run complete"}
    assert session.done is True
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/api/compose/test_bridge.py -v`
Expected: FAIL — `ModuleNotFoundError: ...bridge`.

- [ ] **Step 3: Implement `bridge.py`**

Create `api/server/services/compose/bridge.py`:

```python
"""ComposeBridge: drive one `copilot --acp` run and stream normalized events.

Phase 1 uses a simplified prompt and no MCP tools; the real add-domain prompt,
the compose-bridge MCP, document intake, and the safety guard land in Phase 2.
The `copilot_cmd` seam lets tests inject a fake ACP agent.
"""
from __future__ import annotations

import asyncio
import os

from .acp_client import AcpClient
from .session import ComposeSession
from .translate import translate_update

REPO_ROOT = os.getenv("ZAVA_REPO_ROOT", os.getcwd())


def _default_copilot_cmd() -> list[str]:
    return [os.getenv("COMPOSE_COPILOT_BIN", "copilot")]


class ComposeBridge:
    def __init__(
        self,
        session: ComposeSession,
        document_text: str,
        copilot_cmd: list[str] | None = None,
        repo_root: str | None = None,
    ) -> None:
        self.session = session
        self.document_text = document_text
        self.repo_root = repo_root or REPO_ROOT
        self._copilot_cmd = copilot_cmd or _default_copilot_cmd()
        self.client = AcpClient(self._on_notify, self._on_request)
        self._acp_session_id: str | None = None

    async def start(self) -> None:
        cmd = [*self._copilot_cmd, "--acp", "-C", self.repo_root,
               "--allow-all", "--log-level", "none"]
        await self.client.start(cmd, cwd=self.repo_root)
        await self.client.request("initialize", {
            "protocolVersion": 1,
            "clientCapabilities": {"fs": {"readTextFile": False, "writeTextFile": False}},
        })
        res = await self.client.request(
            "session/new", {"cwd": self.repo_root, "mcpServers": []})
        self._acp_session_id = res.get("sessionId")
        self.session.emit({"type": "stage", "stage": "understanding",
                           "label": "Reading the document"})
        asyncio.create_task(self._run_prompt())

    async def _run_prompt(self) -> None:
        try:
            await self.client.request("session/prompt", {
                "sessionId": self._acp_session_id,
                "prompt": [{"type": "text", "text": self._build_prompt()}],
            })
        except Exception as ex:  # surface, never stall silently
            self.session.emit({"type": "error", "message": str(ex), "fatal": True})
        finally:
            self.session.done = True
            self.session.emit({"type": "stage", "stage": "ready", "label": "Run complete"})
            await self.client.stop()

    def _build_prompt(self) -> str:
        return (
            "Compose a new Zava domain from the following process document by "
            "running the add-domain skill. Ask clarifying questions only if the "
            "document is genuinely ambiguous; always present the drafted brief "
            "before composing.\n\n---\n" + self.document_text + "\n---"
        )

    async def _on_notify(self, method: str, params: dict) -> None:
        if method == "session/update":
            for event in translate_update(params):
                self.session.emit(event)

    async def _on_request(self, method: str, params: dict) -> dict:
        # Phase 1 runs with --allow-all so permission requests should not fire;
        # auto-approve defensively if they do.
        if method == "session/request_permission":
            opts = params.get("options") or []
            allow = next(
                (o for o in opts if str(o.get("kind", "")).startswith("allow")),
                opts[0] if opts else {"optionId": "allow"},
            )
            return {"outcome": {"outcome": "selected", "optionId": allow.get("optionId")}}
        return {}
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/api/compose/test_bridge.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/server/services/compose/bridge.py tests/api/compose/test_bridge.py
git commit -m "feat(compose): ComposeBridge drives ACP run into normalized stream (phase 1)"
```

---

## Task 6: `/api/compose` router + mount

**Files:**
- Create: `api/server/routes/compose.py`
- Modify: `api/server/main.py` (add the include_router call)
- Test: `tests/api/compose/test_routes_compose.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/compose/test_routes_compose.py`:

```python
import sys
import json
from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.server.routes.compose import router, set_copilot_cmd_for_tests


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


def test_create_session_and_stream(monkeypatch):
    monkeypatch.setenv("FAKE_ACP_TRACE", "tests/api/compose/fixtures/basic_trace.jsonl")
    set_copilot_cmd_for_tests([sys.executable, "tests/api/compose/fake_acp_agent.py"])
    client = TestClient(_app())

    r = client.post("/api/compose/session", data={"text": "A capex approval process."})
    assert r.status_code == 200
    cid = r.json()["compose_id"]
    assert cid

    # Consume the SSE stream to the terminal 'ready' stage.
    events = []
    with client.stream("GET", f"/api/compose/{cid}/stream") as s:
        for line in s.iter_lines():
            if not line or not line.startswith("data: "):
                continue
            ev = json.loads(line[len("data: "):])
            events.append(ev)
            if ev.get("type") == "stage" and ev.get("stage") == "ready":
                break

    types = {e["type"] for e in events}
    assert {"thought", "tool", "narration"} <= types


def test_stream_unknown_session_404():
    client = TestClient(_app())
    assert client.get("/api/compose/nope/stream").status_code == 404


def test_non_loopback_forbidden(monkeypatch):
    set_copilot_cmd_for_tests([sys.executable, "tests/api/compose/fake_acp_agent.py"])
    client = TestClient(_app())
    r = client.post("/api/compose/session", data={"text": "x"},
                    headers={"x-forwarded-for": "8.8.8.8"})
    assert r.status_code == 403
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/api/compose/test_routes_compose.py -v`
Expected: FAIL — `ModuleNotFoundError: api.server.routes.compose`.

- [ ] **Step 3: Implement `routes/compose.py`**

Create `api/server/routes/compose.py`:

```python
"""Visual Domain Composer HTTP surface (Phase 1: create + SSE stream).

LOCALHOST-ONLY: this endpoint drives a coding agent that edits the repo. It
refuses non-loopback callers. Phase 2 adds the `.poc-safety` marker check,
document intake (PDF/docx), and the answer/brief/permission/ignite endpoints.
"""
from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Form, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from api.server.services.compose.bridge import ComposeBridge
from api.server.services.compose.session import ComposeSession

router = APIRouter()

_SESSIONS: dict[str, ComposeSession] = {}
_COPILOT_CMD_OVERRIDE: list[str] | None = None

_LOOPBACK = {"127.0.0.1", "::1", "localhost", "testclient"}


def set_copilot_cmd_for_tests(cmd: list[str] | None) -> None:
    """Test seam: inject the fake ACP agent command."""
    global _COPILOT_CMD_OVERRIDE
    _COPILOT_CMD_OVERRIDE = cmd


def _is_loopback(request: Request) -> bool:
    # Any forwarding header means a proxy/non-local caller -> reject.
    if request.headers.get("x-forwarded-for"):
        return False
    host = request.client.host if request.client else ""
    return host in _LOOPBACK


@router.post("/api/compose/session")
async def create_session(
    request: Request,
    text: str | None = Form(default=None),
    file: UploadFile | None = None,
):
    if not _is_loopback(request):
        return JSONResponse({"error": "forbidden: localhost only"}, status_code=403)

    document_text = text or ""
    if file is not None:
        document_text = (await file.read()).decode("utf-8", "ignore")
    if not document_text.strip():
        return JSONResponse({"error": "empty document"}, status_code=422)

    cid = uuid.uuid4().hex
    session = ComposeSession(cid)
    _SESSIONS[cid] = session
    bridge = ComposeBridge(session, document_text, copilot_cmd=_COPILOT_CMD_OVERRIDE)
    await bridge.start()
    return {"compose_id": cid}


@router.get("/api/compose/{cid}/stream")
async def stream(cid: str):
    session = _SESSIONS.get(cid)
    if session is None:
        return JSONResponse({"error": "not found"}, status_code=404)

    async def gen():
        q = session.subscribe()
        try:
            while True:
                event = await q.get()
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") in ("stage",) and event.get("stage") in ("ready", "error"):
                    break
        finally:
            session.unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/api/compose/{cid}")
async def get_session(cid: str):
    session = _SESSIONS.get(cid)
    if session is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return {"compose_id": cid, "stage": session.stage,
            "done": session.done, "events": session.events}
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/api/compose/test_routes_compose.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Mount the router in `main.py`**

Open `api/server/main.py`, find the block of `app.include_router(...)` calls (the other routers are registered together). Add:

```python
from api.server.routes.compose import router as compose_router
```
with the other route imports, and:
```python
app.include_router(compose_router)
```
with the other `include_router` calls.

- [ ] **Step 6: Verify the app still imports**

Run: `uv run python -c "from api.server.main import app; print('routes:', sum(1 for r in app.routes if getattr(r, 'path', '').startswith('/api/compose')))"`
Expected: prints `routes: 3`.

- [ ] **Step 7: Run the full compose test package**

Run: `uv run pytest tests/api/compose/ -v`
Expected: PASS (all tasks' tests green).

- [ ] **Step 8: Commit**

```bash
git add api/server/routes/compose.py api/server/main.py tests/api/compose/test_routes_compose.py
git commit -m "feat(compose): /api/compose session + SSE stream, mounted (phase 1)"
```

---

## Task 7: Phase-1 exit check

**Files:** none (verification).

- [ ] **Step 1: Full backend test sweep**

Run: `uv run pytest tests/api/compose/ -q`
Expected: all green.

- [ ] **Step 2: Lint/type (only what the repo already runs)**

Run: `uv run ruff check api/server/services/compose api/server/routes/compose.py`
Expected: no errors (fix any surfaced).

- [ ] **Step 3: Manual end-to-end against the fake agent (optional confidence)**

Start a throwaway app on a random port using the fake agent, POST a doc, and curl the stream — confirms the SSE wire format by eye. (Use the `TestClient` path in `test_routes_compose.py` as the canonical check; this manual step is optional.)

- [ ] **Step 4: Confirm Phase-1 done-criteria**

  - `POST /api/compose/session` with `{text}` returns a `compose_id`.
  - `GET /api/compose/{id}/stream` emits normalized `thought` / `tool` / `narration` events translated from ACP, ending with a terminal `stage: ready`.
  - Non-loopback callers get `403`.
  - No real `copilot` agent is invoked in any test (hermetic).

---

## Self-Review (completed against the spec)

- **Spec coverage (Phase-1 slice):** ACP client (§4.2) ✓ Task 3; normalized SSE schema (§4.4) ✓ Task 1 + fixtures; ComposeSession/SSE hub (§4.2) ✓ Task 4; bridge handshake + translate (§3.1, §4.2) ✓ Task 5; `/api/compose/session` + `/stream` (§4.1) ✓ Task 6; localhost guard (§6, partial — `.poc-safety` marker deferred to Phase 2) ✓ Task 6. Deferred to Phase 2/3 by design: MCP tools, `/answer` `/brief` `/permission` `/ignite`, document PDF/docx intake, micro-skill, cockpit UI, Ignite restart.
- **Placeholder scan:** none — every step has runnable code/commands.
- **Type consistency:** `translate_update(params)` signature is consistent across `translate.py`, `bridge.py`, and `test_translate.py`; `ComposeSession.subscribe/unsubscribe/emit` and `ComposeBridge(session, document_text, copilot_cmd=...)` match across bridge, routes, and tests; the normalized event `type` values (`thought`/`narration`/`tool`/`plan`/`stage`/`error`) match the spec §4.4 contract.

---

## Next

Phase 2 (`2026-07-07-visual-domain-composer-phase-2-agent-mcp.md`) swaps the fake agent for real `copilot --acp`, adds the compose-bridge MCP (`report_stage`/`ask_operator`/`present_brief`/`composition_complete`) with the `/answer` + `/brief` resolvers, document→text intake (PDF/docx), the `.poc-safety` gate + `COMPOSE_PERMISSION_POLICY` knob, and the committed `compose-domain-live` micro-skill.
