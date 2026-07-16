from pathlib import Path

from api.server.services.blueprint_recorder import (
    BlueprintRecorder,
    runtime_recordings_dir,
)
from api.shared.events import FleetEvent
from api.shared.vertical_loader import build_runtime


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
