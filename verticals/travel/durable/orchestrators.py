"""Travel: the eight distinct orchestrator functions (generated
by verticals.travel.generator.durable_templates).

Each orchestrator below runs its own process's real phase plan --
its real detector (`worlds.processes.DETECTORS`), a real bounded-
authority HITL check where the process has one, and its real
command handler (`actions.commands.COMMAND_HANDLERS`) -- through
the shared, framework-free `engine.run_phase_plan`. Task 6
binds/enhances the flight-disruption-recovery hero onto real Azure
Durable Functions triggers; every orchestrator here stays callable
as plain Python against any TravelWorld for diagnostic, pure-
command exercising (no `/processes/*/run` HTTP dependency).

Do not hand-edit -- change the generator template (or
verticals.travel.generator.portfolio) and regenerate via
`uv run python -m verticals.travel.generator`.
"""
from __future__ import annotations

from typing import Any

from api.server.world.model import SimulationCommand
from verticals.travel.actions.commands import COMMAND_HANDLERS
from verticals.travel.authority import TRAVEL_AUTHORITY
from verticals.travel.durable.engine import PhasePlanResult, PhaseStep, run_phase_plan
from verticals.travel.worlds.processes import DETECTORS

_COST_FIELDS: tuple[str, ...] = (
    "estimated_cost_gbp",
    "estimated_value_gbp",
    "amount_gbp",
)


def _cost_of(payload: dict[str, Any]) -> float:
    for field in _COST_FIELDS:
        if field in payload:
            return float(payload[field])
    return 0.0


def _command_id_of(payload: dict[str, Any], command_type: str) -> str:
    for field in ("booking_id", "quote_id", "transfer_id", "allotment_id", "to_allotment_id"):
        if field in payload:
            return f"CMD-{command_type}-{payload[field]}"
    return f"CMD-{command_type}-auto"


def _detect_step(workflow_type: str):
    def run(world: Any, context: dict[str, Any]) -> dict[str, Any]:
        events = DETECTORS[workflow_type](world)
        return {"detected_event_count": len(events)}

    return run


def _analyse_step(phase_name: str):
    def run(world: Any, context: dict[str, Any]) -> dict[str, Any]:
        payload = context.get("command_payload", {})
        return {
            "analysed_phase": phase_name,
            "analysed_field_count": len(payload),
            "estimated_cost_gbp": _cost_of(payload),
        }

    return run


def _hitl_step(authority_role: str):
    def run(world: Any, context: dict[str, Any]) -> dict[str, Any]:
        payload = context.get("command_payload", {})
        cost_gbp = _cost_of(payload)
        bound_gbp = TRAVEL_AUTHORITY[authority_role].spend_limit_gbp
        return {
            "wait": cost_gbp > bound_gbp,
            "cost_gbp": cost_gbp,
            "authority_bound_gbp": bound_gbp,
        }

    return run


def _execute_step(command_type: str, authority_role: str):
    def run(world: Any, context: dict[str, Any]) -> dict[str, Any]:
        payload = dict(context.get("command_payload", {}))
        command = SimulationCommand(
            command_id=_command_id_of(payload, command_type),
            trace_id=f"TRACE-{command_type}",
            issued_by=payload.get("authorized_by", authority_role),
            type=command_type,
            payload=payload,
        )
        event = COMMAND_HANDLERS[command_type](world, command)
        return {"event_type": event.type, "event_id": event.event_id}

    return run


def HolidaySalesBookingOrchestrator(
    world: Any,
    command_payload: dict[str, Any],
) -> PhasePlanResult:
    """Real phase-plan orchestrator for 'Holiday Sales Booking'.

    Phases: detect_demand, assess_quote, confirm_and_pay.
    Command: `confirm_package_booking`. Authority: `travel_adviser`.
    """
    steps: tuple[PhaseStep, ...] = (
        PhaseStep('detect_demand', 'deterministic', _detect_step('holiday-sales-booking')),
        PhaseStep('assess_quote', 'agent', _analyse_step('assess_quote')),
        PhaseStep('confirm_and_pay', 'deterministic', _execute_step('confirm_package_booking', 'travel_adviser')),
    )
    return run_phase_plan(world, 'holiday-sales-booking', steps, initial_context={"command_payload": command_payload})


def CapacityYieldManagementOrchestrator(
    world: Any,
    command_payload: dict[str, Any],
) -> PhasePlanResult:
    """Real phase-plan orchestrator for 'Capacity Yield Management'.

    Phases: detect_pressure, plan_adjustment, execute_adjustment.
    Command: `adjust_package_allotment`. Authority: `revenue_manager`.
    """
    steps: tuple[PhaseStep, ...] = (
        PhaseStep('detect_pressure', 'deterministic', _detect_step('capacity-yield-management')),
        PhaseStep('plan_adjustment', 'agent', _analyse_step('plan_adjustment')),
        PhaseStep('execute_adjustment', 'deterministic', _execute_step('adjust_package_allotment', 'revenue_manager')),
    )
    return run_phase_plan(world, 'capacity-yield-management', steps, initial_context={"command_payload": command_payload})


