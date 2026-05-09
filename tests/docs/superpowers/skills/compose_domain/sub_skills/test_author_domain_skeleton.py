"""Tests for author-domain-skeleton validator (TASK-008)."""
from __future__ import annotations

import copy

import pytest


@pytest.fixture
def skeleton():
    return {
        "domain": {
            "workflow_type": "vendor-kyc",
            "prefix": "fleet",
            "display_name": "Vendor KYC",
        },
        "phases": [
            {"name": "intake", "kind": "deterministic"},
            {"name": "diligence", "kind": "agent", "agent_skill_name": "x"},
            {
                "name": "signoff",
                "kind": "hitl",
                "persona": "vendor_kyc_finance_bp",
                "external_event": "finance_signoff_decision",
            },
        ],
    }


@pytest.fixture
def validator(sub_skill_loader):
    return sub_skill_loader("author-domain-skeleton", "validator")


def test_clean_skeleton_validates(validator, skeleton):
    validator.validate(skeleton)


def test_missing_workflow_type_raises(validator, skeleton):
    skeleton["domain"].pop("workflow_type")
    with pytest.raises(validator.SchemaError) as exc:
        validator.validate(skeleton)
    assert exc.value.path.startswith("domain")


def test_unknown_phase_kind_raises(validator, skeleton):
    skeleton["phases"][0]["kind"] = "wat"
    with pytest.raises(validator.SchemaError) as exc:
        validator.validate(skeleton)
    assert exc.value.path.startswith("phases[0].kind")


def test_hitl_without_persona_raises(validator, skeleton):
    skeleton["phases"][-1].pop("persona")
    with pytest.raises(validator.SchemaError) as exc:
        validator.validate(skeleton)
    assert "persona" in exc.value.path


def test_hitl_without_external_event_raises(validator, skeleton):
    skeleton["phases"][-1].pop("external_event")
    with pytest.raises(validator.SchemaError) as exc:
        validator.validate(skeleton)
    assert "external_event" in exc.value.path


def test_no_hitl_raises(validator, skeleton):
    skeleton["phases"] = [p for p in skeleton["phases"] if p["kind"] != "hitl"]
    with pytest.raises(validator.SchemaError) as exc:
        validator.validate(skeleton)
    assert "hitl" in exc.value.reason


def test_no_deterministic_raises(validator, skeleton):
    skeleton["phases"][0]["kind"] = "agent"
    skeleton["phases"][0]["agent_skill_name"] = "stub"
    with pytest.raises(validator.SchemaError) as exc:
        validator.validate(skeleton)
    assert "deterministic" in exc.value.reason


def test_empty_phases_raises(validator, skeleton):
    skeleton["phases"] = []
    with pytest.raises(validator.SchemaError) as exc:
        validator.validate(skeleton)
    # Either jsonschema (minItems:1) or our semantic check fires.
    assert "phases" in exc.value.path
