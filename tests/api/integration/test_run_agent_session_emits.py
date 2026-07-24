"""Verify run_agent_session emits exactly one agent.completed event with the
correct payload after a session returns.

We patch the GHCP SDK's CopilotClient with a fake that returns a canned
response, capture FleetEvent emissions via app_state.bus, and assert the
shape.
"""
from __future__ import annotations
import pytest

from api.functions.graphs.executors.agents.runtime import LLMRuntimeResult


class _FakeRuntime:
    def __init__(self, response_text: str):
        self._response_text = response_text

    async def run_session(self, **_):
        return LLMRuntimeResult(
            text=self._response_text,
            tool_calls=[],
            input_tokens=10,
            output_tokens=5,
        )


@pytest.mark.asyncio
async def test_run_agent_session_emits_agent_completed_via_webhook(monkeypatch):
    """run_agent_session must POST agent.completed to the FastAPI webhook
    so the online_subscriber (in the FastAPI process) sees it."""
    captured: list[dict] = []

    async def fake_webhook_emit(workflow_id, instance_id, kind, payload):
        captured.append({"workflow_id": workflow_id, "instance_id": instance_id,
                         "kind": kind, "payload": payload})

    import api.functions.webhook as webhook_mod
    monkeypatch.setattr(webhook_mod, "emit", fake_webhook_emit)

    from api.functions.graphs.executors.agents import _wrapper
    monkeypatch.setattr(_wrapper, "_get_runtime", lambda: _FakeRuntime('{"verdict": "Red"}'))

    parsed = await _wrapper.run_agent_session(
        prompt="classify CLM-001",
        tools=[],
        skill_dir=None,
        skill_label="rag-classifier",
        workflow_id="wf-abc",
    )

    assert parsed == {"verdict": "Red"}
    assert len(captured) == 1
    call = captured[0]
    assert call["kind"] == "agent.completed"
    assert call["workflow_id"] == "wf-abc"
    p = call["payload"]
    assert p["agent_label"] == "rag-classifier"
    assert p["prompt"] == "classify CLM-001"
    assert p["response_text"] == '{"verdict": "Red"}'
    assert p["extracted_json"] == {"verdict": "Red"}
    assert isinstance(p["tool_calls"], list)
    assert p["usage"]["input_tokens"] == 10
    assert p["usage"]["output_tokens"] == 5
    assert p["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_webhook_emit_failure_does_not_propagate(monkeypatch):
    """If the webhook raises, run_agent_session must still return cleanly."""
    async def boom(*a, **kw):
        raise RuntimeError("webhook is broken")

    import api.functions.webhook as webhook_mod
    monkeypatch.setattr(webhook_mod, "emit", boom)

    from api.functions.graphs.executors.agents import _wrapper
    monkeypatch.setattr(_wrapper, "_get_runtime", lambda: _FakeRuntime('{"verdict": "Red"}'))

    parsed = await _wrapper.run_agent_session(
        prompt="q", tools=[], skill_dir=None, skill_label="x", workflow_id=None,
    )
    assert parsed == {"verdict": "Red"}
