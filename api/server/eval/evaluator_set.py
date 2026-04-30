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


def _build_llm_evaluator(name: str) -> Any:
    """Construct one LLM evaluator with the right kwargs for its constructor."""
    classes = _llm_evaluator_classes()
    cls = classes[name]
    if name in ("violence", "hate_unfairness"):
        return cls(azure_ai_project=foundry_client.get_project_config())
    return cls(model_config=foundry_client.get_model_config())


_PER_AGENT: dict[str, tuple[str, ...]] = {
    "rag-classifier": (
        "groundedness", "relevance", "similarity",
        "policy_clause_cited", "tool_call_validity",
    ),
    "arbitration": (
        "groundedness", "relevance", "coherence", "violence", "hate_unfairness",
    ),
}
_DEFAULT: tuple[str, ...] = ("coherence", "fluency", "violence", "hate_unfairness")


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
        else:
            out[n] = _build_llm_evaluator(n)
    return out


_CONTEXT_TOOLS: dict[str, tuple[str, ...]] = {
    "rag-classifier": ("policy_search",),
    "arbitration": ("precedents_search", "policy_search"),
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
