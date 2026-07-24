from api.shared.events import FleetEvent
from api.server.services.substrate_to_agui import SubstrateToAGUI


def _ev(type_: str, **fields) -> FleetEvent:
    return FleetEvent(type=type_, ts=0.0, **fields)


def test_workflow_started_emits_run_started():
    tr = SubstrateToAGUI(run_id="hiring-1")
    out = tr.translate(_ev("durable.workflow.started",
                           workflow_id="hiring-1",
                           workflow_type="hiring"))
    assert [e.__class__.__name__ for e in out] == ["RunStarted"]
    assert out[0].run_id == "hiring-1"


def test_legacy_lifecycle_aliases_still_work_without_canonical_events():
    tr = SubstrateToAGUI(run_id="hiring-legacy")

    started = tr.translate(_ev(
        "workflow.started",
        workflow_id="hiring-legacy",
    ))
    finished = tr.translate(_ev(
        "workflow.resolved",
        workflow_id="hiring-legacy",
        resolution="completed",
    ))

    assert [event.__class__.__name__ for event in started] == ["RunStarted"]
    assert [event.__class__.__name__ for event in finished] == ["RunFinished"]


def test_executor_agent_invocation_opens_a_text_message():
    tr = SubstrateToAGUI(run_id="hiring-1")
    out = tr.translate(_ev("durable.executor.invoked",
                           workflow_id="hiring-1",
                           skill="screener"))
    kinds = [e.__class__.__name__ for e in out]
    assert "TextMessageStart" in kinds
    assert tr.open_message_id("screener") is not None


def test_agent_completed_closes_the_text_message_with_content():
    tr = SubstrateToAGUI(run_id="hiring-1")
    tr.translate(_ev("durable.executor.invoked",
                     workflow_id="hiring-1",
                     skill="screener"))
    out = tr.translate(_ev("agent.completed",
                           workflow_id="hiring-1",
                           skill="screener",
                           output="Candidate is a strong match."))
    kinds = [e.__class__.__name__ for e in out]
    assert kinds == ["TextMessageContent", "TextMessageEnd"]
    assert out[0].delta == "Candidate is a strong match."


def test_production_agent_completed_emits_a_complete_text_message():
    tr = SubstrateToAGUI(run_id="hiring-1")

    out = tr.translate(_ev(
        "agent.completed",
        workflow_id="hiring-1",
        agent_label="rag-classifier",
        agent_run_id="ar-production-1",
        response_text='{"verdict":"red"}',
    ))

    assert [event.__class__.__name__ for event in out] == [
        "TextMessageStart",
        "TextMessageContent",
        "TextMessageEnd",
    ]
    assert {event.message_id for event in out} == {"ar-production-1"}
    assert out[1].delta == '{"verdict":"red"}'


def test_agent_completion_correlates_a_single_open_executor_alias():
    tr = SubstrateToAGUI(run_id="hiring-1")
    tr.translate(_ev(
        "durable.executor.invoked",
        workflow_id="hiring-1",
        stage="start",
        skill="notification",
    ))

    out = tr.translate(_ev(
        "agent.completed",
        workflow_id="hiring-1",
        agent_label="notification-composer",
        response_text='{"channel":"email"}',
    ))

    assert [event.__class__.__name__ for event in out] == [
        "TextMessageContent",
        "TextMessageEnd",
    ]
    assert tr.open_message_id("notification") is None


def test_agent_executor_error_closes_its_open_message():
    tr = SubstrateToAGUI(run_id="hiring-1")
    tr.translate(_ev(
        "durable.executor.invoked",
        workflow_id="hiring-1",
        stage="start",
        skill="risk-reviewer",
    ))

    out = tr.translate(_ev(
        "durable.executor.invoked",
        workflow_id="hiring-1",
        stage="error",
        skill="risk-reviewer",
    ))

    assert [event.__class__.__name__ for event in out] == ["TextMessageEnd"]
    assert tr.open_message_id("risk-reviewer") is None


def test_tool_invocation_via_executor_emits_tool_call_lifecycle():
    tr = SubstrateToAGUI(run_id="hiring-1")
    start = tr.translate(_ev("durable.executor.invoked",
                             workflow_id="hiring-1",
                             tool="policy_search",
                             args={"q": "hiring policy"}))
    start_kinds = [e.__class__.__name__ for e in start]
    assert start_kinds == ["ToolCallStart", "ToolCallArgs"]


def test_wrapper_tool_start_and_completion_emit_one_correlated_lifecycle():
    tr = SubstrateToAGUI(run_id="hiring-1")

    start = tr.translate(_ev(
        "durable.executor.invoked",
        workflow_id="hiring-1",
        executor_type="tool",
        stage="start",
        skill="screener",
        tool="policy_search",
        tool_call_id="call-7",
        args={"q": "hiring policy"},
    ))
    complete = tr.translate(_ev(
        "durable.executor.invoked",
        workflow_id="hiring-1",
        executor_type="tool",
        stage="complete",
        skill="screener",
        tool="policy_search",
        tool_call_id="call-7",
        result={"matches": ["POL-1"]},
        success=True,
    ))

    assert [e.__class__.__name__ for e in start] == [
        "ToolCallStart",
        "ToolCallArgs",
    ]
    assert start[0].tool_call_id == "call-7"
    assert [e.__class__.__name__ for e in complete] == ["ToolCallEnd"]
    assert complete[0].tool_call_id == "call-7"


