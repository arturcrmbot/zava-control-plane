"""Blueprint microsite endpoints.

Two routes:

  - ``GET /api/blueprint/composition`` — JSON tree of skills, MCPs, domains
    and the edges between them. Drawn live from disk via
    ``blueprint_inventory.composition_tree``. Section 4 of the page reads
    this on mount.

  - ``GET /api/blueprint/stream`` — SSE feed of the live event bus, filtered
    to the event types section 5 ("the observatory") cares about. The
    payload per event is a slim shape the page can render directly:

        { type, skill, tool, domain, workflow_id, ts }

The stream subscribes to the in-process EventBus via the existing ``on_any``
API. One subscriber per browser tab.
"""

from __future__ import annotations

import asyncio
import json
import random
import time
from typing import Any

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from api.server.services.blueprint_inventory import DOMAINS, composition_tree
from api.server.state import app_state
from api.shared.events import FleetEvent

router = APIRouter()


# --------------------------------------------------------------------------
# Composition tree
# --------------------------------------------------------------------------


@router.get("/api/blueprint/composition")
async def get_composition() -> dict[str, Any]:
    return composition_tree()


# --------------------------------------------------------------------------
# Live observatory
#
# The EventBus carries FleetEvent objects whose `type` is constrained to the
# enum in api/shared/events.py. We forward a curated subset and translate it
# to the visual vocabulary the page understands.
# --------------------------------------------------------------------------


_OBSERVATORY_TYPES: set[str] = {
    "workflow.started",
    "durable.workflow.started",
    "durable.step.started",
    "durable.step.completed",
    "durable.executor.invoked",
    "agent.completed",
    "durable.validator.blocked",
    "workflow.exception.detected",
    "workflow.hitl.requested",
    "durable.suspended",
    "durable.workflow.completed",
    "workflow.resolved",
}


def _domain_from_workflow_type(workflow_type: str | None) -> str | None:
    """Map a runtime ``workflow_type`` string to the domain name shown on
    the page. Sourced from the DOMAINS manifest in blueprint_inventory so
    new domains do not need a separate edit here.

    Returns ``None`` when the workflow_type is unknown; the page handles
    that gracefully (no centre badge label).
    """
    if not workflow_type:
        return None
    for domain in DOMAINS:
        wt = domain.get("workflow_type")
        if wt and wt == workflow_type:
            return domain["name"]
    return None


def _normalise_event(event: FleetEvent) -> dict[str, Any] | None:
    if event.type not in _OBSERVATORY_TYPES:
        return None

    data = event.model_dump()

    skill = (
        data.get("skill")
        or data.get("skill_name")
        or data.get("agent")
        or data.get("agent_skill")
        or data.get("name")
        or data.get("executor")
    )
    tool = data.get("tool") or data.get("tool_name") or data.get("mcp_tool")
    workflow_id = (
        data.get("workflow_id")
        or data.get("workflowId")
        or data.get("instance_id")
        or data.get("instanceId")
    )
    workflow_type = data.get("workflow_type") or data.get("workflowType")
    domain = _domain_from_workflow_type(workflow_type)

    return {
        "type": event.type,
        "skill": skill,
        "tool": tool,
        "domain": domain,
        "workflow_id": workflow_id,
        "ts": data.get("ts") or time.time(),
    }


@router.get("/api/blueprint/stream")
async def blueprint_stream(request: Request) -> EventSourceResponse:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=200)
    loop = asyncio.get_running_loop()

    def _push(event: FleetEvent) -> None:
        normalised = _normalise_event(event)
        if normalised is None:
            return
        try:
            loop.call_soon_threadsafe(queue.put_nowait, normalised)
        except (RuntimeError, asyncio.QueueFull):
            pass

    unsubscribe = app_state.bus.on_any(_push)

    async def _gen():
        yield {"event": "hello", "data": json.dumps({"ts": time.time()})}
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield {"event": "event", "data": json.dumps(event)}
                except asyncio.TimeoutError:
                    yield {"event": "heartbeat", "data": "{}"}
        finally:
            try:
                unsubscribe()
            except Exception:
                pass

    return EventSourceResponse(_gen())


