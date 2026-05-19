"""Regression: segment validator activity triggers must return JSON-
serializable dicts so Azure Durable Functions can persist them as
activity outputs.

Reproduces the runtime failure surfaced by a real GHCP-driven hiring
run (instance 4a31f099…), where `pydantic.ValidationError.errors()`
returned dicts containing native `ValueError` objects under
`ctx.error`, and the Functions host blew up with:

    ValueError: activity trigger output must be json serializable
    ({'ok': False, 'errors': [{'type': 'value_error', ...,
      'ctx': {'error': ValueError('candidates: at least one required')}, ...}]})
"""
from __future__ import annotations

import json
import os

os.environ["AZURE_STORAGE_CONNECTION_STRING"] = ""

import pytest


@pytest.mark.parametrize(
    "validator_name,bad_payload",
    [
        (
            "validate_segment_b_output_activity_trigger",
            {
                "verdict": "strong",
                "jd_draft_id": "x",
                "sourcing_pool_id": "y",
                "candidates": [],
                "rationale": "z",
            },
        ),
        (
            "validate_segment_d_output_activity_trigger",
            {"decision": "BOGUS"},
        ),
        (
            "validate_segment_e_output_activity_trigger",
            {"offer_letter_id": None},
        ),
        (
            "validate_segment_f_output_activity_trigger",
            {"onboarding_kickoff_id": None, "provisioning_steps": []},
        ),
    ],
)
def test_rejected_validator_output_is_json_serializable(
    validator_name: str, bad_payload: dict
) -> None:
    import function_app

    validator = getattr(function_app, validator_name)
    result = validator(bad_payload)
    assert result["ok"] is False
    assert "errors" in result
    json.dumps(result)
