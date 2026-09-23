"""Banking Hero 1 - APP Fraud Reimbursement Durable core.

Six phases:

  1. Scope Fraud Claim                    deterministic
  2. Trace Beneficiary Path               deterministic (admission)
  3. Assess Claim Evidence                agent (two pack tools)
  4. Decide Reimbursement                 hitl (fraud_decision_manager)
  5. Execute Reimbursement and Recovery   deterministic (typed command)
  6. Verify Reimbursement Outcome         deterministic

The authority check runs *before* the gate is raised, so a claim whose
capped value sits above the claims manager's delegation terminates as an
escalation and the human is never asked to approve something they could not
authorise.

Pure activity functions are importable for tests; ``register(app)`` wires
the Durable triggers onto the pack's existing DFApp.
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
from verticals.banking.fraud_constants import (
    FRAUD_COMMAND_TYPE,
    FRAUD_DECISION_ID,
    FRAUD_HITL_CATEGORY,
    FRAUD_HITL_EVENT,
    FRAUD_HITL_PERSONA,
    FRAUD_ORCHESTRATOR,
    FRAUD_SCENARIO_STANDARD,
    FRAUD_SUCCESS_EVENT,
    FRAUD_WORKFLOW_TYPE,
)
from verticals.banking.fraud_constraints import admit_claim_options
from verticals.banking.mcp_tools.fraud import (
    TOOL_NAMES as FRAUD_TOOL_NAMES,
    banking_rank_admitted_claim_options,
    banking_read_claim_evidence,
)
from verticals.banking.worlds.active import resolve_active_banking_world
from verticals.banking.worlds.scenario import (
    ClaimObservationUnavailableError,
    ZavaBankWorld,
)

WORKFLOW_TYPE = FRAUD_WORKFLOW_TYPE
ORCHESTRATOR = FRAUD_ORCHESTRATOR
HITL_PERSONA = FRAUD_HITL_PERSONA
HITL_EVENT = FRAUD_HITL_EVENT
COMMAND_TYPE = FRAUD_COMMAND_TYPE
HITL_CATEGORY = FRAUD_HITL_CATEGORY

_SCOPE_PHASE = "Scope Fraud Claim"
_TRACE_PHASE = "Trace Beneficiary Path"
_AGENT_PHASE = "Assess Claim Evidence"
_HITL_PHASE = "Decide Reimbursement"
_COMMIT_PHASE = "Execute Reimbursement and Recovery"
_VERIFY_PHASE = "Verify Reimbursement Outcome"

_SKILL_ROOT = Path(__file__).resolve().parent / "skills"
_SKILL_LABEL = "claim-evidence-assessor"
_TOOLS = [banking_read_claim_evidence, banking_rank_admitted_claim_options]
# A model session can fail transiently (a session-auth blip, a rate limit).
# The agent activity only reads evidence and ranks options — the world is
# mutated by the separate command activity — so re-running it is safe, and
# each attempt is recorded in the orchestration history. Each attempt already
# retries a hung session internally (_AGENT_MAX_ATTEMPTS x 150 s), so two
# attempts keep the worst case (~10 min) inside the world bridge's 900 s wait.
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
_AGENT_ATTEMPT_TIMEOUT_SECONDS = 150.0


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
    # `reasoning` is the world bridge's contract key: it records the refusal
    # as responder.deferred carrying this text, instead of a bare failure.
    return {"status": "denied", "command": None, "reason": reason, "reasoning": reason}


def _active_world() -> ZavaBankWorld:
    try:
        return resolve_active_banking_world()
    except RuntimeError:
        if os.getenv("FUNCTIONS_WORKER_RUNTIME") != "python":
            raise
        from verticals.banking.lifecycle import ensure_banking_worker_world

        return ensure_banking_worker_world()


# ---------------------------------------------------------------------------
# 1. Scope Fraud Claim
# ---------------------------------------------------------------------------


def fraud_evidence_activity(
    payload: dict[str, Any],
    *,
    world: ZavaBankWorld | None = None,
) -> dict[str, Any]:
    """Validate the claim is in scope and snapshot its versioned evidence."""
    workflow_id = _required_string(payload.get("workflow_id"), name="workflow_id")
    if payload.get("type") != WORKFLOW_TYPE:
        raise ValueError(
            f"claim evidence has the wrong workflow type: expected "
            f"{WORKFLOW_TYPE!r}, got {payload.get('type')!r}"
        )

    supplied_observation = payload.get("observation")
    if (
        payload.get("diagnostic") is True
        and world is None
        and os.getenv("FUNCTIONS_WORKER_RUNTIME") == "python"
    ):
        from verticals.banking.lifecycle import reset_banking_worker_world

        reset_banking_worker_world()

    target_world = world if world is not None else _active_world()
    if world is None and isinstance(supplied_observation, dict):
        scenario_id = supplied_observation.get("scenario_id") or FRAUD_SCENARIO_STANDARD
        story_id = supplied_observation.get("story_id")
        if target_world.claim_story_status.get(story_id) != "active":
            target_world.activate_scenario(scenario_id)
        target_world.bind_scenario_trace(
            scenario_id,
            _required_string(
                supplied_observation.get("trace_id"),
                name="observation.trace_id",
            ),
        )
        observation = copy.deepcopy(supplied_observation)
    else:
        try:
            observation = copy.deepcopy(target_world.current_fraud_observation())
        except ClaimObservationUnavailableError as exc:
            raise ValueError(f"Banking world has no active claim: {exc}") from exc

    versions = _evidence_versions(
        observation.get("evidence_versions"),
        name="observation.evidence_versions",
    )
    event_ids = _identity_list(
        [event_id for event_id in (observation.get("evidence_event_ids") or []) if event_id],
        name="observation.event_ids",
    )
    actor_ids = sorted(versions)
    observation["actor_ids"] = actor_ids
    observation["event_ids"] = event_ids
    observation["evidence_versions"] = versions

    claim = _required_object(observation.get("claim"), name="observation.claim")
    return {
        "workflow_id": workflow_id,
        "story_id": observation.get("story_id"),
        "claim_id": claim.get("id"),
        "source_mode": "simulated",
        "actor_ids": actor_ids,
        "event_ids": event_ids,
        "evidence_versions": versions,
        "observation": observation,
    }


# ---------------------------------------------------------------------------
# 2. Trace Beneficiary Path (deterministic admission)
# ---------------------------------------------------------------------------


def _option_dict(result: Any) -> dict[str, Any]:
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


def fraud_trace_activity(payload: dict[str, Any]) -> dict[str, Any]:
    """Follow the funds and admit only the options the rules permit."""
    evidence = _required_object(payload.get("evidence"), name="evidence")
    observation = _required_object(
        evidence.get("observation"), name="evidence.observation"
    )
    beneficiary = _required_object(
        observation.get("beneficiary"), name="observation.beneficiary"
    )
    receiving_psp = _required_object(
        observation.get("receiving_psp"), name="observation.receiving_psp"
    )

    results = admit_claim_options(observation)
    admitted = [_option_dict(result) for result in results if result.feasible]
    rejected = [_option_dict(result) for result in results if not result.feasible]
    if not admitted:
        raise ValueError(
            "deterministic admission produced no permissible reimbursement option"
        )

    corporate_holder = observation.get("corporate_holder")
    return {
        "admitted_options": admitted,
        "rejected_options": rejected,
        "beneficiary_path": {
            "beneficiary_id": beneficiary.get("id"),
            "receiving_psp_id": receiving_psp.get("id"),
            "holder_id": beneficiary.get("holder_id"),
            "holder_kind": beneficiary.get("holder_kind"),
            "risk_band": beneficiary.get("risk_band"),
            "recoverable_gbp": beneficiary.get("balance_gbp"),
            "corporate_holder_id": (
                corporate_holder.get("id")
                if isinstance(corporate_holder, dict)
                else None
            ),
        },
    }


# ---------------------------------------------------------------------------
# 3. Assess Claim Evidence (agent)
# ---------------------------------------------------------------------------


async def run_agent_session(prompt: str, **kwargs: Any) -> dict[str, Any]:
    """Wrapper around the canonical agent runner."""
    from api.functions.graphs.executors.agents._wrapper import (
        run_agent_session as _run,
    )

    return await _run(prompt, **kwargs)


def _agent_prompt(payload: dict[str, Any]) -> str:
    evidence = _required_object(payload.get("evidence"), name="evidence")
    admitted_options = payload.get("admitted_options")
    if not isinstance(admitted_options, list) or not admitted_options:
        raise ValueError("admitted_options must contain deterministic options")
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
    output_keys = sorted(_RANKING_KEYS)
    return (
        "Use BOTH registered claim tools before responding. "
        "First call banking_read_claim_evidence, then "
        "banking_rank_admitted_claim_options. "
        "Call each required tool at least once. Avoid repeating tool calls. "
        "Return one JSON object only, without markdown or extra keys. "
        f"Exact output keys: {json.dumps(output_keys)}. "
        "Rank every supplied admitted option ID exactly once. "
        "Do not add, drop, duplicate, or modify an option. "
        "reasoning MUST be a non-empty string explaining the customer-harm, "
        "recovery, receiving-provider liability, vulnerability and no-action "
        "trade-offs. "
        "Preserve the supplied actor_ids, event_ids, and evidence_versions "
        "exactly.\n"
        f"workflow_id={payload.get('workflow_id')}\n"
        f"instance_id={payload.get('instance_id')}\n"
        f"phase={_AGENT_PHASE}\n"
        f"skill={_SKILL_LABEL}\n"
        f"source_mode=simulated\n"
        f"tool_input_evidence={json.dumps(tool_input_evidence, sort_keys=True)}\n"
        f"tool_input_ranking={json.dumps(tool_input_ranking, sort_keys=True)}"
    )


def _validate_agent_output(payload: dict[str, Any], result: Any) -> dict[str, Any]:
    evidence = _required_object(payload.get("evidence"), name="evidence")

    if not isinstance(result, dict):
        raise ValueError("claim agent response must be an object")
    allowed_keys = _RANKING_KEYS | {"_raw_tool_calls"}
    if not _RANKING_KEYS <= set(result):
        missing = sorted(_RANKING_KEYS - set(result))
        raise ValueError(f"claim agent response is missing required keys: {missing}")
    if not set(result) <= allowed_keys:
        extra = sorted(set(result) - allowed_keys)
        raise ValueError(f"claim agent response contains unknown keys: {extra}")

    calls = result.get("_raw_tool_calls")
    if not isinstance(calls, list) or not calls:
        raise ValueError("claim agent requires successful declared tool calls")
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
            raise ValueError("claim agent tool evidence is malformed")

        tool_name = call["name"]
        if tool_name not in FRAUD_TOOL_NAMES:
            raise ValueError(
                f"claim agent used an undeclared tool: {tool_name!r}; "
                f"declared tools are {sorted(FRAUD_TOOL_NAMES)}"
            )
        if call["success"]:
            seen_tools.add(tool_name)
        else:
            failed_tools.add(tool_name)

    uncorrected = failed_tools - seen_tools
    if uncorrected:
        raise ValueError(f"claim agent tool calls were unsuccessful: {sorted(uncorrected)}")
    if seen_tools != FRAUD_TOOL_NAMES:
        missing = sorted(FRAUD_TOOL_NAMES - seen_tools)
        raise ValueError(f"claim agent did not call all required tools; missing: {missing}")

    if result["phase"] != _AGENT_PHASE:
        raise ValueError(
            f"claim agent changed the phase; expected {_AGENT_PHASE!r}, "
            f"got {result['phase']!r}"
        )

    admitted_options = payload.get("admitted_options")
    if not isinstance(admitted_options, list) or not admitted_options:
        raise ValueError("claim agent ranking requires admitted options in payload")
    admitted_ids = [option.get("option_id") for option in admitted_options]
    ranked_ids = result["ranked_option_ids"]
    if (
        not isinstance(ranked_ids, list)
        or any(not isinstance(option_id, str) for option_id in ranked_ids)
        or len(ranked_ids) != len(admitted_ids)
        or len(set(ranked_ids)) != len(ranked_ids)
        or set(ranked_ids) != set(admitted_ids)
    ):
        raise ValueError(
            "claim agent ranking must contain every admitted option exactly once; "
            f"admitted={sorted(admitted_ids)}, ranked={ranked_ids!r}"
        )

    if not isinstance(result["reasoning"], str) or not result["reasoning"].strip():
        raise ValueError("claim agent reasoning must be a non-empty string")
    if result.get("evidence_versions") != evidence.get("evidence_versions"):
        raise ValueError("claim agent changed evidence versions")
    if result.get("actor_ids") != evidence.get("actor_ids"):
        raise ValueError("claim agent changed actor IDs")
    if result.get("event_ids") != evidence.get("event_ids"):
        raise ValueError("claim agent changed event IDs")

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
        and call.get("name") in FRAUD_TOOL_NAMES
        and call.get("success") is True
    }
    failed = {
        call.get("name")
        for call in calls
        if isinstance(call, dict)
        and call.get("name") in FRAUD_TOOL_NAMES
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
        f"({', '.join(sorted(FRAUD_TOOL_NAMES))}) before responding."
    )


async def _run_claim_agent(payload: dict[str, Any]) -> dict[str, Any]:
    session_kwargs: dict[str, Any] = dict(
        tools=list(_TOOLS),
        required_tool_names=[tool.name for tool in _TOOLS],
        skill_dir=_SKILL_ROOT / _SKILL_LABEL,
        skill_label=_SKILL_LABEL,
        workflow_id=payload.get("workflow_id"),
        instance_id=payload.get("instance_id"),
        phase=_AGENT_PHASE,
    )
    original_prompt = _agent_prompt(payload)
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
        if _has_failed_declared_tool_evidence(result) and attempt + 1 < _AGENT_MAX_ATTEMPTS:
            prompt = _corrective_prompt(
                original_prompt,
                reason="The prior attempt contained an unsuccessful declared tool call.",
            )
            continue
        break
    return _validate_agent_output(payload, result)


def fraud_agent_activity(payload: dict[str, Any]) -> dict[str, Any]:
    """Assess Claim Evidence - agent ranks only deterministically admitted options."""
    return asyncio.run(_run_claim_agent(payload))


# ---------------------------------------------------------------------------
# 4. Governance
# ---------------------------------------------------------------------------


def fraud_governance_activity(payload: dict[str, Any]) -> dict[str, Any]:
    """Real authority-matrix check for the selected option's value."""
    selected_option = _required_object(
        payload.get("selected_option"), name="selected_option"
    )
    value = selected_option.get("value_gbp")
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
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


