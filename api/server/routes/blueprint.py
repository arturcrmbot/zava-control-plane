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
import os
import random
import time
import time as _time
from typing import Any

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from api.server.services.blueprint_inventory import DOMAINS, composition_tree
from api.server.services.blueprint_recorder import (
    BlueprintRecorder,
    load_recorded_templates,
)
from api.server.state import app_state
from api.shared.events import FleetEvent

router = APIRouter()

# Module-level recorder handle. One per uvicorn process.
_recorder = BlueprintRecorder(app_state.runtime)


class _TokenBucket:
    """Simple per-second token bucket. Refills to capacity each wallclock second."""

    def __init__(self, capacity: int) -> None:
        self.capacity = max(1, capacity)
        self._tokens = self.capacity
        self._second = int(_time.time())
        self._dropped_in_second = 0

    def allow(self) -> bool:
        now_sec = int(_time.time())
        if now_sec != self._second:
            if self._dropped_in_second > 0:
                print(f"[blueprint] dropped {self._dropped_in_second} events "
                      f"(cap={self.capacity}/sec)")
            self._second = now_sec
            self._tokens = self.capacity
            self._dropped_in_second = 0
        if self._tokens > 0:
            self._tokens -= 1
            return True
        self._dropped_in_second += 1
        return False


def _make_event_cap() -> _TokenBucket:
    cap = int(os.getenv("MAX_OBSERVATORY_EVENTS_PER_SEC", "20"))
    return _TokenBucket(cap)


_OBSERVATORY_CAP = _make_event_cap()


def _make_event_queue() -> asyncio.Queue[dict[str, Any]]:
    return asyncio.Queue(maxsize=max(2_000, _OBSERVATORY_CAP.capacity))


def _put_nowait_if_space(
    queue: asyncio.Queue[dict[str, Any]],
    event: dict[str, Any],
) -> None:
    if queue.full():
        return
    try:
        queue.put_nowait(event)
    except asyncio.QueueFull:
        return


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
    "workflow.hitl.escalated",
    "workflow.policy.violation",
    "workflow.sla.breach_imminent",
    "durable.suspended",
    "durable.resumed",
    "durable.workflow.completed",
    "workflow.resolved",
    # The Org Building (IP1, TASK-002) widens the relay so the zoom-3
    # backbone can react to entity-graph activity, ambient-agent decisions,
    # cadence ticks, sub-workflow spawns, governance write attempts, and
    # write enforcement outcomes without each surface needing its own SSE
    # route.
    "entity.upserted",
    "entity.linked",
    "decision.recorded",
    "ambient.decided",
    "cadence.tick",
    "workflow.sub_spawned",
    "entity.write.failed",
    "entity.write.killed",
    "governance.find_entities",
    "governance.find_entities.denied",
    # Org Ops v2 — persona-thinking telemetry so the live activity stream
    # / conversations channel / river gate-pulse can show personas at work
    # rather than instant flips.
    "persona.thinking",
    "persona.decided",
    # Tool-call traces — agents like rag-classifier call tools like
    # policy_search; we want every step visible in the operator view.
    "tool.invoked",
    "tool.completed",
    "fleet.tick",
    "kpi.published",
    "entity.read",
    "workflow.failed",
    # Dream-pass lifecycle — the constellation pulses the relevant
    # persona / function planet during a pass and adds a lesson
    # satellite when one completes.
    "dream.pass.started",
    "dream.pass.finished",
    "dream.proposal.generated",
    "dream.lesson.promoted",
    "dream.lesson.rejected",
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
    # Dream-pass events carry their domain in payload['domain']; surface
    # it at the top level so the front-end constellation can route the
    # pulse / satellite update without parsing the payload separately.
    payload = data.get("payload") or {}
    if isinstance(payload, dict):
        if not domain and payload.get("domain"):
            domain = payload.get("domain")
        if event.type.startswith("dream."):
            data.setdefault("dream_input_count", payload.get("input_count"))
            data.setdefault("dream_output_count", payload.get("output_count"))
            data.setdefault("dream_trigger", payload.get("trigger"))

    return {
        "type": event.type,
        "skill": skill,
        "tool": tool,
        "domain": domain,
        "workflow_id": workflow_id,
        "workflow_type": workflow_type,
        "executor_type": data.get("executor_type"),
        "stage": data.get("stage"),
        # HITL / suspended events carry the persona that was asked plus a
        # short reason slug ("awaiting_finance_signoff" etc). Forwarded so
        # the Constellation can render a satellite next to awaiting motes.
        "persona": data.get("persona"),
        "reason": data.get("reason"),
        # Org Building entity / function-plane fields. Only set on the
        # entity.* / decision.* / ambient.* / cadence.* / sub_spawned
        # event types — the org-building animation overlay uses these
        # to address the firing window / floor / vault. Other event
        # types leave them None and the frontend ignores them.
        "entity_id": data.get("entity_id"),
        "entity_kind": data.get("entity_kind") or data.get("kind"),
        "function": data.get("function"),
        "agent_name": data.get("agent_name") or data.get("ambient_agent"),
        "cadence": data.get("cadence") or data.get("cadence_name"),
        "decision_id": data.get("decision_id"),
        "parent_workflow_id": data.get("parent_workflow_id")
            or data.get("parent_id"),
        "child_workflow_id": data.get("child_workflow_id")
            or data.get("child_id"),
        # Org Ops v2 — verdict + phase + reason fields so the live stream /
        # conversations / river can render persona decisions in plain English
        # ("ap_clerk approved API-0023 — within policy"). All optional;
        # present on persona.thinking / persona.decided / decision.recorded
        # / workflow.hitl.* events.
        "verdict": data.get("verdict"),
        "phase_name": data.get("phase"),
        "decision_reason": data.get("reason") or data.get("decision_reason"),
        # Dream-pass payload fields — only set on dream.* events.
        "dream_input_count": data.get("dream_input_count"),
        "dream_output_count": data.get("dream_output_count"),
        "dream_trigger": data.get("dream_trigger"),
        "ts": data.get("ts") or time.time(),
    }


