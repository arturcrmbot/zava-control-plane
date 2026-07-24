"""agent_fleet_it_access_request_risk_assessor — invokes the
fleet-it-access-request-access-risk-assessor skill via the GHCP SDK.

Pass *only* the access-risk-assessor skill directory to `skill_directories`
so multiple loaded skills don't fight over the output schema. Tools are
SDK-native (`@define_tool`), registered via `tools=[...]`, and called
autonomously by the model per the skill's `allowed-tools` frontmatter.
No prompt-stuffing.
"""
from __future__ import annotations

from api.server.mcp_tools.delegated_authority import delegated_authority_resolve_approver_tool
from api.server.mcp_tools.employee_history import employee_history_tool
from api.server.mcp_tools.audit_query import audit_query_tool
from api.server.mcp_tools.identity_provider import (
    identity_provider_get_role_template_tool,
)

from ._wrapper import SKILLS_DIR, run_agent_session

_SKILL_DIR = SKILLS_DIR / "fleet-it-access-request-access-risk-assessor"


async def execute(input: dict) -> dict:
    workflow_id = input.get("workflow_id")
    request = input.get("request") or {}
    employee_lookup = input.get("employee_lookup") or {}
    rbac_resolver = input.get("rbac_resolver") or {}
    prompt = (
        f"Score the IT access request below as low / medium / high risk.\n\n"
        f"Request: employee_id={request.get('employee_id')!r}, "
        f"department={request.get('department')!r}, "
        f"requested_role_templates={request.get('requested_role_templates')!r}, "
        f"business_justification={request.get('business_justification')!r}.\n"
        f"Employee context: grade={employee_lookup.get('grade')!r}, "
        f"agency={employee_lookup.get('agency')!r}, "
        f"home_market={employee_lookup.get('home_market')!r}.\n"
        f"RBAC resolver verdict: verdict={rbac_resolver.get('verdict')!r}, "
        f"selected_templates={rbac_resolver.get('selected_templates')!r}, "
        f"sod_conflicts={rbac_resolver.get('sod_conflicts')!r}, "
        f"proposed_bundle_size={len(rbac_resolver.get('proposed_bundle') or [])!r}.\n\n"
        f"Use `employee_history_employee_history(employee_id, lookback_days=90)` "
        f"to load the requester's last-90-day breach history. Use "
        f"`audit_query_audit_query(workflow_id=None, limit=200)` to load the "
        f"recent grant / revocation volume across the audit ledger so you can "
        f"see how often the requested entitlements have been touched. Use "
        f"`identity_provider_get_role_template(template_id)` once per selected "
        f"template to recompute permission depth (count of high-sensitivity "
        f"permissions like `*.write`, `*.approve`, `secrets.*`). "
        f"Reason about per-role and overall risk per your skill spec. "
        f"Then call `delegated_authority_resolve_approver(action=\"it_access_grant\", "
        f"category=<\"privileged_role\" / \"broad_scope\" / \"elevated_role\" / \"standard_role\">)` "
        f"to identify the matrix-resolved approver and surface it as "
        f"`resolved_approver`. Return exactly the JSON object specified in your skill instructions "
        f"— no prose, no markdown."
    )
    result = await run_agent_session(
        prompt=prompt,
        tools=[
            employee_history_tool,
            audit_query_tool,
            identity_provider_get_role_template_tool,
            delegated_authority_resolve_approver_tool,
        ],
        skill_dir=_SKILL_DIR,
        skill_label="fleet-it-access-request-access-risk-assessor",
        workflow_id=workflow_id,
        instance_id=input.get("instance_id"),
    )
    return {"risk_assessor": result}
