from pathlib import Path

from api.server.services.blueprint_recorder import BlueprintRecorder
from api.shared.events import FleetEvent


def test_workflow_failed_closes_recording_without_completion(monkeypatch):
    recorder = BlueprintRecorder()
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
