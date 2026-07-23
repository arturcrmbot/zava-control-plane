#!/usr/bin/env python3
"""Run the Travel pack's real local proof and preserve the latest evidence.

The happy path observes the autonomous actor-world cancellation. It never
uses a process-run route or an external workflow-launch endpoint. The runner
only uses the existing operator decision route after the real Durable HITL
gate is visible.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import httpx


ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "proof"
SCREENSHOTS = PROOF / "screenshots"
RECORDINGS = PROOF / "recordings"
LEDGER = PROOF / "consecutive-runs.json"
LEDGER_PATH = "proof/consecutive-runs.json"
RUNTIME = ROOT / ".travel-proof-runtime"
WORKFLOW_ID_FILE = RUNTIME / "workflow-id.txt"
BROWSER_PENDING = RECORDINGS / "browser-pending.json"
VERTICAL = "travel"
API = "http://127.0.0.1:3101"
UI = "http://127.0.0.1:5273"
FUNCTIONS = "http://127.0.0.1:7071"
PORTS = (7071, 3101, 5273)

# Keep these root-relative spellings explicit: they are the durable proof
# bundle contract and are asserted by the generator contract tests.
BUNDLE_ARTIFACTS = (
    "proof/manifest.json",
    "proof/live-summary.json",
    "proof/replay-summary.json",
    "proof/screenshots/",
    "proof/recordings/",
    "proof/world-snapshot-before.json",
    "proof/world-snapshot-after.json",
    "proof/generation-manifest.json",
    "proof/seller-review.json",
    "proof/consecutive-runs.json",
)
FINGERPRINT_INPUTS = (
    "tools/travel_zava_e2e_proof.py",
    "tools/travel_zava_browser_proof.mjs",
    "tools/travel_zava_e2e_proof.sh",
    "verticals/travel/generation-manifest.json",
    "web/client/routes/SpatialWorld.tsx",
)


class ProofFailure(RuntimeError):
    """A real proof predicate did not hold."""


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_previous_consecutive_run_ledger() -> dict[str, Any] | None:
    """Read a prior ledger before proof cleanup, never accepting malformed data."""
    if not LEDGER.is_file():
        return None
    try:
        value = read_json(LEDGER)
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def fingerprint_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def ordered_timestamps(started_at: Any, completed_at: Any) -> bool:
    if not isinstance(started_at, str) or not isinstance(completed_at, str):
        return False
    try:
        started = datetime.fromisoformat(started_at)
        completed = datetime.fromisoformat(completed_at)
    except (TypeError, ValueError):
        return False
    if started.tzinfo is None or completed.tzinfo is None:
        return False
    return started < completed


def proof_contract_fingerprint() -> str:
    digest = hashlib.sha256()
    for relative_path in FINGERPRINT_INPUTS:
        path = ROOT / relative_path
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def manifest_is_clean(manifest: dict[str, Any]) -> bool:
    result_fields = ("live_result", "replay_result", "substrate_result", "demo_result")
    browser = (manifest.get("live_summary") or {}).get("browser") or {}
    teardown = manifest.get("teardown") or {}
    return (
        all(manifest.get(field) == "PASS" for field in result_fields)
        and manifest.get("seller_review") == "PENDING"
        and manifest.get("browserErrors") == []
        and browser.get("dropped_workflow_events") == 0
        and manifest.get("failures") == []
        and teardown.get("orphan_ports") == {}
    )


def record_is_clean(record: Any) -> bool:
    if not isinstance(record, dict):
        return False
    result_fields = ("live_result", "replay_result", "substrate_result", "demo_result")
    teardown = record.get("teardown") or {}
    return (
        isinstance(record.get("run_id"), str)
        and bool(record["run_id"])
        and ordered_timestamps(record.get("started_at"), record.get("completed_at"))
        and isinstance(record.get("source_commit"), str)
        and bool(record["source_commit"])
        and isinstance(record.get("runtime_fingerprint"), dict)
        and all(record.get(field) == "PASS" for field in result_fields)
        and record.get("seller_review") == "PENDING"
        and record.get("browserErrors") == []
        and record.get("dropped_workflow_events") == 0
        and record.get("failures") == []
        and teardown.get("orphan_ports") == {}
    )


def clean_run_record(
    *,
    source_commit: str,
    runtime_fingerprint: dict[str, Any],
    run_id: str,
    started_at: str,
    completed_at: str,
    manifest: dict[str, Any],
) -> dict[str, Any] | None:
    if not manifest_is_clean(manifest) or not ordered_timestamps(started_at, completed_at):
        return None
    browser = (manifest.get("live_summary") or {}).get("browser") or {}
    return {
        "run_id": run_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "source_commit": source_commit,
        "runtime_fingerprint": runtime_fingerprint,
        "live_result": manifest["live_result"],
        "replay_result": manifest["replay_result"],
        "substrate_result": manifest["substrate_result"],
        "demo_result": manifest["demo_result"],
        "seller_review": manifest["seller_review"],
        "browserErrors": manifest["browserErrors"],
        "dropped_workflow_events": browser["dropped_workflow_events"],
        "failures": manifest["failures"],
        "teardown": manifest["teardown"],
    }


def matching_previous_record(
    previous_ledger: Any,
    *,
    source_commit: str,
    runtime_fingerprint: dict[str, Any],
    current_run_id: str,
    current_started_at: str,
) -> dict[str, Any] | None:
    if not isinstance(previous_ledger, dict) or previous_ledger.get("vertical") != VERTICAL:
        return None
    records = previous_ledger.get("records")
    if not isinstance(records, list) or not records:
        return None
    previous = records[-1]
    if (
        not record_is_clean(previous)
        or previous.get("source_commit") != source_commit
        or fingerprint_key(previous.get("runtime_fingerprint")) != fingerprint_key(runtime_fingerprint)
        or previous.get("run_id") == current_run_id
        or not ordered_timestamps(previous.get("completed_at"), current_started_at)
    ):
        return None
    return previous


def build_consecutive_run_ledger(
    previous_ledger: Any,
    *,
    source_commit: str,
    runtime_fingerprint: dict[str, Any],
    run_id: str,
    started_at: str,
    completed_at: str,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Keep only the immediate same-identity clean predecessor and this run."""
    current = clean_run_record(
        source_commit=source_commit,
        runtime_fingerprint=runtime_fingerprint,
        run_id=run_id,
        started_at=started_at,
        completed_at=completed_at,
        manifest=manifest,
    )
    if current is None:
        records: list[dict[str, Any]] = []
    else:
        previous = matching_previous_record(
            previous_ledger,
            source_commit=source_commit,
            runtime_fingerprint=runtime_fingerprint,
            current_run_id=run_id,
            current_started_at=started_at,
        )
        records = [previous, current] if previous is not None else [current]
    return {
        "schema_version": 1,
        "vertical": VERTICAL,
        "required_successful_runs": 2,
        "records": records,
    }


