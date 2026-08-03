"""Hospitality MCP tools, runtime skills and Durable module contracts."""
from __future__ import annotations

import json
import os
from datetime import datetime
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest

from verticals.hospitality.domains import HOSPITALITY_DOMAINS
from verticals.hospitality.process_profiles import HOSPITALITY_PROCESS_PROFILES
from verticals.hospitality.reference_cases import HOSPITALITY_REFERENCE_CASES

ROOT = Path(__file__).resolve().parents[3]
PACK = ROOT / "verticals" / "hospitality"


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------


def test_registered_tools_match_agent_declarations() -> None:
    from verticals.hospitality.agents import HOSPITALITY_AGENTS
    from verticals.hospitality.mcp_tools.operations import TOOL_BY_NAME

    declared = {
        tool
        for entry in HOSPITALITY_AGENTS.values()
        for tool in entry.allowed_tools
    }
    assert set(TOOL_BY_NAME) == declared
    assert len(TOOL_BY_NAME) == 8


@pytest.mark.asyncio
async def test_tools_return_simulated_evidence_without_mutation() -> None:
    from copilot.tools import ToolInvocation

    from verticals.hospitality.mcp_tools.common import HospitalityEvidence
    from verticals.hospitality.mcp_tools.operations import (
        hospitality_read_hotel_operations,
    )

    params = HospitalityEvidence(
        data={"hotel_id": "HOTEL-RIVERSIDE-CENTRAL", "affected_rooms": 18},
        actor_ids=["HOTEL-RIVERSIDE-CENTRAL", "ASSET-RIVC-HW-01"],
        event_ids=["EVT-HOSP-000000-000001-20260728"],
        trace_id="hosp-ops-20260728-riverside-hot-water-outage",
        as_of_sim_time=12.0,
    )

    result = await hospitality_read_hotel_operations.handler(
        ToolInvocation(
            session_id="hospitality-test",
            tool_call_id="tool-1",
            tool_name="hospitality_read_hotel_operations",
            arguments=params.model_dump(),
        )
    )
    payload = json.loads(result.text_result_for_llm)

    assert payload["source_mode"] == "simulated"
    assert payload["operation"] == "read_hotel_operations"
    assert payload["data"] == params.data
    assert payload["actor_ids"] == params.actor_ids
    assert payload["event_ids"] == params.event_ids
    assert payload["trace_id"] == params.trace_id


# ---------------------------------------------------------------------------
# Runtime skills
# ---------------------------------------------------------------------------


def test_every_declared_skill_has_a_matching_runtime_file() -> None:
    from verticals.hospitality.agents import HOSPITALITY_AGENTS
    from verticals.hospitality.mcp_tools.operations import TOOL_BY_NAME

    declared_skills = {
        skill
        for domain in HOSPITALITY_DOMAINS.values()
        for skill in domain.skills
    }
    files = {p.parent.name: p for p in (PACK / "skills").glob("*/SKILL.md")}
    assert set(files) == declared_skills

    for skill, path in files.items():
        text = path.read_text(encoding="utf-8")
        assert f"name: {skill}\n" in text
        tools = [
            line.split(":", 1)[1].strip()
            for line in text.splitlines()
            if line.startswith("allowed-tools:")
        ]
        assert tools, f"{skill} declares no allowed-tools"
        assert tools[0] in TOOL_BY_NAME

    # every workflow's agent tool is reachable from at least one of its skills
    for workflow_type, domain in HOSPITALITY_DOMAINS.items():
        agent_tool = HOSPITALITY_AGENTS[workflow_type].allowed_tools[0]
        skill_tools = {
            files[skill].read_text(encoding="utf-8").split("allowed-tools:")[1]
            .splitlines()[0]
            .strip()
            for skill in domain.skills
        }
        assert agent_tool in skill_tools


