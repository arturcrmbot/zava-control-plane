from __future__ import annotations


def test_fresh_agency_bootstrap_provides_budget_context_without_fake_workflows(tmp_path):
    from types import SimpleNamespace
    from api.server.services.entity_graph import EntityGraph
    from verticals.agency.lifecycle import bootstrap
    from verticals.agency.aurora import observe_budget_signal

    graph = EntityGraph(tmp_path / "fresh-agency.kuzu")
    try:
        bootstrap(SimpleNamespace(entities=graph))
        result = observe_budget_signal(graph, workflow_id="AUR-FRESH")
        assert result["brand_id"] == "BRAND-aurora"
        assert result["annual_budget_gbp"] > 0
        assert result["after_pct"] >= 1
        assert graph.query(
            "MATCH (w:Workflow) WHERE w.workflow_type = 'aurora-budget-response' RETURN w.id AS id"
        ) == []
    finally:
        graph.close()


def test_agency_registers_real_aurora_domain_and_pack_owned_skill():
    from api.shared.domains import DOMAINS
    from api.server.state import app_state

    domain = DOMAINS["aurora-budget-response"]
    assert domain.workflow_id_prefix == "AUR"
    assert domain.orchestrator_name == "AuroraBudgetResponseOrchestrator"
    assert [phase.kind for phase in domain.phases] == [
        "deterministic",
        "agent",
        "hitl",
        "deterministic",
        "sub_orchestrator",
        "deterministic",
    ]
    assert domain.hitl_gates[0].operator_only is True
    assert "aurora-budget-recommender" in domain.skills
    assert any(
        root.name == "skills" and root.parent.name == "agency"
        for root in app_state.runtime.pack.skill_roots
    )
    assert "AuroraBudgetResponseOrchestrator" in (
        app_state.runtime.pack.durable_functions.orchestrators
    )


def test_aurora_skill_omits_the_unused_tool_allowlist():
    from pathlib import Path

    import yaml

    skill = (
        Path(__file__).resolve().parents[3]
        / "verticals/agency/skills/aurora-budget-recommender/SKILL.md"
    )
    metadata = yaml.safe_load(skill.read_text().split("---", 2)[1])

    assert "allowed-tools" not in metadata, (
        "Omit an unused allowlist: null breaks Copilot discovery and [] is "
        "treated as a tool name by the pack loader"
    )


def test_agency_functions_app_registers_aurora_orchestrator_and_activities():
    from verticals.agency.durable import app

    registered = {function.get_function_name() for function in app.get_functions()}
    assert {
        "AuroraBudgetResponseOrchestrator",
        "aurora_observe_budget_activity_trigger",
        "aurora_recommendation_activity_trigger",
        "aurora_apply_policy_activity_trigger",
        "aurora_synthesise_activity_trigger",
    } <= registered


def test_agency_workflow_detail_exposes_only_recorded_aurora_evidence():
    from types import SimpleNamespace

    from verticals.agency.detail import workflow_detail

    workflow = SimpleNamespace(
        id="AUR-DETAIL-1",
        type="aurora-budget-response",
        orchestration_instance_id="aurora-instance-detail",
        status="awaiting_hitl",
        current_phase="Executive approval",
        payload={
            "request_id": "request-detail",
            "brand_id": "BRAND-aurora",
            "count": 2,
            "outputs": {
                "observation": {"signal_id": "signal-real"},
                "recommendation": {"recommendation": "freeze"},
            },
            "hitl_context": {
                "decision_id": "EXC-REAL-1",
                "operator_only": True,
            },
        },
        metadata={},
    )
    state = SimpleNamespace(
        store=SimpleNamespace(
            get_phases=lambda _wid: [],
            get_agent_reasoning=lambda _wid: [{"agent_label": "aurora-budget-recommender"}],
        ),
        orchestration_history={
            "AUR-DETAIL-1": [{"kind": "suspended", "payload": {"phase": "Executive approval"}}]
        },
    )

    detail = workflow_detail(workflow, state)

    assert detail["workflow_id"] == "AUR-DETAIL-1"
    assert detail["trigger"]["request_id"] == "request-detail"
    assert detail["outputs"]["observation"]["signal_id"] == "signal-real"
    assert detail["outputs"]["policy"] is None
    assert detail["children"] == []
    assert detail["hitl"]["decision_id"] == "EXC-REAL-1"
    assert detail["agent_reasoning"][0]["agent_label"] == "aurora-budget-recommender"