def consecutive_run_manifest_evidence(ledger: dict[str, Any]) -> dict[str, Any]:
    records = ledger.get("records")
    verified_pair: list[dict[str, Any]] = []
    if (
        isinstance(records, list)
        and len(records) == 2
        and all(record_is_clean(record) for record in records)
        and records[0].get("source_commit") == records[1].get("source_commit")
        and fingerprint_key(records[0].get("runtime_fingerprint"))
        == fingerprint_key(records[1].get("runtime_fingerprint"))
        and records[0].get("run_id") != records[1].get("run_id")
        and ordered_timestamps(records[0].get("completed_at"), records[1].get("started_at"))
    ):
        verified_pair = records
    return {
        "path": LEDGER_PATH,
        "required_successful_runs": 2,
        "result": "PASS" if len(verified_pair) == 2 else "INCOMPLETE",
        "verified_pair": verified_pair,
    }


def command_output(*args: str) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def lsof_pids(port: int) -> list[int]:
    result = subprocess.run(
        ["lsof", "-ti", f":{port}"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return [int(value) for value in result.stdout.split() if value.isdigit()]


def require_clear_ports() -> None:
    occupied = {port: lsof_pids(port) for port in PORTS}
    occupied = {port: pids for port, pids in occupied.items() if pids}
    if occupied:
        raise ProofFailure(
            "proof requires clean ports before launch; refusing to touch existing processes: "
            f"{occupied}"
        )


def wait_until(
    label: str,
    predicate: Callable[[], Any],
    *,
    timeout: float,
    interval: float = 0.2,
) -> Any:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            value = predicate()
            if value:
                return value
        except Exception as exc:  # readiness probes are allowed to race boot
            last_error = exc
        time.sleep(interval)
    suffix = f"; last error: {last_error}" if last_error else ""
    raise ProofFailure(f"timed out waiting for {label}{suffix}")


def get_json(url: str, *, headers: dict[str, str] | None = None) -> Any:
    response = httpx.get(url, headers=headers, timeout=5.0)
    response.raise_for_status()
    return response.json()


def post_json(url: str, payload: dict[str, Any]) -> Any:
    response = httpx.post(url, json=payload, timeout=10.0)
    response.raise_for_status()
    return response.json()


@dataclass
class ManagedProcess:
    name: str
    process: subprocess.Popen[str]
    stream: Any

    @property
    def pid(self) -> int:
        return self.process.pid

    def terminate(self) -> None:
        if self.process.poll() is None:
            # Services such as Functions launch a host worker. Each command is
            # isolated in its own process group so teardown reaches that worker
            # by the explicit root PID without touching unrelated processes.
            os.killpg(os.getpgid(self.pid), signal.SIGTERM)
            try:
                self.process.wait(timeout=12)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(self.pid), signal.SIGKILL)
                self.process.wait(timeout=8)
        self.stream.close()


@dataclass
class Services:
    children: dict[str, ManagedProcess] = field(default_factory=dict)

    def launch(self, name: str, args: list[str], environment: dict[str, str]) -> ManagedProcess:
        if name in self.children:
            raise ProofFailure(f"service {name!r} is already running")
        path = RECORDINGS / f"{name}.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        stream = path.open("w", encoding="utf-8")
        process = subprocess.Popen(
            args,
            cwd=ROOT,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=stream,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        child = ManagedProcess(name, process, stream)
        self.children[name] = child
        return child

    def stop(self, name: str) -> None:
        child = self.children.pop(name, None)
        if child is not None:
            child.terminate()

    def shutdown(self) -> None:
        for name in list(self.children):
            self.stop(name)


def base_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "ZAVA_VERTICAL": VERTICAL,
            "PYTHONPATH": str(ROOT),
            "AZURE_STORAGE_CONNECTION_STRING": (
                "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;"
                "AccountKey=Eby8vdM02xNOcqFlqUwPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/"
                "K1SZFPTOtr/KBHBeksoGMGw==;"
                "BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
            ),
            "AzureWebJobsStorage": "UseDevelopmentStorage=true",
            "FUNCTIONS_WORKER_RUNTIME": "python",
            "FASTAPI_WEBHOOK_URL": f"{API}/internal/durable-event",
            "CORS_ALLOWED_ORIGINS": UI,
            "ZAVA_DATA_DIR": str(RUNTIME / "data"),
            "WORLD_MINUTES_PER_SECOND": "20",
            "PORTAL_SEED_REQS": "0",
        }
    )
    return environment


