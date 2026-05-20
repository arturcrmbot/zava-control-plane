from __future__ import annotations

from api.server.services.lessons.working_memory_capture import WorkingMemoryCapture
from api.server.services.lessons.working_memory_store import InMemoryWorkingMemoryStore


def test_agent_completed_event_produces_decision_note() -> None:
    store = InMemoryWorkingMemoryStore()
    capture = WorkingMemoryCapture(store=store)

    capture.on_agent_completed(
        workflow_id="WF-1",
        agent_skill="interview-recommender",
        response_text='{"decision": "advance", "rationale": "level signal strong"}',
        tool_calls=[],
    )

    notes = store.list_for_workflow(workflow_id="WF-1")
    assert len(notes) == 1
    assert notes[0].kind == "decision"
    assert "advance" in notes[0].body


def test_tool_call_event_produces_tool_note() -> None:
    store = InMemoryWorkingMemoryStore()
    capture = WorkingMemoryCapture(store=store)

    capture.on_agent_completed(
        workflow_id="WF-1",
        agent_skill="interview-recommender",
        response_text="{}",
        tool_calls=[
            {"tool": "greenhouse_get_candidate", "args": {"id": "C-001"}, "latency_ms": 120},
        ],
    )

    notes = store.list_for_workflow(workflow_id="WF-1")
    tool_notes = [n for n in notes if n.kind == "tool_call"]
    assert len(tool_notes) == 1
    assert "greenhouse_get_candidate" in tool_notes[0].body


def test_capture_ignores_workflow_id_none() -> None:
    store = InMemoryWorkingMemoryStore()
    capture = WorkingMemoryCapture(store=store)

    capture.on_agent_completed(
        workflow_id=None,
        agent_skill="x",
        response_text="{}",
        tool_calls=[],
    )

    assert store.list_for_workflow(workflow_id="WF-anything") == []


def test_non_json_response_truncates_to_240_chars() -> None:
    store = InMemoryWorkingMemoryStore()
    capture = WorkingMemoryCapture(store=store)

    long = "x" * 500
    capture.on_agent_completed(
        workflow_id="WF-1",
        agent_skill="x",
        response_text=long,
        tool_calls=[],
    )

    notes = store.list_for_workflow(workflow_id="WF-1")
    assert len(notes[0].body) == 240


def test_default_capture_singleton_is_reused() -> None:
    from api.server.services.lessons.working_memory_capture import (
        _reset_default_for_tests,
        get_default_capture,
    )

    _reset_default_for_tests()
    a = get_default_capture()
    b = get_default_capture()
    assert a is b


def test_set_default_capture_swaps_singleton() -> None:
    from api.server.services.lessons.working_memory_capture import (
        _reset_default_for_tests,
        get_default_capture,
        set_default_capture,
    )

    _reset_default_for_tests()
    custom = WorkingMemoryCapture(store=InMemoryWorkingMemoryStore())
    set_default_capture(custom)
    assert get_default_capture() is custom
    _reset_default_for_tests()


def test_tool_call_note_uses_tool_key_and_enriches_with_args_and_result():
    """Producer in _wrapper.py emits dicts with both 'name' and 'tool' keys
    (legacy + capture-consumer contracts). Capture must surface the tool
    name, args summary, and result summary in the note body so a proposer
    can learn from it."""
    store = InMemoryWorkingMemoryStore()
    capture = WorkingMemoryCapture(store=store)
    capture.on_agent_completed(
        workflow_id="WF-1",
        agent_skill="receipt-validator",
        response_text='{"decision":"approve","rationale":"matched receipt to claim"}',
        tool_calls=[
            {
                "name": "fetch_receipt",
                "tool": "fetch_receipt",
                "args": {"claim_id": "C-001"},
                "result": {"vendor": "Acme", "total_gbp": 42.5},
                "success": True,
                "latency_ms": 87,
            }
        ],
    )
    notes = list(store._by_id.values())
    tc_note = next(n for n in notes if n.kind == "tool_call")
    assert "fetch_receipt" in tc_note.body
    assert "C-001" in tc_note.body
    assert "Acme" in tc_note.body
    assert "87ms" in tc_note.body


def test_tool_call_note_handles_missing_args_and_result_gracefully():
    """A tool call with no args/result still produces a useful header."""
    store = InMemoryWorkingMemoryStore()
    capture = WorkingMemoryCapture(store=store)
    capture.on_agent_completed(
        workflow_id="WF-1",
        agent_skill="anomaly-flagger",
        response_text="ok",
        tool_calls=[{"name": "ping", "tool": "ping", "latency_ms": 3}],
    )
    notes = list(store._by_id.values())
    tc_note = next(n for n in notes if n.kind == "tool_call")
    assert "called ping" in tc_note.body
    assert "3ms" in tc_note.body
    assert "args:" not in tc_note.body
    assert "result:" not in tc_note.body


def test_long_tool_args_are_truncated_with_marker():
    store = InMemoryWorkingMemoryStore()
    capture = WorkingMemoryCapture(store=store)
    big = "x" * 1000
    capture.on_agent_completed(
        workflow_id="WF-1",
        agent_skill="anomaly-flagger",
        response_text="ok",
        tool_calls=[{"name": "huge", "tool": "huge", "args": big, "latency_ms": 1}],
    )
    notes = list(store._by_id.values())
    tc_note = next(n for n in notes if n.kind == "tool_call")
    assert "x" in tc_note.body
    assert "…" in tc_note.body
