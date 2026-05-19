# Substrate Agentic Segments — Phase 2: LLMRuntime Protocol — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a provider-neutral `LLMRuntime` Protocol so `_wrapper.py` no longer imports `copilot.CopilotClient` directly. `GHCPRuntime` is the included implementation; `FakeRuntime` unblocks deterministic tests for Phase 3. No behaviour change with `LLM_RUNTIME` unset.

**Architecture:** New 3-file `runtime/` triad under `api/functions/graphs/executors/agents/`: `runtime.py` (Protocol + result model + `_get_runtime()` factory), `runtime_ghcp.py` (existing GHCP body moved verbatim), `runtime_fake.py` (canned response, zero subprocess). `_wrapper.py:run_agent_session` delegates to `_get_runtime().run_session(...)`. OTEL session-event bridge stays in `_wrapper.py` because it's provider-independent; the runtime accepts an `event_subscriber` callback so the bridge subscribes from the outside.

**Tech Stack:** Python 3.11, `typing.Protocol` with `runtime_checkable`, Pydantic v2, pytest. No new third-party dependencies.

**Spec:** [docs/superpowers/specs/2026-05-19-substrate-agentic-segments-design.md](../specs/2026-05-19-substrate-agentic-segments-design.md) — Phase 2.

---

## File structure

### Create

```
api/functions/graphs/executors/agents/
  runtime.py              — LLMRuntime Protocol, LLMRuntimeResult, _get_runtime() factory
  runtime_ghcp.py         — GHCPRuntime: existing CopilotClient body moved here
  runtime_fake.py         — FakeRuntime: canned response, no subprocess

tests/api/functions/agents/
  test_runtime_protocol.py
```

### Modify

```
api/functions/graphs/executors/agents/_wrapper.py
  — delegate session-open block to _get_runtime().run_session
  — keep OTEL bridge, FleetEvent emission, agent_name derivation
pyproject.toml
  — comment-only: note MAF + GHCP deps are runtime-optional once LLM_RUNTIME != ghcp
```

---

## Phase A — Protocol + result model

### Task 1: Define `LLMRuntime` Protocol and `LLMRuntimeResult`

**Files:**
- Create: `api/functions/graphs/executors/agents/runtime.py`
- Test: `tests/api/functions/agents/test_runtime_protocol.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/functions/agents/test_runtime_protocol.py
"""Phase 2 of plan/refactor-substrate-agentic-segments-1.md.

Locks the LLMRuntime contract and the env-driven dispatch.
"""
from __future__ import annotations
import os
os.environ["AZURE_STORAGE_CONNECTION_STRING"] = ""

import subprocess
import pytest
from pydantic import ValidationError


def test_llm_runtime_result_shape() -> None:
    from api.functions.graphs.executors.agents.runtime import LLMRuntimeResult
    r = LLMRuntimeResult(text='{"ok":true}', tool_calls=[], input_tokens=10, output_tokens=20)
    assert r.text == '{"ok":true}'
    assert r.tool_calls == []
    assert r.input_tokens == 10
    assert r.output_tokens == 20
    with pytest.raises(ValidationError):
        LLMRuntimeResult()  # text required


def test_runtime_protocol_runtime_checkable() -> None:
    from api.functions.graphs.executors.agents.runtime import LLMRuntime

    class _Stub:
        async def run_session(self, **kw):  # type: ignore[no-untyped-def]
            from api.functions.graphs.executors.agents.runtime import LLMRuntimeResult
            return LLMRuntimeResult(text="x", tool_calls=[])

    assert isinstance(_Stub(), LLMRuntime)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/api/functions/agents/test_runtime_protocol.py::test_llm_runtime_result_shape -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'api.functions.graphs.executors.agents.runtime'`.

- [ ] **Step 3: Write the file**

