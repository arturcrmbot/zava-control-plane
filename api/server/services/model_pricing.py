"""Model pricing table — keep cost numbers grounded in published Microsoft prices.

Source: https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/
Captured: 2026-05-05 by feature-foundry-credibility-friday-1.md TASK-008.

Per-million-token rates in USD for Azure OpenAI standard deployments. When
pricing changes, edit the table and bump `PRICING_SOURCE_DATE`. Unknown model
ids fall back to `gpt-4.1` rates with a structured warning attribute on the
returned span (callers should set `wpp.cost.fallback_model = true` if they
care to surface this).

Cost is `(input_tokens / 1e6) * input_per_million_usd
       + (output_tokens / 1e6) * output_per_million_usd`.
"""
from __future__ import annotations
import logging

log = logging.getLogger(__name__)

PRICING_SOURCE_URL = "https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/"
PRICING_SOURCE_DATE = "2026-05-05"
PRICING_SOURCE = f"azure-published-{PRICING_SOURCE_DATE}"

# {model_id: {"input_per_million_usd": float, "output_per_million_usd": float}}
MODEL_PRICING: dict[str, dict[str, float]] = {
    # OpenAI 4.1 family — global standard pricing.
    "gpt-4.1": {"input_per_million_usd": 2.00, "output_per_million_usd": 8.00},
    "gpt-4.1-mini": {"input_per_million_usd": 0.40, "output_per_million_usd": 1.60},
    "gpt-4.1-nano": {"input_per_million_usd": 0.10, "output_per_million_usd": 0.40},
    # 4o family — kept for cross-checking against Foundry-deployed judge models.
    "gpt-4o": {"input_per_million_usd": 2.50, "output_per_million_usd": 10.00},
    "gpt-4o-mini": {"input_per_million_usd": 0.15, "output_per_million_usd": 0.60},
}

_FALLBACK_MODEL = "gpt-4.1"


def cost_for(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return the USD cost of an inference with the given token counts.

    Unknown models fall back to `gpt-4.1` rates with a logged warning. Negative
    or non-int token counts are clamped to 0; the math is `(tok/1e6) * rate`.
    """
    in_tok = max(0, int(input_tokens or 0))
    out_tok = max(0, int(output_tokens or 0))
    rates = MODEL_PRICING.get(model)
    if rates is None:
        log.warning(
            "model_pricing: unknown model %r — falling back to %s rates",
            model, _FALLBACK_MODEL,
        )
        rates = MODEL_PRICING[_FALLBACK_MODEL]
    return (in_tok / 1e6) * rates["input_per_million_usd"] + \
           (out_tok / 1e6) * rates["output_per_million_usd"]
