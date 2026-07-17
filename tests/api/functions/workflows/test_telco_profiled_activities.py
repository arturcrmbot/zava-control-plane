from __future__ import annotations

from api.functions.activities.telco_profiled import (
    telco_profile_command_activity,
    telco_profile_skill_activity,
)
from verticals.telco.process_profiles import STANDARD_PROCESS_PROFILES


SKILL_OUTPUT_KEYS = {
    "evidence-correlator": {
        "evidence_groups",
        "causal_links",
        "confidence",
        "reasoning",
    },
    "risk-impact-assessor": {
        "risk_tier",
        "impact_score",
        "affected_actor_ids",
        "uncertainty",
        "reasoning",
    },
    "next-best-action-planner": {
        "ranked_actions",
        "selected_action",
        "reasoning",
    },
    "resource-matcher": {
        "assignments",
        "unmet_constraints",
        "reasoning",
    },
    "policy-entitlement-evaluator": {
        "eligible",
        "entitlement",
        "requires_approval",
        "policy_refs",
        "reasoning",
    },
    "exception-resolution-advisor": {
        "root_cause",
        "resolution_steps",
        "escalation_required",
        "reasoning",
    },
    "communication-drafter": {
        "channel",
        "audience_ids",
        "message",
        "reasoning",
    },
    "scenario-comparator": {
        "scenarios",
        "recommended_scenario",
        "tradeoffs",
        "reasoning",
    },
}


def _payload(workflow_type: str, skill: str) -> dict:
    profile = STANDARD_PROCESS_PROFILES[workflow_type]
    return {
        "agent_mode": "deterministic",
        "workflow_id": f"WF-{workflow_type}",
        "trace_id": f"trace-{workflow_type}",
        "type": workflow_type,
        "skill": skill,
        "observation": {
            "case": {
                "id": "CASE-001",
                "subject_ids": ["ACTOR-1"],
                "facts": {"risk_score": 0.8},
                "allowed_actions": [profile.command_type],
            }
        },
        "prior_outputs": {},
    }


def test_deterministic_mode_returns_each_strict_skill_contract():
    for skill, expected_keys in SKILL_OUTPUT_KEYS.items():
        workflow_type = next(
            profile.workflow_type
            for profile in STANDARD_PROCESS_PROFILES.values()
            if skill in profile.skills
        )
        result = telco_profile_skill_activity(_payload(workflow_type, skill))
        assert set(result) == expected_keys


def test_command_activity_returns_profile_typed_command():
    profile = STANDARD_PROCESS_PROFILES["contact-centre-agent-assist"]
    result = telco_profile_command_activity(
        {
            "workflow_id": "WF-CONTACT",
            "trace_id": "trace-contact",
            "type": profile.workflow_type,
            "observation": {
                "case": {
                    "id": "CASE-001",
                    "subject_ids": ["ACC-00001"],
                    "allowed_actions": [profile.command_type],
                }
            },
            "skill_outputs": {"evidence-correlator": {"confidence": 0.8}},
            "approval": {"decision": "not_required"},
        }
    )

    command = result["command"]
    assert command["type"] == profile.command_type
    assert command["trace_id"] == "trace-contact"
    assert command["issued_by"] == "customer_success"
    assert command["payload"]["case_id"] == "CASE-001"
    assert command["payload"]["subject_ids"] == ["ACC-00001"]


def test_command_activity_rejects_case_without_profile_action():
    profile = STANDARD_PROCESS_PROFILES["contact-centre-agent-assist"]

    try:
        telco_profile_command_activity(
            {
                "workflow_id": "WF-CONTACT",
                "trace_id": "trace-contact",
                "type": profile.workflow_type,
                "observation": {
                    "case": {
                        "id": "CASE-001",
                        "subject_ids": ["ACC-00001"],
                        "allowed_actions": ["different_action"],
                    }
                },
                "skill_outputs": {},
                "approval": {"decision": "not_required"},
            }
        )
    except ValueError as error:
        assert "not allowed" in str(error)
    else:
        raise AssertionError("expected invalid action to be rejected")
