from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable

from api.server.world.model import SimulationCommand, SimulationEvent
from verticals.fashion.process_profiles import FASHION_PROCESS_PROFILES
from verticals.fashion.reference_cases import process_case_view


PROFILE_BY_COMMAND = {
    profile.command_type: profile
    for profile in FASHION_PROCESS_PROFILES.values()
    if profile.workflow_type != "inventory-rebalancing"
}


# --- entity resolution -----------------------------------------------------


def _resolve_reservation(scenario: Any, subjects: tuple[str, ...]):
    location_id, sku_id = subjects[0], subjects[1]
    return scenario.reservations.get(f"RES-{location_id}-{sku_id}")


def _resolve_promotion(scenario: Any, subjects: tuple[str, ...]):
    return scenario.promotions.get(subjects[0])


def _resolve_markdown(scenario: Any, subjects: tuple[str, ...]):
    style_id, location_id = subjects[0], subjects[1]
    return scenario.markdown_recommendations.get(
        f"MREC-{style_id}-{location_id}"
    )


def _resolve_delivery(scenario: Any, subjects: tuple[str, ...]):
    supplier_id, style_id = subjects[0], subjects[1]
    return scenario.deliveries.get(f"DEL-{supplier_id}-{style_id}")


def _resolve_order(scenario: Any, subjects: tuple[str, ...]):
    return scenario.orders.get(subjects[0])


def _resolve_seller_offer(scenario: Any, subjects: tuple[str, ...]):
    seller_id, offer_id = subjects[0], subjects[1]
    offer = scenario.seller_offers.get(offer_id)
    if offer is None or offer.seller_id != seller_id:
        return None
    return offer


def _resolve_return(scenario: Any, subjects: tuple[str, ...]):
    return scenario.returns.get(subjects[0])


ENTITY_RESOLVERS: dict[str, Callable[[Any, tuple[str, ...]], Any]] = {
    "demand-spike-response": _resolve_reservation,
    "promotion-readiness": _resolve_promotion,
    "markdown-governance": _resolve_markdown,
    "supplier-delay-recovery": _resolve_delivery,
    "fulfilment-exception-resolution": _resolve_order,
    "marketplace-seller-exception": _resolve_seller_offer,
    "returns-disposition": _resolve_return,
}


def resolve_case_entity(
    scenario: Any,
    workflow_type: str,
    subjects: tuple[str, ...],
):
    resolver = ENTITY_RESOLVERS.get(workflow_type)
    subjects = tuple(subjects)
    if resolver is None or len(subjects) < 2:
        return None
    try:
        return resolver(scenario, subjects)
    except IndexError:
        return None


# --- typed, idempotent mutations -------------------------------------------


def _mutate_reservation(scenario, case, command, entity, action) -> str:
    if action != "no-action":
        entity.reserved_units += 20
    entity.status = action
    entity.version += 1
    return "allocation.reserved"


def _mutate_promotion(scenario, case, command, entity, action) -> str:
    if action in {"ready-channel", "promotion.prepare"}:
        entity.stock_ready = True
        entity.content_ready = True
        entity.channels_ready = ("store", "ecommerce")
        entity.status = "ready"
    else:
        entity.status = action
    entity.version += 1
    return "promotion.channel.readied"


def _mutate_markdown(scenario, case, command, entity, action) -> str:
    if action in {"recommend-markdown", "markdown.recommend"}:
        entity.recommendation = "markdown"
        entity.status = "recommended"
    else:
        entity.recommendation = "hold"
        entity.status = "held"
    entity.version += 1
    return "markdown.recommendation.recorded"


def _mutate_delivery(scenario, case, command, entity, action) -> str:
    entity.recovery_plan = action
    entity.status = "recovering"
    entity.version += 1
    return "delivery.recovery.planned"


def _mutate_order(scenario, case, command, entity, action) -> str:
    if action == "cancel":
        entity.status = "cancelled"
        entity.allocation_location_id = None
    else:
        entity.allocation_location_id = str(
            command.payload.get("alternate_location") or "DC-UK-01"
        )
        entity.status = action
    entity.version += 1
    return "order.reallocated"


def _mutate_seller_offer(scenario, case, command, entity, action) -> str:
    if action == "suppress-offer":
        entity.suppressed = True
        entity.status = "suppressed"
    elif action == "escalate-partner":
        entity.escalated = True
        entity.status = "escalated"
    else:
        entity.status = "correction-requested"
    entity.version += 1
    return "seller.offer.updated"


