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
    "operations_query_case",
    "operations_search_runbook",
    "operations_match_resources",
    "operations_prepare_case_action",
}


@define_tool(
    name="operations_query_case",
    description="Read simulated ticket, work, stock or change cases.",
)
def operations_query_case_tool(params: EvidenceParams) -> ToolResult:
    return tool_result(
        evidence_result(params, capability="operations", operation="query_case")
    )


@define_tool(
    name="operations_search_runbook",
    description="Return matching synthetic runbook evidence.",
)
def operations_search_runbook_tool(params: EvidenceParams) -> ToolResult:
    return tool_result(
        evidence_result(
            params,
            capability="operations",
            operation="search_runbook",
        )
    )


@define_tool(
    name="operations_match_resources",
    description="Return supplied workforce and stock constraints for matching.",
)
def operations_match_resources_tool(params: EvidenceParams) -> ToolResult:
    return tool_result(
        evidence_result(
            params,
            capability="operations",
            operation="match_resources",
        )
    )


@define_tool(
    name="operations_prepare_case_action",
    description="Prepare a typed operations command without world mutation.",
)
def operations_prepare_case_action_tool(params: ActionParams) -> ToolResult:
    return tool_result(prepared_result(params))