def test_every_persona_has_a_runtime_persona_file() -> None:
    from verticals.hospitality.personas import HOSPITALITY_PERSONAS

    files = {p.parent.name for p in (PACK / "personae").glob("*/SKILL.md")}
    assert files == set(HOSPITALITY_PERSONAS)


# ---------------------------------------------------------------------------
# Durable module
# ---------------------------------------------------------------------------


def _durable():
    return import_module("verticals.hospitality.durable")


def test_durable_exports_all_orchestrators_and_activities() -> None:
    durable = _durable()

    for profile in HOSPITALITY_PROCESS_PROFILES.values():
        assert callable(getattr(durable, profile.orchestrator))
    for activity in (
        "hospitality_evidence_activity_trigger",
        "hospitality_decision_activity_trigger",
        "hospitality_command_activity_trigger",
    ):
        assert callable(getattr(durable, activity))
    assert getattr(durable, "app", None) is not None


def _observation(workflow_type: str) -> dict[str, Any]:
    profile = HOSPITALITY_PROCESS_PROFILES[workflow_type]
    case = HOSPITALITY_REFERENCE_CASES[workflow_type]
    return {
        "workflow_type": workflow_type,
        "case": {
            "id": case.id,
            "workflow_type": workflow_type,
            "subject_ids": list(case.subject_ids),
            "facts": dict(case.facts),
        },
        "actor_ids": list(case.subject_ids),
        "event_ids": ["EVT-HOSP-000000-000001-20260728"],
        "trace_id": f"hosp-{workflow_type}",
        "as_of_sim_time": 12.0,
        "skills": list(HOSPITALITY_DOMAINS[workflow_type].skills),
        "mcp_tools": [profile.skill],
        "policy": {"decision": "approval_required"},
        "authority": {
            "persona": profile.hitl_persona,
            "external_event": profile.hitl_event,
        },
        "typed_command": profile.command_type,
    }


def test_evidence_activity_digests_real_identity() -> None:
    durable = _durable()
    payload = {
        "workflow_id": "HOPREC-1",
        "trace_id": "hosp-hotel-operations-recovery",
        "type": "hotel-operations-recovery",
        "observation": _observation("hotel-operations-recovery"),
    }

    evidence = durable.hospitality_evidence_activity(payload)

    assert evidence["source_mode"] == "simulated"
    assert evidence["evidence_digest"].startswith("sha256:")
    assert evidence["actor_ids"] == payload["observation"]["actor_ids"]
    assert evidence["event_ids"] == payload["observation"]["event_ids"]
    # deterministic
    assert durable.hospitality_evidence_activity(payload) == evidence

    with pytest.raises(ValueError):
        durable.hospitality_evidence_activity(
            {**payload, "observation": {**payload["observation"], "actor_ids": []}}
        )


def test_fallback_decision_activity_produces_typed_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "ZAVA_HOSPITALITY_AGENT_MODE",
        "deterministic-fallback",
    )
    durable = _durable()
    observation = _observation("hotel-operations-recovery")

    result = durable.hospitality_decision_activity(
        {
            "workflow_id": "HOPREC-1",
            "trace_id": observation["trace_id"],
            "type": "hotel-operations-recovery",
            "phase": "Assess Guest and Operational Impact",
            "observation": observation,
        }
    )

    assert result["skill"] == "hotel-impact-assessor"
    assert result["execution_mode"] == "deterministic-fallback"
    assert result["recommendation"] == "hotel.recovery.execute"
    assert result["actor_ids"] == observation["actor_ids"]

    planner = durable.hospitality_decision_activity(
        {
            "workflow_id": "HOPREC-1",
            "trace_id": observation["trace_id"],
            "type": "hotel-operations-recovery",
            "phase": "Plan Network Recovery",
            "observation": observation,
        }
    )
    assert planner["skill"] == "hotel-network-recovery-planner"