@router.get("/api/blueprint/stream")
async def blueprint_stream(request: Request) -> EventSourceResponse:
    """Per-connection event stream.

    Each browser connection runs its own replay loop so a fresh page load
    starts at the beginning of a workflow rather than landing in the
    middle of one. Two parallel sources are merged:

      1. Per-connection replay of recorded templates (the bulk of what
         the page sees). Picked fresh on connect.
      2. Live FleetEvents from the in-process bus (used when there's a
         real backend driving workflows in dev). Always streamed too so
         the page reflects activity if the operator triggers something.

    No global trickle. _stream_loop is gone.
    """
    queue = _make_event_queue()
    loop = asyncio.get_running_loop()

    def _push_bus_event(event: FleetEvent) -> None:
        normalised = _normalise_event(event)
        if normalised is None:
            return
        if not _OBSERVATORY_CAP.allow():
            return
        try:
            loop.call_soon_threadsafe(
                _put_nowait_if_space,
                queue,
                normalised,
            )
        except RuntimeError:
            pass

    unsubscribe = app_state.bus.on_any(_push_bus_event)

    # Per-connection replay task — owns its own in-flight queue, picks
    # fresh templates, paces itself, and pushes normalised events onto
    # the same queue. Cancelled on disconnect.
    async def _per_connection_replay() -> None:
        in_flight: list[dict[str, Any]] = []
        recorded_index = 0
        synthetic_index = 0
        try:
            while True:
                # Maintain exactly 1 workflow in flight so the visitor
                # nearly always catches the start of a workflow within a
                # few seconds of landing on the page.
                if not in_flight:
                    recorded = load_recorded_templates(app_state.runtime)
                    if recorded:
                        recorded = list(
                            {
                                template["workflow_type"]: template
                                for template in recorded
                            }.values()
                        )
                        template = recorded[recorded_index % len(recorded)]
                        recorded_index += 1
                        wf_type = template["workflow_type"]
                        prefix = _PREFIX_BY_TYPE.get(wf_type, "WF")
                        wid = f"{prefix}-{random.randint(1000, 9999)}"
                        events_with_deltas = [
                            {"event": dict(e, workflow_id=wid), "delta_ms": d}
                            for e, d in zip(template["events"], template["deltas_ms"])
                        ]
                        in_flight.append({
                            "events": events_with_deltas,
                            "wid": wid,
                            "source": template.get("source", "recorded"),
                        })
                    elif _STREAM_TEMPLATES:
                        template = _STREAM_TEMPLATES[
                            synthetic_index % len(_STREAM_TEMPLATES)
                        ]
                        synthetic_index += 1
                        wf_type = template[0].get("workflow_type", "hiring")
                        prefix = _PREFIX_BY_TYPE.get(wf_type, "WF")
                        wid = f"{prefix}-{random.randint(1000, 9999)}"
                        events_with_deltas = [
                            {"event": dict(e, workflow_id=wid), "delta_ms": 0}
                            for e in template
                        ]
                        in_flight.append({
                            "events": events_with_deltas,
                            "wid": wid,
                            "source": "synthetic",
                        })
                    else:
                        # Nothing to replay; idle.
                        await asyncio.sleep(2.0)
                        continue

                slot = in_flight[0]
                entry = slot["events"].pop(0)
                try:
                    fe = FleetEvent(**entry["event"])
                    normalised = _normalise_event(fe)
                    if normalised is not None:
                        try:
                            queue.put_nowait(normalised)
                        except asyncio.QueueFull:
                            pass
                except Exception:
                    pass
                if not slot["events"]:
                    in_flight.pop(0)

                delta = entry.get("delta_ms", 0)
                if delta >= 200:
                    pause = min(delta, 4000) / 1000.0
                else:
                    pause = random.uniform(0.9, 2.4)
                if os.getenv("ZAVA_BLUEPRINT_REPLAY_ONLY") == "1":
                    pause = min(pause, 0.2)
                await asyncio.sleep(pause)
        except asyncio.CancelledError:
            return

    replay_task = asyncio.create_task(_per_connection_replay())

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
            replay_task.cancel()

    return EventSourceResponse(_gen())


