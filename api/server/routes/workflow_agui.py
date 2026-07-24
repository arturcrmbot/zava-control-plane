"""AG-UI compatible per-workflow SSE drill-in.

Replays historical events from orchestration_history on connect, then
streams live events from the EventBus.
"""
from __future__ import annotations

import asyncio
import json
from collections import Counter
from typing import Any

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from api.server.services.substrate_to_agui import SubstrateToAGUI
from api.server.state import app_state
from api.shared.agui_events import to_sse_dict
from api.shared.events import FleetEvent

router = APIRouter()

# Maps orchestration_history `kind` to the FleetEvent type(s) to emit.
# Each entry is (fleet_event_type, payload_extractor).
_KIND_FLEET_MAP: dict[str, list[tuple[str, Any]]] = {}


def _event_overlap_key(event: FleetEvent) -> tuple[str, ...]:
    data = event.model_dump(mode="json", exclude_none=True)
    event_type = str(data.pop("type", event.type))
    workflow_id = str(data.pop("workflow_id", "") or "")
    data.pop("ts", None)
    stage = str(data.get("stage") or "")
    for identifier_kind, fields in (
        ("event", ("event_id", "eventId")),
        ("tool-call", ("tool_call_id", "toolCallId", "call_id", "callId")),
        ("agent-run", ("agent_run_id", "agentRunId")),
        ("invocation", ("invocation_id", "invocationId")),
        ("message", ("message_id", "messageId")),
        ("response", ("response_id", "responseId")),
        ("decision", ("decision_id", "decisionId")),
    ):
        identifier = next(
            (data[field] for field in fields if data.get(field) is not None),
            None,
        )
        if identifier is not None:
            identifier = json.dumps(
                identifier,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
            return event_type, workflow_id, identifier_kind, identifier, stage

    if event_type == "agent.completed":
        fingerprint_data: dict[str, Any] = {
            "agent": _agent_identity(data),
            "phase": _phase_identity(data),
            "outputs": sorted(_output_fingerprints(data)),
        }
    else:
        overlap_fields = {
            "durable.workflow.started": (),
            "durable.workflow.completed": (),
            "workflow.failed": ("reason",),
            "workflow.rejected": ("reason",),
            "durable.step.started": ("phase", "step"),
            "durable.step.completed": ("phase", "step"),
            "durable.executor.invoked": (
                "name",
                "executor_type",
                "stage",
                "skill",
                "tool",
            ),
            "durable.validator.blocked": ("name", "reason"),
            "workflow.exception.detected": (
                "category",
                "severity",
                "reason",
            ),
            "workflow.hitl.requested": ("reason", "persona", "phase"),
            "durable.resumed": ("phase",),
        }
        fields = overlap_fields.get(event_type)
        fingerprint_data = (
            {field: data.get(field) for field in fields}
            if fields is not None
            else data
        )
    fingerprint = json.dumps(
        fingerprint_data,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return event_type, workflow_id, fingerprint


def _agent_identity(payload: dict[str, Any]) -> str | None:
    value = payload.get("agent_label") or payload.get("skill") or payload.get("agent")
    if value is None:
        return None
    identity = str(value).strip().lower().replace("_", "-")
    return identity or None


def _invocation_ids(payload: dict[str, Any]) -> set[str]:
    return {
        str(payload[field])
        for field in (
            "invocation_id",
            "invocationId",
            "agent_run_id",
            "agentRunId",
        )
        if payload.get(field) is not None
    }


def _tool_call_id(payload: dict[str, Any]) -> str | None:
    for field in ("tool_call_id", "toolCallId"):
        value = payload.get(field)
        if value is not None:
            return str(value)
    return None


def _phase_identity(payload: dict[str, Any]) -> str | None:
    value = (
        payload.get("phase")
        or payload.get("stage_label")
        or payload.get("stageLabel")
        or payload.get("step")
    )
    if value is None:
        return None
    phase = str(value).strip().lower().replace("_", "-")
    return phase or None


def _output_fingerprints(payload: dict[str, Any]) -> set[str]:
    fingerprints: set[str] = set()
    for field in ("output", "extracted_json", "extractedJson", "response_text", "responseText"):
        value = payload.get(field)
        if value is None:
            continue
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                value = value.strip()
        fingerprints.add(json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ))
    return fingerprints


def _matched_legacy_agent_output_indices(
    history: list[dict[str, Any]],
) -> set[int]:
    legacy_indices = [
        index
        for index, entry in enumerate(history)
        if entry.get("kind") == "agent_output"
    ]
    canonical_indices = [
        index
        for index, entry in enumerate(history)
        if entry.get("kind") == "agent.completed"
    ]
    matched: set[int] = set()
    matched_canonical: set[int] = set()

    def unique_nearest(
        candidates: list[int],
        canonical_index: int,
    ) -> int | None:
        if not candidates:
            return None
        nearest_distance = min(
            abs(index - canonical_index) for index in candidates
        )
        nearest = [
            index
            for index in candidates
            if abs(index - canonical_index) == nearest_distance
        ]
        return nearest[0] if len(nearest) == 1 else None

    for canonical_index in canonical_indices:
        entry = history[canonical_index]
        canonical = entry.get("payload") or {}
        canonical_ids = _invocation_ids(canonical)
        stable_match = unique_nearest([
            legacy_index
            for legacy_index in legacy_indices
            if legacy_index not in matched
            if canonical_ids
            and canonical_ids & _invocation_ids(
                history[legacy_index].get("payload") or {}
            )
        ], canonical_index)
        if stable_match is not None:
            matched.add(stable_match)
            matched_canonical.add(canonical_index)

    for canonical_index in canonical_indices:
        if canonical_index in matched_canonical:
            continue
        canonical = history[canonical_index].get("payload") or {}
        canonical_agent = _agent_identity(canonical)
        if canonical_agent is None:
            continue
        canonical_phase = _phase_identity(canonical)
        canonical_outputs = _output_fingerprints(canonical)
        if not canonical_outputs:
            continue
        fallback_matches: list[int] = []
        for legacy_index in legacy_indices:
            if legacy_index in matched:
                continue
            legacy = history[legacy_index].get("payload") or {}
            if _invocation_ids(legacy):
                continue
            if _agent_identity(legacy) != canonical_agent:
                continue
            legacy_phase = _phase_identity(legacy)
            if (
                canonical_phase is not None
                and legacy_phase is not None
                and canonical_phase != legacy_phase
            ):
                continue
            if canonical_outputs & _output_fingerprints(legacy):
                fallback_matches.append(legacy_index)

        fallback_match = unique_nearest(fallback_matches, canonical_index)
        if fallback_match is not None:
            matched.add(fallback_match)

    return matched


def _history_to_fleet_events(
    run_id: str,
    entry: dict[str, Any],
    *,
    suppress_legacy_agent_output: bool = False,
) -> list[FleetEvent]:
    """Convert one orchestration_history entry to FleetEvent(s)."""
    kind = entry.get("kind", "")
    payload = entry.get("payload") or {}
    ts = entry.get("at", 0.0)
    events: list[FleetEvent] = []

    if kind == "workflow.started":
        events.append(FleetEvent(
            type="durable.workflow.started", ts=ts, workflow_id=run_id,
            workflow_type=payload.get("workflow_type")))

    elif kind == "step.started":
        step = payload.get("step")
        if step:
            events.append(FleetEvent(
                type="durable.step.started", ts=ts, workflow_id=run_id,
                phase=step, step=step))

    elif kind == "step.completed":
        step = payload.get("step")
        if step:
            events.append(FleetEvent(
                type="durable.step.completed", ts=ts, workflow_id=run_id,
                phase=step, step=step))

    elif kind == "executor.invoked":
        name = str(payload.get("name", "?"))
        etype = str(payload.get("type", "?"))
        attrs = payload.get("attributes") or {}
        skill_label = None
        if etype == "agent":
            skill_label = name[len("agent_"):] if name.startswith("agent_") else name
        elif etype == "validator":
            skill_label = name
        invocation_fields = (
            {"invocation_id": payload["invocation_id"]}
            if payload.get("invocation_id") is not None
            else {}
        )
        events.append(FleetEvent(
            type="durable.executor.invoked", ts=ts, workflow_id=run_id,
            name=name, executor_type=etype,
            stage=payload.get("stage"),
            skill=attrs.get("skill") or attrs.get("skill_label") or skill_label,
            tool=attrs.get("tool"),
            **invocation_fields))

    elif kind == "tool.invoked":
        p = payload
        correlation_fields = {
            field: p[field]
            for field in ("agent_run_id", "invocation_id")
            if p.get(field) is not None
        }
        events.append(FleetEvent(
            type="durable.executor.invoked", ts=ts, workflow_id=run_id,
            name=f"tool:{p.get('tool', '?')}",
            executor_type="tool",
            stage=p.get("stage"),
            skill=p.get("skill"),
            tool=p.get("tool"),
            tool_call_id=_tool_call_id(p),
            args=p.get("args"),
            result=p.get("result"),
            success=p.get("success"),
            duration_ms=p.get("duration_ms", 0),
            **correlation_fields))

    elif kind == "agent_output":
        agent = str(payload.get("agent") or "")
        output = payload.get("output")
        if agent and not suppress_legacy_agent_output:
            emit_payload: dict[str, Any] = {"skill": agent}
            if output is not None:
                out_str = (json.dumps(output) if isinstance(output, dict)
                           else str(output))
                emit_payload["output"] = out_str
            for field in ("invocation_id", "agent_run_id", "phase"):
                if payload.get(field) is not None:
                    emit_payload[field] = payload[field]
            events.append(FleetEvent(
                type="agent.completed", ts=ts, workflow_id=run_id,
                **emit_payload))

    elif kind == "agent.completed":
        event_payload = {
            key: value
            for key, value in payload.items()
            if key not in {"type", "ts", "workflow_id"}
        }
        if entry.get("instance_id") is not None:
            event_payload.setdefault("instance_id", entry["instance_id"])
        events.append(FleetEvent(
            type="agent.completed",
            ts=ts,
            workflow_id=run_id,
            **event_payload,
        ))

    elif kind == "validator.blocked":
        reason = payload.get("reason", "validation failed")
        events.append(FleetEvent(
            type="workflow.exception.detected",
            ts=ts,
            workflow_id=run_id,
            category="validator-blocked",
            severity="high",
            reason=reason,
        ))
        events.append(FleetEvent(
            type="durable.validator.blocked", ts=ts, workflow_id=run_id,
            name=payload.get("name", "unknown"),
            reason=reason))

    elif kind == "workflow.exception.detected":
        events.append(FleetEvent(
            type="workflow.exception.detected",
            ts=ts,
            workflow_id=run_id,
            category=payload.get("category"),
            severity=payload.get("severity"),
            reason=payload.get("reason"),
        ))

    elif kind == "suspended":
        reason = payload.get("reason", "approval")
        events.append(FleetEvent(
            type="workflow.hitl.requested", ts=ts, workflow_id=run_id,
            reason=reason, persona=payload.get("persona")))

    elif kind == "resumed":
        events.append(FleetEvent(
            type="durable.resumed", ts=ts, workflow_id=run_id,
            phase=payload.get("phase")))

    elif kind == "workflow.completed":
        events.append(FleetEvent(
            type="durable.workflow.completed", ts=ts, workflow_id=run_id,
            status="completed"))

    elif kind == "workflow.resolved":
        events.append(FleetEvent(
            type="workflow.resolved", ts=ts, workflow_id=run_id,
            resolution=payload.get("resolution"),
            reason=payload.get("reason")))

    elif kind == "workflow.failed":
        events.append(FleetEvent(
            type="workflow.failed", ts=ts, workflow_id=run_id,
            reason=payload.get("reason", "workflow failed")))

    elif kind == "workflow.rejected":
        events.append(FleetEvent(
            type="workflow.rejected", ts=ts, workflow_id=run_id,
            reason=payload.get("reason", "operator rejected")))

    return events


@router.get("/api/workflows/{run_id}/agui")
async def workflow_agui_stream(run_id: str,
                               request: Request) -> EventSourceResponse:
    queue: asyncio.Queue[tuple[bool, FleetEvent]] = asyncio.Queue(maxsize=400)
    loop = asyncio.get_running_loop()
    translator = SubstrateToAGUI(run_id=run_id)
    snapshot_pending = True
    closed = False

    def _enqueue(before_snapshot: bool, event: FleetEvent) -> None:
        if closed:
            return
        try:
            queue.put_nowait((before_snapshot, event))
        except asyncio.QueueFull:
            pass

    def _push(event: FleetEvent) -> None:
        if event.workflow_id != run_id:
            return
        try:
            loop.call_soon_threadsafe(_enqueue, snapshot_pending, event)
        except RuntimeError:
            pass

    async def _gen():
        nonlocal closed, snapshot_pending
        unsubscribe = None
        try:
            # Subscribe before taking the history snapshot. Live events that
            # arrive while history is copied and translated remain queued.
            unsubscribe = app_state.bus.on_any(_push)
            history = list(app_state.orchestration_history.get(run_id, []))
            snapshot_pending = False
            suppressed_legacy_outputs = _matched_legacy_agent_output_indices(history)
            historical_events: list[FleetEvent] = []
            for index, entry in enumerate(history):
                historical_events.extend(_history_to_fleet_events(
                    run_id,
                    entry,
                    suppress_legacy_agent_output=(
                        index in suppressed_legacy_outputs
                    ),
                ))
            overlap_counts = Counter(
                _event_overlap_key(event) for event in historical_events
            )
            for fleet_event in historical_events:
                for agui_event in translator.translate(fleet_event):
                    yield {"data": json.dumps(to_sse_dict(agui_event))}
            while True:
                if await request.is_disconnected():
                    break
                try:
                    before_snapshot, fleet_event = await asyncio.wait_for(
                        queue.get(),
                        timeout=15.0,
                    )
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": ""}
                    continue
                if before_snapshot:
                    overlap_key = _event_overlap_key(fleet_event)
                    if overlap_counts[overlap_key]:
                        overlap_counts[overlap_key] -= 1
                        if overlap_counts[overlap_key] == 0:
                            del overlap_counts[overlap_key]
                        continue
                for agui_event in translator.translate(fleet_event):
                    yield {"data": json.dumps(to_sse_dict(agui_event))}
        finally:
            closed = True
            snapshot_pending = False
            if unsubscribe is not None:
                unsubscribe()

    return EventSourceResponse(_gen())
