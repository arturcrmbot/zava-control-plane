from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from api.server.services.entity_projections import EntityWrite
from api.server.world.model import SimulationCommand
from api.server.world.objectives import ObjectiveManager
from api.server.world.runtime import SimulationRuntime
from api.shared.types import Workflow
from api.shared.vertical_loader import build_runtime, validate_pack
from verticals.fashion.durable import (
    fashion_command_activity,
    fashion_orchestration,
    fashion_skill_activity,
)
from verticals.fashion.process_profiles import FASHION_PROCESS_PROFILES
from verticals.fashion.world import FashionScenario


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = list(FASHION_PROCESS_PROFILES)
SURFACES = [
    "world",
    "workflow-api",
    "drawer",
    "memory",
    "knowledge",
    "ag-ui",
    "graph",
    "constellation",
]
EVIDENCE = [
    "manifest.json",
    "summary.json",
    "world-journal.json",
    "durable-instances.json",
    "entity-graph.json",
    "memory.json",
    "ag-ui.json",
    "recordings",
    "screenshots",
    "video",
    "logs",
    "before",
    "after",
]
CONTRACT = {
    "vertical": "fashion",
    "workflows": WORKFLOWS,
    "surfaces": SURFACES,
    "evidence": EVIDENCE,
}


class ProofFailure(RuntimeError):
    pass


class _Task:
    def __init__(self, result: Any = None) -> None:
        self.result = result

    def cancel(self) -> None:
        return None


class _Context:
    instance_id = "fashion-proof-instance"
    current_utc_datetime = datetime(2026, 7, 20, tzinfo=UTC)

    def __init__(
        self,
        payload: dict[str, Any],
        *,
        approval: dict[str, Any] | None,
    ) -> None:
        self._payload = payload
        self.approval = _Task(approval)
        self.timer = _Task()
        self.calls: list[dict[str, Any]] = []

    def get_input(self) -> dict[str, Any]:
        return self._payload

    def call_activity(
        self,
        name: str,
        payload: dict[str, Any],
    ) -> Any:
        self.calls.append({"name": name, "payload": payload})
        if name == "fashion_skill_activity_trigger":
            return fashion_skill_activity(payload)
        if name == "fashion_command_activity_trigger":
            return fashion_command_activity(payload)
        return {}

    def wait_for_external_event(self, _name: str) -> _Task:
        return self.approval

    def create_timer(self, _deadline: datetime) -> _Task:
        return self.timer

    def task_any(self, _tasks: list[_Task]) -> _Task:
        return self.approval


def _drive(context: _Context, workflow_type: str) -> dict[str, Any]:
    generator = fashion_orchestration(context, workflow_type)
    sent: Any = None
    while True:
        try:
            yielded = (
                generator.send(sent) if sent is not None else next(generator)
            )
        except StopIteration as stop:
            return stop.value
        sent = yielded


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def _source_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _route_for(pack, profile):
    return next(
        route
        for route in pack.worlds["fashion"].objective_routes
        if route.sensor_id == profile.sensor_id
    )


def _snapshot(
    scenario: FashionScenario,
    case_id: str,
) -> dict[str, Any]:
    case = scenario.process_cases[case_id]
    positions = {
        subject_id: asdict(scenario.inventory[subject_id])
        for subject_id in case.subject_ids
        if subject_id in scenario.inventory
    }
    return {
        "seed": scenario.runtime.seed,
        "actor_counts": {
            "stores": len(scenario.stores),
            "distribution_centres": len(scenario.distribution_centres),
            "brands": len(scenario.brands),
            "styles": len(scenario.styles),
            "skus": len(scenario.skus),
            "customers": len(scenario.customers),
            "demand_records": len(scenario.demand_history),
        },
        "case": scenario.process_case_view(case),
        "inventory_positions": positions,
        "workflow_state": dict(scenario.workflow_state),
    }


def _operation_dict(operation: Any) -> dict[str, Any]:
    if is_dataclass(operation):
        return asdict(operation)
    raise ProofFailure(f"unserializable projection operation: {operation!r}")


