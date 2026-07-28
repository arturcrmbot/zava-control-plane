from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from copilot.tools import ToolInvocation

from verticals.airline.mcp_tools import operations


def _invocation(tool_name: str, arguments: dict[str, Any]) -> ToolInvocation:
    return ToolInvocation(
        session_id="airline-test",
        tool_call_id=f"tool-{tool_name}",
        tool_name=tool_name,
        arguments=arguments,
    )


def _admitted_options() -> list[dict[str, Any]]:
    return [
        {
            "option_id": "SYN-OPTION-TAIL-CREW-STAND",
            "impact": "material",
            "value_gbp": 75_000.0,
            "actions": [
                {
                    "action_type": "assign_aircraft",
                    "sector_id": "SYN-SECTOR-OUT-001",
                    "resource_id": "SYN-TAIL-005",
                    "minutes": None,
                }
            ],
            "evidence_versions": {"SYN-SECTOR-OUT-001": 2},
            "feasible": True,
        },
        {
            "option_id": "SYN-OPTION-CANCEL",
            "impact": "high",
            "value_gbp": 145_000.0,
            "actions": [
                {
                    "action_type": "cancel_sector",
                    "sector_id": "SYN-SECTOR-OUT-001",
                    "resource_id": None,
                    "minutes": None,
                }
            ],
            "evidence_versions": {"SYN-SECTOR-OUT-001": 2},
            "feasible": True,
        },
    ]


@pytest.mark.asyncio
async def test_tools_return_only_versioned_simulated_evidence() -> None:
    result = await operations.airline_read_disruption_evidence.handler(
        ToolInvocation(
            session_id="airline-test",
            tool_call_id="tool-1",
            tool_name="airline_read_disruption_evidence",
            arguments={
                "observation": {
                    "story_id": "SYN-STORY-HUB-001",
                    "actor_ids": ["SYN-SECTOR-IN-001"],
                    "event_ids": ["evt-00000042"],
                    "evidence_versions": {"SYN-SECTOR-IN-001": 2},
                }
            },
        )
    )
    payload = json.loads(result.text_result_for_llm)
    assert payload["source_mode"] == "simulated"
    assert payload["story_id"] == "SYN-STORY-HUB-001"
    assert payload["actor_ids"] == ["SYN-SECTOR-IN-001"]
    assert "recommended_action" not in payload


def test_pack_declares_exact_agent_tools() -> None:
    assert {
        operations.airline_read_disruption_evidence.name,
        operations.airline_rank_feasible_recovery_options.name,
    } == operations.TOOL_NAMES
    assert operations.TOOL_NAMES == {
        "airline_read_disruption_evidence",
        "airline_rank_feasible_recovery_options",
    }


