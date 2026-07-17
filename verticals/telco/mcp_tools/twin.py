from __future__ import annotations

from copilot.tools import ToolResult, define_tool

from .common import (
    ActionParams,
    EvidenceParams,
    evidence_result,
    prepared_result,
    tool_result,
)


TOOL_NAMES = {
    "twin_forecast",
    "twin_compare_scenarios",
    "twin_query_external_signal",
    "twin_publish_plan",
}


@define_tool(
    name="twin_forecast",
    description="Return deterministic forecast evidence supplied by the world.",
)
def twin_forecast_tool(params: EvidenceParams) -> ToolResult:
    return tool_result(
        evidence_result(params, capability="twin", operation="forecast")
    )


@define_tool(
    name="twin_compare_scenarios",
    description="Return deterministic scenario comparison evidence.",
)
def twin_compare_scenarios_tool(params: EvidenceParams) -> ToolResult:
    return tool_result(
        evidence_result(
            params,
            capability="twin",
            operation="compare_scenarios",
        )
    )


@define_tool(
    name="twin_query_external_signal",
    description="Read simulated weather, grid or benchmark signals.",
)
def twin_query_external_signal_tool(params: EvidenceParams) -> ToolResult:
    return tool_result(
        evidence_result(
            params,
            capability="twin",
            operation="query_external_signal",
        )
    )


@define_tool(
    name="twin_publish_plan",
    description="Prepare a typed plan publication command.",
)
def twin_publish_plan_tool(params: ActionParams) -> ToolResult:
    return tool_result(prepared_result(params))
