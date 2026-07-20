from verticals._helpers import lazy_projection
from verticals.fashion.process_profiles import FASHION_PROCESS_PROFILES


FASHION_PROJECTIONS = {
    workflow_type: lazy_projection(
        "verticals.fashion.entity_projections.common"
    )
    for workflow_type in FASHION_PROCESS_PROFILES
}

