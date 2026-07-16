from api.shared.agents import ALL_AGENTS


TELCO_AGENT_IDS = (
    "proactive-customer-care-entitlement",
    "proactive-customer-care-execution",
)
TELCO_AGENTS = {
    agent_id: ALL_AGENTS[agent_id]
    for agent_id in TELCO_AGENT_IDS
}
