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
    # POC2 hiring spine
    build_hiring_budget_workflow,
    build_hiring_job_design_workflow,
    build_hiring_sourcing_workflow,
    build_hiring_triage_workflow,
    build_hiring_screening_workflow,
    build_hiring_voice_workflow,
    build_hiring_interview_workflow,
    build_hiring_compliance_workflow,
    build_hiring_offer_workflow,
    build_hiring_onboarding_workflow,
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


def hiring_job_design_activity(payload: dict) -> dict:
    """POC2 Phase 2 — Job Design (jd-drafter)."""
    return asyncio.run(_run_workflow(
        build_hiring_job_design_workflow, _with_phase(payload, "JobDesign"), "Job Design",
    ))


def hiring_sourcing_activity(payload: dict) -> dict:
    """POC2 Phase 3 — Sourcing (linkedin_search + greenhouse_post)."""
    return asyncio.run(_run_workflow(
        build_hiring_sourcing_workflow, _with_phase(payload, "Sourcing"), "Sourcing",
    ))


def hiring_triage_activity(payload: dict) -> dict:
    """POC2 Phase 4 — Triage / CV crystallisation (multimodal)."""
    return asyncio.run(_run_workflow(
        build_hiring_triage_workflow, _with_phase(payload, "Triage"), "Triage",
    ))


def hiring_screening_activity(payload: dict) -> dict:
    """POC2 Phase 5 — Screening (auto-shortlister, verdict drives Voice gating)."""
    return asyncio.run(_run_workflow(
        build_hiring_screening_workflow, _with_phase(payload, "Screening"), "Screening",
    ))


def hiring_voice_activity(payload: dict) -> dict:
    """POC2 Phase 6 — Voice screen (acs_dial + transcript_score)."""
    return asyncio.run(_run_workflow(
        build_hiring_voice_workflow, _with_phase(payload, "Voice"), "Voice",
    ))


def hiring_interview_activity(payload: dict) -> dict:
    """POC2 Phase 7 — Interview (graph_calendar + graph_mail panel scheduling)."""
    return asyncio.run(_run_workflow(
        build_hiring_interview_workflow, _with_phase(payload, "Interview"), "Interview",
    ))


def hiring_compliance_activity(payload: dict) -> dict:
    """POC2 Phase 8 — Compliance (jurisdiction-router; BetrVG on DE)."""
    return asyncio.run(_run_workflow(
        build_hiring_compliance_workflow, _with_phase(payload, "Compliance"), "Compliance",
    ))


def hiring_offer_activity(payload: dict) -> dict:
    """POC2 Phase 9 — Offer (offer-personaliser; non-revocable send hook-gated)."""
    return asyncio.run(_run_workflow(
        build_hiring_offer_workflow, _with_phase(payload, "Offer"), "Offer",
    ))


def hiring_onboarding_activity(payload: dict) -> dict:
    """POC2 Phase 10 — Onboarding (servicenow_jml + heygen_avatar + graph_invite)."""
    return asyncio.run(_run_workflow(
        build_hiring_onboarding_workflow, _with_phase(payload, "Onboarding"), "Onboarding",
    ))


def checkpoint_activity(payload: dict) -> dict:
    """Emit a lifecycle webhook event from the orchestrator."""
    asyncio.run(emit(
        payload.get("workflow_id", "?"),
        payload.get("instance_id"),
        payload["kind"],
        payload.get("payload", {}),
    ))
    return {}
