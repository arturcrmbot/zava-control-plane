"""Tests for the per-workflow AG-UI SSE drill-in route.

The endpoint is an infinite SSE stream — httpx's ``ASGITransport`` buffers
the entire response before returning, so we drive the ASGI app directly
with a hand-rolled scope/receive/send. Disconnect is signalled to the
generator via ``http.disconnect`` once the expected event has been seen.
"""
from __future__ import annotations

import asyncio
import json

import pytest
from starlette.requests import Request

from api.server.main import app
from api.server.routes import workflow_agui as workflow_agui_route
from api.server.routes.workflow_agui import (
    _history_to_fleet_events,
    _matched_legacy_agent_output_indices,
    workflow_agui_stream,
)
from api.server.services.substrate_to_agui import SubstrateToAGUI
from api.server.state import app_state
from api.shared.agui_events import to_sse_dict
from api.shared.events import FleetEvent


def _scope(run_id: str) -> dict:
    path = f"/api/workflows/{run_id}/agui"
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"test")],
        "client": ("127.0.0.1", 0),
        "server": ("test", 80),
    }


async def _drive_until_terminal(
    run_id: str,
    emitter,
    *,
    terminal_type: str = "RUN_FINISHED",
    timeout: float = 5.0,
) -> list[dict]:
    """Run the ASGI app against a synthetic scope, collect SSE payloads.

    Returns the list of JSON-decoded ``data:`` payloads up to and
    including ``terminal_type``. ``emitter`` is an awaitable that pushes
    bus events into ``app_state.bus`` once the route is subscribed.
    """
    seen: list[dict] = []
    finished = asyncio.Event()
    disconnect = asyncio.Event()

    async def receive():
        await disconnect.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        if message["type"] == "http.response.body":
            body = message.get("body", b"").decode()
            for line in body.splitlines():
                if not line.startswith("data:"):
                    continue
                blob = line[len("data:"):].strip()
                if not blob:
                    continue
                try:
                    payload = json.loads(blob)
                except json.JSONDecodeError:
                    continue
                seen.append(payload)
                if payload.get("type") == terminal_type:
                    finished.set()

    app_task = asyncio.create_task(app(_scope(run_id), receive, send))
    emit_task = asyncio.create_task(emitter())
    try:
        await asyncio.wait_for(finished.wait(), timeout=timeout)
    finally:
        disconnect.set()
        emit_task.cancel()
        try:
            await emit_task
        except BaseException:
            pass
        try:
            await asyncio.wait_for(app_task, timeout=2.0)
        except BaseException:
            app_task.cancel()
            try:
                await app_task
            except BaseException:
                pass
    return seen


@pytest.mark.asyncio
async def test_run_started_and_finished_round_trip():
    async def _emit():
        await asyncio.sleep(0.1)
        app_state.bus.emit(FleetEvent(
            type="durable.workflow.started",
            ts=0.0, workflow_id="hiring-42",
            workflow_type="hiring"))
        app_state.bus.emit(FleetEvent(
            type="durable.workflow.completed",
            ts=0.0, workflow_id="hiring-42"))

    seen = await _drive_until_terminal("hiring-42", _emit)
    types = [e["type"] for e in seen]
    assert types == ["RUN_STARTED", "RUN_FINISHED"]


@pytest.mark.asyncio
async def test_other_run_events_are_filtered_out():
    async def _emit():
        await asyncio.sleep(0.1)
        app_state.bus.emit(FleetEvent(
            type="durable.workflow.started",
            ts=0.0, workflow_id="other-run",
            workflow_type="hiring"))
        app_state.bus.emit(FleetEvent(
            type="durable.workflow.completed",
            ts=0.0, workflow_id="hiring-42"))

    seen = await _drive_until_terminal("hiring-42", _emit)
    types = [e["type"] for e in seen]
    assert "RUN_STARTED" not in types
    assert types == ["RUN_FINISHED"]


