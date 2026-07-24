"""agent_fleet_employee_onboarding_access_drafter — invokes the
fleet-employee-onboarding-access-drafter skill via the GHCP SDK.

Pass *only* the access-drafter skill directory to `skill_directories` so
multiple loaded skills don't fight over the output schema. Tools are
SDK-native (`@define_tool`), registered via `tools=[...]`, and called
autonomously by the model per the skill's `allowed-tools` frontmatter.
No prompt-stuffing.
"""
from __future__ import annotations

from api.server.mcp_tools.delegated_authority import delegated_authority_resolve_approver_tool
from api.server.mcp_tools.identity_provider import (
    identity_provider_list_role_templates_tool,
    identity_provider_get_role_template_tool,
    identity_provider_check_separation_of_duties_tool,
)

from ._wrapper import SKILLS_DIR, run_agent_session

_SKILL_DIR = SKILLS_DIR / "fleet-employee-onboarding-access-drafter"


async def execute(input: dict) -> dict:
    workflow_id = input.get("workflow_id")
    joiner = input.get("joiner") or {}
    employee_lookup = input.get("employee_lookup") or {}
    prompt = (
        f"Draft the day-1 RBAC bundle for the new joiner below.\n\n"
        f"Joiner: employee_id={joiner.get('employee_id')!r}, "
        f"department={joiner.get('department')!r}, "
        f"buddy_id={joiner.get('buddy_id')!r}, "
        f"start_date={joiner.get('start_date')!r}.\n"
        f"Employee context: grade={employee_lookup.get('grade')!r}, "
        f"agency={employee_lookup.get('agency')!r}, "
        f"home_market={employee_lookup.get('home_market')!r}, "
        f"manager_id={employee_lookup.get('manager_id')!r}.\n\n"
        f"Use `identity_provider_list_role_templates(department, grade)` "
        f"to list candidate role templates and capture the "
        f"template_default_size for the joiner's grade. Use "
        f"`identity_provider_get_role_template(template_id)` once per "
        f"selected template to fetch its permissions. Use "
        f"`identity_provider_check_separation_of_duties(permissions)` "
        f"to screen the union for SoD conflicts. "
        f"Reason about which templates fit and which permissions to "
        f"include per your skill spec. "
        f"Then call `delegated_authority_resolve_approver(action=\"employee_onboarding_access\", "
        f"category=<\"external_contractor\" / \"elevated_access_request\" / \"standard_joiner\">)` "
        f"to identify the matrix-resolved approver and surface it as "
        f"`resolved_approver`. Return exactly the JSON object specified in your skill instructions "
        f"— no prose, no markdown."
    )
    result = await run_agent_session(
        prompt=prompt,
        tools=[
            identity_provider_list_role_templates_tool,
            identity_provider_get_role_template_tool,
            identity_provider_check_separation_of_duties_tool,
            delegated_authority_resolve_approver_tool,
        ],
        skill_dir=_SKILL_DIR,
        skill_label="fleet-employee-onboarding-access-drafter",
        workflow_id=workflow_id,
        instance_id=input.get("instance_id"),
    )
    return {"access_drafter": result}
