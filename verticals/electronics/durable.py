from __future__ import annotations

import asyncio
import hashlib
import json
import os
from collections.abc import Generator
from datetime import timedelta
from pathlib import Path
from typing import Any

import azure.durable_functions as df

from api.functions.kernel_registration import create_app
from verticals.electronics.agents import ELECTRONICS_AGENTS
from verticals.electronics.domains import ELECTRONICS_DOMAINS
from verticals.electronics.mcp_tools.retail import TOOL_BY_NAME
from verticals.electronics.process_profiles import ELECTRONICS_PROCESS_PROFILES


app = create_app()
_SKILL_ROOT = Path(__file__).resolve().parent / "skills"
_DECISION_OUTPUT_KEYS = {
    "skill",
    "phase",
    "recommendation",
    "actor_ids",
    "event_ids",
    "constraints",
    "reasoning",
}
_DEFAULT_LIVE_WORKFLOWS = frozenset(
    {"inventory-rebalancing", "markdown-governance"}
)
ORCHESTRATOR_NAMES = frozenset(
    profile.orchestrator for profile in ELECTRONICS_PROCESS_PROFILES.values()
)


def _require_observation(payload: dict[str, Any]) -> dict[str, Any]:
    observation = payload.get("observation")
    if not isinstance(observation, dict):
        raise ValueError("observation must be an object")
    return observation


def electronics_evidence_activity(payload: dict[str, Any]) -> dict[str, Any]:
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


def _phase_skill(workflow_type: str, phase_name: str) -> str:
    skills = ELECTRONICS_DOMAINS[workflow_type].skills
    if workflow_type == "inventory-rebalancing":
        return (
            "inventory-imbalance-analysis"
            if phase_name == "Assess Demand and Constraints"
            else "inventory-rebalance-planner"
        )
    if not skills:
        raise ValueError(f"{workflow_type} has no declared reasoning skill")
    return skills[0]


def _deterministic_decision(payload: dict[str, Any]) -> dict[str, Any]:
    workflow_type = str(payload["type"])
    phase_name = str(payload["phase"])
    skill = _phase_skill(workflow_type, phase_name)
    observation = _require_observation(payload)
    actor_ids = [str(value) for value in observation.get("actor_ids") or []]
    if not actor_ids:
        raise ValueError("decision activity requires actor evidence")
    profile = ELECTRONICS_PROCESS_PROFILES[workflow_type]
    return {
        "skill": skill,
        "phase": phase_name,
        "recommendation": profile.command_type,
        "actor_ids": actor_ids,
        "event_ids": list(observation.get("event_ids") or []),
        "constraints": {
            "ownership": "explicit",
            "authority": profile.hitl_persona,
            "stale_evidence": "reject",
        },
        "reasoning": (
            f"{skill} selected {profile.command_type} from supplied "
            f"{workflow_type} evidence."
        ),
    }


async def run_agent_session(prompt: str, **kwargs) -> dict[str, Any]:
    from api.functions.graphs.executors.agents._wrapper import (
        run_agent_session as run,
    )

    return await run(prompt, **kwargs)


def _live_workflows() -> frozenset[str]:
    raw = os.environ.get("ZAVA_ELECTRONICS_LIVE_WORKFLOWS", "").strip()
    if not raw:
        return _DEFAULT_LIVE_WORKFLOWS
    return frozenset(
        workflow_type.strip()
        for workflow_type in raw.split(",")
        if workflow_type.strip()
    )


def _uses_live_agent(payload: dict[str, Any], workflow_type: str) -> bool:
    mode = str(
        payload.get("agent_mode")
        or os.environ.get("ZAVA_ELECTRONICS_AGENT_MODE", "deterministic")
    ).strip().lower()
    if mode == "deterministic":
        return False
    if mode == "live":
        return True
    if mode == "hybrid":
        return workflow_type in _live_workflows()
    raise ValueError(f"unsupported Electronics agent mode: {mode!r}")


