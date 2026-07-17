from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import azure.durable_functions as df


@dataclass(frozen=True)
class CascadeSpec:
    workflow_type: str
    phases: tuple[tuple[str, str], ...]
    approval_phase: str
    approval_event: str
    approval_persona: str


CASCADE_SPECS = {
    "outage-risk-management": CascadeSpec(
        workflow_type="outage-risk-management",
        phases=(
            ("Assess Weather Risk", "deterministic"),
            ("Plan Pre-Staging", "agent"),
            ("Approve Exceptional Spend", "hitl"),
            ("Pre-Stage Resources", "deterministic"),
        ),
        approval_phase="Approve Exceptional Spend",
        approval_event="delivery_lead_decision",
        approval_persona="delivery_lead",
    ),
    "predictive-site-maintenance": CascadeSpec(
        workflow_type="predictive-site-maintenance",
        phases=(
            ("Diagnose Failure Risk", "agent"),
            ("Plan Maintenance", "deterministic"),
            ("Approve Replacement", "hitl"),
            ("Create Work Order", "deterministic"),
        ),
        approval_phase="Approve Replacement",
        approval_event="delivery_lead_decision",
        approval_persona="delivery_lead",
    ),
    "field-repair-dispatch": CascadeSpec(
        workflow_type="field-repair-dispatch",
        phases=(
            ("Match Field Resources", "agent"),
            ("Validate Dispatch", "deterministic"),
            ("Approve Dispatch Exception", "hitl"),
            ("Dispatch Repair", "deterministic"),
        ),
        approval_phase="Approve Dispatch Exception",
        approval_event="delivery_lead_decision",
        approval_persona="delivery_lead",
    ),
    "capacity-optimization": CascadeSpec(
        workflow_type="capacity-optimization",
        phases=(
            ("Diagnose Congestion", "deterministic"),
            ("Plan Capacity Action", "agent"),
            ("Approve Capital Action", "hitl"),
            ("Apply Capacity Action", "deterministic"),
        ),
        approval_phase="Approve Capital Action",
        approval_event="network_ops_director_decision",
        approval_persona="network_ops_director",
    ),
    "service-ticket-resolution": CascadeSpec(
        workflow_type="service-ticket-resolution",
        phases=(
            ("Correlate Root Cause", "agent"),
            ("Plan Ticket Resolution", "deterministic"),
            ("Review Vulnerable Customers", "hitl"),
            ("Resolve Ticket Batch", "deterministic"),
        ),
        approval_phase="Review Vulnerable Customers",
        approval_event="cs_manager_decision",
        approval_persona="cs_manager",
    ),
    "retention-orchestration": CascadeSpec(
        workflow_type="retention-orchestration",
        phases=(
            ("Analyse Churn Drivers", "agent"),
            ("Select Retention Offer", "agent"),
            ("Approve High-Value Offer", "hitl"),
            ("Issue Retention Offer", "deterministic"),
        ),
        approval_phase="Approve High-Value Offer",
        approval_event="cs_manager_decision",
        approval_persona="cs_manager",
    ),
}


def telco_cascade_orchestration(
    context: df.DurableOrchestrationContext,
    workflow_type: str,
) -> Generator[Any, Any, dict]:
    spec = CASCADE_SPECS[workflow_type]
    input_dict = context.get_input() or {}
    workflow_id = input_dict.get("workflow_id", "?")
    instance_id = context.instance_id

    def checkpoint(kind: str, payload: dict) -> Any:
        return context.call_activity(
            "checkpoint_activity_trigger",
            {
                "workflow_id": workflow_id,
                "instance_id": instance_id,
                "kind": kind,
                "payload": {**payload, "workflow_type": workflow_type},
            },
        )

    yield checkpoint("workflow.started", {})
    decision: dict[str, Any] = {}
    approval: dict[str, Any] = {"decision": "not_required"}

    for phase, kind in spec.phases:
        if kind == "hitl":
            if not decision.get("requires_approval"):
                continue
            yield checkpoint(
                "suspended",
                {
                    "reason": "awaiting_approval",
                    "phase": phase,
                    "wait_kind": "operator_review",
                    "persona": spec.approval_persona,
                    "external_event": spec.approval_event,
                    "context": decision.get("approval_context", {}),
                },
            )
            decision_event = context.wait_for_external_event(spec.approval_event)
            timer = context.create_timer(
                context.current_utc_datetime + timedelta(minutes=5)
            )
            winner = yield context.task_any([decision_event, timer])
            if winner == timer:
                return {
                    "status": "timeout",
                    "command": None,
                    "reasoning": f"{phase} timed out",
                }
            timer.cancel()
            approval = decision_event.result or {}
            yield checkpoint("resumed", {"phase": phase})
            if approval.get("decision") != "approve":
                return {
                    "status": "denied",
                    "command": None,
                    "reasoning": f"{phase} denied",
                }
            continue

        yield checkpoint("step.started", {"step": phase})
        if kind == "agent":
            decision = yield context.call_activity(
                "telco_cascade_decision_activity_trigger",
                {
                    **input_dict,
                    "instance_id": instance_id,
                    "type": workflow_type,
                    "phase": phase,
                    "prior_decision": decision,
                },
            )
        yield checkpoint("step.completed", {"step": phase})

    command = decision.get("command")
    if isinstance(command, dict):
        command = {
            **command,
            "payload": {
                **(command.get("payload") or {}),
                "approval_decision": approval.get("decision"),
            },
        }
    return {
        "status": "decision_ready",
        "command": command,
        "reasoning": decision.get("reasoning"),
        "observation": input_dict.get("observation"),
    }


def outage_risk_management_orchestration(context):
    return telco_cascade_orchestration(context, "outage-risk-management")


def predictive_site_maintenance_orchestration(context):
    return telco_cascade_orchestration(context, "predictive-site-maintenance")


def field_repair_dispatch_orchestration(context):
    return telco_cascade_orchestration(context, "field-repair-dispatch")


def capacity_optimization_orchestration(context):
    return telco_cascade_orchestration(context, "capacity-optimization")


def service_ticket_resolution_orchestration(context):
    return telco_cascade_orchestration(context, "service-ticket-resolution")


def retention_orchestration(context):
    return telco_cascade_orchestration(context, "retention-orchestration")
