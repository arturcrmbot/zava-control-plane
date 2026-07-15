"""Generator-driven test of network_incident_orchestration.

Proves the orchestrator runs the two deterministic activities in order
(impact diagnosis → reroute planning), emits the standard checkpoints around
each phase boundary, threads the impact diagnosis into the reroute activity,
and — critically — does NOT emit a terminal ``workflow.completed`` checkpoint
(recovery verification is the later Phase 3 world-evaluation boundary).
"""
from __future__ import annotations

from typing import Any

from api.functions.workflows.network_incident import network_incident_orchestration


class _StubContext:
    def __init__(self, input_dict, impact_result, reroute_result):
        self.instance_id = "instance-ni-1"
        self._input = input_dict
        self._impact = impact_result
        self._reroute = reroute_result
        self.calls: list[tuple[str, dict]] = []

    def get_input(self):
        return self._input

    def call_activity(self, name: str, payload: dict):
        self.calls.append((name, payload))
        if name == "network_incident_impact_activity_trigger":
            return self._impact
        if name == "network_incident_reroute_activity_trigger":
            return self._reroute
        return {}  # checkpoint_activity_trigger


def _drive(ctx: _StubContext) -> dict | None:
    gen = network_incident_orchestration(ctx)  # type: ignore[arg-type]
    sent: Any = None
    while True:
        try:
            target = gen.send(sent) if sent is not None else next(gen)
        except StopIteration as stop:
            return stop.value
        sent = target


def _input():
    return {
        "workflow_id": "incident-evt-00000042",
        "type": "network-incident",
        "trace_id": "network-anomaly-SITE-01-42",
        "observation": {"incident_site": {"id": "SITE-01"}},
    }


def _checkpoints(ctx):
    return [
        p["kind"] for name, p in ctx.calls
        if name == "checkpoint_activity_trigger"
    ]


def _steps(ctx):
    return [
        (p["kind"], p["payload"].get("step"))
        for name, p in ctx.calls
        if name == "checkpoint_activity_trigger" and p["kind"].startswith("step.")
    ]


def test_orchestrator_runs_impact_then_reroute_in_order():
    ctx = _StubContext(
        _input(),
        impact_result={"diagnosis": {"incident_site_id": "SITE-01"}, "reasoning": None},
        reroute_result={"command": {"type": "reroute_sessions"}, "reasoning": "ok"},
    )
    _drive(ctx)
    activities = [n for n, _ in ctx.calls if not n.startswith("checkpoint")]
    assert activities == [
        "network_incident_impact_activity_trigger",
        "network_incident_reroute_activity_trigger",
    ]


def test_orchestrator_emits_standard_phase_checkpoints():
    ctx = _StubContext(
        _input(),
        impact_result={"diagnosis": {"incident_site_id": "SITE-01"}, "reasoning": None},
        reroute_result={"command": {"type": "reroute_sessions"}, "reasoning": "ok"},
    )
    _drive(ctx)
    assert _checkpoints(ctx)[0] == "workflow.started"
    assert _steps(ctx) == [
        ("step.started", "Impact Diagnosis"),
        ("step.completed", "Impact Diagnosis"),
        ("step.started", "Reroute Planning"),
        ("step.completed", "Reroute Planning"),
    ]


def test_orchestrator_does_not_emit_terminal_completion():
    ctx = _StubContext(
        _input(),
        impact_result={"diagnosis": {"incident_site_id": "SITE-01"}, "reasoning": None},
        reroute_result={"command": {"type": "reroute_sessions"}, "reasoning": "ok"},
    )
    _drive(ctx)
    # Recovery verification / effectiveness is the later Phase 3 world-eval
    # boundary — the orchestrator must NOT emit workflow.completed.
    assert "workflow.completed" not in _checkpoints(ctx)


def test_orchestrator_threads_diagnosis_into_reroute():
    diagnosis = {"incident_site_id": "SITE-01", "spare_capacity": {"SITE-02": 5.0}}
    ctx = _StubContext(
        _input(),
        impact_result={"diagnosis": diagnosis, "reasoning": None},
        reroute_result={"command": None, "reasoning": "x"},
    )
    _drive(ctx)
    reroute_call = next(
        p for n, p in ctx.calls if n == "network_incident_reroute_activity_trigger"
    )
    assert reroute_call["diagnosis"] == diagnosis
    assert reroute_call["trace_id"] == "network-anomaly-SITE-01-42"


def test_orchestrator_output_carries_command_and_reasoning():
    command = {"type": "reroute_sessions", "payload": {"incident_site_id": "SITE-01"}}
    ctx = _StubContext(
        _input(),
        impact_result={"diagnosis": {"incident_site_id": "SITE-01"}, "reasoning": None},
        reroute_result={"command": command, "reasoning": "planned 1 session assignment"},
    )
    result = _drive(ctx)
    assert result["status"] == "completed"
    assert result["command"] == command
    assert result["reasoning"] == "planned 1 session assignment"
    assert result["observation"] == {"incident_site": {"id": "SITE-01"}}
