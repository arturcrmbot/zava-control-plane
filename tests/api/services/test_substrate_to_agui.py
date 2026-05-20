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


def test_tool_invocation_via_executor_emits_tool_call_lifecycle():
    tr = SubstrateToAGUI(run_id="hiring-1")
    start = tr.translate(_ev("durable.executor.invoked",
                             workflow_id="hiring-1",
                             tool="policy_search",
                             args={"q": "hiring policy"}))
    start_kinds = [e.__class__.__name__ for e in start]
    assert start_kinds == ["ToolCallStart", "ToolCallArgs"]


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
