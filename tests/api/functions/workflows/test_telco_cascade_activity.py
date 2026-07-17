from __future__ import annotations

from api.functions.activities import telco_cascade


def _base_payload(workflow_type: str, observation: dict) -> dict:
    return {
        "agent_mode": "deterministic",
        "workflow_id": "WF-TELCO-001",
        "trace_id": f"trace-{workflow_type}",
        "type": workflow_type,
        "phase": "Agent Decision",
        "observation": observation,
    }


def test_outage_decision_builds_prestage_command_from_real_resources():
    payload = _base_payload(
        "outage-risk-management",
        {
            "weather_event": {"region": "west", "severity": 1.2},
            "available_technicians": [
                {"id": "TECH-WEST-02", "status": "available"},
                {"id": "TECH-WEST-01", "status": "available"},
            ],
            "spare_stocks": [
                {"part_kind": "radio-unit", "quantity": 0},
                {"part_kind": "power", "quantity": 15},
            ],
        },
    )

    result = telco_cascade.telco_cascade_decision(payload)

    assert result["command"]["type"] == "prestage_field_resources"
    assert result["command"]["payload"]["region"] == "west"
    assert result["command"]["payload"]["technician_ids"] == [
        "TECH-WEST-01",
        "TECH-WEST-02",
    ]
    assert result["command"]["payload"]["spare_part_kinds"] == ["power"]
    assert result["requires_approval"] is False


def test_critical_asset_replacement_requires_delivery_approval():
    payload = _base_payload(
        "predictive-site-maintenance",
        {
            "asset": {
                "id": "AST-SITE-04-radio-unit",
                "risk_band": "critical",
                "failure_probability": 0.9,
            },
            "site": {"id": "SITE-04"},
        },
    )

    result = telco_cascade.telco_cascade_decision(payload)

    assert result["command"]["type"] == "create_maintenance_work_order"
    assert result["command"]["payload"]["kind"] == "replace"
    assert result["command"]["payload"]["priority"] == 1
    assert result["requires_approval"] is True
    assert result["approval_context"]["request"]["amount"] == 12_000.0


def test_severe_storm_prestage_requires_delivery_approval():
    payload = _base_payload(
        "outage-risk-management",
        {
            "weather_event": {"region": "west", "severity": 2.0},
            "available_technicians": [
                {"id": "TECH-WEST-01", "status": "available"},
                {"id": "TECH-WEST-02", "status": "available"},
            ],
            "spare_stocks": [
                {"part_kind": "power", "quantity": 15},
                {"part_kind": "cooling", "quantity": 15},
            ],
        },
    )

    result = telco_cascade.telco_cascade_decision(payload)

    assert result["requires_approval"] is True
    assert result["approval_context"]["request"]["amount"] > 10_000.0


def test_field_decision_uses_cross_region_spare_as_an_approved_exception():
    payload = _base_payload(
        "field-repair-dispatch",
        {
            "work_order": {
                "id": "WO-00001",
                "kind": "repair",
                "required_spare": "radio-unit",
            },
            "site": {"id": "SITE-10", "region": "west"},
            "dispatchable_technicians": [
                {"id": "TECH-WEST-01", "status": "available"},
            ],
            "spare_stock": {
                "id": "SPARE-WEST-RADIO-UNIT",
                "region": "west",
                "part_kind": "radio-unit",
                "quantity": 0,
            },
            "alternate_spare_stocks": [
                {
                    "id": "SPARE-NORTH-RADIO-UNIT",
                    "region": "north",
                    "part_kind": "radio-unit",
                    "quantity": 15,
                },
            ],
        },
    )

    result = telco_cascade.telco_cascade_decision(payload)

    command = result["command"]
    assert command["type"] == "dispatch_field_repair"
    assert command["payload"]["source_stock_id"] == "SPARE-NORTH-RADIO-UNIT"
    assert result["requires_approval"] is True


def test_capacity_decision_restores_twenty_percent_headroom():
    payload = _base_payload(
        "capacity-optimization",
        {
            "site": {
                "id": "SITE-04",
                "traffic_mbps": 400.0,
                "capacity_mbps": 421.053,
                "utilization": 0.95,
            },
            "blocked_orders": [{"id": "ORD-00002"}],
        },
    )

    result = telco_cascade.telco_cascade_decision(payload)

    command = result["command"]
    assert command["type"] == "apply_capacity_action"
    assert command["payload"]["action"] == "temporary_capacity"
    projected_capacity = 421.053 + command["payload"]["capacity_increase_mbps"]
    assert 400.0 / projected_capacity <= 0.8
    assert result["requires_approval"] is False


def test_live_decision_uses_the_registered_workflow_skill(monkeypatch):
    captured = {}

    async def fake_run_agent_session(prompt: str, **kwargs):
        captured["prompt"] = prompt
        captured.update(kwargs)
        return {
            "technician_ids": ["TECH-WEST-01"],
            "spare_part_kinds": ["power"],
            "reasoning": "Resources fit the regional storm risk.",
        }

    monkeypatch.setattr(
        telco_cascade,
        "run_agent_session",
        fake_run_agent_session,
    )
    payload = _base_payload(
        "outage-risk-management",
        {
            "weather_event": {"region": "west", "severity": 1.0},
            "available_technicians": [
                {"id": "TECH-WEST-01", "status": "available"},
            ],
            "spare_stocks": [{"part_kind": "power", "quantity": 15}],
        },
    )
    payload["agent_mode"] = "live"

    result = telco_cascade.telco_cascade_decision(payload)

    assert captured["skill_label"] == "outage-risk-planning"
    assert captured["workflow_id"] == "WF-TELCO-001"
    assert captured["skill_dir"].name == "outage-risk-planning"
    assert result["command"]["payload"]["technician_ids"] == ["TECH-WEST-01"]


def test_deterministic_proof_mode_can_be_selected_by_environment(monkeypatch):
    payload = _base_payload(
        "outage-risk-management",
        {
            "weather_event": {"region": "west", "severity": 1.0},
            "available_technicians": [
                {"id": "TECH-WEST-01", "status": "available"},
            ],
            "spare_stocks": [{"part_kind": "power", "quantity": 15}],
        },
    )
    payload.pop("agent_mode")
    monkeypatch.setenv("ZAVA_TELCO_AGENT_MODE", "deterministic")

    result = telco_cascade.telco_cascade_decision(payload)

    assert result["command"]["type"] == "prestage_field_resources"
