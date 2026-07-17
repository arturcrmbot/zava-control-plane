from __future__ import annotations

from copilot.tools import ToolResult, define_tool

from .common import (
    ActionParams,
    EvidenceParams,
    evidence_result,
    prepared_result,
    tool_result,
    validate_action_result,
)


TOOL_NAMES = {
    "network_query_state",
    "network_query_impact",
    "network_validate_action",
    "network_prepare_action",
}


@define_tool(
    name="network_query_state",
    description="Read simulated network actors and metrics with provenance.",
)
def network_query_state_tool(params: EvidenceParams) -> ToolResult:
    return tool_result(
        evidence_result(params, capability="network", operation="query_state")
    )


@define_tool(
    name="network_query_impact",
    description="Read simulated network service impact with provenance.",
)
def network_query_impact_tool(params: EvidenceParams) -> ToolResult:
    return tool_result(
        evidence_result(params, capability="network", operation="query_impact")
    )


@define_tool(
    name="network_validate_action",
    description="Validate a network action against the process allow-list.",
)
def network_validate_action_tool(params: ActionParams) -> ToolResult:
    return tool_result(validate_action_result(params, capability="network"))


@define_tool(
    name="network_prepare_action",
    description="Prepare a typed network command without mutating the world.",
)
def network_prepare_action_tool(params: ActionParams) -> ToolResult:
    return tool_result(prepared_result(params))
