"""Tests for the named query-template registry (c2 remediation).

The ``find_patterns`` module replaces the old free-form ``cypher_pattern``
MCP surface; these tests pin the validator behaviour and the rendered
Cypher shape.
"""
from __future__ import annotations

import pytest

from api.server.services.find_patterns import (
    PATTERNS,
    pattern_names,
    render,
)


def test_registry_lists_expected_patterns():
    names = set(pattern_names())
    assert {
        "entity_by_id",
        "entities_by_kind",
        "entities_by_attr",
        "entities_touched_by_workflow",
        "linked_outgoing",
        "linked_incoming",
        "decisions_by_workflow",
        "decisions_by_persona_and_entity",
    } <= names


def test_render_unknown_name_raises_keyerror():
    with pytest.raises(KeyError):
        render("nope", {})


def test_render_validates_kind():
    with pytest.raises(ValueError):
        render("entities_by_kind", {"kind": "NotAKind"})


def test_render_inlines_limit_and_returns_bind():
    cypher, bind = render("entities_by_kind", {"kind": "Person", "limit": 5})
    assert "LIMIT 5" in cypher
    assert bind == {}


def test_render_clamps_limit_range():
    with pytest.raises(ValueError):
        render("entities_by_kind", {"kind": "Person", "limit": 0})
    with pytest.raises(ValueError):
        render("entities_by_kind", {"kind": "Person", "limit": 99999})


def test_render_validates_attr_key_identifier():
    with pytest.raises(ValueError):
        render(
            "entities_by_attr",
            {
                "kind": "Person",
                "attr_key": "name; DROP TABLE",
                "attr_value": "x",
            },
        )


def test_render_rejects_unknown_rel():
    with pytest.raises(ValueError):
        render("linked_outgoing", {"id": "X", "rel": "NOT_A_REL"})


def test_render_missing_required_param_is_valueerror():
    with pytest.raises(ValueError):
        render("entity_by_id", {"kind": "Person"})


def test_entities_by_attr_binds_value_as_param():
    cypher, bind = render(
        "entities_by_attr",
        {"kind": "Organisation", "attr_key": "risk_band", "attr_value": "high"},
    )
    assert "n.`risk_band` = $attr_value" in cypher
    assert bind["attr_value"] == "high"


def test_decisions_by_persona_and_entity_includes_decided_rel_filter():
    cypher, bind = render(
        "decisions_by_persona_and_entity",
        {"persona_role": "cfo", "entity_id": "ORG-1"},
    )
    assert "label(r) IN [" in cypher
    assert "ORDER BY d.decided_at DESC" in cypher
    assert bind == {"persona_role": "cfo", "entity_id": "ORG-1"}


def test_every_pattern_describes_itself():
    # Used by the MCP tool description; guard against accidental drop.
    for name, entry in PATTERNS.items():
        assert entry["describe"], name
        assert isinstance(entry["params"], tuple), name
