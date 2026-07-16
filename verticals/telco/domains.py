from api.shared.all_domains import DOMAINS


TELCO_WORKFLOW_TYPES = (
    "network-incident",
    "proactive-customer-care",
    "order-to-activate",
)
TELCO_DOMAINS = {
    workflow_type: DOMAINS[workflow_type]
    for workflow_type in TELCO_WORKFLOW_TYPES
}
