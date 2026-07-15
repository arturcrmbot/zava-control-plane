"""Static responder registry — objective type → Durable orchestrator.

The world bridge no longer selects a Durable responder by scenario branch. It
resolves the objective type (declared by the world-pack registration) to a
:class:`ResponderRegistration` here, which names the orchestrator to schedule,
the workflow type/prefix to tag it with, the owner function that claims the
objective (and must match the command's ``issued_by``), and the poll timeout.

One literal entry per objective type; no dynamic discovery.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResponderRegistration:
    objective_type: str
    orchestrator: str
    workflow_type: str
    prefix: str
    owner_function: str
    timeout_seconds: float
    # Payload key under which the world observation is nested on the canonical
    # Workflow (api.server.services.world_workflow_adapter). The per-domain
    # entity projection reads the observation from this key — for
    # network-incident it MUST be ``"incident"`` so
    # api/server/services/entity_projections/network_incident.py resolves the
    # incident site.
    observation_key: str = "observation"


# owner_function equals the command's ``issued_by`` (see the surge-staffing /
# network-incident decide activities) so the command gateway's claimed-issuer
# check passes end to end.
RESPONDERS: dict[str, ResponderRegistration] = {
    "support_capacity": ResponderRegistration(
        objective_type="support_capacity",
        orchestrator="SurgeStaffingOrchestrator",
        workflow_type="surge-staffing",
        prefix="surge",
        owner_function="surge_staffing",
        timeout_seconds=90.0,
        observation_key="observation",
    ),
    "network_service_recovery": ResponderRegistration(
        objective_type="network_service_recovery",
        orchestrator="NetworkIncidentOrchestrator",
        workflow_type="network-incident",
        prefix="incident",
        owner_function="network_incident",
        timeout_seconds=90.0,
        observation_key="incident",
    ),
}


def resolve_responder(objective_type: str) -> ResponderRegistration:
    """Return the responder for ``objective_type`` or raise ``ValueError``."""
    try:
        return RESPONDERS[objective_type]
    except KeyError:
        raise ValueError(
            f"no responder for objective type {objective_type!r}; "
            f"known types: {sorted(RESPONDERS)}"
        ) from None
