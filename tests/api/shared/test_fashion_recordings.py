import json
from pathlib import Path

from verticals.fashion.process_profiles import FASHION_PROCESS_PROFILES


RECORDINGS_ROOT = (
    Path(__file__).resolve().parents[3]
    / "verticals"
    / "fashion"
    / "recordings"
)


def test_each_fashion_workflow_has_distinct_complete_curated_evidence() -> None:
    recordings = sorted(RECORDINGS_ROOT.glob("*.jsonl"))
    assert len(recordings) == 8
    observed: set[str] = set()

    for recording in recordings:
        entries = [
            json.loads(line)
            for line in recording.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        events = [entry["event"] for entry in entries]
        workflow_types = {event["workflow_type"] for event in events}
        assert len(workflow_types) == 1
        workflow_type = workflow_types.pop()
        profile = FASHION_PROCESS_PROFILES[workflow_type]
        observed.add(workflow_type)

        assert [event["type"] for event in events].count(
            "workflow.started"
        ) == 1
        assert [
            event["phase"]
            for event in events
            if event["type"] == "durable.step.completed"
        ] == [phase.name for phase in profile.phases]
        assert any(
            event["type"] == "typed.command.issued"
            and event["command_type"] == profile.command_type
            for event in events
        )
        assert any(
            event["type"] == "world.mutation.completed"
            and event["mutation_family"] == profile.mutation_family
            for event in events
        )
        assert any(
            event["type"] == "evaluation.completed"
            and event["status"] == "PASS"
            for event in events
        )
        assert events[-1]["type"] == "durable.workflow.completed"
        assert events[-1]["status"] == "completed"

    assert observed == set(FASHION_PROCESS_PROFILES)
