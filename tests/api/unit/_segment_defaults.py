"""Shared default segment activity / validator stubs used by the four
test_hiring_segment_*.py stubs and by test_hiring_voice_phase.py.

Background — refactor commit ("drop HIRING_SEGMENT_MODE flag") made
the four segment activities (B/D/E/F) the only hiring path. Every
orchestrator-driving test now drives through all four segments, even
when the test is focused on only one. The non-focal segments need
schema-valid defaults so the orchestrator can complete instead of
exhausting its retry budget on a missing field.

`default_segment_call_activity(name, payload)` covers the eight
segment-related activity names (4 segment triggers + 4 validators)
and returns None for everything else, letting the per-test stub
keep its own dispatch table for non-segment activities.
"""
from __future__ import annotations

_DEFAULT_SEGMENT_OUTPUTS: dict[str, dict] = {
    "hiring_segment_b_activity_trigger": {
        "verdict": "strong",
        "jd_draft_id": "JD-DEFAULT",
        "sourcing_pool_id": "POOL-DEFAULT",
        "candidates": [{"id": "C-DEFAULT", "score": 0.9, "rationale": "ok"}],
        "rationale": "default",
    },
    "hiring_segment_d_activity_trigger": {
        "decision": "advance",
        "interview_recommendation": {"format": "panel", "level": "senior"},
        "rationale": "default",
    },
    "hiring_segment_e_activity_trigger": {
        "offer_letter_id": "OFFER-DEFAULT",
        "jurisdiction": "USA",
        "compliance_steps": [],
        "policy_citations": [],
    },
    "hiring_segment_f_activity_trigger": {
        "onboarding_kickoff_id": "ONB-DEFAULT",
        "avatar_video_url": None,
        "day1_calendar_id": None,
        "provisioning_steps": [],
    },
}

_VALIDATORS: set[str] = {
    "validate_segment_b_output_activity_trigger",
    "validate_segment_d_output_activity_trigger",
    "validate_segment_e_output_activity_trigger",
    "validate_segment_f_output_activity_trigger",
}


def default_segment_call_activity(name: str, payload: dict):
    """Return a schema-valid default for any segment activity / validator
    the per-test stub doesn't itself dispatch. Returns None otherwise."""
    if name in _DEFAULT_SEGMENT_OUTPUTS:
        return dict(_DEFAULT_SEGMENT_OUTPUTS[name])
    if name in _VALIDATORS:
        return {"ok": True, "output": payload}
    return None
