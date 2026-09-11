"""Fleet Manager service wiring — bus → triage → queue → reasoning.

Covers the fix that lets `fleet.tick` (and other workflow-less wake events)
flow all the way through the pipeline to a `_process_batch` call, so the
demo rail pulses on idle runs instead of staying at "0 recent events".

Cloud startup and tool execution use a mocked HTTP client, not a Copilot
subprocess. The legacy wiring case injects a minimal GitHub session.
"""
from __future__ import annotations
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from copilot.generated.session_events import SessionEventType
from copilot.tools import Tool, ToolResult

from api.server.services.event_bus import EventBus
from api.server.services import fleet_manager_service
from api.server.services.fleet_manager_queue import QueueEntry
from api.server.services.fleet_manager_service import FleetManagerService
from api.shared.events import FleetEvent


class _FakeSession:
    """Minimal stand-in for a copilot session — `send_and_wait` returns a
    completion-like object so `_process_batch` can record `reasoning_done`."""

    async def send_and_wait(self, prompt: str, timeout: float = 120.0):
        return SimpleNamespace(data=SimpleNamespace(content="ok"))


@pytest.mark.parametrize("model,expected", [(None, "configured-model"), ("explicit-model", "explicit-model")])
def test_model_selection_honours_environment_and_explicit_override(monkeypatch, model, expected):
    monkeypatch.setenv("FLEET_MANAGER_MODEL", "configured-model")
    kwargs = {} if model is None else {"model": model}
    fm = FleetManagerService(
        bus=EventBus(), store=MagicMock(), audit=MagicMock(), **kwargs,
    )
    assert fm._model == expected


@pytest.mark.asyncio
async def test_github_start_preserves_persistent_session(monkeypatch):
    monkeypatch.setenv("LLM_RUNTIME", "ghcp")
    monkeypatch.setattr(fleet_manager_service, "_gh_token", lambda: "test-token")
    session = MagicMock()
    session.disconnect = AsyncMock()
    session.send_and_wait = AsyncMock(return_value=SimpleNamespace(data=SimpleNamespace(content="done")))
    client = MagicMock()
    client.start = AsyncMock()
    client.stop = AsyncMock()
    client.create_session = AsyncMock(return_value=session)
    factory = MagicMock(return_value=client)
    monkeypatch.setattr(fleet_manager_service, "CopilotClient", factory)
    fm = FleetManagerService(
        bus=EventBus(), store=MagicMock(), audit=MagicMock(), model="github-model", tools=[],
    )
    try:
        await fm.start()
        assert fm._started
        assert fm._runtime is None
        assert client.create_session.call_args.kwargs["model"] == "github-model"
        await fm._process_batch([QueueEntry(reason="fleet.tick")])
        session.send_and_wait.assert_awaited_once()
    finally:
        await fm.stop()
    session.disconnect.assert_awaited_once()
    client.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_fleet_tick_drives_wakeup_and_reasoning_start():
    bus = EventBus()
    live_events: list[dict] = []

    fm = FleetManagerService(
        bus=bus,
        store=MagicMock(),
        audit=MagicMock(),
        on_live=live_events.append,
    )
    # Bypass start() — wire the bus subscription and inject a fake session.
    fm._session = _FakeSession()
    fm._unsub_bus = bus.on_any(fm._observe)
    # Speed up the debounce so the test doesn't have to wait 2s.
    fm._queue._debounce = 0.05

    bus.emit(FleetEvent(type="fleet.tick"))

    # Wait past the debounce + a bit for _process_batch to run send_and_wait.
    await asyncio.sleep(0.2)

    kinds = [e["kind"] for e in live_events]
    assert "wakeup" in kinds, f"expected wakeup; got {kinds}"
    assert "reasoning_start" in kinds, f"expected reasoning_start; got {kinds}"
    assert kinds.index("wakeup") < kinds.index("reasoning_start")

    wakeup = next(e for e in live_events if e["kind"] == "wakeup")
    assert wakeup["data"]["workflow_id"] is None
    assert wakeup["data"]["reason"] == "fleet.tick"


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["azure", "aoai", "azure_openai"])
async def test_cloud_start_and_batch_do_not_require_github(monkeypatch, provider):
    from api.functions.graphs.executors.agents import runtime_aoai

    monkeypatch.setenv("LLM_RUNTIME", provider)
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "workflow-deployment")
    monkeypatch.setenv("AZURE_OPENAI_FLEET_MANAGER_DEPLOYMENT", "supervisor-deployment")
    github_token = MagicMock(side_effect=AssertionError("GitHub auth must not run"))
    monkeypatch.setattr(fleet_manager_service, "_gh_token", github_token)
    copilot_client = MagicMock(side_effect=AssertionError("Copilot must not start"))
    monkeypatch.setattr(fleet_manager_service, "CopilotClient", copilot_client)
    invoked = []

    def lookup(invocation):
        invoked.append(invocation.arguments)
        return ToolResult(text_result_for_llm='{"status":"awaiting_hitl"}')

    tool = Tool(
        name="lookup", description="Read current workflow state",
        handler=lookup,
        parameters={"type": "object", "properties": {"id": {"type": "string"}}},
    )
    tool_call = SimpleNamespace(
        id="call-1",
        function=SimpleNamespace(name="lookup", arguments='{"id":"WF-1"}'),
    )
    client = MagicMock()
    client.chat.completions.create.side_effect = [
        SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[tool_call]))],
            usage=None,
        ),
        SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Awaiting a decision", tool_calls=None))],
            usage=None,
        ),
    ]
    monkeypatch.setattr(runtime_aoai, "_build_client", lambda: client)
    events = []
    fm = FleetManagerService(
        bus=EventBus(), store=MagicMock(), audit=MagicMock(),
        model="github-model", tools=[tool], on_live=events.append,
    )
    try:
        await fm.start()
        assert fm._started
        github_token.assert_not_called()
        copilot_client.assert_not_called()

        await fm._process_batch([QueueEntry(workflow_id="WF-1", reason="suspended")])

        assert invoked == [{"id": "WF-1"}]
        calls = client.chat.completions.create.call_args_list
        assert calls[0].kwargs["model"] == "supervisor-deployment"
        assert calls[0].kwargs["messages"][0]["role"] == "system"
        completed = next(
            event for event in events
            if event["kind"] == "tool_call" and event["data"]["stage"] == "complete"
        )
        assert completed["data"]["result"] == '{"status":"awaiting_hitl"}'
        assert completed["data"]["success"] is True
        assert next(event for event in events if event["kind"] == "reasoning_done")["data"]["preview"] == (
            "Awaiting a decision"
        )
    finally:
        await fm.stop()


