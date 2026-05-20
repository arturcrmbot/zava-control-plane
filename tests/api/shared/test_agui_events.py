from api.shared.agui_events import (
    RunStarted, RunFinished, RunError, RunInterrupted,
    StepStarted, StepFinished,
    TextMessageStart, TextMessageContent, TextMessageEnd,
    ToolCallStart, ToolCallArgs, ToolCallEnd,
    StateDelta, CustomEvent,
    to_sse_dict,
)


def test_run_started_serialises_to_agui_shape():
    ev = RunStarted(run_id="hiring-123", thread_id="hiring-123")
    out = to_sse_dict(ev)
    assert out == {
        "type": "RUN_STARTED",
        "runId": "hiring-123",
        "threadId": "hiring-123",
    }


def test_tool_call_start_includes_parent_message_id():
    ev = ToolCallStart(
        tool_call_id="tc-1",
        tool_call_name="policy_search",
        parent_message_id="msg-1",
    )
    out = to_sse_dict(ev)
    assert out["type"] == "TOOL_CALL_START"
    assert out["toolCallId"] == "tc-1"
    assert out["toolCallName"] == "policy_search"
    assert out["parentMessageId"] == "msg-1"


def test_state_delta_is_json_patch_array():
    ev = StateDelta(delta=[{"op": "add", "path": "/entities/person/p1",
                            "value": {"name": "Ada"}}])
    out = to_sse_dict(ev)
    assert out["type"] == "STATE_DELTA"
    assert out["delta"][0]["op"] == "add"


def test_custom_event_carries_name_and_value():
    ev = CustomEvent(name="validator.blocked",
                     value={"reason": "missing_signoff"})
    out = to_sse_dict(ev)
    assert out == {
        "type": "CUSTOM",
        "name": "validator.blocked",
        "value": {"reason": "missing_signoff"},
    }
