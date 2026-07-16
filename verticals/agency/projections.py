from verticals._helpers import lazy_projection
from verticals.agency.domains import AGENCY_DOMAINS


AGENCY_PROJECTIONS = {
    workflow_type: lazy_projection(
        "api.server.services.entity_projections."
        + workflow_type.replace("-", "_")
    )
    for workflow_type in AGENCY_DOMAINS
}