async def _live_decision(payload: dict[str, Any]) -> dict[str, Any]:
    workflow_type = str(payload["type"])
    phase_name = str(payload["phase"])
    skill = _phase_skill(workflow_type, phase_name)
    profile = ELECTRONICS_PROCESS_PROFILES[workflow_type]
    observation = _require_observation(payload)
    agent = ELECTRONICS_AGENTS[skill]
    tool_name = agent.allowed_tools[0]
    tool_input = {
        "data": observation,
        "actor_ids": list(observation.get("actor_ids") or []),
        "event_ids": list(observation.get("event_ids") or []),
        "trace_id": str(observation.get("trace_id") or payload.get("trace_id") or ""),
        "as_of_sim_time": float(observation.get("as_of_sim_time") or 0),
    }
    prompt = (
        "Use the registered Electronics tool exactly once before deciding. "
        "Return one JSON object only; no markdown and no extra keys. "
        f"The exact keys are {sorted(_DECISION_OUTPUT_KEYS)}. "
        "Do not invent actor IDs, event IDs, actions, policy, stock or money.\n"
        f"workflow_type={workflow_type}\n"
        f"phase={phase_name}\n"
        f"skill={skill}\n"
        f"required_tool={tool_name}\n"
        f"tool_input={json.dumps(tool_input, sort_keys=True)}\n"
        f"allowed_recommendation={profile.command_type}\n"
        f"required_actor_ids={json.dumps(tool_input['actor_ids'])}\n"
        f"required_event_ids={json.dumps(tool_input['event_ids'])}\n"
        "required_constraints="
        + json.dumps(
            {
                "ownership": "explicit",
                "authority": profile.hitl_persona,
                "stale_evidence": "reject",
            },
            sort_keys=True,
        )
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
    if calls is None:
        raise ValueError(
            "Electronics agent response is missing _raw_tool_calls tool evidence"
        )
    if not isinstance(calls, list):
        raise ValueError("Electronics agent tool evidence must be a list")
    # Metadata calls (e.g. report_intent) may coexist, but exactly one
    # successful call to the declared business tool is required.
    business_calls = [call for call in calls if call.get("name") in TOOL_BY_NAME]
    if not business_calls:
        raise ValueError(
            f"Electronics agent must call {tool_name!r} exactly once, got 0 calls"
        )
    if len(business_calls) > 1:
        raise ValueError(
            f"Electronics agent must call {tool_name!r} exactly once, "
            f"got {len(business_calls)} calls"
        )
    (call,) = business_calls
    if call.get("name") != tool_name or call.get("success") is not True:
        raise ValueError(
            f"Electronics agent emitted an invalid {tool_name!r} tool call"
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
            "Electronics agent response must contain exactly "
            f"{sorted(_DECISION_OUTPUT_KEYS)}, got {keys}"
        )
    workflow_type = str(payload["type"])
    phase_name = str(payload["phase"])
    skill = _phase_skill(workflow_type, phase_name)
    profile = ELECTRONICS_PROCESS_PROFILES[workflow_type]
    observation = _require_observation(payload)
    actor_ids = [str(value) for value in observation.get("actor_ids") or []]
    event_ids = [str(value) for value in observation.get("event_ids") or []]
    if business_result["skill"] != skill or business_result["phase"] != phase_name:
        raise ValueError("Electronics agent changed its declared skill or phase")
    if business_result["recommendation"] != profile.command_type:
        raise ValueError("Electronics agent recommendation is outside the process contract")
    if (
        business_result["actor_ids"] != actor_ids
        or business_result["event_ids"] != event_ids
    ):
        raise ValueError("Electronics agent changed supplied actor or event evidence")
    if not isinstance(business_result["constraints"], dict):
        raise ValueError("Electronics agent constraints must be an object")
    if not str(business_result["reasoning"]).strip():
        raise ValueError("Electronics agent reasoning must be non-empty")
    return business_result


def electronics_decision_activity(payload: dict[str, Any]) -> dict[str, Any]:
    workflow_type = str(payload["type"])
    result = (
        asyncio.run(_live_decision(payload))
        if _uses_live_agent(payload, workflow_type)
        else _deterministic_decision(payload)
    )
    return _validate_decision_output(payload, result)


def _approval_reference(approval: dict[str, Any]) -> str | None:
    decision_id = approval.get("decision_id")
    return str(decision_id) if decision_id else None


def electronics_command_activity(payload: dict[str, Any]) -> dict[str, Any]:
    workflow_type = str(payload["type"])
    profile = ELECTRONICS_PROCESS_PROFILES[workflow_type]
    observation = _require_observation(payload)
    evidence = payload.get("evidence")
    if not isinstance(evidence, dict) or not evidence.get("evidence_digest"):
        raise ValueError("validated evidence digest is required")
    approval = payload.get("approval") or {"decision": "not_required"}
    policy = observation.get("policy") or {}
    requires_approval = (
        profile.hitl_persona is not None
        and not (
            workflow_type == "inventory-rebalancing"
            and policy.get("decision") == "auto_safe"
        )
    )
    if requires_approval:
        if approval.get("decision") != "approve":
            raise ValueError(f"{profile.hitl_event} approval is required")
        if approval.get("persona") != profile.hitl_persona:
            raise ValueError(
                f"{profile.hitl_event} requires persona {profile.hitl_persona}"
            )

    workflow_id = str(payload["workflow_id"])
    trace_id = str(payload["trace_id"])
    if workflow_type == "inventory-rebalancing":
        candidate = observation.get("transfer_candidate")
        if not isinstance(candidate, dict):
            raise ValueError("inventory transfer candidate is required")
        command_payload = {
            "workflow_id": workflow_id,
            "source_location_id": candidate["source_location_id"],
            "destination_location_id": candidate["destination_location_id"],
            "sku_id": candidate["sku_id"],
            "quantity": candidate["quantity"],
            "ownership": candidate["ownership"],
            "expected_source_version": candidate["expected_source_version"],
            "expected_destination_version": candidate["expected_destination_version"],
            "policy_decision": policy.get("decision"),
            "approval_reference": _approval_reference(approval),
            "reason_code": "DEMAND_STOCK_IMBALANCE",
            "evidence_digest": evidence["evidence_digest"],
            "story_id": observation.get("story_id"),
        }
    else:
        case = observation.get("case")
        if not isinstance(case, dict):
            raise ValueError("observation.case is required")
        command_payload = {
            "workflow_id": workflow_id,
            "case_id": str(case["id"]),
            "subject_ids": [str(value) for value in case.get("subject_ids") or []],
            "action": profile.command_type,
            "approval_decision": approval.get("decision"),
            "approval_reference": _approval_reference(approval),
            "skill_outputs": dict(payload.get("skill_outputs") or {}),
            "evidence_digest": evidence["evidence_digest"],
            "story_id": observation.get("story_id"),
        }
    command = {
        "command_id": (
            f"cmd-{workflow_id}-"
            f"{profile.command_type.replace('.', '-').replace('_', '-')}"
        ),
        "trace_id": trace_id,
        "issued_by": profile.function,
        "type": profile.command_type,
        "payload": command_payload,
    }
    return {
        "command": command,
        "reasoning": {
            "summary": (
                f"Prepared {profile.display_name} from journal-backed evidence."
            ),
            "skill_outputs": dict(payload.get("skill_outputs") or {}),
            "authority": {
                "persona": profile.hitl_persona,
                "decision": approval.get("decision"),
                "decision_id": _approval_reference(approval),
            },
            "evidence_digest": evidence["evidence_digest"],
        },
    }


def electronics_orchestration(
    context: df.DurableOrchestrationContext,
) -> Generator[Any, Any, dict[str, Any]]:
    input_dict = context.get_input() or {}
    workflow_type = str(input_dict["type"])
    profile = ELECTRONICS_PROCESS_PROFILES[workflow_type]
    domain = ELECTRONICS_DOMAINS[workflow_type]
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
                "payload": {
                    **event_payload,
                    "workflow_type": workflow_type,
                },
            },
        )

    yield checkpoint("workflow.started", {})
    evidence = yield context.call_activity(
        "electronics_evidence_activity_trigger",
        {**input_dict, "instance_id": instance_id},
    )
    skill_outputs: dict[str, dict[str, Any]] = {}
    approval: dict[str, Any] = {
        "decision": "not_required",
        "authority_persona": profile.hitl_persona,
    }
    policy = observation.get("policy") or {}
    requires_approval = (
        profile.hitl_persona is not None
        and not (
            workflow_type == "inventory-rebalancing"
            and policy.get("decision") == "auto_safe"
        )
    )

    for phase in domain.phases[:-1]:
        if phase.kind == "hitl":
            if not requires_approval:
                yield checkpoint(
                    "step.completed",
                    {
                        "step": phase.name,
                        "status": "not_required",
                        "authority_persona": profile.hitl_persona,
                    },
                )
                continue
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
                            "amount": float(
                                (observation.get("case") or {})
                                .get("facts", {})
                                .get("retail_value_gbp", 0)
                            ),
                            "category": workflow_type,
                            "actor_ids": observation.get("actor_ids") or [],
                        },
                    },
                },
            )
            decision_event = context.wait_for_external_event(
                str(profile.hitl_event)
            )
            timer = context.create_timer(
                context.current_utc_datetime + timedelta(minutes=5)
            )
            winner = yield context.task_any([decision_event, timer])
            if winner == timer:
                return {
                    "status": "timeout",
                    "command": None,
                    "reasoning": f"{phase.name} timed out",
                }
            timer.cancel()
            approval = decision_event.result or {}
            approval = {
                **approval,
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
            continue

        yield checkpoint("step.started", {"step": phase.name})
        if phase.kind == "agent":
            result = yield context.call_activity(
                "electronics_decision_activity_trigger",
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
        "electronics_command_activity_trigger",
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
            {"name": phase.name, "kind": phase.kind}
            for phase in domain.phases
        ],
        "skills": list(domain.skills),
        "tools": list(observation.get("mcp_tools") or []),
        "evaluation": {
            "status": "pending_world_evidence",
            "success_event": profile.success_event,
        },
    }


