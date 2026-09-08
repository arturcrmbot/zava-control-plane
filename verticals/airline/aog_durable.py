"""Airline Hero 2 – AOG Engineering Recovery Durable core.

Isolated six-phase workflow (no active-pack registration):
  1. Detect AOG Event (deterministic evidence)
  2. Check Airworthiness Constraints (deterministic admission)
  3. Synthesize Engineering Recovery Options (agent – two AOG tools)
  4. Approve Engineering Recovery (HITL – engineering_duty_manager)
  5. Commit Engineering and Operational Actions (deterministic command)
  6. Verify Recovery State (deterministic pending-pipeline)

Pure activity/orchestration functions are importable for unit tests.
Call ``register(app)`` to wire DFApp triggers at the next stage without
creating a second DFApp or duplicating business logic.
"""
from __future__ import annotations

import asyncio
import copy
import json
import math
import os
from collections.abc import Generator
from datetime import timedelta
from pathlib import Path
from typing import Any

import azure.durable_functions as df

from api.server.services.governance import kernel
from verticals.airline.aog_constants import (
    AOG_DECISION_ID,
    AOG_HITL_PERSONA,
    AOG_SCENARIO_ID,
    AOG_STORY_ID,
    AOG_WORKFLOW_TYPE,
)
from verticals.airline.aog_constraints import AogFeasibilityResult, admit_aog_options
from verticals.airline.mcp_tools.aog import (
    TOOL_NAMES as AOG_TOOL_NAMES,
    airline_rank_admitted_aog_options,
    airline_read_aog_evidence,
)
from verticals.airline.worlds.active import resolve_active_airline_world
from verticals.airline.worlds.scenario import (
    AirlineWorld,
    RecoveryObservationUnavailableError,
)

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

WORKFLOW_TYPE = AOG_WORKFLOW_TYPE
ORCHESTRATOR = "AirlineAogEngineeringRecoveryOrchestrator"
HITL_PERSONA = AOG_HITL_PERSONA
HITL_EVENT = "engineering_duty_manager_decision"
COMMAND_TYPE = "airline.commit_aog_recovery"
HITL_CATEGORY = "synthetic-engineering-recovery"
GOLDEN_DECISION_ID = AOG_DECISION_ID

# Phase labels
_DETECT_PHASE = "Detect AOG Event"
_AIRWORTHINESS_PHASE = "Check Airworthiness Constraints"
_AGENT_PHASE = "Synthesize Engineering Recovery Options"
_HITL_PHASE = "Approve Engineering Recovery"
_COMMIT_PHASE = "Commit Engineering and Operational Actions"
_VERIFY_PHASE = "Verify Recovery State"

_SKILL_ROOT = Path(__file__).resolve().parent / "skills"
_AOG_SKILL_LABEL = "aog-recovery-ranker"
_AOG_TOOLS = [airline_read_aog_evidence, airline_rank_admitted_aog_options]

_AOG_RANKING_KEYS = frozenset({
    "phase",
    "ranked_option_ids",
    "reasoning",
    "evidence_versions",
    "actor_ids",
    "event_ids",
})
_CANONICAL_TOOL_CALL_KEYS = frozenset({
    "tool_call_id",
    "name",
    "tool",
    "args",
    "result",
    "success",
    "latency_ms",
})

