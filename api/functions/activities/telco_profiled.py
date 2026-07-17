from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from verticals.telco.agents import TELCO_AGENTS
from verticals.telco.mcp_tools.registry import TOOL_BY_NAME
from verticals.telco.process_profiles import STANDARD_PROCESS_PROFILES


_SKILL_ROOT = (
    Path(__file__).resolve().parents[3] / "verticals" / "telco" / "skills"
)

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


async def run_agent_session(prompt: str, **kwargs) -> dict[str, Any]:
    from api.functions.graphs.executors.agents._wrapper import (
        run_agent_session as run,
    )

    return await run(prompt, **kwargs)


def _case(payload: dict[str, Any]) -> dict[str, Any]:
    observation = payload.get("observation")
    if not isinstance(observation, dict):
        raise ValueError("observation must be an object")
    case = observation.get("case")
    if not isinstance(case, dict):
        raise ValueError("observation.case must be an object")
    return case


def _deterministic_skill(payload: dict[str, Any]) -> dict[str, Any]:
    skill = str(payload["skill"])
    profile = STANDARD_PROCESS_PROFILES[str(payload["type"])]
    case = _case(payload)
    subject_ids = [str(value) for value in case.get("subject_ids") or []]
    facts = case.get("facts") if isinstance(case.get("facts"), dict) else {}
    risk_score = float(facts.get("risk_score") or 0.75)
    if skill == "evidence-correlator":
        return {
            "evidence_groups": [
                {
                    "group_id": f"group-{case['id']}",
                    "actor_ids": subject_ids,
                    "event_ids": list(
                        payload.get("observation", {}).get("event_ids") or []
                    ),
                }
            ],
            "causal_links": [],
            "confidence": 0.8,
            "reasoning": "The supplied actors belong to one process case.",
        }
    if skill == "risk-impact-assessor":
        return {
            "risk_tier": "high" if risk_score >= 0.7 else "medium",
            "impact_score": risk_score,
            "affected_actor_ids": subject_ids,
            "uncertainty": "Bounded to supplied process-case evidence.",
            "reasoning": "Risk follows the supplied case score and actors.",
        }
    if skill == "next-best-action-planner":
        return {
            "ranked_actions": [
                {"action": profile.command_type, "score": 1.0}
            ],
            "selected_action": profile.command_type,
            "reasoning": "The profile command is the declared feasible action.",
        }
    if skill == "resource-matcher":
        return {
            "assignments": [
                {
                    "requirement": profile.workflow_type,
                    "resource_ids": subject_ids,
                }
            ],
            "unmet_constraints": [],
            "reasoning": "Supplied subject actors satisfy the reference case.",
        }
    if skill == "policy-entitlement-evaluator":
        return {
            "eligible": True,
            "entitlement": {
                "kind": profile.command_type,
                "value": float(facts.get("value") or 0.0),
            },
            "requires_approval": profile.hitl_persona is not None,
            "policy_refs": [f"TELCO-{profile.source_id}"],
            "reasoning": "The reference case satisfies its declared policy.",
        }
    if skill == "exception-resolution-advisor":
        return {
            "root_cause": "process-case-evidence",
            "resolution_steps": [
                {
                    "action": profile.command_type,
                    "actor_ids": subject_ids,
                }
            ],
            "escalation_required": profile.hitl_persona is not None,
            "reasoning": "The declared action resolves the reference case.",
        }
    if skill == "communication-drafter":
        return {
            "channel": "digital",
            "audience_ids": subject_ids,
            "message": (
                f"{profile.display_name} is being handled under the "
                "declared process policy."
            ),
            "reasoning": "The message states only current process status.",
        }
    if skill == "scenario-comparator":
        scenario_id = f"SCN-{profile.source_id}"
        return {
            "scenarios": [{"scenario_id": scenario_id, "score": 1.0}],
            "recommended_scenario": scenario_id,
            "tradeoffs": ["Reference path optimises the declared objective."],
            "reasoning": "The reference scenario is feasible and bounded.",
        }
    raise ValueError(f"unsupported reusable skill: {skill!r}")


async def _live_skill(payload: dict[str, Any]) -> dict[str, Any]:
    skill = str(payload["skill"])
    profile = STANDARD_PROCESS_PROFILES[str(payload["type"])]
    agent = TELCO_AGENTS[skill]
    tool_names = [
        name
        for name in profile.allowed_tools
        if name in agent.allowed_tools and name in TOOL_BY_NAME
    ]
    prompt = (
        "Return one JSON object only using supplied simulated evidence. "
        "Do not invent actor, event, action or policy IDs.\n"
        f"workflow_type={profile.workflow_type}\n"
        f"skill={skill}\n"
        f"allowed_actions={json.dumps([profile.command_type])}\n"
        f"observation={json.dumps(payload.get('observation') or {}, sort_keys=True)}\n"
        f"prior_outputs={json.dumps(payload.get('prior_outputs') or {}, sort_keys=True)}"
    )
    result = await run_agent_session(
        prompt,
        tools=[TOOL_BY_NAME[name] for name in tool_names],
        skill_dir=_SKILL_ROOT / skill,
        skill_label=skill,
        workflow_id=payload.get("workflow_id"),
    )
    return result


def _validate_skill_output(skill: str, result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError(f"{skill} response must be an object")
    expected = SKILL_OUTPUT_KEYS[skill]
    if set(result) != expected:
        raise ValueError(
            f"{skill} response keys must be {sorted(expected)}"
        )
    return result


def telco_profile_skill_activity(
    payload: dict[str, Any],
) -> dict[str, Any]:
    skill = str(payload.get("skill") or "")
    if skill not in SKILL_OUTPUT_KEYS:
        raise ValueError(f"unknown reusable skill: {skill!r}")
    mode = payload.get("agent_mode") or os.environ.get(
        "ZAVA_TELCO_AGENT_MODE",
        "live",
    )
    if mode == "deterministic":
        result = _deterministic_skill(payload)
    elif mode == "live":
        result = asyncio.run(_live_skill(payload))
    else:
        raise ValueError(f"unsupported agent_mode: {mode!r}")
    return _validate_skill_output(skill, result)


def telco_profile_command_activity(
    payload: dict[str, Any],
) -> dict[str, Any]:
    profile = STANDARD_PROCESS_PROFILES[str(payload["type"])]
    case = _case(payload)
    allowed_actions = case.get("allowed_actions") or []
    if profile.command_type not in allowed_actions:
        raise ValueError(
            f"action {profile.command_type!r} is not allowed by case"
        )
    approval = payload.get("approval") or {"decision": "not_required"}
    if (
        profile.hitl_persona is not None
        and approval.get("decision") != "approve"
    ):
        raise ValueError(f"{profile.hitl_event} approval is required")
    trace_id = str(payload["trace_id"])
    subject_ids = [str(value) for value in case.get("subject_ids") or []]
    command = {
        "command_id": f"cmd-{trace_id}-{profile.command_type}",
        "trace_id": trace_id,
        "issued_by": profile.function.replace("-", "_"),
        "type": profile.command_type,
        "payload": {
            "case_id": str(case["id"]),
            "subject_ids": subject_ids,
            "action": profile.command_type,
            "skill_outputs": dict(payload.get("skill_outputs") or {}),
            "approval_decision": approval.get("decision"),
        },
    }
    return {
        "command": command,
        "reasoning": f"Prepared {profile.display_name} reference action.",
    }