# --------------------------------------------------------------------------
# Dev-only event injector
#
# A tiny endpoint to fire scripted observatory events from curl when the
# Functions host isn't running. Used during dev to verify pulse animations
# and counters without booting the full demo stack. Safe to leave enabled —
# it only emits FleetEvents on the local in-process bus.
# --------------------------------------------------------------------------


_DEMO_SCRIPTS: dict[str, list[dict[str, Any]]] = {
    "hire-walk": [
        {"type": "workflow.started", "workflow_type": "hiring", "workflow_id": "HIRE-DEMO-DRY"},
        {"type": "durable.step.started", "skill": "cv-crystalliser", "workflow_type": "hiring", "workflow_id": "HIRE-DEMO-DRY"},
        {"type": "durable.executor.invoked", "skill": "cv-crystalliser", "tool": "ocr_extract", "workflow_type": "hiring", "workflow_id": "HIRE-DEMO-DRY"},
        {"type": "agent.completed", "skill": "cv-crystalliser", "workflow_type": "hiring", "workflow_id": "HIRE-DEMO-DRY"},
        {"type": "durable.step.started", "skill": "auto-shortlister", "workflow_type": "hiring", "workflow_id": "HIRE-DEMO-DRY"},
        {"type": "agent.completed", "skill": "auto-shortlister", "workflow_type": "hiring", "workflow_id": "HIRE-DEMO-DRY"},
        {"type": "workflow.hitl.requested", "workflow_type": "hiring", "workflow_id": "HIRE-DEMO-DRY"},
        {"type": "durable.workflow.completed", "workflow_type": "hiring", "workflow_id": "HIRE-DEMO-DRY"},
    ],
    "expense-walk": [
        {"type": "workflow.started", "workflow_type": "expense-claim", "workflow_id": "CLM-DEMO-DRY"},
        {"type": "durable.step.started", "skill": "field-extractor", "workflow_type": "expense-claim", "workflow_id": "CLM-DEMO-DRY"},
        {"type": "durable.executor.invoked", "skill": "rag-classifier", "tool": "policy_search", "workflow_type": "expense-claim", "workflow_id": "CLM-DEMO-DRY"},
        {"type": "agent.completed", "skill": "rag-classifier", "workflow_type": "expense-claim", "workflow_id": "CLM-DEMO-DRY"},
        {"type": "durable.executor.invoked", "skill": "receipt-validator", "tool": "ocr_extract", "workflow_type": "expense-claim", "workflow_id": "CLM-DEMO-DRY"},
        {"type": "durable.validator.blocked", "skill": "receipt-validator", "workflow_type": "expense-claim", "workflow_id": "CLM-DEMO-DRY"},
        {"type": "workflow.exception.detected", "workflow_type": "expense-claim", "workflow_id": "CLM-DEMO-DRY"},
        {"type": "durable.workflow.completed", "workflow_type": "expense-claim", "workflow_id": "CLM-DEMO-DRY"},
    ],
}


@router.post("/api/blueprint/_demo_emit")
async def demo_emit(script: str = "hire-walk", interval_ms: int = 350) -> dict[str, Any]:
    """Fire a scripted sequence of FleetEvents on the local bus, paced by
    interval_ms. Returns the count emitted. Dev-only; not wired into any
    customer-facing flow."""
    events = _DEMO_SCRIPTS.get(script, [])
    if not events:
        return {"emitted": 0, "available": list(_DEMO_SCRIPTS.keys())}
    delay = max(0.0, interval_ms / 1000.0)
    for raw in events:
        event = FleetEvent(**raw)
        app_state.bus.emit(event)
        if delay:
            await asyncio.sleep(delay)
    return {"emitted": len(events), "script": script}


