from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class _Call:
    kind: str
    name: str
    payload: dict | list
    instance_id: str | None = None


class _Task:
    def __init__(self, result=None):
        self.result = result
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class _Context:
    instance_id = "aurora-instance-001"
    current_utc_datetime = datetime(2026, 9, 10, tzinfo=timezone.utc)

    def __init__(self, decision: dict):
        self.decision_task = _Task(decision)
        self.timer_task = _Task()
        self.calls: list[_Call] = []

    def get_input(self):
        return {
            "workflow_id": "AUR-TEST001",
            "type": "aurora-budget-response",
            "request_id": "request-001",
            "count": 2,
            "brand_id": "BRAND-aurora",
        }

    def call_activity(self, name, payload):
        call = _Call("activity", name, payload)
        self.calls.append(call)
        return call

    def wait_for_external_event(self, name):
        assert name == "aurora_budget_response_decision"
        return self.decision_task

    def create_timer(self, deadline):
        return self.timer_task

    def task_any(self, tasks):
        assert tasks == [self.decision_task, self.timer_task]
        return _Call("task_any", "approval", {})

    def call_sub_orchestrator(self, name, input_, instance_id=None):
        call = _Call("sub_orchestrator", name, input_, instance_id)
        self.calls.append(call)
        return call

    def task_all(self, tasks):
        return _Call("task_all", "children", list(tasks))


def _drive_approved(context: _Context):
    from api.functions.workflows.aurora_budget_response import (
        aurora_budget_response_orchestration,
    )

    gen = aurora_budget_response_orchestration(context)
    yielded = next(gen)
    while True:
        if yielded.kind == "activity":
            if yielded.name == "aurora_observe_budget_activity_trigger":
                sent = {
                    "brand_id": "BRAND-aurora",
                    "brand_name": "Aurora",
                    "before_pct": 0.4,
                    "after_pct": 1.0,
                    "signal_id": "signal-001",
                }
            elif yielded.name == "aurora_recommendation_activity_trigger":
                sent = {
                    "recommendation": "Freeze Aurora purchase orders for 14 days.",
                    "proposed_action": {
                        "id": "freeze-brand-aurora",
                        "kind": "policy_set",
                        "verdict": "freeze",
                        "decided_on": ["BRAND-aurora"],
                        "attributes": {"scope": "po", "expiry_days": 14},
                    },
                    "selected_invoice_ids": ["INV-AUR-001", "INV-AUR-002"],
                }
            elif yielded.name == "aurora_apply_policy_activity_trigger":
                sent = {
                    "outcome": "applied",
                    "decision_id": "01POLICYDECISION",
                    "governing_rule_id": "POL-CFO-001",
                }
            elif yielded.name == "aurora_synthesise_activity_trigger":
                sent = {
                    "status": "completed",
                    "queued_count": 2,
                    "completed_count": 2,
                    "failed_count": 0,
                }
            else:
                sent = {}
        elif yielded.kind == "task_any":
            sent = context.decision_task
        elif yielded.kind == "task_all":
            sent = [
                {"status": "completed", "invoice_id": "INV-AUR-001"},
                {"status": "completed", "invoice_id": "INV-AUR-002"},
            ]
        else:  # pragma: no cover
            raise AssertionError(yielded)
        try:
            yielded = gen.send(sent)
        except StopIteration as stop:
            return stop.value


def test_approved_arc_waits_then_applies_policy_and_runs_real_ap_children():
    context = _Context({
        "decision": "approve",
        "decision_id": "EXC-AURORA-001",
        "resolved_by": "operator@example.test",
        "actor_role": "cfo",
    })

    result = _drive_approved(context)

    assert result["status"] == "completed"
    assert result["policy"]["governing_rule_id"] == "POL-CFO-001"
    children = [call for call in context.calls if call.kind == "sub_orchestrator"]
    assert [call.name for call in children] == [
        "FleetApInvoiceOrchestrator",
        "FleetApInvoiceOrchestrator",
    ]
    assert [call.payload["workflow_id"] for call in children] == result["child_workflow_ids"]
    assert all(call.payload["parent_workflow_id"] == "AUR-TEST001" for call in children)
    assert all(call.payload["invoice"]["brand_id"] == "BRAND-aurora" for call in children)
    apply_call = next(
        call for call in context.calls
        if call.name == "aurora_apply_policy_activity_trigger"
    )
    assert apply_call.payload["approval"]["decision_id"] == "EXC-AURORA-001"
    assert context.timer_task.cancelled is True


def test_rejected_arc_never_applies_policy_or_starts_children():
    from api.functions.workflows.aurora_budget_response import (
        aurora_budget_response_orchestration,
    )

    context = _Context({
        "decision": "reject",
        "decision_id": "EXC-AURORA-REJECT",
        "resolved_by": "operator@example.test",
        "actor_role": "cfo",
    })
    gen = aurora_budget_response_orchestration(context)
    yielded = next(gen)
    try:
        while True:
            if yielded.kind == "activity":
                if yielded.name == "aurora_observe_budget_activity_trigger":
                    sent = {"brand_id": "BRAND-aurora", "after_pct": 1.0}
                elif yielded.name == "aurora_recommendation_activity_trigger":
                    sent = {
                        "recommendation": "freeze",
                        "proposed_action": {
                            "id": "freeze-brand-aurora",
                            "kind": "policy_set",
                            "verdict": "freeze",
                            "decided_on": ["BRAND-aurora"],
                            "attributes": {"scope": "po", "expiry_days": 14},
                        },
                        "selected_invoice_ids": ["INV-AUR-001"],
                    }
                else:
                    sent = {}
            else:
                sent = context.decision_task
            yielded = gen.send(sent)
    except StopIteration as stop:
        result = stop.value

    assert result["status"] == "rejected"
    assert not any(
        call.name == "aurora_apply_policy_activity_trigger"
        for call in context.calls
    )
    assert not any(call.kind == "sub_orchestrator" for call in context.calls)


