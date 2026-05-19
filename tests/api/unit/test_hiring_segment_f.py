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
