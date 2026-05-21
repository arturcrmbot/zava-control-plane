"""Translate substrate ``FleetEvent`` instances into AG-UI events.

The translator is stateful per workflow run — it tracks open
``TEXT_MESSAGE_*`` and ``TOOL_CALL_*`` lifecycles keyed by skill / tool
name so that streaming chunks reference the right id. Events whose
``workflow_id`` does not match the configured ``run_id`` are dropped.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from api.shared.agui_events import (
    AGUIEvent,
    CustomEvent,
    RunError,
    RunFinished,
    RunInterrupted,
    RunStarted,
    StateDelta,
    StepFinished,
    StepStarted,
    TextMessageContent,
    TextMessageEnd,
    TextMessageStart,
    ToolCallArgs,
    ToolCallEnd,
    ToolCallStart,
)
from api.shared.events import FleetEvent


class SubstrateToAGUI:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self._open_messages: dict[str, str] = {}
        self._open_tools: dict[str, str] = {}

    def open_message_id(self, skill: str) -> str | None:
        return self._open_messages.get(skill)

    def translate(self, event: FleetEvent) -> list[AGUIEvent]:
        data = event.model_dump()
        # Per-workflow AG-UI streams must be strictly scoped to their
        # run_id. Previously this allowed `workflow_id is None` through,
        # which let substrate-wide entity.upserted events (and any other
        # un-scoped FleetEvent) leak into every per-workflow stream —
        # producing "Live reasoning" panels that showed messages from
        # other in-flight workflows and a STATE blob containing the
        # entire substrate's Workflow registry.
        if data.get("workflow_id") != self.run_id:
            return []
        handler = _HANDLERS.get(event.type)
        if handler is None:
            return []
        return handler(self, data)

    # -- handlers ----------------------------------------------------------

    def _on_workflow_started(self, d: dict[str, Any]) -> list[AGUIEvent]:
        return [RunStarted(run_id=self.run_id, thread_id=self.run_id)]

    def _on_workflow_completed(self, d: dict[str, Any]) -> list[AGUIEvent]:
        return [RunFinished(run_id=self.run_id, thread_id=self.run_id)]

    def _on_workflow_failed(self, d: dict[str, Any]) -> list[AGUIEvent]:
        return [RunError(message=str(d.get("reason") or "unknown"))]

    def _on_step_started(self, d: dict[str, Any]) -> list[AGUIEvent]:
        name = str(d.get("stage") or d.get("phase") or "step")
        return [StepStarted(step_name=name)]

    def _on_step_completed(self, d: dict[str, Any]) -> list[AGUIEvent]:
        name = str(d.get("stage") or d.get("phase") or "step")
        return [StepFinished(step_name=name)]

    def _on_executor_invoked(self, d: dict[str, Any]) -> list[AGUIEvent]:
        # Agent invocations carry a `skill` field. Tool invocations carry
        # a `tool` field. Neither carries `executor_type="agent"` in the
        # live substrate inventory.
        skill = d.get("skill")
        if skill:
            mid = self._open_messages.get(str(skill)) or f"msg-{uuid.uuid4().hex[:8]}"
            self._open_messages[str(skill)] = mid
            return [TextMessageStart(message_id=mid, role="assistant")]
        tool = d.get("tool")
        if tool:
            return self._on_tool_invoked(d)
        return []

    def _on_agent_completed(self, d: dict[str, Any]) -> list[AGUIEvent]:
        skill = str(d.get("skill") or d.get("agent") or "agent")
        mid = self._open_messages.pop(skill, None)
        if mid is None:
            return []
        out: list[AGUIEvent] = []
        text = d.get("output")
        if text is not None:
            out.append(TextMessageContent(message_id=mid, delta=str(text)))
        out.append(TextMessageEnd(message_id=mid))
        return out

    def _on_tool_invoked(self, d: dict[str, Any]) -> list[AGUIEvent]:
        tool = str(d.get("tool") or "tool")
        tcid = self._open_tools.get(tool) or f"tc-{uuid.uuid4().hex[:8]}"
        self._open_tools[tool] = tcid
        out: list[AGUIEvent] = [
            ToolCallStart(tool_call_id=tcid, tool_call_name=tool),
        ]
        args = d.get("args")
        if args is not None:
            out.append(ToolCallArgs(tool_call_id=tcid,
                                    delta=json.dumps(args)))
        return out

    def _on_validator_blocked(self, d: dict[str, Any]) -> list[AGUIEvent]:
        return [CustomEvent(name="validator.blocked",
                            value={"reason": d.get("reason")})]

    def _on_hitl_requested(self, d: dict[str, Any]) -> list[AGUIEvent]:
        return [RunInterrupted(
            reason=str(d.get("reason") or "awaiting_human"),
            persona=d.get("persona"),
        )]

    def _on_hitl_resumed(self, d: dict[str, Any]) -> list[AGUIEvent]:
        return [CustomEvent(name="hitl.resumed", value={})]

    def _on_entity_upserted(self, d: dict[str, Any]) -> list[AGUIEvent]:
        kind = d.get("entity_kind") or "unknown"
        eid = d.get("entity_id")
        if not eid:
            return []
        path = f"/entities/{kind}/{eid}"
        value = d.get("fields") or {k: v for k, v in d.items()
                                     if k not in {"type", "ts", "workflow_id",
                                                  "entity_id", "entity_kind"}}
        return [StateDelta(delta=[{"op": "add", "path": path, "value": value}])]

    def _on_decision_recorded(self, d: dict[str, Any]) -> list[AGUIEvent]:
        did = d.get("decision_id")
        if not did:
            return []
        return [StateDelta(delta=[{"op": "add",
                                   "path": f"/decisions/{did}",
                                   "value": {"verdict": d.get("verdict"),
                                             "reason": d.get("reason")}}])]


_HANDLERS = {
    "durable.workflow.started":    SubstrateToAGUI._on_workflow_started,
    "workflow.started":            SubstrateToAGUI._on_workflow_started,
    "durable.workflow.completed":  SubstrateToAGUI._on_workflow_completed,
    "workflow.resolved":           SubstrateToAGUI._on_workflow_completed,
    "workflow.failed":             SubstrateToAGUI._on_workflow_failed,
    "workflow.exception.detected": SubstrateToAGUI._on_workflow_failed,
    "durable.step.started":        SubstrateToAGUI._on_step_started,
    "durable.step.completed":      SubstrateToAGUI._on_step_completed,
    "durable.executor.invoked":    SubstrateToAGUI._on_executor_invoked,
    "agent.completed":             SubstrateToAGUI._on_agent_completed,
    "durable.validator.blocked":   SubstrateToAGUI._on_validator_blocked,
    "workflow.hitl.requested":     SubstrateToAGUI._on_hitl_requested,
    "workflow.hitl.escalated":     SubstrateToAGUI._on_hitl_requested,
    "durable.resumed":             SubstrateToAGUI._on_hitl_resumed,
    "entity.upserted":             SubstrateToAGUI._on_entity_upserted,
    "decision.recorded":           SubstrateToAGUI._on_decision_recorded,
}
