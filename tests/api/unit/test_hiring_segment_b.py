"""Phase 3 of plan/refactor-substrate-agentic-segments-1.md."""
from __future__ import annotations
import os
os.environ["AZURE_STORAGE_CONNECTION_STRING"] = ""

import pytest
from pydantic import ValidationError


def test_segment_b_output_accepts_valid() -> None:
    from api.functions.segments.hiring_b import SegmentBOutput
    out = SegmentBOutput.model_validate({
        "verdict": "strong",
        "jd_draft_id": "JD-1",
        "sourcing_pool_id": "POOL-1",
        "candidates": [{"id": "C-1", "score": 0.91, "rationale": "ok"}],
        "rationale": "all green",
    })
    assert out.verdict == "strong"


@pytest.mark.parametrize("bad", [
    {"verdict": "MAYBE", "jd_draft_id": "x", "sourcing_pool_id": "y", "candidates": [], "rationale": "z"},
    {"verdict": "strong", "jd_draft_id": "x", "sourcing_pool_id": "y", "candidates": [], "rationale": "z"},  # empty candidates not allowed
    {"jd_draft_id": "x", "sourcing_pool_id": "y", "candidates": [{"id":"c","score":0.1,"rationale":"r"}], "rationale": "z"},  # missing verdict
])
def test_segment_b_output_rejects(bad: dict) -> None:
    from api.functions.segments.hiring_b import SegmentBOutput
    with pytest.raises(ValidationError):
        SegmentBOutput.model_validate(bad)


@pytest.mark.asyncio
async def test_run_segment_b_with_fake_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_RUNTIME", "fake")
    from api.functions.graphs.executors.agents.runtime_fake import FakeRuntime
    FakeRuntime.canned_text = (
        '{"verdict": "strong", "jd_draft_id": "JD-1", '
        '"sourcing_pool_id": "POOL-1", '
        '"candidates": [{"id": "C-1", "score": 0.92, "rationale": "ok"}], '
        '"rationale": "all green"}'
    )
    from api.functions.segments.hiring_b import run_segment_b, SegmentBOutput
    out = await run_segment_b({"workflow_id": "WF-1", "req_id": "REQ-1"})
    parsed = SegmentBOutput.model_validate(out)
    assert parsed.verdict == "strong"


def test_validate_activity_accepts_valid_output() -> None:
    """Plain Python call to the validator activity's body."""
    from function_app import validate_segment_b_output_activity_trigger as v_act
    result = v_act({
        "verdict": "strong", "jd_draft_id": "JD-1", "sourcing_pool_id": "POOL-1",
        "candidates": [{"id":"c","score":0.5,"rationale":"r"}], "rationale": "ok",
    })
    assert result["ok"] is True


def test_validate_activity_rejects_invalid() -> None:
    from function_app import validate_segment_b_output_activity_trigger as v_act
    result = v_act({"verdict": "MAYBE"})
    assert result["ok"] is False
    assert "errors" in result


def test_segment_mode_parser() -> None:
    from api.functions.workflows.hiring import _parse_segments_enabled
    assert _parse_segments_enabled("off") == set()
    assert _parse_segments_enabled("") == set()
    assert _parse_segments_enabled("b") == {"b"}
    assert _parse_segments_enabled("b,e") == {"b", "e"}
    assert _parse_segments_enabled("all") == {"all"}
    # unknown letters dropped (with warning, not error)
    assert _parse_segments_enabled("b,zz") == {"b"}


# --------------------------------------------------------------------------
# Orchestrator branch tests (Task 4)
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


class _SegmentBStubContext:
    """Minimal DurableOrchestrationContext stub focused on Segment B paths.

    Records every activity call and lets tests script the validator-activity
    reply sequence (for retry / exhaustion scenarios).
    """

    def __init__(
        self,
        *,
        validator_replies: list[dict] | None = None,
        segment_result: dict | None = None,
        candidate_id: str | None = None,
    ):
        self.instance_id = "instance-segb-1"
        self.current_utc_datetime = datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc)
        self.calls: list[tuple[str, dict]] = []
        self._validator_replies = list(validator_replies or [])
        self._segment_result = segment_result or {
            "verdict": "strong",
            "jd_draft_id": "JD-1",
            "sourcing_pool_id": "POOL-1",
            "candidates": [{"id": "C-1", "score": 0.91, "rationale": "ok"}],
            "rationale": "all green",
        }
        self._candidate_id = candidate_id

    def get_input(self):
        out: dict[str, Any] = {"workflow_id": "HIRE-SEGB-1"}
        if self._candidate_id is not None:
            out["candidate_id"] = self._candidate_id
        return out

    def call_activity(self, name: str, payload: dict):
        self.calls.append((name, payload))
        if name == "hiring_segment_b_activity_trigger":
            return self._segment_result
        if name == "validate_segment_b_output_activity_trigger":
            if self._validator_replies:
                return self._validator_replies.pop(0)
            # Default: pass-through valid
            return {"ok": True, "output": payload}
        if name == "hiring_screening_activity_trigger":
            return {"verdict": "borderline"}
        if name == "issue_screen_link_activity_trigger":
            return {"token": "tok-1", "portal_url": "http://x"}
        # Generic stub return
        return {}

    def wait_for_external_event(self, name: str):
        # Approvals default to "approve" so the orchestrator advances past
        # the Budget HITL into Phase 2-5 (or Segment B).
        if name == "budget_approval":
            return _StubExternalEvent(name, {"decision": "approve"})
        if name == "offer_approval":
            return _StubExternalEvent(name, {"decision": "approve"})
        return _StubExternalEvent(name, {})

    def create_timer(self, fire_at):
        return _StubTimerEvent(fire_at)

    def task_any(self, awaitables: Iterable):
        # Always let the external event win (never time out).
        for e in awaitables:
            if isinstance(e, _StubExternalEvent):
                return e
        return list(awaitables)[-1]


