"""AOG Engineering Recovery – workflow detail view.

Provides a focused detail dict for aog-engineering-recovery workflows.
All evidence is sourced only from observed payload; no fabrication.
"""
from __future__ import annotations

from typing import Any, Mapping

from api.shared.types import Workflow
from verticals.airline.aog_constants import (
    AOG_COMMAND_TYPE,
    AOG_HITL_PERSONA,
    AOG_SCENARIO_ID,
    AOG_STORY_ID,
    AOG_WORKFLOW_TYPE,
)


def _m(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _observation(payload: dict) -> Mapping[str, Any]:
    evidence = _m(payload.get("evidence"))
    wfe = _m(evidence.get("workflow_evidence"))
    obs = wfe.get("observation")
    if isinstance(obs, Mapping):
        return obs
    obs2 = evidence.get("observation")
    return _m(obs2)


def _baseline(obs: Mapping[str, Any]) -> dict[str, Any]:
    tech = _m(obs.get("technical_status"))
    task = _m(obs.get("maintenance_task"))
    no_action = _m(obs.get("no_action_baseline"))
    return {
        "affected_tail_id": obs.get("affected_tail_id"),
        "rotation_id": obs.get("rotation_id"),
        "technical_status_id": tech.get("id"),
        "technical_status": str(tech.get("status") or ""),
        "maintenance_task_id": task.get("id"),
        "no_action": dict(no_action),
    }


def _admission(evidence: Mapping[str, Any]) -> tuple[list[dict], list[dict]]:
    reasoning = _m(evidence.get("reasoning"))
    admission = _m(reasoning.get("admission"))
    admitted = admission.get("admitted_options") or []
    rejected = admission.get("rejected_options") or []
    if not isinstance(admitted, list):
        admitted = []
    if not isinstance(rejected, list):
        rejected = []
    return (
        [dict(o) for o in admitted if isinstance(o, Mapping)],
        [dict(o) for o in rejected if isinstance(o, Mapping)],
    )


def _chosen(evidence: Mapping[str, Any], admitted: list[dict]) -> dict | None:
    approval = _m(evidence.get("approval"))
    option_id = approval.get("selected_option_id")
    context = _m(evidence.get("hitl_context"))
    option_id = option_id or context.get("selected_option_id")
    if not option_id:
        return None
    return next((o for o in admitted if o.get("option_id") == option_id), None)


def _governance(workflow: Workflow, evidence: Mapping[str, Any]) -> dict[str, Any]:
    approval = _m(evidence.get("approval"))
    is_pending = getattr(workflow, "status", "") == "awaiting_hitl"
    return {
        "status": "pending" if is_pending else approval.get("decision", "unknown"),
        "persona": approval.get("persona") or AOG_HITL_PERSONA,
        "decision_id": approval.get("decision_id"),
        "rationale": approval.get("rationale"),
        "governing_rule_id": _m(approval.get("authority")).get("governing_rule_id"),
    }


def _mutations(evidence: Mapping[str, Any]) -> dict | None:
    command = evidence.get("command")
    if not isinstance(command, Mapping):
        return None
    cp = _m(command.get("payload"))
    gateway = _m(evidence.get("gateway_event"))
    gp = _m(gateway.get("payload"))
    return {
        "command_id": command.get("command_id"),
        "command_type": command.get("type"),
        "workflow_id": cp.get("workflow_id"),
        "decision_id": cp.get("decision_id"),
        "option_id": cp.get("option_id"),
        "actions": list(cp.get("actions") or []),
        "business_event_id": gp.get("business_event_id"),
        "gateway_event_type": gateway.get("type"),
    }


def _timeline(
    obs: Mapping[str, Any],
    evidence: Mapping[str, Any],
    governance: dict[str, Any],
    evaluation: dict | None,
) -> list[dict[str, Any]]:
    reasoning = _m(evidence.get("reasoning"))
    return [
        {
            "phase": "Detect AOG Event",
            "kind": "deterministic",
            "status": "completed" if obs else "pending",
            "evidence": {
                "source_event_id": obs.get("source_event_id"),
                "sensor_event_id": obs.get("sensor_event_id"),
            },
        },
        {
            "phase": "Check Airworthiness Constraints",
            "kind": "deterministic",
            "status": ("completed" if isinstance(reasoning.get("admission"), Mapping) else "pending"),
            "evidence": reasoning.get("admission"),
        },
        {
            "phase": "Synthesize Engineering Recovery Options",
            "kind": "agent",
            "status": ("completed" if isinstance(reasoning.get("ranking"), Mapping) else "pending"),
            "evidence": reasoning.get("ranking"),
        },
        {
            "phase": "Approve Engineering Recovery",
            "kind": "hitl",
            "status": governance.get("status"),
            "evidence": dict(governance),
        },
        {
            "phase": "Commit Engineering and Operational Actions",
            "kind": "deterministic",
            "status": ("completed" if isinstance(evidence.get("command"), Mapping) else "pending"),
            "evidence": evidence.get("command"),
        },
        {
            "phase": "Verify Recovery State",
            "kind": "deterministic",
            "status": (evaluation.get("status") if evaluation is not None else "pending"),
            "evidence": evaluation,
        },
    ]


def aog_workflow_detail(
    workflow: Workflow,
    app_state: Any,
) -> Mapping[str, Any] | None:
    """Return AOG detail dict or None if observation is absent."""
    if getattr(workflow, "type", None) != AOG_WORKFLOW_TYPE:
        return None
    payload = workflow.payload if isinstance(workflow.payload, dict) else {}
    evidence = _m(payload.get("evidence"))
    obs = _observation(payload)
    if not obs:
        return None

    wfe = _m(evidence.get("workflow_evidence"))
    admitted, rejected = _admission(evidence)
    chosen = _chosen(evidence, admitted)
    governance = _governance(workflow, evidence)
    evaluation = None  # no live world access at detail time yet
    story = {
        "story_id": obs.get("story_id") or wfe.get("story_id") or AOG_STORY_ID,
        "scenario_id": obs.get("scenario_id") or AOG_SCENARIO_ID,
        "source_mode": wfe.get("source_mode", "simulated"),
        "source_event_id": obs.get("source_event_id"),
        "sensor_event_id": obs.get("sensor_event_id"),
    }
    return {
        "workflow_id": workflow.id,
        "story": story,
        "baseline": _baseline(obs),
        "chosen_admitted_option": chosen,
        "rejected_options": rejected,
        "governance": governance,
        "mutations": _mutations(evidence),
        "evaluation": evaluation,
        "timeline": _timeline(obs, evidence, governance, evaluation),
        "tools": ["airline_read_aog_evidence", "airline_rank_admitted_aog_options"],
        "command_contract": AOG_COMMAND_TYPE,
    }
