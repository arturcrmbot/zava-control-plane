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
    build_approval_workflow,
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
    """Phase 4 — escalation advisor + verdict routing."""
    return asyncio.run(_run_workflow(build_route_workflow, payload, "Route"))


def notify_activity(payload: dict) -> dict:
    """Phase 5 — compose breach notification (Red path only)."""
    return asyncio.run(_run_workflow(build_notify_workflow, payload, "Notify"))


def arbitrate_activity(payload: dict) -> dict:
    raise NotImplementedError("Phase 6 graph wired in Week 3 (build_arbitrate_workflow)")


def audit_activity(payload: dict) -> dict:
    raise NotImplementedError("Phase 7 graph wired in Week 3 (build_audit_workflow)")


# Approval activity retained for the legacy invoice-p2p orchestrator (broken at runtime
# until either rewired or removed in Week 3).
def approval_activity(payload: dict) -> dict:
    return asyncio.run(_run_workflow(build_approval_workflow, payload, "Approval"))


def checkpoint_activity(payload: dict) -> dict:
    """Emit a lifecycle webhook event from the orchestrator."""
    asyncio.run(emit(
        payload.get("workflow_id", "?"),
        payload.get("instance_id"),
        payload["kind"],
        payload.get("payload", {}),
    ))
    return {}
