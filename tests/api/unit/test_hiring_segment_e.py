"""Phase 4 of plan/refactor-substrate-agentic-segments-1.md."""
from __future__ import annotations
import os
os.environ["AZURE_STORAGE_CONNECTION_STRING"] = ""

import pytest
from pydantic import ValidationError


def test_segment_e_output_accepts_valid() -> None:
    from api.functions.segments.hiring_e import SegmentEOutput
    out = SegmentEOutput.model_validate({
        "offer_letter_id": "OFFER-1",
        "jurisdiction": "USA",
        "compliance_steps": ["EEO checks complete"],
        "policy_citations": ["data/policies/hr/eeo.md#L34"],
    })
    assert out.offer_letter_id == "OFFER-1"


@pytest.mark.parametrize("bad", [
    {"offer_letter_id": "OFFER-1", "jurisdiction": "FR", "compliance_steps": [], "policy_citations": []},
    {"jurisdiction": "USA", "compliance_steps": [], "policy_citations": []},
])
def test_segment_e_output_rejects(bad: dict) -> None:
    from api.functions.segments.hiring_e import SegmentEOutput
    with pytest.raises(ValidationError):
        SegmentEOutput.model_validate(bad)


@pytest.mark.asyncio
async def test_run_segment_e_with_fake_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_RUNTIME", "fake")
    from api.functions.graphs.executors.agents.runtime_fake import FakeRuntime
    FakeRuntime.canned_text = (
        '{"offer_letter_id": "OFFER-1", "jurisdiction": "USA", '
        '"compliance_steps": ["EEO checks complete"], '
        '"policy_citations": ["data/policies/hr/eeo.md#L34"]}'
    )
    from api.functions.segments.hiring_e import run_segment_e, SegmentEOutput
    out = await run_segment_e({"workflow_id": "WF-1", "candidate_id": "C-1"})
    parsed = SegmentEOutput.model_validate(out)
    assert parsed.offer_letter_id == "OFFER-1"


def test_validate_activity_accepts_valid_output() -> None:
    """Plain Python call to the validator activity's body."""
    from function_app import validate_segment_e_output_activity_trigger as v_act
    result = v_act({
        "offer_letter_id": "OFFER-1",
        "jurisdiction": "USA",
        "compliance_steps": ["EEO checks complete"],
        "policy_citations": ["data/policies/hr/eeo.md#L34"],
    })
    assert result["ok"] is True


def test_validate_activity_rejects_invalid() -> None:
    from function_app import validate_segment_e_output_activity_trigger as v_act
    result = v_act({"jurisdiction": "FR"})
    assert result["ok"] is False
    assert "errors" in result


# --------------------------------------------------------------------------
# Orchestrator branch tests (Phase 4 Task 4)
# --------------------------------------------------------------------------
from datetime import datetime, timezone
from typing import Any, Iterable


class _StubTimerEvent:
    def __init__(self, fire_at):
        self.fire_at = fire_at
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class _StubExternalEvent:
    def __init__(self, name, result=None):
        self.name = name
        self.result = result


class _SegmentEStubContext:
    def __init__(
        self,
        *,
        validator_replies: list[dict] | None = None,
        segment_result: dict | None = None,
    ):
        self.instance_id = "instance-sege-1"
        self.current_utc_datetime = datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc)
        self.calls: list[tuple[str, dict]] = []
        self._validator_replies = list(validator_replies or [])
        self._segment_result = segment_result or {
            "offer_letter_id": "OFFER-1",
            "jurisdiction": "USA",
            "compliance_steps": ["EEO checks complete"],
            "policy_citations": ["data/policies/hr/eeo.md#L34"],
        }

    def get_input(self):
        return {"workflow_id": "HIRE-SEGE-1"}

    def call_activity(self, name: str, payload: dict):
        self.calls.append((name, payload))
        if name == "hiring_segment_e_activity_trigger":
            return self._segment_result
        if name == "validate_segment_e_output_activity_trigger":
            if self._validator_replies:
                return self._validator_replies.pop(0)
            return {"ok": True, "output": payload}
        if name == "hiring_screening_activity_trigger":
            return {"verdict": "borderline"}
        if name == "issue_screen_link_activity_trigger":
            return {"token": "tok-1", "portal_url": "http://x"}
        return {}

    def wait_for_external_event(self, name: str):
        defaults = {
            "budget_approval": {"decision": "approve"},
            "offer_approval": {"decision": "approve"},
            "voice_complete": {"score": 0.8, "duration_s": 120.0},
            "interview_invite": {"decision": "invite"},
            "interview_booked": {"slot": "2026-06-01T10:00Z"},
            "offer_decision": {"decision": "offer", "level": "L4", "rating": 4},
        }
        return _StubExternalEvent(name, defaults.get(name, {}))

    def create_timer(self, fire_at):
        return _StubTimerEvent(fire_at)

    def task_any(self, awaitables: Iterable):
        for e in awaitables:
            if isinstance(e, _StubExternalEvent):
                return e
        return list(awaitables)[-1]


