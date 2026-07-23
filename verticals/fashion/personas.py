from __future__ import annotations

from api.shared.persona_contracts import Persona


def _persona(role: str, label: str, event: str, colour: str) -> Persona:
    return Persona(
        role=role,
        archetype="approver",
        scope_function="commercial",
        workflow_label=label,
        external_event_default=event,
        default_authority_band="policy-bound",
        uses_authority_mcp=True,
        description=f"{label}; reviews evidenced retail exceptions.",
        display_color=colour,
    )


FASHION_PERSONAS = {
    "merchandising_director": _persona(
        "merchandising_director",
        "Merchandising Director",
        "merchandising_director_decision",
        "#be123c",
    ),
    "inventory_allocation_manager": _persona(
        "inventory_allocation_manager",
        "Inventory Allocation Manager",
        "inventory_allocation_manager_decision",
        "#e11d48",
    ),
    "supply_chain_director": _persona(
        "supply_chain_director",
        "Supply Chain Director",
        "supply_chain_director_decision",
        "#0369a1",
    ),
    "fulfilment_manager": _persona(
        "fulfilment_manager",
        "Fulfilment Manager",
        "fulfilment_manager_decision",
        "#0284c7",
    ),
    "marketplace_operations_director": _persona(
        "marketplace_operations_director",
        "Marketplace Operations Director",
        "marketplace_operations_director_decision",
        "#7c3aed",
    ),
    "returns_operations_manager": _persona(
        "returns_operations_manager",
        "Returns Operations Manager",
        "returns_operations_manager_decision",
        "#0f766e",
    ),
}