_AGENT_MAX_ATTEMPTS = 2
_AGENT_ATTEMPT_TIMEOUT_SECONDS = 90.0


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _required_object(value: Any, *, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _required_string(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


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


def _identity_list(value: Any, *, name: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item.strip() for item in value)
        or len(set(value)) != len(value)
    ):
        raise ValueError(f"{name} must contain unique non-empty string identities")
    return list(value)


def _denied(reason: str) -> dict[str, Any]:
    return {"status": "denied", "command": None, "reason": reason}


def _active_world() -> AirlineWorld:
    try:
        return resolve_active_airline_world()
    except RuntimeError:
        if os.getenv("FUNCTIONS_WORKER_RUNTIME") != "python":
            raise
        from verticals.airline.lifecycle import ensure_airline_worker_world
        return ensure_airline_worker_world()


# ---------------------------------------------------------------------------
# 1. Evidence activity
# ---------------------------------------------------------------------------


def aog_evidence_activity(
    payload: dict[str, Any],
    *,
    world: AirlineWorld | None = None,
) -> dict[str, Any]:
    """Detect AOG Event – validates workflow type and obtains the real AOG observation."""
    workflow_id = _required_string(payload.get("workflow_id"), name="workflow_id")
    if payload.get("type") != WORKFLOW_TYPE:
        raise ValueError(
            f"AOG evidence has the wrong workflow type: expected {WORKFLOW_TYPE!r}, "
            f"got {payload.get('type')!r}"
        )
    supplied_observation = payload.get("observation")
    if (
        payload.get("diagnostic") is True
        and world is None
        and os.getenv("FUNCTIONS_WORKER_RUNTIME") == "python"
    ):
        from verticals.airline.lifecycle import reset_airline_worker_world

        reset_airline_worker_world()
    target_world = world if world is not None else _active_world()
    if world is None and isinstance(supplied_observation, dict):
        if target_world.aog_story_status.get(AOG_STORY_ID) != "active":
            target_world.activate_scenario(AOG_SCENARIO_ID)
        target_world.bind_scenario_trace(
            AOG_SCENARIO_ID,
            _required_string(
                supplied_observation.get("trace_id"),
                name="observation.trace_id",
            ),
        )
        observation = copy.deepcopy(supplied_observation)
    else:
        try:
            observation = copy.deepcopy(target_world.current_aog_observation())
        except RecoveryObservationUnavailableError as exc:
            raise ValueError(f"AOG world has no active scenario: {exc}") from exc

    if observation.get("story_id") != AOG_STORY_ID:
        raise ValueError(
            f"AOG evidence has the wrong story: expected {AOG_STORY_ID!r}"
        )
    versions = _evidence_versions(
        observation.get("evidence_versions"),
        name="observation.evidence_versions",
    )
    event_ids_raw = observation.get("evidence_event_ids") or []
    event_ids = _identity_list(
        [eid for eid in event_ids_raw if eid],
        name="observation.event_ids",
    )
    actor_ids = sorted(versions)
    observation["actor_ids"] = actor_ids
    observation["event_ids"] = event_ids
    observation["evidence_versions"] = versions
    return {
        "workflow_id": workflow_id,
        "story_id": AOG_STORY_ID,
        "source_mode": "simulated",
        "actor_ids": actor_ids,
        "event_ids": event_ids,
        "evidence_versions": versions,
        "observation": observation,
    }


# ---------------------------------------------------------------------------
# 2. Airworthiness / admission activity
# ---------------------------------------------------------------------------


def _aog_option_dict(result: AogFeasibilityResult) -> dict[str, Any]:
    option = result.option
    return {
        "option_id": option.option_id,
        "impact": option.impact,
        "value_gbp": option.value_gbp,
        "actions": [a.to_dict() for a in option.actions],
        "evidence_versions": dict(option.evidence_versions),
        "feasible": result.feasible,
        "admitted": result.feasible,
        "reasons": list(result.reasons),
    }


def aog_airworthiness_activity(payload: dict[str, Any]) -> dict[str, Any]:
    """Check Airworthiness Constraints – deterministic admission of AOG recovery options."""
    evidence = _required_object(payload.get("evidence"), name="evidence")
    observation = _required_object(
        evidence.get("observation"),
        name="evidence.observation",
    )
    results = admit_aog_options(observation)
    admitted = [_aog_option_dict(r) for r in results if r.feasible]
    rejected = [_aog_option_dict(r) for r in results if not r.feasible]
    if not admitted:
        raise ValueError(
            "AOG deterministic admission produced no feasible engineering recovery option"
        )
    return {
        "admitted_options": admitted,
        "rejected_options": rejected,
    }


# ---------------------------------------------------------------------------
# 3. Agent activity (Synthesize Engineering Recovery Options)
# ---------------------------------------------------------------------------


async def run_agent_session(prompt: str, **kwargs: Any) -> dict[str, Any]:
    """Wrapper around the canonical agent runner; never imported from durable.py."""
    from api.functions.graphs.executors.agents._wrapper import (
        run_agent_session as _run,
    )
    return await _run(prompt, **kwargs)


def _aog_agent_prompt(payload: dict[str, Any]) -> str:
    evidence = _required_object(payload.get("evidence"), name="evidence")
    admitted_options = payload.get("admitted_options")
    if not isinstance(admitted_options, list) or not admitted_options:
        raise ValueError("admitted_options must contain deterministic AOG options")
    tool_input_evidence = {
        "observation": {
            "story_id": evidence["story_id"],
            "actor_ids": evidence["actor_ids"],
            "event_ids": evidence["event_ids"],
            "evidence_versions": evidence["evidence_versions"],
            "evidence": evidence["observation"],
        }
    }
    tool_input_ranking = {
        "admitted_options": admitted_options,
        "ranking_context": {
            "story_id": evidence["story_id"],
            "evidence_versions": evidence["evidence_versions"],
        },
    }
    output_keys = sorted(_AOG_RANKING_KEYS)
    return (
        "Use BOTH registered AOG tools before responding. "
        "First call airline_read_aog_evidence, then airline_rank_admitted_aog_options. "
        "Call each required tool at least once. Avoid repeating tool calls. "
        "Return one JSON object only, without markdown or extra keys. "
        f"Exact output keys: {json.dumps(output_keys)}. "
        "Rank every supplied admitted option ID exactly once. "
        "Do not add, drop, duplicate, or modify an option. "
        "reasoning MUST be a non-empty string explaining the engineering, "
        "spare, provider, substitution, cost, and no-action trade-offs. "
        "Preserve the supplied actor_ids, event_ids, and evidence_versions exactly.\n"
        f"workflow_id={payload.get('workflow_id')}\n"
        f"instance_id={payload.get('instance_id')}\n"
        f"phase={_AGENT_PHASE}\n"
        f"skill={_AOG_SKILL_LABEL}\n"
        f"source_mode=simulated\n"
        f"tool_input_evidence={json.dumps(tool_input_evidence, sort_keys=True)}\n"
        f"tool_input_ranking={json.dumps(tool_input_ranking, sort_keys=True)}"
    )


def _validate_aog_agent_output(
    payload: dict[str, Any],
    result: Any,
) -> dict[str, Any]:
    evidence = _required_object(payload.get("evidence"), name="evidence")

    if not isinstance(result, dict):
        raise ValueError("AOG agent response must be an object")
    allowed_keys = _AOG_RANKING_KEYS | {"_raw_tool_calls"}
    if not _AOG_RANKING_KEYS <= set(result):
        missing = sorted(_AOG_RANKING_KEYS - set(result))
        raise ValueError(f"AOG agent response is missing required keys: {missing}")
    if not set(result) <= allowed_keys:
        extra = sorted(set(result) - allowed_keys)
        raise ValueError(f"AOG agent response contains unknown keys: {extra}")

    calls = result.get("_raw_tool_calls")
    if not isinstance(calls, list) or not calls:
        raise ValueError("AOG agent requires successful declared tool calls")
    seen_tools: set[str] = set()
    failed_tools: set[str] = set()
    for call in calls:
        if (
            not isinstance(call, dict)
            or set(call) != _CANONICAL_TOOL_CALL_KEYS
            or not isinstance(call.get("tool_call_id"), str)
            or not call["tool_call_id"].strip()
            or not isinstance(call.get("name"), str)
            or not call["name"].strip()
            or call.get("tool") != call["name"]
            or not isinstance(call.get("args"), str)
            or not call["args"].strip()
            or not isinstance(call.get("result"), str)
            or not call["result"].strip()
            or not isinstance(call.get("success"), bool)
            or isinstance(call.get("latency_ms"), bool)
            or not isinstance(call.get("latency_ms"), int)
            or call["latency_ms"] < 0
        ):
            raise ValueError("AOG agent tool evidence is malformed")

        tool_name = call["name"]
        if tool_name not in AOG_TOOL_NAMES:
            raise ValueError(
                f"AOG agent used an undeclared tool: {tool_name!r}; "
                f"declared tools are {sorted(AOG_TOOL_NAMES)}"
            )
        if call["success"]:
            seen_tools.add(tool_name)
        else:
            failed_tools.add(tool_name)

    uncorrected_tools = failed_tools - seen_tools
    if uncorrected_tools:
        raise ValueError(
            "AOG agent tool calls were unsuccessful: "
            f"{sorted(uncorrected_tools)}"
        )
    if seen_tools != AOG_TOOL_NAMES:
        missing = sorted(AOG_TOOL_NAMES - seen_tools)
        raise ValueError(
            f"AOG agent did not call all required tools; missing: {missing}"
        )

    if result["phase"] != _AGENT_PHASE:
        raise ValueError(
            f"AOG agent changed the phase; expected {_AGENT_PHASE!r}, got {result['phase']!r}"
        )

    admitted_options = payload.get("admitted_options")
    if not isinstance(admitted_options, list) or not admitted_options:
        raise ValueError("AOG agent ranking requires admitted options in payload")
    admitted_ids = [opt.get("option_id") for opt in admitted_options]
    ranked_ids = result["ranked_option_ids"]
    if (
        not isinstance(ranked_ids, list)
        or any(not isinstance(oid, str) for oid in ranked_ids)
        or len(ranked_ids) != len(admitted_ids)
        or len(set(ranked_ids)) != len(ranked_ids)
        or set(ranked_ids) != set(admitted_ids)
    ):
        raise ValueError(
            "AOG agent ranking must contain every admitted option exactly once; "
            f"admitted={sorted(admitted_ids)}, ranked={ranked_ids!r}"
        )

    if not isinstance(result["reasoning"], str) or not result["reasoning"].strip():
        raise ValueError("AOG agent reasoning must be a non-empty string")

    if result.get("evidence_versions") != evidence.get("evidence_versions"):
        raise ValueError("AOG agent changed evidence versions")
    if result.get("actor_ids") != evidence.get("actor_ids"):
        raise ValueError("AOG agent changed actor IDs")
    if result.get("event_ids") != evidence.get("event_ids"):
        raise ValueError("AOG agent changed event IDs")

    return {key: result[key] for key in _AOG_RANKING_KEYS}


def _no_tool_evidence(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    return "_raw_tool_calls" not in result or result.get("_raw_tool_calls") == []


def _has_failed_declared_tool_evidence(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    calls = result.get("_raw_tool_calls")
    if not isinstance(calls, list):
        return False
    succeeded = {
        call.get("name")
        for call in calls
        if isinstance(call, dict)
        and call.get("name") in AOG_TOOL_NAMES
        and call.get("success") is True
    }
    failed = {
        call.get("name")
        for call in calls
        if isinstance(call, dict)
        and call.get("name") in AOG_TOOL_NAMES
        and call.get("success") is False
    }
    return bool(failed - succeeded)


def _corrective_prompt(original: str, *, reason: str = "The prior attempt produced no tool evidence.") -> str:
    return (
        f"{original}\n"
        f"CORRECTION: {reason} "
        f"You MUST call BOTH required tools "
        f"({', '.join(sorted(AOG_TOOL_NAMES))}) before responding."
    )


async def _run_aog_agent(payload: dict[str, Any]) -> dict[str, Any]:
    session_kwargs: dict[str, Any] = dict(
        tools=list(_AOG_TOOLS),
        required_tool_names=[tool.name for tool in _AOG_TOOLS],
        skill_dir=_SKILL_ROOT / _AOG_SKILL_LABEL,
        skill_label=_AOG_SKILL_LABEL,
        workflow_id=payload.get("workflow_id"),
        instance_id=payload.get("instance_id"),
        phase=_AGENT_PHASE,
    )
    original_prompt = _aog_agent_prompt(payload)
    prompt = original_prompt
    result: Any = None
    for attempt in range(_AGENT_MAX_ATTEMPTS):
        try:
            result = await asyncio.wait_for(
                run_agent_session(prompt, **session_kwargs),
                timeout=_AGENT_ATTEMPT_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            if attempt + 1 == _AGENT_MAX_ATTEMPTS:
                raise asyncio.TimeoutError(
                    f"{_AGENT_PHASE} timed out after {_AGENT_MAX_ATTEMPTS} attempts"
                ) from None
            prompt = _corrective_prompt(
                original_prompt,
                reason="The prior attempt timed out before producing tool evidence.",
            )
            continue
        if _no_tool_evidence(result) and attempt + 1 < _AGENT_MAX_ATTEMPTS:
            prompt = _corrective_prompt(original_prompt)
            continue
        if (
            _has_failed_declared_tool_evidence(result)
            and attempt + 1 < _AGENT_MAX_ATTEMPTS
        ):
            prompt = _corrective_prompt(
                original_prompt,
                reason="The prior attempt contained an unsuccessful declared tool call.",
            )
            continue
        break
    return _validate_aog_agent_output(payload, result)


def aog_agent_activity(payload: dict[str, Any]) -> dict[str, Any]:
    """Synthesize Engineering Recovery Options – agent with two AOG tools."""
    return asyncio.run(_run_aog_agent(payload))


# ---------------------------------------------------------------------------
# 4. Governance activity
# ---------------------------------------------------------------------------


def aog_governance_activity(payload: dict[str, Any]) -> dict[str, Any]:
    """Check governance authority for engineering_duty_manager / airline.commit_aog_recovery."""
    selected_option = _required_object(payload.get("selected_option"), name="selected_option")
    value = selected_option.get("value_gbp")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError("selected_option.value_gbp must be finite")
    authority = kernel().check_authority(
        role=HITL_PERSONA,
        action=COMMAND_TYPE,
        category=HITL_CATEGORY,
        value=float(value),
    )
    return {
        "allowed": bool(authority.allowed),
        "reason": str(authority.reason),
        "governing_rule_id": authority.governing_rule_id,
    }


# ---------------------------------------------------------------------------
# 5. Approval validation
# ---------------------------------------------------------------------------


def _aog_approval_reason(
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
    admitted_ids = {opt["option_id"] for opt in admitted_options}
    if selected_option_id not in admitted_ids:
        return "selected option is not deterministically admitted"
    if selected_option_id != selected_option["option_id"]:
        return "selected option does not match the governed ranking"
    if approval.get("evidence_versions") != evidence_versions:
        return "approval evidence is stale or incomplete"
    if approval.get("workflow_id") not in (None, workflow_id):
        return "approval has the wrong workflow"
    if approval.get("story_id") not in (None, AOG_STORY_ID):
        return "approval has the wrong story"
    return None


# ---------------------------------------------------------------------------
# 6. Command activity
# ---------------------------------------------------------------------------


def aog_command_activity(
    payload: dict[str, Any],
    *,
    world: AirlineWorld | None = None,
) -> dict[str, Any]:
    """Commit Engineering and Operational Actions – constructs/applies AOG recovery command."""
    from verticals.airline.actions.aog_commands import aog_recovery_command_id

    workflow_id = _required_string(payload.get("workflow_id"), name="workflow_id")
    approval = _required_object(payload.get("approval"), name="approval")
    hitl_context = _required_object(payload.get("hitl_context"), name="hitl_context")
    expected_versions = _evidence_versions(
        hitl_context.get("evidence_versions"),
        name="hitl_context.evidence_versions",
    )
    target_world = world if world is not None else _active_world()
    option_id = _required_string(
        approval.get("selected_option_id"),
        name="approval.selected_option_id",
    )
    decision_id = _required_string(
        approval.get("decision_id"),
        name="approval.decision_id",
    )
    command_id = aog_recovery_command_id(
        workflow_id=workflow_id,
        decision_id=decision_id,
        option_id=option_id,
    )
    is_retry = target_world.command_was_processed(command_id)
    if is_retry:
        try:
            command = target_world.command_for_aog_option(
                option_id=option_id,
                workflow_id=workflow_id,
                decision_id=decision_id,
                persona=HITL_PERSONA,
            )
        except ValueError as exc:
            return _denied(f"command retry identity is invalid: {exc}")
        version_source = command.payload
    else:
        try:
            version_source = target_world.current_aog_observation()
        except RecoveryObservationUnavailableError as exc:
            return _denied(f"selected AOG option is stale or infeasible: {exc}")

    current_versions = _evidence_versions(
        version_source.get("evidence_versions"),
        name="current_world.evidence_versions",
    )
    if current_versions != expected_versions:
        return _denied("world evidence is stale relative to the HITL checkpoint")

    if not is_retry:
        try:
            command = target_world.command_for_aog_option(
                option_id=option_id,
                workflow_id=workflow_id,
                decision_id=decision_id,
                persona=HITL_PERSONA,
            )
        except (RecoveryObservationUnavailableError, ValueError) as exc:
            return _denied(f"selected AOG option is stale or infeasible: {exc}")
        command_versions = _evidence_versions(
            command.payload.get("evidence_versions"),
            name="command.evidence_versions",
        )
        if command_versions != expected_versions:
            return _denied(
                "world evidence became stale while constructing the AOG engineering command"
            )

    gateway_event = target_world.apply_command(command)
    if gateway_event.type != "command.accepted":
        reason = str(gateway_event.payload.get("reason") or "world command gateway denied")
        return {**_denied(reason), "gateway_event": gateway_event.to_dict()}

    return {
        "status": "decision_ready",
        "command": command.to_dict(),
        "gateway_event": gateway_event.to_dict(),
        "evaluation": {
            "status": "pending_world_event_pipeline",
            "success_event": "airline.aog_recovery.applied",
        },
    }


# ---------------------------------------------------------------------------
# 7. Orchestration
# ---------------------------------------------------------------------------


def aog_orchestration(
    context: df.DurableOrchestrationContext,
) -> Generator[Any, Any, dict[str, Any]]:
    """Six-phase AOG Engineering Recovery orchestration."""
    input_dict = context.get_input() or {}
    workflow_id = _required_string(input_dict.get("workflow_id"), name="workflow_id")
    instance_id = context.instance_id

    def checkpoint(kind: str, event_payload: dict[str, Any]) -> Any:
        return context.call_activity(
            "checkpoint_activity_trigger",
            {
                "workflow_id": workflow_id,
                "instance_id": instance_id,
                "kind": kind,
                "payload": {**event_payload, "workflow_type": WORKFLOW_TYPE},
            },
        )

    def terminal_checkpoint(result: dict[str, Any]) -> Any:
        return checkpoint(
            "workflow.completed",
            {"status": result["status"], "reason": result["reason"]},
        )

    # --- Phase 1: Detect AOG Event ---
    yield checkpoint("workflow.started", {})
    yield checkpoint("step.started", {"step": _DETECT_PHASE})
    evidence = yield context.call_activity(
        "aog_evidence_activity_trigger",
        {**input_dict, "instance_id": instance_id},
    )
    yield checkpoint("step.completed", {"step": _DETECT_PHASE})

    # --- Phase 2: Check Airworthiness Constraints ---
    yield checkpoint("step.started", {"step": _AIRWORTHINESS_PHASE})
    admission = yield context.call_activity(
        "aog_airworthiness_activity_trigger",
        {**input_dict, "instance_id": instance_id, "evidence": evidence},
    )
    yield checkpoint("step.completed", {"step": _AIRWORTHINESS_PHASE})
    admitted_options = admission["admitted_options"]

    # --- Phase 3: Synthesize Engineering Recovery Options ---
    yield checkpoint("step.started", {"step": _AGENT_PHASE})
    ranking = yield context.call_activity(
        "aog_agent_activity_trigger",
        {
            **input_dict,
            "instance_id": instance_id,
            "phase": _AGENT_PHASE,
            "evidence": evidence,
            "admitted_options": admitted_options,
        },
    )
    yield checkpoint("step.completed", {"step": _AGENT_PHASE})

    selected_option_id = ranking["ranked_option_ids"][0]
    selected_option = next(
        opt for opt in admitted_options if opt["option_id"] == selected_option_id
    )

    # Governance check (before suspend)
    authority = yield context.call_activity(
        "aog_governance_activity_trigger",
        {
            "workflow_id": workflow_id,
            "instance_id": instance_id,
            "selected_option": selected_option,
        },
    )
    if not authority.get("allowed"):
        denial = _denied(str(authority.get("reason") or "governance denied"))
        yield terminal_checkpoint(denial)
        return denial

    # --- Phase 4: Approve Engineering Recovery (HITL) ---
    hitl_context = {
        "workflow_id": workflow_id,
        "instance_id": instance_id,
        "workflow_type": WORKFLOW_TYPE,
        "story_id": AOG_STORY_ID,
        "persona": HITL_PERSONA,
        "external_event": HITL_EVENT,
        "phase": _HITL_PHASE,
        "action": COMMAND_TYPE,
        "request": {
            "amount_gbp": selected_option["value_gbp"],
            "category": HITL_CATEGORY,
        },
        "observation": evidence["observation"],
        "evidence": evidence,
        "admitted_options": admitted_options,
        "rejected_options": admission["rejected_options"],
        "ranking": ranking,
        "selected_option": selected_option,
        "selected_option_id": selected_option_id,
        "decision_id": GOLDEN_DECISION_ID,
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
            "context": hitl_context,
            "hitl_context": hitl_context,
        },
    )
    decision_event = context.wait_for_external_event(HITL_EVENT)
    timer = context.create_timer(context.current_utc_datetime + timedelta(minutes=5))
    winner = yield context.task_any([decision_event, timer])
    if winner == timer:
        denial = _denied(f"{_HITL_PHASE} timed out")
        yield terminal_checkpoint(denial)
        return denial
    timer.cancel()
    approval = decision_event.result
    yield checkpoint("resumed", {"phase": _HITL_PHASE})

    denial_reason = _aog_approval_reason(
        approval,
        workflow_id=workflow_id,
        selected_option=selected_option,
        admitted_options=admitted_options,
        evidence_versions=evidence["evidence_versions"],
    )
    if denial_reason is not None:
        denial = _denied(denial_reason)
        yield terminal_checkpoint(denial)
        return denial

    # --- Phase 5: Commit Engineering and Operational Actions ---
    yield checkpoint("step.started", {"step": _COMMIT_PHASE})
    decision = yield context.call_activity(
        "aog_command_activity_trigger",
        {
            "workflow_id": workflow_id,
            "instance_id": instance_id,
            "approval": approval,
            "hitl_context": hitl_context,
        },
    )
    if decision.get("status") != "decision_ready":
        yield terminal_checkpoint(decision)
        return decision
    yield checkpoint(
        "step.completed",
        {"step": _COMMIT_PHASE, "status": "decision_ready"},
    )

    # --- Phase 6: Verify Recovery State ---
    yield checkpoint(
        "step.completed",
        {"step": _VERIFY_PHASE, "status": "pending_world_event_pipeline"},
    )

    return {
        **decision,
        "workflow_id": workflow_id,
        "approval": approval,
        "workflow_evidence": evidence,
        "reasoning": {
            "admission": admission,
            "ranking": ranking,
            "authority": authority,
        },
        "hitl_context": hitl_context,
    }


# ---------------------------------------------------------------------------
# register(app) seam – next stage wires triggers here
# ---------------------------------------------------------------------------


def register(app: Any) -> None:
    """Register AOG Durable activity and orchestration triggers onto an existing DFApp.

    Does NOT create a second DFApp. Pure business logic stays in the module-level
    functions above; this seam adds the Azure Durable Functions decorators.
    """
    _act = app.activity_trigger(input_name="payload")
    _orch = app.orchestration_trigger(context_name="context")

    @_act
    def aog_evidence_activity_trigger(payload: dict) -> dict:
        return aog_evidence_activity(payload)

    @_act
    def aog_airworthiness_activity_trigger(payload: dict) -> dict:
        return aog_airworthiness_activity(payload)

    @_act
    def aog_agent_activity_trigger(payload: dict) -> dict:
        return aog_agent_activity(payload)

    @_act
    def aog_governance_activity_trigger(payload: dict) -> dict:
        return aog_governance_activity(payload)

    @_act
    def aog_command_activity_trigger(payload: dict) -> dict:
        return aog_command_activity(payload)

    @_orch
    def AirlineAogEngineeringRecoveryOrchestrator(
        context: df.DurableOrchestrationContext,
    ) -> Generator:
        return (yield from aog_orchestration(context))
