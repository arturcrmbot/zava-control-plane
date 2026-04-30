"""Unit tests for the three deterministic custom evaluators."""
from __future__ import annotations

from api.server.eval.custom_evaluators import (
    PolicyClauseCited,
    ToolCallValidity,
    GoldLabelMatch,
)


# ---- PolicyClauseCited ------------------------------------------------------

def test_policy_clause_cited_returns_1_when_30plus_char_excerpt_appears_in_response():
    ev = PolicyClauseCited()
    context = (
        "§3.2 Meal claims must not exceed 110% of the per-diem cap published "
        "for the claimant's market in Annex A."
    )
    response = (
        "I am denying this claim under the rule that meal claims must not "
        "exceed 110% of the per-diem cap published for the claimant's market."
    )
    out = ev(query="claim CLM-001", response=response, context=context)
    assert out["policy_clause_cited"] == 1
    assert out["policy_clause_excerpt"] is not None


def test_policy_clause_cited_returns_0_when_no_substring_match():
    ev = PolicyClauseCited()
    context = "§3.2 Meal claims must not exceed 110% of the per-diem cap."
    response = "Approved per policy clause 3.2."
    out = ev(query="claim CLM-002", response=response, context=context)
    assert out["policy_clause_cited"] == 0
    assert out["policy_clause_excerpt"] is None


def test_policy_clause_cited_normalises_whitespace_differences():
    """Different whitespace between context and response should still match."""
    ev = PolicyClauseCited()
    context = "§3.2  Meal claims must not exceed 110% of the per-diem cap."
    response = "Per policy: Meal claims must not exceed 110% of the per-diem cap."
    out = ev(query="claim CLM-003", response=response, context=context)
    assert out["policy_clause_cited"] == 1


def test_policy_clause_cited_returns_0_when_context_empty():
    ev = PolicyClauseCited()
    out = ev(query="q", response="some text", context="")
    assert out["policy_clause_cited"] == 0


# ---- ToolCallValidity -------------------------------------------------------

def test_tool_call_validity_all_valid():
    ev = ToolCallValidity()
    out = ev(
        query="q", response="r",
        tool_calls=[
            {"name": "policy_search", "args": '{"market": "EU"}', "success": True},
            {"name": "claim_get_structured", "args": '{"claim_id": "CLM-001"}', "success": True},
        ],
        declared_tools=["policy_search", "claim_get_structured"],
    )
    assert out["tool_calls_valid"] == 1.0
    assert out["invalid_calls"] == []


def test_tool_call_validity_unknown_tool_name_drops_score():
    ev = ToolCallValidity()
    out = ev(
        query="q", response="r",
        tool_calls=[
            {"name": "policy_search", "args": '{"market": "EU"}', "success": True},
            {"name": "imaginary_tool", "args": "{}", "success": True},
        ],
        declared_tools=["policy_search"],
    )
    assert out["tool_calls_valid"] == 0.5
    assert {"reason": "unknown_tool", "name": "imaginary_tool"} in out["invalid_calls"]


def test_tool_call_validity_unparseable_args_counts_as_invalid():
    ev = ToolCallValidity()
    out = ev(
        query="q", response="r",
        tool_calls=[
            {"name": "policy_search", "args": "{not valid json", "success": True},
        ],
        declared_tools=["policy_search"],
    )
    assert out["tool_calls_valid"] == 0.0
    assert any(c["reason"] == "unparseable_args" for c in out["invalid_calls"])


def test_tool_call_validity_no_tool_calls_returns_1():
    """A response with no tool calls is trivially valid (no invalid calls)."""
    ev = ToolCallValidity()
    out = ev(query="q", response="r", tool_calls=[], declared_tools=["policy_search"])
    assert out["tool_calls_valid"] == 1.0
    assert out["invalid_calls"] == []


# ---- GoldLabelMatch ---------------------------------------------------------

def test_gold_label_match_exact_match_red():
    ev = GoldLabelMatch()
    out = ev(predicted="Red", gold="Red")
    assert out["label_match"] == 1
    assert out["predicted"] == "Red"
    assert out["gold"] == "Red"


def test_gold_label_match_mismatch():
    ev = GoldLabelMatch()
    out = ev(predicted="Amber", gold="Red")
    assert out["label_match"] == 0


def test_gold_label_match_is_case_sensitive():
    """Verdicts in the corpus are exactly Red/Amber/Green; lowercase != match."""
    ev = GoldLabelMatch()
    out = ev(predicted="red", gold="Red")
    assert out["label_match"] == 0