def _bad_live_decision(recommendation: str):
    """Build a live-agent stub whose output breaks the process contract."""
    async def _decide(payload):
        observation = payload["observation"]
        return {
            "skill": "hotel-impact-assessor",
            "phase": payload["phase"],
            "recommendation": recommendation,
            "actor_ids": list(observation["actor_ids"]),
            "event_ids": list(observation["event_ids"]),
            "constraints": {},
            "reasoning": "paraphrased the action instead of copying it",
        }
    return _decide


def test_live_decision_retries_then_falls_back_on_contract_violation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-compliant live agent degrades the phase, it never stalls it.

    The contract is still enforced — the bad response is rejected every
    time — but the deterministic planner completes the phase so one flaky
    model cannot break the cascade.
    """
    monkeypatch.setenv("ZAVA_HOSPITALITY_AGENT_MODE", "live")
    durable = _durable()
    observation = _observation("hotel-operations-recovery")

    attempts = {"count": 0}
    bad = _bad_live_decision("please dispatch someone to fix the boiler")

    async def _counting(payload):
        attempts["count"] += 1
        return await bad(payload)

    monkeypatch.setattr(durable, "_live_decision", _counting)

    result = durable.hospitality_decision_activity(
        {
            "workflow_id": "HOPREC-1",
            "trace_id": observation["trace_id"],
            "type": "hotel-operations-recovery",
            "phase": "Assess Guest and Operational Impact",
            "observation": observation,
        }
    )

    assert attempts["count"] == durable._LIVE_DECISION_ATTEMPTS
    assert result["execution_mode"] == "deterministic-fallback"
    assert result["recommendation"] == "hotel.recovery.execute"
    assert result["actor_ids"] == observation["actor_ids"]


def test_compliant_live_decision_is_used_without_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A compliant live response is returned as-is on the first attempt."""
    monkeypatch.setenv("ZAVA_HOSPITALITY_AGENT_MODE", "live")
    durable = _durable()
    observation = _observation("hotel-operations-recovery")

    attempts = {"count": 0}

    async def _good(payload):
        attempts["count"] += 1
        return {
            "skill": "hotel-impact-assessor",
            "phase": payload["phase"],
            "recommendation": "hotel.recovery.execute",
            "actor_ids": list(observation["actor_ids"]),
            "event_ids": list(observation["event_ids"]),
            "constraints": {},
            "reasoning": "copied the allowed recommendation verbatim",
        }

    monkeypatch.setattr(durable, "_live_decision", _good)

    result = durable.hospitality_decision_activity(
        {
            "workflow_id": "HOPREC-1",
            "trace_id": observation["trace_id"],
            "type": "hotel-operations-recovery",
            "phase": "Assess Guest and Operational Impact",
            "observation": observation,
        }
    )

    assert attempts["count"] == 1
    assert result["execution_mode"] == "live"
    assert result["reasoning"] == "copied the allowed recommendation verbatim"


