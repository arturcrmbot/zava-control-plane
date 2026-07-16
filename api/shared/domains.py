from __future__ import annotations

from api.shared.all_domains import (
    Domain,
    HitlGate,
    Phase,
    PhaseKind,
    RegionOverlay,
    WakeHint,
)
from api.shared.vertical_loader import active_runtime

__all__ = [
    "DOMAINS",
    "Domain",
    "HitlGate",
    "Phase",
    "PhaseKind",
    "RegionOverlay",
    "WakeHint",
    "all_personae",
    "all_wake_hints",
    "by_prefix",
    "get",
    "live_domains",
    "resolve_external_event",
]


DOMAINS = active_runtime().pack.domains


def get(workflow_type: str) -> Domain | None:
    return DOMAINS.get(workflow_type)


def by_prefix(workflow_id: str) -> Domain | None:
    prefix = workflow_id.split("-", 1)[0] if "-" in workflow_id else workflow_id
    return next(
        (
            domain
            for domain in DOMAINS.values()
            if domain.workflow_id_prefix == prefix
        ),
        None,
    )


def resolve_external_event(
    workflow_type: str,
    current_phase: str,
) -> str | None:
    domain = DOMAINS.get(workflow_type)
    if domain is None:
        return None
    phase = current_phase.lower().replace(" ", "_")
    for gate in domain.hitl_gates:
        if gate.gate_phase.lower().replace(" ", "_") == phase:
            return gate.external_event
    return None


def all_wake_hints() -> set[str]:
    return {
        hint.event
        for domain in DOMAINS.values()
        for hint in domain.wake_hints
    }


def all_personae() -> set[str]:
    return {
        gate.persona
        for domain in DOMAINS.values()
        for gate in domain.hitl_gates
    }


def live_domains() -> list[Domain]:
    return [domain for domain in DOMAINS.values() if not domain.stub]
