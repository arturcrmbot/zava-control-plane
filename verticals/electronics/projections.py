from verticals._helpers import lazy_projection
from verticals.electronics.domains import ELECTRONICS_DOMAINS


ELECTRONICS_PROJECTIONS = {
    workflow_type: lazy_projection(
        "verticals.electronics.entity_projections.retail"
    )
    for workflow_type in ELECTRONICS_DOMAINS
}

