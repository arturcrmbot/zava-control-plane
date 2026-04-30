"""Tests for evaluator_set: per-agent evaluator selection + context extractors.

We mock the Foundry-SDK evaluator classes so this test runs without azure-ai-evaluation
needing creds. Production code hits the real SDK; tests assert the *shape* of the
mapping and the *names* of evaluators returned per agent.
"""
from __future__ import annotations
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def mock_sdk_evaluators():
    """Patch the Foundry SDK evaluator classes used by evaluator_set."""
    with patch.dict("sys.modules", {
        "azure.ai.evaluation": MagicMock(
            GroundednessEvaluator=lambda model_config: ("groundedness", model_config),
            RelevanceEvaluator=lambda model_config: ("relevance", model_config),
            SimilarityEvaluator=lambda model_config: ("similarity", model_config),
            CoherenceEvaluator=lambda model_config: ("coherence", model_config),
            FluencyEvaluator=lambda model_config: ("fluency", model_config),
            ViolenceEvaluator=lambda azure_ai_project, credential: ("violence", azure_ai_project),
            HateUnfairnessEvaluator=lambda azure_ai_project, credential: ("hate_unfairness", azure_ai_project),
        ),
    }):
        import sys
        sys.modules.pop("api.server.eval.evaluator_set", None)
        yield


def test_rag_classifier_evaluator_set_includes_groundedness_and_custom(monkeypatch, mock_sdk_evaluators):
    monkeypatch.setenv("AZURE_FOUNDRY_PROJECT_ENDPOINT", "https://e/api/projects/p")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://aoai.example.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    from api.server.eval.evaluator_set import evaluators_for
    evals = evaluators_for("rag-classifier")
    assert set(evals.keys()) == {
        "groundedness", "relevance",
        "policy_clause_cited", "tool_call_validity",
        "violence", "hate_unfairness",
    }


def test_arbitration_evaluator_set(monkeypatch, mock_sdk_evaluators):
    monkeypatch.setenv("AZURE_FOUNDRY_PROJECT_ENDPOINT", "https://e/api/projects/p")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://aoai.example.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    from api.server.eval.evaluator_set import evaluators_for
    evals = evaluators_for("arbitration")
    assert set(evals.keys()) == {
        "groundedness", "relevance", "coherence", "tool_call_validity",
        "violence", "hate_unfairness",
    }


def test_unknown_agent_label_falls_back_to_default(monkeypatch, mock_sdk_evaluators):
    monkeypatch.setenv("AZURE_FOUNDRY_PROJECT_ENDPOINT", "https://e/api/projects/p")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://aoai.example.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    from api.server.eval.evaluator_set import evaluators_for
    evals = evaluators_for("some-future-poc2-agent")
    assert set(evals.keys()) == {
        "coherence", "fluency", "tool_call_validity",
        "violence", "hate_unfairness",
    }


def test_extract_context_for_rag_classifier_concats_policy_search_results():
    from api.server.eval.evaluator_set import extract_context
    tool_calls = [
        {"name": "claim_get_structured", "args": "{}", "result": "{...claim...}", "success": True},
        {"name": "policy_search", "args": "{}",
         "result": "§3.2 Meal claims must not exceed 110% of the per-diem cap.",
         "success": True},
        {"name": "policy_search", "args": "{}",
         "result": "§4.1 Receipts are required for any claim ≥ £25.",
         "success": True},
    ]
    ctx = extract_context("rag-classifier", tool_calls)
    assert "§3.2" in ctx
    assert "§4.1" in ctx
    assert "claim_get_structured" not in ctx  # only policy_search results contribute


def test_extract_context_for_arbitration_concats_precedents_search_results():
    from api.server.eval.evaluator_set import extract_context
    tool_calls = [
        {"name": "precedents_search", "args": "{}", "result": "Case A: warning issued.", "success": True},
        {"name": "policy_search", "args": "{}", "result": "§3.2 ...", "success": True},
    ]
    ctx = extract_context("arbitration", tool_calls)
    assert "Case A" in ctx
    assert "§3.2" in ctx  # arbitration also uses policy_search


def test_extract_context_for_unknown_agent_returns_empty():
    from api.server.eval.evaluator_set import extract_context
    assert extract_context("unknown", [{"name": "anything", "result": "..."}]) == ""


# ---- SafetyAdapter ---------------------------------------------------------

def test_safety_adapter_treats_empty_response_as_safe(monkeypatch):
    """Foundry's Violence/HateUnfairness evaluators return {} on benign content.
    The adapter must convert that to a numeric 0 ('no risk detected') so the
    safety tile renders as 100% safe rather than 'no data'."""
    monkeypatch.setenv("AZURE_FOUNDRY_PROJECT_ENDPOINT", "https://e/api/projects/p")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://aoai.example.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    import sys
    sys.modules.pop("api.server.eval.evaluator_set", None)
    from api.server.eval.evaluator_set import _SafetyAdapter

    inner = lambda **kw: {}  # SDK returns nothing
    adapter = _SafetyAdapter(inner, score_key="violence")
    out = adapter(query="q", response="r")
    assert out["violence"] == 0
    assert out["violence_score"] == 0
    assert out["violence_result"] == "pass"


def test_safety_adapter_passes_through_real_risk(monkeypatch):
    """When the SDK does return a real reading, the adapter must not clobber it."""
    monkeypatch.setenv("AZURE_FOUNDRY_PROJECT_ENDPOINT", "https://e/api/projects/p")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://aoai.example.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    import sys
    sys.modules.pop("api.server.eval.evaluator_set", None)
    from api.server.eval.evaluator_set import _SafetyAdapter

    inner = lambda **kw: {"violence": 5, "violence_score": 5, "violence_reason": "explicit"}
    adapter = _SafetyAdapter(inner, score_key="violence")
    out = adapter(query="q", response="r")
    assert out["violence"] == 5
    assert out["violence_score"] == 5
