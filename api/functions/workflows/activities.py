# src/functions/workflows/activities.py
"""
Activity functions registered as Azure Durable Functions activity triggers.
Each runs synchronously (Azure Durable Functions Python convention) and wraps an
async MAF Workflow run inside asyncio.run.

Activities are the I/O boundary — they call out to MCP servers (via the executors)
and fire webhooks back to FastAPI. The orchestration generator stays pure / deterministic.
"""
from __future__ import annotations
import asyncio

from api.functions.graphs import build_intake_workflow, build_approval_workflow
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
    return asyncio.run(_run_workflow(build_intake_workflow, payload, "Intake"))


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
