from api.shared.authority import ALL_AUTHORITY


TELCO_AUTHORITY_ROLES = (
    "cs_specialist",
    "cs_manager",
    "cs_account_director",
    "cs_director",
    "delivery_lead",
)
TELCO_AUTHORITY = {
    role: ALL_AUTHORITY[role]
    for role in TELCO_AUTHORITY_ROLES
}
