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
    "engineering_duty_manager": Persona(
        role="engineering_duty_manager",
        archetype="approver",
        scope_function="it",
        workflow_label="Engineering Duty Manager",
        external_event_default="engineering_duty_manager_decision",
        default_authority_band="synthetic-up-to-GBP-200000",
        uses_authority_mcp=True,
        description=(
            "Owns the AOG engineering recovery decision for the synthetic "
            "grounded aircraft. Approves within the engineering authority matrix; "
            "does not certify, defer defects, or release aircraft."
        ),
        display_color="#16a34a",
    ),
    "network_operations_director": Persona(
        role="network_operations_director",
        archetype="approver",
        scope_function="commercial",
        workflow_label="Network Operations Director",
        external_event_default="network_operations_director_decision",
        default_authority_band="synthetic-up-to-GBP-300000",
        uses_authority_mcp=True,
        description=(
            "Owns the preemptive schedule resilience adjustment decision for the "
            "synthetic network operation. Approves only within the commercial "
            "authority matrix; safety, legality, slot, and crew rules are never "
            "waived. This persona operates on synthetic data only."
        ),
        display_color="#7c3aed",
    ),
}
