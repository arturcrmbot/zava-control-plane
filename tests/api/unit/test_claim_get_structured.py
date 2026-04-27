from __future__ import annotations
import pytest

from api.server.mcp_tools import claim_get_structured


def test_returns_claim_for_valid_id():
    claim = claim_get_structured.get_structured("CLM-0000")
    assert claim["claim_id"] == "CLM-0000"
    assert "amount" in claim and "category" in claim and "market" in claim


def test_raises_for_unknown_id():
    with pytest.raises(KeyError):
        claim_get_structured.get_structured("CLM-9999")


def test_redacts_gold_fields_by_default():
    claim = claim_get_structured.get_structured("CLM-0000")
    assert "gold_label" not in claim
    assert "gold_reasoning" not in claim
    assert "gold_policy_clause" not in claim


def test_include_gold_flag_for_test_paths():
    claim = claim_get_structured.get_structured("CLM-0000", include_gold=True)
    assert "gold_label" in claim
