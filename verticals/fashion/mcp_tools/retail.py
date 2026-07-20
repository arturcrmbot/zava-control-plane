from __future__ import annotations

from copilot.tools import ToolResult, define_tool

from verticals.fashion.mcp_tools.common import (
    FashionCommandParams,
    FashionEvidenceParams,
    command_result,
    evidence_result,
)

TOOL_NAMES = {
    "fashion_query_demand",
    "fashion_query_inventory",
    "fashion_query_orders",
    "fashion_query_partners",
    "fashion_query_policies",
    "fashion_query_returns",
    "fashion_prepare_command",
}


def _query(
    params: FashionEvidenceParams,
    operation: str,
) -> ToolResult:
    return evidence_result(params, operation=operation)


@define_tool(name="fashion_query_demand", description="Read synthetic demand evidence.")
def fashion_query_demand_tool(params: FashionEvidenceParams) -> ToolResult:
    return _query(params, "query_demand")


@define_tool(name="fashion_query_inventory", description="Read inventory evidence.")
def fashion_query_inventory_tool(params: FashionEvidenceParams) -> ToolResult:
    return _query(params, "query_inventory")


@define_tool(name="fashion_query_orders", description="Read order evidence.")
def fashion_query_orders_tool(params: FashionEvidenceParams) -> ToolResult:
    return _query(params, "query_orders")


@define_tool(name="fashion_query_partners", description="Read partner evidence.")
def fashion_query_partners_tool(params: FashionEvidenceParams) -> ToolResult:
    return _query(params, "query_partners")


@define_tool(name="fashion_query_policies", description="Read demo policy evidence.")
def fashion_query_policies_tool(params: FashionEvidenceParams) -> ToolResult:
    return _query(params, "query_policies")


@define_tool(name="fashion_query_returns", description="Read returns evidence.")
def fashion_query_returns_tool(params: FashionEvidenceParams) -> ToolResult:
    return _query(params, "query_returns")


@define_tool(
    name="fashion_prepare_command",
    description="Prepare a typed Fashion command without mutating world state.",
)
def fashion_prepare_command_tool(params: FashionCommandParams) -> ToolResult:
    return command_result(params)