def test_wrapper_tool_start_and_completion_accept_camel_case_tool_call_id():
    tr = SubstrateToAGUI(run_id="hiring-1")

    start = tr.translate(_ev(
        "durable.executor.invoked",
        workflow_id="hiring-1",
        executor_type="tool",
        stage="start",
        skill="screener",
        tool="policy_search",
        toolCallId="call-8",
        args={"q": "hiring policy"},
    ))
    complete = tr.translate(_ev(
        "durable.executor.invoked",
        workflow_id="hiring-1",
        executor_type="tool",
        stage="complete",
        skill="screener",
        tool="policy_search",
        toolCallId="call-8",
        result={"matches": ["POL-1"]},
        success=True,
    ))

    assert [e.__class__.__name__ for e in start] == [
        "ToolCallStart",
        "ToolCallArgs",
    ]
    assert start[0].tool_call_id == "call-8"
    assert [e.__class__.__name__ for e in complete] == ["ToolCallEnd"]
    assert complete[0].tool_call_id == "call-8"


def test_completed_agent_executor_does_not_open_a_duplicate_message():
    tr = SubstrateToAGUI(run_id="hiring-1")

    tr.translate(_ev(
        "durable.executor.invoked",
        workflow_id="hiring-1",
        executor_type="agent",
        stage="start",
        skill="screener",
    ))
    complete = tr.translate(_ev(
        "durable.executor.invoked",
        workflow_id="hiring-1",
        executor_type="agent",
        stage="complete",
        skill="screener",
    ))

    assert complete == []


def test_hitl_requested_emits_run_interrupted():
    tr = SubstrateToAGUI(run_id="hiring-1")
    out = tr.translate(_ev("workflow.hitl.requested",
                           workflow_id="hiring-1",
                           persona="hiring_manager",
                           reason="awaiting_offer_approval"))
    assert [e.__class__.__name__ for e in out] == ["RunInterrupted"]
    assert out[0].reason == "awaiting_offer_approval"
    assert out[0].persona == "hiring_manager"


def test_entity_upserted_emits_state_delta_json_patch():
    tr = SubstrateToAGUI(run_id="hiring-1")
    out = tr.translate(_ev("entity.upserted",
                           workflow_id="hiring-1",
                           entity_id="cand-7",
                           entity_kind="person",
                           fields={"name": "Ada"}))
    assert len(out) == 1
    delta = out[0]
    assert delta.__class__.__name__ == "StateDelta"
    op = delta.delta[0]
    assert op["op"] == "add"
    assert op["path"] == "/entities/person/cand-7"
    assert op["value"] == {"name": "Ada"}


def test_event_for_other_workflow_id_is_ignored():
    tr = SubstrateToAGUI(run_id="hiring-1")
    out = tr.translate(_ev("durable.workflow.started",
                           workflow_id="other-run",
                           workflow_type="hiring"))
    assert out == []


def test_workflow_completed_emits_run_finished():
    tr = SubstrateToAGUI(run_id="hiring-1")
    out = tr.translate(_ev("durable.workflow.completed",
                           workflow_id="hiring-1"))
    assert [e.__class__.__name__ for e in out] == ["RunFinished"]


def test_workflow_failed_emits_run_error():
    tr = SubstrateToAGUI(run_id="hiring-1")
    out = tr.translate(_ev("workflow.failed",
                           workflow_id="hiring-1",
                           reason="upstream_timeout"))
    assert [e.__class__.__name__ for e in out] == ["RunError"]
    assert out[0].message == "upstream_timeout"


def test_validator_blocked_emits_custom_event():
    tr = SubstrateToAGUI(run_id="hiring-1")
    out = tr.translate(_ev("durable.validator.blocked",
                           workflow_id="hiring-1",
                           reason="missing_signoff"))
    assert [e.__class__.__name__ for e in out] == ["CustomEvent"]
    assert out[0].name == "validator.blocked"
    assert out[0].value == {"reason": "missing_signoff"}


def test_validator_exception_sequence_remains_recoverable_until_completion():
    tr = SubstrateToAGUI(run_id="hiring-recoverable")

    exception = tr.translate(_ev(
        "workflow.exception.detected",
        workflow_id="hiring-recoverable",
        category="validator-blocked",
        severity="high",
        reason="missing_signoff",
    ))
    blocked = tr.translate(_ev(
        "durable.validator.blocked",
        workflow_id="hiring-recoverable",
        name="validate_signoff",
        reason="missing_signoff",
    ))
    completed = tr.translate(_ev(
        "durable.workflow.completed",
        workflow_id="hiring-recoverable",
    ))

    assert [event.__class__.__name__ for event in [
        *exception,
        *blocked,
        *completed,
    ]] == ["CustomEvent", "CustomEvent", "RunFinished"]
    assert exception[0].name == "workflow.exception.detected"
    assert exception[0].value == {
        "category": "validator-blocked",
        "severity": "high",
        "reason": "missing_signoff",
    }