def test_approval_timeout_fails_without_applying_policy():
    from api.functions.workflows.aurora_budget_response import (
        aurora_budget_response_orchestration,
    )

    context = _Context({})
    gen = aurora_budget_response_orchestration(context)
    yielded = next(gen)
    try:
        while True:
            if yielded.kind == "activity":
                if yielded.name == "aurora_observe_budget_activity_trigger":
                    sent = {"brand_id": "BRAND-aurora", "after_pct": 1.0}
                elif yielded.name == "aurora_recommendation_activity_trigger":
                    sent = {
                        "recommendation": "freeze",
                        "proposed_action": {
                            "id": "freeze-brand-aurora",
                            "kind": "policy_set",
                            "verdict": "freeze",
                            "decided_on": ["BRAND-aurora"],
                            "attributes": {"scope": "po", "expiry_days": 14},
                        },
                        "selected_invoice_ids": ["INV-AUR-001"],
                    }
                else:
                    sent = {}
            else:
                sent = context.timer_task
            yielded = gen.send(sent)
    except StopIteration as stop:
        result = stop.value

    assert result == {"status": "failed", "outcome": "approval_timeout"}
    assert not any(
        call.name == "aurora_apply_policy_activity_trigger"
        for call in context.calls
    )


def test_policy_application_denial_is_explicit_terminal_failure():
    from api.functions.workflows.aurora_budget_response import (
        aurora_budget_response_orchestration,
    )

    context = _Context({
        "decision": "approve",
        "decision_id": "EXC-AURORA-DENIED",
        "resolved_by": "operator@example.test",
        "actor_role": "cfo",
    })
    gen = aurora_budget_response_orchestration(context)
    yielded = next(gen)
    try:
        while True:
            if yielded.kind == "activity":
                if yielded.name == "aurora_observe_budget_activity_trigger":
                    sent = {"brand_id": "BRAND-aurora", "after_pct": 1.0}
                elif yielded.name == "aurora_recommendation_activity_trigger":
                    sent = {
                        "recommendation": "freeze",
                        "proposed_action": {
                            "id": "freeze-brand-aurora",
                            "kind": "policy_set",
                            "verdict": "freeze",
                            "decided_on": ["BRAND-aurora"],
                            "attributes": {"scope": "po", "expiry_days": 14},
                        },
                        "selected_invoice_ids": ["INV-AUR-001"],
                    }
                elif yielded.name == "aurora_apply_policy_activity_trigger":
                    yielded = gen.throw(PermissionError("authority denied"))
                    continue
                else:
                    sent = {}
            else:
                sent = context.decision_task
            yielded = gen.send(sent)
    except StopIteration as stop:
        result = stop.value

    assert result["status"] == "failed"
    assert result["outcome"] == "policy_application_denied"
    terminal = context.calls[-1]
    assert terminal.name == "checkpoint_activity_trigger"
    assert terminal.payload["kind"] == "workflow.failed"


def test_failed_child_result_fails_root_after_truthful_synthesis():
    from api.functions.workflows.aurora_budget_response import (
        aurora_budget_response_orchestration,
    )

    context = _Context({
        "decision": "approve",
        "decision_id": "EXC-AURORA-CHILD",
        "resolved_by": "operator@example.test",
        "actor_role": "cfo",
    })
    gen = aurora_budget_response_orchestration(context)
    yielded = next(gen)
    try:
        while True:
            if yielded.kind == "activity":
                if yielded.name == "aurora_observe_budget_activity_trigger":
                    sent = {"brand_id": "BRAND-aurora", "after_pct": 1.0}
                elif yielded.name == "aurora_recommendation_activity_trigger":
                    sent = {
                        "recommendation": "freeze",
                        "proposed_action": {
                            "id": "freeze-brand-aurora",
                            "kind": "policy_set",
                            "verdict": "freeze",
                            "decided_on": ["BRAND-aurora"],
                            "attributes": {"scope": "po", "expiry_days": 14},
                        },
                        "selected_invoice_ids": ["INV-AUR-001"],
                    }
                elif yielded.name == "aurora_apply_policy_activity_trigger":
                    sent = {
                        "outcome": "applied",
                        "decision_id": "01POLICY",
                        "governing_rule_id": "POL-CFO-001",
                    }
                elif yielded.name == "aurora_synthesise_activity_trigger":
                    sent = {
                        "status": "failed",
                        "queued_count": 1,
                        "completed_count": 0,
                        "failed_count": 1,
                    }
                else:
                    sent = {}
            elif yielded.kind == "task_any":
                sent = context.decision_task
            elif yielded.kind == "task_all":
                sent = [{
                    "status": "failed",
                    "outcome": "unresolved_escalation",
                    "invoice_id": "INV-AUR-001",
                }]
            else:  # pragma: no cover
                raise AssertionError(yielded)
            yielded = gen.send(sent)
    except StopIteration as stop:
        result = stop.value

    assert result["status"] == "failed"
    assert result["outcome"] == "child_failure"
