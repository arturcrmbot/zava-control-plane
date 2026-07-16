from api.shared.all_authority import AUTHORITY


TELCO_AUTHORITY_ROLES = (
    "cs_specialist",
    "cs_manager",
    "cs_account_director",
    "cs_director",
    "delivery_lead",
)
TELCO_AUTHORITY = {
    role: AUTHORITY[role]
    for role in TELCO_AUTHORITY_ROLES
}