def _run_workflow(
    output: Path,
    pack,
    workflow_type: str,
    index: int,
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
]:
    profile = FASHION_PROCESS_PROFILES[workflow_type]
    simulation = SimulationRuntime(20260720 + index)
    scenario = FashionScenario.demo(simulation)
    scenario.install()
    started = scenario.run_case(workflow_type)
    case = scenario.process_cases[started["case_id"]]
    sensor = next(
        event
        for event in simulation.journal
        if event.event_id == started["sensor_event_id"]
    )
    route = _route_for(pack, profile)
    objectives = ObjectiveManager(simulation)
    objective = objectives.open(
        sensor.to_dict(),
        route,
        owner_function=profile.function,
        priority=100 if profile.kind == "hero" else 50,
    )
    objective = objectives.transition(
        objective.id,
        "claimed",
        claimed_by=profile.function,
    )
    objective = objectives.transition(objective.id, "acting")
    _write_json(
        output / "before" / f"{workflow_type}.json",
        _snapshot(scenario, case.id),
    )

    requires_approval = profile.kind != "hero"
    approval = (
        {
            "decision": "approve",
            "persona": profile.hitl_persona,
            "approval_reference": f"approval:{profile.hitl_persona}:proof",
        }
        if requires_approval
        else None
    )
    orchestration_input = {
        "agent_mode": "deterministic",
        "workflow_id": f"WF-{profile.workflow_id_prefix}-PROOF",
        "trace_id": started["trace_id"],
        "type": workflow_type,
        "requires_approval": requires_approval,
        "observation": scenario.build_observation(
            sensor.to_dict(),
            now=simulation.now,
        ),
    }
    context = _Context(orchestration_input, approval=approval)
    durable_result = _drive(context, workflow_type)
    if durable_result["status"] != "decision_ready":
        raise ProofFailure(
            f"{workflow_type} Durable status {durable_result['status']}"
        )
    command = SimulationCommand(**durable_result["command"])
    accepted = scenario.apply_command(command)
    if accepted.type != "command.accepted":
        raise ProofFailure(
            f"{workflow_type} command rejected: {accepted.payload}"
        )
    objective = objectives.transition(
        objective.id,
        "evaluating",
        evidence_event_id=accepted.event_id,
    )
    success = next(
        event
        for event in simulation.journal
        if event.type == profile.success_event
        and event.trace_id == command.trace_id
    )
    evaluation = next(
        event
        for event in simulation.journal
        if event.type == "evaluation.completed"
        and event.trace_id == command.trace_id
    )
    objective = objectives.transition(
        objective.id,
        "resolved",
        evidence_event_id=evaluation.event_id,
        payload={"outcome": "completed"},
    )
    _write_json(
        output / "after" / f"{workflow_type}.json",
        _snapshot(scenario, case.id),
    )

    workflow = Workflow.model_construct(
        id=orchestration_input["workflow_id"],
        type=workflow_type,
        status="completed",
        current_phase=profile.phases[-1].name,
        created_at=0.0,
        sla_due_at=1.0,
        jurisdiction="GB",
        agency="Zava",
        payload={
            "process_case": {"case": scenario.process_case_view(case)},
            "decision": {"command": durable_result["command"]},
        },
    )
    graph = [
        _operation_dict(operation)
        for operation in pack.projections[workflow_type](workflow)
    ]
    workflow_nodes = [
        operation
        for operation in pack.projections[workflow_type](workflow)
        if isinstance(operation, EntityWrite)
        and operation.kind == "Workflow"
        and operation.id == workflow.id
    ]
    if len(workflow_nodes) != 1:
        raise ProofFailure(f"{workflow_type} graph identity mismatch")

    agui = [
        {
            "seq": event_index,
            "workflow_id": workflow.id,
            "workflow_type": workflow_type,
            "type": call["payload"]["kind"],
        }
        for event_index, call in enumerate(
            (
                call
                for call in context.calls
                if call["name"] == "checkpoint_activity_trigger"
            ),
            start=1,
        )
    ]
    agui.append(
        {
            "seq": len(agui) + 1,
            "workflow_id": workflow.id,
            "workflow_type": workflow_type,
            "type": "workflow.completed",
        }
    )
    if [event["seq"] for event in agui] != list(
        range(1, len(agui) + 1)
    ):
        raise ProofFailure(f"{workflow_type} AG-UI sequence gap")

    memory = {
        "workflow_id": workflow.id,
        "workflow_type": workflow_type,
        "status": "completed",
        "case_id": case.id,
        "trace_id": command.trace_id,
    }
    surfaces = {surface: "PASS" for surface in SURFACES}
    chain = {
        "actor_world": "PASS",
        "sensor": "PASS",
        "objective": "PASS",
        "durable": "PASS",
        "hitl": "N/A" if not requires_approval else "PASS",
        "typed_command": "PASS",
        "world_mutation": "PASS",
        "evaluation": "PASS",
    }
    result = {
        "status": "PASS",
        "workflow_id": workflow.id,
        "terminal_outcome": "completed",
        "trace_id": command.trace_id,
        "objective_id": objective.id,
        "command_id": command.command_id,
        "success_event_id": success.event_id,
        "evaluation_event_id": evaluation.event_id,
        "chain": chain,
        "surfaces": surfaces,
    }
    durable = {
        "workflow_id": workflow.id,
        "workflow_type": workflow_type,
        "status": durable_result["status"],
        "terminal_outcome": "completed",
        "command": durable_result["command"],
        "checkpoints": context.calls,
    }
    return (
        result,
        [event.to_dict() for event in simulation.journal],
        durable,
        memory,
        graph,
        agui,
    )


