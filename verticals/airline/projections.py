from verticals._helpers import lazy_projection
from verticals.airline.process_profiles import WORKFLOW_TYPE


AIRLINE_PROJECTIONS = {WORKFLOW_TYPE: lazy_projection("verticals.airline.entity_projections.operations")}