@pytest.mark.asyncio
async def test_live_production_agent_completed_emits_closed_message_sequence():
    async def _emit():
        await asyncio.sleep(0.1)
        app_state.bus.emit(FleetEvent(
            type="durable.executor.invoked",
            ts=0.5,
            workflow_id="hiring-live-agent",
            name="agent_rag_classifier",
            executor_type="agent",
            stage="start",
            skill="rag_classifier",
        ))
        app_state.bus.emit(FleetEvent(
            type="agent.completed",
            ts=1.0,
            workflow_id="hiring-live-agent",
            agent_label="rag-classifier",
            agent_run_id="ar-live-1",
            response_text='{"verdict":"red"}',
        ))
        app_state.bus.emit(FleetEvent(
            type="durable.workflow.completed",
            ts=2.0,
            workflow_id="hiring-live-agent",
        ))

    seen = await _drive_until_terminal("hiring-live-agent", _emit)

    assert [event["type"] for event in seen] == [
        "TEXT_MESSAGE_START",
        "TEXT_MESSAGE_CONTENT",
        "TEXT_MESSAGE_END",
        "RUN_FINISHED",
    ]
    assert len({event["messageId"] for event in seen[:3]}) == 1
    assert seen[1]["delta"] == '{"verdict":"red"}'


@pytest.mark.asyncio
async def test_live_lifecycle_aliases_emit_one_canonical_start_and_finish():
    async def _emit():
        await asyncio.sleep(0.1)
        for event_type in (
            "workflow.started",
            "durable.workflow.started",
            "durable.workflow.completed",
            "workflow.resolved",
        ):
            app_state.bus.emit(FleetEvent(
                type=event_type,
                ts=0.0,
                workflow_id="hiring-live-aliases",
            ))

    seen = await _drive_until_terminal("hiring-live-aliases", _emit)

    assert [event["type"] for event in seen] == ["RUN_STARTED", "RUN_FINISHED"]


@pytest.mark.asyncio
async def test_live_rejection_emits_run_error_without_run_finished():
    async def _emit():
        await asyncio.sleep(0.1)
        app_state.bus.emit(FleetEvent(
            type="workflow.resolved",
            ts=0.0,
            workflow_id="hiring-live-rejected",
            resolution="rejected",
        ))
        app_state.bus.emit(FleetEvent(
            type="workflow.failed",
            ts=0.0,
            workflow_id="hiring-live-rejected",
            reason="operator rejected",
        ))

    seen = await _drive_until_terminal(
        "hiring-live-rejected",
        _emit,
        terminal_type="RUN_ERROR",
    )

    assert [event["type"] for event in seen] == ["RUN_ERROR"]
    assert seen[0]["message"] == "workflow rejected"


@pytest.mark.asyncio
async def test_replay_prefers_canonical_agent_completion_and_matches_live():
    replay_run_id = "hiring-replay-canonical-agent"
    live_run_id = "hiring-live-canonical-agent"
    app_state.orchestration_history[replay_run_id] = [
        {
            "kind": "executor.invoked",
            "at": 0.5,
            "payload": {
                "name": "agent_notification",
                "type": "agent",
                "stage": "start",
            },
        },
        {
            "kind": "agent_output",
            "at": 1.0,
            "payload": {
                "agent": "notification_composer",
                "agent_run_id": "canonical-run-1",
                "output": {"verdict": "legacy"},
            },
        },
        {
            "kind": "agent.completed",
            "at": 2.0,
            "payload": {
                "agent_label": "notification-composer",
                "agent_run_id": "canonical-run-1",
                "response_text": '{"verdict":"canonical"}',
            },
        },
        {"kind": "workflow.completed", "at": 3.0, "payload": {}},
    ]

    async def _no_live_events():
        await asyncio.Event().wait()

    async def _emit_live():
        await asyncio.sleep(0.1)
        app_state.bus.emit(FleetEvent(
            type="durable.executor.invoked",
            ts=0.5,
            workflow_id=live_run_id,
            name="agent_notification",
            executor_type="agent",
            stage="start",
            skill="notification",
        ))
        app_state.bus.emit(FleetEvent(
            type="agent.completed",
            ts=2.0,
            workflow_id=live_run_id,
            agent_label="notification-composer",
            agent_run_id="canonical-run-1",
            response_text='{"verdict":"canonical"}',
        ))
        app_state.bus.emit(FleetEvent(
            type="durable.workflow.completed",
            ts=3.0,
            workflow_id=live_run_id,
        ))

    try:
        replay_seen = await _drive_until_terminal(replay_run_id, _no_live_events)
        live_seen = await _drive_until_terminal(live_run_id, _emit_live)
    finally:
        app_state.orchestration_history.pop(replay_run_id, None)

    def _observable(events: list[dict]) -> list[tuple[str, str | None]]:
        return [(event["type"], event.get("delta")) for event in events]

    assert _observable(replay_seen) == _observable(live_seen)
    assert _observable(replay_seen) == [
        ("TEXT_MESSAGE_START", None),
        ("TEXT_MESSAGE_CONTENT", '{"verdict":"canonical"}'),
        ("TEXT_MESSAGE_END", None),
        ("RUN_FINISHED", None),
    ]