def test_command_activity_requires_approved_persona(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    durable = _durable()
    observation = _observation("hotel-operations-recovery")
    base = {
        "workflow_id": "HOPREC-1",
        "trace_id": observation["trace_id"],
        "type": "hotel-operations-recovery",
        "observation": observation,
        "evidence": {"evidence_digest": "sha256:abc"},
        "skill_outputs": {"hotel-network-recovery-planner": {"phase": "x"}},
    }

    with pytest.raises(ValueError):
        durable.hospitality_command_activity(
            {**base, "approval": {"decision": "deny"}}
        )

    decision = durable.hospitality_command_activity(
        {
            **base,
            "approval": {
                "decision": "approve",
                "persona": "regional_operations_manager",
                "decision_id": "REF-HOPREC-0001",
            },
        }
    )
    command = decision["command"]
    assert set(command) == {
        "command_id",
        "trace_id",
        "issued_by",
        "type",
        "payload",
    }
    assert command["type"] == "hotel.recovery.execute"
    assert command["payload"]["workflow_type"] == "hotel-operations-recovery"
    assert command["payload"]["evidence_digest"] == "sha256:abc"
    assert command["payload"]["approval_decision"] == "approve"


# ---------------------------------------------------------------------------
# Orchestration through a fake Durable context
# ---------------------------------------------------------------------------


class _Task:
    def __init__(self, result: Any = None) -> None:
        self.result = result
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True


class _Context:
    instance_id = "hospitality-instance-1"
    current_utc_datetime = datetime(2026, 7, 29)

    def __init__(
        self,
        workflow_type: str,
        *,
        approval: dict[str, Any] | None,
    ) -> None:
        profile = HOSPITALITY_PROCESS_PROFILES[workflow_type]
        self._input = {
            "workflow_id": f"{profile.prefix.upper()}-0001",
            "trace_id": f"hosp-{workflow_type}",
            "type": workflow_type,
            "observation": _observation(workflow_type),
        }
        self.approval = _Task(approval)
        self.timer = _Task()
        self.external_event: str | None = None
        self.checkpoints: list[dict[str, Any]] = []

    def get_input(self) -> dict[str, Any]:
        return self._input

    def call_activity(self, name: str, payload: dict[str, Any]) -> Any:
        durable = _durable()
        if name == "hospitality_evidence_activity_trigger":
            return durable.hospitality_evidence_activity(payload)
        if name == "hospitality_decision_activity_trigger":
            return durable.hospitality_decision_activity(payload)
        if name == "hospitality_command_activity_trigger":
            return durable.hospitality_command_activity(payload)
        self.checkpoints.append(payload)
        return {"checkpoint": payload["kind"]}

    def wait_for_external_event(self, name: str) -> _Task:
        self.external_event = name
        return self.approval

    def create_timer(self, _deadline) -> _Task:
        return self.timer

    def task_any(self, _tasks) -> _Task:
        return self.approval


def _drive(context: _Context) -> dict[str, Any]:
    durable = _durable()
    generator = durable.hospitality_orchestration(context)
    value = None
    try:
        while True:
            value = generator.send(value)
    except StopIteration as stop:
        return stop.value


def test_hero_orchestration_suspends_with_reconstructable_hitl_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ZAVA_HOSPITALITY_AGENT_MODE", "deterministic-fallback")
    context = _Context(
        "hotel-operations-recovery",
        approval={
            "decision": "approve",
            "persona": "regional_operations_manager",
            "decision_id": "REF-HOPREC-0001",
        },
    )

    result = _drive(context)

    assert context.external_event == "regional_operations_manager_decision"
    suspended = [c for c in context.checkpoints if c["kind"] == "suspended"]
    assert len(suspended) == 1
    payload = suspended[0]["payload"]
    assert payload["persona"] == "regional_operations_manager"
    assert payload["phase"] == "Approve Recovery Exception"
    assert payload["external_event"] == "regional_operations_manager_decision"
    request = payload["context"]["request"]
    assert request["category"] == "hotel-operations-recovery"
    assert request["actor_ids"]
    assert request["evidence_digest"].startswith("sha256:")

    assert result["status"] == "decision_ready"
    assert result["command"]["type"] == "hotel.recovery.execute"
    assert result["approval"]["decision"] == "approve"
    assert "hotel-impact-assessor" in result["reasoning"]["skill_outputs"]
    assert "hotel-network-recovery-planner" in result["reasoning"]["skill_outputs"]


def test_denied_approval_stops_before_any_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ZAVA_HOSPITALITY_AGENT_MODE", "deterministic-fallback")
    context = _Context(
        "energy-anomaly-response",
        approval={
            "decision": "deny",
            "persona": "sustainability_operations_manager",
        },
    )

    result = _drive(context)

    assert result["status"] == "denied"
    assert result["command"] is None


def test_live_mode_is_the_production_default() -> None:
    durable = _durable()
    assert os.environ.get("ZAVA_HOSPITALITY_AGENT_MODE") in (None, "", "live")
    assert durable.DEFAULT_AGENT_MODE == "live"