# --------------------------------------------------------------------------
# Dev-only event injector
#
# A tiny endpoint to fire scripted observatory events from curl when the
# Functions host isn't running. Used during dev to verify pulse animations
# and counters without booting the full demo stack. Safe to leave enabled —
# it only emits FleetEvents on the local in-process bus.
# --------------------------------------------------------------------------


_WF = "HIRE-DEMO-01"
_DEMO_SCRIPTS: dict[str, list[dict[str, Any]]] = {
    "hire-agui": [
        # ── workflow start ──────────────────────────────────────────
        {"type": "durable.workflow.started", "workflow_type": "hiring",
         "workflow_id": _WF},
        # ── screening stage ─────────────────────────────────────────
        {"type": "durable.step.started", "stage": "screening",
         "workflow_id": _WF},
        {"type": "durable.executor.invoked", "skill": "cv_screener",
         "workflow_id": _WF},
        {"type": "agent.completed", "skill": "cv_screener",
         "workflow_id": _WF,
         "output": "Candidate Ada Lovelace has 8 years distributed-systems "
                   "experience, strong Python (contributor to CPython), and "
                   "led a team of 12 at Babbage Corp. Screening score: 0.94. "
                   "Recommend proceeding to technical interview."},
        # tool call: policy search
        {"type": "durable.executor.invoked", "tool": "policy_search",
         "workflow_id": _WF,
         "args": {"query": "UK hiring compliance GDPR right-to-work"}},
        # entity upserted: candidate
        {"type": "entity.upserted", "workflow_id": _WF,
         "entity_id": "cand-42", "entity_kind": "person",
         "fields": {"name": "Ada Lovelace", "role": "Senior Engineer",
                    "screening_score": 0.94, "source": "referral"}},
        {"type": "durable.step.completed", "stage": "screening",
         "workflow_id": _WF},
        # ── interview stage ─────────────────────────────────────────
        {"type": "durable.step.started", "stage": "interview",
         "workflow_id": _WF},
        {"type": "durable.executor.invoked", "skill": "interview_scheduler",
         "workflow_id": _WF},
        {"type": "agent.completed", "skill": "interview_scheduler",
         "workflow_id": _WF,
         "output": "Scheduled technical panel for 2026-05-22 14:00 UTC. "
                   "Panel: Sarah Chen (Engineering Lead), James Wright "
                   "(Staff Engineer). Sent calendar invites to all parties."},
        # tool call: calendar lookup
        {"type": "durable.executor.invoked", "tool": "calendar_availability",
         "workflow_id": _WF,
         "args": {"participants": ["sarah.chen", "james.wright"],
                  "duration_mins": 60, "window_days": 5}},
        # HITL: awaiting interview decision
        {"type": "workflow.hitl.requested", "workflow_id": _WF,
         "persona": "hiring_manager",
         "reason": "awaiting_interview_decision"},
        # resume after human approval
        {"type": "durable.resumed", "workflow_id": _WF},
        {"type": "durable.step.completed", "stage": "interview",
         "workflow_id": _WF},
        # ── offer stage ─────────────────────────────────────────────
        {"type": "durable.step.started", "stage": "offer",
         "workflow_id": _WF},
        {"type": "durable.executor.invoked", "skill": "offer_personaliser",
         "workflow_id": _WF},
        {"type": "agent.completed", "skill": "offer_personaliser",
         "workflow_id": _WF,
         "output": "Generated offer letter for Ada Lovelace. Band L5 upper "
                   "quartile (£145k base + 15% bonus + equity). Personalised "
                   "with distributed-systems project highlights and flexible "
                   "working clause per UK policy."},
        # tool call: comp benchmark
        {"type": "durable.executor.invoked", "tool": "comp_benchmark",
         "workflow_id": _WF,
         "args": {"role": "Senior Engineer", "location": "London",
                  "band": "L5"}},
        # decision recorded
        {"type": "decision.recorded", "workflow_id": _WF,
         "decision_id": "dec-offer-42",
         "verdict": "approved",
         "reason": "Unanimous panel recommendation. Exceptional candidate."},
        # entity update: candidate status
        {"type": "entity.upserted", "workflow_id": _WF,
         "entity_id": "cand-42", "entity_kind": "person",
         "fields": {"name": "Ada Lovelace", "role": "Senior Engineer",
                    "status": "offer_sent", "offer_band": "L5",
                    "offer_base": 145000}},
        {"type": "durable.step.completed", "stage": "offer",
         "workflow_id": _WF},
        # ── workflow complete ───────────────────────────────────────
        {"type": "durable.workflow.completed", "workflow_id": _WF},
    ],
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
    # Travel pre-approval — first compose-domain generated journey.
    # Synthetic walk for the trickle. Real workflows fire end-to-end via
    # POST /api/simulator/travel (Functions host + persona responder); this
    # template is what plays when nobody's actively triggering a real run.
    # Same shape and event types as the hiring/expense templates above so
    # the page renders it identically.
    [
        {"type": "workflow.started", "workflow_type": "travel-preapproval"},
        {"type": "durable.step.started", "skill": "fleet-travel-preapproval-policy-fit-checker",
         "workflow_type": "travel-preapproval"},
        {"type": "durable.executor.invoked", "skill": "fleet-travel-preapproval-policy-fit-checker",
         "tool": "concur_travel_policy", "workflow_type": "travel-preapproval"},
        {"type": "durable.executor.invoked", "skill": "fleet-travel-preapproval-policy-fit-checker",
         "tool": "concur_travel_search", "workflow_type": "travel-preapproval"},
        {"type": "agent.completed", "skill": "fleet-travel-preapproval-policy-fit-checker",
         "workflow_type": "travel-preapproval"},
        {"type": "workflow.hitl.requested", "workflow_type": "travel-preapproval"},
        {"type": "durable.workflow.completed", "workflow_type": "travel-preapproval"},
    ],
]


