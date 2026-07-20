from __future__ import annotations

from api.shared.persona_contracts import Persona


def _persona(
    role: str,
    label: str,
    event: str,
    description: str,
    color: str,
) -> Persona:
    return Persona(
        role=role,
        archetype="approver",
        scope_function="commercial",
        workflow_label=label,
        external_event_default=event,
        uses_authority_mcp=True,
        description=description,
        display_color=color,
    )


FASHION_PERSONAS = {
    "merchandising_director": _persona(
        "merchandising_director",
        "Merchandising - director",
        "merchandising_director_decision",
        "Owns exceptional inventory and every markdown decision.",
        "#ec4899",
    ),
    "inventory_allocation_manager": _persona(
        "inventory_allocation_manager",
        "Merchandising - allocation",
        "inventory_allocation_manager_decision",
        "Reviews routine allocation and promotion readiness exceptions.",
        "#f472b6",
    ),
    "supply_chain_director": _persona(
        "supply_chain_director",
        "Supply Chain - director",
        "supply_chain_director_decision",
        "Owns expedite, supplier, and cross-border exceptions.",
        "#8b5cf6",
    ),
    "fulfilment_manager": _persona(
        "fulfilment_manager",
        "Fulfilment - manager",
        "fulfilment_manager_decision",
        "Owns order and stock-movement execution exceptions.",
        "#a78bfa",
    ),
    "marketplace_operations_director": _persona(
        "marketplace_operations_director",
        "Marketplace Operations - director",
        "marketplace_operations_director_decision",
        "Owns seller suppression and partner escalation.",
        "#0ea5e9",
    ),
    "returns_operations_manager": _persona(
        "returns_operations_manager",
        "Returns Operations - manager",
        "returns_operations_manager_decision",
        "Owns high-value and non-standard returns dispositions.",
        "#14b8a6",
    ),
}

