"""End-to-end smoke for the v4 compose-domain pipeline (TASK-040).

THE 13th brief at ``docs/superpowers/specs/fleet-purchase-card-brief.yaml``
is the substrate-by-construction proof: it has no Phase 1 hand-written
projection module, so the only way it could land is via the v4 codegens.
This test invokes both codegens against the brief and asserts the
output is syntactically + semantically usable.

Scope: codegen output only. We do not graduate the brief into
``api/server/services/entity_projections/`` — that is a destructive
manual step performed via ``graduate.sh`` and is out-of-scope for the
test harness.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[5]
BRIEF_PATH = REPO_ROOT / "docs" / "superpowers" / "specs" / "fleet-purchase-card-brief.yaml"


@pytest.fixture(scope="module")
def brief() -> dict:
    return yaml.safe_load(BRIEF_PATH.read_text())


def test_brief_validates(brief, shared_validator):
    """The 13th brief must validate against the v4 schema."""
    shared_validator.validate_brief(brief)


def test_brief_domain_shape(brief):
    domain = brief["domain"]
    assert domain["workflow_type"] == "purchase-card"
    assert domain["prefix"] == "fleet"
    assert domain["display_name"]
    assert brief["function"] == "finance"


def test_render_projection(brief, sub_skill_loader):
    """Entity-projection codegen produces a parseable Python module."""
    codegen = sub_skill_loader("author-entity-projection", "codegen")
    filename, body = codegen.render_projection(brief)

    assert filename == "purchase_card.py"
    # Syntactic round-trip: must parse as Python.
    ast.parse(body)
    # Required surface area mirrors the Phase 1 hand-written projections.
    assert 'WORKFLOW_TYPE = "purchase-card"' in body
    assert "def project(workflow: Workflow)" in body
    # Both entities are emitted.
    assert "kind='Person'" in body
    assert "kind='Money'" in body
    # Source labels surface as the entity's `kind` attr.
    assert "'cardholder'" in body
    assert "'pcard-txn'" in body
    # Imports stay scoped to the entity_projections shared helpers.
    assert "from api.server.services.entity_projections import" in body
    assert "from api.shared.types import Workflow" in body


def test_render_decision_cypher(brief, sub_skill_loader):
    """Decision-mapping codegen produces one .cypher per HITL gate."""
    codegen = sub_skill_loader("author-decision-mapping", "codegen")

    decisions = brief["decisions"]
    assert len(decisions) == 1, "purchase-card has exactly one HITL gate"
    d = decisions[0]

    fname = codegen.render_filename(brief, d)
    body = codegen.render_cypher(brief, d)

    assert fname == "purchase-card_manager_approval.cypher"
    assert "MATCH (d:Decision)-[:DECIDED_ON]->(e {id: $entity_id})" in body
    assert "d.persona_role = 'line_manager'" in body
    assert "d.workflow_type = 'purchase-card'" in body
    assert "$limit" in body


def test_ambient_trigger_block(brief, sub_skill_loader):
    """Ambient block validates + the codegen renders an importable stub."""
    validator = sub_skill_loader("author-ambient-trigger", "validator")
    validator.validate(brief)

    codegen = sub_skill_loader("author-ambient-trigger", "codegen")
    target_path, block = codegen.render_ambient(brief)
    assert "PurchaseCardWatcher" in block
    assert "purchase-card" in block
    # The block targets the `finance` ambient-agents module (matches
    # brief.function) and rides the v4 sentinel-bracketed append shape.
    assert str(target_path).endswith("finance.py")
