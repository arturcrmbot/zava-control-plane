"""
Unit test for the HITL rejection branch in invoice_p2p orchestration.

We drive the generator function directly with a hand-rolled context stub that
mimics the minimal Durable Functions surface the orchestration uses. The goal
is to prove that when the external approval_decision event carries a
`decision` value in DECISION_REJECTED, the generator:

  1. Yields a `workflow.rejected` checkpoint
  2. Returns a rejection result
  3. Never calls payment_activity_trigger or reconciliation_activity_trigger
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

import pytest

from api.functions.workflows.invoice_p2p import invoice_p2p_orchestration


class _Event:
    """Minimal stand-in for a Durable task (external event / timer)."""

    def __init__(self, name: str, result: Any = None) -> None:
        self.name = name
        self.result = result

    def cancel(self) -> None:  # pragma: no cover - no-op
        pass


class _FakeContext:
    """Records every call_activity name/payload and feeds pre-scripted results."""

    def __init__(self, instance_id: str, external_event_payload: dict) -> None:
        self.instance_id = instance_id
        self.current_utc_datetime = datetime.now(timezone.utc)
        self._input = {"workflow_id": "wf-test"}
        self._external_payload = external_event_payload
        self.activity_calls: list[tuple[str, Any]] = []

    def get_input(self) -> dict:
        return self._input

    def call_activity(self, name: str, payload: Any = None) -> _Event:
        self.activity_calls.append((name, payload))
        # Simulate approval activity returning a HITL-required result
        if name == "approval_activity_trigger":
            return _Event(name, {"requires_hitl": True, "reason": "over_threshold"})
        return _Event(name, {})

    def wait_for_external_event(self, _name: str) -> _Event:
        return _Event("approval_decision", self._external_payload)

    def create_timer(self, _dt: datetime) -> _Event:
        return _Event("timer")

    def task_any(self, events: list[_Event]) -> _Event:
        # Always pick the external event in the test — never the timer.
        return next(e for e in events if e.name == "approval_decision")


def _drive(ctx: _FakeContext) -> dict:
    """Drive the sync generator to completion, feeding each yield back."""
    gen = invoice_p2p_orchestration(ctx)
    try:
        sent: Any = None
        while True:
            task = gen.send(sent)
            sent = task.result if hasattr(task, "result") else None
    except StopIteration as stop:
        return stop.value or {}


@pytest.mark.parametrize("decision_value", ["reject", "rejected", "deny", "denied", "REJECT"])
def test_rejection_stops_at_approval(decision_value: str):
    ctx = _FakeContext(
        instance_id="inst-1",
        external_event_payload={"decision": decision_value, "resolved_by": "alice"},
    )
    result = _drive(ctx)

    assert result["status"] == "rejected"
    assert result["phase"] == "Approval"

    activity_names = [n for (n, _p) in ctx.activity_calls]
    assert "payment_activity_trigger" not in activity_names
    assert "reconciliation_activity_trigger" not in activity_names

    # A workflow.rejected checkpoint must have been emitted
    rejected_checkpoints = [
        p for (n, p) in ctx.activity_calls
        if n == "checkpoint_activity_trigger" and p.get("kind") == "workflow.rejected"
    ]
    assert len(rejected_checkpoints) == 1
    assert rejected_checkpoints[0]["payload"]["by"] == "alice"


def test_approval_continues_to_payment():
    ctx = _FakeContext(
        instance_id="inst-2",
        external_event_payload={"decision": "approve", "resolved_by": "bob"},
    )
    result = _drive(ctx)

    assert result["status"] == "completed"
    activity_names = [n for (n, _p) in ctx.activity_calls]
    assert "payment_activity_trigger" in activity_names
    assert "reconciliation_activity_trigger" in activity_names
