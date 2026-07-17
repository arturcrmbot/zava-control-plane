from __future__ import annotations

import json
from typing import Any

from copilot.tools import ToolResult
from pydantic import BaseModel, Field


class EvidenceParams(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)
    actor_ids: list[str] = Field(default_factory=list)
    event_ids: list[str] = Field(default_factory=list)
    trace_id: str
    as_of_sim_time: float = Field(ge=0)


class ActionParams(EvidenceParams):
    action: str
    payload: dict[str, Any] = Field(default_factory=dict)
    allowed_actions: list[str] = Field(default_factory=list)


def simulator_result(
    data: dict[str, Any],
    *,
    actor_ids: list[str],
    event_ids: list[str],
    trace_id: str,
    as_of_sim_time: float,
) -> dict[str, Any]:
    return {
        "data": data,
        "source_mode": "simulated",
        "actor_ids": list(actor_ids),
        "event_ids": list(event_ids),
        "trace_id": trace_id,
        "as_of_sim_time": float(as_of_sim_time),
    }


def evidence_result(
    params: EvidenceParams,
    *,
    capability: str,
    operation: str,
) -> dict[str, Any]:
    return simulator_result(
        {
            "capability": capability,
            "operation": operation,
            **params.data,
        },
        actor_ids=params.actor_ids,
        event_ids=params.event_ids,
        trace_id=params.trace_id,
        as_of_sim_time=params.as_of_sim_time,
    )


def validate_action_result(
    params: ActionParams,
    *,
    capability: str,
) -> dict[str, Any]:
    allowed = not params.allowed_actions or params.action in params.allowed_actions
    return simulator_result(
        {
            "capability": capability,
            "action": params.action,
            "allowed": allowed,
            "reason": (
                "action is declared by the process case"
                if allowed
                else "action is outside the process case allow-list"
            ),
        },
        actor_ids=params.actor_ids,
        event_ids=params.event_ids,
        trace_id=params.trace_id,
        as_of_sim_time=params.as_of_sim_time,
    )


def prepare_action_result(
    observation: dict[str, Any],
    *,
    action: str,
    payload: dict[str, Any],
    actor_ids: list[str],
    event_ids: list[str],
    trace_id: str,
    as_of_sim_time: float,
) -> dict[str, Any]:
    allowed_actions = observation.get("allowed_actions") or []
    if allowed_actions and action not in allowed_actions:
        raise ValueError(f"action {action!r} is not allowed")
    return simulator_result(
        {
            "command_proposal": {
                "type": action,
                "payload": dict(payload),
            }
        },
        actor_ids=actor_ids,
        event_ids=event_ids,
        trace_id=trace_id,
        as_of_sim_time=as_of_sim_time,
    )


def prepared_result(params: ActionParams) -> dict[str, Any]:
    observation = {**params.data, "allowed_actions": params.allowed_actions}
    return prepare_action_result(
        observation,
        action=params.action,
        payload=params.payload,
        actor_ids=params.actor_ids,
        event_ids=params.event_ids,
        trace_id=params.trace_id,
        as_of_sim_time=params.as_of_sim_time,
    )


def tool_result(data: dict[str, Any]) -> ToolResult:
    return ToolResult(text_result_for_llm=json.dumps(data, sort_keys=True))
