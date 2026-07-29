from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ElectronicsProcessProfile:
    workflow_type: str
    display_name: str
    function: str
    sensor_id: str
    objective_type: str
    command_type: str
    success_event: str
    orchestrator: str
    prefix: str
    skill: str
    hitl_persona: str | None
    hitl_event: str | None
    maturity: str = "standard"


ELECTRONICS_PROCESS_PROFILES: dict[str, ElectronicsProcessProfile] = {
    "inventory-rebalancing": ElectronicsProcessProfile(
        workflow_type="inventory-rebalancing",
        display_name="Inventory Rebalancing",
        function="merchandising-planning",
        sensor_id="sensor:inventory_imbalance",
        objective_type="inventory_rebalancing",
        command_type="inventory.transfer",
        success_event="inventory.transferred",
        orchestrator="InventoryRebalancingOrchestrator",
        prefix="rebalance",
        skill="inventory-rebalance-planner",
        hitl_persona="merchandising_director",
        hitl_event="merchandising_director_decision",
        maturity="hero",
    ),
    "demand-spike-response": ElectronicsProcessProfile(
        workflow_type="demand-spike-response",
        display_name="Launch Demand Response",
        function="merchandising-planning",
        sensor_id="sensor:demand_spike",
        objective_type="demand_spike_response",
        command_type="allocation.adjust",
        success_event="allocation.adjusted",
        orchestrator="DemandSpikeResponseOrchestrator",
        prefix="demand",
        skill="inventory-imbalance-analysis",
        hitl_persona="inventory_allocation_manager",
        hitl_event="inventory_allocation_manager_decision",
    ),
    "promotion-readiness": ElectronicsProcessProfile(
        workflow_type="promotion-readiness",
        display_name="Launch Promotion Readiness",
        function="merchandising-planning",
        sensor_id="sensor:promotion_risk",
        objective_type="promotion_readiness",
        command_type="promotion.prepare",
        success_event="promotion.ready",
        orchestrator="PromotionReadinessOrchestrator",
        prefix="promotion",
        skill="promotion-readiness-assessor",
        hitl_persona="inventory_allocation_manager",
        hitl_event="inventory_allocation_manager_decision",
    ),
    "markdown-governance": ElectronicsProcessProfile(
        workflow_type="markdown-governance",
        display_name="Launch Margin Governance",
        function="merchandising-planning",
        sensor_id="sensor:markdown_exposure",
        objective_type="markdown_governance",
        command_type="markdown.recommend",
        success_event="markdown.recommended",
        orchestrator="MarkdownGovernanceOrchestrator",
        prefix="markdown",
        skill="markdown-option-advisor",
        hitl_persona="merchandising_director",
        hitl_event="merchandising_director_decision",
    ),
    "supplier-delay-recovery": ElectronicsProcessProfile(
        workflow_type="supplier-delay-recovery",
        display_name="Supplier Allocation Recovery",
        function="supply-chain-fulfilment",
        sensor_id="sensor:supplier_delay",
        objective_type="supplier_delay_recovery",
        command_type="supplier.recover",
        success_event="supplier.recovery.planned",
        orchestrator="SupplierDelayRecoveryOrchestrator",
        prefix="supplier",
        skill="supplier-recovery-planner",
        hitl_persona="supply_chain_director",
        hitl_event="supply_chain_director_decision",
    ),
    "fulfilment-exception-resolution": ElectronicsProcessProfile(
        workflow_type="fulfilment-exception-resolution",
        display_name="Omnichannel Fulfilment Recovery",
        function="supply-chain-fulfilment",
        sensor_id="sensor:fulfilment_exception",
        objective_type="fulfilment_exception_resolution",
        command_type="fulfilment.resolve",
        success_event="order.fulfilment.resolved",
        orchestrator="FulfilmentExceptionResolutionOrchestrator",
        prefix="fulfilment",
        skill="fulfilment-resolution-advisor",
        hitl_persona="fulfilment_manager",
        hitl_event="fulfilment_manager_decision",
    ),
    "marketplace-seller-exception": ElectronicsProcessProfile(
        workflow_type="marketplace-seller-exception",
        display_name="Marketplace Seller Exception",
        function="marketplace-operations",
        sensor_id="sensor:seller_sla_breach",
        objective_type="marketplace_seller_exception",
        command_type="seller.offer.suppress",
        success_event="seller.offer.suppressed",
        orchestrator="MarketplaceSellerExceptionOrchestrator",
        prefix="seller",
        skill="seller-exception-assessor",
        hitl_persona="marketplace_operations_director",
        hitl_event="marketplace_operations_director_decision",
    ),
    "returns-disposition": ElectronicsProcessProfile(
        workflow_type="returns-disposition",
        display_name="Returns & Repair Disposition",
        function="customer-returns",
        sensor_id="sensor:return_received",
        objective_type="returns_disposition",
        command_type="return.disposition",
        success_event="return.disposed",
        orchestrator="ReturnsDispositionOrchestrator",
        prefix="returns",
        skill="returns-disposition-advisor",
        hitl_persona="returns_operations_manager",
        hitl_event="returns_operations_manager_decision",
    ),
}

