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
