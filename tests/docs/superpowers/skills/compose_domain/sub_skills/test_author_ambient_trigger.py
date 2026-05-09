"""Tests for author-ambient-trigger validator + codegen (TASK-025)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[6]
SUB_SKILL_DIR = (
    REPO_ROOT
    / "docs"
    / "superpowers"
    / "skills"
    / "compose-domain"
    / "sub-skills"
    / "author-ambient-trigger"
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
    "compose_domain_v4__author_ambient_trigger__codegen",
    SUB_SKILL_DIR / "codegen.py",
)
validator = _load(
    "compose_domain_v4__author_ambient_trigger__validator",
    SUB_SKILL_DIR / "validator.py",
)


def _base_brief():
    return {
        "domain": {
            "workflow_type": "vendor-kyc",
            "prefix": "fleet",
            "display_name": "Vendor KYC",
        },
        "phases": [
            {"name": "intake", "kind": "deterministic"},
            {"name": "signoff", "kind": "hitl",
             "persona": "x", "external_event": "x_decision"},
        ],
        "function": "finance",
        "ambient": {
            "name": "VendorRiskWatcher",
            "function": "finance",
            "reasoning_skill": None,
            "spawnable_workflow_types": ["vendor-kyc"],
            "triggers": [
                {"kind": "cypher",
                 "pattern": "(o:Organisation {kind:'vendor'}) WHERE o.risk_band='high'",
                 "sweep_seconds": 3600},
            ],
        },
    }


def test_clean_bus_trigger_validates():
    b = _base_brief()
    b["ambient"]["triggers"] = [
        {"kind": "bus", "event_type": "workflow.completed", "filter": "type='vendor-kyc'"},
    ]
    validator.validate(b, known_workflow_types={"vendor-kyc"})


def test_clean_cypher_trigger_validates():
    validator.validate(_base_brief(), known_workflow_types={"vendor-kyc"})


def test_unknown_spawnable_workflow_type_raises():
    b = _base_brief()
    b["ambient"]["spawnable_workflow_types"] = ["does-not-exist"]
    with pytest.raises(validator.SchemaError) as exc:
        validator.validate(b, known_workflow_types={"vendor-kyc"})
    assert "spawnable_workflow_types" in exc.value.path


def test_self_spawn_is_allowed_even_when_not_in_known():
    b = _base_brief()
    # known_workflow_types is empty; vendor-kyc is allowed because it's
    # the brief's own workflow_type (forward-declaration of self-spawn).
    validator.validate(b, known_workflow_types=set())


def test_two_kinds_in_one_trigger_raises():
    b = _base_brief()
    b["ambient"]["triggers"] = [
        {"kind": "bus", "event_type": "workflow.completed",
         "cron": "0 0 * * *"},  # cron belongs to cadence
    ]
    with pytest.raises(validator.SchemaError) as exc:
        validator.validate(b, known_workflow_types={"vendor-kyc"})
    assert "ambient.triggers[0]" in exc.value.path


def test_ambient_function_must_match_brief_function():
    b = _base_brief()
    b["ambient"]["function"] = "hr"
    with pytest.raises(validator.SchemaError) as exc:
        validator.validate(b, known_workflow_types={"vendor-kyc"})
    assert exc.value.path == "ambient.function"


def test_render_ambient_produces_sentinel_block():
    b = _base_brief()
    file_path, block = codegen.render_ambient(b)
    assert file_path.name == "finance.py"
    assert "compose-domain:ambient:vendor-kyc BEGIN" in block
    assert "compose-domain:ambient:vendor-kyc END" in block
    assert "VendorRiskWatcher" in block
    assert 'hasattr(_module, "AmbientAgent")' in block


def test_apply_ambient_idempotent(tmp_path):
    b = _base_brief()
    p1 = codegen.apply_ambient(b, tmp_path)
    text1 = p1.read_text()
    p2 = codegen.apply_ambient(b, tmp_path)
    text2 = p2.read_text()
    assert text1 == text2
    # Sentinel appears exactly once.
    assert text2.count("compose-domain:ambient:vendor-kyc BEGIN") == 1


def test_no_ambient_block_is_optional():
    b = _base_brief()
    b.pop("ambient")
    validator.validate(b)
