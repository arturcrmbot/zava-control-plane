from verticals._helpers import lazy_projection
from verticals.hospitality.domains import HOSPITALITY_DOMAINS


HOSPITALITY_PROJECTIONS = {
    workflow_type: lazy_projection(
        "verticals.hospitality.entity_projections.operations"
    )
    for workflow_type in HOSPITALITY_DOMAINS
}
