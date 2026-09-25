"""A persona at the top of the chain can send a case back to the agent, once."""
from __future__ import annotations

from datetime import datetime, timezone

from verticals.banking import fraud_durable, supporting_durable
from verticals.banking.fraud_constraints import OPTION_REIMBURSE_FULL

VERSIONS = {"SYN-CLAIM-0032": 2}
FEEDBACK = "The agent's reasoning says there is no vulnerability marker, but the record shows one."


class _Task:
    def __init__(self, result=None) -> None:
        self.result = result

    def cancel(self) -> None:
        pass


class _Context:
    instance_id = "inst-send-back"
    current_utc_datetime = datetime(2026, 9, 25, tzinfo=timezone.utc)

    def __init__(self, input_: dict, results: dict, approvals: list[dict]) -> None:
        self._input = input_
        self.results = {name: list(values) for name, values in results.items()}
        self.approvals = list(approvals)
        self.activities: list[tuple[str, dict]] = []

    def get_input(self) -> dict:
        return self._input

    def call_activity(self, name: str, payload: dict):
        self.activities.append((name, payload))
        queue = self.results.get(name)
        return ("result", queue.pop(0) if queue else None)

    def call_activity_with_retry(self, name: str, retry, payload: dict):
        return self.call_activity(name, payload)

    def wait_for_external_event(self, name: str) -> _Task:
        return _Task(self.approvals.pop(0))

    def create_timer(self, when) -> _Task:
        return _Task()

    def task_any(self, tasks: list):
        return ("any", tasks)

    def payloads(self, name: str) -> list[dict]:
        return [payload for activity, payload in self.activities if activity == name]

    def gates(self) -> list[dict]:
        return [p["payload"] for p in self.payloads("checkpoint_activity_trigger") if p["kind"] == "suspended"]


def _drive(orchestration) -> dict:
    sent = None
    try:
        while True:
            kind, value = orchestration.send(sent)
            sent = value if kind == "result" else value[0]
    except StopIteration as stop:
        return stop.value


def _fraud_approval(decision: str = "approve", **extra) -> dict:
    return {"decision": decision, "persona": "fraud_decision_manager", "decision_id": "SYN-APP-DECISION-001",
            "selected_option_id": OPTION_REIMBURSE_FULL, "evidence_versions": VERSIONS, **extra}


SEND_BACK = _fraud_approval("send_back", decided_by="llm", feedback=FEEDBACK)
WITHIN = {"allowed": True, "reason": "approver", "governing_rule_id": "AUTH-fraud_decision_manager-x"}


def _fraud_results(rounds: int) -> dict:
    ranking = {"ranked_option_ids": [OPTION_REIMBURSE_FULL], "reasoning": "Reimburse in full."}
    return {
        "fraud_evidence_activity_trigger": [{
            "story_id": "SYN-STORY-APP-002", "claim_id": "SYN-CLAIM-0032",
            "evidence_versions": VERSIONS, "observation": {"claim": {"id": "SYN-CLAIM-0032"}},
        }],
        "fraud_trace_activity_trigger": [{
            "admitted_options": [{"option_id": OPTION_REIMBURSE_FULL, "value_gbp": 6_750.0}],
            "rejected_options": [], "beneficiary_path": {},
        }],
        "fraud_agent_activity_trigger": [ranking] * rounds,
        "fraud_governance_activity_trigger": [WITHIN] * rounds,
        "fraud_command_activity_trigger": [{"status": "decision_ready", "command": {"type": "x"}}],
    }


def test_a_send_back_has_the_agent_reassess_with_the_reviewers_reasons() -> None:
    context = _Context({"workflow_id": "BAPP-sb"}, _fraud_results(2), [SEND_BACK, _fraud_approval()])
    output = _drive(fraud_durable.fraud_orchestration(context))
    agent_calls = context.payloads("fraud_agent_activity_trigger")
    assert len(agent_calls) == 2
    assert "reviewer_feedback" not in agent_calls[0]
    assert agent_calls[1]["reviewer_feedback"] == FEEDBACK
    first, second = context.gates()
    assert "reassessment_round" not in first["hitl_context"]
    assert second["hitl_context"]["reassessment_round"] == 1
    assert output["status"] == "decision_ready"


