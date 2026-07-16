from api.shared.functions import Function, PersonaTree


TELCO_FUNCTIONS = {
    "network-operations": Function(
        name="network-operations",
        display="Network Operations",
        operator_surface="network-operations",
        owns_domains=("network-incident", "order-to-activate"),
        ambient_agents=(),
        kpis=("availability-pct", "mttr", "activation-time"),
        persona_hierarchy=PersonaTree(role="delivery_lead"),
    ),
    "customer-success": Function(
        name="customer-success",
        display="Customer Success",
        operator_surface="customer-success",
        owns_domains=("proactive-customer-care",),
        ambient_agents=(),
        kpis=("nps", "proactive-resolution-pct", "credit-cost"),
        persona_hierarchy=PersonaTree(
            role="cs_director",
            manages=(
                PersonaTree(
                    role="cs_account_director",
                    manages=(
                        PersonaTree(
                            role="cs_manager",
                            manages=(PersonaTree(role="cs_specialist"),),
                        ),
                    ),
                ),
            ),
        ),
    ),
}