def _mutate_return(scenario, case, command, entity, action) -> str:
    entity.disposition = action
    entity.status = "dispositioned"
    if action in {"recycle", "reject"}:
        entity.recovery_value_gbp = 0.0
    entity.version += 1
    return "return.dispositioned"


ENTITY_MUTATORS: dict[str, Callable[..., str]] = {
    "demand-spike-response": _mutate_reservation,
    "promotion-readiness": _mutate_promotion,
    "markdown-governance": _mutate_markdown,
    "supplier-delay-recovery": _mutate_delivery,
    "fulfilment-exception-resolution": _mutate_order,
    "marketplace-seller-exception": _mutate_seller_offer,
    "returns-disposition": _mutate_return,
}


# --- validation ------------------------------------------------------------


def validate_reference_command(
    scenario: Any,
    command: SimulationCommand,
) -> str | None:
    profile = PROFILE_BY_COMMAND[command.type]
    case = scenario.process_cases.get(command.payload.get("case_id"))
    if case is None:
        return f"unknown process case: {command.payload.get('case_id')!r}"
    if case.workflow_type != profile.workflow_type:
        return f"case {case.id} does not belong to {profile.workflow_type}"
    if case.status != "open":
        return f"case {case.id} is not open"
    if command.payload.get("workflow_id") is None:
        return "workflow_id is required"
    action = command.payload.get("action")
    if action not in case.allowed_actions:
        return f"action {action!r} is not declared"
    if tuple(command.payload.get("subject_ids") or ()) != case.subject_ids:
        return "command subject_ids do not match case subjects"
    outputs = command.payload.get("skill_outputs")
    if not isinstance(outputs, dict) or not set(profile.skills) <= set(outputs):
        return "command is missing declared skill outputs"
    if command.payload.get("approval_decision") != "approve":
        return f"{profile.hitl_event} approval is required"
    entity = resolve_case_entity(
        scenario, profile.workflow_type, case.subject_ids
    )
    if entity is None:
        return (
            f"unknown {profile.mutation_family} entity for "
            f"subjects {list(case.subject_ids)!r}"
        )
    if (
        profile.workflow_type == "markdown-governance"
        and action in {"recommend-markdown", "markdown.recommend"}
        and not scenario._markdown_eligible(case.subject_ids[0])
    ):
        return (
            f"style {case.subject_ids[0]} is not markdown-eligible at "
            f"lifecycle {scenario.styles[case.subject_ids[0]].lifecycle!r}"
        )
    return None


def apply_reference_command(
    scenario: Any,
    command: SimulationCommand,
) -> SimulationEvent:
    profile = PROFILE_BY_COMMAND[command.type]
    case = scenario.process_cases[command.payload["case_id"]]
    accepted = scenario._record_command_accepted(command, target_id=case.id)
    action = str(command.payload["action"])
    entity = resolve_case_entity(
        scenario, profile.workflow_type, case.subject_ids
    )
    mutator = ENTITY_MUTATORS[profile.workflow_type]
    domain_event = mutator(scenario, case, command, entity, action)
    evaluation = {"status": "pass"}
    mutation = scenario.runtime.emit(
        domain_event,
        actor_id=case.id,
        target_id=entity.id,
        cause_event_id=accepted.event_id,
        trace_id=command.trace_id,
        payload={
            "workflow_type": profile.workflow_type,
            "action": action,
            "entity": asdict(entity),
        },
    )
    case.status = "completed"
    case.outcome = {
        "action": action,
        "command_type": profile.command_type,
        "mutation_family": profile.mutation_family,
        "subject_ids": list(case.subject_ids),
        "source_mode": "world-entity",
        "entity_id": entity.id,
        "entity": asdict(entity),
        "domain_event": domain_event,
        "evaluation": evaluation,
    }
    scenario.workflow_state[profile.workflow_type] = {
        "status": "completed",
        "action": action,
        "case_id": case.id,
        "entity_id": entity.id,
    }
    scenario.runtime.emit(
        profile.success_event,
        actor_id=case.id,
        target_id=entity.id,
        cause_event_id=mutation.event_id,
        trace_id=command.trace_id,
        payload={
            "case": process_case_view(case),
            "command_id": command.command_id,
            "mutation_family": profile.mutation_family,
        },
    )
    scenario.runtime.emit(
        "evaluation.completed",
        actor_id=case.id,
        cause_event_id=mutation.event_id,
        trace_id=command.trace_id,
        payload={
            "workflow_type": profile.workflow_type,
            "status": "pass",
        },
    )
    return accepted
