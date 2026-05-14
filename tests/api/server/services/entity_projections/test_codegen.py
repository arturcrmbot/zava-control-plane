"""Tests for author-entity-projection codegen + validator (TASK-013).

The codegen + validator live under
``docs/superpowers/skills/compose-domain/sub-skills/author-entity-projection/``
which uses hyphens — not importable directly. We load via importlib.
"""
from __future__ import annotations

import ast
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
    / "author-entity-projection"
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
    "compose_domain_v4__author_entity_projection__codegen",
    SUB_SKILL_DIR / "codegen.py",
)
validator = _load(
    "compose_domain_v4__author_entity_projection__validator",
    SUB_SKILL_DIR / "validator.py",
)


@pytest.fixture
def synthetic_brief():
    return {
        "domain": {
            "workflow_type": "purchase-card",
            "prefix": "fleet",
            "display_name": "Purchase card",
        },
        "phases": [
            {"name": "intake", "kind": "deterministic"},
            {"name": "manager_signoff", "kind": "hitl",
             "persona": "manager", "external_event": "manager_signoff_decision"},
        ],
        "entities": [
            {
                "kind": "Money",
                "source": "purchase-card",
                "ref_field": "payload.txn_id",
                "attributes": {"amount": "payload.amount", "currency": "payload.currency"},
            },
            {
                "kind": "Person",
                "source": "cardholder",
                "ref_field": "payload.employee_id",
                "relations": [
                    {"kind": "TRANSACTS", "target_ref": "payload.txn_id"},
                ],
            },
        ],
    }


def test_render_returns_underscored_filename(synthetic_brief):
    fname, body = codegen.render_projection(synthetic_brief)
    assert fname == "purchase_card.py"
    assert isinstance(body, str)


def test_render_body_imports_and_signature(synthetic_brief):
    _, body = codegen.render_projection(synthetic_brief)
    # Must compile.
    tree = ast.parse(body)
    # Has module-level WORKFLOW_TYPE assignment.
    has_wt = any(
        isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "WORKFLOW_TYPE" for t in n.targets)
        for n in tree.body
    )
    assert has_wt
    # Imports the right symbols.
    imports = [n for n in tree.body if isinstance(n, ast.ImportFrom)]
    import_modules = {i.module for i in imports}
    assert "api.server.services.entity_projections" in import_modules
    assert "api.shared.types" in import_modules
    # bare `def project(workflow)` exists.
    project_fns = [
        n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "project"
    ]
    assert len(project_fns) == 1
    assert [a.arg for a in project_fns[0].args.args] == ["workflow"]


def test_render_body_executes_against_workflow(synthetic_brief):
    """Smoke-execute the rendered module against a Workflow instance."""
    _, body = codegen.render_projection(synthetic_brief)
    # Inject the rendered module into a namespace and import sister
    # symbols from the live tree.
    ns: dict = {}
    exec(compile(body, "<rendered>", "exec"), ns)
    project = ns["project"]

    from api.shared.types import Workflow
    wf = Workflow(
        id="PC-001", type="purchase-card", current_phase="Intake",
        created_at=0, sla_due_at=86400, jurisdiction="L", agency="Z",
        payload={
            "txn_id": "T-1", "amount": 42.0, "currency": "USD",
            "employee_id": "E-1",
        },
    )
    ops = project(wf)
    from api.server.services.entity_graph import EntityWrite, RelWrite

    money_writes = [
        o for o in ops if isinstance(o, EntityWrite) and o.kind == "Money"
    ]
    person_writes = [
        o for o in ops if isinstance(o, EntityWrite) and o.kind == "Person"
    ]
    rels = [o for o in ops if isinstance(o, RelWrite)]

    assert len(money_writes) == 1
    assert money_writes[0].id == "MONEY-purchase-card-t-1"
    assert money_writes[0].attrs["amount"] == "42.0"
    assert len(person_writes) == 1
    assert person_writes[0].id == "PERSON-cardholder-e-1"
    assert len(rels) == 1
    assert rels[0].rel == "TRANSACTS"
    assert rels[0].src_id == "PERSON-cardholder-e-1"
    assert rels[0].dst_id == "MONEY-purchase-card-t-1"


def test_unknown_kind_raises(synthetic_brief):
    synthetic_brief["entities"][0]["kind"] = "Foo"
    with pytest.raises(validator.SchemaError) as exc:
        validator.validate(synthetic_brief)
    assert exc.value.path == "entities[0].kind"


def test_unknown_rel_raises(synthetic_brief):
    synthetic_brief["entities"][1]["relations"][0]["kind"] = "FOOS"
    with pytest.raises(validator.SchemaError) as exc:
        validator.validate(synthetic_brief)
    assert "relations[0].kind" in exc.value.path


def test_ref_field_not_in_orchestrator_raises(synthetic_brief, tmp_path):
    """Provide a synthetic orchestrator file that touches only one ref;
    a brief with an unresolved ref_field must raise."""
    orch = tmp_path / "fleet_purchase_card.py"
    orch.write_text(
        "def f(input_dict):\n"
        "    payload = input_dict\n"
        "    payload.get('txn_id')\n"
    )
    # Strip the second entity's payload.employee_id so we trigger
    # the unresolved-ref code path.
    synthetic_brief["entities"][1]["ref_field"] = "payload.unknown_path"
    synthetic_brief["entities"][1]["relations"] = []
    with pytest.raises(validator.SchemaError) as exc:
        validator.validate(synthetic_brief, orch)
    assert exc.value.path == "entities[1].ref_field"
