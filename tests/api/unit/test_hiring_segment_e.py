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