```python
# api/functions/graphs/executors/agents/runtime.py
"""Provider-neutral LLM runtime contract.

Phase 2 of plan/refactor-substrate-agentic-segments-1.md.

`_wrapper.py:run_agent_session` obtains an `LLMRuntime` via `_get_runtime()`
and never imports `copilot.CopilotClient` directly. New providers
(Claude, Azure OpenAI) ship as additional `runtime_<name>.py` files
implementing this Protocol, plus one new branch in `_get_runtime()`.

The OTEL session-event bridge stays in `_wrapper.py`; the runtime
accepts an `event_subscriber` callable it invokes with each session
event so the bridge subscribes from the outside without the runtime
needing to know about OpenTelemetry.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Protocol, runtime_checkable

from pydantic import BaseModel


class LLMRuntimeResult(BaseModel):
    """Return value of `LLMRuntime.run_session`. The shape `_wrapper.py`
    already produces; lifted to its own model so multiple runtimes can
    agree on it."""

    text: str
    tool_calls: list[dict] = []
    input_tokens: int | None = None
    output_tokens: int | None = None
    raw_event: Any = None


@runtime_checkable
class LLMRuntime(Protocol):
    """Open one LLM session, send one prompt, return the parsed
    response. Implementations: `runtime_ghcp.GHCPRuntime` (production),
    `runtime_fake.FakeRuntime` (tests + replay harness)."""

    async def run_session(
        self,
        *,
        prompt: str,
        system_message: str | None = None,
        skill_directories: list[Path] | None = None,
        tools: list | None = None,
        permission_handler: Callable | None = None,
        attachments: list[dict] | None = None,
        model: str = "gpt-4.1",
        timeout_s: float = 120.0,
        event_subscriber: Callable[[Any], None] | None = None,
    ) -> LLMRuntimeResult:
        ...


def _get_runtime() -> LLMRuntime:
    """Dispatch on `LLM_RUNTIME` env var. Defaults to GHCP."""
    name = os.environ.get("LLM_RUNTIME", "ghcp").strip().lower()
    if name == "fake":
        from api.functions.graphs.executors.agents.runtime_fake import FakeRuntime
        return FakeRuntime()
    if name == "ghcp":
        from api.functions.graphs.executors.agents.runtime_ghcp import GHCPRuntime
        return GHCPRuntime()
    raise ValueError(
        f"LLM_RUNTIME={name!r} not recognised. Supported: 'ghcp', 'fake'."
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/api/functions/agents/test_runtime_protocol.py::test_llm_runtime_result_shape tests/api/functions/agents/test_runtime_protocol.py::test_runtime_protocol_runtime_checkable -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add api/functions/graphs/executors/agents/runtime.py tests/api/functions/agents/test_runtime_protocol.py
git commit -m "feat(runtime): introduce LLMRuntime Protocol + LLMRuntimeResult"
```

---

## Phase B — FakeRuntime first (unblocks dispatch test)

### Task 2: Implement `FakeRuntime`

**Files:**
- Create: `api/functions/graphs/executors/agents/runtime_fake.py`
- Test: `tests/api/functions/agents/test_runtime_protocol.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `tests/api/functions/agents/test_runtime_protocol.py`:

```python
import asyncio


def test_fake_runtime_canned_response() -> None:
    from api.functions.graphs.executors.agents.runtime_fake import FakeRuntime
    rt = FakeRuntime()
    rt.canned_text = '{"verdict":"strong"}'
    result = asyncio.run(rt.run_session(prompt="x"))
    assert result.text == '{"verdict":"strong"}'
    assert rt.call_count == 1


