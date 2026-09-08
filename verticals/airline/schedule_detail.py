"""Preemptive Schedule Resilience – workflow detail view.

Provides a focused detail dict for preemptive-schedule-resilience workflows.
All evidence is sourced only from observed payload; no fabrication.
"""
from __future__ import annotations

from typing import Any, Mapping

from api.shared.types import Workflow
from verticals.airline.schedule_constants import (
    SCHED_COMMAND_TYPE,
    SCHED_HITL_PERSONA,
    SCHED_RISK_SIGNAL_ID,
    SCHED_SCENARIO_ID,
    SCHED_STORY_ID,
    SCHED_WORKFLOW_TYPE,
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
    risk_signal = _m(obs.get("risk_signal"))
    no_action = _m(obs.get("no_action_baseline"))
    return {
        "risk_signal_id": risk_signal.get("id") or SCHED_RISK_SIGNAL_ID,
        "forecast_confidence": obs.get("forecast_confidence"),
        "window_start_minutes": obs.get("window_start_minutes") or risk_signal.get("window_start_minutes"),
        "window_end_minutes": obs.get("window_end_minutes") or risk_signal.get("window_end_minutes"),
        "affected_sector_count": len(obs.get("affected_sectors") or []),
        "affected_aircraft_ids": [
            a.get("id") for a in (obs.get("affected_aircraft") or []) if isinstance(a, Mapping)
        ],
        "affected_crew_ids": [
            c.get("id") for c in (obs.get("affected_crew") or []) if isinstance(c, Mapping)
        ],
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
        "persona": approval.get("persona") or SCHED_HITL_PERSONA,
        "decision_id": approval.get("decision_id"),
        "rationale": approval.get("rationale"),
        "authority": _m(evidence.get("reasoning")).get("authority") if not is_pending else None,
    }


def _mutations(workflow: Workflow, evidence: Mapping[str, Any]) -> dict[str, Any] | None:
    cmd = _m(evidence.get("command"))
    if not cmd:
        return None
    return {
        "command_type": cmd.get("command_type") or SCHED_COMMAND_TYPE,
        "command_id": cmd.get("command_id"),
        "affected_actor_ids": list(cmd.get("affected_actor_ids") or []),
        "option_id": cmd.get("option_id"),
        "value_gbp": cmd.get("value_gbp"),
    }


def _evaluation(workflow: Workflow, evidence: Mapping[str, Any]) -> dict[str, Any] | None:
    eval_data = _m(evidence.get("evaluation"))
    if not eval_data:
        return None
    return {
        "status": eval_data.get("status"),
        "workflow_id": getattr(workflow, "id", None),
        "evaluation_id": eval_data.get("evaluation_id"),
        "predicted_delay_reduction_minutes": eval_data.get("predicted_delay_reduction_minutes"),
        "cancellations_reduced": eval_data.get("cancellations_reduced"),
        "capacity_retained_pct": eval_data.get("capacity_retained_pct"),
        "selected_action": eval_data.get("selected_action"),
        "uncertainty": eval_data.get("uncertainty"),
        "counterfactual": eval_data.get("counterfactual"),
    }


def _timeline(
    obs: Mapping[str, Any],
    evidence: Mapping[str, Any],
    governance: dict[str, Any],
) -> list[dict[str, Any]]:
    reasoning = _m(evidence.get("reasoning"))
    assess = reasoning.get("assess")
    admission = _m(reasoning.get("admission"))
    ranking = reasoning.get("ranking")
    cmd = evidence.get("command")
    eval_data = evidence.get("evaluation")
    return [
        {
            "phase": "Detect Schedule Risk Signal",
            "kind": "deterministic",
            "status": "completed" if obs else "pending",
            "evidence": {
                "source_event_id": obs.get("source_event_id"),
                "sensor_event_id": obs.get("sensor_event_id"),
                "risk_signal_id": (_m(obs.get("risk_signal")).get("id")) if obs else None,
            },
        },
        {
            "phase": "Assess Network Ripple Effects",
            "kind": "agent",
            "status": "completed" if isinstance(assess, Mapping) else "pending",
            "evidence": assess if isinstance(assess, Mapping) else None,
        },
        {
            "phase": "Synthesize Resilience Options",
            "kind": "agent",
            "status": "completed" if isinstance(ranking, Mapping) else "pending",
            "evidence": ranking if isinstance(ranking, Mapping) else None,
        },
        {
            "phase": "Approve Schedule Adjustment",
            "kind": "hitl",
            "status": governance.get("status"),
            "evidence": dict(governance),
        },
        {
            "phase": "Commit Schedule Adjustment",
            "kind": "deterministic",
            "status": "completed" if isinstance(cmd, Mapping) else "pending",
            "evidence": cmd if isinstance(cmd, Mapping) else None,
        },
        {
            "phase": "Verify Network Stability",
            "kind": "deterministic",
            "status": (
                _m(eval_data).get("status") if isinstance(eval_data, Mapping) else "pending"
            ),
            "evidence": eval_data if isinstance(eval_data, Mapping) else None,
        },
    ]


def schedule_workflow_detail(
    workflow: Workflow,
    _app_state: Any,
) -> Mapping[str, Any] | None:
    """Return a focused detail dict for a preemptive-schedule-resilience workflow."""
    payload = workflow.payload if isinstance(workflow.payload, dict) else {}
    evidence = _m(payload.get("evidence"))
    obs = _observation(payload)
    if not obs:
        return None

    admitted, rejected = _admission(evidence)
    chosen = _chosen(evidence, admitted)
    governance = _governance(workflow, evidence)
    mutations = _mutations(workflow, evidence)
    evaluation = _evaluation(workflow, evidence)

    wfe = _m(evidence.get("workflow_evidence"))
    story = {
        "story_id": obs.get("story_id") or SCHED_STORY_ID,
        "scenario_id": obs.get("scenario_id") or SCHED_SCENARIO_ID,
        "source_mode": wfe.get("source_mode", "simulated"),
        "source_event_id": obs.get("source_event_id"),
        "sensor_event_id": obs.get("sensor_event_id"),
    }

    return {
        "workflow_id": getattr(workflow, "id", None),
        "story": story,
        "baseline": _baseline(obs),
        "chosen_admitted_option": chosen,
        "rejected_options": rejected,
        "governance": governance,
        "mutations": mutations,
        "evaluation": evaluation,
        "timeline": _timeline(obs, evidence, governance),
        "tools": [
            "airline_read_schedule_risk_evidence",
            "airline_rank_admitted_resilience_options",
        ],
        "command_contract": SCHED_COMMAND_TYPE,
    }