def test_agent_output_remains_fallback_when_only_another_agent_completed():
    history = [
        {
            "kind": "agent_output",
            "payload": {
                "agent": "risk_reviewer",
                "output": {"verdict": "legacy-only"},
            },
        },
        {
            "kind": "agent.completed",
            "payload": {
                "agent_label": "policy-checker",
                "response_text": '{"verdict":"canonical"}',
            },
        },
    ]

    events = _history_to_fleet_events(
        "hiring-legacy-fallback",
        history[0],
        suppress_legacy_agent_output=(
            0 in _matched_legacy_agent_output_indices(history)
        ),
    )

    assert len(events) == 1
    assert events[0].type == "agent.completed"
    assert events[0].skill == "risk_reviewer"


def test_agent_output_fallback_uses_nearest_equivalent_not_merely_adjacent():
    history = [
        {
            "kind": "agent_output",
            "payload": {
                "agent": "risk_reviewer",
                "phase": "Review",
                "output": {"verdict": "clear"},
            },
        },
        {
            "kind": "agent_output",
            "payload": {
                "agent": "risk_reviewer",
                "phase": "Review",
                "output": {"verdict": "retry"},
            },
        },
        {
            "kind": "agent.completed",
            "payload": {
                "agent_label": "risk-reviewer",
                "phase": "Review",
                "response_text": '{"verdict":"clear"}',
            },
        },
    ]

    assert _matched_legacy_agent_output_indices(history) == {0}


def test_agent_output_fallback_retains_equidistant_ambiguous_records():
    history = [
        {
            "kind": "agent_output",
            "payload": {
                "agent": "risk_reviewer",
                "output": {"verdict": "clear"},
            },
        },
        {
            "kind": "agent.completed",
            "payload": {
                "agent_label": "risk-reviewer",
                "response_text": '{"verdict":"clear"}',
            },
        },
        {
            "kind": "agent_output",
            "payload": {
                "agent": "risk_reviewer",
                "output": {"verdict": "clear"},
            },
        },
    ]

    assert _matched_legacy_agent_output_indices(history) == set()


def test_agent_output_matching_accepts_legacy_short_stable_ids():
    history = [
        {
            "kind": "agent_output",
            "payload": {
                "agent": "risk_reviewer",
                "agent_run_id": "ar-deadbeef",
                "output": {"verdict": "legacy"},
            },
        },
        {
            "kind": "agent.completed",
            "payload": {
                "agent_label": "risk-reviewer",
                "agent_run_id": "ar-deadbeef",
                "response_text": '{"verdict":"canonical"}',
            },
        },
    ]

    assert _matched_legacy_agent_output_indices(history) == {0}


def test_agent_output_suppression_pairs_only_matching_invocations():
    history = [
        {
            "kind": "agent_output",
            "at": 1.0,
            "payload": {
                "agent": "risk_reviewer",
                "phase": "Review",
                "output": {"verdict": "retry"},
            },
        },
        {
            "kind": "agent_output",
            "at": 2.0,
            "payload": {
                "agent": "risk_reviewer",
                "phase": "Review",
                "agent_run_id": "risk-run-2",
                "output": {"verdict": "clear"},
            },
        },
        {
            "kind": "agent.completed",
            "at": 2.1,
            "payload": {
                "agent_label": "risk-reviewer",
                "phase": "Review",
                "agent_run_id": "risk-run-2",
                "response_text": '{"verdict":"clear"}',
            },
        },
        {
            "kind": "agent_output",
            "at": 3.0,
            "payload": {
                "agent": "policy_checker",
                "phase": "Policy",
                "output": {"verdict": "amber"},
            },
        },
        {
            "kind": "agent.completed",
            "at": 3.1,
            "payload": {
                "agent_label": "policy-checker",
                "phase": "Policy",
                "response_text": '{"verdict":"amber"}',
            },
        },
        {
            "kind": "agent_output",
            "at": 4.0,
            "payload": {
                "agent": "eligibility_checker",
                "phase": "Eligibility",
                "agent_run_id": "eligibility-run-1",
                "output": {"verdict": "red"},
            },
        },
        {
            "kind": "agent.completed",
            "at": 4.1,
            "payload": {
                "agent_label": "eligibility-checker",
                "phase": "Eligibility",
                "agent_run_id": "eligibility-run-2",
                "response_text": '{"verdict":"red"}',
            },
        },
    ]
    suppressed = _matched_legacy_agent_output_indices(history)

    events = [
        event
        for index, entry in enumerate(history)
        for event in _history_to_fleet_events(
            "hiring-mixed-retries",
            entry,
            suppress_legacy_agent_output=index in suppressed,
        )
    ]

    assert [
        event.model_dump().get("output")
        or event.model_dump().get("response_text")
        for event in events
        if event.type == "agent.completed"
    ] == [
        '{"verdict": "retry"}',
        '{"verdict":"clear"}',
        '{"verdict":"amber"}',
        '{"verdict": "red"}',
        '{"verdict":"red"}',
    ]


