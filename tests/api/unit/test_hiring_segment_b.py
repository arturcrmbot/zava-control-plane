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