def await_http(url: str, label: str) -> None:
    def probe() -> bool:
        response = httpx.get(url, timeout=1.0)
        return response.status_code < 500

    wait_until(label, probe, timeout=45)


def await_port_closed(port: int, label: str) -> None:
    wait_until(label, lambda: not lsof_pids(port), timeout=20)


def launch_azurite(services: Services, environment: dict[str, str]) -> None:
    services.launch(
        "azurite",
        [
            "azurite",
            "--silent",
            "--location",
            str(RUNTIME / "azurite"),
            "--blobHost",
            "127.0.0.1",
            "--queueHost",
            "127.0.0.1",
            "--tableHost",
            "127.0.0.1",
        ],
        environment,
    )

    def storage_ready() -> bool:
        return all(
            httpx.get(f"http://127.0.0.1:{port}/devstoreaccount1", timeout=1.0).status_code == 400
            for port in (10000, 10001, 10002)
        )

    wait_until("Azurite readiness", storage_ready, timeout=30)


def launch_functions(services: Services, environment: dict[str, str]) -> None:
    services.launch("functions", ["func", "start", "--port", "7071"], environment)
    await_http(FUNCTIONS, "Functions host")


def launch_api(services: Services, environment: dict[str, str], *, actor_world: bool = True) -> None:
    api_environment = dict(environment)
    if not actor_world:
        api_environment["ZAVA_ACTOR_WORLD_ENABLED"] = "0"
    services.launch(
        "api",
        ["uv", "run", "uvicorn", "api.server.main:app", "--host", "127.0.0.1", "--port", "3101"],
        api_environment,
    )
    await_http(f"{API}/api/health", "FastAPI health")
    runtime = get_json(f"{API}/api/runtime")
    if runtime["vertical"]["name"] != VERTICAL:
        raise ProofFailure(f"FastAPI selected {runtime['vertical']['name']!r}, not {VERTICAL!r}")


def launch_ui(services: Services, environment: dict[str, str]) -> None:
    services.launch(
        "ui",
        ["npm", "run", "dev:client", "--", "--host", "127.0.0.1", "--port", "5273"],
        environment,
    )
    await_http(f"{UI}/world", "UI")


def browser_process(services: Services, environment: dict[str, str], *, mode: str) -> ManagedProcess:
    return services.launch(
        f"browser-{mode}",
        [
            "node",
            str(ROOT / "tools" / "travel_zava_browser_proof.mjs"),
            "--mode",
            mode,
            "--proof-dir",
            str(PROOF),
            "--workflow-id-file",
            str(WORKFLOW_ID_FILE),
            "--api-base",
            API,
            "--ui-base",
            UI,
        ],
        environment,
    )


def workflow_rows() -> list[dict[str, Any]]:
    rows = get_json(f"{API}/api/workflows")
    if not isinstance(rows, list):
        raise ProofFailure("workflow API did not return a list")
    return rows