@pytest.mark.asyncio
async def test_replay_over_400_records_preserves_order_and_completion():
    run_id = "hiring-replay-long-history"
    history = [
        {
            "kind": "step.started",
            "at": float(index),
            "payload": {"step": f"Step {index:03d}"},
        }
        for index in range(401)
    ]
    history.append({
        "kind": "workflow.completed",
        "at": 401.0,
        "payload": {},
    })
    app_state.orchestration_history[run_id] = history
    subscribers_before = len(app_state.bus._any)

    async def _no_live_events():
        await asyncio.Event().wait()

    try:
        seen = await _drive_until_terminal(
            run_id,
            _no_live_events,
            timeout=1.0,
        )
    finally:
        app_state.orchestration_history.pop(run_id, None)

    assert [event["stepName"] for event in seen[:-1]] == [
        f"Step {index:03d}" for index in range(401)
    ]
    assert seen[-1]["type"] == "RUN_FINISHED"
    assert len(app_state.bus._any) == subscribers_before


@pytest.mark.asyncio
async def test_immediate_disconnect_does_not_leak_bus_subscription():
    run_id = "hiring-immediate-disconnect"
    subscribers_before = len(app_state.bus._any)

    async def receive():
        return {"type": "http.disconnect"}

    async def send(_message):
        return None

    await asyncio.wait_for(app(_scope(run_id), receive, send), timeout=1.0)

    assert len(app_state.bus._any) == subscribers_before


@pytest.mark.asyncio
async def test_history_setup_error_does_not_leak_bus_subscription(monkeypatch):
    run_id = "hiring-history-setup-error"
    app_state.orchestration_history[run_id] = [{
        "kind": "workflow.started",
        "at": 1.0,
        "payload": {"workflow_type": "hiring"},
    }]
    subscribers_before = len(app_state.bus._any)

    def _raise_conversion_error(*_args, **_kwargs):
        raise RuntimeError("history conversion failed")

    monkeypatch.setattr(
        workflow_agui_route,
        "_history_to_fleet_events",
        _raise_conversion_error,
    )

    async def _receive():
        await asyncio.Event().wait()

    response = await workflow_agui_stream(
        run_id,
        Request(_scope(run_id), _receive),
    )
    try:
        with pytest.raises(RuntimeError, match="history conversion failed"):
            await anext(response.body_iterator)
    finally:
        app_state.orchestration_history.pop(run_id, None)

    assert len(app_state.bus._any) == subscribers_before


@pytest.mark.asyncio
async def test_live_event_emitted_during_history_setup_is_not_lost(monkeypatch):
    run_id = "hiring-history-subscribe-race"
    app_state.orchestration_history[run_id] = [{
        "kind": "workflow.started",
        "at": 1.0,
        "payload": {"workflow_type": "hiring"},
    }]
    original_converter = workflow_agui_route._history_to_fleet_events
    emitted = False

    def _convert_and_emit(*args, **kwargs):
        nonlocal emitted
        events = original_converter(*args, **kwargs)
        if not emitted:
            emitted = True
            app_state.bus.emit(FleetEvent(
                type="durable.workflow.completed",
                ts=2.0,
                workflow_id=run_id,
                status="completed",
            ))
        return events

    monkeypatch.setattr(
        workflow_agui_route,
        "_history_to_fleet_events",
        _convert_and_emit,
    )

    async def _no_later_events():
        await asyncio.Event().wait()

    try:
        seen = await _drive_until_terminal(
            run_id,
            _no_later_events,
            timeout=0.5,
        )
    finally:
        app_state.orchestration_history.pop(run_id, None)

    assert [event["type"] for event in seen] == [
        "RUN_STARTED",
        "RUN_FINISHED",
    ]