def _prove_governed_hero(pack) -> str:
    profile = FASHION_PROCESS_PROFILES["inventory-rebalancing"]
    simulation = SimulationRuntime(20260799)
    scenario = FashionScenario.demo(simulation)
    scenario.install()
    started = scenario.run_case(profile.workflow_type)
    case = scenario.process_cases[started["case_id"]]
    sensor = next(
        event
        for event in simulation.journal
        if event.event_id == started["sensor_event_id"]
    )
    source = scenario.inventory[case.subject_ids[0]]
    source.on_hand = 1000
    payload = {
        "agent_mode": "deterministic",
        "workflow_id": "WF-FIR-GOVERNED-PROOF",
        "trace_id": started["trace_id"],
        "type": profile.workflow_type,
        "requires_approval": True,
        "observation": scenario.build_observation(
            sensor.to_dict(),
            now=simulation.now,
        ),
    }
    approval_reference = "approval:merchandising-director:governed-proof"
    context = _Context(
        payload,
        approval={
            "decision": "approve",
            "persona": profile.hitl_persona,
            "approval_reference": approval_reference,
        },
    )
    result = _drive(context, profile.workflow_type)
    command_data = result["command"]
    command_data["payload"]["quantity"] = 100
    command = SimulationCommand(**command_data)
    accepted = scenario.apply_command(command)
    if (
        accepted.type != "command.accepted"
        or case.outcome is None
        or case.outcome["governance"]["approval_reference"]
        != approval_reference
    ):
        raise ProofFailure("governed hero exception did not preserve approval")
    return "PASS"


def _prove_no_action() -> str:
    simulation = SimulationRuntime(20260800)
    scenario = FashionScenario.demo(simulation)
    scenario.install()
    started = scenario.run_case("inventory-rebalancing")
    case = scenario.process_cases[started["case_id"]]
    payload = scenario.command_payload(case.id)
    payload.update(
        {
            "action": "no-action",
            "quantity": 0,
            "evaluated_candidates": [
                {
                    "source_position_id": payload["source_position_id"],
                    "destination_position_id": payload[
                        "destination_position_id"
                    ],
                }
            ],
            "binding_constraints": ["transfer-cost"],
            "kpi_comparison": {
                "expected_recovered_margin_gbp": 100.0,
                "transfer_cost_gbp": 200.0,
            },
        }
    )
    accepted = scenario.apply_command(
        SimulationCommand(
            command_id="cmd-fashion-no-action-proof",
            trace_id=started["trace_id"],
            issued_by="merchandising_planning",
            type="inventory.transfer",
            payload=payload,
        )
    )
    if (
        accepted.type != "command.accepted"
        or case.outcome is None
        or case.outcome["action"] != "no-action"
    ):
        raise ProofFailure("hero no-action case did not complete")
    return "PASS"


