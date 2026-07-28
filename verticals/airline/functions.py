from __future__ import annotations

from api.shared.function_contracts import Function, PersonaTree


WORKFLOW_TYPE = "integrated-hub-disruption-recovery"

AIRLINE_FUNCTIONS: dict[str, Function] = {
    "operations-control": Function(
        name="operations-control",
        display="Operations Control",
        operator_surface="operations-control",
        owns_domains=(WORKFLOW_TYPE,),
        ambient_agents=(),
        kpis=(),
        persona_hierarchy=PersonaTree(role="duty_operations_manager"),
    ),
}
