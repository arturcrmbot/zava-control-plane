from __future__ import annotations

import json
from typing import Any

from copilot.tools import ToolResult
from pydantic import BaseModel, Field


class FashionEvidenceParams(BaseModel):
    evidence: dict[str, Any] = Field(default_factory=dict)
    actor_ids: list[str] = Field(default_factory=list)
    event_ids: list[str] = Field(default_factory=list)
    trace_id: str
    as_of_sim_time: float = Field(ge=0)


class FashionCommandParams(FashionEvidenceParams):
    workflow_id: str
    command_id: str
    command_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    allowed_commands: list[str] = Field(default_factory=list)


def evidence_result(
    params: FashionEvidenceParams,
    *,
    operation: str,
) -> ToolResult:
    result = {
        "data": {"operation": operation, **params.evidence},
        "source_mode": "simulated",
        "actor_ids": params.actor_ids,
        "event_ids": params.event_ids,
        "trace_id": params.trace_id,
        "as_of_sim_time": params.as_of_sim_time,
    }
    return ToolResult(text_result_for_llm=json.dumps(result, sort_keys=True))


def command_result(params: FashionCommandParams) -> ToolResult:
    if not params.allowed_commands:
        raise ValueError("an explicit allow-list is required")
    if params.command_type not in params.allowed_commands:
        raise ValueError(
            f"command {params.command_type!r} is outside the allow-list"
        )
    result = {
        "command": {
            "command_id": params.command_id,
            "trace_id": params.trace_id,
            "issued_by": "fashion",
            "type": params.command_type,
            "payload": {
                **params.payload,
                "workflow_id": params.workflow_id,
                "evidence_event_ids": params.event_ids,
            },
        },
        "source_mode": "simulated",
    }
    return ToolResult(text_result_for_llm=json.dumps(result, sort_keys=True))