def _drive(ctx):
    from api.functions.workflows.hiring import hiring_orchestration
    gen = hiring_orchestration(ctx)  # type: ignore[arg-type]
    sent: Any = None
    while True:
        try:
            target = gen.send(sent) if sent is not None else next(gen)
        except StopIteration as stop:
            return stop.value
        sent = target


def test_orchestrator_segment_e_on_replaces_per_phase_activities(monkeypatch):
    monkeypatch.setenv("HIRING_SEGMENT_MODE", "e")
    ctx = _SegmentEStubContext()
    _drive(ctx)
    activities = [c[0] for c in ctx.calls]
    assert "hiring_segment_e_activity_trigger" in activities
    assert "validate_segment_e_output_activity_trigger" in activities
    for legacy in (
        "hiring_compliance_activity_trigger",
        "hiring_offer_activity_trigger",
    ):
        assert legacy not in activities, f"Segment E should replace {legacy}"


def test_orchestrator_segment_e_off_keeps_existing_path(monkeypatch):
    monkeypatch.setenv("HIRING_SEGMENT_MODE", "off")
    ctx = _SegmentEStubContext()
    _drive(ctx)
    activities = [c[0] for c in ctx.calls]
    for legacy in (
        "hiring_compliance_activity_trigger",
        "hiring_offer_activity_trigger",
    ):
        assert legacy in activities
    assert "hiring_segment_e_activity_trigger" not in activities


def test_orchestrator_segment_e_retry_on_validation_failure(monkeypatch):
    monkeypatch.setenv("HIRING_SEGMENT_MODE", "e")
    valid = {
        "offer_letter_id": "OFFER-1",
        "jurisdiction": "USA",
        "compliance_steps": ["EEO checks complete"],
        "policy_citations": ["data/policies/hr/eeo.md#L34"],
    }
    ctx = _SegmentEStubContext(
        validator_replies=[
            {"ok": False, "errors": ["bad jurisdiction"]},
            {"ok": True, "output": valid},
        ],
    )
    _drive(ctx)
    activities = [c[0] for c in ctx.calls]
    assert activities.count("hiring_segment_e_activity_trigger") == 2
    assert activities.count("validate_segment_e_output_activity_trigger") == 2


def test_orchestrator_segment_e_retry_exhaustion(monkeypatch):
    monkeypatch.setenv("HIRING_SEGMENT_MODE", "e")
    monkeypatch.setattr("api.functions.workflows.hiring.SEGMENT_MAX_RETRIES", 1)
    ctx = _SegmentEStubContext(
        validator_replies=[
            {"ok": False, "errors": ["e1"]},
            {"ok": False, "errors": ["e2"]},
            {"ok": False, "errors": ["e3"]},
        ],
    )
    with pytest.raises(RuntimeError, match="Segment E validation failed"):
        _drive(ctx)
    failure_checkpoints = [
        payload for (name, payload) in ctx.calls
        if name == "checkpoint_activity_trigger"
        and payload.get("kind") == "segment.failed"
    ]
    assert len(failure_checkpoints) == 1
    assert failure_checkpoints[0]["segment"] == "e"