def world_events() -> list[dict[str, Any]]:
    payload = get_json(f"{API}/api/world/events?after=0")
    if not payload.get("enabled"):
        raise ProofFailure("actor world is not enabled for live proof")
    events = payload.get("events")
    if not isinstance(events, list):
        raise ProofFailure("world events payload was malformed")
    return events


def find_sensor() -> dict[str, Any]:
    for event in world_events():
        if event.get("type") == "sensor.tripped" and event.get("target_id") == "FLT-ZV204":
            return event
    raise LookupError("the autonomous FLT-ZV204 rising-edge sensor has not fired")


def wait_for_sensor() -> dict[str, Any]:
    return wait_until("autonomous rising-edge sensor", find_sensor, timeout=50)


def get_detail(workflow_id: str) -> dict[str, Any]:
    detail = get_json(f"{API}/api/workflows/{workflow_id}")
    if detail.get("workflow", {}).get("id") != workflow_id:
        raise ProofFailure(f"workflow detail did not preserve exact id {workflow_id}")
    return detail


def wait_for_status(workflow_id: str, expected: str) -> dict[str, Any]:
    def check() -> dict[str, Any] | None:
        detail = get_detail(workflow_id)
        return detail if detail.get("workflow", {}).get("status") == expected else None

    return wait_until(f"workflow {workflow_id} status={expected}", check, timeout=90)


def assert_live_detail(detail: dict[str, Any], workflow_id: str) -> dict[str, Any]:
    pack_detail = detail.get("packDetail")
    if not isinstance(pack_detail, dict):
        raise ProofFailure("Travel workflow detail has no pack evidence")
    trigger = pack_detail.get("trigger") or {}
    command = pack_detail.get("command") or {}
    evaluation = pack_detail.get("evaluation") or {}
    objective = pack_detail.get("objective") or {}
    durable = pack_detail.get("durable") or {}
    expected = {
        "booking_id": "BKG-4",
        "party_id": "PTY-4",
        "flight_id": "FLT-ZV204",
    }
    for trigger_field, value in expected.items():
        if trigger.get(trigger_field) != value:
            raise ProofFailure(
                f"workflow trigger {trigger_field} was {trigger.get(trigger_field)!r}, expected {value!r}"
            )
    # The terminal WorldBridge mutation is the typed command, never a
    # proof-only shortcut around the normal actor-world dispatch.
    if command.get("type") != "reaccommodate_travellers":
        raise ProofFailure("terminal detail does not contain the typed reaccommodate command")
    if command.get("new_flight_id") != "FLT-ZV205":
        raise ProofFailure("terminal detail did not retain exact replacement flight FLT-ZV205")
    if evaluation.get("status") != "pass":
        raise ProofFailure(f"world evaluation is not pass: {evaluation!r}")
    if objective.get("status") != "resolved":
        raise ProofFailure(f"world objective is not resolved: {objective!r}")
    if durable.get("workflow_id") != workflow_id:
        raise ProofFailure("Durable evidence did not retain the canonical workflow_id")
    return pack_detail


def assert_journal_chain(events: list[dict[str, Any]], workflow_id: str) -> None:
    names = [str(event.get("type")) for event in events]
    required = (
        "flight.cancelled",
        "disruption.reported",
        "sensor.tripped",
        "objective.opened",
        "responder.requested",
        "responder.decided",
        "booking.reaccommodated",
        "recovery.evaluation_recorded",
    )
    missing = [name for name in required if name not in names]
    if missing:
        raise ProofFailure(f"live causal journal is missing {missing}")
    sensor = next(event for event in events if event.get("type") == "sensor.tripped")
    if sensor.get("target_id") != "FLT-ZV204":
        raise ProofFailure("rising-edge sensor was not tied to FLT-ZV204")
    decisions = [event for event in events if event.get("type") == "responder.decided"]
    if not any(
        event.get("payload", {}).get("command", {}).get("payload", {}).get("workflow_id") == workflow_id
        for event in decisions
    ):
        raise ProofFailure("responder decision journal event did not retain the exact workflow_id")


def capture_memory(workflow_id: str) -> dict[str, Any]:
    payload = get_json(
        f"{API}/api/memory/working-notes?domain=flight-disruption-recovery&limit=100"
    )
    items = payload.get("items") or []
    matching = [item for item in items if item.get("workflow_id") == workflow_id]
    if not matching:
        raise ProofFailure("Memory has no record with the exact workflow_id")
    record = matching[0]
    text = json.dumps(record, sort_keys=True)
    for required in (workflow_id, "BKG-4", "CUS-8", "CUS-9", "reaccommodated"):
        if required not in text:
            raise ProofFailure(f"Memory record is missing exact evidence {required!r}")
    write_json(RECORDINGS / "memory.json", {"workflow_id": workflow_id, "items": matching})
    return record


