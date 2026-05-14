"""Per-agent evaluator selection + context extractors.

`evaluators_for(agent_label)` returns a `{name: evaluator_instance}` dict.
LLM-based evaluators (Groundedness, Relevance, etc.) are imported lazily
from azure.ai.evaluation only when this function is first called for an
agent that needs them.

`extract_context(agent_label, tool_calls)` returns a string used as the
`context=` input to Groundedness — for `rag-classifier` it's the
concatenated policy_search results; for `arbitration` it's
precedents_search + policy_search; for unknown agents it's empty.
"""
from __future__ import annotations
from functools import lru_cache
from typing import Any

from api.server.eval import foundry_client
from api.server.eval.custom_evaluators import (
    PolicyClauseCited,
    ToolCallValidity,
    GoldLabelMatch,
    CVFieldExtractionAccuracy,
    ShortlistDecisionMatch,
    JurisdictionRoutingCorrectness,
)


@lru_cache(maxsize=1)
def _llm_evaluator_classes():
    """Lazy-import the SDK evaluator classes. Called at most once per process."""
    from azure.ai.evaluation import (
        GroundednessEvaluator,
        RelevanceEvaluator,
        SimilarityEvaluator,
        CoherenceEvaluator,
        FluencyEvaluator,
        ViolenceEvaluator,
        HateUnfairnessEvaluator,
    )
    return {
        "groundedness": GroundednessEvaluator,
        "relevance": RelevanceEvaluator,
        "similarity": SimilarityEvaluator,
        "coherence": CoherenceEvaluator,
        "fluency": FluencyEvaluator,
        "violence": ViolenceEvaluator,
        "hate_unfairness": HateUnfairnessEvaluator,
    }


class _SafetyAdapter:
    """Wraps a Foundry safety evaluator (Violence/HateUnfairness/...).

    The SDK's safety evaluators return an empty dict `{}` when no risk is
    detected — the common case for benign business content like expense
    classifications. The downstream tile aggregator needs a numeric value
    to render "safe", so we map empty → numeric 0 ("no risk detected" on
    the SDK's 0..7 risk scale).

    Real risk detections still pass through unchanged.
    """

    def __init__(self, inner, score_key: str):
        self._inner = inner
        self._score_key = score_key  # e.g. "violence" / "hate_unfairness"

    def __call__(self, **kwargs) -> dict:
        out = self._inner(**kwargs) or {}
        if not isinstance(out, dict):
            out = {}
        if not out:
            # Synthesise a "safe" reading. The score is 0 ("no risk") on
            # the SDK's 0..7 scale; the label mirrors the SDK's textual
            # classification. The tile aggregator reads the numeric base key.
            return {
                self._score_key: 0,
                f"{self._score_key}_score": 0,
                f"{self._score_key}_reason": "no risk detected",
                f"{self._score_key}_result": "pass",
            }
        return out


def _build_llm_evaluator(name: str) -> Any:
    """Construct one LLM evaluator with the right kwargs for its constructor.

    Quality evaluators take `model_config=`. Safety evaluators take
    `azure_ai_project=` + `credential=` (both required positional).
    Safety evaluators are wrapped in `_SafetyAdapter` so empty responses
    become a numeric 0 ("safe") rather than no-data.
    """
    classes = _llm_evaluator_classes()
    cls = classes[name]
    if name in ("violence", "hate_unfairness"):
        inner = cls(
            azure_ai_project=foundry_client.get_project_config(),
            credential=foundry_client._credential(),
        )
        return _SafetyAdapter(inner, score_key=name)
    return cls(model_config=foundry_client.get_model_config())


_PER_AGENT: dict[str, tuple[str, ...]] = {
    # NOTE: SimilarityEvaluator requires `ground_truth=` (only batch has it).
    # ViolenceEvaluator / HateUnfairnessEvaluator wrapped via SafetyAdapter
    # below — an empty SDK response (the common case for benign business
    # content) is interpreted as "no risk detected" (numeric 0).
    "rag-classifier": (
        "groundedness", "relevance",
        "policy_clause_cited", "tool_call_validity",
        "violence", "hate_unfairness",
    ),
    "arbitration": (
        "groundedness", "relevance", "coherence", "tool_call_validity",
        "violence", "hate_unfairness",
    ),
    # POC2 hiring — added 2026-05-05 per
    # plan/feature-foundry-credibility-friday-1.md TASK-016. Three new
    # deterministic evaluators join the labels CSV in
    # data/synthetic/hiring/ to score CV extraction, shortlist decision,
    # and jurisdiction routing.
    "cv-crystalliser": (
        "groundedness", "tool_call_validity", "cv_field_extraction_accuracy",
    ),
    "auto-shortlister": (
        "relevance", "tool_call_validity", "shortlist_decision_match",
    ),
    "jurisdiction-router": (
        "tool_call_validity", "jurisdiction_routing_correctness",
    ),
    "betrvg-checker": (
        "groundedness", "relevance",
    ),
    "voice-screener": (
        "relevance", "coherence",
    ),
    "interview-recommender": (
        "coherence", "relevance",
    ),
    "offer-personaliser": (
        "coherence", "fluency",
    ),
}
_DEFAULT: tuple[str, ...] = (
    "coherence", "fluency", "tool_call_validity",
    "violence", "hate_unfairness",
)


def evaluators_for(agent_label: str) -> dict[str, Any]:
    """Return `{name: evaluator_instance}` for the given agent label.

    Unknown labels fall back to the default `*` set.
    """
    names = _PER_AGENT.get(agent_label, _DEFAULT)
    out: dict[str, Any] = {}
    for n in names:
        if n == "policy_clause_cited":
            out[n] = PolicyClauseCited()
        elif n == "tool_call_validity":
            out[n] = ToolCallValidity()
        elif n == "gold_label_match":
            out[n] = GoldLabelMatch()
        elif n == "cv_field_extraction_accuracy":
            out[n] = CVFieldExtractionAccuracy()
        elif n == "shortlist_decision_match":
            out[n] = ShortlistDecisionMatch()
        elif n == "jurisdiction_routing_correctness":
            out[n] = JurisdictionRoutingCorrectness()
        else:
            out[n] = _build_llm_evaluator(n)
    return out


_CONTEXT_TOOLS: dict[str, tuple[str, ...]] = {
    "rag-classifier": ("policy_search",),
    "arbitration": ("precedents_search", "policy_search"),
    # POC2 hiring — contextual MCP tools whose `result` is the grounding
    # signal for `groundedness` evaluators.
    "cv-crystalliser": ("ocr_extract",),
    "jurisdiction-router": ("policy_search",),
    "betrvg-checker": ("policy_search",),
}


def extract_context(agent_label: str, tool_calls: list[dict]) -> str:
    """Concat the `result` field of tool calls whose `name` is in the
    per-agent context-tool list. Returns empty string for unknown agents.
    """
    relevant_names = _CONTEXT_TOOLS.get(agent_label, ())
    if not relevant_names:
        return ""
    parts: list[str] = []
    for call in tool_calls or []:
        if call.get("name") in relevant_names:
            result = call.get("result") or ""
            if isinstance(result, str) and result:
                parts.append(result)
    return "\n\n".join(parts)
