from __future__ import annotations

from api.server.services.entity_graph import RelWrite, _REL_TABLES
from api.shared.types import Workflow
from verticals.telco.projections import TELCO_PROJECTIONS


def _workflow(workflow_type: str, observation_key: str, observation: dict) -> Workflow:
    return Workflow.model_construct(
        id=f"WF-{workflow_type}",
        type=workflow_type,
        status="in_progress",
        current_phase="Intake",
        created_at=0.0,
        sla_due_at=1.0,
        jurisdiction="GB",
        agency="Zava",
        payload={
            observation_key: observation,
            "decision": {
                "command": {
                    "payload": {
                        "account_id": observation.get("account", {}).get("id"),
                        "offer_kind": "service_recovery_bundle",
                        "value_gbp": 75.0,
                    }
                }
            },
        },
    )


def _rels(workflow: Workflow) -> set[str]:
    return {
        operation.rel
        for operation in TELCO_PROJECTIONS[workflow.type](workflow)
        if isinstance(operation, RelWrite)
    }


def test_all_six_expansion_projections_load():
    workflows = (
        _workflow(
            "outage-risk-management",
            "weather_risk",
            {
                "at_risk_assets": [
                    {
                        "id": "AST-SITE-10-radio-unit",
                        "site_id": "SITE-10",
                        "kind": "radio-unit",
                    }
                ]
            },
        ),
        _workflow(
            "predictive-site-maintenance",
            "asset_failure_risk",
            {
                "asset": {
                    "id": "AST-SITE-10-radio-unit",
                    "site_id": "SITE-10",
                    "kind": "radio-unit",
                },
                "site": {"id": "SITE-10"},
            },
        ),
        _workflow(
            "field-repair-dispatch",
            "work_order",
            {
                "work_order": {
                    "id": "WO-00001",
                    "asset_id": "AST-SITE-10-radio-unit",
                    "required_spare": "radio-unit",
                },
                "asset": {"id": "AST-SITE-10-radio-unit"},
                "site": {"id": "SITE-10"},
                "dispatchable_technicians": [{"id": "TECH-WEST-01"}],
                "spare_stock": {"id": "SPARE-WEST-RADIO-UNIT"},
            },
        ),
        _workflow(
            "capacity-optimization",
            "site_congestion",
            {"site": {"id": "SITE-10", "utilization": 0.95}},
        ),
        _workflow(
            "service-ticket-resolution",
            "ticket_pressure",
            {
                "tickets": [
                    {
                        "id": "TKT-000001",
                        "subscription_id": "SUBS-00002",
                        "account_id": "ACC-00002",
                    }
                ],
                "accounts": [{"id": "ACC-00002", "segment": "consumer"}],
            },
        ),
        _workflow(
            "retention-orchestration",
            "churn_risk",
            {"account": {"id": "ACC-00002", "segment": "consumer"}},
        ),
    )

    for workflow in workflows:
        assert TELCO_PROJECTIONS[workflow.type](workflow)


def test_expansion_projections_emit_connected_telco_relationships():
    maintenance = _workflow(
        "predictive-site-maintenance",
        "asset_failure_risk",
        {
            "asset": {
                "id": "AST-SITE-10-radio-unit",
                "site_id": "SITE-10",
                "kind": "radio-unit",
            },
            "site": {"id": "SITE-10"},
        },
    )
    field = _workflow(
        "field-repair-dispatch",
        "work_order",
        {
            "work_order": {
                "id": "WO-00001",
                "asset_id": "AST-SITE-10-radio-unit",
                "required_spare": "radio-unit",
            },
            "asset": {"id": "AST-SITE-10-radio-unit"},
            "site": {"id": "SITE-10"},
            "dispatchable_technicians": [{"id": "TECH-WEST-01"}],
            "spare_stock": {"id": "SPARE-WEST-RADIO-UNIT"},
        },
    )
    ticket = _workflow(
        "service-ticket-resolution",
        "ticket_pressure",
        {
            "tickets": [
                {
                    "id": "TKT-000001",
                    "subscription_id": "SUBS-00002",
                    "account_id": "ACC-00002",
                }
            ],
            "accounts": [{"id": "ACC-00002", "segment": "consumer"}],
        },
    )
    retention = _workflow(
        "retention-orchestration",
        "churn_risk",
        {"account": {"id": "ACC-00002", "segment": "consumer"}},
    )

    assert "ASSET_AT_SITE" in _rels(maintenance)
    assert {
        "WORK_FOR_ASSET",
        "ASSIGNED_TO",
        "REQUIRES_SPARE",
    } <= _rels(field)
    assert "TICKET_FOR_SERVICE" in _rels(ticket)
    assert "OFFER_FOR_ACCOUNT" in _rels(retention)


def test_entity_graph_registers_telco_expansion_relationship_tables():
    registered = {name for name, _ddl in _REL_TABLES}

    assert {
        "ASSET_AT_SITE",
        "WORK_FOR_ASSET",
        "ASSIGNED_TO",
        "REQUIRES_SPARE",
        "TICKET_FOR_SERVICE",
        "OFFER_FOR_ACCOUNT",
    } <= registered
