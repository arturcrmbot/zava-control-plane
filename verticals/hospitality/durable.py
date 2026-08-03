"""Durable Functions app for the Hospitality vertical.

Exports one orchestration trigger per declared process profile plus three
pack-prefixed activities. The orchestration is generic: it walks the domain's
declared phases, runs each agent phase through the canonical
``run_agent_session`` wrapper, suspends on the declared HITL gate with a
reconstructable context, and finishes by shaping a shared
``SimulationCommand`` mapping. The scenario adapter — not this module — builds
and validates the live typed domain action.

The production default is ``live`` agent execution. Offline demos and focused
tests may set ``ZAVA_HOSPITALITY_AGENT_MODE=deterministic-fallback``; every
decision is labelled with its ``execution_mode`` so the difference is never
hidden.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from collections.abc import Generator
from datetime import timedelta
from pathlib import Path
from typing import Any

import azure.durable_functions as df

from api.functions.kernel_registration import create_app
from verticals.hospitality.agents import HOSPITALITY_AGENTS
from verticals.hospitality.domains import HOSPITALITY_DOMAINS
from verticals.hospitality.mcp_tools.operations import TOOL_BY_NAME
from verticals.hospitality.process_profiles import HOSPITALITY_PROCESS_PROFILES


app = create_app()

_SKILL_ROOT = Path(__file__).resolve().parent / "skills"
DEFAULT_AGENT_MODE = "live"
FALLBACK_AGENT_MODE = "deterministic-fallback"

# How many times a live agent may answer before the deterministic planner
# takes the phase. One retry covers transient model noise without stalling
# the cascade behind a persistently non-compliant response.
_LIVE_DECISION_ATTEMPTS = 2
HITL_TIMEOUT_MINUTES = 5.0
HERO_WORKFLOW = "hotel-operations-recovery"

_DECISION_OUTPUT_KEYS = {
    "skill",
    "phase",
    "recommendation",
    "actor_ids",
    "event_ids",
    "constraints",
    "reasoning",
}

ORCHESTRATOR_NAMES = frozenset(
    profile.orchestrator for profile in HOSPITALITY_PROCESS_PROFILES.values()
)
ACTIVITY_NAMES = frozenset(
    {
        "hospitality_evidence_activity_trigger",
        "hospitality_decision_activity_trigger",
        "hospitality_command_activity_trigger",
    }
)


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


def _require_observation(payload: dict[str, Any]) -> dict[str, Any]:
    observation = payload.get("observation")
    if not isinstance(observation, dict):
        raise ValueError("observation must be an object")
    return observation


def hospitality_evidence_activity(payload: dict[str, Any]) -> dict[str, Any]:
    observation = _require_observation(payload)
    actor_ids = observation.get("actor_ids")
    event_ids = observation.get("event_ids")
    if not isinstance(actor_ids, list) or not actor_ids:
        raise ValueError("observation.actor_ids must contain real actor IDs")
    if not isinstance(event_ids, list) or not event_ids:
        raise ValueError("observation.event_ids must contain journal event IDs")
    if not observation.get("trace_id"):
        raise ValueError("observation.trace_id is required")
    canonical = json.dumps(observation, sort_keys=True, separators=(",", ":"))
    return {
        "actor_ids": [str(value) for value in actor_ids],
        "event_ids": [str(value) for value in event_ids],
        "trace_id": str(observation["trace_id"]),
        "as_of_sim_time": float(observation.get("as_of_sim_time") or 0),
        "evidence_digest": "sha256:"
        + hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "source_mode": "simulated",
    }


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------


def _phase_skill(workflow_type: str, phase_name: str) -> str:
    domain = HOSPITALITY_DOMAINS[workflow_type]
    if workflow_type == HERO_WORKFLOW:
        return (
            "hotel-impact-assessor"
            if phase_name == "Assess Guest and Operational Impact"
            else "hotel-network-recovery-planner"
        )
    if not domain.skills:
        raise ValueError(f"{workflow_type} has no declared reasoning skill")
    return HOSPITALITY_PROCESS_PROFILES[workflow_type].skill


def _agent_mode(payload: dict[str, Any]) -> str:
    mode = str(
        payload.get("agent_mode")
        or os.environ.get("ZAVA_HOSPITALITY_AGENT_MODE")
        or DEFAULT_AGENT_MODE
    ).strip().lower()
    if mode not in {DEFAULT_AGENT_MODE, FALLBACK_AGENT_MODE}:
        raise ValueError(f"unsupported Hospitality agent mode: {mode!r}")
    return mode


async def run_agent_session(prompt: str, **kwargs) -> dict[str, Any]:
    from api.functions.graphs.executors.agents._wrapper import (
        run_agent_session as run,
    )

    return await run(prompt, **kwargs)


def _constraints(workflow_type: str) -> dict[str, Any]:
    profile = HOSPITALITY_PROCESS_PROFILES[workflow_type]
    return {
        "authority": profile.hitl_persona,
        "external_event": profile.hitl_event,
        "stale_evidence": "reject",
        "mutation": "world_validated_only",
    }


def _fallback_decision(payload: dict[str, Any]) -> dict[str, Any]:
    workflow_type = str(payload["type"])
    phase_name = str(payload["phase"])
    skill = _phase_skill(workflow_type, phase_name)
    observation = _require_observation(payload)
    actor_ids = [str(value) for value in observation.get("actor_ids") or []]
    if not actor_ids:
        raise ValueError("decision activity requires actor evidence")
    profile = HOSPITALITY_PROCESS_PROFILES[workflow_type]
    return {
        "skill": skill,
        "phase": phase_name,
        "recommendation": profile.command_type,
        "actor_ids": actor_ids,
        "event_ids": [str(value) for value in observation.get("event_ids") or []],
        "constraints": _constraints(workflow_type),
        "reasoning": (
            f"{skill} selected {profile.command_type} from the supplied "
            f"{workflow_type} evidence."
        ),
    }


async def _live_decision(payload: dict[str, Any]) -> dict[str, Any]:
    workflow_type = str(payload["type"])
    phase_name = str(payload["phase"])
    skill = _phase_skill(workflow_type, phase_name)
    profile = HOSPITALITY_PROCESS_PROFILES[workflow_type]
    observation = _require_observation(payload)
    tool_name = HOSPITALITY_AGENTS[workflow_type].allowed_tools[0]
    tool_input = {
        "data": observation,
        "actor_ids": [str(value) for value in observation.get("actor_ids") or []],
        "event_ids": [str(value) for value in observation.get("event_ids") or []],
        "trace_id": str(
            observation.get("trace_id") or payload.get("trace_id") or ""
        ),
        "as_of_sim_time": float(observation.get("as_of_sim_time") or 0),
    }
    prompt = (
        "Use the registered Hospitality tool exactly once before deciding. "
        "Return one JSON object only; no markdown and no extra keys. "
        f"The exact keys are {sorted(_DECISION_OUTPUT_KEYS)}. "
        "Do not invent hotel, room, booking, asset, shift, actor or event IDs.\n"
        "Set `recommendation` to the allowed_recommendation value below, "
        "copied verbatim as an exact string. Do not paraphrase it, do not "
        "describe the action in prose, and do not substitute a synonym.\n"
        "Copy `actor_ids` and `event_ids` verbatim from the required lists, "
        "in the same order.\n"
        f"workflow_type={workflow_type}\n"
        f"phase={phase_name}\n"
        f"skill={skill}\n"
        f"required_tool={tool_name}\n"
        f"tool_input={json.dumps(tool_input, sort_keys=True)}\n"
        f"allowed_recommendation={profile.command_type}\n"
        f"required_actor_ids={json.dumps(tool_input['actor_ids'])}\n"
        f"required_event_ids={json.dumps(tool_input['event_ids'])}\n"
        "required_constraints="
        + json.dumps(_constraints(workflow_type), sort_keys=True)
        + "\n"
        f"prior_outputs={json.dumps(payload.get('prior_outputs') or {}, sort_keys=True)}"
    )
    result = await run_agent_session(
        prompt,
        tools=[TOOL_BY_NAME[tool_name]],
        skill_dir=_SKILL_ROOT / skill,
        skill_label=skill,
        workflow_id=payload.get("workflow_id"),
        instance_id=payload.get("instance_id"),
        phase=phase_name,
    )
    calls = result.get("_raw_tool_calls") if isinstance(result, dict) else None
    if calls is not None:
        if not isinstance(calls, list):
            raise ValueError("Hospitality agent tool evidence must be a list")
        business_calls = [
            call for call in calls if call.get("name") in TOOL_BY_NAME
        ]
        if any(
            call.get("name") != tool_name or call.get("success") is False
            for call in business_calls
        ):
            raise ValueError(
                f"Hospitality agent emitted an invalid {tool_name!r} tool call"
            )
    return result


def _validate_decision_output(
    payload: dict[str, Any],
    result: Any,
) -> dict[str, Any]:
    business_result = (
        {key: value for key, value in result.items() if key != "_raw_tool_calls"}
        if isinstance(result, dict)
        else result
    )
    if (
        not isinstance(business_result, dict)
        or set(business_result) != _DECISION_OUTPUT_KEYS
    ):
        keys = (
            sorted(business_result)
            if isinstance(business_result, dict)
            else type(business_result).__name__
        )
        raise ValueError(
            "Hospitality agent response must contain exactly "
            f"{sorted(_DECISION_OUTPUT_KEYS)}, got {keys}"
        )
    workflow_type = str(payload["type"])
    phase_name = str(payload["phase"])
    skill = _phase_skill(workflow_type, phase_name)
    profile = HOSPITALITY_PROCESS_PROFILES[workflow_type]
    observation = _require_observation(payload)
    actor_ids = [str(value) for value in observation.get("actor_ids") or []]
    event_ids = [str(value) for value in observation.get("event_ids") or []]
    if business_result["skill"] != skill or business_result["phase"] != phase_name:
        raise ValueError("Hospitality agent changed its declared skill or phase")
    if business_result["recommendation"] != profile.command_type:
        raise ValueError(
            "Hospitality agent recommendation is outside the process contract"
        )
    if (
        business_result["actor_ids"] != actor_ids
        or business_result["event_ids"] != event_ids
    ):
        raise ValueError("Hospitality agent changed supplied actor or event evidence")
    if not isinstance(business_result["constraints"], dict):
        raise ValueError("Hospitality agent constraints must be an object")
    if not str(business_result["reasoning"]).strip():
        raise ValueError("Hospitality agent reasoning must be non-empty")
    return business_result


def hospitality_decision_activity(payload: dict[str, Any]) -> dict[str, Any]:
    mode = _agent_mode(payload)
    if mode == FALLBACK_AGENT_MODE:
        validated = _validate_decision_output(payload, _fallback_decision(payload))
        return {**validated, "execution_mode": mode}

    # A live agent occasionally returns output outside the process contract.
    # The contract is not relaxed to accommodate that: the response is
    # rejected, retried once, and only then does the deterministic planner
    # take over. A flaky model degrades this phase, it never breaks the
    # cascade, and the recorded execution_mode always says which path ran.
    last_error: Exception | None = None
    for attempt in range(_LIVE_DECISION_ATTEMPTS):
        try:
            result = asyncio.run(_live_decision(payload))
            validated = _validate_decision_output(payload, result)
            return {**validated, "execution_mode": mode}
        except ValueError as error:
            last_error = error
            logging.warning(
                "hospitality decision attempt %d/%d violated the process "
                "contract for %s/%s: %s",
                attempt + 1,
                _LIVE_DECISION_ATTEMPTS,
                payload.get("type"),
                payload.get("phase"),
                error,
            )

    logging.warning(
        "hospitality decision falling back to the deterministic planner for "
        "%s/%s after %d contract violations (last: %s)",
        payload.get("type"),
        payload.get("phase"),
        _LIVE_DECISION_ATTEMPTS,
        last_error,
    )
    validated = _validate_decision_output(payload, _fallback_decision(payload))
    return {**validated, "execution_mode": FALLBACK_AGENT_MODE}


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


def _approval_reference(approval: dict[str, Any]) -> str | None:
    decision_id = approval.get("decision_id")
    return str(decision_id) if decision_id else None


def hospitality_command_activity(payload: dict[str, Any]) -> dict[str, Any]:
    workflow_type = str(payload["type"])
    profile = HOSPITALITY_PROCESS_PROFILES[workflow_type]
    observation = _require_observation(payload)
    evidence = payload.get("evidence")
    if not isinstance(evidence, dict) or not evidence.get("evidence_digest"):
        raise ValueError("validated evidence digest is required")

    approval = payload.get("approval") or {"decision": "not_required"}
    if profile.hitl_persona is not None:
        if approval.get("decision") != "approve":
            raise ValueError(f"{profile.hitl_event} approval is required")
        if approval.get("persona") != profile.hitl_persona:
            raise ValueError(
                f"{profile.hitl_event} requires persona {profile.hitl_persona}"
            )

    workflow_id = str(payload["workflow_id"])
    trace_id = str(payload["trace_id"])
    skill_outputs = dict(payload.get("skill_outputs") or {})
    command = {
        "command_id": (
            f"cmd-{workflow_id}-"
            f"{profile.command_type.replace('.', '-').replace('_', '-')}"
        ),
        "trace_id": trace_id,
        "issued_by": profile.function,
        "type": profile.command_type,
        "payload": {
            "workflow_type": workflow_type,
            "workflow_id": workflow_id,
            "case_id": (observation.get("case") or {}).get("id"),
            "actor_ids": [
                str(value) for value in observation.get("actor_ids") or []
            ],
            "approval_decision": approval.get("decision"),
            "approval_reference": _approval_reference(approval),
            "evidence_digest": evidence["evidence_digest"],
            "skill_outputs": skill_outputs,
        },
    }
    return {
        "command": command,
        "reasoning": {
            "summary": (
                f"Prepared {profile.display_name} from journal-backed evidence."
            ),
            "skill_outputs": skill_outputs,
            "authority": {
                "persona": profile.hitl_persona,
                "decision": approval.get("decision"),
                "decision_id": _approval_reference(approval),
            },
            "evidence_digest": evidence["evidence_digest"],
        },
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def hospitality_orchestration(
    context: df.DurableOrchestrationContext,
) -> Generator[Any, Any, dict[str, Any]]:
    input_dict = context.get_input() or {}
    workflow_type = str(input_dict["type"])
    profile = HOSPITALITY_PROCESS_PROFILES[workflow_type]
    domain = HOSPITALITY_DOMAINS[workflow_type]
    workflow_id = str(input_dict["workflow_id"])
    instance_id = context.instance_id
    observation = _require_observation(input_dict)

    def checkpoint(kind: str, event_payload: dict[str, Any]) -> Any:
        return context.call_activity(
            "checkpoint_activity_trigger",
            {
                "workflow_id": workflow_id,
                "instance_id": instance_id,
                "kind": kind,
                "payload": {**event_payload, "workflow_type": workflow_type},
            },
        )

    yield checkpoint("workflow.started", {})
    evidence = yield context.call_activity(
        "hospitality_evidence_activity_trigger",
        {**input_dict, "instance_id": instance_id},
    )

    skill_outputs: dict[str, dict[str, Any]] = {}
    approval: dict[str, Any] = {
        "decision": "not_required",
        "authority_persona": profile.hitl_persona,
    }

    for phase in domain.phases[:-1]:
        if phase.kind == "hitl":
            yield checkpoint(
                "suspended",
                {
                    "reason": "awaiting_approval",
                    "phase": phase.name,
                    "wait_kind": "operator_review",
                    "persona": profile.hitl_persona,
                    "external_event": profile.hitl_event,
                    "context": {
                        "action": profile.hitl_event,
                        "request": {
                            "action": profile.command_type,
                            "category": workflow_type,
                            "value": float(
                                (observation.get("recovery_plan") or {}).get(
                                    "estimated_recovery_cost_gbp"
                                )
                                or (observation.get("measurements") or {}).get(
                                    "estimated_recovery_spend_gbp"
                                )
                                or 0.0
                            ),
                            "actor_ids": [
                                str(value)
                                for value in observation.get("actor_ids") or []
                            ],
                            "evidence_digest": evidence["evidence_digest"],
                        },
                    },
                },
            )
            decision_event = context.wait_for_external_event(
                str(profile.hitl_event)
            )
            timer = context.create_timer(
                context.current_utc_datetime
                + timedelta(minutes=HITL_TIMEOUT_MINUTES)
            )
            winner = yield context.task_any([decision_event, timer])
            if winner == timer:
                yield checkpoint(
                    "step.completed",
                    {"step": phase.name, "status": "timeout"},
                )
                return {
                    "status": "timeout",
                    "command": None,
                    "reasoning": f"{phase.name} timed out",
                }
            timer.cancel()
            approval = {
                **(decision_event.result or {}),
                "authority_persona": profile.hitl_persona,
            }
            yield checkpoint("resumed", {"phase": phase.name})
            if (
                approval.get("decision") != "approve"
                or approval.get("persona") != profile.hitl_persona
            ):
                return {
                    "status": "denied",
                    "command": None,
                    "reasoning": (
                        f"{phase.name} denied or approved by the wrong persona"
                    ),
                }
            yield checkpoint("step.completed", {"step": phase.name})
            continue

        yield checkpoint("step.started", {"step": phase.name})
        if phase.kind == "agent":
            result = yield context.call_activity(
                "hospitality_decision_activity_trigger",
                {
                    **input_dict,
                    "instance_id": instance_id,
                    "phase": phase.name,
                    "evidence": evidence,
                    "prior_outputs": skill_outputs,
                },
            )
            skill_outputs[str(result["skill"])] = result
        yield checkpoint("step.completed", {"step": phase.name})

    decision = yield context.call_activity(
        "hospitality_command_activity_trigger",
        {
            **input_dict,
            "instance_id": instance_id,
            "evidence": evidence,
            "skill_outputs": skill_outputs,
            "approval": approval,
        },
    )
    return {
        "status": "decision_ready",
        "command": decision["command"],
        "reasoning": decision["reasoning"],
        "workflow_evidence": evidence,
        "observation": observation,
        "approval": approval,
        "phases": [
            {"name": phase.name, "kind": phase.kind} for phase in domain.phases
        ],
        "skills": list(domain.skills),
        "tools": list(observation.get("mcp_tools") or []),
        "evaluation": {
            "status": "pending_world_evidence",
            "success_event": profile.success_event,
        },
    }


# ---------------------------------------------------------------------------
# Registrations
# ---------------------------------------------------------------------------


@app.activity_trigger(input_name="payload")
def hospitality_evidence_activity_trigger(payload: dict) -> dict:
    return hospitality_evidence_activity(payload)


@app.activity_trigger(input_name="payload")
def hospitality_decision_activity_trigger(payload: dict) -> dict:
    return hospitality_decision_activity(payload)


@app.activity_trigger(input_name="payload")
def hospitality_command_activity_trigger(payload: dict) -> dict:
    return hospitality_command_activity(payload)


@app.orchestration_trigger(context_name="context")
def HotelOperationsRecoveryOrchestrator(context):
    return hospitality_orchestration(context)


@app.orchestration_trigger(context_name="context")
def RoomReadinessCoordinationOrchestrator(context):
    return hospitality_orchestration(context)


@app.orchestration_trigger(context_name="context")
def AssetMaintenanceResponseOrchestrator(context):
    return hospitality_orchestration(context)


@app.orchestration_trigger(context_name="context")
def GuestServiceRecoveryOrchestrator(context):
    return hospitality_orchestration(context)


@app.orchestration_trigger(context_name="context")
def OccupancyPressureResponseOrchestrator(context):
    return hospitality_orchestration(context)


@app.orchestration_trigger(context_name="context")
def WorkforceDemandBalancingOrchestrator(context):
    return hospitality_orchestration(context)


@app.orchestration_trigger(context_name="context")
def FoodAndBeverageReadinessOrchestrator(context):
    return hospitality_orchestration(context)


@app.orchestration_trigger(context_name="context")
def EnergyAnomalyResponseOrchestrator(context):
    return hospitality_orchestration(context)
