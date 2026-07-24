from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]

EXPECTED_COVERAGE = {
    "hiring.py": [
        ["Job Design", "Sourcing", "Triage", "Screening"],
        ["Interview"],
        ["Compliance", "Offer"],
        ["Onboarding"],
    ],
    "fleet_employee_transfer.py": [
        ["Eligibility Check"],
        ["Compensation Remap"],
    ],
    "fleet_training_request.py": [
        ["Eligibility & Catalogue"],
    ],
}


def _dict_keys(node: ast.Dict) -> dict[str, ast.expr]:
    return {
        key.value: value
        for key, value in zip(node.keys, node.values)
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }


def _suspended_payloads(path: Path) -> list[dict[str, ast.expr]]:
    payloads = []
    for node in ast.walk(ast.parse(path.read_text())):
        if (
            not isinstance(node, ast.Call)
            or not isinstance(node.func, ast.Attribute)
            or node.func.attr != "call_activity"
            or len(node.args) < 2
            or not isinstance(node.args[0], ast.Constant)
            or node.args[0].value != "checkpoint_activity_trigger"
            or not isinstance(node.args[1], ast.Dict)
        ):
            continue
        envelope = _dict_keys(node.args[1])
        if (
            isinstance(envelope.get("kind"), ast.Constant)
            and envelope["kind"].value == "suspended"
            and isinstance(envelope.get("payload"), ast.Dict)
        ):
            payloads.append(_dict_keys(envelope["payload"]))
    return payloads


def test_segment_orchestrators_keep_control_plane_and_durable_identities_separate():
    workflows_dir = ROOT / "api" / "functions" / "workflows"

    for filename, expected_coverage in EXPECTED_COVERAGE.items():
        tree = ast.parse((workflows_dir / filename).read_text())
        initial_enriched = next(
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "enriched"
                for target in node.targets
            )
            and isinstance(node.value, ast.Dict)
            and any(
                key is None
                and isinstance(value, ast.Name)
                and value.id == "input_dict"
                for key, value in zip(node.value.keys, node.value.values)
            )
        )
        enriched_keys = _dict_keys(initial_enriched)
        assert ast.unparse(enriched_keys["workflow_id"]) == "workflow_id"
        assert ast.unparse(enriched_keys["instance_id"]) == "context.instance_id"

        initial_segments = sorted(
            (
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "segment_input"
                    for target in node.targets
                )
                and isinstance(node.value, ast.Dict)
                and any(
                    key is None
                    and isinstance(value, ast.Name)
                    and value.id in {"enriched", "rec_input_gate1"}
                    for key, value in zip(node.value.keys, node.value.values)
                )
            ),
            key=lambda node: node.lineno,
        )
        assert len(initial_segments) == len(expected_coverage)

        for assignment, covered_phases in zip(initial_segments, expected_coverage):
            keys = _dict_keys(assignment.value)
            assert "workflow_id" not in keys
            assert ast.literal_eval(keys["covered_phases"]) == covered_phases


def test_hitl_payloads_use_canonical_contract_phase_and_persona() -> None:
    from verticals.agency.domains import AGENCY_DOMAINS

    workflows_dir = ROOT / "api" / "functions" / "workflows"
    cases = (
        (
            "fleet_employee_transfer.py",
            "employee-transfer",
            "manager_approval_decision",
        ),
        ("hiring.py", "hiring", "offer_approval"),
    )
    for filename, workflow_type, external_event in cases:
        gate = next(
            gate
            for gate in AGENCY_DOMAINS[workflow_type].hitl_gates
            if gate.external_event == external_event
        )
        payload = next(
            payload
            for payload in _suspended_payloads(workflows_dir / filename)
            if (
                isinstance(payload.get("external_event"), ast.Constant)
                and payload["external_event"].value == external_event
            )
        )

        assert ast.literal_eval(payload["phase"]) == gate.gate_phase
        assert ast.literal_eval(payload["persona"]) == gate.persona