def _approval_reason(
    approval: Any,
    *,
    workflow_id: str,
    story_id: str,
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
    if approval.get("story_id") not in (None, story_id):
        return "approval has the wrong story"
    return None


# ---------------------------------------------------------------------------
# 6. Command
# ---------------------------------------------------------------------------


def fraud_command_activity(
    payload: dict[str, Any],
    *,
    world: ZavaBankWorld | None = None,
) -> dict[str, Any]:
    """Build and apply the typed reimbursement command."""
    from verticals.banking.actions.fraud_commands import reimbursement_command_id

    workflow_id = _required_string(payload.get("workflow_id"), name="workflow_id")
    approval = _required_object(payload.get("approval"), name="approval")
    hitl_context = _required_object(payload.get("hitl_context"), name="hitl_context")
    expected_versions = _evidence_versions(
        hitl_context.get("evidence_versions"), name="hitl_context.evidence_versions"
    )
    claim_id = _required_string(hitl_context.get("claim_id"), name="hitl_context.claim_id")
    option_id = _required_string(
        approval.get("selected_option_id"), name="approval.selected_option_id"
    )
    decision_id = _required_string(
        approval.get("decision_id"), name="approval.decision_id"
    )

    target_world = world if world is not None else _active_world()
    command_id = reimbursement_command_id(
        workflow_id=workflow_id, decision_id=decision_id, option_id=option_id
    )
    is_retry = target_world.command_was_processed(command_id)

    if is_retry:
        try:
            command = target_world.command_for_claim_option(
                claim_id=claim_id,
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
            version_source = target_world.observation_for_claim(claim_id)
        except ClaimObservationUnavailableError as exc:
            return _denied(f"selected option is stale or infeasible: {exc}")

    current_versions = _evidence_versions(
        version_source.get("evidence_versions"), name="current_world.evidence_versions"
    )
    if current_versions != expected_versions:
        return _denied("world evidence is stale relative to the HITL checkpoint")

    if not is_retry:
        try:
            command = target_world.command_for_claim_option(
                claim_id=claim_id,
                option_id=option_id,
                workflow_id=workflow_id,
                decision_id=decision_id,
                persona=HITL_PERSONA,
            )
        except (ClaimObservationUnavailableError, ValueError) as exc:
            return _denied(f"selected option is stale or infeasible: {exc}")
        command_versions = _evidence_versions(
            command.payload.get("evidence_versions"), name="command.evidence_versions"
        )
        if command_versions != expected_versions:
            return _denied(
                "world evidence became stale while constructing the command"
            )

    gateway_event = target_world.apply_command(command)
    if gateway_event.type != FRAUD_SUCCESS_EVENT:
        reason = str(
            gateway_event.payload.get("reason") or "world command gateway denied"
        )
        return {**_denied(reason), "gateway_event": gateway_event.to_dict()}

    return {
        "status": "decision_ready",
        "command": command.to_dict(),
        "gateway_event": gateway_event.to_dict(),
        "evaluation": {
            "status": "pending_world_event_pipeline",
            "success_event": FRAUD_SUCCESS_EVENT,
        },
    }


# ---------------------------------------------------------------------------
# 7. Orchestration
# ---------------------------------------------------------------------------


def fraud_orchestration(
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
                "payload": {**event_payload, "workflow_type": WORKFLOW_TYPE},
            },
        )

    def terminal_checkpoint(result: dict[str, Any]) -> Any:
        return checkpoint(
            "workflow.completed",
            {"status": result["status"], "reason": result["reason"]},
        )

    # --- Phase 1 ---
    yield checkpoint("workflow.started", {})
    yield checkpoint("step.started", {"step": _SCOPE_PHASE})
    evidence = yield context.call_activity(
        "fraud_evidence_activity_trigger",
        {**input_dict, "instance_id": instance_id},
    )
    yield checkpoint("step.completed", {"step": _SCOPE_PHASE})

    # --- Phase 2 ---
    yield checkpoint("step.started", {"step": _TRACE_PHASE})
    admission = yield context.call_activity(
        "fraud_trace_activity_trigger",
        {**input_dict, "instance_id": instance_id, "evidence": evidence},
    )
    yield checkpoint("step.completed", {"step": _TRACE_PHASE})
    admitted_options = admission["admitted_options"]

    # --- Phase 3 ---
    yield checkpoint("step.started", {"step": _AGENT_PHASE})
    ranking = yield context.call_activity_with_retry(
        "fraud_agent_activity_trigger",
        _AGENT_RETRY,
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
        option for option in admitted_options if option["option_id"] == selected_option_id
    )

    # Authority is resolved before the gate is raised.
    authority = yield context.call_activity(
        "fraud_governance_activity_trigger",
        {
            "workflow_id": workflow_id,
            "instance_id": instance_id,
            "selected_option": selected_option,
        },
    )
    if not authority.get("allowed"):
        # Stamp the decision phase and carry the governing rule in the reason.
        # The rejection handler persists `phase` as `rejected_at_phase` and the
        # reason as `rejection_reason`, so the surfaces can say the workflow
        # was refused *at the decision* by the authority matrix, rather than
        # appearing to have failed in the preceding agent phase.
        rule_id = authority.get("governing_rule_id") or "no matching rule"
        why = authority.get("reason") or "governance denied"
        denial = _denied(
            f"{HITL_PERSONA} is not authorised to approve "
            f"GBP {float(selected_option['value_gbp']):,.2f} for "
            f"{HITL_CATEGORY}: {why}"
            + ("" if rule_id in why else f" (matched rule {rule_id})")
        )
        yield checkpoint(
            "workflow.completed",
            {
                "status": denial["status"],
                "reason": denial["reason"],
                "phase": _HITL_PHASE,
            },
        )
        return denial

    # --- Phase 4 (HITL) ---
    hitl_context = {
        "workflow_id": workflow_id,
        "instance_id": instance_id,
        "workflow_type": WORKFLOW_TYPE,
        "story_id": evidence["story_id"],
        "claim_id": evidence["claim_id"],
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
        "beneficiary_path": admission["beneficiary_path"],
        "ranking": ranking,
        "selected_option": selected_option,
        "selected_option_id": selected_option_id,
        "decision_id": FRAUD_DECISION_ID,
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

    denial_reason = _approval_reason(
        approval,
        workflow_id=workflow_id,
        story_id=evidence["story_id"],
        selected_option=selected_option,
        admitted_options=admitted_options,
        evidence_versions=evidence["evidence_versions"],
    )
    if denial_reason is not None:
        denial = _denied(denial_reason)
        yield terminal_checkpoint(denial)
        return denial

    # --- Phase 5 ---
    yield checkpoint("step.started", {"step": _COMMIT_PHASE})
    decision = yield context.call_activity(
        "fraud_command_activity_trigger",
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
        "step.completed", {"step": _COMMIT_PHASE, "status": "decision_ready"}
    )

    # --- Phase 6 ---
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


def register(app: Any) -> None:
    """Wire Hero 1 triggers onto the pack's DFApp."""
    _act = app.activity_trigger(input_name="payload")
    _orch = app.orchestration_trigger(context_name="context")

    @_act
    def fraud_evidence_activity_trigger(payload: dict) -> dict:
        return fraud_evidence_activity(payload)

    @_act
    def fraud_trace_activity_trigger(payload: dict) -> dict:
        return fraud_trace_activity(payload)

    @_act
    def fraud_agent_activity_trigger(payload: dict) -> dict:
        return fraud_agent_activity(payload)

    @_act
    def fraud_governance_activity_trigger(payload: dict) -> dict:
        return fraud_governance_activity(payload)

    @_act
    def fraud_command_activity_trigger(payload: dict) -> dict:
        return fraud_command_activity(payload)

    @_orch
    def BankingAppFraudReimbursementOrchestrator(
        context: df.DurableOrchestrationContext,
    ) -> Generator:
        return (yield from fraud_orchestration(context))
