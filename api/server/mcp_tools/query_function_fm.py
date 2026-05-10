"""query_function_fm MCP tool — Phase 4 IP6 (TASK-029, DEC-OQ2).

CEO-FM-only delegation surface. Resolves a named ``FunctionFleetManager``
from :attr:`AppState.function_fms` and returns a stub response payload
plus the most recent KPI snapshot rows for that function (one row per
metric, taken as the latest ``captured_at``).

The session-call semantics are deliberately stubbed: fully wiring the
CEO-FM session into a sub-FM session is a future enhancement. The
contract this tool returns is stable so the CEO-FM skill text can call
the tool today.
"""
from __future__ import annotations

import json

from copilot.tools import ToolInvocation, ToolResult, define_tool
from pydantic import BaseModel, Field

from api.shared.functions import FUNCTIONS
from ._otel import traced_tool


class _Params(BaseModel):
    function: str = Field(..., description="Target function name (e.g. 'finance').")
    prompt: str = Field(..., description="Prompt to forward to the function FM.")


def _latest_per_metric(rows: list[dict]) -> list[dict]:
    """Reduce a flat list of KPI rows to one row per metric (latest captured)."""
    by_metric: dict[str, dict] = {}
    for r in rows:
        m = r.get("metric")
        if m is None:
            continue
        prev = by_metric.get(m)
        if prev is None or r.get("captured_at", 0) > prev.get("captured_at", 0):
            by_metric[m] = r
    return sorted(by_metric.values(), key=lambda r: r.get("metric", ""))


def query_function_fm(app_state, function: str, prompt: str) -> dict:
    """Pure-Python delegation handler. Returns the stub payload.

    Public so tests can call it without going through the tool wrapper.
    """
    if function not in FUNCTIONS:
        raise ValueError(f"unknown function: {function!r}")
    fm = app_state.function_fms.get(function)
    if fm is None:
        raise LookupError(
            f"FunctionFleetManager for function={function!r} is not registered "
            f"on app_state (init_function_fms() may not have been called)."
        )
    kpi_rows: list[dict] = []
    kpi_store = getattr(app_state, "kpi_store", None)
    if kpi_store is not None:
        try:
            kpi_rows = kpi_store.query(function=function)
        except Exception:  # pragma: no cover — defensive: KpiStore missing
            kpi_rows = []
    return {
        "function": function,
        "response": (
            "<stub - full FM session call lands later; CEO-FM skill text "
            "uses kpi_snapshot for now>"
        ),
        "prompt": prompt,
        "kpi_snapshot": _latest_per_metric(kpi_rows),
    }


def make_query_function_fm_tool(app_state):
    """Build a CEO-FM-bound delegation tool. Singleton — only the CEO-FM
    gets this in its tool list (per TASK-031)."""

    @define_tool(
        name="query_function_fm",
        description=(
            "CEO-FM only. Delegate a prompt to a named FunctionFleetManager "
            "and return its stub response plus the latest KPI snapshot rows "
            "for that function (one per metric). Args: function (one of "
            f"{sorted(k for k in FUNCTIONS if k not in ('legacy', 'ceo'))!r}), "
            "prompt."
        ),
        skip_permission=True,
    )
    @traced_tool("query_function_fm")
    def _tool(params: _Params, invocation: ToolInvocation) -> ToolResult:
        try:
            payload = query_function_fm(app_state, params.function, params.prompt)
        except (ValueError, LookupError) as exc:
            return ToolResult(
                text_result_for_llm=json.dumps({"error": str(exc)}),
                result_type="error",
            )
        return ToolResult(
            text_result_for_llm=json.dumps(payload, default=str),
            result_type="success",
        )

    return _tool