@pytest.mark.asyncio
async def test_history_live_setup_overlap_is_emitted_once(monkeypatch):
    run_id = "hiring-history-live-overlap"
    history = [{
        "kind": "workflow.started",
        "at": 1.0,
        "payload": {"workflow_type": "hiring"},
    }]
    app_state.orchestration_history[run_id] = history
    original_on_any = app_state.bus.on_any
    subscribers_before = len(app_state.bus._any)

    def _subscribe_with_overlapping_completion(handler):
        unsubscribe = original_on_any(handler)
        history.append({
            "kind": "executor.invoked",
            "at": 1.5,
            "payload": {
                "name": "agent_risk_reviewer",
                "type": "agent",
                "stage": "start",
                "phase": "Review",
                "invocation_id": "executor-overlap-1",
            },
        })
        app_state.bus.emit(FleetEvent(
            type="durable.executor.invoked",
            ts=1.5,
            workflow_id=run_id,
            workflow_type="hiring",
            name="agent_risk_reviewer",
            executor_type="agent",
            stage="start",
            phase="Review",
            skill="risk_reviewer",
            invocation_id="executor-overlap-1",
            duration_ms=0,
        ))
        payload = {
            "agent_label": "risk-reviewer",
            "agent_run_id": "ar-overlap-1",
            "response_text": '{"verdict":"amber"}',
        }
        history.append({
            "kind": "agent.completed",
            "at": 2.0,
            "payload": payload,
        })
        app_state.bus.emit(FleetEvent(
            type="agent.completed",
            ts=2.0,
            workflow_id=run_id,
            **payload,
        ))
        return unsubscribe

    monkeypatch.setattr(
        app_state.bus,
        "on_any",
        _subscribe_with_overlapping_completion,
    )

    async def _complete():
        await asyncio.sleep(0.1)
        app_state.bus.emit(FleetEvent(
            type="durable.workflow.completed",
            ts=3.0,
            workflow_id=run_id,
            status="completed",
        ))

    try:
        seen = await _drive_until_terminal(run_id, _complete)
    finally:
        app_state.orchestration_history.pop(run_id, None)

    assert [event["type"] for event in seen] == [
        "RUN_STARTED",
        "TEXT_MESSAGE_START",
        "TEXT_MESSAGE_CONTENT",
        "TEXT_MESSAGE_END",
        "RUN_FINISHED",
    ]
    assert seen[2]["delta"] == '{"verdict":"amber"}'
    assert len(app_state.bus._any) == subscribers_before


@pytest.mark.asyncio
async def test_bus_subscription_is_deferred_until_stream_iteration():
    subscribers_before = list(app_state.bus._any)

    async def receive():
        return {"type": "http.disconnect"}

    try:
        await workflow_agui_stream(
            "hiring-unconsumed-stream",
            Request(_scope("hiring-unconsumed-stream"), receive),
        )
        assert app_state.bus._any == subscribers_before
    finally:
        app_state.bus._any[:] = subscribers_before


def test_failed_history_replays_run_error_without_run_finished():
    events = _history_to_fleet_events(
        "care-failed",
        {
            "kind": "workflow.failed",
            "at": 1.0,
            "payload": {"reason": "approval denied"},
        },
    )
    translator = SubstrateToAGUI("care-failed")

    payloads = [
        to_sse_dict(event)
        for fleet_event in events
        for event in translator.translate(fleet_event)
    ]

    assert [payload["type"] for payload in payloads] == ["RUN_ERROR"]
    assert payloads[0]["message"] == "approval denied"


def test_rejected_history_replays_direct_run_error_without_live_alias():
    events = _history_to_fleet_events(
        "hiring-rejected",
        {
            "kind": "workflow.rejected",
            "at": 1.0,
            "payload": {"reason": "recruiter declined"},
        },
    )
    translator = SubstrateToAGUI("hiring-rejected")

    assert [event.type for event in events] == ["workflow.rejected"]

    payloads = [
        to_sse_dict(event)
        for fleet_event in events
        for event in translator.translate(fleet_event)
    ]

    assert [payload["type"] for payload in payloads] == ["RUN_ERROR"]
    assert payloads[0]["message"] == "recruiter declined"


