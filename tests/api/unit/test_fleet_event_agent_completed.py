"""Verify FleetEvent accepts the agent.completed type with extra fields."""
from __future__ import annotations
from api.shared.events import FleetEvent, WAKE_TYPES, wakes_fleet_manager


def test_agent_completed_is_a_valid_event_type():
    ev = FleetEvent(
        type="agent.completed",
        workflow_id="wf-abc",
        agent_label="rag-classifier",
        agent_run_id="ar-123",
        prompt="...",
        response_text="...",
        tool_calls=[],
        usage={"input_tokens": 100, "output_tokens": 50},
        latency_ms=1234,
    )
    assert ev.type == "agent.completed"
    assert ev.workflow_id == "wf-abc"
    # extra="allow" exposes additional fields:
    assert ev.agent_label == "rag-classifier"
    assert ev.latency_ms == 1234


def test_agent_completed_does_not_wake_the_fleet_manager():
    ev = FleetEvent(type="agent.completed", workflow_id="wf-abc")
    assert "agent.completed" not in WAKE_TYPES
    assert wakes_fleet_manager(ev) is False
