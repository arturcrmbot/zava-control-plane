# src/functions/workflows/activities.py
"""
Activity functions registered as Azure Durable Functions activity triggers.
Each runs synchronously (Azure Durable Functions Python convention) and wraps an
async MAF Workflow run inside asyncio.run.

Activities are the I/O boundary — they call out to MCP servers (via the executors)
and fire webhooks back to FastAPI. The orchestration generator stays pure /
deterministic.

Phases 3-7 are stubbed (`NotImplementedError`); they get wired progressively as
their graphs land in Days 7-10 and Week 3.
"""
from __future__ import annotations
import asyncio

from api.functions.graphs import (
    build_intake_workflow,
    build_intake_expense_workflow,
    build_classify_workflow,
    build_receipt_workflow,
    build_route_workflow,
    build_notify_workflow,
    build_arbitrate_workflow,
    build_audit_workflow,
    build_approval_workflow,
    # POC2 hiring spine — Budget + Voice are the only per-phase activities
    # that survive after segments became the only path (refactor commit —
    # drop HIRING_SEGMENT_MODE flag). Job Design / Sourcing / Triage /
    # Screening / Compliance / Offer / Onboarding / Interview-Recommender
    # are now folded into the segment activities (hiring_segment_b/d/e/f
    # in api.functions.segments).
    build_hiring_budget_workflow,
    build_hiring_voice_workflow,
)
from api.functions.webhook import emit


async def _run_workflow(workflow_factory, payload: dict, step_name: str) -> dict:
    """Run a freshly-built MAF Workflow and return the first output dict."""
    wf = workflow_factory()
    await emit(payload.get("workflow_id", "?"), payload.get("instance_id"),
               "step.started", {"step": step_name})
    import time as _t
    t0 = _t.time()
    try:
        events = await wf.run(payload)
    except Exception as ex:
        await emit(payload.get("workflow_id", "?"), payload.get("instance_id"),
                   "step.failed", {"step": step_name, "error": str(ex)})
        raise
    outputs = events.get_outputs()
    result = outputs[0] if outputs else {}
    await emit(payload.get("workflow_id", "?"), payload.get("instance_id"),
               "step.completed", {"step": step_name, "duration_ms": int((_t.time() - t0) * 1000)})
    return result


def intake_activity(payload: dict) -> dict:
    """Phase 1 — runs the expense-claim Intake graph by default. Falls back
    to the legacy invoice graph only when payload.type == 'invoice-p2p'."""
    if payload.get("type") == "invoice-p2p":
        return asyncio.run(_run_workflow(build_intake_workflow, payload, "Intake"))
    return asyncio.run(_run_workflow(build_intake_expense_workflow, payload, "Intake"))


def classify_activity(payload: dict) -> dict:
    """Phase 2 — Classify (R/A/G) graph: agent_rag_classifier + schema validator."""
    return asyncio.run(_run_workflow(build_classify_workflow, payload, "Classify"))


def receipt_activity(payload: dict) -> dict:
    """Phase 3 — multimodal receipt cross-validation graph."""
    return asyncio.run(_run_workflow(build_receipt_workflow, payload, "Validate Receipt"))


def route_activity(payload: dict) -> dict:
    """Phase 4 — escalation advisor + verdict routing.

    After the graph resolves, surface the verdict to the FastAPI tier so the
    fleet bus can fire `claim.routed.{green,amber,red}` — the Fleet Manager
    rail uses this signal to wake on red routes before any HITL gate trips.
    """
    result = asyncio.run(_run_workflow(build_route_workflow, payload, "Route"))
    asyncio.run(emit(
        payload.get("workflow_id", "?"),
        payload.get("instance_id"),
        "claim_routed",
        {
            "verdict": result.get("verdict"),
            "routed_to": result.get("routed_to"),
            "escalation_tier": result.get("escalation_tier"),
        },
    ))
    return result


def notify_activity(payload: dict) -> dict:
    """Phase 5 — compose breach notification (Red path only)."""
    return asyncio.run(_run_workflow(build_notify_workflow, payload, "Notify"))


def arbitrate_activity(payload: dict) -> dict:
    """Phase 6 — SSC reviewer arbitration on Red claims (post-justification)."""
    return asyncio.run(_run_workflow(build_arbitrate_workflow, payload, "Arbitrate"))


def audit_activity(payload: dict) -> dict:
    """Phase 7 — narrative audit summary over the workflow's ledger."""
    return asyncio.run(_run_workflow(build_audit_workflow, payload, "Audit"))


# Approval activity retained for the legacy invoice-p2p orchestrator (broken at runtime
# until either rewired or removed in Week 3).
def approval_activity(payload: dict) -> dict:
    return asyncio.run(_run_workflow(build_approval_workflow, payload, "Approval"))


# ---------------------------------------------------------------------------
# POC2 hiring activities — one per phase. Each tags the payload with `phase`
# so the stub agent + UI can show the current phase in spans/events. Every
# activity follows the same shape as the expense-claim activities above.
# ---------------------------------------------------------------------------

def _with_phase(payload: dict, phase: str) -> dict:
    return {**payload, "phase": phase}


def hiring_budget_activity(payload: dict) -> dict:
    """POC2 Phase 1 — Budget (Workday position + Finance BP HITL upstream)."""
    return asyncio.run(_run_workflow(
        build_hiring_budget_workflow, _with_phase(payload, "Budget"), "Budget",
    ))


def hiring_voice_activity(payload: dict) -> dict:
    """POC2 Phase 6 — Voice screen (acs_dial + transcript_score)."""
    return asyncio.run(_run_workflow(
        build_hiring_voice_workflow, _with_phase(payload, "Voice"), "Voice",
    ))


# Phase 6 voice-screen activities live in their own module so they can be
# imported (e.g. from tests) without dragging in the agent-framework graph
# stack via `api.functions.graphs.*`. We re-export here so function_app.py's
# registration block stays unchanged.
from api.functions.workflows.voice_screen_activities import (  # noqa: E402
    issue_screen_link_activity,
    send_screen_email_activity,
)
from api.functions.workflows.interview_activities import (  # noqa: E402
    issue_book_interview_link_activity,
    send_book_interview_email_activity,
    send_rejection_email_activity,
)

__all__ = list(globals().get("__all__", [])) + [
    "issue_screen_link_activity",
    "send_screen_email_activity",
    "issue_book_interview_link_activity",
    "send_book_interview_email_activity",
    "send_rejection_email_activity",
]


def checkpoint_activity(payload: dict) -> dict:
    """Emit a lifecycle webhook event from the orchestrator."""
    asyncio.run(emit(
        payload.get("workflow_id", "?"),
        payload.get("instance_id"),
        payload["kind"],
        payload.get("payload", {}),
    ))
    return {}