@pytest.mark.asyncio
async def test_evidence_tool_preserves_versioned_event_identity_without_mutation() -> None:
    observation = {
        "story_id": "SYN-STORY-HUB-001",
        "actor_ids": ["SYN-TAIL-001", "SYN-ROTATION-01"],
        "event_ids": ["evt-00000041", "evt-00000042"],
        "evidence_versions": {"SYN-TAIL-001": 4, "SYN-ROTATION-01": 7},
        "evidence": {
            "aircraft": {"id": "SYN-TAIL-001", "status": "delayed"},
            "connection_cohorts": [{"id": "SYN-COHORT-001", "at_risk": 22}],
        },
    }
    before = copy.deepcopy(observation)

    result = await operations.airline_read_disruption_evidence.handler(
        _invocation(
            "airline_read_disruption_evidence",
            {"observation": observation},
        )
    )
    payload = json.loads(result.text_result_for_llm)

    assert result.result_type == "success"
    assert observation == before
    assert payload == {"source_mode": "simulated", **before}
    assert "live" not in result.text_result_for_llm.lower()
    assert set(payload["actor_ids"]) == set(before["actor_ids"])
    assert set(payload["event_ids"]) == set(before["event_ids"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "observation",
    [
        {
            "story_id": "SYN-STORY-HUB-001",
            "actor_ids": ["SYN-SECTOR-IN-001"],
            "evidence_versions": {"SYN-SECTOR-IN-001": 2},
        },
        {
            "story_id": "SYN-STORY-HUB-001",
            "actor_ids": "SYN-SECTOR-IN-001",
            "event_ids": ["evt-00000042"],
            "evidence_versions": {"SYN-SECTOR-IN-001": 2},
        },
        {
            "story_id": "SYN-STORY-HUB-001",
            "actor_ids": ["SYN-SECTOR-IN-001"],
            "event_ids": ["evt-00000042"],
            "evidence_versions": {"SYN-SECTOR-IN-001": True},
        },
        {
            "story_id": "SYN-STORY-HUB-001",
            "actor_ids": ["SYN-SECTOR-IN-001"],
            "event_ids": ["evt-00000042"],
            "evidence_versions": {"SYN-SECTOR-IN-001": 2},
            "recommended_action": "cancel",
        },
    ],
)
async def test_evidence_tool_fails_explicitly_for_invalid_shapes(
    observation: dict[str, Any],
) -> None:
    result = await operations.airline_read_disruption_evidence.handler(
        _invocation(
            "airline_read_disruption_evidence",
            {"observation": observation},
        )
    )

    assert result.result_type == "failure"
    assert result.error
    assert "error" in result.text_result_for_llm.lower()


@pytest.mark.asyncio
async def test_ranking_tool_returns_every_admitted_option_exactly_once_unchanged() -> None:
    admitted_options = _admitted_options()
    ranking_context = {
        "story_id": "SYN-STORY-HUB-001",
        "trade_off_dimensions": ["network_recovery", "passenger_impact", "cost"],
        "no_action_comparison": {
            "delay_minutes": 390,
            "connection_cohorts_at_risk": 2,
        },
    }
    arguments = {
        "admitted_options": admitted_options,
        "ranking_context": ranking_context,
    }
    before = copy.deepcopy(arguments)

    result = await operations.airline_rank_feasible_recovery_options.handler(
        _invocation("airline_rank_feasible_recovery_options", arguments)
    )
    payload = json.loads(result.text_result_for_llm)

    assert result.result_type == "success"
    assert arguments == before
    assert payload == {"source_mode": "simulated", **before}
    assert [item["option_id"] for item in payload["admitted_options"]] == [
        item["option_id"] for item in admitted_options
    ]
    assert "recommended_action" not in payload
    assert "selected_option_id" not in payload


@pytest.mark.asyncio
async def test_ranking_tool_refuses_a_rejected_option() -> None:
    rejected = _admitted_options()[0]
    rejected["feasible"] = False

    result = await operations.airline_rank_feasible_recovery_options.handler(
        _invocation(
            "airline_rank_feasible_recovery_options",
            {
                "admitted_options": [rejected],
                "ranking_context": {"story_id": "SYN-STORY-HUB-001"},
            },
        )
    )

    assert result.result_type == "failure"
    assert result.error
    assert "not admitted" in result.error


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("admitted_options", "ranking_context"),
    [
        ({"option_id": "SYN-OPTION-ONE"}, {"story_id": "SYN-STORY-HUB-001"}),
        ([{"impact": "high", "actions": [], "evidence_versions": {}}], {}),
        (
            [
                {
                    "option_id": "SYN-OPTION-ONE",
                    "actions": [],
                    "evidence_versions": {"SYN-ACTOR-001": 1},
                },
                {
                    "option_id": "SYN-OPTION-ONE",
                    "actions": [],
                    "evidence_versions": {"SYN-ACTOR-001": 1},
                },
            ],
            {},
        ),
        (
            [
                {
                    "option_id": "SYN-OPTION-ONE",
                    "actions": [],
                    "evidence_versions": {"SYN-ACTOR-001": 1.5},
                }
            ],
            {},
        ),
        (_admitted_options(), ["network_recovery"]),
    ],
)
async def test_ranking_tool_fails_explicitly_for_invalid_shapes(
    admitted_options: Any,
    ranking_context: Any,
) -> None:
    result = await operations.airline_rank_feasible_recovery_options.handler(
        _invocation(
            "airline_rank_feasible_recovery_options",
            {
                "admitted_options": admitted_options,
                "ranking_context": ranking_context,
            },
        )
    )

    assert result.result_type == "failure"
    assert result.error
    assert "error" in result.text_result_for_llm.lower()


def _skill_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    match = re.fullmatch(r"---\n(.*?)\n---\n(.*)", text, flags=re.DOTALL)
    assert match is not None
    return yaml.safe_load(match.group(1)), match.group(2)


def test_agent_skills_declare_exact_pack_local_tools_and_truth_boundaries() -> None:
    root = Path(__file__).resolve().parents[3] / "verticals" / "airline" / "skills"
    expectations = {
        "network-impact-assessor": {
            "tool": "airline_read_disruption_evidence",
            "required_terms": {
                "aircraft",
                "rotation",
                "crew",
                "slot",
                "stand",
                "passenger connection cohorts",
                "actor_ids",
                "event_ids",
                "evidence_versions",
                "story_id",
                "source_mode",
                "simulated",
                "uncertainty",
                "no invented operational facts or actions",
            },
        },
        "recovery-option-ranker": {
            "tool": "airline_rank_feasible_recovery_options",
            "required_terms": {
                "only admitted option ids",
                "trade-offs",
                "uncertainty",
                "no-action comparison",
                "cannot introduce options",
                "cannot declare infeasible options feasible",
                "cannot mutate state",
                "cannot claim live data",
            },
        },
    }

    for skill_name, expected in expectations.items():
        frontmatter, body = _skill_frontmatter(root / skill_name / "SKILL.md")
        assert set(frontmatter) == {"name", "description", "allowed-tools"}
        assert frontmatter["name"] == skill_name
        allowed_tools = {frontmatter["allowed-tools"]}
        assert allowed_tools <= operations.TOOL_NAMES
        assert frontmatter["allowed-tools"] == expected["tool"]
        lowered_body = " ".join(body.lower().split())
        assert all(term in lowered_body for term in expected["required_terms"])
