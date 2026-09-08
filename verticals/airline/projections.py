from verticals._helpers import lazy_projection
from verticals.airline.aog_constants import AOG_WORKFLOW_TYPE
from verticals.airline.process_profiles import WORKFLOW_TYPE
from verticals.airline.schedule_constants import SCHED_WORKFLOW_TYPE


AIRLINE_PROJECTIONS = {
    WORKFLOW_TYPE: lazy_projection("verticals.airline.entity_projections.operations"),
    AOG_WORKFLOW_TYPE: lazy_projection("verticals.airline.entity_projections.aog"),
    SCHED_WORKFLOW_TYPE: lazy_projection("verticals.airline.entity_projections.schedule"),
}
