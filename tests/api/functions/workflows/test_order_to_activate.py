from typing import Any

from api.functions.workflows.order_to_activate import order_to_activate_orchestration
from api.functions.workflows.order_to_activate_activities import (
    order_activation_feasibility_activity,
    order_activation_prepare_activity,
)


class _Task:
    def __init__(self, result=None):
        self.result = result

    def cancel(self):
        return None


class _Context:
    instance_id = "order-instance-1"
    current_utc_datetime = __import__("datetime").datetime(2026, 1, 1)

    def __init__(self, utilization=0.5, decision=None):
        self._input = {
            "workflow_id": "order-evt-1",
            "type": "order-to-activate",
            "trace_id": "service-order-ORD-00002",
            "observation": {
                "order": {"id": "ORD-00002", "status": "pending"},
                "requested_site": {
                    "id": "SITE-02",
                    "status": "healthy",
                    "utilization": utilization,
                },
            },
        }
        self.decision = _Task(decision)
        self.timer = _Task()
        self.calls: list[tuple[str, dict]] = []

    def get_input(self):
        return self._input

    def call_activity(self, name, payload):
        self.calls.append((name, payload))
        if name == "order_activation_feasibility_activity_trigger":
            return order_activation_feasibility_activity(payload)
        if name == "order_activation_prepare_activity_trigger":
            return order_activation_prepare_activity(payload)
        return {}

    def wait_for_external_event(self, name):
        assert name == "capacity_manager_decision"
        return self.decision

    def create_timer(self, _deadline):
        return self.timer

    def task_any(self, _tasks):
        return self.decision


def _drive(context):
    generator = order_to_activate_orchestration(context)
    sent: Any = None
    while True:
        try:
            yielded = generator.send(sent) if sent is not None else next(generator)
        except StopIteration as stop:
            return stop.value
        sent = yielded


def test_feasible_order_returns_typed_activation_command_without_hitl():
    context = _Context(utilization=0.5)

    result = _drive(context)

    assert result["command"]["type"] == "activate_service_order"
    assert result["command"]["payload"] == {
        "order_id": "ORD-00002",
        "capacity_approved": False,
    }
    assert not any(
        payload.get("kind") == "suspended"
        for name, payload in context.calls
        if name == "checkpoint_activity_trigger"
    )


def test_capacity_exception_waits_for_manager_and_marks_approval():
    context = _Context(
        utilization=0.95,
        decision={"decision": "approve", "persona": "delivery_lead"},
    )

    result = _drive(context)

    assert result["command"]["payload"]["capacity_approved"] is True
    suspended = next(
        payload["payload"]
        for name, payload in context.calls
        if name == "checkpoint_activity_trigger" and payload.get("kind") == "suspended"
    )
    assert suspended["persona"] == "delivery_lead"