@app.activity_trigger(input_name="payload")
def electronics_evidence_activity_trigger(payload: dict) -> dict:
    return electronics_evidence_activity(payload)


@app.activity_trigger(input_name="payload")
def electronics_decision_activity_trigger(payload: dict) -> dict:
    return electronics_decision_activity(payload)


@app.activity_trigger(input_name="payload")
def electronics_command_activity_trigger(payload: dict) -> dict:
    return electronics_command_activity(payload)


@app.orchestration_trigger(context_name="context")
def InventoryRebalancingOrchestrator(context):
    return electronics_orchestration(context)


@app.orchestration_trigger(context_name="context")
def DemandSpikeResponseOrchestrator(context):
    return electronics_orchestration(context)


@app.orchestration_trigger(context_name="context")
def PromotionReadinessOrchestrator(context):
    return electronics_orchestration(context)


@app.orchestration_trigger(context_name="context")
def MarkdownGovernanceOrchestrator(context):
    return electronics_orchestration(context)


@app.orchestration_trigger(context_name="context")
def SupplierDelayRecoveryOrchestrator(context):
    return electronics_orchestration(context)


@app.orchestration_trigger(context_name="context")
def FulfilmentExceptionResolutionOrchestrator(context):
    return electronics_orchestration(context)


@app.orchestration_trigger(context_name="context")
def MarketplaceSellerExceptionOrchestrator(context):
    return electronics_orchestration(context)


@app.orchestration_trigger(context_name="context")
def ReturnsDispositionOrchestrator(context):
    return electronics_orchestration(context)
