from __future__ import annotations

import asyncio
import json

from api.server.routes import workflows


def test_replay_snapshot_serves_captured_workflow_details(
    tmp_path,
    monkeypatch,
) -> None:
    detail = {
        "workflow": {
            "id": "AOGA-0001",
            "type": "aog-engineering-recovery",
            "status": "completed",
            "currentPhase": "Verify Recovery State",
            "agency": "Synthetic Airline Operations",
        },
        "phases": [{"name": "Detect AOG Event", "status": "completed"}],
        "spans": [],
        "amplifications": [],
        "activeException": None,
        "mcpCalls": [],
        "economics": {},
        "narrative": None,
        "timeline": [{"id": "workflow:AOGA-0001", "kind": "workflow"}],
        "auditBlobUrl": None,
        "packDetail": {"workflow_id": "AOGA-0001"},
    }
    snapshot = tmp_path / "workflow-replay-details.json"
    snapshot.write_text(
        json.dumps({
            "schemaVersion": 1,
            "vertical": "airline",
            "workflows": [detail],
        }),
        encoding="utf-8",
    )
    monkeypatch.setenv("ZAVA_REPLAY_WORKFLOW_DETAILS", str(snapshot))
    workflows._load_replay_workflow_details.cache_clear()

    listing = asyncio.run(workflows.list_workflows())
    fetched = asyncio.run(workflows.get_workflow("AOGA-0001"))

    assert listing == [detail["workflow"]]
    assert fetched == detail
