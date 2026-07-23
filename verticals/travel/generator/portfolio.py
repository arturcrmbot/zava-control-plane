"""The Travel vertical's eight-process portfolio: one declarative source.

This is pure data -- no rendering, no I/O. Every other Task 4 generator
template (`pack_templates.py`, `skill_templates.py`, `process_templates.py`,
`durable_templates.py`, `mcp_templates.py`) imports `PROCESS_SPECS`,
`FUNCTION_SPECS`, `AUTHORITY_SPECS` and `AGENT_SPECS` from here rather than
repeating any process/role/bound literal, so the eight-process portfolio,
the six organisation functions, the fourteen-row authority matrix and the
per-process machine agents are each defined exactly once and stay
consistent across every generated file (`domains.py`, `functions.py`,
`authority.py`, `personas.py`, `agents.py`, the per-process
`domains/*.yaml` / `profiles/*.json` / `cases/*.json` / `skills/*/SKILL.md`
and the world routing table in `worlds/registration.py`).

Portfolio order below matches the task's own numbered list exactly (1..8);
every template that iterates `PROCESS_SPECS` inherits that same order.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PhaseSpec:
    name: str
    kind: str  # "deterministic" | "agent" | "hitl"


@dataclass(frozen=True)
class HitlGateSpec:
    gate_phase: str
    external_event: str
    persona: str
    wait_probability: float = 0.3


@dataclass(frozen=True)
class ProcessSpec:
    """One of the eight executable process contracts."""

    workflow_type: str
    display_name: str
    workflow_id_prefix: str
    orchestrator_name: str
    function: str
    sensor_id: str
    objective_type: str
    command_type: str
    success_event_types: tuple[str, ...]
    failure_event_types: tuple[str, ...]
    evaluation_timeout_minutes: float
    timeout_seconds: float
    authority_role: str
    phases: tuple[PhaseSpec, ...]
    skill_summary: str
    tools: tuple[str, ...]
    evaluation_type: str
    detector_fn: str
    evaluator_fn: str
    hero: bool = False
    hitl_gate: HitlGateSpec | None = None
    maturity: str = "graduated"
    # Task 6: the flight-disruption-recovery hero alone binds onto a real
    # Azure Durable Functions module (`verticals/travel/durable/functions.py`).
    # `None` for every other process keeps `registration.py`'s responder
    # pointed at the existing pure-simulator `orchestrator_name`.
    real_orchestrator_name: str | None = None
    real_external_event: str | None = None
    real_phases: tuple[str, ...] | None = None
    lifecycle_start_via_bridge: bool = False


@dataclass(frozen=True)
class FunctionSpec:
    """One of the six organisation functions grouping the portfolio."""

    name: str
    display: str
    operator_surface: str
    kpis: tuple[str, ...]
    head_role: str
    process_roles: tuple[str, ...]
    owns_workflow_types: tuple[str, ...]


@dataclass(frozen=True)
class AuthoritySpec:
    role: str
    spend_limit_gbp: float
    approval_actions: tuple[str, ...]
    delegate_to: str | None


@dataclass(frozen=True)
class AgentSpec:
    agent_id: str
    workflow_type: str
    allowed_tools: tuple[str, ...]
    max_value_gbp: float | None
    scope_function: str
    description: str


@dataclass(frozen=True)
class CaseSpec:
    """One executable reference scenario per process: a real setup recipe
    against a fresh `TravelWorld`, the exact detector target to pick out of
    that process's own detector function, and a real, authority-valid
    command payload. Every id named below is a genuine seeded (or
    disruption-derived) Travel actor id -- never a placeholder.

    `verticals.travel.generator.process_templates` renders this into a real
    Python `ReferenceCase` (setup/detect/build_command callables) for
    `worlds/processes.REFERENCE_CASES`, and
    `verticals.travel.generator.skill_templates` renders the exact same
    fields into `cases/<workflow_type>.json` -- one source, zero drift
    between the executable case and its documented mirror.
    """

    workflow_type: str
    run_until_minutes: float
    disruption: tuple[str, str] | None  # (kind, resource_id) or None
    detect_target_id: str
    command_payload: dict[str, object]
    expected_event_type: str


# ---------------------------------------------------------------------------
# 1. holiday-sales-booking
# ---------------------------------------------------------------------------
_HOLIDAY_SALES_BOOKING = ProcessSpec(
    workflow_type="holiday-sales-booking",
    display_name="Holiday Sales Booking",
    workflow_id_prefix="hsb",
    orchestrator_name="HolidaySalesBookingOrchestrator",
    function="commercial",
    sensor_id="sensor:quote_ready",
    objective_type="convert_holiday_demand",
    command_type="confirm_package_booking",
    success_event_types=("booking.paid",),
    failure_event_types=("command.rejected",),
    evaluation_timeout_minutes=60.0,
    timeout_seconds=120.0,
    authority_role="travel_adviser",
    phases=(
        PhaseSpec("detect_demand", "deterministic"),
        PhaseSpec("assess_quote", "agent"),
        PhaseSpec("confirm_and_pay", "deterministic"),
    ),
    skill_summary=(
        "Confirms a priced holiday-package quote as a paid booking: reserves "
        "flight, hotel allotment and transfer capacity and records payment "
        "in one bounded, authorised action."
    ),
    tools=("travel_operations_check_quote_offer", "travel_operations_reserve_package_capacity"),
    evaluation_type="booking_confirmed_and_paid",
    detector_fn="detect_quote_ready",
    evaluator_fn="evaluate_booking_confirmed_and_paid",
)

# ---------------------------------------------------------------------------
# 2. capacity-yield-management
# ---------------------------------------------------------------------------
_CAPACITY_YIELD_MANAGEMENT = ProcessSpec(
    workflow_type="capacity-yield-management",
    display_name="Capacity Yield Management",
    workflow_id_prefix="cym",
    orchestrator_name="CapacityYieldManagementOrchestrator",
    function="commercial",
    sensor_id="sensor:capacity_pressure",
    objective_type="protect_package_capacity",
    command_type="adjust_package_allotment",
    success_event_types=("hotel.allotment_adjusted",),
    failure_event_types=("command.rejected",),
    evaluation_timeout_minutes=60.0,
    timeout_seconds=120.0,
    authority_role="revenue_manager",
    phases=(
        PhaseSpec("detect_pressure", "deterministic"),
        PhaseSpec("plan_adjustment", "agent"),
        PhaseSpec("execute_adjustment", "deterministic"),
    ),
    skill_summary=(
        "Moves contracted room headroom between hotel allotments to relieve "
        "capacity pressure without ever breaching a supplier's contracted "
        "total."
    ),
    tools=("travel_operations_check_allotment_headroom", "travel_operations_move_allotment_rooms"),
    evaluation_type="capacity_within_bounds",
    detector_fn="detect_capacity_pressure",
    evaluator_fn="evaluate_capacity_within_bounds",
)

# ---------------------------------------------------------------------------
# 3. flight-disruption-recovery (hero)
# ---------------------------------------------------------------------------
_FLIGHT_DISRUPTION_RECOVERY = ProcessSpec(
    workflow_type="flight-disruption-recovery",
    display_name="Flight Disruption Recovery",
    workflow_id_prefix="fdr",
    orchestrator_name="FlightDisruptionRecoveryOrchestrator",
    function="operations-control",
    sensor_id="sensor:flight_cancellation_impact",
    objective_type="recover_cancelled_flight",
    command_type="reaccommodate_travellers",
    success_event_types=("booking.reaccommodated",),
    failure_event_types=("command.rejected",),
    evaluation_timeout_minutes=90.0,
    timeout_seconds=180.0,
    authority_role="operations_controller",
    phases=(
        PhaseSpec("detect_cancellation", "deterministic"),
        PhaseSpec("assess_impact", "agent"),
        PhaseSpec("escalate", "hitl"),
        PhaseSpec("reaccommodate", "deterministic"),
    ),
    skill_summary=(
        "Recovers travellers stranded by a cancelled flight: moves the "
        "affected booking's flight and transfer to a validated alternative, "
        "escalating material or high-cost cases to Head of Operations."
    ),
    tools=(
        "travel_operations_check_flight_disruption",
        "travel_operations_reaccommodate_booking",
    ),
    evaluation_type="travellers_reaccommodated",
    detector_fn="detect_flight_cancellation_impact",
    evaluator_fn="evaluate_travellers_reaccommodated",
    hero=True,
    hitl_gate=HitlGateSpec(
        gate_phase="escalate",
        external_event="reaccommodation_approval",
        persona="head_of_operations",
        wait_probability=0.3,
    ),
    # Task 6: bind the golden path onto the real Azure Durable Functions
    # orchestrator in `verticals/travel/durable/functions.py`, indexed by
    # the root `function_app.py`. `real_external_event` is deliberately a
    # distinct name from `hitl_gate.external_event` above: the latter stays
    # owned by the pre-existing pure-Python phase-plan simulator
    # (`verticals/travel/durable/orchestrators.py`), untouched by Task 6.
    real_orchestrator_name="TravelFlightDisruptionRecoveryOrchestrator",
    real_external_event="TravelRecoveryApproval",
    real_phases=(
        "detect",
        "assess_impact",
        "search_alternatives",
        "bound_options",
        "approve_material_change",
        "reaccommodate",
        "notify",
        "evaluate",
    ),
    lifecycle_start_via_bridge=True,
)

# ---------------------------------------------------------------------------
# 4. hotel-supplier-recovery (hero)
# ---------------------------------------------------------------------------
_HOTEL_SUPPLIER_RECOVERY = ProcessSpec(
    workflow_type="hotel-supplier-recovery",
    display_name="Hotel Supplier Recovery",
    workflow_id_prefix="hsr",
    orchestrator_name="HotelSupplierRecoveryOrchestrator",
    function="accommodation-supply",
    sensor_id="sensor:hotel_allotment_shortfall",
    objective_type="restore_hotel_accommodation",
    command_type="move_hotel_allotment",
    success_event_types=("hotel.allotment_moved",),
    failure_event_types=("command.rejected",),
    evaluation_timeout_minutes=90.0,
    timeout_seconds=180.0,
    authority_role="accommodation_manager",
    phases=(
        PhaseSpec("detect_shortfall", "deterministic"),
        PhaseSpec("assess_recovery", "agent"),
        PhaseSpec("plan_move", "agent"),
        PhaseSpec("execute_move", "deterministic"),
    ),
    skill_summary=(
        "Restores accommodation for a shortfall-hit hotel allotment by "
        "moving contracted rooms from a donor allotment with headroom, "
        "resolving the reported supplier shortfall."
    ),
    tools=(
        "travel_operations_check_allotment_headroom",
        "travel_operations_move_allotment_rooms",
    ),
    evaluation_type="accommodation_restored",
    detector_fn="detect_hotel_allotment_shortfall",
    evaluator_fn="evaluate_accommodation_restored",
    hero=True,
)

# ---------------------------------------------------------------------------
# 5. cancellation-refund
# ---------------------------------------------------------------------------
_CANCELLATION_REFUND = ProcessSpec(
    workflow_type="cancellation-refund",
    display_name="Cancellation Refund",
    workflow_id_prefix="cxr",
    orchestrator_name="CancellationRefundOrchestrator",
    function="customer-finance",
    sensor_id="sensor:customer_cancellation_accepted",
    objective_type="settle_cancelled_booking",
    command_type="cancel_and_refund_booking",
    success_event_types=("refund.issued",),
    failure_event_types=("command.rejected",),
    evaluation_timeout_minutes=60.0,
    timeout_seconds=120.0,
    authority_role="finance_operations_lead",
    phases=(
        PhaseSpec("detect_cancellation", "deterministic"),
        PhaseSpec("assess_refund", "agent"),
        PhaseSpec("settle", "deterministic"),
    ),
    skill_summary=(
        "Settles an accepted customer cancellation: releases the booking's "
        "flight, hotel and transfer capacity and issues the bounded refund."
    ),
    tools=("travel_operations_check_booking_status", "travel_operations_release_booking_capacity"),
    evaluation_type="refund_settled",
    detector_fn="detect_customer_cancellation_accepted",
    evaluator_fn="evaluate_refund_settled",
)

# ---------------------------------------------------------------------------
# 6. payment-exception
# ---------------------------------------------------------------------------
_PAYMENT_EXCEPTION = ProcessSpec(
    workflow_type="payment-exception",
    display_name="Payment Exception",
    workflow_id_prefix="pex",
    orchestrator_name="PaymentExceptionOrchestrator",
    function="customer-finance",
    sensor_id="sensor:balance_payment_exception",
    objective_type="preserve_payment_booking",
    command_type="resolve_payment_exception",
    success_event_types=("payment.succeeded", "booking.cancelled"),
    failure_event_types=("command.rejected",),
    evaluation_timeout_minutes=60.0,
    timeout_seconds=120.0,
    authority_role="payments_specialist",
    phases=(
        PhaseSpec("detect_exception", "deterministic"),
        PhaseSpec("assess_resolution", "agent"),
        PhaseSpec("resolve", "deterministic"),
    ),
    skill_summary=(
        "Resolves a failed balance payment by retrying it to complete the "
        "booking, or releasing the booking's inventory when retry is not "
        "viable."
    ),
    tools=("travel_operations_check_booking_status", "travel_operations_release_booking_capacity"),
    evaluation_type="payment_or_inventory_resolved",
    detector_fn="detect_balance_payment_exception",
    evaluator_fn="evaluate_payment_or_inventory_resolved",
)

# ---------------------------------------------------------------------------
# 7. destination-operations
# ---------------------------------------------------------------------------
_DESTINATION_OPERATIONS = ProcessSpec(
    workflow_type="destination-operations",
    display_name="Destination Operations",
    workflow_id_prefix="dop",
    orchestrator_name="DestinationOperationsOrchestrator",
    function="destination-operations",
    sensor_id="sensor:transfer_arrival_risk",
    objective_type="restore_destination_journey",
    command_type="dispatch_replacement_transfer",
    success_event_types=("transfer.replacement_dispatched",),
    failure_event_types=("command.rejected",),
    evaluation_timeout_minutes=45.0,
    timeout_seconds=90.0,
    authority_role="destination_operations_manager",
    phases=(
        PhaseSpec("detect_risk", "deterministic"),
        PhaseSpec("plan_replacement", "agent"),
        PhaseSpec("dispatch", "deterministic"),
    ),
    skill_summary=(
        "Dispatches a replacement resort transfer when an arrival is at "
        "risk, rebinding any travellers on the at-risk transfer to the "
        "replacement."
    ),
    tools=(
        "travel_operations_check_transfer_risk",
        "travel_operations_dispatch_replacement_transfer",
    ),
    evaluation_type="transfer_sla_restored",
    detector_fn="detect_transfer_arrival_risk",
    evaluator_fn="evaluate_transfer_sla_restored",
)

# ---------------------------------------------------------------------------
# 8. proactive-customer-care
# ---------------------------------------------------------------------------
_PROACTIVE_CUSTOMER_CARE = ProcessSpec(
    workflow_type="proactive-customer-care",
    display_name="Proactive Customer Care",
    workflow_id_prefix="pcc",
    orchestrator_name="ProactiveCustomerCareOrchestrator",
    function="customer-care",
    sensor_id="sensor:material_itinerary_change",
    objective_type="protect_disrupted_customer",
    command_type="issue_customer_care_action",
    success_event_types=("care.action_issued",),
    failure_event_types=("command.rejected",),
    evaluation_timeout_minutes=30.0,
    timeout_seconds=60.0,
    authority_role="customer_care_lead",
    phases=(
        PhaseSpec("detect_change", "deterministic"),
        PhaseSpec("assess_care", "agent"),
        PhaseSpec("issue_action", "deterministic"),
    ),
    skill_summary=(
        "Proactively notifies and, where warranted, extends a small bounded "
        "goodwill gesture to a customer whose itinerary materially changed."
    ),
    tools=("travel_operations_check_booking_status", "travel_operations_issue_care_action"),
    evaluation_type="customer_notified_and_supported",
    detector_fn="detect_material_itinerary_change",
    evaluator_fn="evaluate_customer_notified_and_supported",
)

PROCESS_SPECS: tuple[ProcessSpec, ...] = (
    _HOLIDAY_SALES_BOOKING,
    _CAPACITY_YIELD_MANAGEMENT,
    _FLIGHT_DISRUPTION_RECOVERY,
    _HOTEL_SUPPLIER_RECOVERY,
    _CANCELLATION_REFUND,
    _PAYMENT_EXCEPTION,
    _DESTINATION_OPERATIONS,
    _PROACTIVE_CUSTOMER_CARE,
)

PROCESS_BY_WORKFLOW_TYPE: dict[str, ProcessSpec] = {
    spec.workflow_type: spec for spec in PROCESS_SPECS
}

HERO_WORKFLOW_TYPES: tuple[str, ...] = tuple(
    spec.workflow_type for spec in PROCESS_SPECS if spec.hero
)


# ---------------------------------------------------------------------------
# Six organisation functions grouping the eight processes.
# ---------------------------------------------------------------------------
FUNCTION_SPECS: tuple[FunctionSpec, ...] = (
    FunctionSpec(
        name="commercial",
        display="Commercial",
        operator_surface="commercial-manager",
        kpis=("conversion_rate_pct", "package_margin_pct", "capacity_utilisation_pct"),
        head_role="head_of_commercial",
        process_roles=("travel_adviser", "revenue_manager"),
        owns_workflow_types=("holiday-sales-booking", "capacity-yield-management"),
    ),
    FunctionSpec(
        name="operations-control",
        display="Operations Control",
        operator_surface="operations-controller",
        kpis=("recovery_time_hours", "rebooking_success_rate_pct", "disruption_cost_gbp"),
        head_role="head_of_operations",
        process_roles=("operations_controller",),
        owns_workflow_types=("flight-disruption-recovery",),
    ),
    FunctionSpec(
        name="accommodation-supply",
        display="Accommodation & Supply",
        operator_surface="accommodation-manager",
        kpis=("allotment_utilisation_pct", "shortfall_resolution_time_hours", "supplier_slippage_rate"),
        head_role="head_of_accommodation",
        process_roles=("accommodation_manager",),
        owns_workflow_types=("hotel-supplier-recovery",),
    ),
    FunctionSpec(
        name="customer-finance",
        display="Customer Finance",
        operator_surface="finance-operations-lead",
        kpis=("refund_cycle_time_hours", "payment_exception_rate_pct", "revenue_at_risk_gbp"),
        head_role="head_of_customer_finance",
        process_roles=("finance_operations_lead", "payments_specialist"),
        owns_workflow_types=("cancellation-refund", "payment-exception"),
    ),
    FunctionSpec(
        name="destination-operations",
        display="Destination Operations",
        operator_surface="destination-operations-manager",
        kpis=("transfer_sla_pct", "on_ground_incident_rate"),
        head_role="head_of_destination_operations",
        process_roles=("destination_operations_manager",),
        owns_workflow_types=("destination-operations",),
    ),
    FunctionSpec(
        name="customer-care",
        display="Customer Care",
        operator_surface="customer-care-lead",
        kpis=("care_response_time_minutes", "goodwill_spend_gbp", "customer_satisfaction_score"),
        head_role="head_of_customer_care",
        process_roles=("customer_care_lead",),
        owns_workflow_types=("proactive-customer-care",),
    ),
)

FUNCTION_BY_NAME: dict[str, FunctionSpec] = {spec.name: spec for spec in FUNCTION_SPECS}


# ---------------------------------------------------------------------------
# Fourteen-row bounded GBP authority matrix: eight process roles plus their
# six escalation heads. Every bound below is cross-checked against the
# locked test fixtures in tests/api/world/actor/test_travel_process_commands.py
# (see module docstring of authority.py in pack_templates.py for the exact
# numeric derivation of each row).
#
# `operations_controller`'s own bound is this registry's single source of
# truth for flight-disruption-recovery auto-approval: it MUST stay equal to
# `verticals.travel.recovery.planner.AUTO_APPROVE_BOUND_GBP` (750.0, the
# recovery planner's own hand-authored constant in
# verticals/travel/generator/recovery_templates.py), since that planner
# decides `RecoveryOption.requires_approval` by comparing an option's
# incremental cost directly against that bound. Every other surface that
# gates the same decision -- the diagnostic phase-plan orchestrator's
# `_hitl_step`, this role's rendered profile/skill JSON, and the command
# handler's own authority guard -- all read this same registry row rather
# than duplicating the number, so changing it here is the only edit needed
# to move the bound everywhere at once.
# ---------------------------------------------------------------------------
AUTHORITY_SPECS: tuple[AuthoritySpec, ...] = (
    AuthoritySpec("travel_adviser", 2_000.0, ("confirm_package_booking",), "head_of_commercial"),
    AuthoritySpec("revenue_manager", 5_000.0, ("adjust_package_allotment",), "head_of_commercial"),
    AuthoritySpec("operations_controller", 750.0, ("reaccommodate_travellers",), "head_of_operations"),
    AuthoritySpec("accommodation_manager", 5_000.0, ("move_hotel_allotment",), "head_of_accommodation"),
    AuthoritySpec("finance_operations_lead", 2_000.0, ("cancel_and_refund_booking",), "head_of_customer_finance"),
    AuthoritySpec("payments_specialist", 5_000.0, ("resolve_payment_exception",), "head_of_customer_finance"),
    AuthoritySpec("destination_operations_manager", 1_000.0, ("dispatch_replacement_transfer",), "head_of_destination_operations"),
    AuthoritySpec("customer_care_lead", 500.0, ("issue_customer_care_action",), "head_of_customer_care"),
    AuthoritySpec("head_of_commercial", 50_000.0, ("confirm_package_booking", "adjust_package_allotment"), None),
    AuthoritySpec("head_of_operations", 2_000_000.0, ("reaccommodate_travellers",), None),
    AuthoritySpec("head_of_accommodation", 50_000.0, ("move_hotel_allotment",), None),
    AuthoritySpec("head_of_customer_finance", 50_000.0, ("cancel_and_refund_booking", "resolve_payment_exception"), None),
    AuthoritySpec("head_of_destination_operations", 50_000.0, ("dispatch_replacement_transfer",), None),
    AuthoritySpec("head_of_customer_care", 20_000.0, ("issue_customer_care_action",), None),
)

AUTHORITY_BY_ROLE: dict[str, AuthoritySpec] = {spec.role: spec for spec in AUTHORITY_SPECS}

ALL_PERSONA_ROLES: tuple[str, ...] = tuple(spec.role for spec in AUTHORITY_SPECS)


# ---------------------------------------------------------------------------
# One machine agent per process, referencing that process's own MCP tools.
# ---------------------------------------------------------------------------
AGENT_SPECS: tuple[AgentSpec, ...] = tuple(
    AgentSpec(
        agent_id=f"travel-{spec.workflow_id_prefix}-assistant",
        workflow_type=spec.workflow_type,
        allowed_tools=spec.tools,
        max_value_gbp=AUTHORITY_BY_ROLE[spec.authority_role].spend_limit_gbp,
        scope_function=spec.function,
        description=(
            f"Assistant agent for {spec.display_name}: proposes and drafts "
            f"the {spec.command_type} action within {spec.authority_role}'s "
            "bounded authority; every write is journalled and reversible."
        ),
    )
    for spec in PROCESS_SPECS
)


# ---------------------------------------------------------------------------
# Eight executable reference scenarios, one per process. Every id below is a
# real seeded (or disruption-derived) Travel actor id, empirically checked
# against `verticals.travel.worlds.reference_data`'s seed=42 world: donor and
# recipient allotments always keep enough slack/headroom for the planned
# room move, and every command's cost/value stays within its authorising
# role's spend_limit_gbp in AUTHORITY_SPECS above.
# ---------------------------------------------------------------------------
CASE_SPECS: tuple[CaseSpec, ...] = (
    CaseSpec(
        workflow_type="holiday-sales-booking",
        run_until_minutes=50.0,
        disruption=None,
        detect_target_id="QTE-6",
        command_payload={
            "quote_id": "QTE-6",
            "flight_id": "FLT-ZV102",
            "hotel_id": "HTL-BLU-TFS",
            "allotment_id": "ALT-BLU-TFS",
            "transfer_id": "TRF-3",
            "rooms": 1,
            "authorized_by": "travel_adviser",
        },
        expected_event_type="booking.paid",
    ),
    CaseSpec(
        workflow_type="capacity-yield-management",
        run_until_minutes=80.0,
        disruption=None,
        detect_target_id="ALT-SUN-PMI",
        command_payload={
            "from_allotment_id": "ALT-SUN-AYT",
            "to_allotment_id": "ALT-SUN-PMI",
            "rooms": 5,
            "estimated_value_gbp": 500.0,
            "authorized_by": "revenue_manager",
        },
        expected_event_type="hotel.allotment_adjusted",
    ),
    CaseSpec(
        workflow_type="flight-disruption-recovery",
        run_until_minutes=80.0,
        disruption=("flight_cancellation", "FLT-ZV101"),
        detect_target_id="FLT-ZV101",
        command_payload={
            "booking_id": "BKG-1",
            "disruption_id": "DIS-flight_cancellation-FLT-ZV101",
            "to_flight_id": "FLT-ZV204",
            "to_transfer_id": "TRF-2",
            "estimated_cost_gbp": 500.0,
            "authorized_by": "operations_controller",
        },
        expected_event_type="booking.reaccommodated",
    ),
    CaseSpec(
        workflow_type="hotel-supplier-recovery",
        run_until_minutes=80.0,
        disruption=("hotel_allotment_shortfall", "ALT-SUN-PMI"),
        detect_target_id="ALT-SUN-PMI",
        command_payload={
            "disruption_id": "DIS-hotel_allotment_shortfall-ALT-SUN-PMI",
            "from_allotment_id": "ALT-SUN-AYT",
            "to_allotment_id": "ALT-SUN-PMI",
            "rooms": 15,
            "estimated_value_gbp": 2000.0,
            "authorized_by": "accommodation_manager",
        },
        expected_event_type="hotel.allotment_moved",
    ),
    CaseSpec(
        workflow_type="cancellation-refund",
        run_until_minutes=80.0,
        disruption=("customer_cancellation_accepted", "BKG-2"),
        detect_target_id="BKG-2",
        command_payload={
            "disruption_id": "DIS-customer_cancellation_accepted-BKG-2",
            "booking_id": "BKG-2",
            "authorized_by": "finance_operations_lead",
        },
        expected_event_type="refund.issued",
    ),
    CaseSpec(
        workflow_type="payment-exception",
        run_until_minutes=60.0,
        disruption=("balance_payment_exception", "BKG-3"),
        detect_target_id="BKG-3",
        command_payload={
            "disruption_id": "DIS-balance_payment_exception-BKG-3",
            "booking_id": "BKG-3",
            "action": "retry",
            "authorized_by": "payments_specialist",
        },
        expected_event_type="payment.succeeded",
    ),
    CaseSpec(
        workflow_type="destination-operations",
        run_until_minutes=45.0,
        disruption=("transfer_arrival_risk", "TRF-1"),
        detect_target_id="TRF-1",
        command_payload={
            "disruption_id": "DIS-transfer_arrival_risk-TRF-1",
            "transfer_id": "TRF-1",
            "estimated_cost_gbp": 150.0,
            "authorized_by": "destination_operations_manager",
        },
        expected_event_type="transfer.replacement_dispatched",
    ),
    CaseSpec(
        workflow_type="proactive-customer-care",
        run_until_minutes=80.0,
        disruption=("material_itinerary_change", "BKG-1"),
        detect_target_id="BKG-1",
        command_payload={
            "disruption_id": "DIS-material_itinerary_change-BKG-1",
            "booking_id": "BKG-1",
            "kind": "goodwill_gesture",
            "amount_gbp": 50.0,
            "message": "We are sorry for the disruption to your holiday.",
            "authorized_by": "customer_care_lead",
        },
        expected_event_type="care.action_issued",
    ),
)

CASE_BY_WORKFLOW_TYPE: dict[str, CaseSpec] = {spec.workflow_type: spec for spec in CASE_SPECS}
