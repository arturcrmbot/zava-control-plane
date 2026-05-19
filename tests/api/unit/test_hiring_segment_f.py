"""Phase 4 of plan/refactor-substrate-agentic-segments-1.md."""
from __future__ import annotations
import os
os.environ["AZURE_STORAGE_CONNECTION_STRING"] = ""

import pytest
from pydantic import ValidationError


def test_segment_f_output_accepts_valid() -> None:
    from api.functions.segments.hiring_f import SegmentFOutput
    out = SegmentFOutput.model_validate({
        "onboarding_kickoff_id": "ONB-1",
        "avatar_video_url": "https://example.test/avatar.mp4",
        "day1_calendar_id": "MS-INV-1",
        "provisioning_steps": ["JML ticket SN-1234 raised"],
    })
    assert out.onboarding_kickoff_id == "ONB-1"


@pytest.mark.parametrize("bad", [
    {"onboarding_kickoff_id": None, "provisioning_steps": []},
])
def test_segment_f_output_rejects(bad: dict) -> None:
    from api.functions.segments.hiring_f import SegmentFOutput
    with pytest.raises(ValidationError):
        SegmentFOutput.model_validate(bad)


@pytest.mark.asyncio
async def test_run_segment_f_with_fake_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_RUNTIME", "fake")
    from api.functions.graphs.executors.agents.runtime_fake import FakeRuntime
    FakeRuntime.canned_text = (
        '{"onboarding_kickoff_id": "ONB-1", '
        '"avatar_video_url": "https://example.test/avatar.mp4", '
        '"day1_calendar_id": "MS-INV-1", '
        '"provisioning_steps": ["JML ticket SN-1234 raised"]}'
    )
    from api.functions.segments.hiring_f import run_segment_f, SegmentFOutput
    out = await run_segment_f({"workflow_id": "WF-1", "candidate_id": "C-1"})
    parsed = SegmentFOutput.model_validate(
        {k: v for k, v in out.items() if not k.startswith("_")}
    )
    assert parsed.onboarding_kickoff_id == "ONB-1"


def test_validate_activity_accepts_valid_output() -> None:
    from function_app import validate_segment_f_output_activity_trigger as v_act
    result = v_act({
        "onboarding_kickoff_id": "ONB-1",
        "avatar_video_url": "https://example.test/avatar.mp4",
        "day1_calendar_id": "MS-INV-1",
        "provisioning_steps": ["JML ticket SN-1234 raised"],
    })
    assert result["ok"] is True


def test_validate_activity_rejects_invalid() -> None:
    from function_app import validate_segment_f_output_activity_trigger as v_act
    result = v_act({"onboarding_kickoff_id": None, "provisioning_steps": []})
    assert result["ok"] is False
    assert "errors" in result


@pytest.mark.asyncio
async def test_run_segment_f_surfaces_tool_call_summary(monkeypatch):
    """Verifies _raw_tool_calls propagates from the wrapper into
    Segment F's _tool_call_summary with correct reversibility tags."""
    monkeypatch.setenv("LLM_RUNTIME", "fake")
    from api.functions.graphs.executors.agents.runtime_fake import FakeRuntime
    FakeRuntime.canned_text = (
        '{"onboarding_kickoff_id": "ONB-1", '
        '"avatar_video_url": null, "day1_calendar_id": null, '
        '"provisioning_steps": []}'
    )
    # FakeRuntime ignores event_subscriber today, so the bridge's
    # tool_calls_collected stays empty. We monkeypatch run_agent_session
    # to return a synthetic parsed dict carrying _raw_tool_calls so the
    # _tool_call_summary mapping can be exercised in isolation.
    from api.functions.segments import hiring_f as hf

    async def _fake_run(**kwargs):
        return {
            "onboarding_kickoff_id": "ONB-1",
            "provisioning_steps": [],
            "_raw_tool_calls": [
                {"name": "graph.search_calendar", "args": "{}", "result": "[]"},
                {"name": "servicenow.create_ticket", "args": "{}", "result": "{}"},
            ],
        }

    monkeypatch.setattr(
        "api.functions.graphs.executors.agents._wrapper.run_agent_session",
        _fake_run,
    )
    out = await hf.run_segment_f({"workflow_id": "WF-1", "candidate_id": "C-1"})
    summary = out["_tool_call_summary"]
    assert {s["name"]: s["reversible"] for s in summary} == {
        "graph.search_calendar": True,
        "servicenow.create_ticket": False,
    }


def test_is_reversible_classifier():
    from api.functions.segments.hiring_f import _is_reversible
    assert _is_reversible("graph.search_users") is True
    assert _is_reversible("graph.get_user") is True
    assert _is_reversible("policy.search") is True
    assert _is_reversible("servicenow.create_ticket") is False
    assert _is_reversible("avatar.render") is False
    assert _is_reversible(None) is True
    assert _is_reversible("") is True


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


