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


def test_ghcp_runtime_satisfies_protocol() -> None:
    from api.functions.graphs.executors.agents.runtime import LLMRuntime
    from api.functions.graphs.executors.agents.runtime_ghcp import GHCPRuntime
    assert isinstance(GHCPRuntime(), LLMRuntime)


def test_get_runtime_default_is_ghcp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_RUNTIME", raising=False)
    from api.functions.graphs.executors.agents.runtime import _get_runtime
    from api.functions.graphs.executors.agents.runtime_ghcp import GHCPRuntime
    assert isinstance(_get_runtime(), GHCPRuntime)


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
