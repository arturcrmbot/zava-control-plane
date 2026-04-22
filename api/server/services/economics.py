# api/server/services/economics.py
from __future__ import annotations
import hashlib
import time
from api.shared.types import Workflow, OtelSpan, McpCall


COMPUTE_RATE_PER_SECOND = 0.0001   # $ per second of executor wall-clock
MODEL_CALL_RATE = 0.02             # $ per agent executor invocation


def compute(workflow: Workflow, *, spans: list[OtelSpan],
            mcp_calls: list[McpCall]) -> dict:
    model_calls = sum(
        1 for s in spans if s.attributes.get("executor.type") == "agent"
    )
    tool_calls = len(mcp_calls)
    executor_seconds = sum(max(0.0, s.end_ms - s.start_ms) for s in spans) / 1000.0
    compute_usd = (
        executor_seconds * COMPUTE_RATE_PER_SECOND
        + model_calls * MODEL_CALL_RATE
    )
    days_elapsed = max(0.0, (time.time() - workflow.created_at) / 86400.0)
    sla_token = "SLA-" + hashlib.sha256(workflow.id.encode()).hexdigest()[:4].upper()
    return {
        "computeCostUsd": round(compute_usd, 2),
        "modelCalls": model_calls,
        "toolCalls": tool_calls,
        "daysElapsed": round(days_elapsed, 2),
        "slaToken": sla_token,
    }