def test_legacy_resolved_rejection_matches_replay_and_live_translation():
    run_id = "hiring-legacy-resolved-rejection"
    legacy_entry = {
        "kind": "workflow.resolved",
        "at": 1.0,
        "payload": {"resolution": "rejected"},
    }
    replay_events = _history_to_fleet_events(run_id, legacy_entry)
    live_event = FleetEvent(
        type="workflow.resolved",
        ts=1.0,
        workflow_id=run_id,
        resolution="rejected",
    )

    replay_translator = SubstrateToAGUI(run_id)
    live_translator = SubstrateToAGUI(run_id)
    replay_payloads = [
        to_sse_dict(event)
        for fleet_event in replay_events
        for event in replay_translator.translate(fleet_event)
    ]
    live_payloads = [
        to_sse_dict(event)
        for event in live_translator.translate(live_event)
    ]

    assert [event.type for event in replay_events] == ["workflow.resolved"]
    assert replay_payloads == live_payloads
    assert replay_payloads == [{
        "type": "RUN_ERROR",
        "message": "workflow rejected",
    }]
    assert replay_translator.translate(FleetEvent(
        type="workflow.failed",
        ts=2.0,
        workflow_id=run_id,
        reason="canonical rejection",
    )) == []
    assert live_translator.translate(FleetEvent(
        type="workflow.failed",
        ts=2.0,
        workflow_id=run_id,
        reason="canonical rejection",
    )) == []


def test_replayed_validator_exception_can_complete_after_recoverable_evidence():
    history = [
        {
            "kind": "validator.blocked",
            "at": 1.0,
            "payload": {
                "name": "validate_signoff",
                "reason": "missing_signoff",
            },
        },
        {"kind": "workflow.completed", "at": 2.0, "payload": {}},
    ]
    translator = SubstrateToAGUI("hiring-recoverable-replay")

    payloads = [
        to_sse_dict(event)
        for entry in history
        for fleet_event in _history_to_fleet_events(
            "hiring-recoverable-replay",
            entry,
        )
        for event in translator.translate(fleet_event)
    ]

    assert [payload["type"] for payload in payloads] == [
        "CUSTOM",
        "CUSTOM",
        "RUN_FINISHED",
    ]
    assert [payload.get("name") for payload in payloads[:2]] == [
        "workflow.exception.detected",
        "validator.blocked",
    ]


def test_production_agent_completed_history_replays_closed_message_sequence():
    translator = SubstrateToAGUI("hiring-replay-agent")
    history = [
        {
            "kind": "executor.invoked",
            "at": 0.5,
            "instance_id": "instance-replay-1",
            "payload": {
                "name": "agent_rag_classifier",
                "type": "agent",
                "stage": "start",
            },
        },
        {
            "kind": "agent.completed",
            "at": 1.0,
            "instance_id": "instance-replay-1",
            "payload": {
                "agent_label": "rag-classifier",
                "agent_run_id": "ar-replay-1",
                "response_text": '{"verdict":"amber"}',
            },
        },
    ]

    payloads = [
        to_sse_dict(event)
        for entry in history
        for fleet_event in _history_to_fleet_events("hiring-replay-agent", entry)
        for event in translator.translate(fleet_event)
    ]

    assert [payload["type"] for payload in payloads] == [
        "TEXT_MESSAGE_START",
        "TEXT_MESSAGE_CONTENT",
        "TEXT_MESSAGE_END",
    ]
    assert len({payload["messageId"] for payload in payloads}) == 1
    assert payloads[1]["delta"] == '{"verdict":"amber"}'


