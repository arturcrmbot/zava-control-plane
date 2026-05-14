"""Generator-driven test of expense_claim_orchestration.

Drives the orchestration with a hand-rolled context stub that mimics the
minimal Durable Functions surface the orchestrator uses. Goal: prove the
right phase activities are called and the verdict-gated branch logic works.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Iterable

from api.functions.workflows.expense_claim import expense_claim_orchestration


class _StubTimerEvent:
    """Sentinel returned by context.create_timer."""
    def __init__(self, fire_at):
        self.fire_at = fire_at
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class _StubExternalEvent:
    """Sentinel returned by context.wait_for_external_event."""
    def __init__(self, name, result=None):
        self.name = name
        self.result = result


class _StubContext:
    """Minimal DurableOrchestrationContext stub.

    Drive the generator step by step; on each yield, supply the activity result
    via .send(). Lifecycle/checkpoint activities return {}; phase activities
    return whatever the test specifies.
    """
    def __init__(self, claim_id="CLM-9000", verdict="green", justification=None, decision=None):
        self.instance_id = "instance-1"
        self.current_utc_datetime = datetime(2026, 4, 28, 12, 0, tzinfo=timezone.utc)
        self._claim_id = claim_id
        self._verdict = verdict
        self._justification = justification
        self._decision = decision
        self.calls: list[tuple[str, dict]] = []

    def get_input(self):
        return {"workflow_id": self._claim_id}

    def call_activity(self, name: str, payload: dict):
        self.calls.append((name, payload))
        if name == "checkpoint_activity_trigger":
            return {}
        if name == "intake_activity_trigger":
            return {"normalised": True}
        if name == "classify_activity_trigger":
            return {"verdict": self._verdict}
        if name == "receipt_activity_trigger":
            return {"valid": True}
        if name == "route_activity_trigger":
            return {"target": self._verdict}
        if name == "notify_activity_trigger":
            return {"sent": True}
        if name == "arbitrate_activity_trigger":
            return {"recommended": "accept-justification"}
        if name == "audit_activity_trigger":
            return {"appended": True}
        return {}

    def wait_for_external_event(self, name: str):
        if name == "justification":
            return _StubExternalEvent(name, self._justification)
        if name == "reviewer_decision":
            return _StubExternalEvent(name, self._decision)
        return _StubExternalEvent(name)

    def create_timer(self, fire_at):
        return _StubTimerEvent(fire_at)

    def task_any(self, awaitables: Iterable):
        # Pick the first non-timer event when supplied; otherwise the timer.
        evs = list(awaitables)
        for e in evs:
            if isinstance(e, _StubExternalEvent):
                return e
        return evs[-1] if evs else None


def _drive(ctx: _StubContext) -> dict | None:
    gen = expense_claim_orchestration(ctx)  # type: ignore[arg-type]
    sent: Any = None
    while True:
        try:
            target = gen.send(sent) if sent is not None else next(gen)
        except StopIteration as stop:
            return stop.value
        if isinstance(target, _StubExternalEvent) or isinstance(target, _StubTimerEvent):
            sent = target
        else:
            sent = target


def test_green_verdict_skips_notify_and_arbitrate():
    ctx = _StubContext(claim_id="CLM-G", verdict="green")
    result = _drive(ctx)
    activities = [c[0] for c in ctx.calls]
    assert "intake_activity_trigger" in activities
    assert "classify_activity_trigger" in activities
    assert "receipt_activity_trigger" in activities
    assert "route_activity_trigger" in activities
    assert "notify_activity_trigger" not in activities
    assert "arbitrate_activity_trigger" not in activities
    assert "audit_activity_trigger" in activities
    assert result["status"] == "completed"
    assert result["verdict"] == "green"


def test_red_verdict_runs_notify_and_arbitrate_with_accept():
    ctx = _StubContext(
        claim_id="CLM-R",
        verdict="red",
        justification={"text": "client lunch — see attached approval", "by": "EMP-0001"},
        decision={"decision": "accept-justification", "resolved_by": "ssc-reviewer-1"},
    )
    result = _drive(ctx)
    activities = [c[0] for c in ctx.calls]
    assert activities.count("notify_activity_trigger") == 1
    assert activities.count("arbitrate_activity_trigger") == 1
    assert "audit_activity_trigger" in activities
    assert result["status"] == "completed"
    assert result["verdict"] == "red"


def test_red_verdict_reviewer_rejection_short_circuits_audit():
    ctx = _StubContext(
        claim_id="CLM-RX",
        verdict="red",
        justification={"text": "n/a"},
        decision={"decision": "rejected", "resolved_by": "ssc-reviewer-2"},
    )
    result = _drive(ctx)
    activities = [c[0] for c in ctx.calls]
    assert "arbitrate_activity_trigger" in activities
    assert "audit_activity_trigger" not in activities
    assert result["status"] == "rejected"
    assert result["phase"] == "Arbitrate"
