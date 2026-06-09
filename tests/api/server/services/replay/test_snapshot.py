from __future__ import annotations

import json
from pathlib import Path

import pytest

from api.server.services.audit_logger import AuditLogger
from api.server.services.kpi_store import KpiStore
from api.server.services.memory.domain_memory import DomainMemory
from api.server.services.memory.fallback_memory import get_fallback_memory
from api.server.services.persona_responder import PersonaDefinition
from api.server.services.replay.snapshot import take_snapshot
from api.server.services.state_store import StateStore
from api.server.state import app_state
from api.shared.types import Exception_, Workflow


@pytest.fixture
def isolated_app_state(tmp_path: Path):
    original_store = app_state.store
    original_audit = app_state.audit
    original_domain_memories = app_state.domain_memories
    had_kpi_store = hasattr(app_state, "kpi_store")
    original_kpi_store = getattr(app_state, "kpi_store", None)

    from api.server.services import persona_responder

    original_personae = dict(persona_responder.PERSONA_DEFINITIONS)

    app_state.store = StateStore()
    app_state.audit = AuditLogger()

    fallback = get_fallback_memory()
    domain = "replay-test"
    memory_store = DomainMemory(domain=domain, memory=fallback)
    memory_store.delete_all()
    app_state.domain_memories = {domain: memory_store}

    app_state.kpi_store = KpiStore(tmp_path / "kpis.sqlite")

    persona_responder.PERSONA_DEFINITIONS.clear()
    persona_responder.PERSONA_DEFINITIONS["controller"] = PersonaDefinition(
        role="controller",
        description="Replay snapshot test controller persona.",
        workflow_label="Finance Compliance",
        external_event="controller_approval",
        decide=lambda context: {"decision": "approve"},
        skill_path=tmp_path / "controller" / "SKILL.md",
        personality={"risk_appetite": "medium", "thoroughness": "high", "escalation_style": "direct"},
    )

    try:
        yield {
            "domain": domain,
            "memory_store": memory_store,
        }
    finally:
        memory_store.delete_all()
        app_state.store = original_store
        app_state.audit = original_audit
        app_state.domain_memories = original_domain_memories
        if had_kpi_store:
            app_state.kpi_store = original_kpi_store
        else:
            delattr(app_state, "kpi_store")
        persona_responder.PERSONA_DEFINITIONS.clear()
        persona_responder.PERSONA_DEFINITIONS.update(original_personae)


def test_take_snapshot_writes_expected_json_files(tmp_path: Path, isolated_app_state):
    workflow = Workflow(
        id="wf-snapshot-001",
        type="expense-claim",
        status="awaiting_hitl",
        current_phase="Audit",
        created_at=1_716_399_200.0,
        sla_due_at=1_716_485_600.0,
        jurisdiction="London-Zava",
        agency="Zava",
        payload={"amount": 1200, "persona": "controller"},
    )
    app_state.store.upsert_workflow(workflow)

    exception = Exception_(
        id="exc-snapshot-001",
        workflow_id=workflow.id,
        composed_by="deterministic",
        severity="high",
        category="threshold-exceeded",
        summary="Needs controller review.",
        recommendation="Escalate for approval.",
        created_at=1_716_399_260.0,
    )
    app_state.store.upsert_exception(exception)

    memory_store = isolated_app_state["memory_store"]
    memory_store.add(
        "Controller asked for supporting evidence.",
        agent_skill="persona:controller",
        workflow_id=workflow.id,
    )
    memory_store.add_distilled(
        "High-value claims should carry supporting evidence before controller review.",
        metadata={"consolidated_at": "2026-05-22T10:00:00Z", "source": "dream-consolidation"},
    )

    app_state.audit.log("workflow.created", {"workflow_id": workflow.id})
    app_state.audit.log("exception.raised", {"workflow_id": workflow.id})

    app_state.kpi_store.publish("finance", "dso", 41.2, "2026-05", schema_version=1)

    written = take_snapshot(tmp_path)

    expected_names = [
        "workflows.json",
        "phases.json",
        "exceptions.json",
        "personae.json",
        "functions.json",
        "memories.json",
        "lessons.json",
        "kpis.json",
        "audit_summary.json",
        "audit_entries.json",
        "dream_history.json",
        "spans.json",
        "mcp_calls.json",
    ]
    assert [path.name for path in written] == expected_names

    payloads: dict[str, object] = {}
    for name in expected_names:
        path = tmp_path / name
        assert path.exists(), name
        payloads[name] = json.loads(path.read_text())

    workflows = payloads["workflows.json"]
    assert isinstance(workflows, list)
    assert any(item["id"] == workflow.id and item["currentPhase"] == "Audit" for item in workflows)

    exceptions = payloads["exceptions.json"]
    assert isinstance(exceptions, list)
    assert any(item["id"] == exception.id and item["workflowId"] == workflow.id for item in exceptions)

    personae = payloads["personae.json"]
    assert personae["total"] >= 1
    assert any(
        item["role"] == "controller"
        and item["description"] == "Replay snapshot test controller persona."
        and item["external_event_default"] == "controller_approval"
        for item in personae["items"]
    )

    functions = payloads["functions.json"]
    assert isinstance(functions, list)
    assert any(item["name"] == "finance" for item in functions)

    memories = payloads["memories.json"]
    assert any(item["workflow_id"] == workflow.id for item in memories["items"])

    lessons = payloads["lessons.json"]
    assert any("supporting evidence" in item["memory"] for item in lessons["items"])

    kpis = payloads["kpis.json"]
    assert isinstance(kpis["values"], list)
    assert any(row["metric"] == "dso" and row["function"] == "finance" for row in kpis["values"])

    audit_summary = payloads["audit_summary.json"]
    assert audit_summary["total"] == 2
    assert audit_summary["by_action"] == {
        "workflow.created": 1,
        "exception.raised": 1,
    }