def test_tool_history_replays_start_args_and_completion():
    translator = SubstrateToAGUI("hiring-42")
    history = [
        {
            "kind": "tool.invoked",
            "at": 1.0,
            "payload": {
                "tool": "policy_search",
                "skill": "screener",
                "stage": "start",
                "tool_call_id": "call-7",
                "agent_run_id": "session-run-7",
                "invocation_id": "executor-parent-7",
                "args": {"q": "hiring policy"},
            },
        },
        {
            "kind": "tool.invoked",
            "at": 2.0,
            "payload": {
                "tool": "policy_search",
                "skill": "screener",
                "stage": "complete",
                "tool_call_id": "call-7",
                "agent_run_id": "session-run-7",
                "invocation_id": "executor-parent-7",
                "result": {"matches": ["POL-1"]},
                "success": True,
            },
        },
    ]

    fleet_events = [
        fleet_event
        for entry in history
        for fleet_event in _history_to_fleet_events("hiring-42", entry)
    ]
    payloads = [
        to_sse_dict(event)
        for fleet_event in fleet_events
        for event in translator.translate(fleet_event)
    ]

    assert {event.agent_run_id for event in fleet_events} == {"session-run-7"}
    assert {event.invocation_id for event in fleet_events} == {
        "executor-parent-7"
    }
    assert [payload["type"] for payload in payloads] == [
        "TOOL_CALL_START",
        "TOOL_CALL_ARGS",
        "TOOL_CALL_END",
    ]
    assert {payload["toolCallId"] for payload in payloads} == {"call-7"}


def test_overlap_key_keeps_tool_calls_distinct_within_one_session():
    first = FleetEvent(
        type="durable.executor.invoked",
        workflow_id="hiring-42",
        executor_type="tool",
        stage="start",
        tool="policy_search",
        tool_call_id="call-1",
        agent_run_id="session-run-7",
        invocation_id="executor-parent-7",
    )
    second = FleetEvent(
        type="durable.executor.invoked",
        workflow_id="hiring-42",
        executor_type="tool",
        stage="start",
        tool="policy_search",
        tool_call_id="call-2",
        agent_run_id="session-run-7",
        invocation_id="executor-parent-7",
    )

    assert workflow_agui_route._event_overlap_key(
        first
    ) != workflow_agui_route._event_overlap_key(second)


def test_overlap_key_keeps_session_runs_distinct_within_one_executor():
    first = FleetEvent(
        type="agent.completed",
        workflow_id="hiring-42",
        agent_label="risk-reviewer",
        agent_run_id="session-run-1",
        invocation_id="executor-parent-7",
    )
    second = FleetEvent(
        type="agent.completed",
        workflow_id="hiring-42",
        agent_label="risk-reviewer",
        agent_run_id="session-run-2",
        invocation_id="executor-parent-7",
    )

    assert workflow_agui_route._event_overlap_key(
        first
    ) != workflow_agui_route._event_overlap_key(second)


def test_tool_history_replays_start_args_and_completion_with_camel_case_tool_call_id():
    translator = SubstrateToAGUI("hiring-42")
    history = [
        {
            "kind": "tool.invoked",
            "at": 1.0,
            "payload": {
                "tool": "policy_search",
                "skill": "screener",
                "stage": "start",
                "toolCallId": "call-7",
                "args": {"q": "hiring policy"},
            },
        },
        {
            "kind": "tool.invoked",
            "at": 2.0,
            "payload": {
                "tool": "policy_search",
                "skill": "screener",
                "stage": "complete",
                "toolCallId": "call-7",
                "result": {"matches": ["POL-1"]},
                "success": True,
            },
        },
    ]

    payloads = [
        to_sse_dict(event)
        for entry in history
        for fleet_event in _history_to_fleet_events("hiring-42", entry)
        for event in translator.translate(fleet_event)
    ]

    assert [payload["type"] for payload in payloads] == [
        "TOOL_CALL_START",
        "TOOL_CALL_ARGS",
        "TOOL_CALL_END",
    ]
    assert {payload["toolCallId"] for payload in payloads} == {"call-7"}


def test_tool_history_mints_an_id_only_when_missing():
    translator = SubstrateToAGUI("hiring-42")
    history = [
        {
            "kind": "tool.invoked",
            "at": 1.0,
            "payload": {
                "tool": "policy_search",
                "skill": "screener",
                "stage": "start",
                "args": {"q": "hiring policy"},
            },
        },
        {
            "kind": "tool.invoked",
            "at": 2.0,
            "payload": {
                "tool": "policy_search",
                "skill": "screener",
                "stage": "complete",
                "result": {"matches": ["POL-1"]},
                "success": True,
            },
        },
    ]

    payloads = [
        to_sse_dict(event)
        for entry in history
        for fleet_event in _history_to_fleet_events("hiring-42", entry)
        for event in translator.translate(fleet_event)
    ]

    tool_call_ids = [payload["toolCallId"] for payload in payloads]
    assert len(set(tool_call_ids)) == 1
    assert tool_call_ids[0].startswith("tc-")
