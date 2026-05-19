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


def test_segment_mode_parser_removed() -> None:
    """The HIRING_SEGMENT_MODE feature flag (and its `_parse_segments_enabled`
    parser) were removed once segments became the only hiring path
    (refactor commit — drop HIRING_SEGMENT_MODE flag). Pin that the
    symbol stays gone so a revert doesn't silently restore the dead
    scaffolding."""
    import api.functions.workflows.hiring as hiring_mod
    assert not hasattr(hiring_mod, "_parse_segments_enabled")
    assert not hasattr(hiring_mod, "_segment_enabled")
    assert not hasattr(hiring_mod, "SEGMENT_MAX_RETRIES")


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
        voice_event: dict | None = None,
        invite_decision: dict | None = None,
        booked_decision: dict | None = None,
        post_decision: dict | None = None,
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
        # Defaults mirror the green-path defaults in test_hiring_voice_phase
        # so completion-path tests can opt in without spelling each gate.
        self._voice_event = voice_event or {"score": 0.8, "duration_s": 120.0}
        self._invite_decision = invite_decision or {"decision": "invite"}
        self._booked_decision = booked_decision or {"slot": "2026-06-01T10:00Z"}
        self._post_decision = post_decision or {"decision": "offer", "level": "L4", "rating": 4}

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
        if name == "issue_screen_link_activity_trigger":
            return {"token": "tok-1", "portal_url": "http://x"}
        # Segments D/E/F (non-focal) need schema-valid defaults so the
        # orchestrator completes instead of exhausting its retry budget.
        from tests.api.unit._segment_defaults import default_segment_call_activity
        default = default_segment_call_activity(name, payload)
        if default is not None:
            return default
        # Generic stub return
        return {}

    def wait_for_external_event(self, name: str):
        # Approvals default to "approve" so the orchestrator advances past
        # the Budget HITL into Phase 2-5 (or Segment B).
        if name == "budget_approval":
            return _StubExternalEvent(name, {"decision": "approve"})
        if name == "offer_approval":
            return _StubExternalEvent(name, {"decision": "approve"})
        if name == "voice_complete":
            return _StubExternalEvent(name, self._voice_event)
        if name == "interview_invite":
            return _StubExternalEvent(name, self._invite_decision)
        if name == "interview_booked":
            return _StubExternalEvent(name, self._booked_decision)
        if name == "offer_decision":
            return _StubExternalEvent(name, self._post_decision)
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


def test_orchestrator_segment_b_yields_segment_activities(monkeypatch):
    """Segment B is now the only path; the four legacy per-phase activities
    have been deleted (refactor commit — drop HIRING_SEGMENT_MODE flag).
    Asserts the orchestrator drives the segment-B activity + its validator."""
    ctx = _SegmentBStubContext()
    _drive_until_done_or_error(ctx)
    activities = [c[0] for c in ctx.calls]
    assert "hiring_segment_b_activity_trigger" in activities
    assert "validate_segment_b_output_activity_trigger" in activities


def test_orchestrator_segment_b_retry_on_validation_failure(monkeypatch):
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
    # SEGMENT_MAX_RETRIES is read inside the orchestrator on each run
    # (refactor commit — drop HIRING_SEGMENT_MODE flag) so the env var
    # is honoured without a worker restart. Patch the env.
    monkeypatch.setenv("SEGMENT_MAX_RETRIES", "1")
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


def test_orchestrator_segment_b_runs_to_completion(monkeypatch):
    """Defect 1 regression: the orchestrator must reach the final
    workflow.completed return dict without raising UnboundLocalError on
    job_design_result / sourcing_result / triage_result.
    """
    ctx = _SegmentBStubContext(candidate_id="C-COMPLETE-1")
    result = _drive_until_done_or_error(ctx)
    assert result is not None, "orchestrator must reach return statement"
    assert result["status"] == "completed"
    # These three were the UnboundLocalError vars in the bug.
    assert result["job_design"] is not None
    assert result["sourcing"] is not None
    assert result["triage"] is not None


def test_orchestrator_segment_b_populates_enriched_keys(monkeypatch):
    """Defect 2 regression: enriched.get('triage')/sourcing/job_design
    must be non-None on the segment-B path so the Segment D input and
    HITL payloads don't lose context.
    """
    ctx = _SegmentBStubContext(candidate_id="C-ENRICHED-1")
    _drive_until_done_or_error(ctx)
    # Segment D's input (gate-1 recommender, now folded in) reads
    # enriched.get("triage").
    segment_d_calls = [
        payload for (name, payload) in ctx.calls
        if name == "hiring_segment_d_activity_trigger"
    ]
    assert segment_d_calls, "Segment D must have been invoked"
    first = segment_d_calls[0]
    assert first.get("triage") is not None, "enriched['triage'] must be seeded under segment-B"
    assert first.get("sourcing") is not None
    assert first.get("job_design") is not None
    # HITL suspended payload carries triage in its context.
    invite_suspend = [
        payload for (name, payload) in ctx.calls
        if name == "checkpoint_activity_trigger"
        and payload.get("kind") == "suspended"
        and payload.get("payload", {}).get("reason") == "awaiting_interview_invite"
    ]
    assert invite_suspend, "expected awaiting_interview_invite suspend checkpoint"
    assert invite_suspend[0]["payload"]["context"]["triage"] is not None
