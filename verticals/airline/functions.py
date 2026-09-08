from __future__ import annotations

from api.shared.function_contracts import Function, PersonaTree
from verticals.airline.aog_constants import AOG_WORKFLOW_TYPE
from verticals.airline.schedule_constants import SCHED_WORKFLOW_TYPE


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
    "engineering-maintenance": Function(
        name="engineering-maintenance",
        display="Engineering and Maintenance",
        operator_surface="engineering-maintenance",
        owns_domains=(AOG_WORKFLOW_TYPE,),
        ambient_agents=(),
        kpis=(),
        persona_hierarchy=PersonaTree(role="engineering_duty_manager"),
    ),
    "network-planning": Function(
        name="network-planning",
        display="Network Planning",
        operator_surface="network-planning",
        owns_domains=(SCHED_WORKFLOW_TYPE,),
        ambient_agents=(),
        kpis=(),
        persona_hierarchy=PersonaTree(role="network_operations_director"),
    ),
}
