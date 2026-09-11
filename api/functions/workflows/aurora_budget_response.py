from __future__ import annotations

import hashlib
from collections.abc import Generator
from datetime import timedelta
from typing import Any

import azure.durable_functions as df


WORKFLOW_TYPE = "aurora-budget-response"
APPROVAL_EVENT = "aurora_budget_response_decision"
APPROVAL_TIMEOUT = timedelta(hours=24)


def _child_identity(workflow_id: str, invoice_id: str) -> tuple[str, str]:
    digest = hashlib.sha256(
        f"{workflow_id}:{invoice_id}".encode("utf-8")
    ).hexdigest()[:12].upper()
    return f"API-{digest}", f"aurora-ap-{digest.lower()}"


def _checkpoint(context, workflow_id: str, kind: str, payload: dict):
    return context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id,
        "instance_id": context.instance_id,
        "kind": kind,
        "payload": {"workflow_type": WORKFLOW_TYPE, **payload},
    })


def _output(context, workflow_id: str, slot: str, data: Any):
    return _checkpoint(
        context,
        workflow_id,
        "workflow.output",
        {"slot": slot, "data": data},
    )


def _start_phase(context, workflow_id: str, phase: str):
    return _checkpoint(context, workflow_id, "step.started", {"step": phase})


def _complete_phase(context, workflow_id: str, phase: str):
    return _checkpoint(context, workflow_id, "step.completed", {"step": phase})


