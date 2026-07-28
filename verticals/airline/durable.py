from __future__ import annotations

import asyncio
import copy
import json
import math
from collections.abc import Generator
from datetime import timedelta
from pathlib import Path
from typing import Any

import azure.durable_functions as df

from api.functions.kernel_registration import create_app
from api.server.services.governance import kernel
from api.server.world.runtime import SimulationRuntime
from verticals.airline.constraints import FeasibilityResult, admit_recovery_options
from verticals.airline.mcp_tools import operations
from verticals.airline.process_profiles import (
    COMMAND_TYPE,
    HITL_EVENT,
    HITL_PERSONA,
    ORCHESTRATOR as _ORCHESTRATOR,
    SCENARIO_ID,
    STORY_ID,
    SUCCESS_EVENT,
    WORKFLOW_TYPE,
)
from verticals.airline.worlds.scenario import AirlineWorld


app = create_app()
_SKILL_ROOT = Path(__file__).resolve().parent / "skills"
_IMPACT_PHASE = "Assess Network Impact"
_RANKING_PHASE = "Synthesize Recovery Options"
_HITL_PHASE = "Approve Recovery Plan"
_IMPACT_KEYS = {"phase", "actor_ids", "event_ids", "impact_summary"}
_RANKING_KEYS = {"phase", "ranked_option_ids", "reasoning"}
ORCHESTRATOR = _ORCHESTRATOR
_PHASE_CONTRACTS = {
    _IMPACT_PHASE: (
        "network-impact-assessor",
        operations.airline_read_disruption_evidence,
    ),
    _RANKING_PHASE: (
        "recovery-option-ranker",
        operations.airline_rank_feasible_recovery_options,
    ),
}


