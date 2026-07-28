from __future__ import annotations

from api.shared.persona_contracts import Persona


AIRLINE_PERSONAS: dict[str, Persona] = {
    "duty_operations_manager": Persona(
        role="duty_operations_manager",
        archetype="approver",
        scope_function="commercial",
        workflow_label="Duty Operations Manager",
        external_event_default="duty_operations_manager_decision",
        default_authority_band="synthetic-up-to-GBP-150000",
        uses_authority_mcp=True,
        description=(
            "Owns the material integrated recovery decision for the synthetic "
            "hub operation."
        ),
        display_color="#2563eb",
    ),
}
