"""agent_fleet_travel_preapproval_policy_fit_check — invokes the
fleet-travel-preapproval-policy-fit-checker skill via the GHCP SDK.

Pass *only* the policy-fit-checker skill directory to `skill_directories`
so multiple loaded skills don't fight over the output schema. Tools are
SDK-native (`@define_tool`), registered via `tools=[...]`, and called
autonomously by the model per the skill's `allowed-tools` frontmatter.
No prompt-stuffing.
"""
from __future__ import annotations

from api.server.mcp_tools.concur_travel_policy import concur_travel_policy_get_policy_tool
from api.server.mcp_tools.concur_travel_search import concur_travel_search_search_options_tool
from api.server.mcp_tools.delegated_authority import delegated_authority_resolve_approver_tool

from ._wrapper import SKILLS_DIR, run_agent_session

_SKILL_DIR = SKILLS_DIR / "fleet-travel-preapproval-policy-fit-checker"


async def execute(input: dict) -> dict:
    workflow_id = input.get("workflow_id")
    trip = input.get("trip") or {}
    employee_lookup = input.get("employee_lookup") or {}
    prompt = (
        f"Determine policy fit and cost band for the proposed trip below.\n\n"
        f"Trip: origin={trip.get('origin')!r}, destination={trip.get('destination')!r}, "
        f"depart={trip.get('depart_date')!r}, return={trip.get('return_date')!r}, "
        f"business_reason={trip.get('business_reason')!r}.\n"
        f"Employee context: grade={employee_lookup.get('grade')!r}, "
        f"home_market={employee_lookup.get('home_market')!r}, "
        f"agency={employee_lookup.get('agency')!r}.\n\n"
        f"Use `concur_travel_policy_get_policy(grade, market)` to load the "
        f"applicable policy slice. Use `concur_travel_search_search_options"
        f"(origin, destination, depart_date, return_date)` to load booking "
        f"options. Reason about policy fit and cost band per your skill spec. "
        f"Then call `delegated_authority_resolve_approver(action=\"travel_preapproval\", "
        f"category=<\"international\" if origin and destination differ in country, "
        f"else \"domestic\">, value=<cheapest_total_usd>)` to identify the "
        f"matrix-resolved approver and surface it as `resolved_approver`. "
        f"Return exactly the JSON object specified in your skill instructions "
        f"— no prose, no markdown."
    )
    result = await run_agent_session(
        prompt=prompt,
        tools=[
            concur_travel_policy_get_policy_tool,
            concur_travel_search_search_options_tool,
            delegated_authority_resolve_approver_tool,
        ],
        skill_dir=_SKILL_DIR,
        skill_label="fleet-travel-preapproval-policy-fit-checker",
        workflow_id=workflow_id,
    )
    return {"policy_fit_check": result}