def _required_object(value: Any, *, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _required_string(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _identity_list(value: Any, *, name: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item.strip() for item in value)
        or len(set(value)) != len(value)
    ):
        raise ValueError(f"{name} must contain unique non-empty string identities")
    return list(value)


def _evidence_versions(value: Any, *, name: str) -> dict[str, int]:
    if not isinstance(value, dict) or not value:
        raise ValueError(f"{name} must be a non-empty version map")
    versions: dict[str, int] = {}
    for actor_id, version in value.items():
        if not isinstance(actor_id, str) or not actor_id.strip():
            raise ValueError(f"{name} contains an invalid actor identity")
        if isinstance(version, bool) or not isinstance(version, int) or version < 0:
            raise ValueError(f"{name} contains an invalid version")
        versions[actor_id] = version
    return versions


def airline_evidence_activity(payload: dict[str, Any]) -> dict[str, Any]:
    workflow_id = _required_string(payload.get("workflow_id"), name="workflow_id")
    if payload.get("type") != WORKFLOW_TYPE:
        raise ValueError("Airline evidence has the wrong workflow type")
    observation = copy.deepcopy(_required_object(payload.get("observation"), name="observation"))
    if observation.get("story_id") != STORY_ID:
        raise ValueError("Airline evidence has the wrong story")
    versions = _evidence_versions(
        observation.get("evidence_versions"),
        name="observation.evidence_versions",
    )
    supplied_actor_ids = observation.get("actor_ids")
    actor_ids = (
        _identity_list(supplied_actor_ids, name="observation.actor_ids")
        if supplied_actor_ids is not None
        else list(versions)
    )
    supplied_event_ids = observation.get("event_ids")
    event_ids = _identity_list(
        (supplied_event_ids if supplied_event_ids is not None else observation.get("evidence_event_ids")),
        name="observation.event_ids",
    )
    observation["actor_ids"] = actor_ids
    observation["event_ids"] = event_ids
    observation["evidence_versions"] = versions
    return {
        "workflow_id": workflow_id,
        "story_id": STORY_ID,
        "source_mode": "simulated",
        "actor_ids": actor_ids,
        "event_ids": event_ids,
        "evidence_versions": versions,
        "observation": observation,
    }


async def run_agent_session(prompt: str, **kwargs: Any) -> dict[str, Any]:
    from api.functions.graphs.executors.agents._wrapper import (
        run_agent_session as run,
    )

    return await run(prompt, **kwargs)


def _agent_prompt(payload: dict[str, Any], phase: str, skill_label: str) -> str:
    evidence = _required_object(payload.get("evidence"), name="evidence")
    if phase == _IMPACT_PHASE:
        tool_input = {
            "observation": {
                "story_id": evidence["story_id"],
                "actor_ids": evidence["actor_ids"],
                "event_ids": evidence["event_ids"],
                "evidence_versions": evidence["evidence_versions"],
                "evidence": evidence["observation"],
            }
        }
        output_keys = sorted(_IMPACT_KEYS)
        constraints = "Preserve the supplied actor_ids and event_ids exactly. Do not recommend an action."
    else:
        admitted_options = payload.get("admitted_options")
        if not isinstance(admitted_options, list) or not admitted_options:
            raise ValueError("admitted_options must contain deterministic options")
        impact = _required_object(payload.get("impact"), name="impact")
        tool_input = {
            "admitted_options": admitted_options,
            "ranking_context": {
                "story_id": evidence["story_id"],
                "impact_summary": impact["impact_summary"],
                "evidence_versions": evidence["evidence_versions"],
                "source_mode": "simulated",
            },
        }
        output_keys = sorted(_RANKING_KEYS)
        constraints = (
            "Rank every supplied admitted option ID exactly once. "
            "Do not add, drop, duplicate, or modify an option."
        )
    return (
        "Use the one registered Airline tool before responding. "
        "Return one JSON object only, without markdown or extra keys. "
        f"Exact output keys: {json.dumps(output_keys)}. {constraints}\n"
        f"workflow_id={payload['workflow_id']}\n"
        f"phase={phase}\n"
        f"skill={skill_label}\n"
        f"source_mode=simulated\n"
        f"tool_input={json.dumps(tool_input, sort_keys=True)}"
    )


def _business_agent_output(
    result: Any,
    *,
    expected_keys: set[str],
    expected_tool_name: str,
) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError("Airline agent response must be an object")
    allowed_keys = expected_keys | {"_raw_tool_calls"}
    if not set(result) <= allowed_keys or not expected_keys <= set(result):
        raise ValueError(f"Airline agent response must contain exactly {sorted(expected_keys)} business keys")
    calls = result.get("_raw_tool_calls")
    if calls is not None:
        if not isinstance(calls, list):
            raise ValueError("Airline agent tool evidence must be a list")
        business_calls = [
            call for call in calls if isinstance(call, dict) and call.get("name") in operations.TOOL_NAMES
        ]
        if any(
            call.get("name") != expected_tool_name or call.get("success") is not True
            for call in business_calls
        ):
            raise ValueError("Airline agent used an undeclared or unsuccessful tool")
    return {key: result[key] for key in expected_keys}


def _validate_impact_output(
    payload: dict[str, Any],
    result: Any,
) -> dict[str, Any]:
    evidence = _required_object(payload.get("evidence"), name="evidence")
    output = _business_agent_output(
        result,
        expected_keys=_IMPACT_KEYS,
        expected_tool_name=operations.airline_read_disruption_evidence.name,
    )
    if output["phase"] != _IMPACT_PHASE:
        raise ValueError("Airline agent changed the impact phase")
    if output["actor_ids"] != evidence["actor_ids"]:
        raise ValueError("Airline agent changed supplied actor IDs")
    if output["event_ids"] != evidence["event_ids"]:
        raise ValueError("Airline agent changed supplied event IDs")
    if not isinstance(output["impact_summary"], str) or not output["impact_summary"].strip():
        raise ValueError("Airline agent impact_summary must be a non-empty string")
    return output


def _validate_ranking_output(
    payload: dict[str, Any],
    result: Any,
) -> dict[str, Any]:
    output = _business_agent_output(
        result,
        expected_keys=_RANKING_KEYS,
        expected_tool_name=operations.airline_rank_feasible_recovery_options.name,
    )
    if output["phase"] != _RANKING_PHASE:
        raise ValueError("Airline agent changed the ranking phase")
    admitted_options = payload.get("admitted_options")
    if not isinstance(admitted_options, list) or not admitted_options:
        raise ValueError("Airline agent ranking requires admitted options")
    admitted_ids = [option.get("option_id") for option in admitted_options]
    ranked_ids = output["ranked_option_ids"]
    if (
        not isinstance(ranked_ids, list)
        or any(not isinstance(option_id, str) for option_id in ranked_ids)
        or len(ranked_ids) != len(admitted_ids)
        or len(set(ranked_ids)) != len(ranked_ids)
        or set(ranked_ids) != set(admitted_ids)
    ):
        raise ValueError("Airline agent ranking must contain every admitted option exactly once")
    if not isinstance(output["reasoning"], str) or not output["reasoning"].strip():
        raise ValueError("Airline agent reasoning must be a non-empty string")
    return output


async def _run_airline_agent(payload: dict[str, Any]) -> dict[str, Any]:
    phase = _required_string(payload.get("phase"), name="phase")
    contract = _PHASE_CONTRACTS.get(phase)
    if contract is None:
        raise ValueError(f"unsupported Airline agent phase: {phase!r}")
    skill_label, tool = contract
    prompt = _agent_prompt(payload, phase, skill_label)
    result = await run_agent_session(
        prompt,
        tools=[tool],
        skill_dir=_SKILL_ROOT / skill_label,
        skill_label=skill_label,
        workflow_id=payload.get("workflow_id"),
        instance_id=payload.get("instance_id"),
        phase=phase,
    )
    if phase == _IMPACT_PHASE:
        return _validate_impact_output(payload, result)
    return _validate_ranking_output(payload, result)


def airline_agent_activity(payload: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(_run_airline_agent(payload))


def _option_dict(result: FeasibilityResult) -> dict[str, Any]:
    option = result.option
    return {
        "option_id": option.option_id,
        "impact": option.impact,
        "value_gbp": option.value_gbp,
        "actions": [action.to_dict() for action in option.actions],
        "evidence_versions": dict(option.evidence_versions),
        "feasible": result.feasible,
        "admitted": result.feasible,
        "reasons": list(result.reasons),
    }


def airline_admission_activity(payload: dict[str, Any]) -> dict[str, Any]:
    evidence = _required_object(payload.get("evidence"), name="evidence")
    _required_object(payload.get("impact"), name="impact")
    observation = _required_object(
        evidence.get("observation"),
        name="evidence.observation",
    )
    results = admit_recovery_options(observation)
    admitted_options = [_option_dict(result) for result in results if result.feasible]
    if not admitted_options:
        raise ValueError("deterministic admission produced no feasible recovery option")
    return {
        "admitted_options": admitted_options,
        "rejected_options": [_option_dict(result) for result in results if not result.feasible],
    }


def airline_governance_activity(payload: dict[str, Any]) -> dict[str, Any]:
    selected_option = _required_object(
        payload.get("selected_option"),
        name="selected_option",
    )
    value = selected_option.get("value_gbp")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError("selected_option.value_gbp must be finite")
    authority = kernel().check_authority(
        role=HITL_PERSONA,
        action=COMMAND_TYPE,
        category="synthetic-operational-recovery",
        value=float(value),
    )
    return {
        "allowed": bool(authority.allowed),
        "reason": str(authority.reason),
        "governing_rule_id": authority.governing_rule_id,
    }


def _denied(reason: str) -> dict[str, Any]:
    return {
        "status": "denied",
        "command": None,
        "reason": reason,
    }


def _approval_reason(
    approval: Any,
    *,
    workflow_id: str,
    selected_option: dict[str, Any],
    admitted_options: list[dict[str, Any]],
    evidence_versions: dict[str, int],
) -> str | None:
    if not isinstance(approval, dict):
        return "approval payload is missing"
    if approval.get("decision") != "approve":
        return "decision must be approve"
    if approval.get("persona") != HITL_PERSONA:
        return f"approval persona must be {HITL_PERSONA}"
    decision_id = approval.get("decision_id")
    if not isinstance(decision_id, str) or not decision_id.strip():
        return "decision_id is required"
    selected_option_id = approval.get("selected_option_id")
    admitted_ids = {option["option_id"] for option in admitted_options}
    if selected_option_id not in admitted_ids:
        return "selected option is not deterministically admitted"
    if selected_option_id != selected_option["option_id"]:
        return "selected option does not match the governed ranking"
    if approval.get("evidence_versions") != evidence_versions:
        return "approval evidence is stale or incomplete"
    if approval.get("workflow_id") not in (None, workflow_id):
        return "approval has the wrong workflow"
    if approval.get("story_id") not in (None, STORY_ID):
        return "approval has the wrong story"
    return None


def _active_world() -> AirlineWorld:
    runtime = SimulationRuntime(seed=42)
    world = AirlineWorld(seed=42, runtime=runtime)
    world.install()
    world.activate_scenario(SCENARIO_ID)
    return world


def airline_command_activity(
    payload: dict[str, Any],
    *,
    world: AirlineWorld | None = None,
) -> dict[str, Any]:
    workflow_id = _required_string(payload.get("workflow_id"), name="workflow_id")
    approval = _required_object(payload.get("approval"), name="approval")
    hitl_context = _required_object(
        payload.get("hitl_context"),
        name="hitl_context",
    )
    expected_versions = _evidence_versions(
        hitl_context.get("evidence_versions"),
        name="hitl_context.evidence_versions",
    )
    target_world = world if world is not None else _active_world()
    current_versions = _evidence_versions(
        target_world._current_recovery_observation().get("evidence_versions"),
        name="current_world.evidence_versions",
    )
    if current_versions != expected_versions:
        return _denied("world evidence is stale relative to the HITL checkpoint")
    option_id = _required_string(
        approval.get("selected_option_id"),
        name="approval.selected_option_id",
    )
    decision_id = _required_string(
        approval.get("decision_id"),
        name="approval.decision_id",
    )
    command = target_world.command_for_option(
        option_id=option_id,
        workflow_id=workflow_id,
        decision_id=decision_id,
        persona=HITL_PERSONA,
    )
    gateway_event = target_world.apply_command(command)
    if gateway_event.type != "command.accepted":
        reason = str(gateway_event.payload.get("reason") or "world command gateway denied")
        return {
            **_denied(reason),
            "gateway_event": gateway_event.to_dict(),
        }
    return {
        "status": "decision_ready",
        "command": command.to_dict(),
        "gateway_event": gateway_event.to_dict(),
        "evaluation": {
            "status": "pending_world_event_pipeline",
            "success_event": SUCCESS_EVENT,
        },
    }


def airline_orchestration(
    context: df.DurableOrchestrationContext,
) -> Generator[Any, Any, dict[str, Any]]:
    input_dict = context.get_input() or {}
    workflow_id = _required_string(
        input_dict.get("workflow_id"),
        name="workflow_id",
    )
    instance_id = context.instance_id

    def checkpoint(kind: str, event_payload: dict[str, Any]) -> Any:
        return context.call_activity(
            "checkpoint_activity_trigger",
            {
                "workflow_id": workflow_id,
                "instance_id": instance_id,
                "kind": kind,
                "payload": {
                    **event_payload,
                    "workflow_type": WORKFLOW_TYPE,
                },
            },
        )

    yield checkpoint("workflow.started", {})
    evidence = yield context.call_activity(
        "airline_evidence_activity_trigger",
        {**input_dict, "instance_id": instance_id},
    )

    yield checkpoint("step.started", {"step": _IMPACT_PHASE})
    impact = yield context.call_activity(
        "airline_agent_activity_trigger",
        {
            **input_dict,
            "instance_id": instance_id,
            "phase": _IMPACT_PHASE,
            "evidence": evidence,
        },
    )
    yield checkpoint("step.completed", {"step": _IMPACT_PHASE})

    admission = yield context.call_activity(
        "airline_admission_activity_trigger",
        {
            **input_dict,
            "instance_id": instance_id,
            "evidence": evidence,
            "impact": impact,
        },
    )
    admitted_options = admission["admitted_options"]

    yield checkpoint("step.started", {"step": _RANKING_PHASE})
    ranking = yield context.call_activity(
        "airline_agent_activity_trigger",
        {
            **input_dict,
            "instance_id": instance_id,
            "phase": _RANKING_PHASE,
            "evidence": evidence,
            "impact": impact,
            "admitted_options": admitted_options,
        },
    )
    yield checkpoint("step.completed", {"step": _RANKING_PHASE})

    selected_option_id = ranking["ranked_option_ids"][0]
    selected_option = next(option for option in admitted_options if option["option_id"] == selected_option_id)
    authority = yield context.call_activity(
        "airline_governance_activity_trigger",
        {
            "workflow_id": workflow_id,
            "instance_id": instance_id,
            "selected_option": selected_option,
        },
    )
    if not authority.get("allowed"):
        return _denied(str(authority.get("reason") or "governance denied"))

    hitl_context = {
        "workflow_id": workflow_id,
        "instance_id": instance_id,
        "workflow_type": WORKFLOW_TYPE,
        "story_id": STORY_ID,
        "persona": HITL_PERSONA,
        "external_event": HITL_EVENT,
        "phase": _HITL_PHASE,
        "observation": evidence["observation"],
        "evidence": evidence,
        "impact": impact,
        "admitted_options": admitted_options,
        "ranking": ranking,
        "selected_option": selected_option,
        "evidence_versions": evidence["evidence_versions"],
        "authority": authority,
    }
    yield checkpoint(
        "suspended",
        {
            "reason": "awaiting_approval",
            "phase": _HITL_PHASE,
            "persona": HITL_PERSONA,
            "external_event": HITL_EVENT,
            "hitl_context": hitl_context,
        },
    )
    decision_event = context.wait_for_external_event(HITL_EVENT)
    timer = context.create_timer(context.current_utc_datetime + timedelta(minutes=5))
    winner = yield context.task_any([decision_event, timer])
    if winner == timer:
        return _denied(f"{_HITL_PHASE} timed out")
    timer.cancel()
    approval = decision_event.result
    yield checkpoint("resumed", {"phase": _HITL_PHASE})
    denial_reason = _approval_reason(
        approval,
        workflow_id=workflow_id,
        selected_option=selected_option,
        admitted_options=admitted_options,
        evidence_versions=evidence["evidence_versions"],
    )
    if denial_reason is not None:
        return _denied(denial_reason)

    yield checkpoint("step.started", {"step": "Commit Recovery Actions"})
    decision = yield context.call_activity(
        "airline_command_activity_trigger",
        {
            "workflow_id": workflow_id,
            "instance_id": instance_id,
            "approval": approval,
            "hitl_context": hitl_context,
        },
    )
    if decision.get("status") != "decision_ready":
        return decision
    yield checkpoint(
        "step.completed",
        {"step": "Commit Recovery Actions", "status": "decision_ready"},
    )
    yield checkpoint(
        "step.completed",
        {
            "step": "Verify Recovery Outcome",
            "status": "pending_world_event_pipeline",
        },
    )
    return {
        **decision,
        "approval": approval,
        "workflow_evidence": evidence,
        "reasoning": {
            "impact": impact,
            "admission": admission,
            "ranking": ranking,
            "authority": authority,
        },
        "hitl_context": hitl_context,
    }


@app.activity_trigger(input_name="payload")
def airline_evidence_activity_trigger(payload: dict) -> dict:
    return airline_evidence_activity(payload)


@app.activity_trigger(input_name="payload")
def airline_agent_activity_trigger(payload: dict) -> dict:
    return airline_agent_activity(payload)


@app.activity_trigger(input_name="payload")
def airline_admission_activity_trigger(payload: dict) -> dict:
    return airline_admission_activity(payload)


@app.activity_trigger(input_name="payload")
def airline_governance_activity_trigger(payload: dict) -> dict:
    return airline_governance_activity(payload)


@app.activity_trigger(input_name="payload")
def airline_command_activity_trigger(payload: dict) -> dict:
    return airline_command_activity(payload)


@app.orchestration_trigger(context_name="context")
def AirlineIntegratedHubRecoveryOrchestrator(
    context: df.DurableOrchestrationContext,
):
    return airline_orchestration(context)
