"""agent_fleet_vendor_kyc_kyc_diligence — invokes the
fleet-vendor-kyc-kyc-diligence-checker skill via the GHCP SDK.

Pass *only* the kyc-diligence-checker skill directory to `skill_directories`
so multiple loaded skills don't fight over the output schema. Tools are
SDK-native (`@define_tool`), registered via `tools=[...]`, and called
autonomously by the model per the skill's `allowed-tools` frontmatter.
No prompt-stuffing.
"""
from __future__ import annotations

from api.server.mcp_tools.delegated_authority import delegated_authority_resolve_approver_tool
from api.server.mcp_tools.vendor_registry import (
    vendor_registry_lookup_vendor_tool,
    vendor_registry_list_filings_tool,
)
from api.server.mcp_tools.sanctions_api import sanctions_api_screen_entity_tool

from ._wrapper import SKILLS_DIR, run_agent_session

_SKILL_DIR = SKILLS_DIR / "fleet-vendor-kyc-kyc-diligence-checker"


async def execute(input: dict) -> dict:
    workflow_id = input.get("workflow_id")
    vendor_intake = input.get("vendor_intake") or {}
    prompt = (
        f"Run KYC diligence on the proposed vendor below.\n\n"
        f"Vendor intake: vendor_name={vendor_intake.get('vendor_name')!r}, "
        f"country_of_incorporation={vendor_intake.get('country_of_incorporation')!r}, "
        f"proposing_agency={vendor_intake.get('proposing_agency')!r}.\n\n"
        f"Use `vendor_registry_lookup_vendor(vendor_name, country)` to load "
        f"the registry record. Use `vendor_registry_list_filings(registry_id, "
        f"months=24)` to load the last 24 months of filings. Use "
        f"`sanctions_api_screen_entity(name, country)` once per country to "
        f"screen the legal entity for the country of incorporation and "
        f"each additional country surfaced in the filings.\n"
        f"Reason about registry status, filing footprint, and sanctions "
        f"exposure per your skill spec. Then call "
        f"`delegated_authority_resolve_approver(action=\"vendor_kyc_signoff\", "
        f"category=<\"sanctions_hit\" / \"high_risk\" / \"medium_risk\" / \"low_risk\">)` "
        f"to identify the matrix-resolved approver and surface it as "
        f"`resolved_approver`. Return exactly the JSON object "
        f"specified in your skill instructions — no prose, no markdown."
    )
    result = await run_agent_session(
        prompt=prompt,
        tools=[
            vendor_registry_lookup_vendor_tool,
            vendor_registry_list_filings_tool,
            sanctions_api_screen_entity_tool,
            delegated_authority_resolve_approver_tool,
        ],
        skill_dir=_SKILL_DIR,
        skill_label="fleet-vendor-kyc-kyc-diligence-checker",
        workflow_id=workflow_id,
    )
    return {"kyc_diligence": result}
