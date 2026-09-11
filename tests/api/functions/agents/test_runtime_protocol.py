"""Phase 2 of plan/refactor-substrate-agentic-segments-1.md.

Locks the LLMRuntime contract and the env-driven dispatch.
"""
from __future__ import annotations
import os
os.environ["AZURE_STORAGE_CONNECTION_STRING"] = ""

import subprocess
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from copilot.generated.session_events import SessionEventType
from copilot.tools import Tool, ToolResult
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


def test_azure_deployment_override_does_not_change_workflow_default(monkeypatch) -> None:
    from api.functions.graphs.executors.agents.runtime import _get_runtime

    monkeypatch.setenv("LLM_RUNTIME", "azure")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "workflow-deployment")

    supervisor = _get_runtime(azure_deployment="supervisor-deployment")
    workflow = _get_runtime()

    assert supervisor._deployment == "supervisor-deployment"
    assert workflow._deployment == "workflow-deployment"


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


@pytest.fixture
def ghcp_session(monkeypatch):
    from api.functions.graphs.executors.agents import runtime_ghcp

    class Session:
        def __init__(self):
            self.events = []
            self.subscriber = None
            self.unsubscribe = MagicMock()
            self.disconnect = AsyncMock()

        def on(self, subscriber):
            self.subscriber = subscriber
            return self.unsubscribe

        async def send_and_wait(self, *args, **kwargs):
            for event in self.events:
                if self.subscriber is not None:
                    self.subscriber(event)
            return SimpleNamespace(data=SimpleNamespace(content='{"ok": true}'))

    session = Session()
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.create_session = AsyncMock(return_value=session)
    factory = MagicMock(return_value=client)
    token = MagicMock(return_value="test-token")
    monkeypatch.setattr(runtime_ghcp, "CopilotClient", factory)
    monkeypatch.setattr(runtime_ghcp, "_gh_token", token)
    tool = Tool(
        name="lookup", description="Read fixture evidence",
        handler=lambda invocation: ToolResult(text_result_for_llm="evidence"),
    )
    return SimpleNamespace(
        runtime=runtime_ghcp.GHCPRuntime(), session=session,
        factory=factory, token=token, tool=tool,
    )


async def test_ghcp_rejects_unregistered_required_tools_before_starting(ghcp_session):
    with pytest.raises(ValueError, match="not registered"):
        await ghcp_session.runtime.run_session(
            prompt="read evidence", tools=[ghcp_session.tool],
            required_tool_names=["missing"],
        )
    ghcp_session.factory.assert_not_called()
    ghcp_session.token.assert_not_called()


async def test_ghcp_rejects_final_answer_without_required_tool(ghcp_session):
    with pytest.raises(RuntimeError, match="required tools.*lookup"):
        await ghcp_session.runtime.run_session(
            prompt="read evidence", tools=[ghcp_session.tool],
            required_tool_names=["lookup"],
        )
    ghcp_session.session.disconnect.assert_awaited_once()
    ghcp_session.session.unsubscribe.assert_called_once()


@pytest.mark.parametrize("success", [False, None])
async def test_ghcp_failed_or_unknown_tool_result_is_not_success(ghcp_session, success):
    ghcp_session.session.events = [
        SimpleNamespace(
            type=SessionEventType.TOOL_EXECUTION_START,
            data=SimpleNamespace(tool_name="lookup", tool_call_id="call-1"),
        ),
        SimpleNamespace(
            type=SessionEventType.TOOL_EXECUTION_COMPLETE,
            data=SimpleNamespace(tool_call_id="call-1", success=success),
        ),
    ]
    with pytest.raises(RuntimeError, match="required tools.*lookup"):
        await ghcp_session.runtime.run_session(
            prompt="read evidence", tools=[ghcp_session.tool],
            required_tool_names=["lookup"],
        )


async def test_ghcp_validates_required_tool_and_preserves_subscriber(ghcp_session):
    ghcp_session.session.events = [
        SimpleNamespace(
            type=SessionEventType.TOOL_EXECUTION_START,
            data=SimpleNamespace(tool_name="lookup", tool_call_id="call-1"),
        ),
        SimpleNamespace(
            type=SessionEventType.TOOL_EXECUTION_COMPLETE,
            data=SimpleNamespace(tool_call_id="call-1", success=True),
        ),
    ]
    observed = []
    result = await ghcp_session.runtime.run_session(
        prompt="read evidence", tools=[ghcp_session.tool],
        required_tool_names=["lookup", "lookup"], event_subscriber=observed.append,
    )
    assert result.text == '{"ok": true}'
    assert observed == ghcp_session.session.events
    ghcp_session.session.unsubscribe.assert_called_once()
