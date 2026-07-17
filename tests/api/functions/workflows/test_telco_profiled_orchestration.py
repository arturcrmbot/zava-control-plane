from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from api.functions.activities.telco_profiled import (
    telco_profile_command_activity,
    telco_profile_skill_activity,
)
from api.functions.workflows.telco_profiled import telco_profile_orchestration
from verticals.telco.process_profiles import STANDARD_PROCESS_PROFILES


PROFILE_BY_ENGINE = {
    "DDA": "energy-optimization",
    "FSP": "ran-capacity-planning",
    "CTR": "billing-dispute-resolution",
    "OFV": "service-provisioning-activation",
    "RIG": "revenue-assurance",
    "ARA": "contact-centre-agent-assist",
}


class _Task:
    def __init__(self, result=None):
        self.result = result

    def cancel(self):
        return None


class _Context:
    instance_id = "profile-instance-1"
    current_utc_datetime = datetime(2026, 7, 17)

    def __init__(self, workflow_type: str, approval=None):
        profile = STANDARD_PROCESS_PROFILES[workflow_type]
        self._input = {
            "agent_mode": "deterministic",
            "workflow_id": f"WF-{workflow_type}",
            "trace_id": f"trace-{workflow_type}",
            "type": workflow_type,
            "observation": {
                "case": {
                    "id": "CASE-001",
                    "subject_ids": ["ACTOR-1"],
                    "facts": {"risk_score": 0.8},
                    "allowed_actions": [profile.command_type],
                }
            },
        }
        self.approval = _Task(approval)
        self.timer = _Task()
        self.external_event = None
        self.calls: list[tuple[str, dict]] = []

    def get_input(self):
        return self._input

    def call_activity(self, name, payload):
        self.calls.append((name, payload))
        if name == "telco_profile_skill_activity_trigger":
            return telco_profile_skill_activity(payload)
        if name == "telco_profile_command_activity_trigger":
            return telco_profile_command_activity(payload)
        return {}

    def wait_for_external_event(self, name):
        self.external_event = name
        return self.approval

    def create_timer(self, _deadline):
        return self.timer

    def task_any(self, _tasks):
        return self.approval


def _drive(context: _Context, engine: str) -> dict:
    generator = telco_profile_orchestration(context, engine)
    sent: Any = None
    while True:
        try:
            yielded = generator.send(sent) if sent is not None else next(generator)
        except StopIteration as stop:
            return stop.value
        sent = yielded


@pytest.mark.parametrize("engine,workflow_type", PROFILE_BY_ENGINE.items())
def test_each_engine_returns_its_profile_command(engine, workflow_type):
    profile = STANDARD_PROCESS_PROFILES[workflow_type]
    approval = (
        {"decision": "approve", "persona": profile.hitl_persona}
        if profile.hitl_persona
        else None
    )
    context = _Context(workflow_type, approval=approval)

    result = _drive(context, engine)

    assert result["status"] == "decision_ready"
    assert result["command"]["type"] == profile.command_type
    assert result["observation"]["case"]["id"] == "CASE-001"
    checkpoint_kinds = [
        payload["kind"]
        for name, payload in context.calls
        if name == "checkpoint_activity_trigger"
    ]
    assert checkpoint_kinds[0] == "workflow.started"
    assert "workflow.completed" not in checkpoint_kinds


def test_profile_orchestration_waits_for_declared_persona():
    profile = STANDARD_PROCESS_PROFILES["revenue-assurance"]
    context = _Context(
        profile.workflow_type,
        approval={"decision": "approve", "persona": profile.hitl_persona},
    )

    result = _drive(context, profile.engine)

    assert context.external_event == "commercial_risk_director_decision"
    assert result["command"]["payload"]["approval_decision"] == "approve"


def test_profile_orchestration_rejects_wrong_engine():
    context = _Context("revenue-assurance")

    with pytest.raises(ValueError, match="uses RIG"):
        next(telco_profile_orchestration(context, "DDA"))
