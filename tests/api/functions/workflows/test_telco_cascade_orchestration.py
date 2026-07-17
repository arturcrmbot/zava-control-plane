from __future__ import annotations

from datetime import datetime
from typing import Any

from api.functions.workflows.telco_cascade import telco_cascade_orchestration


class _Task:
    def __init__(self, result=None):
        self.result = result

    def cancel(self):
        return None


class _Context:
    instance_id = "cascade-instance-1"
    current_utc_datetime = datetime(2026, 1, 1)

    def __init__(
        self,
        workflow_type: str,
        decision: dict,
        approval: dict | None = None,
    ):
        self._input = {
            "workflow_id": "WF-CASCADE-001",
            "type": workflow_type,
            "trace_id": f"trace-{workflow_type}",
            "observation": {"example": True},
            "agent_mode": "deterministic",
        }
        self.activity_decision = decision
        self.approval = _Task(approval)
        self.timer = _Task()
        self.calls: list[tuple[str, dict]] = []
        self.external_event: str | None = None

    def get_input(self):
        return self._input

    def call_activity(self, name, payload):
        self.calls.append((name, payload))
        if name == "telco_cascade_decision_activity_trigger":
            return self.activity_decision
        return {}

    def wait_for_external_event(self, name):
        self.external_event = name
        return self.approval

    def create_timer(self, _deadline):
        return self.timer

    def task_any(self, _tasks):
        return self.approval


def _drive(context: _Context, workflow_type: str) -> dict:
    generator = telco_cascade_orchestration(context, workflow_type)
    sent: Any = None
    while True:
        try:
            yielded = generator.send(sent) if sent is not None else next(generator)
        except StopIteration as stop:
            return stop.value
        sent = yielded


def _decision(*, requires_approval: bool) -> dict:
    return {
        "command": {
            "type": "create_maintenance_work_order",
            "payload": {"asset_id": "AST-SITE-04-radio-unit"},
        },
        "requires_approval": requires_approval,
        "approval_context": {
            "action": "delivery_lead_decision",
            "request": {"amount": 12_000.0},
        },
        "reasoning": "evidence-backed decision",
    }


def test_cascade_orchestration_returns_decision_without_terminal_checkpoint():
    context = _Context(
        "outage-risk-management",
        _decision(requires_approval=False),
    )

    result = _drive(context, "outage-risk-management")

    assert result["status"] == "decision_ready"
    assert result["command"]["payload"]["approval_decision"] == "not_required"
    checkpoint_kinds = [
        payload["kind"]
        for name, payload in context.calls
        if name == "checkpoint_activity_trigger"
    ]
    assert checkpoint_kinds[0] == "workflow.started"
    assert "workflow.completed" not in checkpoint_kinds
    assert context.external_event is None


def test_cascade_orchestration_waits_for_registered_approver():
    context = _Context(
        "predictive-site-maintenance",
        _decision(requires_approval=True),
        approval={"decision": "approve", "persona": "delivery_lead"},
    )

    result = _drive(context, "predictive-site-maintenance")

    assert context.external_event == "delivery_lead_decision"
    assert result["command"]["payload"]["approval_decision"] == "approve"
    suspended = next(
        payload["payload"]
        for name, payload in context.calls
        if name == "checkpoint_activity_trigger"
        and payload["kind"] == "suspended"
    )
    assert suspended["persona"] == "delivery_lead"
    assert suspended["context"]["request"]["amount"] == 12_000.0


def test_cascade_orchestration_stops_when_approval_is_denied():
    context = _Context(
        "predictive-site-maintenance",
        _decision(requires_approval=True),
        approval={"decision": "deny", "persona": "delivery_lead"},
    )

    result = _drive(context, "predictive-site-maintenance")

    assert result["status"] == "denied"
    assert result["command"] is None
