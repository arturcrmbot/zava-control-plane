from __future__ import annotations

import json
import re
from pathlib import Path

from verticals.telco.agents import TELCO_AGENTS
from verticals.telco.process_profiles import (
    SKILL_NAMES,
    STANDARD_PROCESS_PROFILES,
)


SKILL_ROOT = Path(__file__).resolve().parents[3] / "verticals" / "telco" / "skills"
EXPECTED_OUTPUT_KEYS = {
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


def _example(skill_name: str) -> dict:
    text = (SKILL_ROOT / skill_name / "SKILL.md").read_text(encoding="utf-8")
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    assert match is not None, f"{skill_name} has no JSON example"
    return json.loads(match.group(1))


def test_eight_reusable_skills_exist_and_are_registered():
    assert set(EXPECTED_OUTPUT_KEYS) == SKILL_NAMES
    assert SKILL_NAMES <= set(TELCO_AGENTS)
    for skill_name in SKILL_NAMES:
        assert (SKILL_ROOT / skill_name / "SKILL.md").is_file()


def test_skill_examples_define_exact_output_contracts():
    for skill_name, expected_keys in EXPECTED_OUTPUT_KEYS.items():
        assert set(_example(skill_name)) == expected_keys


def test_every_standard_profile_skill_is_registered():
    for profile in STANDARD_PROCESS_PROFILES.values():
        assert set(profile.skills) <= set(TELCO_AGENTS)


def test_reusable_skills_are_reversible_shared_agents():
    for skill_name in SKILL_NAMES:
        agent = TELCO_AGENTS[skill_name]
        assert agent.scope_function == "shared"
        assert agent.reversible_only is True
        assert agent.allowed_tools
