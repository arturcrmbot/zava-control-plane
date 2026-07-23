from verticals._helpers import lazy_projection
from verticals.fashion.domains import FASHION_DOMAINS


FASHION_PROJECTIONS = {
    workflow_type: lazy_projection(
        "verticals.fashion.entity_projections.retail"
    )
    for workflow_type in FASHION_DOMAINS
}

