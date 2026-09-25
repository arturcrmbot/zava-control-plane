"""Banking supporting processes - shared Durable engine.

Two processes run on this engine: mule-account investigation (Financial
Crime) and merchant-onboarding risk (Payments). Sharing an engine is
deliberate and permitted; sharing identity is not. Each keeps its own
workflow type, orchestrator, typed command, persona, authority band,
success event, skill and evidence.

Every process here does real agent work: a bounded agent ranks only the
options deterministic admission has already permitted, calling both declared
pack tools and returning instrumented tool evidence. The deterministic layer
decides what is permissible; the agent explains and orders; the governance
kernel decides who may authorise the value; a human decides.

These are ramp-spawned rather than world-owned, so they have no actor-world
sensor and no world mutation. That node of the proof chain is recorded as
not applicable rather than faked.
"""
from __future__ import annotations

import asyncio
import json
import math
from collections.abc import Generator
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

import azure.durable_functions as df

from api.server.services.governance import kernel
from verticals.banking.mcp_tools.supporting import (
    TOOL_NAMES as CASE_TOOL_NAMES,
    banking_rank_admitted_case_options,
    banking_read_case_evidence,
)
from verticals.banking.support_constants import (
    MERCHANT_COMMAND_TYPE,
    MERCHANT_FUNCTION,
    MERCHANT_HITL_CATEGORY,
    MERCHANT_HITL_EVENT,
    MERCHANT_HITL_PERSONA,
    MERCHANT_ORCHESTRATOR,
    MERCHANT_SKILL,
    MERCHANT_SUCCESS_EVENT,
    MERCHANT_WORKFLOW_TYPE,
    MULE_COMMAND_TYPE,
    MULE_FUNCTION,
    MULE_HITL_CATEGORY,
    MULE_HITL_EVENT,
    MULE_HITL_PERSONA,
    MULE_ORCHESTRATOR,
    MULE_SKILL,
    MULE_SUCCESS_EVENT,
    MULE_WORKFLOW_TYPE,
)

_SKILL_ROOT = Path(__file__).resolve().parent / "skills"
_TOOLS = [banking_read_case_evidence, banking_rank_admitted_case_options]
# A model session can fail transiently (a session-auth blip, a rate limit).
# The agent activity only reads evidence and ranks options, so re-running it
# is safe, and each attempt is recorded in the orchestration history. Each
# attempt already retries a hung session internally, so two attempts keep
# the worst case inside the world bridge's wait.
_AGENT_RETRY = df.RetryOptions(
    first_retry_interval_in_milliseconds=10_000, max_number_of_attempts=2
)

