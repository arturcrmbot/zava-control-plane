"""agent_receipt_validator — multimodal cross-check of receipt vs claim.

The receipt PNG is pre-fetched in Python and passed to the SDK session as a
multimodal `attachments=[{type: inline, content_type: image/png, data: b64}]`
(the SDK delivers it directly to the model — vision-capable models render it).
Structured claim fields stay accessible to the model via the `claim_get_structured`
tool, so the model can lazily read them per the skill's decision procedure.

Missing-receipt claims short-circuit: no model call, return the canonical
mismatch verdict. Saves tokens and avoids spurious vision attempts on a
zero-byte image.
"""
from __future__ import annotations
from pathlib import Path

from api.server.mcp_tools.claim_get_receipt import get_receipt
from api.server.mcp_tools.claim_get_structured import claim_get_structured_tool

from ._wrapper import run_agent_session

_SKILL_DIR = Path(__file__).resolve().parents[4] / "server" / "skills" / "receipt-validator"


async def execute(input: dict) -> dict:
    claim_id = input["claim_id"]
    receipt = get_receipt(claim_id)

    if receipt["absent"]:
        return {
            "receipt_validation": {
                "verdict": "mismatch",
                "flavour": "missing-receipt",
                "evidence": (
                    f"No receipt attached for claim {claim_id} "
                    f"(zero-byte marker on {receipt['filename']})."
                ),
                "confidence": 1.0,
            }
        }

    prompt = (
        f"Validate the attached receipt against expense claim `{claim_id}`. "
        f"Use `claim_get_structured` to load the claim's structured fields, "
        f"then inspect the attached image. Return the JSON object specified "
        f"in your skill — no prose, no markdown."
    )

    attachments = [
        {
            "type": "inline",
            "content_type": "image/png",
            "data": receipt["image_b64"],
        }
    ]

    validation = await run_agent_session(
        prompt=prompt,
        tools=[claim_get_structured_tool],
        skill_dir=_SKILL_DIR,
        skill_label="receipt-validator",
        attachments=attachments,
    )
    return {"receipt_validation": validation}