class _SegmentFStubContext:
    def __init__(
        self,
        *,
        validator_replies: list[dict] | None = None,
        segment_result: dict | None = None,
        tool_call_summary: list[dict] | None = None,
    ):
        self.instance_id = "instance-segf-1"
        self.current_utc_datetime = datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc)
        self.calls: list[tuple[str, dict]] = []
        self._validator_replies = list(validator_replies or [])
        base = segment_result or {
            "onboarding_kickoff_id": "ONB-1",
            "avatar_video_url": "https://example.test/avatar.mp4",
            "day1_calendar_id": "MS-INV-1",
            "provisioning_steps": ["JML ticket SN-1234 raised"],
        }
        if tool_call_summary is not None:
            base = {**base, "_tool_call_summary": tool_call_summary}
        self._segment_result = base

    def get_input(self):
        return {"workflow_id": "HIRE-SEGF-1"}

    def call_activity(self, name: str, payload: dict):
        self.calls.append((name, payload))
        if name == "hiring_segment_f_activity_trigger":
            return self._segment_result
        if name == "validate_segment_f_output_activity_trigger":
            if self._validator_replies:
                return self._validator_replies.pop(0)
            return {"ok": True, "output": payload}
        if name == "issue_screen_link_activity_trigger":
            return {"token": "tok-1", "portal_url": "http://x"}
        from tests.api.unit._segment_defaults import default_segment_call_activity
        default = default_segment_call_activity(name, payload)
        if default is not None:
            return default
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


def test_orchestrator_segment_f_yields_segment_activities(monkeypatch):
    """Segment F is now the only path; the per-phase onboarding activity
    has been deleted (refactor commit — drop HIRING_SEGMENT_MODE flag)."""
    ctx = _SegmentFStubContext()
    _drive(ctx)
    activities = [c[0] for c in ctx.calls]
    assert "hiring_segment_f_activity_trigger" in activities
    assert "validate_segment_f_output_activity_trigger" in activities


def test_orchestrator_segment_f_retry_on_validation_failure(monkeypatch):
    valid = {
        "onboarding_kickoff_id": "ONB-1",
        "avatar_video_url": "https://example.test/avatar.mp4",
        "day1_calendar_id": "MS-INV-1",
        "provisioning_steps": ["JML ticket SN-1234 raised"],
    }
    ctx = _SegmentFStubContext(
        validator_replies=[
            {"ok": False, "errors": ["bad provisioning"]},
            {"ok": True, "output": valid},
        ],
    )
    _drive(ctx)
    activities = [c[0] for c in ctx.calls]
    assert activities.count("hiring_segment_f_activity_trigger") == 2
    assert activities.count("validate_segment_f_output_activity_trigger") == 2


def test_orchestrator_segment_f_retry_exhaustion(monkeypatch):
    monkeypatch.setenv("SEGMENT_MAX_RETRIES", "1")
    ctx = _SegmentFStubContext(
        validator_replies=[
            {"ok": False, "errors": ["e1"]},
            {"ok": False, "errors": ["e2"]},
            {"ok": False, "errors": ["e3"]},
        ],
    )
    with pytest.raises(RuntimeError, match="Segment F validation failed after"):
        _drive(ctx)
    failure_checkpoints = [
        payload for (name, payload) in ctx.calls
        if name == "checkpoint_activity_trigger"
        and payload.get("kind") == "segment.failed"
    ]
    assert len(failure_checkpoints) == 1
    assert failure_checkpoints[0]["segment"] == "f"


def test_orchestrator_segment_f_skips_retry_after_irreversible_tool_call(monkeypatch):
    ctx = _SegmentFStubContext(
        tool_call_summary=[
            {"name": "servicenow.create_ticket", "reversible": False},
        ],
        validator_replies=[
            {"ok": False, "errors": ["invalid onboarding output"]},
        ],
    )
    with pytest.raises(RuntimeError, match="irreversible tool calls"):
        _drive(ctx)
    activities = [c[0] for c in ctx.calls]
    # Exactly one segment activity yield — no retry after irreversible.
    assert activities.count("hiring_segment_f_activity_trigger") == 1
    assert activities.count("validate_segment_f_output_activity_trigger") == 1
    irrev_checkpoints = [
        payload for (name, payload) in ctx.calls
        if name == "checkpoint_activity_trigger"
        and payload.get("kind") == "segment.failed.irreversible"
    ]
    assert len(irrev_checkpoints) == 1
    assert irrev_checkpoints[0]["segment"] == "f"
    assert irrev_checkpoints[0]["irreversible_tools"] == ["servicenow.create_ticket"]
