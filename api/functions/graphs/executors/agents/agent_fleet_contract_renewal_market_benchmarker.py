"""agent_fleet_contract_renewal_market_benchmarker — invokes the
fleet-contract-renewal-market-benchmarker skill via the GHCP SDK.

Pass *only* the market-benchmarker skill directory to `skill_directories`
so multiple loaded skills don't fight over the output schema. Tools are
SDK-native (`@define_tool`), registered via `tools=[...]`, and called
autonomously by the model per the skill's `allowed-tools` frontmatter.
No prompt-stuffing.
"""
from __future__ import annotations

from api.server.mcp_tools.contract_repository import (
    contract_repository_get_contract_tool,
    contract_repository_find_similar_tool,
    contract_repository_list_amendments_tool,
)
from api.server.mcp_tools.market_pricing import market_pricing_get_quotes_tool

from ._wrapper import SKILLS_DIR, run_agent_session

_SKILL_DIR = SKILLS_DIR / "fleet-contract-renewal-market-benchmarker"


async def execute(input: dict) -> dict:
    workflow_id = input.get("workflow_id")
    contract = input.get("contract") or {}
    contract_lookup = input.get("contract_lookup") or {}
    prompt = (
        f"Benchmark the contract below against three comparable contracts in "
        f"our portfolio, fresh market quotes for the same category and "
        f"region, and the contract's amendment history.\n\n"
        f"Contract: contract_id={contract.get('contract_id')!r}.\n"
        f"Contract record: vendor={contract_lookup.get('vendor')!r}, "
        f"counterparty={contract_lookup.get('counterparty')!r}, "
        f"category={contract_lookup.get('category')!r}, "
        f"region={contract_lookup.get('region')!r}, "
        f"current_annual_value_usd={contract_lookup.get('current_annual_value_usd')!r}, "
        f"term_years={contract_lookup.get('term_years')!r}, "
        f"expires_on={contract_lookup.get('expires_on')!r}.\n\n"
        f"Use `contract_repository_find_similar(category, region, "
        f"value_usd_low, value_usd_high)` to load three comparable "
        f"contracts in the same category and region whose annual value "
        f"sits inside ±25% of the current_annual_value_usd. Use "
        f"`market_pricing_get_quotes(category, region)` to load fresh "
        f"market quotes for the same category and region. Use "
        f"`contract_repository_list_amendments(contract_id)` to load "
        f"this contract's amendment history so you can detect creeping "
        f"scope (count of amendments and whether scope has been "
        f"materially expanded). "
        f"Reason about the price band the renewal should sit in per "
        f"your skill spec. "
        f"Return exactly the JSON object specified in your skill instructions "
        f"— no prose, no markdown."
    )
    result = await run_agent_session(
        prompt=prompt,
        tools=[
            contract_repository_get_contract_tool,
            contract_repository_find_similar_tool,
            contract_repository_list_amendments_tool,
            market_pricing_get_quotes_tool,
        ],
        skill_dir=_SKILL_DIR,
        skill_label="fleet-contract-renewal-market-benchmarker",
        workflow_id=workflow_id,
        instance_id=input.get("instance_id"),
    )
    return {"market_benchmarker": result}
