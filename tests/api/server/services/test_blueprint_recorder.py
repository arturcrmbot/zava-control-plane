import json
from dataclasses import replace
from pathlib import Path

from api.server.services.blueprint_recorder import (
    BlueprintRecorder,
    load_recorded_templates,
    runtime_recordings_dir,
)
from api.shared.events import FleetEvent
from api.shared.vertical_loader import build_runtime
from api.shared.vertical_pack import RecordingSources


def test_workflow_failed_closes_recording_without_completion(
    monkeypatch,
    tmp_path,
):
    runtime = build_runtime(
        {"ZAVA_VERTICAL": "telco"},
        data_root=tmp_path,
    )
    recorder = BlueprintRecorder(runtime)
    written = []

    def capture(recording):
        written.append(recording)
        return Path("failure.jsonl")

    monkeypatch.setattr(recorder, "_write_recording", capture)
    recorder._handle(
        FleetEvent(
            type="workflow.started",
            workflow_id="care-failed",
            workflow_type="proactive-customer-care",
        )
    )
    recorder._handle(
        FleetEvent(
            type="workflow.failed",
            workflow_id="care-failed",
            reason="approval denied",
        )
    )

    assert "care-failed" not in recorder._workflows
    assert "care-failed" in recorder._closed
    assert [entry["event"]["type"] for entry in written[0].events] == [
        "workflow.started",
        "workflow.failed",
    ]


def test_recordings_dir_accepts_isolated_override(monkeypatch, tmp_path):
    runtime = build_runtime({}, data_root=tmp_path)
    target = tmp_path / "recordings"
    monkeypatch.setenv("BLUEPRINT_RECORDINGS_DIR", str(target))

    assert runtime_recordings_dir(runtime) == target


def test_runtime_recording_loader_skips_malformed_and_foreign_files(
    monkeypatch,
    tmp_path,
):
    runtime = build_runtime(
        {"ZAVA_VERTICAL": "telco"},
        data_root=tmp_path,
    )
    runtime = replace(
        runtime,
        pack=replace(
            runtime.pack,
            recordings=RecordingSources(curated_dirs=()),
        ),
    )
    target = tmp_path / "recordings"
    target.mkdir()
    monkeypatch.setenv("BLUEPRINT_RECORDINGS_DIR", str(target))

    (target / "malformed.jsonl").write_text("{not-json}\n", encoding="utf-8")
    (target / "foreign.jsonl").write_text(
        json.dumps(
            {
                "ts_offset_ms": 0,
                "event": {
                    "type": "workflow.started",
                    "workflow_type": "hiring",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (target / "valid.jsonl").write_text(
        json.dumps(
            {
                "ts_offset_ms": 0,
                "event": {
                    "type": "workflow.started",
                    "workflow_type": "network-incident",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    templates = load_recorded_templates(runtime)

    assert [template["filename"] for template in templates] == ["valid.jsonl"]
