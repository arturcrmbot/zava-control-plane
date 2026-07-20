from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FashionPhaseProfile:
    name: str
    kind: str


@dataclass(frozen=True, slots=True)
class FashionProcessProfile:
    workflow_type: str
    display_name: str
    kind: str
    function: str
    workflow_id_prefix: str
    sensor_id: str
    objective_type: str
    orchestrator_name: str
    phases: tuple[FashionPhaseProfile, ...]
    hitl_event: str
    hitl_persona: str
    skills: tuple[str, ...]
    command_type: str
    allowed_actions: tuple[str, ...]
    success_event: str
    mutation_family: str
    case_id: str
    # The Fashion authority-persona role that generates/owns the
    # recommendation for this workflow (audit identity for the world's
    # self-approval guard). Same namespace as FASHION_AUTHORITY keys and
    # ``hitl_persona`` — distinct from ``function``, which is a
    # CommandGateway ownership label, not a persona.
    recommender_persona: str = ""
    stub: bool = False


def _phases(*values: tuple[str, str]) -> tuple[FashionPhaseProfile, ...]:
    return tuple(FashionPhaseProfile(name, kind) for name, kind in values)


FASHION_PROCESS_PROFILES: dict[str, FashionProcessProfile] = {
    "inventory-rebalancing": FashionProcessProfile(
        workflow_type="inventory-rebalancing",
        display_name="Inventory Rebalancing",
        kind="hero",
        function="merchandising-planning",
        workflow_id_prefix="FIR",
        sensor_id="sensor:inventory_imbalance",
        objective_type="rebalance_inventory",
        orchestrator_name="InventoryRebalancingOrchestrator",
        phases=_phases(
            ("Detect Imbalance", "deterministic"),
            ("Assess Demand and Constraints", "agent"),
            ("Plan Rebalance", "agent"),
            ("Approve Exception", "hitl"),
            ("Execute Stock Action", "deterministic"),
            ("Verify Outcome", "deterministic"),
        ),
        hitl_event="merchandising_director_decision",
        hitl_persona="merchandising_director",
        skills=(
            "inventory-imbalance-analysis",
            "inventory-rebalance-planner",
        ),
        command_type="inventory.transfer",
        allowed_actions=("inventory.transfer", "no-action"),
        success_event="inventory.transfer.completed",
        mutation_family="inventory",
        case_id="fashion-inventory-rebalance-auto",
        recommender_persona="inventory_allocation_manager",
    ),
    "demand-spike-response": FashionProcessProfile(
        workflow_type="demand-spike-response",
        display_name="Demand Spike Response",
        kind="supporting",
        function="merchandising-planning",
        workflow_id_prefix="FDS",
        sensor_id="sensor:demand_spike",
        objective_type="respond_to_demand_spike",
        orchestrator_name="DemandSpikeResponseOrchestrator",
        phases=_phases(
            ("Detect Demand Spike", "deterministic"),
            ("Assess Allocation Options", "agent"),
            ("Approve Allocation Exception", "hitl"),
            ("Apply Allocation Response", "deterministic"),
            ("Verify Demand Coverage", "deterministic"),
        ),
        hitl_event="inventory_allocation_manager_decision",
        hitl_persona="inventory_allocation_manager",
        skills=("inventory-imbalance-analysis",),
        command_type="allocation.respond",
        allowed_actions=(
            "allocation.respond",
            "reallocate",
            "reserve",
            "no-action",
        ),
        success_event="allocation.response.completed",
        mutation_family="allocation",
        case_id="fashion-demand-spike-response",
    ),
    "promotion-readiness": FashionProcessProfile(
        workflow_type="promotion-readiness",
        display_name="Promotion Readiness",
        kind="supporting",
        function="merchandising-planning",
        workflow_id_prefix="FPR",
        sensor_id="sensor:promotion_window_risk",
        objective_type="prepare_promotion",
        orchestrator_name="PromotionReadinessOrchestrator",
        phases=_phases(
            ("Detect Readiness Risk", "deterministic"),
            ("Assess Stock Content and Channel", "agent"),
            ("Approve Readiness Exception", "hitl"),
            ("Apply Readiness Action", "deterministic"),
            ("Verify Promotion Readiness", "deterministic"),
        ),
        hitl_event="inventory_allocation_manager_decision",
        hitl_persona="inventory_allocation_manager",
        skills=("promotion-readiness-assessor",),
        command_type="promotion.prepare",
        allowed_actions=(
            "promotion.prepare",
            "ready-channel",
            "hold-channel",
            "defer-promotion",
        ),
        success_event="promotion.readiness.completed",
        mutation_family="promotion",
        case_id="fashion-promotion-readiness",
    ),
    "markdown-governance": FashionProcessProfile(
        workflow_type="markdown-governance",
        display_name="Markdown Governance",
        kind="supporting",
        function="merchandising-planning",
        workflow_id_prefix="FMG",
        sensor_id="sensor:excess_stock_risk",
        objective_type="govern_markdown",
        orchestrator_name="MarkdownGovernanceOrchestrator",
        phases=_phases(
            ("Detect Excess Stock Risk", "deterministic"),
            ("Assess Markdown Options", "agent"),
            ("Approve Markdown Recommendation", "hitl"),
            ("Record Recommendation", "deterministic"),
            ("Verify Governance Outcome", "deterministic"),
        ),
        hitl_event="merchandising_director_decision",
        hitl_persona="merchandising_director",
        skills=("markdown-option-advisor",),
        command_type="markdown.recommend",
        allowed_actions=(
            "markdown.recommend",
            "recommend-markdown",
            "hold-full-price",
        ),
        success_event="markdown.recommendation.reviewed",
        mutation_family="recommendation",
        case_id="fashion-markdown-governance",
    ),
    "supplier-delay-recovery": FashionProcessProfile(
        workflow_type="supplier-delay-recovery",
        display_name="Supplier Delay Recovery",
        kind="supporting",
        function="supply-chain-fulfilment",
        workflow_id_prefix="FSR",
        sensor_id="sensor:supplier_milestone_delay",
        objective_type="recover_supplier_delay",
        orchestrator_name="SupplierDelayRecoveryOrchestrator",
        phases=_phases(
            ("Detect Supplier Delay", "deterministic"),
            ("Plan Recovery", "agent"),
            ("Approve Recovery Exception", "hitl"),
            ("Execute Recovery Action", "deterministic"),
            ("Verify Availability Recovery", "deterministic"),
        ),
        hitl_event="supply_chain_director_decision",
        hitl_persona="supply_chain_director",
        skills=("supplier-recovery-planner",),
        command_type="supplier.recover",
        allowed_actions=(
            "supplier.recover",
            "substitute",
            "split",
            "expedite",
            "replan",
        ),
        success_event="supplier.recovery.completed",
        mutation_family="supplier-delivery",
        case_id="fashion-supplier-delay-recovery",
    ),
    "fulfilment-exception-resolution": FashionProcessProfile(
        workflow_type="fulfilment-exception-resolution",
        display_name="Fulfilment Exception Resolution",
        kind="supporting",
        function="supply-chain-fulfilment",
        workflow_id_prefix="FFE",
        sensor_id="sensor:order_allocation_failure",
        objective_type="resolve_fulfilment_exception",
        orchestrator_name="FulfilmentExceptionResolutionOrchestrator",
        phases=_phases(
            ("Detect Allocation Failure", "deterministic"),
            ("Plan Fulfilment Resolution", "agent"),
            ("Approve Resolution Exception", "hitl"),
            ("Execute Fulfilment Action", "deterministic"),
            ("Verify Order Outcome", "deterministic"),
        ),
        hitl_event="fulfilment_manager_decision",
        hitl_persona="fulfilment_manager",
        skills=("fulfilment-resolution-advisor",),
        command_type="fulfilment.resolve",
        allowed_actions=(
            "fulfilment.resolve",
            "reroute",
            "split-fulfilment",
            "cancel",
        ),
        success_event="fulfilment.exception.resolved",
        mutation_family="order-fulfilment",
        case_id="fashion-fulfilment-exception",
    ),
    "marketplace-seller-exception": FashionProcessProfile(
        workflow_type="marketplace-seller-exception",
        display_name="Marketplace Seller Exception",
        kind="supporting",
        function="marketplace-operations",
        workflow_id_prefix="FME",
        sensor_id="sensor:seller_stock_sla_breach",
        objective_type="resolve_seller_exception",
        orchestrator_name="MarketplaceSellerExceptionOrchestrator",
        phases=_phases(
            ("Detect Seller Breach", "deterministic"),
            ("Assess Seller Exception", "agent"),
            ("Approve Seller Action", "hitl"),
            ("Execute Seller Action", "deterministic"),
            ("Verify Partner Outcome", "deterministic"),
        ),
        hitl_event="marketplace_operations_director_decision",
        hitl_persona="marketplace_operations_director",
        skills=("seller-exception-assessor",),
        command_type="seller.exception.resolve",
        allowed_actions=(
            "seller.exception.resolve",
            "request-correction",
            "suppress-offer",
            "escalate-partner",
        ),
        success_event="seller.exception.resolved",
        mutation_family="seller-offer",
        case_id="fashion-marketplace-seller-exception",
    ),
    "returns-disposition": FashionProcessProfile(
        workflow_type="returns-disposition",
        display_name="Returns Disposition",
        kind="supporting",
        function="customer-returns",
        workflow_id_prefix="FRD",
        sensor_id="sensor:return_inspected",
        objective_type="disposition_return",
        orchestrator_name="ReturnsDispositionOrchestrator",
        phases=_phases(
            ("Inspect Returned Item", "deterministic"),
            ("Assess Disposition Options", "agent"),
            ("Approve Disposition Exception", "hitl"),
            ("Execute Disposition", "deterministic"),
            ("Verify Recovery Outcome", "deterministic"),
        ),
        hitl_event="returns_operations_manager_decision",
        hitl_persona="returns_operations_manager",
        skills=("returns-disposition-advisor",),
        command_type="return.disposition",
        allowed_actions=(
            "return.disposition",
            "restock",
            "refurbish",
            "return-to-vendor",
            "recycle",
            "reject",
        ),
        success_event="return.disposition.completed",
        mutation_family="return",
        case_id="fashion-returns-disposition",
    ),
}
