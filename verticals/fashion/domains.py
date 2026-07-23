from __future__ import annotations

from api.shared.domain_contracts import Domain, HitlGate, Phase


def _gate(phase: str, event: str, persona: str) -> tuple[HitlGate, ...]:
    return (HitlGate(phase, event, persona),)


FASHION_DOMAINS: dict[str, Domain] = {
    "inventory-rebalancing": Domain(
        workflow_type="inventory-rebalancing",
        display_name="Inventory Rebalancing",
        workflow_id_prefix="REBAL",
        orchestrator_name="InventoryRebalancingOrchestrator",
        operator_surface="merchandising-planning",
        phases=(
            Phase("Detect Imbalance", "deterministic"),
            Phase("Assess Demand and Constraints", "agent"),
            Phase("Plan Rebalance", "agent"),
            Phase("Approve Exception", "hitl"),
            Phase("Execute Stock Action", "deterministic"),
            Phase("Verify Outcome", "deterministic"),
        ),
        hitl_gates=_gate(
            "Approve Exception",
            "merchandising_director_decision",
            "merchandising_director",
        ),
        skills=("inventory-imbalance-analysis", "inventory-rebalance-planner"),
        wake_hints=(),
    ),
    "demand-spike-response": Domain(
        workflow_type="demand-spike-response",
        display_name="Demand Spike Response",
        workflow_id_prefix="DEMAND",
        orchestrator_name="DemandSpikeResponseOrchestrator",
        operator_surface="merchandising-planning",
        phases=(
            Phase("Detect Regional Demand", "deterministic"),
            Phase("Assess Stock Exposure", "agent"),
            Phase("Approve Allocation Exception", "hitl"),
            Phase("Adjust Allocation", "deterministic"),
            Phase("Verify Availability", "deterministic"),
        ),
        hitl_gates=_gate(
            "Approve Allocation Exception",
            "inventory_allocation_manager_decision",
            "inventory_allocation_manager",
        ),
        skills=("inventory-imbalance-analysis",),
    ),
    "promotion-readiness": Domain(
        workflow_type="promotion-readiness",
        display_name="Promotion Readiness",
        workflow_id_prefix="PROMO",
        orchestrator_name="PromotionReadinessOrchestrator",
        operator_surface="merchandising-planning",
        phases=(
            Phase("Inspect Promotion Window", "deterministic"),
            Phase("Assess Channel Readiness", "agent"),
            Phase("Approve Readiness Plan", "hitl"),
            Phase("Prepare Promotion", "deterministic"),
            Phase("Verify Readiness", "deterministic"),
        ),
        hitl_gates=_gate(
            "Approve Readiness Plan",
            "inventory_allocation_manager_decision",
            "inventory_allocation_manager",
        ),
        skills=("promotion-readiness-assessor",),
    ),
    "markdown-governance": Domain(
        workflow_type="markdown-governance",
        display_name="Markdown Governance",
        workflow_id_prefix="MARKDOWN",
        orchestrator_name="MarkdownGovernanceOrchestrator",
        operator_surface="merchandising-planning",
        phases=(
            Phase("Detect Excess Stock", "deterministic"),
            Phase("Assess Markdown Options", "agent"),
            Phase("Approve Markdown Recommendation", "hitl"),
            Phase("Record Recommendation", "deterministic"),
            Phase("Verify Governance", "deterministic"),
        ),
        hitl_gates=_gate(
            "Approve Markdown Recommendation",
            "merchandising_director_decision",
            "merchandising_director",
        ),
        skills=("markdown-option-advisor",),
    ),
    "supplier-delay-recovery": Domain(
        workflow_type="supplier-delay-recovery",
        display_name="Supplier Delay Recovery",
        workflow_id_prefix="SUPPLY",
        orchestrator_name="SupplierDelayRecoveryOrchestrator",
        operator_surface="supply-chain-fulfilment",
        phases=(
            Phase("Detect Milestone Delay", "deterministic"),
            Phase("Plan Recovery Options", "agent"),
            Phase("Approve Recovery Spend", "hitl"),
            Phase("Commit Recovery Plan", "deterministic"),
            Phase("Verify Supplier Response", "deterministic"),
        ),
        hitl_gates=_gate(
            "Approve Recovery Spend",
            "supply_chain_director_decision",
            "supply_chain_director",
        ),
        skills=("supplier-recovery-planner",),
    ),
    "fulfilment-exception-resolution": Domain(
        workflow_type="fulfilment-exception-resolution",
        display_name="Fulfilment Exception Resolution",
        workflow_id_prefix="FULFIL",
        orchestrator_name="FulfilmentExceptionResolutionOrchestrator",
        operator_surface="supply-chain-fulfilment",
        phases=(
            Phase("Detect Allocation Failure", "deterministic"),
            Phase("Assess Fulfilment Options", "agent"),
            Phase("Approve Customer Exception", "hitl"),
            Phase("Resolve Fulfilment", "deterministic"),
            Phase("Verify Order Outcome", "deterministic"),
        ),
        hitl_gates=_gate(
            "Approve Customer Exception",
            "fulfilment_manager_decision",
            "fulfilment_manager",
        ),
        skills=("fulfilment-resolution-advisor",),
    ),
    "marketplace-seller-exception": Domain(
        workflow_type="marketplace-seller-exception",
        display_name="Marketplace Seller Exception",
        workflow_id_prefix="SELLER",
        orchestrator_name="MarketplaceSellerExceptionOrchestrator",
        operator_surface="marketplace-operations",
        phases=(
            Phase("Detect Seller Breach", "deterministic"),
            Phase("Assess Seller Evidence", "agent"),
            Phase("Approve Offer Suppression", "hitl"),
            Phase("Suppress Seller Offer", "deterministic"),
            Phase("Verify Marketplace State", "deterministic"),
        ),
        hitl_gates=_gate(
            "Approve Offer Suppression",
            "marketplace_operations_director_decision",
            "marketplace_operations_director",
        ),
        skills=("seller-exception-assessor",),
    ),
    "returns-disposition": Domain(
        workflow_type="returns-disposition",
        display_name="Returns Disposition",
        workflow_id_prefix="RETURN",
        orchestrator_name="ReturnsDispositionOrchestrator",
        operator_surface="customer-returns",
        phases=(
            Phase("Inspect Returned Item", "deterministic"),
            Phase("Assess Recovery Options", "agent"),
            Phase("Approve Non-standard Disposition", "hitl"),
            Phase("Apply Disposition", "deterministic"),
            Phase("Verify Recovery Outcome", "deterministic"),
        ),
        hitl_gates=_gate(
            "Approve Non-standard Disposition",
            "returns_operations_manager_decision",
            "returns_operations_manager",
        ),
        skills=("returns-disposition-advisor",),
    ),
}

