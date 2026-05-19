"""Recommender executor — wraps run_agent_session with the right prompt
shape and returns the parsed JSON. We mock the wrapper so the test doesn't
spin up a GHCP session."""
from unittest.mock import patch, AsyncMock
import pytest

from api.functions.graphs.executors.agents import agent_interview_recommender


@pytest.mark.asyncio
async def test_executor_passes_gate_and_role_in_prompt():
    parsed = {
        "decision": "advance",
        "level_suggestion": None,
        "rationale": "Voice transcript shows depth on Spark.",
        "talking_points": ["pipeline ownership"],
    }
    with patch.object(
        agent_interview_recommender, "run_agent_session",
        new=AsyncMock(return_value=parsed),
    ) as mock:
        out = await agent_interview_recommender.execute({
            "gate": "post_voice",
            "role_title": "Senior Data Engineer",
            "role_jurisdiction": "USA",
            "workflow_id": "WF-1",
            "cv_crystalliser": {"name": "X", "current_title": {"value": "DE"}},
            "screening": {"verdict": "green", "rationale": "ok"},
            "voice_transcript": [{"role": "agent", "text": "hi", "ts": 0.0}],
            "voice_score": 7.5,
        })

    assert out == {"interview_recommender": parsed}
    call = mock.call_args
    prompt = call.kwargs["prompt"]
    # Must declare which gate so the skill picks the right behaviour
    assert "gate=post_voice" in prompt or '"gate": "post_voice"' in prompt
    # Must include the role title so the agent knows the level ladder
    assert "Senior Data Engineer" in prompt
    # Must pass the levels list so the agent can validate level_suggestion
    assert "Mid-Level" in prompt and "Principal" in prompt
    # Skill label drives the agent_reasoning filter on the recruiter UI
    assert call.kwargs["skill_label"] == "interview_recommender"


@pytest.mark.asyncio
async def test_executor_returns_empty_payload_when_no_workflow():
    """No workflow_id → agent shouldn't run (matches cv_crystalliser pattern)."""
    out = await agent_interview_recommender.execute({"gate": "post_voice"})
    assert out == {"interview_recommender": None}


@pytest.mark.asyncio
async def test_executor_handles_parse_error_gracefully():
    """When the wrapper returns parse_error, executor returns a structured
    failure instead of bubbling — recruiter UI shows "rec unavailable"."""
    with patch.object(
        agent_interview_recommender, "run_agent_session",
        new=AsyncMock(return_value={"raw": "blah", "parse_error": True}),
    ):
        out = await agent_interview_recommender.execute({
            "gate": "post_voice",
            "workflow_id": "WF-1",
            "role_title": "Senior Data Engineer",
        })
    rec = out["interview_recommender"]
    assert rec["decision"] == "advance"
    assert rec["recommender_status"] == "failed"


@pytest.mark.asyncio
async def test_build_prompt_includes_lessons_and_working_notes() -> None:
    prompt = agent_interview_recommender._build_prompt({
        "gate": "post_voice",
        "role_title": "Engineer",
        "lessons": ["candidates with tenure < 2y targeting L6 should be re-screened"],
        "working_notes": ["screening flagged employment-date inconsistency"],
    })
    assert "tenure < 2y" in prompt
    assert "employment-date inconsistency" in prompt

    prompt_no_lessons = agent_interview_recommender._build_prompt({
        "gate": "post_voice",
        "role_title": "Engineer",
    })
    prompt_empty_lessons = agent_interview_recommender._build_prompt({
        "gate": "post_voice",
        "role_title": "Engineer",
        "lessons": [],
        "working_notes": [],
    })
    assert prompt_no_lessons == prompt_empty_lessons


@pytest.mark.asyncio
async def test_executor_passes_lessons_to_prompt() -> None:
    parsed = {
        "decision": "advance",
        "level_suggestion": None,
        "rationale": "Voice transcript shows depth on Spark.",
        "talking_points": ["pipeline ownership"],
    }
    with patch.object(
        agent_interview_recommender, "run_agent_session",
        new=AsyncMock(return_value=parsed),
    ) as mock:
        await agent_interview_recommender.execute({
            "gate": "post_voice",
            "role_title": "Senior Data Engineer",
            "role_jurisdiction": "USA",
            "workflow_id": "WF-1",
            "lessons": ["flag inconsistent dates before advancing"],
            "working_notes": ["candidate has overlapping employment dates"],
        })

    prompt = mock.call_args.kwargs["prompt"]
    assert "flag inconsistent dates" in prompt
    assert "overlapping employment dates" in prompt
