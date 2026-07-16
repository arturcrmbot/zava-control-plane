from dataclasses import replace

from api.shared.all_domains import DOMAINS


TELCO_WORKFLOW_TYPES = {
    "network-incident",
    "proactive-customer-care",
    "order-to-activate",
}
AGENCY_DOMAINS = {
    workflow_type: domain
    for workflow_type, domain in DOMAINS.items()
    if workflow_type not in TELCO_WORKFLOW_TYPES
}
AGENCY_DOMAINS["creative-campaign"] = replace(
    AGENCY_DOMAINS["creative-campaign"],
    skills=("brand-guardian",),
)