# --------------------------------------------------------------------------
# Always-on demo stream
#
# Runs an indefinite background task that keeps the observatory alive by
# emitting plausible FleetEvents from a pool. Three workflows in flight at
# any one time, randomised event cadence (~1.0 to ~3.0 seconds between
# emissions). Started via POST /_demo_stream/start, stopped via /stop.
#
# Designed so the page reads as a continuously breathing operating
# environment, not a periodic demo with quiet gaps.
# --------------------------------------------------------------------------

# Pool of plausible per-domain workflow walks. Each entry is the ordered
# sequence of events one workflow goes through. The stream picks a workflow
# template, gives it a fresh id, and emits its events one at a time.
_STREAM_TEMPLATES: list[list[dict[str, Any]]] = [
    # Hiring — happy path
    [
        {"type": "workflow.started", "workflow_type": "hiring"},
        {"type": "durable.step.started", "skill": "cv-crystalliser", "workflow_type": "hiring"},
        {"type": "durable.executor.invoked", "skill": "cv-crystalliser", "tool": "ocr_extract", "workflow_type": "hiring"},
        {"type": "agent.completed", "skill": "cv-crystalliser", "workflow_type": "hiring"},
        {"type": "durable.step.started", "skill": "auto-shortlister", "workflow_type": "hiring"},
        {"type": "agent.completed", "skill": "auto-shortlister", "workflow_type": "hiring"},
        {"type": "durable.step.started", "skill": "interview-recommender", "workflow_type": "hiring"},
        {"type": "workflow.hitl.requested", "workflow_type": "hiring"},
        {"type": "durable.step.started", "skill": "offer-personaliser", "workflow_type": "hiring"},
        {"type": "agent.completed", "skill": "offer-personaliser", "workflow_type": "hiring"},
        {"type": "durable.workflow.completed", "workflow_type": "hiring"},
    ],
    # Hiring — jurisdiction route, slightly different shape
    [
        {"type": "workflow.started", "workflow_type": "hiring"},
        {"type": "durable.step.started", "skill": "jd-drafter", "workflow_type": "hiring"},
        {"type": "agent.completed", "skill": "jd-drafter", "workflow_type": "hiring"},
        {"type": "durable.step.started", "skill": "cv-crystalliser", "workflow_type": "hiring"},
        {"type": "durable.executor.invoked", "skill": "cv-crystalliser", "tool": "ocr_extract", "workflow_type": "hiring"},
        {"type": "agent.completed", "skill": "cv-crystalliser", "workflow_type": "hiring"},
        {"type": "durable.step.started", "skill": "jurisdiction-router", "workflow_type": "hiring"},
        {"type": "durable.executor.invoked", "skill": "jurisdiction-router", "tool": "policy_search", "workflow_type": "hiring"},
        {"type": "agent.completed", "skill": "jurisdiction-router", "workflow_type": "hiring"},
        {"type": "durable.workflow.completed", "workflow_type": "hiring"},
    ],
    # Expense — happy classify + audit
    [
        {"type": "workflow.started", "workflow_type": "expense-claim"},
        {"type": "durable.step.started", "skill": "field-extractor", "workflow_type": "expense-claim"},
        {"type": "agent.completed", "skill": "field-extractor", "workflow_type": "expense-claim"},
        {"type": "durable.step.started", "skill": "rag-classifier", "workflow_type": "expense-claim"},
        {"type": "durable.executor.invoked", "skill": "rag-classifier", "tool": "policy_search", "workflow_type": "expense-claim"},
        {"type": "agent.completed", "skill": "rag-classifier", "workflow_type": "expense-claim"},
        {"type": "durable.step.started", "skill": "audit-summariser", "workflow_type": "expense-claim"},
        {"type": "durable.executor.invoked", "skill": "audit-summariser", "tool": "audit_query", "workflow_type": "expense-claim"},
        {"type": "agent.completed", "skill": "audit-summariser", "workflow_type": "expense-claim"},
        {"type": "durable.workflow.completed", "workflow_type": "expense-claim"},
    ],
    # Expense — receipt mismatch (validator block)
    [
        {"type": "workflow.started", "workflow_type": "expense-claim"},
        {"type": "durable.step.started", "skill": "field-extractor", "workflow_type": "expense-claim"},
        {"type": "agent.completed", "skill": "field-extractor", "workflow_type": "expense-claim"},
        {"type": "durable.step.started", "skill": "receipt-validator", "workflow_type": "expense-claim"},
        {"type": "durable.executor.invoked", "skill": "receipt-validator", "tool": "ocr_extract", "workflow_type": "expense-claim"},
        {"type": "durable.validator.blocked", "skill": "receipt-validator", "workflow_type": "expense-claim"},
        {"type": "workflow.exception.detected", "workflow_type": "expense-claim"},
        {"type": "workflow.hitl.requested", "workflow_type": "expense-claim"},
        {"type": "durable.workflow.completed", "workflow_type": "expense-claim"},
    ],
    # Onboarding — short walk
    [
        {"type": "workflow.started", "workflow_type": "onboarding"},
        {"type": "durable.step.started", "skill": "onboarding-buddy", "workflow_type": "onboarding"},
        {"type": "agent.completed", "skill": "onboarding-buddy", "workflow_type": "onboarding"},
        {"type": "durable.workflow.completed", "workflow_type": "onboarding"},
    ],
]


