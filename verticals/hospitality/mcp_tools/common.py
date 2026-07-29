"""Shared evidence model for every Hospitality MCP read tool.

Tools are read-only: they echo back the versioned evidence supplied by the
caller, tagged with the operation and an explicit ``source_mode``. They never
mutate world state and never invent actor, event or trace identity.
"""
from __future__ import annotations

import json
from typing import Any

from copilot.tools import ToolResult
from pydantic import BaseModel, Field


class HospitalityEvidence(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)
    actor_ids: list[str] = Field(default_factory=list)
    event_ids: list[str] = Field(default_factory=list)
    trace_id: str
    as_of_sim_time: float = Field(ge=0)


def evidence_result(
    params: HospitalityEvidence,
    *,
    operation: str,
) -> ToolResult:
    payload = {
        "source_mode": "simulated",
        "operation": operation,
        "data": params.data,
        "actor_ids": params.actor_ids,
        "event_ids": params.event_ids,
        "trace_id": params.trace_id,
        "as_of_sim_time": params.as_of_sim_time,
    }
    return ToolResult(text_result_for_llm=json.dumps(payload, sort_keys=True))
