"""query_economics MCP tool — weekly cost-per-task aggregate over the
in-memory workflow store.

Walks `app_state.store.list_workflows()` over a `window_hours` window
(default 168 = 1 week) and aggregates `tokens_spent` + `cost_usd`.
Returns total cost, average cost per task, and a per-verdict breakdown.

Used by the Fleet Manager `report.cost_per_task` extension (AC #13).

Dual-surface (plain Python `query()` + SDK-native Tool) per the project's
MCP tool convention.
"""
from __future__ import annotations
import json
import time
from collections import defaultdict
from typing import Optional

from copilot.tools import ToolResult, define_tool
from opentelemetry import trace
from pydantic import BaseModel, Field

from ._otel import traced_tool
from api.server.services import economics
from api.server.state import app_state


def _group_avg_cost(items: list[dict]) -> dict:
    """Bucket items by `verdict` and compute (n, total_cost_usd, avg).

    Workflows with `verdict=None` cluster as the "unknown" key so the FM
    skill can surface them distinctly from green/amber/red.
    """
    buckets: dict[str, list[dict]] = defaultdict(list)
    for it in items:
        key = it.get("verdict") or "unknown"
        buckets[key].append(it)
    out: dict[str, dict] = {}
    for key, members in buckets.items():
        n = len(members)
        total = sum(m["cost_usd"] for m in members)
        out[key] = {
            "n": n,
            "total_cost_usd": round(total, 4),
            "avg_cost_per_task_usd": round(total / n, 6) if n else 0,
        }
    return out


@traced_tool("query.economics")
def query(window_hours: int = 24 * 7) -> dict:
    """Aggregate per-workflow tokens / cost over the last `window_hours`.

    Cost is derived per workflow from OTEL spans via
    `services.economics.compute()` — see
    plan/feature-foundry-credibility-friday-1.md TASK-013 for the swap from
    `w.tokens_spent` / `w.cost_usd` (never written, always 0) to real
    `gen_ai.usage.*` attributes recorded by the agent wrapper.
    """
    span = trace.get_current_span()
    span.set_attribute("zava.economics.window_hours", window_hours)

    cutoff = time.time() - window_hours * 3600
    items: list[dict] = []
    for w in app_state.store.list_workflows():
        if w.created_at < cutoff:
            continue
        eco = economics.compute(
            w,
            spans=app_state.store.get_spans(w.id),
            mcp_calls=app_state.store.get_mcp_calls(w.id),
        )
        items.append({
            "workflow_id": w.id,
            "tokens_spent": eco["inputTokens"] + eco["outputTokens"],
            "input_tokens": eco["inputTokens"],
            "output_tokens": eco["outputTokens"],
            "cost_usd": eco["modelCostUsd"],
            "verdict": getattr(w, "verdict", None),
        })

    n = len(items)
    total_cost = sum(i["cost_usd"] for i in items)
    span.set_attribute("zava.economics.n", n)
    span.set_attribute("zava.economics.total_cost_usd", float(total_cost))

    return {
        "window_hours": window_hours,
        "n": n,
        "total_cost_usd": round(total_cost, 4),
        "avg_cost_per_task_usd": round(total_cost / n, 6) if n else 0,
        "by_verdict": _group_avg_cost(items),
        "items": items[:50],
        "pricing_source": "azure-published-2026-05-05",
    }


class _Params(BaseModel):
    window_hours: int = Field(
        default=168,
        ge=1,
        le=24 * 365,
        description=(
            "Look-back window in hours (default 168 = 1 week). "
            "Only workflows with created_at within the window are counted."
        ),
    )


@define_tool(
    name="query_economics",
    description=(
        "Aggregate per-workflow tokens and cost over a window (default 168h). "
        "Returns total_cost_usd, avg_cost_per_task_usd, and a by_verdict "
        "breakdown for green / amber / red / unknown plus the first 50 items."
    ),
)
def query_economics_tool(params: _Params) -> ToolResult:
    out = query(window_hours=params.window_hours)
    return ToolResult(text_result_for_llm=json.dumps(out, ensure_ascii=False))
