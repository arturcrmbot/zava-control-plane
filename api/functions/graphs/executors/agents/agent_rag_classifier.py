"""agent_rag_classifier — invokes the rag_classifier skill via the GHCP wrapper."""
from __future__ import annotations

from ._wrapper import run_agent_skill


async def execute(input: dict) -> dict:
    claim_id = input["claim_id"]
    prompt = (
        f"Classify expense claim {claim_id} per your role.\n\n"
        f"Call claim.getStructured to load the claim, then policy.search to ground "
        f"your verdict in the relevant policy clause. Return the JSON object specified "
        f"in your skill instructions — no prose."
    )
    classification = await run_agent_skill("rag_classifier", prompt)
    return {"classification": classification}