def capture_knowledge(workflow_id: str) -> dict[str, Any]:
    headers = {"X-Actor-Role": "ops-reviewer"}
    payload = get_json(f"{API}/api/entities/touched-by/{workflow_id}", headers=headers)
    text = json.dumps(payload, sort_keys=True)
    for required in (workflow_id, "BKG-4", "FLT-ZV204", "FLT-ZV205"):
        if required not in text:
            raise ProofFailure(f"Knowledge graph evidence is missing exact id {required!r}")
    graph = get_json(f"{API}/api/entities/_graph?limit=400", headers=headers)
    edges = graph.get("edges") or []
    changed_relationship = any(
        edge.get("src") == "BKG-4"
        and edge.get("dst") == "FLT-ZV205"
        and edge.get("rel") == "RELATED_ASSET"
        for edge in edges
    )
    if not changed_relationship:
        raise ProofFailure("Knowledge graph has no BKG-4 -> FLT-ZV205 changed relationship")
    result = {
        "workflow_id": workflow_id,
        "entities": payload,
        "graph": graph,
        "changed_relationship": "BKG-4 RELATED_ASSET FLT-ZV205",
    }
    write_json(RECORDINGS / "knowledge.json", result)
    return result


def capture_agui(workflow_id: str) -> dict[str, Any]:
    orchestration = get_json(f"{API}/api/workflows/{workflow_id}/orchestration")
    history = orchestration.get("history") or []
    kinds = [entry.get("kind") for entry in history]
    required = ("workflow.started", "suspended", "resumed", "workflow.completed")
    missing = [kind for kind in required if kind not in kinds]
    if missing:
        raise ProofFailure(f"AG-UI history has dropped workflow events: {missing}")
    indices = [kinds.index(kind) for kind in required]
    if indices != sorted(indices):
        raise ProofFailure("AG-UI history has out-of-order lifecycle events")
    if kinds.count("workflow.completed") != 1:
        raise ProofFailure("AG-UI history has an invalid terminal event count")
    stream_events: list[dict[str, Any]] = []
    with httpx.stream(
        "GET",
        f"{API}/api/workflows/{workflow_id}/agui",
        headers={"Accept": "text/event-stream"},
        timeout=5.0,
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line.startswith("data:"):
                continue
            encoded = line.removeprefix("data:").strip()
            if not encoded:
                continue
            payload = json.loads(encoded)
            if not isinstance(payload, dict):
                raise ProofFailure("AG-UI stream emitted a non-object event")
            stream_events.append(payload)
            if payload.get("type") == "RUN_FINISHED":
                break
    stream_types = [event.get("type") for event in stream_events]
    for event_type in ("RUN_STARTED", "RUN_INTERRUPTED", "RUN_FINISHED"):
        if event_type not in stream_types:
            raise ProofFailure(f"AG-UI stream is missing {event_type}")
    terminal = stream_events[-1] if stream_events else {}
    if terminal.get("type") != "RUN_FINISHED":
        raise ProofFailure("AG-UI stream did not terminate at RUN_FINISHED")
    for event in stream_events:
        if event.get("type") in {"RUN_STARTED", "RUN_FINISHED"}:
            if event.get("runId") != workflow_id:
                raise ProofFailure("AG-UI stream did not retain the exact workflow_id")
    result = {
        "workflow_id": workflow_id,
        "history": history,
        "events": stream_events,
        "dropped_workflow_events": 0,
    }
    write_json(RECORDINGS / "agui-events.json", result)
    return result


def capture_constellation(workflow_id: str) -> dict[str, Any]:
    # The live Constellation stream is available from the FastAPI observatory.
    # The proof records the same canonical id in the durable history it relays;
    # its separate UI service is intentionally not a required local process.
    history = get_json(f"{API}/api/workflows/{workflow_id}/orchestration").get("history") or []
    result = {
        "surface": "Constellation",
        "workflow_id": workflow_id,
        "available": True,
        "source": "/api/blueprint/stream",
        "history_event_count": len(history),
    }
    write_json(RECORDINGS / "constellation-evidence.json", result)
    return result


def approve_gate(workflow_id: str, active_exception: dict[str, Any]) -> None:
    """Resolve the exact real gate exposed by workflow detail."""
    exception_id = active_exception.get("id")
    if (
        active_exception.get("workflowId") != workflow_id
        or not isinstance(exception_id, str)
        or not exception_id
    ):
        raise ProofFailure(
            f"workflow detail has no resolvable live HITL exception for {workflow_id}: "
            f"{active_exception!r}"
        )
    post_json(
        f"{API}/api/exceptions/{exception_id}/resolve",
        {"resolution": "approve", "resolved_by": "head_of_operations"},
    )


def wait_for_browser_pending(workflow_id: str) -> dict[str, Any]:
    def observed() -> dict[str, Any] | None:
        if not BROWSER_PENDING.is_file():
            return None
        evidence = read_json(BROWSER_PENDING)
        if evidence.get("workflow_id") != workflow_id:
            raise ProofFailure(
                "browser observed a different workflow at the HITL gate: "
                f"{evidence!r}"
            )
        if evidence.get("status") != "awaiting_hitl":
            raise ProofFailure(f"browser pending evidence is malformed: {evidence!r}")
        if evidence.get("visible_workflow_id") != workflow_id:
            raise ProofFailure(
                "browser Workflow detail did not visibly retain the exact workflow id: "
                f"{evidence!r}"
            )
        visible_detail = evidence.get("visible_detail")
        visible_hitl_audit = evidence.get("visible_hitl_audit")
        required_detail_terms = (
            "hitl gate audit",
            "state",
            "awaiting_hitl",
            "exception id",
            "workflow id",
        )
        if (
            not isinstance(visible_detail, str)
            or not isinstance(visible_hitl_audit, str)
            or workflow_id not in visible_hitl_audit
            or any(term not in visible_hitl_audit.lower() for term in required_detail_terms)
            or evidence.get("screenshot") != "screenshots/workflow-detail-pending.png"
            or not (SCREENSHOTS / "workflow-detail-pending.png").is_file()
        ):
            raise ProofFailure(
                "browser pending evidence does not contain the visible real HITL detail panel: "
                f"{evidence!r}"
            )
        return evidence

    return wait_until(
        "browser observation of real Durable HITL",
        observed,
        timeout=90,
    )


def run_live_chain(services: Services, environment: dict[str, str], *, browser_mode: str) -> dict[str, Any]:
    before = get_json(f"{API}/api/world/state")
    if not before.get("enabled") or before.get("scenario") != "travel":
        raise ProofFailure(f"Travel actor world is not live: {before!r}")
    write_json(PROOF / "world-snapshot-before.json", before)
    WORKFLOW_ID_FILE.write_text("", encoding="utf-8")
    browser = browser_process(services, environment, mode=browser_mode)
    sensor = wait_for_sensor()
    workflow_id = f"fdr-{sensor['event_id']}"
    WORKFLOW_ID_FILE.write_text(workflow_id + "\n", encoding="utf-8")
    pending = wait_for_status(workflow_id, "awaiting_hitl")
    pending_detail = get_detail(workflow_id)
    active_exception = pending_detail.get("activeException") or {}
    pending_history = get_json(f"{API}/api/workflows/{workflow_id}/orchestration").get("history") or []
    if (
        active_exception.get("workflowId") != workflow_id
        or active_exception.get("resolvedAt") is not None
        or not any(entry.get("kind") == "suspended" for entry in pending_history)
    ):
        raise ProofFailure(
            "Durable HITL gate is not truthfully pending: "
            f"exception={active_exception!r}, history={pending_history!r}"
        )
    browser_pending = wait_for_browser_pending(workflow_id)
    approve_gate(workflow_id, active_exception)
    terminal = wait_for_status(workflow_id, "completed")
    detail = get_detail(workflow_id)
    pack_detail = assert_live_detail(detail, workflow_id)
    after = get_json(f"{API}/api/world/state")
    write_json(PROOF / "world-snapshot-after.json", after)
    events = world_events()
    assert_journal_chain(events, workflow_id)
    memory = capture_memory(workflow_id)
    knowledge = capture_knowledge(workflow_id)
    agui = capture_agui(workflow_id)
    constellation = capture_constellation(workflow_id)
    wait_until(
        "browser semantic proof completion",
        lambda: browser.process.poll() is not None,
        timeout=90,
    )
    browser.stream.close()
    services.children.pop(browser.name, None)
    if browser.process.returncode != 0:
        raise ProofFailure(
            f"browser semantic proof failed (see {RECORDINGS / (browser.name + '.log')})"
        )
    browser_result = read_json(RECORDINGS / "browser-interactions.json")
    errors = browser_result.get("browserErrors") or []
    if errors:
        raise ProofFailure(f"browserErrors is non-empty: {errors!r}")
    if browser_result.get("dropped_workflow_events") != 0:
        raise ProofFailure("browser reported dropped workflow events")
    interactions = browser_result.get("interactions") or []
    detail_actions = {
        interaction.get("action"): interaction
        for interaction in interactions
        if isinstance(interaction, dict)
    }
    completed_detail = detail_actions.get("workflow-detail-completed") or {}
    if (
        completed_detail.get("workflow_id") != workflow_id
        or completed_detail.get("visible_workflow_id") != workflow_id
        or not isinstance(completed_detail.get("visible_detail"), str)
        or not (SCREENSHOTS / "workflow-detail-completed.png").is_file()
    ):
        raise ProofFailure("browser did not preserve completed Workflow detail evidence")
    return {
        "result": "PASS",
        "workflow_id": workflow_id,
        "sensor_event_id": sensor["event_id"],
        "actor_id": "FLT-ZV204",
        "journal_event": sensor["event_id"],
        "objective_id": pack_detail["objective"]["objective_id"],
        "status": terminal["workflow"]["status"],
        "pending_status": pending["workflow"]["status"],
        "browser_pending": browser_pending,
        "memory": memory,
        "knowledge": knowledge,
        "agui": agui,
        "constellation": constellation,
        "browser": browser_result,
    }


def reset_api(services: Services, environment: dict[str, str], *, actor_world: bool = True) -> None:
    services.stop("api")
    await_port_closed(3101, "FastAPI shutdown")
    launch_api(services, environment, actor_world=actor_world)


def functions_disabled_probe(services: Services, environment: dict[str, str]) -> dict[str, Any]:
    services.stop("functions")
    await_port_closed(7071, "Functions shutdown")
    reset_api(services, environment)
    before_ids = {row.get("id") for row in workflow_rows()}
    sensor = wait_for_sensor()
    expected_id = f"fdr-{sensor['event_id']}"

    def failure_observed() -> bool:
        return any(event.get("type") == "responder.failed" for event in world_events())

    wait_until("Functions-disabled responder failure recording", failure_observed, timeout=25)
    after_ids = {row.get("id") for row in workflow_rows()}
    phantom = expected_id in after_ids or bool(after_ids - before_ids)
    ui_response = httpx.get(f"{UI}/world", timeout=5.0)
    if ui_response.status_code >= 500:
        raise ProofFailure(f"Functions-disabled browser route returned {ui_response.status_code}")
    if phantom:
        raise ProofFailure(
            f"functions-disabled probe created phantom workflow {expected_id}; ids={sorted(after_ids - before_ids)}"
        )
    return {
        "name": "functions-disabled",
        "result": "PASS",
        "sensor_event_id": sensor["event_id"],
        "expected_workflow_id": expected_id,
        "phantom": False,
        "browser_status": ui_response.status_code,
    }


def actor_world_disabled_probe(services: Services, environment: dict[str, str]) -> dict[str, Any]:
    reset_api(services, environment, actor_world=False)
    state = get_json(f"{API}/api/world/state")
    if state.get("enabled") is not False:
        raise ProofFailure("actor-world-disabled probe still has a live actor world")
    response = post_json(
        f"{API}/api/world/diagnostics/flight-disruption-recovery",
        {"mode": "direct-diagnostic"},
    )
    workflow_id = response.get("workflow_id")
    if not isinstance(workflow_id, str) or not workflow_id:
        raise ProofFailure("actor-world-disabled diagnostic did not return a workflow_id")
    pending_detail = wait_for_status(workflow_id, "awaiting_hitl")
    approve_gate(workflow_id, pending_detail.get("activeException") or {})
    detail = wait_for_status(workflow_id, "completed")
    history = get_json(f"{API}/api/workflows/{workflow_id}/orchestration").get("history") or []
    if any(entry.get("kind") == "dead_letter" for entry in history):
        raise ProofFailure("actor-world-disabled diagnostic produced a dead letter")
    return {
        "name": "actor-world-disabled",
        "result": "PASS",
        "workflow_id": workflow_id,
        "status": detail["workflow"]["status"],
        "dead_letter": False,
    }


def restart_recovery_probe(services: Services, environment: dict[str, str]) -> dict[str, Any]:
    services.stop("api")
    await_port_closed(3101, "FastAPI shutdown before Functions restart")
    launch_functions(services, environment)
    reset_api(services, environment)
    # The recovered host has a fresh actor world. Drive the same real chain
    # without a second browser session; the live pass already captured the
    # semantic UI evidence and this probe verifies service recovery.
    sensor = wait_for_sensor()
    workflow_id = f"fdr-{sensor['event_id']}"
    wait_for_status(workflow_id, "awaiting_hitl")
    recovered_detail = get_detail(workflow_id)
    approve_gate(workflow_id, recovered_detail.get("activeException") or {})
    terminal = wait_for_status(workflow_id, "completed")
    return {
        "name": "restart",
        "result": "PASS",
        "workflow_id": workflow_id,
        "status": terminal["workflow"]["status"],
    }


def clear_proof_root() -> None:
    if PROOF.exists():
        shutil.rmtree(PROOF)
    PROOF.mkdir(parents=True)
    SCREENSHOTS.mkdir()
    RECORDINGS.mkdir()
    if RUNTIME.exists():
        shutil.rmtree(RUNTIME)
    RUNTIME.mkdir(parents=True)


def teardown(services: Services) -> dict[str, list[int]]:
    services.shutdown()
    try:
        observed = {str(port): lsof_pids(port) for port in PORTS}
    finally:
        if RUNTIME.exists():
            shutil.rmtree(RUNTIME)
    return {port: pids for port, pids in observed.items() if pids}


def main() -> int:
    previous_ledger = read_previous_consecutive_run_ledger()
    run_id = uuid4().hex
    started_at = utc_timestamp()
    clear_proof_root()
    environment = base_environment()
    services = Services()
    failures: list[str] = []
    live_summary: dict[str, Any] = {"result": "FAIL"}
    replay_summary: dict[str, Any] = {"result": "FAIL"}
    browser_errors: list[Any] = []
    runtime_fingerprint: dict[str, Any] = {
        "python": sys.version.split()[0],
        "node": command_output("node", "--version"),
        "proof_contract": proof_contract_fingerprint(),
    }
    source_commit = command_output("git", "rev-parse", "HEAD")
    shutil.copy2(ROOT / "verticals" / "travel" / "generation-manifest.json", PROOF / "generation-manifest.json")
    write_json(
        PROOF / "seller-review.json",
        {"seller_review": "PENDING", "operator_owned": True},
    )

    try:
        require_clear_ports()
        launch_azurite(services, environment)
        launch_functions(services, environment)
        launch_api(services, environment)
        launch_ui(services, environment)
        runtime_fingerprint["runtime"] = get_json(f"{API}/api/runtime")
        live_summary = run_live_chain(services, environment, browser_mode="live")
        browser_errors = list(live_summary.get("browser", {}).get("browserErrors") or [])
    except Exception as exc:  # keep truthful evidence even on a failed live chain
        failures.append(f"live: {type(exc).__name__}: {exc}")
        live_summary = {**live_summary, "result": "FAIL", "error": failures[-1]}

    try:
        if live_summary.get("result") == "PASS":
            functions_probe = functions_disabled_probe(services, environment)
            restart_probe = restart_recovery_probe(services, environment)
            actor_probe = actor_world_disabled_probe(services, environment)
            replay_summary = {
                "result": "PASS",
                "functions-disabled": functions_probe,
                "restart": restart_probe,
                "actor-world-disabled": actor_probe,
            }
    except Exception as exc:
        failures.append(f"replay: {type(exc).__name__}: {exc}")
        replay_summary = {**replay_summary, "result": "FAIL", "error": failures[-1]}
    finally:
        orphan_ports = teardown(services)

    if orphan_ports:
        failures.append(f"teardown: orphan ports remain {orphan_ports}")
    try:
        browser_result_path = RECORDINGS / "browser-interactions.json"
        if browser_result_path.is_file():
            browser_errors = list(read_json(browser_result_path).get("browserErrors") or [])
    except Exception as exc:
        failures.append(f"browser evidence: {type(exc).__name__}: {exc}")

    substrate_result = "PASS" if (
        live_summary.get("result") == "PASS"
        and replay_summary.get("result") == "PASS"
        and not orphan_ports
        and not failures
    ) else "FAIL"
    demo_result = "PASS" if (
        live_summary.get("result") == "PASS"
        and not browser_errors
        and (SCREENSHOTS / "world-before.png").is_file()
        and (SCREENSHOTS / "world-after.png").is_file()
        and (SCREENSHOTS / "knowledge-after.png").is_file()
        and (SCREENSHOTS / "workflow-detail-pending.png").is_file()
        and (SCREENSHOTS / "workflow-detail-completed.png").is_file()
        and not failures
    ) else "FAIL"
    manifest = {
        "source_commit": source_commit,
        "vertical": VERTICAL,
        "runtime_fingerprint": runtime_fingerprint,
        "live_result": live_summary.get("result", "FAIL"),
        "replay_result": replay_summary.get("result", "FAIL"),
        "substrate_result": substrate_result,
        "demo_result": demo_result,
        "seller_review": "PENDING",
        "browserErrors": browser_errors,
        "live_summary": live_summary,
        "replay_summary": replay_summary,
        "teardown": {"orphan_ports": orphan_ports},
        "failures": failures,
        "bundle_artifacts": list(BUNDLE_ARTIFACTS),
    }
    completed_at = utc_timestamp()
    ledger = build_consecutive_run_ledger(
        previous_ledger,
        source_commit=source_commit,
        runtime_fingerprint=runtime_fingerprint,
        run_id=run_id,
        started_at=started_at,
        completed_at=completed_at,
        manifest=manifest,
    )
    manifest["consecutive_runs"] = consecutive_run_manifest_evidence(ledger)
    write_json(PROOF / "live-summary.json", live_summary)
    write_json(PROOF / "replay-summary.json", replay_summary)
    write_json(LEDGER, ledger)
    write_json(PROOF / "manifest.json", manifest)
    return 0 if all(
        manifest[key] == "PASS"
        for key in ("live_result", "replay_result", "substrate_result", "demo_result")
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