_RANKING_KEYS = frozenset({
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
_MAX_REASSESSMENTS = 1
_AGENT_ATTEMPT_TIMEOUT_SECONDS = 150.0


@dataclass(frozen=True, slots=True)
class CaseProfile:
    workflow_type: str
    orchestrator: str
    command_type: str
    success_event: str
    hitl_persona: str
    hitl_event: str
    hitl_category: str
    skill: str
    prefix: str
    evidence_phase: str
    agent_phase: str
    hitl_phase: str
    commit_phase: str
    verify_phase: str
    options: tuple[tuple[str, str, float], ...]   # (option_id, impact, value)
    # The organisational function that issues the typed command; a world case
    # names it as the command's issuer so the world's gateway accepts it.
    function: str = ""


MULE_PROFILE = CaseProfile(
    workflow_type=MULE_WORKFLOW_TYPE,
    orchestrator=MULE_ORCHESTRATOR,
    command_type=MULE_COMMAND_TYPE,
    success_event=MULE_SUCCESS_EVENT,
    hitl_persona=MULE_HITL_PERSONA,
    hitl_event=MULE_HITL_EVENT,
    hitl_category=MULE_HITL_CATEGORY,
    skill=MULE_SKILL,
    prefix="mule",
    evidence_phase="Assemble Beneficiary Evidence",
    agent_phase="Analyse Mule Network",
    hitl_phase="Approve Account Disposition",
    commit_phase="Commit Disposition",
    verify_phase="Verify Disposition",
    options=(
        ("SYN-MULE-OPTION-RESTRAIN",
         "Restrain the account and preserve the balance.", 45_000.0),
        ("SYN-MULE-OPTION-MONITOR",
         "Keep the account open under enhanced monitoring.", 5_000.0),
        ("SYN-MULE-OPTION-CLOSE",
         "Close the account and return residual funds.", 120_000.0),
    ),
    function=MULE_FUNCTION,
)

MERCHANT_PROFILE = CaseProfile(
    workflow_type=MERCHANT_WORKFLOW_TYPE,
    orchestrator=MERCHANT_ORCHESTRATOR,
    command_type=MERCHANT_COMMAND_TYPE,
    success_event=MERCHANT_SUCCESS_EVENT,
    hitl_persona=MERCHANT_HITL_PERSONA,
    hitl_event=MERCHANT_HITL_EVENT,
    hitl_category=MERCHANT_HITL_CATEGORY,
    skill=MERCHANT_SKILL,
    prefix="merchant",
    evidence_phase="Collect Merchant Application",
    agent_phase="Assess Merchant Risk",
    hitl_phase="Approve Onboarding Decision",
    commit_phase="Commit Merchant Decision",
    verify_phase="Verify Merchant State",
    options=(
        ("SYN-MER-OPTION-ONBOARD-STANDARD", "Onboard on standard terms.", 25_000.0),
        ("SYN-MER-OPTION-ONBOARD-RESERVE", "Onboard with a rolling reserve.", 60_000.0),
        ("SYN-MER-OPTION-DECLINE",
         "Decline the application and record the reason.", 0.0),
    ),
    function=MERCHANT_FUNCTION,
)

PROFILES: dict[str, CaseProfile] = {
    MULE_PROFILE.workflow_type: MULE_PROFILE,
    MERCHANT_PROFILE.workflow_type: MERCHANT_PROFILE,
}


def _required_object(value: Any, *, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _required_string(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _denied(reason: str) -> dict[str, Any]:
    # `reasoning` is the orchestration-output contract key shared by every
    # vertical; `reason` is kept for this module's own terminal checkpoints.
    return {"status": "denied", "command": None, "reason": reason, "reasoning": reason}


# ---------------------------------------------------------------------------
# 1. Deterministic evidence + admission
# ---------------------------------------------------------------------------


def case_evidence_activity(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the spawned case and admit the options its facts permit."""
    workflow_type = _required_string(payload.get("type"), name="type")
    profile = PROFILES.get(workflow_type)
    if profile is None:
        raise ValueError(f"unsupported supporting workflow type {workflow_type!r}")
    workflow_id = _required_string(payload.get("workflow_id"), name="workflow_id")
    # A spawned case carries `case`; a case the world noticed arrives through
    # the world bridge as an `observation` that holds the case.
    world_observation = payload.get("observation") if isinstance(payload.get("observation"), dict) else None
    case = _required_object(
        payload.get("case") if world_observation is None else world_observation.get("case"),
        name="case",
    )
    case_id = _required_string(case.get("id"), name="case.id")

    risk_band = str(case.get("risk_band") or "medium")
    subject_id = _required_string(case.get("subject_id"), name="case.subject_id")
    versions = {case_id: int(case.get("version") or 1)}

    admitted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for option_id, impact, value in profile.options:
        reasons: list[str] = []
        # A low-risk subject cannot be restrained or declined; a high-risk
        # subject cannot be waved through on permissive terms.
        if risk_band == "low" and option_id.endswith(("RESTRAIN", "CLOSE", "DECLINE")):
            reasons.append(
                "subject risk band is low; a restrictive disposition is not admitted"
            )
        if risk_band == "high" and option_id.endswith(("MONITOR", "ONBOARD-STANDARD")):
            reasons.append(
                "subject risk band is high; a permissive disposition is not admitted"
            )
        entry = {
            "option_id": option_id,
            "impact": impact,
            "value_gbp": value,
            "actions": [
                {"action_type": "record_disposition", "resource_id": subject_id}
            ],
            "evidence_versions": dict(versions),
            "feasible": not reasons,
            "admitted": not reasons,
            "reasons": reasons,
        }
        (admitted if not reasons else rejected).append(entry)

    if not admitted:
        raise ValueError("deterministic admission produced no permissible option")

    return {
        "workflow_id": workflow_id,
        "workflow_type": workflow_type,
        "story_id": case_id,
        "case_id": case_id,
        "source_mode": "simulated",
        "actor_ids": [case_id, subject_id],
        "event_ids": [f"seed-{case_id}" if world_observation is None else f"world-{case_id}"],
        "evidence_versions": versions,
        "observation": world_observation if world_observation is not None else {"case": case},
        "admitted_options": admitted,
        "rejected_options": rejected,
    }


# ---------------------------------------------------------------------------
# 2. Agent
# ---------------------------------------------------------------------------


async def run_agent_session(prompt: str, **kwargs: Any) -> dict[str, Any]:
    """Wrapper around the canonical agent runner."""
    from api.functions.graphs.executors.agents._wrapper import (
        run_agent_session as _run,
    )

    return await _run(prompt, **kwargs)


def _review_note(payload: dict[str, Any]) -> str:
    feedback = payload.get("reviewer_feedback")
    if not isinstance(feedback, str) or not feedback.strip():
        return ""
    return (
        f"A reviewer sent your last assessment back: {feedback} Re-read the "
        "evidence with the tools and correct your reasoning; it must agree "
        "with the case.\n"
    )


def _agent_prompt(
    profile: CaseProfile,
    evidence: dict[str, Any],
    payload: dict[str, Any],
) -> str:
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
        "admitted_options": evidence["admitted_options"],
        "ranking_context": {
            "story_id": evidence["story_id"],
            "evidence_versions": evidence["evidence_versions"],
        },
    }
    return (
        "Use BOTH registered case tools before responding. "
        "First call banking_read_case_evidence, then "
        "banking_rank_admitted_case_options. "
        "Call each required tool at least once. Avoid repeating tool calls. "
        "Return one JSON object only, without markdown or extra keys. "
        f"Exact output keys: {json.dumps(sorted(_RANKING_KEYS))}. "
        "Rank every supplied admitted option ID exactly once. "
        "Do not add, drop, duplicate, or modify an option. "
        "reasoning MUST be a non-empty string covering the trade-offs, the "
        "uncertainty, and an explicit no-action comparison. "
        "Preserve the supplied actor_ids, event_ids and evidence_versions "
        "exactly.\n"
        f"{_review_note(payload)}"
        f"workflow_id={payload.get('workflow_id')}\n"
        f"instance_id={payload.get('instance_id')}\n"
        f"phase={profile.agent_phase}\n"
        f"skill={profile.skill}\n"
        f"source_mode=simulated\n"
        f"tool_input_evidence={json.dumps(tool_input_evidence, sort_keys=True)}\n"
        f"tool_input_ranking={json.dumps(tool_input_ranking, sort_keys=True)}"
    )


def _validate_agent_output(
    profile: CaseProfile,
    evidence: dict[str, Any],
    result: Any,
) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError("case agent response must be an object")
    if not _RANKING_KEYS <= set(result):
        raise ValueError(
            f"case agent response is missing keys: "
            f"{sorted(_RANKING_KEYS - set(result))}"
        )
    allowed = _RANKING_KEYS | {"_raw_tool_calls"}
    if not set(result) <= allowed:
        raise ValueError(
            f"case agent response has unknown keys: {sorted(set(result) - allowed)}"
        )

    calls = result.get("_raw_tool_calls")
    if not isinstance(calls, list) or not calls:
        raise ValueError("case agent requires successful declared tool calls")
    seen: set[str] = set()
    failed: set[str] = set()
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
            raise ValueError("case agent tool evidence is malformed")
        if call["name"] not in CASE_TOOL_NAMES:
            raise ValueError(
                f"case agent used an undeclared tool: {call['name']!r}; "
                f"declared tools are {sorted(CASE_TOOL_NAMES)}"
            )
        (seen if call["success"] else failed).add(call["name"])

    uncorrected = failed - seen
    if uncorrected:
        raise ValueError(
            f"case agent tool calls were unsuccessful: {sorted(uncorrected)}"
        )
    if seen != CASE_TOOL_NAMES:
        raise ValueError(
            f"case agent did not call all required tools; missing: "
            f"{sorted(CASE_TOOL_NAMES - seen)}"
        )

    if result["phase"] != profile.agent_phase:
        raise ValueError(
            f"case agent changed the phase; expected {profile.agent_phase!r}, "
            f"got {result['phase']!r}"
        )

    admitted_ids = [option["option_id"] for option in evidence["admitted_options"]]
    ranked = result["ranked_option_ids"]
    if (
        not isinstance(ranked, list)
        or any(not isinstance(option_id, str) for option_id in ranked)
        or len(ranked) != len(admitted_ids)
        or set(ranked) != set(admitted_ids)
        or len(set(ranked)) != len(ranked)
    ):
        raise ValueError(
            "case agent ranking must contain every admitted option exactly once; "
            f"admitted={sorted(admitted_ids)}, ranked={ranked!r}"
        )
    if not isinstance(result["reasoning"], str) or not result["reasoning"].strip():
        raise ValueError("case agent reasoning must be a non-empty string")
    if result.get("evidence_versions") != evidence["evidence_versions"]:
        raise ValueError("case agent changed evidence versions")
    if result.get("actor_ids") != evidence["actor_ids"]:
        raise ValueError("case agent changed actor IDs")
    if result.get("event_ids") != evidence["event_ids"]:
        raise ValueError("case agent changed event IDs")

    return {key: result[key] for key in _RANKING_KEYS}


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
        and call.get("name") in CASE_TOOL_NAMES
        and call.get("success") is True
    }
    failed = {
        call.get("name")
        for call in calls
        if isinstance(call, dict)
        and call.get("name") in CASE_TOOL_NAMES
        and call.get("success") is False
    }
    return bool(failed - succeeded)


def _corrective_prompt(
    original: str,
    *,
    reason: str = "The prior attempt produced no tool evidence.",
) -> str:
    return (
        f"{original}\n"
        f"CORRECTION: {reason} "
        f"You MUST call BOTH required tools "
        f"({', '.join(sorted(CASE_TOOL_NAMES))}) before responding."
    )


async def _run_case_agent(
    profile: CaseProfile,
    evidence: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    from api.functions.graphs.executors.agents.runtime import RequiredToolsNotCalledError

    session_kwargs: dict[str, Any] = dict(
        tools=list(_TOOLS),
        required_tool_names=[tool.name for tool in _TOOLS],
        skill_dir=_SKILL_ROOT / profile.skill,
        skill_label=profile.skill,
        workflow_id=payload.get("workflow_id"),
        instance_id=payload.get("instance_id"),
        phase=profile.agent_phase,
    )
    original_prompt = _agent_prompt(profile, evidence, payload)
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
                    f"{profile.agent_phase} timed out after "
                    f"{_AGENT_MAX_ATTEMPTS} attempts"
                ) from None
            prompt = _corrective_prompt(
                original_prompt,
                reason="The prior attempt timed out before producing tool evidence.",
            )
            continue
        except RequiredToolsNotCalledError:
            # The runtime refused an answer given before the evidence was read.
            if attempt + 1 == _AGENT_MAX_ATTEMPTS:
                raise
            prompt = _corrective_prompt(
                original_prompt,
                reason="The prior attempt answered before calling the required tools.",
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
    return _validate_agent_output(profile, evidence, result)


def case_agent_activity(payload: dict[str, Any]) -> dict[str, Any]:
    """Agent ranks only the deterministically admitted options."""
    workflow_type = _required_string(payload.get("workflow_type"), name="workflow_type")
    profile = PROFILES[workflow_type]
    evidence = _required_object(payload.get("evidence"), name="evidence")
    return asyncio.run(_run_case_agent(profile, evidence, payload))


# ---------------------------------------------------------------------------
# 3. Governance + command
# ---------------------------------------------------------------------------


def case_governance_activity(payload: dict[str, Any]) -> dict[str, Any]:
    workflow_type = _required_string(payload.get("workflow_type"), name="workflow_type")
    profile = PROFILES[workflow_type]
    selected = _required_object(payload.get("selected_option"), name="selected_option")
    value = selected.get("value_gbp")
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
        raise ValueError("selected_option.value_gbp must be finite")
    authority = kernel().check_authority(
        role=profile.hitl_persona,
        action=profile.command_type,
        category=profile.hitl_category,
        value=float(value),
    )
    return {
        "allowed": bool(authority.allowed),
        "reason": str(authority.reason),
        "governing_rule_id": authority.governing_rule_id,
    }


def case_command_activity(payload: dict[str, Any]) -> dict[str, Any]:
    """Record the typed disposition. No actor-world mutation applies here."""
    workflow_type = _required_string(payload.get("workflow_type"), name="workflow_type")
    profile = PROFILES[workflow_type]
    workflow_id = _required_string(payload.get("workflow_id"), name="workflow_id")
    approval = _required_object(payload.get("approval"), name="approval")
    hitl_context = _required_object(payload.get("hitl_context"), name="hitl_context")

    if approval.get("decision") != "approve":
        if approval.get("decision") == "reject" and approval.get("decided_by"):
            # A judged decline says why, in the persona's own words.
            who = str(approval.get("persona") or "the persona").replace("_", " ")
            return _denied(f"{who} declined to approve: {approval.get('reason') or 'no reason given'}")
        return _denied("decision must be approve")
    if approval.get("persona") != profile.hitl_persona:
        return _denied(f"approval persona must be {profile.hitl_persona}")
    option_id = approval.get("selected_option_id")
    admitted_ids = {
        option["option_id"] for option in hitl_context.get("admitted_options", [])
    }
    if option_id not in admitted_ids:
        return _denied("selected option is not deterministically admitted")
    if approval.get("evidence_versions") != hitl_context.get("evidence_versions"):
        return _denied("approval evidence is stale or incomplete")

    decision_id = _required_string(
        approval.get("decision_id"), name="approval.decision_id"
    )
    command = {
        "command_id": (
            f"SYN-{profile.prefix.upper()}-CMD-{workflow_id}-{decision_id}-{option_id}"
        ),
        "type": profile.command_type,
        "payload": {
            "workflow_id": workflow_id,
            "case_id": hitl_context.get("case_id"),
            "option_id": option_id,
            "persona": profile.hitl_persona,
            "decision_id": decision_id,
            "value_gbp": hitl_context.get("selected_option", {}).get("value_gbp"),
            "evidence_versions": hitl_context.get("evidence_versions"),
            "expected_event_type": profile.success_event,
        },
    }
    observation = hitl_context.get("observation") if isinstance(hitl_context.get("observation"), dict) else {}
    world_trace = observation.get("trace_id")
    if world_trace and profile.function:
        # A case the world noticed: the bridge applies this command back to the
        # world, whose gateway needs the case's trace and the owning function.
        command["trace_id"] = world_trace
        command["issued_by"] = profile.function
        command["payload"]["subject_id"] = (observation.get("case") or {}).get("subject_id")
    return {
        "status": "decision_ready",
        "command": command,
        "evaluation": {
            "status": "recorded",
            "success_event": profile.success_event,
            "world_mutation": "applied_by_world_bridge" if world_trace else "not_applicable",
        },
    }


# ---------------------------------------------------------------------------
# 4. Orchestration
# ---------------------------------------------------------------------------


def case_orchestration(
    profile: CaseProfile,
    context: df.DurableOrchestrationContext,
) -> Generator[Any, Any, dict[str, Any]]:
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
                "payload": {**event_payload, "workflow_type": profile.workflow_type},
            },
        )

    def terminal_checkpoint(result: dict[str, Any]) -> Any:
        return checkpoint(
            "workflow.completed",
            {"status": result["status"], "reason": result["reason"]},
        )

    yield checkpoint("workflow.started", {})
    yield checkpoint("step.started", {"step": profile.evidence_phase})
    evidence = yield context.call_activity(
        "case_evidence_activity_trigger", {**input_dict, "instance_id": instance_id}
    )
    yield checkpoint("step.completed", {"step": profile.evidence_phase})

    # A judged persona may send the case back to the agent with its reasons;
    # the agent then re-assesses once. Without judgement this runs once.
    reassessment_round = 0
    reviewer_feedback: str | None = None
    while True:
        yield checkpoint("step.started", {"step": profile.agent_phase})
        ranking = yield context.call_activity_with_retry(
            "case_agent_activity_trigger",
            _AGENT_RETRY,
            {
                **input_dict,
                "instance_id": instance_id,
                "workflow_type": profile.workflow_type,
                "phase": profile.agent_phase,
                "evidence": evidence,
                **({"reviewer_feedback": reviewer_feedback} if reviewer_feedback else {}),
            },
        )
        yield checkpoint("step.completed", {"step": profile.agent_phase})

        selected_option_id = ranking["ranked_option_ids"][0]
        selected_option = next(
            option
            for option in evidence["admitted_options"]
            if option["option_id"] == selected_option_id
        )

        authority = yield context.call_activity(
            "case_governance_activity_trigger",
            {
                "workflow_id": workflow_id,
                "workflow_type": profile.workflow_type,
                "selected_option": selected_option,
            },
        )
        if not authority.get("allowed"):
            denial = _denied(
                f"{profile.hitl_persona} is not authorised for this value: "
                f"{authority.get('reason') or 'governance denied'}"
            )
            yield terminal_checkpoint(denial)
            return denial

        hitl_context = {
            "workflow_id": workflow_id,
            "instance_id": instance_id,
            "workflow_type": profile.workflow_type,
            "story_id": evidence["story_id"],
            "case_id": evidence["case_id"],
            "persona": profile.hitl_persona,
            "external_event": profile.hitl_event,
            "phase": profile.hitl_phase,
            "action": profile.command_type,
            "request": {
                "amount_gbp": selected_option["value_gbp"],
                "category": profile.hitl_category,
            },
            "observation": evidence["observation"],
            "admitted_options": evidence["admitted_options"],
            "rejected_options": evidence["rejected_options"],
            "ranking": ranking,
            "selected_option": selected_option,
            "selected_option_id": selected_option_id,
            "decision_id": f"SYN-{profile.prefix.upper()}-DECISION-{workflow_id}",
            "evidence_versions": evidence["evidence_versions"],
            "authority": authority,
        }
        if reassessment_round:
            hitl_context["reassessment_round"] = reassessment_round
        yield checkpoint(
            "suspended",
            {
                "reason": "awaiting_approval",
                "phase": profile.hitl_phase,
                "persona": profile.hitl_persona,
                "external_event": profile.hitl_event,
                "context": hitl_context,
                "hitl_context": hitl_context,
            },
        )
        decision_event = context.wait_for_external_event(profile.hitl_event)
        timer = context.create_timer(context.current_utc_datetime + timedelta(minutes=5))
        winner = yield context.task_any([decision_event, timer])
        if winner == timer:
            denial = _denied(f"{profile.hitl_phase} timed out")
            yield terminal_checkpoint(denial)
            return denial
        timer.cancel()
        approval = decision_event.result
        yield checkpoint("resumed", {"phase": profile.hitl_phase})
        if (
            isinstance(approval, dict)
            and approval.get("decision") == "send_back"
            and reassessment_round < _MAX_REASSESSMENTS
        ):
            reassessment_round += 1
            reviewer_feedback = str(approval.get("feedback") or approval.get("reason") or "")
            continue
        break

    yield checkpoint("step.started", {"step": profile.commit_phase})
    decision = yield context.call_activity(
        "case_command_activity_trigger",
        {
            "workflow_id": workflow_id,
            "workflow_type": profile.workflow_type,
            "approval": approval,
            "hitl_context": hitl_context,
        },
    )
    if decision.get("status") != "decision_ready":
        yield terminal_checkpoint(decision)
        return decision
    yield checkpoint(
        "step.completed", {"step": profile.commit_phase, "status": "decision_ready"}
    )
    yield checkpoint(
        "step.completed", {"step": profile.verify_phase, "status": "recorded"}
    )
    # Success completion carries no status key. The terminal status vocabulary
    # is reserved for denials and timeouts; stamping a non-terminal value here
    # marks an otherwise healthy workflow as failed.
    yield checkpoint("workflow.completed", {})

    return {
        **decision,
        "workflow_id": workflow_id,
        "approval": approval,
        "workflow_evidence": evidence,
        "reasoning": {"ranking": ranking, "authority": authority},
        "hitl_context": hitl_context,
    }


def register(app: Any) -> None:
    """Wire the shared supporting activities and both orchestrators."""
    _act = app.activity_trigger(input_name="payload")
    _orch = app.orchestration_trigger(context_name="context")

    @_act
    def case_evidence_activity_trigger(payload: dict) -> dict:
        return case_evidence_activity(payload)

    @_act
    def case_agent_activity_trigger(payload: dict) -> dict:
        return case_agent_activity(payload)

    @_act
    def case_governance_activity_trigger(payload: dict) -> dict:
        return case_governance_activity(payload)

    @_act
    def case_command_activity_trigger(payload: dict) -> dict:
        return case_command_activity(payload)

    @_orch
    def BankingMuleAccountInvestigationOrchestrator(
        context: df.DurableOrchestrationContext,
    ) -> Generator:
        return (yield from case_orchestration(MULE_PROFILE, context))

    @_orch
    def BankingMerchantOnboardingRiskOrchestrator(
        context: df.DurableOrchestrationContext,
    ) -> Generator:
        return (yield from case_orchestration(MERCHANT_PROFILE, context))
