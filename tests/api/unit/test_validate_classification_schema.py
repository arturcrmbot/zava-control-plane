"""validate_classification_schema tests."""
from __future__ import annotations
import pytest

from api.functions.graphs.executors.validators import validate_classification_schema as v


def test_valid_payload_passes():
    v.validate({
        "verdict": "amber",
        "policy_clause": "§3.1 Meals — UK per-attendee cap £75",
        "reasoning": "Within 110% of per-attendee cap.",
        "confidence": 0.7,
        "competing_interpretations": [],
    })


def test_missing_verdict_raises():
    with pytest.raises(v.ClassificationSchemaError):
        v.validate({"policy_clause": "§1", "reasoning": "x", "confidence": 0.5, "competing_interpretations": []})


def test_invalid_verdict_raises():
    with pytest.raises(v.ClassificationSchemaError):
        v.validate({
            "verdict": "yellow",
            "policy_clause": "§1", "reasoning": "x", "confidence": 0.5, "competing_interpretations": [],
        })


def test_policy_clause_must_start_with_section_marker():
    with pytest.raises(v.ClassificationSchemaError):
        v.validate({
            "verdict": "green",
            "policy_clause": "Meals UK", "reasoning": "x", "confidence": 0.5, "competing_interpretations": [],
        })


def test_parse_error_payload_raises():
    with pytest.raises(v.ClassificationSchemaError, match="parse_error"):
        v.validate({"raw": "...", "parse_error": True})


def test_confidence_out_of_range_raises():
    with pytest.raises(v.ClassificationSchemaError):
        v.validate({
            "verdict": "amber", "policy_clause": "§1", "reasoning": "x",
            "confidence": 1.5, "competing_interpretations": [],
        })