def FlightDisruptionRecoveryOrchestrator(
    world: Any,
    command_payload: dict[str, Any],
) -> PhasePlanResult:
    """Real phase-plan orchestrator for 'Flight Disruption Recovery'.

    Phases: detect_cancellation, assess_impact, escalate, reaccommodate.
    Command: `reaccommodate_travellers`. Authority: `operations_controller`.
    """
    steps: tuple[PhaseStep, ...] = (
        PhaseStep('detect_cancellation', 'deterministic', _detect_step('flight-disruption-recovery')),
        PhaseStep('assess_impact', 'agent', _analyse_step('assess_impact')),
        PhaseStep('escalate', 'hitl', _hitl_step('operations_controller')),
        PhaseStep('reaccommodate', 'deterministic', _execute_step('reaccommodate_travellers', 'operations_controller')),
    )
    return run_phase_plan(world, 'flight-disruption-recovery', steps, initial_context={"command_payload": command_payload})


def HotelSupplierRecoveryOrchestrator(
    world: Any,
    command_payload: dict[str, Any],
) -> PhasePlanResult:
    """Real phase-plan orchestrator for 'Hotel Supplier Recovery'.

    Phases: detect_shortfall, assess_recovery, plan_move, execute_move.
    Command: `move_hotel_allotment`. Authority: `accommodation_manager`.
    """
    steps: tuple[PhaseStep, ...] = (
        PhaseStep('detect_shortfall', 'deterministic', _detect_step('hotel-supplier-recovery')),
        PhaseStep('assess_recovery', 'agent', _analyse_step('assess_recovery')),
        PhaseStep('plan_move', 'agent', _analyse_step('plan_move')),
        PhaseStep('execute_move', 'deterministic', _execute_step('move_hotel_allotment', 'accommodation_manager')),
    )
    return run_phase_plan(world, 'hotel-supplier-recovery', steps, initial_context={"command_payload": command_payload})


def CancellationRefundOrchestrator(
    world: Any,
    command_payload: dict[str, Any],
) -> PhasePlanResult:
    """Real phase-plan orchestrator for 'Cancellation Refund'.

    Phases: detect_cancellation, assess_refund, settle.
    Command: `cancel_and_refund_booking`. Authority: `finance_operations_lead`.
    """
    steps: tuple[PhaseStep, ...] = (
        PhaseStep('detect_cancellation', 'deterministic', _detect_step('cancellation-refund')),
        PhaseStep('assess_refund', 'agent', _analyse_step('assess_refund')),
        PhaseStep('settle', 'deterministic', _execute_step('cancel_and_refund_booking', 'finance_operations_lead')),
    )
    return run_phase_plan(world, 'cancellation-refund', steps, initial_context={"command_payload": command_payload})


def PaymentExceptionOrchestrator(
    world: Any,
    command_payload: dict[str, Any],
) -> PhasePlanResult:
    """Real phase-plan orchestrator for 'Payment Exception'.

    Phases: detect_exception, assess_resolution, resolve.
    Command: `resolve_payment_exception`. Authority: `payments_specialist`.
    """
    steps: tuple[PhaseStep, ...] = (
        PhaseStep('detect_exception', 'deterministic', _detect_step('payment-exception')),
        PhaseStep('assess_resolution', 'agent', _analyse_step('assess_resolution')),
        PhaseStep('resolve', 'deterministic', _execute_step('resolve_payment_exception', 'payments_specialist')),
    )
    return run_phase_plan(world, 'payment-exception', steps, initial_context={"command_payload": command_payload})


def DestinationOperationsOrchestrator(
    world: Any,
    command_payload: dict[str, Any],
) -> PhasePlanResult:
    """Real phase-plan orchestrator for 'Destination Operations'.

    Phases: detect_risk, plan_replacement, dispatch.
    Command: `dispatch_replacement_transfer`. Authority: `destination_operations_manager`.
    """
    steps: tuple[PhaseStep, ...] = (
        PhaseStep('detect_risk', 'deterministic', _detect_step('destination-operations')),
        PhaseStep('plan_replacement', 'agent', _analyse_step('plan_replacement')),
        PhaseStep('dispatch', 'deterministic', _execute_step('dispatch_replacement_transfer', 'destination_operations_manager')),
    )
    return run_phase_plan(world, 'destination-operations', steps, initial_context={"command_payload": command_payload})


def ProactiveCustomerCareOrchestrator(
    world: Any,
    command_payload: dict[str, Any],
) -> PhasePlanResult:
    """Real phase-plan orchestrator for 'Proactive Customer Care'.

    Phases: detect_change, assess_care, issue_action.
    Command: `issue_customer_care_action`. Authority: `customer_care_lead`.
    """
    steps: tuple[PhaseStep, ...] = (
        PhaseStep('detect_change', 'deterministic', _detect_step('proactive-customer-care')),
        PhaseStep('assess_care', 'agent', _analyse_step('assess_care')),
        PhaseStep('issue_action', 'deterministic', _execute_step('issue_customer_care_action', 'customer_care_lead')),
    )
    return run_phase_plan(world, 'proactive-customer-care', steps, initial_context={"command_payload": command_payload})