_PREFIX_BY_TYPE = {
    "hiring": "HIRE",
    "expense-claim": "CLM",
    "onboarding": "ONB",
}


# Module-level handle so the stream survives across requests.
_stream_task: asyncio.Task | None = None


async def _stream_loop() -> None:
    """Indefinite trickle: keep up to 3 workflows in flight, drip events
    from each at randomised intervals so the page reads as continuous."""
    in_flight: list[dict[str, Any]] = []  # each entry: {events: [...], wid: str}
    try:
        while True:
            # Top up to 3 in-flight workflows.
            while len(in_flight) < 3:
                template = random.choice(_STREAM_TEMPLATES)
                wf_type = template[0].get("workflow_type", "hiring")
                prefix = _PREFIX_BY_TYPE.get(wf_type, "WF")
                wid = f"{prefix}-{random.randint(1000, 9999)}"
                in_flight.append({
                    "events": [dict(e, workflow_id=wid) for e in template],
                    "wid": wid,
                })

            # Pick one of the in-flight workflows at random and pop its next event.
            slot_idx = random.randrange(len(in_flight))
            slot = in_flight[slot_idx]
            event_data = slot["events"].pop(0)
            try:
                app_state.bus.emit(FleetEvent(**event_data))
            except Exception:
                pass
            if not slot["events"]:
                in_flight.pop(slot_idx)

            # Randomised cadence — fast enough to feel alive, slow enough to read.
            await asyncio.sleep(random.uniform(0.9, 2.4))
    except asyncio.CancelledError:
        return


@router.post("/api/blueprint/_demo_stream/start")
async def demo_stream_start() -> dict[str, Any]:
    """Start the always-on observatory event trickle. Idempotent."""
    global _stream_task
    if _stream_task is None or _stream_task.done():
        _stream_task = asyncio.create_task(_stream_loop())
        return {"status": "started"}
    return {"status": "already running"}


@router.post("/api/blueprint/_demo_stream/stop")
async def demo_stream_stop() -> dict[str, Any]:
    """Stop the always-on observatory event trickle. Idempotent."""
    global _stream_task
    if _stream_task and not _stream_task.done():
        _stream_task.cancel()
        try:
            await _stream_task
        except asyncio.CancelledError:
            pass
        _stream_task = None
        return {"status": "stopped"}
    return {"status": "not running"}


@router.get("/api/blueprint/_demo_stream/status")
async def demo_stream_status() -> dict[str, Any]:
    """Return whether the always-on stream is currently running."""
    running = _stream_task is not None and not _stream_task.done()
    return {"running": running}