def _drive_until_done_or_error(ctx: _SegmentBStubContext):
    """Drive orchestrator to completion or until it raises."""
    from api.functions.workflows.hiring import hiring_orchestration
    gen = hiring_orchestration(ctx)  # type: ignore[arg-type]
    sent: Any = None
    while True:
        try:
            target = gen.send(sent) if sent is not None else next(gen)
        except StopIteration as stop:
            return stop.value
        sent = target


def test_orchestrator_segment_b_on_replaces_four_phase_activities(monkeypatch):
    monkeypatch.setenv("HIRING_SEGMENT_MODE", "b")
    ctx = _SegmentBStubContext()
    _drive_until_done_or_error(ctx)
    activities = [c[0] for c in ctx.calls]
    assert "hiring_segment_b_activity_trigger" in activities
    assert "validate_segment_b_output_activity_trigger" in activities
    for legacy in (
        "hiring_job_design_activity_trigger",
        "hiring_sourcing_activity_trigger",
        "hiring_triage_activity_trigger",
        "hiring_screening_activity_trigger",
    ):
        assert legacy not in activities, f"Segment B should replace {legacy}"


def test_orchestrator_segment_b_off_keeps_existing_path(monkeypatch):
    monkeypatch.setenv("HIRING_SEGMENT_MODE", "off")
    ctx = _SegmentBStubContext()
    _drive_until_done_or_error(ctx)
    activities = [c[0] for c in ctx.calls]
    for legacy in (
        "hiring_job_design_activity_trigger",
        "hiring_sourcing_activity_trigger",
        "hiring_triage_activity_trigger",
        "hiring_screening_activity_trigger",
    ):
        assert legacy in activities, f"Off-path must still run {legacy}"
    assert "hiring_segment_b_activity_trigger" not in activities


def test_orchestrator_segment_b_retry_on_validation_failure(monkeypatch):
    monkeypatch.setenv("HIRING_SEGMENT_MODE", "b")
    valid_output = {
        "verdict": "strong",
        "jd_draft_id": "JD-1",
        "sourcing_pool_id": "POOL-1",
        "candidates": [{"id": "C-1", "score": 0.91, "rationale": "ok"}],
        "rationale": "all green",
    }
    ctx = _SegmentBStubContext(
        validator_replies=[
            {"ok": False, "errors": ["bad verdict"]},
            {"ok": True, "output": valid_output},
        ],
    )
    _drive_until_done_or_error(ctx)
    activities = [c[0] for c in ctx.calls]
    assert activities.count("hiring_segment_b_activity_trigger") == 2
    assert activities.count("validate_segment_b_output_activity_trigger") == 2


def test_orchestrator_segment_b_retry_exhaustion(monkeypatch):
    monkeypatch.setenv("HIRING_SEGMENT_MODE", "b")
    # SEGMENT_MAX_RETRIES is read at module import time; patch directly.
    monkeypatch.setattr("api.functions.workflows.hiring.SEGMENT_MAX_RETRIES", 1)
    ctx = _SegmentBStubContext(
        validator_replies=[
            {"ok": False, "errors": ["e1"]},
            {"ok": False, "errors": ["e2"]},
            {"ok": False, "errors": ["e3"]},
        ],
    )
    with pytest.raises(RuntimeError, match="Segment B validation failed"):
        _drive_until_done_or_error(ctx)
    # Failure checkpoint was emitted.
    failure_checkpoints = [
        payload for (name, payload) in ctx.calls
        if name == "checkpoint_activity_trigger"
        and payload.get("kind") == "segment.failed"
    ]
    assert len(failure_checkpoints) == 1
    assert failure_checkpoints[0]["segment"] == "b"
