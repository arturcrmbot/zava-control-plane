# api/server/services/economics.py
"""Per-workflow cost aggregation, derived from real OTEL token telemetry.

History: prior to 2026-05-05 this module multiplied executor wall-clock seconds
by a hardcoded `COMPUTE_RATE_PER_SECOND` and agent-call count by a hardcoded
`MODEL_CALL_RATE`. Both constants were synthetic. This rewrite (per
plan/feature-foundry-credibility-friday-1.md TASK-010) reads the
`gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens` /
`gen_ai.request.model` attributes that the agent wrapper at
`api/functions/graphs/executors/agents/_wrapper.py` already records on every
`gen_ai.generate_content` span, and converts them to USD via the pricing
table in `model_pricing.py`. The same span shape goes to App Insights →
Foundry Tracing, so the number on screen and the number in Foundry's
monitoring dashboard agree by construction.

Returned dict shape (camelCase to match the UI binding):
    modelCostUsd: float        # NEW — derived from real tokens × pricing
    computeCostUsd: float      # DEPRECATED alias of modelCostUsd (UI back-compat)
    inputTokens: int           # NEW — sum across spans
    outputTokens: int          # NEW — sum across spans
    pricingSource: str         # NEW — provenance string
    modelCalls: int            # count of agent spans
    toolCalls: int             # count of MCP calls
    daysElapsed: float         # time since workflow.created_at
    slaToken: str              # opaque ID for ledger correlation
    perModel: list[dict]       # NEW — per-model breakdown for drill-down
"""
from __future__ import annotations
import hashlib
import time
from collections import defaultdict
from typing import Any

from api.server.services import model_pricing
from api.shared.types import McpCall, OtelSpan, Workflow


_DEFAULT_MODEL = "gpt-4.1"


def _is_agent_span(span: OtelSpan) -> bool:
    """A span counts as an agent invocation if it carries the `gen_ai.system`
    attribute (set by the agent wrapper) OR has the legacy
    `executor.type == "agent"` label still emitted by `_tracked_executor`.
    Either signal is sufficient.
    """
    attrs = span.attributes or {}
    return bool(attrs.get("gen_ai.system")) or attrs.get("executor.type") == "agent"


def _token_buckets(spans: list[OtelSpan]) -> dict[str, dict[str, int]]:
    """Group input/output token counts per model id across all spans.

    Returns `{model_id: {"input": int, "output": int, "calls": int}}`.
    Spans without `gen_ai.usage.*` attributes contribute 0 tokens; they still
    count as a `call` so the call counter remains meaningful when the GHCP SDK
    didn't surface usage for a particular response.
    """
    buckets: dict[str, dict[str, int]] = defaultdict(
        lambda: {"input": 0, "output": 0, "calls": 0}
    )
    for s in spans:
        if not _is_agent_span(s):
            continue
        attrs = s.attributes or {}
        model = (
            attrs.get("gen_ai.request.model")
            or attrs.get("zava.agent.model")
            or _DEFAULT_MODEL
        )
        in_tok = int(attrs.get("gen_ai.usage.input_tokens") or 0)
        out_tok = int(attrs.get("gen_ai.usage.output_tokens") or 0)
        b = buckets[model]
        b["input"] += in_tok
        b["output"] += out_tok
        b["calls"] += 1
    return dict(buckets)


def compute(workflow: Workflow, *, spans: list[OtelSpan],
            mcp_calls: list[McpCall]) -> dict[str, Any]:
    buckets = _token_buckets(spans)
    total_input = sum(b["input"] for b in buckets.values())
    total_output = sum(b["output"] for b in buckets.values())
    total_cost = sum(
        model_pricing.cost_for(m, b["input"], b["output"])
        for m, b in buckets.items()
    )
    model_calls = sum(b["calls"] for b in buckets.values())
    tool_calls = len(mcp_calls)
    days_elapsed = max(0.0, (time.time() - workflow.created_at) / 86400.0)
    sla_token = "SLA-" + hashlib.sha256(workflow.id.encode()).hexdigest()[:4].upper()

    cost_rounded = round(total_cost, 4)
    return {
        "modelCostUsd": cost_rounded,
        # Back-compat alias: existing UI tiles bind to `computeCostUsd`. Same
        # number, different key. Removable once the UI migrates.
        "computeCostUsd": cost_rounded,
        "inputTokens": total_input,
        "outputTokens": total_output,
        "pricingSource": model_pricing.PRICING_SOURCE,
        "modelCalls": model_calls,
        "toolCalls": tool_calls,
        "daysElapsed": round(days_elapsed, 2),
        "slaToken": sla_token,
        "perModel": [
            {
                "model": m,
                "inputTokens": b["input"],
                "outputTokens": b["output"],
                "calls": b["calls"],
                "costUsd": round(model_pricing.cost_for(m, b["input"], b["output"]), 4),
            }
            for m, b in sorted(buckets.items())
        ],
    }
