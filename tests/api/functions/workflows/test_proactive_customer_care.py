from typing import Any

from api.functions.workflows.proactive_customer_care import (
    proactive_customer_care_orchestration,
)
from api.functions.workflows.proactive_customer_care_activities import (
    customer_care_entitlement_activity,
    customer_care_impact_activity,
)


class _Task:
    def __init__(self, result=None):
        self.result = result

    def cancel(self):
        return None


class _Context:
    instance_id = "care-instance-1"
    current_utc_datetime = __import__("datetime").datetime(2026, 1, 1)

    def __init__(self, entitlement, execution, decision=None):
        self._input = {
            "workflow_id": "care-evt-impact",
            "type": "proactive-customer-care",
            "trace_id": "incident-root",
            "observation": {
                "impacted_accounts": [
                    {
                        "id": "ACC-00001",
                        "segment": "priority_business",
                        "vulnerable": False,
                        "approval_required": False,
                    }
                ]
            },
        }
        self.entitlement = entitlement
        self.execution = execution
        self.decision = _Task(decision)
        self.timer = _Task()
        self.calls: list[tuple[str, dict]] = []

    def get_input(self):
        return self._input

    def call_activity(self, name, payload):
        self.calls.append((name, payload))
        if name == "customer_care_impact_activity_trigger":
            return customer_care_impact_activity(payload)
        if name == "customer_care_entitlement_activity_trigger":
            return self.entitlement
        if name == "customer_care_execution_activity_trigger":
            return self.execution
        return {}

    def wait_for_external_event(self, name):
        assert name == "cs_manager_decision"
        return self.decision

    def create_timer(self, _deadline):
        return self.timer

    def task_any(self, tasks):
        return self.decision


def _drive(context):
    generator = proactive_customer_care_orchestration(context)
    sent: Any = None
    while True:
        try:
            yielded = generator.send(sent) if sent is not None else next(generator)
        except StopIteration as stop:
            return stop.value
        sent = yielded


def test_impact_activity_selects_bounded_real_accounts():
    result = customer_care_impact_activity(
        {
            "observation": {
                "impacted_accounts": [
                    {"id": f"ACC-{index:05d}", "segment": "consumer"}
                    for index in range(1, 10)
                ]
            }
        }
    )

    assert len(result["accounts"]) == 3
    assert result["accounts"][0]["id"] == "ACC-00001"


def test_low_credit_path_returns_typed_command_without_hitl():
    command = {
        "command_id": "care-cmd-1",
        "trace_id": "incident-root",
        "issued_by": "customer_care",
        "type": "apply_customer_remediation",
        "payload": {"actions": []},
    }
    context = _Context(
        entitlement={
            "actions": [{"account_id": "ACC-00001", "credit_amount": 5.0}],
            "aggregate_credit": 5.0,
            "requires_approval": False,
        },
        execution={"command": command, "reasoning": "prepared care actions"},
    )

    result = _drive(context)

    assert result["command"] == {
        **command,
        "payload": {
            **command["payload"],
            "approval_decision": "approve",
        },
    }
    assert not any(
        payload.get("kind") == "suspended" for name, payload in context.calls
        if name == "checkpoint_activity_trigger"
    )
    assert not any(
        payload.get("kind") == "workflow.completed" for name, payload in context.calls
        if name == "checkpoint_activity_trigger"
    )
    completed_steps = {
        payload["payload"]["step"]
        for name, payload in context.calls
        if name == "checkpoint_activity_trigger"
        and payload.get("kind") == "step.completed"
    }
    assert completed_steps == {
        "Impact Assessment",
        "Entitlement Decision",
        "Care Execution",
    }


def test_high_credit_path_waits_for_cs_manager_and_threads_decision():
    context = _Context(
        entitlement={
            "actions": [{"account_id": "ACC-00003", "credit_amount": 50.0}],
            "aggregate_credit": 50.0,
            "requires_approval": True,
        },
        execution={"command": {"type": "apply_customer_remediation"}, "reasoning": "approved"},
        decision={"decision": "approve", "persona": "cs_manager"},
    )
    context._input["observation"]["impacted_accounts"][0]["approval_required"] = True

    result = _drive(context)

    suspended = next(
        payload["payload"]
        for name, payload in context.calls
        if name == "checkpoint_activity_trigger" and payload.get("kind") == "suspended"
    )
    assert suspended["persona"] == "cs_manager"
    assert suspended["external_event"] == "cs_manager_decision"
    execution_payload = next(
        payload
        for name, payload in context.calls
        if name == "customer_care_execution_activity_trigger"
    )
    assert execution_payload["approval"]["decision"] == "approve"
    assert result["command"]["payload"]["approval_decision"] == "approve"


def test_agent_cannot_suppress_required_credit_approval():
    context = _Context(
        entitlement={
            "actions": [{"account_id": "ACC-00001", "credit_amount": 50.0}],
            "aggregate_credit": 50.0,
            "requires_approval": False,
        },
        execution={"command": {"type": "apply_customer_remediation"}, "reasoning": "approved"},
        decision={"decision": "approve", "persona": "cs_manager"},
    )
    context._input["observation"]["impacted_accounts"][0]["approval_required"] = True

    _drive(context)

    assert any(
        payload.get("kind") == "suspended"
        for name, payload in context.calls
        if name == "checkpoint_activity_trigger"
    )


def test_denied_credit_approval_returns_without_executing_care():
    context = _Context(
        entitlement={
            "actions": [{"account_id": "ACC-00001", "credit_amount": 50.0}],
            "aggregate_credit": 50.0,
            "requires_approval": True,
        },
        execution={"command": {"type": "apply_customer_remediation"}},
        decision={"decision": "deny", "persona": "cs_manager"},
    )
    context._input["observation"]["impacted_accounts"][0]["approval_required"] = True

    result = _drive(context)

    assert result == {
        "status": "denied",
        "command": None,
        "reasoning": "credit approval denied",
    }
    assert not any(
        name == "customer_care_execution_activity_trigger"
        for name, _ in context.calls
    )


def test_agent_activities_leave_phase_ownership_to_orchestrator(monkeypatch):
    calls = []

    async def run(factory, payload, step, *, emit_boundaries=True):
        calls.append((step, emit_boundaries))
        return {}

    monkeypatch.setattr(
        "api.functions.workflows.proactive_customer_care_activities._run_workflow",
        run,
    )

    customer_care_entitlement_activity({"workflow_id": "care-1"})

    assert calls == [("Entitlement Decision", False)]
