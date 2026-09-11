from __future__ import annotations

from datetime import datetime, timezone


class _Task:
    def __init__(self, result=None):
        self.result = result
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class _Context:
    instance_id = "ap-instance"
    current_utc_datetime = datetime(2026, 9, 10, tzinfo=timezone.utc)

    def __init__(self, clerk_decision: str, controller_decision: str = "approve"):
        self.clerk = _Task({"decision": clerk_decision, "decision_id": "DEC-CLERK"})
        self.controller = _Task({
            "decision": controller_decision,
            "decision_id": "DEC-CONTROLLER",
        })
        self.timers: list[_Task] = []
        self.wait_count = 0
        self.checkpoints: list[dict] = []

    def get_input(self):
        return {
            "workflow_id": "API-AUR-001",
            "type": "ap-invoice",
            "parent_workflow_id": "AUR-ROOT",
            "invoice": {
                "invoice_id": "INV-AUR-001",
                "brand_id": "BRAND-aurora",
                "amount_gbp": 5000,
                "category": "standard",
            },
            "scenario": "matched-clean",
        }

    def call_activity(self, name, payload):
        if name == "checkpoint_activity_trigger":
            self.checkpoints.append(payload)
        return (name, payload)

    def wait_for_external_event(self, _name):
        self.wait_count += 1
        return self.clerk if self.wait_count == 1 else self.controller

    def create_timer(self, _deadline):
        task = _Task()
        self.timers.append(task)
        return task

    def task_any(self, tasks):
        return ("task_any", tasks)


def _drive(context: _Context):
    from api.functions.workflows.fleet_ap_invoice import (
        fleet_ap_invoice_orchestration,
    )

    gen = fleet_ap_invoice_orchestration(context)
    yielded = next(gen)
    try:
        while True:
            name = yielded[0]
            if name == "fleet_ap_invoice_invoice_lookup_activity_trigger":
                sent = {
                    "invoice_id": "INV-AUR-001",
                    "amount_gbp": 5000,
                    "vendor": "Acme Holdings",
                    "gl_code": "4100",
                }
            elif name == "fleet_ap_invoice_three_way_match_activity_trigger":
                sent = {"matched": True, "invoice_amount_gbp": 5000}
            elif name == "task_any":
                sent = context.clerk if context.wait_count == 1 else context.controller
            else:
                sent = {}
            yielded = gen.send(sent)
    except StopIteration as stop:
        return stop.value


def test_ap_clerk_rejection_is_terminal_not_controller_escalation():
    context = _Context("reject")

    result = _drive(context)

    assert result["status"] == "rejected"
    assert result["phase"] == "ap_clerk_signoff"
    assert context.wait_count == 1
    terminal = context.checkpoints[-1]
    assert terminal["kind"] == "workflow.rejected"


def test_controller_escalation_is_failed_not_completed():
    context = _Context("escalate", "escalate")

    result = _drive(context)

    assert result["status"] == "failed"
    assert result["outcome"] == "unresolved_escalation"
    terminal = context.checkpoints[-1]
    assert terminal["kind"] == "workflow.failed"
