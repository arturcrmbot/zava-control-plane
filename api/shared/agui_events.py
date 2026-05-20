"""Typed AG-UI event shapes we emit on /api/workflows/{run_id}/agui.

Reference: https://docs.ag-ui.com/concepts/events. We implement a subset
(13 of ~16 event types). Field names follow AG-UI's camelCase wire
format on serialisation; Python attributes stay snake_case.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Union


@dataclass
class RunStarted:
    run_id: str
    thread_id: str


@dataclass
class RunFinished:
    run_id: str
    thread_id: str


@dataclass
class RunError:
    message: str
    code: str | None = None


@dataclass
class RunInterrupted:
    reason: str
    persona: str | None = None


@dataclass
class StepStarted:
    step_name: str


@dataclass
class StepFinished:
    step_name: str


@dataclass
class TextMessageStart:
    message_id: str
    role: str = "assistant"


@dataclass
class TextMessageContent:
    message_id: str
    delta: str


@dataclass
class TextMessageEnd:
    message_id: str


@dataclass
class ToolCallStart:
    tool_call_id: str
    tool_call_name: str
    parent_message_id: str | None = None


@dataclass
class ToolCallArgs:
    tool_call_id: str
    delta: str  # JSON-string chunk per AG-UI spec


@dataclass
class ToolCallEnd:
    tool_call_id: str


@dataclass
class StateDelta:
    # RFC 6902 JSON Patch
    delta: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CustomEvent:
    name: str
    value: Any


AGUIEvent = Union[
    RunStarted, RunFinished, RunError, RunInterrupted,
    StepStarted, StepFinished,
    TextMessageStart, TextMessageContent, TextMessageEnd,
    ToolCallStart, ToolCallArgs, ToolCallEnd,
    StateDelta, CustomEvent,
]


_TYPE_MAP: dict[type, str] = {
    RunStarted: "RUN_STARTED",
    RunFinished: "RUN_FINISHED",
    RunError: "RUN_ERROR",
    RunInterrupted: "RUN_INTERRUPTED",
    StepStarted: "STEP_STARTED",
    StepFinished: "STEP_FINISHED",
    TextMessageStart: "TEXT_MESSAGE_START",
    TextMessageContent: "TEXT_MESSAGE_CONTENT",
    TextMessageEnd: "TEXT_MESSAGE_END",
    ToolCallStart: "TOOL_CALL_START",
    ToolCallArgs: "TOOL_CALL_ARGS",
    ToolCallEnd: "TOOL_CALL_END",
    StateDelta: "STATE_DELTA",
    CustomEvent: "CUSTOM",
}


_FIELD_RENAMES = {
    "run_id": "runId",
    "thread_id": "threadId",
    "step_name": "stepName",
    "message_id": "messageId",
    "tool_call_id": "toolCallId",
    "tool_call_name": "toolCallName",
    "parent_message_id": "parentMessageId",
}


def to_sse_dict(event: AGUIEvent) -> dict[str, Any]:
    raw = asdict(event)
    out: dict[str, Any] = {"type": _TYPE_MAP[type(event)]}
    for k, v in raw.items():
        if v is None:
            continue
        out[_FIELD_RENAMES.get(k, k)] = v
    return out
