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
        self._run_started = False
        self._run_terminal = False

    def open_message_id(self, skill: str) -> str | None:
        return self._open_messages.get(self._agent_key(skill))

    @staticmethod
    def _agent_key(value: Any) -> str:
        return str(value).strip().lower().replace("_", "-")

    @staticmethod
    def _tool_call_id(value: dict[str, Any]) -> str | None:
        for field in ("tool_call_id", "toolCallId"):
            call_id = value.get(field)
            if call_id is not None:
                return str(call_id)
        return None

    def _pop_open_message(self, skill: str) -> str | None:
        mid = self._open_messages.pop(skill, None)
        if mid is not None:
            return mid
        aliases = [
            key
            for key in self._open_messages
            if key in skill or skill in key
        ]
        if len(aliases) == 1:
            return self._open_messages.pop(aliases[0])
        if len(self._open_messages) == 1:
            return self._open_messages.pop(next(iter(self._open_messages)))
        return None

    def _close_open_messages(self) -> list[AGUIEvent]:
        message_ids = list(dict.fromkeys(self._open_messages.values()))
        self._open_messages.clear()
        return [TextMessageEnd(message_id=mid) for mid in message_ids]

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
        if self._run_started or self._run_terminal:
            return []
        self._run_started = True
        return [RunStarted(run_id=self.run_id, thread_id=self.run_id)]

    def _on_workflow_completed(self, d: dict[str, Any]) -> list[AGUIEvent]:
        if self._run_terminal:
            return []
        if d.get("resolution") == "rejected":
            self._run_terminal = True
            return [
                *self._close_open_messages(),
                RunError(message=str(d.get("reason") or "workflow rejected")),
            ]
        self._run_terminal = True
        return [
            *self._close_open_messages(),
            RunFinished(run_id=self.run_id, thread_id=self.run_id),
        ]

    def _on_workflow_failed(self, d: dict[str, Any]) -> list[AGUIEvent]:
        if self._run_terminal:
            return []
        self._run_terminal = True
        return [
            *self._close_open_messages(),
            RunError(message=str(d.get("reason") or "unknown")),
        ]

    def _on_workflow_exception(self, d: dict[str, Any]) -> list[AGUIEvent]:
        value = {
            key: d[key]
            for key in ("category", "severity", "reason")
            if d.get(key) is not None
        }
        return [CustomEvent(name="workflow.exception.detected", value=value)]

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
        tool = d.get("tool")
        if tool:
            return self._on_tool_invoked(d)
        skill = d.get("skill")
        if skill:
            if d.get("stage") == "error":
                mid = self._pop_open_message(self._agent_key(skill))
                return [TextMessageEnd(message_id=mid)] if mid else []
            if d.get("stage") == "complete":
                return []
            key = self._agent_key(skill)
            mid = self._open_messages.get(key) or f"msg-{uuid.uuid4().hex[:8]}"
            self._open_messages[key] = mid
            return [TextMessageStart(message_id=mid, role="assistant")]
        return []

    def _on_agent_completed(self, d: dict[str, Any]) -> list[AGUIEvent]:
        skill = self._agent_key(
            d.get("agent_label")
            or d.get("skill")
            or d.get("agent")
            or "agent"
        )
        mid = self._pop_open_message(skill)
        started = mid is None
        if mid is None:
            mid = str(
                d.get("message_id")
                or d.get("response_id")
                or d.get("agent_run_id")
                or f"msg-{uuid.uuid4().hex[:8]}"
            )
        out: list[AGUIEvent] = (
            [TextMessageStart(message_id=mid, role="assistant")]
            if started
            else []
        )
        text = d.get("response_text")
        if text is None:
            text = d.get("output")
        if text is not None:
            out.append(TextMessageContent(message_id=mid, delta=str(text)))
        out.append(TextMessageEnd(message_id=mid))
        return out

    def _on_tool_invoked(self, d: dict[str, Any]) -> list[AGUIEvent]:
        tool = str(d.get("tool") or "tool")
        call_id = self._tool_call_id(d)
        key = str(call_id or tool)
        stage = d.get("stage")
        if stage in {"complete", "error"}:
            tcid = self._open_tools.pop(key, None)
            if tcid is None and call_id is not None:
                tcid = str(call_id)
            return [ToolCallEnd(tool_call_id=tcid)] if tcid else []

        tcid = self._open_tools.get(key) or str(call_id or f"tc-{uuid.uuid4().hex[:8]}")
        self._open_tools[key] = tcid
        out: list[AGUIEvent] = [
            ToolCallStart(tool_call_id=tcid, tool_call_name=tool),
        ]
        args = d.get("args")
        if args is not None:
            delta = args if isinstance(args, str) else json.dumps(args)
            out.append(ToolCallArgs(tool_call_id=tcid,
                                    delta=delta))
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
    "workflow.rejected":           SubstrateToAGUI._on_workflow_failed,
    "workflow.exception.detected": SubstrateToAGUI._on_workflow_exception,
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
