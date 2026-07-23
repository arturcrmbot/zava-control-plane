from __future__ import annotations

from copilot.tools import ToolResult, define_tool

from .common import RetailEvidence, evidence_result


TOOL_NAMES = {
    "fashion_read_inventory",
    "fashion_prepare_inventory_transfer",
    "fashion_assess_promotion",
    "fashion_prepare_markdown_recommendation",
    "fashion_prepare_supplier_recovery",
    "fashion_prepare_fulfilment_resolution",
    "fashion_prepare_seller_suppression",
    "fashion_prepare_return_disposition",
}


@define_tool(
    name="fashion_read_inventory",
    description="Read versioned Fashion inventory and demand evidence.",
)
def fashion_read_inventory(params: RetailEvidence) -> ToolResult:
    return evidence_result(params, operation="read_inventory")


@define_tool(
    name="fashion_prepare_inventory_transfer",
    description="Prepare, but never directly apply, a typed inventory transfer.",
)
def fashion_prepare_inventory_transfer(params: RetailEvidence) -> ToolResult:
    return evidence_result(params, operation="prepare_inventory_transfer")


@define_tool(
    name="fashion_assess_promotion",
    description="Assess promotion stock, content and channel readiness.",
)
def fashion_assess_promotion(params: RetailEvidence) -> ToolResult:
    return evidence_result(params, operation="assess_promotion")


@define_tool(
    name="fashion_prepare_markdown_recommendation",
    description="Prepare a governed markdown recommendation without changing price.",
)
def fashion_prepare_markdown_recommendation(params: RetailEvidence) -> ToolResult:
    return evidence_result(params, operation="prepare_markdown_recommendation")


@define_tool(
    name="fashion_prepare_supplier_recovery",
    description="Prepare a supplier delay recovery option.",
)
def fashion_prepare_supplier_recovery(params: RetailEvidence) -> ToolResult:
    return evidence_result(params, operation="prepare_supplier_recovery")


@define_tool(
    name="fashion_prepare_fulfilment_resolution",
    description="Prepare a typed order fulfilment resolution.",
)
def fashion_prepare_fulfilment_resolution(params: RetailEvidence) -> ToolResult:
    return evidence_result(params, operation="prepare_fulfilment_resolution")


@define_tool(
    name="fashion_prepare_seller_suppression",
    description="Prepare a marketplace offer suppression for human approval.",
)
def fashion_prepare_seller_suppression(params: RetailEvidence) -> ToolResult:
    return evidence_result(params, operation="prepare_seller_suppression")


@define_tool(
    name="fashion_prepare_return_disposition",
    description="Prepare a typed return disposition from inspection evidence.",
)
def fashion_prepare_return_disposition(params: RetailEvidence) -> ToolResult:
    return evidence_result(params, operation="prepare_return_disposition")
