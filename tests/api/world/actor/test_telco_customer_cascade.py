from __future__ import annotations

from api.functions.activities.telco_cascade import telco_cascade_decision
from api.server.world.model import SimulationCommand
from api.server.world.runtime import SimulationRuntime
from verticals.telco.world import NetworkConfig, NetworkScenario


def _scenario(seed: int = 51) -> NetworkScenario:
    runtime = SimulationRuntime(seed)
    scenario = NetworkScenario(
        runtime,
        NetworkConfig(
            site_count=12,
            subscriber_count=200,
            session_count=240,
            site_capacity_mbps=600.0,
            simulation_minutes=30.0,
        ),
    )
    scenario.install()
    return scenario


def _fail_vulnerable_customer_site(scenario: NetworkScenario):
    scenario.inject_site_failure("SITE-02")
    scenario.runtime.run_until(0.0)
    return next(
        event
        for event in scenario.runtime.journal
        if event.type == "sensor.tripped"
        and event.actor_id == "sensor:ticket_pressure"
    )


def _command(
    command_id: str,
    command_type: str,
    payload: dict,
    *,
    trace_id: str,
) -> SimulationCommand:
    return SimulationCommand(
        command_id=command_id,
        trace_id=trace_id,
        issued_by="customer_care",
        type=command_type,
        payload=payload,
    )


def _events(scenario: NetworkScenario, event_type: str):
    return [event for event in scenario.runtime.journal if event.type == event_type]


def test_ticket_and_retention_agents_complete_the_customer_story():
    scenario = _scenario()
    ticket_sensor = _fail_vulnerable_customer_site(scenario)
    ticket_observation = scenario.build_observation(
        ticket_sensor.to_dict(),
        now=scenario.runtime.now,
    )
    ticket_decision = telco_cascade_decision(
        {
            "agent_mode": "deterministic",
            "workflow_id": "WF-TICKET",
            "trace_id": ticket_sensor.trace_id,
            "type": "service-ticket-resolution",
            "phase": "Correlate Root Cause",
            "observation": ticket_observation,
        }
    )
    assert ticket_decision["requires_approval"] is True
    ticket_decision["command"]["payload"]["approval_decision"] = "approve"
    scenario.apply_command(SimulationCommand(**ticket_decision["command"]))

    churn_sensor = next(
        event
        for event in _events(scenario, "sensor.tripped")
        if event.actor_id == "sensor:churn_risk"
    )
    retention_observation = scenario.build_observation(
        churn_sensor.to_dict(),
        now=scenario.runtime.now,
    )
    analysis = telco_cascade_decision(
        {
            "agent_mode": "deterministic",
            "workflow_id": "WF-RETENTION",
            "trace_id": churn_sensor.trace_id,
            "type": "retention-orchestration",
            "phase": "Analyse Churn Drivers",
            "observation": retention_observation,
        }
    )
    offer = telco_cascade_decision(
        {
            "agent_mode": "deterministic",
            "workflow_id": "WF-RETENTION",
            "trace_id": churn_sensor.trace_id,
            "type": "retention-orchestration",
            "phase": "Select Retention Offer",
            "observation": retention_observation,
            "prior_decision": analysis,
        }
    )
    assert offer["requires_approval"] is True
    offer["command"]["payload"]["approval_decision"] = "approve"
    scenario.apply_command(SimulationCommand(**offer["command"]))

    assert _events(scenario, "ticket_batch.resolved")
    assert _events(scenario, "retention_offer.issued")
    assert ticket_sensor.trace_id == churn_sensor.payload["parent_trace_id"]


def test_network_incident_opens_tickets_and_customer_experience_evidence():
    scenario = _scenario()

    ticket_sensor = _fail_vulnerable_customer_site(scenario)

    failed = _events(scenario, "site.failed")[-1]
    assert scenario.tickets
    assert scenario.experience_episodes
    assert any(ticket.account_id == "ACC-00002" for ticket in scenario.tickets.values())
    assert any(
        episode.account_id == "ACC-00002"
        for episode in scenario.experience_episodes.values()
    )
    assert ticket_sensor.cause_event_id in {
        event.event_id for event in _events(scenario, "ticket.opened")
    }
    assert ticket_sensor.trace_id != failed.trace_id
    assert ticket_sensor.payload["parent_trace_id"] == failed.trace_id


