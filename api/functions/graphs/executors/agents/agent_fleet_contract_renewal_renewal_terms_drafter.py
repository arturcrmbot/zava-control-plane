"""agent_fleet_contract_renewal_renewal_terms_drafter — invokes the
fleet-contract-renewal-renewal-terms-drafter skill via the GHCP SDK.

Pass *only* the renewal-terms-drafter skill directory to
`skill_directories` so multiple loaded skills don't fight over the
output schema. Tools are SDK-native (`@define_tool`), registered via
`tools=[...]`, and called autonomously by the model per the skill's
`allowed-tools` frontmatter. No prompt-stuffing.
"""
from __future__ import annotations

from api.server.mcp_tools.contract_repository import (
    contract_repository_get_contract_tool,
    contract_repository_find_similar_tool,
    contract_repository_list_amendments_tool,
)
from api.server.mcp_tools.market_pricing import market_pricing_get_quotes_tool
from api.server.mcp_tools.policy_cite import policy_cite_tool

from ._wrapper import SKILLS_DIR, run_agent_session

_SKILL_DIR = SKILLS_DIR / "fleet-contract-renewal-renewal-terms-drafter"


async def execute(input: dict) -> dict:
    workflow_id = input.get("workflow_id")
    contract = input.get("contract") or {}
    contract_lookup = input.get("contract_lookup") or {}
    market_benchmarker = input.get("market_benchmarker") or {}
    prompt = (
        f"Draft proposed renewal terms for the contract below. Combine "
        f"the benchmarked price band from Phase 2 with the relevant "
        f"legal-clause precedents and propose a per-line delta vs the "
        f"current contract.\n\n"
        f"Contract: contract_id={contract.get('contract_id')!r}.\n"
        f"Contract record: vendor={contract_lookup.get('vendor')!r}, "
        f"category={contract_lookup.get('category')!r}, "
        f"region={contract_lookup.get('region')!r}, "
        f"current_annual_value_usd={contract_lookup.get('current_annual_value_usd')!r}, "
        f"term_years={contract_lookup.get('term_years')!r}.\n"
        f"Benchmark verdict: verdict={market_benchmarker.get('verdict')!r}, "
        f"benchmark_band_low_usd={market_benchmarker.get('benchmark_band_low_usd')!r}, "
        f"benchmark_band_high_usd={market_benchmarker.get('benchmark_band_high_usd')!r}, "
        f"comparable_contracts={market_benchmarker.get('comparable_contracts')!r}, "
        f"market_quotes={market_benchmarker.get('market_quotes')!r}, "
        f"amendment_summary={market_benchmarker.get('amendment_summary')!r}.\n\n"
        f"Use `contract_repository_get_contract(contract_id)` if you need "
        f"to re-read the source-of-truth contract record (e.g. line-item "
        f"breakdown). Use `contract_repository_list_amendments(contract_id)` "
        f"to enumerate the amendment delta the new terms must reconcile "
        f"with. Use `market_pricing_get_quotes(category, region)` to "
        f"re-confirm the current market quotes if a vendor's quote moved. "
        f"Use `policy_cite_policy_cite(clause)` once per clause name you "
        f"intend to cite (e.g. \"renewal-cap\", \"price-index\", "
        f"\"termination-for-convenience\") to fetch the verbatim policy "
        f"text. "
        f"Reason about a renewal price inside the benchmark band per "
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
            policy_cite_tool,
        ],
        skill_dir=_SKILL_DIR,
        skill_label="fleet-contract-renewal-renewal-terms-drafter",
        workflow_id=workflow_id,
    )
    return {"renewal_terms_drafter": result}