_PREFIX_BY_TYPE = {
    "hiring": "HIRE",
    "expense-claim": "CLM",
    "onboarding": "ONB",
    "travel-preapproval": "TRVL",
}


# Module-level handle so the stream survives across requests.
_stream_task: asyncio.Task | None = None


async def _stream_loop() -> None:
    """Indefinite trickle: keep up to 3 workflows in flight, drip events
    from each so the page reads as continuous.

    Source preference (computed once on each top-up, so adding new
    recordings while the stream is running gets picked up on the next
    workflow that lands a slot):

      1. data/blueprint-recordings/*.jsonl   — real captured walks,
         replayed at original cadence.
      2. _STREAM_TEMPLATES                    — hand-coded fallback for
         when no recordings exist.
    """
    in_flight: list[dict[str, Any]] = []
    try:
        while True:
            # Top up to 3 in-flight workflows.
            while len(in_flight) < 3:
                recorded = load_recorded_templates(app_state.runtime)
                if recorded:
                    template = random.choice(recorded)
                    wf_type = template["workflow_type"]
                    prefix = _PREFIX_BY_TYPE.get(wf_type, "WF")
                    wid = f"{prefix}-{random.randint(1000, 9999)}"
                    # Replay with original deltas.
                    events_with_deltas = [
                        {"event": dict(e, workflow_id=wid), "delta_ms": d}
                        for e, d in zip(template["events"], template["deltas_ms"])
                    ]
                    in_flight.append({
                        "events": events_with_deltas,
                        "wid": wid,
                        "source": template.get("source", "recorded"),
                    })
                else:
                    template = random.choice(_STREAM_TEMPLATES)
                    wf_type = template[0].get("workflow_type", "hiring")
                    prefix = _PREFIX_BY_TYPE.get(wf_type, "WF")
                    wid = f"{prefix}-{random.randint(1000, 9999)}"
                    # Synthetic templates have no deltas; use 0 (the
                    # outer randomised sleep below paces them).
                    events_with_deltas = [
                        {"event": dict(e, workflow_id=wid), "delta_ms": 0}
                        for e in template
                    ]
                    in_flight.append({
                        "events": events_with_deltas,
                        "wid": wid,
                        "source": "synthetic",
                    })

            # Pick one of the in-flight workflows at random and pop its
            # next event. Emitting from a randomly selected workflow keeps
            # multiple workflows interleaved on the page.
            slot_idx = random.randrange(len(in_flight))
            slot = in_flight[slot_idx]
            entry = slot["events"].pop(0)
            try:
                app_state.bus.emit(FleetEvent(**entry["event"]))
            except Exception:
                pass
            if not slot["events"]:
                in_flight.pop(slot_idx)

            # Cadence policy:
            #   - Recorded entries replay at their original delta when
            #     it's between 200ms and 4000ms (clamps to keep the page
            #     readable; some real entries are bunched within ms of
            #     each other and would strobe).
            #   - Synthetic entries (delta_ms == 0) get the original
            #     randomised pacing so they still feel alive.
            delta = entry.get("delta_ms", 0)
            if delta >= 200:
                pause = min(delta, 4000) / 1000.0
            else:
                pause = random.uniform(0.9, 2.4)
            await asyncio.sleep(pause)
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


# --------------------------------------------------------------------------
# Recorder — capture real bus events to JSONL files for later replay.
#
# Workflow:
#   1. Start the FastAPI server with whatever real backend is firing
#      events (Functions host, mock MCPs, simulator).
#   2. POST /api/blueprint/_recorder/start
#   3. Run your real workflows.
#   4. POST /api/blueprint/_recorder/stop
#   5. JSONL files land under data/blueprint-recordings/. Inspect, curate
#      (delete short/bad runs), commit.
#   6. Restart the server. The next /_demo_stream/start will replay the
#      recordings instead of synthetic templates.
# --------------------------------------------------------------------------


@router.post("/api/blueprint/_recorder/start")
async def recorder_start() -> dict[str, Any]:
    """Subscribe to the bus and record observatory events. Idempotent."""
    return _recorder.start(app_state.bus)


@router.post("/api/blueprint/_recorder/stop")
async def recorder_stop() -> dict[str, Any]:
    """Stop recording. Flushes any in-flight workflows to disk."""
    return _recorder.stop()


@router.get("/api/blueprint/_recorder/status")
async def recorder_status() -> dict[str, Any]:
    """Return current recorder state: running flag, in-flight workflows."""
    return _recorder.status()