def test_ticket_pressure_observation_contains_real_tickets_and_accounts():
    scenario = _scenario()
    ticket_sensor = _fail_vulnerable_customer_site(scenario)

    observation = scenario.build_observation(
        ticket_sensor.to_dict(),
        now=scenario.runtime.now,
    )

    assert observation["tickets"]
    assert observation["accounts"]
    assert any(account["vulnerable"] for account in observation["accounts"])
    assert observation["incident_site"]["id"] == "SITE-02"
    assert observation["allowed_commands"] == ["resolve_ticket_batch"]


def test_ticket_batch_requires_review_for_vulnerable_customer():
    scenario = _scenario()
    ticket_sensor = _fail_vulnerable_customer_site(scenario)
    ticket_ids = sorted(scenario.tickets)
    payload = {
        "ticket_ids": ticket_ids,
        "root_cause": "network_site_failure",
        "resolution": "Restored service and confirmed account impact.",
    }

    rejected = scenario.apply_command(
        _command(
            "cmd-ticket-denied",
            "resolve_ticket_batch",
            payload,
            trace_id=ticket_sensor.trace_id,
        )
    )
    assert rejected.type == "command.rejected"

    accepted = scenario.apply_command(
        _command(
            "cmd-ticket-approved",
            "resolve_ticket_batch",
            {**payload, "approval_decision": "approve"},
            trace_id=ticket_sensor.trace_id,
        )
    )
    assert accepted.type == "command.accepted"
    assert all(ticket.status == "resolved" for ticket in scenario.tickets.values())
    resolved = _events(scenario, "ticket_batch.resolved")[-1]
    assert resolved.trace_id == ticket_sensor.trace_id


def test_ticket_resolution_opens_one_customer_retention_trace():
    scenario = _scenario()
    ticket_sensor = _fail_vulnerable_customer_site(scenario)
    scenario.apply_command(
        _command(
            "cmd-ticket-retention",
            "resolve_ticket_batch",
            {
                "ticket_ids": sorted(scenario.tickets),
                "root_cause": "network_site_failure",
                "resolution": "Restored service and confirmed account impact.",
                "approval_decision": "approve",
            },
            trace_id=ticket_sensor.trace_id,
        )
    )

    churn_sensors = [
        event
        for event in _events(scenario, "sensor.tripped")
        if event.actor_id == "sensor:churn_risk"
    ]
    assert len(churn_sensors) == 1
    churn_sensor = churn_sensors[0]
    assert churn_sensor.target_id == "ACC-00002"
    assert churn_sensor.trace_id != ticket_sensor.trace_id
    assert churn_sensor.payload["parent_trace_id"] == ticket_sensor.trace_id
    assert ticket_sensor.trace_id in churn_sensor.payload["contributing_trace_ids"]


def test_churn_observation_and_retention_offer_use_real_account_history():
    scenario = _scenario()
    ticket_sensor = _fail_vulnerable_customer_site(scenario)
    scenario.apply_command(
        _command(
            "cmd-ticket-history",
            "resolve_ticket_batch",
            {
                "ticket_ids": sorted(scenario.tickets),
                "root_cause": "network_site_failure",
                "resolution": "Restored service and confirmed account impact.",
                "approval_decision": "approve",
            },
            trace_id=ticket_sensor.trace_id,
        )
    )
    churn_sensor = next(
        event
        for event in _events(scenario, "sensor.tripped")
        if event.actor_id == "sensor:churn_risk"
    )

    observation = scenario.build_observation(
        churn_sensor.to_dict(),
        now=scenario.runtime.now,
    )
    assert observation["account"]["id"] == "ACC-00002"
    assert observation["account"]["vulnerable"] is True
    assert observation["experience_episodes"]
    assert observation["allowed_commands"] == ["apply_retention_offer"]

    rejected = scenario.apply_command(
        _command(
            "cmd-retention-denied",
            "apply_retention_offer",
            {
                "account_id": "ACC-00002",
                "reason": "Repeated outage impact",
                "value_gbp": 75.0,
                "offer_kind": "service_recovery_bundle",
            },
            trace_id=churn_sensor.trace_id,
        )
    )
    assert rejected.type == "command.rejected"

    accepted = scenario.apply_command(
        _command(
            "cmd-retention-approved",
            "apply_retention_offer",
            {
                "account_id": "ACC-00002",
                "reason": "Repeated outage impact",
                "value_gbp": 75.0,
                "offer_kind": "service_recovery_bundle",
                "approval_decision": "approve",
            },
            trace_id=churn_sensor.trace_id,
        )
    )
    assert accepted.type == "command.accepted"
    offer = next(iter(scenario.retention_offers.values()))
    assert offer.account_id == "ACC-00002"
    assert offer.status == "issued"
    issued = _events(scenario, "retention_offer.issued")[-1]
    assert issued.trace_id == churn_sensor.trace_id
