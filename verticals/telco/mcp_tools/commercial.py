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
    "commercial_query_customer",
    "commercial_query_order_revenue",
    "commercial_evaluate_entitlement",
    "commercial_prepare_action",
}


@define_tool(
    name="commercial_query_customer",
    description="Read simulated Customer 360 evidence with provenance.",
)
def commercial_query_customer_tool(params: EvidenceParams) -> ToolResult:
    return tool_result(
        evidence_result(
            params,
            capability="commercial",
            operation="query_customer",
        )
    )


@define_tool(
    name="commercial_query_order_revenue",
    description="Read simulated order, usage, bill and payment evidence.",
)
def commercial_query_order_revenue_tool(params: EvidenceParams) -> ToolResult:
    return tool_result(
        evidence_result(
            params,
            capability="commercial",
            operation="query_order_revenue",
        )
    )


@define_tool(
    name="commercial_evaluate_entitlement",
    description="Return supplied policy and entitlement evidence.",
)
def commercial_evaluate_entitlement_tool(
    params: EvidenceParams,
) -> ToolResult:
    return tool_result(
        evidence_result(
            params,
            capability="commercial",
            operation="evaluate_entitlement",
        )
    )


@define_tool(
    name="commercial_prepare_action",
    description="Prepare a typed commercial command without world mutation.",
)
def commercial_prepare_action_tool(params: ActionParams) -> ToolResult:
    return tool_result(prepared_result(params))
