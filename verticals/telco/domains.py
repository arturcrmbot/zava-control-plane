from api.shared.domains import ALL_DOMAINS


TELCO_WORKFLOW_TYPES = (
    "network-incident",
    "proactive-customer-care",
    "order-to-activate",
)
TELCO_DOMAINS = {
    workflow_type: ALL_DOMAINS[workflow_type]
    for workflow_type in TELCO_WORKFLOW_TYPES
}
