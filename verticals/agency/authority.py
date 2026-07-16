from api.shared.authority import ALL_AUTHORITY


TELCO_ONLY_AUTHORITY = {
    "cs_specialist",
    "cs_manager",
    "cs_account_director",
    "cs_director",
}
AGENCY_AUTHORITY = {
    role: row
    for role, row in ALL_AUTHORITY.items()
    if role not in TELCO_ONLY_AUTHORITY
}
