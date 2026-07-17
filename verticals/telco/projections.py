from verticals._helpers import lazy_projection
from verticals.telco.domains import TELCO_DOMAINS


_DEDICATED_PROJECTIONS = {
    "network-incident",
    "proactive-customer-care",
    "order-to-activate",
}

TELCO_PROJECTIONS = {
    workflow_type: lazy_projection(
        (
            "verticals.telco.entity_projections."
            + workflow_type.replace("-", "_")
        )
        if workflow_type in _DEDICATED_PROJECTIONS
        else "verticals.telco.entity_projections.cascade"
    )
    for workflow_type in TELCO_DOMAINS
}
