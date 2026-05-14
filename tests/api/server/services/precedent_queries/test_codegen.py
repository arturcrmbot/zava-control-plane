"""Tests for author-decision-mapping codegen + validator (TASK-017)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
SUB_SKILL_DIR = (
    REPO_ROOT
    / "docs"
    / "superpowers"
    / "skills"
    / "compose-domain"
    / "sub-skills"
    / "author-decision-mapping"
)
SHARED_DIR = SUB_SKILL_DIR.parent / "_shared"


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_load("_shared", SHARED_DIR / "__init__.py")
_load("_shared.brief_validator", SHARED_DIR / "brief_validator.py")
codegen = _load(
    "compose_domain_v4__author_decision_mapping__codegen",
    SUB_SKILL_DIR / "codegen.py",
)
validator = _load(
    "compose_domain_v4__author_decision_mapping__validator",
    SUB_SKILL_DIR / "validator.py",
)


@pytest.fixture
def brief():
    return {
        "domain": {
            "workflow_type": "vendor-kyc",
            "prefix": "fleet",
            "display_name": "Vendor KYC",
        },
        "phases": [
            {"name": "intake", "kind": "deterministic"},
            {"name": "diligence", "kind": "agent", "agent_skill_name": "x"},
            {"name": "finance_signoff", "kind": "hitl",
             "persona": "vendor_kyc_finance_bp",
             "external_event": "finance_signoff_decision"},
        ],
        "entities": [
            {"kind": "Organisation", "source": "vendor",
             "ref_field": "payload.vendor.id"},
        ],
        "decisions": [
            {"phase": "finance_signoff", "persona": "vendor_kyc_finance_bp",
             "source_event": "workflow.hitl.requested",
             "decided_on_entities": ["payload.vendor.id"]},
        ],
    }


def test_render_filename_kebab_phase(brief):
    fname = codegen.render_filename(brief, brief["decisions"][0])
    assert fname == "vendor-kyc_finance_signoff.cypher"


def test_render_cypher_has_dedupe_match_clause(brief):
    body = codegen.render_cypher(brief, brief["decisions"][0])
    assert "MATCH (d:Decision)-[:DECIDED_ON]->(e {id: $entity_id})" in body
    assert "d.persona_role = 'vendor_kyc_finance_bp'" in body
    assert "d.workflow_type = 'vendor-kyc'" in body
    assert "ORDER BY d.decided_at DESC" in body
    assert "LIMIT $limit" in body


def test_validate_clean_brief(brief):
    validator.validate(brief, repo_root=REPO_ROOT)


def test_phase_not_hitl_raises(brief):
    brief["decisions"][0]["phase"] = "diligence"
    with pytest.raises(validator.SchemaError) as exc:
        validator.validate(brief, repo_root=REPO_ROOT)
    assert exc.value.path == "decisions[0].phase"
    assert "hitl" in exc.value.reason


def test_unknown_phase_raises(brief):
    brief["decisions"][0]["phase"] = "made_up_phase"
    with pytest.raises(validator.SchemaError) as exc:
        validator.validate(brief, repo_root=REPO_ROOT)
    assert exc.value.path == "decisions[0].phase"


def test_dup_phase_raises(brief):
    brief["decisions"].append(dict(brief["decisions"][0]))
    with pytest.raises(validator.SchemaError) as exc:
        validator.validate(brief, repo_root=REPO_ROOT)
    assert exc.value.path == "decisions[1].phase"
    assert "already claimed" in exc.value.reason


def test_unknown_decided_on_entity_raises(brief):
    brief["decisions"][0]["decided_on_entities"] = ["payload.bogus.id"]
    with pytest.raises(validator.SchemaError) as exc:
        validator.validate(brief, repo_root=REPO_ROOT)
    assert "decided_on_entities" in exc.value.path


def test_unknown_persona_raises(brief, tmp_path):
    """When personae directory is reachable, unknown persona must raise."""
    # Build a minimal personae dir containing only "x".
    p = tmp_path / "api" / "server" / "personae" / "x"
    p.mkdir(parents=True)
    (p / "SKILL.md").write_text("---\nname: x\n---\n")
    brief["decisions"][0]["persona"] = "not-a-real-persona"
    with pytest.raises(validator.SchemaError) as exc:
        validator.validate(brief, repo_root=tmp_path)
    assert exc.value.path == "decisions[0].persona"
