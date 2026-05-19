"""Phase 4 of plan/refactor-substrate-agentic-segments-1.md."""
from __future__ import annotations
import os
os.environ["AZURE_STORAGE_CONNECTION_STRING"] = ""

import pytest
from pydantic import ValidationError


def test_segment_d_output_accepts_valid() -> None:
    from api.functions.segments.hiring_d import SegmentDOutput
    out = SegmentDOutput.model_validate({
        "decision": "advance",
        "interview_recommendation": {"format": "panel", "level": "senior"},
        "rationale": "strong screen signals",
    })
    assert out.decision == "advance"


@pytest.mark.parametrize("bad", [
    {"decision": "MAYBE", "interview_recommendation": {}, "rationale": "x"},
    {"interview_recommendation": {}, "rationale": "x"},
    {"decision": "advance", "rationale": "x"},
])
def test_segment_d_output_rejects(bad: dict) -> None:
    from api.functions.segments.hiring_d import SegmentDOutput
    with pytest.raises(ValidationError):
        SegmentDOutput.model_validate(bad)


@pytest.mark.asyncio
async def test_run_segment_d_with_fake_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_RUNTIME", "fake")
    from api.functions.graphs.executors.agents.runtime_fake import FakeRuntime
    FakeRuntime.canned_text = (
        '{"decision": "advance", '
        '"interview_recommendation": {"format": "panel", "level": "senior"}, '
        '"rationale": "ok"}'
    )
    from api.functions.segments.hiring_d import run_segment_d, SegmentDOutput
    out = await run_segment_d({"workflow_id": "WF-1", "candidate_id": "C-1"})
    parsed = SegmentDOutput.model_validate(out)
    assert parsed.decision == "advance"


def test_validate_activity_accepts_valid_output() -> None:
    """Plain Python call to the validator activity's body."""
    from function_app import validate_segment_d_output_activity_trigger as v_act
    result = v_act({
        "decision": "advance",
        "interview_recommendation": {"format": "panel", "level": "senior"},
        "rationale": "ok",
    })
    assert result["ok"] is True


def test_validate_activity_rejects_invalid() -> None:
    from function_app import validate_segment_d_output_activity_trigger as v_act
    result = v_act({"decision": "MAYBE"})
    assert result["ok"] is False
    assert "errors" in result