def test_get_runtime_dispatch_fake(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_RUNTIME", "fake")
    from api.functions.graphs.executors.agents.runtime import _get_runtime
    from api.functions.graphs.executors.agents.runtime_fake import FakeRuntime
    assert isinstance(_get_runtime(), FakeRuntime)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/api/functions/agents/test_runtime_protocol.py::test_fake_runtime_canned_response -v
```

Expected: FAIL — `ModuleNotFoundError: ...runtime_fake`.

- [ ] **Step 3: Write the file**

```python
# api/functions/graphs/executors/agents/runtime_fake.py
"""Test/replay double for `LLMRuntime`.

Returns a canned response, increments `call_count`, never opens a
subprocess. Mutable class attributes so tests configure behaviour
before calling `run_session`:

    rt = FakeRuntime()
    rt.canned_text = '{"verdict": "strong"}'
    rt.canned_tool_calls = [{"name": "policy.search", "args": "{}", "result": "[]"}]
"""
from __future__ import annotations

from typing import Any, Callable
from pathlib import Path

from api.functions.graphs.executors.agents.runtime import LLMRuntimeResult


class FakeRuntime:
    canned_text: str = '{"ok": true}'
    canned_tool_calls: list[dict] = []
    canned_input_tokens: int | None = 10
    canned_output_tokens: int | None = 20
    call_count: int = 0
    last_prompt: str | None = None

    async def run_session(
        self,
        *,
        prompt: str,
        system_message: str | None = None,
        skill_directories: list[Path] | None = None,
        tools: list | None = None,
        permission_handler: Callable | None = None,
        attachments: list[dict] | None = None,
        model: str = "gpt-4.1",
        timeout_s: float = 120.0,
        event_subscriber: Callable[[Any], None] | None = None,
    ) -> LLMRuntimeResult:
        self.call_count += 1
        self.last_prompt = prompt
        return LLMRuntimeResult(
            text=self.canned_text,
            tool_calls=list(self.canned_tool_calls),
            input_tokens=self.canned_input_tokens,
            output_tokens=self.canned_output_tokens,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/api/functions/agents/test_runtime_protocol.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add api/functions/graphs/executors/agents/runtime_fake.py tests/api/functions/agents/test_runtime_protocol.py
git commit -m "feat(runtime): add FakeRuntime for deterministic tests"
```

---

## Phase C — Move GHCP body into GHCPRuntime

### Task 3: Implement `GHCPRuntime`

**Files:**
- Create: `api/functions/graphs/executors/agents/runtime_ghcp.py`
- Modify: `api/functions/graphs/executors/agents/_wrapper.py`
- Test: `tests/api/functions/agents/test_runtime_protocol.py` (extend)

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_ghcp_runtime_satisfies_protocol() -> None:
    from api.functions.graphs.executors.agents.runtime import LLMRuntime
    from api.functions.graphs.executors.agents.runtime_ghcp import GHCPRuntime
    assert isinstance(GHCPRuntime(), LLMRuntime)


def test_get_runtime_default_is_ghcp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_RUNTIME", raising=False)
    from api.functions.graphs.executors.agents.runtime import _get_runtime
    from api.functions.graphs.executors.agents.runtime_ghcp import GHCPRuntime
    assert isinstance(_get_runtime(), GHCPRuntime)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/api/functions/agents/test_runtime_protocol.py::test_ghcp_runtime_satisfies_protocol -v
```

Expected: FAIL — `ModuleNotFoundError: ...runtime_ghcp`.

- [ ] **Step 3: Write the file**

Lift the body of `_wrapper.py:run_agent_session`'s `CopilotClient` block (`SubprocessConfig`, `client.create_session`, `session.send_and_wait`, `session.disconnect`) into `GHCPRuntime.run_session`. Also extract `_gh_token` to a module-level cached helper that both files can import.

```python
# api/functions/graphs/executors/agents/runtime_ghcp.py
"""GHCP implementation of LLMRuntime — current production path.

Body lifted verbatim from `_wrapper.py:run_agent_session` so behaviour
under `LLM_RUNTIME=ghcp` (the default) is unchanged.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Callable

from copilot import CopilotClient
from copilot.client import SubprocessConfig
from copilot.session import PermissionHandler

from api.functions.graphs.executors.agents.runtime import LLMRuntimeResult


_gh_token_cache: str | None = None


def _gh_token() -> str:
    global _gh_token_cache
    if _gh_token_cache is None:
        _gh_token_cache = subprocess.check_output(
            ["gh", "auth", "token"], text=True,
        ).strip()
    return _gh_token_cache


class GHCPRuntime:
    """Wraps copilot.CopilotClient as an LLMRuntime."""

    async def run_session(
        self,
        *,
        prompt: str,
        system_message: str | None = None,
        skill_directories: list[Path] | None = None,
        tools: list | None = None,
        permission_handler: Callable | None = None,
        attachments: list[dict] | None = None,
        model: str = "gpt-4.1",
        timeout_s: float = 120.0,
        event_subscriber: Callable[[Any], None] | None = None,
    ) -> LLMRuntimeResult:
        config = SubprocessConfig(github_token=_gh_token(), log_level="warning")
        client = CopilotClient(config)
        async with client:
            session_kwargs: dict = {
                "on_permission_request": permission_handler or PermissionHandler.approve_all,
                "model": model,
                "tools": tools or [],
            }
            if system_message:
                session_kwargs["system_message"] = {"mode": "append", "content": system_message}
            if skill_directories:
                session_kwargs["skill_directories"] = [str(p) for p in skill_directories]
            session = await client.create_session(**session_kwargs)
            unsub = None
            if event_subscriber is not None:
                unsub = session.on(event_subscriber)
            try:
                if attachments:
                    response_event = await session.send_and_wait(
                        prompt, attachments=attachments, timeout=timeout_s,
                    )
                else:
                    response_event = await session.send_and_wait(prompt, timeout=timeout_s)
            finally:
                if unsub is not None:
                    try:
                        unsub()
                    except Exception:
                        pass
                try:
                    await session.disconnect()
                except Exception:
                    pass

        text = ""
        in_tok = out_tok = None
        if response_event and getattr(response_event, "data", None):
            text = getattr(response_event.data, "content", "") or ""
            usage = getattr(response_event.data, "usage", None)
            if usage is not None:
                in_tok = getattr(usage, "input_tokens", None) or getattr(usage, "prompt_tokens", None)
                out_tok = getattr(usage, "output_tokens", None) or getattr(usage, "completion_tokens", None)

        return LLMRuntimeResult(
            text=text,
            tool_calls=[],  # collected externally via event_subscriber
            input_tokens=in_tok,
            output_tokens=out_tok,
            raw_event=response_event,
        )
```

- [ ] **Step 4: Refactor `_wrapper.py:run_agent_session`**

Replace the inline `CopilotClient`/`session.send_and_wait`/`disconnect` block in `_wrapper.py` with one call through the runtime. Keep the OTEL bridge subscribing via `event_subscriber=`. Pseudocode for the replacement:

```python
# inside run_agent_session, after agent_name + skill_text setup
runtime = _get_runtime()
def _subscriber(event):
    _on_event_for_bridge(event)  # the existing closure from _install_session_otel_bridge
# (the bridge stays; just plug it in through event_subscriber)

permission_handler = (
    AGTPermissionHandler(skill_label=agent_name, workflow_id=workflow_id)
    if os.environ.get("AGT_ENFORCE", "0").strip() in ("1", "true", "TRUE", "yes")
    else None  # GHCPRuntime falls back to approve_all
)

result = await runtime.run_session(
    prompt=prompt,
    system_message=skill_text,
    skill_directories=[skill_dir] if skill_dir else None,
    tools=tools,
    permission_handler=permission_handler,
    attachments=attachments,
    model=model,
    timeout_s=120.0,
    event_subscriber=_subscriber,
)

text = result.text
in_tok = result.input_tokens
out_tok = result.output_tokens
response_event = result.raw_event
# remaining code (FleetEvent emission, return shape) unchanged
```

Imports to add at top of `_wrapper.py`:

```python
from api.functions.graphs.executors.agents.runtime import _get_runtime, LLMRuntimeResult
```

Imports to remove from `_wrapper.py`:

```python
from copilot import CopilotClient
from copilot.client import SubprocessConfig
# PermissionHandler import stays if AGTPermissionHandler fallback still uses it; otherwise drop
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/api/functions/agents/test_runtime_protocol.py -v
pytest tests/api/server/services/governance/test_permission_handler.py -v
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add api/functions/graphs/executors/agents/runtime_ghcp.py api/functions/graphs/executors/agents/_wrapper.py tests/api/functions/agents/test_runtime_protocol.py
git commit -m "refactor(runtime): move GHCP session body into GHCPRuntime; _wrapper delegates"
```

---

## Phase D — End-to-end fake path

### Task 4: Verify `run_agent_session` under `LLM_RUNTIME=fake` never spawns a subprocess

**Files:**
- Test: `tests/api/functions/agents/test_runtime_protocol.py` (extend)

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_run_agent_session_under_fake_no_subprocess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_RUNTIME", "fake")

    # Patch subprocess.check_output to raise if anyone calls it
    def _boom(*args, **kwargs):
        raise AssertionError("FakeRuntime path must not spawn a subprocess")
    monkeypatch.setattr(subprocess, "check_output", _boom)

    # Configure FakeRuntime's canned response BEFORE the call
    from api.functions.graphs.executors.agents.runtime_fake import FakeRuntime
    FakeRuntime.canned_text = '{"verdict": "strong", "rationale": "x"}'

    from api.functions.graphs.executors.agents._wrapper import run_agent_session
    out = await run_agent_session(
        prompt="screen these candidates",
        tools=[],
        skill_dir=None,
        skill_label="hiring-segment-b",
        workflow_id="WF-TEST-1",
    )
    assert out == {"verdict": "strong", "rationale": "x"}
```

- [ ] **Step 2: Run test to verify it fails (or passes if Phase C wired correctly)**

```bash
pytest tests/api/functions/agents/test_runtime_protocol.py::test_run_agent_session_under_fake_no_subprocess -v
```

Expected: PASS after Phase C is wired. If it FAILS with `AssertionError: FakeRuntime path must not spawn a subprocess`, the `_wrapper.py` refactor is incomplete — fix Phase C Step 4.

- [ ] **Step 3: Commit**

```bash
git add tests/api/functions/agents/test_runtime_protocol.py
git commit -m "test(runtime): end-to-end fake path bypasses subprocess"
```

---

## Phase E — `pyproject.toml` housekeeping

### Task 5: Comment-only documentation that MAF + GHCP deps are runtime-optional

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Edit `pyproject.toml`**

Locate the `dependencies = [` block (~line 12). Above the GHCP/MAF lines, add this comment block:

```toml
# LLM runtime providers — pluggable via LLM_RUNTIME env var
# (LLM_RUNTIME=ghcp default, or fake for tests). The four packages
# below back GHCPRuntime; a future ClaudeRuntime / AzureOpenAIRuntime
# implementation would not require any of them. See
# api/functions/graphs/executors/agents/runtime.py for the Protocol
# and docs/superpowers/specs/2026-05-19-substrate-agentic-segments-design.md
# for the architectural rationale.
```

- [ ] **Step 2: Verify no version changes**

```bash
git diff pyproject.toml
```

Expected: only the comment block added; no `+`/`-` on any dependency line.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "docs(deps): note GHCP+MAF deps are runtime-optional"
```

---

## Acceptance

- [ ] `pytest tests/api/functions/agents/test_runtime_protocol.py -v` — all green
- [ ] `pytest tests/api/server/services/governance/test_permission_handler.py -v` — still green (Phase 1 regression)
- [ ] `grep -n 'from copilot import CopilotClient' api/functions/graphs/executors/agents/_wrapper.py` — 0 matches (wrapper no longer imports the SDK client directly)
- [ ] With `LLM_RUNTIME` unset, `_get_runtime()` returns `GHCPRuntime`. With `LLM_RUNTIME=fake`, returns `FakeRuntime`.
- [ ] No new third-party dependency added to `pyproject.toml`.

---

## Risks

- **R1**: `_install_session_otel_bridge` in `_wrapper.py` may have hidden coupling to `copilot.session.Session` types beyond the `session.on(...)` subscribe pattern. Mitigation: keep the bridge body in `_wrapper.py`; refactor only the subscribe call so it goes through `event_subscriber=...`. If the bridge breaks, restore the inline `session.on(...)` call and pass the bridge's callable directly into the runtime.
- **R2**: `agent-framework-github-copilot` is a beta (`>=1.0.0b260409`). Any breaking change in `CopilotClient.create_session` surfaces in `runtime_ghcp.py` only; the Protocol shields the rest of the codebase.