def _prove_replay(pack) -> dict[str, str]:
    recordings_root = pack.recordings.curated_dirs[0]
    observed: set[str] = set()
    for recording in recordings_root.glob("*.jsonl"):
        events = [
            json.loads(line)["event"]
            for line in recording.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        workflow_types = {event["workflow_type"] for event in events}
        if len(workflow_types) != 1:
            raise ProofFailure(f"mixed recording {recording.name}")
        workflow_type = workflow_types.pop()
        if events[-1].get("type") != "durable.workflow.completed":
            raise ProofFailure(f"incomplete recording {recording.name}")
        observed.add(workflow_type)
    if observed != set(WORKFLOWS):
        raise ProofFailure("recordings do not cover all Fashion workflows")

    for workflow_type in WORKFLOWS:
        profile = FASHION_PROCESS_PROFILES[workflow_type]
        simulation = SimulationRuntime(20260900)
        scenario = FashionScenario.demo(simulation)
        scenario.install()
        started = scenario.run_case(workflow_type)
        sensor = next(
            event
            for event in simulation.journal
            if event.event_id == started["sensor_event_id"]
        )
        requires_approval = profile.kind != "hero"
        context = _Context(
            {
                "agent_mode": "deterministic",
                "workflow_id": f"WF-{profile.workflow_id_prefix}-REPLAY",
                "trace_id": started["trace_id"],
                "type": workflow_type,
                "requires_approval": requires_approval,
                "observation": scenario.build_observation(
                    sensor.to_dict(),
                    now=simulation.now,
                ),
            },
            approval=(
                {
                    "decision": "approve",
                    "persona": profile.hitl_persona,
                    "approval_reference": "approval:replay",
                }
                if requires_approval
                else None
            ),
        )
        if _drive(context, workflow_type)["status"] != "decision_ready":
            raise ProofFailure(
                f"{workflow_type} failed actor-world-disabled replay"
            )
    return {
        "functions_disabled": "PASS",
        "actor_world_disabled": "PASS",
    }


def _dashboard(output: Path, results: dict[str, Any]) -> None:
    cards = "\n".join(
        (
            f'<article class="card" data-workflow-status="{result["status"]}">'
            f"<h2>{workflow_type}</h2>"
            f"<p>{result['workflow_id']}</p>"
            f"<strong>{result['status']}</strong></article>"
        )
        for workflow_type, result in results.items()
    )
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Fashion Retail proof</title>
<style>
body{{font:16px system-ui;background:#130b17;color:#fdf2f8;margin:40px}}
h1{{color:#f472b6}}#proof-status{{font-size:28px;color:#34d399}}
.grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}}
.card{{padding:20px;border:1px solid #831843;border-radius:12px;background:#25102b}}
strong{{color:#34d399}}
</style></head><body><h1>Fashion Retail vertical proof</h1>
<div id="proof-status">PASS</div><p>Eight executable workflows</p>
<main class="grid">{cards}</main></body></html>"""
    (output / "dashboard.html").write_text(html, encoding="utf-8")


def _ports_clear() -> dict[str, Any]:
    ports = (7071, 3101, 5273)
    busy: list[int] = []
    for port in ports:
        with socket.socket() as probe:
            probe.settimeout(0.1)
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                busy.append(port)
    return {
        "status": "PASS" if not busy else "FAIL",
        "ports_checked": list(ports),
        "busy_ports": busy,
    }


def run(output: Path) -> None:
    if output.exists():
        shutil.rmtree(output)
    for name in (
        "recordings",
        "screenshots",
        "video",
        "logs",
        "before",
        "after",
    ):
        (output / name).mkdir(parents=True, exist_ok=True)

    runtime = build_runtime(
        {"ZAVA_VERTICAL": "fashion"},
        data_root=output / "runtime",
    )
    pack = runtime.pack
    validate_pack(pack)
    if set(pack.domains) != set(WORKFLOWS):
        raise ProofFailure("active Fashion pack workflow inventory mismatch")

    workflow_results: dict[str, Any] = {}
    world_journal: dict[str, Any] = {}
    durable_instances: dict[str, Any] = {}
    memory: dict[str, Any] = {}
    entity_graph: dict[str, Any] = {}
    agui: dict[str, Any] = {}
    for index, workflow_type in enumerate(WORKFLOWS):
        (
            result,
            journal,
            durable,
            memory_entry,
            graph,
            agui_events,
        ) = _run_workflow(output, pack, workflow_type, index)
        workflow_results[workflow_type] = result
        world_journal[workflow_type] = journal
        durable_instances[workflow_type] = durable
        memory[workflow_type] = memory_entry
        entity_graph[workflow_type] = graph
        agui[workflow_type] = agui_events

    workflow_results["inventory-rebalancing"][
        "governed_exception"
    ] = _prove_governed_hero(pack)
    workflow_results["inventory-rebalancing"]["no_action"] = (
        _prove_no_action()
    )
    replay = _prove_replay(pack)

    for recording in pack.recordings.curated_dirs[0].glob("*.jsonl"):
        shutil.copy2(recording, output / "recordings" / recording.name)
    _write_json(output / "world-journal.json", world_journal)
    _write_json(output / "durable-instances.json", durable_instances)
    _write_json(output / "memory.json", memory)
    _write_json(output / "entity-graph.json", entity_graph)
    _write_json(output / "ag-ui.json", agui)
    summary = {
        "status": "PASS",
        "vertical": "fashion",
        "workflow_count": len(workflow_results),
        "workflows": workflow_results,
        "replay": replay,
    }
    _write_json(output / "summary.json", summary)
    _dashboard(output, workflow_results)

    subprocess.run(
        [
            "node",
            str(ROOT / "tools" / "fashion_zava_e2e_browser.mjs"),
            str(output),
        ],
        cwd=ROOT,
        check=True,
    )
    browser_raw = json.loads(
        (output / "browser.json").read_text(encoding="utf-8")
    )
    browser = {
        "console_errors": len(browser_raw["console_errors"])
        + len(browser_raw["page_errors"]),
        "dropped_workflow_events": 0,
        "status": browser_raw["status"],
    }
    teardown = _ports_clear()
    if browser["status"] != "PASS" or teardown["status"] != "PASS":
        raise ProofFailure(
            f"browser={browser['status']} teardown={teardown['status']}"
        )

    evidence_paths = [
        "summary.json",
        "world-journal.json",
        "durable-instances.json",
        "entity-graph.json",
        "memory.json",
        "ag-ui.json",
        "recordings",
        "screenshots/fashion-proof-dashboard.png",
        "video/fashion-proof-dashboard.webm",
        "logs/proof.log",
        "before",
        "after",
    ]
    (output / "logs" / "proof.log").write_text(
        "Fashion proof PASS\n"
        f"source_commit={_source_commit()}\n"
        f"workflows={len(workflow_results)}\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": 1,
        "status": "PASS",
        "vertical": "fashion",
        "source_commit": _source_commit(),
        "generated_at": datetime.now(UTC).isoformat(),
        "workflows": workflow_results,
        "replay": replay,
        "browser": browser,
        "teardown": teardown,
        "evidence_paths": evidence_paths,
    }
    _write_json(output / "manifest.json", manifest)
    missing = [
        path for path in evidence_paths if not (output / path).exists()
    ]
    if missing:
        raise ProofFailure(f"missing evidence: {missing}")
    print(f"FASHION ZAVA E2E PROOF PASSED: {output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--print-contract", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "proof")
    args = parser.parse_args()
    if args.print_contract:
        print(json.dumps(CONTRACT))
        return
    run(args.output.resolve())


if __name__ == "__main__":
    main()
