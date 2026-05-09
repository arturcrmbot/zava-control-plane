"""Tests for compose-domain v4 sub_orchestrator codegen (TASK-022).

Exercises :mod:`docs.superpowers.skills.compose-domain.sub-skills.
author-domain-skeleton.codegen` against synthetic briefs:

* Single ``kind: sub_orchestrator`` phase emits ``call_sub_orchestrator``.
* Two same-``parallel_group`` entries collapse into one ``task_all``.
* Each sub-call is preceded by a ``workflow.sub_spawned`` audit
  checkpoint (SEC-002).
* Output parses cleanly via :func:`ast.parse`.
* Round-trip emits a precedent .cypher file per HITL phase, skipping
  pre-existing files.
"""
from __future__ import annotations

import ast

import pytest


@pytest.fixture
def codegen(sub_skill_loader):
    return sub_skill_loader("author-domain-skeleton", "codegen")


@pytest.fixture
def validator(sub_skill_loader):
    return sub_skill_loader("author-domain-skeleton", "validator")


@pytest.fixture
def single_sub_brief():
    return {
        "domain": {
            "workflow_type": "hire-to-productive",
            "prefix": "fleet",
            "display_name": "Hire to Productive",
        },
        "phases": [
            {"name": "fetch_joiner", "kind": "agent",
             "agent_skill_name": "joiner-fetcher"},
            {
                "name": "grant_access", "kind": "sub_orchestrator",
                "target_workflow_type": "it-access-request",
                "target_orchestrator": "FleetItAccessRequestOrchestrator",
                "payload_from": "python:{'employee_id': input_dict['employee_id']}",
            },
            {"name": "manager_signoff", "kind": "hitl",
             "persona": "hr_bp", "external_event": "manager_signoff_decision"},
        ],
    }


@pytest.fixture
def parallel_brief():
    return {
        "domain": {
            "workflow_type": "vendor-risk-to-pay",
            "prefix": "fleet",
            "display_name": "Vendor risk to pay",
        },
        "phases": [
            {"name": "fetch_vendor", "kind": "agent",
             "agent_skill_name": "vendor-fetcher"},
            {
                "name": "kyc", "kind": "sub_orchestrator",
                "target_workflow_type": "vendor-kyc",
                "target_orchestrator": "FleetVendorKycOrchestrator",
                "payload_from": "MATCH (v:Organisation {id: $vid}) RETURN v",
            },
            {
                "name": "ap", "kind": "sub_orchestrator",
                "target_workflow_type": "ap-invoice",
                "target_orchestrator": "FleetApInvoiceOrchestrator",
                "parallel_group": "pay",
                "payload_from": "python:{'invoice_id': input_dict['invoice_id']}",
            },
            {
                "name": "fx", "kind": "sub_orchestrator",
                "target_workflow_type": "treasury-fx",
                "target_orchestrator": "FleetTreasuryFxOrchestrator",
                "parallel_group": "pay",
                "payload_from": "python:{'invoice_id': input_dict['invoice_id']}",
            },
            {"name": "release", "kind": "hitl",
             "persona": "cfo", "external_event": "payment_release_decision"},
        ],
    }


def test_render_filename(codegen, single_sub_brief):
    assert codegen.render_filename(single_sub_brief) == "hire_to_productive.py"


def test_derive_classname(codegen):
    assert (
        codegen.derive_orchestrator_classname("vendor-kyc", "fleet")
        == "FleetVendorKycOrchestrator"
    )
    # Prefix already contained in the workflow_type — don't double up.
    assert (
        codegen.derive_orchestrator_classname("fleet-purchase-card", "fleet")
        == "FleetPurchaseCardOrchestrator"
    )


def test_single_sub_orchestrator_emits_call(codegen, single_sub_brief):
    body = codegen.render_orchestrator(single_sub_brief)
    ast.parse(body)
    assert "call_sub_orchestrator(\"FleetItAccessRequestOrchestrator\"" in body
    # HITL still emits wait_for_external_event.
    assert "wait_for_external_event(\"manager_signoff_decision\")" in body
    # Audit checkpoint stamped before the sub-call (SEC-002).
    assert "workflow.sub_spawned" in body
    # Function name uses snake_case workflow_type.
    assert "def hire_to_productive_orchestration(" in body


def test_parallel_group_collapses_to_task_all(codegen, parallel_brief):
    body = codegen.render_orchestrator(parallel_brief)
    ast.parse(body)
    assert "context.task_all([" in body
    # Both members appear inside the task_all batch.
    assert "FleetApInvoiceOrchestrator" in body
    assert "FleetTreasuryFxOrchestrator" in body
    # The non-grouped sub-call stays a singleton call_sub_orchestrator.
    assert "call_sub_orchestrator(\"FleetVendorKycOrchestrator\"" in body
    # Two audit checkpoints for the two grouped children.
    assert body.count("workflow.sub_spawned") >= 3


def test_validator_accepts_sub_orchestrator(validator, single_sub_brief):
    validator.validate(single_sub_brief)


def test_validator_rejects_sub_without_target(validator, single_sub_brief):
    bad = single_sub_brief
    bad["phases"][1].pop("target_workflow_type")
    with pytest.raises(validator.SchemaError) as exc:
        validator.validate(bad)
    assert "target_workflow_type" in exc.value.path


def test_validator_rejects_sub_without_payload(validator, single_sub_brief):
    bad = single_sub_brief
    bad["phases"][1].pop("payload_from")
    with pytest.raises(validator.SchemaError) as exc:
        validator.validate(bad)
    assert "payload_from" in exc.value.path


def test_emit_precedent_files_creates_per_hitl(codegen, single_sub_brief, tmp_path):
    paths = codegen.emit_precedent_files(single_sub_brief, tmp_path)
    assert len(paths) == 1
    body = paths[0].read_text()
    assert "MATCH (d:Decision)-[:DECIDED_ON]->" in body
    assert "d.persona_role = 'hr_bp'" in body
    assert "d.workflow_type = 'hire-to-productive'" in body
    assert paths[0].name == "hire-to-productive_manager_signoff.cypher"


def test_emit_precedent_files_does_not_overwrite(codegen, single_sub_brief, tmp_path):
    target = tmp_path / "hire-to-productive_manager_signoff.cypher"
    target.write_text("// hand-edited by domain author\n")
    paths = codegen.emit_precedent_files(single_sub_brief, tmp_path)
    assert paths == [], "compose-v4 must not overwrite existing precedent files"
    assert target.read_text() == "// hand-edited by domain author\n"
