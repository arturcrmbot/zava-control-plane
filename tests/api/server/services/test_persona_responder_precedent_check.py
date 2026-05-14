"""Pitch I1: precedent_check sandbox helper + integration with the
controller persona's decision_policy.

The helper aggregates rows returned by the ``query_precedents`` MCP tool
into a single ``{verdict, confidence, n_precedents, hits}`` dict. When
≥3 precedents agree, the controller persona auto-applies that verdict
without consulting the authority matrix.
"""
from __future__ import annotations

from typing import Any

import pytest

from api.server.services import persona_responder


# ---------------------------------------------------------------------------
# Direct unit tests on the sandbox helper
# ---------------------------------------------------------------------------


def _patch_query_tool(monkeypatch, rows: list[dict[str, Any]]):
    """Replace ``make_query_precedents_tool`` so the helper sees ``rows``."""
    def _fake_make(_graph):
        def _tool(persona_role, entity_id, limit, *,
                  workflow_type=None, phase=None,
                  cite_from_decision_id=None):
            _tool.calls.append({
                "persona_role": persona_role,
                "entity_id": entity_id,
                "limit": limit,
                "workflow_type": workflow_type,
                "phase": phase,
                "cite_from_decision_id": cite_from_decision_id,
            })
            return rows
        _tool.calls = []
        return _tool

    import api.server.mcp_tools.query_precedents as qp
    monkeypatch.setattr(qp, "make_query_precedents_tool", _fake_make)


def test_precedent_check_no_rows_returns_zero(monkeypatch):
    _patch_query_tool(monkeypatch, [])
    out = persona_responder._sandbox_precedent_check(
        workflow_type="ap_invoice", phase="controller_review",
        persona_role="controller",
    )
    assert out == {"verdict": None, "n_precedents": 0,
                   "confidence": 0.0, "hits": []}


def test_precedent_check_majority_verdict(monkeypatch):
    rows = [
        {"d": {"verdict": "approve"}},
        {"d": {"verdict": "approve"}},
        {"d": {"verdict": "approve"}},
        {"d": {"verdict": "reject"}},
    ]
    _patch_query_tool(monkeypatch, rows)
    out = persona_responder._sandbox_precedent_check(
        workflow_type="ap_invoice", phase="controller_review",
        persona_role="controller",
    )
    assert out["verdict"] == "approve"
    assert out["n_precedents"] == 3
    assert out["confidence"] == pytest.approx(0.75)
    assert out["hits"] == ["approve", "approve", "approve", "reject"]


def test_precedent_check_passes_first_decided_on_as_entity(monkeypatch):
    """The first element of ``decided_on`` scopes the lookup to one entity."""
    _patch_query_tool(monkeypatch, [])
    fake_tool_factory = {"latest": None}

    import api.server.mcp_tools.query_precedents as qp

    def _factory(_graph):
        def _tool(persona_role, entity_id, limit, *,
                  workflow_type=None, phase=None,
                  cite_from_decision_id=None):
            fake_tool_factory["latest"] = {
                "persona_role": persona_role,
                "entity_id": entity_id,
                "limit": limit,
                "workflow_type": workflow_type,
                "phase": phase,
                "cite_from_decision_id": cite_from_decision_id,
            }
            return []
        return _tool

    monkeypatch.setattr(qp, "make_query_precedents_tool", _factory)
    persona_responder._sandbox_precedent_check(
        workflow_type="ap_invoice", phase="controller_review",
        persona_role="controller",
        decided_on=("vendor:ACME-42", "money:row-1"),
    )
    seen = fake_tool_factory["latest"]
    assert seen is not None
    assert seen["entity_id"] == "vendor:ACME-42"
    assert seen["persona_role"] == "controller"
    assert seen["workflow_type"] == "ap_invoice"
    assert seen["phase"] == "controller_review"


def test_precedent_check_swallows_tool_errors(monkeypatch):
    """Any exception in the underlying tool degrades to no-precedent."""
    import api.server.mcp_tools.query_precedents as qp

    def _factory(_graph):
        def _tool(*a, **kw):
            raise RuntimeError("graph offline")
        return _tool

    monkeypatch.setattr(qp, "make_query_precedents_tool", _factory)
    out = persona_responder._sandbox_precedent_check(
        workflow_type="ap_invoice", phase="controller_review",
        persona_role="controller",
    )
    assert out["verdict"] is None
    assert out["n_precedents"] == 0


def test_precedent_check_is_in_decision_builtins():
    """The sandbox MUST expose ``precedent_check`` so SKILL.md policies
    can call it directly."""
    assert "precedent_check" in persona_responder._DECISION_BUILTINS
    assert persona_responder._DECISION_BUILTINS["precedent_check"] is (
        persona_responder._sandbox_precedent_check
    )


# ---------------------------------------------------------------------------
# Integration: the controller persona auto-applies precedent verdicts
# ---------------------------------------------------------------------------


@pytest.fixture
def _controller(monkeypatch):
    monkeypatch.setenv("PERSONA_AUTO_CLOSE", "*")
    persona_responder.PERSONA_DEFINITIONS = persona_responder._load_personae()
    persona = persona_responder.PERSONA_DEFINITIONS.get("controller")
    assert persona is not None, "controller persona must load from SKILL.md"
    return persona


def test_controller_applies_precedent_when_three_agree(monkeypatch, _controller):
    """≥3 precedents agreeing on ``approve`` short-circuits authority_check."""
    rows = [
        {"d": {"verdict": "approve"}},
        {"d": {"verdict": "approve"}},
        {"d": {"verdict": "approve"}},
    ]
    _patch_query_tool(monkeypatch, rows)

    # If authority_check is consulted, fail the test loudly — precedent
    # path must short-circuit it.
    def _boom(*a, **kw):
        raise AssertionError(
            "authority_check should not be called when precedents agree"
        )

    original = persona_responder._DECISION_BUILTINS["authority_check"]
    persona_responder._DECISION_BUILTINS["authority_check"] = _boom

    try:
        out = _controller.decide({
            "invoice": {"amount_gbp": 1000, "category": "standard"},
            "workflow_type": "ap_invoice",
            "phase": "controller_review",
        })
    finally:
        persona_responder._DECISION_BUILTINS["authority_check"] = original

    assert out["decision"] == "approve"
    assert "precedent" in out["reason"]


def test_controller_falls_through_when_few_precedents(monkeypatch, _controller):
    """<3 precedents → original authority_check path runs."""
    rows = [{"d": {"verdict": "approve"}}, {"d": {"verdict": "approve"}}]
    _patch_query_tool(monkeypatch, rows)

    out = _controller.decide({
        "invoice": {"amount_gbp": 100, "category": "standard"},
        "workflow_type": "ap_invoice",
        "phase": "controller_review",
    })
    # 2 precedents → fall through; controller's authority matrix decides.
    assert out["decision"] in {"approve", "reject", "escalate"}
    assert "precedent" not in out["reason"].lower()
