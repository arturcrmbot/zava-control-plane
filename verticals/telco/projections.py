from verticals._helpers import lazy_projection
from verticals.telco.domains import TELCO_DOMAINS


TELCO_PROJECTIONS = {
    workflow_type: lazy_projection(
        "verticals.telco.entity_projections."
        + workflow_type.replace("-", "_")
    )
    for workflow_type in TELCO_DOMAINS
}
