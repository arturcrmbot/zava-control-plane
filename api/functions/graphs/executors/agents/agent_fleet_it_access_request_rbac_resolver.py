"""agent_fleet_it_access_request_rbac_resolver — invokes the
fleet-it-access-request-rbac-resolver skill via the GHCP SDK.

Pass *only* the rbac-resolver skill directory to `skill_directories` so
multiple loaded skills don't fight over the output schema. Tools are
SDK-native (`@define_tool`), registered via `tools=[...]`, and called
autonomously by the model per the skill's `allowed-tools` frontmatter.
No prompt-stuffing.
"""
from __future__ import annotations

from api.server.mcp_tools.identity_provider import (
    identity_provider_list_role_templates_tool,
    identity_provider_get_role_template_tool,
    identity_provider_check_separation_of_duties_tool,
)

from ._wrapper import SKILLS_DIR, run_agent_session

_SKILL_DIR = SKILLS_DIR / "fleet-it-access-request-rbac-resolver"


async def execute(input: dict) -> dict:
    workflow_id = input.get("workflow_id")
    request = input.get("request") or {}
    employee_lookup = input.get("employee_lookup") or {}
    prompt = (
        f"Resolve the requested IT access bundle below into a concrete "
        f"set of role templates and screen the union for SoD conflicts.\n\n"
        f"Request: employee_id={request.get('employee_id')!r}, "
        f"department={request.get('department')!r}, "
        f"requested_role_templates={request.get('requested_role_templates')!r}, "
        f"business_justification={request.get('business_justification')!r}.\n"
        f"Employee context: grade={employee_lookup.get('grade')!r}, "
        f"agency={employee_lookup.get('agency')!r}, "
        f"home_market={employee_lookup.get('home_market')!r}, "
        f"manager_id={employee_lookup.get('manager_id')!r}.\n\n"
        f"Use `identity_provider_list_role_templates(department, grade)` to "
        f"discover the grade-band default templates and capture the "
        f"template_default_size. Use `identity_provider_get_role_template"
        f"(template_id)` once per requested template AND once per default "
        f"template to fetch its permissions. Use `identity_provider_check"
        f"_separation_of_duties(permissions)` to screen the union of all "
        f"permissions (requested ∪ existing grade-band defaults) for SoD "
        f"conflict pairs. "
        f"Reason about which requested templates resolve cleanly and which "
        f"introduce conflicts per your skill spec. "
        f"Return exactly the JSON object specified in your skill instructions "
        f"— no prose, no markdown."
    )
    result = await run_agent_session(
        prompt=prompt,
        tools=[
            identity_provider_list_role_templates_tool,
            identity_provider_get_role_template_tool,
            identity_provider_check_separation_of_duties_tool,
        ],
        skill_dir=_SKILL_DIR,
        skill_label="fleet-it-access-request-rbac-resolver",
        workflow_id=workflow_id,
        instance_id=input.get("instance_id"),
    )
    return {"rbac_resolver": result}
