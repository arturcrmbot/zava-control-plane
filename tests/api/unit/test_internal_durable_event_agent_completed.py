"""POST `kind=agent.completed` to /internal/durable-event and assert the
FastAPI bus fires an `agent.completed` FleetEvent. This is the cross-process
bridge: the agent executor (in the Functions host) calls webhook.emit, the
FastAPI server re-emits onto its own bus where online_subscriber is listening.
"""
from __future__ import annotations
from fastapi.testclient import TestClient
from tests.api._helpers.durable_event import signed_post

import api.server.main  # noqa: F401  side-effect: wires bus → SSE topics
from api.server.main import app
from api.server.state import app_state
from api.shared.events import FleetEvent


def _capture_fleet_events() -> tuple[list[FleetEvent], callable]:
    captured: list[FleetEvent] = []
    unsub = app_state.bus.on_any(captured.append)
    return captured, unsub


def test_agent_completed_webhook_re_emits_on_bus():
    captured, unsub = _capture_fleet_events()
    try:
        client = TestClient(app)
        r = signed_post(client, {
            "workflow_id": "wf-99",
            "instance_id": None,
            "kind": "agent.completed",
            "payload": {
                "agent_label": "rag-classifier",
                "agent_run_id": "ar-abc",
                "prompt": "classify CLM-001",
                "response_text": '{"verdict": "red"}',
                "extracted_json": {"verdict": "red"},
                "tool_calls": [],
                "context": "policy chunk",
                "usage": {"input_tokens": 100, "output_tokens": 50},
                "latency_ms": 1234,
            },
        })
        assert r.status_code == 200
    finally:
        unsub()

    re_emitted = [e for e in captured if e.type == "agent.completed"]
    assert len(re_emitted) == 1
    ev = re_emitted[0]
    assert ev.workflow_id == "wf-99"
    # Extra payload fields surface via Pydantic extra="allow"
    assert ev.agent_label == "rag-classifier"
    assert ev.prompt == "classify CLM-001"
    assert ev.latency_ms == 1234
