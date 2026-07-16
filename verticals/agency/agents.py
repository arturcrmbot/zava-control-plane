from api.shared.agents import ALL_AGENTS


EXCLUDED_AGENT_IDS = {
    "proactive-customer-care-entitlement",
    "proactive-customer-care-execution",
    "reflector.entity_reflector",
}
AGENCY_AGENTS = {
    agent_id: agent
    for agent_id, agent in ALL_AGENTS.items()
    if agent_id not in EXCLUDED_AGENT_IDS
}
