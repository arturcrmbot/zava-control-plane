from __future__ import annotations

from copilot.tools import ToolResult, define_tool

from .common import RetailEvidence, evidence_result


TOOL_NAMES = {
    "electronics_read_inventory",
    "electronics_prepare_inventory_transfer",
    "electronics_assess_promotion",
    "electronics_prepare_markdown_recommendation",
    "electronics_prepare_supplier_recovery",
    "electronics_prepare_fulfilment_resolution",
    "electronics_prepare_seller_suppression",
    "electronics_prepare_return_disposition",
}


@define_tool(
    name="electronics_read_inventory",
    description="Read versioned device inventory and demand evidence.",
)
def electronics_read_inventory(params: RetailEvidence) -> ToolResult:
    return evidence_result(params, operation="read_inventory")


@define_tool(
    name="electronics_prepare_inventory_transfer",
    description=(
        "Prepare, but never directly apply, a typed device inventory transfer "
        "between store and distribution-centre locations."
    ),
)
def electronics_prepare_inventory_transfer(params: RetailEvidence) -> ToolResult:
    return evidence_result(params, operation="prepare_inventory_transfer")


@define_tool(
    name="electronics_assess_promotion",
    description="Assess launch readiness: stock, content and channel readiness for a device promotion.",
)
def electronics_assess_promotion(params: RetailEvidence) -> ToolResult:
    return evidence_result(params, operation="assess_promotion")


@define_tool(
    name="electronics_prepare_markdown_recommendation",
    description="Prepare a governed markdown recommendation without changing device price.",
)
def electronics_prepare_markdown_recommendation(params: RetailEvidence) -> ToolResult:
    return evidence_result(params, operation="prepare_markdown_recommendation")


@define_tool(
    name="electronics_prepare_supplier_recovery",
    description="Prepare a supplier allocation delay recovery option for delayed device deliveries.",
)
def electronics_prepare_supplier_recovery(params: RetailEvidence) -> ToolResult:
    return evidence_result(params, operation="prepare_supplier_recovery")


@define_tool(
    name="electronics_prepare_fulfilment_resolution",
    description="Prepare a typed omnichannel order fulfilment resolution.",
)
def electronics_prepare_fulfilment_resolution(params: RetailEvidence) -> ToolResult:
    return evidence_result(params, operation="prepare_fulfilment_resolution")


@define_tool(
    name="electronics_prepare_seller_suppression",
    description="Prepare a marketplace offer suppression for human approval.",
)
def electronics_prepare_seller_suppression(params: RetailEvidence) -> ToolResult:
    return evidence_result(params, operation="prepare_seller_suppression")


@define_tool(
    name="electronics_prepare_return_disposition",
    description="Prepare a typed device return/repair disposition from inspection evidence.",
)
def electronics_prepare_return_disposition(params: RetailEvidence) -> ToolResult:
    return evidence_result(params, operation="prepare_return_disposition")


TOOL_BY_NAME = {
    "electronics_read_inventory": electronics_read_inventory,
    "electronics_prepare_inventory_transfer": electronics_prepare_inventory_transfer,
    "electronics_assess_promotion": electronics_assess_promotion,
    "electronics_prepare_markdown_recommendation": (
        electronics_prepare_markdown_recommendation
    ),
    "electronics_prepare_supplier_recovery": electronics_prepare_supplier_recovery,
    "electronics_prepare_fulfilment_resolution": (
        electronics_prepare_fulfilment_resolution
    ),
    "electronics_prepare_seller_suppression": electronics_prepare_seller_suppression,
    "electronics_prepare_return_disposition": electronics_prepare_return_disposition,
}
