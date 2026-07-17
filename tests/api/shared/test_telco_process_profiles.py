from __future__ import annotations

import pytest

from verticals.telco.process_profiles import (
    ENGINE_CODES,
    SKILL_NAMES,
    STANDARD_PROCESS_PROFILES,
    TOOLS_BY_PACK,
    validate_process_profiles,
)


EXPECTED_STANDARD_WORKFLOWS = {
    "ran-capacity-planning",
    "network-configuration-validation",
    "rollout-site-planning",
    "network-slice-assurance",
    "energy-optimization",
    "spares-inventory-optimization",
    "site-asset-health-monitoring",
    "backhaul-optimization",
    "core-network-anomaly-management",
    "proactive-service-assurance",
    "network-change-release",
    "spectrum-interference-management",
    "network-security-response",
    "experience-benchmarking",
    "contact-centre-agent-assist",
    "autonomous-self-service",
    "next-best-action",
    "service-provisioning-activation",
    "billing-dispute-resolution",
    "revenue-assurance",
    "collections-dunning",
    "fraud-prevention",
    "customer-onboarding-kyc",
    "complaint-nps-closed-loop",
    "device-lifecycle-upgrade",
    "roaming-experience-steering",
    "number-sim-porting",
    "customer-experience-twin",
}


def test_standard_profile_inventory_is_complete_and_unique():
    profiles = STANDARD_PROCESS_PROFILES

    assert set(profiles) == EXPECTED_STANDARD_WORKFLOWS
    assert len(profiles) == 28
    assert len({profile.source_id for profile in profiles.values()}) == 28
    assert len({profile.sensor_id for profile in profiles.values()}) == 28
    assert len({profile.command_type for profile in profiles.values()}) == 28
    assert len({profile.success_event for profile in profiles.values()}) == 28
    assert {profile.engine for profile in profiles.values()} == ENGINE_CODES


def test_every_profile_uses_reusable_skills_and_mcp_tools():
    all_tools = {
        tool for tools in TOOLS_BY_PACK.values() for tool in tools
    }

    for profile in STANDARD_PROCESS_PROFILES.values():
        assert profile.skills
        assert set(profile.skills) <= SKILL_NAMES
        assert profile.mcp_packs
        assert profile.allowed_tools
        assert set(profile.allowed_tools) <= all_tools
        assert any(phase.kind == "agent" for phase in profile.phases)
        assert {
            phase.skill for phase in profile.phases if phase.kind == "agent"
        } == set(profile.skills)


def test_hitl_metadata_is_complete_when_present():
    for profile in STANDARD_PROCESS_PROFILES.values():
        hitl_phases = [
            phase for phase in profile.phases if phase.kind == "hitl"
        ]
        if profile.hitl_persona is None:
            assert profile.hitl_event is None
            assert hitl_phases == []
        else:
            assert profile.hitl_event == f"{profile.hitl_persona}_decision"
            assert len(hitl_phases) == 1


def test_profile_validation_rejects_key_mismatch():
    profile = next(iter(STANDARD_PROCESS_PROFILES.values()))

    with pytest.raises(ValueError, match="profile key mismatch"):
        validate_process_profiles({"wrong-key": profile})