def test_a_second_send_back_ends_the_case_instead_of_looping() -> None:
    context = _Context({"workflow_id": "BAPP-sb2"}, _fraud_results(2), [SEND_BACK, SEND_BACK])
    output = _drive(fraud_durable.fraud_orchestration(context))
    assert output["status"] == "denied"
    assert len(context.payloads("fraud_agent_activity_trigger")) == 2
    assert context.payloads("fraud_command_activity_trigger") == []


def test_the_agent_prompt_carries_the_reviewers_reasons() -> None:
    payload = {
        "workflow_id": "BAPP-sb", "instance_id": "i", "reviewer_feedback": FEEDBACK,
        "evidence": {"story_id": "S", "actor_ids": ["a"], "event_ids": ["e"], "evidence_versions": {"a": 1},
                     "observation": {}},
        "admitted_options": [{"option_id": OPTION_REIMBURSE_FULL}],
    }
    prompt = fraud_durable._agent_prompt(payload)
    assert f"A reviewer sent your last assessment back: {FEEDBACK}" in prompt
    assert "A reviewer sent" not in fraud_durable._agent_prompt({**payload, "reviewer_feedback": None})


def test_a_mule_case_can_be_sent_back_once() -> None:
    profile = supporting_durable.MULE_PROFILE
    evidence = {
        "story_id": "SYN-MULE-CASE-1", "case_id": "SYN-MULE-CASE-1", "evidence_versions": {"SYN-MULE-CASE-1": 1},
        "actor_ids": ["SYN-MULE-CASE-1"], "event_ids": ["seed"], "observation": {"case": {"id": "SYN-MULE-CASE-1"}},
        "admitted_options": [{"option_id": "SYN-MULE-OPTION-MONITOR", "value_gbp": 5_000.0}],
        "rejected_options": [],
    }
    approval = {"decision": "approve", "persona": profile.hitl_persona, "decision_id": "d",
                "selected_option_id": "SYN-MULE-OPTION-MONITOR", "evidence_versions": {"SYN-MULE-CASE-1": 1}}
    send_back = {**approval, "decision": "send_back", "decided_by": "llm", "feedback": "Weigh the linked claims."}
    ranking = {"ranked_option_ids": ["SYN-MULE-OPTION-MONITOR"], "reasoning": "Monitor."}
    context = _Context(
        {"workflow_id": "BMUL-sb", "type": profile.workflow_type},
        {"case_evidence_activity_trigger": [evidence],
         "case_agent_activity_trigger": [ranking, ranking],
         "case_governance_activity_trigger": [{"allowed": True}, {"allowed": True}],
         "case_command_activity_trigger": [{"status": "decision_ready", "command": {}}]},
        [send_back, approval],
    )
    output = _drive(supporting_durable.case_orchestration(profile, context))
    agent_calls = context.payloads("case_agent_activity_trigger")
    assert [call.get("reviewer_feedback") for call in agent_calls] == [None, "Weigh the linked claims."]
    assert context.gates()[1]["hitl_context"]["reassessment_round"] == 1
    assert output["status"] == "decision_ready"


def test_the_case_agent_prompt_carries_the_reviewers_reasons() -> None:
    evidence = {"story_id": "S", "actor_ids": ["a"], "event_ids": ["e"], "evidence_versions": {"a": 1},
                "observation": {}, "admitted_options": []}
    prompt = supporting_durable._agent_prompt(
        supporting_durable.MULE_PROFILE, evidence, {"workflow_id": "BMUL-sb", "reviewer_feedback": "Weigh the claims."})
    assert "A reviewer sent your last assessment back: Weigh the claims." in prompt