@pytest.mark.asyncio
async def test_fake_start_does_not_require_github(monkeypatch):
    from api.functions.graphs.executors.agents.runtime_fake import FakeRuntime

    monkeypatch.setenv("LLM_RUNTIME", "fake")
    token = MagicMock(side_effect=AssertionError("GitHub auth must not run"))
    monkeypatch.setattr(fleet_manager_service, "_gh_token", token)
    fm = FleetManagerService(
        bus=EventBus(), store=MagicMock(), audit=MagicMock(), tools=[],
    )
    try:
        await fm.start()
        assert fm._started
        assert isinstance(fm._runtime, FakeRuntime)
        token.assert_not_called()
    finally:
        await fm.stop()


@pytest.mark.asyncio
async def test_github_auth_failure_is_not_silent_startup_success(monkeypatch):
    monkeypatch.setenv("LLM_RUNTIME", "ghcp")
    monkeypatch.setattr(
        fleet_manager_service, "_gh_token",
        MagicMock(side_effect=RuntimeError("GitHub credentials unavailable")),
    )
    fm = FleetManagerService(
        bus=EventBus(), store=MagicMock(), audit=MagicMock(), tools=[],
    )

    with pytest.raises(RuntimeError, match="GitHub credentials unavailable"):
        await fm.start()

    assert not fm._started
    assert fm._tick_task is None


@pytest.mark.parametrize("result", ["denied", SimpleNamespace(content="denied")])
def test_tool_result_evidence_accepts_both_provider_shapes(result):
    events = []
    fm = FleetManagerService(
        bus=EventBus(), store=MagicMock(), audit=MagicMock(), on_live=events.append,
    )

    fm._on_session_event(SimpleNamespace(
        type=SessionEventType.TOOL_EXECUTION_COMPLETE,
        data=SimpleNamespace(tool_call_id="call-1", success=False, result=result),
    ))

    assert events[-1]["data"]["result"] == "denied"
    assert events[-1]["data"]["success"] is False


@pytest.mark.asyncio
async def test_runtime_failure_emits_error_not_reasoning_done():
    events = []
    fm = FleetManagerService(
        bus=EventBus(), store=MagicMock(), audit=MagicMock(), on_live=events.append,
    )
    fm._runtime = SimpleNamespace(
        run_session=AsyncMock(side_effect=RuntimeError("Model gateway unavailable")),
    )

    await fm._process_batch([QueueEntry(reason="fleet.tick")])

    assert [event["kind"] for event in events] == ["reasoning_start", "error"]
    assert events[-1]["data"]["message"] == "Model gateway unavailable"
