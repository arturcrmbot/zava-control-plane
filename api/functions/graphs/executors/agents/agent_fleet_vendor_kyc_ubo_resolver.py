"""agent_fleet_vendor_kyc_ubo_resolver — invokes the
fleet-vendor-kyc-ubo-resolver skill via the GHCP SDK.

Pass *only* the ubo-resolver skill directory to `skill_directories` so
multiple loaded skills don't fight over the output schema. Tools are
SDK-native (`@define_tool`), registered via `tools=[...]`, and called
autonomously by the model per the skill's `allowed-tools` frontmatter.
No prompt-stuffing.
"""
from __future__ import annotations

from api.server.mcp_tools.vendor_registry import vendor_registry_list_ubos_tool
from api.server.mcp_tools.sanctions_api import sanctions_api_screen_entity_tool
from api.server.mcp_tools.adverse_media import adverse_media_search_tool

from ._wrapper import SKILLS_DIR, run_agent_session

_SKILL_DIR = SKILLS_DIR / "fleet-vendor-kyc-ubo-resolver"


async def execute(input: dict) -> dict:
    workflow_id = input.get("workflow_id")
    vendor_intake = input.get("vendor_intake") or {}
    kyc_diligence = input.get("kyc_diligence") or {}
    prompt = (
        f"Enumerate ultimate beneficial owners and screen them.\n\n"
        f"Vendor intake: vendor_name={vendor_intake.get('vendor_name')!r}, "
        f"country_of_incorporation={vendor_intake.get('country_of_incorporation')!r}.\n"
        f"KYC diligence: registry_id={kyc_diligence.get('registry_id')!r}.\n\n"
        f"Use `vendor_registry_list_ubos(registry_id)` to enumerate the "
        f"ultimate beneficial owners. Use `sanctions_api_screen_entity"
        f"(name, country)` once per UBO to screen each one. Sort UBOs by "
        f"ownership_pct descending; for the top three, call "
        f"`adverse_media_search(name, country)` to run the adverse-media "
        f"sweep.\n"
        f"Reason about UBO sanctions exposure and adverse-media exposure "
        f"per your skill spec. Return exactly the JSON object specified "
        f"in your skill instructions — no prose, no markdown."
    )
    result = await run_agent_session(
        prompt=prompt,
        tools=[
            vendor_registry_list_ubos_tool,
            sanctions_api_screen_entity_tool,
            adverse_media_search_tool,
        ],
        skill_dir=_SKILL_DIR,
        skill_label="fleet-vendor-kyc-ubo-resolver",
        workflow_id=workflow_id,
        instance_id=input.get("instance_id"),
    )
    return {"ubo_resolver": result}