def aurora_budget_response_orchestration(
    context: df.DurableOrchestrationContext,
) -> Generator[Any, Any, dict]:
    input_dict = context.get_input() or {}
    workflow_id = str(input_dict.get("workflow_id") or "?")
    brand_id = str(input_dict.get("brand_id") or "BRAND-aurora")
    count = max(1, min(20, int(input_dict.get("count", 3))))
    enriched = {
        **input_dict,
        "workflow_id": workflow_id,
        "brand_id": brand_id,
        "count": count,
        "instance_id": context.instance_id,
    }

    yield _checkpoint(context, workflow_id, "workflow.started", {
        "workflow": {
            "current_phase": "Observe budget signal",
            "jurisdiction": "London-Zava",
            "agency": "Zava",
            "payload": {
                "request_id": input_dict.get("request_id"),
                "brand_id": brand_id,
                "count": count,
            },
        },
    })

    phase = "Observe budget signal"
    yield _start_phase(context, workflow_id, phase)
    try:
        observation = yield context.call_activity(
            "aurora_observe_budget_activity_trigger",
            {**enriched, "target_pct": 1.0},
        )
    except Exception as exc:
        yield _checkpoint(context, workflow_id, "step.failed", {
            "step": phase, "reason": str(exc),
        })
        yield _checkpoint(context, workflow_id, "workflow.failed", {
            "outcome": "observation_failed", "reason": str(exc),
        })
        return {"status": "failed", "outcome": "observation_failed"}
    enriched["observation"] = observation
    yield _output(context, workflow_id, "observation", observation)
    yield _complete_phase(context, workflow_id, phase)

    phase = "Recommend response"
    yield _start_phase(context, workflow_id, phase)
    try:
        recommendation = yield context.call_activity(
            "aurora_recommendation_activity_trigger",
            enriched,
        )
    except Exception as exc:
        yield _checkpoint(context, workflow_id, "step.failed", {
            "step": phase, "reason": str(exc),
        })
        yield _checkpoint(context, workflow_id, "workflow.failed", {
            "outcome": "recommendation_failed", "reason": str(exc),
        })
        return {"status": "failed", "outcome": "recommendation_failed"}
    enriched["recommendation"] = recommendation
    yield _output(context, workflow_id, "recommendation", recommendation)
    yield _complete_phase(context, workflow_id, phase)

    phase = "Executive approval"
    yield _checkpoint(context, workflow_id, "suspended", {
        "reason": "awaiting_explicit_operator_approval",
        "phase": phase,
        "wait_kind": "operator_review",
        "persona": "cfo",
        "operator_only": True,
        "external_event": APPROVAL_EVENT,
        "context": {
            "operator_only": True,
            "workflow_id": workflow_id,
            "brand_id": brand_id,
            "action": recommendation["proposed_action"]["kind"],
            "category": recommendation["proposed_action"]["attributes"]["scope"],
            "proposed_action": recommendation["proposed_action"],
            "recommendation": recommendation["recommendation"],
        },
    })
    approval_task = context.wait_for_external_event(APPROVAL_EVENT)
    timeout_task = context.create_timer(
        context.current_utc_datetime + APPROVAL_TIMEOUT
    )
    winner = yield context.task_any([approval_task, timeout_task])
    if winner == timeout_task:
        yield _checkpoint(context, workflow_id, "workflow.failed", {
            "outcome": "approval_timeout",
            "reason": "Aurora operator approval timed out",
            "phase": phase,
        })
        return {"status": "failed", "outcome": "approval_timeout"}
    timeout_task.cancel()
    approval = approval_task.result or {}
    yield _checkpoint(context, workflow_id, "resumed", {
        "phase": phase,
        "decision_id": approval.get("decision_id"),
    })
    if approval.get("decision") == "reject":
        yield _checkpoint(context, workflow_id, "workflow.rejected", {
            "phase": phase,
            "reason": approval.get("reason") or "Operator rejected Aurora response",
            "by": approval.get("resolved_by"),
            "decision_id": approval.get("decision_id"),
        })
        return {
            "status": "rejected",
            "decision_id": approval.get("decision_id"),
        }
    if approval.get("decision") != "approve":
        yield _checkpoint(context, workflow_id, "workflow.failed", {
            "phase": phase,
            "outcome": "invalid_operator_decision",
            "reason": f"Unsupported operator decision {approval.get('decision')!r}",
        })
        return {"status": "failed", "outcome": "invalid_operator_decision"}

    phase = "Apply governed policy"
    yield _start_phase(context, workflow_id, phase)
    try:
        policy = yield context.call_activity(
            "aurora_apply_policy_activity_trigger",
            {
                **enriched,
                "approval": approval,
                "proposed_action": recommendation["proposed_action"],
            },
        )
    except Exception as exc:
        yield _checkpoint(context, workflow_id, "step.failed", {
            "step": phase, "reason": str(exc),
        })
        yield _checkpoint(context, workflow_id, "workflow.failed", {
            "outcome": "policy_application_denied",
            "reason": str(exc),
        })
        return {
            "status": "failed",
            "outcome": "policy_application_denied",
            "reason": str(exc),
        }
    enriched["policy"] = policy
    yield _output(context, workflow_id, "policy", policy)
    yield _complete_phase(context, workflow_id, phase)

    phase = "Queue AP invoice reviews"
    yield _start_phase(context, workflow_id, phase)
    child_tasks = []
    child_workflow_ids = []
    queued_invoice_ids = []
    selected_invoices = list(recommendation.get("selected_invoices") or [])
    if not selected_invoices:
        selected_ids = list(recommendation.get("selected_invoice_ids") or [])
        selected_invoices = [
            {
                "invoice_id": invoice_id,
                "brand_id": brand_id,
                "scenario": "matched-clean",
            }
            for invoice_id in selected_ids
        ]
    for invoice in selected_invoices:
        invoice_id = str(invoice["invoice_id"])
        child_workflow_id, child_instance_id = _child_identity(
            workflow_id, invoice_id
        )
        child_workflow_ids.append(child_workflow_id)
        queued_invoice_ids.append(invoice_id)
        child_tasks.append(context.call_sub_orchestrator(
            "FleetApInvoiceOrchestrator",
            {
                "workflow_id": child_workflow_id,
                "type": "ap-invoice",
                "parent_workflow_id": workflow_id,
                "invoice": {
                    **invoice,
                    "brand_id": brand_id,
                },
                "scenario": invoice.get("scenario") or "matched-clean",
            },
            instance_id=child_instance_id,
        ))
    yield _output(context, workflow_id, "children", [
        {
            "workflow_id": child_workflow_id,
            "invoice_id": invoice_id,
            "status": "queued",
        }
        for child_workflow_id, invoice_id
        in zip(child_workflow_ids, queued_invoice_ids, strict=True)
    ])
    try:
        child_results = yield context.task_all(child_tasks)
    except Exception as exc:
        yield _checkpoint(context, workflow_id, "step.failed", {
            "step": phase, "reason": str(exc),
        })
        yield _checkpoint(context, workflow_id, "workflow.failed", {
            "outcome": "child_execution_failed",
            "reason": str(exc),
            "child_workflow_ids": child_workflow_ids,
        })
        return {
            "status": "failed",
            "outcome": "child_execution_failed",
            "child_workflow_ids": child_workflow_ids,
        }
    yield _complete_phase(context, workflow_id, phase)

    phase = "Synthesise outcomes"
    yield _start_phase(context, workflow_id, phase)
    try:
        synthesis = yield context.call_activity(
            "aurora_synthesise_activity_trigger",
            {
                "workflow_id": workflow_id,
                "child_workflow_ids": child_workflow_ids,
                "queued_invoice_ids": queued_invoice_ids,
                "child_results": child_results,
            },
        )
    except Exception as exc:
        yield _checkpoint(context, workflow_id, "step.failed", {
            "step": phase, "reason": str(exc),
        })
        yield _checkpoint(context, workflow_id, "workflow.failed", {
            "outcome": "synthesis_failed", "reason": str(exc),
        })
        return {"status": "failed", "outcome": "synthesis_failed"}
    yield _output(context, workflow_id, "synthesis", synthesis)
    if synthesis.get("status") != "completed":
        yield _checkpoint(context, workflow_id, "step.failed", {
            "step": phase,
            "reason": "One or more AP child workflows failed",
        })
        yield _checkpoint(context, workflow_id, "workflow.failed", {
            "outcome": "child_failure",
            "reason": "One or more AP child workflows failed",
            "child_workflow_ids": child_workflow_ids,
        })
        return {
            "status": "failed",
            "outcome": "child_failure",
            "child_workflow_ids": child_workflow_ids,
            "synthesis": synthesis,
        }
    yield _complete_phase(context, workflow_id, phase)
    yield _checkpoint(context, workflow_id, "workflow.completed", {
        "status": "completed",
        "child_workflow_ids": child_workflow_ids,
    })
    return {
        "status": "completed",
        "workflow_id": workflow_id,
        "policy": policy,
        "child_workflow_ids": child_workflow_ids,
        "synthesis": synthesis,
    }
